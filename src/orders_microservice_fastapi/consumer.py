"""Kafka consumer: читает события `new_order` и запускает фоновую задачу в Celery."""
import asyncio
import json
import logging
import signal

from aiokafka import AIOKafkaConsumer

from .settings import settings
from .worker import celery

log = logging.getLogger(__name__)


async def run() -> None:
    consumer = AIOKafkaConsumer(
        settings.kafka_topic_orders,
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
                    await handle_message(tp.topic, tp.partition, msg)

            if batch:
                await consumer.commit()
    finally:
        await consumer.stop()


async def handle_message(topic: str, partition: int, msg) -> None:
    """Обработать одно сообщение; некорректные пропускаем, чтобы не блокировать партицию."""
    try:
        payload = json.loads(msg.value)
    except json.JSONDecodeError:
        log.exception("bad payload at %s:%s:%s", topic, partition, msg.offset)
        return

    if payload.get("event") != "new_order" or "order_id" not in payload:
        return

    event_id = f"{topic}:{partition}:{msg.offset}"
    await asyncio.to_thread(
        celery.send_task,
        "process_order",
        kwargs={"order_id": payload["order_id"], "event_id": event_id},
        queue="default",
    )
    log.info("enqueued order %s", payload["order_id"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
