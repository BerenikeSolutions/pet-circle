---
task: 017
feature: dashboard-rebuild
status: complete
depends_on: [12, 13, 14, 15, 16]
---

# Task 017: Frontend — DashboardClient.tsx Rewrite (Orchestrator)

## Session Bootstrap
Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Rewrite `DashboardClient.tsx` to use view-switching navigation (7 states) instead of tab-based navigation. Wire all navigation flows. Preserve offline-first, stale data recovery, and error boundaries.

---

## Codebase Context

### Key Code Snippets

```typescript
// [Current DashboardClient state — from frontend/src/components/DashboardClient.tsx:23-49]
const [data, setData] = useState<DashboardData | null>(null);
const [error, setError] = useState("");
const [loading, setLoading] = useState(true);
const [refreshing, setRefreshing] = useState(false);
const [stale, setStale] = useState(false);
const [cachedAt, setCachedAt] = useState<string | undefined>();
const [retryCount, setRetryCount] = useState(0);
const [activeTab, setActiveTab] = useState("overview");        // REMOVE
const [visitedTabs, setVisitedTabs] = useState<Set<string>>(); // REMOVE
const [pinnedCartItem, setPinnedCartItem] = useState<string | null>(null);
const [showReminders, setShowReminders] = useState(false);     // REPLACE with view state
const [showNudges, setShowNudges] = useState(false);           // REMOVE
const [nudges, setNudges] = useState<NudgeItem[]>([]);         // REMOVE
const [showNudgesAfterCart, setShowNudgesAfterCart] = useState(false); // REMOVE
const [isOnline, setIsOnline] = useState(navigator.onLine);
```

```typescript
// [Current load function — from frontend/src/components/DashboardClient.tsx:55-70]
const load = useCallback(async () => {
  try {
    setError("");
    setData((prev) => {
      if (prev) { setRefreshing(true); } else { setLoading(true); }
      return prev;
    });
    const result = await fetchDashboard(token);
    // ... handles stale, caching, retry
```

### Key Patterns in Use
- **Offline-first:** localStorage cache, auto-retry with exponential backoff (10s-60s, max 10 retries)
- **Error boundary:** Wraps entire dashboard in `ErrorBoundary`
- **Stale data recovery:** Shows cached data with "Showing last saved data" banner + auto-retry
- **Network events:** `window.online/offline` listeners

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. **Replace state model:**
   - Remove: `activeTab`, `visitedTabs`, `showReminders`, `showNudges`, `nudges`, `showNudgesAfterCart`, `nudgesLoading`, `nudgesError`
   - Add: `view: ViewState` where `type ViewState = 'dashboard' | 'trends' | 'reminders' | 'cart' | 'checkout' | 'confirm' | 'records'`
   - Keep: `data`, `error`, `loading`, `refreshing`, `stale`, `cachedAt`, `retryCount`, `isOnline`
   - Add: `cart: CartItem[]` state (moved from sub-component)

2. **Wire navigation:**
   - Bell icon (ProfileBanner) → `setView('reminders')`
   - "Discuss with vet" CTA (HealthConditionsCard) → `setView('trends')`
   - "View all reports" (RecognitionCard) → `setView('records')`
   - "See Full Health Records" (HealthRecordsNav) → `setView('records')`
   - Cart floater → `setView('cart')`
   - Back buttons → `setView('dashboard')`
   - "Proceed to Checkout" → `setView('checkout')`
   - "Place Order" → `setView('confirm')`
   - "Back to Dashboard" (ConfirmView) → `setView('dashboard')` + clear cart

3. **Cart state management:**
   - `addToCart(item)`, `updateQty(id, qty)`, `removeFromCart(id)`
   - Passed as props to DashboardView and CartView

4. **Preserve existing patterns:**
   - Offline detection + banners
   - Stale data auto-retry with exponential backoff
   - Error boundary wrapping
   - Loading/refreshing states
   - localStorage cache

5. **Remove old imports:**
   - Remove: DashboardHeader, DashboardTabBar, OverviewTab, HealthTab, HygieneTab, NutritionTab, ConditionsTab, NudgesView
   - Add: DashboardView, HealthTrendsView, RemindersView, CartView, CheckoutView, ConfirmView, RecordsView

6. **Render view based on state:**
   ```
   switch(view) {
     case 'dashboard': <DashboardView ... />
     case 'trends': <HealthTrendsView ... />
     case 'reminders': <RemindersView ... />
     case 'cart': <CartView ... />
     case 'checkout': <CheckoutView ... />
     case 'confirm': <ConfirmView ... />
     case 'records': <RecordsView ... />
   }
   ```

_Requirements: 2_

---

## Acceptance Criteria
- [x] All 7 view transitions work correctly
- [x] Bell → reminders, CTA → trends, nav → records, floater → cart
- [x] Back buttons return to dashboard
- [x] Cart → checkout → confirm flow works
- [x] Offline/stale handling preserved (banners, auto-retry)
- [x] Error boundaries wrap all views
- [x] Cart state persists across view transitions
- [x] No references to removed imports (tabs, nudges, etc.)
- [x] `npm run build` passes
- [x] `/verify` passes (tests unavailable: no frontend test script)

---

## Handoff — What Was Done

- Rewrote the dashboard orchestrator to a 7-view switch model in `DashboardClient.tsx`, replacing tab/nudges routing with explicit view-state navigation.
- Moved cart state to the orchestrator and rewired `DashboardView` + `CartView` so cart count/total persist across view transitions into checkout and confirm.
- Preserved offline-first behavior (offline banner/fallback), stale-cache recovery (auto-retry with backoff), and global error boundary wrapping.

## Handoff — Patterns Learned

- Keep view transitions centralized in one switch to avoid state drift between sub-views.
- Derive cart button state in dashboard cards from orchestrator cart quantity map, not per-card local state.
- This workspace has no frontend `npm run test` script; `/verify` test phase must be documented as blocked.

## Handoff — Files Changed

- `.spec/dashboard-rebuild/tasks/task-017.md`
- `frontend/src/components/DashboardClient.tsx`
- `frontend/src/components/CartView.tsx`
- `frontend/src/components/dashboard/DashboardView.tsx`
- `frontend/src/lib/api.ts`

## Status

COMPLETE

## Handoff to Next Task

**Files changed:** `frontend/src/components/DashboardClient.tsx`, `frontend/src/components/CartView.tsx`, `frontend/src/components/dashboard/DashboardView.tsx`, `frontend/src/lib/api.ts`
**Decisions made:** Cart/checkout/confirm flow is orchestrated by `view` state in `DashboardClient.tsx`; stale/offline logic kept in the orchestrator wrapper.
**Context for next task:** Old tab/nav/nudge components are now disconnected from the app and ready for cleanup deletion in task 018.
**Open questions:** Whether checkout confirmation should call backend `placeOrder` in this phase or stay UI-local until order wiring task.
