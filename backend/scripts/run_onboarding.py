"""
run_onboarding.py — Simulates full WhatsApp onboarding for E2E testing.

Creates two test users via the onboarding service (same pattern as test_e2e.py):
  1. FULL_TOKEN: Zayn, Labrador, all values filled in
  2. EMPTY_TOKEN: Skippy, all optional steps skipped

Prints tokens to stdout in KEY=VALUE format for global-setup.ts to capture.
Usage:
    cd backend && python scripts/run_onboarding.py
"""

import sys
import os
import asyncio

# Add project root to path so app imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import User
from app.models.pet import Pet
from app.models.preventive_record import PreventiveRecord
from app.models.reminder import Reminder
from app.models.dashboard_token import DashboardToken
from app.models.document import Document
from app.models.conflict_flag import ConflictFlag
from app.models.diet_item import DietItem
from app.models.hygiene_preference import HygienePreference
from app.services.onboarding import create_pending_user, handle_onboarding_step
from app.core.encryption import hash_field

FULL_MOBILE = "15551657226"   # TEST_PHONE_NUMBER from .env.production
EMPTY_MOBILE = "15551657227"  # Secondary test slot (same base + 1)


def cleanup_user(db, mobile: str):
    """Remove test user and all related data."""
    existing = db.query(User).filter(User.mobile_hash == hash_field(mobile)).first()
    if not existing:
        return
    pets = db.query(Pet).filter(Pet.user_id == existing.id).all()
    for p in pets:
        db.query(DashboardToken).filter(DashboardToken.pet_id == p.id).delete()
        db.query(Document).filter(Document.pet_id == p.id).delete()
        try:
            db.query(DietItem).filter(DietItem.pet_id == p.id).delete()
        except Exception:
            pass
        try:
            db.query(HygienePreference).filter(HygienePreference.pet_id == p.id).delete()
        except Exception:
            pass
        recs = db.query(PreventiveRecord).filter(PreventiveRecord.pet_id == p.id).all()
        for rec in recs:
            db.query(Reminder).filter(Reminder.preventive_record_id == rec.id).delete()
            db.query(ConflictFlag).filter(ConflictFlag.preventive_record_id == rec.id).delete()
        db.query(PreventiveRecord).filter(PreventiveRecord.pet_id == p.id).delete()
    db.query(Pet).filter(Pet.user_id == existing.id).delete()
    db.query(User).filter(User.id == existing.id).delete()
    db.commit()


async def mock_send(db, to, text):
    """No-op send function — suppresses WhatsApp API calls during test."""
    pass


def run_onboarding(db, mobile: str, steps: list[tuple[str, str]]) -> str:
    """
    Run the onboarding state machine with the given steps.
    Each step is (label, input_text).
    Returns the dashboard token string.
    """
    user = create_pending_user(db, mobile)
    user._plaintext_mobile = mobile

    loop = asyncio.new_event_loop()
    try:
        for label, text in steps:
            loop.run_until_complete(handle_onboarding_step(db, user, text, mock_send))
            db.refresh(user)
    finally:
        loop.close()

    token_record = db.query(DashboardToken).join(Pet, Pet.id == DashboardToken.pet_id)\
        .join(User, User.id == Pet.user_id)\
        .filter(User.mobile_hash == hash_field(mobile))\
        .order_by(DashboardToken.created_at.desc())\
        .first()

    if not token_record:
        raise RuntimeError(f"No dashboard token found for mobile {mobile}")

    return token_record.token


def main():
    db = SessionLocal()
    try:
        # ── Clean up previous test data ──────────────────────────────────────
        print("Cleaning up previous test data...", file=sys.stderr)
        cleanup_user(db, FULL_MOBILE)
        cleanup_user(db, EMPTY_MOBILE)

        # ── RUN A: Full Zayn — every field filled in ─────────────────────────
        print("Running FULL onboarding (Zayn)...", file=sys.stderr)
        full_steps = [
            ("consent",       "yes"),
            ("name",          "Zayn Parent"),
            ("pincode",       "400016"),
            ("pet_name",      "Zayn"),
            ("pet_photo",     "skip"),          # skip photo (no media available)
            ("species",       "dog"),
            ("breed",         "Labrador Retriever"),
            ("gender",        "male"),
            ("dob",           "01/11/2021"),
            ("weight",        "28"),
            ("neutered",      "yes"),
            ("packaged_food", "Royal Canin Maxi Adult 3kg daily"),
            ("homemade_food", "Boiled chicken 200g rice morning"),
            ("supplements",   "Salmon oil 5ml daily"),
            ("grooming",      "Bath every 2 weeks, nail trim monthly, ear cleaning weekly"),
            ("documents",     "skip"),
        ]
        full_token = run_onboarding(db, FULL_MOBILE, full_steps)
        print(f"FULL onboarding complete. Token: {full_token[:8]}...", file=sys.stderr)

        # ── RUN B: Empty / skipped — minimal data ────────────────────────────
        print("Running EMPTY onboarding (Skippy)...", file=sys.stderr)
        empty_steps = [
            ("consent",       "yes"),
            ("name",          "Empty Test User"),
            ("pincode",       "skip"),
            ("pet_name",      "Skippy"),
            ("pet_photo",     "skip"),
            ("species",       "dog"),
            ("breed",         "skip"),
            ("gender",        "skip"),
            ("dob",           "skip"),
            ("weight",        "skip"),
            ("neutered",      "skip"),
            ("packaged_food", "skip"),
            ("homemade_food", "skip"),
            ("supplements",   "skip"),
            ("grooming",      "skip"),
            ("documents",     "skip"),
        ]
        empty_token = run_onboarding(db, EMPTY_MOBILE, empty_steps)
        print(f"EMPTY onboarding complete. Token: {empty_token[:8]}...", file=sys.stderr)

        # ── Output tokens to stdout for global-setup.ts ──────────────────────
        print(f"FULL_TOKEN={full_token}")
        print(f"EMPTY_TOKEN={empty_token}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
