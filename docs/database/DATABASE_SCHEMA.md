# PetCircle Supabase Database Schema

**Database:** PostgreSQL (Supabase)
**Project:** iufvqyrwevigkvpcanvk
**Generated:** Automated Schema Documentation

---

## Table of Contents

- [agent_order_sessions](#agent_order_sessions)
- [breed_consequence_library](#breed_consequence_library)
- [cart_items](#cart_items)
- [condition_medications](#condition_medications)
- [condition_monitoring](#condition_monitoring)
- [conditions](#conditions)
- [conflict_flags](#conflict_flags)
- [contacts](#contacts)
- [custom_preventive_items](#custom_preventive_items)
- [dashboard_tokens](#dashboard_tokens)
- [dashboard_visits](#dashboard_visits)
- [deferred_care_plan_pending](#deferred_care_plan_pending)
- [diagnostic_test_results](#diagnostic_test_results)
- [diet_items](#diet_items)
- [documents](#documents)
- [food_nutrition_cache](#food_nutrition_cache)
- [hygiene_preferences](#hygiene_preferences)
- [hygiene_tip_cache](#hygiene_tip_cache)
- [ideal_weight_cache](#ideal_weight_cache)
- [message_logs](#message_logs)
- [nudge_config](#nudge_config)
- [nudge_delivery_log](#nudge_delivery_log)
- [nudge_engagement](#nudge_engagement)
- [nudge_message_library](#nudge_message_library)
- [nudges](#nudges)
- [nutrition_target_cache](#nutrition_target_cache)
- [order_recommendations](#order_recommendations)
- [orders](#orders)
- [pet_ai_insights](#pet_ai_insights)
- [pet_life_stage_traits](#pet_life_stage_traits)
- [pet_preferences](#pet_preferences)
- [pets](#pets)
- [prescribed_medicines](#prescribed_medicines)
- [preventive_master](#preventive_master)
- [preventive_master_archive_037](#preventive_master_archive_037)
- [preventive_records](#preventive_records)
- [preventive_records_archive_037](#preventive_records_archive_037)
- [product_food](#product_food)
- [product_medicines](#product_medicines)
- [product_supplement](#product_supplement)
- [reminders](#reminders)
- [shown_fun_facts](#shown_fun_facts)
- [users](#users)
- [weight_history](#weight_history)
- [whatsapp_template_configs](#whatsapp_template_configs)

---

## agent_order_sessions

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| user_id | uuid | No | - |  |
| messages | jsonb | No | '[]'::jsonb |  |
| collected_data | jsonb | No | '{}'::jsonb |  |
| is_complete | boolean | No | false |  |
| created_at | timestamp with time zone | No | now() |  |
| updated_at | timestamp with time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **user_id** → users.id

### Indexes

- agent_order_sessions_pkey
- uq_agent_order_session_user
- idx_agent_order_session_user_id

---

## breed_consequence_library

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| breed | character varying(100) | No | - |  |
| category | character varying(50) | No | - |  |
| consequence_text | text | No | - |  |
| created_at | timestamp with time zone | No | now() |  |

### Primary Key

```
id
```

### Unique Constraints

- **breed_consequence_library_breed_category_key** on (breed, category)

### Indexes

- breed_consequence_library_pkey
- breed_consequence_library_breed_category_key
- idx_breed_consequence_breed_category

---

## cart_items

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| product_id | character varying(100) | No | - |  |
| icon | character varying(50) | Yes | - |  |
| name | character varying(200) | No | - |  |
| sub | character varying(200) | Yes | - |  |
| price | integer(32,0) | No | - |  |
| tag | character varying(100) | Yes | - |  |
| tag_color | character varying(50) | Yes | - |  |
| in_cart | boolean | No | false |  |
| quantity | integer(32,0) | No | 1 |  |
| created_at | timestamp without time zone | No | now() |  |
| cart_expires_at | timestamp with time zone | Yes | (now() + '72:00:00'::interval) |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Unique Constraints

- **uq_cart_item** on (pet_id, product_id)

### Indexes

- cart_items_pkey
- ix_cart_items_pet_id
- idx_cart_items_pet_id
- uq_cart_item

---

## condition_medications

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| condition_id | uuid | No | - |  |
| name | character varying(200) | No | - |  |
| dose | character varying(100) | Yes | - |  |
| frequency | character varying(100) | Yes | - |  |
| route | character varying(50) | Yes | - |  |
| status | character varying(20) | No | 'active'::character varying |  |
| started_at | date | Yes | - |  |
| refill_due_date | date | Yes | - |  |
| price | character varying(20) | Yes | - |  |
| notes | character varying(500) | Yes | - |  |
| created_at | timestamp without time zone | No | now() |  |
| updated_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **condition_id** → conditions.id

### Indexes

- condition_medications_pkey
- ix_condition_medications_condition_id
- idx_condition_medications_condition_id
- idx_condition_medications_condition

---

## condition_monitoring

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| condition_id | uuid | No | - |  |
| name | character varying(200) | No | - |  |
| frequency | character varying(100) | Yes | - |  |
| next_due_date | date | Yes | - |  |
| last_done_date | date | Yes | - |  |
| created_at | timestamp without time zone | No | now() |  |
| updated_at | timestamp without time zone | No | now() |  |
| result_summary | character varying(200) | Yes | NULL::character varying |  |

### Primary Key

```
id
```

### Foreign Keys

- **condition_id** → conditions.id

### Indexes

- condition_monitoring_pkey
- ix_condition_monitoring_condition_id
- idx_condition_monitoring_condition_id
- idx_condition_monitoring_condition

---

## conditions

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| document_id | uuid | Yes | - |  |
| name | character varying(200) | No | - |  |
| diagnosis | character varying(500) | Yes | - |  |
| condition_type | character varying(20) | No | 'chronic'::character varying |  |
| diagnosed_at | date | Yes | - |  |
| notes | character varying(1000) | Yes | - |  |
| icon | character varying(10) | Yes | - |  |
| managed_by | character varying(200) | Yes | - |  |
| source | character varying(20) | No | 'extraction'::character varying |  |
| is_active | boolean | Yes | true |  |
| created_at | timestamp without time zone | No | now() |  |
| updated_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **document_id** → documents.id
- **pet_id** → pets.id

### Unique Constraints

- **uq_conditions_pet_name** on (name, pet_id)

### Indexes

- conditions_pkey
- uq_conditions_pet_name
- ix_conditions_pet_id
- ix_conditions_document_id
- idx_conditions_pet_id
- idx_conditions_document_id
- idx_conditions_pet_active

---

## conflict_flags

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | - | [PK] |
| preventive_record_id | uuid | Yes | - |  |
| new_date | date | No | - |  |
| status | character varying(20) | No | - |  |
| created_at | timestamp without time zone | Yes | - |  |

### Primary Key

```
id
```

### Foreign Keys

- **preventive_record_id** → preventive_records.id

### Indexes

- conflict_flags_pkey
- idx_conflict_flags_record_status

---

## contacts

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| document_id | uuid | Yes | - |  |
| role | character varying(30) | No | 'veterinarian'::character varying |  |
| name | character varying(200) | No | - |  |
| clinic_name | character varying(200) | Yes | - |  |
| phone | character varying(30) | Yes | - |  |
| email | character varying(200) | Yes | - |  |
| address | character varying(500) | Yes | - |  |
| source | character varying(20) | No | 'extraction'::character varying |  |
| created_at | timestamp without time zone | No | now() |  |
| updated_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **document_id** → documents.id
- **pet_id** → pets.id

### Unique Constraints

- **uq_contacts_pet_name_role** on (pet_id, name, role)

### Indexes

- contacts_pkey
- uq_contacts_pet_name_role
- ix_contacts_pet_id
- ix_contacts_document_id
- idx_contacts_pet_id
- idx_contacts_document_id
- idx_contacts_pet

---

## custom_preventive_items

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| user_id | uuid | No | - |  |
| item_name | character varying(120) | No | - |  |
| category | character varying(20) | No | 'complete'::character varying |  |
| circle | character varying(20) | No | 'health'::character varying |  |
| species | character varying(10) | No | - |  |
| recurrence_days | integer(32,0) | No | - |  |
| medicine_dependent | boolean | Yes | false |  |
| reminder_before_days | integer(32,0) | No | 7 |  |
| overdue_after_days | integer(32,0) | No | 7 |  |
| created_at | timestamp with time zone | Yes | now() |  |
| updated_at | timestamp with time zone | Yes | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **user_id** → users.id

### Unique Constraints

- **custom_preventive_items_user_id_item_name_species_key** on (item_name, user_id, species)

### Indexes

- custom_preventive_items_pkey
- custom_preventive_items_user_id_item_name_species_key
- ix_custom_preventive_items_user_id

---

## dashboard_tokens

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | - | [PK] |
| pet_id | uuid | Yes | - |  |
| token | character varying(255) | No | - |  |
| revoked | boolean | Yes | - |  |
| created_at | timestamp without time zone | Yes | - |  |
| expires_at | timestamp without time zone | Yes | - |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Unique Constraints

- **dashboard_tokens_token_key** on (token)

### Indexes

- dashboard_tokens_pkey
- dashboard_tokens_token_key
- idx_dashboard_tokens_token

---

## dashboard_visits

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| user_id | uuid | No | - |  |
| pet_id | uuid | No | - |  |
| token | character varying(200) | No | - |  |
| visited_at | timestamp with time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id
- **user_id** → users.id

### Indexes

- dashboard_visits_pkey
- idx_dashboard_visits_user_visited
- idx_dashboard_visits_pet_visited

---

## deferred_care_plan_pending

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| user_id | uuid | No | - |  |
| pet_id | uuid | No | - |  |
| reason | character varying(64) | No | 'pending_extractions'::character varying |  |
| is_cleared | boolean | No | false |  |
| created_at | timestamp without time zone | No | now() |  |
| cleared_at | timestamp without time zone | Yes | - |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id
- **user_id** → users.id

### Indexes

- deferred_care_plan_pending_pkey
- ix_deferred_care_plan_pending_pet
- ix_deferred_care_plan_pending_user
- ix_deferred_care_plan_pending_uncleared
- uq_deferred_care_plan_pending_pet_active

---

## diagnostic_test_results

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| document_id | uuid | Yes | - |  |
| test_type | character varying(30) | No | - |  |
| parameter_name | character varying(120) | No | - |  |
| value_numeric | numeric(14,4) | Yes | - |  |
| value_text | character varying(200) | Yes | - |  |
| unit | character varying(60) | Yes | - |  |
| reference_range | character varying(120) | Yes | - |  |
| status_flag | character varying(20) | Yes | - |  |
| observed_at | date | Yes | - |  |
| created_at | timestamp without time zone | No | now() |  |
| updated_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **document_id** → documents.id
- **pet_id** → pets.id

### Indexes

- diagnostic_test_results_pkey
- idx_diagnostic_results_pet
- idx_diagnostic_results_type_date
- idx_diagnostic_results_parameter
- uq_diagnostic_result_dedupe
- idx_diagnostic_test_results_pet

---

## diet_items

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| type | character varying(20) | No | - |  |
| icon | character varying(10) | Yes | - |  |
| label | character varying(200) | No | - |  |
| detail | character varying(200) | Yes | - |  |
| created_at | timestamp without time zone | No | now() |  |
| brand | character varying(200) | Yes | - |  |
| pack_size_g | integer(32,0) | Yes | - |  |
| daily_portion_g | integer(32,0) | Yes | - |  |
| units_in_pack | integer(32,0) | Yes | - |  |
| doses_per_day | integer(32,0) | Yes | - |  |
| last_purchase_date | date | Yes | - |  |
| reminder_order_at_o21 | boolean | No | false |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Unique Constraints

- **uq_diet_item** on (pet_id, label, type)

### Indexes

- diet_items_pkey
- uq_diet_item
- ix_diet_items_pet_id
- idx_diet_items_pet_id

---

## documents

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | - | [PK] |
| pet_id | uuid | Yes | - |  |
| file_path | character varying | No | - |  |
| mime_type | character varying(50) | No | - |  |
| extraction_status | character varying(20) | No | - |  |
| created_at | timestamp without time zone | Yes | - |  |
| document_name | character varying(200) | Yes | - |  |
| document_category | character varying(30) | Yes | NULL::character varying |  |
| source_wamid | character varying(200) | Yes | NULL::character varying |  |
| doctor_name | character varying(200) | Yes | NULL::character varying |  |
| hospital_name | character varying(200) | Yes | NULL::character varying |  |
| event_date | date | Yes | - |  |
| storage_backend | character varying(20) | No | 'supabase'::character varying |  |
| rejection_reason | character varying(200) | Yes | - |  |
| retry_count | integer(32,0) | No | 0 |  |
| content_hash | character varying(64) | Yes | - |  |
| extraction_confidence | double precision(53,None) | Yes | - |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Indexes

- documents_pkey
- ix_documents_pet_id
- uq_documents_source_wamid
- idx_documents_doctor_name
- idx_documents_hospital_name
- idx_documents_pet_extraction
- ix_documents_storage_backend
- idx_documents_retry_eligible
- idx_documents_content_hash

---

## food_nutrition_cache

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| food_label_normalized | character varying(200) | No | - |  |
| food_type | character varying(20) | No | - |  |
| nutrition_json | jsonb | No | - |  |
| created_at | timestamp with time zone | No | now() |  |

### Primary Key

```
id
```

### Unique Constraints

- **uq_food_nutrition_lookup** on (food_label_normalized, food_type)

### Indexes

- food_nutrition_cache_pkey
- uq_food_nutrition_lookup
- idx_food_nutrition_lookup

---

## hygiene_preferences

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| item_id | character varying(50) | No | - |  |
| name | character varying(100) | Yes | - |  |
| icon | character varying(10) | Yes | '🧹'::character varying |  |
| category | character varying(20) | Yes | 'daily'::character varying |  |
| is_default | boolean | No | false |  |
| freq | integer(32,0) | No | 1 |  |
| unit | character varying(10) | No | 'month'::character varying |  |
| reminder | boolean | No | false |  |
| last_done | character varying(20) | Yes | - |  |
| created_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Unique Constraints

- **uq_hygiene_pref** on (pet_id, item_id)

### Indexes

- hygiene_preferences_pkey
- uq_hygiene_pref
- ix_hygiene_preferences_pet_id
- idx_hygiene_preferences_pet_id

---

## hygiene_tip_cache

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| species | character varying(10) | No | - |  |
| breed_normalized | character varying(100) | No | - |  |
| item_id | character varying(50) | No | - |  |
| tip | character varying(300) | No | - |  |
| created_at | timestamp with time zone | No | now() |  |

### Primary Key

```
id
```

### Unique Constraints

- **uq_hygiene_tip_lookup** on (species, breed_normalized, item_id)

### Indexes

- hygiene_tip_cache_pkey
- uq_hygiene_tip_lookup
- idx_hygiene_tip_cache_lookup

---

## ideal_weight_cache

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| species | character varying(10) | No | - |  |
| breed_normalized | character varying(100) | No | - |  |
| gender | character varying(10) | No | - |  |
| age_category | character varying(20) | No | - |  |
| min_weight | numeric(5,2) | No | - |  |
| max_weight | numeric(5,2) | No | - |  |
| created_at | timestamp with time zone | No | now() |  |

### Primary Key

```
id
```

### Unique Constraints

- **uq_ideal_weight_lookup** on (gender, species, breed_normalized, age_category)

### Indexes

- ideal_weight_cache_pkey
- uq_ideal_weight_lookup

---

## message_logs

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | - | [PK] |
| mobile_number | character varying(15) | Yes | - |  |
| direction | character varying(10) | Yes | - |  |
| message_type | character varying(20) | Yes | - |  |
| payload | jsonb | Yes | - |  |
| created_at | timestamp without time zone | Yes | - |  |
| wamid | character varying(200) | Yes | - |  |

### Primary Key

```
id
```

### Indexes

- message_logs_pkey
- uq_message_logs_wamid

---

## nudge_config

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| key | character varying(100) | No | - |  |
| value | character varying(200) | No | - |  |
| description | text | Yes | - |  |
| updated_at | timestamp without time zone | Yes | now() |  |

### Primary Key

```
id
```

### Unique Constraints

- **nudge_config_key_key** on (key)

### Indexes

- nudge_config_pkey
- nudge_config_key_key

---

## nudge_delivery_log

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| nudge_id | uuid | Yes | - |  |
| pet_id | uuid | No | - |  |
| user_id | uuid | No | - |  |
| wa_status | character varying(20) | Yes | - |  |
| sent_at | timestamp without time zone | No | now() |  |
| nudge_level | integer(32,0) | Yes | - |  |
| template_name | character varying(100) | Yes | - |  |
| template_params | jsonb | Yes | - |  |
| message_body | text | Yes | - |  |

### Primary Key

```
id
```

### Foreign Keys

- **nudge_id** → nudges.id
- **pet_id** → pets.id
- **user_id** → users.id

### Indexes

- nudge_delivery_log_pkey
- idx_nudge_delivery_log_user_sent
- idx_nudge_delivery_log_user_level

---

## nudge_engagement

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| user_id | uuid | No | - |  |
| pet_id | uuid | No | - |  |
| last_engagement_at | timestamp without time zone | Yes | - |  |
| paused_until | timestamp without time zone | Yes | - |  |
| total_nudges_sent | integer(32,0) | Yes | 0 |  |
| total_acted_on | integer(32,0) | Yes | 0 |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id
- **user_id** → users.id

### Unique Constraints

- **uq_nudge_engagement_user_pet** on (user_id, pet_id)

### Indexes

- nudge_engagement_pkey
- uq_nudge_engagement_user_pet

---

## nudge_message_library

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| level | integer(32,0) | No | - |  |
| slot_day | integer(32,0) | No | 0 |  |
| seq | integer(32,0) | No | 1 |  |
| message_type | character varying(30) | No | - |  |
| breed | character varying(100) | No | 'All'::character varying |  |
| category | character varying(50) | Yes | - |  |
| template_key | character varying(100) | No | - |  |
| template_var_1 | text | Yes | - |  |
| template_var_2 | text | Yes | - |  |
| template_var_3 | text | Yes | - |  |
| template_var_4 | text | Yes | - |  |
| notes | text | Yes | - |  |
| created_at | timestamp with time zone | No | now() |  |

### Primary Key

```
id
```

### Unique Constraints

- **nudge_message_library_level_slot_day_seq_message_type_breed_key** on (message_type, breed, level, seq, slot_day)

### Indexes

- nudge_message_library_pkey
- nudge_message_library_level_slot_day_seq_message_type_breed_key
- idx_nudge_library_level_slot
- idx_nudge_library_l2_category

---

## nudges

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| category | character varying(30) | No | - |  |
| priority | character varying(10) | No | - |  |
| icon | character varying(10) | Yes | - |  |
| title | character varying(200) | No | - |  |
| message | text | No | - |  |
| mandatory | boolean | No | false |  |
| orderable | boolean | No | false |  |
| price | character varying(20) | Yes | - |  |
| order_type | character varying(30) | Yes | - |  |
| cart_item_id | character varying(10) | Yes | - |  |
| dismissed | boolean | No | false |  |
| source | character varying(20) | Yes | 'record'::character varying |  |
| wa_status | character varying(20) | Yes | - |  |
| wa_sent_at | timestamp without time zone | Yes | - |  |
| wa_message_id | character varying(100) | Yes | - |  |
| trigger_type | character varying(20) | Yes | 'cron'::character varying |  |
| expires_at | date | Yes | - |  |
| acted_on | boolean | Yes | false |  |
| created_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Indexes

- nudges_pkey
- ix_nudges_pet_id
- idx_nudges_pet_id
- idx_nudges_pet_dismissed
- idx_nudges_pet_created

---

## nutrition_target_cache

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| species | character varying(10) | No | - |  |
| breed_normalized | character varying(100) | No | - |  |
| age_category | character varying(20) | No | - |  |
| targets_json | jsonb | No | - |  |
| created_at | timestamp with time zone | No | now() |  |

### Primary Key

```
id
```

### Unique Constraints

- **uq_nutrition_target_lookup** on (species, age_category, breed_normalized)

### Indexes

- nutrition_target_cache_pkey
- uq_nutrition_target_lookup
- idx_nutrition_target_lookup

---

## order_recommendations

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | Yes | - |  |
| species | character varying(10) | No | - |  |
| breed | character varying(100) | Yes | - |  |
| age_range | character varying(20) | Yes | - |  |
| category | character varying(30) | No | - |  |
| items | jsonb | No | '[]'::jsonb |  |
| used_count | integer(32,0) | No | 0 |  |
| created_at | timestamp without time zone | No | now() |  |
| updated_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Indexes

- order_recommendations_pkey
- ix_order_recommendations_species
- ix_order_recommendations_breed
- ix_order_recommendations_category
- ix_order_recommendations_profile

---

## orders

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| user_id | uuid | No | - |  |
| pet_id | uuid | Yes | - |  |
| category | character varying(30) | No | - |  |
| items_description | character varying(2000) | No | - |  |
| status | character varying(20) | No | 'pending'::character varying |  |
| admin_notes | character varying(2000) | Yes | - |  |
| created_at | timestamp without time zone | Yes | now() |  |
| updated_at | timestamp without time zone | Yes | now() |  |
| razorpay_order_id | character varying(100) | Yes | - |  |
| razorpay_payment_id | character varying(100) | Yes | - |  |
| payment_status | character varying(20) | Yes | 'pending'::character varying |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id
- **user_id** → users.id

### Indexes

- orders_pkey
- ix_orders_user_id
- ix_orders_status
- ix_orders_created_at
- ix_orders_razorpay_order_id

---

## pet_ai_insights

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| insight_type | character varying(50) | No | - |  |
| content_json | jsonb | No | - |  |
| generated_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Unique Constraints

- **uq_pet_ai_insight** on (insight_type, pet_id)

### Indexes

- pet_ai_insights_pkey
- uq_pet_ai_insight
- ix_pet_ai_insights_pet_id
- idx_pet_ai_insights_pet_type

---

## pet_life_stage_traits

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| life_stage | character varying(20) | No | - |  |
| breed_size | character varying(20) | No | - |  |
| traits | jsonb | No | - |  |
| generated_at | timestamp without time zone | No | - |  |
| created_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Unique Constraints

- **uq_pet_life_stage_trait_pet_stage** on (pet_id, life_stage)

### Indexes

- pet_life_stage_traits_pkey
- uq_pet_life_stage_trait_pet_stage
- ix_pet_life_stage_traits_pet_id

---

## pet_preferences

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| category | character varying(30) | No | - |  |
| preference_type | character varying(20) | No | 'custom'::character varying |  |
| item_name | character varying(500) | No | - |  |
| used_count | integer(32,0) | No | 1 |  |
| created_at | timestamp without time zone | No | now() |  |
| updated_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Indexes

- pet_preferences_pkey
- ix_pet_preferences_pet_category
- ix_pet_preferences_preference_type

---

## pets

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | - | [PK] |
| user_id | uuid | Yes | - |  |
| name | character varying(100) | No | - |  |
| species | character varying(10) | No | - |  |
| breed | character varying(100) | Yes | - |  |
| gender | character varying(10) | Yes | - |  |
| dob | date | Yes | - |  |
| weight | numeric(5,2) | Yes | - |  |
| neutered | boolean | Yes | - |  |
| is_deleted | boolean | Yes | - |  |
| created_at | timestamp without time zone | Yes | - |  |
| updated_at | timestamp without time zone | Yes | - |  |
| weight_flagged | boolean | Yes | false |  |
| photo_path | text | Yes | - |  |
| age_text | character varying(50) | Yes | - |  |

### Primary Key

```
id
```

### Foreign Keys

- **user_id** → users.id

### Indexes

- pets_pkey

---

## prescribed_medicines

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| document_id | uuid | Yes | - |  |
| medicine_name | character varying(200) | No | - |  |
| dosage | character varying(200) | Yes | - |  |
| frequency | character varying(200) | Yes | - |  |
| duration | character varying(200) | Yes | - |  |
| notes | text | Yes | - |  |
| is_active | boolean | No | true |  |
| start_date | date | Yes | - |  |
| end_date | date | Yes | - |  |
| created_at | timestamp without time zone | No | now() |  |
| updated_at | timestamp without time zone | No | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **document_id** → documents.id
- **pet_id** → pets.id

### Indexes

- prescribed_medicines_pkey
- idx_prescribed_medicines_pet
- idx_prescribed_medicines_active
- uq_prescribed_medicines_doc_medicine

---

## preventive_master

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | - | [PK] |
| item_name | character varying(120) | No | - |  |
| category | character varying(20) | No | - |  |
| species | character varying(10) | No | - |  |
| recurrence_days | integer(32,0) | No | - |  |
| medicine_dependent | boolean | Yes | - |  |
| reminder_before_days | integer(32,0) | No | - |  |
| overdue_after_days | integer(32,0) | No | - |  |
| circle | character varying(20) | No | 'health'::character varying |  |
| is_core | boolean | No | false |  |
| is_mandatory | boolean | No | false |  |

### Primary Key

```
id
```

### Unique Constraints

- **uq_preventive_master_item_species** on (item_name, species)

### Indexes

- preventive_master_pkey
- uq_preventive_master_item_species

---

## preventive_master_archive_037

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | Yes | - |  |
| item_name | character varying(120) | Yes | - |  |
| category | character varying(20) | Yes | - |  |
| species | character varying(10) | Yes | - |  |
| recurrence_days | integer(32,0) | Yes | - |  |
| medicine_dependent | boolean | Yes | - |  |
| reminder_before_days | integer(32,0) | Yes | - |  |
| overdue_after_days | integer(32,0) | Yes | - |  |
| circle | character varying(20) | Yes | - |  |

---

## preventive_records

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | - | [PK] |
| pet_id | uuid | Yes | - |  |
| preventive_master_id | uuid | Yes | - |  |
| last_done_date | date | Yes | - |  |
| next_due_date | date | Yes | - |  |
| status | character varying(20) | No | - |  |
| created_at | timestamp without time zone | Yes | - |  |
| updated_at | timestamp without time zone | Yes | - |  |
| custom_recurrence_days | integer(32,0) | Yes | - |  |
| custom_preventive_item_id | uuid | Yes | - |  |
| medicine_name | character varying(200) | Yes | - |  |

### Primary Key

```
id
```

### Foreign Keys

- **custom_preventive_item_id** → custom_preventive_items.id
- **pet_id** → pets.id
- **preventive_master_id** → preventive_master.id

### Unique Constraints

- **uq_preventive_record_pet_custom_item_date** on (last_done_date, custom_preventive_item_id, pet_id)
- **uq_preventive_record_pet_item_date** on (pet_id, preventive_master_id, last_done_date)

### Indexes

- preventive_records_pkey
- uq_preventive_record_pet_item_date
- ix_preventive_records_pet_id
- uq_preventive_record_pet_custom_item_date
- idx_preventive_records_pet_status
- idx_preventive_records_pet_next_due

---

## preventive_records_archive_037

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | Yes | - |  |
| pet_id | uuid | Yes | - |  |
| preventive_master_id | uuid | Yes | - |  |
| last_done_date | date | Yes | - |  |
| next_due_date | date | Yes | - |  |
| status | character varying(20) | Yes | - |  |
| created_at | timestamp without time zone | Yes | - |  |
| updated_at | timestamp without time zone | Yes | - |  |
| custom_recurrence_days | integer(32,0) | Yes | - |  |
| custom_preventive_item_id | uuid | Yes | - |  |
| medicine_name | character varying(200) | Yes | - |  |

---

## product_food

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| sku_id | character varying(10) | No | - | [PK] |
| brand_id | character varying(10) | No | - |  |
| brand_name | character varying(100) | No | - |  |
| product_line | character varying(200) | No | - |  |
| life_stage | character varying(20) | No | - |  |
| breed_size | character varying(20) | No | - |  |
| pack_size_kg | numeric(5,1) | No | - |  |
| mrp | integer(32,0) | No | - |  |
| discounted_price | integer(32,0) | No | - |  |
| condition_tags | text | Yes | - |  |
| breed_tags | text | Yes | - |  |
| vet_diet_flag | boolean | No | false |  |
| active | boolean | No | true |  |
| popularity_rank | integer(32,0) | No | - |  |
| monthly_units_sold | integer(32,0) | Yes | - |  |
| price_per_kg | integer(32,0) | Yes | - |  |
| in_stock | boolean | No | true |  |
| notes | text | Yes | - |  |
| created_at | timestamp with time zone | No | now() |  |

### Primary Key

```
sku_id
```

### Indexes

- product_food_pkey
- idx_product_food_brand_id
- idx_product_food_life_stage_breed
- idx_product_food_condition_tags

---

## product_medicines

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| sku_id | character varying(10) | No | - | [PK] |
| brand_id | character varying(10) | No | - |  |
| brand_name | character varying(100) | No | - |  |
| product_name | character varying(255) | No | - |  |
| type | character varying(100) | No | - |  |
| form | character varying(50) | No | - |  |
| pack_size | character varying(100) | No | - |  |
| mrp_paise | integer(32,0) | No | - |  |
| discounted_paise | integer(32,0) | No | - |  |
| key_ingredients | text | Yes | - |  |
| condition_tags | text | Yes | - |  |
| life_stage_tags | text | Yes | - |  |
| active | boolean | No | true |  |
| popularity_rank | integer(32,0) | Yes | - |  |
| monthly_units_sold | integer(32,0) | Yes | - |  |
| price_per_unit_paise | integer(32,0) | Yes | - |  |
| in_stock | boolean | No | true |  |
| dosage | text | Yes | - |  |
| repeat_frequency | character varying(100) | Yes | - |  |
| notes | text | Yes | - |  |
| created_at | timestamp with time zone | No | now() |  |

### Primary Key

```
sku_id
```

### Indexes

- product_medicines_pkey
- idx_product_medicines_brand_id
- idx_product_medicines_type
- idx_product_medicines_condition_tags
- idx_product_medicines_life_stage_tags

---

## product_supplement

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| sku_id | character varying(10) | No | - | [PK] |
| brand_id | character varying(10) | No | - |  |
| brand_name | character varying(100) | No | - |  |
| product_name | character varying(200) | No | - |  |
| type | character varying(50) | No | - |  |
| form | character varying(30) | No | - |  |
| pack_size | character varying(50) | No | - |  |
| mrp | integer(32,0) | No | - |  |
| discounted_price | integer(32,0) | No | - |  |
| key_ingredients | text | Yes | - |  |
| condition_tags | text | Yes | - |  |
| life_stage_tags | text | Yes | - |  |
| active | boolean | No | true |  |
| popularity_rank | integer(32,0) | No | - |  |
| monthly_units | integer(32,0) | Yes | - |  |
| price_per_unit | integer(32,0) | Yes | - |  |
| in_stock | boolean | No | true |  |
| notes | text | Yes | - |  |
| created_at | timestamp with time zone | No | now() |  |

### Primary Key

```
sku_id
```

### Indexes

- product_supplement_pkey
- idx_product_supplement_brand_id
- idx_product_supplement_type

---

## reminders

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | - | [PK] |
| preventive_record_id | uuid | Yes | - |  |
| next_due_date | date | No | - |  |
| status | character varying(20) | No | - |  |
| sent_at | timestamp without time zone | Yes | - |  |
| created_at | timestamp without time zone | Yes | - |  |
| stage | character varying(20) | No | 'due'::character varying |  |
| ignore_count | integer(32,0) | No | 0 |  |
| monthly_fallback | boolean | No | false |  |
| last_ignored_at | timestamp with time zone | Yes | - |  |
| source_type | character varying(30) | Yes | - |  |
| source_id | uuid | Yes | - |  |
| item_desc | character varying(300) | Yes | - |  |
| pet_id | uuid | Yes | - |  |
| template_name | character varying(100) | Yes | - |  |
| template_params | jsonb | Yes | - |  |
| message_body | text | Yes | - |  |
| sub_type | character varying(30) | Yes | - |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id
- **preventive_record_id** → preventive_records.id

### Unique Constraints

- **uq_reminder_record_duedate_stage** on (preventive_record_id, stage, next_due_date)

### Indexes

- reminders_pkey
- ix_reminders_preventive_record_id
- idx_reminders_record_status
- uq_reminder_record_duedate_stage
- idx_reminders_stage
- idx_reminders_monthly_fallback
- idx_reminders_pet_id

---

## shown_fun_facts

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| user_id | uuid | No | - |  |
| fact_hash | character varying(64) | No | - |  |
| created_at | timestamp with time zone | Yes | now() |  |

### Primary Key

```
id
```

### Foreign Keys

- **user_id** → users.id

### Indexes

- shown_fun_facts_pkey
- uq_shown_fun_facts_user_hash
- ix_shown_fun_facts_user_id

---

## users

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | - | [PK] |
| mobile_number | character varying(500) | No | - |  |
| full_name | character varying(120) | No | - |  |
| pincode | character varying(500) | Yes | - |  |
| is_deleted | boolean | Yes | - |  |
| created_at | timestamp without time zone | Yes | - |  |
| updated_at | timestamp without time zone | Yes | - |  |
| consent_given | boolean | Yes | false |  |
| onboarding_state | character varying(30) | Yes | 'awaiting_consent'::character varying |  |
| email | character varying(500) | Yes | - |  |
| mobile_hash | character varying(64) | No | - |  |
| mobile_display | character varying(20) | Yes | - |  |
| doc_upload_deadline | timestamp with time zone | Yes | - |  |
| order_state | character varying(30) | Yes | - |  |
| active_order_id | uuid | Yes | - |  |
| dashboard_link_pending | boolean | No | false |  |
| onboarding_completed_at | timestamp with time zone | Yes | - |  |
| active_reminder_id | uuid | Yes | - |  |
| onboarding_data | jsonb | Yes | - |  |
| delivery_address | text | Yes | - |  |
| payment_method_pref | character varying(10) | Yes | - |  |
| saved_upi_id | character varying(500) | Yes | - |  |
| edit_state | character varying(30) | Yes | - |  |
| edit_data | jsonb | Yes | - |  |

### Primary Key

```
id, id
```

### Foreign Keys

- **active_order_id** → orders.id
- **active_reminder_id** → reminders.id

### Unique Constraints

- **uq_users_mobile_hash** on (mobile_hash)
- **users_phone_key** on (phone)

### Indexes

- users_pkey
- uq_users_mobile_hash
- ix_users_mobile_hash
- idx_users_onboarding_completed

---

## weight_history

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | uuid | No | gen_random_uuid() | [PK] |
| pet_id | uuid | No | - |  |
| weight | numeric(5,2) | No | - |  |
| recorded_at | date | No | - |  |
| note | character varying(255) | Yes | - |  |
| created_at | timestamp without time zone | No | now() |  |
| bcs | smallint(16,0) | Yes | - |  |

### Primary Key

```
id
```

### Foreign Keys

- **pet_id** → pets.id

### Indexes

- weight_history_pkey
- ix_weight_history_pet_id
- idx_weight_history_pet_id

---

## whatsapp_template_configs

**Description:** Auto-extracted from database

### Columns

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| template_name | character varying(100) | No | - | [PK] |
| body_text | text | No | ''::text |  |
| param_count | integer(32,0) | No | 0 |  |
| language_code | character varying(10) | No | 'en'::character varying |  |
| description | text | Yes | - |  |
| created_at | timestamp with time zone | No | now() |  |
| updated_at | timestamp with time zone | No | now() |  |

### Primary Key

```
template_name
```

### Indexes

- whatsapp_template_configs_pkey

---

