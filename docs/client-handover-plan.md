# PetCircle — Full Client Handover Plan

## Context
You are handing over the entire PetCircle project to a client. This includes the GitHub repository, Render backend, Vercel frontend, Supabase database, and all third-party service credentials. The goal is for the client to fully own and operate the system after handover, with zero dependency on your personal accounts.

---

## Pre-Handover Audit Findings (Security Issues to Address First)

| Issue | Severity | Action Required |
|-------|----------|-----------------|
| GitHub PAT embedded in `.git/config` remote URL | HIGH | Rotate the PAT immediately before/after transfer |
| `backend/envs/.env.production` may be committed to repo | HIGH | Audit git history; remove if present |
| `anthropic` package unpinned in `requirements.txt` | MEDIUM | Pin to current version |
| Duplicate migration `032_` prefix (two files) | MEDIUM | Rename one file |
| Missing migration `048` (gap in sequence) | LOW | Confirm intentional or rename to fill gap |

---

## Phase 0: Security Cleanup (Before Transfer)

### 0A — Audit .env.production in git history
```bash
git log --all --full-history -- "backend/envs/.env.production"
git ls-files "backend/envs/.env.production"
```
- If it's tracked: remove from history using `git filter-repo` and add to `.gitignore`
- If not tracked: confirm it's in `.gitignore` — leave as-is

### 0B — Fix git remote URL (remove embedded PAT)
The current remote embeds a PAT: `https://BerenikeSolutions:<TOKEN>@github.com/...`
After transfer: the client should set their own remote. For now:
```bash
git remote set-url origin https://github.com/BerenikeSolutions/pet-circle.git
```

### 0C — Pin anthropic package
File: `backend/requirements.txt`
- Check current installed version: `pip show anthropic`
- Pin it: `anthropic==<version>`

---

## Phase 1: Prepare Handover Documentation

### 1A — Compile full credentials inventory
Create a secure document (1Password, Bitwarden, or encrypted file) listing every credential the client needs. Categories:

**GitHub:**
- Repository URL: `https://github.com/BerenikeSolutions/pet-circle`

**Render (Backend):**
All these must be set in the Render dashboard → Environment Variables:
- `APP_ENV=production`
- `DATABASE_URL` (Supabase connection string)
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_BUCKET_NAME=petcircle-documents`
- `WHATSAPP_TOKEN`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_TEMPLATE_CONFLICT`
- `WHATSAPP_TEMPLATE_ORDER_FULFILLMENT_CHECK`
- `WHATSAPP_TEMPLATE_BIRTHDAY`
- `ADMIN_SECRET_KEY`
- `ADMIN_DASHBOARD_PASSWORD`
- `ENCRYPTION_KEY`
- `FRONTEND_URL` (Vercel URL)
- `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` depending on `AI_PROVIDER`)
- `AI_PROVIDER` (`claude` or `openai`)
- `GCP_CREDENTIALS_JSON` (base64-encoded GCP service account JSON)
- `GCP_BUCKET_NAME`
- All `WHATSAPP_TEMPLATE_*` vars (13 total — see list below)
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (if payments active)
- `ORDER_NOTIFICATION_PHONE`
- `CLOUDAMQP_URL` (if RabbitMQ used)

**All WHATSAPP_TEMPLATE_* variables (13 total):**
- `WHATSAPP_TEMPLATE_CONFLICT`
- `WHATSAPP_TEMPLATE_ORDER_FULFILLMENT_CHECK`
- `WHATSAPP_TEMPLATE_BIRTHDAY`
- `WHATSAPP_TEMPLATE_REMINDER_T7`
- `WHATSAPP_TEMPLATE_REMINDER_DUE`
- `WHATSAPP_TEMPLATE_REMINDER_D3`
- `WHATSAPP_TEMPLATE_REMINDER_OVERDUE`
- `WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL`
- `WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT`
- `WHATSAPP_TEMPLATE_NUDGE_BREED`
- `WHATSAPP_TEMPLATE_NUDGE_BREED_DATA`
- `WHATSAPP_TEMPLATE_NUDGE_NO_BREED`
- `WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED`
- `WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED`
- `WHATSAPP_TEMPLATE_REMINDER_FOOD_SCHEDULED`
- `WHATSAPP_TEMPLATE_REMINDER_SUPPLEMENT_SCHEDULED`
- `WHATSAPP_TEMPLATE_REMINDER_CHRONIC_SCHEDULED`

**Vercel (Frontend):**
- `NEXT_PUBLIC_API_URL` → Render production URL

**GitHub Actions Secrets:**
- `PRODUCTION_API_URL` → Render production URL
- `ADMIN_SECRET_KEY`
- `RENDER_BACKEND_URL` → Render production URL

**External Services (client needs their own accounts or transferred access):**
- Meta (WhatsApp Business API) — app, phone number, token
- OpenAI — API key
- Anthropic — API key
- GCP — Storage bucket + service account
- Supabase — project + credentials
- Razorpay — key + secret

---

## Phase 2: GitHub Repository Transfer

### Option A — Transfer to client's GitHub account (recommended)
1. Client creates a GitHub account (or provides existing one)
2. Go to: `github.com/BerenikeSolutions/pet-circle` → Settings → Danger Zone → Transfer
3. Enter client's GitHub username or organization name
4. Confirm transfer

**After transfer:**
- Update GitHub Actions secrets in the new repo:
  - `PRODUCTION_API_URL`
  - `ADMIN_SECRET_KEY`
  - `RENDER_BACKEND_URL`
- Render auto-deploy webhook URL may need updating in repo settings

### Option B — Add client as owner, transfer later
1. Settings → Collaborators → Add client with Owner role
2. Client accepts invitation
3. When ready, transfer ownership (same steps as Option A)

---

## Phase 3: Render Backend Transfer

### 3A — New Render account for client
1. Client creates account at `render.com`
2. Client connects their GitHub account to Render

### 3B — Recreate services from render.yaml
The `render.yaml` defines two services. Client imports via:
- Render Dashboard → New → Blueprint → select their forked repo → uses `render.yaml` auto-config

**OR** client creates services manually:

| Setting | Value |
|---------|-------|
| Runtime | Python 3 |
| Build command | `cd backend && pip install --only-binary=PyMuPDF -r requirements.txt` |
| Start command | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| Region | Singapore (or client preference) |

**Two services to create:**
- `petcircle-api` — deploys from `main` branch (production)
- `petcircle-api-dev` — deploys from `dev` branch (staging)

### 3C — Set all environment variables
All 30+ env vars (listed in Phase 1A) must be entered in Render → Environment tab.
None are synced from render.yaml (all marked `sync: false`).

### 3D — Update Render keepalive and cron workflows
After new Render URL is known, update GitHub Actions secrets:
- `RENDER_BACKEND_URL` → new Render URL

---

## Phase 4: Vercel Frontend Transfer

### 4A — New Vercel account for client
1. Client creates account at `vercel.com`
2. Client imports project from their GitHub repo

### 4B — Deploy settings
No `vercel.json` committed — Vercel auto-detects Next.js.

| Setting | Value |
|---------|-------|
| Framework | Next.js (auto-detected) |
| Root Directory | `frontend` |
| Build command | `npm run build` (auto) |
| Output directory | `.next` (auto) |

### 4C — Set frontend environment variable
In Vercel project → Settings → Environment Variables:
- `NEXT_PUBLIC_API_URL` → new Render production URL (e.g., `https://petcircle-api.onrender.com`)

### 4D — Update FRONTEND_URL in Render
After Vercel deployment URL is known, update Render env var:
- `FRONTEND_URL` → new Vercel URL

---

## Phase 5: Supabase Database Transfer

### Option A — Transfer Supabase project (recommended)
1. Client creates a Supabase account and organization
2. Go to Supabase Dashboard → Project Settings → General → Transfer project
3. Transfer to client's organization

**After transfer:**
- Client rotates all Supabase keys (anon key, service role key)
- Update Render env vars: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`

### Option B — Fresh Supabase project + migration
1. Client creates new Supabase project
2. Run all 60 migrations in order against the new DB
3. Export + import data from old to new project
4. Update Render env vars

**Migration run command:**
```bash
psql $DATABASE_URL -f backend/migrations/<file>.sql
```

**Migration notes:**
- Migration `032` has two files with the same prefix — run both, in alphabetical order
- Migration `048` is missing (gap between 047 and 049) — this is intentional; skip it

**Full migration list (60 files in run order):**
```
000_add_conditions_contacts.sql
001_add_dashboard_tables.sql
002_nutrition_cache_tables.sql
003_hygiene_columns.sql
004_condition_phase5_columns.sql
005_nudge_engine.sql
006_document_event_date.sql
007_medicine_name_optional_vaccines.sql
008_custom_preventive_items.sql
009_hygiene_tip_cache.sql
010_dog_dhppi_puppy_vaccines.sql
011_dog_mandatory_vaccines.sql
012_pet_ai_insights.sql
013_orders_payment_fields.sql
014_agent_onboarding_sessions.sql
015_agent_order_sessions.sql
016_user_dashboard_link_pending.sql
017_performance_indexes.sql
018_documents_storage_backend.sql
019_document_rejection.sql
020_nudge_indexes.sql
021_kennel_cough_ccov_optional.sql
022_reminder_stage.sql
023_onboarding_completed_at.sql
024_diet_items_order_data.sql
025_nudge_message_library.sql
026_breed_consequence_library.sql
027_dashboard_visits.sql
028_reminder_source_columns.sql
029_nudge_delivery_log_level.sql
030_whatsapp_template_configs.sql
031_template_message_columns.sql
032_nudge_generic_no_breed.sql       (run first)
032_update_template_body_texts.sql   (run second)
033_reminder_subtype.sql
034_onboarding_data_and_age.sql
035_pet_life_stage_traits.sql
036_deferred_care_plan_pending.sql
037_preventive_master_dog_only_cleanup.sql
038_kennel_cough_ccov_essential.sql
039_core_preventive_flag.sql
040_drop_agent_onboarding_sessions.sql
041_health_trends_guardrail_columns.sql
042_kennel_cough_ccov_core_essential.sql
043_truncate_preventive_master.sql
044_cart_rules_product_tables.sql
045_cart_expires_at.sql
046_preventive_master_is_mandatory.sql
047_seed_product_catalog.sql
049_user_checkout_preferences.sql    (048 does not exist — intentional gap)
050_reseed_supplement_catalog.sql
051_create_product_medicines.sql
052_seed_product_medicines.sql
053_document_hardening.sql
054_edit_state.sql
055_drop_essential_care_column.sql
056_health_conditions_v2.sql
057_diagnostic_test_type_vital.sql
058_contacts_source_document_fields.sql
059_extraction_missing_fields.sql
```

---

## Phase 6: External Service Credentials

| Service | Action |
|---------|--------|
| Meta/WhatsApp Business API | Client registers/obtains their own WhatsApp Business account; update all `WHATSAPP_*` env vars |
| OpenAI | Client creates API key at platform.openai.com; update `OPENAI_API_KEY` |
| Anthropic | Client creates API key at console.anthropic.com; update `ANTHROPIC_API_KEY` |
| GCP Storage | Client creates GCP project + bucket; create service account; base64-encode JSON; update `GCP_CREDENTIALS_JSON` + `GCP_BUCKET_NAME` |
| Razorpay | Client creates account; update `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET` |
| CloudAMQP/RabbitMQ | If used: client creates CloudAMQP account; update `CLOUDAMQP_URL` |

---

## Phase 7: GitHub Actions Cron Reference

| Workflow File | Schedule | Purpose | Secrets Used |
|--------------|----------|---------|--------------|
| `reminder-cron.yml` | 02:30 UTC (08:00 IST) daily | POST `/internal/run-reminder-engine` and `/internal/run-nudge-scheduler` | `PRODUCTION_API_URL`, `ADMIN_SECRET_KEY` |
| `sync-gcp.yml` | 03:00 UTC (08:30 IST) daily | POST `/admin/trigger-gcp-sync` | `RENDER_BACKEND_URL`, `ADMIN_SECRET_KEY` |
| `render-keepalive.yml` | Every 10 minutes | GET `/health` to prevent cold starts | `RENDER_BACKEND_URL` |
| `extraction-replay.yml` | Every 6 hours | POST `/internal/run-extraction-replay` | `PRODUCTION_API_URL`, `ADMIN_SECRET_KEY` |
| `deploy-check.yml` | On push to dev/main | GET `/health` post-deploy verification | `RENDER_BACKEND_URL` |
| `ci-backend.yml` | On PR/push (backend paths) | Lint + unit tests | — |
| `ci-frontend.yml` | On PR/push (frontend paths) | npm ci + lint + next build | — |

---

## Phase 8: Final Transfer Verification Checklist

After all transfers complete, verify the following:

### Infrastructure
- [ ] GitHub repo owned by client, your access removed
- [ ] GitHub Actions workflows running (check Actions tab)
- [ ] Render backend health check passing: `GET /health`
- [ ] Vercel frontend loading at new domain
- [ ] `NEXT_PUBLIC_API_URL` points to new Render URL
- [ ] `FRONTEND_URL` in Render points to new Vercel URL

### Database
- [ ] Supabase credentials updated in Render env vars
- [ ] Dashboard loads pet data correctly

### WhatsApp
- [ ] All `WHATSAPP_TEMPLATE_*` env vars set in Render
- [ ] WhatsApp webhook verified at new Render URL (Meta Developer Console)
- [ ] Test message send/receive working

### Cron Jobs
- [ ] Reminder cron job (`reminder-cron.yml`) firing and hitting correct URL
- [ ] GCP sync cron (`sync-gcp.yml`) firing correctly
- [ ] Keepalive pinging new Render URL

### Security
- [ ] PAT from old `.git/config` rotated/revoked (GitHub → Settings → Developer settings → Tokens)
- [ ] Your Render account disconnected from the service
- [ ] Your Vercel account disconnected from the project
- [ ] Your Supabase access removed from the project
- [ ] All API keys rotated (OpenAI, Anthropic, GCP service account)

---

## Deliverables to Hand to Client

1. **Credentials Sheet** — All secrets listed in Phase 1A, filled in with actual values (share via secure channel: 1Password, Bitwarden, or encrypted email)
2. **This Setup Guide** — Step-by-step for Render + Vercel + GitHub setup
3. **Migration SQL Archive** — All 60 SQL files zipped, with README noting the 032 duplicate and 048 gap
4. **Environment Variables Reference** — Which var goes where (Render vs Vercel vs GitHub Actions)
5. **Cron Schedule Summary** — Phase 7 table above

---

## Execution Order

```
Phase 0 (security cleanup)
  ↓
Phase 1 (prepare credentials doc)
  ↓
Phase 2 (GitHub transfer)
  ↓
Phase 3 + 4 + 5 + 6 (can all run in parallel)
Render + Vercel + Supabase + External services
  ↓
Phase 7 (verification checklist)
```
