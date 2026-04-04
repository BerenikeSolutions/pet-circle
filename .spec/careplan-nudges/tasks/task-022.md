---
task: 022
feature: careplan-nudges
status: complete
depends_on: []
---

# Task 022: Frontend — NudgesView Component

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Build the NudgesView and NudgeCard components that display prioritized health action nudges grouped by category. Wire into DashboardClient's ViewState system. Support dismiss flow, orderable "Add to Cart" CTAs, and loading/empty states.

---

## Codebase Context

### Key Code Snippets

```typescript
// [ViewState type — from frontend/src/components/DashboardClient.tsx:15]
type ViewState = "dashboard" | "trends" | "reminders" | "cart" | "checkout" | "confirm" | "records";
// Needs: "nudges" added to this union
```

```typescript
// [State management — from DashboardClient.tsx:33-46]
const [view, setView] = useState<ViewState>("dashboard");
const [data, setData] = useState<DashboardData | null>(null);
const [cart, setCart] = useState<CartItem[]>([]);
```

```typescript
// [NudgeItem interface — from frontend/src/lib/api.ts:609-626]
export interface NudgeItem {
  id: string;
  category: string;
  priority: string;
  icon: string | null;
  title: string;
  message: string;
  mandatory: boolean;
  orderable: boolean;
  price: string | null;
  order_type: string | null;
  cart_item_id: string | null;
  dismissed: boolean;
  acted_on: boolean;
  source: string;
  trigger_type: string;
  created_at: string | null;
}
```

```typescript
// [API functions — from frontend/src/lib/api.ts]
// getNudges(token) — already exists at line ~1183
// dismissNudge(token, nudgeId) — already exists at line ~1194
```

```typescript
// [CarePlanItem interface — from frontend/src/lib/api.ts:263-275]
export interface CarePlanItem {
  name: string;
  test_type: string;
  product_id?: string | null;
  icon?: string | null;
  price?: number;
  freq: string;
  next_due: string | null;
  status_tag: string;
  classification: string;
  reason: string | null;
  orderable: boolean;
}
// Needs: cta_label?: string added
```

### Key Patterns in Use
- **View switching:** `setView("nudges")` / `setView("dashboard")` in DashboardClient.
- **Cart flow:** `onAddToCart(item, sectionTitle)` callback with 1.8s green "Added" animation.
- **ViewHeader:** Used by RemindersView, RecordsView — back button + title pattern.
- **Dismiss pattern:** RemindersView has a dismiss confirmation flow that can be reused.
- **Category icons:** NudgeItem has `icon` field from backend, or map category to default icon.
- **Priority badges:** `priority` field is "urgent" | "high" | "medium" — map to red/amber/neutral.

### Architecture Decisions Affecting This Task
- Nudges are lazy-loaded: only fetched when user navigates to NudgesView.
- Category grouping order: vaccine, deworming, flea, condition, nutrition, grooming, checkup.

---

## Handoff from Previous Task
> This is an independent task with no prior dependencies.

**Files changed by previous task:** _(none)_
**Decisions made:** _(none)_
**Context for this task:** _(none)_
**Open questions left:** _(none)_

---

## Implementation Steps

1. **Add `cta_label?: string` to `CarePlanItem` in `frontend/src/lib/api.ts`:**
   - This is a minor addition used by task-025 but added here since we're touching the file.

2. **Create `frontend/src/components/nudges/NudgeCard.tsx`:**
   - Props: `nudge: NudgeItem`, `onDismiss`, `onAddToCart`, `isAdded: boolean`.
   - Render: icon + title + priority badge (urgent=`s-tag-r`, high=`s-tag-y`, medium=`s-tag`).
   - Message body: expandable if long (>100 chars, show "Show more").
   - Dismiss button: only if `!nudge.mandatory`. Confirmation step ("Dismiss this?").
   - "Order Now" CTA: only if `nudge.orderable`. On click → `onAddToCart`. 1.8s green "Added" feedback.

3. **Create `frontend/src/components/nudges/NudgesView.tsx`:**
   - Props: `token: string`, `onBack: () => void`, `onAddToCart`, `cart`.
   - On mount: fetch nudges via `getNudges(token)`.
   - Group nudges by category in order: vaccine, deworming, flea, condition, nutrition, grooming, checkup.
   - Render ViewHeader with "Health Actions" title and back button.
   - Render category groups with headers (icon + category name).
   - Dismiss flow: call `dismissNudge(token, id)`, optimistically remove from list.
   - Empty state: "All caught up! No actions needed right now."
   - Loading state: spinner.
   - Home floater button at bottom.

4. **Add `"nudges"` to ViewState in `DashboardClient.tsx`:**
   - Update type: `type ViewState = "dashboard" | "trends" | "reminders" | "cart" | "checkout" | "confirm" | "records" | "nudges";`
   - Add NudgesView import.
   - Add NudgesView case in the view-rendering switch/conditional.
   - Pass: `token`, `onBack: () => setView("dashboard")`, `onAddToCart`, `cart`.

5. **Verify build:**
   - `cd frontend && npm run build` — zero errors.

---

## Acceptance Criteria
- [x] NudgesView renders all undismissed nudges grouped by category in correct order
- [x] Priority badges render with correct colors (urgent=red, high=amber, medium=neutral)
- [x] Dismiss flow calls API and removes card optimistically
- [x] Mandatory nudges have no dismiss button
- [x] Orderable nudges show "Order Now" CTA, add to cart with 1.8s feedback
- [x] Empty state shows "All caught up!" message
- [x] Loading state shows spinner
- [x] Navigation to/from nudges works via DashboardClient
- [x] `npm run build` passes

---

## Handoff — What Was Done
- Implemented new nudges UI components with grouped category rendering, priority badges, long-message expand/collapse, dismiss confirmation, and order CTA feedback flow.
- Wired NudgesView into DashboardClient ViewState by adding `"nudges"` union support and a render switch case with back/cart callbacks.
- Completed verify flow for build/types/lint, and documented E2E blocker (backend not running locally for Playwright global setup).

## Handoff — Patterns Learned
- This frontend is style-driven by shared utility classes (`card`, `vh`, `floater`, `s-tag*`) plus inline style overrides; new views should reuse this pattern for consistency.
- For this project, `npm run build` also runs lint+type checks in Next.js; explicit `tsc --noEmit` remains useful for fast iteration.
- Playwright E2E in this repo requires backend health at `http://localhost:8000` with valid dashboard tokens before tests can proceed.

## Handoff — Files Changed
- frontend/src/components/nudges/NudgeCard.tsx
- frontend/src/components/nudges/NudgesView.tsx
- frontend/src/components/DashboardClient.tsx

## Status
COMPLETE
