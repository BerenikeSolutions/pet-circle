# Dashboard Rebuild — Complete Reference Data

## Prototype Structure (petcircle_150326_8.jsx)
The prototype is a single-file React app with 6 "steps": WhatsApp chat → Processing → Dashboard → Nudges → Reminders → Cart.
We only need **Step 3 (DashboardStep)** and **Step 6 (CartStep)** for the rebuild. The rest (WhatsApp, Processing, Nudges, Reminders) are NOT part of the dashboard rebuild.

---

## Constants & Theme from Prototype

### Status Config
```ts
export const STATUS_CONFIG = {
  overdue:  { color: '#FF3B30', bg: '#FFF0F0', label: 'Overdue' },
  upcoming: { color: '#FF9500', bg: '#FFF6ED', label: 'Due Soon' },
  done:     { color: '#34C759', bg: '#F0FFF4', label: 'Up to Date' },
  missing:  { color: '#8E8E93', bg: '#F2F2F7', label: 'No Record' },
  managed:  { color: '#007AFF', bg: '#F0F6FF', label: 'Managed' },
  urgent:   { color: '#FF3B30', bg: '#FFF0F0', label: 'Refill Now' },
  ok:       { color: '#34C759', bg: '#F0FFF4', label: 'Adequate' },
};
```

### Brand Colors (CSS vars)
```css
:root {
  --brand-primary: #D44800;
  --brand-gradient: linear-gradient(135deg, #D44800 0%, #FF9A6C 100%);
  --bg-app: #F7F4F0;
  --status-overdue: #FF3B30;
  --status-upcoming: #FF9500;
  --status-done: #34C759;
  --status-missing: #8E8E93;
  --status-managed: #007AFF;
}
```

### Fonts
- Body: DM Sans (400/500/600/700)
- Headings: Fraunces (700/900)

### DASHBOARD_TABS
```ts
const DASHBOARD_TABS = [["overview","Overview"],["medical","Health"],["grooming","Hygiene"],["nutrition","Nutrition"],["conditions","Conditions"]];
```

---

## Mock Data Constants (from prototype)

### DAILY_HYGIENE_ITEMS
```ts
[
  { id:"coat-brush",  icon:"🪮", name:"Coat Brushing",  note:"Prevents matting & reduces shedding.", lastDone:"Today", status:"done" },
  { id:"teeth-brush", icon:"🦷", name:"Teeth Brushing", note:"Daily brushing prevents plaque.", lastDone:"2 days ago", status:"overdue" },
  { id:"ear-clean",   icon:"👂", name:"Ear Cleaning",   note:"Floppy ears trap moisture.", lastDone:"10/01/2024", status:"upcoming" },
  { id:"eye-wipe",    icon:"👁️", name:"Eye Wipe",       note:"Prevents tear stain buildup.", lastDone:"01/02/2024", status:"upcoming" },
]
```

### PERIODIC_HYGIENE_ITEMS
```ts
[
  { id:"bath-nail",  icon:"🛁", name:"Bath, brush & nail trim", note:"Monthly baths manage shedding.", lastDone:"10/01/2024", status:"overdue" },
  { id:"anal-gland", icon:"🐾", name:"Anal gland cleaning",     note:"Prevents impaction.", lastDone:"Not recorded", status:"upcoming" },
]
```

### NUTRITION_MACROS
```ts
[
  { name:"Protein",       icon:"🥩", actual:28, target:30, unit:"%", status:"low",  note:"Slightly below optimal." },
  { name:"Fat",           icon:"🧈", actual:14, target:14, unit:"%", status:"ok",   note:"Within healthy range." },
  { name:"Carbohydrates", icon:"🌾", actual:46, target:40, unit:"%", status:"high", note:"Slightly elevated." },
  { name:"Fibre",         icon:"🥦", actual:3,  target:4,  unit:"%", status:"low",  note:"Could be improved." },
  { name:"Moisture",      icon:"💧", actual:10, target:10, unit:"%", status:"ok",   note:"Normal for dry kibble." },
]
```

### NUTRITION_VITAMINS
```ts
[
  { name:"Vitamin E",   status:"Low",      supplement:"Vit E 400 IU",       price:"₹349/mo", priority:"high" },
  { name:"Vitamin D",   status:"Low",      supplement:"Calcitriol 0.25mcg", price:"₹299/mo", priority:"medium" },
  { name:"Vitamin B12", status:"Adequate", supplement:null, price:null, priority:"ok" },
  { name:"Vitamin C",   status:"Adequate", supplement:null, price:null, priority:"ok" },
]
```

### NUTRITION_MINERALS
```ts
[
  { name:"Glucosamine", icon:"🦴", status:"Missing",  priority:"urgent", reason:"Essential for cartilage repair.", supplement:"Cosequin DS Chewable", price:"₹799/mo" },
  { name:"Calcium",     icon:"🥛", status:"Adequate", priority:"ok",     reason:"Supplement in use.",             supplement:null, price:null },
  { name:"Zinc",        icon:"⚡", status:"Adequate", priority:"ok",     reason:"Sufficient zinc from food.",     supplement:null, price:null },
  { name:"Iron",        icon:"🔩", status:"Adequate", priority:"ok",     reason:"Adequate from kibble.",          supplement:null, price:null },
]
```

### NUTRITION_OTHERS
```ts
[
  { name:"Omega-3",    icon:"🐟", status:"Adequate", priority:"ok",     reason:"Supplement in use.",     supplement:null, price:null },
  { name:"Probiotics", icon:"🦠", status:"Low",      priority:"medium", reason:"Goldens are digestive-sensitive.", supplement:"FortiFlora Probiotic", price:"₹649/mo" },
]
```

### NUTRITION_IMPROVE
```ts
[
  { dot:"#FF3B30", text:"Glucosamine missing → critical for hip joint support" },
  { dot:"#FF9500", text:"Vitamin E & D low → immunity & bone density" },
  { dot:"#FF9500", text:"Protein slightly low → muscle recovery & energy" },
  { dot:"#FF9500", text:"Calories below target → increase daily portions" },
  { dot:"#FFCC00", text:"Probiotics low → gut health & coat quality" },
]
```

### DOC_SECTIONS (mock)
```ts
[
  { id:"vaccination",  icon:"💉", label:"Vaccination Card",  color:"#34C759", bg:"#F0FFF4", files:[
    { name:"vaccine_card.jpg", parsed:"Rabies · 20 Jun 2023", note:"Next due: 20 Jun 2024", status:"Parsed ✓" },
    { name:"vaccine_card.jpg", parsed:"9-in-1 (DHPPiL+) · 12 Jun 2023", note:"Next due: 12 Jun 2024", status:"Parsed ✓" }
  ]},
  { id:"prescriptions",icon:"📋", label:"Prescriptions", color:"#007AFF", bg:"#F0F6FF", files:[
    { name:"hip_xray_report.jpg", parsed:"Meloxicam 1mg — once daily", note:"Hip dysplasia management", status:"Parsed ✓" },
    { name:"hip_xray_report.jpg", parsed:"Omega-3 Supplement — 1 capsule daily", note:"Joint inflammation support", status:"Parsed ✓" }
  ]},
  { id:"reports", icon:"🔬", label:"Reports", color:"#FF9500", bg:"#FFF6ED", files:[
    { name:"hip_xray_report.jpg", parsed:"Hip X-Ray — Mild dysplasia confirmed", note:"Dr. Meera Nair · 10 Sep 2023", status:"Parsed ✓" },
    { name:"deworming_record.jpg", parsed:"Deworming record · Last done 01 Jan 2024", note:"Next due: 01 Apr 2024", status:"Parsed ✓" }
  ]},
]
```

### Cart Items (cartItemsData)
```ts
[
  { id:"c1",  icon:"🏠", name:"Home Vet Visit",              sub:"Vaccination — DHPPiL + Rabies boosters",     price:499,  tag:"OVERDUE",         tagColor:"#FF3B30", inCart:true  },
  { id:"c2",  icon:"🪱", name:"Bayer Drontal Plus",          sub:"Deworming — overdue since Apr 2024",         price:189,  tag:"OVERDUE",         tagColor:"#FF3B30", inCart:true  },
  { id:"c3",  icon:"🫙", name:"Zesty Paws Omega-3",          sub:"Joint supplement — hip dysplasia refill",    price:349,  tag:"CRITICAL REFILL", tagColor:"#FF3B30", inCart:true  },
  { id:"c4",  icon:"🦴", name:"Nutramax Cosequin DS",        sub:"Joint supplement — glucosamine missing",     price:799,  tag:"MISSING",         tagColor:"#FF3B30", inCart:true  },
  { id:"c5",  icon:"🐛", name:"Boehringer NexGard",          sub:"Flea & tick protection — no record found",   price:420,  tag:"NO RECORD",       tagColor:"#FF9500", inCart:true  },
  { id:"c6",  icon:"🌿", name:"Vit E 400 IU Softgel",        sub:"Antioxidant — breed gap for Goldens",        price:349,  tag:"HIGH PRIORITY",   tagColor:"#FF9500", inCart:false },
  { id:"c7",  icon:"🛁", name:"Full Grooming Session",        sub:"Bath, brush & nail trim",                    price:799,  tag:"OVERDUE",         tagColor:"#FF9500", inCart:false },
  { id:"c8",  icon:"✂️", name:"Home Grooming — Nail Trim",   sub:"Nail care — affects gait & joints",          price:299,  tag:"OVERDUE",         tagColor:"#FF9500", inCart:false },
  { id:"c9",  icon:"💉", name:"Kennel Cough Vaccine",        sub:"Vaccination — recommended for park/boarding", price:349,  tag:"NOT GIVEN",       tagColor:"#FF9500", inCart:false },
  { id:"c10", icon:"💉", name:"CCoV (Covid) Vaccine",        sub:"Vaccination — optional, no record found",    price:349,  tag:"NOT GIVEN",       tagColor:"#FF9500", inCart:false },
  { id:"c11", icon:"🦠", name:"Purina FortiFlora Probiotic", sub:"Gut health — breed recommendation",          price:649,  tag:"BREED REC",       tagColor:"#007AFF", inCart:false },
  { id:"c12", icon:"☀️", name:"Sun Pharma Calcitriol",       sub:"Vitamin D — bone density, hip support",      price:299,  tag:"LOW",             tagColor:"#B8860B", inCart:false },
  { id:"c13", icon:"🥣", name:"Royal Canin GR Adult",        sub:"Main food — breed-specific kibble reorder",  price:2499, tag:"REORDER",         tagColor:"#34C759", inCart:false },
  { id:"c14", icon:"🩺", name:"Home Vet — Wellness Exam",    sub:"Annual checkup — due Mar 2025",              price:799,  tag:"UPCOMING",        tagColor:"#007AFF", inCart:false },
]
```

### PAYMENT_METHODS
```ts
[
  { id:"upi",  label:"UPI",              icon:"📱", sub:"Pay via any UPI app" },
  { id:"card", label:"Card",             icon:"💳", sub:"Credit / Debit card" },
  { id:"net",  label:"Net Banking",      icon:"🏦", sub:"All major banks" },
  { id:"cod",  label:"Cash on Delivery", icon:"💵", sub:"Pay when delivered" },
]
```

### WhatsApp Reminders (whatsappReminders)
```ts
[
  { id:"r1", type:"deworming",  daysOut:7,  status:"upcoming", icon:"🪱", title:"Bruno's deworming is due in 1 week",     body:"Hi Priya 🐾 Bruno's deworming is due on 01 Apr...", actions:[{label:"🛒 Order Medicine — ₹189",color:"#25D366"},{label:"📍 Find Vet Nearby",color:"#075E54"}] },
  { id:"r2", type:"vaccine",    daysOut:7,  status:"upcoming", icon:"💉", title:"Bruno's Rabies booster due in 1 week",   body:"Hi Priya 🐾 Bruno's Rabies booster is due 20 Jun 2025...", actions:[{label:"🏠 Book Home Vet — ₹499",color:"#25D366"},{label:"📍 Find Clinic Nearby",color:"#075E54"}] },
  { id:"r3", type:"supplement", daysOut:7,  status:"upcoming", icon:"💊", title:"Meloxicam refill due in 1 week",         body:"Hi Priya 🐾 Bruno's Meloxicam refill is due 01 Apr...", actions:[{label:"🔄 Reorder Meloxicam — ₹280",color:"#25D366"},{label:"⏭ Remind Later",color:"#8E8E93"}] },
  { id:"r4", type:"deworming",  daysOut:0,  status:"due",      icon:"🪱", title:"Bruno's deworming is due TODAY",         body:"Priya, today is the day for Bruno's deworming 🐾...", actions:[{label:"🛒 Order Now — ₹189",color:"#FF9500"},{label:"✅ Already Done — Log It",color:"#34C759"}] },
  { id:"r5", type:"deworming",  daysOut:-7, status:"overdue",  icon:"🚨", title:"🚨 Bruno's deworming is 1 week overdue", body:"Priya, Bruno's deworming was due Apr 1 and is now a week overdue...", actions:[{label:"🛒 Order Now — ₹189",color:"#FF3B30"},{label:"✅ Already Done — Log It",color:"#34C759"}] },
]
```

### FREQ_MODAL constants
```ts
const FREQ_MODAL_UNITS = ["day","week","month","year"];
const FREQ_MODAL_OPTIONS = { day:[1,2,3], week:[1,2,3,4,6], month:[1,2,3,6], year:[1] };
const VAX_FREQ_OPTS = [6, 9, 12, 18, 24];
const VAX_FREQ_LABELS = { 6:"Every 6 months", 9:"Every 9 months", 12:"Yearly", 18:"Every 18 months", 24:"Every 2 years" };
```

### WA Reminder Colors
```ts
const WA_REMINDER_COLORS = { upcoming:"#FF9500", due:"#D44800", overdue:"#FF3B30" };
const WA_REMINDER_BG     = { upcoming:"#FFF6ED", due:"#FFF3EE", overdue:"#FFF0F0" };
const WA_REMINDER_LABELS = { upcoming:"1 WEEK BEFORE", due:"DUE TODAY", overdue:"OVERDUE" };
```

### REMINDER_EXPLAINER
```ts
[
  ["1 week before",  "UPCOMING reminder with option to pre-order medicine, book home vet, or reorder meds."],
  ["Due date",       "Due today message sent at 9am with one-tap order or log action."],
  ["No action taken","Overdue follow-up sent every 7 days until the action is logged or completed."],
  ["Action taken",   "Reminder series stops automatically. Next cycle scheduled based on due date."],
  ["Condition meds", "Separate refill reminder series for each chronic medication — never miss a dose."],
]
```

---

## Existing API Types (api.ts — KEEP AS-IS)

### Key Types
- `PetProfile`: name, species, breed, gender, dob, weight, weight_flagged, neutered, photo_url
- `OwnerInfo`: full_name
- `PreventiveRecord`: item_name, category, circle, last_done_date, next_due_date, status, recurrence_days
- `ReminderItem`: item_name, next_due_date, status, sent_at
- `DocumentItem`: id, document_name, document_category, doctor_name, hospital_name, mime_type, extraction_status, uploaded_at
- `DiagnosticResultItem`: test_type, parameter_name, value_numeric, value_text, unit, reference_range, status_flag, observed_at, document_id
- `HealthScore`: score, label, breakdown: HealthScoreBreakdown[], draggers: HealthScoreDragger[]
- `DashboardData`: pet, owner, preventive_records, reminders, documents, diagnostic_results, health_score

### Key Functions (keep)
- `fetchDashboard(token)` → `{data, stale, cachedAt}`
- `updateWeight(token, weight)` → `{status, old_weight, new_weight}`
- `updatePreventiveDate(token, item_name, last_done_date)` → `{status, item_name, new_last_done_date, new_next_due_date, record_status}`
- `retryExtraction(token, documentId)`

### API_BASE
`process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`

---

## Existing Code to Reuse

### DocumentsSection.tsx — `inferCategory` function
Classifies DocumentItem into: "Vaccination" | "Diagnostic" | "Prescription" | "Other"
Uses regex on document_name + hospital_name.

### BloodUrineSection.tsx — parameter grouping logic
Groups DiagnosticResultItem by parameter_name, calculates trends.

### ErrorBoundary.tsx — Class component wrapping children, shows error UI on crash.

### branding.ts constants
- `DASHBOARD_CACHE_PREFIX = "petcircle_dash_"`
- `APP_TAGLINE = "PetCircle — Preventive Pet Health System"`
- `MEDICINES_STORAGE_PREFIX = "petcircle_medicines_"`

---

## Keyword Arrays for Record Classification
```ts
const VACCINE_KW = ["vaccine", "rabies", "dhpp", "core vaccine", "feline core", "bordetella"];
const DEWORMING_KW = ["deworming", "deworm"];
const FLEA_TICK_KW = ["tick", "flea"];
const CHECKUP_KW = ["checkup", "annual", "wellness", "blood test", "preventive blood"];
```

---

## Utility Functions Needed (from prototype)
- `formatDMY(date)` — Date → DD/MM/YYYY
- `parseDMY(str)` — DD/MM/YYYY → Date
- `addMonths(lastDone, freqMonths)` — calc next due from DD/MM/YYYY string
- `addByUnit(last, freq, unit)` — flexible: day/week/month/year
- `diffDaysFromToday(dateStr)` — days until/since DD/MM/YYYY
- `deriveStatus(lastDone, nextDue)` → "overdue" | "upcoming" | "done" | "missing" (60-day threshold)
- `freqLabel(freq, unit)` → "Daily", "Every 3 months", etc.
- `formatApiDate(isoDate)` — YYYY-MM-DD → DD/MM/YYYY
- `ageFromDob(dob)` → "3 yrs", "8 months"
- `isDateInputValid(str)` — validates DD/MM/YYYY format

---

## File Structure (Final)
```
frontend/src/
├── app/
│   ├── globals.css                    [MODIFY]
│   ├── layout.tsx                     [MODIFY]
│   └── dashboard/[token]/page.tsx     [KEEP]
├── components/
│   ├── DashboardClient.tsx            [REPLACE]
│   ├── DashboardHeader.tsx            [NEW]
│   ├── DashboardTabBar.tsx            [NEW]
│   ├── CartView.tsx                   [NEW]
│   ├── ErrorBoundary.tsx              [KEEP]
│   ├── ui/
│   │   ├── BottomSheet.tsx            [NEW]
│   │   ├── StatusBadge.tsx            [NEW]
│   │   ├── Toggle.tsx                 [NEW]
│   │   ├── AddRow.tsx                 [NEW]
│   │   ├── Ring.tsx                   [NEW]
│   │   ├── CollapsibleCard.tsx        [NEW]
│   │   ├── DateEditSheet.tsx          [NEW]
│   │   ├── FreqModal.tsx              [NEW]
│   │   ├── ReminderBar.tsx            [NEW]
│   │   └── CareCard.tsx              [NEW]
│   └── tabs/
│       ├── OverviewTab.tsx            [NEW]
│       ├── HealthTab.tsx              [NEW]
│       ├── HygieneTab.tsx             [NEW]
│       ├── NutritionTab.tsx           [NEW]
│       └── ConditionsTab.tsx          [NEW]
├── lib/
│   ├── api.ts                         [KEEP]
│   ├── branding.ts                    [KEEP]
│   ├── phone.ts                       [KEEP]
│   └── dashboard-utils.ts             [NEW]
└── tailwind.config.js                 [MODIFY]
```

## DashboardClient Orchestrator (new structure)
- Preserve: fetchDashboard, stale recovery, localStorage cache, auto-retry, loading/error states, ErrorBoundary
- Add: `activeTab` state, `showCart` state
- Render: if showCart → CartView, else → Header + TabBar + active tab
- Pass down: data, token, onUpdated (refetch), onCartClick, onTabChange

## State Management
- API-backed: dates, weight → API call → refetch
- Client-persistent: contacts, diet, hygiene settings → localStorage per-token
- Ephemeral: sheet open/closed, input values, expanded items → useState
