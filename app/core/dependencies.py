"""
app/core/dependencies.py — FastAPI Dependency Functions for Auth
================================================================

WHY THIS FILE EXISTS:
  FastAPI's dependency injection system (`Depends()`) lets us declare
  "what a route needs" as a function parameter rather than running the
  same auth/validation code inside every route.

  This file provides two reusable auth dependencies:
    1. get_current_user  — validates the Bearer token, returns the User
    2. require_role(...)  — factory that returns a dependency checking user role

INTERVIEW TALKING POINT — Dependency Injection:
  "FastAPI resolves the dependency graph before calling the route function.
  If get_current_user raises a 401, FastAPI short-circuits immediately —
  the route body never runs. This is similar to middleware, but scoped
  to individual routes and composable (one dependency can depend on another)."

INTERVIEW TALKING POINT — Why not middleware?
  "Middleware runs for every request. Using Depends() lets me attach auth
  only to routes that need it (e.g., GET /listings is public, but
  POST /listings is donor-only). Middleware would require manual URL pattern
  matching which is fragile."
"""

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.token import TokenData

# ── OAuth2 Scheme ─────────────────────────────────────────────────────────────
# OAuth2PasswordBearer does two things:
#   1. Tells FastAPI that the "lock" icon in /docs means "send a Bearer token"
#   2. Extracts the token string from the "Authorization: Bearer <token>" header
#      on every request that depends on this scheme.
#
# `tokenUrl` is only for Swagger UI's "Authorize" button — it tells the docs
# page where to POST credentials to get a token. It has no security role.
#
# WHY auto_error=False?
#   Setting auto_error=False prevents OAuth2PasswordBearer from automatically
#   raising a 401 if the Authorization header is missing. This allows get_current_user
#   to fall back to checking the httpOnly `access_token` cookie for browser-based navigation.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ── get_current_user ──────────────────────────────────────────────────────────
async def get_current_user(
    request: Request,
    header_token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    FastAPI dependency: validates the JWT and returns the authenticated User.

    HOW THE DEPENDENCY CHAIN WORKS (step by step):
      1. FastAPI sees `Depends(oauth2_scheme)` → extracts the Bearer token
         from the Authorization header. Raises 401 automatically if header
         is missing.
      2. We call decode_access_token(token) → python-jose verifies:
           - The signature (was this signed by our SECRET_KEY?)
           - The `exp` claim (has it expired?)
           Returns None on any failure (avoids leaking error details).
      3. We parse the `sub` claim (user ID) via TokenData for type safety.
      4. We fetch the User from the database. Why fetch at all if the JWT
         already identifies the user? Because the user might have been
         deleted or deactivated since the token was issued. JWTs are
         stateless — the DB is the source of truth for account status.
      5. Return the live User ORM object. Any route that `Depends` on this
         gets the actual user — no extra DB call needed in the route itself.

    Raises:
      HTTP 401 UNAUTHORIZED — if token is missing, invalid, expired, or
                               if the user no longer exists.

    WHY 401 (not 403)?
      401 means "you are not authenticated" (identity unknown).
      403 means "you are authenticated but not authorised" (identity known,
      permission denied). Here we don't even know who you are yet → 401.
    """
    # Reusable 401 exception — defined once so every failure path returns
    # identical response headers (WWW-Authenticate: Bearer), which is required
    # by the OAuth2 spec. Identical errors also prevent timing-based user
    # enumeration attacks.
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        # WWW-Authenticate header tells the client *how* to authenticate.
        # Required by RFC 6750 (Bearer Token Usage).
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Step 0 — Obtain token from Authorization header or cookie
    token = header_token or request.cookies.get("access_token")
    if not token:
        raise credentials_exception

    # Step 1 — Decode and verify the JWT
    payload = decode_access_token(token)
    if payload is None:
        # Token was invalid, expired, or tampered with.
        raise credentials_exception

    # Step 2 — Extract the subject claim (user ID)
    # `sub` is always stored as a string (JWT spec says claims are strings),
    # so we cast it to int for DB lookup.
    raw_user_id = payload.get("sub")
    if raw_user_id is None:
        raise credentials_exception

    try:
        token_data = TokenData(user_id=int(raw_user_id))
    except (ValueError, TypeError):
        # sub was present but not a valid integer — malformed token
        raise credentials_exception

    # Step 3 — Fetch the user from the database
    # WHY SQLAlchemy select() instead of session.get()?
    #   Both work. select() is more explicit and easier to extend later
    #   (e.g., add .where(User.is_active == True) to block deactivated users).
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if user is None:
        # User was deleted after the token was issued — deny access.
        raise credentials_exception

    return user


# ── require_role — Dependency Factory ─────────────────────────────────────────
def require_role(*roles: UserRole | str) -> Callable:
    """
    Dependency **factory** — returns a FastAPI dependency that enforces role access.

    WHY A FACTORY (function that returns a function)?
      We can't use `Depends(some_function)` with arguments directly. The factory
      pattern captures the allowed roles in a closure, then returns a zero-argument
      (but dependency-injected) callable that FastAPI can use.

    USAGE IN ROUTES:
      @router.post("/listings", dependencies=[Depends(require_role("donor"))])
      async def create_listing(...):
          ...

      Or inject the user too:
      @router.post("/listings")
      async def create_listing(
          current_user: Annotated[User, Depends(require_role("donor", "admin"))],
      ):
          ...

    Args:
      *roles: One or more role strings (or UserRole enum values) that are
              allowed to access the route. Multiple roles = OR logic
              (any one of them is sufficient).

    Returns:
      A FastAPI-compatible async dependency function.

    Raises:
      HTTP 403 FORBIDDEN — if the authenticated user's role is not in `roles`.
      (401 errors are handled upstream by get_current_user.)
    """
    # Normalise to a set of strings for O(1) lookup, regardless of whether
    # the caller passed UserRole.DONOR or the string "donor".
    allowed_roles = {r.value if isinstance(r, UserRole) else r for r in roles}

    async def _check_role(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        """
        Inner dependency: checks that the already-authenticated user has
        one of the required roles.

        Note that `get_current_user` runs first (it's a dependency of this
        function). If the token is invalid, we never reach this check.
        FastAPI handles the dependency graph automatically.
        """
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Required role(s): {', '.join(allowed_roles)}. "
                    f"Your role: {current_user.role.value}."
                ),
            )
        return current_user

    return _check_role


# ── Convenience type aliases ──────────────────────────────────────────────────
# These shorten route signatures from:
#   current_user: Annotated[User, Depends(get_current_user)]
# to:
#   current_user: CurrentUser
#
# Annotated[] is Pydantic/FastAPI's way of attaching metadata (the Depends)
# to a type hint without changing the type itself.
CurrentUser = Annotated[User, Depends(get_current_user)]
DonorUser = Annotated[User, Depends(require_role(UserRole.DONOR))]
ReceiverUser = Annotated[User, Depends(require_role(UserRole.RECEIVER))]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
