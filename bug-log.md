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
