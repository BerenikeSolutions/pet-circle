# Requirements: Dashboard Rebuild

## Introduction

Rebuild the PetCircle frontend dashboard from a 5-tab data management layout to a narrative-driven, scrolling dashboard with clinical analysis, visual health trends, and care commerce. The backend gains a new Care Plan Classification Engine that algorithmically assigns preventive items to Continue/Attend To/Suggested buckets. New API endpoints serve health trends and records data. The frontend replaces tab navigation with view-switching across 5 pages: Dashboard, Health Trends, Reminders, Cart/Checkout/Confirm, and Records.

---

## Requirements

### Requirement 1: Design System Update

**User Story:** As a pet parent, I want a visually warm, modern dashboard so that I feel confident in the information presented.

#### Acceptance Criteria

1. The system SHALL use the updated CSS variables: `--orange: #FF6B35`, `--amber: #FF9F1C`, `--black: #1A1A1A`, `--green: #34C759`, `--red: #FF3B30`, `--bg: #F7F4F0`, `--warm: #FDFAF7`, `--border: #E8E4DF`, plus tint and text variables as specified.
2. The system SHALL use DM Sans for body text and Fraunces for brand/headings.
3. The system SHALL constrain max-width to 430px.
4. The system SHALL use `--radius: 16px` and `--rs: 10px` for border radii.

---

### Requirement 2: Navigation Model

**User Story:** As a pet parent, I want to navigate between views without a tab bar so that the dashboard feels like a continuous narrative.

#### Acceptance Criteria

1. WHEN the dashboard loads THEN the system SHALL display the scrolling dashboard view (no tab bar).
2. The system SHALL support view states: `dashboard | trends | reminders | cart | checkout | confirm | records`.
3. WHEN the user taps the bell icon THEN the system SHALL navigate to the reminders view.
4. WHEN the user taps "Discuss with your vet" CTA THEN the system SHALL navigate to the trends view (Ask Your Vet tab).
5. WHEN the user taps "See [Name]'s Full Health Records" THEN the system SHALL navigate to the records view.
6. WHEN the user taps the cart floater THEN the system SHALL navigate to the cart view.
7. WHEN the user taps a back button on any sub-view THEN the system SHALL return to the dashboard view.

---

### Requirement 3: Profile Banner

**User Story:** As a pet parent, I want to see my pet's key info at a glance in a warm banner.

#### Acceptance Criteria

1. The system SHALL display a gradient banner (`linear-gradient(135deg, #E8412A, #FF6B35, #FF8C5A)`).
2. Row 1 SHALL show "PetCircle" (Fraunces 18px 700) and a bell icon (36px circle, rgba white background).
3. Row 2 SHALL show a species-matched avatar emoji (56x56), pet name (Fraunces 24px 700 white), and breed/sex/age/weight in ONE line (12px) with no text spillover.
4. Row 3 SHALL show vet info: `🩺 Vet [full name] · Last visit [date]` — the vet name SHALL never be abbreviated.
5. The banner SHALL NOT display health status, alerts, scores, next-appointment dates, or weight as a health concern.

---

### Requirement 4: Recognition Card ("What We Found")

**User Story:** As a pet parent, I want to understand what PetCircle learned from my reports so that I trust the analysis.

#### Acceptance Criteria

1. The system SHALL display: "We reviewed **X reports** and WhatsApp chat and identified [name]'s current care routine."
2. The card SHALL include a "View all reports" link that navigates to the records view.
3. The card SHALL show max 3 bullets, each ONE line only (no text spillover), ordered: conditions first, preventive second, diet last.
4. The system SHALL use the label "active health conditions" (not "active conditions").
5. Each bullet SHALL be traceable to a source document or record. The system SHALL NOT infer, recommend, or use alarming language. Tone SHALL be observational.

---

### Requirement 5: Life Stage Card

**User Story:** As a pet parent, I want to understand where my pet is in their life and what to expect at this stage.

#### Acceptance Criteria

1. The section label SHALL read "What to expect as [name] turns [age]".
2. The system SHALL display a 4-stage progress bar: Puppy (10%) → Junior (12%) → Adult (45%) → Senior (33%).
3. The current life stage SHALL be filled with an orange gradient; other stages SHALL recede (50% opacity).
4. A marker (18px circle, orange with white border) SHALL be positioned at the computed `ageMonths` position.
5. A caption SHALL read "[Name] is here · [age]" (centered, orange, 11px).
6. Trait pills SHALL be life-stage-specific FOR THE BREED (not breed-generic), max 2 lines, ordered: behavior/energy first → appetite/physiology. Colors: green (positive), yellow (watch), red (concern), neutral (personality).
7. Trait pills SHALL NEVER use alarming phrases — they SHALL inform how body is changing and what to monitor.
8. Essential care items SHALL be max 2, each linked to pills above, displayed as amber background tiles with icon + 1-line detail.
9. The current stage SHALL visually dominate. Age label SHALL be computed from `ageMonths`, never hardcoded.

---

### Requirement 6: Health Conditions Card

**User Story:** As a pet parent, I want to see my pet's active health conditions with clinical context so I can discuss them with my vet.

#### Acceptance Criteria

1. IF the pet has ongoing conditions THEN the system SHALL show ALL ongoing conditions and recurrent patterns (not just red severity).
2. Each condition SHALL display: a red dot (7px), title, trend label ("Active · Since Feb 2025"), and a 1-line insight (12px, left border 2px #FFCDD2) explaining the mechanism (not a diagnosis).
3. IF there are more than 2 ongoing/recurrent conditions THEN the system SHALL show all. Insights SHALL be limited to max 2 only if there are no ongoing/recurrent patterns.
4. IF the pet has no conditions THEN the system SHALL show "No active concerns · Routine care maintained" — no instructions, no comments on preventive cadence.
5. IF the pet is a puppy THEN the system SHALL include preventive care (vaccination progress, tick/flea, deworming) framed as health milestones.
6. IF the pet is adult/senior THEN preventive care SHALL appear ONLY IF there is health impact or an actionable gap.
7. The CTA button SHALL read "🩺 Discuss with your vet →" (red background) and navigate to the trends Ask Your Vet section.
8. The system SHALL NEVER recommend medication. Test/diagnostic recommendations SHALL be phrased "ask your vet". The system SHALL NOT use "urgent"/"alarming" tone — "High Priority" is acceptable. No product recommendations or order buttons SHALL appear on this card.

---

### Requirement 7: Diet Analysis Card

**User Story:** As a pet parent, I want to see how my pet's diet meets their nutritional needs so I can make informed food choices.

#### Acceptance Criteria

1. The system SHALL display 4 macro donuts in a 4-column grid: Calories, Protein, Omega-3, Fat.
2. Each donut SHALL be an SVG ring (64px) with % of need as center text, label below, and status note.
3. Thresholds SHALL be: Calories >100% = amber; all others >110% = amber, <80% = red; Omega-3 at 15% = RED (critical deficiency, not amber).
4. WHEN the user taps/hovers a donut THEN the system SHALL show the note field as an inline label.
5. Missing micronutrients SHALL be displayed as pill tags (amber), max 3, each traceable to a dietary gap.
6. The system SHALL NOT show supplement recommendations on this card. The system SHALL show % of need, not pass/fail. Green SHALL NOT be used for >110%.

---

### Requirement 8: Care Plan Card

**User Story:** As a pet parent, I want a personalized care plan with clear buckets (continue, attend to, add) so I know what actions to take.

#### Acceptance Criteria

1. The section label SHALL read "[Name]'s Care Plan".
2. A sub-source line SHALL read "✦ Based on lifestage, health & diet analysis" (orange, 12px).
3. The card SHALL display 3 buckets in fixed order: (1) ✅ Continue (green bg #F0FFF4, border #C3E6CB), (2) ⚠️ Attend to (red bg #FFF0F0, border #FFCDD2), (3) ✦ Quick Fixes to Add (orange bg #FFF3EE, border #FFD5C2).
4. Each bucket SHALL contain sections (e.g., "💉 Vaccines & Preventive Care"), each section with items showing: name (13px 600), freq, next due (11px meta), status tag, and optional Order button.
5. Orderable items MUST have a `reason` field (italic 11px). An order button without context SHALL be treated as upsell and is NOT allowed.
6. The reason SHALL connect insights from life stage, health, and nutrition cards.
7. The "Attend to" bucket SHALL NOT contain orderable items (lab tests/vet visits cannot be ordered).
8. The "Continue" bucket SHALL include ongoing branded food/supplements with "Order Now" CTA.
9. WHEN the user taps "Order Now →" THEN the button SHALL change to "✓ Added" (green, 1.8s), then to "Order Again (X in cart)".
10. The same item SHALL NEVER appear in two buckets. No "Buy" language SHALL be used.

---

### Requirement 9: Care Plan Classification Engine (Backend)

**User Story:** As the system, I want to algorithmically classify each preventive test into the correct care plan bucket so that recommendations are evidence-based and per-pet.

#### Acceptance Criteria

1. The engine SHALL run INDEPENDENTLY per test_type per pet.
2. The engine SHALL implement the 7-step classification algorithm:
   - Step 1: Count valid (non-redundant) reports → n
   - Step 2: n=0 → NO_HISTORY; n=1 → SINGLE; n≥2 → continue
   - Step 3: Sort by date, calculate consecutive gaps
   - Step 4: Any gap > 2× baseline → SPORADIC
   - Step 5: Tolerance = 0.40 × baseline_interval. All gaps within tolerance → candidate PERIODIC
   - Step 6: median_gap ≤ baseline + tolerance → PERIODIC (derived_frequency = median_gap). Else → SPORADIC
   - Step 7: IF PERIODIC AND median_gap > baseline → PERIODIC_INSUFFICIENT → SUGGESTED
3. Report redundancy guards SHALL apply: duplicate same-day reports keep one; reports within 30 days of prior (non-Rx) are marked redundant and excluded from frequency calc.
4. IF an active vet prescription exists with no post-Rx report THEN the item SHALL be classified as ATTEND TO with prescription due date as next due.
5. Conflict resolution SHALL follow: ATTEND TO > CONTINUE > SUGGESTED. The same test SHALL NEVER appear in two buckets.
6. The engine SHALL determine breed size from weight/breed using 5 categories (Mini/Toy <5kg, Small 5-10kg, Medium 10-25kg, Large 25-45kg, Extra Large >45kg).
7. The engine SHALL classify life stage using breed-size-aware boundaries (e.g., Large breed: Senior at 7+, Extra Large: Senior at 5+).
8. The engine SHALL look up baseline test protocol per life stage per test type (CBC, Urinalysis, Fecal, X-Ray, USG, ECG, Echo, Dental).
9. IF an item is due next year THEN the engine SHALL record it in the backend but EXCLUDE it from the care plan response.
10. Baseline SHALL be OVERRIDDEN by observed periodic frequency when periodic reports qualify, regardless of whether periodic < or > baseline.
11. Mapping: PERIODIC → Continue, PRESCRIPTION_ACTIVE → Attend To, all others (NO_HISTORY, SINGLE, SPORADIC, PERIODIC_INSUFFICIENT) → Suggested.
12. The engine SHALL place orderable food/supplements in the Continue bucket with Order Now CTA.

---

### Requirement 10: Health Records Nav Card

**User Story:** As a pet parent, I want a clear entry point to my pet's full health records.

#### Acceptance Criteria

1. The section title SHALL read "Source Documents".
2. The main text SHALL read "See [Name]'s Full Health Records" (personalized).
3. A sub-line SHALL show "[X] reports · vet visits · lab results" (dynamic count).
4. The whole card SHALL be tappable (not just the arrow). The arrow SHALL be a 32px orange circle with "→".
5. The card SHALL NOT be hidden below the fold.

---

### Requirement 11: Cart Floater

**User Story:** As a pet parent, I want to see my cart status while browsing the care plan so I can check out easily.

#### Acceptance Criteria

1. The floater SHALL be fixed-position bottom-right, 48px height, orange, rounded 28px.
2. The floater SHALL show: 🛒 + item count + total price.
3. The floater SHALL ONLY appear after the first `.order-btn` scrolls into view (IntersectionObserver, threshold 0.1).
4. Hidden state SHALL use `opacity: 0; pointer-events: none; transform: translateY(8px)`.
5. Transition SHALL be `opacity 0.25s, transform 0.25s`.

---

### Requirement 12: Health Trends — Ask Your Vet

**User Story:** As a pet parent, I want vet-ready questions and clinical trend data to share with my veterinarian.

#### Acceptance Criteria

1. The trends view SHALL have a sticky header with back button, "[Name]'s Health Trends 🐕", and scrollable pill tabs: "Ask Your Vet" (default active, orange), "Signals", "Care Cadence".
2. Active pill SHALL be orange bg with white text; inactive SHALL be white bg with border.
3. Scroll sync SHALL use IntersectionObserver with `rootMargin: '-40% 0px -55% 0px'`; each section SHALL have `scrollMarginTop: 130px`.
4. A share banner SHALL read: "🩺 Share this section with **Dr. [Vet Name]** at your next visit." (red bg, #FFCDD2 border).
5. Each condition card SHALL link to the Health Conditions card on the dashboard.
6. The headline SHALL describe current clinical STATUS (not history).
7. Questions section: "ASK YOUR VET" header, max 2 questions (3 only if essential), suggestive tone, directly askable without offending vet. No repetitive questions.
8. Charts SHALL use real test dates on X-axis. Pus cell bars: red (>5 HPF), amber (1-5), green (nil). Platelet line: green dashed reference at 200K, below=red, above=green, gradient fill.
9. Timelines: max 5 nodes per swim-lane. If >5: start point + break + latest 4. Each node: colored circle + emoji + label + date sub-label. Never abbreviate to ambiguity.
10. The system SHALL NOT make treatment recommendations. Questions ONLY. No mixing UTI/Anaplasma data. PCR vs microscopy distinction SHALL be explicit. "1-2 HPF" SHALL NOT be labeled as normal.

---

### Requirement 13: Health Trends — Signals

**User Story:** As a pet parent, I want to see my pet's lab results and weight trends in a clear visual format.

#### Acceptance Criteria

1. Blood Panel Table SHALL show: header "🩸 Blood Panel · [DATE]", headline summary, table with Marker|Range|Value|Status.
2. Status SHALL be binary: green (Normal) or red (Low/High). No amber.
3. Out-of-range rows SHALL be red on BOTH Value and Status cells.
4. Rows SHALL be sorted within relevant groups (not mixing KFT markers with others).
5. Weight Trend SHALL show latest 5 entries as a line chart with amber fill gradient. Final data point SHALL be RED.
6. Headline SHALL show absolute change + BCS ("±X kg over Y months. BCS trending Z/9.").
7. Recommendation box SHALL be concrete, specific, actionable (cups, walks, target weight + timeline).
8. The system SHALL NOT use "obese" label, future projections, or calorie calculators. Only historical actuals.
9. Metabolic/Organ Health card SHALL appear AFTER Blood Panel and Weight. It SHALL be a positive signal card only (green tiles).
10. IF all metabolic markers are within range THEN the system SHALL display a 2x2 grid of green tiles with reassuring headline.

---

### Requirement 14: Health Trends — Care Cadence

**User Story:** As a pet parent, I want to see my pet's vaccination, flea/tick, and deworming patterns over time.

#### Acceptance Criteria

1. The order SHALL be: Vaccines first, Tick & Flea second, Deworming third.
2. Vaccination cadence: SVG timeline with round nodes (R1-R4). Done=solid green, upcoming=dashed grey. Gap labels between nodes. Footer: "✓ Next due [date]" (green pill). Upcoming SHALL NOT be green.
3. Tick & Flea cadence: SVG dot-plot with numbered dose circles. Colors: green (<=6w gap), amber (7-12w), red (>12w). Critical gaps SHALL have bracket annotations with red text. Footer: "⚠ Gaps coincide with Anaplasma reactivation" (amber pill). Frame as "coverage gaps" NOT "missed doses due to neglect".
4. Deworming cadence: SVG timeline with green ✓ (done), red ✗ dashed (missed), amber ! dashed (administer now). "Now" node SHALL be amber (NOT green or grey). A 2-year gap SHALL be red NOT amber. Urgency SHALL NOT be softened. No specific products listed.

---

### Requirement 15: Reminders View

**User Story:** As a pet parent, I want to manage my care reminders with the ability to edit frequency and dates.

#### Acceptance Criteria

1. The view SHALL have a ViewHeader: "Care Reminders" + back button.
2. Items SHALL be grouped by care plan section.
3. Each item SHALL show: status dot, name, meta (Freq/Last/Next), Edit/Delete buttons.
4. Edit mode SHALL include: frequency dropdown (Weekly/Every 2 weeks/Monthly/Every 3 months/Every 6 months/Annual/One-time), date input, and auto-computed "Next due".
5. Delete SHALL show a confirmation row ("Remove this reminder?" + Remove/Cancel).
6. Daily-frequency items SHALL be filtered out.
7. A home floater (black circle, 🏠) SHALL appear at bottom-right.

---

### Requirement 16: Cart, Checkout, and Confirm

**User Story:** As a pet parent, I want a streamlined ordering flow from care plan to checkout.

#### Acceptance Criteria

1. CartView SHALL show: ViewHeader "Your Cart", each item with icon (44px orange bg tile), name, SKU, section, price, qty controls (−/+).
2. Summary SHALL show: Subtotal, Delivery (₹49 or Free if >=₹599), Total. A free delivery nudge SHALL appear if applicable.
3. "Proceed to Checkout" button SHALL navigate to CheckoutView.
4. CheckoutView SHALL show: ViewHeader "Checkout", delivery details (Name, Phone, Address, Pincode), payment options (COD/UPI/Card radio buttons), "Place Order" button.
5. ConfirmView SHALL show: green check circle, "Order Placed!", delivery estimate, order summary (items × qty with prices), total paid, "Back to Dashboard" button.

---

### Requirement 17: Records View

**User Story:** As a pet parent, I want to browse all my pet's health records organized by type.

#### Acceptance Criteria

1. The view SHALL have a ViewHeader: "[Name]'s Health Records".
2. Tab pills (scrollable) SHALL be in order: Vet Visits | Lab Reports | Imaging | WhatsApp Channel.
3. Vet Visits tab SHALL use collapsible cards: header with icon (40px), title, date, tag pill, chevron toggle. Expanded view SHALL show: Rx summary (orange bg tile), Medications table (name/dose/duration), Notes.
4. The latest vet visit SHALL be OPEN by default; all others SHALL be COLLAPSED.
5. Other tabs SHALL show cards with: icon, title, date, tag pill, "View →".
6. A home floater SHALL appear at bottom-right.

---

### Requirement 18: Enriched Dashboard API

**User Story:** As the frontend, I need enriched data from the dashboard API to render the new narrative dashboard.

#### Acceptance Criteria

1. `GET /dashboard/{token}` response SHALL be extended with: `vet_summary`, `life_stage`, `health_conditions_summary`, `care_plan_v2`, `diet_summary`, `recognition`.
2. `vet_summary` SHALL include: `name`, `last_visit`.
3. `life_stage` SHALL include: `stage`, `age_months`, `breed_size`, `traits[]`, `essential_care[]`.
4. `health_conditions_summary` SHALL include: `[{ id, icon, title, severity, trend_label, insight }]`.
5. `care_plan_v2` SHALL include: `{ continue: Section[], attend: Section[], add: Section[] }` — computed by the classification engine.
6. `diet_summary` SHALL include: `{ macros: Donut[], missing_micros: Micro[] }`.
7. `recognition` SHALL include: `{ report_count, bullets: Bullet[] }`.

---

### Requirement 19: Health Trends API

**User Story:** As the frontend, I need a dedicated endpoint for health trends data.

#### Acceptance Criteria

1. `GET /dashboard/{token}/health-trends-v2` SHALL return: `ask_vet`, `signals`, `cadence`.
2. `ask_vet` SHALL include per-condition card data: condition tag, headline, questions, chart data, timeline data.
3. `signals` SHALL include: `blood_panel` (table data), `weight` (trend data), `metabolic` (tile data).
4. `cadence` SHALL include: `vaccines` (timeline nodes), `flea_tick` (dot-plot data), `deworming` (timeline data).

---

### Requirement 20: Records API

**User Story:** As the frontend, I need a dedicated endpoint for structured health records.

#### Acceptance Criteria

1. `GET /dashboard/{token}/records-v2` SHALL return: `vet_visits`, `records`.
2. `vet_visits` SHALL include: `[{ title, date, tag, rx, medications[], notes }]`.
3. `records` SHALL include: `[{ icon, type, title, date, tag, tag_color, tag_bg }]`.

---

## Resolved Questions

1. **Life stage traits**: GPT-generated on first access per pet, then stored in DB and served from cache on subsequent loads. Regenerate only when life stage changes.
2. **Vet summary**: Multiple vets are captured from prescription reports and stored in care contacts. The vet with the most mentions across reports becomes the "primary vet" shown in the banner. Backend must compute primary vet by mention count.
3. **Diet summary**: Use existing `nutrition_service.py` logic. Extend/modify as needed to produce macro % of need and missing micronutrient data for the donut format.
4. **Care Plan reason field**: GPT-generated always (not cached). Each orderable item's reason is generated per dashboard load, connecting life stage + health + nutrition insights for that specific pet.
5. **JSX reference files**: Available at `project details/PetDashboard_3103_4.jsx` and `project details/JSX_Guardrails.xlsx`. Use for pixel-perfect implementation and guardrail compliance.
