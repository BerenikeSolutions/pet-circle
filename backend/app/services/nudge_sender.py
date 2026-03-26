"""
PetCircle Phase 1 — Nudge Sender Service

Engagement tracking, inactivity detection, and rate-limit helpers.

NOTE (Excel v5): WhatsApp nudge delivery is now handled by nudge_scheduler.py
(Level 0/1/2 system). send_pending_nudges() and send_immediate_nudge() have
been removed from this file. Use nudge_scheduler.run_nudge_scheduler(db) instead.

Remaining entry points:
    - check_inactivity_nudges(db): Detect 30d inactive users, create re-engagement nudges
    - record_nudge_engagement(db, user_id, pet_id): On user action (button tap)
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.nudge import Nudge
from app.models.nudge_delivery_log import NudgeDeliveryLog
from app.models.nudge_engagement import NudgeEngagement
from app.models.pet import Pet
from app.models.user import User
from app.core.constants import NUDGE_TRIGGER_INACTIVITY
from app.services.nudge_config_service import get_nudge_config_int

logger = logging.getLogger(__name__)


def send_pending_nudges(db: Session) -> dict:
    """
    DEPRECATED — WhatsApp nudge delivery is now handled by nudge_scheduler.py.

    This stub is retained for backward-compat with any callers. Call
    nudge_scheduler.run_nudge_scheduler(db) instead.
    """
    logger.warning(
        "send_pending_nudges() is deprecated — use nudge_scheduler.run_nudge_scheduler(db) instead."
    )
    return {"sent": 0, "skipped": 0, "failed": 0}


def check_inactivity_nudges(db: Session) -> dict:
    """
    Find users with no activity in N days and create re-engagement nudges.

    Inactivity threshold is configured via nudge_config table.
    """
    threshold_days = get_nudge_config_int(db, "inactivity_threshold_days", 30)
    cutoff = datetime.utcnow() - timedelta(days=threshold_days)

    pets = (
        db.query(Pet)
        .join(User)
        .filter(
            Pet.is_deleted == False,
            User.onboarding_state == "complete",
        )
        .all()
    )

    created = 0
    for pet in pets:
        engagement = (
            db.query(NudgeEngagement)
            .filter(NudgeEngagement.user_id == pet.user_id, NudgeEngagement.pet_id == pet.id)
            .first()
        )

        # Skip if recently engaged or paused
        if engagement:
            if engagement.last_engagement_at and engagement.last_engagement_at > cutoff:
                continue
            if engagement.paused_until and engagement.paused_until > datetime.utcnow():
                continue

        # Check if we already have a recent inactivity nudge
        existing = (
            db.query(Nudge)
            .filter(
                Nudge.pet_id == pet.id,
                Nudge.trigger_type == NUDGE_TRIGGER_INACTIVITY,
                Nudge.dismissed == False,
                Nudge.created_at >= cutoff,
            )
            .first()
        )
        if existing:
            continue

        nudge = Nudge(
            pet_id=pet.id,
            category="checkup",
            priority="medium",
            icon="👋",
            title=f"We miss {pet.name}!",
            message=f"It's been a while since you checked in on {pet.name}'s health. Open the dashboard to review.",
            trigger_type=NUDGE_TRIGGER_INACTIVITY,
            source="record",
        )
        db.add(nudge)
        created += 1

    if created > 0:
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to create inactivity nudges")

    logger.info("Inactivity nudges created: %d", created)
    return {"inactivity_nudges_created": created}


def record_nudge_engagement(db: Session, user_id, pet_id):
    """
    Record that a user acted on a nudge (button tap).
    Clears pause, updates counters.
    """
    engagement = (
        db.query(NudgeEngagement)
        .filter(NudgeEngagement.user_id == user_id, NudgeEngagement.pet_id == pet_id)
        .first()
    )

    if engagement:
        engagement.last_engagement_at = datetime.utcnow()
        engagement.paused_until = None
        engagement.total_acted_on = (engagement.total_acted_on or 0) + 1
    else:
        engagement = NudgeEngagement(
            user_id=user_id,
            pet_id=pet_id,
            last_engagement_at=datetime.utcnow(),
            total_acted_on=1,
        )
        db.add(engagement)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record nudge engagement")


async def send_immediate_nudge(db: Session, pet_id) -> dict:
    """
    DEPRECATED — WhatsApp nudge delivery is now handled by nudge_scheduler.py.

    This stub is retained for backward-compat. The cron-driven scheduler
    (nudge_scheduler.run_nudge_scheduler) replaces per-upload immediate sends.
    """
    logger.warning(
        "send_immediate_nudge() is deprecated — nudge_scheduler handles WA delivery."
    )
    return {"sent": False, "reason": "deprecated"}


# ──────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────

def _check_rate_limits(db: Session, user_id) -> bool:
    """Check if user is within nudge rate limits (from nudge_config)."""
    max_24h = get_nudge_config_int(db, "max_per_24h", 1)
    max_7d = get_nudge_config_int(db, "max_per_7d", 3)

    now = datetime.utcnow()

    count_24h = (
        db.query(func.count(NudgeDeliveryLog.id))
        .filter(
            NudgeDeliveryLog.user_id == user_id,
            NudgeDeliveryLog.wa_status == "sent",
            NudgeDeliveryLog.sent_at >= now - timedelta(hours=24),
        )
        .scalar() or 0
    )

    if count_24h >= max_24h:
        return False

    count_7d = (
        db.query(func.count(NudgeDeliveryLog.id))
        .filter(
            NudgeDeliveryLog.user_id == user_id,
            NudgeDeliveryLog.wa_status == "sent",
            NudgeDeliveryLog.sent_at >= now - timedelta(days=7),
        )
        .scalar() or 0
    )

    if count_7d >= max_7d:
        return False

    return True


def _update_engagement_sent(db: Session, user_id, pet_id):
    """Increment total_nudges_sent counter in engagement table."""
    engagement = (
        db.query(NudgeEngagement)
        .filter(NudgeEngagement.user_id == user_id, NudgeEngagement.pet_id == pet_id)
        .first()
    )

    pause_days = get_nudge_config_int(db, "pause_days_if_inactive", 14)

    if engagement:
        engagement.total_nudges_sent = (engagement.total_nudges_sent or 0) + 1
        # Auto-pause if no engagement and sent too many
        if (engagement.total_acted_on or 0) == 0 and (engagement.total_nudges_sent or 0) >= 3:
            engagement.paused_until = datetime.utcnow() + timedelta(days=pause_days)
            logger.info("Pausing nudges for user %s pet %s for %d days", user_id, pet_id, pause_days)
    else:
        engagement = NudgeEngagement(
            user_id=user_id,
            pet_id=pet_id,
            total_nudges_sent=1,
        )
        db.add(engagement)
