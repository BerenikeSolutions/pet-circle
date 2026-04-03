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
