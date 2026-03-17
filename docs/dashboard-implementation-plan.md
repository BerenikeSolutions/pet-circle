# PetCircle Dashboard — Full Implementation Plan

## Context

The JSX reference file (`petcircle_150326_8.jsx`) defines the complete expected UI for the PetCircle dashboard. The current Next.js frontend has partial implementations across 5 tabs. This plan brings the dashboard to full parity with the JSX, wired to real backend APIs (no mock data, no localStorage persistence).

Additionally:
- The WhatsApp onboarding flow + AI processing animation from the JSX will be documented (not built in Next.js) in `docs/whatsapp-onboarding-flow.md`
- The nutrition Excel database (`PetCircle_Nutrition_Database_1.xlsx`) will be imported into Supabase as a product catalog
- All features are built full-stack (backend + frontend together)

**Key principle**: Each phase plan is self-contained with all file paths, schemas, API shapes, and component details. No codebase reading needed during implementation.

---

## Phase Overview

| Phase | Feature | Backend | Frontend |
|-------|---------|---------|----------|
| 0 | WhatsApp Flow Documentation | — | — |
| 1 | Database Foundation | DB models, migrations, seed script | — |
| 2 | Health Tab | Weight history API, checkup APIs | Weight log, checkups, vaccines |
| 3 | Nutrition Tab | Diet items CRUD, nutrition analysis | Diet editor, nutrition breakdown |
| 4 | Hygiene Tab | Hygiene preferences API | Frequency settings, periodic grooming |
| 5 | Conditions Tab | Chronology API, PDF export | Timeline, vet visit, recommendations |
| 6 | Overview Tab | Health score breakdown, reminders API | Care tiles, nutrition note, reminders, docs, contacts |
| 7 | Nudges & Action Plan | Nudge engine | Action plan screen |
| 8 | Cart & Orders | Cart CRUD, order placement | Cart, payment, success screens |
| 9 | WhatsApp Reminders Screen | — | Reminder preview screen |

---

## Phase 0: WhatsApp Flow Documentation

**Goal**: Document the WhatsApp onboarding conversation flow and AI processing animation from the JSX, stored in `docs/whatsapp-onboarding-flow.md`.

### File to create: `docs/whatsapp-onboarding-flow.md`

**Content to document:**

1. **Conversation Flow** (from `WHATSAPP_CONV` constant, lines 131-150 of JSX):
   - Bot: Welcome message → User: Confirm → Bot: Ask photo+name → User: Photo+name → Bot: Ask breed/dob/gender → User: Details → Bot: Ask pincode → User: Pincode → Bot: Ask packaged food → User: Food details → Bot: Ask homemade food → User: Homemade details → Bot: Ask supplements → User: Supplements+medications → Bot: Ask health records → User: Upload files → Bot: Processing → Bot: Profile complete

2. **Processing Animation** (from `PROCESSING_TASKS` constant, line 152-156):
   - Steps: Reading vaccination card → Parsing deworming record → Extracting hip dysplasia report → Analysing nutrition label → Identifying breed-specific gaps → Calculating next due dates → Mapping WhatsApp reminder schedule → Building supplement recommendations → Profile ready
   - Visual: Circular progress ring (140px, 8px stroke, #D44800), dark background (#0A0A0A), checklist with green checkmarks

3. **Data Fields Collected**: name, breed, dob, gender, pincode, currentFood (brand, type, portion, meals), homemade items, supplements, health record uploads

4. **WhatsApp Reminder Templates** (from `whatsappReminders` constant, lines 91-97):
   - 5 reminder types: deworming upcoming, vaccine upcoming, supplement refill, deworming due today, deworming overdue
   - Each has: title, body text, 2 action buttons (order/book + secondary action)
   - Status colors: upcoming=#FF9500, due=#D44800, overdue=#FF3B30

5. **Reminder Schedule Logic** (from `REMINDER_EXPLAINER`, lines 233-239):
   - 1 week before → UPCOMING reminder
   - Due date → Due today at 9am
   - No action → Overdue follow-up every 7 days
   - Action taken → Series stops, next cycle scheduled
   - Condition meds → Separate refill series per medication

**Verification**: File exists and contains all 5 sections above.

---

## Phase 1: Database Foundation

**Goal**: Create all missing DB tables and seed the product catalog from the Excel file.

### 1A. New Database Models

#### `backend/app/models/weight_history.py` (NEW)
```python
from app.database import Base
# UUID PK, pet_id UUID FK to pets(id), weight DECIMAL(5,2), recorded_at DATE, note VARCHAR(255), created_at TIMESTAMPTZ
```

#### `backend/app/models/diet_item.py` (NEW)
```python
from app.database import Base
# UUID PK, pet_id UUID FK, type VARCHAR(20), icon VARCHAR(10), label VARCHAR(200), detail VARCHAR(200)
# UniqueConstraint("pet_id", "label", "type")
```

#### `backend/app/models/hygiene_preference.py` (NEW)
```python
from app.database import Base
# UUID PK, pet_id UUID FK, item_id VARCHAR(50), freq INTEGER, unit VARCHAR(10), reminder BOOLEAN, last_done VARCHAR(20)
# UniqueConstraint("pet_id", "item_id")
```

#### `backend/app/models/product_catalog.py` (NEW)
```python
from app.database import Base
# UUID PK, category VARCHAR(30), brand VARCHAR(100), product_name VARCHAR(200), description TEXT
# Nutritional: crude_protein, crude_fat, crude_fibre, moisture, ash, calcium, phosphorus, omega_3, omega_6, vitamin_e, vitamin_d3, glucosamine, probiotics, energy_kcal
# Medicine: active_ingredient, indication, dosage, frequency, formulation, prescription_required
# Common: life_stage, breed_size, type, pack_size, mrp, notes, cart_item_id
```

#### `backend/app/models/nudge.py` (NEW)
```python
from app.database import Base
# UUID PK, pet_id UUID FK, category VARCHAR(30), priority VARCHAR(10), icon VARCHAR(10), title VARCHAR(200), message TEXT
# mandatory BOOLEAN, orderable BOOLEAN, price VARCHAR(20), order_type VARCHAR(30), cart_item_id VARCHAR(10), dismissed BOOLEAN
```

#### `backend/app/models/cart_item.py` (NEW)
```python
from app.database import Base
# UUID PK, pet_id UUID FK, product_id VARCHAR(10), icon VARCHAR(10), name VARCHAR(200), sub VARCHAR(200)
# price INTEGER, tag VARCHAR(30), tag_color VARCHAR(10), in_cart BOOLEAN, quantity INTEGER
# UniqueConstraint("pet_id", "product_id")
```

### 1B. Update `backend/app/models/__init__.py`

Add imports for all new models: WeightHistory, DietItem, HygienePreference, ProductCatalog, Nudge, CartItem

### 1C. Seed Script: `backend/scripts/seed_product_catalog.py`

Reads from `PetCircle_Nutrition_Database_1.xlsx` (4 sheets) and inserts into `product_catalog` table.

**Sheet mapping:**
- "Nutrition Database" (rows 4+, 23 cols) → category="food"
- "Deworming Medicines" (rows 4+, 12 cols) → category="deworming"
- "Flea & Tick Products" (rows 4+, 12 cols) → category="flea_tick"
- "Disease Medicines" (rows 4+, 12 cols) → category="medicine"

**Cart item ID mapping** (from Notes column):
- c2 = Bayer Drontal Plus (deworming)
- c3 = Zesty Paws Salmon Oil (omega-3)
- c4 = Nutramax Cosequin DS (glucosamine)
- c5 = NexGard Chewable (flea/tick)
- c6 = NOW Vitamin E-400 IU
- c11 = Purina FortiFlora (probiotic)
- c12 = Sun Pharma Calcitriol (vitamin D)

### 1D. Migration Script

`backend/migrations/001_add_dashboard_tables.sql`: CREATE TABLE for all 6 new tables + ALTER TABLE preventive_records ADD COLUMN custom_recurrence_days

### Verification
- All model files created and importable
- Migration runs without errors
- Seed script populates product_catalog with all rows from Excel
- `SELECT count(*) FROM product_catalog` returns ~90+ rows

---

## Phase 2: Health Tab (Full-Stack)

**Goal**: Match JSX `renderMedicalTab()` (lines 1113-1356) exactly. Add weight history, improved checkups, vaccination enhancements.

### 2A. Backend: Weight History

**File**: `backend/app/services/weight_service.py` (NEW)
- `get_weight_history(db, pet_id)` → list of entries + ideal_range
- `add_weight_entry(db, pet_id, weight, recorded_at, note)` → new entry

**Endpoints** in `backend/app/routers/dashboard.py`:
- `GET /{token}/weight-history` → entries + ideal_range
- `POST /{token}/weight-history` → add entry

**Ideal weight ranges** by breed (hardcoded in service):
- Golden Retriever Male: 27-34 kg
- Golden Retriever Female: 25-32 kg

### 2B. Backend: Vaccine Frequency Persistence

`PATCH /dashboard/{token}/preventive-frequency`
- Body: `{"item_name": "Kennel Cough", "recurrence_days": 365}`
- Updates `custom_recurrence_days` column on preventive_records

### 2C. Frontend: HealthTab.tsx Updates

**Sections:**
1. **Vaccinations** — Split Mandatory/Optional, vaccine rows with status, ReminderBar, frequency modal (6/9/12/18/24 months)
2. **CareCard for Deworming** — icon="🪱", product="Milbemax - Every 3 months"
3. **CareCard for Flea & Tick** — icon="🐛", product="Bravecto - Every month"
4. **Annual Health Checkups** — 5 items, progress bar, info banner, each with ReminderBar
5. **Weight Log** — Current weight, trend arrow, bar chart sparkline, log table, "Log weight" AddRow

### 2D. Frontend: API Types Update

Add to `frontend/src/lib/api.ts`:
- `WeightEntry`, `WeightHistoryResponse` interfaces
- `getWeightHistory()`, `addWeightEntry()`, `updatePreventiveFrequency()` functions

---

## Phase 3: Nutrition Tab (Full-Stack)

**Goal**: Match JSX `renderNutritionTab()` (lines 1358-1621) exactly.

### 3A. Backend: Diet Items CRUD

**File**: `backend/app/services/diet_service.py` (NEW)
- `get_diet_items()`, `add_diet_item()`, `update_diet_item()`, `delete_diet_item()`
- Auto-classification: PACKAGED_KW list → type="packaged" icon="🥣"; else "homemade" icon="🥗"

**Endpoints**:
- `GET/POST /{token}/diet-items`, `PUT/DELETE /{token}/diet-items/{id}`

### 3B. Backend: Nutrition Analysis

**File**: `backend/app/services/nutrition_service.py` (NEW)
- `analyze_nutrition(db, pet_id)` → calories, macros, vitamins, minerals, others, improvements, overall_label, recommendation

**Logic**: Match diet items to product_catalog → sum nutrients → compare to breed targets → identify gaps (especially glucosamine for hip dysplasia)

**Endpoint**: `GET /{token}/nutrition-analysis`

### 3C. Frontend: NutritionTab.tsx Updates

**Sections:**
1. **Current Diet** — Diet rows with edit/delete, AddRow, supplements section
2. **Edit Diet Row Sheet** — BottomSheet with name/quantity inputs
3. **Order Reminders** — Reorder items with frequency toggle
4. **Nutrition Note** — 3 colored boxes (overall/improve/recommendation)
5. **Nutrition Breakdown** — Calories bar, macros, vitamins, minerals, other nutrients

---

## Phase 4: Hygiene Tab (Full-Stack)

**Goal**: Match JSX `renderGroomingTab()` (lines 1623-1731) exactly.

### 4A. Backend: Hygiene Preferences CRUD

**File**: `backend/app/services/hygiene_service.py` (NEW)
- `get_hygiene_preferences()`, `upsert_hygiene_preference()`, `update_hygiene_date()`
- Seeds defaults on first access

**Default hygiene items:**
- coat-brush: 1/day, teeth-brush: 1/day, ear-clean: 6/week, eye-wipe: 1/month, bath-nail: 1/month, anal-gland: 6/week

**Endpoints**:
- `GET /{token}/hygiene-preferences`
- `PUT /{token}/hygiene-preferences/{item_id}`
- `PATCH /{token}/hygiene-preferences/{item_id}/date`

### 4B. Frontend: HygieneTab.tsx Updates

**Sections:**
1. **Breed info banner** — Orange, breed-adjusted note
2. **Frequent Activities** — 4 items (coat-brush, teeth-brush, ear-clean, eye-wipe) with ReminderBar + FreqPill
3. **Periodic Grooming** — 2 items (bath-nail, anal-gland) with date edit + next due
4. **FreqPill** — Inline pill with frequency, opens FreqModal

---

## Phase 5: Conditions Tab (Full-Stack)

**Goal**: Match JSX `renderConditionsTab()` (lines 1824-1974) exactly.

### 5A. Backend

**New endpoint**: `GET /{token}/condition-timeline`
- Returns chronological events: [{date, type, icon, title, detail, tag}]

**File**: `backend/app/services/condition_service.py` (NEW)

### 5B. Frontend: ConditionsTab.tsx Updates

**Sections:**
1. **Condition Cards** — Header, medications with refill status, monitoring checkups, recommendations
2. **Add Another Condition** — Dashed button
3. **Last Vet Visit** — Doctor/clinic/dates card
4. **Management History** (ConditionsChronology) — Vertical timeline with events
5. **Complete Health Analysis PDF** (ConditionsPdfCard) — 2x3 grid, download button

---

## Phase 6: Overview Tab (Full-Stack)

**Goal**: Match JSX `renderOverviewTab()` (lines 773-1110) exactly.

### 6A. Backend: Enhanced Dashboard Response

Add to GET /dashboard/{token} response:
- `health_score.breakdown[]` — 6 categories with weights and scores
- `health_score.draggers[]` — Categories pulling score down
- `whatsapp_reminders[]` — Scheduled reminders with actions

**Health score calculation** (JSX `computeHealthScore`):
- Vaccines (25%), Deworming & Flea (20%), Conditions (20%), Nutrition (20%), Grooming (10%), Checkups (5%)
- Labels: >=85 "Excellent", >=65 "Good", >=45 "Fair", else "Poor"

### 6B. Frontend: OverviewTab.tsx Updates

**Sections:**
1. **Care at a Glance** — 3x2 grid of status tiles
2. **Condition Summary** — Medications, next follow-up
3. **Order Now CTA** — Full-width orange button
4. **Nutrition Note** — 3 colored boxes
5. **WhatsApp Reminders** — Collapsible with expandable reminder cards
6. **Uploaded Documents** — Collapsible with sub-sections
7. **Care Contacts** — Collapsible with CRUD

---

## Phase 7: Nudges & Action Plan

**Goal**: Build Action Plan screen matching JSX `NudgesStep` (lines 2244-2331).

### 7A. Backend: Nudge Engine

**File**: `backend/app/services/nudge_engine.py` (NEW)
- `generate_nudges(db, pet_id)` → prioritized nudge list

**10 nudge types** (deworming, vaccine, condition, nutrition, flea, grooming)

**Endpoints**: `GET /{token}/nudges`, `PATCH /{token}/nudges/{id}/dismiss`

### 7B. Frontend: NudgesView.tsx

- Header with counts, WhatsApp banner, filter chips (All/Must Do/Nutrition/Grooming)
- Nudge cards with priority borders, expandable order/dismiss
- Empty state when all dismissed

**Priority config**: urgent=#FF3B30, high=#FF9500, medium=#FFCC00

---

## Phase 8: Cart & Orders (Full-Stack)

**Goal**: Match JSX `CartStep` (lines 2334-2692) with 3 screens.

### 8A. Backend: Cart & Orders

**File**: `backend/app/services/cart_service.py` (NEW)
- `get_cart()`, `toggle_cart_item()`, `update_quantity()`, `initialize_cart()`, `place_order()`

**14 cart items** (c1-c14) with default inCart states

**Endpoints**: `GET /{token}/cart`, `POST toggle`, `PATCH quantity`, `POST apply-coupon`, `POST place-order`

### 8B. Frontend: CartView — 3 screens

1. **Cart** — Urgent/Recommended sections, toggle/quantity, coupon, sticky footer
2. **Payment** — Address selection, 4 payment methods (UPI/Card/NetBanking/COD), bill summary
3. **Success** — Confirmation with order ID, items, total, delivery estimate

---

## Phase 9: WhatsApp Reminders Screen

**Goal**: Match JSX `RemindersStep` (lines 2153-2242).

### Frontend Only

**File**: `frontend/src/components/RemindersView.tsx`
- Timeline legend, WhatsApp-styled reminder cards, expand/collapse actions
- "How WhatsApp reminders work" info card
- Status colors: upcoming=#FF9500, due=#D44800, overdue=#FF3B30

---

## Cross-Cutting Concerns

### Design System
- Brand: #D44800, fonts: DM Sans + Fraunces
- Status colors in `frontend/src/lib/branding.ts`
- 10 shared UI primitives in `components/ui/`
- Max-width: 430px, borderRadius: 16px, min touch target: 36x36px

### Implementation Order
1. Save plan docs (Step 0)
2. Execute phases 1 → 9 in order
3. Each phase is full-stack and independently testable
