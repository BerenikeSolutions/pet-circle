---
task: 009
feature: dashboard-rebuild
status: pending
depends_on: [2, 3, 4, 5, 6, 7, 8]
---

# Task 009: Backend API — Enrich Dashboard Endpoint + New Endpoints

## Session Bootstrap
Skills: /python-patterns, /api-design, /code-writing-software-development
Commands: /verify, /task-handoff

---

## Objective

Wire all new services into the dashboard router: extend `GET /dashboard/{token}` with 6 new fields, add `GET /dashboard/{token}/health-trends-v2` and `GET /dashboard/{token}/records-v2` endpoints. Parallelize service calls with `asyncio.gather`. Isolate failures per section.

---

## Codebase Context

### Key Code Snippets

```python
# [Dashboard GET endpoint — from backend/app/routers/dashboard.py:144-179]
@router.get("/{token}")
async def dashboard_get(
    token: str,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        data = get_dashboard_data(db, token)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return data
    except ValueError as e:
```

```python
# [dashboard_service.py get_dashboard_data — from backend/app/services/dashboard_service.py:109-149]
def get_dashboard_data(db: Session, token: str) -> dict:
    dashboard_token = validate_dashboard_token(db, token)
    pet_id = dashboard_token.pet_id
    # ... loads pet, preventive_records, reminders, documents, health_score
```

```python
# [Token validation — from backend/app/services/dashboard_service.py:64-105]
def validate_dashboard_token(db: Session, token: str) -> DashboardToken:
    dashboard_token = db.query(DashboardToken).filter(DashboardToken.token == token).first()
    if not dashboard_token:
        raise ValueError("Invalid dashboard token.")
    if dashboard_token.revoked:
        raise ValueError("This dashboard link has been revoked.")
```

### Key Patterns in Use
- **Token validation first:** All dashboard endpoints validate token before any service call
- **Error isolation:** Each service call wrapped in try/except, returns None/empty on failure
- **Cache-Control header:** `no-store` on all dashboard responses
- **asyncio.gather:** Use for parallelizing independent service calls

---

## Handoff from Previous Task

**Files changed by previous task:** _(none yet)_

---

## Implementation Steps

1. **Extend `get_dashboard_data()`** in `dashboard_service.py`:
   - After existing data load, call new services in parallel via `asyncio.gather`:
     - `care_plan_engine.compute_care_plan(db, pet)`
     - `life_stage_service.get_life_stage_data(db, pet)`
     - `vet_summary_service.get_vet_summary(db, pet.id)`
     - `nutrition_service.get_diet_summary(db, pet)`
     - `ai_insights_service.generate_recognition_bullets(db, pet)`
   - After care_plan resolves, call `generate_care_plan_reasons(db, pet, orderable_items)` (depends on care plan result)
   - Build `health_conditions_summary` from existing conditions data
   - Add all 6 new fields to response dict
   - Wrap each service call in try/except — return None/empty on failure, log error

2. **Add `GET /dashboard/{token}/health-trends-v2`** in `dashboard.py`:
   - Validate token
   - Call `health_trends_service.get_health_trends(db, pet)`
   - Return structured response
   - Cache-Control: no-store

3. **Add `GET /dashboard/{token}/records-v2`** in `dashboard.py`:
   - Validate token
   - Call `records_service.get_records(db, pet)`
   - Return structured response
   - Cache-Control: no-store

4. **Create/update Pydantic response models** for new endpoint shapes

5. Write integration tests for enriched response and new endpoints

_Requirements: 18, 19, 20_

---

## Acceptance Criteria
- [ ] Enriched dashboard response includes all 6 new fields
- [ ] Service calls parallelized via asyncio.gather
- [ ] Individual service failures don't crash the response (isolated try/except)
- [ ] Health trends endpoint returns structured data
- [ ] Records endpoint returns structured data
- [ ] Token validation on all new endpoints
- [ ] Cache-Control headers set
- [ ] Integration tests pass
- [ ] All existing tests pass
- [ ] `/verify` passes

---

## Handoff to Next Task

**Files changed:** _(fill via /task-handoff)_
**Decisions made:** _(fill via /task-handoff)_
**Context for next task:** _(fill via /task-handoff)_
**Open questions:** _(fill via /task-handoff)_
