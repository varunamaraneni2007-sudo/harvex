from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from ortools.linear_solver import pywraplp

app = FastAPI(title="Farm2Value API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# ── Shared input model ────────────────────────────────────────────────────────

class ProduceInput(BaseModel):
    crop: str
    quantity_kg: float
    quality: str          # "Premium" | "Standard" | "Low"
    farmer_location: str
    harvest_date: str     # display-only string in v1
    shelf_life_days: int


# ── Sample market data ────────────────────────────────────────────────────────

MARKETS = [
    {
        "market_name": "Local Mandi",
        "location": "Vijayawada",
        "base_price_per_kg": 12.0,
        "transport_cost_per_kg": 0.5,
        "capacity_kg": 500.0,
        "base_spoilage_pct": 3.0,
    },
    {
        "market_name": "Guntur Wholesale Hub",
        "location": "Guntur",
        "base_price_per_kg": 15.0,
        "transport_cost_per_kg": 1.2,
        "capacity_kg": 2000.0,
        "base_spoilage_pct": 5.0,
    },
    {
        "market_name": "Hyderabad Metro Market",
        "location": "Hyderabad",
        "base_price_per_kg": 20.0,
        "transport_cost_per_kg": 3.5,
        "capacity_kg": 5000.0,
        "base_spoilage_pct": 8.0,
    },
    {
        "market_name": "FreshLink Retail Aggregator",
        "location": "Vijayawada",
        "base_price_per_kg": 18.0,
        "transport_cost_per_kg": 0.8,
        "capacity_kg": 300.0,
        "base_spoilage_pct": 2.0,
    },
    {
        "market_name": "FreezeMart Cold Storage",
        "location": "Guntur",
        "base_price_per_kg": 14.0,
        "transport_cost_per_kg": 1.5,
        "capacity_kg": 10000.0,
        "base_spoilage_pct": 1.0,
    },
]

QUALITY_MULTIPLIER = {
    "Premium": 1.15,
    "Standard": 1.00,
    "Low": 0.80,
}

# Three strategy configurations for the LP objective.
# transport_weight and spoilage_weight scale those cost terms in the
# objective only; reported net values always use the true (1x) formula.
ALLOCATION_STRATEGIES = [
    {
        "id": "optimal",
        "name": "Maximum Net Value",
        "description": (
            "Allocates your produce across markets to maximise total expected "
            "earnings after all transport and spoilage costs."
        ),
        "transport_weight": 1.0,
        "spoilage_weight": 1.0,
    },
    {
        "id": "quick_cash",
        "name": "Quick Turnaround",
        "description": (
            "Prioritises nearby markets to cut transport time and get cash "
            "faster — best when you need liquidity quickly."
        ),
        "transport_weight": 5.0,
        "spoilage_weight": 1.0,
    },
    {
        "id": "min_risk",
        "name": "Minimum Risk",
        "description": (
            "Favours buyers with the lowest spoilage rates to protect your "
            "harvest value against quality loss in transit."
        ),
        "transport_weight": 1.0,
        "spoilage_weight": 5.0,
    },
]


# ── /api/recommend (single-channel, v1) ──────────────────────────────────────

class OpportunityResult(BaseModel):
    market_name: str
    location: str
    allocated_qty_kg: float
    price_per_kg: float
    gross_revenue: float
    transport_cost: float
    spoilage_loss_kg: float
    spoilage_loss_value: float
    net_value: float
    rank: int


class RecommendationResponse(BaseModel):
    crop: str
    quantity_kg: float
    quality: str
    farmer_location: str
    opportunities: List[OpportunityResult]
    summary: str


def calculate_opportunities(data: ProduceInput) -> List[OpportunityResult]:
    quality_mult = QUALITY_MULTIPLIER.get(data.quality, 1.0)
    results: List[OpportunityResult] = []

    for m in MARKETS:
        price = round(m["base_price_per_kg"] * quality_mult, 2)
        allocated_qty = min(data.quantity_kg, m["capacity_kg"])
        spoilage_pct = m["base_spoilage_pct"]
        if data.shelf_life_days <= 3:
            spoilage_pct = min(spoilage_pct * 1.5, 30.0)

        gross_revenue = round(allocated_qty * price, 2)
        transport_cost = round(allocated_qty * m["transport_cost_per_kg"], 2)
        spoilage_qty = round(allocated_qty * spoilage_pct / 100, 2)
        spoilage_value = round(spoilage_qty * price, 2)
        net_value = round(gross_revenue - transport_cost - spoilage_value, 2)

        if net_value <= 0:
            continue

        results.append(OpportunityResult(
            market_name=m["market_name"],
            location=m["location"],
            allocated_qty_kg=allocated_qty,
            price_per_kg=price,
            gross_revenue=gross_revenue,
            transport_cost=transport_cost,
            spoilage_loss_kg=spoilage_qty,
            spoilage_loss_value=spoilage_value,
            net_value=net_value,
            rank=0,
        ))

    results.sort(key=lambda r: r.net_value, reverse=True)
    for i, r in enumerate(results):
        r.rank = i + 1
    return results


@app.post("/api/recommend")
def recommend(data: ProduceInput) -> RecommendationResponse:
    opportunities = calculate_opportunities(data)
    if opportunities:
        top = opportunities[0]
        summary = (
            f"Best opportunity: {top.market_name} ({top.location}) — "
            f"expected net value ₹{top.net_value:,.2f} for {top.allocated_qty_kg} kg"
        )
    else:
        summary = "No viable market opportunities found for this produce."

    return RecommendationResponse(
        crop=data.crop,
        quantity_kg=data.quantity_kg,
        quality=data.quality,
        farmer_location=data.farmer_location,
        opportunities=opportunities,
        summary=summary,
    )


# ── /api/decision/optimize (multi-channel allocation) ────────────────────────

class ChannelAllocation(BaseModel):
    market_name: str
    location: str
    quantity_kg: float
    price_per_kg: float
    gross_revenue: float
    transport_cost: float
    spoilage_loss_kg: float
    spoilage_loss_value: float
    net_value: float


class AllocationStrategy(BaseModel):
    strategy_name: str
    strategy_description: str
    allocations: List[ChannelAllocation]
    total_quantity_allocated: float
    total_gross_revenue: float
    total_transport_cost: float
    total_spoilage_loss_value: float
    total_net_value: float


class OptimizeResponse(BaseModel):
    crop: str
    quantity_kg: float
    quality: str
    farmer_location: str
    recommended: AllocationStrategy
    alternatives: List[AllocationStrategy]


def _effective_spoilage_pct(base_pct: float, shelf_life_days: int) -> float:
    if shelf_life_days <= 3:
        return min(base_pct * 1.5, 30.0)
    return base_pct


def _true_net_per_kg(market: dict, quality_mult: float, shelf_life_days: int) -> float:
    """Net value per kg using the unweighted true formula."""
    price = market["base_price_per_kg"] * quality_mult
    sp = _effective_spoilage_pct(market["base_spoilage_pct"], shelf_life_days)
    return price * (1 - sp / 100) - market["transport_cost_per_kg"]


def _solve_strategy(
    quantity_kg: float,
    markets: List[dict],
    quality_mult: float,
    shelf_life_days: int,
    transport_weight: float,
    spoilage_weight: float,
) -> Optional[List[float]]:
    """
    Solve a continuous LP to allocate quantity_kg across markets.

    Objective (per kg for market i):
        score_i = price_i * (1 - sp_i * spoilage_weight / 100)
                - transport_i * transport_weight

    Constraints:
        sum(x_i) <= quantity_kg
        0 <= x_i <= capacity_i   for all i

    Only markets with a positive true net per kg are included.
    Returns a list of allocated quantities parallel to `markets`.
    """
    solver = pywraplp.Solver.CreateSolver("GLOP")
    if not solver:
        return None

    vars_: List[Optional[pywraplp.Variable]] = []
    scores: List[float] = []

    for m in markets:
        true_net = _true_net_per_kg(m, quality_mult, shelf_life_days)
        if true_net <= 0:
            vars_.append(None)
            scores.append(0.0)
            continue

        price = m["base_price_per_kg"] * quality_mult
        sp = _effective_spoilage_pct(m["base_spoilage_pct"], shelf_life_days)
        score = (
            price * (1 - sp * spoilage_weight / 100)
            - m["transport_cost_per_kg"] * transport_weight
        )
        v = solver.NumVar(0.0, m["capacity_kg"], m["market_name"])
        vars_.append(v)
        scores.append(score)

    active = [v for v in vars_ if v is not None]
    if not active:
        return [0.0] * len(markets)

    # Total quantity constraint
    solver.Add(solver.Sum(active) <= quantity_kg)

    # Objective
    obj = solver.Objective()
    for v, s in zip(vars_, scores):
        if v is not None:
            obj.SetCoefficient(v, s)
    obj.SetMaximization()

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return None

    return [
        round(v.solution_value(), 2) if v is not None else 0.0
        for v in vars_
    ]


def _build_strategy(
    data: ProduceInput,
    strategy_cfg: dict,
    quality_mult: float,
    raw_allocations: List[float],
) -> AllocationStrategy:
    """Compute true (unweighted) channel metrics from raw LP allocations."""
    channels: List[ChannelAllocation] = []

    for m, qty in zip(MARKETS, raw_allocations):
        if qty < 0.01:
            continue

        price = round(m["base_price_per_kg"] * quality_mult, 2)
        sp = _effective_spoilage_pct(m["base_spoilage_pct"], data.shelf_life_days)

        gross = round(qty * price, 2)
        transport = round(qty * m["transport_cost_per_kg"], 2)
        spoilage_qty = round(qty * sp / 100, 2)
        spoilage_val = round(spoilage_qty * price, 2)
        net = round(gross - transport - spoilage_val, 2)

        channels.append(ChannelAllocation(
            market_name=m["market_name"],
            location=m["location"],
            quantity_kg=qty,
            price_per_kg=price,
            gross_revenue=gross,
            transport_cost=transport,
            spoilage_loss_kg=spoilage_qty,
            spoilage_loss_value=spoilage_val,
            net_value=net,
        ))

    channels.sort(key=lambda c: c.net_value, reverse=True)

    return AllocationStrategy(
        strategy_name=strategy_cfg["name"],
        strategy_description=strategy_cfg["description"],
        allocations=channels,
        total_quantity_allocated=round(sum(c.quantity_kg for c in channels), 2),
        total_gross_revenue=round(sum(c.gross_revenue for c in channels), 2),
        total_transport_cost=round(sum(c.transport_cost for c in channels), 2),
        total_spoilage_loss_value=round(sum(c.spoilage_loss_value for c in channels), 2),
        total_net_value=round(sum(c.net_value for c in channels), 2),
    )


def _allocation_signature(strategy: AllocationStrategy) -> frozenset:
    """Used to deduplicate strategies that produce identical allocations."""
    return frozenset(
        (ch.market_name, round(ch.quantity_kg, 1))
        for ch in strategy.allocations
    )


@app.post("/api/decision/optimize")
def optimize(data: ProduceInput) -> OptimizeResponse:
    quality_mult = QUALITY_MULTIPLIER.get(data.quality, 1.0)

    strategies: List[AllocationStrategy] = []
    seen_signatures: set = set()

    for cfg in ALLOCATION_STRATEGIES:
        raw = _solve_strategy(
            data.quantity_kg,
            MARKETS,
            quality_mult,
            data.shelf_life_days,
            cfg["transport_weight"],
            cfg["spoilage_weight"],
        )
        if raw is None:
            continue

        strategy = _build_strategy(data, cfg, quality_mult, raw)
        sig = _allocation_signature(strategy)

        # Keep duplicates only when they come from different named strategies —
        # drop if both the allocation AND the name already appeared.
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            strategies.append(strategy)

    # Sort so the highest true net value is recommended.
    strategies.sort(key=lambda s: s.total_net_value, reverse=True)

    if not strategies:
        empty = AllocationStrategy(
            strategy_name="No viable allocation",
            strategy_description="No market offers a positive net return for this produce.",
            allocations=[],
            total_quantity_allocated=0,
            total_gross_revenue=0,
            total_transport_cost=0,
            total_spoilage_loss_value=0,
            total_net_value=0,
        )
        return OptimizeResponse(
            crop=data.crop,
            quantity_kg=data.quantity_kg,
            quality=data.quality,
            farmer_location=data.farmer_location,
            recommended=empty,
            alternatives=[],
        )

    return OptimizeResponse(
        crop=data.crop,
        quantity_kg=data.quantity_kg,
        quality=data.quality,
        farmer_location=data.farmer_location,
        recommended=strategies[0],
        alternatives=strategies[1:],
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
