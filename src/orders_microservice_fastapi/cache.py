import json
import redis.asyncio as aioredis
from .settings import settings

redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

ORDER_TTL = 300


def order_key(order_id) -> str:
    return f"order:{order_id}"


async def cache_order(data: dict) -> None:
    await redis_client.setex(order_key(data["id"]), ORDER_TTL, json.dumps(data, default=str))


async def get_cached_order(order_id) -> dict | None:
    raw = await redis_client.get(order_key(order_id))
    return json.loads(raw) if raw else None


async def invalidate_order(order_id) -> None:
    await redis_client.delete(order_key(order_id))