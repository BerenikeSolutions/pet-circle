"""
Quick test of the updated COMBINED_MEAL_SYSTEM_PROMPT with food: royal canin, egg, carrots.
No DB needed — uses a hardcoded pet profile and food list.

Usage:
  cd backend
  python scripts/test_new_prompt.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Load .env if present
for env_file in [
    Path(__file__).parent.parent / "envs" / ".env.production",
    Path(__file__).parent.parent / "envs" / ".env.test",
    Path(__file__).parent.parent / ".env",
]:
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = value.strip()
        break

# Add backend to path so we can import nutrition_service
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.nutrition_service import COMBINED_MEAL_SYSTEM_PROMPT  # noqa: E402

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set.")
    sys.exit(1)

# ── Pet profile (generic adult dog, no specific pet needed) ─────────────────
PET = {
    "species": "dog",
    "breed": "Labrador Retriever",
    "age": "4 years",
    "weight_kg": 22,
    "gender": "male",
    "conditions": [],
}

# ── Food items to test ───────────────────────────────────────────────────────
FOODS = [
    {"label": "Royal Canin", "type": "food", "detail": None},
    {"label": "Egg",         "type": "food", "detail": None},
    {"label": "Carrots",     "type": "food", "detail": None},
]


def build_user_prompt(pet: dict, foods: list) -> str:
    parts = [
        f"Species: {pet['species']}",
        f"Breed: {pet['breed']}",
        f"Age: {pet['age']}",
        f"Weight: {pet['weight_kg']} kg",
        f"Gender: {pet['gender']}",
    ]
    if pet["conditions"]:
        parts.append(f"Conditions: {', '.join(pet['conditions'])}")
    parts.append("\nFoods (complete daily diet):")
    for i, f in enumerate(foods, 1):
        line = f"{i}. {f['label']} (type: {f['type']})"
        if f.get("detail") and str(f["detail"]).strip():
            line += f" -- User-provided quantity: {str(f['detail']).strip()}"
        else:
            line += " -- Quantity: not specified"
        parts.append(line)
    return "\n".join(parts)


async def main():
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    user_prompt = build_user_prompt(PET, FOODS)

    print("=" * 60)
    print("USER PROMPT")
    print("=" * 60)
    print(user_prompt)
    print("\nCalling LLM with updated COMBINED_MEAL_SYSTEM_PROMPT...")

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        temperature=0.0,
        system=COMBINED_MEAL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    print("\n" + "=" * 60)
    print("RAW LLM OUTPUT")
    print("=" * 60)
    print(raw)

    # Strip markdown fences if present
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1] if "\n" in stripped else stripped[3:]
        if "```" in stripped:
            stripped = stripped[:stripped.rfind("```")]
    stripped = stripped.strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as e:
        print(f"\n[ERROR] Could not parse JSON: {e}")
        return

    print("\n" + "=" * 60)
    print("PARSED JSON (pretty)")
    print("=" * 60)
    print(json.dumps(parsed, indent=2))

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if parsed.get("error"):
        print(f"  INSUFFICIENT_DATA")
        print(f"  warning : {parsed.get('warning_message')}")
    else:
        print(f"  resolved_name    : {parsed.get('resolved_name')}")
        print(f"  confidence       : {parsed.get('confidence')}")
        print(f"  serving          : {parsed.get('serving_description')}")
        print(f"  show_warning     : {parsed.get('show_warning')}")
        if parsed.get("warning_message"):
            print(f"  warning_message  : {parsed.get('warning_message')}")
        if parsed.get("prescription_context"):
            print(f"  prescription     : {parsed.get('prescription_context')}")
        print(f"  calories_per_day : {parsed.get('calories_per_day')}")
        print(f"  calorie_target   : {parsed.get('calorie_target')}")
        print(f"  calorie_gap_pct  : {parsed.get('calorie_gap_pct')}%")
        print(f"  protein_pct      : {parsed.get('protein_pct')}")
        print(f"  fat_pct          : {parsed.get('fat_pct')}")
        print(f"  carbs_pct        : {parsed.get('carbs_pct')}")
        print(f"  fibre_pct        : {parsed.get('fibre_pct')}")
        gaps = parsed.get("micronutrient_gaps", [])
        print(f"\n  micronutrient_gaps ({len(gaps)}):")
        for g in gaps:
            prescribed = " [prescribed]" if g.get("prescribed") else ""
            print(f"    * {g['name']}: {g['status']} (severity={g.get('severity_score')}){prescribed}")
        improvements = parsed.get("top_improvements", [])
        print(f"\n  top_improvements ({len(improvements)}):")
        for imp in improvements:
            print(f"    [{imp.get('severity','?').upper()}] {imp.get('title')} — {imp.get('detail')}")


asyncio.run(main())
