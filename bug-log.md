## [2026-04-02] Life stage cache stale on breed-size change
What broke: `life_stage_service` cache hit path accepted stage match only and could return stale traits after weight-driven breed-size changes.
Root cause: Cache key logic did not validate `breed_size` alongside `life_stage`.
Fix: Cache is now valid only when both fields match; regenerate and replace stale rows when either changes.
File(s): backend/app/services/life_stage_service.py, backend/tests/unit/test_life_stage_service.py

## [2026-04-02] Care-plan reasons could crash before GPT fallback
What broke: `generate_care_plan_reasons` could raise before the GPT retry block (e.g., invalid weight parsing or nutrition summary failure), bypassing empty-dict fallback behavior.
Root cause: Exception handling wrapped only GPT call/parsing, not context-building steps.
Fix: Added defensive guards around context building, safe weight coercion, malformed item filtering, and fail-open return `{}` on any context preparation error.
File(s): backend/app/services/ai_insights_service.py, backend/tests/unit/test_ai_insights_service.py

## [2026-04-03] Care plan v2 keys mismatched dashboard response contract
What broke: `dashboard_service` expected `care_plan_v2` keys `continue/attend/add`, but `care_plan_engine` returned `continue_items/attend_items/add_items`, so orderable items and generated reasons were not attached.
Root cause: Service integration assumed normalized keys without adapter logic between engine and API response contract.
Fix: Added care plan shape normalization in dashboard service and applied reason enrichment after normalization.
File(s): backend/app/services/dashboard_service.py

## [2026-04-03] Dashboard globals duplicated class blocks
What broke: Task-012 dashboard styles were duplicated in `globals.css`, creating maintainability risk and inconsistent overrides.
Root cause: A repeated style insertion left two full blocks for shared dashboard classes.
Fix: Removed the duplicate block and kept a single canonical dashboard style definition.
File(s): frontend/src/app/globals.css

## [2026-04-04] Level-2 nudge post-schedule cadence skipped 30-day gate
What broke: Level 2 users past slot 5 could be selected before the intended post-schedule window, causing over-frequent nudge eligibility.
Root cause: `_select_level2_message` only enforced O+N gating for slots within `[1,5,10,20,30]` and lacked explicit 30-day cadence checks for `completed >= 5`.
Fix: Added post-schedule day gating in Level 2 using `NUDGE_POST_SCHEDULE_INTERVAL_DAYS`, with inactivity override still explicitly controlled by `ignore_schedule=True`.
File(s): backend/app/services/nudge_scheduler.py, backend/tests/test_nudges_and_reminders_comprehensive.py

## [2026-04-11] Late-arriving meal/supplement messages misclassified at every post-diet step
What broke: When a user sent diet or supplement details across multiple WhatsApp messages, later messages arrived after state had already advanced. The wrong step handler processed them — food got stored as supplements, supplements got treated as preventive info, etc. — and the original step's question was never properly answered.
Root cause: No onboarding step handler guarded against cross-step input. Each step blindly processed any incoming text using its own parser, without checking whether the message actually belonged to a prior step.
Fix: Added two helpers — `_ai_is_food_not_supplement()` for the supplements step, and the generalised `_classify_prior_step_input()` + `_save_prior_step_dietary_input()` pair for all later steps. Guards inserted in: `awaiting_supplements`, `awaiting_preventive`, `awaiting_prev_retry`, `awaiting_vaccine_type`, `awaiting_flea_brand`, `awaiting_documents`. On detection, data is saved to the correct table and the current step's question is re-asked.
File(s): backend/app/services/onboarding.py

## [2026-04-04] NudgesView category extras iteration failed TS target compatibility
What broke: Frontend type-check and build failed after introducing NudgesView category grouping logic.
Root cause: Spreading `Map.keys()` (`[...groups.keys()]`) required iterator downlevel support not available under the current TypeScript target/tooling settings.
Fix: Replaced iterator spread with `Array.from(groups.keys())` and re-ran type/build verification.
File(s): frontend/src/components/nudges/NudgesView.tsx
