"""
RabbitMQ Queue Connectivity Test

Verifies that the CloudAMQP connection is working correctly:
    1. Connects to the broker using CLOUDAMQP_URL
    2. Publishes a test extraction job to document.extract
    3. Publishes a test precompute job to dashboard.precompute
    4. Consumes both messages back (round-trip confirmation)
    5. Reports queue stats

Does NOT require a database, OpenAI key, or WhatsApp — purely tests
the queue infrastructure.

Usage:
    cd backend
    set APP_ENV=production
    python -m tests.test_queue_connection
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APP_ENV", "production")


async def main():
    from app.services import queue_service
    from app.services.queue_service import (
        QUEUE_DASHBOARD_PRECOMPUTE,
        QUEUE_DOCUMENT_EXTRACT,
        _broker_url,
    )

    url = _broker_url()
    if not url:
        print("FAIL: CLOUDAMQP_URL is not set in the environment.")
        return

    masked = url[:30] + "..." if len(url) > 30 else url
    print(f"\n{'='*60}")
    print(f"RabbitMQ Queue Connectivity Test")
    print(f"{'='*60}")
    print(f"Broker: {masked}")

    # --- Step 1: Connect ---
    print("\n[1/4] Connecting to CloudAMQP...")
    await queue_service.connect()

    if not queue_service.is_connected():
        print("FAIL: Could not establish connection to RabbitMQ.")
        print("      Check CLOUDAMQP_URL and that the CloudAMQP instance is running.")
        return

    print("  OK — Connected. Queues declared.")

    # --- Step 2: Publish jobs ---
    print("\n[2/4] Publishing test jobs...")

    t0 = time.monotonic()
    ok1 = await queue_service.publish_extraction_job(
        pet_id="00000000-0000-0000-0000-000000000001",
        document_ids=["00000000-0000-0000-0000-000000000002"],
        user_id="00000000-0000-0000-0000-000000000003",
        from_number=None,
        pet_name="TestPet",
        source="test",
    )
    ok2 = await queue_service.publish_precompute_job(
        pet_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000003",
    )
    publish_ms = (time.monotonic() - t0) * 1000

    if ok1 and ok2:
        print(f"  OK — Both jobs published in {publish_ms:.0f}ms")
    else:
        print(f"  FAIL — extraction publish={ok1}, precompute publish={ok2}")

    # --- Step 3: Consume messages back (round-trip) ---
    print("\n[3/4] Consuming messages back (round-trip check)...")

    import aio_pika

    received = {"extract": None, "precompute": None}
    done_event = asyncio.Event()

    async def _consume():
        conn = await aio_pika.connect_robust(url)
        ch = await conn.channel()

        extract_q = await ch.declare_queue(QUEUE_DOCUMENT_EXTRACT, durable=True, passive=True)
        precompute_q = await ch.declare_queue(QUEUE_DASHBOARD_PRECOMPUTE, durable=True, passive=True)

        async def on_extract(msg):
            async with msg.process():
                received["extract"] = json.loads(msg.body.decode())
            if received["extract"] and received["precompute"]:
                done_event.set()

        async def on_precompute(msg):
            async with msg.process():
                received["precompute"] = json.loads(msg.body.decode())
            if received["extract"] and received["precompute"]:
                done_event.set()

        await extract_q.consume(on_extract)
        await precompute_q.consume(on_precompute)

        try:
            await asyncio.wait_for(done_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass
        finally:
            await conn.close()

    t0 = time.monotonic()
    await _consume()
    consume_ms = (time.monotonic() - t0) * 1000

    if received["extract"]:
        job = received["extract"]
        print(f"  OK — document.extract received in {consume_ms:.0f}ms")
        print(f"       job_id={job.get('job_id')}, source={job.get('source')}, "
              f"docs={len(job.get('document_ids', []))}")
    else:
        print("  FAIL — No message received from document.extract within 10s")

    if received["precompute"]:
        job = received["precompute"]
        print(f"  OK — dashboard.precompute received")
        print(f"       job_id={job.get('job_id')}, pet_id={job.get('pet_id')}")
    else:
        print("  FAIL — No message received from dashboard.precompute within 10s")

    # --- Step 4: Close ---
    print("\n[4/4] Closing connection...")
    await queue_service.close()
    print("  OK — Connection closed cleanly.")

    # --- Summary ---
    print(f"\n{'='*60}")
    all_ok = ok1 and ok2 and bool(received["extract"]) and bool(received["precompute"])
    if all_ok:
        print("RESULT: ALL CHECKS PASSED")
        print("        CloudAMQP is wired up correctly.")
        print("        Start the API and document uploads will flow through the queue.")
    else:
        print("RESULT: SOME CHECKS FAILED — review errors above.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
