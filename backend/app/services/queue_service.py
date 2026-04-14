"""
PetCircle — RabbitMQ Queue Service

Manages the RabbitMQ connection (via CloudAMQP free tier) and provides
publisher functions for durable document processing jobs.

Queues:
    document.extract      — GPT extraction jobs from WhatsApp + dashboard uploads
    dashboard.precompute  — Dashboard cache-warming jobs after extraction

Connection uses aio-pika RobustConnection which auto-reconnects on network drops
or Render's free-tier sleep/wake cycles.

Falls back gracefully when CLOUDAMQP_URL is not configured (local dev without broker):
publish functions return False and callers use asyncio.create_task() directly.

Environment variables:
    CLOUDAMQP_URL   — amqps://user:pass@host/vhost (CloudAMQP free tier URL)
    RABBITMQ_URL    — alias accepted if CLOUDAMQP_URL is not set
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection

logger = logging.getLogger(__name__)

# Queue names — centralised here so consumer and publisher always agree.
QUEUE_DOCUMENT_EXTRACT = "document.extract"
QUEUE_DOCUMENT_EXTRACT_DLQ = "document.extract.dlq"
QUEUE_DASHBOARD_PRECOMPUTE = "dashboard.precompute"
EXCHANGE_DOCUMENT_DLX = "document.extract.dlx"

# Module-level connection handles (set by connect(), cleared by close()).
_connection: Optional[AbstractRobustConnection] = None
_channel: Optional[AbstractRobustChannel] = None


def _broker_url() -> Optional[str]:
    """
    Return the broker URL, or None if not configured.

    Checks os.environ first (set by hosting provider), then falls back to
    pydantic Settings which reads the env file (envs/.env.{APP_ENV}) in
    development/test environments.
    """
    url = os.environ.get("CLOUDAMQP_URL") or os.environ.get("RABBITMQ_URL")
    if url:
        return url
    try:
        from app.config import settings as _settings
        return _settings.CLOUDAMQP_URL
    except Exception:
        return None


async def connect() -> None:
    """
    Establish a robust RabbitMQ connection and declare queues/exchanges.

    Called once at FastAPI startup. Uses aio-pika RobustConnection which
    automatically reconnects after network drops or Render cold-starts.

    If no broker URL is set, logs a warning and skips (dev mode).
    Publish calls will return False and callers fall back to asyncio.create_task().
    """
    global _connection, _channel

    url = _broker_url()
    if not url:
        logger.warning(
            "[queue] CLOUDAMQP_URL not set — RabbitMQ disabled. "
            "Document jobs will use in-process asyncio fallback."
        )
        return

    try:
        _connection = await aio_pika.connect_robust(url)
        _channel = await _connection.channel()

        # Dead-letter exchange: extraction jobs that exhaust all retries land here.
        dlx = await _channel.declare_exchange(
            EXCHANGE_DOCUMENT_DLX, ExchangeType.DIRECT, durable=True
        )
        dlq = await _channel.declare_queue(QUEUE_DOCUMENT_EXTRACT_DLQ, durable=True)
        await dlq.bind(dlx, routing_key=QUEUE_DOCUMENT_EXTRACT_DLQ)

        # Main extraction queue — failed messages are routed to the DLX.
        await _channel.declare_queue(
            QUEUE_DOCUMENT_EXTRACT,
            durable=True,
            arguments={
                "x-dead-letter-exchange": EXCHANGE_DOCUMENT_DLX,
                "x-dead-letter-routing-key": QUEUE_DOCUMENT_EXTRACT_DLQ,
            },
        )

        # Precompute queue — fire-and-forget, no DLX required.
        await _channel.declare_queue(QUEUE_DASHBOARD_PRECOMPUTE, durable=True)

        logger.info("[queue] Connected to RabbitMQ. Queues ready.")
    except Exception as exc:
        logger.error("[queue] Failed to connect to RabbitMQ: %s", exc)
        _connection = None
        _channel = None


async def close() -> None:
    """Close the RabbitMQ connection on FastAPI shutdown."""
    global _connection, _channel
    if _connection and not _connection.is_closed:
        try:
            await _connection.close()
            logger.info("[queue] RabbitMQ connection closed.")
        except Exception as exc:
            logger.warning("[queue] Error closing RabbitMQ connection: %s", exc)
    _connection = None
    _channel = None


def is_connected() -> bool:
    """Return True if the channel is open and ready to publish."""
    return _channel is not None and _connection is not None and not _connection.is_closed


async def publish_extraction_job(
    pet_id: str,
    document_ids: list,
    user_id: str,
    from_number: Optional[str],
    pet_name: str,
    source: str = "whatsapp",
) -> bool:
    """
    Publish a document extraction job to the document.extract queue.

    Args:
        pet_id:        UUID string of the pet.
        document_ids:  List of Document UUID strings to extract.
        user_id:       UUID string of the owning user.
        from_number:   WhatsApp mobile number for reply messages (None = dashboard).
        pet_name:      Pet's display name (used in user-facing error messages).
        source:        'whatsapp' or 'dashboard'.

    Returns:
        True if published to RabbitMQ, False if queue unavailable (caller should fallback).
    """
    if not is_connected():
        return False

    payload = {
        "job_id": str(uuid.uuid4()),
        "pet_id": str(pet_id),
        "document_ids": [str(d) for d in document_ids],
        "user_id": str(user_id),
        "from_number": from_number,
        "pet_name": pet_name,
        "source": source,
        "attempt": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        message = Message(
            body=json.dumps(payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await _channel.default_exchange.publish(
            message, routing_key=QUEUE_DOCUMENT_EXTRACT
        )
        logger.info(
            "[queue] Published extraction job: job_id=%s, pet_id=%s, docs=%d, source=%s",
            payload["job_id"], pet_id, len(document_ids), source,
        )
        return True
    except Exception as exc:
        logger.error("[queue] Failed to publish extraction job: %s", exc)
        return False


async def publish_precompute_job(pet_id: str, user_id: str) -> bool:
    """
    Publish a dashboard precompute job to the dashboard.precompute queue.

    Args:
        pet_id:   UUID string of the pet.
        user_id:  UUID string of the owning user.

    Returns:
        True if published, False if queue unavailable (caller ignores — fire-and-forget).
    """
    if not is_connected():
        return False

    payload = {
        "job_id": str(uuid.uuid4()),
        "pet_id": str(pet_id),
        "user_id": str(user_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        message = Message(
            body=json.dumps(payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await _channel.default_exchange.publish(
            message, routing_key=QUEUE_DASHBOARD_PRECOMPUTE
        )
        logger.info("[queue] Published precompute job: pet_id=%s", pet_id)
        return True
    except Exception as exc:
        logger.error("[queue] Failed to publish precompute job: %s", exc)
        return False
