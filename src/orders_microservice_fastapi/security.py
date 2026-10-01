"""Хеширование паролей (bcrypt) и JWT."""
import asyncio
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .settings import settings

JWT_ALGORITHM = "HS256"


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    return bcrypt.checkpw(raw.encode(), hashed.encode())


async def hash_password_async(raw: str) -> str:
    """bcrypt — CPU-bound, не блокируем event loop."""
    return await asyncio.to_thread(hash_password, raw)


async def verify_password_async(raw: str, hashed: str) -> bool:
    return await asyncio.to_thread(verify_password, raw, hashed)


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    return int(payload["sub"])
