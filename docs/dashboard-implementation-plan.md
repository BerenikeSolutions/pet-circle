# PetCircle Dashboard — Implementation Plan

## Context

10-phase plan bringing the dashboard to full parity with the design reference (JSX prototype), wired to real backend APIs with no mock data.

---

## Phase Status

| Phase | Feature | Status |
|-------|---------|--------|
| 0 | WhatsApp Flow Documentation | ✅ COMPLETE |
| 1 | Database Foundation | ✅ COMPLETE |
| 2 | Health Tab | ✅ COMPLETE |
| 3 | Nutrition Tab | ✅ COMPLETE |
| 4 | Hygiene Tab | ✅ COMPLETE |
| 5 | Conditions Tab | ✅ COMPLETE |
| 6 | Overview Tab | ✅ COMPLETE |
| 7 | Nudges & Action Plan | ⏳ PENDING |
| 8 | Cart & Orders | ✅ COMPLETE |
| 9 | WhatsApp Reminders Screen | ⏳ PENDING |

---

## Completed Phases

### Phase 0 — WhatsApp Flow Documentation
- `docs/whatsapp-onboarding-flow.md` — 18-step conversation flow, processing animation, 5 reminder templates, reminder schedule logic

### Phase 1 — Database Foundation
- Models: `weight_history`, `diet_item`, `hygiene_preference`, `product_catalog`, `nudge`, `cart_item`
- Migration: `backend/migrations/001_add_dashboard_tables.sql`
- Seed script: `backend/scripts/seed_product_catalog.py`

### Phase 2 — Health Tab
- Weight history API (add, list, delete)
- Checkup/vaccination record APIs
- `HealthTab.tsx` wired to real APIs

### Phase 3 — Nutrition Tab
- Diet items CRUD, order reminder logic, nutrition analysis matching by product name
- `NutritionTab.tsx` with full macro breakdown

### Phase 4 — Hygiene Tab
- Hygiene preferences API (auto-seeds defaults on first access)
- `HygieneTab.tsx` with frequency settings and periodic grooming

### Phase 5 — Conditions Tab
- 12 endpoints: conditions CRUD, medications, monitoring, vet visits
- GPT-generated conditions summary (`condition_service.py`)
- `ConditionsTab.tsx` with timeline, vet visit, PDF placeholder

### Phase 6 — Overview Tab
- 6-category weighted health score (`health_score.py`)
- Real contacts API, nutrition note
- `OverviewTab.tsx` with care tiles, reminders, docs, contacts

### Phase 8 — Cart & Orders
- DB-driven cart CRUD (`cart_service.py`)
- Recommendation engine by species/breed/nutrition gaps
- `CartView.tsx` rewritten (no mock data)
- Additional performance work: migration 017 indexes, `selectinload` eager loading on all dashboard queries

---

## Pending Phases

### Phase 7 — Nudges & Action Plan
**Backend**: `nudge_engine.py`, `nudge_sender.py`, `nudge_config_service.py` — all exist.
**Frontend**: `NudgesView.tsx` — not built.

Components needed:
- Nudge card list (actionable items per pet)
- Mark nudge as done / snooze
- Action plan summary screen

### Phase 9 — WhatsApp Reminders Screen
**Backend**: Reminder data available via existing dashboard endpoint.
**Frontend**: `RemindersView.tsx` — not built.

Components needed:
- Reminder preview list (upcoming + overdue)
- Reminder status badges
- Link to WhatsApp to respond to reminders

---

## Key Architecture Notes

- All models use UUID PKs (`from app.database import Base`)
- Pet FK: `UUID(as_uuid=True), ForeignKey("pets.id", ondelete="CASCADE")`
- Dashboard router validates token via `validate_dashboard_token(db, token)`
- Hygiene preferences auto-seed defaults on first access
- Nutrition analysis matches diet items to `product_catalog` by name
- API types: `frontend/src/lib/api.ts`
