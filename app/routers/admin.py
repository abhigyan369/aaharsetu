"""
app/routers/admin.py — Admin Analytics Router
==============================================

WHY THIS FILE EXISTS:
  Provides two endpoints for the admin analytics dashboard:
    1. GET /admin/stats   — JSON API with aggregated DB statistics
    2. GET /admin/dashboard — Jinja2 HTML page that visualises those stats
                             using Chart.js (loaded via CDN, no build step)

AGGREGATE QUERY PRIMER (for interview prep):
  SQLAlchemy's `func` object maps to SQL aggregate functions:
    - func.count(column)  → COUNT(column)  — counts non-NULL values
    - func.count("*")     → COUNT(*)       — counts all rows (incl. NULLs)
    - func.sum(column)    → SUM(column)
    - .group_by(column)   → GROUP BY column
    - .label("alias")     → AS alias       — names the result column

  All queries here use select() + session.execute() (SQLAlchemy 2.0 style).
  We avoid the legacy session.query() API because it's being deprecated.

SECURITY:
  Both endpoints are behind `AdminUser` which chains:
    get_current_user → require_role("admin")
  A missing/invalid token or wrong role returns 401/403 before any DB call.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from fastapi import Depends

from app.core.dependencies import AdminUser
from app.db.database import get_db
from app.models.claim import Claim, ClaimStatus
from app.models.food_listing import FoodListing, FoodType, ListingStatus
from app.models.user import User, UserRole

router = APIRouter()

# Jinja2 templates directory — shared with the rest of the app.
# `directory="app/templates"` is relative to where uvicorn is launched (project root).
templates = Jinja2Templates(directory="app/templates")


# ── Helper: run all aggregate queries ─────────────────────────────────────────

async def _gather_stats(db: AsyncSession) -> dict[str, Any]:
    """
    Run all SQLAlchemy aggregate queries and return a single dict.

    Splitting the DB work into its own function keeps both route handlers
    (JSON and HTML) DRY — they both call this and format the result differently.

    QUERY EXPLANATIONS (annotated for interview prep):
    """

    # ── 1. Total listings ────────────────────────────────────────────────────
    # SQL equivalent:
    #   SELECT COUNT(*) FROM food_listings;
    #
    # func.count() with no argument or "*" counts every row (including NULLs).
    # Using scalar_one() because a COUNT always returns exactly one row.
    total_listings_result = await db.execute(
        select(func.count()).select_from(FoodListing)
    )
    total_listings: int = total_listings_result.scalar_one() or 0

    # ── 2. Active listings (status = 'available') ────────────────────────────
    # SQL equivalent:
    #   SELECT COUNT(*) FROM food_listings WHERE status = 'available';
    #
    # .where() on an aggregate query adds a WHERE clause before counting.
    # We don't use HAVING here because we're filtering rows, not groups.
    active_listings_result = await db.execute(
        select(func.count())
        .select_from(FoodListing)
        .where(FoodListing.status == ListingStatus.AVAILABLE)
    )
    active_listings: int = active_listings_result.scalar_one() or 0

    # ── 3. Completed pickups ("meals saved" proxy) ───────────────────────────
    # SQL equivalent:
    #   SELECT COUNT(*) FROM claims WHERE status = 'completed';
    #
    # WHY proxy on Claims, not FoodListings?
    #   A Claim with status='completed' means a receiver physically picked up
    #   the food. The FoodListing status='picked_up' is the same event from the
    #   listing's perspective. We count Claims because it's the more granular
    #   record — each completed Claim = one successful redistribution event.
    #
    # INTERVIEW TALKING POINT:
    #   "We use 'completed claims' as a proxy for meals saved because each
    #    Claim represents one redistribution transaction. We could weight by
    #    quantity to get kg saved, but count is simpler and good enough for
    #    a portfolio dashboard."
    completed_pickups_result = await db.execute(
        select(func.count())
        .select_from(Claim)
        .where(Claim.status == ClaimStatus.COMPLETED)
    )
    completed_pickups: int = completed_pickups_result.scalar_one() or 0

    # ── 4. Registered donors and receivers ──────────────────────────────────
    # SQL equivalent:
    #   SELECT role, COUNT(*) as count
    #   FROM users
    #   WHERE role IN ('donor', 'receiver')
    #   GROUP BY role;
    #
    # .group_by() partitions rows by the column value before counting.
    # Each (role, count) pair becomes one row in the result set.
    # .label("count") renames the COUNT(*) column so we can access it by name.
    role_counts_result = await db.execute(
        select(User.role, func.count().label("count"))
        .where(User.role.in_([UserRole.DONOR, UserRole.RECEIVER]))
        .group_by(User.role)
    )
    role_rows = role_counts_result.all()

    # Convert the list of (role, count) tuples into a dict for O(1) lookup.
    # e.g. {UserRole.DONOR: 12, UserRole.RECEIVER: 34}
    role_map: dict[str, int] = {row.role.value: row.count for row in role_rows}
    total_donors: int = role_map.get("donor", 0)
    total_receivers: int = role_map.get("receiver", 0)

    # ── 5. Listings by food_type breakdown ───────────────────────────────────
    # SQL equivalent:
    #   SELECT food_type, COUNT(*) as count
    #   FROM food_listings
    #   GROUP BY food_type
    #   ORDER BY count DESC;
    #
    # GROUP BY food_type partitions the table into one group per enum value.
    # ORDER BY count DESC puts the most common food type first (useful for charts).
    food_type_result = await db.execute(
        select(FoodListing.food_type, func.count().label("count"))
        .group_by(FoodListing.food_type)
        .order_by(func.count().desc())
    )
    food_type_rows = food_type_result.all()

    # Build two parallel lists for Chart.js: labels and values.
    # Chart.js expects arrays like: labels=["cooked","packaged"], data=[10, 5]
    food_type_labels: list[str] = [row.food_type.value for row in food_type_rows]
    food_type_counts: list[int] = [row.count for row in food_type_rows]

    # ── 6. Time-series: listings created per day for the last 30 days ────────
    # SQL equivalent (PostgreSQL):
    #   SELECT created_at::date AS day, COUNT(*) as count
    #   FROM food_listings
    #   WHERE created_at >= NOW() - INTERVAL '30 days'
    #   GROUP BY day
    #   ORDER BY day ASC;
    #
    # cast(FoodListing.created_at, Date):
    #   Truncates the timestamp to date-only (strips the time component) so
    #   all listings created on the same day land in the same GROUP BY bucket.
    #   Without this, each unique timestamp would be its own group.
    #
    # WHY 30 days?
    #   Long enough to see a trend; short enough to be readable on a chart.
    #   For real products you'd make this configurable via a query param.
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=30)

    timeseries_result = await db.execute(
        select(
            cast(FoodListing.created_at, Date).label("day"),
            func.count().label("count"),
        )
        .where(FoodListing.created_at >= cutoff)
        .group_by(cast(FoodListing.created_at, Date))
        .order_by(cast(FoodListing.created_at, Date).asc())
    )
    timeseries_rows = timeseries_result.all()

    # Generate a COMPLETE date range for the last 30 days so days with zero
    # listings appear as 0 in the chart (rather than being absent, which would
    # make the x-axis irregular and confuse viewers).
    today = date.today()
    all_days: list[date] = [today - timedelta(days=i) for i in range(29, -1, -1)]

    # Map DB results to a dict: {date: count}
    day_count_map: dict[date, int] = {row.day: row.count for row in timeseries_rows}

    # Fill gaps with 0 for days not present in the DB results.
    timeseries_labels: list[str] = [d.strftime("%b %d") for d in all_days]
    timeseries_counts: list[int] = [day_count_map.get(d, 0) for d in all_days]

    return {
        "total_listings": total_listings,
        "active_listings": active_listings,
        "completed_pickups": completed_pickups,
        "total_donors": total_donors,
        "total_receivers": total_receivers,
        # Food type chart data
        "food_type_labels": food_type_labels,
        "food_type_counts": food_type_counts,
        # Time-series chart data
        "timeseries_labels": timeseries_labels,
        "timeseries_counts": timeseries_counts,
        # Computed at query time so the template doesn't need to do math
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ── Route 1: GET /admin/stats — JSON API ──────────────────────────────────────

@router.get(
    "/stats",
    summary="Admin: platform statistics (JSON)",
    response_description="Aggregated platform metrics",
    tags=["Admin"],
)
async def get_admin_stats(
    # AdminUser chains: get_current_user → require_role("admin")
    # If the caller isn't an authenticated admin, FastAPI raises 401/403
    # before this function body runs.
    current_admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Returns aggregated platform statistics as JSON.

    Useful for:
      - Connecting to an external BI tool (Grafana, Metabase)
      - Automated monitoring / alerting scripts
      - The /admin/dashboard page (it calls this data via the same helper)

    All aggregate queries live in `_gather_stats()` — see inline comments
    there for SQL explanations.
    """
    stats = await _gather_stats(db)
    return stats


# ── Route 2: GET /admin/dashboard — Jinja2 HTML page ─────────────────────────

@router.get(
    "/dashboard",
    response_class=HTMLResponse,
    summary="Admin: analytics dashboard (HTML)",
    tags=["Admin"],
)
async def admin_dashboard(
    request: Request,
    current_admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    """
    Renders the admin analytics dashboard as a server-side HTML page.

    Uses the same `_gather_stats()` helper as the JSON endpoint — single
    source of truth for the aggregate queries.

    WHY SERVER-SIDE RENDERING instead of a React/Vue SPA?
      The user only knows HTML/CSS and vanilla JS. Server-rendered Jinja2
      templates let us pass Python data directly to the template without
      a separate fetch() call. Chart.js is loaded via CDN and fed data
      embedded in a <script> block — no build step, no npm, no bundler.
    """
    stats = await _gather_stats(db)

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={
            # Pass all stats directly — Jinja2 makes them available as variables.
            **stats,
            # Also pass the admin's name for a personalised greeting.
            "admin_name": current_admin.name,
        },
    )
