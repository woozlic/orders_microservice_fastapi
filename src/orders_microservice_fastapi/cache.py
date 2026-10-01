"""Кеш заказов в Redis (TTL 5 минут). Недоступность Redis не ломает API — идём в БД."""
import json
import logging

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from .settings import settings

log = logging.getLogger(__name__)

redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

ORDER_TTL = 300  # секунд (5 минут), см. ТЗ п. 2.4


def order_key(order_id) -> str:
    return f"order:{order_id}"


async def cache_order(data: dict) -> None:
    """Записать (или обновить) заказ в кеше."""
    try:
        await redis_client.setex(order_key(data["id"]), ORDER_TTL, json.dumps(data, default=str))
    except RedisError:
        log.exception("failed to cache order %s", data.get("id"))


async def get_cached_order(order_id) -> dict | None:
    """Вернуть заказ из кеша или None, если его там нет / Redis недоступен."""
    try:
        raw = await redis_client.get(order_key(order_id))
    except RedisError:
        log.exception("failed to read order %s from cache", order_id)
        return None
    return json.loads(raw) if raw else None
