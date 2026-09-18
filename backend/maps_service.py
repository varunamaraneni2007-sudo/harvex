"""
Google Maps Distance Matrix integration.

Provides real road distances between the farmer's location and each market.
Falls back gracefully when the API key is missing or the call fails — the
decision engine always has a usable transport cost.
"""
import os
from typing import Optional, List

import httpx

# Transport cost model: ₹/kg = base_handling + distance_km × per_km_rate
# Calibrated so static fallback values are reproduced at approximate road distances:
#   Vijayawada ≈  0 km → ₹0.50/kg  (matches FreshLink / Local Mandi statics)
#   Guntur     ≈ 65 km → ₹1.18/kg  (≈ Guntur Hub static ₹1.20)
#   Hyderabad  ≈275 km → ₹3.39/kg  (≈ Hyderabad Metro static ₹3.50)
LOCAL_BASE_COST_PER_KG = 0.50   # ₹/kg base loading/handling cost
KM_RATE_PER_KG = 0.0105         # ₹/kg/km truck freight rate

# In-process cache so repeated submits from the same location are free.
# Keys are (origin_lower, destination_lower) tuples.
DISTANCE_CACHE: dict = {}


def _get_api_key() -> Optional[str]:
    key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    return key if key else None


def get_distance_km(origin: str, destination: str) -> Optional[float]:
    """
    Return road distance in km between origin and destination, or None if the
    API key is absent or the request fails. Results are cached in-process.
    """
    if not _get_api_key():
        return None

    cache_key = (origin.strip().lower(), destination.strip().lower())
    if cache_key in DISTANCE_CACHE:
        return DISTANCE_CACHE[cache_key]

    try:
        resp = httpx.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params={
                "origins": origin,
                "destinations": destination,
                "mode": "driving",
                "key": _get_api_key(),
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        element = data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            return None
        km = round(element["distance"]["value"] / 1000.0, 1)
        DISTANCE_CACHE[cache_key] = km
        return km
    except Exception:
        return None


def transport_cost_from_distance(distance_km: float) -> float:
    """Convert road distance in km to ₹/kg transport cost."""
    return round(LOCAL_BASE_COST_PER_KG + distance_km * KM_RATE_PER_KG, 4)


def enrich_markets_with_distances(farmer_location: str, markets: List[dict]) -> List[dict]:
    """
    Return a copy of each market dict, with transport_cost_per_kg updated from
    a real road-distance lookup where the Maps API is available, plus a
    distance_km field.  Falls back to the original static transport_cost_per_kg
    when Maps is unavailable.
    """
    result = []
    for m in markets:
        distance_km = get_distance_km(farmer_location, m["location"])
        if distance_km is not None:
            result.append({
                **m,
                "transport_cost_per_kg": transport_cost_from_distance(distance_km),
                "distance_km": distance_km,
            })
        else:
            result.append({**m, "distance_km": None})
    return result
