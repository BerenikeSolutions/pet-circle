"""
PetCircle Phase 1 — FastAPI Application Entry Point

This is the main application module. It initializes the FastAPI app,
validates environment configuration at startup, registers routers,
and configures security middleware.

No business logic lives here — only app bootstrapping.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.constants import APP_API_TITLE
from app.routers import admin, dashboard, internal, webhook
from app.services.message_router import (
    start_document_window_sweeper,
    stop_document_window_sweeper,
)
from app.services import queue_service, document_consumer

# Application initialization.
# Settings are validated at import time (app/config.py).
# If any required env var is missing, the app crashes before reaching this point.
# Swagger/redoc disabled in production to avoid exposing full API schema.
app = FastAPI(
    title=APP_API_TITLE,
    description="WhatsApp-based preventive pet health system — Phase 1",
    version="1.0.0",
    docs_url=None if settings.APP_ENV == "production" else "/docs",
    redoc_url=None if settings.APP_ENV == "production" else "/redoc",
    openapi_url=None if settings.APP_ENV == "production" else "/openapi.json",
)

# --- CORS Middleware ---
# Restrict cross-origin requests to the frontend dashboard URL only.
# Allow localhost:3000 for local development and E2E testing.
_cors_origins = [settings.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-ADMIN-KEY"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all HTTP responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # Prevent browser/CDN caching of API responses containing sensitive data.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


# --- Register Routers ---
# Webhook router: /webhook/whatsapp (GET verify, POST messages)
app.include_router(webhook.router)
# Admin login router: /admin/login (password-based, no X-ADMIN-KEY required)
app.include_router(admin.login_router)
# Admin router: /admin/* (all routes require X-ADMIN-KEY header)
app.include_router(admin.router)
# Internal router: /internal/* (cron jobs, requires X-ADMIN-KEY header)
app.include_router(internal.router)
# Dashboard router: /dashboard/{token} (token-based access, no auth header)
app.include_router(dashboard.router)


@app.on_event("startup")
async def _start_background_reconciliation() -> None:
    """Start background reconciliation loops and the RabbitMQ consumer."""
    start_document_window_sweeper()
    # Connect to CloudAMQP and declare queues (no-op if CLOUDAMQP_URL not set).
    await queue_service.connect()
    # Start the in-process consumer as a background asyncio task.
    # Consumes document.extract and dashboard.precompute queues.
    # Store the task reference so stop() can cancel it on shutdown.
    import asyncio
    document_consumer._consumer_task = asyncio.create_task(
        document_consumer.start_consuming()
    )


@app.on_event("shutdown")
async def _stop_background_reconciliation() -> None:
    """Stop the RabbitMQ consumer and background reconciliation loops cleanly."""
    document_consumer.stop()
    await queue_service.close()
    await stop_document_window_sweeper()


@app.get("/health")
async def health_check():
    """
    Basic health check endpoint.

    Returns 200 OK to confirm the service is running
    and environment configuration is valid.
    Used for uptime monitoring.
    """
    return {
        "status": "healthy",
        "timezone": settings.TIMEZONE,
    }
