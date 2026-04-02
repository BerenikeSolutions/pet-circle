---
name: database-migrations
description: Safe, reversible database schema changes with zero-downtime patterns, rollback strategies, data backfills, and constraint handling for production systems.
---

# Database Migrations

Principles and patterns for schema changes that never lock production tables or lose data.

---

## 1. Core Rules

- Every change is a migration — never alter production databases manually.
- Migrations are forward-only in production — rollbacks use new forward migrations.
- Schema and data migrations are separate — never mix DDL and DML in one migration.
- Test migrations against production-sized data — a migration that works on 100 rows may lock on 10M rows.
- Migrations are immutable once deployed — never edit a migration that has run in production.

---

## 2. Pre-Migration Checklist

- [ ] Migration has both UP and DOWN (or is explicitly marked irreversible)
- [ ] No full table locks on large tables (use concurrent operations)
- [ ] New columns are nullable or have a default (never add `NOT NULL` without a default)
- [ ] Indexes created with `CONCURRENTLY` on existing tables
- [ ] Data backfill is a separate migration from the schema change
- [ ] Tested against a copy of production data
- [ ] Rollback plan documented

---

## 3. Adding Columns Safely

```sql
-- GOOD: nullable, no lock
ALTER TABLE users ADD COLUMN avatar_url TEXT;

-- GOOD: default value (Postgres 11+ is instant, no table rewrite)
ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;

-- BAD: NOT NULL without default — locks the table and rewrites every row
ALTER TABLE users ADD COLUMN role TEXT NOT NULL;
```

**Rule:** Never add a `NOT NULL` column without a default to an existing table. Add nullable first, backfill, then add the constraint.

---

## 4. Zero-Downtime Index Creation

```sql
-- BAD: blocks writes on large tables
CREATE INDEX idx_users_email ON users (email);

-- GOOD: non-blocking, allows concurrent writes
CREATE INDEX CONCURRENTLY idx_users_email ON users (email);
```

`CONCURRENTLY` cannot run inside a transaction block. Use your migration tool's escape hatch for raw SQL when needed (see ORM sections below).

---

## 5. Zero-Downtime Column Rename (Expand-Contract)

Never rename a column directly in production. Use the three-phase expand-contract pattern:

```
Phase 1 — EXPAND
  Migration: Add new column (nullable or with default).
  App writes to BOTH old and new columns.

Phase 2 — MIGRATE
  Migration: Backfill old rows into new column.
  App reads from NEW, writes to BOTH.
  Verify data consistency.

Phase 3 — CONTRACT
  Deploy: App uses only the new column.
  Migration: Drop old column.
```

```sql
-- Migration 001: add column
ALTER TABLE users ADD COLUMN display_name TEXT;

-- Migration 002: backfill (separate migration)
UPDATE users SET display_name = username WHERE display_name IS NULL;

-- Migration 003: drop old column (after app deploy)
ALTER TABLE users DROP COLUMN username;
```

**Rule:** Always remove all application references to a column before dropping it. Dropping first causes immediate application errors.

---

## 6. Large Data Backfills

Never update all rows in a single transaction on large tables — it locks the table and can run for hours.

```sql
-- BAD: locks table
UPDATE users SET normalized_email = LOWER(email);

-- GOOD: batch with SKIP LOCKED, commit each batch
DO $$
DECLARE
  batch_size INT := 10000;
  rows_updated INT;
BEGIN
  LOOP
    UPDATE users
    SET normalized_email = LOWER(email)
    WHERE id IN (
      SELECT id FROM users
      WHERE normalized_email IS NULL
      LIMIT batch_size
      FOR UPDATE SKIP LOCKED
    );
    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    EXIT WHEN rows_updated = 0;
    COMMIT;
  END LOOP;
END $$;
```

---

## 7. Rollback Strategies

Production rollbacks use new forward migrations, not `DOWN` scripts. Document the rollback migration before applying the original.

| Scenario | Rollback Approach |
|---|---|
| Added nullable column | `ALTER TABLE t DROP COLUMN col` |
| Added index | `DROP INDEX CONCURRENTLY idx` |
| Data backfill | Write inverse transform migration |
| Renamed column (expand-contract) | Stop at Phase 1; revert app code |
| Dropped column | Restore from backup; column data is unrecoverable |

**Rule:** Before dropping any column, verify no backup restore will be needed for that column's data within your retention window.

---

## 8. ORM-Specific Patterns

**Prisma** — use `--create-only` for operations Prisma cannot express (e.g., concurrent indexes):

```bash
npx prisma migrate dev --create-only --name add_email_index
# Edit the generated SQL to add CONCURRENTLY
npx prisma migrate deploy
```

**Drizzle:**

```bash
npx drizzle-kit generate   # generate migration from schema
npx drizzle-kit migrate    # apply migrations
# Never use drizzle-kit push in production
```

**Django** — use `SeparateDatabaseAndState` to decouple model state from DB state when removing columns:

```python
operations = [
    migrations.SeparateDatabaseAndState(
        state_operations=[migrations.RemoveField(model_name="user", name="legacy_field")],
        database_operations=[],  # Drop column in the next migration
    ),
]
```

**golang-migrate** — always create paired `.up.sql` and `.down.sql` files:

```bash
migrate create -ext sql -dir migrations -seq add_user_avatar
```

---

## 9. Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|---|---|---|
| Manual SQL in production | No audit trail, unrepeatable | Always use migration files |
| Editing deployed migrations | Causes environment drift | Create a new migration |
| `NOT NULL` without default on existing table | Locks and rewrites entire table | Add nullable → backfill → add constraint |
| Inline `CREATE INDEX` on large table | Blocks writes during index build | `CREATE INDEX CONCURRENTLY` |
| Schema + data in one migration | Long transactions, hard to rollback | Separate DDL and DML migrations |
| Dropping column before removing code | Application errors on missing column | Remove code, deploy, then drop column |
