---
task: 009
feature: cart-rules-engine
status: pending
depends_on: [007, 008]
---

# Task 009: Frontend — Wire ProductSelectorCard into care plan + cart search

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective
Connect `ProductSelectorCard` to the care plan's "Order Now" button and add product search to `CartView`. When user taps "Order Now", fetch resolved products via API and open the selector. L1 items show info text instead of CTA. Cart page gets a search bar.

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```tsx
// [CarePlanCard onAddToCart callback — from frontend/src/components/dashboard/CarePlanCard.tsx:6-14]
interface CarePlanCardProps {
  petName: string;
  buckets: Record<"continue" | "attend" | "add", CarePlanSection[]>;
  cartQtyByItem: Record<string, number>;
  addedIds: Record<string, boolean>;
  onAddToCart: (item: CarePlanItem, sectionTitle: string) => void;
  // ...
}
// Currently onAddToCart directly adds to cart. Must change to: resolve products → open selector
```

```tsx
// [DashboardClient or DashboardView — where state is managed]
// The parent component manages cart state and passes onAddToCart down to CarePlanCard
// Look for where onAddToCart is defined to intercept it
```

```tsx
// [CartView — from frontend/src/components/CartView.tsx:50-80]
// Currently has: header "Your Cart", item list, qty controls, pricing
// Need to add: search bar at top, search results as addable items
```

```tsx
// [API base pattern — check frontend/src/lib/api.ts for fetch helpers]
// Dashboard API calls typically: fetch(`/api/dashboard/${token}/...`)
```

```tsx
// [CartFloater — from frontend/src/components/dashboard/CartFloater.tsx]
// Shows floating cart button with count + total
// Count must update after add-from-selector
```

### Key Patterns in Use
- **API calls:** `fetch()` with token in URL path
- **State management:** React `useState`/`useEffect` in parent component, props drilled down
- **Cart count sync:** Parent tracks cart items, passes count to CartFloater

---

## Handoff from Previous Task
> Populated by /task-handoff after prior task completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps
1. Modify the parent component that renders `CarePlanCard` (likely `DashboardView` or `ReturningDashboardView`):
   - Change `onAddToCart` handler: instead of directly adding to cart, call `GET /products/resolve?diet_item_id=...`
   - Store resolved products in state
   - Open `ProductSelectorCard` with the resolved products
   - On `ProductSelectorCard.onAddToCart`: call `POST /cart/add`, update cart state, close selector
2. Handle L1 items in `CarePlanCard`:
   - Read `signal_level` from care plan item data (added in task-007)
   - If L1: hide "Order Now" button, show info text prompt (e.g., "Share your pet's food brand on WhatsApp to enable ordering")
3. Add search bar to `CartView.tsx`:
   - Text input at top of cart view
   - On input (debounced 300ms): call `GET /products/search?q=...`
   - Render search results below input as product cards with "Add" button
   - On add: call `POST /cart/add`, refresh cart items
4. Update `CartView.tsx` pricing display:
   - Show MRP (strikethrough) and discounted price when different (C3)
   - Show unit price label
5. Wire cart count update:
   - After add-from-selector or add-from-search, refresh cart data
   - CartFloater count updates automatically from cart state

_Requirements: 6.1, 6.7, 6.9, 7.1, 7.2, 7.3_
_Skills: /code-writing-software-development_

---

## Acceptance Criteria
- [ ] Tapping "Order Now" on a care plan item calls resolve API and opens ProductSelectorCard
- [ ] ProductSelectorCard shows resolved products at correct signal level
- [ ] Adding from selector calls POST /cart/add and closes card
- [ ] L1 items show info text instead of "Order Now" CTA
- [ ] Cart page has search bar that queries /products/search
- [ ] Search results can be added to cart
- [ ] CartView shows MRP vs discounted price per C3
- [ ] Cart floater count updates after add
- [ ] Build succeeds (`npm run build`)
- [ ] `/verify` passes

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
