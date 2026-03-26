"""
PetCircle Phase 1 — Nudge Sender Service

Engagement tracking and inactivity detection.

WhatsApp nudge delivery (Excel v5) is handled by nudge_scheduler.py.

Entry points:
    - check_inactivity_nudges(db): Detect 30d inactive users, create re-engagement nudges
    - record_nudge_engagement(db, user_id, pet_id): On user action (button tap)
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.constants import NUDGE_TRIGGER_INACTIVITY
from app.models.nudge import Nudge
from app.models.nudge_engagement import NudgeEngagement
from app.models.pet import Pet
from app.models.user import User
from app.services.nudge_config_service import get_nudge_config_int

logger = logging.getLogger(__name__)


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
