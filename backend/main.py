"""
Entry point FastAPI — Bomtempo Intelligence Backend
"""

import asyncio
from contextlib import asynccontextmanager

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.config import Config

# Sync interval: 10 minutes (600s). Adjust here for all platforms.
INVERSOR_SYNC_INTERVAL = 600


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.routers.inversores import run_periodic_sync
    sync_task = asyncio.create_task(run_periodic_sync(INVERSOR_SYNC_INTERVAL))
    yield
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Bomtempo Intelligence API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in Config.CORS_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# ── Routers (registrados dinamicamente conforme são criados) ───────────────────
# Descomentar cada linha à medida que o router for implementado:

from backend.routers import auth  # noqa: E402
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

from backend.routers import dashboard  # noqa: E402
app.include_router(dashboard.router)

from backend.routers import hub  # noqa: E402
app.include_router(hub.router)

from backend.routers import financeiro  # noqa: E402
app.include_router(financeiro.router)

from backend.routers import rdo  # noqa: E402
app.include_router(rdo.router)

from backend.routers import alertas  # noqa: E402
app.include_router(alertas.router)

from backend.routers import usuarios  # noqa: E402
app.include_router(usuarios.router)

from backend.routers import master  # noqa: E402
app.include_router(master.router)

from backend.routers import reembolso  # noqa: E402
app.include_router(reembolso.router)

from backend.routers import relatorios  # noqa: E402
app.include_router(relatorios.router)

from backend.routers import om  # noqa: E402
app.include_router(om.router)

from backend.routers import inversores  # noqa: E402
app.include_router(inversores.router)

from backend.routers import observabilidade  # noqa: E402
app.include_router(observabilidade.router)

from backend.routers import ai  # noqa: E402
app.include_router(ai.router)

from backend.routers import maintenance  # noqa: E402
app.include_router(maintenance.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# Serve uploaded files (timeline attachments)
_uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(_uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")
