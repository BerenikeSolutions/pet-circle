# PetCircle Dashboard Rebuild Plan

## Context

The current frontend uses a **5-tab layout** (Overview, Health, Hygiene, Nutrition, Conditions) designed for data management — editing dates, toggling reminders, managing hygiene items. The new reference design (`PetDashboard_3103_4.jsx` + `JSX_Guardrails.xlsx`) is fundamentally different: a **narrative-driven, scrolling dashboard** with clinical analysis, visual health trends, and a care commerce flow. The goal is to rebuild the frontend to match the JSX reference pixel-for-pixel and follow every guardrail specification without exception.

---

## PLAN A: Implementation Plan (Matching JSX + Guardrails Word-for-Word)

### Design System Changes

**File: `frontend/src/app/globals.css`**

Replace/extend CSS variables to match JSX `:root`:
```
--orange: #FF6B35     (was --brand-primary: #D44800)
--amber: #FF9F1C
--black: #1A1A1A
--green: #34C759
--red: #FF3B30
--bg: #F7F4F0         (matches current --bg-app)
--white: #FFFFFF
--warm: #FDFAF7
--border: #E8E4DF
--tg: #F0FFF4  --tr: #FFF0F0  --ta: #FFF6ED  --to: #FFF3EE
--t1: #1A1A1A  --t2: #4A4A4A  --t3: #8A8A8A
--radius: 16px  --rs: 10px
```
Fonts: DM Sans (body) + Fraunces (brand/headings) — already in current design system.
Max-width: 430px (matches current).

### Navigation Model

Replace tab-based nav with view-switching state in `DashboardClient.tsx`:
```
view: 'dashboard' | 'trends' | 'reminders' | 'cart' | 'checkout' | 'confirm' | 'records'
```

No tab bar. Navigation via:
- Bell icon (banner) → reminders
- "Discuss with your vet" CTA → trends (Ask Your Vet)
- "See [name]'s Full Health Records" → records
- Cart floater → cart
- Back buttons on sub-views → dashboard

---

### Component-by-Component Specification

#### PAGE 1: Dashboard (Scrolling)

**1. Profile Banner** — `components/dashboard/ProfileBanner.tsx`
- Gradient: `linear-gradient(135deg, #E8412A, #FF6B35, #FF8C5A)`
- Row 1: "PetCircle" (Fraunces 18px 700) + bell icon (36px circle, rgba white)
- Row 2: Avatar emoji (56x56, species-matched) + Pet Name (Fraunces 24px 700 white) + breed/sex/age/weight in ONE line (12px, no spillover)
- Row 3: Vet row — `🩺 Vet [full name] · Last visit [date]` (never abbreviate vet name)
- Guardrails: NO health status/alerts/scores here. NO next-appointment dates. NO weight as health concern.

**2. What We Found (Recognition)** — `components/dashboard/RecognitionCard.tsx`
- "We reviewed **X reports** and WhatsApp chat and identified [name]'s current care routine." + "View all reports →" (links to Records)
- Max 3 bullets, each ONE line only, no spillover: conditions first, preventive second, diet last
- Rename: "active health conditions" (not "active conditions")
- Guardrails: Each bullet traceable to source. NO inference. NO recommendations. NO alarming language. Observational tone.

**3. Life Stage Card** — `components/dashboard/LifeStageCard.tsx`
- Section label: "What to expect as [name] turns [age]"
- 4-stage bar: Puppy (10%) → Junior (12%) → Adult (45%) → Senior (33%)
- Current stage: orange gradient fill, others recede (50% opacity)
- Marker: 18px circle at computed `ageMonths` position, orange with white border
- Caption: "[Name] is here · [age]" (centered, orange, 11px)
- Trait pills: life-stage-specific FOR THE BREED, max 2 lines. Order: behavior/energy first → appetite/physiology. Color: green (positive), yellow (watch), red (concern), neutral (personality). NEVER alarming phrases — informing how body is changing and what to monitor.
- Essential care: max 2 items, each LINKED to pills above. Format: amber background tiles with icon + 1-line detail.
- Guardrails: Current stage must visually dominate. Traits must be age-specific not breed-generic. Age label computed from `ageMonths`, never hardcoded.

**4. Health Conditions Card** — `components/dashboard/HealthConditionsCard.tsx`
- Guardrail (CONTRARY TO JSX): Show ALL ongoing conditions and recurrent patterns, not just red severity
- WITH conditions: up to 2 primary (by severity + recency), each with:
  - Red dot (7px) + title + trend label ("Active · Since Feb 2025")
  - 1-line insight below (12px, left border 2px #FFCDD2) explaining mechanism, not diagnosis
- If more than 2 ongoing/recurrent conditions: show all. Limit insights to max 2 only if no ongoing/recurrent patterns.
- WITHOUT conditions: "No active concerns · Routine care maintained" — NO instructions, NO comments on preventive cadence
- PUPPIES: Include preventive care (vaccination progress, tick/flea, deworming) framed as health milestones
- ADULTS/SENIORS: Preventive care ONLY IF health impact or actionable gap
- CTA button: "🩺 Discuss with your vet →" (red background, links to trends Ask Your Vet)
- Guardrails: NEVER recommend medication. Test/diagnostic recs phrased "ask your vet". NO "urgent"/"alarming" tone — "High Priority" is acceptable. NO product recommendations/order buttons here.

**5. Diet Analysis Card** — `components/dashboard/DietAnalysisCard.tsx`
- 4 macro donuts in 4-column grid: Calories, Protein, Omega-3, Fat
- Each donut: SVG ring (64px), % of need center text, label below, status note
- Thresholds (GUARDRAIL SPEC):
  - Calories: >100% = amber
  - All others: >110% = amber, <80% = red
  - Omega-3 at 15% = RED (critical deficiency, not amber)
- Tap/hover shows note field (inline label)
- Missing micronutrients section: pill tags (amber), max 3, each traceable to dietary gap
- Guardrails: NO supplement recommendations here (those in Care Plan). Show % of need not pass/fail. Green NOT used for >110%.

**6. Care Plan Card** — `components/dashboard/CarePlanCard.tsx`
- Section label: "[Name]'s Care Plan"
- Sub-source: "✦ Based on lifestage, health & diet analysis" (orange, 12px)
- 3 buckets in ORDER:
  1. `✅ Continue` (green bg #F0FFF4, border #C3E6CB)
  2. `⚠️ Attend to` (red bg #FFF0F0, border #FFCDD2)
  3. `✦ Quick Fixes to Add` (orange bg #FFF3EE, border #FFD5C2)
- Each bucket has sections (e.g., "💉 Vaccines & Preventive Care"), each section has items
- Each item: name (13px 600) + freq + next due (11px meta) + status tag (s-tag-g/y/r) + optional Order button
- Orderable items MUST have `reason` field (italic 11px) — button without context = upsell
- Reason must connect insights from life stage, health, and nutrition cards
- Attend to bucket: NO orderable items (lab tests/vet visits can't be ordered)
- Continue bucket: Include ongoing branded food/supplements with "Order Now" CTA (per careplan.txt: visually same as Vaccines & Preventive Care section under Continue; first time CTA = "Order Now" since no purchase history; repeat = tag "Due Soon" when applicable)
- Order button: "Order Now →" → "✓ Added" (green, 1.8s) → "Order Again (X in cart)"
- Guardrails: Same item NEVER in two buckets. No "Buy" language. Maintain insight connectivity.

##### Care Plan Bucket Classification Engine (from PetCircle_CarePlan_Framework_1.xlsx)

The bucket assignment is NOT hardcoded — it runs a **per-test-type algorithmic classification** for each pet. This engine must be implemented on the backend.

**Decision Logic (Sheet 1) — Scenario → Bucket:**

| Scenario | Bucket | Frequency | Next Due | Status |
|----------|--------|-----------|----------|--------|
| No reports on file for this test | ✦ SUGGESTED | Baseline (life stage) | Today | 🆕 Not Started |
| Exactly 1 report | ✦ SUGGESTED | Baseline (life stage) | Last report + baseline | 🔔 Due Soon / ⚠️ Overdue |
| 2+ reports, sporadic (any gap > 2× baseline) | ✦ SUGGESTED | Baseline (life stage) | Last report + baseline | 🔁 Regularise Schedule |
| 2+ reports, periodic (all gaps within ±40% baseline) | ✔ CONTINUE | Derived (median gap) | Last report + median gap | ✅ On Track / 🔔 Due Soon |
| Periodic but median gap > baseline | ✦ SUGGESTED | Baseline (life stage) | Last report + baseline | ⬆️ Frequency Insufficient |
| Active vet prescription, no post-Rx report | ⚑ ATTEND TO | Rx due date | Prescription due date (hard override) | 📋 Prescription Active |
| Prescription + report received after Rx | Re-classify using report history | Per classification | Per classification | Per classification |
| Both prescription AND periodic history | ⚑ ATTEND TO (until fulfilled) | Rx due date | Prescription due date | 📋 Prescription Active |

**Conflict Resolution:** ATTEND TO > CONTINUE > SUGGESTED. Same test NEVER in two buckets.

**Report Redundancy Guardrails:**
- Duplicate same-day reports: keep one, discard duplicate
- Reports within 30 days of prior (non-Rx): mark newer as redundant, exclude from frequency calc

**Classification Algorithm (Sheet 4) — Steps 1-7:**
1. Count valid (non-redundant) reports → n
2. n=0 → NO_HISTORY; n=1 → SINGLE; n≥2 → continue
3. Sort by date, calculate consecutive gaps
4. Any gap > 2× baseline → SPORADIC
5. Tolerance = 0.40 × baseline_interval. All gaps within tolerance → candidate PERIODIC
6. median_gap ≤ baseline + tolerance → PERIODIC (derived_frequency = median_gap). Else → SPORADIC
7. If PERIODIC and median_gap > baseline → PERIODIC_INSUFFICIENT → SUGGESTED

**Life Stage Baselines (Sheet 2 + 3):**

Breed size determines life stage boundaries:
- Mini/Toy (<5kg): Adult 2-10yr, Senior 10+
- Small (5-10kg): Adult 2-9yr, Senior 9+
- Medium (10-25kg): Adult 2-8yr, Senior 8+
- Large (25-45kg): Adult 2-7yr, Senior 7+
- Extra Large (>45kg): Adult 2-5yr, Senior 5+

Baseline test protocol by life stage:
| Test | Puppy | Junior | Adult | Senior |
|------|-------|--------|-------|--------|
| CBC + Chemistry | 8wk & 16wk | Once at intake | Every 2 years | Annually |
| Urinalysis | 12wk | Once at intake | Every 2 years | Annually |
| Fecal Flotation | Every 2wk→12wk, monthly→6mo | Twice yearly | Annually | Annually |
| Chest X-Ray | — | — | Every 3 years | Annually |
| Abdominal USG | — | — | Every 3 years | Annually |
| ECG | — | — | — | Annually (at-risk breeds) |
| Echocardiogram | — | — | — | Annually (at-risk breeds) |
| Dental X-Ray | — | Annually | Annually | Annually |

**Key rules:**
- Baseline is OVERRIDDEN by observed periodic frequency (when periodic reports qualify), regardless of whether periodic < or > baseline
- If an item is due next year → record in backend but DO NOT show in care plan
- Logic runs INDEPENDENTLY per test_type per pet — a pet can simultaneously have CBC in CONTINUE, Urinalysis in ATTEND TO, and ECG in SUGGESTED

**7. Health Records Nav Card** — `components/dashboard/HealthRecordsNav.tsx`
- Section title: "Source Documents"
- Main text: "See [Name]'s Full Health Records" (personalized)
- Sub: "[X] reports · vet visits · lab results"
- Whole card tappable (not just arrow). Arrow: 32px orange circle with "→"
- Dynamic count. Must not be hidden below fold.

**8. Cart Floater** — `components/dashboard/CartFloater.tsx`
- Fixed position bottom-right, 48px height, orange, rounded 28px
- Shows: 🛒 + item count + total price
- ONLY appears after first `.order-btn` scrolls into view (IntersectionObserver, threshold 0.1)
- Hidden state: `opacity: 0; pointer-events: none; transform: translateY(8px)`
- Transition: `opacity 0.25s, transform 0.25s`

---

#### PAGE 2: Health Trends — `components/trends/HealthTrendsView.tsx`

**Sticky header:**
- Back button + "[Name]'s Health Trends 🐕" + spacer
- Scrollable pill tabs: "Ask Your Vet" (orange active) | "Signals" | "Care Cadence"
- Active pill: orange bg, white text. Inactive: white bg, border
- Scroll sync: IntersectionObserver with `rootMargin: '-40% 0px -55% 0px'`
- Each section: `scrollMarginTop: 130px`

**Tab 1: Ask Your Vet** — `components/trends/AskVetSection.tsx`
- Share banner: "🩺 Share this section with **Dr. [Vet Name]** at your next visit." (red bg, #FFCDD2 border)
- Per condition card (`components/trends/AskVetConditionCard.tsx`):
  - Condition tag pill (inline-flex, colored bg, dot + label)
  - MUST link to Health Conditions card on page 1
  - Headline: current clinical STATUS not history
  - Sub: latest reading or key fact
  - Sequence: Ask Vet questions → Health marker trend chart → Condition timeline
  - Questions section: "ASK YOUR VET" header, max 2 questions (3 only if essential), suggestive tone, directly askable without offending vet. NO repetitive questions.
  - Each question: amber/purple card with "Ask:" prefix (800 weight)
  - Charts:
    - Pus cell bars: red (>5 HPF), amber (1-5), green (nil). Real test dates on X-axis.
    - Platelet line: green dashed reference at 200K, points below=red, above=green. Gradient fill.
  - Timelines:
    - Episode swim-lane: max 5 nodes. If >5: start point + break + latest 4. Each node: colored circle + emoji + label + date sub-label. Never abbreviate to ambiguity.
    - Detection timeline: key nodes with UNTREATED label (red badge, most important fact)
  - Guardrails: NO treatment recommendations. Questions ONLY. NO mixing UTI/Anaplasma data. PCR vs microscopy distinction must be explicit. "1-2 HPF" is NOT normal.

**Tab 2: Health Signals** — `components/trends/SignalsSection.tsx`
- Section guideline: Latest Lab Reports + Weight chart. CBC/blood chemistry as table. Other reports (imaging/urine culture) as concise cross-report findings. Weight chart always LAST.

- Blood Panel Table (`components/trends/BloodPanelTable.tsx`):
  - Header: "🩸 Blood Panel · [DATE]" (red label)
  - Headline: contextualizing summary ("All markers normal except platelets")
  - Table: Marker | Range | Value | Status
  - Binary: green (Normal) or red (Low/High). NO amber.
  - Out-of-range rows: red on BOTH Value and Status cells
  - Sort within relevant groups (don't mix KFT markers with others)
  - Include test date in card label

- Weight Trend (`components/trends/WeightTrendCard.tsx`):
  - Label: amber. Latest 5 entries line chart.
  - Amber fill gradient under line. Final data point: RED.
  - Headline: absolute change + BCS ("±X kg over Y months. BCS trending Z/9.")
  - Sub-label: cause explanation ("X cups/day exceeds maintenance by ~Y%")
  - Recommendation box: concrete, specific, actionable (cups, walks, target weight + timeline)
  - Guardrails: NO "obese" label. NO future projection. NO calorie calculator. Only historical actuals.

- Metabolic/Organ Health (`components/trends/MetabolicCard.tsx`):
  - Label: green. 2x2 grid of green tiles.
  - Headline: reassuring ("Liver and kidneys consistently healthy.")
  - Sub: "All markers within range across every test · Imaging clear"
  - Each tile: large value + unit label. Green bg (#F0FFF4), green border (#C3E6CB).
  - MUST appear AFTER Blood Panel and Weight. Positive signal card only.
  - Guardrails: NO amber/red tiles unless genuinely out of range. NO new concerns introduced.

**Tab 3: Care Cadence** — `components/trends/CareCadenceSection.tsx`
- Section guideline: Show established recurrent activities. Order: Vaccines first, Tick & Flea second, Deworming third. Standard timeline chart format. Show additional activities (lab tests, vet visits) if pattern visible.

- Vaccinations (`components/charts/VaccinationCadence.tsx`):
  - SVG timeline: round nodes (R1-R4). Done=solid green, upcoming=dashed grey.
  - Gap labels between nodes above connecting line ("~13 months")
  - Each node: round number, date, vaccine names (smaller font OK)
  - Footer tag: "✓ Next due [date]" (green pill)
  - Headline: "All X vaccines current. Annual cadence maintained."
  - Legend: Completed (green solid), Upcoming (dashed grey)
  - Guardrails: Upcoming NOT green. NO mixing with tick/flea data.

- Tick & Flea (`components/charts/TickFleaCadence.tsx`):
  - SVG dot-plot: numbered dose circles + 1 upcoming dashed.
  - Colors: green (<=6w gap), amber (7-12w), red (>12w)
  - Critical gaps: bracket annotations with red text above timeline
  - Gap durations below each non-first dot
  - Footer: "⚠ Gaps coincide with Anaplasma reactivation" (amber pill)
  - Legend: 4 states (on time/delayed/critical/upcoming)
  - Guardrails: Frame as "coverage gaps" NOT "missed doses due to neglect"

- Deworming (`components/charts/DewormingCadence.tsx`):
  - SVG timeline: green ✓ (done), red ✗ dashed (missed), amber ! dashed (administer now)
  - Red ✗ = dashed red border (visually distinct from empty)
  - "Now" node: amber (urgent pending action), NOT green or grey
  - Footer: "🚨 Administer immediately" (red pill)
  - Headline: severity in headline ("Only 1 dose in 2+ years. Significantly overdue.")
  - Legend: Done/Missed/Administer now
  - Guardrails: 2-year gap = red NOT amber. Do NOT soften urgency. Do NOT list specific products.

---

#### PAGE 3: Reminders — `components/reminders/RemindersView.tsx`

- ViewHeader: "Care Reminders" + back button
- Items grouped by care plan section
- Each item: status dot + name + meta (Freq/Last/Next) + Edit/Delete buttons
- Edit mode: frequency dropdown (Weekly/Every 2 weeks/Monthly/Every 3 months/Every 6 months/Annual/One-time) + date input + auto-computed "Next due"
- Delete: confirmation row ("Remove this reminder?" + Remove/Cancel)
- Filter out daily-frequency items
- Home floater (black circle, 🏠) at bottom-right

---

#### PAGE 4: Cart/Checkout/Confirm

**CartView** — `components/cart/CartView.tsx`
- ViewHeader: "Your Cart"
- Each item: icon (44px, orange bg tile) + name + SKU + section + price + qty controls (−/+)
- Summary: Subtotal, Delivery (₹49 or Free if >=₹599), Total
- Free delivery nudge if applicable
- "Proceed to Checkout" button

**CheckoutView** — `components/cart/CheckoutView.tsx`
- ViewHeader: "Checkout"
- Delivery details: Name, Phone, Address, Pincode
- Payment: COD / UPI / Card radio buttons
- "Place Order" button

**ConfirmView** — `components/cart/ConfirmView.tsx`
- Green check circle, "Order Placed!", delivery estimate
- Order summary: items × qty with prices
- Total paid
- "Back to Dashboard" button

---

#### PAGE 5: Records — `components/records/RecordsView.tsx`

- ViewHeader: "[Name]'s Health Records"
- Tab pills (scrollable): Vet Visits | Lab Reports | Imaging | WhatsApp Channel (THIS ORDER per guardrails)
- Tab: Vet Visits → `VetVisitCard` (collapsible):
  - Header: icon (40px) + title + date + tag pill. Chevron toggles.
  - Expanded: Rx summary (orange bg tile) + Medications table (name/dose/duration per row) + Notes
  - Default: latest visit OPEN, rest COLLAPSED
- Other tabs: card per record with icon + title + date + tag pill + "View →"
- Home floater at bottom-right

---

### API Changes Required

**Extend `GET /dashboard/{token}` response** with:
- `vet_summary: { name, last_visit }`
- `life_stage: { stage, age_months, breed_size, traits[], essential_care[] }`
- `health_conditions_summary: [{ id, icon, title, severity, trend_label, insight }]`
- `care_plan_v2: { continue: Section[], attend: Section[], add: Section[] }` — computed by the care plan classification engine
- `diet_summary: { macros: Donut[], missing_micros: Micro[] }`
- `recognition: { report_count, bullets: Bullet[] }`

**New backend service: `care_plan_engine.py`** — Implements the full classification algorithm:
1. For each test_type for this pet:
   - Fetch all reports, remove redundant (same-day dups, <30 day non-Rx)
   - Count valid reports → classify as NO_HISTORY / SINGLE / SPORADIC / PERIODIC / PERIODIC_INSUFFICIENT
   - Check for active vet prescriptions → ATTEND TO overrides
   - Apply conflict resolution (ATTEND TO > CONTINUE > SUGGESTED)
   - Determine frequency (derived median gap for PERIODIC, baseline for others)
   - Calculate next due date
   - Assign status flag (On Track / Due Soon / Overdue / Not Started / Regularise / Prescription Active)
2. Map classifications to UI buckets: PERIODIC → Continue, PRESCRIPTION_ACTIVE → Attend To, everything else → Suggested (Quick Fixes to Add)
3. Determine breed size from breed → look up life stage → look up baseline test protocol
4. Items due next year: store in backend but EXCLUDE from care plan response
5. Add orderable food/supplements to Continue bucket with Order Now CTA

**New `GET /dashboard/{token}/health-trends-v2`**:
- `ask_vet: [{ condition card data }]`
- `signals: { blood_panel, weight, metabolic }`
- `cadence: { vaccines, flea_tick, deworming }`

**New `GET /dashboard/{token}/records-v2`**:
- `vet_visits: [{ title, date, tag, rx, medications[], notes }]`
- `records: [{ icon, type, title, date, tag, tag_color, tag_bg }]`

---

### Files to Remove After Migration
- `components/tabs/OverviewTab.tsx`
- `components/tabs/HealthTab.tsx`
- `components/tabs/HygieneTab.tsx`
- `components/tabs/NutritionTab.tsx`
- `components/tabs/ConditionsTab.tsx`
- `components/DashboardTabBar.tsx`
- `components/DashboardHeader.tsx`
- `components/NudgesView.tsx`
- Old unused components: `PetProfileCard`, `ActivityRings`, `PreventiveRecordsTable`, `HealthScoreRing`, `BloodUrineSection`, `HealthTrendsSection`, `DocumentsSection`, `MedicinesSection`, `RemindersSection`

### Implementation Order
1. **Backend: Care Plan Classification Engine** — `backend/app/services/care_plan_engine.py`
   - Breed size lookup (5 categories from weight/breed)
   - Life stage classification (breed-size-aware boundaries)
   - Baseline test protocol per life stage (Sheet 3)
   - Report frequency classification algorithm (Steps 1-7 from Sheet 4)
   - Report redundancy guards (same-day dups, <30 day non-Rx)
   - Prescription override logic
   - Conflict resolution (ATTEND TO > CONTINUE > SUGGESTED)
   - Next due date calculation
   - Items due next year: exclude from response
   - Branded food/supplement placement in Continue bucket
2. **Backend: Enriched dashboard endpoint** — extend `GET /dashboard/{token}` with care_plan_v2, life_stage, vet_summary, recognition, diet_summary, health_conditions_summary
3. **Backend: Health trends + Records endpoints** — `/health-trends-v2`, `/records-v2`
4. CSS variables + types in `api.ts`
5. Shared chart components (Donut, Bar, Line, Timeline, Cadence)
6. Dashboard cards (Banner → Recognition → LifeStage → Conditions → Diet → CarePlan → RecordsNav → Floater)
7. DashboardView wrapper composing all cards
8. Health Trends sub-views (AskVet → Signals → CareCadence → wrapper)
9. Records view (VetVisitCard → RecordCard → wrapper)
10. Reminders view rewrite
11. Cart simplification
12. DashboardClient.tsx rewrite (orchestrator)
13. Cleanup old components

### Verification
- Open dashboard in browser at 430px width
- Verify each card matches JSX reference visually
- Test all navigation flows: bell→reminders, CTA→trends, nav→records, order→cart
- Test cart floater only appears on orderable item scroll
- Test "Added" animation (1.8s green)
- Test scroll-sync on Health Trends tabs
- Test vet visit card collapse/expand (latest open by default)
- Verify all guardrail rules (no alarming language, no medication recommendations, correct donut thresholds, etc.)

