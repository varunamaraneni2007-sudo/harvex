import pytest
from main import calculate_opportunities, ProduceInput


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


def test_results_sorted_by_net_value():
    results = calculate_opportunities(_input())
    net_values = [r.net_value for r in results]
    assert net_values == sorted(net_values, reverse=True)


def test_ranks_are_sequential_from_one():
    results = calculate_opportunities(_input())
    assert [r.rank for r in results] == list(range(1, len(results) + 1))


def test_premium_gets_higher_price_than_standard():
    std = {r.market_name: r.price_per_kg for r in calculate_opportunities(_input(quality="Standard"))}
    prem = {r.market_name: r.price_per_kg for r in calculate_opportunities(_input(quality="Premium"))}
    for name in set(std) & set(prem):
        assert prem[name] > std[name]


def test_low_gets_lower_price_than_standard():
    std = {r.market_name: r.price_per_kg for r in calculate_opportunities(_input(quality="Standard"))}
    low = {r.market_name: r.price_per_kg for r in calculate_opportunities(_input(quality="Low"))}
    for name in set(std) & set(low):
        assert low[name] < std[name]


def test_allocated_qty_does_not_exceed_capacity():
    results = calculate_opportunities(_input(quantity_kg=99999))
    for r in results:
        assert r.allocated_qty_kg <= 10000  # max capacity in MARKETS


def test_short_shelf_life_increases_or_keeps_spoilage():
    normal = {r.market_name: r.spoilage_loss_kg for r in calculate_opportunities(_input(shelf_life_days=10))}
    urgent = {r.market_name: r.spoilage_loss_kg for r in calculate_opportunities(_input(shelf_life_days=2))}
    for name in set(normal) & set(urgent):
        assert urgent[name] >= normal[name]


def test_net_value_equals_gross_minus_transport_minus_spoilage():
    results = calculate_opportunities(_input(quantity_kg=100, shelf_life_days=10))
    for r in results:
        expected = round(r.gross_revenue - r.transport_cost - r.spoilage_loss_value, 2)
        assert abs(r.net_value - expected) < 0.01


def test_all_returned_net_values_are_positive():
    results = calculate_opportunities(_input())
    for r in results:
        assert r.net_value > 0


def test_gross_revenue_equals_qty_times_price():
    results = calculate_opportunities(_input(quantity_kg=200))
    for r in results:
        expected = round(r.allocated_qty_kg * r.price_per_kg, 2)
        assert abs(r.gross_revenue - expected) < 0.01


def test_transport_cost_is_positive_and_less_than_gross():
    results = calculate_opportunities(_input())
    for r in results:
        assert r.transport_cost > 0
        assert r.transport_cost < r.gross_revenue


def test_standard_input_produces_at_least_one_result():
    results = calculate_opportunities(_input())
    assert len(results) >= 1


def test_onion_400kg_standard_vijayawada():
    """Integration-style check for the hackathon demo scenario."""
    results = calculate_opportunities(_input(
        crop="onion",
        quantity_kg=400,
        quality="Standard",
        farmer_location="Vijayawada",
        harvest_date="18/09/2026",
        shelf_life_days=5,
    ))
    assert len(results) > 0
    # Best result should be ranked 1
    assert results[0].rank == 1
    # Net value of best must exceed that of others
    for r in results[1:]:
        assert results[0].net_value >= r.net_value
