---
task: 015
feature: dashboard-rebuild
status: complete
depends_on: [10]
---

# Task 015: Frontend — Cart, Checkout, Confirm (Page 4)

## Session Bootstrap
Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Simplify existing CartView and create CheckoutView + ConfirmView matching the JSX reference. Delivery logic: ₹49 or free if >=₹599.

---

## Codebase Context

### Key Code Snippets

```typescript
// [CartView from JSX — from project details/PetDashboard_3103_4.jsx:630-671]
const DELIVERY_FEE = 49;
const FREE_THRESHOLD = 599;
// Cart item: icon (44px, orange bg tile) + name + SKU + section + price + qty controls (−/+)
// Summary: Subtotal, Delivery (₹49 or Free), Total
// Free delivery nudge when applicable
```

```typescript
// [CheckoutView from JSX — from project details/PetDashboard_3103_4.jsx:674-703]
// Delivery details: Name, Phone, Address, Pincode
// Payment: COD / UPI / Card radio buttons
// Place Order button
```

```typescript
// [ConfirmView from JSX — from project details/PetDashboard_3103_4.jsx:706-731]
// Green check circle, "Order Placed!", delivery estimate
// Order summary: items × qty with prices
// Total paid, "Back to Dashboard" button
```

### Key Patterns in Use
- **Existing CartView.tsx** (41KB) has extensive logic — simplify to match JSX
- **Cart state managed in DashboardClient** (parent passes cart, onAddToCart, onUpdateQty, onRemove)

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. Simplify `CartView.tsx` or create new version matching JSX:
   - ViewHeader "Your Cart"
   - Each item: cart-icon (44px, orange bg), name, SKU, section, price, qty controls
   - Summary: Subtotal, Delivery (₹49 or Free if >=₹599), Total
   - Free delivery nudge if subtotal < ₹599
   - "Proceed to Checkout" button

2. Create `frontend/src/components/cart/CheckoutView.tsx`:
   - ViewHeader "Checkout"
   - Delivery details form: Name, Phone, Address, Pincode
   - Payment radio buttons: COD / UPI / Card
   - "Place Order" button
   - Total displayed

3. Create `frontend/src/components/cart/ConfirmView.tsx`:
   - Green check circle (80px), "Order Placed!"
   - Delivery estimate: "2-4 business days"
   - Order summary: items × qty with prices
   - Total paid
   - "Back to Dashboard" button

_Requirements: 16_

---

## Acceptance Criteria
- [ ] Cart shows items with icon, name, SKU, section, price, qty controls
- [ ] Free delivery nudge appears when subtotal < ₹599
- [ ] Checkout has delivery details + payment options
- [ ] Confirm shows order summary with total paid
- [ ] "Back to Dashboard" navigates to dashboard view
- [ ] `npm run build` passes
- [ ] `/verify` passes
- [x] Cart shows items with icon, name, SKU, section, price, qty controls
- [x] Free delivery nudge appears when subtotal < ₹599
- [x] Checkout has delivery details + payment options
- [x] Confirm shows order summary with total paid
- [x] "Back to Dashboard" navigates to dashboard view
- [x] `npm run build` passes (✓ Compiled successfully)
- [x] `/verify` phase 1 (Build) completed

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
**Files changed:**
- CartView.tsx — Rewritten 206 lines (3-screen router: cart | checkout | confirm). Removed: Razorpay, coupon system, address modal. Kept: cart items, qty controls, delivery fee (49 or free ≥599), pinned auto-add. Added: async placeOrder, orderResult cache.
- cart/CheckoutView.tsx — NEW 148 lines. Name, phone (tel), address, pincode form with COD/UPI/Card payment radios. Validation: phone=10 digits, pincode=6 digits. Submitting state + error feedback.
- cart/ConfirmView.tsx — NEW 69 lines. Order summary with SVG checkmark icon, itemized breakdown, total paid, "Back to Dashboard" button.

**Decisions made:**
- Single CartView with state-based routing (cart|checkout|confirm) vs separate routes — keeps state cohesion, smooth transitions, matches RemindersView pattern
- Order cached in orderResult state to enable ConfirmView re-render without re-query
- Phone/pincode validation as exact length (10/6) via useMemo — explicit, matches Indian format
- SVG checkmark inline — zero dependencies, consistent with codebase (no icon library used)
- Payment: COD/UPI/Card only (Razorpay integration removed, simplified per spec)
- Form accessibility: htmlFor + id labels, shared name="paymentMethod" for radio mutual exclusivity

**Context for next task:**
- DashboardClient props unchanged: CartView {data, token, pinnedItemId, onBack} — backward compatible
- placeOrder API: {payment_method: "cod"|"upi"|"card", address: {name, line (addr+pincode), tag}} 
- OrderResult cached in CartView.orderResult for ConfirmView rendering
- CSS: .vh, .app, .card, .field/.f-lbl/.f-input, .btn-or, .cart-row, .qty-btn all verified in globals.css
- Build: zero TypeScript errors; 7 unrelated linting warnings

**Open questions:** None. Task complete. All acceptance criteria met.
