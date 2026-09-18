import pytest
from main import (
    ProduceInput,
    WhatIfScenario,
    WhatIfRequest,
    MARKETS,
    QUALITY_MULTIPLIER,
    _greedy_allocate,
    _apply_scenario,
    _scenario_description,
    _plan_from_allocations,
    whatif,
)


def _input(**overrides):
    base = dict(
        crop="onion",
        quantity_kg=400,
        quality="Standard",
        farmer_location="Vijayawada",
        harvest_date="18/09/2026",
        shelf_life_days=5,
    )
    base.update(overrides)
    return ProduceInput(**base)


def _req(produce_overrides=None, scenario_overrides=None):
    produce = _input(**(produce_overrides or {}))
    scenario = WhatIfScenario(**(scenario_overrides or {}))
    return WhatIfRequest(produce=produce, scenario=scenario)


# ── greedy allocator ──────────────────────────────────────────────────────────

def test_greedy_total_does_not_exceed_quantity():
    qm = QUALITY_MULTIPLIER["Standard"]
    raw = _greedy_allocate(400, MARKETS, qm, 5)
    assert sum(raw) <= 400.01


def test_greedy_no_channel_exceeds_capacity():
    qm = QUALITY_MULTIPLIER["Standard"]
    caps = {m["market_name"]: m["capacity_kg"] for m in MARKETS}
    raw = _greedy_allocate(99999, MARKETS, qm, 5)
    for m, qty in zip(MARKETS, raw):
        assert qty <= caps[m["market_name"]] + 0.01


# ── scenario application ──────────────────────────────────────────────────────

def test_transport_increase_raises_cost():
    scenario = WhatIfScenario(transport_cost_increase_pct=30)
    mod, _ = _apply_scenario(MARKETS, _input(), scenario)
    original = {m["market_name"]: m["transport_cost_per_kg"] for m in MARKETS}
    for m in mod:
        assert m["transport_cost_per_kg"] > original[m["market_name"]]


def test_price_decrease_lowers_price():
    scenario = WhatIfScenario(price_decrease_pct=10)
    mod, _ = _apply_scenario(MARKETS, _input(), scenario)
    original = {m["market_name"]: m["base_price_per_kg"] for m in MARKETS}
    for m in mod:
        assert m["base_price_per_kg"] < original[m["market_name"]]


def test_shelf_life_reduction_decreases_effective_shelf():
    scenario = WhatIfScenario(shelf_life_reduction_days=2)
    _, eff = _apply_scenario(MARKETS, _input(shelf_life_days=5), scenario)
    assert eff == 3


def test_shelf_life_clamped_to_minimum_one():
    scenario = WhatIfScenario(shelf_life_reduction_days=10)
    _, eff = _apply_scenario(MARKETS, _input(shelf_life_days=2), scenario)
    assert eff >= 1


def test_cancelled_market_excluded():
    scenario = WhatIfScenario(cancelled_market="Hyderabad Metro Market")
    mod, _ = _apply_scenario(MARKETS, _input(), scenario)
    names = [m["market_name"] for m in mod]
    assert "Hyderabad Metro Market" not in names
    assert len(names) == len(MARKETS) - 1


def test_capacity_reduction_shrinks_capacity():
    scenario = WhatIfScenario(capacity_reduction_pct=50)
    mod, _ = _apply_scenario(MARKETS, _input(), scenario)
    original = {m["market_name"]: m["capacity_kg"] for m in MARKETS}
    for m in mod:
        assert m["capacity_kg"] < original[m["market_name"]]


# ── scenario description ──────────────────────────────────────────────────────

def test_scenario_description_baseline():
    assert _scenario_description(WhatIfScenario()) == "No changes (baseline)"


def test_scenario_description_combined():
    s = WhatIfScenario(transport_cost_increase_pct=30, cancelled_market="Local Mandi")
    desc = _scenario_description(s)
    assert "transport" in desc
    assert "Local Mandi" in desc


# ── /api/decision/whatif endpoint ─────────────────────────────────────────────

def test_whatif_baseline_delta_zero():
    resp = whatif(_req())
    assert abs(resp.delta_net_value - (resp.whatif_plan.total_net_value - resp.current_plan.total_net_value)) < 0.01


def test_whatif_transport_increase_reduces_net_value():
    base = whatif(_req())
    stressed = whatif(_req(scenario_overrides={"transport_cost_increase_pct": 50}))
    assert stressed.whatif_plan.total_net_value < base.current_plan.total_net_value


def test_whatif_price_decrease_reduces_net_value():
    base = whatif(_req())
    stressed = whatif(_req(scenario_overrides={"price_decrease_pct": 20}))
    assert stressed.whatif_plan.total_net_value < base.current_plan.total_net_value


def test_whatif_cancelled_market_not_in_whatif_plan():
    resp = whatif(_req(scenario_overrides={"cancelled_market": "Hyderabad Metro Market"}))
    alloc_names = {c.market_name for c in resp.whatif_plan.allocations}
    assert "Hyderabad Metro Market" not in alloc_names


def test_whatif_all_markets_cancelled_gives_zero():
    # Cancel all markets sequentially using capacity 0
    resp = whatif(_req(scenario_overrides={"capacity_reduction_pct": 100}))
    assert resp.whatif_plan.total_quantity_allocated == 0


def test_whatif_total_allocation_does_not_exceed_quantity():
    resp = whatif(_req(scenario_overrides={"transport_cost_increase_pct": 30, "price_decrease_pct": 10}))
    assert resp.whatif_plan.total_quantity_allocated <= 400.01
