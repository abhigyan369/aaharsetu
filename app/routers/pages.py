"""
app/routers/pages.py — Server-Rendered HTML Page Routes
========================================================

WHY THIS FILE EXISTS:
  The JSON API routes (auth.py, listings.py, etc.) handle machine-to-machine
  communication. This file handles browser-to-server communication: serving
  full HTML pages for humans to interact with.

  The pages router is the "glue" between the Jinja2 templates and the
  backend data. Each route:
    1. Reads the httpOnly JWT cookie (instead of Bearer token header)
    2. Fetches the data needed for the page
    3. Renders the template with that data

JWT STORAGE — httpOnly COOKIE vs. localStorage:
  ┌─────────────────┬────────────────────────────┬────────────────────────────┐
  │                 │ localStorage               │ httpOnly Cookie            │
  ├─────────────────┼────────────────────────────┼────────────────────────────┤
  │ XSS risk        │ ❌ JS can steal the token  │ ✅ JS cannot read it at all │
  │ CSRF risk       │ ✅ Not auto-sent            │ ⚠️  Auto-sent (use SameSite)│
  │ Server-rendered │ ❌ JS must attach it        │ ✅ Browser sends it always  │
  │ SPA-friendly    │ ✅ Easy to use in headers   │ ❌ Needs credentials:include│
  └─────────────────┴────────────────────────────┴────────────────────────────┘

  DECISION: httpOnly Cookie — because this is a server-rendered app.
    - The server needs the token on EVERY page load (not just API calls).
    - httpOnly = JS cannot steal it via XSS, even with injected <script> tags.
    - SameSite=Lax prevents CSRF: the cookie is only sent on same-site
      navigations (form POSTs from other domains are rejected by default).

  HOW IT WORKS HERE:
    - POST /pages/login → server calls auth logic, issues JWT,
      sets it as a Set-Cookie: access_token=<jwt>; HttpOnly; Path=/; SameSite=Lax
    - Every page route reads request.cookies.get("access_token")
    - GET /pages/logout → deletes the cookie, redirects to /

  The fetch() calls in templates that hit JSON API endpoints still need the
  token. We pass it from the cookie in the Authorization header using a small
  JS helper defined in base.html.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.models.claim import Claim, ClaimStatus
from app.models.food_listing import FoodListing, FoodType, ListingStatus
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.schemas.token import TokenData

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ── Cookie helpers ─────────────────────────────────────────────────────────────

COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = 60 * 30  # 30 minutes — matches ACCESS_TOKEN_EXPIRE_MINUTES


from app.core.config import settings

def _set_auth_cookie(response: RedirectResponse | HTMLResponse, token: str) -> None:
    """
    Set the JWT as an httpOnly cookie on the response.
    """
    is_secure = settings.APP_ENV == "production" or not settings.DEBUG
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,       # ← JS cannot read this
        samesite="lax",      # ← CSRF protection
        max_age=COOKIE_MAX_AGE,
        path="/",
        secure=is_secure,    # ← HTTPS only in production
    )


def _get_current_user_from_cookie(request: Request) -> TokenData | None:
    """
    Extract and validate the JWT from the cookie. Returns TokenData or None.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    raw_id = payload.get("sub")
    if raw_id is None:
        return None
    try:
        return TokenData(user_id=int(raw_id))
    except (ValueError, TypeError):
        return None


async def _fetch_user(token_data: TokenData | None, db: AsyncSession) -> User | None:
    """Fetch the User ORM object from the DB given decoded token data."""
    if token_data is None or token_data.user_id is None:
        return None
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    return result.scalar_one_or_none()


def _require_login(request: Request, token_data: TokenData | None) -> RedirectResponse | None:
    """
    If the user isn't logged in, return a redirect to /login.
    """
    if token_data is None:
        return RedirectResponse(url="/login?msg=Please+log+in+first", status_code=302)
    return None


# ── GET / — Landing page ──────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def landing_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    """
    Public landing page. No auth required.
    Explains the platform and presents CTAs to sign up as donor or receiver.
    """
    token_data = _get_current_user_from_cookie(request)
    user = await _fetch_user(token_data, db)
    raw_token = request.cookies.get(COOKIE_NAME, "")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": user,
            "token": raw_token,
            "current_user_id": token_data.user_id if token_data else None,
        },
    )


# ── GET /signup — Signup form ─────────────────────────────────────────────────

@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request, role: str = "receiver") -> HTMLResponse:
    """
    Signup form page. Accepts ?role=donor or ?role=receiver to pre-select
    the role radio button.
    """
    return templates.TemplateResponse(
        request=request,
        name="auth/signup.html",
        context={"default_role": role},
    )


# ── GET /login — Login form ───────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, msg: str = "") -> HTMLResponse:
    """Login form page. `msg` query param shows simple status messages."""
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"msg": msg},
    )


# ── POST /login — Process login, set httpOnly cookie ─────────────────────────

@router.post("/login")
async def login_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    """
    Process login form submission.

    WHY NOT use POST /auth/login directly from the form?
      /auth/login is an API endpoint that returns JSON. A plain HTML <form>
      submission follows the response as a redirect — it can't read JSON.
      This route handles the same logic server-side and redirects the browser
      to the right page after setting the httpOnly cookie.

    Internally this replicates the /auth/login logic. The alternative would be
    to call our own API with httpx internally — but that's unnecessary overhead
    when we can call the same DB + security functions directly.
    """
    DUMMY_HASH = "$2b$12$invalidhashfortimingtttttttttttttttttttttttttttt"
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    password_ok = verify_password(
        password,
        user.hashed_password if user else DUMMY_HASH,
    )

    if not user or not password_ok:
        return RedirectResponse(
            url="/login?msg=Incorrect+email+or+password",
            status_code=302,
        )

    # Issue the JWT access token (same function as the JSON API uses)
    token = create_access_token(subject=user.id)

    # Redirect to the right dashboard based on role
    redirect_url = "/dashboard" if user.role == UserRole.DONOR else "/browse"
    if user.role == UserRole.ADMIN:
        redirect_url = "/admin/dashboard"

    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_auth_cookie(response, token)  # ← sets httpOnly cookie
    return response


# ── GET /logout — Clear cookie, redirect ─────────────────────────────────────

@router.get("/logout")
async def logout() -> RedirectResponse:
    """Delete the auth cookie and redirect to home."""
    response = RedirectResponse(url="/?msg=logged_out", status_code=302)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


# ── GET /dashboard — Donor dashboard ─────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse, response_model=None)
async def donor_dashboard(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse | RedirectResponse:
    """
    Donor dashboard: shows the donor's own listings and a form to create new ones.
    Requires authentication + donor role.
    """
    token_data = _get_current_user_from_cookie(request)
    redirect = _require_login(request, token_data)
    if redirect:
        return redirect

    user = await _fetch_user(token_data, db)
    if user is None or user.role not in (UserRole.DONOR, UserRole.ADMIN):
        return RedirectResponse(url="/browse", status_code=302)

    # Fetch this donor's listings, newest first
    result = await db.execute(
        select(FoodListing)
        .where(FoodListing.donor_id == user.id)
        .order_by(FoodListing.created_at.desc())
    )
    listings = list(result.scalars().all())

    # Get the raw JWT token from cookie to pass to templates
    # (templates use it for fetch() calls to the JSON API)
    raw_token = request.cookies.get(COOKIE_NAME, "")

    return templates.TemplateResponse(
        request=request,
        name="donor/dashboard.html",
        context={
            "user": user,
            "listings": listings,
            "food_types": [ft.value for ft in FoodType],
            "token": raw_token,
        },
    )


# ── GET /browse — Receiver browse page ───────────────────────────────────────

@router.get("/browse", response_class=HTMLResponse)
async def browse_listings(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    food_type: str = "",
    sort: str = "expiry",
) -> HTMLResponse:
    """
    Browse available food listings. Public page — no login required to view.
    Login required to claim (enforced client-side via fetch() response).

    Filters applied server-side:
      - food_type: optional enum filter
      - sort: 'expiry' (soonest first) or 'newest' (created_at desc)
    """
    token_data = _get_current_user_from_cookie(request)
    user = await _fetch_user(token_data, db)

    # Build the query
    query = select(FoodListing).where(FoodListing.status == ListingStatus.AVAILABLE)

    if food_type and food_type in [ft.value for ft in FoodType]:
        query = query.where(FoodListing.food_type == food_type)

    if sort == "expiry":
        # Nulls last — listings without expiry time go to the end
        query = query.order_by(
            FoodListing.expiry_time.is_(None).asc(),
            FoodListing.expiry_time.asc(),
        )
    else:
        query = query.order_by(FoodListing.created_at.desc())

    result = await db.execute(query)
    listings = list(result.scalars().all())

    raw_token = request.cookies.get(COOKIE_NAME, "")

    return templates.TemplateResponse(
        request=request,
        name="browse.html",
        context={
            "user": user,
            "listings": listings,
            "food_types": [ft.value for ft in FoodType],
            "selected_food_type": food_type,
            "selected_sort": sort,
            "token": raw_token,
        },
    )


# ── GET /listings/{id} — Listing detail page ─────────────────────────────────

@router.get("/listings/{listing_id}", response_class=HTMLResponse, response_model=None)
async def listing_detail(
    listing_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse | RedirectResponse:
    """
    Full detail view for a single food listing.
    Shows claim button (receiver) or complete button (donor/claimer) based on role.
    """
    token_data = _get_current_user_from_cookie(request)
    user = await _fetch_user(token_data, db)

    # Fetch listing with donor relationship
    result = await db.execute(
        select(FoodListing)
        .where(FoodListing.id == listing_id)
        .options(selectinload(FoodListing.donor))
    )
    listing = result.scalar_one_or_none()

    if listing is None:
        return RedirectResponse(url="/browse?msg=listing_not_found", status_code=302)

    # Check if the current user has claimed this listing (for "complete" button)
    active_claim = None
    if user and user.role == UserRole.RECEIVER:
        claim_result = await db.execute(
            select(Claim).where(
                Claim.listing_id == listing_id,
                Claim.receiver_id == user.id,
                Claim.status.in_([ClaimStatus.PENDING, ClaimStatus.CONFIRMED]),
            )
        )
        active_claim = claim_result.scalar_one_or_none()

    # Check if current user is the donor (for "complete" button on donor side)
    is_donor_of_listing = (
        user is not None
        and user.role == UserRole.DONOR
        and listing.donor_id == user.id
    )

    # For the donor: find the active claim on their listing
    donor_active_claim = None
    if is_donor_of_listing and listing.status == ListingStatus.CLAIMED:
        claim_result = await db.execute(
            select(Claim).where(
                Claim.listing_id == listing_id,
                Claim.status.in_([ClaimStatus.PENDING, ClaimStatus.CONFIRMED]),
            )
        )
        donor_active_claim = claim_result.scalar_one_or_none()

    raw_token = request.cookies.get(COOKIE_NAME, "")

    return templates.TemplateResponse(
        request=request,
        name="listing_detail.html",
        context={
            "user": user,
            "listing": listing,
            "active_claim": active_claim,
            "is_donor_of_listing": is_donor_of_listing,
            "donor_active_claim": donor_active_claim,
            "token": raw_token,
        },
    )


# ── GET /notifications-page — Notifications page ─────────────────────────────

@router.get("/notifications-page", response_class=HTMLResponse, response_model=None)
async def notifications_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse | RedirectResponse:
    """
    Renders in-app notifications for the authenticated user.
    """
    token_data = _get_current_user_from_cookie(request)
    redirect = _require_login(request, token_data)
    if redirect:
        return redirect

    user = await _fetch_user(token_data, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )
    notifications = list(result.scalars().all())

    raw_token = request.cookies.get(COOKIE_NAME, "")

    return templates.TemplateResponse(
        request=request,
        name="notifications.html",
        context={
            "user": user,
            "notifications": notifications,
            "token": raw_token,
        },
    )

