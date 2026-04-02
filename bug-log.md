## [2026-04-02] Life stage cache stale on breed-size change
What broke: `life_stage_service` cache hit path accepted stage match only and could return stale traits after weight-driven breed-size changes.
Root cause: Cache key logic did not validate `breed_size` alongside `life_stage`.
Fix: Cache is now valid only when both fields match; regenerate and replace stale rows when either changes.
File(s): backend/app/services/life_stage_service.py, backend/tests/unit/test_life_stage_service.py
