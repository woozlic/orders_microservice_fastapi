"""Rate limiting: фиксированное окно на клиента (IP), счётчики хранятся в Redis."""
import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from .cache import redis_client
from .settings import settings

log = logging.getLogger(__name__)


async def rate_limit_middleware(request: Request, call_next):
    """Отвечает 429, если клиент превысил лимит запросов в текущем окне."""
    if request.method == "OPTIONS":  # CORS preflight не считаем
        return await call_next(request)

    window = settings.rate_limit_window_seconds
    now = int(time.time())
    client = request.client.host if request.client else "unknown"
    key = f"ratelimit:{client}:{now // window}"

    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window)
            count, _ = await pipe.execute()
    except RedisError:
        log.exception("rate limiter unavailable, skipping")
        return await call_next(request)

    if count > settings.rate_limit_requests:
        retry_after = window - now % window
        return JSONResponse(
            {"detail": "Too many requests"},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)
