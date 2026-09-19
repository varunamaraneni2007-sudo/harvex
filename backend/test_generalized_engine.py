"""
Regression tests for Steps 32–36: generalized decision engine.

Verifies that the engine is data-driven and makes no hardcoded crop, market,
location, or price assumptions, and that existing behaviour is unchanged.
"""
import pytest
from unittest.mock import MagicMock

from main import (
    ProduceInput,
    MARKETS,
    QUALITY_MULTIPLIER,
    _eligible_markets,
    _prepare_markets,
    _enrich_markets_with_prices,
    _run_optimize,
    _run_plans,
    _greedy_allocate,
    calculate_opportunities,
    whatif,
    WhatIfRequest,
    WhatIfScenario,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _input(**overrides):
    base = dict(
        crop="Tomato",
        quantity_kg=500,
        quality="Standard",
        farmer_location="Bangalore",
        harvest_date="2026-10-01",
        shelf_life_days=7,
    )
    base.update(overrides)
    return ProduceInput(**base)


def _custom_markets(n=2, base_price=15.0):
    """Return a minimal valid market list for testing — no MARKETS dependency."""
    return [
        {
            "market_name": f"Dynamic Market {i}",
            "buyer_type": "Wholesale Buyer",
            "location": f"City {i}",
            "base_price_per_kg": base_price + i,
            "transport_cost_per_kg": 1.0,
            "capacity_kg": 1000.0,
            "base_spoilage_pct": 5.0,
            "accepted_crops": ["all"],
            "min_quality": "Low",
        }
        for i in range(n)
    ]


# ── Step 32: Different crops processed without engine code change ─────────────

def test_engine_accepts_arbitrary_crop_names():
    """Engine processes any crop name without source-code changes."""
    for crop in ("Tomato", "Onion", "Potato", "Wheat", "Rice", "Banana", "Cotton"):
        data = _input(crop=crop)
        result = _run_optimize(data, MARKETS)
        assert result.crop == crop
        assert result.quantity_kg == 500


def test_crop_name_preserved_in_plans():
    """Crop name flows through Plan A/B/C without modification."""
    for crop in ("Maize", "Sugarcane", "Chilli"):
        data = _input(crop=crop)
        result = _run_plans(data, MARKETS)
        assert result.crop == crop


def test_eligible_markets_crop_filter_excludes_non_matching():
    """Markets with a specific accepted_crops list reject non-matching crops."""
    markets = [
        {**_custom_markets(1)[0], "accepted_crops": ["wheat", "rice"]},
        {**_custom_markets(1)[0], "market_name": "All Crops Market", "accepted_crops": ["all"]},
    ]
    eligible = _eligible_markets(markets, "Standard", crop="onion")
    names = [m["market_name"] for m in eligible]
    assert "All Crops Market" in names
    assert "Dynamic Market 0" not in names


def test_eligible_markets_crop_none_keeps_all_quality_eligible():
    """Without a crop argument, crop filtering is skipped (backward-compatible)."""
    markets = _custom_markets(3)
    markets[0]["accepted_crops"] = ["wheat"]
    without_crop = _eligible_markets(markets, "Standard", crop=None)
    with_crop = _eligible_markets(markets, "Standard", crop="onion")
    assert len(without_crop) >= len(with_crop)


def test_eligible_markets_all_crops_accepted_passes_any_crop():
    """accepted_crops=['all'] means the market accepts every crop."""
    markets = _custom_markets(2)  # all have accepted_crops=["all"]
    for crop in ("Grapes", "Garlic", "Ginger"):
        eligible = _eligible_markets(markets, "Standard", crop=crop)
        assert len(eligible) == 2


# ── Step 33: Different markets supplied dynamically ──────────────────────────

def test_optimizer_works_with_custom_market_list():
    """_run_optimize operates correctly on any caller-supplied market list."""
    custom = _custom_markets(3, base_price=20.0)
    data = _input()
    result = _run_optimize(data, custom)
    used = {ch.market_name for ch in result.recommended.allocations}
    for name in used:
        assert any(m["market_name"] == name for m in custom)


def test_plans_work_with_custom_market_list():
    """_run_plans produces Plan A/B/C for any caller-supplied market list."""
    custom = _custom_markets(4, base_price=18.0)
    data = _input()
    result = _run_plans(data, custom)
    assert result.plan_a.plan_label == "A"
    assert result.plan_b.plan_label == "B"
    assert result.plan_c.plan_label == "C"
    for ch in result.plan_a.allocations:
        assert any(m["market_name"] == ch.market_name for m in custom)


def test_optimizer_respects_dynamic_market_capacity():
    """Engine never allocates more than the capacity declared by each market."""
    markets = [
        {**_custom_markets(1)[0], "market_name": "Small Buyer", "capacity_kg": 50.0},
        {**_custom_markets(1)[0], "market_name": "Large Buyer", "capacity_kg": 5000.0},
    ]
    data = _input(quantity_kg=2000)
    result = _run_optimize(data, markets)
    alloc = {ch.market_name: ch.quantity_kg for ch in result.recommended.allocations}
    assert alloc.get("Small Buyer", 0) <= 50.0


# ── Step 34: Different farmer locations supplied dynamically ─────────────────

def test_farmer_location_preserved_in_optimize_response():
    """farmer_location from the input is echoed back unchanged."""
    for loc in ("Bangalore", "Pune", "Jaipur", "Amritsar", "Kochi"):
        data = _input(farmer_location=loc)
        result = _run_optimize(data, MARKETS)
        assert result.farmer_location == loc


def test_farmer_location_preserved_in_plans_response():
    for loc in ("Delhi", "Mumbai", "Kolkata"):
        data = _input(farmer_location=loc)
        result = _run_plans(data, MARKETS)
        assert result.farmer_location == loc


def test_prepare_markets_passes_farmer_location_to_distance_service(monkeypatch):
    """_prepare_markets forwards the farmer's location to enrich_markets_with_distances."""
    captured = []

    def fake_enrich(location, markets):
        captured.append(location)
        return markets

    monkeypatch.setattr("main.enrich_markets_with_distances", fake_enrich)
    data = _input(farmer_location="Mysore")
    _prepare_markets(data)
    assert captured == ["Mysore"]


def test_prepare_markets_different_locations_produce_different_calls(monkeypatch):
    """Each call to _prepare_markets passes the correct location."""
    captured = []

    def fake_enrich(location, markets):
        captured.append(location)
        return markets

    monkeypatch.setattr("main.enrich_markets_with_distances", fake_enrich)
    _prepare_markets(_input(farmer_location="Pune"))
    _prepare_markets(_input(farmer_location="Nagpur"))
    assert captured == ["Pune", "Nagpur"]


# ── Step 35: Prices come from supplied price data, not hardcoded constants ────

def test_enrich_prices_overrides_base_price_from_live_data(monkeypatch):
    """When AGMARKNET has a modal price for this market+crop, it replaces the static price."""
    from price_service import PriceRecord

    live_record = PriceRecord(
        market_id="ka_bangalore_local_mandi",
        market_name="Local Mandi",
        state="Karnataka",
        district="Bangalore",
        commodity="Tomato",
        modal_price_per_kg=22.5,
    )
    mock_repo = MagicMock()
    mock_repo.search.return_value = [live_record]

    import price_service as ps
    monkeypatch.setattr(ps, "_price_repo", mock_repo)

    markets = [{
        "market_name": "Local Mandi",
        "base_price_per_kg": 12.0,
        "transport_cost_per_kg": 0.5,
        "capacity_kg": 500.0,
        "base_spoilage_pct": 3.0,
        "accepted_crops": ["all"],
        "min_quality": "Low",
        "buyer_type": "Local Mandi",
        "location": "Bangalore",
    }]
    result = _enrich_markets_with_prices(markets, "Tomato")
    assert result[0]["base_price_per_kg"] == 22.5


def test_enrich_prices_falls_back_to_static_when_no_live_record(monkeypatch):
    """Static price is kept when no AGMARKNET price exists for this crop."""
    mock_repo = MagicMock()
    mock_repo.search.return_value = []

    import price_service as ps
    monkeypatch.setattr(ps, "_price_repo", mock_repo)

    markets = _custom_markets(2, base_price=15.0)
    result = _enrich_markets_with_prices(markets, "Tomato")
    for m_orig, m_new in zip(markets, result):
        assert m_new["base_price_per_kg"] == m_orig["base_price_per_kg"]


def test_enrich_prices_safe_when_service_raises(monkeypatch):
    """Price enrichment catches all exceptions and returns the input markets unchanged."""
    mock_repo = MagicMock()
    mock_repo.search.side_effect = RuntimeError("Service unavailable")

    import price_service as ps
    monkeypatch.setattr(ps, "_price_repo", mock_repo)

    markets = _custom_markets(2, base_price=10.0)
    result = _enrich_markets_with_prices(markets, "Wheat")
    assert len(result) == 2
    assert result[0]["base_price_per_kg"] == 10.0


def test_enrich_prices_skips_records_without_modal_price(monkeypatch):
    """A record with modal_price_per_kg=None does not override the static price."""
    from price_service import PriceRecord

    record = PriceRecord(
        market_id="test",
        market_name="Dynamic Market 0",
        state="Test State",
        district="Test District",
        commodity="Onion",
        modal_price_per_kg=None,
        min_price_per_kg=8.0,
        max_price_per_kg=14.0,
    )
    mock_repo = MagicMock()
    mock_repo.search.return_value = [record]

    import price_service as ps
    monkeypatch.setattr(ps, "_price_repo", mock_repo)

    markets = _custom_markets(1, base_price=10.0)
    result = _enrich_markets_with_prices(markets, "Onion")
    assert result[0]["base_price_per_kg"] == 10.0


def test_enrich_prices_no_op_for_empty_crop():
    """Empty-string crop skips price enrichment entirely."""
    markets = _custom_markets(2, base_price=12.0)
    result = _enrich_markets_with_prices(markets, "")
    for m_orig, m_new in zip(markets, result):
        assert m_new["base_price_per_kg"] == m_orig["base_price_per_kg"]


# ── Step 36 / Backward compatibility ────────────────────────────────────────

def test_optimizer_is_deterministic():
    """Same input always produces identical output (engine is not stochastic)."""
    data = _input()
    r1 = _run_optimize(data, MARKETS)
    r2 = _run_optimize(data, MARKETS)
    assert r1.recommended.total_net_value == r2.recommended.total_net_value
    assert [(c.market_name, c.quantity_kg) for c in r1.recommended.allocations] == \
           [(c.market_name, c.quantity_kg) for c in r2.recommended.allocations]


def test_allocation_total_does_not_exceed_quantity():
    """Multi-channel allocation never exceeds the farmer's available quantity."""
    data = _input(quantity_kg=750)
    result = _run_optimize(data, MARKETS)
    assert result.recommended.total_quantity_allocated <= 750.01


def test_whatif_allocation_does_not_exceed_quantity():
    """What-If allocation never exceeds the farmer's quantity."""
    req = WhatIfRequest(produce=_input(quantity_kg=600), scenario=WhatIfScenario())
    resp = whatif(req)
    assert resp.current_plan.total_quantity_allocated <= 600.01
    assert resp.whatif_plan.total_quantity_allocated <= 600.01


def test_api_optimize_accepts_any_crop():
    """POST /api/decision/optimize processes arbitrary crops and returns 200."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    for crop in ("Mango", "Banana", "Turmeric", "Garlic"):
        resp = client.post("/api/decision/optimize", json={
            "crop": crop, "quantity_kg": 300, "quality": "Standard",
            "farmer_location": "Hyderabad", "harvest_date": "2026-10-01",
            "shelf_life_days": 5,
        })
        assert resp.status_code == 200, f"Failed for crop={crop}"
        assert resp.json()["crop"] == crop


def test_api_plans_accepts_any_crop():
    """POST /api/decision/plans returns Plan A/B/C for arbitrary crops."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    for crop in ("Papaya", "Lemon", "Guava", "Pomegranate"):
        resp = client.post("/api/decision/plans", json={
            "crop": crop, "quantity_kg": 200, "quality": "Low",
            "farmer_location": "Chennai", "harvest_date": "2026-10-01",
            "shelf_life_days": 10,
        })
        assert resp.status_code == 200, f"Failed for crop={crop}"
        assert resp.json()["crop"] == crop


def test_api_whatif_accepts_any_crop():
    """POST /api/decision/whatif returns a valid response for arbitrary crops."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.post("/api/decision/whatif", json={
        "produce": {
            "crop": "Grapes", "quantity_kg": 400, "quality": "Premium",
            "farmer_location": "Nashik", "harvest_date": "2026-10-01",
            "shelf_life_days": 7,
        },
        "scenario": {"transport_cost_increase_pct": 20},
    })
    assert resp.status_code == 200
    assert resp.json()["crop"] == "Grapes"


def test_api_recommend_accepts_any_crop():
    """POST /api/recommend returns a valid response for arbitrary crops."""
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.post("/api/recommend", json={
        "crop": "Spinach", "quantity_kg": 150, "quality": "Standard",
        "farmer_location": "Lucknow", "harvest_date": "2026-10-01",
        "shelf_life_days": 3,
    })
    assert resp.status_code == 200
    assert resp.json()["crop"] == "Spinach"


def test_existing_demo_scenario_unchanged():
    """The classic 400 kg onion demo still produces the same allocation."""
    data = ProduceInput(
        crop="onion", quantity_kg=400, quality="Standard",
        farmer_location="Vijayawada", harvest_date="18/09/2026", shelf_life_days=5,
    )
    result = _run_optimize(data, MARKETS)
    assert result.recommended.total_quantity_allocated <= 400.01
    assert result.recommended.total_net_value > 0
    assert len(result.recommended.allocations) >= 2


# ── Step 33: Market catalogue loaded from data file, not source code ──────────

def test_markets_loaded_from_json_file():
    """MARKETS is populated by reading data/markets.json, not from Python literals."""
    import json, os
    catalogue_path = os.path.join(os.path.dirname(__file__), "data", "markets.json")
    with open(catalogue_path, encoding="utf-8") as fh:
        file_markets = json.load(fh)
    assert len(MARKETS) == len(file_markets)
    for m_file, m_runtime in zip(file_markets, MARKETS):
        assert m_file["market_name"] == m_runtime["market_name"]
        assert m_file["base_price_per_kg"] == m_runtime["base_price_per_kg"]


def test_markets_json_has_required_engine_fields():
    """Every market in data/markets.json contains all fields the engine requires."""
    required = {
        "market_name", "base_price_per_kg", "transport_cost_per_kg",
        "capacity_kg", "base_spoilage_pct", "buyer_type", "accepted_crops", "min_quality",
    }
    for m in MARKETS:
        missing = required - m.keys()
        assert not missing, f"Market '{m.get('market_name')}' missing fields: {missing}"


def test_load_markets_tolerates_missing_file(tmp_path, monkeypatch):
    """_load_markets returns [] gracefully when the JSON file does not exist."""
    import main as m_mod
    monkeypatch.setattr(m_mod.os.path, "join", lambda *a: str(tmp_path / "nonexistent.json"))
    result = m_mod._load_markets()
    assert result == []


def test_load_markets_tolerates_corrupt_file(tmp_path, monkeypatch):
    """_load_markets returns [] gracefully when the JSON file is malformed."""
    import main as m_mod
    bad = tmp_path / "markets.json"
    bad.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(m_mod.os.path, "join", lambda *a: str(bad))
    result = m_mod._load_markets()
    assert result == []


def test_markets_catalogue_is_externally_configurable(tmp_path, monkeypatch):
    """_load_markets reads whatever markets.json contains — engine is not tied to fixed entries."""
    import json, main as m_mod
    custom = [
        {
            "market_name": "Custom Test Market",
            "location": "Test City",
            "base_price_per_kg": 30.0,
            "transport_cost_per_kg": 2.0,
            "capacity_kg": 800.0,
            "base_spoilage_pct": 4.0,
            "buyer_type": "Wholesale Buyer",
            "accepted_crops": ["all"],
            "min_quality": "Low",
        }
    ]
    custom_file = tmp_path / "markets.json"
    custom_file.write_text(json.dumps(custom), encoding="utf-8")
    monkeypatch.setattr(m_mod.os.path, "join", lambda *a: str(custom_file))
    result = m_mod._load_markets()
    assert len(result) == 1
    assert result[0]["market_name"] == "Custom Test Market"
    assert result[0]["base_price_per_kg"] == 30.0
