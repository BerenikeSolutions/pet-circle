"""
PetCircle Phase 1 — Preventive Master Seeder (Module 6)

Seeds the frozen preventive master table with standard preventive
health items.

Current scope:
    - Dog items only.
    - Excludes grooming items.
    - Excludes dental and fecal test items.

Rules:
    - Insert missing canonical rows (idempotent — safe to re-run).
    - Enforce UNIQUE(item_name, species) via the table constraint.
    - All recurrence values are stored in the DB, never hardcoded in
      application logic — the seeder is the only place these appear.
    - This table is frozen after seeding. No runtime modifications.

Circle groupings are defined in SEED_DATA, and the effective seeded set is
filtered by current scope rules in seed_preventive_master().
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.preventive_master import PreventiveMaster

logger = logging.getLogger(__name__)


# --- Frozen Preventive Master Data ---
# This is the ONLY place recurrence values are defined.
# All application logic must read recurrence_days from the DB.
#
# Structure per entry:
#   item_name, category, circle, species, recurrence_days,
#   medicine_dependent, reminder_before_days, overdue_after_days
#
# Species "both" is expanded into separate "dog" and "cat" rows
# to satisfy the UNIQUE(item_name, species) constraint cleanly.
SEED_DATA: list[dict] = [
    # =============================
    # HEALTH CIRCLE
    # =============================

    # --- Rabies Vaccine ---
    # Essential for both dogs and cats. Annual recurrence (365 days).
    # Reminder 30 days before due, overdue after 7 days past due.
    {
        "item_name": "Rabies Vaccine",
        "category": "essential",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 7,
        "is_core": True,
        "is_mandatory": True,
    },
    {
        "item_name": "Rabies Vaccine",
        "category": "essential",
        "circle": "health",
        "species": "cat",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 7,
        "is_core": True,
        "is_mandatory": True,
    },
    # --- DHPPi (Dogs only) ---
    # Essential. Covers Distemper, Hepatitis, Parvovirus, Parainfluenza.
    # Alternate names: 7-in-1 / 9-in-1 vaccination.
    # Annual recurrence after completing puppy series. Reminder 30 days before, overdue after 7 days.
    {
        "item_name": "DHPPi",
        "category": "essential",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 7,
        "is_core": True,
        "is_mandatory": True,
    },
    # --- Feline Core (Cats only) ---
    # Essential. Covers FVRCP (Feline Viral Rhinotracheitis, Calicivirus, Panleukopenia).
    # Annual recurrence. Reminder 30 days before, overdue after 7 days.
    {
        "item_name": "Feline Core",
        "category": "essential",
        "circle": "health",
        "species": "cat",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 7,
        "is_core": True,
        "is_mandatory": True,
    },
    # --- Deworming ---
    # Essential for both dogs and cats. Quarterly (90 days).
    # Medicine-dependent — specific product matters.
    # Reminder 7 days before, overdue after 7 days.
    {
        "item_name": "Deworming",
        "category": "essential",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 90,
        "medicine_dependent": True,
        "reminder_before_days": 7,
        "overdue_after_days": 7,
        "is_core": True,
        "is_mandatory": True,
    },
    {
        "item_name": "Deworming",
        "category": "essential",
        "circle": "health",
        "species": "cat",
        "recurrence_days": 90,
        "medicine_dependent": True,
        "reminder_before_days": 7,
        "overdue_after_days": 7,
        "is_core": True,
        "is_mandatory": True,
    },
    # --- Annual Checkup ---
    # Complementary for both dogs and cats. Yearly (365 days).
    # Reminder 30 days before, overdue after 14 days.
    {
        "item_name": "Annual Checkup",
        "category": "complete",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },
    {
        "item_name": "Annual Checkup",
        "category": "complete",
        "circle": "health",
        "species": "cat",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },
    # --- Preventive Blood Test ---
    # Complementary for both dogs and cats. Yearly (365 days).
    # Reminder 30 days before, overdue after 14 days.
    {
        "item_name": "Preventive Blood Test",
        "category": "complete",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },
    {
        "item_name": "Preventive Blood Test",
        "category": "complete",
        "circle": "health",
        "species": "cat",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },
    # --- Chronic Care ---
    # Complementary for both dogs and cats. Semi-annual (180 days).
    # Covers ongoing condition management and veterinary follow-ups.
    # Reminder 14 days before, overdue after 14 days.
    {
        "item_name": "Chronic Care",
        "category": "complete",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 180,
        "medicine_dependent": False,
        "reminder_before_days": 14,
        "overdue_after_days": 14,
    },
    {
        "item_name": "Chronic Care",
        "category": "complete",
        "circle": "health",
        "species": "cat",
        "recurrence_days": 180,
        "medicine_dependent": False,
        "reminder_before_days": 14,
        "overdue_after_days": 14,
    },

    # =============================
    # NUTRITION CIRCLE
    # =============================

    # --- Food Ordering ---
    # Complementary for both dogs and cats. Monthly (30 days).
    # Reminder 5 days before, overdue after 3 days.
    {
        "item_name": "Food Ordering",
        "category": "complete",
        "circle": "nutrition",
        "species": "dog",
        "recurrence_days": 30,
        "medicine_dependent": False,
        "reminder_before_days": 5,
        "overdue_after_days": 3,
    },
    {
        "item_name": "Food Ordering",
        "category": "complete",
        "circle": "nutrition",
        "species": "cat",
        "recurrence_days": 30,
        "medicine_dependent": False,
        "reminder_before_days": 5,
        "overdue_after_days": 3,
    },
    # --- Nutrition Planning ---
    # Complementary for both dogs and cats. Semi-annual (180 days).
    # Covers diet review and meal plan adjustments.
    # Reminder 14 days before, overdue after 14 days.
    {
        "item_name": "Nutrition Planning",
        "category": "complete",
        "circle": "nutrition",
        "species": "dog",
        "recurrence_days": 180,
        "medicine_dependent": False,
        "reminder_before_days": 14,
        "overdue_after_days": 14,
    },
    {
        "item_name": "Nutrition Planning",
        "category": "complete",
        "circle": "nutrition",
        "species": "cat",
        "recurrence_days": 180,
        "medicine_dependent": False,
        "reminder_before_days": 14,
        "overdue_after_days": 14,
    },
    # --- Supplements ---
    # Complementary for both dogs and cats. Monthly (30 days).
    # Medicine-dependent — specific supplement matters.
    # Reminder 5 days before, overdue after 3 days.
    {
        "item_name": "Supplements",
        "category": "complete",
        "circle": "nutrition",
        "species": "dog",
        "recurrence_days": 30,
        "medicine_dependent": True,
        "reminder_before_days": 5,
        "overdue_after_days": 3,
    },
    {
        "item_name": "Supplements",
        "category": "complete",
        "circle": "nutrition",
        "species": "cat",
        "recurrence_days": 30,
        "medicine_dependent": True,
        "reminder_before_days": 5,
        "overdue_after_days": 3,
    },

    # =============================
    # HYGIENE CIRCLE
    # =============================

    # --- Bath & Grooming ---
    # Complementary for both dogs and cats. Bi-weekly (14 days).
    # Reminder 3 days before, overdue after 3 days.
    {
        "item_name": "Bath & Grooming",
        "category": "complete",
        "circle": "hygiene",
        "species": "dog",
        "recurrence_days": 14,
        "medicine_dependent": False,
        "reminder_before_days": 3,
        "overdue_after_days": 3,
    },
    {
        "item_name": "Bath & Grooming",
        "category": "complete",
        "circle": "hygiene",
        "species": "cat",
        "recurrence_days": 14,
        "medicine_dependent": False,
        "reminder_before_days": 3,
        "overdue_after_days": 3,
    },
    # --- Tick/Flea Prevention ---
    # Essential for both dogs and cats. Monthly (30 days).
    # Medicine-dependent — specific product matters.
    # Reminder 5 days before, overdue after 3 days.
    {
        "item_name": "Tick/Flea",
        "category": "essential",
        "circle": "hygiene",
        "species": "dog",
        "recurrence_days": 30,
        "medicine_dependent": True,
        "reminder_before_days": 5,
        "overdue_after_days": 3,
        "is_core": True,
        "is_mandatory": True,
    },
    {
        "item_name": "Tick/Flea",
        "category": "essential",
        "circle": "hygiene",
        "species": "cat",
        "recurrence_days": 30,
        "medicine_dependent": True,
        "reminder_before_days": 5,
        "overdue_after_days": 3,
        "is_core": True,
        "is_mandatory": True,
    },
    # --- Nail Trimming ---
    # Complementary for both dogs and cats. Every 3 weeks (21 days).
    # Reminder 3 days before, overdue after 7 days.
    {
        "item_name": "Nail Trimming",
        "category": "complete",
        "circle": "hygiene",
        "species": "dog",
        "recurrence_days": 21,
        "medicine_dependent": False,
        "reminder_before_days": 3,
        "overdue_after_days": 7,
    },
    {
        "item_name": "Nail Trimming",
        "category": "complete",
        "circle": "hygiene",
        "species": "cat",
        "recurrence_days": 21,
        "medicine_dependent": False,
        "reminder_before_days": 3,
        "overdue_after_days": 7,
    },
    # --- Ear Cleaning ---
    # Complementary for both dogs and cats. Bi-weekly (14 days).
    # Reminder 3 days before, overdue after 3 days.
    {
        "item_name": "Ear Cleaning",
        "category": "complete",
        "circle": "hygiene",
        "species": "dog",
        "recurrence_days": 14,
        "medicine_dependent": False,
        "reminder_before_days": 3,
        "overdue_after_days": 3,
    },
    {
        "item_name": "Ear Cleaning",
        "category": "complete",
        "circle": "hygiene",
        "species": "cat",
        "recurrence_days": 14,
        "medicine_dependent": False,
        "reminder_before_days": 3,
        "overdue_after_days": 3,
    },
    # --- Dental Check ---
    # Complementary for both dogs and cats. Yearly (365 days).
    # Reminder 30 days before, overdue after 14 days.
    {
        "item_name": "Dental Check",
        "category": "complete",
        "circle": "hygiene",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },
    {
        "item_name": "Dental Check",
        "category": "complete",
        "circle": "hygiene",
        "species": "cat",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },

    # =============================
    # ADDITIONAL CORE & OPTIONAL VACCINES
    # =============================

    # --- Kennel Cough / Nobivac KC (Dogs only) ---
    # Core vaccine covering Bordetella bronchiseptica + Parainfluenza.
    # Brand: Nobivac KC. Annual recurrence (365 days).
    # Always shown on dashboard alongside Rabies and DHPPi.
    {
        "item_name": "Kennel Cough (Nobivac KC)",
        "category": "essential",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
        "is_core": True,
    },
    # --- Canine Coronavirus / CCoV (Dogs only) ---
    # Core vaccine. Annual recurrence (365 days).
    # Protects against canine enteric coronavirus causing gastroenteritis.
    # Always shown on dashboard alongside Rabies and DHPPi.
    {
        "item_name": "Canine Coronavirus (CCoV)",
        "category": "essential",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
        "is_core": True,
    },
    # --- Leptospirosis (Dogs only) ---
    # Optional vaccine. Annual recurrence (365 days).
    # Recommended in areas with wildlife or standing water exposure.
    {
        "item_name": "Leptospirosis",
        "category": "complete",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },
    # --- Canine Influenza (Dogs only) ---
    # Optional vaccine. Annual recurrence (365 days).
    {
        "item_name": "Canine Influenza",
        "category": "complete",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },
    # --- FeLV — Feline Leukemia (Cats only) ---
    # Optional vaccine. Annual recurrence (365 days).
    # Recommended for outdoor or multi-cat households.
    {
        "item_name": "FeLV Vaccine",
        "category": "complete",
        "circle": "health",
        "species": "cat",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },
    # --- FIV — Feline Immunodeficiency (Cats only) ---
    # Optional vaccine. Annual recurrence (365 days).
    {
        "item_name": "FIV Vaccine",
        "category": "complete",
        "circle": "health",
        "species": "cat",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },

    # =============================
    # PUPPY VACCINATION SERIES (Dogs only — Mandatory)
    # =============================
    # One-time doses given at specific ages during puppyhood.
    # recurrence_days=36500 (100 years) marks these as effectively non-recurring.
    # After completing the series, the annual DHPPi and Rabies Vaccine items take over.
    # Alternate names for DHPPi: 7-in-1 / 9-in-1 vaccination.

    # --- DHPPi 1st Dose (6–8 weeks) ---
    {
        "item_name": "DHPPi 1st Dose",
        "category": "essential",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 36500,
        "medicine_dependent": False,
        "reminder_before_days": 14,
        "overdue_after_days": 21,
    },
    # --- DHPPi 2nd Dose (9–12 weeks) ---
    {
        "item_name": "DHPPi 2nd Dose",
        "category": "essential",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 36500,
        "medicine_dependent": False,
        "reminder_before_days": 14,
        "overdue_after_days": 21,
    },
    # --- DHPPi 3rd Dose (12–16 weeks, given together with first Rabies dose) ---
    {
        "item_name": "DHPPi 3rd Dose",
        "category": "essential",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 36500,
        "medicine_dependent": False,
        "reminder_before_days": 14,
        "overdue_after_days": 21,
    },
    # --- Puppy Booster (1 year — DHPPi & Rabies combined booster) ---
    # After this booster the pet transitions to the standard annual DHPPi + Rabies cycle.
    {
        "item_name": "Puppy Booster",
        "category": "essential",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 36500,
        "medicine_dependent": False,
        "reminder_before_days": 30,
        "overdue_after_days": 14,
    },

    # =============================
    # SPECIAL: BIRTHDAY CELEBRATION
    # =============================

    # --- Birthday Celebration ---
    # Special event for both dogs and cats to celebrate pet's birthday.
    # Annual recurrence (365 days). Only created if DOB is provided during onboarding.
    # Reminder 7 days before, overdue after 7 days past birthday date.
    {
        "item_name": "Birthday Celebration",
        "category": "complete",
        "circle": "health",
        "species": "dog",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 7,
        "overdue_after_days": 7,
    },
    {
        "item_name": "Birthday Celebration",
        "category": "complete",
        "circle": "health",
        "species": "cat",
        "recurrence_days": 365,
        "medicine_dependent": False,
        "reminder_before_days": 7,
        "overdue_after_days": 7,
    },
]


def seed_preventive_master(db: Session) -> int:
    """
    Seed the preventive_master table with frozen health items.

    This function is idempotent — it inserts only missing canonical rows.
    Existing rows are preserved and never overwritten.

    The effective seed scope is dog-only and excludes grooming/dental/fecal
    entries.

    Args:
        db: SQLAlchemy database session.

    Returns:
        Number of rows inserted (0 if table was already populated).
    """
    existing_pairs = {
        (row[0], row[1])
        for row in db.query(PreventiveMaster.item_name, PreventiveMaster.species).all()
    }

    excluded_item_names = {
        "Bath & Grooming",
        "Nail Trimming",
        "Ear Cleaning",
        "Dental Check",
        "Fecal Test",
        "Fecal Examination",
        "Stool Test",
    }

    # Insert allowed seed rows that are currently missing.
    inserted = 0
    for item_data in SEED_DATA:
        item_name = str(item_data["item_name"])
        key = (item_name, item_data["species"])

        if item_data["species"] != "dog":
            continue
        if item_name in excluded_item_names:
            continue
        if key in existing_pairs:
            continue

        nested = db.begin_nested()
        try:
            row = PreventiveMaster(
                item_name=item_data["item_name"],
                category=item_data["category"],
                circle=item_data["circle"],
                species=item_data["species"],
                recurrence_days=item_data["recurrence_days"],
                medicine_dependent=item_data["medicine_dependent"],
                reminder_before_days=item_data["reminder_before_days"],
                overdue_after_days=item_data["overdue_after_days"],
                is_core=item_data.get("is_core", False),
                is_mandatory=item_data.get("is_mandatory", False),
            )
            db.add(row)
            db.flush()
            nested.commit()
            existing_pairs.add(key)
            inserted += 1
        except IntegrityError:
            nested.rollback()
            logger.debug(
                "Preventive master row already exists during self-heal: %s/%s",
                item_data["item_name"],
                item_data["species"],
            )
        except Exception:
            nested.rollback()
            raise

    db.commit()
    logger.info(
        "Preventive master self-heal inserted %d missing row(s).",
        inserted,
    )

    return inserted
