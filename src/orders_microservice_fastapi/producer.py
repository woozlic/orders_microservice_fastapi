"""Публикация событий заказов в Kafka (event-bus)."""
import json

from aiokafka import AIOKafkaProducer

from .settings import settings

_producer: AIOKafkaProducer | None = None


async def start_producer() -> None:
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, default=str).encode(),
        acks="all",
        enable_idempotence=True,
    )
    await _producer.start()


async def stop_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None


async def publish_new_order(order) -> None:
    """Опубликовать событие `new_order` для созданного заказа."""
    if _producer is None:
        raise RuntimeError("Kafka producer is not started")
    await _producer.send_and_wait(
        settings.kafka_topic_orders,
        key=str(order.user_id).encode(),
        value={
            "event": "new_order",
            "order_id": str(order.id),
            "user_id": order.user_id,
            "total_price": str(order.total_price),
            "created_at": order.created_at,
        },
    )
