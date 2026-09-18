"""
Tests for the Google Maps distance service and its integration with the
decision engine.  All HTTP calls are mocked — no live API key needed.
"""
import os
from unittest.mock import MagicMock, patch

import pytest
import maps_service


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok_response(distance_m: int):
    """Build a mock httpx response that looks like a Maps API success."""
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "rows": [{"elements": [{"status": "OK", "distance": {"value": distance_m}}]}]
    }
    return m


def _clear_cache():
    maps_service.DISTANCE_CACHE.clear()


# ── API key handling ──────────────────────────────────────────────────────────

def test_get_distance_returns_none_without_api_key():
    _clear_cache()
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}):
        result = maps_service.get_distance_km("Vijayawada", "Hyderabad")
    assert result is None


def test_get_distance_returns_km_on_success():
    _clear_cache()
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.get", return_value=_ok_response(275_000)):
            result = maps_service.get_distance_km("Vijayawada", "Hyderabad")
    assert result == 275.0


def test_get_distance_returns_none_on_network_error():
    _clear_cache()
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.get", side_effect=Exception("network error")):
            result = maps_service.get_distance_km("Vijayawada", "Hyderabad")
    assert result is None


def test_get_distance_returns_none_when_element_status_not_ok():
    _clear_cache()
    bad_resp = MagicMock()
    bad_resp.raise_for_status.return_value = None
    bad_resp.json.return_value = {
        "rows": [{"elements": [{"status": "NOT_FOUND"}]}]
    }
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.get", return_value=bad_resp):
            result = maps_service.get_distance_km("Nowhere", "Nowhere")
    assert result is None


def test_get_distance_rounds_to_one_decimal():
    _clear_cache()
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.get", return_value=_ok_response(65_432)):
            result = maps_service.get_distance_km("Vijayawada", "Guntur")
    assert result == 65.4


# ── Cache ─────────────────────────────────────────────────────────────────────

def test_cache_prevents_duplicate_http_calls():
    _clear_cache()
    mock_get = MagicMock(return_value=_ok_response(65_000))
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.get", mock_get):
            maps_service.get_distance_km("Vijayawada", "Guntur")
            maps_service.get_distance_km("Vijayawada", "Guntur")
    assert mock_get.call_count == 1


def test_cache_is_case_insensitive():
    _clear_cache()
    mock_get = MagicMock(return_value=_ok_response(65_000))
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}):
        with patch("httpx.get", mock_get):
            maps_service.get_distance_km("Vijayawada", "Guntur")
            maps_service.get_distance_km("vijayawada", "GUNTUR")
    assert mock_get.call_count == 1


# ── Transport cost formula ────────────────────────────────────────────────────

def test_transport_cost_at_zero_km():
    cost = maps_service.transport_cost_from_distance(0.0)
    assert cost == maps_service.LOCAL_BASE_COST_PER_KG


def test_transport_cost_at_100km():
    expected = round(maps_service.LOCAL_BASE_COST_PER_KG + 100 * maps_service.KM_RATE_PER_KG, 4)
    assert maps_service.transport_cost_from_distance(100.0) == expected


def test_transport_cost_increases_with_distance():
    assert maps_service.transport_cost_from_distance(100) < maps_service.transport_cost_from_distance(300)


# ── enrich_markets_with_distances ────────────────────────────────────────────

_SAMPLE_MARKETS = [
    {
        "market_name": "Local Mandi",
        "location": "Vijayawada",
        "transport_cost_per_kg": 0.5,
        "base_price_per_kg": 12.0,
        "capacity_kg": 500.0,
        "base_spoilage_pct": 3.0,
    },
    {
        "market_name": "Hyderabad Metro Market",
        "location": "Hyderabad",
        "transport_cost_per_kg": 3.5,
        "base_price_per_kg": 20.0,
        "capacity_kg": 5000.0,
        "base_spoilage_pct": 8.0,
    },
]


def test_enrich_keeps_static_cost_when_maps_unavailable():
    with patch("maps_service.get_distance_km", return_value=None):
        result = maps_service.enrich_markets_with_distances("Vijayawada", _SAMPLE_MARKETS)
    assert result[0]["transport_cost_per_kg"] == 0.5
    assert result[1]["transport_cost_per_kg"] == 3.5


def test_enrich_sets_distance_none_when_unavailable():
    with patch("maps_service.get_distance_km", return_value=None):
        result = maps_service.enrich_markets_with_distances("Vijayawada", _SAMPLE_MARKETS)
    assert all(m["distance_km"] is None for m in result)


def test_enrich_updates_transport_cost_from_real_distance():
    with patch("maps_service.get_distance_km", return_value=275.0):
        result = maps_service.enrich_markets_with_distances("Vijayawada", _SAMPLE_MARKETS)
    expected = maps_service.transport_cost_from_distance(275.0)
    assert result[1]["transport_cost_per_kg"] == expected


def test_enrich_records_distance_km_field():
    with patch("maps_service.get_distance_km", return_value=65.0):
        result = maps_service.enrich_markets_with_distances("Vijayawada", _SAMPLE_MARKETS)
    assert result[0]["distance_km"] == 65.0


def test_enrich_does_not_mutate_original_markets():
    original_cost = _SAMPLE_MARKETS[1]["transport_cost_per_kg"]
    with patch("maps_service.get_distance_km", return_value=275.0):
        maps_service.enrich_markets_with_distances("Vijayawada", _SAMPLE_MARKETS)
    assert _SAMPLE_MARKETS[1]["transport_cost_per_kg"] == original_cost


def test_enrich_mixed_availability():
    """Some markets get real distances, others fall back."""
    def _fake_dist(origin, dest):
        return 65.0 if dest.lower() == "vijayawada" else None

    with patch("maps_service.get_distance_km", side_effect=_fake_dist):
        result = maps_service.enrich_markets_with_distances("Farmer Town", _SAMPLE_MARKETS)
    # Vijayawada market: real distance applied
    assert result[0]["distance_km"] == 65.0
    assert result[0]["transport_cost_per_kg"] == maps_service.transport_cost_from_distance(65.0)
    # Hyderabad market: static cost kept
    assert result[1]["distance_km"] is None
    assert result[1]["transport_cost_per_kg"] == 3.5


# ── Integration: submission uses enriched markets ─────────────────────────────

def test_submission_uses_real_distances_when_maps_available():
    """With Maps returning real distances, optimize result must change from static."""
    from main import ProduceInput, submission

    data = ProduceInput(
        crop="onion", quantity_kg=400, quality="Standard",
        farmer_location="Vijayawada", harvest_date="18/09/2026", shelf_life_days=5,
    )

    # Simulate Maps returning much higher transport costs (e.g. 500 km to everyone)
    with patch("maps_service.get_distance_km", return_value=500.0):
        with patch("main._get_supabase", return_value=None):
            resp_with_maps = submission(data)

    with patch("maps_service.get_distance_km", return_value=None):
        with patch("main._get_supabase", return_value=None):
            resp_static = submission(data)

    # At 500 km the transport cost is higher → net value must be lower
    assert resp_with_maps.optimize.recommended.total_net_value < resp_static.optimize.recommended.total_net_value


def test_submission_fallback_matches_static_values():
    """When Maps is unavailable, submission must return the same numbers as before."""
    from main import ProduceInput, submission

    data = ProduceInput(
        crop="onion", quantity_kg=400, quality="Standard",
        farmer_location="Vijayawada", harvest_date="18/09/2026", shelf_life_days=5,
    )
    with patch("maps_service.get_distance_km", return_value=None):
        with patch("main._get_supabase", return_value=None):
            resp = submission(data)

    assert resp.plans.plan_a.total_net_value == 6542.0
