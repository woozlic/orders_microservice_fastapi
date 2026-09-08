from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field
import uuid
from datetime import datetime
from .models import OrderStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrderItem(BaseModel):
    sku: str
    qty: int = Field(gt=0)
    price: Decimal = Field(gt=0)


class OrderCreate(BaseModel):
    items: list[OrderItem] = Field(min_length=1)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: int
    items: list[OrderItem]
    total_price: Decimal
    status: OrderStatus
    created_at: datetime