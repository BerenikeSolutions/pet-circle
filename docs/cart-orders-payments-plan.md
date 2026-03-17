# Plan: Build Orders, Cart & Payments Logic (per petcircle.jsx reference)

## Context
The current `CartView.tsx` has a basic 3-screen flow (cart → payment → success) but is missing many features from the reference design in `petcircle_150326_8.jsx`. The `onCartClick` across all tabs is a plain `() => void` with no deep-linking support. This plan upgrades the frontend cart/payment flow to match the reference exactly, and adds a workflow SOP document.

---

## Step 1 — Add constants to `dashboard-utils.ts`
**File:** `frontend/src/lib/dashboard-utils.ts`

Add two new exports:
- `NUDGE_CART_MAP: Record<number, string>` — maps nudge IDs to cart item IDs (e.g., `1 → 'c2'`, `2 → 'c1'`, etc.)
- `NET_BANKS: string[]` — `['HDFC Bank', 'ICICI Bank', 'SBI', 'Axis Bank', 'Kotak Bank', 'Yes Bank']`

---

## Step 2 — Update `DashboardClient.tsx` state model
**File:** `frontend/src/components/DashboardClient.tsx`

- Replace `const [showCart, setShowCart] = useState(false)` with `const [pinnedCartItem, setPinnedCartItem] = useState<string | null>(null)`
- Guard: `if (pinnedCartItem !== null)` → render `<CartView data={data} pinnedItemId={pinnedCartItem || undefined} onBack={() => setPinnedCartItem(null)} />`
- Update all `onCartClick` props to `(itemId?: string) => setPinnedCartItem(itemId ?? '')`
- Add `onCartClick` prop to `ConditionsTab` (currently missing)

---

## Step 3 — Update prop interfaces (all tabs + header)
**Files:** `DashboardHeader.tsx`, `OverviewTab.tsx`, `HealthTab.tsx`, `HygieneTab.tsx`, `NutritionTab.tsx`, `ConditionsTab.tsx`

Change `onCartClick: () => void` → `onCartClick: (itemId?: string) => void` in each interface. No call-site changes yet.

---

## Step 4 — Rewrite `CartView.tsx`
**File:** `frontend/src/components/CartView.tsx`

Major changes to match reference `CartStep`:

### Props
- Add `pinnedItemId?: string` prop

### State changes
- Replace flat `items[]` array with two dictionaries: `cart: Record<string, boolean>` + `qtys: Record<string, number>`
- Multi-address model: `addresses[]` array with `{id, name, line, tag, selected}`, `addressSheet: {mode, id?} | null`, `addrForm: {name, line, tag}`
- Card fields: `cardNum`, `cardName`, `cardExp`, `cardCvv` (with auto-formatting)
- `netBank` state for chip selection

### New features
- `useEffect` to auto-add `pinnedItemId` to cart on mount
- `sortWithPin` callback to sort pinned item first
- `useMemo` for derived cart values (inCart, subtotal, discount, delivery, total)
- Urgent/recommended split based on base `inCart` OR `pinnedItemId`

### Cart screen UI
- Header: `"{petName}'s Care Orders"` + red item count badge
- Pinned item banner (orange `#FFF6ED` with item name)
- Updated `CartItem` component: colored icon box, circular toggle button (orange ✓ / gray ＋), opacity 0.6 when not in cart, per-row total
- Coupon moved into sticky footer (above totals line)
- Section labels: "Urgent for {petName}" / "Recommended for {petName}"

### Payment screen UI
- Multi-address radio list with Edit/Add buttons
- Card number auto-formatting (spaces every 4 digits)
- Expiry auto-formatting (auto `/` after MM)
- CVV as `type="password"`, max 4 chars
- Net banking: chip buttons instead of `<select>` dropdown
- Inline address bottom sheet with tag chips (Home/Work/Other), replaces BottomSheet import

### Success screen
- Itemized receipt (icon + name + per-item total for each cart item)
- "Total paid" row
- Green delivery note box
- Order ID format: `PC-{random 5 digits}`

---

## Step 5 — Wire deep-link cart item IDs in tab CTAs
**Files:** All tab components

| Tab | CTA | Cart Item ID |
|-----|-----|-------------|
| OverviewTab | "Order Now — Care Essentials" | (none, plain open) |
| HealthTab | Vaccine "Book Now" | `'c1'` |
| HealthTab | Deworming CareCard | `'c2'` |
| HealthTab | Flea/Tick CareCard | `'c5'` |
| HealthTab | Annual Checkup | `'c14'` |
| HygieneTab | Grooming "Book Now" | `'c7'` |
| NutritionTab | "Order Supplements" | `'c4'` |
| ConditionsTab | (interface only for now) | — |

---

## Step 6 — Create workflow SOP
**File:** `workflows/order_cart_payments.md`

Document covering:
- Trigger: any cart CTA from dashboard tabs or header
- Deep-link signal: `pinnedItemId` propagation
- Cart state model and item classification (urgent vs recommended)
- Address management flow
- Payment method options
- Success screen and order confirmation
- Phase 2 notes: backend `POST /orders` integration

---

## Verification
1. Run `cd frontend && npx next build` — must pass with 0 errors
2. Visual check: open dashboard → tap any "Order Now" → verify pinned item banner appears and item is at top
3. Cart flow: add/remove items, adjust qty, apply coupon → proceed to payment
4. Payment: test all 4 payment methods render correctly, address add/edit works
5. Success: verify itemized receipt shows all cart items with correct totals
