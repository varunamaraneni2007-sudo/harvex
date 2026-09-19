import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Tuple

from maps_service import enrich_markets_with_distances
from explanation_service import generate_explanation, generate_whatif_explanation

from ortools.linear_solver import pywraplp

# ── Supabase client (lazy, optional) ─────────────────────────────────────────

_supabase_client = None  # module-level singleton; replaced in tests


def _get_supabase():
    """Return a live Supabase client or None if credentials are not configured."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception:
        return None

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
        "buyer_type": "Local Mandi",
        "accepted_crops": ["all"],
        "min_quality": "Low",
    },
    {
        "market_name": "Guntur Wholesale Hub",
        "location": "Guntur",
        "base_price_per_kg": 15.0,
        "transport_cost_per_kg": 1.2,
        "capacity_kg": 2000.0,
        "base_spoilage_pct": 5.0,
        "buyer_type": "Wholesale Buyer",
        "accepted_crops": ["all"],
        "min_quality": "Low",
    },
    {
        "market_name": "Hyderabad Metro Market",
        "location": "Hyderabad",
        "base_price_per_kg": 20.0,
        "transport_cost_per_kg": 3.5,
        "capacity_kg": 5000.0,
        "base_spoilage_pct": 8.0,
        "buyer_type": "Retail Chain",
        "accepted_crops": ["all"],
        "min_quality": "Standard",
    },
    {
        "market_name": "FreshLink Retail Aggregator",
        "location": "Vijayawada",
        "base_price_per_kg": 18.0,
        "transport_cost_per_kg": 0.8,
        "capacity_kg": 300.0,
        "base_spoilage_pct": 2.0,
        "buyer_type": "Retail Chain",
        "accepted_crops": ["all"],
        "min_quality": "Standard",
    },
    {
        "market_name": "FreezeMart Cold Storage",
        "location": "Guntur",
        "base_price_per_kg": 14.0,
        "transport_cost_per_kg": 1.5,
        "capacity_kg": 10000.0,
        "base_spoilage_pct": 1.0,
        "buyer_type": "Cold Storage",
        "accepted_crops": ["all"],
        "min_quality": "Low",
    },
]

QUALITY_MULTIPLIER = {
    "Premium": 1.15,
    "Standard": 1.00,
    "Low": 0.80,
}

# Numeric rank for quality comparison (used by marketplace suitability check)
QUALITY_ORDER = {"Low": 0, "Standard": 1, "Premium": 2}

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


def _eligible_markets(markets: List[dict], quality: str) -> List[dict]:
    """Return only markets whose min_quality the farmer's produce meets."""
    farmer_rank = QUALITY_ORDER.get(quality, 1)
    return [
        m for m in markets
        if QUALITY_ORDER.get(m.get("min_quality", "Low"), 0) <= farmer_rank
    ]


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
    markets: Optional[List[dict]] = None,
) -> AllocationStrategy:
    """Compute true (unweighted) channel metrics from raw LP allocations."""
    if markets is None:
        markets = MARKETS
    channels: List[ChannelAllocation] = []

    for m, qty in zip(markets, raw_allocations):
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


def _run_optimize(data: ProduceInput, markets: List[dict]) -> OptimizeResponse:
    """Core optimizer; accepts any markets list (real-distance or static)."""
    quality_mult = QUALITY_MULTIPLIER.get(data.quality, 1.0)
    markets = _eligible_markets(markets, data.quality)

    strategies: List[AllocationStrategy] = []
    seen_signatures: set = set()

    for cfg in ALLOCATION_STRATEGIES:
        raw = _solve_strategy(
            data.quantity_kg,
            markets,
            quality_mult,
            data.shelf_life_days,
            cfg["transport_weight"],
            cfg["spoilage_weight"],
        )
        if raw is None:
            continue

        strategy = _build_strategy(data, cfg, quality_mult, raw, markets)
        sig = _allocation_signature(strategy)

        if sig not in seen_signatures:
            seen_signatures.add(sig)
            strategies.append(strategy)

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


@app.post("/api/decision/optimize")
def optimize(data: ProduceInput) -> OptimizeResponse:
    return _run_optimize(data, MARKETS)


# ── /api/markets ─────────────────────────────────────────────────────────────

@app.get("/api/markets")
def list_markets():
    return [
        {"market_name": m["market_name"], "location": m["location"]}
        for m in MARKETS
    ]


# ── /api/decision/whatif ──────────────────────────────────────────────────────

class WhatIfScenario(BaseModel):
    transport_cost_increase_pct: float = 0.0   # 0–100
    price_decrease_pct: float = 0.0            # 0–50
    shelf_life_reduction_days: int = 0          # 0–3
    cancelled_market: Optional[str] = None      # market_name to exclude
    capacity_reduction_pct: float = 0.0        # 0–100


class WhatIfRequest(BaseModel):
    produce: ProduceInput
    scenario: WhatIfScenario


class WhatIfPlan(BaseModel):
    allocations: List[ChannelAllocation]
    total_quantity_allocated: float
    total_gross_revenue: float
    total_transport_cost: float
    total_spoilage_loss_value: float
    total_net_value: float


class WhatIfResponse(BaseModel):
    crop: str
    quantity_kg: float
    quality: str
    farmer_location: str
    scenario_description: str
    current_plan: WhatIfPlan
    whatif_plan: WhatIfPlan
    delta_net_value: float
    explanation: Optional[str] = None


def _greedy_allocate(quantity_kg: float, markets: List[dict], quality_mult: float, shelf_life_days: int) -> List[float]:
    """
    Greedy allocation: sort markets by true net per kg (descending), fill to
    capacity. Equivalent to GLOP for this linear objective.
    """
    indexed = [
        (i, _true_net_per_kg(m, quality_mult, shelf_life_days), m["capacity_kg"])
        for i, m in enumerate(markets)
    ]
    indexed.sort(key=lambda t: t[1], reverse=True)

    allocations = [0.0] * len(markets)
    remaining = quantity_kg
    for idx, net_per_kg, cap in indexed:
        if net_per_kg <= 0 or remaining <= 0:
            break
        alloc = min(remaining, cap)
        allocations[idx] = round(alloc, 2)
        remaining -= alloc

    return allocations


def _apply_scenario(markets: List[dict], data: ProduceInput, scenario: WhatIfScenario):
    """Return (modified_markets, effective_shelf_life_days)."""
    effective_shelf = max(1, data.shelf_life_days - scenario.shelf_life_reduction_days)

    modified = []
    for m in markets:
        if m["market_name"] == scenario.cancelled_market:
            continue
        cap_factor = 1.0 - scenario.capacity_reduction_pct / 100.0
        modified.append({
            **m,
            "base_price_per_kg": m["base_price_per_kg"] * (1.0 - scenario.price_decrease_pct / 100.0),
            "transport_cost_per_kg": m["transport_cost_per_kg"] * (1.0 + scenario.transport_cost_increase_pct / 100.0),
            "capacity_kg": m["capacity_kg"] * cap_factor,
        })
    return modified, effective_shelf


def _scenario_description(scenario: WhatIfScenario) -> str:
    parts = []
    if scenario.transport_cost_increase_pct:
        parts.append(f"transport costs +{scenario.transport_cost_increase_pct:.0f}%")
    if scenario.price_decrease_pct:
        parts.append(f"prices -{scenario.price_decrease_pct:.0f}%")
    if scenario.shelf_life_reduction_days:
        parts.append(f"shelf life -{scenario.shelf_life_reduction_days}d")
    if scenario.cancelled_market:
        parts.append(f"{scenario.cancelled_market} cancelled")
    if scenario.capacity_reduction_pct:
        parts.append(f"capacity -{scenario.capacity_reduction_pct:.0f}%")
    return ", ".join(parts) if parts else "No changes (baseline)"


def _plan_from_allocations(markets: List[dict], raw: List[float], quality_mult: float, shelf_life_days: int) -> WhatIfPlan:
    channels: List[ChannelAllocation] = []
    for m, qty in zip(markets, raw):
        if qty < 0.01:
            continue
        price = round(m["base_price_per_kg"] * quality_mult, 2)
        sp = _effective_spoilage_pct(m["base_spoilage_pct"], shelf_life_days)
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
    return WhatIfPlan(
        allocations=channels,
        total_quantity_allocated=round(sum(c.quantity_kg for c in channels), 2),
        total_gross_revenue=round(sum(c.gross_revenue for c in channels), 2),
        total_transport_cost=round(sum(c.transport_cost for c in channels), 2),
        total_spoilage_loss_value=round(sum(c.spoilage_loss_value for c in channels), 2),
        total_net_value=round(sum(c.net_value for c in channels), 2),
    )


@app.post("/api/decision/whatif")
def whatif(req: WhatIfRequest) -> WhatIfResponse:
    data = req.produce
    scenario = req.scenario
    quality_mult = QUALITY_MULTIPLIER.get(data.quality, 1.0)

    # Current plan — greedy on original MARKETS (filtered by quality)
    eligible = _eligible_markets(MARKETS, data.quality)
    current_raw = _greedy_allocate(data.quantity_kg, eligible, quality_mult, data.shelf_life_days)
    current_plan = _plan_from_allocations(eligible, current_raw, quality_mult, data.shelf_life_days)

    # What-if plan — greedy on modified markets / shelf life (also quality-filtered)
    modified_markets, effective_shelf = _apply_scenario(eligible, data, scenario)
    if modified_markets:
        whatif_raw = _greedy_allocate(data.quantity_kg, modified_markets, quality_mult, effective_shelf)
        whatif_plan = _plan_from_allocations(modified_markets, whatif_raw, quality_mult, effective_shelf)
    else:
        whatif_plan = WhatIfPlan(
            allocations=[],
            total_quantity_allocated=0,
            total_gross_revenue=0,
            total_transport_cost=0,
            total_spoilage_loss_value=0,
            total_net_value=0,
        )

    resp = WhatIfResponse(
        crop=data.crop,
        quantity_kg=data.quantity_kg,
        quality=data.quality,
        farmer_location=data.farmer_location,
        scenario_description=_scenario_description(scenario),
        current_plan=current_plan,
        whatif_plan=whatif_plan,
        delta_net_value=round(whatif_plan.total_net_value - current_plan.total_net_value, 2),
    )
    resp.explanation = generate_whatif_explanation(req, resp)
    return resp


# ── /api/decision/plans (Plan A / B / C) ─────────────────────────────────────

class PlanResult(BaseModel):
    plan_label: str           # "A", "B", "C"
    plan_name: str
    plan_description: str
    plan_tradeoff: str
    allocations: List[ChannelAllocation]
    total_quantity_allocated: float
    total_gross_revenue: float
    total_transport_cost: float
    total_spoilage_loss_value: float
    total_net_value: float


class PlansResponse(BaseModel):
    crop: str
    quantity_kg: float
    quality: str
    farmer_location: str
    plan_a: PlanResult
    plan_b: PlanResult
    plan_c: PlanResult


def _plan_b_allocate(quantity_kg: float, markets: List[dict], quality_mult: float, shelf_life_days: int) -> List[float]:
    """Diversified greedy: cap each viable market at 60 % of total quantity to spread risk."""
    viable_count = sum(
        1 for m in markets if _true_net_per_kg(m, quality_mult, shelf_life_days) > 0
    )
    if viable_count < 2:
        return _greedy_allocate(quantity_kg, markets, quality_mult, shelf_life_days)

    max_per_market = quantity_kg * 0.6
    modified = [
        {**m, "capacity_kg": min(m["capacity_kg"], max_per_market)}
        if _true_net_per_kg(m, quality_mult, shelf_life_days) > 0
        else m
        for m in markets
    ]
    return _greedy_allocate(quantity_kg, modified, quality_mult, shelf_life_days)


def _plan_c_allocate(quantity_kg: float, markets: List[dict], quality_mult: float, shelf_life_days: int) -> List[float]:
    """Quick-sale greedy: penalise transport cost 5× to favour nearby buyers."""
    TRANSPORT_WEIGHT = 5.0
    indexed = []
    for i, m in enumerate(markets):
        if _true_net_per_kg(m, quality_mult, shelf_life_days) <= 0:
            continue
        price = m["base_price_per_kg"] * quality_mult
        sp = _effective_spoilage_pct(m["base_spoilage_pct"], shelf_life_days)
        score = price * (1 - sp / 100) - m["transport_cost_per_kg"] * TRANSPORT_WEIGHT
        indexed.append((i, score, m["capacity_kg"]))
    indexed.sort(key=lambda t: t[1], reverse=True)

    allocations = [0.0] * len(markets)
    remaining = quantity_kg
    for idx, _score, cap in indexed:
        if remaining <= 0:
            break
        alloc = min(remaining, cap)
        allocations[idx] = round(alloc, 2)
        remaining -= alloc
    return allocations


def _build_plan_result(
    plan_label: str,
    plan_name: str,
    plan_description: str,
    plan_tradeoff: str,
    markets: List[dict],
    raw: List[float],
    quality_mult: float,
    shelf_life_days: int,
) -> PlanResult:
    channels: List[ChannelAllocation] = []
    for m, qty in zip(markets, raw):
        if qty < 0.01:
            continue
        price = round(m["base_price_per_kg"] * quality_mult, 2)
        sp = _effective_spoilage_pct(m["base_spoilage_pct"], shelf_life_days)
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
    return PlanResult(
        plan_label=plan_label,
        plan_name=plan_name,
        plan_description=plan_description,
        plan_tradeoff=plan_tradeoff,
        allocations=channels,
        total_quantity_allocated=round(sum(c.quantity_kg for c in channels), 2),
        total_gross_revenue=round(sum(c.gross_revenue for c in channels), 2),
        total_transport_cost=round(sum(c.transport_cost for c in channels), 2),
        total_spoilage_loss_value=round(sum(c.spoilage_loss_value for c in channels), 2),
        total_net_value=round(sum(c.net_value for c in channels), 2),
    )


def _run_plans(data: ProduceInput, markets: List[dict]) -> PlansResponse:
    """Core plan generator; accepts any markets list (real-distance or static)."""
    quality_mult = QUALITY_MULTIPLIER.get(data.quality, 1.0)
    markets = _eligible_markets(markets, data.quality)

    raw_a = _greedy_allocate(data.quantity_kg, markets, quality_mult, data.shelf_life_days)
    raw_b = _plan_b_allocate(data.quantity_kg, markets, quality_mult, data.shelf_life_days)
    raw_c = _plan_c_allocate(data.quantity_kg, markets, quality_mult, data.shelf_life_days)

    plan_a = _build_plan_result(
        "A", "Primary Plan",
        "Allocates your harvest to maximise total expected net value across all buyers.",
        "Concentrates volume in the highest-value market — risk if that buyer cancels.",
        markets, raw_a, quality_mult, data.shelf_life_days,
    )
    plan_b = _build_plan_result(
        "B", "Lower-Risk Plan",
        "Spreads the harvest across more buyers to reduce dependence on any single market.",
        "Net value may be slightly lower than Plan A, but protects against buyer failure.",
        markets, raw_b, quality_mult, data.shelf_life_days,
    )
    plan_c = _build_plan_result(
        "C", "Quick-Sale Plan",
        "Prioritises nearby, low-transport-cost buyers for a faster cash turnaround.",
        "May yield less net value than Plan A, but reduces transit time and logistics risk.",
        markets, raw_c, quality_mult, data.shelf_life_days,
    )

    return PlansResponse(
        crop=data.crop,
        quantity_kg=data.quantity_kg,
        quality=data.quality,
        farmer_location=data.farmer_location,
        plan_a=plan_a,
        plan_b=plan_b,
        plan_c=plan_c,
    )


@app.post("/api/decision/plans")
def plans(data: ProduceInput) -> PlansResponse:
    return _run_plans(data, MARKETS)


# ── /api/submission (persist + return all results) ────────────────────────────

class SubmissionResponse(BaseModel):
    optimize: OptimizeResponse
    plans: PlansResponse
    saved: bool
    farmer_input_id: Optional[str] = None
    explanation: Optional[str] = None


def _save_plan_rows(sb, farmer_input_id: str, plan_name: str, plan) -> None:
    """Insert one decision_result row plus its allocation rows."""
    result_row = (
        sb.table("decision_results")
        .insert({
            "farmer_input_id": farmer_input_id,
            "plan_name": plan_name,
            "total_allocated_kg": float(plan.total_quantity_allocated),
            "gross_revenue": float(plan.total_gross_revenue),
            "transport_cost": float(plan.total_transport_cost),
            "spoilage_loss": float(plan.total_spoilage_loss_value),
            "expected_net_value": float(plan.total_net_value),
        })
        .execute()
    )
    decision_result_id = result_row.data[0]["id"]

    for ch in plan.allocations:
        sb.table("allocations").insert({
            "decision_result_id": decision_result_id,
            "buyer_name": ch.market_name,
            "allocated_quantity_kg": float(ch.quantity_kg),
            "selling_price_per_kg": float(ch.price_per_kg),
            "gross_revenue": float(ch.gross_revenue),
            "transport_cost": float(ch.transport_cost),
            "spoilage_loss": float(ch.spoilage_loss_value),
            "expected_net_value": float(ch.net_value),
        }).execute()


def _save_to_supabase(
    data,
    optimize_resp: OptimizeResponse,
    plans_resp: PlansResponse,
) -> Optional[str]:
    """
    Persist farmer input + recommended plan + Plan A/B/C to Supabase.
    Returns the farmer_input_id UUID on success, or None on any failure.
    Never raises — Supabase unavailability must not break the response.
    """
    sb = _get_supabase()
    if sb is None:
        return None
    try:
        input_row = (
            sb.table("farmer_inputs")
            .insert({
                "crop": data.crop,
                "quantity_kg": float(data.quantity_kg),
                "quality": data.quality,
                "farmer_location": data.farmer_location,
                "harvest_date": data.harvest_date,
                "shelf_life_days": data.shelf_life_days,
            })
            .execute()
        )
        farmer_input_id: str = input_row.data[0]["id"]

        _save_plan_rows(sb, farmer_input_id, "optimize_recommended", optimize_resp.recommended)
        _save_plan_rows(sb, farmer_input_id, "plan_a", plans_resp.plan_a)
        _save_plan_rows(sb, farmer_input_id, "plan_b", plans_resp.plan_b)
        _save_plan_rows(sb, farmer_input_id, "plan_c", plans_resp.plan_c)

        return farmer_input_id
    except Exception:
        return None


@app.post("/api/submission")
def submission(data: ProduceInput) -> SubmissionResponse:
    # Enrich markets with real road distances; falls back to static costs if
    # the Maps API key is missing or the call fails.
    markets = enrich_markets_with_distances(data.farmer_location, MARKETS)
    optimize_resp = _run_optimize(data, markets)
    plans_resp = _run_plans(data, markets)
    farmer_input_id = _save_to_supabase(data, optimize_resp, plans_resp)
    explanation = generate_explanation(data, optimize_resp, plans_resp)
    return SubmissionResponse(
        optimize=optimize_resp,
        plans=plans_resp,
        saved=farmer_input_id is not None,
        farmer_input_id=farmer_input_id,
        explanation=explanation,
    )


# ── /api/distances (informational — road distances for all markets) ───────────

@app.get("/api/distances")
def distances(farmer_location: str = Query(..., description="Farmer's location")):
    """
    Return road distance and effective transport cost from farmer_location to
    every market.  distance_km is null when the Maps API is unavailable.
    """
    enriched = enrich_markets_with_distances(farmer_location, MARKETS)
    return [
        {
            "market_name": m["market_name"],
            "location": m["location"],
            "distance_km": m.get("distance_km"),
            "travel_time_minutes": m.get("travel_time_minutes"),
            "transport_cost_per_kg": m["transport_cost_per_kg"],
            "maps_live": m.get("distance_km") is not None,
        }
        for m in enriched
    ]


# ── /api/places — Google Places proxy (key never reaches browser) ─────────────

@app.get("/api/places/autocomplete")
def places_autocomplete(
    input: str = Query(..., description="User search text"),
    session_token: str = Query(default="", description="Billing session token"),
):
    """
    Proxy to Google Places Autocomplete (New) API.  The Google API key stays
    on the server; the browser never sees it.  Returns suggestions plus a
    maps_configured flag so the frontend can degrade to free-text gracefully.
    """
    from maps_service import autocomplete_places
    key_present = bool(os.getenv("GOOGLE_MAPS_API_KEY", ""))
    suggestions = autocomplete_places(input, session_token)
    return {"suggestions": suggestions, "maps_configured": key_present}


@app.get("/api/places/details")
def places_details(place_id: str = Query(..., description="Google Place ID")):
    """
    Proxy to Google Place Details (New) API.  Returns the canonical address,
    place ID, and lat/lng for the selected place, or place: null on failure.
    """
    from maps_service import get_place_details
    key_present = bool(os.getenv("GOOGLE_MAPS_API_KEY", ""))
    details = get_place_details(place_id)
    return {"place": details, "maps_configured": key_present}


# ── /api/marketplace ──────────────────────────────────────────────────────────

class MarketCard(BaseModel):
    market_name: str
    buyer_type: str
    location: str
    base_price_per_kg: float
    effective_price_per_kg: Optional[float] = None
    transport_cost_per_kg: float
    capacity_kg: float
    base_spoilage_pct: float
    effective_spoilage_pct: Optional[float] = None
    distance_km: Optional[float] = None
    travel_time_minutes: Optional[float] = None
    maps_live: bool = False
    accepted_crops: List[str]
    min_quality: str
    suitability: str = "Unknown"
    suitability_reason: str = ""
    net_value_per_kg: Optional[float] = None
    total_net_value: Optional[float] = None


def _compute_suitability(
    market: dict,
    crop: Optional[str] = None,
    quality: Optional[str] = None,
    quantity_kg: Optional[float] = None,
    shelf_life_days: Optional[int] = None,
) -> Tuple[str, str]:
    """
    Return (suitability_label, reason_string) for a market given farmer context.
    Labels: "Suitable" | "Partial" | "Not Suitable"
    """
    accepted = market.get("accepted_crops", ["all"])
    min_q = market.get("min_quality", "Low")
    cap = market["capacity_kg"]

    # 1. Crop compatibility
    if crop and "all" not in [a.lower() for a in accepted]:
        if crop.lower() not in [a.lower() for a in accepted]:
            return "Not Suitable", f"Does not purchase {crop}."

    # 2. Quality compatibility
    if quality:
        farmer_rank = QUALITY_ORDER.get(quality, 1)
        req_rank = QUALITY_ORDER.get(min_q, 0)
        if farmer_rank < req_rank:
            return (
                "Not Suitable",
                f"Requires {min_q} quality or better; your produce is {quality} grade.",
            )

    level = "Suitable"
    notes: List[str] = []

    # 3. Capacity vs quantity
    if quantity_kg and quantity_kg > 0 and cap < quantity_kg:
        pct = round(cap / quantity_kg * 100)
        level = "Partial"
        notes.append(
            f"capacity {cap:.0f} kg — can take {pct}% of your {quantity_kg:.0f} kg harvest"
        )

    # 4. Travel time risk vs shelf life
    travel_min = market.get("travel_time_minutes")
    if shelf_life_days and travel_min:
        travel_days = travel_min / 60.0 / 24.0
        if travel_days > shelf_life_days * 0.5:
            if level == "Suitable":
                level = "Partial"
            travel_h = round(travel_min / 60, 1)
            notes.append(
                f"travel time (~{travel_h}h) may strain {shelf_life_days}d shelf life"
            )

    # Build human-readable reason
    if level == "Suitable":
        parts: List[str] = []
        if crop:
            parts.append(f"accepts {crop}")
        if quality:
            parts.append(f"{quality} quality meets requirement")
        if quantity_kg:
            parts.append(f"has capacity for your full {quantity_kg:.0f} kg harvest")
        reason = "Suitable" + (f" — {', '.join(parts)}." if parts else ".")
    else:
        reason = "Limited — " + "; ".join(notes) + "." if notes else "Partially suitable."

    return level, reason


@app.get("/api/marketplace")
def marketplace(
    farmer_location: str = Query(..., description="Farmer's location"),
    crop: Optional[str] = Query(None),
    quality: Optional[str] = Query(None),
    quantity_kg: Optional[float] = Query(None, gt=0),
    shelf_life_days: Optional[int] = Query(None, gt=0),
    min_price_per_kg: float = Query(0.0, ge=0),
    max_distance_km: Optional[float] = Query(None, gt=0),
    min_capacity_kg: float = Query(0.0, ge=0),
) -> List[MarketCard]:
    """
    Return enriched market/buyer cards for the marketplace view.
    Filters, suitability, and net-value previews are all computed server-side
    using the same decision-engine calculations as the rest of the API.
    """
    enriched = enrich_markets_with_distances(farmer_location, MARKETS)

    cards: List[MarketCard] = []
    for m in enriched:
        distance_km: Optional[float] = m.get("distance_km")
        travel_time_minutes: Optional[float] = m.get("travel_time_minutes")
        maps_live = distance_km is not None

        # ── Filters ──────────────────────────────────────────────────────────
        if m["base_price_per_kg"] < min_price_per_kg:
            continue
        if m["capacity_kg"] < min_capacity_kg:
            continue
        # Only apply distance filter when the distance is actually known
        if max_distance_km is not None and distance_km is not None:
            if distance_km > max_distance_km:
                continue

        # ── Suitability ───────────────────────────────────────────────────────
        # Attach live travel_time_minutes so _compute_suitability can check shelf risk
        m_with_travel = {**m, "travel_time_minutes": travel_time_minutes}
        suitability, reason = _compute_suitability(
            m_with_travel, crop, quality, quantity_kg, shelf_life_days
        )

        # ── Per-quality effective values ──────────────────────────────────────
        effective_price: Optional[float] = None
        effective_spoilage: Optional[float] = None
        net_value_per_kg: Optional[float] = None
        total_net_value: Optional[float] = None

        if quality:
            qm = QUALITY_MULTIPLIER.get(quality, 1.0)
            effective_price = round(m["base_price_per_kg"] * qm, 2)

        if shelf_life_days is not None:
            effective_spoilage = round(
                _effective_spoilage_pct(m["base_spoilage_pct"], shelf_life_days), 2
            )

        if quality and shelf_life_days is not None:
            qm = QUALITY_MULTIPLIER.get(quality, 1.0)
            nv = _true_net_per_kg(m, qm, shelf_life_days)
            if nv > 0:
                net_value_per_kg = round(nv, 2)
                if quantity_kg:
                    eff_qty = min(quantity_kg, m["capacity_kg"])
                    total_net_value = round(nv * eff_qty, 2)

        cards.append(MarketCard(
            market_name=m["market_name"],
            buyer_type=m["buyer_type"],
            location=m["location"],
            base_price_per_kg=m["base_price_per_kg"],
            effective_price_per_kg=effective_price,
            transport_cost_per_kg=round(m["transport_cost_per_kg"], 4),
            capacity_kg=m["capacity_kg"],
            base_spoilage_pct=m["base_spoilage_pct"],
            effective_spoilage_pct=effective_spoilage,
            distance_km=distance_km,
            travel_time_minutes=travel_time_minutes,
            maps_live=maps_live,
            accepted_crops=m["accepted_crops"],
            min_quality=m["min_quality"],
            suitability=suitability,
            suitability_reason=reason,
            net_value_per_kg=net_value_per_kg,
            total_net_value=total_net_value,
        ))

    # Sort: Suitable first, then Partial, then Not Suitable; within group by base price desc
    order = {"Suitable": 0, "Partial": 1, "Not Suitable": 2, "Unknown": 3}
    cards.sort(key=lambda c: (order.get(c.suitability, 3), -c.base_price_per_kg))
    return cards


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
