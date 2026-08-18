"""
app/core/email_service.py — Async Email Delivery
==================================================

WHY aiosmtplib INSTEAD OF smtplib?
  FastAPI runs on an async event loop (uvicorn). The standard library's
  `smtplib` is synchronous — it blocks the entire event loop during the
  TCP connection, SMTP handshake, and DATA transfer. That means every
  other request waiting in the queue has to wait for the email to send.
  `aiosmtplib` is a pure-async implementation that awaits I/O without
  blocking, keeping the event loop free.

WHY NOT fastapi-mail?
  fastapi-mail is a convenience wrapper around aiosmtplib anyway. Going
  one level lower keeps our dependency tree lean, the code is equally
  simple, and it's a cleaner interview story ("I use the async SMTP
  client directly and know what's happening underneath").

SWAPPING TO PRODUCTION EMAIL PROVIDERS:
  No code changes needed — just update .env variables:

  Mailtrap (dev sandbox) → smtp.mailtrap.io:587
  Gmail (dev, App Password) → smtp.gmail.com:587
  SendGrid (production) → smtp.sendgrid.net:587, user="apikey"
  Resend (production) → smtp.resend.com:465, SMTP_USE_TLS=false

  The EMAILS_ENABLED master switch lets you run locally without any SMTP
  config: the app logs a warning and skips the send, but always writes
  the Notification row to the DB so in-app notifications still work.

INTERVIEW TALKING POINT:
  "Email sends are best-effort in this system. I deliberately don't let a
  failed SMTP connection propagate as an HTTP error — food redistribution
  can't be blocked because Mailtrap is down. The Notification is always
  stored in Postgres regardless, so the user sees it in-app. This is the
  'store-then-send' pattern: write to durable storage first, attempt
  side-effects second."
"""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Plain-text Email Templates ────────────────────────────────────────────────
# We use simple plain-text templates — no HTML, no Jinja2.
# Rationale: plain text works in every email client (even text-only MUAs),
# has no rendering bugs, and is easier to test. We can upgrade to HTML later.

def render_claim_notification(
    listing_title: str,
    receiver_name: str,
    pickup_window_start: str,
    pickup_window_end: str,
) -> tuple[str, str]:
    """
    Build the subject + body for a "your listing was claimed" email.

    Returns:
        (subject, body) — both plain text strings.
    """
    subject = f"Your listing '{listing_title}' has been claimed!"
    body = f"""\
Hello,

Great news! Your food listing "{listing_title}" has been claimed by {receiver_name}.

Pickup window:
  From: {pickup_window_start}
  To:   {pickup_window_end}

Please make sure the food is ready for pickup during this window.
If you need to reach the receiver, you can view their details on the platform.

Thank you for reducing food waste!

— {settings.EMAILS_FROM_NAME}
"""
    return subject, body


def render_expiry_warning(
    listing_title: str,
    expiry_time: str,
) -> tuple[str, str]:
    """
    Build the subject + body for a "listing about to expire" warning email.

    Returns:
        (subject, body) — both plain text strings.
    """
    subject = f"Reminder: '{listing_title}' expires soon"
    body = f"""\
Hello,

This is a reminder that your food listing "{listing_title}" is expiring soon.

Expiry time: {expiry_time}

If the food has not been claimed yet, consider:
  - Extending the expiry time by editing the listing
  - Contacting a local food bank directly
  - Marking it as cancelled if it is no longer available

Act quickly to avoid waste!

— {settings.EMAILS_FROM_NAME}
"""
    return subject, body


# ── Core Send Function ────────────────────────────────────────────────────────
async def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send a plain-text email via SMTP (async, non-blocking).

    HOW IT WORKS:
      1. Check EMAILS_ENABLED — if False, log and return early (no error raised).
         This is the local dev safety valve: the app works without SMTP config.
      2. Build an EmailMessage object (stdlib, zero deps).
      3. Connect to the SMTP server with aiosmtplib.
         - SMTP_USE_TLS=True: STARTTLS upgrade on port 587 (most common).
         - SMTP_USE_TLS=False: plain connection, used when server already wraps
           in SSL (port 465 implicit TLS, e.g. Resend).
      4. Authenticate with SMTP_USER / SMTP_PASSWORD.
      5. Send and disconnect.

    RESILIENCE:
      Any SMTP error is caught and logged — it never propagates as an exception.
      The caller (notification_service) always writes the DB row regardless.

    Args:
        to_email: Recipient email address.
        subject:  Email subject line.
        body:     Plain-text email body.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    if not settings.EMAILS_ENABLED:
        logger.info(
            "EMAILS_ENABLED=False — skipping email to %s (subject: %s). "
            "Set EMAILS_ENABLED=true in .env to send real emails.",
            to_email,
            subject,
        )
        return False

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning(
            "SMTP_USER or SMTP_PASSWORD is empty — cannot send email to %s. "
            "Check your .env configuration.",
            to_email,
        )
        return False

    # Build the message using stdlib's EmailMessage (cleaner than string concat)
    message = EmailMessage()
    message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)  # sets Content-Type: text/plain automatically

    try:
        # aiosmtplib.send() is a high-level helper that:
        #   - opens a connection
        #   - optionally does STARTTLS (start_tls=True)
        #   - authenticates
        #   - sends the message
        #   - closes the connection
        # All in one awaitable call — no explicit connect/quit needed.
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS,
        )
        logger.info("Email sent successfully to %s (subject: %s)", to_email, subject)
        return True

    except aiosmtplib.SMTPException as exc:
        # Catch all SMTP-level errors (auth failure, connection refused, etc.)
        # and log them without crashing the caller.
        logger.error(
            "Failed to send email to %s: %s. "
            "The in-app Notification row was still created.",
            to_email,
            exc,
        )
        return False
    except OSError as exc:
        # Network-level errors (DNS failure, connection timeout, etc.)
        logger.error(
            "Network error sending email to %s: %s. "
            "Check SMTP_HOST and SMTP_PORT in .env.",
            to_email,
            exc,
        )
        return False
