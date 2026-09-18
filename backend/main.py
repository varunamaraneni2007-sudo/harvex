from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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


# ── Models ────────────────────────────────────────────────────────────────────

class ProduceInput(BaseModel):
    crop: str
    quantity_kg: float
    quality: str          # "Premium" | "Standard" | "Low"
    farmer_location: str
    harvest_date: str     # display-only string in v1
    shelf_life_days: int


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


# ── Decision engine ───────────────────────────────────────────────────────────

def calculate_opportunities(data: ProduceInput) -> List[OpportunityResult]:
    quality_mult = QUALITY_MULTIPLIER.get(data.quality, 1.0)
    results: List[OpportunityResult] = []

    for m in MARKETS:
        price = round(m["base_price_per_kg"] * quality_mult, 2)
        allocated_qty = min(data.quantity_kg, m["capacity_kg"])

        # Increase spoilage estimate when shelf life is critically short
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


# ── Endpoint ──────────────────────────────────────────────────────────────────

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
