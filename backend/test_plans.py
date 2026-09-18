import pytest
from main import (
    ProduceInput,
    MARKETS,
    QUALITY_MULTIPLIER,
    _plan_b_allocate,
    _plan_c_allocate,
    _build_plan_result,
    plans,
    PlansResponse,
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


def _caps():
    return {m["market_name"]: m["capacity_kg"] for m in MARKETS}


# ── Plan A (primary / max net value) ─────────────────────────────────────────

def test_plan_a_valid_demo():
    resp = plans(_input())
    assert resp.plan_a.total_quantity_allocated <= 400.01
    assert resp.plan_a.total_net_value > 0
    assert len(resp.plan_a.allocations) >= 1


def test_plan_a_demo_allocates_freshlink_and_hyderabad():
    resp = plans(_input())
    alloc = {ch.market_name: ch.quantity_kg for ch in resp.plan_a.allocations}
    # FreshLink has highest net/kg (16.84); fills first to capacity 300
    assert alloc.get("FreshLink Retail Aggregator", 0) == 300.0
    # Remaining 100 kg goes to second-best: Hyderabad Metro (14.9 net/kg)
    assert alloc.get("Hyderabad Metro Market", 0) == 100.0


# ── Plan B (lower-risk / diversified) ────────────────────────────────────────

def test_plan_b_valid():
    resp = plans(_input())
    assert resp.plan_b.total_quantity_allocated <= 400.01
    assert resp.plan_b.total_net_value > 0


def test_plan_b_more_diversified_than_plan_a():
    resp = plans(_input())
    # Plan B caps each market at 60% so no single market gets >240 kg
    for ch in resp.plan_b.allocations:
        assert ch.quantity_kg <= 400 * 0.6 + 0.01


def test_plan_b_demo_splits_across_two_markets():
    resp = plans(_input())
    alloc = {ch.market_name: ch.quantity_kg for ch in resp.plan_b.allocations}
    # With 60% cap (=240 kg), FreshLink gets 240, Hyderabad gets 160
    assert alloc.get("FreshLink Retail Aggregator", 0) == 240.0
    assert alloc.get("Hyderabad Metro Market", 0) == 160.0


# ── Plan C (quick-sale / low transport) ──────────────────────────────────────

def test_plan_c_valid():
    resp = plans(_input())
    assert resp.plan_c.total_quantity_allocated <= 400.01
    assert resp.plan_c.total_net_value > 0


def test_plan_c_demo_avoids_hyderabad_high_transport():
    resp = plans(_input())
    alloc = {ch.market_name: ch.quantity_kg for ch in resp.plan_c.allocations}
    # Hyderabad has highest transport (3.5/kg); with 5x penalty it scores last
    # FreshLink fills 300 (cap), LocalMandi fills remaining 100
    assert alloc.get("FreshLink Retail Aggregator", 0) == 300.0
    assert alloc.get("Local Mandi", 0) == 100.0
    assert alloc.get("Hyderabad Metro Market", 0) == 0.0


# ── All three plans together ──────────────────────────────────────────────────

def test_all_plans_respect_quantity_constraint():
    data = _input()
    resp = plans(data)
    for plan in (resp.plan_a, resp.plan_b, resp.plan_c):
        assert plan.total_quantity_allocated <= data.quantity_kg + 0.01


def test_no_channel_exceeds_market_capacity():
    caps = _caps()
    resp = plans(_input(quantity_kg=99999))
    for plan in (resp.plan_a, resp.plan_b, resp.plan_c):
        for ch in plan.allocations:
            assert ch.quantity_kg <= caps[ch.market_name] + 0.01


def test_financial_totals_correct():
    resp = plans(_input())
    for plan in (resp.plan_a, resp.plan_b, resp.plan_c):
        for ch in plan.allocations:
            expected_net = round(ch.gross_revenue - ch.transport_cost - ch.spoilage_loss_value, 2)
            assert abs(ch.net_value - expected_net) < 0.01
        expected_total = round(sum(ch.net_value for ch in plan.allocations), 2)
        assert abs(plan.total_net_value - expected_total) < 0.01


def test_three_plans_are_returned_for_demo():
    resp = plans(_input())
    assert isinstance(resp, PlansResponse)
    assert resp.plan_a.plan_label == "A"
    assert resp.plan_b.plan_label == "B"
    assert resp.plan_c.plan_label == "C"
    assert resp.crop == "onion"


def test_plans_b_and_c_differ_from_plan_a():
    resp = plans(_input())
    sig_a = frozenset((ch.market_name, ch.quantity_kg) for ch in resp.plan_a.allocations)
    sig_b = frozenset((ch.market_name, ch.quantity_kg) for ch in resp.plan_b.allocations)
    sig_c = frozenset((ch.market_name, ch.quantity_kg) for ch in resp.plan_c.allocations)
    assert sig_b != sig_a, "Plan B should differ from Plan A"
    assert sig_c != sig_a, "Plan C should differ from Plan A"
