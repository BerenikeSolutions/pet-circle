"""
PetCircle Phase 1 — Nutrition Analysis Service

Computes detailed nutrition breakdown based on a pet's diet items
matched against the product catalog. Identifies gaps relative to
breed-specific targets and generates recommendations.
"""

import logging
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.diet_item import DietItem
from app.models.product_catalog import ProductCatalog
from app.models.pet import Pet
from app.models.condition import Condition

logger = logging.getLogger(__name__)

# Breed-specific nutritional targets
BREED_TARGETS = {
    "golden retriever": {
        "calories": 1450,
        "protein": 30,
        "fat": 15,
        "carbs": 45,
        "fibre": 4,
        "moisture": 10,
        "calcium": 1.2,
        "phosphorus": 1.0,
        "omega_3": 500,
        "omega_6": 2000,
        "vitamin_e": 400,
        "vitamin_d3": 500,
        "glucosamine": 1200,
        "probiotics": True,
    },
}

DEFAULT_TARGETS = {
    "calories": 1200,
    "protein": 25,
    "fat": 14,
    "carbs": 50,
    "fibre": 4,
    "moisture": 10,
    "calcium": 1.0,
    "phosphorus": 0.8,
    "omega_3": 300,
    "omega_6": 1500,
    "vitamin_e": 300,
    "vitamin_d3": 400,
    "glucosamine": 500,
    "probiotics": False,
}


def _status_for_ratio(ratio: float) -> str:
    """Determine status based on actual/target ratio."""
    if ratio >= 0.9:
        return "Adequate"
    elif ratio >= 0.6:
        return "Low"
    else:
        return "Missing"


def _priority_for_status(status: str, is_critical: bool = False) -> str:
    """Determine priority based on status."""
    if status == "Missing":
        return "urgent" if is_critical else "high"
    elif status == "Low":
        return "high" if is_critical else "medium"
    return "ok"


async def analyze_nutrition(db: Session, pet_id) -> dict:
    """
    Analyze a pet's nutrition based on their diet items and product catalog data.

    Returns a comprehensive breakdown with macros, vitamins, minerals,
    and improvement recommendations.
    """
    # Get pet info
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise ValueError("Pet not found")

    breed_key = (pet.breed or "").lower().strip()
    targets = BREED_TARGETS.get(breed_key, DEFAULT_TARGETS)

    # Get conditions for context-aware recommendations
    conditions = (
        db.query(Condition)
        .filter(Condition.pet_id == pet_id, Condition.is_active == True)
        .all()
    )
    condition_names = [c.name.lower() for c in conditions]
    has_hip_dysplasia = any("hip" in c or "dysplasia" in c for c in condition_names)

    # Get diet items
    diet_items = (
        db.query(DietItem)
        .filter(DietItem.pet_id == pet_id)
        .all()
    )

    # Match diet items to product catalog
    actual = {
        "calories": 0, "protein": 0, "fat": 0, "fibre": 0, "moisture": 0,
        "calcium": 0, "phosphorus": 0, "omega_3": 0, "omega_6": 0,
        "vitamin_e": 0, "vitamin_d3": 0, "glucosamine": 0, "probiotics": False,
    }

    matched_products = []
    for item in diet_items:
        # Try to match by product_name containing the label or vice versa
        product = (
            db.query(ProductCatalog)
            .filter(
                ProductCatalog.category == "food",
                func.lower(ProductCatalog.product_name).contains(item.label.lower()[:30])
            )
            .first()
        )
        if not product:
            # Try reverse match
            product = (
                db.query(ProductCatalog)
                .filter(
                    ProductCatalog.category == "food",
                    func.lower(item.label).contains(func.lower(ProductCatalog.brand))
                )
                .first()
            )

        if product:
            matched_products.append(product)
            if product.crude_protein:
                actual["protein"] = max(actual["protein"], float(product.crude_protein))
            if product.crude_fat:
                actual["fat"] = max(actual["fat"], float(product.crude_fat))
            if product.crude_fibre:
                actual["fibre"] = max(actual["fibre"], float(product.crude_fibre))
            if product.moisture:
                actual["moisture"] = max(actual["moisture"], float(product.moisture))
            if product.energy_kcal:
                actual["calories"] += int(product.energy_kcal * 0.28)  # Rough portion estimate
            if product.calcium:
                actual["calcium"] = max(actual["calcium"], float(product.calcium))
            if product.phosphorus:
                actual["phosphorus"] = max(actual["phosphorus"], float(product.phosphorus))
            if product.omega_3:
                actual["omega_3"] += product.omega_3
            if product.omega_6:
                actual["omega_6"] += product.omega_6
            if product.vitamin_e:
                actual["vitamin_e"] += product.vitamin_e
            if product.vitamin_d3:
                actual["vitamin_d3"] += product.vitamin_d3
            if product.glucosamine:
                actual["glucosamine"] += product.glucosamine
            if product.probiotics and product.probiotics != "-":
                actual["probiotics"] = True

    # If no products matched, provide estimates for homemade food
    if not matched_products and diet_items:
        actual["calories"] = int(targets["calories"] * 0.85)
        actual["protein"] = int(targets["protein"] * 0.75)
        actual["fat"] = int(targets["fat"] * 0.8)

    # Calculate calorie status
    cal_ratio = actual["calories"] / targets["calories"] if targets["calories"] else 1
    cal_status = "adequate" if cal_ratio >= 0.9 else ("low" if cal_ratio >= 0.6 else "deficit")

    # Build macros
    macros = [
        {
            "name": "Protein", "icon": "🥩",
            "actual": actual["protein"], "target": targets["protein"], "unit": "%",
            "status": _status_for_ratio(actual["protein"] / targets["protein"]) if targets["protein"] else "Adequate",
            "note": f"{'Good protein content' if actual['protein'] >= targets['protein'] * 0.9 else 'Consider protein-rich supplements'}",
        },
        {
            "name": "Fat", "icon": "🧈",
            "actual": actual["fat"], "target": targets["fat"], "unit": "%",
            "status": _status_for_ratio(actual["fat"] / targets["fat"]) if targets["fat"] else "Adequate",
            "note": "Essential for coat health in Golden Retrievers" if "golden" in breed_key else "Essential for energy",
        },
        {
            "name": "Carbohydrates", "icon": "🌾",
            "actual": 100 - actual["protein"] - actual["fat"] - actual["fibre"] - actual["moisture"],
            "target": targets["carbs"], "unit": "%",
            "status": "Adequate",
            "note": "Derived from remaining macronutrient balance",
        },
        {
            "name": "Fibre", "icon": "🥦",
            "actual": actual["fibre"], "target": targets["fibre"], "unit": "%",
            "status": _status_for_ratio(actual["fibre"] / targets["fibre"]) if targets["fibre"] else "Adequate",
            "note": "Supports digestive regularity",
        },
        {
            "name": "Moisture", "icon": "💧",
            "actual": actual["moisture"], "target": targets["moisture"], "unit": "%",
            "status": _status_for_ratio(actual["moisture"] / targets["moisture"]) if targets["moisture"] else "Adequate",
            "note": "Ensure fresh water is always available",
        },
    ]

    # Build vitamins
    vit_e_status = _status_for_ratio(actual["vitamin_e"] / targets["vitamin_e"]) if targets["vitamin_e"] else "Adequate"
    vit_d_status = _status_for_ratio(actual["vitamin_d3"] / targets["vitamin_d3"]) if targets["vitamin_d3"] else "Adequate"

    vitamins = [
        {
            "name": "Vitamin E", "status": vit_e_status,
            "supplement": "Vit E 400 IU Softgel", "price": "Rs.349/mo",
            "priority": _priority_for_status(vit_e_status),
        },
        {
            "name": "Vitamin D3", "status": vit_d_status,
            "supplement": "Sun Pharma Calcitriol", "price": "Rs.299/mo",
            "priority": _priority_for_status(vit_d_status),
        },
    ]

    # Build minerals
    gluc_status = _status_for_ratio(actual["glucosamine"] / targets["glucosamine"]) if targets["glucosamine"] else "Adequate"
    minerals = [
        {
            "name": "Glucosamine", "icon": "🦴",
            "status": gluc_status,
            "priority": _priority_for_status(gluc_status, is_critical=has_hip_dysplasia),
            "reason": "Critical for hip joint support" if has_hip_dysplasia else "Supports joint health",
            "actual": actual["glucosamine"], "target": targets["glucosamine"],
            "supplement": "Nutramax Cosequin DS Chewable", "price": "Rs.799/mo",
        },
        {
            "name": "Calcium", "icon": "🦷",
            "status": _status_for_ratio(actual["calcium"] / targets["calcium"]) if targets["calcium"] else "Adequate",
            "priority": "ok",
            "actual": actual["calcium"], "target": targets["calcium"],
        },
        {
            "name": "Phosphorus", "icon": "⚡",
            "status": _status_for_ratio(actual["phosphorus"] / targets["phosphorus"]) if targets["phosphorus"] else "Adequate",
            "priority": "ok",
            "actual": actual["phosphorus"], "target": targets["phosphorus"],
        },
    ]

    # Build others
    omega3_status = _status_for_ratio(actual["omega_3"] / targets["omega_3"]) if targets["omega_3"] else "Adequate"
    prob_status = "Adequate" if actual["probiotics"] else "Low"

    others = [
        {
            "name": "Omega-3", "icon": "🐟",
            "status": omega3_status,
            "actual": actual["omega_3"], "target": targets["omega_3"],
            "supplement": "Zesty Paws Salmon Oil", "price": "Rs.349/mo",
            "priority": _priority_for_status(omega3_status, is_critical=has_hip_dysplasia),
        },
        {
            "name": "Omega-6", "icon": "🌻",
            "status": _status_for_ratio(actual["omega_6"] / targets["omega_6"]) if targets["omega_6"] else "Adequate",
            "actual": actual["omega_6"], "target": targets["omega_6"],
            "priority": "ok",
        },
        {
            "name": "Probiotics", "icon": "🦠",
            "status": prob_status,
            "supplement": "Purina FortiFlora" if prob_status != "Adequate" else None,
            "price": "Rs.649/mo" if prob_status != "Adequate" else None,
            "priority": _priority_for_status(prob_status),
        },
    ]

    # Build improvements list
    improvements = []
    gap_colors = {"urgent": "#FF3B30", "high": "#FF9500", "medium": "#FFCC00"}

    all_nutrients = minerals + others + vitamins
    for n in sorted(all_nutrients, key=lambda x: {"urgent": 0, "high": 1, "medium": 2}.get(x.get("priority", "ok"), 3)):
        if n.get("priority") in ("urgent", "high", "medium"):
            dot = gap_colors.get(n["priority"], "#FFCC00")
            reason = n.get("reason", f"{n['name']} supplementation recommended")
            supplement_text = f" → {n['supplement']}" if n.get("supplement") else ""
            improvements.append({"dot": dot, "text": f"{n['name']} {n['status'].lower()}{supplement_text} - {reason}"})

    # Overall assessment
    gap_count = sum(1 for n in all_nutrients if n.get("priority") in ("urgent", "high", "medium"))
    if gap_count == 0:
        overall_label = "excellent"
        recommendation = f"Great nutrition profile! {pet.name}'s diet is well-balanced."
    elif gap_count <= 2:
        overall_label = "good"
        recommendation = f"Consider adding targeted supplements to address {gap_count} minor gap{'s' if gap_count > 1 else ''}."
    elif gap_count <= 4:
        overall_label = "moderate"
        recommendation = f"Add a joint health supplement + Vitamin E & D to {pet.name}'s daily routine."
    else:
        overall_label = "needs_attention"
        recommendation = f"{pet.name}'s diet has significant nutritional gaps. Consult your vet about supplementation."

    breed_label = pet.breed or "your pet's breed"
    condition_context = " + " + conditions[0].name if conditions else ""

    return {
        "calories": {"actual": actual["calories"], "target": targets["calories"], "status": cal_status},
        "macros": macros,
        "vitamins": vitamins,
        "minerals": minerals,
        "others": others,
        "improvements": improvements,
        "overall_label": overall_label,
        "recommendation": recommendation,
        "analysis_context": f"Analysis based on {breed_label} breed profile{condition_context}",
        "gap_count": gap_count,
    }
