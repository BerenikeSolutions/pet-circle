---
task: 025
feature: careplan-nudges
status: pending
depends_on: [020]
---

# Task 025: Frontend — CarePlan Food/Supplement CTA Enhancements

## Session Bootstrap
> Load these before reading anything else. Do not load skills not listed here.

Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Render differentiated CTAs for food/supplement items in the care plan: use `cta_label` from the API for button text, show amber "Due Soon" badge, and ensure food/supplement rows visually match vaccine row styling.

---

## Codebase Context

### Key Code Snippets

```typescript
// [Item rendering in CarePlanCard — from frontend/src/components/dashboard/CarePlanCard.tsx:59-105]
{section.items.map((item) => {
  const id = itemId(item, section.title);
  const inCartQty = cartQtyByItem[id] || 0;
  const isAdded = !!addedIds[id];
  const canOrder = bucketKey !== "attend" && item.orderable && !!item.reason;

  return (
    <div key={id} className="care-item">
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="care-name">{item.name}</div>
        <div className="care-meta">
          {item.freq} · Next: {item.next_due || "--"}
        </div>
        {item.reason && (
          <div style={{ fontSize: 11, color: "var(--t2)", lineHeight: 1.4, marginTop: 3, fontStyle: "italic" }}>
            {item.reason}
          </div>
        )}
      </div>

      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 5, flexShrink: 0 }}>
        <span className={`s-tag ${itemStatusClass(item)}`}>{item.status_tag}</span>

        {canOrder && (
          <button className="order-btn" type="button" onClick={() => onAddToCart(item, section.title)}
            style={isAdded ? { background: "#34C759", transform: "scale(1.04)", transition: "all .2s" } : { transition: "all .2s" }}
          >
            {isAdded
              ? `✓ Added${inCartQty > 1 ? ` (${inCartQty})` : ""}`
              : inCartQty > 0
                ? `Order Again (${inCartQty} in cart)`
                : "Order Now →"}  {/* ← This hardcoded text needs to use item.cta_label */}
          </button>
        )}
      </div>
    </div>
  );
})}
```

```typescript
// [CarePlanItem interface — already updated in task-022]
// cta_label?: string — "Order Now" | "Reorder" (from backend task-020)
```

### Key Patterns in Use
- **Status tag classes:** `itemStatusClass(item)` returns CSS class. Need to add `s-tag-y` for "Due Soon" amber.
- **Button text:** Currently hardcoded `"Order Now →"` — should use `item.cta_label || "Order Now"`.
- **Visual parity:** Vaccine rows in Continue bucket use same `care-item` class — food/supplement should match.

---

## Handoff from Previous Task
> Depends on task-020 (backend provides `cta_label` and `status_tag: "Due Soon"`).

**Files changed by previous task:** `care_plan_engine.py` now returns `cta_label` and conditional `status_tag`.
**Decisions made:** `cta_label` is "Order Now" (first time) or "Reorder" (repeat). `status_tag` is "Due Soon" when supply ≤7 days.
**Context for this task:** Frontend must read and render these new fields.

---

## Implementation Steps

1. **Update button text in `CarePlanCard.tsx`:**
   - Replace the hardcoded `"Order Now →"` with `item.cta_label ? `${item.cta_label} →` : "Order Now →"`.
   - This handles both new and legacy items.

2. **Add "Due Soon" amber badge:**
   - In `itemStatusClass()` (or inline), check `item.status_tag === "Due Soon"` → return `s-tag-y` (amber class).
   - Verify `s-tag-y` exists in globals.css (it's part of the design system from dashboard-rebuild).

3. **Ensure food/supplement row visual parity:**
   - Verify that food/supplement items in Continue bucket use the same `care-item` class and layout as vaccine items.
   - If there are visual differences, align padding, icon placement, and spacing.

4. **Ensure "reason" field builds connectivity:**
   - Verify that `item.reason` renders for food/supplement items (already does — line 72-76 of CarePlanCard).
   - The backend (task-020) should provide reason text connecting to health/nutrition insights.

5. **Verify build:**
   - `cd frontend && npm run build` — zero errors.

---

## Acceptance Criteria
- [ ] First-time food items show "Order Now →" CTA (from `cta_label`)
- [ ] Repeat food items show "Reorder →" CTA (from `cta_label`)
- [ ] Items with `status_tag: "Due Soon"` show amber badge
- [ ] Food/supplement rows visually match vaccine row styling in Continue bucket
- [ ] Reason text renders connecting to health/nutrition insights
- [ ] `npm run build` passes
