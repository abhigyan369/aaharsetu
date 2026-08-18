"""
app/core/security.py — Password Hashing & JWT Token Handling
=============================================================

WHY THIS FILE EXISTS:
  Centralising all security primitives here means there's one place to
  update if you ever swap the hashing algorithm or token library. It also
  makes it easy to mock/stub in tests.

INTERVIEW TALKING POINTS:
  - "Passwords are hashed with bcrypt, which is slow by design — that's what
    makes brute-forcing expensive. We never store or log the plaintext."
  - "JWTs are signed (not encrypted). Anyone can decode the payload, but they
    can't forge a valid signature without the SECRET_KEY."
  - "The token has an `exp` (expiry) claim — the server checks this on every
    protected request so stolen tokens expire automatically."
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Password Hashing ──────────────────────────────────────────────────────────
# CryptContext is a passlib helper that can support multiple schemes at once
# (useful if you ever migrate from bcrypt to argon2 — old hashes still work).
# "deprecated='auto'" automatically re-hashes old-scheme passwords on login.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    Store the *returned string* in the database — never the original password.

    bcrypt embeds the salt and cost factor in the hash string itself, so you
    don't need to store the salt separately.
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Return True if `plain_password` matches `hashed_password`.
    passlib re-runs the bcrypt KDF with the embedded salt and compares hashes.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Tokens ────────────────────────────────────────────────────────────────

def create_access_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: Typically the user's ID or email — identifies who the token
                 belongs to. This ends up in the `sub` claim.
        expires_delta: How long until the token expires. Defaults to the value
                       in settings (e.g., 30 minutes).

    The token payload (called "claims") looks like:
        { "sub": "42", "exp": 1720000000 }
    `exp` is a Unix timestamp; the server rejects tokens past this time.

    WHY NOT sessions?
      JWTs are stateless — the server doesn't need a database lookup to
      validate them (the signature proves authenticity). This makes them
      easy to scale horizontally. The tradeoff: you can't invalidate a
      JWT before it expires without a token blacklist.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),  # `sub` = "subject" — standard JWT claim for identity
        "exp": expire,        # `exp` = "expiry"  — standard JWT claim for expiry
    }
    # jwt.encode signs the payload with our SECRET_KEY using ALGORITHM (HS256)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    """
    Create a signed JWT refresh token.

    WHY A SEPARATE FUNCTION (not just a long-lived access token)?
      Refresh tokens exist to limit damage if an access token leaks:
        - Access token: short-lived (30 min), used on EVERY request.
          If intercepted, the attacker has 30 minutes — that's acceptable.
        - Refresh token: long-lived (7 days), sent ONLY to /auth/refresh.
          Fewer requests = fewer opportunities to intercept.

    The `"type": "refresh"` claim is a custom claim we add so the server
    can reject a refresh token if someone tries to use it as an access token.
    Standard JWT libraries don't enforce this automatically — we must check
    it manually in a /auth/refresh endpoint (Phase 3+).

    Args:
        subject: The user's ID — same as access token.
        expires_delta: Override TTL; defaults to settings.REFRESH_TOKEN_EXPIRE_DAYS.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        # Custom claim: distinguishes this token from an access token.
        # A /auth/refresh endpoint should verify this is "refresh" before issuing
        # a new access token.
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """
    Decode and verify a JWT token.
    Returns the payload dict if valid, or None if the token is invalid/expired.

    jose raises JWTError for:
      - Invalid signature (tampered token)
      - Expired token (`exp` claim in the past)
      - Malformed token (not a valid JWT structure)
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        return None
