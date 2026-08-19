import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.redis_compat import apply_redis_resp2
from app.core.logging import setup_logging
from app.routers import auth, accounts, contacts, opportunities, activities
from app.routers.admin import llm as admin_llm
from app.routers.admin import rag as admin_rag
from app.routers.admin import notify as admin_notify
from app.routers.writeback import router as writeback_router, pa_router
from app.routers.health import router as health_router, dashboard_router
from app.routers.copilot import router as copilot_router
from app.routers.audit import router as audit_router

setup_logging(level="INFO" if not settings.DEBUG else "DEBUG")
apply_redis_resp2()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sqlalchemy import text
    from app.db.session import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pass
    try:
        from sqlalchemy import select as sel
        from app.db.session import AsyncSessionLocal
        from app.models.llm_settings import LLMSettings
        from app.services.guard import apply_runtime_from_settings_row
        async with AsyncSessionLocal() as session:
            row = (await session.execute(sel(LLMSettings).limit(1))).scalar_one_or_none()
            apply_runtime_from_settings_row(row)
    except Exception:
        pass
    yield
    try:
        await engine.dispose()
    except Exception:
        pass


app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="AI-native B2B CRM — MontoCRM (Phase 2 / P5–P9)",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rate limit + security headers ─────────────────────────────────────────────

@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    from app.core.ratelimit import too_many
    path = request.url.path
    if settings.RATE_LIMIT_ENABLED:
        ip = request.client.host if request.client else "unknown"
        if path == "/auth/token" and request.method == "POST":
            if too_many(f"auth:{ip}", settings.RATE_LIMIT_AUTH_PER_MIN):
                return JSONResponse(status_code=429, content={"detail": "Too many login attempts"})
        if path == "/activities/extract" and request.method == "POST":
            auth = request.headers.get("authorization") or ip
            if too_many(f"extract:{auth[:48]}", settings.RATE_LIMIT_EXTRACT_PER_MIN):
                return JSONResponse(status_code=429, content={"detail": "Too many extract requests"})
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    latency = time.perf_counter() - t0
    try:
        from app.core.metrics import http_requests_total, http_latency_seconds
        path = request.url.path
        # Collapse UUIDs in path for label cardinality
        import re
        path_label = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}", path
        )
        http_requests_total.labels(
            method=request.method, path=path_label,
            status_code=response.status_code,
        ).inc()
        http_latency_seconds.labels(
            method=request.method, path=path_label,
        ).observe(latency)
    except Exception:
        pass
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(contacts.router)
app.include_router(opportunities.router)
app.include_router(activities.router)
app.include_router(admin_llm.router)
app.include_router(admin_rag.router)
app.include_router(admin_notify.router)
app.include_router(writeback_router)
app.include_router(pa_router)
app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(copilot_router)
app.include_router(audit_router)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": "2.0.0"}


@app.get("/health/ready", tags=["Health"])
async def health_ready():
    from app.db.session import engine
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"DB not ready: {e}")


# ── Prometheus metrics ────────────────────────────────────────────────────────

@app.get("/metrics", tags=["Observability"], include_in_schema=False)
async def metrics():
    from app.core.metrics import get_metrics_output
    return Response(
        content=get_metrics_output(),
        media_type="text/plain; version=0.0.4",
    )
