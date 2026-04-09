"""
PetCircle — Product Catalog Seed Script (cart-rules-engine)

Seeds the two signal-level catalog tables:
    - product_food       (F001..F025, 25 rows)
    - product_supplement (S001..S016, 16 rows)

The data is embedded directly in this module (source of truth is
.spec/cart-rules-engine/tasks/task-002.md). The script uses upsert
semantics (ON CONFLICT (sku_id) DO UPDATE) so it is safe to re-run.

Usage:
    cd backend
    python -m scripts.seed_product_catalog
"""

import logging
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models.product_food import ProductFood
from app.models.product_supplement import ProductSupplement

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Food SKUs (25 rows) — F001..F025
# Columns match product_food. `None` is used for missing cells.
# ---------------------------------------------------------------------------
FOOD_ROWS: list[dict] = [
    {"sku_id": "F001", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Hypoallergenic", "life_stage": "All", "breed_size": "All", "pack_size_kg": 2, "mrp": 1690, "discounted_price": 1520, "condition_tags": "allergy,skin,hypoallergenic", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 3, "monthly_units_sold": 210, "price_per_kg": 760, "in_stock": True, "notes": "Prescription range"},
    {"sku_id": "F002", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Hypoallergenic", "life_stage": "All", "breed_size": "All", "pack_size_kg": 7, "mrp": 4990, "discounted_price": 4490, "condition_tags": "allergy,skin,hypoallergenic", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 1, "monthly_units_sold": 420, "price_per_kg": 641, "in_stock": True, "notes": "Most popular pack"},
    {"sku_id": "F003", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Hypoallergenic", "life_stage": "All", "breed_size": "All", "pack_size_kg": 14, "mrp": 8900, "discounted_price": 7990, "condition_tags": "allergy,skin,hypoallergenic", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 4, "monthly_units_sold": 85, "price_per_kg": 571, "in_stock": True, "notes": "Value pack"},
    {"sku_id": "F004", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Labrador Adult", "life_stage": "Adult", "breed_size": "Large", "pack_size_kg": 3, "mrp": 2100, "discounted_price": 1890, "condition_tags": "joint,weight", "breed_tags": "labrador", "vet_diet_flag": False, "popularity_rank": 2, "monthly_units_sold": 310, "price_per_kg": 630, "in_stock": False, "notes": "Breed-specific"},
    {"sku_id": "F005", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Labrador Adult", "life_stage": "Adult", "breed_size": "Large", "pack_size_kg": 12, "mrp": 7200, "discounted_price": 6480, "condition_tags": "joint,weight", "breed_tags": "labrador", "vet_diet_flag": False, "popularity_rank": 5, "monthly_units_sold": 90, "price_per_kg": 540, "in_stock": False, "notes": None},
    {"sku_id": "F006", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Large Adult", "life_stage": "Adult", "breed_size": "Large", "pack_size_kg": 4, "mrp": 2400, "discounted_price": 2160, "condition_tags": "joint,digestive", "breed_tags": "large_breed", "vet_diet_flag": False, "popularity_rank": 6, "monthly_units_sold": 180, "price_per_kg": 540, "in_stock": False, "notes": None},
    {"sku_id": "F007", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Large Puppy", "life_stage": "Puppy", "breed_size": "Large", "pack_size_kg": 4, "mrp": 2600, "discounted_price": 2340, "condition_tags": "growth", "breed_tags": "large_breed", "vet_diet_flag": False, "popularity_rank": 7, "monthly_units_sold": 150, "price_per_kg": 585, "in_stock": False, "notes": None},
    {"sku_id": "F008", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Renal", "life_stage": "All", "breed_size": "All", "pack_size_kg": 2, "mrp": 2100, "discounted_price": 1890, "condition_tags": "kidney,renal", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 8, "monthly_units_sold": 45, "price_per_kg": 945, "in_stock": True, "notes": "Prescription"},
    {"sku_id": "F009", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Renal", "life_stage": "All", "breed_size": "All", "pack_size_kg": 7, "mrp": 6500, "discounted_price": 5850, "condition_tags": "kidney,renal", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 9, "monthly_units_sold": 30, "price_per_kg": 836, "in_stock": True, "notes": None},
    {"sku_id": "F010", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Gastrointestinal", "life_stage": "All", "breed_size": "All", "pack_size_kg": 2, "mrp": 2200, "discounted_price": 1980, "condition_tags": "digestive,IBD,gastrointestinal", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 10, "monthly_units_sold": 60, "price_per_kg": 990, "in_stock": True, "notes": None},
    {"sku_id": "F011", "brand_id": "BR02", "brand_name": "Hills Science Diet", "product_line": "i/d Digestive", "life_stage": "All", "breed_size": "All", "pack_size_kg": 1.5, "mrp": 1800, "discounted_price": 1620, "condition_tags": "digestive,IBD", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 11, "monthly_units_sold": 55, "price_per_kg": 1080, "in_stock": True, "notes": None},
    {"sku_id": "F012", "brand_id": "BR02", "brand_name": "Hills Science Diet", "product_line": "k/d Kidney Care", "life_stage": "All", "breed_size": "All", "pack_size_kg": 1.5, "mrp": 2100, "discounted_price": 1890, "condition_tags": "kidney,renal", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 12, "monthly_units_sold": 40, "price_per_kg": 1260, "in_stock": True, "notes": "Prescription renal"},
    {"sku_id": "F013", "brand_id": "BR02", "brand_name": "Hills Science Diet", "product_line": "z/d Allergy", "life_stage": "All", "breed_size": "All", "pack_size_kg": 3.5, "mrp": 4200, "discounted_price": 3780, "condition_tags": "allergy,skin", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 13, "monthly_units_sold": 35, "price_per_kg": 1080, "in_stock": True, "notes": None},
    {"sku_id": "F014", "brand_id": "BR02", "brand_name": "Hills Science Diet", "product_line": "Large Breed Adult", "life_stage": "Adult", "breed_size": "Large", "pack_size_kg": 6, "mrp": 3800, "discounted_price": 3420, "condition_tags": "joint", "breed_tags": "large_breed", "vet_diet_flag": False, "popularity_rank": 14, "monthly_units_sold": 120, "price_per_kg": 570, "in_stock": False, "notes": None},
    {"sku_id": "F015", "brand_id": "BR02", "brand_name": "Hills Science Diet", "product_line": "Large Breed Puppy", "life_stage": "Puppy", "breed_size": "Large", "pack_size_kg": 6, "mrp": 4100, "discounted_price": 3690, "condition_tags": "growth", "breed_tags": "large_breed", "vet_diet_flag": False, "popularity_rank": 15, "monthly_units_sold": 95, "price_per_kg": 615, "in_stock": True, "notes": None},
    {"sku_id": "F016", "brand_id": "BR03", "brand_name": "Drools", "product_line": "Focus Adult Large", "life_stage": "Adult", "breed_size": "Large", "pack_size_kg": 3, "mrp": 1200, "discounted_price": 1080, "condition_tags": "joint", "breed_tags": "large_breed", "vet_diet_flag": False, "popularity_rank": 16, "monthly_units_sold": 380, "price_per_kg": 360, "in_stock": True, "notes": "Value India brand"},
    {"sku_id": "F017", "brand_id": "BR03", "brand_name": "Drools", "product_line": "Focus Adult Large", "life_stage": "Adult", "breed_size": "Large", "pack_size_kg": 12, "mrp": 4200, "discounted_price": 3780, "condition_tags": "joint", "breed_tags": "large_breed", "vet_diet_flag": False, "popularity_rank": 17, "monthly_units_sold": 160, "price_per_kg": 315, "in_stock": True, "notes": None},
    {"sku_id": "F018", "brand_id": "BR03", "brand_name": "Drools", "product_line": "Focus Puppy Large", "life_stage": "Puppy", "breed_size": "Large", "pack_size_kg": 3, "mrp": 1350, "discounted_price": 1215, "condition_tags": "growth", "breed_tags": "large_breed", "vet_diet_flag": False, "popularity_rank": 18, "monthly_units_sold": 290, "price_per_kg": 405, "in_stock": True, "notes": None},
    {"sku_id": "F019", "brand_id": "BR03", "brand_name": "Drools", "product_line": "Absolute Calcium", "life_stage": "Puppy", "breed_size": "All", "pack_size_kg": 3, "mrp": 1100, "discounted_price": 990, "condition_tags": "growth,bone", "breed_tags": "all", "vet_diet_flag": False, "popularity_rank": 19, "monthly_units_sold": 210, "price_per_kg": 330, "in_stock": True, "notes": None},
    {"sku_id": "F020", "brand_id": "BR04", "brand_name": "Pedigree", "product_line": "Adult", "life_stage": "Adult", "breed_size": "All", "pack_size_kg": 10, "mrp": 2200, "discounted_price": 1980, "condition_tags": None, "breed_tags": "all", "vet_diet_flag": False, "popularity_rank": 20, "monthly_units_sold": 850, "price_per_kg": 198, "in_stock": True, "notes": "Mass market"},
    {"sku_id": "F021", "brand_id": "BR04", "brand_name": "Pedigree", "product_line": "Puppy", "life_stage": "Puppy", "breed_size": "All", "pack_size_kg": 3, "mrp": 750, "discounted_price": 675, "condition_tags": "growth", "breed_tags": "all", "vet_diet_flag": False, "popularity_rank": 21, "monthly_units_sold": 620, "price_per_kg": 225, "in_stock": True, "notes": None},
    {"sku_id": "F022", "brand_id": "BR05", "brand_name": "Farmina N&D", "product_line": "GF Ancestral Grain Boar", "life_stage": "Adult", "breed_size": "Medium", "pack_size_kg": 3, "mrp": 3900, "discounted_price": 3510, "condition_tags": "skin,coat,grain_free", "breed_tags": "all", "vet_diet_flag": False, "popularity_rank": 22, "monthly_units_sold": 70, "price_per_kg": 1170, "in_stock": True, "notes": "Premium grain-free"},
    {"sku_id": "F023", "brand_id": "BR05", "brand_name": "Farmina N&D", "product_line": "Ocean Cod Puppy", "life_stage": "Puppy", "breed_size": "All", "pack_size_kg": 2.5, "mrp": 3200, "discounted_price": 2880, "condition_tags": "growth,skin", "breed_tags": "all", "vet_diet_flag": False, "popularity_rank": 23, "monthly_units_sold": 45, "price_per_kg": 1152, "in_stock": True, "notes": None},
    {"sku_id": "F024", "brand_id": "BR06", "brand_name": "Acana", "product_line": "Regionals Meadowland", "life_stage": "Adult", "breed_size": "All", "pack_size_kg": 2, "mrp": 3500, "discounted_price": 3150, "condition_tags": "skin,coat", "breed_tags": "all", "vet_diet_flag": False, "popularity_rank": 24, "monthly_units_sold": 30, "price_per_kg": 1575, "in_stock": True, "notes": "Super-premium import"},
    {"sku_id": "F025", "brand_id": "BR01", "brand_name": "Royal Canin", "product_line": "Satiety Weight Mgmt", "life_stage": "All", "breed_size": "All", "pack_size_kg": 1.5, "mrp": 1900, "discounted_price": 1710, "condition_tags": "obesity,weight", "breed_tags": "all", "vet_diet_flag": True, "popularity_rank": 25, "monthly_units_sold": 65, "price_per_kg": 1140, "in_stock": True, "notes": "Prescription weight"},
]


# ---------------------------------------------------------------------------
# Supplement SKUs (16 rows) — S001..S016
# Columns match product_supplement. `None` is used for missing cells.
# ---------------------------------------------------------------------------
SUPPLEMENT_ROWS: list[dict] = [
    {"sku_id": "S001", "brand_id": "SB01", "brand_name": "Honst", "product_name": "Fish Oil - Salmon 300ml", "type": "fish_oil", "form": "liquid", "pack_size": "300 ml", "mrp": 850, "discounted_price": 765, "key_ingredients": "Omega", "condition_tags": "coat,skin,joint,inflammation,omega3", "life_stage_tags": "adult,puppy", "popularity_rank": 1, "monthly_units": 340, "price_per_unit": 765, "in_stock": True, "notes": None},
    {"sku_id": "S002", "brand_id": "SB01", "brand_name": "Honst", "product_name": "Fish Oil - Salmon 150ml", "type": "fish_oil", "form": "liquid", "pack_size": "150 ml", "mrp": 499, "discounted_price": 449, "key_ingredients": "Fish Oil", "condition_tags": "coat,skin,joint,omega3", "life_stage_tags": "adult,puppy", "popularity_rank": 2, "monthly_units": 510, "price_per_unit": 449, "in_stock": True, "notes": "Starter size"},
    {"sku_id": "S003", "brand_id": "SB02", "brand_name": "Zesty Paws", "product_name": "Omega Bites - 90 chews", "type": "fish_oil", "form": "chew", "pack_size": "90 chews", "mrp": 1800, "discounted_price": 1620, "key_ingredients": "UC-II & Zinc", "condition_tags": "coat,skin,omega3", "life_stage_tags": "adult", "popularity_rank": 3, "monthly_units": 180, "price_per_unit": 1620, "in_stock": True, "notes": "Chew form"},
    {"sku_id": "S004", "brand_id": "SB02", "brand_name": "Zesty Paws", "product_name": "Mobility Bites - 90 chews", "type": "joint_supplement", "form": "chew", "pack_size": "90 chews", "mrp": 2100, "discounted_price": 1890, "key_ingredients": None, "condition_tags": "joint,hip,arthritis", "life_stage_tags": "senior,adult", "popularity_rank": 4, "monthly_units": 145, "price_per_unit": 1890, "in_stock": False, "notes": "Glucosamine + Chondroitin"},
    {"sku_id": "S005", "brand_id": "SB02", "brand_name": "Zesty Paws", "product_name": "Multivitamin Bites - 90", "type": "multivitamin", "form": "chew", "pack_size": "90 chews", "mrp": 1600, "discounted_price": 1440, "key_ingredients": None, "condition_tags": "immunity,general_health", "life_stage_tags": "adult,puppy", "popularity_rank": 5, "monthly_units": 220, "price_per_unit": 1440, "in_stock": False, "notes": None},
    {"sku_id": "S006", "brand_id": "SB03", "brand_name": "Beaphar", "product_name": "Puppy Milk", "type": "milk_replacer", "form": "powder", "pack_size": "500 g", "mrp": 900, "discounted_price": 810, "key_ingredients": None, "condition_tags": "growth,nutrition", "life_stage_tags": "puppy", "popularity_rank": 6, "monthly_units": 90, "price_per_unit": 810, "in_stock": False, "notes": "For puppies < 6 weeks"},
    {"sku_id": "S007", "brand_id": "SB03", "brand_name": "Beaphar", "product_name": "Multivitamin Syrup", "type": "multivitamin", "form": "liquid", "pack_size": "200 ml", "mrp": 650, "discounted_price": 585, "key_ingredients": None, "condition_tags": "immunity,general_health", "life_stage_tags": "adult,puppy,senior", "popularity_rank": 7, "monthly_units": 210, "price_per_unit": 585, "in_stock": False, "notes": None},
    {"sku_id": "S008", "brand_id": "SB04", "brand_name": "Drools", "product_name": "Absolute Boneup - 500g", "type": "joint_supplement", "form": "powder", "pack_size": "500 g", "mrp": 750, "discounted_price": 675, "key_ingredients": None, "condition_tags": "joint,bone", "life_stage_tags": "senior,large_breed", "popularity_rank": 8, "monthly_units": 320, "price_per_unit": 675, "in_stock": True, "notes": "Calcium + Phosphorus"},
    {"sku_id": "S009", "brand_id": "SB05", "brand_name": "Himalaya", "product_name": "Erina EP Coat Supplement", "type": "coat_supplement", "form": "liquid", "pack_size": "200 ml", "mrp": 280, "discounted_price": 252, "key_ingredients": None, "condition_tags": "coat,skin", "life_stage_tags": "adult", "popularity_rank": 9, "monthly_units": 480, "price_per_unit": 252, "in_stock": True, "notes": "Affordable India brand"},
    {"sku_id": "S010", "brand_id": "SB06", "brand_name": "NutriVet", "product_name": "Joint Health Chews - 60", "type": "joint_supplement", "form": "chew", "pack_size": "60 chews", "mrp": 1400, "discounted_price": 1260, "key_ingredients": None, "condition_tags": "joint,hip", "life_stage_tags": "senior", "popularity_rank": 10, "monthly_units": 95, "price_per_unit": 1260, "in_stock": True, "notes": None},
    {"sku_id": "S011", "brand_id": "SB07", "brand_name": "Virbac", "product_name": "Megaderm - 250 ml", "type": "skin_supplement", "form": "liquid", "pack_size": "250 ml", "mrp": 1100, "discounted_price": 990, "key_ingredients": None, "condition_tags": "skin,allergy,coat,omega6", "life_stage_tags": "adult", "popularity_rank": 11, "monthly_units": 75, "price_per_unit": 990, "in_stock": True, "notes": "Dermatology-grade"},
    {"sku_id": "S012", "brand_id": "SB07", "brand_name": "Virbac", "product_name": "Pronefra - 180 ml", "type": "kidney_supplement", "form": "liquid", "pack_size": "180 ml", "mrp": 1800, "discounted_price": 1620, "key_ingredients": None, "condition_tags": "kidney,renal", "life_stage_tags": "adult,senior", "popularity_rank": 12, "monthly_units": 30, "price_per_unit": 1620, "in_stock": True, "notes": "Vet-grade phosphate binder"},
    {"sku_id": "S013", "brand_id": "SB08", "brand_name": "Vet Activ", "product_name": "Probiotic Paste - 30g", "type": "probiotic", "form": "paste", "pack_size": "30 g", "mrp": 750, "discounted_price": 675, "key_ingredients": None, "condition_tags": "digestive,gut_health", "life_stage_tags": "adult,puppy,senior", "popularity_rank": 13, "monthly_units": 165, "price_per_unit": 675, "in_stock": True, "notes": None},
    {"sku_id": "S014", "brand_id": "SB08", "brand_name": "Vet Activ", "product_name": "Urinary Care - 100 tabs", "type": "urinary_supplement", "form": "tablet", "pack_size": "100 tabs", "mrp": 1200, "discounted_price": 1080, "key_ingredients": None, "condition_tags": "urinary,bladder", "life_stage_tags": "adult", "popularity_rank": 14, "monthly_units": 55, "price_per_unit": 1080, "in_stock": False, "notes": "D-mannose + cranberry"},
    {"sku_id": "S015", "brand_id": "SB09", "brand_name": "Venkys", "product_name": "Gro Pet - 500g", "type": "growth_supplement", "form": "powder", "pack_size": "500 g", "mrp": 650, "discounted_price": 585, "key_ingredients": None, "condition_tags": "growth,bone", "life_stage_tags": "puppy", "popularity_rank": 15, "monthly_units": 190, "price_per_unit": 585, "in_stock": True, "notes": "Value puppy supplement"},
    {"sku_id": "S016", "brand_id": "SB10", "brand_name": "Pet Health", "product_name": "CBD Calming Chews - 30", "type": "calming", "form": "chew", "pack_size": "30 chews", "mrp": 2200, "discounted_price": 1980, "key_ingredients": None, "condition_tags": "anxiety,stress,behaviour", "life_stage_tags": "adult,senior", "popularity_rank": 16, "monthly_units": 40, "price_per_unit": 1980, "in_stock": True, "notes": "New category"},
]


# Columns updated by ON CONFLICT for each table (everything except the PK)
_FOOD_UPDATE_COLS = [
    "brand_id", "brand_name", "product_line", "life_stage", "breed_size",
    "pack_size_kg", "mrp", "discounted_price", "condition_tags", "breed_tags",
    "vet_diet_flag", "active", "popularity_rank", "monthly_units_sold",
    "price_per_kg", "in_stock", "notes",
]
_SUPPLEMENT_UPDATE_COLS = [
    "brand_id", "brand_name", "product_name", "type", "form", "pack_size",
    "mrp", "discounted_price", "key_ingredients", "condition_tags",
    "life_stage_tags", "active", "popularity_rank", "monthly_units",
    "price_per_unit", "in_stock", "notes",
]


def _upsert(db, table, rows: list[dict], update_cols: list[str]) -> None:
    """Upsert all rows into the given table by primary key sku_id."""
    for row in rows:
        # Ensure `active` column always has a value; default True.
        row.setdefault("active", True)
        stmt = pg_insert(table).values(**row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["sku_id"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        db.execute(stmt)


def seed() -> None:
    """Insert (or update) all food and supplement SKUs."""
    if len(FOOD_ROWS) != 25:
        raise RuntimeError(f"Expected 25 food rows, got {len(FOOD_ROWS)}")
    if len(SUPPLEMENT_ROWS) != 16:
        raise RuntimeError(f"Expected 16 supplement rows, got {len(SUPPLEMENT_ROWS)}")

    db = SessionLocal()
    try:
        logger.info("Seeding %d food SKUs...", len(FOOD_ROWS))
        _upsert(db, ProductFood.__table__, FOOD_ROWS, _FOOD_UPDATE_COLS)

        logger.info("Seeding %d supplement SKUs...", len(SUPPLEMENT_ROWS))
        _upsert(db, ProductSupplement.__table__, SUPPLEMENT_ROWS, _SUPPLEMENT_UPDATE_COLS)

        db.commit()

        food_count = db.query(ProductFood).count()
        supplement_count = db.query(ProductSupplement).count()
        logger.info(
            "Seed complete: product_food=%d, product_supplement=%d",
            food_count, supplement_count,
        )
    except Exception:
        db.rollback()
        logger.exception("Seed failed — rolled back")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
