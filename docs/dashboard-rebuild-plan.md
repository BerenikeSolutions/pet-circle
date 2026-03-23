# PetCircle Dashboard Rebuild — Implementation Plan

## Context

The existing Next.js dashboard at `/dashboard/[token]` is a functional but basic layout (profile card, activity rings, records table, trends chart). A comprehensive JSX prototype (`petcircle_150326_8.jsx`) defines a much richer mobile-first pet health dashboard with 5 tabbed sections + a cart/payment flow. This plan replaces the existing dashboard with an exact replica of the prototype's design, wired to real API data where available and mocked where not.

**Decisions:**
- Replace existing `/dashboard/[token]` (not a new route)
- Styling: Tailwind CSS + CSS custom properties for brand colors
- Data: Real API where available, mock what's missing
- Scope: Dashboard (5 tabs) + Cart/Payment flow

---

## File Structure (New/Modified)

```
frontend/src/
├── app/
│   ├── globals.css                    [MODIFY] — brand CSS vars, fonts, keyframes
│   ├── layout.tsx                     [MODIFY] — Google Fonts preconnect
│   └── dashboard/[token]/page.tsx     [KEEP]
├── components/
│   ├── DashboardClient.tsx            [REPLACE] — new orchestrator, keep stale-recovery logic
│   ├── DashboardHeader.tsx            [NEW] — gradient header, avatar, actions banner
│   ├── DashboardTabBar.tsx            [NEW] — 5-tab bar
│   ├── CartView.tsx                   [NEW] — cart + payment + success screens
│   ├── ErrorBoundary.tsx              [KEEP]
│   ├── ui/
│   │   ├── BottomSheet.tsx            [NEW] — overlay container
│   │   ├── StatusBadge.tsx            [NEW] — colored status pill
│   │   ├── Toggle.tsx                 [NEW] — on/off switch
│   │   ├── AddRow.tsx                 [NEW] — dashed "+ Add" button
│   │   ├── Ring.tsx                   [NEW] — SVG arc ring
│   │   ├── CollapsibleCard.tsx        [NEW] — expandable card
│   │   ├── DateEditSheet.tsx          [NEW] — date edit bottom sheet
│   │   ├── FreqModal.tsx              [NEW] — frequency selector bottom sheet
│   │   ├── ReminderBar.tsx            [NEW] — reminder toggle row
│   │   └── CareCard.tsx              [NEW] — deworming/flea-tick style card
│   └── tabs/
│       ├── OverviewTab.tsx            [NEW] — care tiles, condition summary, nutrition note, WA reminders, docs, contacts
│       ├── HealthTab.tsx              [NEW] — vaccines, deworming, flea/tick, checkups, weight log
│       ├── HygieneTab.tsx             [NEW] — daily activities, periodic grooming
│       ├── NutritionTab.tsx           [NEW] — diet, supplements, calorie/macro/vitamin analysis
│       └── ConditionsTab.tsx          [NEW] — conditions, medications, chronology, PDF card
├── lib/
│   ├── api.ts                         [KEEP] — all types & fetchers already correct
│   ├── branding.ts                    [KEEP]
│   ├── phone.ts                       [KEEP]
│   └── dashboard-utils.ts             [NEW] — date helpers, status config, mock data factories
└── tailwind.config.js                 [MODIFY] — brand colors, fonts, max-w-mobile
```

**Retired components** (no longer rendered but kept in codebase):
- `ActivityRings.tsx`, `PetProfileCard.tsx`, `PreventiveRecordsTable.tsx`, `HealthTrendsSection.tsx`, `RemindersSection.tsx`, `MedicinesSection.tsx`, `HealthScoreRing.tsx`

**Adapted** (logic reused inside new tabs):
- `DocumentsSection.tsx` — `inferCategory`, `RetryButton`, viewer modal logic reused in OverviewTab
- `BloodUrineSection.tsx` — parameter grouping logic reused in HealthTab/ConditionsTab

---

## Design System

### Brand Colors (CSS Custom Properties)
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
- **Body**: DM Sans (400/500/600/700)
- **Headings**: Fraunces (700/900)
- Loaded via Google Fonts `<link>` in `layout.tsx`

### Component Patterns
- **Cards**: `bg-white rounded-2xl border border-[statusColor]/20 shadow-sm`
- **Status badges**: `rounded-full px-2.5 py-0.5 text-[10px] font-bold` with dynamic color/bg
- **Bottom sheets**: fixed overlay + panel with `rounded-t-[20px]`
- **Mobile-first**: max-width 430px centered

### Tailwind Config Extensions
```js
theme: {
  extend: {
    colors: { brand: '#D44800', 'brand-light': '#FF9A6C' },
    fontFamily: { sans: ['DM Sans', 'sans-serif'], display: ['Fraunces', 'serif'] },
    maxWidth: { mobile: '430px' },
  }
}
```

---

## Data Mapping: API → UI

### Real API Data (from `GET /dashboard/{token}`)
| UI Section | API Field |
|---|---|
| Header: pet info | `pet.name`, `pet.breed`, `pet.dob`, `pet.photo_url`, `pet.weight` |
| Header: parent | `owner.full_name` |
| Header: overdue count | `preventive_records` count where `status === "overdue"` |
| Overview care tiles | `preventive_records` grouped by `circle` (health/nutrition/hygiene) |
| Health tab vaccines | `preventive_records` where `item_name` contains vaccine keywords |
| Health tab deworming | `preventive_records` where `item_name` ~ "deworming" |
| Health tab flea/tick | `preventive_records` where `item_name` ~ "tick" or "flea" |
| Health tab checkups | `preventive_records` where `item_name` ~ checkup keywords |
| Hygiene tab items | `preventive_records` where `circle === "hygiene"` |
| Nutrition tab items | `preventive_records` where `circle === "nutrition"` |
| Documents collapsible | `documents[]` |
| WA Reminders | `reminders[]` |
| Blood/urine data | `diagnostic_results[]` |
| Health score | `health_score.score`, `health_score.label`, `health_score.breakdown` (6 categories), `health_score.draggers` |

### Mocked Data (no backend API)
| UI Section | Mock Strategy |
|---|---|
| Weight history | Generate plausible entries from `pet.weight` + `pet.dob` |
| Nutrition analysis (calories, macros, vitamins, minerals) | Static mock keyed by species |
| Condition details (medications, monitoring) | Empty state by default; mock if diagnostic data present |
| Cart items + pricing | Static catalog; overdue records map to pre-selected urgent items |
| Care contacts | Empty, localStorage-persisted (`petcircle_contacts_${token}`) |
| Hygiene reminder settings | localStorage-persisted (`petcircle_hygiene_${token}`) |
| Diet rows | localStorage-persisted (`petcircle_diet_${token}`) |
| WA reminder body text | Template-generated from `reminders[]` data |

---

## Implementation Steps

### Step 1: Design System Foundation
**Files:** `globals.css`, `layout.tsx`, `tailwind.config.js`

- Add CSS custom properties for brand colors, status colors, app background
- Add Google Fonts import (DM Sans + Fraunces) via `<link rel="preconnect">` in layout
- Add keyframe animations: `fadeIn`, `slideUp`
- Extend Tailwind theme with brand colors, font families, max-width token

### Step 2: Utility Module
**File:** `lib/dashboard-utils.ts`

**Date helpers:**
- `formatDMY(date)` — Date → DD/MM/YYYY
- `parseDMY(str)` — DD/MM/YYYY → Date
- `addMonths(lastDone, freqMonths)` — calculate next due
- `addByUnit(last, freq, unit)` — flexible frequency math
- `diffDaysFromToday(dateStr)` — days until/since
- `deriveStatus(lastDone, nextDue)` — "overdue" | "upcoming" | "done" | "missing"
- `freqLabel(freq, unit)` — "Daily", "Every 3 months", etc.
- `formatApiDate(isoDate)` — YYYY-MM-DD → DD/MM/YYYY
- `ageFromDob(dob)` — "3 yrs", "8 months"

**Status config:**
```ts
export const STATUS_CONFIG = {
  overdue:  { color: '#FF3B30', bg: '#FFF0F0', label: 'Overdue' },
  upcoming: { color: '#FF9500', bg: '#FFF6ED', label: 'Due Soon' },
  done:     { color: '#34C759', bg: '#F0FFF4', label: 'Up to Date' },
  missing:  { color: '#8E8E93', bg: '#F2F2F7', label: 'No Record' },
  managed:  { color: '#007AFF', bg: '#F0F6FF', label: 'Managed' },
};
```

**Record helpers:**
- `filterByCircle(records, circle)` — filter preventive_records by circle field
- `filterByKeywords(records, keywords)` — filter by item_name keyword matching
- `countOverdue(records)` — count records with status "overdue"

**Mock data factories:**
- `buildMockWeightHistory(currentWeight, dob)` — plausible weight entries
- `buildMockNutritionData(species)` — calories, macros, vitamins, minerals
- `buildMockCartItems(records)` — cart items derived from overdue records
- `buildWaReminderPreviews(reminders)` — body text from reminder data

**Item name keyword arrays:**
```ts
const VACCINE_KW = ["vaccine", "rabies", "dhpp", "core vaccine", "feline core", "bordetella"];
const DEWORMING_KW = ["deworming", "deworm"];
const FLEA_TICK_KW = ["tick", "flea"];
const CHECKUP_KW = ["checkup", "annual", "wellness", "blood test", "preventive blood"];
```

### Step 3: Shared UI Primitives (10 components)
**Files:** `components/ui/*.tsx`

Build in dependency order:

1. **`StatusBadge`** — takes `status` key, renders colored pill from `STATUS_CONFIG`
2. **`Toggle`** — on/off slide toggle with optional label
3. **`AddRow`** — dashed border "+ Add" button with brand color
4. **`Ring`** — SVG circle with progress arc (percentage, size, stroke width, color)
5. **`BottomSheet`** — fixed overlay + sliding panel container, click-outside-to-close
6. **`CollapsibleCard`** — card with header (icon, title, subtitle, badge), chevron toggle, animated expand/collapse
7. **`DateEditSheet`** — bottom sheet: title, subtitle, DD/MM/YYYY text input, auto-calculated "Next Due" preview, Save/Cancel. Calls `updatePreventiveDate` from `api.ts` on save.
8. **`FreqModal`** — bottom sheet: frequency number pills + unit pills (day/week/month/year), preview label, Save
9. **`ReminderBar`** — row: "Reminder" label, frequency pill (clickable → opens FreqModal), Toggle
10. **`CareCard`** — full card for deworming/flea-tick style items: icon, title, product text, lastDone/nextDue, status badge, edit button, ReminderBar, Order Now CTA

### Step 4: Dashboard Shell
**Files:** `DashboardHeader.tsx`, `DashboardTabBar.tsx`

**DashboardHeader:**
- Gradient background (`var(--brand-gradient)`)
- Pet avatar: photo from `pet.photo_url` (prefixed with API URL) or initials in gradient circle. Photo upload via `<input type="file">` (client-side preview only, no upload endpoint).
- Pet name in Fraunces font, breed/age/species line, parent name
- Clickable "X Actions Due" banner with overdue count badge and "Order →" CTA

**DashboardTabBar:**
- 5 tabs: Overview, Health, Hygiene, Nutrition, Conditions
- Horizontal scroll, hidden scrollbar
- Active tab: brand color text + 2px bottom border

### Step 5: Tab Components

#### OverviewTab
**Sections (in order):**
1. **Care-at-a-glance grid** — 3-column, 6 tiles (Vaccines, Deworming, Flea & tick, Daily care, Grooming, Ann. Checkup). Data from `preventive_records` grouped by keywords. Each tile: icon, label, status badge, due text. Clickable → switches tab.
2. **Condition summary card** — shown only if `diagnostic_results.length > 0`. Shows medications with refill status, next follow-up. Otherwise hidden.
3. **Order Now CTA** — full-width brand button → cart
4. **Nutrition note card** — three sub-blocks: Overall diet (amber), What to improve (blue, bullet list), Recommendation (green). Mock data from `buildMockNutritionData`.
5. **WhatsApp Reminders collapsible** — green WA header (#075E54), list of reminders from API, expandable with mock body text and action buttons
6. **Uploaded Documents collapsible** — reuses `inferCategory` logic from existing `DocumentsSection.tsx`, grouped by category, file rows with parsed status, upload button
7. **Care Contacts collapsible** — localStorage-backed, editable contact list with BottomSheet form (type/name/clinic/phone/note), add/edit/delete

#### HealthTab
**Sections:**
1. **Vaccinations card** — mandatory vs optional groups, each row: dot indicator, name, given/next dates, status badge, edit button (→ DateEditSheet). Optional rows include ReminderBar. "Book Now" CTA if overdue.
2. **Deworming CareCard** — from `preventive_records` matching deworming keywords
3. **Flea & Tick CareCard** — from `preventive_records` matching flea/tick keywords
4. **Annual Health Checkups** — progress bar (completed/total required), checklist rows (vet visit, blood, x-ray, urinalysis, fecal) with edit buttons and ReminderBars. "Book Now" CTA.
5. **Weight Log** — current weight from API, history from mock factory. SVG sparkline bar chart, ideal range indicator, log table (newest first), "+ Log weight" → calls `updateWeight` from `api.ts`.

#### HygieneTab
**Sections:**
1. **Breed note banner** — "Frequencies are breed-adjusted for [breed]"
2. **Frequent activities** — from hygiene circle records matching daily keywords. Each row: icon, name, last done, status badge, reminder Toggle, frequency FreqPill. Settings in localStorage.
3. **Periodic grooming** — from hygiene circle records matching grooming keywords. Same row pattern + date edit button (→ DateEditSheet using `updatePreventiveDate`). "Book Now" CTA.

#### NutritionTab
**Sections:**
1. **Current diet** — editable food items (localStorage), supplements list, add/edit/delete via BottomSheets
2. **Order reminders** — food/supplement reorder rows with frequency/reminder settings
3. **Nutrition note** — same card as OverviewTab (reuse component)
4. **Nutrition breakdown** — calories progress bar, macronutrients bar charts, vitamins gap analysis, minerals table, other nutrients. All mock data.

#### ConditionsTab
**Sections:**
1. **Per-condition card** — if `diagnostic_results` exist: diagnosis info, medications with refill status + ReminderBars, monitoring checkups + ReminderBars, PetCircle recommendations. Otherwise: informational empty state.
2. **"+ Add Condition" button** — opens BottomSheet (state-only)
3. **Last Vet Visit card** — derived from most recent document or diagnostic date
4. **Management Chronology** — collapsible timeline (mocked events if no real data)
5. **Complete Health PDF card** — simulated PDF generation with loading state and download confirmation

### Step 6: Cart/Payment Flow
**File:** `CartView.tsx`

Three screens managed by `screen` state:

**Cart screen:**
- Items from `buildMockCartItems(preventive_records)`: overdue records → pre-selected urgent items
- `CartItem` sub-component: icon, name, tag badge, price, add/remove toggle, quantity controls
- Urgent section (pre-selected) + Recommended section
- Coupon input (PETCARE10 → 10% off)
- Sticky footer: item count, delivery info (free >999), total, "Proceed to Payment"

**Payment screen:**
- Order summary pill
- Delivery address (seeded from `owner.full_name`, edit/add via BottomSheet)
- Payment methods: UPI (with ID input), Card (number/name/exp/CVV), Net Banking (bank selector), COD
- Bill summary: subtotal, discount, delivery, total
- Sticky "Pay ₹X" button

**Success screen:**
- Celebration emoji + Fraunces heading
- Random order ID
- Order summary card
- Delivery note
- "Back to Dashboard" button

### Step 7: Orchestrator Rewrite
**File:** `DashboardClient.tsx`

**Preserved from existing:**
- `fetchDashboard(token)` call on mount
- Stale data recovery: localStorage cache with key `petcircle_dash_${token}`
- Auto-retry: 30s interval, up to 20 retries when stale
- Loading spinner, error state, stale data amber banner
- `ErrorBoundary` wrapping

**New additions:**
- `activeTab` state (overview/health/hygiene/nutrition/conditions)
- `showCart` state (boolean)
- Routing: if `showCart` → `<CartView>`, else → Header + TabBar + active Tab
- Props passed down: `data`, `token`, `onUpdated` (refetch), `onCartClick`, `onTabChange`

```tsx
// Simplified render structure
if (showCart) return <CartView data={data} onBack={() => setShowCart(false)} />;
return (
  <div className="min-h-screen" style={{ background: 'var(--bg-app)' }}>
    {staleData && <StaleBanner />}
    <DashboardHeader pet={data.pet} owner={data.owner} overdueCount={...} onCartClick={...} />
    <DashboardTabBar activeTab={activeTab} onTabChange={setActiveTab} />
    <div className="max-w-[430px] mx-auto p-4 pb-24">
      {activeTab === 'overview' && <OverviewTab ... />}
      {activeTab === 'health' && <HealthTab ... />}
      {activeTab === 'hygiene' && <HygieneTab ... />}
      {activeTab === 'nutrition' && <NutritionTab ... />}
      {activeTab === 'conditions' && <ConditionsTab ... />}
    </div>
  </div>
);
```

---

## State Management Strategy

| State Type | Storage | Example |
|---|---|---|
| API-backed (dates, weight) | API call → refetch | Vaccine date edit → `updatePreventiveDate` → `onUpdated()` |
| Client-persistent | localStorage per-token | Contacts, diet rows, hygiene settings, reminder frequencies |
| Ephemeral UI | Component useState | Sheet open/closed, date input value, expanded items |

---

## Key Design Decisions

### Item Name Matching
API returns free-form `item_name` strings like "Rabies Vaccine", "Deworming", "Tick/Flea". We use case-insensitive substring matching with keyword arrays to classify records into UI categories. This is fragile but necessary without a dedicated category field beyond `circle`.

### Styling Mix
- Tailwind for layout, spacing, typography, responsive
- CSS custom properties for brand theming (easy to adjust)
- Inline styles for dynamic status colors (computed per-record)
- Bottom sheets use inline styles (fixed positioning is simpler than Tailwind for overlays)

### Mobile-First
The entire dashboard is designed for 430px max-width (phone screen). Content is centered on desktop. No desktop-specific layouts needed.

---

## Verification Plan

1. **Dev server**: `cd frontend && npm run dev` — no TypeScript errors
2. **Visual comparison**: Open `/dashboard/{token}` at 430px viewport — compare each tab against JSX prototype
3. **API integration**: Verify real data renders in Overview tiles, Health records, Documents, Reminders
4. **Interactions**: Date editing (→ API call), weight update (→ API call), tab switching, collapsible cards, bottom sheets
5. **Cart flow**: Cart → Payment → Success screens all work
6. **localStorage persistence**: Contacts, diet, hygiene settings survive page reload
7. **Stale recovery**: Kill backend → cached data shows with amber banner
8. **Error boundary**: Break a component → error UI shows (not blank page)
