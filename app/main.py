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

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates  # noqa: F401 — used by routers

from app.core.config import settings

# ── Lifespan (startup/shutdown events) ───────────────────────────────────────
# The `lifespan` context manager replaces the old @app.on_event("startup")
# pattern (deprecated in newer FastAPI). Code before `yield` runs on startup;
# code after `yield` runs on shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    # Good place to: warm caches, start background schedulers (Phase 5),
    # verify DB connectivity, etc.
    print(f"🚀 Starting {settings.APP_NAME} [{settings.APP_ENV}]")
    yield
    # ── Shutdown ──────────────────────────────────────────────────────────────
    # Good place to: flush caches, shut down schedulers cleanly, etc.
    print("👋 Shutting down...")


# ── Create the FastAPI app ────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="A platform connecting food donors with receivers to reduce food waste.",
    version="0.1.0",
    # Disable interactive docs in production — they expose your API surface
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Static Files ──────────────────────────────────────────────────────────────
# Serves everything inside app/static/ at the /static URL path.
# e.g., app/static/css/main.css → http://localhost:8000/static/css/main.css
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ── Register Routers ──────────────────────────────────────────────────────────
# Uncomment each router as you build it in future phases.
# The `prefix` is prepended to every route in that router.
# The `tags` group endpoints in the /docs UI.
#
# from app.routers import auth, listings, notifications, admin, pages
# app.include_router(auth.router,          prefix="/auth",          tags=["Auth"])
# app.include_router(listings.router,      prefix="/listings",      tags=["Listings"])
# app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
# app.include_router(admin.router,         prefix="/admin",         tags=["Admin"])
# app.include_router(pages.router,                                  tags=["Pages"])


# ── Health Check ──────────────────────────────────────────────────────────────
# Simple endpoint used by load balancers and uptime monitors to verify the
# app is running. Returns 200 OK as long as the process is alive.
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}


# ── Root Redirect (temporary placeholder) ────────────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    """Placeholder root — will be replaced by the Jinja2 landing page in Phase 8."""
    return {
        "message": f"Welcome to {settings.APP_NAME}!",
        "docs": "/docs",
    }
