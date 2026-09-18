import pytest
from main import (
    calculate_opportunities,
    ProduceInput,
    MARKETS,
    QUALITY_MULTIPLIER,
    _solve_strategy,
    _build_strategy,
    _true_net_per_kg,
    _effective_spoilage_pct,
    ALLOCATION_STRATEGIES,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _run_optimal(data: ProduceInput):
    """Run the optimal (unweighted) strategy and return the AllocationStrategy."""
    cfg = next(c for c in ALLOCATION_STRATEGIES if c["id"] == "optimal")
    qm = QUALITY_MULTIPLIER.get(data.quality, 1.0)
    raw = _solve_strategy(data.quantity_kg, MARKETS, qm, data.shelf_life_days, 1.0, 1.0)
    return _build_strategy(data, cfg, qm, raw)


# ── /api/recommend (single-channel) ──────────────────────────────────────────

def test_recommend_results_sorted_by_net_value():
    results = calculate_opportunities(_input())
    net_values = [r.net_value for r in results]
    assert net_values == sorted(net_values, reverse=True)


def test_recommend_ranks_are_sequential():
    results = calculate_opportunities(_input())
    assert [r.rank for r in results] == list(range(1, len(results) + 1))


def test_recommend_premium_gets_higher_price_than_standard():
    std = {r.market_name: r.price_per_kg for r in calculate_opportunities(_input(quality="Standard"))}
    prem = {r.market_name: r.price_per_kg for r in calculate_opportunities(_input(quality="Premium"))}
    for name in set(std) & set(prem):
        assert prem[name] > std[name]


def test_recommend_low_gets_lower_price_than_standard():
    std = {r.market_name: r.price_per_kg for r in calculate_opportunities(_input(quality="Standard"))}
    low = {r.market_name: r.price_per_kg for r in calculate_opportunities(_input(quality="Low"))}
    for name in set(std) & set(low):
        assert low[name] < std[name]


def test_recommend_allocated_qty_does_not_exceed_capacity():
    results = calculate_opportunities(_input(quantity_kg=99999))
    for r in results:
        assert r.allocated_qty_kg <= 10000


def test_recommend_net_value_formula():
    results = calculate_opportunities(_input(quantity_kg=100, shelf_life_days=10))
    for r in results:
        expected = round(r.gross_revenue - r.transport_cost - r.spoilage_loss_value, 2)
        assert abs(r.net_value - expected) < 0.01


def test_recommend_all_net_values_positive():
    results = calculate_opportunities(_input())
    for r in results:
        assert r.net_value > 0


# ── Allocation engine (multi-channel) ────────────────────────────────────────

def test_total_allocation_does_not_exceed_farmer_quantity():
    strategy = _run_optimal(_input(quantity_kg=400))
    assert strategy.total_quantity_allocated <= 400.01  # small float tolerance


def test_no_channel_exceeds_its_market_capacity():
    strategy = _run_optimal(_input(quantity_kg=99999))
    caps = {m["market_name"]: m["capacity_kg"] for m in MARKETS}
    for ch in strategy.allocations:
        assert ch.quantity_kg <= caps[ch.market_name] + 0.01


def test_multi_channel_beats_single_channel_net_value():
    """
    Multi-channel allocation should be >= any single-channel allocation
    because the LP can always replicate a single-channel solution.
    """
    data = _input(quantity_kg=1000)
    strategy = _run_optimal(data)

    single_best = max(calculate_opportunities(data), key=lambda r: r.net_value)
    assert strategy.total_net_value >= single_best.net_value - 0.01


def test_channel_net_value_formula_is_correct():
    strategy = _run_optimal(_input())
    for ch in strategy.allocations:
        expected = round(ch.gross_revenue - ch.transport_cost - ch.spoilage_loss_value, 2)
        assert abs(ch.net_value - expected) < 0.01


def test_channel_gross_revenue_formula():
    strategy = _run_optimal(_input())
    for ch in strategy.allocations:
        assert abs(ch.gross_revenue - round(ch.quantity_kg * ch.price_per_kg, 2)) < 0.01


def test_all_channel_net_values_positive():
    strategy = _run_optimal(_input())
    for ch in strategy.allocations:
        assert ch.net_value > 0


def test_total_net_value_equals_sum_of_channels():
    strategy = _run_optimal(_input())
    computed = round(sum(ch.net_value for ch in strategy.allocations), 2)
    assert abs(strategy.total_net_value - computed) < 0.01


def test_short_shelf_life_increases_spoilage():
    normal_sp = _effective_spoilage_pct(5.0, shelf_life_days=10)
    urgent_sp = _effective_spoilage_pct(5.0, shelf_life_days=2)
    assert urgent_sp > normal_sp


def test_spoilage_capped_at_30_percent():
    assert _effective_spoilage_pct(30.0, shelf_life_days=1) <= 30.0


def test_quality_multipliers():
    m = MARKETS[0]
    assert _true_net_per_kg(m, QUALITY_MULTIPLIER["Premium"], 10) > _true_net_per_kg(m, QUALITY_MULTIPLIER["Standard"], 10)
    assert _true_net_per_kg(m, QUALITY_MULTIPLIER["Standard"], 10) > _true_net_per_kg(m, QUALITY_MULTIPLIER["Low"], 10)


def test_quick_cash_strategy_penalises_high_transport_markets():
    """Quick-cash strategy should favour local markets over distant ones."""
    data = _input(quantity_kg=10000)  # large enough to fill all markets
    qm = QUALITY_MULTIPLIER[data.quality]
    cfg = next(c for c in ALLOCATION_STRATEGIES if c["id"] == "quick_cash")

    raw = _solve_strategy(data.quantity_kg, MARKETS, qm, data.shelf_life_days, 5.0, 1.0)
    strategy = _build_strategy(data, cfg, qm, raw)

    # Hyderabad Metro has transport_cost_per_kg=3.5 — the highest.
    # Local Mandi has transport_cost_per_kg=0.5 — the lowest.
    alloc = {ch.market_name: ch.quantity_kg for ch in strategy.allocations}
    local_mandi_qty = alloc.get("Local Mandi", 0)
    hyderabad_qty = alloc.get("Hyderabad Metro Market", 0)
    # With 5x transport penalty Hyderabad's score goes very low; local gets more
    assert local_mandi_qty >= hyderabad_qty


def test_min_risk_strategy_avoids_high_spoilage_markets():
    """
    With 5x spoilage weight, the LP should fill low-spoilage markets first
    and avoid the highest-spoilage market (Hyderabad Metro, 8%) when enough
    low-spoilage capacity exists to satisfy the farmer's quantity.

    With quantity_kg=5000:
      - FreshLink (2% sp, cap 300) fills first  → 300 kg
      - FreezeMart (1% sp, cap 10000) fills next → 4700 kg
      Total = 5000 — Hyderabad should receive 0.
    """
    data = _input(quantity_kg=5000)
    qm = QUALITY_MULTIPLIER[data.quality]
    cfg = next(c for c in ALLOCATION_STRATEGIES if c["id"] == "min_risk")

    raw = _solve_strategy(data.quantity_kg, MARKETS, qm, data.shelf_life_days, 1.0, 5.0)
    strategy = _build_strategy(data, cfg, qm, raw)

    alloc = {ch.market_name: ch.quantity_kg for ch in strategy.allocations}
    # Hyderabad Metro (8% spoilage) should be skipped entirely
    assert alloc.get("Hyderabad Metro Market", 0) == 0
    # FreezeMart and FreshLink (lowest spoilage) should receive allocations
    assert alloc.get("FreezeMart Cold Storage", 0) > 0
    assert alloc.get("FreshLink Retail Aggregator", 0) > 0


def test_hackathon_demo_onion_400kg():
    """End-to-end check for the demo scenario."""
    data = _input(crop="onion", quantity_kg=400, quality="Standard",
                  farmer_location="Vijayawada", harvest_date="18/09/2026", shelf_life_days=5)
    strategy = _run_optimal(data)

    assert strategy.total_quantity_allocated <= 400.01
    assert strategy.total_net_value > 0
    assert len(strategy.allocations) >= 1
    # Multi-channel should split across at least 2 markets for 400 kg
    assert len(strategy.allocations) >= 2
