from contextlib import asynccontextmanager
from fastapi import FastAPI

from orders_microservice_fastapi.producer import start_producer, stop_producer
from orders_microservice_fastapi.routers import auth, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_producer()
    yield
    await stop_producer()


app = FastAPI(title="Orders", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(orders.router)