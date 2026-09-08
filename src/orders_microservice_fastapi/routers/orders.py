import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orders_microservice_fastapi.cache import cache_order, get_cached_order, invalidate_order
from orders_microservice_fastapi.db import get_session
from orders_microservice_fastapi.deps import get_current_user
from orders_microservice_fastapi.models import Order, OrderStatus, User
from orders_microservice_fastapi.schemas import OrderCreate, OrderOut, OrderStatusUpdate
from orders_microservice_fastapi.worker import celery

router = APIRouter(prefix="/orders", tags=["orders"])

ALLOWED_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELED},
    OrderStatus.SHIPPED: set(),
    OrderStatus.CANCELED: set(),
}


@router.post("/", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
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

    celery.send_task("process_order", kwargs={"order_id": str(order.id)}, queue="default")
    return order


@router.get("/{order_id}/", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    cached = await get_cached_order(order_id)
    if cached:
        if cached["user_id"] != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
        return OrderOut(**cached)

    order = await session.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

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
    order = await session.get(Order, order_id, with_for_update=True)
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

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
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    result = await session.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    )
    return list(result.scalars().all())