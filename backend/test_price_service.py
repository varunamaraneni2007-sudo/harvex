"""
Focused tests for price_service.py and the /api/market-prices endpoints.
Run with: pytest test_price_service.py -v
"""

import json
import time
import pytest
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_raw_record(
    state="Andhra Pradesh",
    district="Krishna",
    market="Vijayawada",
    commodity="Tomato",
    variety="Hybrid",
    grade="FAQ",
    min_price="1500",
    modal_price="1800",
    max_price="2200",
    arrival_date="15/09/2026",
):
    return {
        "state": state,
        "district": district,
        "market": market,
        "commodity": commodity,
        "variety": variety,
        "grade": grade,
        "min_price": min_price,
        "modal_price": modal_price,
        "max_price": max_price,
        "arrival_date": arrival_date,
    }


def make_cache_file(tmp_path: Path, records: list) -> Path:
    cache = tmp_path / "price_cache.json"
    cache.write_text(
        json.dumps({"fetched_at": time.time(), "records": records}),
        encoding="utf-8",
    )
    return cache


# ── Unit tests: _parse_price ──────────────────────────────────────────────────

def test_parse_price_basic():
    from price_service import _parse_price
    assert _parse_price("2000") == 20.0      # 2000 ₹/quintal → 20 ₹/kg


def test_parse_price_with_comma():
    from price_service import _parse_price
    assert _parse_price("1,500") == 15.0


def test_parse_price_decimal():
    from price_service import _parse_price
    assert _parse_price("1250.50") == 12.51  # rounded to 2 dp


def test_parse_price_empty_string():
    from price_service import _parse_price
    assert _parse_price("") is None


def test_parse_price_none():
    from price_service import _parse_price
    assert _parse_price(None) is None


def test_parse_price_non_numeric():
    from price_service import _parse_price
    assert _parse_price("N/A") is None


def test_parse_price_zero():
    from price_service import _parse_price
    assert _parse_price("0") == 0.0


# ── Unit tests: _date_key ─────────────────────────────────────────────────────

def test_date_key_converts_correctly():
    from price_service import _date_key
    assert _date_key("15/09/2026") == "2026/09/15"


def test_date_key_none():
    from price_service import _date_key
    assert _date_key(None) == ""


def test_date_key_empty_string():
    from price_service import _date_key
    assert _date_key("") == ""


def test_date_key_ordering():
    from price_service import _date_key
    # Newer date should sort after older date lexicographically
    assert _date_key("20/09/2026") > _date_key("19/09/2026")
    assert _date_key("01/01/2027") > _date_key("31/12/2026")


# ── Unit tests: _make_market_id ───────────────────────────────────────────────

def test_make_market_id_known_state():
    from price_service import _make_market_id
    assert _make_market_id("Andhra Pradesh", "Krishna", "Vijayawada") == "ap_krishna_vijayawada"


def test_make_market_id_telangana():
    from price_service import _make_market_id
    result = _make_market_id("Telangana", "Hyderabad", "Bowenpally")
    assert result == "tg_hyderabad_bowenpally"


def test_make_market_id_unknown_state_uses_slug():
    from price_service import _make_market_id
    result = _make_market_id("Nagaland", "Kohima", "Kohima Market")
    # Unknown state → first 3 chars of slug
    assert result.startswith("nag_")


def test_make_market_id_special_chars():
    from price_service import _make_market_id
    result = _make_market_id("Andhra Pradesh", "East Godavari", "Rajahmundry")
    assert result == "ap_east_godavari_rajahmundry"


# ── Unit tests: raw_to_price_record ──────────────────────────────────────────

def test_raw_to_price_record_full():
    from price_service import raw_to_price_record
    raw = make_raw_record()
    rec = raw_to_price_record(raw)
    assert rec is not None
    assert rec.market_id == "ap_krishna_vijayawada"
    assert rec.commodity == "Tomato"
    assert rec.min_price_per_kg == 15.0    # 1500 / 100
    assert rec.modal_price_per_kg == 18.0  # 1800 / 100
    assert rec.max_price_per_kg == 22.0    # 2200 / 100
    assert rec.unit == "kg"
    assert rec.source == "AGMARKNET"
    assert rec.price_date == "15/09/2026"


def test_raw_to_price_record_missing_state():
    from price_service import raw_to_price_record
    raw = make_raw_record(state="")
    assert raw_to_price_record(raw) is None


def test_raw_to_price_record_missing_commodity():
    from price_service import raw_to_price_record
    raw = make_raw_record(commodity="")
    assert raw_to_price_record(raw) is None


def test_raw_to_price_record_missing_market():
    from price_service import raw_to_price_record
    raw = make_raw_record(market="")
    assert raw_to_price_record(raw) is None


def test_raw_to_price_record_bad_prices_still_valid():
    from price_service import raw_to_price_record
    raw = make_raw_record(min_price="N/A", modal_price="", max_price=None)
    rec = raw_to_price_record(raw)
    assert rec is not None
    assert rec.min_price_per_kg is None
    assert rec.modal_price_per_kg is None
    assert rec.max_price_per_kg is None


def test_raw_to_price_record_variety_grade_normalised():
    from price_service import raw_to_price_record
    raw = make_raw_record(variety="hybrid", grade="faq")
    rec = raw_to_price_record(raw)
    assert rec.variety == "Hybrid"     # title-cased
    assert rec.grade == "FAQ"          # uppercased


def test_raw_to_price_record_empty_variety_becomes_none():
    from price_service import raw_to_price_record
    raw = make_raw_record(variety="", grade="")
    rec = raw_to_price_record(raw)
    assert rec.variety is None
    assert rec.grade is None


# ── Unit tests: PriceRepository ───────────────────────────────────────────────

def _seed_repo(tmp_path: Path, records: list):
    from price_service import PriceRepository, raw_to_price_record
    price_records = [raw_to_price_record(r).model_dump() for r in records]
    cache = make_cache_file(tmp_path, price_records)
    return PriceRepository(cache_path=cache)


def test_repository_loads_records(tmp_path):
    repo = _seed_repo(tmp_path, [make_raw_record()])
    assert repo.count() == 1


def test_repository_empty_when_no_cache(tmp_path):
    from price_service import PriceRepository
    repo = PriceRepository(cache_path=tmp_path / "nonexistent.json")
    assert repo.count() == 0
    assert repo.cache_age_hours() is None


def test_repository_cache_age(tmp_path):
    repo = _seed_repo(tmp_path, [make_raw_record()])
    age = repo.cache_age_hours()
    assert age is not None
    assert age < 0.01   # just written


def test_repository_search_no_filter(tmp_path):
    records = [
        make_raw_record(commodity="Tomato"),
        make_raw_record(commodity="Onion"),
    ]
    repo = _seed_repo(tmp_path, records)
    results = repo.search()
    assert len(results) == 2


def test_repository_search_by_commodity(tmp_path):
    records = [
        make_raw_record(commodity="Tomato"),
        make_raw_record(commodity="Onion"),
    ]
    repo = _seed_repo(tmp_path, records)
    results = repo.search(commodity="tomato")
    assert len(results) == 1
    assert results[0].commodity == "Tomato"


def test_repository_search_commodity_partial_match(tmp_path):
    records = [
        make_raw_record(commodity="Tomato"),
        make_raw_record(commodity="Cherry Tomato"),
    ]
    repo = _seed_repo(tmp_path, records)
    results = repo.search(commodity="tomato")
    assert len(results) == 2


def test_repository_search_by_state(tmp_path):
    records = [
        make_raw_record(state="Andhra Pradesh"),
        make_raw_record(state="Telangana", district="Hyderabad", market="Bowenpally"),
    ]
    repo = _seed_repo(tmp_path, records)
    results = repo.search(state="Telangana")
    assert len(results) == 1
    assert results[0].state == "Telangana"


def test_repository_search_by_district(tmp_path):
    records = [
        make_raw_record(district="Krishna"),
        make_raw_record(district="Guntur", market="Guntur APMC"),
    ]
    repo = _seed_repo(tmp_path, records)
    results = repo.search(district="Guntur")
    assert len(results) == 1


def test_repository_search_by_market(tmp_path):
    records = [
        make_raw_record(market="Vijayawada"),
        make_raw_record(market="Guntur APMC", district="Guntur"),
    ]
    repo = _seed_repo(tmp_path, records)
    results = repo.search(market="guntur")
    assert len(results) == 1


def test_repository_search_latest_deduplication(tmp_path):
    """latest=True should keep only the most recent record per market+commodity."""
    from price_service import PriceRepository, raw_to_price_record
    records = [
        make_raw_record(arrival_date="10/09/2026"),
        make_raw_record(arrival_date="15/09/2026"),  # newer — should be kept
    ]
    price_records = [raw_to_price_record(r).model_dump() for r in records]
    cache = make_cache_file(tmp_path, price_records)
    repo = PriceRepository(cache_path=cache)
    results = repo.search(latest=True)
    assert len(results) == 1
    assert results[0].price_date == "15/09/2026"


def test_repository_search_latest_false(tmp_path):
    """latest=False returns all records."""
    from price_service import PriceRepository, raw_to_price_record
    records = [
        make_raw_record(arrival_date="10/09/2026"),
        make_raw_record(arrival_date="15/09/2026"),
    ]
    price_records = [raw_to_price_record(r).model_dump() for r in records]
    cache = make_cache_file(tmp_path, price_records)
    repo = PriceRepository(cache_path=cache)
    results = repo.search(latest=False)
    assert len(results) == 2


def test_repository_search_limit(tmp_path):
    records = [
        make_raw_record(commodity=f"Crop{i}", market=f"Market{i}", district=f"Dist{i}")
        for i in range(10)
    ]
    repo = _seed_repo(tmp_path, records)
    results = repo.search(limit=3)
    assert len(results) == 3


# ── API endpoint tests ────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with a temporary price cache and no real API key."""
    import price_service
    import main

    # Inject a real price repo backed by a temp cache
    records = [
        make_raw_record(commodity="Tomato", state="Andhra Pradesh",
                        district="Krishna", market="Vijayawada",
                        min_price="1500", modal_price="1800", max_price="2200"),
        make_raw_record(commodity="Onion", state="Maharashtra",
                        district="Nashik", market="Lasalgaon",
                        min_price="800", modal_price="1000", max_price="1200"),
    ]
    from price_service import PriceRepository, raw_to_price_record
    price_records = [raw_to_price_record(r).model_dump() for r in records]
    cache = make_cache_file(tmp_path, price_records)

    repo = PriceRepository(cache_path=cache)
    price_service._price_repo = repo

    monkeypatch.delenv("AGMARKNET_API_KEY", raising=False)
    yield TestClient(main.app)
    price_service._price_repo = None


def test_endpoint_market_prices_returns_200(client):
    resp = client.get("/api/market-prices")
    assert resp.status_code == 200


def test_endpoint_market_prices_response_shape(client):
    resp = client.get("/api/market-prices")
    data = resp.json()
    assert "prices" in data
    assert "total" in data
    assert "source" in data
    assert "unit" in data
    assert "price_type" in data
    assert "cache_age_hours" in data
    assert "api_configured" in data


def test_endpoint_market_prices_correct_unit(client):
    resp = client.get("/api/market-prices")
    data = resp.json()
    assert "₹/kg" in data["unit"]


def test_endpoint_market_prices_source_attribution(client):
    resp = client.get("/api/market-prices")
    data = resp.json()
    assert "AGMARKNET" in data["source"]


def test_endpoint_market_prices_price_fields(client):
    resp = client.get("/api/market-prices")
    prices = resp.json()["prices"]
    assert len(prices) > 0
    p = prices[0]
    assert "market_id" in p
    assert "commodity" in p
    assert "min_price_per_kg" in p
    assert "modal_price_per_kg" in p
    assert "max_price_per_kg" in p
    assert "unit" in p
    assert p["unit"] == "kg"


def test_endpoint_market_prices_filter_commodity(client):
    resp = client.get("/api/market-prices?commodity=Tomato")
    data = resp.json()
    assert all(p["commodity"] == "Tomato" for p in data["prices"])


def test_endpoint_market_prices_filter_state(client):
    resp = client.get("/api/market-prices?state=Maharashtra")
    data = resp.json()
    assert all(p["state"] == "Maharashtra" for p in data["prices"])


def test_endpoint_market_prices_filter_no_match(client):
    resp = client.get("/api/market-prices?commodity=Mango")
    data = resp.json()
    assert data["prices"] == []
    assert data["total"] == 0


def test_endpoint_market_prices_api_not_configured(client):
    resp = client.get("/api/market-prices")
    data = resp.json()
    assert data["api_configured"] is False


def test_endpoint_refresh_without_api_key(client):
    resp = client.post("/api/market-prices/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "AGMARKNET_API_KEY" in data["message"]


def test_endpoint_market_prices_empty_cache(tmp_path, monkeypatch):
    import price_service
    import main
    empty_repo_path = tmp_path / "empty_cache.json"
    from price_service import PriceRepository
    price_service._price_repo = PriceRepository(cache_path=empty_repo_path)
    monkeypatch.delenv("AGMARKNET_API_KEY", raising=False)
    c = TestClient(main.app)
    resp = c.get("/api/market-prices")
    assert resp.status_code == 200
    data = resp.json()
    assert data["prices"] == []
    assert data["total"] == 0
    assert data["note"] is not None   # helpful message when cache is absent
    price_service._price_repo = None
