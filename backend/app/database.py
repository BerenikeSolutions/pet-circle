"""
PetCircle Phase 1 — Database Connection

Establishes SQLAlchemy engine and session factory using DATABASE_URL
from environment configuration. All database access flows through
the get_db() dependency to ensure proper session lifecycle management.

Connection strategy:
    - Supabase uses PgBouncer/Supavisor (port 6543) in transaction mode.
    - QueuePool with pool_pre_ping=True validates each connection before
      use, but cannot prevent the TOCTOU race where SSL drops after ping.
    - pool_recycle=120 refreshes connections aggressively — well under any
      idle-timeout Supabase/Supavisor might enforce server-side.
    - Pool (pool_size=5, max_overflow=10) keeps fewer idle connections alive,
      reducing the target surface for server-side SSL termination while still
      supporting burst webhook + background task concurrency.
    - keepalives settings prevent OS-level TCP idle drops on long queries.

No business logic lives here — only connection infrastructure.
"""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings

logger = logging.getLogger(__name__)


# Build connection args for SSL compatibility with Supabase.
connect_args = {}
if "supabase" in settings.DATABASE_URL:
    # Supabase requires SSL but psycopg2 needs keepalive settings
    # to prevent idle connection drops from PgBouncer.
    connect_args = {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    }

# SQLAlchemy engine — QueuePool with pre_ping to detect dead connections.
# pool_pre_ping disabled: with cross-region deployment (Render Oregon →
# Supabase Southeast), each pre-ping round-trip costs ~150ms per request.
# pool_recycle=120 + TCP keepalives handle dead-connection recovery instead.
# Re-enable if stale connection errors appear in production logs.
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_pre_ping=False,
    pool_size=15,       # Handles burst uploads (15 docs = 15 concurrent tasks)
    max_overflow=10,    # Hard cap at 25 total — headroom for 15 uploads + 8 extractions + dashboard
    pool_recycle=120,   # Refresh well before Supabase/Supavisor idle-timeout
    pool_timeout=30,
    connect_args=connect_args,
    # Disable SQL echo in production — only enable for debugging.
    echo=False,
)


@event.listens_for(engine, "checkout")
def _on_checkout(dbapi_conn, connection_rec, connection_proxy):
    """Log pool checkout events for monitoring connection usage."""
    logger.debug("DB connection checked out from pool")


# Session factory — autocommit and autoflush disabled for explicit transaction control.
# Every DB write must be committed explicitly to prevent silent data loss.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative base for all SQLAlchemy models.
# Every model in app/models/ must inherit from this base.
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Yields a session and ensures it is closed after the request completes,
    regardless of whether the request succeeded or raised an exception.
    Rolls back on errors to prevent dirty session state from poisoning
    subsequent requests.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_fresh_session() -> Session:
    """
    Create a fresh DB session for background tasks.

    Use this instead of raw SessionLocal() to ensure consistent
    configuration. Caller is responsible for closing the session.
    """
    return SessionLocal()


def safe_db_execute(db: Session, operation, max_retries: int = 1):
    """
    Execute a DB operation with retry on connection failure.

    If the connection has been dropped by PgBouncer/Supabase, this will
    rollback, close the dead session, create a new one, and retry once.

    Args:
        db: The current SQLAlchemy session.
        operation: A callable that takes a session and performs the DB work.
        max_retries: Number of retries on OperationalError (default 1).

    Returns:
        Tuple of (result, session) — session may be a new one if retry occurred.
    """
    try:
        result = operation(db)
        return result, db
    except OperationalError as e:
        logger.warning("DB operation failed (SSL/connection drop), retrying: %s", str(e))
        try:
            db.rollback()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass

        if max_retries > 0:
            new_db = SessionLocal()
            return safe_db_execute(new_db, operation, max_retries - 1)
        raise
