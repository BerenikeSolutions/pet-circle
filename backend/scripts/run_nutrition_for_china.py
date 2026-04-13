"""
Standalone script to run the nutrition estimation prompt for pet "China"
and print the raw JSON output from the LLM.

Usage:
  ANTHROPIC_API_KEY=sk-ant-... python scripts/run_nutrition_for_china.py

The script connects to the database using the DATABASE_URL from
backend/envs/.env.test (or DATABASE_URL env var), fetches China's pet profile
and diet items, then calls the Claude API with the same prompt that
estimate_food_nutrition() uses in production.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# ─── Load .env.test if no DATABASE_URL is set ───────────────────────────────
ENV_FILE = Path(__file__).parent.parent / "envs" / ".env.test"
if not os.environ.get("DATABASE_URL") and ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip()

DATABASE_URL = os.environ.get("DATABASE_URL")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Set it in env or backend/envs/.env.test")
    sys.exit(1)

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set.")
    print("Run: ANTHROPIC_API_KEY=sk-ant-... python scripts/run_nutrition_for_china.py")
    sys.exit(1)

import psycopg2
import psycopg2.extras

# ─── Connect to DB ───────────────────────────────────────────────────────────
print(f"Connecting to database...")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# ─── Find pet "China" ────────────────────────────────────────────────────────
cur.execute("""
    SELECT id, name, species, breed, dob, weight, gender
    FROM pets
    WHERE lower(name) = 'china'
    LIMIT 1
""")
pet = cur.fetchone()

if not pet:
    print("No pet named 'China' found. Searching case-insensitively...")
    cur.execute("""
        SELECT id, name, species, breed, dob, weight, gender
        FROM pets
        WHERE lower(name) LIKE '%china%'
        LIMIT 5
    """)
    rows = cur.fetchall()
    if rows:
        print("Found similar pets:")
        for r in rows:
            print(f"  id={r['id']} name={r['name']} species={r['species']}")
    else:
        print("No pets matching 'china' found in the database.")
    conn.close()
    sys.exit(1)

pet_id = pet["id"]
print(f"\n{'='*60}")
print(f"PET PROFILE: {pet['name']}")
print(f"{'='*60}")
print(f"  ID:       {pet_id}")
print(f"  Species:  {pet['species']}")
print(f"  Breed:    {pet['breed']}")
print(f"  DOB:      {pet['dob']}")
print(f"  Weight:   {pet['weight']} kg")
print(f"  Gender:   {pet['gender']}")

# ─── Get active conditions ───────────────────────────────────────────────────
cur.execute("""
    SELECT name FROM conditions
    WHERE pet_id = %s AND is_active = true
""", (pet_id,))
conditions = [r["name"] for r in cur.fetchall()]
print(f"  Conditions: {conditions or 'None'}")

# ─── Get diet items ──────────────────────────────────────────────────────────
cur.execute("""
    SELECT id, label, type, detail, daily_portion_g
    FROM diet_items
    WHERE pet_id = %s
""", (pet_id,))
diet_items = cur.fetchall()

print(f"\n{'='*60}")
print(f"DIET ITEMS ({len(diet_items)} items)")
print(f"{'='*60}")
for item in diet_items:
    print(f"  [{item['type']:12}] {item['label']}")
    if item['detail']:
        print(f"              detail: {item['detail']}")
    if item['daily_portion_g']:
        print(f"              portion: {item['daily_portion_g']}g/day")

conn.close()

if not diet_items:
    print("\nNo diet items found. Nothing to analyse.")
    sys.exit(0)

# ─── Build the prompt (same logic as nutrition_service.py) ───────────────────
SYSTEM_PROMPT = (
    "You are a board-certified veterinary nutritionist.\n\n"
    "Your task:\n"
    "Given food items, pet details, and optionally user-provided quantities, estimate DAILY nutritional intake and identify the most important micronutrient gaps.\n\n"
    "You must follow this strict decision framework:\n\n"
    "-----------------------------------\n"
    "STEP 1 — RESOLVE FOOD IDENTITY\n"
    "-----------------------------------\n"
    "- Identify the most likely specific product based on:\n"
    "- food name\n"
    "- species\n"
    "- age (puppy / adult / senior)\n"
    "- Example:\n"
    "\"Pedigree\" + adult dog -> Pedigree Adult Dog Food\n"
    "- If multiple variants are possible, choose the most common one and reduce confidence\n"
    "- If product identity is highly ambiguous, reduce confidence\n\n"
    "-----------------------------------\n"
    "STEP 2 — DETERMINE SERVING SIZE\n"
    "-----------------------------------\n\n"
    "CASE A: USER PROVIDED QUANTITY (any food)\n"
    "- Use EXACTLY the user-provided quantity (e.g., \"2 cups/day\", \"1 bowl/day\")\n"
    "- Do NOT override, scale, or reinterpret it\n\n"
    "CASE B: COMMERCIAL / PACKAGED FOOD AND NO QUANTITY PROVIDED\n"
    "- Use ONLY official brand feeding guidelines\n"
    "- Use pet weight and age ONLY to select the correct feeding range\n"
    "- Choose a reasonable midpoint within that range\n"
    "- Do NOT invent or extrapolate beyond brand guidance\n\n"
    "CASE C: HOMEMADE / GENERIC FOOD AND NO QUANTITY PROVIDED\n"
    "- DO NOT estimate or assume any serving size\n"
    "- Mark portion as UNKNOWN\n\n"
    "IF serving size cannot be determined with confidence:\n"
    "- Set confidence < 0.6\n"
    "- RETURN NO ANALYSIS (see fail-safe)\n\n"
    "-----------------------------------\n"
    "STEP 3 — MIXED DIET HANDLING\n"
    "-----------------------------------\n\n"
    "If BOTH commercial food AND homemade food are present:\n\n"
    "- Treat commercial food as the PRIMARY diet anchor:\n"
    "- Use it for:\n"
    "- calories_per_day\n"
    "- macronutrient percentages (protein, fat, fibre)\n\n"
    "- For homemade food WITHOUT quantity:\n"
    "- DO NOT include in:\n"
    "- calories\n"
    "- macronutrient calculations\n"
    "- ONLY use it for qualitative micronutrient signals if possible\n\n"
    "- If homemade food HAS quantity:\n"
    "- Include it fully in all calculations\n\n"
    "-----------------------------------\n"
    "STEP 4 — NUTRITION ESTIMATION\n"
    "-----------------------------------\n"
    "- Estimate TOTAL DAILY intake based on determined serving size\n"
    "- Ensure values are realistic and internally consistent\n"
    "- Prevent extreme or biologically impossible outputs\n"
    "- Macro percentages must remain within realistic biological limits\n"
    "- Total calories must fall within realistic daily intake ranges\n\n"
    "-----------------------------------\n"
    "STEP 5 — MICRONUTRIENT GAP ANALYSIS\n"
    "-----------------------------------\n\n"
    "- Identify micronutrient gaps dynamically based on:\n"
    "- pet nutritional requirements\n"
    "- current diet composition\n\n"
    "- Use ONLY this controlled list of nutrient names:\n"
    "omega_3, omega_6, vitamin_e, vitamin_d3, glucosamine, calcium, phosphorus, iron, zinc, taurine, fibre\n\n"
    "- For each nutrient:\n"
    "- Assign ONLY one of the following statuses:\n"
    "- \"sufficient\"\n"
    "- \"low\"\n"
    "- \"missing\"\n\n"
    "- DO NOT include nutrients where status cannot be confidently determined\n"
    "- DO NOT output \"unknown\" under any condition\n\n"
    "- DO NOT output numeric values, units, or requirements for micronutrients\n"
    "- Micronutrients are strictly qualitative signals\n\n"
    "- Assign a severity_score (0-1) based on:\n"
    "- deficiency severity (missing > low > sufficient)\n"
    "- relevance to pet conditions\n"
    "- confidence in assessment\n\n"
    "-----------------------------------\n"
    "STEP 6 — SELECT TOP MICRONUTRIENTS\n"
    "-----------------------------------\n\n"
    "- Rank micronutrients by severity_score\n"
    "- Return ONLY the TOP 4 most important micronutrient gaps\n"
    "- EXCLUDE all nutrients marked as \"sufficient\"\n"
    "- If fewer than 4 meaningful gaps exist, return fewer\n\n"
    "-----------------------------------\n"
    "OUTPUT FORMAT\n"
    "-----------------------------------\n\n"
    "Return ONLY valid JSON with these keys:\n\n"
    "resolved_name (string),\n"
    "confidence (float 0-1),\n"
    "serving_description (string),\n"
    "calories_per_day (int),\n"
    "protein_pct (float),\n"
    "fat_pct (float),\n"
    "fibre_pct (float),\n\n"
    "micronutrient_gaps: [\n"
    "{\n"
    "name (string),\n"
    "status (string: sufficient | low | missing),\n"
    "severity_score (float 0-1),\n"
    "supplement (string | null),\n"
    "reason (string)\n"
    "}\n"
    "]\n\n"
    "-----------------------------------\n"
    "CRITICAL RULES\n"
    "-----------------------------------\n\n"
    "- NEVER estimate serving size arbitrarily\n"
    "- NEVER assume portion size for homemade food\n"
    "- NEVER scale portions beyond brand guidelines\n"
    "- NEVER include homemade food in calorie or macro calculations unless quantity is provided\n"
    "- NEVER fabricate precision where data is missing\n"
    "- Maintain internal consistency across all outputs\n\n"
    "-----------------------------------\n"
    "FAIL-SAFE\n"
    "-----------------------------------\n\n"
    "If ANY of the following:\n"
    "- product identity is ambiguous OR\n"
    "- serving size is missing or unclear OR\n"
    "- confidence < 0.6\n\n"
    "THEN RETURN:\n\n"
    "{\n"
    '"confidence": <value>,\n'
    '"error": "INSUFFICIENT_DATA",\n'
    '"message": "Provide exact SKU or serving size for accurate diet analysis"\n'
    "}\n\n"
    "-----------------------------------\n"
    "GENERAL\n"
    "-----------------------------------\n\n"
    "- No explanation\n"
    "- No markdown\n"
    "- JSON only"
)


COMBINED_SYSTEM_PROMPT = (
    "You are a board-certified veterinary nutritionist.\n\n"
    "Your task:\n"
    "Analyse ALL listed foods together as the pet's COMPLETE daily diet. "
    "Calculate TOTAL daily nutrition across all foods.\n\n"
    "CASE A: USER PROVIDED QUANTITY -> Use EXACTLY the user-provided quantity\n"
    "CASE B: COMMERCIAL FOOD, NO QUANTITY -> Use official brand feeding guidelines\n"
    "CASE C: HOMEMADE / GENERIC, NO QUANTITY -> Exclude from calorie/macro calcs\n\n"
    "Sum calories_per_day across all foods with known portions.\n"
    "For protein_pct, fat_pct, fibre_pct: CALORIE-WEIGHTED AVERAGE across all foods.\n\n"
    "MICRONUTRIENTS: Assess what is missing/low in the COMBINED diet.\n"
    "Use ONLY: omega_3, omega_6, vitamin_e, vitamin_d3, glucosamine, calcium, phosphorus, iron, zinc, taurine, fibre\n"
    "Status: sufficient | low | missing. Return top 4 with status low or missing.\n\n"
    "CONFIDENCE = certainty about food identity and serving sizes (NOT dietary completeness).\n"
    "Return INSUFFICIENT_DATA only if NO food has determinable identity AND serving size.\n\n"
    "OUTPUT: Valid JSON only, no markdown:\n"
    "{ confidence, calories_per_day, protein_pct, fat_pct, fibre_pct,\n"
    "  micronutrient_gaps: [{name, status, severity_score, supplement, reason}] }"
)


def build_combined_user_prompt(items, pet_row):
    from datetime import date
    parts = []
    if pet_row["species"]:
        parts.append(f"Species: {pet_row['species']}")
    if pet_row["breed"]:
        parts.append(f"Breed: {pet_row['breed']}")
    if pet_row["dob"]:
        age_months = (date.today() - pet_row["dob"]).days // 30
        parts.append(f"Age: {age_months} months" if age_months < 24 else f"Age: {age_months // 12} years")
    if pet_row["weight"]:
        parts.append(f"Weight: {float(pet_row['weight']):.1f} kg")
    if pet_row["gender"]:
        parts.append(f"Gender: {pet_row['gender']}")
    parts.append("\nFoods (complete daily diet):")
    for i, item in enumerate(items, 1):
        line = f"{i}. {item['label']} (type: {item['type']})"
        if item["daily_portion_g"]:
            line += f" -- Daily portion: {item['daily_portion_g']}g"
        elif item["detail"] and str(item["detail"]).strip():
            line += f" -- User-provided quantity: {str(item['detail']).strip()}"
        else:
            line += " -- Quantity: not specified"
        parts.append(line)
    return "\n".join(parts)


async def call_claude(system_prompt, user_prompt):
    """Call Claude API with the given prompts."""
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        temperature=0.0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text


def strip_fences(raw):
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1] if "\n" in stripped else stripped[3:]
        if stripped.endswith("```"):
            stripped = stripped[:stripped.rfind("```")]
    return stripped.strip()


async def main():
    user_prompt = build_combined_user_prompt(diet_items, dict(pet))

    print(f"\n{'='*60}")
    print("COMBINED MEAL ANALYSIS (all foods together)")
    print(f"{'='*60}")
    print(user_prompt)
    print("\nWaiting for LLM response...")

    raw = await call_claude(COMBINED_SYSTEM_PROMPT, user_prompt)
    print("\nRAW LLM OUTPUT:")
    print(raw.encode("ascii", "replace").decode("ascii"))

    try:
        parsed = json.loads(strip_fences(raw))
        print("\nPARSED JSON:")
        print(json.dumps(parsed, indent=2))
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        if parsed.get("error"):
            print(f"  INSUFFICIENT_DATA: {parsed.get('message', '')}")
        else:
            print(f"  calories_per_day : {parsed.get('calories_per_day')}")
            print(f"  protein_pct      : {parsed.get('protein_pct')}")
            print(f"  fat_pct          : {parsed.get('fat_pct')}")
            print(f"  fibre_pct        : {parsed.get('fibre_pct')}")
            gaps = parsed.get("micronutrient_gaps", [])
            print(f"  micronutrient gaps ({len(gaps)}):")
            for g in gaps:
                print(f"    * {g.get('name')}: {g.get('status')} (severity={g.get('severity_score')})")
    except json.JSONDecodeError:
        print("[WARNING] Could not parse as JSON")


asyncio.run(main())
