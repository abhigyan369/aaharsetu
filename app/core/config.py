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

from pydantic import field_validator
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
    CORS_ORIGINS: list[str] = ["*"]  # Configurable CORS allowed origins

    # ── Database ──────────────────────────────────────────────────────────────
    # Full connection string; asyncpg is the async PostgreSQL driver
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        """
        Render and other PaaS providers export DATABASE_URL with 'postgres://' or
        'postgresql://'. SQLAlchemy 2.0 async engine requires 'postgresql+asyncpg://'.
        This validator normalizes the dialect scheme automatically.
        """
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and "+asyncpg" not in v and "+aiosqlite" not in v:
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    # SECRET_KEY signs the JWT — anyone with this key can forge tokens!
    # Generate a safe value with: openssl rand -hex 32
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Refresh tokens live much longer (7 days by default). They are only used
    # to obtain a new access token — never to access protected resources directly.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Email (Phase 4) ───────────────────────────────────────────────────────
    # EMAILS_ENABLED is the master switch. Default=False so local dev works
    # without any SMTP config — the app still stores Notification rows in DB,
    # it just skips the actual email send. Set to True when SMTP creds are ready.
    #
    # Dev: use Mailtrap (smtp.mailtrap.io:587) — a free sandbox inbox that
    #       catches all outgoing mail without delivering it to real addresses.
    # Prod: swap SMTP_HOST/PORT/USER/PASSWORD to:
    #   SendGrid → host=smtp.sendgrid.net, port=587, user=apikey, password=<API_KEY>
    #   Resend   → host=smtp.resend.com,   port=465, user=resend,  password=<API_KEY>
    EMAILS_ENABLED: bool = False
    SMTP_HOST: str = "smtp.mailtrap.io"
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True   # STARTTLS on port 587; set False for port 465 SSL
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@foodwaste.example.com"
    EMAILS_FROM_NAME: str = "Food Waste Platform"

    # ── Cloudinary (Phase 5 — Image Upload) ──────────────────────────────────
    # These three values come from your Cloudinary dashboard (see .env.example
    # for the step-by-step setup guide).
    # CLOUDINARY_CLOUD_NAME: the unique name shown at the top of your dashboard.
    # CLOUDINARY_API_KEY / API_SECRET: treat the secret like a password — never
    #   commit it. On Render/Railway, set all three as environment variables.
    # CLOUDINARY_UPLOAD_FOLDER: images are organised into this folder inside
    #   your Cloudinary media library (keeps things tidy in the dashboard).
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_UPLOAD_FOLDER: str = "food_waste"  # sub-folder in Cloudinary library

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
