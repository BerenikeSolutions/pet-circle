"""
Unit tests for signal_resolver.py — covers all food rules (A1-A6),
supplement rules (B1-B4), cross-cutting rules (OOS filtering, max 3 trim,
ranking), and edge cases.

Uses an in-memory SQLite database with real SQLAlchemy models so the
resolver's queries execute against actual data.
"""

import os
import uuid
from datetime import date, timedelta

import pytest

os.environ.setdefault("APP_ENV", "test")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.condition import Condition
from app.models.diet_item import DietItem
from app.models.pet import Pet
from app.models.product_food import ProductFood
from app.models.product_supplement import ProductSupplement
from app.services.signal_resolver import (
    CTA_ORDER_NOW,
    L1_MESSAGE,
    MAX_OPTIONS,
    SUPPLEMENT_L1_MESSAGE,
    SignalLevel,
    resolve_food_signal,
    resolve_supplement_signal,
)

# ---------------------------------------------------------------------------
# SQLite in-memory session fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    """Create a fresh in-memory SQLite DB per test.

    Only creates the tables needed by signal_resolver to avoid JSONB
    incompatibility from other models that use PostgreSQL-specific types.
    """
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    # Create only the tables we need — avoids JSONB errors from other models.
    tables = [
        ProductFood.__table__,
        ProductSupplement.__table__,
        DietItem.__table__,
        Pet.__table__,
        Condition.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def _make_pet(
    *,
    breed: str | None = None,
    dob: date | None = None,
    weight: float | None = None,
    species: str = "dog",
) -> Pet:
    """Create a detached Pet instance for testing (not added to any session)."""
    return Pet(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="TestPet",
        species=species,
        breed=breed,
        dob=dob,
        weight=weight,
    )


def _make_diet_item(
    *,
    type: str = "packaged",
    label: str = "",
    brand: str | None = None,
    detail: str | None = None,
    pack_size_g: int | None = None,
) -> DietItem:
    """Create a detached DietItem instance for testing."""
    return DietItem(
        id=uuid.uuid4(),
        pet_id=uuid.uuid4(),
        type=type,
        label=label,
        brand=brand,
        detail=detail,
        pack_size_g=pack_size_g,
    )


def _make_condition(name: str, is_active: bool = True) -> Condition:
    """Create a detached Condition instance for testing."""
    return Condition(
        id=uuid.uuid4(),
        pet_id=uuid.uuid4(),
        name=name,
        condition_type="chronic",
        source="manual",
        is_active=is_active,
    )


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def seed_food_products(db: Session) -> list[ProductFood]:
    """Insert a representative subset of food products."""
    products = [
        # Royal Canin — Labrador Adult line, 3 sizes
        ProductFood(
            sku_id="F001", brand_id="BR01", brand_name="Royal Canin",
            product_line="Labrador Adult", life_stage="Adult", breed_size="Large",
            pack_size_kg=12.0, mrp=7500, discounted_price=6800,
            condition_tags=None, breed_tags="labrador",
            vet_diet_flag=False, active=True, popularity_rank=1,
            monthly_units_sold=100, price_per_kg=567, in_stock=True,
        ),
        ProductFood(
            sku_id="F002", brand_id="BR01", brand_name="Royal Canin",
            product_line="Labrador Adult", life_stage="Adult", breed_size="Large",
            pack_size_kg=3.0, mrp=2200, discounted_price=1980,
            condition_tags=None, breed_tags="labrador",
            vet_diet_flag=False, active=True, popularity_rank=2,
            monthly_units_sold=80, price_per_kg=660, in_stock=True,
        ),
        ProductFood(
            sku_id="F003", brand_id="BR01", brand_name="Royal Canin",
            product_line="Labrador Adult", life_stage="Adult", breed_size="Large",
            pack_size_kg=7.0, mrp=4800, discounted_price=4300,
            condition_tags=None, breed_tags="labrador",
            vet_diet_flag=False, active=True, popularity_rank=3,
            monthly_units_sold=60, price_per_kg=614, in_stock=True,
        ),
        # Royal Canin — Medium Adult line
        ProductFood(
            sku_id="F004", brand_id="BR01", brand_name="Royal Canin",
            product_line="Medium Adult", life_stage="Adult", breed_size="Medium",
            pack_size_kg=4.0, mrp=2800, discounted_price=2500,
            condition_tags=None, breed_tags=None,
            vet_diet_flag=False, active=True, popularity_rank=4,
            monthly_units_sold=50, price_per_kg=625, in_stock=True,
        ),
        # Royal Canin — Pug Adult (breed-specific)
        ProductFood(
            sku_id="F005", brand_id="BR01", brand_name="Royal Canin",
            product_line="Pug Adult", life_stage="Adult", breed_size="Small",
            pack_size_kg=1.5, mrp=1200, discounted_price=1080,
            condition_tags=None, breed_tags="pug",
            vet_diet_flag=False, active=True, popularity_rank=5,
            monthly_units_sold=40, price_per_kg=720, in_stock=True,
        ),
        # Hills Science Diet — Sensitive Stomach (condition-tagged)
        ProductFood(
            sku_id="F006", brand_id="BR02", brand_name="Hills Science Diet",
            product_line="Sensitive Stomach", life_stage="Adult", breed_size="All",
            pack_size_kg=5.5, mrp=4200, discounted_price=3800,
            condition_tags="ibd,sensitive stomach,digestive",
            breed_tags=None,
            vet_diet_flag=True, active=True, popularity_rank=6,
            monthly_units_sold=35, price_per_kg=691, in_stock=True,
        ),
        # Hills Science Diet — Kidney Care (condition-tagged)
        ProductFood(
            sku_id="F007", brand_id="BR02", brand_name="Hills Science Diet",
            product_line="Kidney Care", life_stage="Senior", breed_size="All",
            pack_size_kg=3.5, mrp=3500, discounted_price=3200,
            condition_tags="kidney disease,ckd",
            breed_tags=None,
            vet_diet_flag=True, active=True, popularity_rank=7,
            monthly_units_sold=25, price_per_kg=914, in_stock=True,
        ),
        # Pedigree — Adult (budget, all breeds)
        ProductFood(
            sku_id="F008", brand_id="BR03", brand_name="Pedigree",
            product_line="Adult Complete", life_stage="Adult", breed_size="All",
            pack_size_kg=10.0, mrp=2000, discounted_price=1800,
            condition_tags=None, breed_tags=None,
            vet_diet_flag=False, active=True, popularity_rank=8,
            monthly_units_sold=200, price_per_kg=180, in_stock=True,
        ),
        # Drools — Puppy (small breed)
        ProductFood(
            sku_id="F009", brand_id="BR04", brand_name="Drools",
            product_line="Puppy Small Breed", life_stage="Puppy", breed_size="Small",
            pack_size_kg=3.0, mrp=900, discounted_price=810,
            condition_tags=None, breed_tags=None,
            vet_diet_flag=False, active=True, popularity_rank=9,
            monthly_units_sold=150, price_per_kg=270, in_stock=True,
        ),
        # Farmina — Senior Large (life stage + breed size)
        ProductFood(
            sku_id="F010", brand_id="BR05", brand_name="Farmina",
            product_line="Senior Large Breed", life_stage="Senior", breed_size="Large",
            pack_size_kg=12.0, mrp=8500, discounted_price=7650,
            condition_tags="joint,arthritis",
            breed_tags=None,
            vet_diet_flag=False, active=True, popularity_rank=10,
            monthly_units_sold=20, price_per_kg=638, in_stock=True,
        ),
    ]
    db.add_all(products)
    db.commit()
    return products


def seed_supplement_products(db: Session) -> list[ProductSupplement]:
    """Insert a representative subset of supplement products."""
    products = [
        ProductSupplement(
            sku_id="S001", brand_id="SB01", brand_name="Honst",
            product_name="Honst Fish Oil 300ml", type="fish_oil", form="liquid",
            pack_size="300 ml", mrp=800, discounted_price=720,
            key_ingredients="omega-3,EPA,DHA", condition_tags="skin,coat",
            life_stage_tags="Adult,Senior", active=True, popularity_rank=1,
            monthly_units=90, price_per_unit=720, in_stock=True,
        ),
        ProductSupplement(
            sku_id="S002", brand_id="SB01", brand_name="Honst",
            product_name="Honst Fish Oil 500ml", type="fish_oil", form="liquid",
            pack_size="500 ml", mrp=1200, discounted_price=1080,
            key_ingredients="omega-3,EPA,DHA", condition_tags="skin,coat",
            life_stage_tags="Adult,Senior", active=True, popularity_rank=2,
            monthly_units=60, price_per_unit=1080, in_stock=True,
        ),
        ProductSupplement(
            sku_id="S003", brand_id="SB02", brand_name="Vivaldis",
            product_name="Vivaldis Fish Oil 200ml", type="fish_oil", form="liquid",
            pack_size="200 ml", mrp=650, discounted_price=585,
            key_ingredients="omega-3,salmon oil", condition_tags="skin,coat",
            life_stage_tags="All", active=True, popularity_rank=3,
            monthly_units=50, price_per_unit=585, in_stock=True,
        ),
        ProductSupplement(
            sku_id="S004", brand_id="SB03", brand_name="Petvit",
            product_name="Petvit Fish Oil Capsules", type="fish_oil", form="capsule",
            pack_size="60 capsules", mrp=500, discounted_price=450,
            key_ingredients="omega-3", condition_tags="skin",
            life_stage_tags="All", active=True, popularity_rank=4,
            monthly_units=40, price_per_unit=450, in_stock=True,
        ),
        ProductSupplement(
            sku_id="S005", brand_id="SB01", brand_name="Honst",
            product_name="Honst Joint Support 90 chews", type="joint_supplement",
            form="chew", pack_size="90 chews", mrp=1500, discounted_price=1350,
            key_ingredients="glucosamine,chondroitin",
            condition_tags="joint,arthritis",
            life_stage_tags="Adult,Senior", active=True, popularity_rank=5,
            monthly_units=30, price_per_unit=1350, in_stock=True,
        ),
        ProductSupplement(
            sku_id="S006", brand_id="SB02", brand_name="Vivaldis",
            product_name="Vivaldis Joint Chews 60ct", type="joint_supplement",
            form="chew", pack_size="60 chews", mrp=1100, discounted_price=990,
            key_ingredients="glucosamine", condition_tags="joint",
            life_stage_tags="All", active=True, popularity_rank=6,
            monthly_units=25, price_per_unit=990, in_stock=True,
        ),
        ProductSupplement(
            sku_id="S007", brand_id="SB04", brand_name="NaturVet",
            product_name="NaturVet Joint Powder", type="joint_supplement",
            form="powder", pack_size="200 g", mrp=900, discounted_price=810,
            key_ingredients="glucosamine,MSM", condition_tags="joint,arthritis",
            life_stage_tags="Senior", active=True, popularity_rank=7,
            monthly_units=20, price_per_unit=810, in_stock=True,
        ),
        ProductSupplement(
            sku_id="S008", brand_id="SB01", brand_name="Honst",
            product_name="Honst Multivitamin Chews", type="multivitamin",
            form="chew", pack_size="120 chews", mrp=1000, discounted_price=900,
            key_ingredients="vitamins A,D,E,B12", condition_tags=None,
            life_stage_tags="All", active=True, popularity_rank=8,
            monthly_units=45, price_per_unit=900, in_stock=True,
        ),
        ProductSupplement(
            sku_id="S009", brand_id="SB02", brand_name="Vivaldis",
            product_name="Vivaldis Probiotic Powder", type="probiotic",
            form="powder", pack_size="100 g", mrp=750, discounted_price=675,
            key_ingredients="lactobacillus,bifidobacterium",
            condition_tags="digestive",
            life_stage_tags="All", active=True, popularity_rank=9,
            monthly_units=35, price_per_unit=675, in_stock=True,
        ),
        ProductSupplement(
            sku_id="S010", brand_id="SB03", brand_name="Petvit",
            product_name="Petvit Calming Drops", type="calming",
            form="liquid", pack_size="30 ml", mrp=600, discounted_price=540,
            key_ingredients="L-theanine,chamomile", condition_tags="anxiety",
            life_stage_tags="All", active=True, popularity_rank=10,
            monthly_units=15, price_per_unit=540, in_stock=True,
        ),
    ]
    db.add_all(products)
    db.commit()
    return products


# ===========================================================================
# FOOD RULE TESTS (A1 – A6)
# ===========================================================================


class TestFoodL5ExactMatch:
    """A1: brand + product_line + pack_size → L5, exact SKU + alts."""

    def test_exact_sku_returned(self, db):
        seed_food_products(db)
        pet = _make_pet(breed="Labrador", weight=30.0)
        item = _make_diet_item(
            label="Royal Canin Labrador Adult 12kg",
            brand="Royal Canin",
            pack_size_g=12000,
        )
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L5
        assert result.highlight_sku == "F001"
        assert result.products[0]["sku_id"] == "F001"
        assert result.products[0]["is_highlighted"] is True
        assert len(result.products) <= MAX_OPTIONS
        assert result.cta_label == CTA_ORDER_NOW

    def test_nearest_size_fallback(self, db):
        """A1.2: exact size not in DB → nearest size highlighted."""
        seed_food_products(db)
        pet = _make_pet(breed="Labrador", weight=30.0)
        # 10kg doesn't exist; nearest is 12kg (F001)
        item = _make_diet_item(
            label="Royal Canin Labrador Adult",
            brand="Royal Canin",
            detail="10 kg bag",
        )
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L5
        # Should still return products from the Labrador Adult line
        skus = {p["sku_id"] for p in result.products}
        assert skus & {"F001", "F002", "F003"}  # at least one from the line
        assert len(result.products) <= MAX_OPTIONS


class TestFoodL4PackSelector:
    """A2: brand + product_line, no size → L4, pack sizes sorted by popularity."""

    def test_brand_line_no_size(self, db):
        seed_food_products(db)
        pet = _make_pet(breed="Labrador", weight=30.0)
        item = _make_diet_item(
            label="Royal Canin Labrador Adult",
            brand="Royal Canin",
        )
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L4
        assert len(result.products) <= MAX_OPTIONS
        assert result.cta_label == CTA_ORDER_NOW
        # Products should be sorted by popularity_rank (ascending)
        ranks = [p["sku_id"] for p in result.products]
        assert ranks[0] == "F001"  # popularity_rank=1

    def test_max_3_sizes(self, db):
        """Ensure max 3 sizes returned even if more exist."""
        seed_food_products(db)
        # Add a 4th size for the same line
        db.add(ProductFood(
            sku_id="F099", brand_id="BR01", brand_name="Royal Canin",
            product_line="Labrador Adult", life_stage="Adult", breed_size="Large",
            pack_size_kg=1.5, mrp=1200, discounted_price=1080,
            condition_tags=None, breed_tags="labrador",
            vet_diet_flag=False, active=True, popularity_rank=15,
            monthly_units_sold=10, price_per_kg=720, in_stock=True,
        ))
        db.commit()

        pet = _make_pet(breed="Labrador", weight=30.0)
        item = _make_diet_item(
            label="Royal Canin Labrador Adult",
            brand="Royal Canin",
        )
        result = resolve_food_signal(db, item, pet)
        assert len(result.products) == MAX_OPTIONS  # exactly 3, not 4


class TestFoodL3BrandLines:
    """A3: brand only → L3, profile-ranked lines."""

    def test_brand_only(self, db):
        seed_food_products(db)
        pet = _make_pet(breed="Labrador", weight=30.0, dob=date.today() - timedelta(days=3*365))
        item = _make_diet_item(label="Royal Canin something", brand="Royal Canin")
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L3
        assert len(result.products) <= MAX_OPTIONS
        assert result.cta_label == CTA_ORDER_NOW
        # Each product should be a distinct product_line
        lines = [p["product_line"] for p in result.products]
        assert len(lines) == len(set(lines))


class TestFoodL2cConditionMatch:
    """A4 (condition): health condition → L2c, condition-matched products."""

    def test_condition_match(self, db):
        seed_food_products(db)
        pet = _make_pet(weight=15.0)  # no breed → skip L2b
        conditions = [_make_condition("IBD")]
        item = _make_diet_item(label="dog food")  # generic, no brand
        result = resolve_food_signal(db, item, pet, conditions)
        assert result.level == SignalLevel.L2C
        assert len(result.products) >= 1
        # F006 has condition_tags="ibd,sensitive stomach,digestive"
        skus = {p["sku_id"] for p in result.products}
        assert "F006" in skus


class TestFoodL2bBreedSpecific:
    """A5: breed known → L2b, breed-tagged products."""

    def test_breed_tag_match(self, db):
        seed_food_products(db)
        pet = _make_pet(breed="Pug", weight=8.0, dob=date.today() - timedelta(days=3*365))
        item = _make_diet_item(label="dog food")  # no brand
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L2B
        # F005 has breed_tags="pug"
        skus = {p["sku_id"] for p in result.products}
        assert "F005" in skus

    def test_fallback_breed_size(self, db):
        """No breed tag → fallback to breed_size category."""
        seed_food_products(db)
        # "Beagle" is in _SMALL_BREED_KEYWORDS but no product has breed_tags="beagle"
        pet = _make_pet(breed="Beagle", weight=12.0, dob=date.today() - timedelta(days=3*365))
        item = _make_diet_item(label="dog food")
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L2B
        # Should still return products matching Small breed_size
        assert len(result.products) >= 1


class TestFoodL2CategoryProfile:
    """A4 (profile): life stage/size → L2, top 3 brands."""

    def test_life_stage_profile(self, db):
        seed_food_products(db)
        # No breed → no L2b. No conditions → no L2c. Has DOB → triggers L2.
        pet = _make_pet(dob=date.today() - timedelta(days=3*365), weight=15.0)
        item = _make_diet_item(label="dog food")
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L2
        assert len(result.products) <= MAX_OPTIONS
        assert result.cta_label == CTA_ORDER_NOW


class TestFoodL1NoData:
    """A6: nothing known → L1, no products, prompt message."""

    def test_l1_empty(self, db):
        seed_food_products(db)
        # Pet with no breed, no DOB, no weight → L1
        pet = _make_pet()
        item = _make_diet_item(label="food")
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L1
        assert result.products == []
        assert result.message == L1_MESSAGE
        assert result.cta_label is None
        assert result.highlight_sku is None


# ===========================================================================
# SUPPLEMENT RULE TESTS (B1 – B4)
# ===========================================================================


class TestSupplementL5Exact:
    """B1: brand + type + pack_size → L5, exact SKU."""

    def test_exact_match(self, db):
        seed_supplement_products(db)
        pet = _make_pet()
        item = _make_diet_item(
            type="supplement",
            label="Honst Fish Oil",
            brand="Honst",
            detail="300 ml bottle",
        )
        result = resolve_supplement_signal(db, item, pet)
        assert result.level == SignalLevel.L5
        assert result.highlight_sku == "S001"
        assert result.products[0]["sku_id"] == "S001"
        assert result.products[0]["is_highlighted"] is True
        assert len(result.products) <= MAX_OPTIONS
        assert result.cta_label == CTA_ORDER_NOW

    def test_closest_variant(self, db):
        """B1.2: exact pack size not found → closest variant."""
        seed_supplement_products(db)
        pet = _make_pet()
        item = _make_diet_item(
            type="supplement",
            label="Honst Fish Oil",
            brand="Honst",
            detail="400 ml",  # doesn't exist
        )
        result = resolve_supplement_signal(db, item, pet)
        assert result.level == SignalLevel.L5
        # Should still return products from Honst fish_oil
        skus = {p["sku_id"] for p in result.products}
        assert skus & {"S001", "S002"}
        assert len(result.products) <= MAX_OPTIONS


class TestSupplementL4SizeSelector:
    """B2: brand + type → L4, sizes sorted by popularity."""

    def test_brand_type_no_size(self, db):
        seed_supplement_products(db)
        pet = _make_pet()
        item = _make_diet_item(
            type="supplement",
            label="Honst Fish Oil",
            brand="Honst",
        )
        result = resolve_supplement_signal(db, item, pet)
        assert result.level == SignalLevel.L4
        assert len(result.products) <= MAX_OPTIONS
        # Sorted by popularity_rank: S001 (rank 1), S002 (rank 2)
        assert result.products[0]["sku_id"] == "S001"
        assert result.cta_label == CTA_ORDER_NOW


class TestSupplementL3TypeOnly:
    """B3: type known → L3, 2 bestsellers + 1 budget."""

    def test_type_only(self, db):
        seed_supplement_products(db)
        pet = _make_pet()
        item = _make_diet_item(
            type="supplement",
            label="fish oil",  # type keyword, no brand
        )
        result = resolve_supplement_signal(db, item, pet)
        assert result.level == SignalLevel.L3
        assert len(result.products) <= MAX_OPTIONS
        assert result.cta_label == CTA_ORDER_NOW
        # Should have products from the fish_oil type
        assert all(p["type"] == "fish_oil" for p in result.products)


class TestSupplementL1Generic:
    """B4: generic mention → L1, no products."""

    def test_generic_supplements(self, db):
        """Generic mention like "supplements" → L1 (no identifiable type)."""
        seed_supplement_products(db)
        pet = _make_pet()
        item = _make_diet_item(
            type="supplement",
            label="supplements",
        )
        result = resolve_supplement_signal(db, item, pet)
        assert result.level == SignalLevel.L1
        assert result.products == []
        assert result.message == SUPPLEMENT_L1_MESSAGE
        assert result.cta_label is None


# ===========================================================================
# CROSS-CUTTING TESTS
# ===========================================================================


class TestOOSFiltering:
    """C2: OOS products excluded from primary position."""

    def test_oos_excluded_primary(self, db):
        """OOS product should not be first."""
        seed_food_products(db)
        # Make F001 (most popular) out of stock
        f001 = db.get(ProductFood, "F001")
        f001.in_stock = False
        db.commit()

        pet = _make_pet(breed="Labrador", weight=30.0)
        item = _make_diet_item(
            label="Royal Canin Labrador Adult",
            brand="Royal Canin",
        )
        result = resolve_food_signal(db, item, pet)
        # First product should be in-stock
        assert result.products[0]["in_stock"] is True

    def test_oos_all_products_fallback(self, db):
        """All matching OOS → show nearest in-stock (fallback keeps them)."""
        # Create products where all for a specific line are OOS
        db.add_all([
            ProductFood(
                sku_id="F050", brand_id="BR06", brand_name="TestBrand",
                product_line="TestLine", life_stage="Adult", breed_size="Medium",
                pack_size_kg=5.0, mrp=3000, discounted_price=2700,
                condition_tags=None, breed_tags=None,
                vet_diet_flag=False, active=True, popularity_rank=1,
                monthly_units_sold=10, price_per_kg=540, in_stock=False,
            ),
            ProductFood(
                sku_id="F051", brand_id="BR06", brand_name="TestBrand",
                product_line="TestLine", life_stage="Adult", breed_size="Medium",
                pack_size_kg=10.0, mrp=5000, discounted_price=4500,
                condition_tags=None, breed_tags=None,
                vet_diet_flag=False, active=True, popularity_rank=2,
                monthly_units_sold=5, price_per_kg=450, in_stock=False,
            ),
        ])
        db.commit()

        pet = _make_pet(weight=15.0)
        item = _make_diet_item(
            label="TestBrand TestLine",
            brand="TestBrand",
        )
        result = resolve_food_signal(db, item, pet)
        # Should still return the OOS products as fallback (C2 rule)
        assert len(result.products) >= 1


class TestMax3Trim:
    """C8: always trim to 3."""

    def test_max_3_food(self, db):
        """DB has >3 matches → only 3 returned."""
        # Add 5 products for same brand, different lines
        for i in range(5):
            db.add(ProductFood(
                sku_id=f"F06{i}", brand_id="BR07", brand_name="BigBrand",
                product_line=f"Line {i}", life_stage="Adult", breed_size="Medium",
                pack_size_kg=5.0, mrp=3000, discounted_price=2700,
                condition_tags=None, breed_tags=None,
                vet_diet_flag=False, active=True, popularity_rank=i + 1,
                monthly_units_sold=50, price_per_kg=540, in_stock=True,
            ))
        db.commit()

        pet = _make_pet(weight=15.0, dob=date.today() - timedelta(days=3*365))
        item = _make_diet_item(label="BigBrand kibble", brand="BigBrand")
        result = resolve_food_signal(db, item, pet)
        assert len(result.products) <= MAX_OPTIONS

    def test_max_3_supplement(self, db):
        """Supplement results also capped at 3."""
        # Add 5 supplements of same type
        for i in range(5):
            db.add(ProductSupplement(
                sku_id=f"S05{i}", brand_id=f"SB0{i}", brand_name=f"Brand{i}",
                product_name=f"Brand{i} Probiotic", type="probiotic",
                form="powder", pack_size="100 g",
                mrp=700 + i*100, discounted_price=630 + i*90,
                key_ingredients="lactobacillus", condition_tags=None,
                life_stage_tags="All", active=True, popularity_rank=i + 1,
                monthly_units=20, price_per_unit=630 + i*90, in_stock=True,
            ))
        db.commit()

        pet = _make_pet()
        item = _make_diet_item(type="supplement", label="probiotic")
        result = resolve_supplement_signal(db, item, pet)
        assert len(result.products) <= MAX_OPTIONS


class TestRankingOrder:
    """3.9: condition > life_stage > breed > popularity."""

    def test_condition_match_ranked_first(self, db):
        # Product with condition match vs without
        db.add_all([
            ProductFood(
                sku_id="F070", brand_id="BR08", brand_name="RankBrand",
                product_line="Line A", life_stage="Adult", breed_size="Medium",
                pack_size_kg=5.0, mrp=3000, discounted_price=2700,
                condition_tags="arthritis", breed_tags=None,
                vet_diet_flag=False, active=True, popularity_rank=10,
                monthly_units_sold=10, price_per_kg=540, in_stock=True,
            ),
            ProductFood(
                sku_id="F071", brand_id="BR09", brand_name="RankBrand2",
                product_line="Line B", life_stage="Adult", breed_size="Medium",
                pack_size_kg=5.0, mrp=2500, discounted_price=2250,
                condition_tags=None, breed_tags=None,
                vet_diet_flag=False, active=True, popularity_rank=1,
                monthly_units_sold=100, price_per_kg=450, in_stock=True,
            ),
        ])
        db.commit()

        pet = _make_pet(weight=15.0, dob=date.today() - timedelta(days=3*365))
        conditions = [_make_condition("Arthritis")]
        item = _make_diet_item(label="dog food")
        result = resolve_food_signal(db, item, pet, conditions)
        # With arthritis condition, F070 (condition_tags="arthritis") should rank higher
        assert result.level == SignalLevel.L2C
        assert result.products[0]["sku_id"] == "F070"


class TestSignalPriority:
    """L5 chosen over L4 when both possible."""

    def test_l5_over_l4(self, db):
        seed_food_products(db)
        pet = _make_pet(breed="Labrador", weight=30.0)
        # Full info: brand + line + size → should be L5, not L4
        item = _make_diet_item(
            label="Royal Canin Labrador Adult",
            brand="Royal Canin",
            pack_size_g=3000,
        )
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L5


# ===========================================================================
# EDGE CASES
# ===========================================================================


class TestEdgeCases:
    """Edge cases: empty fields, no products."""

    def test_empty_brand_field(self, db):
        """diet_item.brand is None, label has brand name."""
        seed_food_products(db)
        pet = _make_pet(breed="Labrador", weight=30.0)
        # brand=None but label contains "Royal Canin"
        item = _make_diet_item(
            label="Royal Canin Labrador Adult",
            brand=None,
        )
        result = resolve_food_signal(db, item, pet)
        # Should still detect Royal Canin from label
        assert result.level in (SignalLevel.L4, SignalLevel.L3)
        assert len(result.products) >= 1

    def test_empty_label(self, db):
        """Minimal diet_item with empty label."""
        seed_food_products(db)
        pet = _make_pet()
        item = _make_diet_item(label="", brand=None)
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L1
        assert result.products == []

    def test_no_products_in_db(self, db):
        """Empty product tables → L1."""
        pet = _make_pet(breed="Labrador", weight=30.0, dob=date.today() - timedelta(days=3*365))
        item = _make_diet_item(
            label="Royal Canin Labrador Adult 12kg",
            brand="Royal Canin",
            pack_size_g=12000,
        )
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L1
        assert result.products == []
        assert result.message == L1_MESSAGE

    def test_no_supplement_products_in_db(self, db):
        """Empty supplement table → L1."""
        pet = _make_pet()
        item = _make_diet_item(
            type="supplement",
            label="Honst Fish Oil 300ml",
            brand="Honst",
            detail="300 ml",
        )
        result = resolve_supplement_signal(db, item, pet)
        assert result.level == SignalLevel.L1
        assert result.products == []

    def test_inactive_products_excluded(self, db):
        """Inactive products should not appear in results."""
        db.add(ProductFood(
            sku_id="F080", brand_id="BR10", brand_name="InactiveBrand",
            product_line="Dead Line", life_stage="Adult", breed_size="Medium",
            pack_size_kg=5.0, mrp=3000, discounted_price=2700,
            condition_tags=None, breed_tags=None,
            vet_diet_flag=False, active=False, popularity_rank=1,
            monthly_units_sold=10, price_per_kg=540, in_stock=True,
        ))
        db.commit()

        pet = _make_pet(weight=15.0)
        item = _make_diet_item(
            label="InactiveBrand Dead Line",
            brand="InactiveBrand",
        )
        result = resolve_food_signal(db, item, pet)
        assert result.level == SignalLevel.L1
        assert result.products == []

    def test_supplement_form_as_hint(self, db):
        """Form is a soft hint — used when matches exist, ignored otherwise."""
        seed_supplement_products(db)
        pet = _make_pet()
        # Honst fish oil exists as liquid; request "chew" form
        item = _make_diet_item(
            type="supplement",
            label="Honst Fish Oil chew",
            brand="Honst",
            detail="300 ml",
        )
        result = resolve_supplement_signal(db, item, pet)
        # Should still return results (form hint is soft)
        assert result.level == SignalLevel.L5
        assert len(result.products) >= 1

    def test_serialization_fields_food(self, db):
        """Verify all expected fields in serialized food product."""
        seed_food_products(db)
        pet = _make_pet(breed="Labrador", weight=30.0)
        item = _make_diet_item(
            label="Royal Canin Labrador Adult 12kg",
            brand="Royal Canin",
            pack_size_g=12000,
        )
        result = resolve_food_signal(db, item, pet)
        product = result.products[0]
        expected_keys = {
            "sku_id", "category", "brand_name", "product_line", "pack_size",
            "pack_size_kg", "mrp", "discounted_price", "price_per_unit",
            "unit_label", "in_stock", "vet_diet_flag", "is_highlighted",
        }
        assert set(product.keys()) == expected_keys
        assert product["category"] == "food"
        assert product["unit_label"] == "per kg"

    def test_serialization_fields_supplement(self, db):
        """Verify all expected fields in serialized supplement product."""
        seed_supplement_products(db)
        pet = _make_pet()
        item = _make_diet_item(
            type="supplement",
            label="Honst Fish Oil",
            brand="Honst",
            detail="300 ml",
        )
        result = resolve_supplement_signal(db, item, pet)
        product = result.products[0]
        expected_keys = {
            "sku_id", "category", "brand_name", "product_name", "type",
            "form", "pack_size", "mrp", "discounted_price", "price_per_unit",
            "unit_label", "in_stock", "is_highlighted",
        }
        assert set(product.keys()) == expected_keys
        assert product["category"] == "supplement"
        assert product["unit_label"] == "per unit"
