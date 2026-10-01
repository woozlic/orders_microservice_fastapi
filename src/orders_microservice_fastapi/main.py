"""Точка входа FastAPI-приложения."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .producer import start_producer, stop_producer
from .rate_limit import rate_limit_middleware
from .routers import auth, orders
from .settings import settings

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_producer()
    yield
    await stop_producer()


app = FastAPI(
    title="Orders",
    description="Сервис управления заказами: JWT, Kafka, Redis-кеш, Celery.",
    lifespan=lifespan,
)

app.middleware("http")(rate_limit_middleware)
# CORS добавляется последним, т.е. является внешним слоем: заголовки получают и ответы 429.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(orders.router)
