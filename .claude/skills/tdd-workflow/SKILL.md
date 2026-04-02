---
name: tdd-workflow
description: Enforce test-driven development with Red/Green/Refactor cycle and 80%+ coverage across unit, integration, and E2E test types.
---

# TDD Workflow

---

## 1. Red/Green/Refactor Cycle

Write a failing test. Run it — confirm it fails. Write the minimum code to make it pass. Run again — confirm green. Refactor for clarity and quality. Never skip the red phase.

**Rule:** If you write implementation code before a failing test exists, stop and write the test first.

---

## 2. Test-First Discipline

Start every feature with a user journey: "As a [role], I want to [action], so that [benefit]." Derive test cases from that journey before touching any source file. Cover the happy path, edge cases, error paths, and boundary conditions.

**Rule:** No `it.skip`, `test.skip`, or disabled tests in committed code.

---

## 3. Coverage Requirements

Maintain 80%+ coverage across branches, functions, lines, and statements. Configure thresholds in `jest`/`vitest` config under `coverageThresholds.global`. Run `npm run test:coverage` to verify before every PR.

**Rule:** A PR that drops coverage below 80% must not merge.

---

## 4. Test Types and Placement

Use **unit tests** for pure functions, utilities, and component logic — co-locate alongside source files as `*.test.ts`. Use **integration tests** for API routes, database operations, and service interactions — place in `src/app/api/**/route.test.ts`. Use **E2E tests** (Playwright) for critical user flows — place in `e2e/*.spec.ts`.

**Rule:** Each test type lives in a predictable location; never mix unit and E2E tests in the same file.

---

## 5. Test Naming Conventions

Name tests in the pattern `[unit] [action] [expected outcome]`. Use `describe` to group by component or feature. Inner `it`/`test` blocks must read as plain English sentences. Example: `it('returns 400 when email is missing')`.

**Rule:** A test name must be understandable without reading the test body.

---

## 6. Test Isolation

Each test must set up its own data and tear down after itself. Never let tests share mutable state or depend on execution order. Use `beforeEach`/`afterEach` for setup and cleanup, not `beforeAll` when state can leak.

**Rule:** Any test must pass when run in isolation with `--testNamePattern`.

---

## 7. Mocking Guidelines

Mock only at the boundary of the unit under test. Mock external services (Supabase, Redis, OpenAI) with `jest.mock()` or `vi.mock()` in unit tests. Use real implementations in integration tests unless the service is unavailable in CI. Never mock the module you are testing.

**Rule:** If a mock makes the test pass for the wrong reason, delete the mock and fix the code.

---

## 8. TDD with AI-Generated Code

When using AI to generate implementation code, provide the failing tests as context first. Treat AI output as a draft — run tests immediately. If tests pass on the first generation, verify the implementation is not just pattern-matching your test assertions. Add at least one adversarial test case the AI did not see.

**Rule:** AI-generated code is not trusted until it passes tests you wrote before generation.

---

## 9. Continuous Testing

Run tests in watch mode during development (`npm test -- --watch`). Enforce `npm test && npm run lint` as a pre-commit hook. In CI, run with `--coverage` and upload reports to Codecov or equivalent.

**Rule:** Tests must run in under 30 seconds for the unit suite; flag and fix any test exceeding 50ms.
