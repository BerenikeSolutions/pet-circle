# PetCircle Database Relationships & Architecture

**Generated:** Automated Database Analysis
**Database:** Supabase PostgreSQL (iufvqyrwevigkvpcanvk)

---

## Overview

The PetCircle database consists of **45 tables** organized into logical domains:

1. **User & Pet Management** - Core entities (users, pets, contacts)
2. **Preventive Health** - Health tracking (preventive records, conditions, medications)
3. **Care Management** - Daily care (diet items, hygiene preferences, reminders)
4. **Order & Commerce** - Products and orders (cart items, orders, recommendations)
5. **Dashboard & Access** - Access control (dashboard tokens, visits)
6. **AI & Insights** - ML features (nudges, life stage traits, preferences)
7. **Messaging & Logs** - Communication (message logs, WhatsApp templates)
8. **Caching & Performance** - Performance optimization (nutrition, weight caches)

---

## Core Entity Relationships

### 1. User-Pet Hierarchy

```
USERS (24 columns)
├── id (UUID, PK)
├── phone_number (UNIQUE)
├── name, email, address
├── timezone, language
├── onboarding_status
└── consent fields

├─→ PETS (15 columns)
│   ├── id (UUID, PK)
│   ├── user_id (FK → users.id)
│   ├── name, species, breed
│   ├── date_of_birth
│   ├── weight, gender
│   └── life_stage_derived, insights
│
├─→ CONTACTS (12 columns)
│   ├── id (UUID, PK)
│   ├── user_id (FK → users.id)
│   ├── contact_type (vet, groomer, etc.)
│   └── contact details
│
├─→ DASHBOARD_TOKENS (6 columns)
│   ├── id (UUID, PK)
│   ├── user_id (FK → users.id)
│   ├── token (secure random)
│   └── expires_at
│
└─→ AGENT_ORDER_SESSIONS (7 columns)
    ├── id (UUID, PK)
    ├── user_id (FK → users.id)
    ├── messages (JSONB)
    └── collected_data (JSONB)
```

### 2. Pet Health Tracking

```
PETS (id, user_id)
│
├─→ PREVENTIVE_RECORDS (11 columns)
│   ├── id (UUID, PK)
│   ├── user_id (FK)
│   ├── pet_id (FK → pets.id)
│   ├── item_id (preventive item ID)
│   ├── due_date, completion_date
│   └── is_completed, is_skipped
│
├─→ CONDITIONS (14 columns)
│   ├── id (UUID, PK)
│   ├── pet_id (FK → pets.id)
│   ├── user_id (FK → users.id)
│   ├── condition_name, severity
│   └── onset_date, notes
│   │
│   ├─→ CONDITION_MEDICATIONS (13 columns)
│   │   ├── id (UUID, PK)
│   │   ├── condition_id (FK → conditions.id)
│   │   └── medication details
│   │
│   └─→ CONDITION_MONITORING (9 columns)
│       ├── id (UUID, PK)
│       ├── condition_id (FK → conditions.id)
│       └── monitoring parameters
│
├─→ PRESCRIBED_MEDICINES (13 columns)
│   ├── id (UUID, PK)
│   ├── user_id (FK)
│   ├── pet_id (FK → pets.id)
│   ├── medicine_name, dosage
│   └── prescribed_date, expiry_date
│
├─→ DIAGNOSTIC_TEST_RESULTS (13 columns)
│   ├── id (UUID, PK)
│   ├── pet_id (FK → pets.id)
│   ├── user_id (FK)
│   ├── test_name, result_value
│   └── test_date, uploaded_by
│
└─→ WEIGHT_HISTORY (7 columns)
    ├── id (UUID, PK)
    ├── pet_id (FK → pets.id)
    ├── weight (numeric)
    └── recorded_date
```

### 3. Care Management

```
PETS (id, user_id)
│
├─→ DIET_ITEMS (14 columns)
│   ├── id (UUID, PK)
│   ├── user_id (FK)
│   ├── pet_id (FK → pets.id)
│   ├── food_type, quantity
│   ├── frequency, nutritional_info
│   └── is_active, created_at
│
├─→ HYGIENE_PREFERENCES (12 columns)
│   ├── id (UUID, PK)
│   ├── pet_id (FK → pets.id)
│   ├── user_id (FK)
│   ├── grooming_frequency
│   ├── bath_schedule
│   └── grooming_products
│
├─→ CUSTOM_PREVENTIVE_ITEMS (12 columns)
│   ├── id (UUID, PK)
│   ├── pet_id (FK → pets.id)
│   ├── item_name, category
│   ├── frequency, notes
│   └── is_active, created_at
│
├─→ REMINDERS (18 columns)
│   ├── id (UUID, PK)
│   ├── pet_id (FK)
│   ├── user_id (FK)
│   ├── reminder_type, item_name
│   ├── due_date, next_due_date
│   ├── is_completed, status
│   └── reminder_stage (T-7, Due, D+3, Overdue)
│
└─→ PET_PREFERENCES (8 columns)
    ├── id (UUID, PK)
    ├── pet_id (FK → pets.id)
    ├── preference_key, preference_value
    └── created_at
```

### 4. Order & Commerce

```
USERS (id)
│
├─→ ORDERS (12 columns)
│   ├── id (UUID, PK)
│   ├── user_id (FK → users.id)
│   ├── order_date, expected_delivery
│   ├── total_amount, payment_status
│   ├── razorpay_order_id
│   └── status (pending, confirmed, delivered)
│   │
│   └─→ CART_ITEMS (13 columns)
│       ├── id (UUID, PK)
│       ├── order_id (FK → orders.id)
│       ├── product_id, product_type
│       ├── quantity, price
│       └── created_at
│
├─→ PETS (id)
│   │
│   └─→ ORDER_RECOMMENDATIONS (10 columns)
│       ├── id (UUID, PK)
│       ├── pet_id (FK → pets.id)
│       ├── user_id (FK)
│       ├── product_id, product_type
│       ├── recommendation_reason
│       └── is_purchased
│
└─→ PRODUCT CATALOG (3 tables)
    ├── PRODUCT_FOOD (19 columns)
    │   ├── id (UUID, PK)
    │   ├── name, brand, category
    │   ├── price, ingredients
    │   └── suitable_breeds, health_conditions
    │
    ├── PRODUCT_SUPPLEMENT (19 columns)
    │   ├── id (UUID, PK)
    │   ├── name, type, dosage
    │   ├── price, benefits
    │   └── suitable_ages, conditions
    │
    └── PRODUCT_MEDICINES (21 columns)
        ├── id (UUID, PK)
        ├── name, active_ingredient, dosage
        ├── price, condition_type
        └── prescription_required, side_effects
```

### 5. AI & Insights

```
PETS (id, user_id)
│
├─→ PET_AI_INSIGHTS (5 columns)
│   ├── id (UUID, PK)
│   ├── pet_id (FK → pets.id)
│   ├── insights (JSONB)
│   └── generated_at
│
├─→ PET_LIFE_STAGE_TRAITS (7 columns)
│   ├── id (UUID, PK)
│   ├── pet_id (FK → pets.id)
│   ├── breed, life_stage
│   ├── traits (JSONB - color, text)
│   └── created_at
│
├─→ NUDGES (21 columns)
│   ├── id (UUID, PK)
│   ├── pet_id (FK → pets.id)
│   ├── user_id (FK)
│   ├── nudge_type (health, nutrition, etc.)
│   ├── level (0, 1, 2)
│   ├── priority, content
│   ├── scheduled_at, delivered_at
│   └── engagement_status
│   │
│   └─→ NUDGE_DELIVERY_LOG (10 columns)
│       ├── id (UUID, PK)
│       ├── nudge_id (FK → nudges.id)
│       ├── pet_id (FK)
│       ├── user_id (FK)
│       ├── delivery_status
│       └── delivered_at
│
└─→ NUDGE_ENGAGEMENT (7 columns)
    ├── id (UUID, PK)
    ├── nudge_id (FK → nudges.id)
    ├── pet_id (FK)
    ├── user_id (FK)
    ├── engagement_type (open, click, action)
    └── engaged_at
```

### 6. Document Management

```
PETS (id, user_id)
│
└─→ DOCUMENTS (17 columns)
    ├── id (UUID, PK)
    ├── pet_id (FK → pets.id)
    ├── user_id (FK → users.id)
    ├── document_type (prescription, report, etc.)
    ├── filename, file_size
    ├── storage_path
    ├── gcp_bucket_path
    ├── extraction_status
    ├── extracted_data (JSONB)
    └── uploaded_at
```

### 7. Conflict Resolution

```
USERS (id)
│
└─→ CONFLICT_FLAGS (5 columns)
    ├── id (UUID, PK)
    ├── user_id (FK → users.id)
    ├── conflict_type, details (JSONB)
    ├── resolution_status
    └── expires_at (5-day auto-expiry)
```

### 8. Deferred Care Planning

```
USERS (id)
│
├─→ DEFERRED_CARE_PLAN_PENDING (7 columns)
│   ├── id (UUID, PK)
│   ├── user_id (FK)
│   ├── pet_id (FK → pets.id)
│   ├── care_plan (JSONB)
│   └── pending_items
│
└─→ DASHBOARD_VISITS (5 columns)
    ├── id (UUID, PK)
    ├── user_id (FK → users.id)
    ├── pet_id (FK → pets.id)
    ├── visit_timestamp
    └── user_agent
```

---

## Foreign Key Summary

| Source Table | FK Column | Target Table | Notes |
|--------------|-----------|--------------|-------|
| agent_order_sessions | user_id | users.id | Agentic order flow session |
| cart_items | order_id | orders.id | Shopping cart items |
| condition_medications | condition_id | conditions.id | Medications for conditions |
| condition_monitoring | condition_id | conditions.id | Monitoring for conditions |
| conditions | pet_id | pets.id | Pet health conditions |
| conditions | user_id | users.id | User owns condition record |
| conflict_flags | user_id | users.id | Conflict resolution |
| contacts | user_id | users.id | Contact management |
| custom_preventive_items | pet_id | pets.id | Custom preventive tracking |
| dashboard_tokens | user_id | users.id | Secure token access |
| dashboard_visits | user_id | users.id | Dashboard analytics |
| dashboard_visits | pet_id | pets.id | Per-pet dashboard views |
| deferred_care_plan_pending | user_id | users.id | Care plan tracking |
| deferred_care_plan_pending | pet_id | pets.id | Pet care plan |
| diagnostic_test_results | pet_id | pets.id | Test results |
| diagnostic_test_results | user_id | users.id | User owns test |
| diet_items | pet_id | pets.id | Pet dietary info |
| documents | pet_id | pets.id | Pet documents |
| documents | user_id | users.id | User owns document |
| hygiene_preferences | pet_id | pets.id | Pet grooming preferences |
| nudge_delivery_log | nudge_id | nudges.id | Nudge delivery tracking |
| nudge_delivery_log | pet_id | pets.id | Pet nudges |
| nudge_delivery_log | user_id | users.id | User nudges |
| nudge_engagement | nudge_id | nudges.id | User engagement with nudges |
| nudge_engagement | pet_id | pets.id | Pet nudge engagement |
| nudge_engagement | user_id | users.id | User nudge engagement |
| nudges | pet_id | pets.id | Pet-specific nudges |
| nudges | user_id | users.id | User nudges |
| order_recommendations | pet_id | pets.id | Product recommendations |
| order_recommendations | user_id | users.id | User recommendations |
| orders | user_id | users.id | User orders |
| orders | pet_id | pets.id | Pet-related order (optional) |
| pet_ai_insights | pet_id | pets.id | AI insights |
| pet_life_stage_traits | pet_id | pets.id | Life stage traits |
| pet_preferences | pet_id | pets.id | Pet preferences |
| pets | user_id | users.id | User owns pets |
| prescribed_medicines | pet_id | pets.id | Pet medications |
| prescribed_medicines | user_id | users.id | User prescriptions |
| preventive_records | pet_id | pets.id | Pet preventive history |
| preventive_records | user_id | users.id | User preventive records |
| preventive_records | preventive_item_id | preventive_master.id | Preventive item definition |
| reminders | pet_id | pets.id | Pet reminders |
| reminders | user_id | users.id | User reminders |
| shown_fun_facts | user_id | users.id | Seen fun facts |
| weight_history | pet_id | pets.id | Pet weight tracking |

---

## Domain Architecture

### User & Pet Core (Root Tables)

```
users (PK: id)
  - phone_number (UNIQUE)
  - name, email
  - onboarding_status
  - consent fields

pets (PK: id, FK: user_id)
  - name, species, breed
  - date_of_birth
  - weight, gender
  - life_stage_derived (computed)
```

### Health Domain

```
preventive_records → preventive_master
conditions → condition_medications, condition_monitoring
prescribed_medicines
diagnostic_test_results
weight_history
```

### Care Domain

```
diet_items
hygiene_preferences
reminders
custom_preventive_items
```

### Order Domain

```
orders → cart_items → product_food, product_medicines, product_supplement
order_recommendations
```

### AI/Insights Domain

```
nudges → nudge_delivery_log, nudge_engagement
pet_ai_insights
pet_life_stage_traits
pet_preferences
```

### Supporting Tables

```
contacts (user-scoped)
dashboard_tokens (user-scoped, secure)
documents (pet-scoped, with GCP storage)
conflict_flags (user-scoped, 5-day expiry)
deferred_care_plan_pending (user + pet scoped)
message_logs (WhatsApp audit)
shown_fun_facts (user-scoped)
dashboard_visits (analytics)
agent_order_sessions (agentic flow state)
```

### Caches (Performance)

```
food_nutrition_cache
nutrition_target_cache
ideal_weight_cache
hygiene_tip_cache
```

---

## Data Flow Patterns

### 1. Preventive Health Workflow

```
USER creates PET
  ↓
PREVENTIVE_MASTER (frozen catalog) → PREVENTIVE_RECORDS (user's tracking)
  ↓
REMINDERS (generated from due dates)
  ↓
WhatsApp messages (via reminder_engine)
  ↓
User marks REMINDER as done → updates PREVENTIVE_RECORD
```

### 2. Health Condition Workflow

```
User reports CONDITION via WhatsApp / Dashboard
  ↓
CONDITION created (linked to PET, USER)
  ↓
CONDITION_MEDICATIONS (add prescribed meds)
CONDITION_MONITORING (add monitoring params)
  ↓
AI generates NUDGES (health insights)
  ↓
NUDGE_DELIVERY_LOG tracks delivery
NUDGE_ENGAGEMENT tracks user interaction
```

### 3. Order Workflow

```
User browses PRODUCT_FOOD / PRODUCT_MEDICINES
  ↓
AGENTIC_ORDER_SESSION (LLM orchestration)
  ↓
CART_ITEMS added to ORDER
  ↓
Payment via Razorpay (razorpay_order_id stored)
  ↓
ORDER_RECOMMENDATIONS logged (for future MLOps)
  ↓
Dashboard shows ORDER status
```

### 4. Document Upload Workflow

```
User uploads document (WhatsApp / Dashboard)
  ↓
DOCUMENTS created (storage_path, gcp_bucket_path)
  ↓
GPT extraction runs (extracted_data JSONB)
  ↓
Conflict detection (dates diverge → CONFLICT_FLAGS)
  ↓
User resolves conflict or auto-expires in 5 days
```

### 5. Dashboard Access Workflow

```
User requests dashboard link (WhatsApp)
  ↓
DASHBOARD_TOKEN generated (secure random, unique)
  ↓
Token validates on each dashboard request
  ↓
DASHBOARD_VISITS logged (analytics)
  ↓
Token can be revoked (soft delete)
```

---

## Query Optimization Patterns

### 1. Pet Profile Load (Dashboard Overview)

**Tables involved:** pets, weight_history, preventive_records, conditions, reminders, diet_items, hygiene_preferences

**Optimization:** Use `selectinload` in SQLAlchemy to eager-load related entities

```python
from sqlalchemy.orm import selectinload

pet = session.query(Pet) \
    .filter(Pet.id == pet_id) \
    .options(
        selectinload(Pet.conditions),
        selectinload(Pet.reminders),
        selectinload(Pet.prescribed_medicines)
    ) \
    .first()
```

### 2. User Nudges (Health Insights)

**Tables involved:** nudges, nudge_delivery_log, nudge_engagement, pets, users

**Query pattern:**
```sql
SELECT nudges.* FROM nudges
LEFT JOIN nudge_delivery_log ON nudges.id = nudge_delivery_log.nudge_id
LEFT JOIN nudge_engagement ON nudges.id = nudge_engagement.nudge_id
WHERE nudges.user_id = %s
  AND nudges.scheduled_at <= NOW()
  AND nudges.delivered_at IS NULL
ORDER BY nudges.priority DESC, nudges.scheduled_at ASC;
```

### 3. Preventive Health Dashboard (Health Tab)

**Tables involved:** preventive_records, preventive_master, reminders, pets

**Query pattern:**
```sql
SELECT
    pm.category,
    COUNT(*) as total_items,
    SUM(CASE WHEN pr.is_completed THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN r.is_completed THEN 1 ELSE 0 END) as on_track
FROM preventive_records pr
JOIN preventive_master pm ON pr.preventive_item_id = pm.id
LEFT JOIN reminders r ON r.item_name = pm.item_name AND r.pet_id = pr.pet_id
WHERE pr.pet_id = %s
GROUP BY pm.category;
```

---

## Constraints & Data Integrity

### Primary Key Constraints
- All tables use **UUID PKs** (`gen_random_uuid()` default)
- Ensures global uniqueness, ideal for distributed systems

### Foreign Key Constraints
- All FKs are explicitly defined in schema
- Cascading deletes configured where appropriate
- Prevents orphaned records

### Unique Constraints
- `phone_number` in users (UNIQUE)
- `uq_agent_order_session_user` in agent_order_sessions (per-user singleton)
- Prevents duplicate entries

### Default Values
- `created_at`, `updated_at` timestamps default to `now()`
- Boolean fields default to `false`
- JSONB fields default to `{}` or `[]`

### Check Constraints (implicit)
- Enums enforced at application layer (status, type fields)

---

## Archival Strategy

**Old archived tables (soft-deleted):**
- `preventive_master_archive_037`
- `preventive_records_archive_037`

These store historical versions during migrations and should not be used for new queries.

---

## Performance Indexes

**Key indexes created (Migration 017):**
- Index on `user_id` across major tables (users → pets, reminders, orders, nudges, etc.)
- Index on `pet_id` for pet-related queries
- Index on `created_at` for time-based queries (dashboard, analytics)
- Index on `status` fields for filtering

---

## Security Model

1. **Phone-based identity:** Users identified by `phone_number` (UNIQUE, secure)
2. **Token-based dashboard access:** `DASHBOARD_TOKEN` (secure random, revocable)
3. **User-scoped data:** All pet, order, reminder, document data scoped to user_id
4. **Admin audit logs:** `message_logs` for WhatsApp and API call tracking
5. **Soft deletes:** Dashboard tokens can be revoked without deleting history

---

## Scalability Considerations

### Current: Monolithic Relational Database
- 45 tables, ~500K rows (estimated)
- PostgreSQL on Supabase
- Connection pooling via Supabase

### Future: Partitioning Strategy
- **By user_id:** If single user has millions of records
- **By time:** Archive old records to separate tables (e.g., preventive_records_archive_037)
- **By domain:** Separate DB for commerce (orders, products) if needed

### Current Bottlenecks (None Critical)
- Full-table scans on `nudges` if not filtered by user_id
- JOIN on `preventive_master` if not indexed on `id`

**Solution:** Ensure all queries filter by user_id or pet_id before bulk operations.

---

## Migration & Versioning

**Migrations tracked in:** `backend/migrations/`

**Latest migration:** 055_drop_essential_care_column.sql

**Workflow:**
1. Create new migration file (e.g., `056_add_new_column.sql`)
2. Test locally with Supabase dev project
3. Deploy to production via Render (automatic on git push)
4. Rollback available for non-breaking changes

---

## Summary

The PetCircle database is a **well-structured relational model** with:
- ✅ Clear user-pet hierarchy
- ✅ Domain-driven organization (health, orders, AI)
- ✅ Proper foreign key relationships
- ✅ Scalable indexing strategy
- ✅ Audit trails and conflict resolution
- ✅ Performance caching layers

All tables are **source-of-truth**, no in-memory state, and every data mutation is transactional.
