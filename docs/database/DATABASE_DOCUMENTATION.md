# PetCircle Database Documentation Index

**Last Updated:** April 14, 2026
**Database:** Supabase PostgreSQL (iufvqyrwevigkvpcanvk)
**Tables:** 45
**Status:** Production

---

## 📋 Documentation Files

### 1. [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)
**Complete technical schema documentation**

Contains detailed information for all 45 tables:
- Column definitions (name, type, nullable, default)
- Primary keys
- Foreign keys
- Unique constraints
- Indexes

**Use this for:** Understanding exact column types, constraints, and storage definitions

**Size:** ~45 KB | **Sections:** 45 table definitions

---

### 2. [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md)
**Entity relationships and data flow patterns**

High-level documentation including:
- Entity relationship diagrams (text-based)
- Foreign key relationships (visual hierarchy)
- Data flow workflows
- Domain architecture
- Query optimization patterns
- Security model
- Scalability considerations

**Use this for:** Understanding how tables connect, data flows, and architectural patterns

**Size:** ~19 KB | **Sections:** 8 domains, 5 data flows

---

### 3. [database_schema.json](./database_schema.json)
**Raw machine-readable schema data**

JSON format containing:
- All tables with columns, types, and constraints
- Foreign key definitions
- Unique constraints
- Index information

**Use this for:** 
- Automated tooling / schema analysis
- IDE schema generation
- Database documentation generators
- Programmatic schema validation

**Size:** ~50 KB | **Format:** JSON

---

## 🎯 Quick Reference

### Database Statistics

| Metric | Count |
|--------|-------|
| Total Tables | 45 |
| Total Foreign Keys | ~54 |
| Tables with PKs | 45 (all) |
| Tables with FKs | ~35 |
| Unique Constraints | ~15 |
| Archive Tables | 2 |

### Tables by Domain

| Domain | Count | Tables |
|--------|-------|--------|
| **User & Pet Core** | 2 | users, pets |
| **Health & Medical** | 8 | conditions, prescribed_medicines, diagnostic_test_results, weight_history, condition_medications, condition_monitoring, pet_life_stage_traits, pet_ai_insights |
| **Preventive Care** | 4 | preventive_records, preventive_master, custom_preventive_items, reminders |
| **Nutrition & Diet** | 5 | diet_items, product_food, food_nutrition_cache, nutrition_target_cache, ideal_weight_cache |
| **Hygiene & Grooming** | 3 | hygiene_preferences, hygiene_tip_cache, contacts |
| **Orders & Commerce** | 6 | orders, cart_items, order_recommendations, product_medicines, product_supplement, agent_order_sessions |
| **AI & Insights** | 5 | nudges, nudge_delivery_log, nudge_engagement, nudge_config, nudge_message_library |
| **Dashboard & Access** | 4 | dashboard_tokens, dashboard_visits, deferred_care_plan_pending, conflict_flags |
| **Documents & Uploads** | 1 | documents |
| **Messaging & Logs** | 2 | message_logs, whatsapp_template_configs |
| **Other** | 3 | shown_fun_facts, breed_consequence_library, (archive tables) |

---

## 🔗 Core Relationships at a Glance

### Root Entities

```
USERS (24 cols)
├── PETS (15 cols)
│   ├── Health: conditions, prescribed_medicines, diagnostic_test_results, weight_history
│   ├── Care: diet_items, hygiene_preferences, reminders, custom_preventive_items
│   ├── Records: preventive_records
│   ├── Orders: order_recommendations
│   ├── Documents: documents
│   ├── AI: nudges, pet_ai_insights, pet_life_stage_traits, pet_preferences
│   └── Tracking: weight_history, dashboard_visits
│
├── Orders: orders → cart_items → [product_food, product_medicines, product_supplement]
├── Contacts: contacts
├── Dashboard: dashboard_tokens, dashboard_visits
├── Workflow: agent_order_sessions
└── Conflicts: conflict_flags
```

### Key Relationships

| Relationship | Type | Purpose |
|--------------|------|---------|
| users → pets | 1:N | User has multiple pets |
| pets → conditions | 1:N | Pet can have multiple conditions |
| conditions → condition_medications | 1:N | Condition can have multiple medications |
| conditions → condition_monitoring | 1:N | Condition has monitoring parameters |
| pets → preventive_records | 1:N | Track preventive health items |
| preventive_records → preventive_master | N:1 | Reference frozen preventive catalog |
| pets → reminders | 1:N | Reminders for pet care items |
| users → orders | 1:N | User has multiple orders |
| orders → cart_items | 1:N | Order contains multiple items |
| pets → nudges | 1:N | AI insights sent to pet owner |
| users → dashboard_tokens | 1:N | User can have multiple access tokens |
| pets → documents | 1:N | Pet can have uploaded documents |

---

## 📊 Top 10 Most Connected Tables

| Table | Incoming FKs | Outgoing FKs | Total |
|-------|--------------|--------------|-------|
| users | 15 | 2 | 17 |
| pets | 20 | 1 | 21 |
| orders | 2 | 2 | 4 |
| conditions | 2 | 2 | 4 |
| nudges | 2 | 2 | 4 |
| preventive_master | 1 | 0 | 1 |
| preventive_records | 1 | 1 | 2 |
| product_food | 1 | 0 | 1 |
| product_medicines | 1 | 0 | 1 |
| product_supplement | 1 | 0 | 1 |

---

## 🛠️ How to Navigate

### For Understanding Data Structure
1. Start with [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md) - **Section: "Core Entity Relationships"**
2. Review the visual hierarchy diagrams for your domain of interest
3. Consult [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) for exact column details

### For Building Queries
1. Check [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md) - **Section: "Query Optimization Patterns"**
2. Use [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) to verify field names and types
3. Reference Foreign Key Summary for JOIN patterns

### For API Development
1. Review [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md) - **Section: "Data Flow Patterns"**
2. Understand the workflow for your use case
3. Check data validation rules in code (`backend/app/models/`)

### For Database Migrations
1. Check latest schema in [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)
2. Review migration files in `backend/migrations/`
3. Reference [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md) - **Section: "Constraints & Data Integrity"**

### For Troubleshooting
1. Check [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md) - **Section: "Performance Indexes"**
2. Use [database_schema.json](./database_schema.json) for programmatic analysis
3. Review constraint violations in [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md) - **Section: "Constraints & Data Integrity"**

---

## 🔐 Security Highlights

### User Data Protection
- **Unique identifier:** `users.phone_number` (UNIQUE, no personal emails in auth)
- **Secure access:** Dashboard via random `DASHBOARD_TOKEN` (not username/password)
- **Scope isolation:** All data scoped to user_id, preventing cross-user access

### Audit Trail
- **Message logs:** All WhatsApp messages logged in `message_logs`
- **API tracking:** API calls tracked for compliance
- **Timestamps:** All records have `created_at` and `updated_at`

### Data Integrity
- **Foreign keys:** Enforced relationships prevent orphaned data
- **Constraints:** Unique constraints on critical fields
- **Soft deletes:** Dashboard tokens can be revoked without data loss

---

## 📈 Scalability Strategy

### Current Architecture
- Single PostgreSQL database (Supabase)
- Connection pooling (Supabase pooler)
- ~45 tables, estimated 500K-1M rows

### Optimization Layers
1. **Indexing:** Strategic indexes on user_id, pet_id, created_at
2. **Eager loading:** SQLAlchemy selectinload for related entities
3. **Caching:** Separate cache tables for expensive computations

### Future Partitioning (if needed)
- **By user:** If single user has millions of records
- **By time:** Archive old data to separate tables
- **By domain:** Separate database for commerce domain

---

## 🔄 Common Workflows

### Onboarding Flow
```
users → pets → preventive_records (from preventive_master)
           ↓
        reminders (generated from due dates)
```

### Health Tracking Flow
```
Document Upload → DOCUMENTS → GPT Extraction → CONDITION/PREVENTIVE_RECORD
                                                    ↓
                                                NUDGES (AI insights)
                                                    ↓
                                            WhatsApp Messages
```

### Order Flow
```
User Selection → CART_ITEMS → ORDER → RAZORPAY → Payment Status
                                          ↓
                                    ORDER_RECOMMENDATIONS (logging)
```

### Dashboard Access Flow
```
User Request → DASHBOARD_TOKEN (generated) → TOKEN Validation
                                                  ↓
                                            PET Profile Load (selectinload)
                                                  ↓
                                            DASHBOARD_VISITS (logging)
```

---

## 📝 Generation Details

### Script Used
**File:** `backend/db_schema_extractor.py`

**Process:**
1. Connects to Supabase PostgreSQL via `DATABASE_URL`
2. Queries `information_schema` for all tables
3. Extracts columns, types, constraints, indexes
4. Generates markdown documentation
5. Exports raw JSON for tooling

**Last Run:** April 14, 2026, 15:36 UTC

**Command:**
```bash
python backend/db_schema_extractor.py
```

---

## 🔍 Table Lookup Guide

### Health Domain
- **Conditions:** conditions, condition_medications, condition_monitoring
- **Preventive:** preventive_records, preventive_master, custom_preventive_items
- **Tracking:** weight_history, diagnostic_test_results
- **Medications:** prescribed_medicines

### Care Domain
- **Nutrition:** diet_items, product_food, food_nutrition_cache, nutrition_target_cache
- **Hygiene:** hygiene_preferences, hygiene_tip_cache
- **Reminders:** reminders, pet_life_stage_traits

### Order Domain
- **Orders:** orders, cart_items, order_recommendations
- **Products:** product_food, product_medicines, product_supplement
- **Workflow:** agent_order_sessions

### AI Domain
- **Nudges:** nudges, nudge_delivery_log, nudge_engagement
- **Config:** nudge_config, nudge_message_library
- **Insights:** pet_ai_insights, pet_life_stage_traits, pet_preferences

### Access & Audit
- **Dashboard:** dashboard_tokens, dashboard_visits
- **Logging:** message_logs
- **Conflict:** conflict_flags
- **Documents:** documents

---

## 📞 Support

### For Schema Questions
→ Check [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)

### For Relationship Questions
→ Check [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md)

### For Programmatic Access
→ Use [database_schema.json](./database_schema.json)

### For Migration Help
→ Review `backend/migrations/` directory

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-14 | Initial auto-generated schema documentation |

---

**Generated by:** Database Schema Extractor
**Database:** PostgreSQL (Supabase)
**Project:** PetCircle Phase 1
