"""
app/core/config.py — Application Settings
==========================================

WHY THIS FILE EXISTS:
  Hard-coding values like database URLs and secret keys directly in code is
  dangerous (they end up in git history) and inflexible (can't change them
  per-environment). pydantic-settings reads these values from environment
  variables (or a .env file) and validates them as typed Python objects.
  If a required variable is missing, the app fails at startup with a clear
  error — not at runtime when a user hits an endpoint.

INTERVIEW TALKING POINT:
  "I use the 12-factor app principle of separating config from code. All
  environment-specific values live in .env files that are never committed."
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All application settings are defined here as typed fields.
    pydantic-settings automatically reads matching env vars or .env entries.
    """

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "Food Waste Redistribution Platform"
    APP_ENV: str = "development"    # Used to enable/disable debug features
    DEBUG: bool = True

    # ── Database ──────────────────────────────────────────────────────────────
    # Full connection string; asyncpg is the async PostgreSQL driver
    DATABASE_URL: str

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    # SECRET_KEY signs the JWT — anyone with this key can forge tokens!
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Email (Phase 5) ───────────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@foodwaste.example.com"

    # ── Cloudinary (Phase 6) ──────────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Tell pydantic-settings to look for a .env file automatically
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,   # DATABASE_URL != database_url
    )


# ── Singleton ──────────────────────────────────────────────────────────────────
# Import this `settings` object anywhere in the app instead of re-instantiating.
# Python's module system caches it, so the .env is only parsed once.
settings = Settings()  # type: ignore[call-arg]
