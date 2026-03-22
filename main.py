"""Claudius AI Vending Machine — FastAPI entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.products import router as products_router
from api.checkout import router as checkout_router
from api.webhook import router as webhook_router
from api.admin import router as admin_router
from api.requests import router as requests_router
from api.scenario import router as scenario_router
from api.websocket import router as ws_router
from db import init_db
from config_app import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("Claudius starting up — environment=%s", settings.environment)
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Claudius shutting down")


app = FastAPI(
    title="Claudius AI Vending Machine",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Mount API routers ---
app.include_router(products_router, prefix="/api", tags=["products"])
app.include_router(checkout_router, prefix="/api", tags=["checkout"])
app.include_router(webhook_router, prefix="/api", tags=["webhook"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(requests_router, prefix="/api", tags=["requests"])
app.include_router(scenario_router, prefix="/api", tags=["scenario"])
app.include_router(ws_router, tags=["websocket"])


@app.get("/api/status")
async def machine_status():
    """Quick health check and machine status."""
    return {
        "status": "online",
        "version": "0.1.0",
        "environment": settings.environment,
    }
