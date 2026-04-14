# 📚 PetCircle Database Documentation

**Generated:** April 14, 2026 | **Status:** ✅ Complete

---

## 🎯 Quick Navigation

**New to this database?** → Start with [DATABASE_README.md](./DATABASE_README.md)

**Looking for something specific?** → Check the table below

**Need to navigate everything?** → Open [DATABASE_INDEX.md](./DATABASE_INDEX.md)

---

## 📋 Files in This Folder

### 1. **[DATABASE_README.md](./DATABASE_README.md)** ⭐ **START HERE**
**Quick reference guide for the entire database**
- Size: 12 KB
- Perfect for: First-time readers, quick lookups
- Contains: 3-layer overview, common queries, security model, navigation guide

### 2. **[DATABASE_INDEX.md](./DATABASE_INDEX.md)**
**Complete navigation index and learning paths**
- Size: 14 KB
- Perfect for: Finding specific documents, learning paths by role
- Contains: Navigation matrix, reading recommendations, quick reference

### 3. **[DATABASE_DOCUMENTATION.md](./DATABASE_DOCUMENTATION.md)**
**Master index with comprehensive statistics**
- Size: 11 KB
- Perfect for: Understanding architecture, domain breakdown
- Contains: Table statistics, domain organization, scalability strategy

### 4. **[DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md)**
**Entity relationships and data flow patterns**
- Size: 19 KB
- Perfect for: Understanding connections, data flows, optimization
- Contains: FK relationships, workflows, query patterns, security model

### 5. **[DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)**
**Complete technical schema documentation**
- Size: 45 KB
- Perfect for: Finding exact column types, constraints, definitions
- Contains: All 45 tables with columns, types, nullability, defaults, indexes

### 6. **[DATABASE_ERD.md](./DATABASE_ERD.md)**
**Visual diagrams and relationship maps**
- Size: 20 KB
- Perfect for: Visual overview, architecture understanding
- Contains: PlantUML ER diagram, ASCII maps, join patterns, domain clustering

### 7. **[database_schema.json](./database_schema.json)**
**Machine-readable schema data**
- Size: 178 KB
- Perfect for: Programmatic analysis, tooling integration
- Contains: All tables, columns, constraints in JSON format

### 8. **[DATABASE_GENERATION_SUMMARY.txt](./DATABASE_GENERATION_SUMMARY.txt)**
**Text-based summary of generation**
- Size: 13 KB
- Perfect for: Quick overview without markdown rendering
- Contains: File descriptions, statistics, next steps

---

## 🗺️ Navigation by Role

| Your Role | Read These Files | Time |
|-----------|------------------|------|
| **Backend Developer** | DATABASE_README.md → DATABASE_SCHEMA.md → DATABASE_RELATIONSHIPS.md | ~45 min |
| **Database Engineer** | DATABASE_RELATIONSHIPS.md → DATABASE_SCHEMA.md → DATABASE_ERD.md | ~60 min |
| **Solution Architect** | DATABASE_ERD.md → DATABASE_RELATIONSHIPS.md (Architecture section) | ~35 min |
| **DevOps/Automation** | DATABASE_README.md → database_schema.json | ~20 min |
| **New Team Member** | DATABASE_README.md → DATABASE_INDEX.md → Specific docs | ~25 min |

---

## 🔍 What Are You Looking For?

| I want to... | Read this |
|--------------|-----------|
| Understand the basic structure | DATABASE_README.md |
| Find a specific table | DATABASE_SCHEMA.md (search) |
| See how tables connect | DATABASE_RELATIONSHIPS.md |
| Get a visual overview | DATABASE_ERD.md |
| Understand data flows | DATABASE_RELATIONSHIPS.md |
| Optimize a query | DATABASE_RELATIONSHIPS.md (Query Optimization) |
| Plan a migration | DATABASE_RELATIONSHIPS.md (Constraints section) |
| Find all FK relationships | DATABASE_SCHEMA.md (Foreign Keys sections) |
| Access schema programmatically | database_schema.json + jq/Python |
| Get a quick text overview | DATABASE_GENERATION_SUMMARY.txt |

---

## 📊 Quick Stats

| Metric | Count |
|--------|-------|
| Tables Documented | 45 / 45 (100%) |
| Columns Defined | 400+ |
| Foreign Keys Mapped | 54+ |
| Primary Keys | 45 / 45 |
| Unique Constraints | 15+ |
| Indexes Listed | 50+ |
| **Total Documentation** | **~10,700 lines** |
| **Total Size** | **~285 KB** |

---

## 📚 Documentation Overview

### Core Entities (2 tables)
- **users** — User identity (phone-based)
- **pets** — Pet registry

### Health & Medical (8 tables)
- conditions, condition_medications, condition_monitoring
- prescribed_medicines, diagnostic_test_results, weight_history
- pet_ai_insights, pet_life_stage_traits

### Preventive Care (4 tables)
- preventive_records, preventive_master, custom_preventive_items, reminders

### Care Management (3 tables)
- diet_items, hygiene_preferences, contacts

### Orders & Commerce (6 tables)
- orders, cart_items, order_recommendations, product_food, product_medicines, product_supplement

### AI & Insights (5 tables)
- nudges, nudge_delivery_log, nudge_engagement, nudge_config, nudge_message_library

### Dashboard & Access (4 tables)
- dashboard_tokens, dashboard_visits, deferred_care_plan_pending, conflict_flags

### Documents (1 table)
- documents

### Logging & Config (2 tables)
- message_logs, whatsapp_template_configs

### Caching (4 tables)
- food_nutrition_cache, nutrition_target_cache, ideal_weight_cache, hygiene_tip_cache

### Workflow & Other (6 tables)
- agent_order_sessions, shown_fun_facts, breed_consequence_library, archives

---

## 🚀 Getting Started

### Step 1: Choose Your Entry Point
Pick **one** of the starting files based on your role:

```
Backend Developer?        → DATABASE_SCHEMA.md
Architect?               → DATABASE_ERD.md
DBA?                     → DATABASE_RELATIONSHIPS.md
First-time reader?       → DATABASE_README.md
```

### Step 2: Navigate Using Cross-References
- All documents link to each other
- Use [DATABASE_INDEX.md](./DATABASE_INDEX.md) as a master guide
- Search for specific content using Ctrl+F

### Step 3: Deep Dive
- Review specific domain sections
- Check query patterns
- Understand security model
- Study data flows

### Step 4: Reference During Development
- Bookmark the files you use most
- Use DATABASE_SCHEMA.md for quick lookups
- Reference query patterns when building features

---

## 🔄 Regenerating Documentation

When your database schema changes, regenerate all documentation:

```bash
cd backend
python db_schema_extractor.py
```

This will:
- Connect to Supabase PostgreSQL
- Extract the current schema
- Regenerate all files in this folder
- Update JSON schema data

**Time to regenerate:** ~5 seconds

---

## 📁 Folder Structure

```
pet-circle/
├── docs/
│   └── database/                           ← You are here
│       ├── README.md                       ← This file
│       ├── DATABASE_README.md              ← Start here
│       ├── DATABASE_INDEX.md               ← Navigation
│       ├── DATABASE_DOCUMENTATION.md       ← Master index
│       ├── DATABASE_RELATIONSHIPS.md       ← Connections
│       ├── DATABASE_SCHEMA.md              ← Technical details
│       ├── DATABASE_ERD.md                 ← Visual diagrams
│       ├── database_schema.json            ← Machine-readable
│       └── DATABASE_GENERATION_SUMMARY.txt ← Text overview
│
└── backend/
    ├── db_schema_extractor.py              ← Generator script
    ├── DATABASE_SCHEMA.md                  ← Copy (reference)
    └── database_schema.json                ← Copy (reference)
```

---

## 🎯 Quick Reference: Top 10 Tables

| Table | Columns | Purpose | FK Count |
|-------|---------|---------|----------|
| **users** | 24 | User identity | 2 |
| **pets** | 15 | Pet registry | 1 |
| **conditions** | 14 | Health conditions | 2 |
| **orders** | 12 | Purchase orders | 2 |
| **reminders** | 18 | Care reminders | 2 |
| **preventive_records** | 11 | Preventive tracking | 3 |
| **nudges** | 21 | Health insights | 1 |
| **documents** | 17 | Uploads & extraction | 2 |
| **prescribed_medicines** | 13 | Medications | 2 |
| **diet_items** | 14 | Nutrition plans | 1 |

---

## 🔐 Security Highlights

✅ **User Isolation**
- All data scoped to user_id
- No cross-user data leakage

✅ **Access Control**
- Dashboard tokens (secure random)
- Token-based access (not username/password)
- Revocable tokens (soft delete)

✅ **Audit Trail**
- message_logs (all WhatsApp messages)
- dashboard_visits (access logging)
- conflict_flags (resolution tracking)

✅ **Data Integrity**
- Foreign keys enforced
- Unique constraints on critical fields
- Proper normalization

---

## 💡 Pro Tips

1. **Bookmark** DATABASE_README.md for quick access
2. **Search** DATABASE_SCHEMA.md for column names
3. **Reference** DATABASE_RELATIONSHIPS.md when building queries
4. **Use** database_schema.json with `jq` for analysis
5. **Regenerate** after schema changes using the script

---

## 📞 Support

**Can't find what you're looking for?**

1. Check [DATABASE_INDEX.md](./DATABASE_INDEX.md) - Has complete navigation matrix
2. Search [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - For specific tables/columns
3. Review [DATABASE_RELATIONSHIPS.md](./DATABASE_RELATIONSHIPS.md) - For connections
4. Examine [DATABASE_ERD.md](./DATABASE_ERD.md) - For visual overview

---

## ✨ File Summary

| File | Size | Lines | Purpose |
|------|------|-------|---------|
| DATABASE_README.md | 12 KB | 382 | Quick start |
| DATABASE_INDEX.md | 14 KB | 455 | Navigation |
| DATABASE_DOCUMENTATION.md | 11 KB | 335 | Master index |
| DATABASE_RELATIONSHIPS.md | 19 KB | 670 | Connections |
| DATABASE_SCHEMA.md | 45 KB | 1,807 | Technical |
| DATABASE_ERD.md | 20 KB | 837 | Visual |
| database_schema.json | 178 KB | 5,906 | Data |
| DATABASE_GENERATION_SUMMARY.txt | 13 KB | 370 | Summary |
| **TOTAL** | **~310 KB** | **~10,700** | **All docs** |

---

## 🎓 Learning Path

```
Start Here
    ↓
DATABASE_README.md (Overview)
    ↓
[Pick based on your role]
    ├─ Developers       → DATABASE_SCHEMA.md
    ├─ DBAs             → DATABASE_RELATIONSHIPS.md
    ├─ Architects       → DATABASE_ERD.md
    └─ Automation       → database_schema.json
    ↓
Reference as Needed During Development
    ↓
[Bookmark your most-used files]
```

---

## 📝 Maintenance

These files are:
- ✅ Auto-generated (from live Supabase database)
- ✅ Regeneratable (script included in backend/)
- ✅ Version controlled (tracked in git)
- ✅ Up-to-date (reflect current schema)
- ✅ Shareable (no credentials included)

**Regenerate whenever your schema changes!**

---

## 📋 Checklist for Teams

- ✅ Copy this folder to your docs
- ✅ Share DATABASE_README.md with the team
- ✅ Bookmark docs/database/ for quick access
- ✅ Review role-specific documents
- ✅ Update when schema changes

---

## 🎉 Summary

You now have **comprehensive, organized database documentation**:

✅ **8 files** (~310 KB)
✅ **10,700+ lines** of content
✅ **45 tables** (100% documented)
✅ **Multiple perspectives** (different views for different roles)
✅ **Machine-readable** (JSON included)
✅ **Regeneratable** (script provided)

All located in: **docs/database/**

**Start reading: [DATABASE_README.md](./DATABASE_README.md)**

---

**Generated:** April 14, 2026
**Database:** Supabase PostgreSQL (iufvqyrwevigkvpcanvk)
**Project:** PetCircle Phase 1
**Status:** ✅ COMPLETE & ORGANIZED
