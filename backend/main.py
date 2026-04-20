"""
Entry point FastAPI — Bomtempo Intelligence Backend
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.core.config import Config




@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown


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
    allow_methods=["*"],
    allow_headers=["*"],
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

from backend.routers import observabilidade  # noqa: E402
app.include_router(observabilidade.router)

from backend.routers import ai  # noqa: E402
app.include_router(ai.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
