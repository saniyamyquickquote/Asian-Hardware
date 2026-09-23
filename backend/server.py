import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).parent / ".env")

from core import client, bootstrap  # noqa: E402
from api_auth import router as auth_router  # noqa: E402
from api_inventory import router as inventory_router  # noqa: E402
from api_sales import router as sales_router  # noqa: E402

app = FastAPI(title="Asian Hardware and Paints")
# The storefront and API are served from the same origin. Enable credentialed
# cross-origin requests only for explicit, configured origins—not a wildcard.
allowed_origins = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",")
                   if origin.strip() and origin.strip() != "*"]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(auth_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")
app.include_router(sales_router, prefix="/api")


@app.on_event("startup")
async def on_startup():
    await bootstrap()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


logging.basicConfig(level=logging.INFO)