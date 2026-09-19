"""
Focused tests for the AGMARKNET market repository and /api/markets/* endpoints.

Tests verify:
  - MarketRecord model validation
  - MarketRepository loading, filtering, and metadata queries
  - /api/markets/discover filters (state, district, q, commodity)
  - /api/markets/states and /api/markets/districts
  - Fallback behavior when seed file is absent or malformed
  - That the repo does NOT require the hardcoded demo-market names
"""
import json
import tempfile
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient

from market_repository import MarketRecord, MarketRepository
from main import app

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed(*markets: dict) -> Path:
    """Write a temp JSON seed file and return its path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(list(markets), tmp, ensure_ascii=False)
    tmp.flush()
    return Path(tmp.name)


def _market(
    market_id="ap_test_testmarket",
    market_name="Test APMC",
    state="Andhra Pradesh",
    district="Krishna",
    market_type="APMC",
    source="AGMARKNET",
    commodities=None,
    lat=16.5,
    lng=80.6,
    active=True,
) -> dict:
    return {
        "market_id": market_id,
        "market_name": market_name,
        "state": state,
        "district": district,
        "market_type": market_type,
        "source": source,
        "commodities": commodities if commodities is not None else ["all"],
        "lat": lat,
        "lng": lng,
        "active": active,
    }


# ── MarketRecord model ────────────────────────────────────────────────────────

def test_market_record_required_fields():
    m = MarketRecord(**_market())
    assert m.market_id == "ap_test_testmarket"
    assert m.market_name == "Test APMC"
    assert m.state == "Andhra Pradesh"
    assert m.district == "Krishna"
    assert m.active is True


def test_market_record_lat_lng_optional():
    m = MarketRecord(**_market(lat=None, lng=None))
    assert m.lat is None
    assert m.lng is None


def test_market_record_commodities_default_all():
    m = MarketRecord(**_market(commodities=["all"]))
    assert "all" in m.commodities


def test_market_record_specific_commodities():
    m = MarketRecord(**_market(commodities=["Onion", "Tomato"]))
    assert "Onion" in m.commodities
    assert "all" not in m.commodities


# ── MarketRepository loading ──────────────────────────────────────────────────

def test_repository_loads_from_seed_file():
    path = _seed(_market(market_id="ap_k_vij"), _market(market_id="tg_h_bow", state="Telangana", district="Hyderabad"))
    repo = MarketRepository(data_path=path)
    assert repo.count() == 2


def test_repository_empty_when_file_missing():
    repo = MarketRepository(data_path=Path("/tmp/nonexistent_harvest_markets.json"))
    assert repo.count() == 0


def test_repository_empty_when_file_malformed():
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    tmp.write("NOT VALID JSON [[{")
    tmp.flush()
    repo = MarketRepository(data_path=Path(tmp.name))
    assert repo.count() == 0


def test_repository_skips_inactive_markets():
    path = _seed(
        _market(market_id="ap_active", active=True),
        _market(market_id="ap_inactive", active=False),
    )
    repo = MarketRepository(data_path=path)
    assert repo.count() == 1
    assert repo.get_by_id("ap_inactive") is None


# ── MarketRepository.search — filtering ──────────────────────────────────────

def test_search_no_filters_returns_all():
    path = _seed(
        _market(market_id="m1", state="Andhra Pradesh"),
        _market(market_id="m2", state="Telangana"),
    )
    repo = MarketRepository(data_path=path)
    assert len(repo.search()) == 2


def test_search_filter_by_state():
    path = _seed(
        _market(market_id="m1", state="Andhra Pradesh"),
        _market(market_id="m2", state="Telangana"),
        _market(market_id="m3", state="Maharashtra"),
    )
    repo = MarketRepository(data_path=path)
    results = repo.search(state="Telangana")
    assert len(results) == 1
    assert results[0].market_id == "m2"


def test_search_state_filter_case_insensitive():
    path = _seed(_market(market_id="m1", state="Andhra Pradesh"))
    repo = MarketRepository(data_path=path)
    assert len(repo.search(state="andhra pradesh")) == 1
    assert len(repo.search(state="ANDHRA PRADESH")) == 1


def test_search_filter_by_district():
    path = _seed(
        _market(market_id="m1", district="Krishna"),
        _market(market_id="m2", district="Guntur"),
    )
    repo = MarketRepository(data_path=path)
    assert len(repo.search(district="Guntur")) == 1


def test_search_filter_by_q_matches_market_name():
    path = _seed(
        _market(market_id="m1", market_name="Vijayawada APMC"),
        _market(market_id="m2", market_name="Guntur APMC"),
    )
    repo = MarketRepository(data_path=path)
    results = repo.search(q="vijay")
    assert len(results) == 1
    assert results[0].market_id == "m1"


def test_search_filter_by_q_matches_district():
    path = _seed(
        _market(market_id="m1", market_name="APMC X", district="Nasik"),
        _market(market_id="m2", market_name="APMC Y", district="Pune"),
    )
    repo = MarketRepository(data_path=path)
    assert len(repo.search(q="nasik")) == 1


def test_search_filter_by_commodity_accepts_all():
    path = _seed(_market(market_id="m1", commodities=["all"]))
    repo = MarketRepository(data_path=path)
    assert len(repo.search(commodity="onion")) == 1


def test_search_filter_by_commodity_specific_match():
    path = _seed(
        _market(market_id="m1", commodities=["Onion", "Tomato"]),
        _market(market_id="m2", commodities=["Wheat", "Rice"]),
    )
    repo = MarketRepository(data_path=path)
    results = repo.search(commodity="onion")
    assert len(results) == 1
    assert results[0].market_id == "m1"


def test_search_filter_by_commodity_no_match():
    path = _seed(_market(market_id="m1", commodities=["Wheat"]))
    repo = MarketRepository(data_path=path)
    assert len(repo.search(commodity="mango")) == 0


def test_search_limit_respected():
    path = _seed(
        _market(market_id="m1"),
        _market(market_id="m2"),
        _market(market_id="m3"),
    )
    repo = MarketRepository(data_path=path)
    assert len(repo.search(limit=2)) == 2


def test_search_combined_state_and_q():
    path = _seed(
        _market(market_id="m1", state="Andhra Pradesh", market_name="Vijayawada APMC"),
        _market(market_id="m2", state="Telangana", market_name="Vijayawada TG APMC"),
    )
    repo = MarketRepository(data_path=path)
    results = repo.search(state="Andhra Pradesh", q="vijayawada")
    assert len(results) == 1
    assert results[0].market_id == "m1"


# ── MarketRepository metadata queries ────────────────────────────────────────

def test_all_states_returns_sorted_unique():
    path = _seed(
        _market(market_id="m1", state="Maharashtra"),
        _market(market_id="m2", state="Andhra Pradesh"),
        _market(market_id="m3", state="Maharashtra"),
    )
    repo = MarketRepository(data_path=path)
    states = repo.all_states()
    assert states == ["Andhra Pradesh", "Maharashtra"]  # sorted, deduplicated


def test_districts_in_state():
    path = _seed(
        _market(market_id="m1", state="Andhra Pradesh", district="Krishna"),
        _market(market_id="m2", state="Andhra Pradesh", district="Guntur"),
        _market(market_id="m3", state="Telangana", district="Hyderabad"),
    )
    repo = MarketRepository(data_path=path)
    districts = repo.districts_in_state("Andhra Pradesh")
    assert "Krishna" in districts
    assert "Guntur" in districts
    assert "Hyderabad" not in districts


def test_get_by_id_found():
    path = _seed(_market(market_id="ap_k_vij", market_name="Vijayawada APMC"))
    repo = MarketRepository(data_path=path)
    m = repo.get_by_id("ap_k_vij")
    assert m is not None
    assert m.market_name == "Vijayawada APMC"


def test_get_by_id_not_found():
    path = _seed(_market(market_id="ap_k_vij"))
    repo = MarketRepository(data_path=path)
    assert repo.get_by_id("does_not_exist") is None


# ── Seed file has real AGMARKNET markets, not invented ones ──────────────────

def test_real_seed_file_loads():
    """The production seed file must load without errors and contain real APMCs."""
    from market_repository import get_repository
    repo = get_repository()
    assert repo.count() > 0, "Seed file must contain at least one market"


def test_real_seed_has_multiple_states():
    from market_repository import get_repository
    states = get_repository().all_states()
    assert len(states) >= 5, "Seed must cover at least 5 Indian states"


def test_real_seed_covers_major_agricultural_states():
    from market_repository import get_repository
    states = get_repository().all_states()
    major = {"Andhra Pradesh", "Telangana", "Maharashtra", "Karnataka", "Gujarat"}
    for s in major:
        assert s in states, f"Expected major agricultural state {s!r} in seed data"


def test_real_seed_markets_have_required_fields():
    from market_repository import get_repository
    for m in get_repository().search(limit=5):
        assert m.market_id
        assert m.market_name
        assert m.state
        assert m.district
        assert m.source == "AGMARKNET"


def test_real_seed_does_not_require_demo_market_names():
    """
    The discovery service must work independently of the 5 hardcoded demo
    markets used by the optimizer (Local Mandi, FreshLink, FreezeMart, etc.).
    """
    from market_repository import get_repository
    demo_names = {
        "Local Mandi", "FreshLink Retail Aggregator",
        "FreezeMart Cold Storage", "Hyderabad Metro Market",
        "Guntur Wholesale Hub",
    }
    repo = get_repository()
    discovered = {m.market_name for m in repo.search(limit=200)}
    # At least some real markets should NOT be in the demo list
    assert len(discovered - demo_names) > 0


# ── /api/markets/discover endpoint ───────────────────────────────────────────

def test_discover_endpoint_returns_200():
    resp = client.get("/api/markets/discover")
    assert resp.status_code == 200


def test_discover_endpoint_response_shape():
    resp = client.get("/api/markets/discover")
    data = resp.json()
    assert "markets" in data
    assert "total" in data
    assert "source" in data
    assert data["source"] == "AGMARKNET/data.gov.in"


def test_discover_endpoint_markets_have_required_fields():
    resp = client.get("/api/markets/discover")
    for m in resp.json()["markets"][:5]:
        for field in ["market_id", "market_name", "state", "district",
                      "market_type", "source", "commodities", "active"]:
            assert field in m, f"Missing field: {field}"


def test_discover_endpoint_filter_by_state():
    resp = client.get("/api/markets/discover", params={"state": "Andhra Pradesh"})
    assert resp.status_code == 200
    for m in resp.json()["markets"]:
        assert m["state"] == "Andhra Pradesh"


def test_discover_endpoint_filter_by_state_case_insensitive():
    resp1 = client.get("/api/markets/discover", params={"state": "Andhra Pradesh"})
    resp2 = client.get("/api/markets/discover", params={"state": "andhra pradesh"})
    assert resp1.json()["total"] == resp2.json()["total"]


def test_discover_endpoint_filter_by_q():
    resp = client.get("/api/markets/discover", params={"q": "Guntur"})
    assert resp.status_code == 200
    names = [m["market_name"] for m in resp.json()["markets"]]
    assert any("Guntur" in n for n in names)


def test_discover_endpoint_filter_by_commodity():
    resp = client.get("/api/markets/discover", params={"commodity": "Onion"})
    assert resp.status_code == 200
    # Markets accepting "all" or specifically "Onion" should appear
    for m in resp.json()["markets"]:
        comms = [c.lower() for c in m["commodities"]]
        assert "all" in comms or "onion" in comms


def test_discover_endpoint_limit():
    resp = client.get("/api/markets/discover", params={"limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()["markets"]) <= 3


def test_discover_endpoint_no_demo_names_required():
    """Discovery must return results without needing the 5 hardcoded demo markets."""
    demo_names = {
        "Local Mandi", "FreshLink Retail Aggregator",
        "FreezeMart Cold Storage", "Hyderabad Metro Market",
        "Guntur Wholesale Hub",
    }
    resp = client.get("/api/markets/discover", params={"limit": 100})
    returned = {m["market_name"] for m in resp.json()["markets"]}
    real_markets = returned - demo_names
    assert len(real_markets) > 0, "Discovery must return real APMC markets"


# ── /api/markets/states endpoint ─────────────────────────────────────────────

def test_states_endpoint_returns_200():
    resp = client.get("/api/markets/states")
    assert resp.status_code == 200


def test_states_endpoint_response_shape():
    data = client.get("/api/markets/states").json()
    assert "states" in data
    assert isinstance(data["states"], list)


def test_states_endpoint_contains_major_states():
    states = client.get("/api/markets/states").json()["states"]
    for s in ["Andhra Pradesh", "Maharashtra", "Karnataka"]:
        assert s in states, f"{s} missing from states list"


# ── /api/markets/districts endpoint ──────────────────────────────────────────

def test_districts_endpoint_returns_200():
    resp = client.get("/api/markets/districts", params={"state": "Andhra Pradesh"})
    assert resp.status_code == 200


def test_districts_endpoint_response_shape():
    data = client.get("/api/markets/districts", params={"state": "Andhra Pradesh"}).json()
    assert "state" in data
    assert "districts" in data
    assert isinstance(data["districts"], list)


def test_districts_endpoint_returns_known_district():
    data = client.get("/api/markets/districts", params={"state": "Andhra Pradesh"}).json()
    assert "Krishna" in data["districts"]


def test_districts_endpoint_requires_state_param():
    resp = client.get("/api/markets/districts")
    assert resp.status_code == 422
