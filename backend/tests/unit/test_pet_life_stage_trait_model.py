from app.models.pet import Pet
from app.models.pet_life_stage_trait import PetLifeStageTrait


def test_pet_life_stage_trait_unique_constraint_declared() -> None:
    unique_constraints = list(PetLifeStageTrait.__table__.constraints)
    target = [
        c
        for c in unique_constraints
        if getattr(c, "name", None) == "uq_pet_life_stage_trait_pet_stage"
    ]

    assert len(target) == 1
    assert {col.name for col in target[0].columns} == {"pet_id", "life_stage"}


def test_pet_relationship_wiring_for_life_stage_traits() -> None:
    pet_rel = Pet.__mapper__.relationships["life_stage_traits"]
    trait_rel = PetLifeStageTrait.__mapper__.relationships["pet"]

    assert pet_rel.mapper.class_ is PetLifeStageTrait
    assert trait_rel.mapper.class_ is Pet
    assert pet_rel.back_populates == "pet"
    assert trait_rel.back_populates == "life_stage_traits"
