---
task: 015
feature: dashboard-rebuild
status: pending
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

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
