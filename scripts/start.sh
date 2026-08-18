#!/bin/sh
# ==============================================================================
# ENTRYPOINT / START SCRIPT FOR PRODUCTION CONTAINER
# ==============================================================================
#
# WHY THIS FILE EXISTS:
#   In production, database schema migrations (Alembic) must run BEFORE the
#   web application accepts HTTP traffic. Placing `alembic upgrade head` here
#   ensures every new deployment automatically updates the database schema.
#
# INTERVIEW TALKING POINT:
#   "We use `set -e` so if migrations fail, the script exits immediately with an
#   error code, preventing the outdated app or half-migrated state from serving traffic.
#   We use `exec` for Uvicorn so it runs as PID 1 inside the container, correctly
#   receiving SIGTERM signals from the container runtime for graceful shutdown."
# ==============================================================================

set -e

echo "🚀 Running database schema migrations with Alembic..."
alembic upgrade head
echo "✅ Migrations completed successfully."

echo "🌐 Starting Uvicorn ASGI server..."
# PORT is passed dynamically by hosting platforms like Render ($PORT)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
