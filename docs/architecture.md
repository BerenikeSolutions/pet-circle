# PetCircle — Architecture Overview

## System Purpose

PetCircle is a WhatsApp-based preventive pet health system for India. Pet parents interact via WhatsApp to track vaccinations, deworming, lab tests, and other preventive care items. The system sends reminders, extracts data from uploaded documents using AI, and provides a web dashboard for viewing health records.

## Architecture Pattern: WAT Framework

The system uses the **WAT** (Workflows, Agents, Tools) pattern:

- **Workflows** (`workflows/`): Markdown SOPs defining each business process step-by-step
- **Agents**: The orchestration layer (FastAPI routers + message router) that reads workflows and calls tools
- **Tools** (`backend/app/services/`): Deterministic Python modules that execute specific operations

## System Flow

```
User (WhatsApp)
    |
    v
WhatsApp Cloud API
    |
    v
FastAPI Webhook (/webhook/whatsapp)
    |
    v
Message Router (app/services/message_router.py)
    |
    +---> Onboarding Service (standard or agentic)
    +---> Document Upload + GPT Extraction
    +---> Conflict Engine
    +---> Reminder Response Handler
    +---> Order Service (agentic order flow + admin fulfillment check)
    +---> Query Engine
    |
    v
Supabase (PostgreSQL) + GCP Cloud Storage
    |
    v
Reminder Engine (daily cron at 8 AM IST)
    |
    v
WhatsApp Template Messages
    |
    v
Next.js Dashboard (token-based access)
```

## Component Map

| Component | Technology | Location |
|-----------|------------|----------|
| Backend API | Python 3.11 + FastAPI | `backend/` |
| Messaging | WhatsApp Cloud API | `backend/app/services/whatsapp_sender.py` |
| AI Extraction | OpenAI GPT (gpt-4.1) | `backend/app/services/gpt_extraction.py` |
| AI Query | OpenAI GPT (gpt-4.1) | `backend/app/services/query_engine.py` |
| Agentic Flows | OpenAI GPT (gpt-4.1) | `backend/app/services/agentic_onboarding.py`, `agentic_order.py`, `agentic_finalization.py` |
| Database | Supabase (PostgreSQL) | `backend/app/database.py`, `backend/app/models/` |
| File Storage | GCP Cloud Storage (primary), Supabase Storage (fallback) | `backend/app/services/storage_service.py`, `document_upload.py` |
| Frontend | Next.js 14 + Tailwind | `frontend/` |
| Backend Hosting | Render | `render.yaml` |
| Frontend Hosting | Vercel | `frontend/` |
| Cron | GitHub Actions | `.github/workflows/reminder-cron.yml` |

## Key Design Decisions

1. **Monolithic backend**: No microservices. All logic in one FastAPI app with clear layer separation.
2. **No background queue**: Background processing via `asyncio.create_task()`. Queue can be added later if needed.
3. **Token-based dashboard**: No login system. Secure 128-bit random tokens shared via WhatsApp.
4. **GCP primary storage**: Document uploads go to GCP Cloud Storage (`petcircle-documents` bucket). Supabase Storage is the fallback. No public URLs — access via signed URLs only.
5. **Environment-aware config**: `APP_ENV` controls which env file is loaded (development/test/production).
6. **Performance**: Dashboard queries use SQLAlchemy `selectinload` for eager loading. Migration 017 adds composite indexes on all high-frequency filter patterns.

## Agentic Flows

Three LLM-orchestrated flows handle complex multi-turn interactions:

- **`agentic_onboarding.py`**: Guides new users through onboarding using GPT to compose responses and manage conversation state.
- **`agentic_order.py`**: Drives the order placement flow with GPT-powered product recommendations and intent detection.
- **`agentic_finalization.py`**: Composes the final confirmation message after order or onboarding, using GPT to personalize the summary.

All agentic flows use `gpt-4.1`, log all calls, and never block the webhook response.

## Health Score

The dashboard health score uses a **6-category weighted formula** computed by `backend/app/services/health_score.py`:

1. Vaccinations
2. Deworming
3. Tick/flea prevention
4. Vet checkups
5. Nutrition
6. Conditions management

Each category is scored 0–100 and weighted. The composite score drives the ring indicator on the Overview tab.

## Order Notification Flow

- When a user confirms an order, the backend sends a WhatsApp template notification to `ORDER_NOTIFICATION_PHONE` (if configured).
- The template name is loaded from `WHATSAPP_TEMPLATE_ORDER_FULFILLMENT_CHECK`.
- If `ORDER_NOTIFICATION_PHONE` is not configured, the order is still saved and user confirmation is unaffected.

## Security Model

- Mobile number as unique user identifier
- WhatsApp webhook signature verification (`X-Hub-Signature-256`)
- Admin endpoints require `X-ADMIN-KEY` header
- Dashboard access via 128-bit random token
- Media files in private GCP bucket (no public URLs)
- All secrets loaded from environment variables (never hardcoded)
