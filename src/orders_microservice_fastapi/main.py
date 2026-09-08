from fastapi import FastAPI
from .routers import auth, orders

app = FastAPI(title="Orders")
app.include_router(auth.router)
app.include_router(orders.router)


@app.get("/health")
async def health():
    return {"status": "ok"}