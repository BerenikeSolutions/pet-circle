---
name: postgres-patterns
description: PostgreSQL query optimization, indexing, Row Level Security, connection pooling, JSONB, CTEs, window functions, and maintenance patterns.
---

# PostgreSQL Patterns

Production-grade PostgreSQL patterns for schema design, query performance, and security.

---

## 1. Data Types

Use the most precise type available:

| Use Case | Correct Type | Avoid |
|---|---|---|
| IDs | `bigint` | `int`, random UUID as PK |
| Strings | `text` | `varchar(255)` |
| Timestamps | `timestamptz` | `timestamp` (no timezone) |
| Money | `numeric(10,2)` | `float` (imprecise) |
| Flags | `boolean` | `varchar`, `int` |

**Rule:** Always use `timestamptz`. `timestamp` silently drops timezone information.

---

## 2. Indexing Strategies

| Query Pattern | Index Type | Example |
|---|---|---|
| `WHERE col = value` | B-tree (default) | `CREATE INDEX ON t (col)` |
| `WHERE col > value` | B-tree | `CREATE INDEX ON t (col)` |
| `WHERE a = x AND b > y` | Composite | `CREATE INDEX ON t (a, b)` |
| `WHERE jsonb_col @> '{}'` | GIN | `CREATE INDEX ON t USING gin (col)` |
| Full-text search `@@` | GIN | `CREATE INDEX ON t USING gin (tsvector_col)` |
| Time-series range scans | BRIN | `CREATE INDEX ON t USING brin (created_at)` |

**Composite index rule:** Equality columns first, range columns last.

```sql
-- Works for: WHERE status = 'pending' AND created_at > '2024-01-01'
CREATE INDEX idx ON orders (status, created_at);
```

**Covering index** — avoid table heap lookup for read-heavy queries:

```sql
CREATE INDEX idx ON users (email) INCLUDE (name, created_at);
```

**Partial index** — index only the rows you actually query:

```sql
CREATE INDEX idx ON users (email) WHERE deleted_at IS NULL;
```

**Rule:** Always create indexes `CONCURRENTLY` on existing large tables to avoid write locks.

---

## 3. Row Level Security (RLS)

Wrap `auth.uid()` in a `SELECT` subquery to prevent per-row re-evaluation:

```sql
-- GOOD: evaluated once per query
CREATE POLICY orders_policy ON orders
  USING ((SELECT auth.uid()) = user_id);

-- BAD: re-evaluated for every row
CREATE POLICY orders_policy ON orders
  USING (auth.uid() = user_id);
```

Enable RLS on every table that holds user data:

```sql
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders FORCE ROW LEVEL SECURITY;  -- applies to table owners too
```

**Rule:** Never expose a table with user data without an RLS policy in place.

---

## 4. Connection Pooling

Use PgBouncer or a managed equivalent (Supabase Pooler) in transaction mode for serverless/edge workloads.

```sql
-- Limit max connections at the server level
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET work_mem = '8MB';

-- Kill idle-in-transaction sessions before they accumulate locks
ALTER SYSTEM SET idle_in_transaction_session_timeout = '30s';
ALTER SYSTEM SET statement_timeout = '30s';

SELECT pg_reload_conf();
```

**Rule:** Set `idle_in_transaction_session_timeout` on every production instance. Idle transactions hold locks and block autovacuum.

---

## 5. JSONB Patterns

Use `@>` containment with a GIN index for JSONB queries:

```sql
CREATE INDEX idx ON events USING gin (properties);

-- Efficient containment check
SELECT * FROM events WHERE properties @> '{"event_type": "purchase"}';

-- Extract a field
SELECT properties->>'email' AS email FROM events;

-- Update a nested field without rewriting the whole document
UPDATE users SET metadata = metadata || '{"verified": true}';
```

**Rule:** Never store JSONB columns without a GIN index if you query their contents.

---

## 6. Common Table Expressions and Window Functions

**CTEs** for readable multi-step queries:

```sql
WITH active_orders AS (
  SELECT * FROM orders WHERE status = 'active'
),
order_totals AS (
  SELECT user_id, SUM(amount) AS total FROM active_orders GROUP BY user_id
)
SELECT u.email, ot.total
FROM users u
JOIN order_totals ot ON u.id = ot.user_id
ORDER BY ot.total DESC;
```

**Window functions** for running totals, rankings, and lag/lead comparisons:

```sql
SELECT
  date,
  revenue,
  SUM(revenue) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative,
  LAG(revenue, 1) OVER (ORDER BY date) AS prev_day_revenue
FROM daily_revenue;
```

**Cursor pagination with window** — O(1) vs OFFSET O(n):

```sql
SELECT * FROM products WHERE id > $last_id ORDER BY id LIMIT 20;
```

---

## 7. UPSERT and Queue Patterns

**UPSERT:**

```sql
INSERT INTO settings (user_id, key, value)
VALUES (123, 'theme', 'dark')
ON CONFLICT (user_id, key)
DO UPDATE SET value = EXCLUDED.value;
```

**Queue processing with `SKIP LOCKED`** — prevents multiple workers from claiming the same job:

```sql
UPDATE jobs SET status = 'processing'
WHERE id = (
  SELECT id FROM jobs WHERE status = 'pending'
  ORDER BY created_at LIMIT 1
  FOR UPDATE SKIP LOCKED
) RETURNING *;
```

---

## 8. Vacuum and Analyze

Enable `pg_stat_statements` for query performance monitoring:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY mean_exec_time DESC;

-- Find table bloat (candidates for VACUUM)
SELECT relname, n_dead_tup, last_vacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;
```

Run `ANALYZE` after large data loads to update planner statistics. Run `VACUUM ANALYZE` on tables with high update/delete rates. Configure `autovacuum_vacuum_scale_factor` more aggressively on high-churn tables.

**Rule:** Never disable autovacuum. Monitor `n_dead_tup` — table bloat degrades query performance and index efficiency.

---

## 9. Security Defaults

```sql
-- Remove public schema access on new databases
REVOKE ALL ON SCHEMA public FROM public;

-- Find unindexed foreign keys (common source of slow joins)
SELECT conrelid::regclass, a.attname
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
WHERE c.contype = 'f'
  AND NOT EXISTS (
    SELECT 1 FROM pg_index i
    WHERE i.indrelid = c.conrelid AND a.attnum = ANY(i.indkey)
  );
```

**Rule:** Every foreign key column must have an index. Unindexed FKs cause full table scans on joins and cascading deletes.
