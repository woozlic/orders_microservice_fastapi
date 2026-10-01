"""Эндпоинты заказов."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import cache_order, get_cached_order
from ..db import get_session
from ..deps import get_current_user
from ..models import Order, OrderStatus, User
from ..producer import publish_new_order
from ..schemas import OrderCreate, OrderOut, OrderStatusUpdate

log = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])

# Допустимые переходы статусов заказа.
ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELED},
    OrderStatus.SHIPPED: set(),
    OrderStatus.CANCELED: set(),
}


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Создать заказ и опубликовать событие `new_order` в Kafka."""
    total = sum(i.price * i.qty for i in payload.items)
    order = Order(
        user_id=user.id,
        items=[i.model_dump(mode="json") for i in payload.items],
        total_price=total,
        status=OrderStatus.PENDING,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    # Заказ уже сохранён: сбой брокера не должен превращаться в 500 для клиента.
    try:
        await publish_new_order(order)
    except Exception:
        log.exception("failed to publish new_order for %s", order.id)
    return order


@router.get("/{order_id}/", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Получить заказ: сначала из Redis, при промахе — из БД с записью в кеш."""
    cached = await get_cached_order(order_id)
    if cached:
        if cached["user_id"] != user.id:
            raise _not_found()
        return OrderOut(**cached)

    order = await session.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise _not_found()

    data = OrderOut.model_validate(order)
    await cache_order(data.model_dump(mode="json"))
    return data


@router.patch("/{order_id}/", response_model=OrderOut)
async def update_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Изменить статус заказа и обновить кеш. 409 при недопустимом переходе."""
    order = await session.get(Order, order_id, with_for_update=True)
    if order is None or order.user_id != user.id:
        raise _not_found()

    if payload.status not in ALLOWED_TRANSITIONS[order.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot move from {order.status.value} to {payload.status.value}",
        )

    order.status = payload.status
    await session.commit()
    await session.refresh(order)

    data = OrderOut.model_validate(order)
    await cache_order(data.model_dump(mode="json"))
    return data


@router.get("/user/{user_id}/", response_model=list[OrderOut])
async def list_user_orders(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Список заказов пользователя (только собственные), новые первыми."""
    if user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    result = await session.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
