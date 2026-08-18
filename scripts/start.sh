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

echo "⏳ Waiting for database connection to be ready..."
python -c '
import asyncio, sys
from app.db.database import engine
from sqlalchemy import text

async def check_db():
    max_retries = 30
    for i in range(1, max_retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("✅ Database connection established!")
            return
        except Exception as e:
            print(f"⏳ DB connection attempt {i}/{max_retries} failed: {e}. Retrying in 2s...")
            await asyncio.sleep(2)
    print("❌ Database connection timed out after 60 seconds.")
    sys.exit(1)

asyncio.run(check_db())
'

echo "🚀 Running database schema migrations with Alembic..."
alembic upgrade head
echo "✅ Migrations completed successfully."

echo "🌐 Starting Uvicorn ASGI server..."
# PORT is passed dynamically by hosting platforms like Render ($PORT)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

