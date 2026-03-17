# Workflow: Order Cart & Payments

## Objective

Enable pet parents to order care products (supplements, medications, grooming, checkups) directly from the dashboard. Supports deep-linking from tab CTAs, multi-item cart management, address selection, multiple payment methods, and order confirmation.

## Trigger

User taps any cart-related CTA button from the dashboard:
- **DashboardHeader:** Cart icon (plain open, no pinned item)
- **OverviewTab:** "Order Now — Care Essentials" (plain open)
- **HealthTab:** "Book Now" buttons for vaccine (`c1`), deworming (`c2`), flea/tick (`c5`), annual checkup (`c14`)
- **HygieneTab:** "Book Now" for grooming (`c7`)
- **NutritionTab:** "Order Supplements" (`c4`)
- **ConditionsTab:** Reserved for Phase 2

## Required Inputs

- `pinnedItemId` (optional): Cart item ID passed from the triggering CTA
- `data`: Full pet dashboard data object (pet name, existing records)
- Cart item catalog: Hardcoded in `CartView.tsx` with id, name, price, category, icon

## Steps

### 1. Deep-link signal propagation

- When a tab CTA is tapped, it calls `onCartClick(itemId?)` with an optional cart item ID.
- `DashboardClient` stores this as `pinnedCartItem` state and renders `CartView` with `pinnedItemId` prop.
- If no item ID is provided, cart opens without a pinned item.

### 2. Cart initialization

- On mount, if `pinnedItemId` is provided, auto-add it to the cart (`cart[pinnedItemId] = true`).
- Display a pinned item banner (orange `#FFF6ED` background) showing the item name.
- Sort pinned item to the top of the list.

### 3. Item classification

- **Urgent items:** Items that are in the cart OR match the pinned item ID. Displayed under "Urgent for {petName}".
- **Recommended items:** All other items not currently in cart. Displayed under "Recommended for {petName}".
- Each item shows: colored icon box, name, unit price, quantity controls, per-row total.
- Toggle: circular button — orange ✓ when in cart, gray ＋ when not.

### 4. Cart summary and coupon

- Derived values computed via `useMemo`: items in cart, subtotal, discount, delivery fee, total.
- Coupon input in sticky footer above totals line.
- Coupon applies a percentage discount to subtotal.

### 5. Proceed to payment

- User taps "Place Order" button in cart footer.
- Screen transitions to payment view.

### 6. Address management

- Display saved addresses as radio list.
- Each address has: name, address line, tag (Home/Work/Other).
- User can add or edit addresses via inline bottom sheet with tag chip selector.
- One address must be selected before payment can proceed.

### 7. Payment method selection

- **UPI:** Text input for UPI ID (e.g., `name@upi`).
- **Credit/Debit Card:** Card number (auto-formatted with spaces every 4 digits), cardholder name, expiry (auto `/` after MM), CVV (`type="password"`, max 4 chars).
- **Net Banking:** Chip buttons for banks: HDFC Bank, ICICI Bank, SBI, Axis Bank, Kotak Bank, Yes Bank.
- **Cash on Delivery:** No additional input required.

### 8. Order confirmation (success screen)

- Generate order ID: `PC-{random 5 digits}`.
- Display itemized receipt: icon + name + per-item total for each cart item.
- "Total paid" summary row.
- Green delivery note box with estimated delivery info.
- "Back to Dashboard" button returns to main dashboard.

## Expected Output

- Cart opens with correct pinned item (if any) highlighted and auto-added.
- User can add/remove items, adjust quantities, apply coupon.
- Payment screen collects address and payment method.
- Success screen shows itemized order confirmation.
- All state is client-side only (Phase 1 — no backend persistence).

## Edge Cases

- **No pinned item:** Cart opens showing all items, none pre-selected.
- **Invalid pinned item ID:** Ignored silently; cart opens normally.
- **Empty cart at checkout:** "Place Order" button is disabled when no items are in cart.
- **Zero quantity:** Removing all quantity of an item removes it from cart.
- **No address selected:** Payment button disabled until an address is chosen.
- **Card field validation:** Auto-formatting prevents malformed input. No server-side validation in Phase 1.
- **Coupon not found:** Display inline error message; do not block cart flow.
- **Multiple rapid CTA taps:** `pinnedCartItem` state updates atomically; last tap wins.

## Phase 2 Notes

- **Backend integration:** Add `POST /orders` endpoint to persist orders in `orders` table.
- **Payment gateway:** Integrate Razorpay or similar for real payment processing.
- **Order status tracking:** Add order status updates via WhatsApp template messages.
- **Inventory management:** Validate item availability before order confirmation.
- **Address persistence:** Store addresses in `user_addresses` table linked to user record.
- **Order history:** Add "My Orders" tab or section to dashboard.
