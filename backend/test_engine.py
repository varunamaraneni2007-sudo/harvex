"""
Automated tests for the Farm2Value Decision Engine.
Run with:  python3 -m pytest backend/test_engine.py -v
       or: python3 backend/test_engine.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from engine import (
    FarmerData,
    OpportunityData,
    evaluate_opportunity,
    run_decision_engine,
    QUALITY_RANK,
    BASE_SPOILAGE_RATE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_farmer(quality="Standard", quantity=400.0, shelf_life_days=6):
    return FarmerData(
        crop="Onion",
        quantity=quantity,
        quality=quality,
        shelf_life_days=shelf_life_days,
    )


def make_opp(
    id=1,
    name="Test Buyer",
    buyer_type="Direct Buyer",
    price=28.5,
    capacity=500,
    distance=12.0,
    transport_cost=320.0,
    travel_time=25,
    demand="High",
    min_quality="Standard",
    spoilage_risk="Low",
):
    return OpportunityData(
        id=id,
        name=name,
        type=buyer_type,
        price_per_kg=price,
        maximum_capacity_kg=capacity,
        distance_km=distance,
        estimated_transport_cost=transport_cost,
        estimated_travel_time_minutes=travel_time,
        demand_level=demand,
        minimum_quality=min_quality,
        spoilage_risk=spoilage_risk,
    )


# ---------------------------------------------------------------------------
# Test 1: Quality gate — Low farmer rejected by Premium buyer
# ---------------------------------------------------------------------------
def test_quality_gate_fail():
    farmer = make_farmer(quality="Low")
    opp    = make_opp(min_quality="Premium")
    result = evaluate_opportunity(farmer, opp)
    assert not result.is_feasible, "Low quality farmer should be rejected by Premium buyer"
    assert result.allocated_quantity_kg == 0
    assert result.gross_revenue == 0
    assert "Quality mismatch" in (result.infeasibility_reason or "")
    print("PASS test_quality_gate_fail")


# ---------------------------------------------------------------------------
# Test 2: Quality gate — Standard farmer accepted by Low-min buyer
# ---------------------------------------------------------------------------
def test_quality_gate_pass():
    farmer = make_farmer(quality="Standard")
    opp    = make_opp(min_quality="Low")
    result = evaluate_opportunity(farmer, opp)
    assert result.is_feasible, "Standard quality should pass a Low minimum requirement"
    assert result.gross_revenue > 0
    print("PASS test_quality_gate_pass")


# ---------------------------------------------------------------------------
# Test 3: Allocated quantity is capped at buyer capacity
# ---------------------------------------------------------------------------
def test_quantity_capped_at_capacity():
    farmer = make_farmer(quantity=1000.0)
    opp    = make_opp(capacity=300)
    result = evaluate_opportunity(farmer, opp)
    assert result.allocated_quantity_kg == 300.0, (
        f"Expected 300 kg allocated, got {result.allocated_quantity_kg}"
    )
    print("PASS test_quantity_capped_at_capacity")


# ---------------------------------------------------------------------------
# Test 4: Allocated quantity uses full farmer stock when it is smaller
# ---------------------------------------------------------------------------
def test_quantity_uses_farmer_stock():
    farmer = make_farmer(quantity=150.0)
    opp    = make_opp(capacity=500)
    result = evaluate_opportunity(farmer, opp)
    assert result.allocated_quantity_kg == 150.0
    print("PASS test_quantity_uses_farmer_stock")


# ---------------------------------------------------------------------------
# Test 5: Gross revenue formula — allocated_qty × price_per_kg
# ---------------------------------------------------------------------------
def test_gross_revenue_formula():
    farmer = make_farmer(quantity=400.0)
    opp    = make_opp(price=28.5, capacity=500)
    result = evaluate_opportunity(farmer, opp)
    expected_gross = 400.0 * 28.5
    assert abs(result.gross_revenue - expected_gross) < 0.01, (
        f"Expected gross revenue {expected_gross}, got {result.gross_revenue}"
    )
    print("PASS test_gross_revenue_formula")


# ---------------------------------------------------------------------------
# Test 6: Net value formula — gross - transport - spoilage_loss
# ---------------------------------------------------------------------------
def test_net_value_formula():
    farmer = make_farmer(quantity=400.0)
    opp    = make_opp(price=28.5, capacity=500, transport_cost=320.0)
    result = evaluate_opportunity(farmer, opp)
    expected_net = result.gross_revenue - result.transport_cost - result.spoilage_loss
    assert abs(result.expected_net_value - expected_net) < 0.01, (
        f"Net value formula mismatch: expected {expected_net}, got {result.expected_net_value}"
    )
    print("PASS test_net_value_formula")


# ---------------------------------------------------------------------------
# Test 7: Shorter shelf life → higher spoilage percentage
# ---------------------------------------------------------------------------
def test_shelf_life_increases_spoilage():
    opp         = make_opp(spoilage_risk="Medium", distance=10.0, demand="High")
    farmer_long = make_farmer(shelf_life_days=20)
    farmer_short= make_farmer(shelf_life_days=2)
    result_long  = evaluate_opportunity(farmer_long, opp)
    result_short = evaluate_opportunity(farmer_short, opp)
    assert result_short.spoilage_percentage > result_long.spoilage_percentage, (
        "Shorter shelf life should produce higher spoilage percentage"
    )
    print("PASS test_shelf_life_increases_spoilage")


# ---------------------------------------------------------------------------
# Test 8: Farther distance → higher spoilage percentage (same shelf life)
# ---------------------------------------------------------------------------
def test_distance_increases_spoilage():
    farmer    = make_farmer(shelf_life_days=5)
    opp_near  = make_opp(id=1, distance=10.0)
    opp_far   = make_opp(id=2, distance=70.0)
    near      = evaluate_opportunity(farmer, opp_near)
    far       = evaluate_opportunity(farmer, opp_far)
    assert far.spoilage_percentage > near.spoilage_percentage, (
        "Farther opportunity should have higher spoilage percentage"
    )
    print("PASS test_distance_increases_spoilage")


# ---------------------------------------------------------------------------
# Test 9: Nearby lower-price buyer can beat far higher-price buyer on net value
# ---------------------------------------------------------------------------
def test_nearby_low_price_beats_distant_high_price():
    farmer = make_farmer(quantity=400.0, shelf_life_days=4)

    # High-price but far, expensive transport, high spoilage risk
    far_premium = make_opp(
        id=1,
        name="Far Premium Buyer",
        price=34.0,
        capacity=500,
        distance=65.0,
        transport_cost=1200.0,
        demand="Medium",
        min_quality="Standard",
        spoilage_risk="High",
    )

    # Lower price but close, cheap transport, low spoilage risk
    near_standard = make_opp(
        id=2,
        name="Nearby Standard Buyer",
        price=26.0,
        capacity=500,
        distance=10.0,
        transport_cost=300.0,
        demand="High",
        min_quality="Standard",
        spoilage_risk="Low",
    )

    far_result  = evaluate_opportunity(farmer, far_premium)
    near_result = evaluate_opportunity(farmer, near_standard)

    assert near_result.expected_net_value > far_result.expected_net_value, (
        f"Nearby buyer (₹{near_result.expected_net_value}) should beat "
        f"far buyer (₹{far_result.expected_net_value}) on net value.\n"
        f"  Far:  gross={far_result.gross_revenue}, transport={far_result.transport_cost}, "
        f"spoilage={far_result.spoilage_loss:.2f}, net={far_result.expected_net_value:.2f}\n"
        f"  Near: gross={near_result.gross_revenue}, transport={near_result.transport_cost}, "
        f"spoilage={near_result.spoilage_loss:.2f}, net={near_result.expected_net_value:.2f}"
    )
    print(f"PASS test_nearby_low_price_beats_distant_high_price")
    print(f"  Far  buyer (₹34/kg, 65 km): net = ₹{far_result.expected_net_value:,.2f}")
    print(f"  Near buyer (₹26/kg, 10 km): net = ₹{near_result.expected_net_value:,.2f}")


# ---------------------------------------------------------------------------
# Test 10: run_decision_engine returns feasible first, sorted by net value desc
# ---------------------------------------------------------------------------
def test_engine_sorts_by_net_value():
    farmer = make_farmer(quantity=400.0, shelf_life_days=7)
    opps = [
        make_opp(id=1, price=22.0, capacity=5000, distance=35.0, transport_cost=850.0,
                 demand="High", spoilage_risk="Medium", min_quality="Low"),
        make_opp(id=2, price=28.5, capacity=500,  distance=12.0, transport_cost=320.0,
                 demand="High", spoilage_risk="Low",    min_quality="Standard"),
        make_opp(id=3, price=34.0, capacity=200,  distance=8.0,  transport_cost=180.0,
                 demand="Medium", spoilage_risk="Low",  min_quality="Premium"),  # rejected
        make_opp(id=4, price=19.5, capacity=800,  distance=62.0, transport_cost=1200.0,
                 demand="Medium", spoilage_risk="High", min_quality="Low"),
    ]
    results = run_decision_engine(farmer, opps)

    feasible = [r for r in results if r.is_feasible]
    infeasible = [r for r in results if not r.is_feasible]

    # Feasible results should be sorted descending by net value
    for i in range(len(feasible) - 1):
        assert feasible[i].expected_net_value >= feasible[i+1].expected_net_value, (
            "Feasible results should be sorted by net value (descending)"
        )

    # Infeasible results should come last
    assert all(r.is_feasible for r in results[:len(feasible)])
    assert all(not r.is_feasible for r in results[len(feasible):])

    print(f"PASS test_engine_sorts_by_net_value")
    print(f"  {len(feasible)} feasible, {len(infeasible)} infeasible")
    for r in feasible:
        print(f"    [{r.risk_level:6s} risk] {r.opportunity_name}: net = ₹{r.expected_net_value:,.2f}")


# ---------------------------------------------------------------------------
# Test 11: Spoilage capped at 60%
# ---------------------------------------------------------------------------
def test_spoilage_capped_at_sixty_percent():
    # Worst case: 1 day shelf life, high spoilage risk, low demand, 80 km distance
    farmer = make_farmer(shelf_life_days=1, quality="Low")
    opp    = make_opp(
        spoilage_risk="High",
        demand="Low",
        distance=80.0,
        transport_cost=100.0,
        min_quality="Low",
    )
    result = evaluate_opportunity(farmer, opp)
    assert result.spoilage_percentage <= 60.0, (
        f"Spoilage should be capped at 60%, got {result.spoilage_percentage}%"
    )
    print(f"PASS test_spoilage_capped_at_sixty_percent  (got {result.spoilage_percentage}%)")


# ---------------------------------------------------------------------------
# Test 12: Determinism — same inputs always give same output
# ---------------------------------------------------------------------------
def test_determinism():
    farmer = make_farmer(quality="Standard", quantity=400.0, shelf_life_days=6)
    opp    = make_opp()
    r1 = evaluate_opportunity(farmer, opp)
    r2 = evaluate_opportunity(farmer, opp)
    assert r1.expected_net_value == r2.expected_net_value, "Engine must be deterministic"
    assert r1.spoilage_percentage == r2.spoilage_percentage
    print("PASS test_determinism")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tests = [
        test_quality_gate_fail,
        test_quality_gate_pass,
        test_quantity_capped_at_capacity,
        test_quantity_uses_farmer_stock,
        test_gross_revenue_formula,
        test_net_value_formula,
        test_shelf_life_increases_spoilage,
        test_distance_increases_spoilage,
        test_nearby_low_price_beats_distant_high_price,
        test_engine_sorts_by_net_value,
        test_spoilage_capped_at_sixty_percent,
        test_determinism,
    ]

    print("=" * 60)
    print("Farm2Value Decision Engine — Automated Tests")
    print("=" * 60)
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)
    if failed:
        sys.exit(1)
