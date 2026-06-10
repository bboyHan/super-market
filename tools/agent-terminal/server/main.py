"""Agent Terminal - FastAPI backend entry point.

Credential collection workstation for Super Market platform.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from config import settings
from storage.db import init_db, get_recent_logs, add_log
from services import task_manager
from routers import tasks, inventory, accounts, platform, system, collector

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(settings.APP_NAME)

# --- Application lifespan ---
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Set PLAYWRIGHT_BROWSERS_PATH for browser automation
    if settings.PLAYWRIGHT_BROWSERS_PATH:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = settings.PLAYWRIGHT_BROWSERS_PATH

    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} starting up...")
    init_db()
    add_log("info", "system", f"{settings.APP_NAME} v{settings.APP_VERSION} started on {settings.HOST}:{settings.PORT}")

    # Start background health check loop
    bg_tasks = []

    async def periodic_log_cleanup():
        """Periodically clean up old logs (keep last 10000)."""
        while True:
            await asyncio.sleep(3600)  # Every hour
            from storage.db import get_cursor
            with get_cursor() as cursor:
                cursor.execute("""
                    DELETE FROM logs WHERE id NOT IN (
                        SELECT id FROM logs ORDER BY id DESC LIMIT 10000
                    )
                """)

    cleanup_task = asyncio.create_task(periodic_log_cleanup())
    bg_tasks.append(cleanup_task)

    yield

    # Shutdown
    logger.info(f"{settings.APP_NAME} shutting down...")
    for t in bg_tasks:
        t.cancel()
    await asyncio.gather(*bg_tasks, return_exceptions=True)
    add_log("info", "system", f"{settings.APP_NAME} stopped")


# --- FastAPI app creation ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# --- CORS middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:8800",
        "http://127.0.0.1:8800",
    ],
    allow_origin_regex=r"https?://localhost(:\d+)?.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mount routers ---
app.include_router(tasks.router)
app.include_router(inventory.router)
app.include_router(accounts.router)
app.include_router(platform.router)
app.include_router(system.router)
app.include_router(collector.router)


# --- SSE log streaming ---
@app.get("/api/sse/logs")
async def stream_logs(request: Request):
    """SSE endpoint that streams log entries to connected clients."""

    async def event_generator() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue = asyncio.Queue()
        task_manager._sse_queues.append(queue)

        try:
            # Send initial recent logs
            recent_logs = get_recent_logs(limit=50)
            for log_entry in reversed(recent_logs):
                data = json.dumps({
                    "id": log_entry["id"],
                    "level": log_entry["level"],
                    "source": log_entry["source"],
                    "message": log_entry["message"],
                    "created_at": log_entry["created_at"],
                })
                yield f"data: {data}\n\n"

            # Send heartbeat
            yield f"data: {json.dumps({'type': 'heartbeat', 'time': datetime.utcnow().isoformat() + 'Z'})}\n\n"

            # Stream new events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    data = json.dumps(event)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

        finally:
            # Clean up queue on disconnect
            if queue in task_manager._sse_queues:
                task_manager._sse_queues.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Health endpoint ---
@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    uptime = time.time() - _start_time
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "uptime_seconds": uptime,
        "active_tasks": task_manager.get_active_count(),
    }


# --- Global exception handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a 500 response."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


# --- Main entry point ---
def main():
    """Run the application with uvicorn."""
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
