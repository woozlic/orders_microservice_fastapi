import time
from orders_microservice_fastapi.worker import celery


@celery.task(name="process_order")
def process_order(order_id: str, event_id: str | None = None) -> str:
    time.sleep(2)
    print(f"Order {order_id} processed", flush=True)
    return order_id