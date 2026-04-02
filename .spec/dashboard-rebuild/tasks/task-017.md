---
task: 017
feature: dashboard-rebuild
status: pending
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
- [ ] All 7 view transitions work correctly
- [ ] Bell → reminders, CTA → trends, nav → records, floater → cart
- [ ] Back buttons return to dashboard
- [ ] Cart → checkout → confirm flow works
- [ ] Offline/stale handling preserved (banners, auto-retry)
- [ ] Error boundaries wrap all views
- [ ] Cart state persists across view transitions
- [ ] No references to removed imports (tabs, nudges, etc.)
- [ ] `npm run build` passes
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
