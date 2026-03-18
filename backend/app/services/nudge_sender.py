"""
PetCircle Phase 1 — Nudge Sender Service

Handles WhatsApp delivery of nudges with rate limiting, engagement
tracking, and inactivity detection.

Entry points:
    - send_pending_nudges(db): After cron — delivers highest-priority nudge per user
    - check_inactivity_nudges(db): Detect 30d inactive users and create re-engagement nudges
    - send_immediate_nudge(db, pet_id): Post-upload trigger — sends if rate limit allows
    - record_nudge_engagement(db, user_id, pet_id): On user action (button tap)
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.nudge import Nudge
from app.models.nudge_delivery_log import NudgeDeliveryLog
from app.models.nudge_engagement import NudgeEngagement
from app.models.pet import Pet
from app.models.user import User
from app.core.constants import (
    NUDGE_PRIORITY_ORDER,
    NUDGE_SOURCE_ORDER,
    NUDGE_TRIGGER_INACTIVITY,
)
from app.services.nudge_config_service import get_nudge_config_int

logger = logging.getLogger(__name__)

# WhatsApp template name for nudges — loaded from environment
WHATSAPP_TEMPLATE_NUDGE = os.getenv("WHATSAPP_TEMPLATE_NUDGE", "pet_health_nudge")


def _sort_key(n: Nudge):
    """Sort key: mandatory first → source (record > ai) → priority (urgent > high > medium)."""
    return (
        0 if n.mandatory else 1,
        NUDGE_SOURCE_ORDER.get(n.source or "record", 9),
        NUDGE_PRIORITY_ORDER.get(n.priority, 9),
    )


def send_pending_nudges(db: Session) -> dict:
    """
    Send pending nudges via WhatsApp after cron generation.

    For each user/pet combo with unsent nudges:
    1. Check rate limits via nudge_delivery_log
    2. Check engagement pause status
    3. Select highest-priority eligible nudge
    4. Send via WhatsApp template
    5. Log delivery and update engagement

    Returns summary dict.
    """
    from app.services.whatsapp_sender import send_template_message
    from app.core.encryption import decrypt_field

    # Get all unsent nudges grouped by pet
    pending = (
        db.query(Nudge)
        .filter(
            Nudge.wa_status.is_(None),
            Nudge.dismissed == False,
            Nudge.acted_on == False,
        )
        .all()
    )

    if not pending:
        return {"sent": 0, "skipped": 0, "failed": 0}

    # Group by pet_id
    by_pet: dict[str, list[Nudge]] = {}
    for n in pending:
        key = str(n.pet_id)
        by_pet.setdefault(key, []).append(n)

    sent = 0
    skipped = 0
    failed = 0

    for pet_id_str, nudges in by_pet.items():
        try:
            pet = db.query(Pet).filter(Pet.id == nudges[0].pet_id).first()
            if not pet or pet.is_deleted:
                continue

            user = db.query(User).filter(User.id == pet.user_id).first()
            if not user:
                continue

            # Check engagement pause
            engagement = (
                db.query(NudgeEngagement)
                .filter(NudgeEngagement.user_id == user.id, NudgeEngagement.pet_id == pet.id)
                .first()
            )
            if engagement and engagement.paused_until and engagement.paused_until > datetime.utcnow():
                for n in nudges:
                    n.wa_status = "skipped"
                skipped += len(nudges)
                db.commit()
                continue

            # Check rate limits
            if not _check_rate_limits(db, user.id):
                for n in nudges:
                    n.wa_status = "skipped"
                skipped += len(nudges)
                db.commit()
                continue

            # Sort and pick highest priority
            sorted_nudges = sorted(nudges, key=_sort_key)
            top_nudge = sorted_nudges[0]

            # Decrypt mobile
            plaintext_mobile = decrypt_field(user.mobile_number)

            # Bridge async WhatsApp send into sync context
            coro = send_template_message(
                db=db,
                to_number=plaintext_mobile,
                template_name=WHATSAPP_TEMPLATE_NUDGE,
                parameters=[pet.name, top_nudge.title, top_nudge.message],
            )

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                result = future.result(timeout=30)
            else:
                result = asyncio.run(coro)

            if result:
                top_nudge.wa_status = "sent"
                top_nudge.wa_sent_at = datetime.utcnow()
                top_nudge.wa_message_id = result.get("messages", [{}])[0].get("id")

                log = NudgeDeliveryLog(
                    nudge_id=top_nudge.id,
                    pet_id=pet.id,
                    user_id=user.id,
                    wa_status="sent",
                )
                db.add(log)
                _update_engagement_sent(db, user.id, pet.id)
                sent += 1
            else:
                top_nudge.wa_status = "failed"
                failed += 1

            # Mark remaining nudges as skipped (only 1 per cycle)
            for n in sorted_nudges[1:]:
                n.wa_status = "skipped"
                skipped += 1

            db.commit()

        except Exception:
            logger.exception("Failed to send nudge for pet %s", pet_id_str)
            try:
                db.rollback()
            except Exception:
                pass
            failed += 1

    logger.info("Nudge sender: sent=%d, skipped=%d, failed=%d", sent, skipped, failed)
    return {"sent": sent, "skipped": skipped, "failed": failed}


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
    Post-upload trigger — send the top-priority unsent nudge if rate limits allow.
    Called from async gpt_extraction context.
    """
    from app.services.nudge_engine import generate_nudges
    from app.services.whatsapp_sender import send_template_message
    from app.core.encryption import decrypt_field

    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        return {"sent": False, "reason": "pet_not_found"}

    user = db.query(User).filter(User.id == pet.user_id).first()
    if not user:
        return {"sent": False, "reason": "user_not_found"}

    if not _check_rate_limits(db, user.id):
        return {"sent": False, "reason": "rate_limited"}

    # Regenerate nudges first
    generate_nudges(db, pet_id)

    # Find top unsent nudge
    top = (
        db.query(Nudge)
        .filter(
            Nudge.pet_id == pet_id,
            Nudge.wa_status.is_(None),
            Nudge.dismissed == False,
            Nudge.acted_on == False,
        )
        .all()
    )

    if not top:
        return {"sent": False, "reason": "no_pending_nudges"}

    sorted_nudges = sorted(top, key=_sort_key)
    nudge = sorted_nudges[0]

    plaintext_mobile = decrypt_field(user.mobile_number)

    result = await send_template_message(
        db=db,
        to_number=plaintext_mobile,
        template_name=WHATSAPP_TEMPLATE_NUDGE,
        parameters=[pet.name, nudge.title, nudge.message],
    )

    if result:
        nudge.wa_status = "sent"
        nudge.wa_sent_at = datetime.utcnow()
        nudge.wa_message_id = result.get("messages", [{}])[0].get("id")
        nudge.trigger_type = "upload"

        log = NudgeDeliveryLog(
            nudge_id=nudge.id,
            pet_id=pet.id,
            user_id=user.id,
            wa_status="sent",
        )
        db.add(log)
        _update_engagement_sent(db, user.id, pet.id)
        db.commit()
        return {"sent": True, "nudge_title": nudge.title}

    nudge.wa_status = "failed"
    db.commit()
    return {"sent": False, "reason": "send_failed"}


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
