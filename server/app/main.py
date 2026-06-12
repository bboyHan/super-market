from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.shared.exceptions.handlers import register_exception_handlers


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan: startup / shutdown."""
        logger.info("Starting {} v{}", settings.APP_NAME, settings.APP_VERSION)
        # ── startup ──────────────────────────────────────
        await startup(app)
        # Start callback worker
        from app.infrastructure.callback.worker import start_worker
        from app.infrastructure.persistence.postgres.session import async_session_factory
        callback_task = start_worker(async_session_factory)
        # Start blockchain monitor (now using httpx async)
        from app.infrastructure.blockchain.monitor import start_monitor
        asyncio.create_task(start_monitor())
        # Start order worker (auto-cancel expired + Redis counters)
        from app.worker.order_worker import start_order_worker
        asyncio.create_task(start_order_worker())
        # Start stats aggregation worker
        from app.worker.stats_worker import start_stats_worker
        asyncio.create_task(start_stats_worker())
        yield
        # ── shutdown ─────────────────────────────────────
        callback_task.cancel()
        try:
            await callback_task
        except asyncio.CancelledError:
            pass
        await shutdown(app)
        logger.info("{} stopped", settings.APP_NAME)

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── exception handlers ───────────────────────────────
    register_exception_handlers(app)

    # ── routers ──────────────────────────────────────────
    from app.interfaces.api.merchant.router import router as merchant_router
    from app.interfaces.api.admin.router import router as admin_router
    from app.interfaces.api.open.router import router as open_router
    from app.interfaces.api.terminal.router import router as terminal_router
    from app.interfaces.api.auth.router import router as auth_router
    from app.interfaces.ws.terminal import terminal_ws_handler

    app.include_router(auth_router)
    app.include_router(merchant_router)
    app.include_router(admin_router)
    app.include_router(open_router)
    app.include_router(terminal_router)

    # ── WebSocket ────────────────────────────────────────
    app.add_api_websocket_route("/ws/terminal/{agent_id}", terminal_ws_handler)

    # ── health ───────────────────────────────────────────
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    return app


async def startup(app: FastAPI) -> None:
    """Initialize connections and services on startup."""
    from app.infrastructure.persistence.postgres.session import init_db

    await init_db()


async def shutdown(app: FastAPI) -> None:
    """Gracefully close connections on shutdown."""
    from app.infrastructure.persistence.postgres.session import close_db

    await close_db()


app = create_app()
