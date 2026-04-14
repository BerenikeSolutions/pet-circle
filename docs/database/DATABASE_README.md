# 🗄️ PetCircle Database Documentation - Quick Start

**Status:** ✅ Complete
**Generated:** April 14, 2026
**Database:** Supabase PostgreSQL (iufvqyrwevigkvpcanvk)
**Tables:** 45 | **FKs:** 54+ | **Size:** ~10,500 lines of documentation

---

## 📁 Documentation Files Overview

| File | Size | Purpose | Best For |
|------|------|---------|----------|
| [DATABASE_DOCUMENTATION.md](#database_documentationmd) | 11 KB | Master index & navigation | **Starting here** |
| [DATABASE_SCHEMA.md](#database_schemamd) | 45 KB | Complete technical schema | Column details, types, constraints |
| [DATABASE_RELATIONSHIPS.md](#database_relationshipsmd) | 19 KB | Entity relationships & flows | Understanding connections |
| [DATABASE_ERD.md](#database_erdmd) | 20 KB | Visual diagrams & patterns | Architecture overview |
| [database_schema.json](#database_schemajson) | 178 KB | Raw machine-readable data | Tooling, automation, analysis |
| [db_schema_extractor.py](#db_schema_extractorpy) | - | Schema generation script | Regenerating documentation |

---

## 🚀 Quick Reference

### Three-Layer Model

```
Layer 1: Root Entities
├─ users (24 cols)
└─ pets (15 cols)

Layer 2: Domain Data (Health, Care, Orders, AI)
├─ Health: conditions, medications, diagnostic_tests, weight
├─ Care: reminders, diet, hygiene, preventive_records
├─ Orders: orders, cart_items, products
└─ AI: nudges, insights, traits, preferences

Layer 3: Supporting (Access, Audit, Cache)
├─ Access: dashboard_tokens, dashboard_visits
├─ Audit: message_logs, conflict_flags
└─ Cache: nutrition_cache, weight_cache, etc.
```

### 45 Tables at a Glance

**Core (2):** users, pets

**Health (8):** conditions, condition_medications, condition_monitoring, prescribed_medicines, diagnostic_test_results, weight_history, pet_ai_insights, pet_life_stage_traits

**Preventive (4):** preventive_records, preventive_master, custom_preventive_items, reminders

**Care (3):** diet_items, hygiene_preferences, contacts

**Orders (6):** orders, cart_items, order_recommendations, product_food, product_medicines, product_supplement

**AI/Nudges (5):** nudges, nudge_delivery_log, nudge_engagement, nudge_config, nudge_message_library

**Dashboard (4):** dashboard_tokens, dashboard_visits, deferred_care_plan_pending, conflict_flags

**Documents (1):** documents

**Logging (2):** message_logs, whatsapp_template_configs

**Cache (3):** food_nutrition_cache, nutrition_target_cache, ideal_weight_cache, hygiene_tip_cache

**Other (3):** agent_order_sessions, shown_fun_facts, breed_consequence_library

---

## 📖 Which Document Should I Read?

### "I want to understand the overall structure"
→ **Start with [DATABASE_DOCUMENTATION.md](./DATABASE_DOCUMENTATION.md)**
- Master index with navigation
- Table statistics
- Domain breakdown
- Quick reference table

### "I need to know exact column types and constraints"
→ **[DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)**
- All 45 tables listed
- Every column defined
- Data types, nullability, defaults
- Indexes and constraints

### "I want to understand how tables connect"
→ **[DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md)**
- Foreign key relationships
- Entity hierarchy diagrams
- Data flow patterns
- Query optimization

### "I need a visual diagram"
→ **[DATABASE_ERD.md](./DATABASE_ERD.md)**
- PlantUML ER diagram (copy & render)
- ASCII relationship maps
- Domain clustering
- Join pattern examples

### "I'm building tooling or doing programmatic analysis"
→ **[database_schema.json](./database_schema.json)**
- Machine-readable schema
- All tables, columns, FKs
- Structured for parsing
- Use with jq, Python, etc.

---

## 🔗 Key Relationships (One-Liner)

| Relationship | Meaning |
|--------------|---------|
| `users (1) → (N) pets` | Each user has multiple pets |
| `pets (1) → (N) conditions` | Each pet can have multiple health conditions |
| `pets (1) → (N) preventive_records` | Track preventive care item completion per pet |
| `pets (1) → (N) reminders` | Reminders sent to pet owner |
| `users (1) → (N) orders` | Order history per user |
| `orders (1) → (N) cart_items` | Multiple items in each order |
| `pets (1) → (N) nudges` | AI-generated insights per pet |
| `preventive_master → preventive_records` | Frozen catalog referenced in records |

---

## 💾 Data Domains

### 1️⃣ User & Pet Core
- **Root tables:** users, pets
- **Purpose:** User identity, pet registry
- **Key fields:** user.phone_number (UNIQUE), pet.life_stage_derived

### 2️⃣ Health Management
- **Tables:** conditions, prescribed_medicines, diagnostic_test_results, weight_history
- **Purpose:** Track pet health history
- **Linked to:** pets, users
- **Key pattern:** One-to-many per pet

### 3️⃣ Preventive Care
- **Tables:** preventive_records, preventive_master, custom_preventive_items, reminders
- **Purpose:** Vaccination, checkup, and routine care tracking
- **Key feature:** preventive_master is frozen (read-only catalog)
- **Pattern:** user_id + pet_id scope

### 4️⃣ Daily Care
- **Tables:** diet_items, hygiene_preferences, contacts
- **Purpose:** Nutrition and grooming preferences
- **Pattern:** Pet-scoped preferences

### 5️⃣ Orders & Products
- **Tables:** orders, cart_items, product_food, product_medicines, product_supplement
- **Purpose:** E-commerce workflow
- **Key:** Razorpay payment integration (razorpay_order_id)
- **Related:** order_recommendations for ML

### 6️⃣ AI & Insights
- **Tables:** nudges, nudge_delivery_log, nudge_engagement, pet_ai_insights, pet_life_stage_traits
- **Purpose:** AI-generated health tips and insights
- **Tracking:** Delivery and user engagement logged
- **Scope:** User + pet

### 7️⃣ Dashboard & Access
- **Tables:** dashboard_tokens, dashboard_visits, deferred_care_plan_pending, conflict_flags
- **Purpose:** Secure dashboard access and planning
- **Security:** Token-based (not username/password)
- **Audit:** All visits logged

### 8️⃣ Documents & Uploads
- **Table:** documents
- **Features:** GPT extraction, GCP storage integration, conflict detection
- **Scope:** User + pet

---

## 🔐 Security Model

### User Isolation
```
users.phone_number (UNIQUE)
    ↓
All data scoped to user_id
    ↓
No query should cross user_id boundary
```

### Dashboard Access
```
DASHBOARD_TOKEN (secure random, unique per user)
    ↓
Validates on each request
    ↓
Can be revoked (soft delete)
    ↓
Expires at specified timestamp
```

### Audit Trail
```
message_logs → All WhatsApp messages logged
dashboard_visits → All dashboard access logged
nudge_delivery_log → All nudge deliveries logged
conflict_flags → Conflict resolution tracked
```

---

## ⚡ Common Queries

### Load Pet Profile
```python
pet = session.query(Pet).filter(
    Pet.user_id == user_id,
    Pet.id == pet_id
).options(
    selectinload(Pet.conditions),
    selectinload(Pet.reminders),
    selectinload(Pet.weight_history)
).first()
```

### Get Pending Reminders
```sql
SELECT * FROM reminders
WHERE user_id = ? AND pet_id = ?
  AND is_completed = false
  AND due_date <= CURRENT_DATE
ORDER BY due_date ASC;
```

### Track Health Score
```sql
SELECT COUNT(*) as total_items,
       SUM(CASE WHEN is_completed THEN 1 ELSE 0 END) as completed
FROM preventive_records
WHERE pet_id = ? AND user_id = ?;
```

### List Orders
```sql
SELECT o.*, COUNT(ci.id) as item_count, SUM(ci.price) as total
FROM orders o
LEFT JOIN cart_items ci ON o.id = ci.order_id
WHERE o.user_id = ?
GROUP BY o.id
ORDER BY o.order_date DESC;
```

---

## 📊 Statistics

| Metric | Count |
|--------|-------|
| Total Tables | 45 |
| Total Columns | ~400+ |
| Foreign Keys | 54+ |
| Unique Constraints | 15+ |
| Default Indexes | 50+ |
| JSONB Columns | 20+ (flexible data) |
| UUID Primary Keys | 45 (all tables) |
| Timestamp Fields | ~80+ (audit trail) |

---

## 🏗️ Architecture Principles

### ✅ Applied Patterns
- **User-centric:** All data rooted in users table
- **Pet-scoped:** Most data scoped to user_id + pet_id
- **Referential integrity:** All FKs enforced
- **Audit trail:** Timestamps on all tables
- **Soft deletes:** Revocation without data loss (dashboard_tokens)
- **Frozen catalogs:** preventive_master is read-only
- **JSONB flexibility:** For extensible attributes
- **Connection pooling:** Via Supabase pooler

### ❌ Avoided Patterns
- No in-memory state (DB is source of truth)
- No hardcoded enum values (stored as VARCHAR)
- No circular references
- No denormalization (proper normalization)

---

## 🔧 For Developers

### Common Tasks

**Add a new pet attribute:**
1. Add column to `pets` table (migration)
2. Update `Pet` model in code
3. Document in DATABASE_SCHEMA.md

**Add a health condition type:**
1. Insert into `conditions` table
2. Update `condition_medications` if needed
3. Create `nudges` records if insights required

**Track a new reminder type:**
1. Add to `reminders` table with item_name
2. Or create custom_preventive_items
3. Update reminder_engine.py to handle it

**Launch a product:**
1. Insert into `product_food` / `product_medicines` / `product_supplement`
2. Create `order_recommendations` for matching pets
3. Optionally create `nudges` to notify users

### Regenerate Documentation
```bash
cd backend
python db_schema_extractor.py
```

This will recreate:
- `DATABASE_SCHEMA.md`
- `database_schema.json`

---

## 📅 Maintenance

### Regular Tasks
- ✅ Monitor index usage (check slow queries)
- ✅ Vacuum & analyze (PostgreSQL maintenance)
- ✅ Archive old records if needed
- ✅ Validate constraints (no orphaned FKs)

### Migration Workflow
1. Create `backend/migrations/NNN_description.sql`
2. Test locally with Supabase dev project
3. Deploy via Render (automatic on git push)
4. Verify in production
5. Update DATABASE_SCHEMA.md

---

## 📞 Support & Reference

### Schema Questions
→ [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - Column definitions, types, constraints

### Relationship Questions
→ [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md) - FK relationships, data flows

### Architecture Questions
→ [DATABASE_ERD.md](./DATABASE_ERD.md) - ER diagrams, domain isolation

### Integration Questions
→ [DATABASE_DOCUMENTATION.md](./DATABASE_DOCUMENTATION.md) - Workflows, optimization

### Programmatic Access
→ [database_schema.json](./database_schema.json) - Machine-readable schema

---

## 📝 File Locations

All documentation files are in the project root:
```
pet-circle/
├── DATABASE_DOCUMENTATION.md   ← Master index
├── DATABASE_SCHEMA.md          ← Technical details
├── DATABASE_RELATIONSHIPS.md   ← Connections & flows
├── DATABASE_ERD.md             ← Visual diagrams
├── DATABASE_README.md          ← This file
├── database_schema.json        ← Raw data
└── backend/
    ├── db_schema_extractor.py  ← Generator script
    └── DATABASE_SCHEMA.md      ← Copy
```

---

## ✨ Summary

The PetCircle database is a **well-structured relational model** designed for:
- ✅ User data isolation (security)
- ✅ Pet-centric health tracking
- ✅ Preventive care management
- ✅ E-commerce integration
- ✅ AI insights & nudges
- ✅ Audit and compliance

**Next Steps:**
1. **Start with:** [DATABASE_DOCUMENTATION.md](./DATABASE_DOCUMENTATION.md)
2. **Read:** The relevant domain document (Relationships or Schema)
3. **Reference:** JSON file for programmatic work
4. **Build:** Using established patterns documented here

---

**Generated:** April 14, 2026
**Database:** Supabase PostgreSQL
**Project:** PetCircle Phase 1
**Status:** Ready for Production ✅

