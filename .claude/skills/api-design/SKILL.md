---
name: api-design
description: Design consistent, developer-friendly REST APIs with correct resource naming, status codes, pagination, versioning, error envelopes, and rate limiting.
---

# API Design

Conventions for REST APIs that are predictable, easy to consume, and safe to evolve.

---

## 1. URL Conventions

Use plural, lowercase, kebab-case nouns. Never put verbs in URLs except for explicit action endpoints.

```
GET    /api/v1/users
GET    /api/v1/users/:id
POST   /api/v1/users
PUT    /api/v1/users/:id
PATCH  /api/v1/users/:id
DELETE /api/v1/users/:id

GET    /api/v1/users/:id/orders      # sub-resource for ownership
POST   /api/v1/orders/:id/cancel     # explicit action (verb acceptable)
POST   /api/v1/auth/login
```

**Rule:** Never use `getUsers`, `user` (singular), or `team_members` (snake_case) in URLs.

---

## 2. HTTP Methods and Status Codes

| Method | Idempotent | Use For |
|---|---|---|
| GET | Yes | Retrieve resources |
| POST | No | Create resources, trigger actions |
| PUT | Yes | Full replacement |
| PATCH | No | Partial update |
| DELETE | Yes | Remove a resource |

Required status codes:

```
200 OK              — GET, PUT, PATCH (with body)
201 Created         — POST (include Location header)
204 No Content      — DELETE, PUT (no body)
400 Bad Request     — Malformed JSON, missing fields
401 Unauthorized    — Missing or invalid auth
403 Forbidden       — Authenticated but not authorized
404 Not Found       — Resource does not exist
409 Conflict        — Duplicate entry, state conflict
422 Unprocessable   — Valid JSON, semantically invalid data
429 Too Many        — Rate limit exceeded (add Retry-After)
500 Internal Error  — Never expose stack traces
503 Unavailable     — Include Retry-After header
```

**Rule:** Never return `200 OK` with `"success": false` in the body — use the correct HTTP status code.

---

## 3. Error Envelope Format

All errors use this envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      { "field": "email", "message": "Must be a valid email address", "code": "invalid_format" },
      { "field": "age",   "message": "Must be between 0 and 150",    "code": "out_of_range"   }
    ]
  }
}
```

All successes wrap the resource in `data`:

```json
{ "data": { "id": "abc-123", "email": "alice@example.com", "created_at": "2025-01-15T10:30:00Z" } }
```

**Rule:** Never expose internal details (SQL errors, stack traces, internal IDs) in error responses.

---

## 4. Pagination Patterns

**Offset pagination** — simple, supports jump-to-page:

```
GET /api/v1/users?page=2&per_page=20
```

Response includes `meta.total`, `meta.page`, `meta.per_page`, `meta.total_pages` and `links.next`, `links.last`.

**Cursor pagination** — consistent performance at any dataset size:

```
GET /api/v1/users?cursor=eyJpZCI6MTIzfQ&limit=20
```

Fetch `limit + 1` rows; if extra row exists set `has_next: true` and return opaque `next_cursor`.

| Use Case | Type |
|---|---|
| Admin dashboards, datasets < 10K | Offset |
| Infinite scroll, feeds, large datasets | Cursor |
| Public APIs | Cursor (default) |
| Search results with page numbers | Offset |

**Rule:** Never use `OFFSET` on tables exceeding 100K rows — switch to cursor pagination.

---

## 5. Filtering, Sorting, and Sparse Fieldsets

```
# Equality
GET /api/v1/orders?status=active&customer_id=abc-123

# Comparison (bracket notation)
GET /api/v1/products?price[gte]=10&price[lte]=100

# Multiple values
GET /api/v1/products?category=electronics,clothing

# Sorting (prefix - for descending)
GET /api/v1/products?sort=-created_at,price

# Sparse fieldsets
GET /api/v1/users?fields=id,name,email
```

---

## 6. Versioning Strategy

Use URL path versioning: `/api/v1/`, `/api/v2/`.

```
1. Start with /api/v1/ — do not version until a breaking change is needed.
2. Maintain at most 2 active versions (current + previous).
3. Announce deprecation 6 months in advance for public APIs.
4. Add Sunset header: Sunset: Sat, 01 Jan 2026 00:00:00 GMT
5. Return 410 Gone after sunset date.
```

Non-breaking changes (new fields, new optional params, new endpoints) do not require a new version. Breaking changes (removed/renamed fields, changed types, changed auth) require a new version.

**Rule:** Never change a field type or remove a field in an existing version.

---

## 7. Authentication Headers

```
# Bearer token (user-facing)
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# API key (server-to-server)
X-API-Key: sk_live_abc123
```

Always check resource ownership before returning data. Return `403 Forbidden`, not `404 Not Found`, when the resource exists but the user cannot access it.

---

## 8. Rate Limiting

Return these headers on every response:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```

On `429 Too Many Requests`, add `Retry-After: 60`.

| Tier | Limit | Window |
|---|---|---|
| Anonymous | 30/min | Per IP |
| Authenticated | 100/min | Per user |
| Premium | 1000/min | Per API key |
| Internal | 10000/min | Per service |

---

## 9. OpenAPI / Swagger

Document every endpoint in an OpenAPI spec. Update the spec before shipping new endpoints. Include request schemas, response schemas, error codes, and authentication requirements. Validate request bodies against a schema library (Zod, Pydantic, Bean Validation) and return `422` on semantic failures.

**Rule:** Never ship a public endpoint without a corresponding OpenAPI spec entry.

---

## 10. Pre-Ship Checklist

- [ ] URL follows naming conventions (plural, kebab-case, no verbs)
- [ ] Correct HTTP method and status codes
- [ ] Input validated with schema library
- [ ] Error responses use standard envelope
- [ ] Pagination on all list endpoints
- [ ] Authentication required or explicitly public
- [ ] Authorization checks resource ownership
- [ ] Rate limiting configured
- [ ] Response leaks no internal details
- [ ] OpenAPI spec updated
