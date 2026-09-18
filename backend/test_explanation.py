"""
Tests for the AI Explanation Layer (explanation_service.py).
All Anthropic API calls are mocked — no live API key needed.
"""
import os
from unittest.mock import MagicMock, patch

import pytest
import explanation_service
from explanation_service import (
    generate_explanation,
    generate_whatif_explanation,
    _fallback_submission,
    _fallback_whatif,
    _get_api_key,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_channel(market_name="Local Mandi", location="Vijayawada",
                  qty=300.0, price=12.0, gross=3600.0,
                  transport=150.0, spoilage_qty=9.0, spoilage_val=108.0, net=3342.0):
    ch = MagicMock()
    ch.market_name = market_name
    ch.location = location
    ch.quantity_kg = qty
    ch.price_per_kg = price
    ch.gross_revenue = gross
    ch.transport_cost = transport
    ch.spoilage_loss_kg = spoilage_qty
    ch.spoilage_loss_value = spoilage_val
    ch.net_value = net
    return ch


def _make_strategy(name="Maximum Net Value", desc="Optimal", allocs=None, net=3342.0):
    s = MagicMock()
    s.strategy_name = name
    s.strategy_description = desc
    s.allocations = allocs if allocs is not None else [_make_channel()]
    s.total_quantity_allocated = 300.0
    s.total_gross_revenue = 3600.0
    s.total_transport_cost = 150.0
    s.total_spoilage_loss_value = 108.0
    s.total_net_value = net
    return s


def _make_plan(label="A", name="Primary Plan", tradeoff="Some tradeoff", net=3342.0):
    p = MagicMock()
    p.plan_label = label
    p.plan_name = name
    p.plan_description = "Description"
    p.plan_tradeoff = tradeoff
    p.allocations = [_make_channel()]
    p.total_quantity_allocated = 300.0
    p.total_gross_revenue = 3600.0
    p.total_transport_cost = 150.0
    p.total_spoilage_loss_value = 108.0
    p.total_net_value = net
    return p


def _make_optimize_resp(allocs=None, alternatives=None):
    rec = _make_strategy(allocs=allocs)
    resp = MagicMock()
    resp.recommended = rec
    resp.alternatives = alternatives if alternatives is not None else []
    resp.crop = "onion"
    resp.quantity_kg = 400.0
    resp.quality = "Standard"
    resp.farmer_location = "Vijayawada"
    return resp


def _make_plans_resp():
    resp = MagicMock()
    resp.plan_a = _make_plan("A", "Primary Plan", "Concentrates volume", 3342.0)
    resp.plan_b = _make_plan("B", "Lower-Risk Plan", "Spreads risk", 3200.0)
    resp.plan_c = _make_plan("C", "Quick-Sale Plan", "Nearby buyers", 2900.0)
    return resp


def _make_produce_input():
    d = MagicMock()
    d.crop = "onion"
    d.quantity_kg = 400.0
    d.quality = "Standard"
    d.farmer_location = "Vijayawada"
    d.harvest_date = "18/09/2026"
    d.shelf_life_days = 5
    return d


def _make_whatif_plan(net=3342.0, allocs=None):
    p = MagicMock()
    p.total_net_value = net
    p.total_quantity_allocated = 300.0
    p.total_gross_revenue = 3600.0
    p.total_transport_cost = 150.0
    p.total_spoilage_loss_value = 108.0
    p.allocations = allocs if allocs is not None else [_make_channel()]
    return p


def _make_whatif_resp(delta=-500.0, scenario="transport costs +20%"):
    resp = MagicMock()
    resp.crop = "onion"
    resp.quantity_kg = 400.0
    resp.quality = "Standard"
    resp.farmer_location = "Vijayawada"
    resp.scenario_description = scenario
    resp.current_plan = _make_whatif_plan(net=3342.0)
    resp.whatif_plan = _make_whatif_plan(net=2842.0)
    resp.delta_net_value = delta
    return resp


def _make_whatif_req():
    req = MagicMock()
    req.produce = _make_produce_input()
    req.scenario = MagicMock()
    return req


# ── API key handling ──────────────────────────────────────────────────────────

def test_get_api_key_returns_none_when_empty():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
        assert _get_api_key() is None


def test_get_api_key_returns_key_when_set():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        assert _get_api_key() == "sk-test"


# ── Fallback submission ───────────────────────────────────────────────────────

def test_fallback_submission_contains_market_name():
    opt = _make_optimize_resp()
    pls = _make_plans_resp()
    text = _fallback_submission(opt, pls)
    assert "Local Mandi" in text


def test_fallback_submission_contains_net_value():
    opt = _make_optimize_resp()
    pls = _make_plans_resp()
    text = _fallback_submission(opt, pls)
    assert "3,342.00" in text


def test_fallback_submission_mentions_all_plans():
    opt = _make_optimize_resp()
    pls = _make_plans_resp()
    text = _fallback_submission(opt, pls)
    assert "Plan A" in text
    assert "Plan B" in text
    assert "Plan C" in text


def test_fallback_submission_no_allocations():
    opt = _make_optimize_resp(allocs=[])
    pls = _make_plans_resp()
    text = _fallback_submission(opt, pls)
    assert "No viable market" in text


# ── Fallback whatif ───────────────────────────────────────────────────────────

def test_fallback_whatif_contains_scenario():
    resp = _make_whatif_resp()
    text = _fallback_whatif(resp)
    assert "transport costs +20%" in text


def test_fallback_whatif_shows_delta():
    resp = _make_whatif_resp(delta=-500.0)
    text = _fallback_whatif(resp)
    assert "decrease" in text
    assert "500.00" in text


def test_fallback_whatif_positive_delta():
    resp = _make_whatif_resp(delta=200.0)
    text = _fallback_whatif(resp)
    assert "increase" in text


def test_fallback_whatif_no_markets():
    resp = _make_whatif_resp()
    resp.whatif_plan.allocations = []
    text = _fallback_whatif(resp)
    assert "no viable market" in text.lower()


# ── generate_explanation (submission) ────────────────────────────────────────

def test_generate_explanation_uses_fallback_without_key():
    data = _make_produce_input()
    opt = _make_optimize_resp()
    pls = _make_plans_resp()
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
        result = generate_explanation(data, opt, pls)
    assert "Local Mandi" in result  # fallback includes market name


def test_generate_explanation_uses_ai_when_key_present():
    data = _make_produce_input()
    opt = _make_optimize_resp()
    pls = _make_plans_resp()

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="AI explanation text")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        with patch("anthropic.Anthropic", return_value=mock_client):
            result = generate_explanation(data, opt, pls)

    assert result == "AI explanation text"


def test_generate_explanation_falls_back_on_ai_failure():
    data = _make_produce_input()
    opt = _make_optimize_resp()
    pls = _make_plans_resp()

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        with patch("anthropic.Anthropic", side_effect=Exception("API error")):
            result = generate_explanation(data, opt, pls)

    assert "Local Mandi" in result  # fallback was used


def test_generate_explanation_deterministic_without_key():
    data = _make_produce_input()
    opt = _make_optimize_resp()
    pls = _make_plans_resp()
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
        r1 = generate_explanation(data, opt, pls)
        r2 = generate_explanation(data, opt, pls)
    assert r1 == r2


# ── generate_whatif_explanation ───────────────────────────────────────────────

def test_generate_whatif_uses_fallback_without_key():
    req = _make_whatif_req()
    resp = _make_whatif_resp()
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
        result = generate_whatif_explanation(req, resp)
    assert "transport costs +20%" in result


def test_generate_whatif_uses_ai_when_key_present():
    req = _make_whatif_req()
    resp = _make_whatif_resp()

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Whatif AI explanation")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        with patch("anthropic.Anthropic", return_value=mock_client):
            result = generate_whatif_explanation(req, resp)

    assert result == "Whatif AI explanation"


def test_generate_whatif_falls_back_on_ai_failure():
    req = _make_whatif_req()
    resp = _make_whatif_resp()

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        with patch("anthropic.Anthropic", side_effect=Exception("network")):
            result = generate_whatif_explanation(req, resp)

    assert "transport costs +20%" in result  # fallback used


# ── Integration: submission endpoint includes explanation ─────────────────────

def test_submission_includes_explanation_field():
    from main import ProduceInput, submission

    data = ProduceInput(
        crop="onion", quantity_kg=400, quality="Standard",
        farmer_location="Vijayawada", harvest_date="18/09/2026", shelf_life_days=5,
    )
    with patch("maps_service.get_route", return_value=None):
        with patch("main._get_supabase", return_value=None):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
                resp = submission(data)

    assert resp.explanation is not None
    assert len(resp.explanation) > 10


def test_submission_explanation_is_string():
    from main import ProduceInput, submission

    data = ProduceInput(
        crop="tomato", quantity_kg=200, quality="Premium",
        farmer_location="Guntur", harvest_date="18/09/2026", shelf_life_days=3,
    )
    with patch("maps_service.get_route", return_value=None):
        with patch("main._get_supabase", return_value=None):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
                resp = submission(data)

    assert isinstance(resp.explanation, str)
