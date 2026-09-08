import json
from aiokafka import AIOKafkaProducer

from orders_microservice_fastapi.settings import settings

TOPIC_ORDERS = "orders"

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
    if _producer:
        await _producer.stop()


async def publish_new_order(order) -> None:
    await _producer.send_and_wait(
        TOPIC_ORDERS,
        key=str(order.user_id).encode(),
        value={
            "event": "new_order",
            "order_id": str(order.id),
            "user_id": order.user_id,
            "total_price": str(order.total_price),
            "created_at": order.created_at,
        },
    )