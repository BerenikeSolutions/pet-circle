---
name: security-review
description: Apply OWASP Top 10 security patterns when implementing auth, input handling, API endpoints, secrets, or payment features.
---

# Security Review

---

## 1. Secrets Management

Store all credentials in environment variables — never in source code. Verify each required secret exists at startup and throw a descriptive error if missing. Add `.env.local` to `.gitignore` and audit git history for accidental commits using `git log -S 'sk-'`.

**Rule:** Any hardcoded API key, token, or password is a critical finding — fix before committing.

---

## 2. Input Validation

Validate every user-supplied value with a schema library (Zod, Joi, Yup) before processing. Use whitelist validation, not blacklist. Restrict file uploads by size, MIME type, and extension. Never pass raw user input to database queries, shell commands, or HTML renderers.

**Rule:** Reject input that does not match the expected schema; never sanitize and accept.

---

## 3. SQL Injection Prevention

Use parameterized queries or an ORM for all database interactions. Never concatenate user input into a SQL string. When using Supabase, chain `.eq()`, `.filter()`, and similar builder methods — never use `.rpc()` with raw string interpolation.

**Rule:** A grep for string-concatenated SQL (`query + userInput`) must return zero results.

---

## 4. Authentication and Authorization

Store tokens in `HttpOnly; Secure; SameSite=Strict` cookies — never in `localStorage`. Check authorization before every sensitive operation: verify the requester's role or ownership, not just authentication status. Enable Row Level Security on all Supabase tables and write explicit policies for each operation.

**Rule:** Every protected endpoint must return 401 when unauthenticated and 403 when unauthorized — test both.

---

## 5. XSS Prevention

Sanitize any user-provided HTML with DOMPurify before rendering. Use allowlists for permitted tags and strip all attributes by default. Configure a Content Security Policy header with `default-src 'self'`. Rely on React's default escaping; never use `dangerouslySetInnerHTML` without sanitization.

**Rule:** Any `dangerouslySetInnerHTML` without a preceding `DOMPurify.sanitize()` call is a blocking finding.

---

## 6. CSRF Protection

Add CSRF tokens to all state-changing operations. Set `SameSite=Strict` on session cookies. Validate the `X-CSRF-Token` header on POST, PUT, PATCH, and DELETE endpoints.

**Rule:** State-changing API routes without CSRF validation must not ship.

---

## 7. Rate Limiting

Apply rate limiting to every API route. Use stricter limits on expensive operations (search, auth, file upload). Implement both IP-based and user-based limits for authenticated endpoints. Return `429 Too Many Requests` with a `Retry-After` header.

**Rule:** No API endpoint ships without a rate limit configured.

---

## 8. Sensitive Data Exposure

Redact passwords, tokens, card numbers, and PII from all logs. Return generic error messages to clients — log full details server-side only. Never expose stack traces, internal paths, or database error messages in API responses.

**Rule:** Run `grep -r 'console.log' src/` and verify no log line outputs a secret or full error object.

---

## 9. Dependency Security

Run `npm audit` before every release. Fix or document every critical and high vulnerability. Commit lock files (`package-lock.json` / `pnpm-lock.yaml`). Use `npm ci` in CI pipelines, not `npm install`. Enable Dependabot or Renovate for automated update PRs.

**Rule:** A release with an unmitigated critical `npm audit` finding must not deploy.

---

## 10. Pre-Deployment Checklist

Before any production deployment verify: no hardcoded secrets, all inputs validated, all queries parameterized, user HTML sanitized, CSRF enabled, tokens in httpOnly cookies, RLS enabled, rate limits active, HTTPS enforced, CSP headers set, errors generic to clients, no sensitive data in logs, dependencies audited, CORS scoped to expected origins, file uploads validated.

**Rule:** Every item on this checklist must be confirmed — not assumed — before merging to main.
