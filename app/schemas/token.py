"""
app/schemas/token.py — Pydantic Schemas for JWT Token Responses
================================================================

WHY A SEPARATE FILE?
  Token schemas have nothing to do with user profile data — mixing them into
  user.py would violate the single-responsibility principle and make it harder
  to find things. A dedicated module also makes it easy to add new token-related
  schemas later (e.g., a RefreshRequest schema for a /auth/refresh endpoint).

INTERVIEW TALKING POINT:
  "I follow schema layering: what the client sends in (TokenData) is modelled
  separately from what we return out (TokenResponse). This keeps request and
  response contracts explicit and independently evolvable."
"""

from pydantic import BaseModel


# ── Token Response ────────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    """
    Returned by POST /auth/login on success.

    Fields:
      access_token  — Short-lived JWT (default 30 min). Sent in every
                      subsequent request as 'Authorization: Bearer <token>'.
      refresh_token — Longer-lived JWT (default 7 days). Used ONLY to obtain
                      a new access token when the current one expires.
                      WHY TWO TOKENS? If we only had one long-lived token,
                      a leak would be catastrophic for a week. Two tokens
                      limit blast radius: the access token expires quickly,
                      and the refresh token can be rotated or revoked.
      token_type    — OAuth2 spec requires this field; value is always "bearer".
                      The client prepends it to the header:
                      'Authorization: Bearer <access_token>'
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ── Token Data (internal) ─────────────────────────────────────────────────────
class TokenData(BaseModel):
    """
    Represents the decoded, validated contents of a JWT payload.

    WHY THIS EXISTS:
      After decoding a token we get a raw dict. Parsing it into a typed
      Pydantic model immediately gives us validation and IDE autocompletion.
      If the token is missing expected fields, Pydantic raises a ValidationError
      rather than us getting a KeyError somewhere deep in business logic.

    Fields:
      user_id — Parsed from the `sub` claim. We store user ID (not email)
                in `sub` because IDs never change; emails can be updated.
    """

    user_id: int | None = None
