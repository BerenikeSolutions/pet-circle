---
task: 008
feature: cart-rules-engine
status: pending
depends_on: [006]
---

# Task 008: Frontend — ProductSelectorCard component

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective
Create the `ProductSelectorCard` component — a bottom sheet that shows resolved products when user taps "Order Now". Supports all signal levels (L5 single product, L4 size selector, L3/L2 comparison cards).

---

## Codebase Context
> Pre-populated by Task Enrichment. No file reading required.

### Key Code Snippets

```tsx
// [BottomSheet UI primitive — from frontend/src/components/ui/BottomSheet.tsx:1-34]
interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}
export default function BottomSheet({ open, onClose, title, children }: BottomSheetProps) {
  // Locks body scroll when open
  // Renders: overlay backdrop + sliding panel (max-w-[430px], rounded top, 85vh max height)
  // Has drag handle bar at top
}
```

```tsx
// [CarePlanCard "Order Now" button — from frontend/src/components/dashboard/CarePlanCard.tsx:139-155]
{canOrder && (
  <button className="order-btn" type="button"
    onClick={() => onAddToCart(item, section.title)}>
    {isAdded ? `✓ Added` : `${ctaText} →`}
  </button>
)}
// onAddToCart callback is where ProductSelectorCard will be triggered
```

```tsx
// [CartView item display — from frontend/src/components/CartView.tsx:65-79]
// Shows: icon, name, SKU, section, price (Rs locale), qty buttons
// Price: Rs {item.price.toLocaleString("en-IN")}
```

```tsx
// [Existing design tokens — from frontend/src/app/globals.css]
// --orange: #D44800 (brand primary)
// --t1, --t2, --t3: text colors
// --bg-app: background
// Font: DM Sans (body), Fraunces (headings)
// Max width: 430px mobile-first
```

```typescript
// [API response shape — from design spec]
interface ProductResolveResponse {
  signal_level: string;
  products: ResolvedProduct[];
  cta_label: string | null;
  vet_diet_warning: boolean;
  pack_size_suggestion: string | null;
  message: string | null;
}
interface ResolvedProduct {
  sku_id: string;
  category: "food" | "supplement";
  brand_name: string;
  product_line?: string;    // food
  product_name?: string;    // supplement
  pack_size: string;
  mrp: number;
  discounted_price: number;
  price_per_unit: number;
  unit_label: string;       // "per kg" or "per unit"
  in_stock: boolean;
  vet_diet_flag: boolean;
  is_highlighted: boolean;
  highlight_reason?: string;
}
```

### Key Patterns in Use
- **Mobile-first:** 430px max-width, inline styles + CSS custom properties
- **Price format:** `Rs {price.toLocaleString("en-IN")}` for Indian locale
- **MRP strikethrough:** Show MRP crossed out, discounted price prominent
- **Component pattern:** Functional components with "use client" directive

---

## Handoff from Previous Task
> Populated by /task-handoff after prior task completes.

**Files changed by previous task:** _(none yet)_
**Decisions made:** _(none yet)_
**Context for this task:** _(none yet)_
**Open questions left:** _(none yet)_

---

## Implementation Steps
1. Create `frontend/src/components/dashboard/ProductSelectorCard.tsx`
2. Define props interface:
   ```tsx
   interface ProductSelectorCardProps {
     open: boolean;
     onClose: () => void;
     products: ResolvedProduct[];
     signalLevel: string;
     vetDietWarning: boolean;
     packSizeSuggestion: string | null;
     onAddToCart: (skuId: string, quantity: number) => void;
     hideSearchMore?: boolean;  // true for focus group
   }
   ```
3. Render using `BottomSheet` as container with title "Select Product"
4. Product list as radio-selectable cards:
   - Radio button + brand name + product line/name
   - Pack size label
   - MRP (strikethrough if different from discounted) + discounted price (bold, orange)
   - Price per unit label (e.g., "Rs.641/kg")
   - "Most Popular" / highlight reason badge on highlighted product
   - Top product pre-selected
5. Vet diet disclaimer below products when `vetDietWarning` (C5):
   - Amber background, text: "This is a therapeutic diet. Please use under veterinary guidance."
6. Pack size suggestion text when present (C7)
7. Quantity selector: `[ - ] {qty} [ + ]` row, default 1 (C1)
8. Bottom buttons row:
   - "Search more" (left, hidden when `hideSearchMore=true`)
   - "Add to cart" (right, orange background, calls `onAddToCart(selectedSku, qty)`)
9. Cancel (x) top right — use BottomSheet's built-in close or add explicit button

_Requirements: 5.1, 5.3, 5.6, 5.7, 5.10, 6.1-6.8_
_Skills: /code-writing-software-development_

---

## Acceptance Criteria
- [ ] `ProductSelectorCard.tsx` exists at `frontend/src/components/dashboard/`
- [ ] Renders as bottom sheet with product radio options
- [ ] Top product pre-selected with qty=1 (C1)
- [ ] MRP vs discounted price shown per C3
- [ ] Price per unit displayed
- [ ] Vet diet disclaimer shown when applicable (C5)
- [ ] Pack size suggestion shown when applicable (C7)
- [ ] "Add to cart" calls `onAddToCart` with selected sku_id and quantity
- [ ] "Search more" hidden when `hideSearchMore=true`
- [ ] Cancel (x) closes the card
- [ ] Follows project design system (DM Sans, --orange, 430px max-width)
- [ ] `/verify` passes (build succeeds)

---

## Handoff to Next Task
> Fill via `/task-handoff` after completing this task.

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
