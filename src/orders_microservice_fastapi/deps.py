import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import User
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    creds_error = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_token(token)
    except jwt.PyJWTError:
        raise creds_error

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise creds_error
    return user