---
task: 012
feature: dashboard-rebuild
status: complete
depends_on: [11]
---

# Task 012: Frontend — Dashboard Cards (Page 1)

## Session Bootstrap
Skills: /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Create all 8 dashboard card components plus a DashboardView wrapper that composes them into the scrolling Page 1. Match the JSX reference pixel-for-pixel and enforce all guardrails.

---

## Codebase Context

### Key Code Snippets

```typescript
// [Banner from JSX — from project details/PetDashboard_3103_4.jsx:392-411]
<div className="banner">
  <div className="bn-top">
    <span className="brand">PetCircle</span>
    <button className="bell" onClick={onGoToReminders}>🔔</button>
  </div>
  <div className="profile">
    <div className="avatar">{pet.avatar}</div>
    <div>
      <div className="dog-name">{pet.name}</div>
      <div className="dog-sub">{pet.breed} · {pet.sex} · {pet.ageLabel} · ⚖️ {pet.weight}</div>
    </div>
  </div>
  <div className="vet-row">
    <span>🩺</span><span className="vet-l">Vet</span>
    <span className="vet-v">{pet.vet.name}</span><span className="vet-sep">·</span>
    <span className="vet-l">Last visit</span><span className="vet-v">{pet.vet.lastVisit}</span>
  </div>
</div>
```

```typescript
// [Care Plan buckets — from project details/PetDashboard_3103_4.jsx:358-362]
const BUCKET_META = {
  continue: { label: '✅ Continue', bg: '#F0FFF4', border: '#C3E6CB', color: '#1e8c3a' },
  attend:   { label: '⚠️ Attend to', bg: '#FFF0F0', border: '#FFCDD2', color: '#c0392b' },
  add:      { label: '✦ Quick Fixes to Add', bg: '#FFF3EE', border: '#FFD5C2', color: '#FF6B35' },
};
```

```typescript
// [Cart floater IntersectionObserver — from project details/PetDashboard_3103_4.jsx:369-376]
useEffect(() => {
  if (floaterUnlocked) return;
  const btn = document.querySelector('.order-btn');
  if (!btn) return;
  const obs = new IntersectionObserver(([e]) => {
    if (e.isIntersecting) { setFloaterUnlocked(true); obs.disconnect(); }
  }, { threshold: 0.1 });
  obs.observe(btn);
  return () => obs.disconnect();
}, [floaterUnlocked]);
```

```typescript
// [Order button states — from project details/PetDashboard_3103_4.jsx:495-497]
{isAdded ? `✓ Added${inCart && inCart.qty > 1 ? ` (${inCart.qty})` : ''}` : inCart ? `Order Again (${inCart.qty} in cart)` : 'Order Now →'}
```

```typescript
// [LifeStageCard marker position — from project details/PetDashboard_3103_4.jsx:302-307]
const STAGE_WIDTHS = [10, 12, 45, 33];
const STAGE_STARTS = STAGE_WIDTHS.reduce((acc, w, i) => { acc.push(i === 0 ? 0 : acc[i-1] + STAGE_WIDTHS[i-1]); return acc; }, []);
const adultStart = STAGE_STARTS[2], adultWidth = STAGE_WIDTHS[2];
const posInAdult = (pet.ageMonths - 24) / (84 - 24);
const markerPct = adultStart + posInAdult * adultWidth;
```

### Key Patterns in Use
- **CSS classes from JSX:** `.card`, `.banner`, `.sec-lbl`, `.care-item`, `.order-btn`, `.nav-card`, `.floater`
- **Inline styles for specifics:** The JSX uses inline styles extensively for fine-tuned spacing
- **All CSS classes defined in globals.css** (will be added in this task)

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. Add all JSX reference CSS classes to `globals.css` (`.card`, `.banner`, `.bn-top`, `.brand`, `.bell`, `.profile`, `.avatar`, `.dog-name`, `.dog-sub`, `.vet-row`, `.sec-lbl`, `.care-item`, `.care-name`, `.care-meta`, `.order-btn`, `.nav-card`, `.nav-arr`, `.floater`, `.fl-cart`, `.s-tag`, `.s-tag-g/y/r`, `.trait-pill`, `.trait-g/r/y/p`, `.dot`, `.dot-g/y/r`, `.care-sec`, `.care-hdr`, `.sec-source`)

2. Create 8 components in `frontend/src/components/dashboard/`:
   - `ProfileBanner.tsx` — gradient, brand, bell, avatar, pet info, vet row
   - `RecognitionCard.tsx` — report count, max 3 bullets, "View all reports →"
   - `LifeStageCard.tsx` — 4-stage bar, marker at ageMonths, traits, essential care
   - `HealthConditionsCard.tsx` — ALL ongoing conditions, insights, "Discuss with vet" CTA
   - `DietAnalysisCard.tsx` — 4 Donut grid, missing micros pills
   - `CarePlanCard.tsx` — 3 buckets in order, sections, items, order buttons with animation
   - `HealthRecordsNav.tsx` — tappable nav card with dynamic count
   - `CartFloater.tsx` — IntersectionObserver on first .order-btn

3. Create `DashboardView.tsx` wrapper composing all 8 cards with navigation callbacks

4. Enforce guardrails:
   - Banner: NO health status/scores
   - Recognition: max 3 bullets, 1 line each, observational
   - Life stage: marker by ageMonths, breed-specific traits
   - Conditions: show ALL ongoing (not just red)
   - Diet: correct thresholds
   - Care plan: no item in two buckets, "Attend to" has no orderable items
   - Order: reason required for orderable items

_Requirements: 2, 3, 4, 5, 6, 7, 8, 10, 11_

---

## Acceptance Criteria
- [ ] All 8 cards render correctly at 430px
- [ ] Banner: gradient, no health status/scores, vet name never abbreviated
- [ ] Recognition: max 3 bullets, 1 line each, "active health conditions" label
- [ ] Life stage: marker positioned by ageMonths, current stage dominates
- [ ] Conditions: ALL ongoing shown, insights max 2 unless ongoing patterns
- [ ] Diet: donuts use correct thresholds, Omega-3 at 15% = RED
- [ ] Care plan: 3 buckets in order, no duplicates, order button animation works
- [ ] Cart floater: appears on first order-btn scroll via IntersectionObserver
- [ ] `npm run build` passes
- [ ] `/verify` passes

---

## Handoff — What Was Done

- Added all Page-1 dashboard card components in `frontend/src/components/dashboard/` and composed them in `DashboardView.tsx`.
- Implemented guardrails in component logic: recognition capped to 3 bullets, conditions fallback to active-only summary, care-plan dedup across buckets, and no order buttons in the attend bucket.
- Added the required dashboard CSS class set to `frontend/src/app/globals.css` and removed an accidental duplicate style block to keep one canonical definition.

## Handoff — Patterns Learned

- Keep dashboard cards data-driven from `DashboardData` optional v2 fields, with safe fallbacks when backend rollout is partial.
- For the cart floater unlock behavior, scope `IntersectionObserver` to the dashboard container instead of global document queries.
- Use semantic clickable elements (`button`) for nav and links to avoid accessibility/lint regressions.

## Handoff — Files Changed

- `frontend/src/app/globals.css`
- `frontend/src/components/dashboard/dashboard-utils.ts`
- `frontend/src/components/dashboard/ProfileBanner.tsx`
- `frontend/src/components/dashboard/RecognitionCard.tsx`
- `frontend/src/components/dashboard/LifeStageCard.tsx`
- `frontend/src/components/dashboard/HealthConditionsCard.tsx`
- `frontend/src/components/dashboard/DietAnalysisCard.tsx`
- `frontend/src/components/dashboard/CarePlanCard.tsx`
- `frontend/src/components/dashboard/HealthRecordsNav.tsx`
- `frontend/src/components/dashboard/CartFloater.tsx`
- `frontend/src/components/dashboard/DashboardView.tsx`

## Status

COMPLETE
