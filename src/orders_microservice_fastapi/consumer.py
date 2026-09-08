import asyncio
import json
import logging
import signal

from aiokafka import AIOKafkaConsumer

from orders_microservice_fastapi.settings import settings
from orders_microservice_fastapi.worker import celery

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

TOPIC_ORDERS = "orders"


async def run() -> None:
    consumer = AIOKafkaConsumer(
        TOPIC_ORDERS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="orders-bridge",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    log.info("consumer started")

    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stopping.set)

    try:
        while not stopping.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=100)
            for tp, messages in batch.items():
                for msg in messages:
                    try:
                        payload = json.loads(msg.value)
                    except json.JSONDecodeError:
                        log.exception("bad payload at %s:%s", tp, msg.offset)
                        continue

                    if payload.get("event") != "new_order":
                        continue

                    event_id = f"{tp.topic}:{tp.partition}:{msg.offset}"
                    await asyncio.to_thread(
                        celery.send_task,
                        "process_order",
                        kwargs={"order_id": payload["order_id"], "event_id": event_id},
                        queue="default",
                    )
                    log.info("enqueued order %s", payload["order_id"])

            if batch:
                await consumer.commit()
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(run())