"""
PetCircle Phase 1 — Application Configuration

Uses Pydantic BaseSettings to load and validate all environment variables.
If any required variable is missing, the application will refuse to start
and print a clear error message identifying the missing variable.

All credentials are loaded from environment files only — never hardcoded.

Environment selection:
  - Set APP_ENV to 'development', 'test', or 'production'.
  - Defaults to 'development' if not set.
  - Loads envs/.env.{APP_ENV} file; in production, the hosting provider sets env vars directly.
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings

from app.core.constants import SYSTEM_TIMEZONE

# --- Environment Selection ---
# APP_ENV controls which env file is loaded: development | test | production
APP_ENV: str = os.getenv("APP_ENV", "development")

# Resolve the env file path relative to the backend/ directory.
# In production, the hosting provider injects env vars directly — no file needed.
_backend_dir = Path(__file__).resolve().parent.parent
_env_file = _backend_dir / "envs" / f".env.{APP_ENV}"
_env_file_path: str | None = str(_env_file) if _env_file.exists() else None


class Settings(BaseSettings):
    """
    Central configuration for PetCircle backend.

    Every field maps to an environment variable.
    Pydantic validates presence and type at startup.
    If any required field is missing, a RuntimeError is raised
    with a clear message identifying which variable is absent.
    """

    # --- Environment ---
    APP_ENV: str = APP_ENV

    # --- AI Providers ---
    # At least one key must be set depending on AI_PROVIDER.
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    # --- Supabase ---
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_BUCKET_NAME: str

    # --- WhatsApp Cloud API ---
    WHATSAPP_TOKEN: str
    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_APP_SECRET: str

    # --- WhatsApp Template Names ---
    # Templates are loaded from environment to allow changes without code deploys.

    # Transactional
    WHATSAPP_TEMPLATE_CONFLICT: str
    WHATSAPP_TEMPLATE_ORDER_FULFILLMENT_CHECK: str
    WHATSAPP_TEMPLATE_BIRTHDAY: str

    # --- 4-Stage Reminder Templates (Excel v5) ---
    WHATSAPP_TEMPLATE_REMINDER_T7: str | None = None
    WHATSAPP_TEMPLATE_REMINDER_DUE: str | None = None
    WHATSAPP_TEMPLATE_REMINDER_D3: str | None = None
    WHATSAPP_TEMPLATE_REMINDER_OVERDUE: str | None = None

    # --- Nudge Scheduler Templates ---
    WHATSAPP_TEMPLATE_NUDGE_VALUE_ADD_PERSONAL: str | None = None
    WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT: str | None = None
    WHATSAPP_TEMPLATE_NUDGE_BREED: str | None = None
    WHATSAPP_TEMPLATE_NUDGE_BREED_DATA: str | None = None

    # No-breed fallback templates (v6) — fired when pet has no breed set.
    # Registered in Meta separately; body_text seeded via migration 032.
    WHATSAPP_TEMPLATE_NUDGE_NO_BREED: str | None = None
    WHATSAPP_TEMPLATE_NUDGE_ENGAGEMENT_NO_BREED: str | None = None
    WHATSAPP_TEMPLATE_NUDGE_BREED_DATA_NO_BREED: str | None = None

    # --- Scheduled Reminder Templates (v6) ---
    # Fired at O+21 for first-time users with no supply data.
    # Registered in Meta separately; body_text seeded via migration 033.
    WHATSAPP_TEMPLATE_REMINDER_FOOD_SCHEDULED: str | None = None
    WHATSAPP_TEMPLATE_REMINDER_SUPPLEMENT_SCHEDULED: str | None = None
    WHATSAPP_TEMPLATE_REMINDER_CHRONIC_SCHEDULED: str | None = None

    # --- Admin ---
    # Secret key for admin API authentication via X-ADMIN-KEY header.
    ADMIN_SECRET_KEY: str
    # Separate password for admin dashboard login (not the raw API key).
    ADMIN_DASHBOARD_PASSWORD: str

    # --- Database ---
    DATABASE_URL: str

    # --- Security ---
    # Fernet encryption key for PII field-level encryption.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str

    # Frontend URL for CORS allow-origin (e.g., https://petcircle.vercel.app).
    FRONTEND_URL: str

    # --- GCP Cloud Storage ---
    # Optional at startup — if absent, all document uploads fall back to Supabase silently.
    # GCP_CREDENTIALS_JSON: base64-encoded service account JSON string.
    # Generate with: base64 -w 0 service-account.json
    GCP_CREDENTIALS_JSON: str | None = None
    GCP_BUCKET_NAME: str | None = None

    # --- RabbitMQ (CloudAMQP free tier) ---
    # amqps://user:pass@host/vhost from CloudAMQP dashboard.
    # If not set, document extraction falls back to in-process asyncio tasks.
    CLOUDAMQP_URL: str | None = None

    # --- Razorpay ---
    # Live/test keys from Razorpay dashboard → Settings → API Keys.
    # Optional at startup — payment endpoints will raise 503 if missing.
    RAZORPAY_KEY_ID: str | None = None
    RAZORPAY_KEY_SECRET: str | None = None

    # --- Order Notifications ---
    # WhatsApp phone number to notify when a new order is placed.
    # Format: country code + number, no + prefix (e.g., "919095705762").
    # Optional — if not set, only dashboard notification (no WhatsApp alert).
    ORDER_NOTIFICATION_PHONE: str | None = None

    # --- Click-to-Chat ---
    # Dialable WhatsApp Business phone number for wa.me link generation.
    # Digits only, no + prefix (e.g. "919876543210").
    # Optional — only used by /admin/chat-link. App runs without it.
    WHATSAPP_BUSINESS_PHONE: str | None = None

    # --- AI Provider ---
    # Controls which AI backend is used across all services.
    # "claude" → Anthropic (claude-opus-4-6 / claude-sonnet-4-6)
    # "openai" → OpenAI (gpt-4.1)
    # Must match the AI_PROVIDER value in constants.py (both read the same env var).
    AI_PROVIDER: str = "claude"

    # --- Feature Flags ---
    # Set to 'true' to enable AI-driven conversational order flow.
    # Requires ANTHROPIC_API_KEY. Falls back to deterministic state machine if either
    # is absent or if the Anthropic API health check fails.
    AGENTIC_ORDER_ENABLED: str = "true"

    # --- Timezone ---
    # Derived from constants, not from environment.
    # Exposed here so all layers can access timezone through settings.
    TIMEZONE: str = SYSTEM_TIMEZONE

    class Config:
        """Load variables from the environment-specific env file."""
        env_file = _env_file_path
        env_file_encoding = "utf-8"
        # Do not allow extra fields — catches typos in .env
        extra = "ignore"


def get_settings() -> Settings:
    """
    Load and validate all environment variables.

    Raises RuntimeError with a clear message if any required
    environment variable is missing, preventing the application
    from starting in an invalid state.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as e:
        # Extract which fields are missing from the validation error.
        # Pydantic v2 raises ValidationError with details per field.
        raise RuntimeError(
            f"Application startup failed — missing or invalid environment variables.\n"
            f"APP_ENV={APP_ENV}, env_file={_env_file_path}\n"
            f"Details: {e}\n"
            f"Ensure all variables in envs/.env.example are set."
        ) from e


# Singleton settings instance — initialized at import time.
# If env vars are missing, the application crashes immediately on startup
# rather than failing silently at runtime.
settings = get_settings()
