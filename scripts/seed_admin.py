"""
scripts/seed_admin.py — Create the initial Admin user
======================================================

WHY THIS IS A SCRIPT, NOT AN ENDPOINT:
  Admin is a privileged role. If we allowed admin creation via POST /auth/signup
  (even with a secret code or invite token), we'd be exposing an attack surface
  that's only needed once at deploy time. Instead:
    - This script runs once, locally or in the deploy pipeline, by a trusted operator.
    - It reads credentials from environment variables (never hardcoded).
    - It's idempotent: running it twice won't create duplicate admins.

  INTERVIEW TALKING POINT:
    "Privileged bootstrapping operations don't belong in the API surface. I use a
    separate CLI script that can only be run by someone with server/terminal access.
    This follows the principle of least privilege — the HTTP layer has no knowledge
    of how admins are created."

USAGE:
  # Set env vars (or use your .env file)
  export ADMIN_EMAIL="admin@foodwaste.example.com"
  export ADMIN_PASSWORD="Str0ngAdminP@ss!"

  # Run from the project root (so Python can find `app.*` modules)
  python -m scripts.seed_admin

  # Or with .env loaded automatically:
  # python -m scripts.seed_admin  (pydantic-settings reads .env)
"""

import asyncio
import os
import sys

# ── Ensure the project root is in the Python path ────────────────────────────
# When run as `python -m scripts.seed_admin`, Python adds the package root
# automatically. This guard handles running the script directly (rare, but safe).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402 (after sys.path manipulation)

from app.core.security import hash_password  # noqa: E402
from app.db.database import AsyncSessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


async def seed_admin() -> None:
    """
    Idempotent admin seeding function.

    Reads ADMIN_EMAIL and ADMIN_PASSWORD from environment variables.
    Creates the admin user if one doesn't already exist.

    Idempotent = safe to run multiple times:
      If an admin with the given email already exists, the script skips creation
      and exits cleanly. This makes it safe to include in deploy pipelines that
      run on every deploy.
    """
    # ── Read credentials from environment ─────────────────────────────────────
    # WHY ENV VARS, not .env?
    #   This script can be called during CI/CD where the .env file doesn't
    #   exist (and shouldn't — secrets are injected as platform env vars).
    #   We fall back to a safe default error message, not a default password.
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        print(
            "ERROR: ADMIN_EMAIL and ADMIN_PASSWORD environment variables must be set.\n"
            "Example:\n"
            "  export ADMIN_EMAIL='admin@example.com'\n"
            "  export ADMIN_PASSWORD='Str0ngP@ss!'\n"
            "  python -m scripts.seed_admin",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Validate password length ───────────────────────────────────────────────
    if len(admin_password) < 12:
        print(
            "ERROR: Admin password must be at least 12 characters for security.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Database operation ─────────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        # Check if an admin with this email already exists (idempotency check)
        result = await session.execute(
            select(User).where(User.email == admin_email)
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            if existing.role == UserRole.ADMIN:
                print(f"✅ Admin account already exists: {admin_email} — no changes made.")
            else:
                # Edge case: the email exists but as a non-admin.
                # Refuse to overwrite — this could indicate a configuration error.
                print(
                    f"⚠️  A non-admin account with email '{admin_email}' already exists "
                    f"(role: {existing.role.value}). Refusing to overwrite. "
                    "Use a different ADMIN_EMAIL or promote this user manually.",
                    file=sys.stderr,
                )
                sys.exit(1)
            return

        # ── Create the admin user ──────────────────────────────────────────────
        admin = User(
            name="Admin",  # Can be updated later via a profile endpoint
            email=admin_email,
            hashed_password=hash_password(admin_password),  # bcrypt hash
            role=UserRole.ADMIN,
            is_verified=True,  # Admin accounts are implicitly verified
        )

        session.add(admin)
        await session.commit()
        await session.refresh(admin)

        print(
            f"✅ Admin account created successfully!\n"
            f"   Email: {admin.email}\n"
            f"   ID:    {admin.id}\n"
            f"   Role:  {admin.role.value}\n\n"
            "⚠️  Store these credentials securely — this script cannot recover them."
        )


if __name__ == "__main__":
    # asyncio.run() creates a new event loop, runs the coroutine, and closes it.
    # We can't just call `await seed_admin()` at the module level because
    # `await` requires an existing event loop (you'd need to be inside an async
    # function or a running ASGI app).
    asyncio.run(seed_admin())
