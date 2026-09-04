"""
app/main.py — Application Entrypoint
=====================================

WHY THIS FILE EXISTS:
  This is where the FastAPI application object (`app`) is created and
  configured. Think of it as the "assembly point" — it doesn't define
  business logic itself; it just wires everything together.

  On startup, Uvicorn (the ASGI server) imports this file and calls the
  ASGI interface on `app` to handle incoming HTTP requests.

INTERVIEW TALKING POINT:
  "FastAPI is an ASGI framework. ASGI (Async Server Gateway Interface)
  is the async successor to WSGI. Uvicorn runs the event loop and
  forwards requests to FastAPI's request handler."
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db

# ── Lifespan (startup/shutdown events) ───────────────────────────────────────
# The `lifespan` context manager replaces the old @app.on_event("startup")
# pattern (deprecated in newer FastAPI). Code before `yield` runs on startup;
# code after `yield` runs on shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    # Good place to: warm caches, start background schedulers, verify DB
    # connectivity, etc.
    print(f"🚀 Starting {settings.APP_NAME} [{settings.APP_ENV}]")

    # ── Start APScheduler ─────────────────────────────────────────────────────
    # WHY HERE (not at module level)?
    #   The scheduler must start *after* the asyncio event loop is running.
    #   The lifespan context manager is called by FastAPI once the event loop
    #   is active — so this is the correct place. Starting it at module
    #   import time would race against the event loop setup.
    #
    # INTERVIEW TALKING POINT:
    #   "APScheduler's AsyncIOScheduler reuses FastAPI's existing event loop.
    #   I start it in the lifespan context manager so it starts after the
    #   app is ready and shuts down cleanly with the app — no orphaned threads
    #   or unclosed sessions."
    from app.core.scheduler import scheduler, check_expiring_listings  # noqa: E402
    from app.routers.listings import expire_stale_listings  # noqa: E402

    # Register the auto-expiry job — runs every minute to mark past-due listings as EXPIRED.
    scheduler.add_job(
        expire_stale_listings,
        trigger="interval",
        minutes=1,
        id="expire_stale_listings",
        replace_existing=True,
    )

    # Register the expiry warning job — runs every 15 minutes.
    # `id` is required for deduplication (APScheduler won't add duplicates
    # if the lifespan is somehow called twice). `replace_existing=True` ensures
    # a clean re-registration if the app hot-reloads in dev.
    scheduler.add_job(
        check_expiring_listings,
        trigger="interval",
        minutes=15,
        id="check_expiring_listings",
        replace_existing=True,
    )
    scheduler.start()
    print("🕐 APScheduler started — auto-expiring past-due listings (1m) & checking expiry warnings (15m)")

    # Create database tables if they do not exist
    from app.db.database import engine  # noqa: E402
    from app.db.base import Base  # noqa: E402
    import app.models  # noqa: E402
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✨ Database tables created/verified")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    # Shut down the scheduler cleanly: wait for the current running job (if any)
    # to finish before the process exits. `wait=True` (default) is the safe choice
    # — it avoids killing a job mid-DB-write.
    scheduler.shutdown(wait=True)
    print("👋 Shutting down...")


# ── Create the FastAPI app ────────────────────────────────────────────────────
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title=settings.APP_NAME,
    description="A platform connecting food donors with receivers to reduce food waste.",
    version="0.1.0",
    # Disable interactive docs in production — they expose your API surface
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
cors_origins = [o for o in settings.CORS_ORIGINS if o != "*"]
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
allowed_origins = list(set(cors_origins + default_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static Files & SPA Mounting ───────────────────────────────────────────────
import os
from fastapi.responses import FileResponse

# Serves legacy Jinja2 static assets inside app/static/ at /static
if os.path.exists("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

# If compiled React SPA exists (frontend/dist), serve assets and fallback to index.html
if os.path.exists("frontend/dist"):
    if os.path.exists("frontend/dist/assets"):
        app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="react_assets")

    @app.get("/app/{full_path:path}", include_in_schema=False)
    async def serve_spa_route(full_path: str):
        file_path = os.path.join("frontend/dist", full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse("frontend/dist/index.html")

    @app.get("/app", include_in_schema=False)
    async def serve_spa_root():
        return FileResponse("frontend/dist/index.html")


# ── Register Routers ──────────────────────────────────────────────────────────
# The `prefix` is prepended to every route in that router.
# The `tags` group endpoints in the /docs UI.
from app.routers import auth  # noqa: E402
from app.routers import listings  # noqa: E402
from app.routers import notifications  # noqa: E402
from app.routers import admin  # noqa: E402  # Phase 6: analytics dashboard
from app.routers import chat  # noqa: E402
from app.routers import pages  # noqa: E402  # Phase 7: Jinja2 HTML pages

app.include_router(auth.router,          prefix="/auth",          tags=["Auth"])
app.include_router(listings.router,      prefix="/listings",      tags=["Listings"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(admin.router,         prefix="/admin",         tags=["Admin"])
app.include_router(chat.router,          prefix="/chat",          tags=["Chat"])
app.include_router(pages.router,                                  tags=["Pages"])

# ── Register Jinja2 custom filters ────────────────────────────────────────────
# Jinja2's built-in filters don't include `zip` (Python's built-in zip()).
# We add it here as a global filter so templates can do:
#   {% for label, count in labels | zip(counts) %}
# This avoids the need for an index variable and keeps templates readable.
admin.templates.env.filters["zip"] = zip



# ── Health Check ──────────────────────────────────────────────────────────────
# Comprehensive endpoint used by load balancers and uptime monitors (e.g., Render, Better Stack).
# Verifies that both the web process and the underlying database connection pool are active.
@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        # Ping the database
        await db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
            "app": settings.APP_NAME,
            "environment": settings.APP_ENV,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "database": f"unhealthy: {str(exc)}",
                "app": settings.APP_NAME,
                "environment": settings.APP_ENV,
            },
        )


# ── Root → handled by the pages router ──────────────────────────────────────
# The pages router registers GET / which renders the Jinja2 landing page.
# This comment is left here as a signpost — the actual route is in pages.py.
