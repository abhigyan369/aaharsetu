"""
app/core/cloudinary_service.py — Cloudinary Image Upload Service
================================================================

WHY A DEDICATED SERVICE MODULE?
  The router's job is HTTP: parse the request, call business logic, return
  a response. Image upload is business logic (validation, external API call,
  URL extraction). Keeping it here:
    - Makes the router thin and readable.
    - Makes it easy to swap Cloudinary for S3 / Backblaze later — only this
      file changes.
    - Makes it unit-testable in isolation (mock `upload_image()`).

CLOUDINARY ACCOUNT SETUP (one-time):
  1. Sign up free at https://cloudinary.com
  2. Dashboard → top-left shows your Cloud Name.
  3. Settings → API Keys → copy API Key + API Secret.
  4. Paste all three into your .env file:
       CLOUDINARY_CLOUD_NAME=your_cloud_name
       CLOUDINARY_API_KEY=123456789012345
       CLOUDINARY_API_SECRET=AbCdEf_your_secret_here
  5. On Render / Railway: add the same three variables in the platform's
     "Environment Variables" section — never commit them to git.

HOW CLOUDINARY UPLOAD WORKS:
  1. We read the file bytes from the UploadFile stream.
  2. We call cloudinary.uploader.upload() (sync SDK call — see ASYNC NOTE below).
  3. Cloudinary stores the file, resizes/CDN-caches it, returns a JSON dict
     that includes `secure_url` — a permanent HTTPS CDN URL.
  4. We store that URL string in FoodListing.image_url (plain VARCHAR).
  5. When the frontend renders the listing, it uses that URL as <img src=...>.
     The image is served from Cloudinary's global CDN — not from our server.

ASYNC NOTE:
  The Cloudinary Python SDK is synchronous (it uses `requests` internally).
  We wrap the upload call with `asyncio.get_event_loop().run_in_executor(None, ...)`,
  which runs it in a thread-pool executor. This means the FastAPI event loop
  is NOT blocked during the upload — other requests continue to be served while
  the image is being transferred to Cloudinary.

  INTERVIEW TALKING POINT:
    "FastAPI is async, but not all libraries are. Calling a sync function
    directly in an async endpoint blocks the event loop for every other request.
    run_in_executor offloads it to a thread pool so the event loop stays free."
"""

import asyncio
import io
import logging
from functools import partial

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Allowed MIME types ────────────────────────────────────────────────────────
# We whitelist rather than blacklist — anything not in this set is rejected.
ALLOWED_CONTENT_TYPES: set[str] = {"image/jpeg", "image/png"}
ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png"}

# ── Size limit ────────────────────────────────────────────────────────────────
# 5 MB in bytes. We read the full file into memory anyway (small images) so
# checking len(data) is safe and avoids streaming partial uploads to Cloudinary.
MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB

# ── Placeholder URL ───────────────────────────────────────────────────────────
# Used when the donor submits a listing without an image.
# This is a public, stable Cloudinary sample image. You can replace it with
# your own by uploading a custom placeholder to your Cloudinary account and
# pasting its secure_url here.
PLACEHOLDER_IMAGE_URL: str = (
    "https://res.cloudinary.com/demo/image/upload/v1/samples/food/spices.jpg"
)


# ── One-time SDK configuration ─────────────────────────────────────────────────
def _configure_cloudinary() -> None:
    """
    Configure the Cloudinary SDK with credentials from settings.

    This is called once at module import time (when the module is first used).
    The Cloudinary SDK stores config globally in cloudinary.config — it does
    not create a per-request client object.

    If any credential is missing (empty string), Cloudinary calls will fail at
    runtime with an AuthorizationRequired error — not at startup. This is
    intentional: the app should still boot without Cloudinary keys so developers
    can run it locally without an account (listings with no image get the
    placeholder and no upload is attempted).
    """
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,  # Always use HTTPS URLs (never HTTP)
    )


_configure_cloudinary()


# ── Validation helper ─────────────────────────────────────────────────────────
def _validate_image_file(filename: str | None, content_type: str | None, size: int) -> None:
    """
    Validate file type and size before uploading.

    We check BOTH the content-type header AND the file extension because:
    - Content-type is sent by the client and can be spoofed.
    - Extension alone is easy to fake (rename a .exe to .jpg).
    - Checking both adds a small layer of defence; real validation would
      inspect the file magic bytes (first few bytes), but for a portfolio
      project this is sufficient and explainable.

    Raises HTTPException (422 or 413) on validation failure so FastAPI
    automatically returns the right status code to the client.
    """
    # ── Extension check ───────────────────────────────────────────────────────
    if filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unsupported file extension '{ext}'. "
                    f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
                ),
            )

    # ── Content-type check ────────────────────────────────────────────────────
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported content type '{content_type}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}."
            ),
        )

    # ── Size check ────────────────────────────────────────────────────────────
    if size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        actual_mb = size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File is too large ({actual_mb:.1f} MB). "
                f"Maximum allowed size is {max_mb:.0f} MB."
            ),
        )


# ── Public upload function ────────────────────────────────────────────────────
async def upload_image(file: UploadFile | None) -> str:
    """
    Upload an image file to Cloudinary and return its CDN URL.

    If `file` is None (no image submitted), the placeholder URL is returned
    immediately — no Cloudinary call is made.

    Args:
        file: FastAPI UploadFile from File() parameter, or None.

    Returns:
        A permanent HTTPS Cloudinary CDN URL string (e.g.
        "https://res.cloudinary.com/<cloud>/image/upload/v123/food_waste/abc.jpg")
        or PLACEHOLDER_IMAGE_URL if no file was provided.

    Raises:
        HTTPException 422: invalid file type / extension.
        HTTPException 413: file exceeds 5 MB.
        HTTPException 500: Cloudinary upload failed (logged; not exposed to client).

    INTERVIEW TALKING POINT — why store the URL, not the bytes?
        Storing the URL means our database row is tiny (a VARCHAR). The heavy
        binary data lives on Cloudinary's CDN servers. When the browser renders
        <img src="https://res.cloudinary.com/...">, it fetches the image
        directly from Cloudinary — our backend never re-serves it.
        This offloads bandwidth + storage costs to a service purpose-built for it.
    """
    # ── No file provided: return placeholder immediately ──────────────────────
    if file is None or file.filename == "":
        return PLACEHOLDER_IMAGE_URL

    # ── Read file bytes ───────────────────────────────────────────────────────
    # We read the whole file into memory. For a 5 MB max this is fine —
    # we're not streaming GB-scale video. The bytes are then passed to the
    # Cloudinary SDK as a BytesIO object.
    data: bytes = await file.read()

    # ── Validate (type + size) ────────────────────────────────────────────────
    _validate_image_file(
        filename=file.filename,
        content_type=file.content_type,
        size=len(data),
    )

    # ── Upload to Cloudinary (in thread executor — see module docstring) ──────
    # We wrap the sync SDK call so the async event loop is not blocked.
    # `partial` is used to bind keyword arguments to the function before
    # passing it to run_in_executor (which only accepts callables + positional args).
    loop = asyncio.get_event_loop()
    try:
        upload_fn = partial(
            cloudinary.uploader.upload,
            io.BytesIO(data),
            folder=settings.CLOUDINARY_UPLOAD_FOLDER,
            resource_type="image",
            # `unique_filename=True` lets Cloudinary generate a collision-safe name.
            # `overwrite=False` ensures we never accidentally clobber an existing image.
            unique_filename=True,
            overwrite=False,
        )
        result: dict = await loop.run_in_executor(None, upload_fn)
    except Exception as exc:
        # Log the full error for debugging but don't expose Cloudinary internals
        # to the client (could leak API details).
        logger.error("Cloudinary upload failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Image upload failed. The listing was not created. "
                "Please try again or submit without an image."
            ),
        ) from exc

    # ── Extract secure URL ────────────────────────────────────────────────────
    # Cloudinary returns a dict; `secure_url` is always HTTPS (we set secure=True
    # in _configure_cloudinary). This is the URL we store in the DB.
    secure_url: str = result["secure_url"]
    logger.info(
        "Image uploaded to Cloudinary: public_id=%s url=%s",
        result.get("public_id"),
        secure_url,
    )
    return secure_url
