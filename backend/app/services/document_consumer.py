"""
PetCircle — In-Process RabbitMQ Document Consumer

Runs as an asyncio background task inside the FastAPI process (same Render service).
Subscribes to CloudAMQP queues and processes document extraction and dashboard
precompute jobs without needing a separate Render background worker.

Queues:
    document.extract      — calls run_extraction_batch() from message_router
    dashboard.precompute  — calls precompute_dashboard_enrichments() from precompute_service

Concurrency:
    Both queues share RABBITMQ_PREFETCH_COUNT (default 4, clamped 1–5).
    Keeps at most that many batch jobs in-flight across each queue, limiting
    concurrent GPT API calls and memory pressure on Render's free tier (~512 MB RAM).

Retry policy (document.extract):
    Up to 3 attempts (tracked via "attempt" field in the job payload).
    On failure, republishes with attempt+1 after a 5s delay.
    After 3 failures: nack(requeue=False) → message lands in document.extract.dlq.

Precompute jobs:
    Fire-and-forget. Any failure is logged and nacked without retry.

Graceful shutdown:
    stop() sets an asyncio.Event that causes start_consuming() to exit cleanly.
    The in-flight message is allowed to complete before the consumer closes.
"""

import asyncio
import json
import logging
import os
from typing import Optional

import aio_pika
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractIncomingMessage

from app.services.queue_service import (
    QUEUE_DASHBOARD_PRECOMPUTE,
    QUEUE_DOCUMENT_EXTRACT,
    _broker_url,
)

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 5

_stop_event: Optional[asyncio.Event] = None
_consumer_task: Optional[asyncio.Task] = None


def _prefetch_count() -> int:
    """
    Read RABBITMQ_PREFETCH_COUNT from env, clamped to [1, 5].

    Default is 4 — a safe value for Render's free tier (512 MB RAM).
    Lower to 1–2 if memory pressure is observed during bulk extractions.
    """
    raw = os.environ.get("RABBITMQ_PREFETCH_COUNT", "4")
    try:
        return max(1, min(int(raw), 5))
    except ValueError:
        return 4


async def _handle_extraction_job(message: AbstractIncomingMessage) -> None:
    """
    Process one document extraction job from the document.extract queue.

    Calls run_extraction_batch() (defined in message_router) with the job payload.
    Acks on success. On failure, retries up to _MAX_ATTEMPTS by republishing
    the message with an incremented attempt counter, then nacks to DLQ.
    """
    from app.services.message_router import run_extraction_batch

    try:
        payload = json.loads(message.body.decode())
    except Exception as exc:
        logger.error("[consumer] Malformed extraction job body — discarding: %s", exc)
        await message.nack(requeue=False)
        return

    pet_id = payload.get("pet_id", "")
    document_ids = payload.get("document_ids", [])
    user_id = payload.get("user_id", "")
    from_number = payload.get("from_number")
    pet_name = payload.get("pet_name", "your pet")
    attempt = int(payload.get("attempt", 1))

    logger.info(
        "[consumer] Extraction job received: pet_id=%s, docs=%d, attempt=%d/%d",
        pet_id, len(document_ids), attempt, _MAX_ATTEMPTS,
    )

    try:
        await run_extraction_batch(
            pet_id=pet_id,
            document_ids=document_ids,
            user_id=user_id,
            from_number=from_number,
            pet_name=pet_name,
        )
        await message.ack()
        logger.info("[consumer] Extraction job done: pet_id=%s", pet_id)

    except Exception as exc:
        logger.error(
            "[consumer] Extraction job failed (attempt %d/%d): pet_id=%s, error=%s",
            attempt, _MAX_ATTEMPTS, pet_id, exc,
        )

        if attempt < _MAX_ATTEMPTS:
            # Republish with incremented attempt counter after a short back-off.
            # Ack the original so it doesn't re-enter the queue via requeue.
            await asyncio.sleep(_RETRY_DELAY_SECONDS)
            try:
                from app.services import queue_service as _qs
                payload["attempt"] = attempt + 1
                retry_msg = Message(
                    body=json.dumps(payload).encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    content_type="application/json",
                )
                if _qs._channel:
                    await _qs._channel.default_exchange.publish(
                        retry_msg, routing_key=QUEUE_DOCUMENT_EXTRACT
                    )
                    logger.info(
                        "[consumer] Retry published (attempt %d): pet_id=%s",
                        attempt + 1, pet_id,
                    )
                await message.ack()
            except Exception as retry_exc:
                logger.error("[consumer] Retry publish failed: %s", retry_exc)
                await message.nack(requeue=False)
        else:
            # All attempts exhausted — send to DLQ.
            logger.error(
                "[consumer] Max attempts reached — sending to DLQ: pet_id=%s", pet_id
            )
            await message.nack(requeue=False)


async def _handle_precompute_job(message: AbstractIncomingMessage) -> None:
    """
    Process one dashboard precompute job from the dashboard.precompute queue.

    Fire-and-forget: failures are logged and the message is nacked without retry.
    The dashboard always recalculates data on demand if the cache is cold.
    """
    from app.services.precompute_service import precompute_dashboard_enrichments

    try:
        payload = json.loads(message.body.decode())
    except Exception as exc:
        logger.error("[consumer] Malformed precompute job body — discarding: %s", exc)
        await message.nack(requeue=False)
        return

    pet_id = payload.get("pet_id", "")
    logger.info("[consumer] Precompute job received: pet_id=%s", pet_id)

    try:
        await precompute_dashboard_enrichments(str(pet_id))
        await message.ack()
        logger.info("[consumer] Precompute job done: pet_id=%s", pet_id)
    except Exception as exc:
        logger.error(
            "[consumer] Precompute job failed: pet_id=%s, error=%s", pet_id, exc
        )
        await message.nack(requeue=False)


async def start_consuming() -> None:
    """
    Start the in-process RabbitMQ consumer as a background asyncio task.

    Opens a dedicated connection (separate from the publisher channel so
    prefetch settings don't interfere with publishing), subscribes to both
    queues, and blocks on _stop_event until FastAPI shuts down.

    If CLOUDAMQP_URL is not set, exits immediately without error.
    """
    global _stop_event

    url = _broker_url()
    if not url:
        logger.info("[consumer] No broker URL — consumer not started.")
        return

    _stop_event = asyncio.Event()
    prefetch = _prefetch_count()

    connection = None
    try:
        # Separate connection from the publisher so QoS settings are isolated.
        connection = await aio_pika.connect_robust(url)

        # Both channels share the same prefetch count from RABBITMQ_PREFETCH_COUNT.
        extract_channel = await connection.channel()
        await extract_channel.set_qos(prefetch_count=prefetch)

        precompute_channel = await connection.channel()
        await precompute_channel.set_qos(prefetch_count=prefetch)

        # passive=True: queues were already declared by queue_service.connect().
        extract_queue = await extract_channel.declare_queue(
            QUEUE_DOCUMENT_EXTRACT, durable=True, passive=True
        )
        precompute_queue = await precompute_channel.declare_queue(
            QUEUE_DASHBOARD_PRECOMPUTE, durable=True, passive=True
        )

        await extract_queue.consume(_handle_extraction_job)
        await precompute_queue.consume(_handle_precompute_job)

        logger.info(
            "[consumer] Listening on %s and %s (prefetch=%d)",
            QUEUE_DOCUMENT_EXTRACT, QUEUE_DASHBOARD_PRECOMPUTE, prefetch,
        )

        # Block here until stop() is called during FastAPI shutdown.
        await _stop_event.wait()

        logger.info("[consumer] Shutdown signal received — closing consumer connection.")
        await connection.close()

    except asyncio.CancelledError:
        # Task was cancelled during shutdown (e.g. Render redeploy).
        # Close the connection if it was established before yielding cancellation.
        logger.info("[consumer] Consumer task cancelled — shutting down gracefully.")
        if connection and not connection.is_closed:
            try:
                await connection.close()
            except Exception:
                pass
        raise

    except Exception as exc:
        logger.error("[consumer] Consumer crashed: %s", exc, exc_info=True)


def stop() -> None:
    """
    Signal the consumer to stop cleanly.

    Called during FastAPI shutdown (lifespan shutdown hook).
    Sets the stop event (for a running consumer) and cancels the task
    (handles the case where the consumer is still connecting).
    """
    if _stop_event and not _stop_event.is_set():
        _stop_event.set()
        logger.info("[consumer] Stop signal sent.")
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        logger.info("[consumer] Consumer task cancelled.")
