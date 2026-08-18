"""
app/core/utils.py — General-purpose utility functions
======================================================

WHY THIS FILE EXISTS:
  Small, stateless helper functions that don't belong to any one feature
  live here. Currently it holds the haversine distance function used by
  the listings router for proximity filtering.

INTERVIEW TALKING POINT — Haversine vs. a routing API:
  "We don't call Google Maps or any external service for distance filtering.
  We compute the straight-line (great-circle) distance in pure Python using
  the haversine formula. It's fast (microseconds), has no cost, no rate
  limits, and no network dependency.  For food pickup, straight-line
  distance is a good-enough proxy — if food is 2 km away by air, it's
  probably within 5 km by road. A real ML 'smart matching' would layer in
  road-graph data, but the haversine gives us the spatial intuition cheaply."
"""

import math


# ── Haversine Formula ─────────────────────────────────────────────────────────
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the great-circle distance (in kilometres) between two points
    on the Earth's surface, identified by their latitude and longitude.

    HOW IT WORKS — step by step:

    The Earth is a sphere (approximate radius R = 6,371 km).
    Given two points P1=(lat1, lon1) and P2=(lat2, lon2) in decimal degrees:

      1. CONVERT TO RADIANS
         Trigonometric functions (sin, cos) in Python expect radians.
         Degrees × (π / 180) → radians.

      2. COMPUTE ANGULAR DIFFERENCES
         Δlat = lat2_rad − lat1_rad
         Δlon = lon2_rad − lon1_rad

      3. HAVERSINE INTERMEDIATE VALUE (the 'a' term)
         a = sin²(Δlat/2) + cos(lat1_rad) × cos(lat2_rad) × sin²(Δlon/2)

         sin²(Δlat/2) captures the north-south difference.
         The middle term captures the east-west difference, scaled by
         how far we are from the poles (cos → 0 near poles, where
         lines of longitude converge).

      4. CENTRAL ANGLE (the 'c' term)
         c = 2 × arcsin(√a)

         arcsin(√a) gives the half-angle of the arc between the two points
         on the unit sphere.  Multiplying by 2 gives the full central angle.

      5. DISTANCE
         distance = R × c   (arc length = radius × angle in radians)

    WHY NOT EUCLIDEAN (straight-line in 3D)?
      Euclidean distance ignores the Earth's curvature. For distances > ~10 km
      the error becomes noticeable. Haversine is accurate to within ~0.5% for
      distances up to several thousand km (only breaks down near the poles,
      which is irrelevant for food redistribution).

    NUMERICAL STABILITY NOTE:
      We clamp `a` to [0, 1] before the sqrt to guard against floating-point
      rounding errors that can push `a` to values like -1e-16, which would
      make math.sqrt() raise a ValueError.

    Args:
        lat1: Latitude of point 1, in decimal degrees (-90 to 90).
        lon1: Longitude of point 1, in decimal degrees (-180 to 180).
        lat2: Latitude of point 2, in decimal degrees.
        lon2: Longitude of point 2, in decimal degrees.

    Returns:
        Great-circle distance in kilometres (float).

    Example:
        >>> haversine(12.9716, 77.5946, 13.0827, 80.2707)  # Bengaluru→Chennai
        291.3   # approximately
    """
    # Earth's mean radius in kilometres (WGS-84 spherical approximation)
    R = 6_371.0

    # Step 1 — Convert all inputs from degrees to radians
    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lat2_r = math.radians(lat2)
    lon2_r = math.radians(lon2)

    # Step 2 — Angular differences
    delta_lat = lat2_r - lat1_r
    delta_lon = lon2_r - lon1_r

    # Step 3 — Haversine formula for the 'a' term
    # math.sin(x) ** 2  is the haversine of angle x (hav(x) = sin²(x/2))
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(delta_lon / 2) ** 2
    )

    # Guard against floating-point overshoot (e.g. 1.0000000000000002)
    a = max(0.0, min(1.0, a))

    # Step 4 — Central angle
    c = 2 * math.asin(math.sqrt(a))

    # Step 5 — Convert to kilometres
    return R * c


# ── Convenience helper ────────────────────────────────────────────────────────
def is_within_distance(
    user_lat: float,
    user_lon: float,
    listing_lat: float | None,
    listing_lon: float | None,
    max_km: float,
) -> bool:
    """
    Return True if the listing's coordinates are within `max_km` of the user.

    If the listing has no coordinates (latitude/longitude is None), we return
    True — "no location data" means we can't exclude it, so we include it and
    let the receiver decide. This keeps the filter non-exclusive when geo data
    is absent.

    Used by GET /listings when `max_distance_km` query param is provided.
    """
    if listing_lat is None or listing_lon is None:
        # Cannot compute distance — include the listing optimistically
        return True

    distance = haversine(user_lat, user_lon, listing_lat, listing_lon)
    return distance <= max_km
