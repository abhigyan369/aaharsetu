"""
app/routers/listings.py — Food Listing Endpoints
==================================================

ENDPOINTS SUMMARY:
  POST   /listings                — Donor only: create a listing
  GET    /listings                — Public: list/filter/paginate listings
  GET    /listings/{id}           — Public: get single listing detail
  PUT    /listings/{id}           — Donor only (owner): edit if status=available
  DELETE /listings/{id}           — Donor only (owner): soft-delete → cancelled
  POST   /listings/{id}/claim     — Receiver only: atomic claim (no double-claim)
  POST   /listings/{id}/complete  — Donor or Receiver: mark picked_up/completed

BACKGROUND TASK:
  expire_stale_listings() — called after POST /listings as a FastAPI BackgroundTask.
  Marks available listings whose expiry_time has passed → status=expired.

INTERVIEW TALKING POINT — BackgroundTasks vs. APScheduler:
  "FastAPI BackgroundTasks run *after* the HTTP response is sent, in the same
  process and event loop. They're great for lightweight fire-and-forget work
  (like expiring stale rows) triggered by user actions. APScheduler would be
  needed if we want a *periodic* check (e.g., every 5 minutes regardless of
  traffic). For Phase 4, I'll add APScheduler for the near-expiry email job.
  I didn't use Celery because that requires a separate broker (Redis/RabbitMQ)
  and worker process — way too much infra overhead for a portfolio project."

INTERVIEW TALKING POINT — Double-claim prevention:
  "Two receivers could both see status=available and both POST /claim
  simultaneously. To prevent both succeeding, we use a database transaction
  with SELECT ... FOR UPDATE (pessimistic locking). The first transaction
  acquires the row lock; the second blocks until the first commits. Then the
  second sees status=claimed and we return HTTP 409 Conflict. This is safe
  even under concurrent load without any application-level mutex."
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cloudinary_service import upload_image
from app.core.dependencies import (
    CurrentUser,
    DonorUser,
    ReceiverUser,
    get_current_user,
)
from app.core.email_service import render_claim_notification, send_email
from app.core.notification_service import create_notification
from app.core.utils import is_within_distance
from app.db.database import AsyncSessionLocal, get_db
from app.models.claim import Claim, ClaimStatus
from app.models.food_listing import FoodListing, FoodType, ListingStatus
from app.models.user import User, UserRole
from app.schemas.claim import ClaimCreate, ClaimRead
from app.schemas.food_listing import (
    FoodListingCreate,
    FoodListingListResponse,
    FoodListingRead,
    FoodListingSummary,
    FoodListingUpdate,
)

router = APIRouter()


# ── Background Task — Expire stale listings ───────────────────────────────────
async def expire_stale_listings() -> None:
    """
    Mark all 'available' listings whose expiry_time is in the past as 'expired'.

    WHY A FRESH SESSION?
      This function runs as a FastAPI BackgroundTask — after the HTTP response
      is already sent, and after the request's DB session is closed. Using the
      request's session here would raise a "session is closed" error. We open
      a brand-new session from the session factory instead.

    SCALABILITY NOTE:
      This is a bulk UPDATE — one SQL statement touches all stale rows at once,
      not a Python loop. For very high write volumes you'd move this to a
      dedicated cron/scheduler, but for this scale it's perfectly fine.
    """
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                update(FoodListing)
                .where(
                    FoodListing.status == ListingStatus.AVAILABLE,
                    FoodListing.expiry_time != None,  # noqa: E711
                    FoodListing.expiry_time < now,
                )
                .values(status=ListingStatus.EXPIRED)
            )
        # session.begin() commits on context-manager exit — no explicit commit needed


# ── Helper — fetch listing or 404 ─────────────────────────────────────────────
async def get_listing_or_404(listing_id: int, db: AsyncSession) -> FoodListing:
    """Fetch a FoodListing by ID, with the donor relationship pre-loaded."""
    result = await db.execute(
        select(FoodListing)
        .where(FoodListing.id == listing_id)
        .options(selectinload(FoodListing.donor))
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found.",
        )
    return listing


# ─────────────────────────────────────────────────────────────────────────────
# POST /listings  — Donor only: create a new food listing
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/",
    response_model=FoodListingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a food listing (donor only)",
)
async def create_listing(
    background_tasks: BackgroundTasks,
    current_user: DonorUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    # ── Required listing fields (sent as form fields, not JSON) ───────────────
    # WHY FORM FIELDS INSTEAD OF JSON?
    #   HTTP does not allow mixing a file upload (binary stream) with a JSON
    #   body in a single request. The solution is multipart/form-data, where
    #   each field is a "part" of the multipart body. FastAPI's Form() reads
    #   each text field from the form; File() reads the binary file part.
    #   INTERVIEW: "Can't mix file upload with JSON body — multipart/form-data
    #   is the standard encoding for requests that include files."
    title: Annotated[str, Form(min_length=3, max_length=200, description="Listing title")],
    food_type: Annotated[FoodType, Form(description="Type of food being listed")],
    quantity: Annotated[float, Form(gt=0, description="Quantity available")],
    quantity_unit: Annotated[str, Form(max_length=50, description="Unit (e.g. portions, kg)")],
    # ── Optional listing fields ───────────────────────────────────────────────
    description: Annotated[str | None, Form(description="Additional details")] = None,
    latitude: Annotated[float | None, Form(ge=-90, le=90, description="Pickup location latitude")] = None,
    longitude: Annotated[float | None, Form(ge=-180, le=180, description="Pickup location longitude")] = None,
    address: Annotated[str | None, Form(max_length=500, description="Human-readable pickup address")] = None,
    pickup_window_start: Annotated[datetime | None, Form(description="Pickup window start (ISO 8601)")] = None,
    pickup_window_end: Annotated[datetime | None, Form(description="Pickup window end (ISO 8601)")] = None,
    expiry_time: Annotated[datetime | None, Form(description="When the food expires (ISO 8601)")] = None,
    # ── Optional image file ───────────────────────────────────────────────────
    # File(None) means the field is optional — no image = None is passed.
    # Validation (type + size) happens inside upload_image() in cloudinary_service.py.
    # Allowed: jpg, jpeg, png only. Max size: 5 MB.
    # If omitted, a placeholder CDN URL is used so image_url is never NULL.
    image: Annotated[
        UploadFile | None,
        File(description="Optional food image (jpg/png, max 5 MB)"),
    ] = None,
) -> FoodListingRead:
    """
    Create a new food listing.

    **Request format:** `multipart/form-data` (required because the request
    may include a binary file; HTTP cannot mix JSON body + file in one request).

    **Image upload:**
    - Provide an optional `image` file field (jpg/png, max 5 MB).
    - The file is uploaded to Cloudinary; the returned CDN URL is stored in
      `image_url` on the listing record.
    - If no image is provided, a placeholder image URL is stored automatically.

    **Other fields:**
    - `donor_id` is taken from the authenticated JWT — never from the request body.
    - `status` is always set to `available` on creation; clients cannot override it.
    - After committing, a background task runs `expire_stale_listings()` to clean up
      any listings that expired while the app was running.

    **Pickup window validation:**
    - If both `pickup_window_start` and `pickup_window_end` are provided,
      `pickup_window_end` must be after `pickup_window_start`.
    """
    # ── Validate pickup window (mirrors the Pydantic validator from the schema) ─
    # Since we accept Form fields instead of a Pydantic model, we must replicate
    # the cross-field validation manually here.
    if (
        pickup_window_start is not None
        and pickup_window_end is not None
        and pickup_window_end <= pickup_window_start
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pickup_window_end must be after pickup_window_start.",
        )

    # ── Upload image (or get placeholder) ────────────────────────────────────
    # upload_image() handles all validation internally and raises HTTPException
    # on failure — the listing is NOT created if the image upload fails.
    # This keeps the DB consistent: we never store a listing with a broken URL.
    image_url: str = await upload_image(image)

    # ── Create the listing ────────────────────────────────────────────────────
    listing = FoodListing(
        title=title,
        description=description,
        food_type=food_type,
        quantity=quantity,
        quantity_unit=quantity_unit,
        latitude=latitude,
        longitude=longitude,
        address=address,
        pickup_window_start=pickup_window_start,
        pickup_window_end=pickup_window_end,
        expiry_time=expiry_time,
        image_url=image_url,           # Cloudinary CDN URL or placeholder
        donor_id=current_user.id,
        status=ListingStatus.AVAILABLE,
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    # Eager-load the donor for the response schema (avoids a lazy-load after commit)
    result = await db.execute(
        select(FoodListing)
        .where(FoodListing.id == listing.id)
        .options(selectinload(FoodListing.donor))
    )
    listing = result.scalar_one()

    # Schedule expiry cleanup AFTER the response is sent — does not delay the caller
    background_tasks.add_task(expire_stale_listings)

    return listing  # type: ignore[return-value]




# ─────────────────────────────────────────────────────────────────────────────
# GET /listings  — Public: list listings with filters + pagination
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=FoodListingListResponse,
    summary="List food listings with filters and pagination",
)
async def list_listings(
    db: Annotated[AsyncSession, Depends(get_db)],
    # ── Filters ───────────────────────────────────────────────────────────────
    food_type: Annotated[FoodType | None, Query(description="Filter by food type")] = None,
    listing_status: Annotated[
        ListingStatus | None,
        Query(alias="status", description="Filter by listing status"),
    ] = None,
    # ── Proximity filter (haversine) ──────────────────────────────────────────
    # All three must be provided together; validated below.
    lat: Annotated[float | None, Query(ge=-90, le=90, description="Caller's latitude")] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180, description="Caller's longitude")] = None,
    max_distance_km: Annotated[
        float | None,
        Query(gt=0, description="Max distance from lat/lon in kilometres"),
    ] = None,
    # ── Pagination ────────────────────────────────────────────────────────────
    limit: Annotated[int, Query(ge=1, le=100, description="Page size (max 100)")] = 20,
    offset: Annotated[int, Query(ge=0, description="Number of records to skip")] = 0,
) -> FoodListingListResponse:
    """
    Return a paginated list of food listings.

    **Filters (all optional, combinable):**
    - `food_type` — cooked | packaged | raw | bakery | other
    - `status` — available | claimed | picked_up | expired | cancelled
    - `lat` + `lon` + `max_distance_km` — proximity filter using the haversine formula

    **Proximity filter notes:**
    - All three (`lat`, `lon`, `max_distance_km`) must be provided together.
    - Listings with no stored coordinates are **included** (cannot be excluded).
    - Distance is the straight-line great-circle distance, NOT road distance.
    - The `distance_km` field is populated in each result item when filtering.

    **Pagination:**
    - Default page size is 20, max is 100.
    - `total` in the response envelope is the count *before* limit/offset is applied.
    """
    # ── Validate that proximity params are provided as a group ────────────────
    proximity_params = [lat, lon, max_distance_km]
    if any(p is not None for p in proximity_params) and not all(
        p is not None for p in proximity_params
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="lat, lon, and max_distance_km must all be provided together.",
        )

    # ── Build base query ──────────────────────────────────────────────────────
    base_query = select(FoodListing)

    if food_type is not None:
        base_query = base_query.where(FoodListing.food_type == food_type)

    if listing_status is not None:
        base_query = base_query.where(FoodListing.status == listing_status)

    # Order by newest first (most recently posted listings appear at the top)
    base_query = base_query.order_by(FoodListing.created_at.desc())

    # ── Count total matching rows (for the response envelope) ─────────────────
    # We run the count BEFORE applying limit/offset so the client knows how many
    # pages exist. Using func.count() is a single aggregate query — not len(rows).
    count_query = select(func.count()).select_from(base_query.subquery())
    total: int = (await db.execute(count_query)).scalar_one()

    # ── Fetch the page ────────────────────────────────────────────────────────
    if max_distance_km is None:
        # No proximity filter — apply limit/offset in SQL (efficient)
        paginated_query = base_query.offset(offset).limit(limit)
        result = await db.execute(paginated_query)
        rows = list(result.scalars().all())

        items = [FoodListingSummary.model_validate(row) for row in rows]
    else:
        # Proximity filter — we must compute haversine in Python, so we fetch
        # ALL matching rows first, filter by distance, then apply pagination.
        #
        # WHY NOT SQL? PostgreSQL (without PostGIS) has no built-in spherical
        # distance function. We could add a bounding-box pre-filter
        # (WHERE lat BETWEEN ... AND lon BETWEEN ...) for efficiency at scale,
        # but at this volume Python post-filtering is fine.
        #
        # BOUNDING BOX PRE-FILTER (optimisation note):
        #   Approx 1 degree of latitude ≈ 111 km. So max_distance_km / 111
        #   gives a bounding box in degrees. This would be a good next step
        #   to add as a WHERE clause to reduce rows fetched before haversine.
        result = await db.execute(base_query)
        all_rows = list(result.scalars().all())

        # Filter by haversine distance and annotate with distance_km
        filtered: list[FoodListingSummary] = []
        for row in all_rows:
            if is_within_distance(lat, lon, row.latitude, row.longitude, max_distance_km):  # type: ignore[arg-type]
                summary = FoodListingSummary.model_validate(row)
                if row.latitude is not None and row.longitude is not None:
                    from app.core.utils import haversine
                    summary.distance_km = round(
                        haversine(lat, lon, row.latitude, row.longitude), 2  # type: ignore[arg-type]
                    )
                filtered.append(summary)

        # Update total to reflect post-haversine count, then paginate in Python
        total = len(filtered)
        items = filtered[offset : offset + limit]

    return FoodListingListResponse(total=total, limit=limit, offset=offset, items=items)


# ─────────────────────────────────────────────────────────────────────────────
# GET /listings/{id}  — Public: get a single listing's full detail
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/{listing_id}",
    response_model=FoodListingRead,
    summary="Get a single food listing by ID",
)
async def get_listing(
    listing_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FoodListingRead:
    """
    Return full details for a single food listing, including the donor's
    public profile (name, id — never email/password).
    """
    listing = await get_listing_or_404(listing_id, db)
    return listing  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# PUT /listings/{id}  — Donor only (owner): edit a listing if still available
# ─────────────────────────────────────────────────────────────────────────────
@router.put(
    "/{listing_id}",
    response_model=FoodListingRead,
    summary="Edit a food listing (donor/owner only, status must be 'available')",
)
async def update_listing(
    listing_id: int,
    payload: FoodListingUpdate,
    current_user: DonorUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FoodListingRead:
    """
    Partially update a food listing.

    **Ownership check:** only the donor who created the listing can edit it.
    **Status check:** edits are only allowed while the listing is `available`.
    Once claimed, picked_up, expired, or cancelled — it's immutable.

    All fields are optional — send only what you want to change.
    Status is never accepted in the body (use dedicated workflow endpoints).
    """
    listing = await get_listing_or_404(listing_id, db)

    # ── Ownership check ───────────────────────────────────────────────────────
    if listing.donor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own listings.",
        )

    # ── Status guard ──────────────────────────────────────────────────────────
    if listing.status != ListingStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Listing cannot be edited in status '{listing.status.value}'. "
                "Only 'available' listings can be modified."
            ),
        )

    # ── Apply partial update ──────────────────────────────────────────────────
    # exclude_unset=True means only fields the client actually sent are applied;
    # fields omitted from the request body are left unchanged.
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(listing, field, value)

    await db.commit()
    await db.refresh(listing)

    # Re-fetch with donor relationship for the response
    result = await db.execute(
        select(FoodListing)
        .where(FoodListing.id == listing_id)
        .options(selectinload(FoodListing.donor))
    )
    return result.scalar_one()  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /listings/{id}  — Donor only (owner): soft-delete → cancelled
# ─────────────────────────────────────────────────────────────────────────────
@router.delete(
    "/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a food listing (donor/owner only)",
)
async def cancel_listing(
    listing_id: int,
    current_user: DonorUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Soft-delete a listing by setting its status to `cancelled`.

    **Why soft-delete?**
    A hard DELETE removes data permanently, making it impossible to audit
    history (e.g., "how many listings did this donor post?"). Setting status
    to `cancelled` keeps the row for analytics while hiding it from active
    listings queries.

    Ownership is checked — only the owning donor can cancel their listing.
    """
    listing = await get_listing_or_404(listing_id, db)

    if listing.donor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own listings.",
        )

    if listing.status in (ListingStatus.CANCELLED, ListingStatus.PICKED_UP):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Listing is already '{listing.status.value}' and cannot be cancelled.",
        )

    listing.status = ListingStatus.CANCELLED
    await db.commit()
    # 204 No Content — no body returned


# ─────────────────────────────────────────────────────────────────────────────
# POST /listings/{id}/claim  — Receiver only: atomic claim with row lock
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/{listing_id}/claim",
    response_model=ClaimRead,
    status_code=status.HTTP_201_CREATED,
    summary="Claim a food listing (receiver only, atomic — no double-claiming)",
)
async def claim_listing(
    listing_id: int,
    payload: ClaimCreate,
    background_tasks: BackgroundTasks,
    current_user: ReceiverUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClaimRead:
    """
    Atomically claim a food listing for the authenticated receiver.

    **How double-claiming is prevented (interview answer):**

    We use a database transaction with `SELECT ... FOR UPDATE`.
    This places a pessimistic row-level lock on the `food_listings` row.
    Two concurrent requests hitting this endpoint simultaneously will queue
    on the lock — only one proceeds at a time. The second request, when it
    finally gets the lock, will see `status = 'claimed'` and receive a
    `409 Conflict` response.

    No application-level mutex, no Redis lock needed — the DB transaction
    guarantees atomicity by itself.

    **State transitions:**
    - `FoodListing.status`: `available` → `claimed`
    - `Claim.status`: `pending` (new claim starts here)
    """
    # ── SELECT FOR UPDATE — acquire row lock ──────────────────────────────
    # `with_for_update()` appends `FOR UPDATE` to the SQL SELECT.
    # The lock is held until this transaction commits.
    # Other transactions that try to lock the same row will WAIT here.
    result = await db.execute(
        select(FoodListing)
        .where(FoodListing.id == listing_id)
        .with_for_update()  # <-- THE KEY: row-level lock
    )
    listing = result.scalar_one_or_none()

    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found.",
        )

    # ── Status guard — reject if not available ────────────────────────────
    if listing.status != ListingStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Listing is no longer available (current status: "
                f"'{listing.status.value}'). It may have already been claimed."
            ),
        )

    # ── Create Claim record ───────────────────────────────────────────────
    claim = Claim(
        listing_id=listing_id,
        receiver_id=current_user.id,
        status=ClaimStatus.PENDING,
        notes=payload.notes,
    )
    db.add(claim)

    # ── Update listing status ─────────────────────────────────────────────
    listing.status = ListingStatus.CLAIMED

    await db.commit()

    # After commit, the lock is released. Any waiting transactions can now proceed
    # and will see status='claimed', triggering the 409 above.

    # Refresh and load the receiver + listing relationships for notification
    await db.refresh(claim)
    result = await db.execute(
        select(Claim)
        .where(Claim.id == claim.id)
        .options(selectinload(Claim.receiver))
    )
    claim = result.scalar_one()

    # ── Fetch listing + donor for notification ────────────────────────────────
    # We need the donor's email and the listing details to compose the message.
    # The listing object from the FOR UPDATE block is still in session memory.
    listing_result = await db.execute(
        select(FoodListing)
        .where(FoodListing.id == listing_id)
        .options(selectinload(FoodListing.donor))
    )
    notif_listing = listing_result.scalar_one_or_none()

    if notif_listing and notif_listing.donor:
        donor = notif_listing.donor
        receiver_name = claim.receiver.name if claim.receiver else "a receiver"

        # Format pickup window times for the notification message
        pickup_start = (
            notif_listing.pickup_window_start.strftime("%Y-%m-%d %H:%M UTC")
            if notif_listing.pickup_window_start
            else "not specified"
        )
        pickup_end = (
            notif_listing.pickup_window_end.strftime("%Y-%m-%d %H:%M UTC")
            if notif_listing.pickup_window_end
            else "not specified"
        )

        # ── Store in-app Notification (always — regardless of email success) ───
        # STORE-THEN-SEND PATTERN:
        #   We write the DB row here (synchronously, in the same request) so
        #   the donor immediately sees an unread notification in the app.
        #   The email is sent afterward as a BackgroundTask — fire-and-forget.
        #   A failed email never causes a 5xx or rolls back the claim.
        notification_message = (
            f"Your listing '{notif_listing.title}' was claimed by "
            f"{receiver_name}. Pickup window: {pickup_start} – {pickup_end}."
        )
        await create_notification(
            db=db,
            user_id=donor.id,
            message=notification_message,
        )
        await db.commit()  # commit the Notification row

        # ── Send email as BackgroundTask (after HTTP response is returned) ─────
        # BackgroundTasks run AFTER the response is sent to the client —
        # the receiver gets their 201 immediately, then the email goes out.
        # If SMTP fails, send_email() handles the error internally (logs it)
        # and never raises — so the claim is never affected.
        subject, body = render_claim_notification(
            listing_title=notif_listing.title,
            receiver_name=receiver_name,
            pickup_window_start=pickup_start,
            pickup_window_end=pickup_end,
        )
        background_tasks.add_task(send_email, donor.email, subject, body)

    return claim  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# POST /listings/{id}/complete  — Donor or Receiver: mark as picked up
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/{listing_id}/complete",
    response_model=ClaimRead,
    summary="Mark a listing as completed/picked up (donor or receiver)",
)
async def complete_listing(
    listing_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClaimRead:
    """
    Mark a claimed listing as completed (food has been physically picked up).

    **Who can call this?** Either the donor who posted the listing, or the
    receiver who claimed it. Both parties need to be able to confirm pickup
    (e.g., the donor marks it done if the receiver doesn't).

    **State transitions:**
    - `Claim.status`: `pending` or `confirmed` → `completed`
    - `FoodListing.status`: `claimed` → `picked_up`

    Returns the updated Claim record.
    """
    listing = await get_listing_or_404(listing_id, db)

    # ── Authorization: caller must be the donor or the receiver ───────────────
    is_donor = (
        current_user.role == UserRole.DONOR and listing.donor_id == current_user.id
    )

    # Find the active claim to check receiver identity
    claim_result = await db.execute(
        select(Claim)
        .where(
            Claim.listing_id == listing_id,
            Claim.status.in_([ClaimStatus.PENDING, ClaimStatus.CONFIRMED]),
        )
        .options(selectinload(Claim.receiver))
        .order_by(Claim.claimed_at.desc())  # most recent active claim
        .limit(1)
    )
    claim = claim_result.scalar_one_or_none()

    if claim is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active claim found for this listing.",
        )

    is_receiver = (
        current_user.role == UserRole.RECEIVER and claim.receiver_id == current_user.id
    )

    if not (is_donor or is_receiver):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the listing's donor or the claiming receiver can complete it.",
        )

    # ── Status guard ──────────────────────────────────────────────────────────
    if listing.status != ListingStatus.CLAIMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Listing cannot be completed in status '{listing.status.value}'. "
                "It must be in 'claimed' status first."
            ),
        )

    # ── Apply state transitions ───────────────────────────────────────────────
    claim.status = ClaimStatus.COMPLETED
    listing.status = ListingStatus.PICKED_UP

    await db.commit()
    await db.refresh(claim)

    # Re-fetch with receiver relationship for the response schema
    result = await db.execute(
        select(Claim)
        .where(Claim.id == claim.id)
        .options(selectinload(Claim.receiver))
    )
    return result.scalar_one()  # type: ignore[return-value]
