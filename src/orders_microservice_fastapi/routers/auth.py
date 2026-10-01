"""Регистрация пользователей и выдача JWT."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import User
from ..schemas import Token, UserCreate, UserOut
from ..security import create_access_token, hash_password_async, verify_password_async

router = APIRouter(tags=["auth"])


@router.post("/register/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: AsyncSession = Depends(get_session)):
    """Зарегистрировать пользователя. 409, если email уже занят."""
    user = User(
        email=payload.email.lower(),
        password_hash=await hash_password_async(payload.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    await session.refresh(user)
    return user


@router.post("/token/", response_model=Token)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """Получить JWT (OAuth2 Password Flow: `username` — это email)."""
    result = await session.execute(select(User).where(User.email == form.username.lower()))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not await verify_password_async(
        form.password, user.password_hash
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))
