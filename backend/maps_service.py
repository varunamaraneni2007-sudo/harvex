"""
Google Routes API integration (v2 — replaces the legacy Distance Matrix API).

Provides real road distances and travel times between the farmer's location
and each market.  Falls back gracefully when the API key is missing or the
call fails — the decision engine always has a usable transport cost.
"""
import os
from typing import Optional, List, Tuple

import httpx

# Transport cost model: ₹/kg = base_handling + distance_km × per_km_rate
# Calibrated so static fallback values are reproduced at approximate road distances:
#   Vijayawada ≈  0 km → ₹0.50/kg  (matches FreshLink / Local Mandi statics)
#   Guntur     ≈ 65 km → ₹1.18/kg  (≈ Guntur Hub static ₹1.20)
#   Hyderabad  ≈275 km → ₹3.39/kg  (≈ Hyderabad Metro static ₹3.50)
LOCAL_BASE_COST_PER_KG = 0.50   # ₹/kg base loading/handling cost
KM_RATE_PER_KG = 0.0105         # ₹/kg/km truck freight rate

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# In-process cache: (origin_lower, destination_lower) → (distance_km, travel_time_minutes)
DISTANCE_CACHE: dict = {}


def _get_api_key() -> Optional[str]:
    key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    return key if key else None


def _parse_duration_seconds(duration_str: str) -> float:
    """Parse Routes API duration string '18000s' → seconds as float."""
    return float(duration_str.rstrip("s"))


def get_route(origin: str, destination: str) -> Optional[Tuple[float, float]]:
    """
    Call the Google Routes API and return (distance_km, travel_time_minutes),
    or None if the key is absent, no route exists, or the request fails.
    Results are cached in-process so repeated lookups from the same location
    are free.
    """
    if not _get_api_key():
        return None

    cache_key = (origin.strip().lower(), destination.strip().lower())
    if cache_key in DISTANCE_CACHE:
        return DISTANCE_CACHE[cache_key]

    try:
        resp = httpx.post(
            ROUTES_URL,
            headers={
                "X-Goog-Api-Key": _get_api_key(),
                "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
                "Content-Type": "application/json",
            },
            json={
                "origin": {"address": origin},
                "destination": {"address": destination},
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_UNAWARE",
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        routes = data.get("routes", [])
        if not routes:
            return None
        route = routes[0]
        km = round(route["distanceMeters"] / 1000.0, 1)
        minutes = round(_parse_duration_seconds(route["duration"]) / 60.0, 1)
        result: Tuple[float, float] = (km, minutes)
        DISTANCE_CACHE[cache_key] = result
        return result
    except Exception:
        return None


def get_distance_km(origin: str, destination: str) -> Optional[float]:
    """Return road distance in km, or None if unavailable."""
    route = get_route(origin, destination)
    return route[0] if route is not None else None


def transport_cost_from_distance(distance_km: float) -> float:
    """Convert road distance in km to ₹/kg transport cost."""
    return round(LOCAL_BASE_COST_PER_KG + distance_km * KM_RATE_PER_KG, 4)


def enrich_markets_with_distances(farmer_location: str, markets: List[dict]) -> List[dict]:
    """
    Return a copy of each market dict, with transport_cost_per_kg updated from
    a real road-distance lookup where the Routes API is available, plus
    distance_km and travel_time_minutes fields. Falls back to the original
    static transport_cost_per_kg when the API is unavailable.
    """
    result = []
    for m in markets:
        route = get_route(farmer_location, m["location"])
        if route is not None:
            distance_km, travel_time_minutes = route
            result.append({
                **m,
                "transport_cost_per_kg": transport_cost_from_distance(distance_km),
                "distance_km": distance_km,
                "travel_time_minutes": travel_time_minutes,
            })
        else:
            result.append({**m, "distance_km": None, "travel_time_minutes": None})
    return result
