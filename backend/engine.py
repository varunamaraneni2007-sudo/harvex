"""
Farm2Value Decision Engine
==========================
Evaluates all feasible selling opportunities for a farmer's produce.

Rules:
- An opportunity is FEASIBLE only if the farmer's quality meets the buyer's minimum.
- Allocated quantity = min(farmer quantity, buyer maximum capacity).
- Spoilage percentage is derived from multiple real-world factors (not just
  the raw spoilage_risk label on the opportunity).
- Transport cost is a fixed fee the farmer pays regardless of load size.
- Expected net value = gross_revenue - transport_cost - spoilage_loss.
- The engine does NOT simply rank by price; a nearby lower-price buyer often
  beats a distant high-price buyer once transport and spoilage are deducted.
- All multipliers are constants → the calculation is fully deterministic.
"""

from typing import List, Optional
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Quality ranking (higher = better)
# ---------------------------------------------------------------------------
QUALITY_RANK = {"Premium": 3, "Standard": 2, "Low": 1}

# ---------------------------------------------------------------------------
# Base spoilage rates by opportunity's spoilage_risk label
# These represent the minimum % of gross revenue lost even under ideal
# conditions (short distance, ample shelf life, high demand).
# ---------------------------------------------------------------------------
BASE_SPOILAGE_RATE = {
    "Low":    0.02,   # 2 %
    "Medium": 0.05,   # 5 %
    "High":   0.10,   # 10 %
}

# ---------------------------------------------------------------------------
# Shelf-life urgency multiplier
# The fewer days left, the faster the produce deteriorates in transit.
# ---------------------------------------------------------------------------
def _shelf_life_multiplier(shelf_life_days: int) -> float:
    if shelf_life_days <= 2:
        return 3.5    # critical — almost certain heavy loss
    if shelf_life_days <= 4:
        return 2.5    # very urgent
    if shelf_life_days <= 7:
        return 1.75   # urgent
    if shelf_life_days <= 14:
        return 1.25   # moderate
    return 1.0        # comfortable


# ---------------------------------------------------------------------------
# Demand multiplier
# Low demand = goods sit longer in the supply chain = more spoilage.
# ---------------------------------------------------------------------------
DEMAND_MULTIPLIER = {
    "High":   1.0,    # moves quickly, minimal extra spoilage
    "Medium": 1.15,   # some delay expected
    "Low":    1.40,   # goods sit, significant extra spoilage
}

# ---------------------------------------------------------------------------
# Distance multiplier
# Farther = longer transit = more exposure to heat/handling = more spoilage.
# ---------------------------------------------------------------------------
def _distance_multiplier(distance_km: float) -> float:
    if distance_km > 50:
        return 1.50
    if distance_km > 30:
        return 1.25
    if distance_km > 15:
        return 1.10
    return 1.0


# ---------------------------------------------------------------------------
# Overall risk level (3 inputs → Low / Medium / High)
# ---------------------------------------------------------------------------
def _risk_level(
    opp_spoilage_risk: str,
    opp_demand_level: str,
    shelf_life_days: int,
) -> str:
    score = 0

    # Spoilage risk contribution
    score += {"Low": 1, "Medium": 2, "High": 3}[opp_spoilage_risk]

    # Demand contribution
    score += {"High": 1, "Medium": 2, "Low": 3}[opp_demand_level]

    # Shelf-life urgency contribution
    if shelf_life_days <= 3:
        score += 3
    elif shelf_life_days <= 7:
        score += 2
    else:
        score += 1

    # Score range: 3 (best) – 9 (worst)
    if score <= 4:
        return "Low"
    if score <= 6:
        return "Medium"
    return "High"


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FarmerData:
    """Simplified view of the farmer's produce needed by the engine."""
    crop: str
    quantity: float           # kg
    quality: str              # "Premium" | "Standard" | "Low"
    shelf_life_days: int


@dataclass
class OpportunityData:
    """Mirrors the Opportunity model from main.py (all primitive types)."""
    id: int
    name: str
    type: str
    price_per_kg: float
    maximum_capacity_kg: int
    distance_km: float
    estimated_transport_cost: float
    estimated_travel_time_minutes: int
    demand_level: str
    minimum_quality: str
    spoilage_risk: str


@dataclass
class OpportunityResult:
    opportunity_id: int
    opportunity_name: str
    buyer_type: str
    is_feasible: bool
    infeasibility_reason: Optional[str]

    allocated_quantity_kg: float
    selling_price_per_kg: float

    gross_revenue: float
    transport_cost: float
    spoilage_percentage: float      # as a percentage (e.g. 8.75, not 0.0875)
    spoilage_loss: float
    expected_net_value: float

    risk_level: str

    explanation: dict


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def evaluate_opportunity(
    farmer: FarmerData,
    opp: OpportunityData,
) -> OpportunityResult:
    """
    Evaluate a single opportunity against a farmer's produce.

    Returns an OpportunityResult with is_feasible=False if the farmer's
    quality grade is too low, or if net value is negative (selling would
    cause a net loss).
    """

    # ── 1. Quality gate ──────────────────────────────────────────────────────
    farmer_rank = QUALITY_RANK[farmer.quality]
    min_rank    = QUALITY_RANK[opp.minimum_quality]
    if farmer_rank < min_rank:
        return OpportunityResult(
            opportunity_id=opp.id,
            opportunity_name=opp.name,
            buyer_type=opp.type,
            is_feasible=False,
            infeasibility_reason=(
                f"Quality mismatch: buyer requires '{opp.minimum_quality}' "
                f"but farmer has '{farmer.quality}'"
            ),
            allocated_quantity_kg=0,
            selling_price_per_kg=opp.price_per_kg,
            gross_revenue=0,
            transport_cost=0,
            spoilage_percentage=0,
            spoilage_loss=0,
            expected_net_value=0,
            risk_level="High",
            explanation={
                "quality_check": "FAILED — quality below minimum requirement",
            },
        )

    # ── 2. Allocated quantity ────────────────────────────────────────────────
    allocated_qty = min(farmer.quantity, float(opp.maximum_capacity_kg))

    # ── 3. Gross revenue ─────────────────────────────────────────────────────
    gross_revenue = allocated_qty * opp.price_per_kg

    # ── 4. Transport cost (fixed fee, farmer pays regardless of load size) ───
    transport_cost = opp.estimated_transport_cost

    # ── 5. Spoilage percentage ───────────────────────────────────────────────
    base_rate   = BASE_SPOILAGE_RATE[opp.spoilage_risk]
    sl_mult     = _shelf_life_multiplier(farmer.shelf_life_days)
    demand_mult = DEMAND_MULTIPLIER[opp.demand_level]
    dist_mult   = _distance_multiplier(opp.distance_km)

    raw_spoilage_rate = base_rate * sl_mult * demand_mult * dist_mult
    spoilage_rate     = min(raw_spoilage_rate, 0.60)   # hard cap at 60 %

    # ── 6. Spoilage loss & expected net value ────────────────────────────────
    spoilage_loss    = spoilage_rate * gross_revenue
    expected_net_val = gross_revenue - transport_cost - spoilage_loss

    # ── 7. Risk level ─────────────────────────────────────────────────────────
    risk = _risk_level(opp.spoilage_risk, opp.demand_level, farmer.shelf_life_days)

    # ── 8. Human-readable explanation ────────────────────────────────────────
    explanation = {
        "quality_check": (
            f"PASSED — farmer quality '{farmer.quality}' meets "
            f"minimum requirement '{opp.minimum_quality}'"
        ),
        "capacity_note": (
            f"Allocated {allocated_qty:,.0f} kg "
            f"(farmer has {farmer.quantity:,.0f} kg; "
            f"buyer accepts up to {opp.maximum_capacity_kg:,} kg)"
        ),
        "spoilage_breakdown": {
            "base_spoilage_risk":   f"{opp.spoilage_risk} ({base_rate*100:.0f}% base)",
            "shelf_life_urgency":   f"{farmer.shelf_life_days} days remaining → ×{sl_mult}",
            "demand_factor":        f"{opp.demand_level} demand → ×{demand_mult}",
            "distance_factor":      f"{opp.distance_km} km → ×{dist_mult}",
            "final_spoilage_rate":  f"{spoilage_rate*100:.2f}%",
        },
        "value_summary": {
            "gross_revenue":    f"₹{gross_revenue:,.2f}",
            "transport_cost":   f"₹{transport_cost:,.2f}",
            "spoilage_loss":    f"₹{spoilage_loss:,.2f}",
            "expected_net_val": f"₹{expected_net_val:,.2f}",
        },
    }

    # Mark infeasible if selling would cause a net loss
    is_feasible = expected_net_val > 0
    infeasibility_reason = (
        "Net value is negative after transport and spoilage costs"
        if not is_feasible else None
    )

    return OpportunityResult(
        opportunity_id=opp.id,
        opportunity_name=opp.name,
        buyer_type=opp.type,
        is_feasible=is_feasible,
        infeasibility_reason=infeasibility_reason,
        allocated_quantity_kg=round(allocated_qty, 2),
        selling_price_per_kg=opp.price_per_kg,
        gross_revenue=round(gross_revenue, 2),
        transport_cost=round(transport_cost, 2),
        spoilage_percentage=round(spoilage_rate * 100, 2),
        spoilage_loss=round(spoilage_loss, 2),
        expected_net_value=round(expected_net_val, 2),
        risk_level=risk,
        explanation=explanation,
    )


def run_decision_engine(
    farmer: FarmerData,
    opportunities: List[OpportunityData],
) -> List[OpportunityResult]:
    """
    Evaluate all opportunities.
    Returns results sorted by expected_net_value descending
    (feasible first, then infeasible).
    """
    results = [evaluate_opportunity(farmer, opp) for opp in opportunities]

    # Sort: feasible opportunities by net value desc, infeasible at the end
    feasible   = sorted([r for r in results if r.is_feasible],
                        key=lambda r: r.expected_net_value, reverse=True)
    infeasible = [r for r in results if not r.is_feasible]

    return feasible + infeasible
