"""
app/core/scheduler.py — APScheduler Background Jobs
=====================================================

WHY APScheduler INSTEAD OF Celery?
  Celery requires:
    1. A message broker (Redis or RabbitMQ) running as a separate service
    2. At least one Celery worker process (separate from the FastAPI process)
    3. Optionally: Celery Beat (another process) for periodic scheduling
    4. Network serialization of tasks (pickle/JSON) across processes

  That's 2-4 extra infra pieces for a single periodic job that runs every
  15 minutes and touches a handful of DB rows. APScheduler, by contrast,
  is just a Python library that runs jobs inside the same process as FastAPI,
  sharing the same event loop. Zero extra services, zero extra config.

  USE Celery when you need:
    - Distributed task queues across multiple machines
    - Tens of thousands of background jobs per second
    - Complex retry logic with exponential backoff at scale
    - Task routing (different queues for different job types)

  We have none of those needs. APScheduler is the pragmatic choice.

INTERVIEW TALKING POINT:
  "I use APScheduler's AsyncIOScheduler, which hooks into the same asyncio
  event loop as FastAPI/uvicorn. The scheduled job is an async function that
  opens its own DB session (using AsyncSessionLocal directly) — the same
  pattern as the expire_stale_listings background task in the listings router.
  The scheduler is started in the lifespan context manager so it's guaranteed
  to start after the app is ready and shut down cleanly on SIGTERM."

SCHEDULER LIFECYCLE:
  - Created at module import time (singleton, like `settings`)
  - Started in app/main.py lifespan (startup)
  - Shut down in app/main.py lifespan (shutdown)

JOB: check_expiring_listings
  - Runs every 15 minutes
  - Finds listings where: status=available AND expiry_time BETWEEN now AND now+1h
  - For each, checks if an expiry warning was already sent (avoids spam)
  - Creates a Notification row + sends email to the donor
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.email_service import render_expiry_warning, send_email
from app.core.notification_service import create_notification
from app.db.database import AsyncSessionLocal
from app.models.food_listing import FoodListing, ListingStatus
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger(__name__)

# ── Scheduler Singleton ───────────────────────────────────────────────────────
# Created at import time. main.py calls scheduler.start() on app startup.
# Using AsyncIOScheduler so jobs are coroutines that run on the existing
# asyncio event loop — no new threads needed.
scheduler = AsyncIOScheduler(timezone="UTC")


# ── Job: check_expiring_listings ──────────────────────────────────────────────
async def check_expiring_listings() -> None:
    """
    Periodic job (every 15 minutes): warn donors when their listing is within
    1 hour of expiring and no notification has been sent yet for it.

    WHAT "ABOUT TO EXPIRE" MEANS:
      expiry_time is between now and now + 1 hour, AND status is still 'available'.
      We check status=available because claimed/picked_up listings don't need a
      warning — they're already being handled.

    DEDUPLICATION:
      We check the Notification table to see if a warning was already sent for
      this listing (message contains the listing title + "expiring soon" marker).
      This prevents the job from spamming the donor every 15 minutes for the
      same listing. A production system would use a dedicated
      `expiry_warned_at` column on FoodListing for cleaner deduplication.

    SESSION MANAGEMENT:
      We open a fresh AsyncSessionLocal() session — the same pattern as
      `expire_stale_listings()` in listings.py. We can't use the request
      session because no HTTP request is in flight; this runs on a timer.
    """
    now = datetime.now(timezone.utc)
    warning_window_end = now + timedelta(hours=1)

    logger.info(
        "Scheduler: checking for listings expiring between %s and %s",
        now.isoformat(),
        warning_window_end.isoformat(),
    )

    async with AsyncSessionLocal() as session:
        # ── Find listings expiring within the next hour ────────────────────────
        result = await session.execute(
            select(FoodListing)
            .where(
                FoodListing.status == ListingStatus.AVAILABLE,
                FoodListing.expiry_time.is_not(None),
                FoodListing.expiry_time >= now,              # not already expired
                FoodListing.expiry_time <= warning_window_end,  # expires within 1h
            )
        )
        expiring_listings = result.scalars().all()

        if not expiring_listings:
            logger.info("Scheduler: no listings expiring within 1 hour. All clear.")
            return

        logger.info(
            "Scheduler: found %d listing(s) expiring soon.", len(expiring_listings)
        )

        for listing in expiring_listings:
            await _warn_donor_for_listing(session, listing)


async def _warn_donor_for_listing(session, listing: FoodListing) -> None:
    """
    For a single about-to-expire listing:
      1. Check if we already sent a warning (deduplication).
      2. Fetch the donor's email.
      3. Write a Notification row.
      4. Send the email.
      5. Commit.

    Errors for individual listings are caught so one bad listing doesn't
    abort the whole job.
    """
    try:
        # ── Deduplication: already warned about this listing? ──────────────────
        # We look for an existing notification for this user whose message
        # contains a unique marker for this listing's expiry warning.
        # Simple but effective at this scale. A real system would use a
        # dedicated boolean flag on the FoodListing model instead.
        dedup_marker = f"[expiry-warn:{listing.id}]"
        existing = await session.execute(
            select(Notification).where(
                Notification.user_id == listing.donor_id,
                Notification.message.contains(dedup_marker),
            )
        )
        if existing.scalar_one_or_none() is not None:
            logger.debug(
                "Scheduler: expiry warning already sent for listing id=%d, skipping.",
                listing.id,
            )
            return

        # ── Fetch donor for email address ──────────────────────────────────────
        donor_result = await session.execute(
            select(User).where(User.id == listing.donor_id)
        )
        donor = donor_result.scalar_one_or_none()
        if donor is None:
            logger.warning(
                "Scheduler: donor id=%d not found for listing id=%d — skipping.",
                listing.donor_id,
                listing.id,
            )
            return

        # ── Format expiry time for human display ───────────────────────────────
        expiry_str = (
            listing.expiry_time.strftime("%Y-%m-%d %H:%M UTC")
            if listing.expiry_time
            else "unknown"
        )

        # ── Build notification message (include dedup marker) ──────────────────
        # The marker is invisible to users but lets us detect it in the DB.
        # Format: "Your listing 'X' is expiring soon (at Y). [expiry-warn:42]"
        notification_message = (
            f"Your listing '{listing.title}' is expiring soon "
            f"(at {expiry_str}). Please take action if the food is still available. "
            f"{dedup_marker}"
        )

        # ── Write Notification row (store-then-send pattern) ───────────────────
        await create_notification(
            db=session,
            user_id=donor.id,
            message=notification_message,
        )
        await session.commit()  # Commit the notification row immediately so it's
                                # visible in the in-app list even if email fails.

        # ── Send email ────────────────────────────────────────────────────────
        subject, body = render_expiry_warning(
            listing_title=listing.title,
            expiry_time=expiry_str,
        )
        await send_email(
            to_email=donor.email,
            subject=subject,
            body=body,
        )
        # send_email handles its own errors — it never raises.

    except Exception as exc:
        # Catch-all so one broken listing never stops the job from
        # processing the remaining listings.
        logger.exception(
            "Scheduler: unexpected error processing listing id=%d: %s",
            listing.id,
            exc,
        )
        await session.rollback()
