"""
Tests for the /api/marketplace endpoint and _compute_suitability helper.
All HTTP calls to Google Routes are mocked — no live API key needed.
"""
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app, _compute_suitability, MARKETS, QUALITY_ORDER

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _market(
    name="Test Market",
    capacity=1000.0,
    price=15.0,
    min_quality="Low",
    accepted_crops=None,
    buyer_type="Wholesale Buyer",
    spoilage=5.0,
    transport=1.2,
    travel_time_minutes=None,
):
    return {
        "market_name": name,
        "buyer_type": buyer_type,
        "location": "Guntur",
        "base_price_per_kg": price,
        "transport_cost_per_kg": transport,
        "capacity_kg": capacity,
        "base_spoilage_pct": spoilage,
        "accepted_crops": accepted_crops or ["all"],
        "min_quality": min_quality,
        "travel_time_minutes": travel_time_minutes,
    }


def _mp_get(farmer_location="Vijayawada", **params):
    """Helper to call GET /api/marketplace with Maps mocked off."""
    with patch("maps_service.get_route", return_value=None):
        resp = client.get(
            "/api/marketplace",
            params={"farmer_location": farmer_location, **params},
        )
    return resp


# ── _compute_suitability unit tests ──────────────────────────────────────────

def test_suitable_with_no_context():
    level, reason = _compute_suitability(_market())
    assert level == "Suitable"


def test_suitable_when_all_match():
    m = _market(capacity=500, min_quality="Standard")
    level, reason = _compute_suitability(m, crop="onion", quality="Standard", quantity_kg=400)
    assert level == "Suitable"
    assert "Suitable" in reason


def test_partial_when_capacity_less_than_quantity():
    m = _market(capacity=200)
    level, reason = _compute_suitability(m, quantity_kg=400)
    assert level == "Partial"
    assert "200" in reason


def test_not_suitable_when_quality_too_low():
    m = _market(min_quality="Standard")
    level, reason = _compute_suitability(m, quality="Low")
    assert level == "Not Suitable"
    assert "Standard" in reason
    assert "Low" in reason


def test_not_suitable_when_quality_much_too_low():
    m = _market(min_quality="Premium")
    level, reason = _compute_suitability(m, quality="Low")
    assert level == "Not Suitable"


def test_suitable_when_quality_exceeds_requirement():
    m = _market(min_quality="Standard")
    level, _ = _compute_suitability(m, quality="Premium")
    assert level == "Suitable"


def test_not_suitable_for_wrong_crop():
    m = _market(accepted_crops=["wheat", "rice"])
    level, reason = _compute_suitability(m, crop="onion")
    assert level == "Not Suitable"
    assert "onion" in reason.lower()


def test_suitable_when_accepts_all_crops():
    m = _market(accepted_crops=["all"])
    level, _ = _compute_suitability(m, crop="onion")
    assert level == "Suitable"


def test_partial_due_to_travel_time_risk():
    m = _market(travel_time_minutes=60 * 36)  # 36 hours travel
    level, reason = _compute_suitability(m, shelf_life_days=2)
    assert level == "Partial"
    assert "shelf life" in reason.lower() or "travel" in reason.lower()


def test_suitable_when_travel_within_shelf_life():
    m = _market(travel_time_minutes=60 * 2)  # 2 hours travel
    level, _ = _compute_suitability(m, shelf_life_days=5)
    assert level == "Suitable"


# ── /api/marketplace endpoint tests ──────────────────────────────────────────

def test_marketplace_returns_all_five_markets():
    resp = _mp_get()
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5


def test_marketplace_card_has_required_fields():
    resp = _mp_get()
    card = resp.json()[0]
    for field in [
        "market_name", "buyer_type", "location", "base_price_per_kg",
        "transport_cost_per_kg", "capacity_kg", "base_spoilage_pct",
        "accepted_crops", "min_quality", "suitability", "suitability_reason",
        "maps_live",
    ]:
        assert field in card, f"Missing field: {field}"


def test_marketplace_maps_live_false_without_api_key():
    resp = _mp_get()
    data = resp.json()
    assert all(not c["maps_live"] for c in data)
    assert all(c["distance_km"] is None for c in data)


def test_marketplace_maps_live_true_when_route_available():
    with patch("maps_service.get_route", return_value=(65.0, 90.0)):
        resp = client.get("/api/marketplace", params={"farmer_location": "Vijayawada"})
    data = resp.json()
    assert all(c["maps_live"] for c in data)
    assert all(c["distance_km"] == 65.0 for c in data)
    assert all(c["travel_time_minutes"] == 90.0 for c in data)


def test_marketplace_filter_min_price():
    resp = _mp_get(min_price_per_kg=16.0)
    data = resp.json()
    assert all(c["base_price_per_kg"] >= 16.0 for c in data)
    assert len(data) < 5  # Local Mandi (₹12) and FreezeMart (₹14) filtered out


def test_marketplace_filter_min_capacity():
    resp = _mp_get(min_capacity_kg=1000.0)
    data = resp.json()
    assert all(c["capacity_kg"] >= 1000.0 for c in data)
    # FreshLink (300 kg) and Local Mandi (500 kg) filtered out
    names = {c["market_name"] for c in data}
    assert "FreshLink Retail Aggregator" not in names
    assert "Local Mandi" not in names


def test_marketplace_filter_max_distance_excludes_known_far():
    # With live distances available, max_distance_km filters out far markets
    def _fake_route(origin, dest):
        return (300.0, 360.0) if "Hyderabad" in dest else (65.0, 90.0)

    with patch("maps_service.get_route", side_effect=_fake_route):
        resp = client.get(
            "/api/marketplace",
            params={"farmer_location": "Vijayawada", "max_distance_km": 150},
        )
    data = resp.json()
    names = {c["market_name"] for c in data}
    assert "Hyderabad Metro Market" not in names


def test_marketplace_max_distance_keeps_unknown_distance_markets():
    # Markets with distance_km=None should NOT be filtered out by max_distance_km
    def _fake_route(origin, dest):
        return (65.0, 90.0) if "Guntur" in dest else None

    with patch("maps_service.get_route", side_effect=_fake_route):
        resp = client.get(
            "/api/marketplace",
            params={"farmer_location": "Vijayawada", "max_distance_km": 50},
        )
    data = resp.json()
    # Vijayawada markets (distance unknown) must still appear
    names = {c["market_name"] for c in data}
    assert "Local Mandi" in names
    assert "FreshLink Retail Aggregator" in names


def test_marketplace_suitability_suitable_standard_quality():
    resp = _mp_get(crop="onion", quality="Standard", quantity_kg=400, shelf_life_days=5)
    data = resp.json()
    by_name = {c["market_name"]: c for c in data}
    # Guntur Wholesale Hub: min_quality Low, capacity 2000 → Suitable
    assert by_name["Guntur Wholesale Hub"]["suitability"] == "Suitable"


def test_marketplace_suitability_partial_for_small_capacity():
    # FreshLink capacity 300 < quantity 400 → Partial
    resp = _mp_get(crop="onion", quality="Standard", quantity_kg=400, shelf_life_days=5)
    data = resp.json()
    by_name = {c["market_name"]: c for c in data}
    assert by_name["FreshLink Retail Aggregator"]["suitability"] == "Partial"


def test_marketplace_suitability_not_suitable_low_quality_for_retail():
    # Hyderabad Metro Market requires Standard; Low quality → Not Suitable
    resp = _mp_get(crop="onion", quality="Low", quantity_kg=400, shelf_life_days=5)
    data = resp.json()
    by_name = {c["market_name"]: c for c in data}
    assert by_name["Hyderabad Metro Market"]["suitability"] == "Not Suitable"
    assert by_name["FreshLink Retail Aggregator"]["suitability"] == "Not Suitable"


def test_marketplace_net_value_calculated_when_quality_and_shelf_given():
    resp = _mp_get(crop="onion", quality="Standard", quantity_kg=400, shelf_life_days=5)
    data = resp.json()
    # At least one market should have a net_value_per_kg
    assert any(c["net_value_per_kg"] is not None for c in data)


def test_marketplace_total_net_value_capped_at_capacity():
    # FreshLink capacity=300 < quantity=400; total_net_value should use 300 kg
    resp = _mp_get(quality="Standard", quantity_kg=400, shelf_life_days=5)
    data = resp.json()
    by_name = {c["market_name"]: c for c in data}
    fl = by_name["FreshLink Retail Aggregator"]
    if fl["net_value_per_kg"] is not None and fl["total_net_value"] is not None:
        # total should be ~net_per_kg × 300 (capacity), not × 400
        expected = round(fl["net_value_per_kg"] * 300.0, 2)
        assert abs(fl["total_net_value"] - expected) < 0.1


def test_marketplace_effective_price_reflects_quality():
    resp = _mp_get(quality="Premium", quantity_kg=400, shelf_life_days=5)
    data = resp.json()
    for card in data:
        if card["effective_price_per_kg"] is not None:
            expected = round(card["base_price_per_kg"] * 1.15, 2)
            assert abs(card["effective_price_per_kg"] - expected) < 0.01


def test_marketplace_sorted_suitable_first():
    resp = _mp_get(quality="Low", quantity_kg=400, shelf_life_days=5)
    data = resp.json()
    suitabilities = [c["suitability"] for c in data]
    # All "Not Suitable" entries should come after all "Suitable" and "Partial"
    order = {"Suitable": 0, "Partial": 1, "Not Suitable": 2, "Unknown": 3}
    ranks = [order[s] for s in suitabilities]
    assert ranks == sorted(ranks)


def test_marketplace_requires_farmer_location():
    resp = client.get("/api/marketplace")
    assert resp.status_code == 422  # FastAPI validation error


def test_marketplace_empty_when_all_filtered_out():
    # min_price_per_kg so high nothing matches
    resp = _mp_get(min_price_per_kg=999.0)
    assert resp.status_code == 200
    assert resp.json() == []
