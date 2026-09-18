from datetime import date
from enum import Enum
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from engine import (
    FarmerData,
    OpportunityData,
    OpportunityResult,
    run_decision_engine,
)

app = FastAPI(title="Farm2Value API")

# Enable CORS so the browser can talk directly to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class QualityTier(str, Enum):
    PREMIUM = "Premium"
    STANDARD = "Standard"
    LOW = "Low"


class DemandLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SpoilageRisk(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class BuyerType(str, Enum):
    DIRECT = "Direct Buyer"
    WHOLESALE = "Wholesale Buyer"
    LOCAL_MARKET = "Local Market"
    RETAIL = "Retail Buyer"


class ProduceInput(BaseModel):
    crop: str = Field(..., min_length=1, max_length=100)
    quantity: float = Field(..., gt=0)
    quality: QualityTier
    location: str = Field(..., min_length=1, max_length=150)
    harvest_date: date
    shelf_life_days: int = Field(..., gt=0, le=365)

    @field_validator("crop", "location")
    @classmethod
    def strip_and_check_non_empty(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or just whitespace")
        return trimmed

    @field_validator("harvest_date")
    @classmethod
    def validate_harvest_date(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Harvest date cannot be in the future")
        return v


class Opportunity(BaseModel):
    id: int
    name: str
    type: BuyerType
    price_per_kg: float
    maximum_capacity_kg: int
    distance_km: float
    estimated_transport_cost: float
    estimated_travel_time_minutes: int
    demand_level: DemandLevel
    minimum_quality: QualityTier
    spoilage_risk: SpoilageRisk


# ---------------------------------------------------------------------------
# Sample dataset — 6 realistic DEMO opportunities
# ---------------------------------------------------------------------------

SAMPLE_OPPORTUNITIES: List[Opportunity] = [
    Opportunity(
        id=1,
        name="Raju Fresh Produce (Direct Buyer)",
        type=BuyerType.DIRECT,
        price_per_kg=28.50,
        maximum_capacity_kg=500,
        distance_km=12.0,
        estimated_transport_cost=320.0,
        estimated_travel_time_minutes=25,
        demand_level=DemandLevel.HIGH,
        minimum_quality=QualityTier.STANDARD,
        spoilage_risk=SpoilageRisk.LOW,
    ),
    Opportunity(
        id=2,
        name="Vijayawada APMC Wholesale Market",
        type=BuyerType.WHOLESALE,
        price_per_kg=22.00,
        maximum_capacity_kg=5000,
        distance_km=35.5,
        estimated_transport_cost=850.0,
        estimated_travel_time_minutes=60,
        demand_level=DemandLevel.HIGH,
        minimum_quality=QualityTier.LOW,
        spoilage_risk=SpoilageRisk.MEDIUM,
    ),
    Opportunity(
        id=3,
        name="Green Basket Retail Chain",
        type=BuyerType.RETAIL,
        price_per_kg=34.00,
        maximum_capacity_kg=200,
        distance_km=8.0,
        estimated_transport_cost=180.0,
        estimated_travel_time_minutes=18,
        demand_level=DemandLevel.MEDIUM,
        minimum_quality=QualityTier.PREMIUM,
        spoilage_risk=SpoilageRisk.LOW,
    ),
    Opportunity(
        id=4,
        name="Guntur Local Sabzi Mandi",
        type=BuyerType.LOCAL_MARKET,
        price_per_kg=19.50,
        maximum_capacity_kg=800,
        distance_km=62.0,
        estimated_transport_cost=1200.0,
        estimated_travel_time_minutes=90,
        demand_level=DemandLevel.MEDIUM,
        minimum_quality=QualityTier.LOW,
        spoilage_risk=SpoilageRisk.HIGH,
    ),
    Opportunity(
        id=5,
        name="FreshMart Superstore (Retail)",
        type=BuyerType.RETAIL,
        price_per_kg=31.00,
        maximum_capacity_kg=350,
        distance_km=18.5,
        estimated_transport_cost=420.0,
        estimated_travel_time_minutes=35,
        demand_level=DemandLevel.HIGH,
        minimum_quality=QualityTier.STANDARD,
        spoilage_risk=SpoilageRisk.LOW,
    ),
    Opportunity(
        id=6,
        name="Krishna Agro Wholesale Hub",
        type=BuyerType.WHOLESALE,
        price_per_kg=24.75,
        maximum_capacity_kg=3000,
        distance_km=28.0,
        estimated_transport_cost=650.0,
        estimated_travel_time_minutes=45,
        demand_level=DemandLevel.MEDIUM,
        minimum_quality=QualityTier.STANDARD,
        spoilage_risk=SpoilageRisk.MEDIUM,
    ),
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/decision/input")
def receive_produce_input(payload: ProduceInput):
    """Validates farmer produce input and returns the structured data."""
    return {
        "status": "success",
        "message": "Produce details validated successfully",
        "data": payload,
    }


@app.get("/api/opportunities", response_model=List[Opportunity])
def get_opportunities():
    """Returns the sample list of selling opportunities."""
    return SAMPLE_OPPORTUNITIES


@app.post("/api/decision/calculate")
def calculate_decision(payload: ProduceInput):
    """
    Runs the Farm2Value decision engine.

    For each opportunity, calculates:
      - Gross revenue
      - Transport cost (fixed fee)
      - Expected spoilage loss (based on risk, shelf life, demand, distance)
      - Expected net value

    Returns all opportunities ranked by expected net value (feasible first).
    Does NOT simply choose the highest price — a nearby cheaper buyer often
    has a higher net value once transport and spoilage are deducted.
    """
    farmer = FarmerData(
        crop=payload.crop,
        quantity=payload.quantity,
        quality=payload.quality.value,
        shelf_life_days=payload.shelf_life_days,
    )

    opp_data = [
        OpportunityData(
            id=opp.id,
            name=opp.name,
            type=opp.type.value,
            price_per_kg=opp.price_per_kg,
            maximum_capacity_kg=opp.maximum_capacity_kg,
            distance_km=opp.distance_km,
            estimated_transport_cost=opp.estimated_transport_cost,
            estimated_travel_time_minutes=opp.estimated_travel_time_minutes,
            demand_level=opp.demand_level.value,
            minimum_quality=opp.minimum_quality.value,
            spoilage_risk=opp.spoilage_risk.value,
        )
        for opp in SAMPLE_OPPORTUNITIES
    ]

    results: List[OpportunityResult] = run_decision_engine(farmer, opp_data)

    return {
        "status": "success",
        "farmer": payload,
        "total_opportunities_evaluated": len(results),
        "feasible_count": sum(1 for r in results if r.is_feasible),
        "results": [
            {
                "opportunity_id": r.opportunity_id,
                "opportunity_name": r.opportunity_name,
                "buyer_type": r.buyer_type,
                "is_feasible": r.is_feasible,
                "infeasibility_reason": r.infeasibility_reason,
                "allocated_quantity_kg": r.allocated_quantity_kg,
                "selling_price_per_kg": r.selling_price_per_kg,
                "gross_revenue": r.gross_revenue,
                "transport_cost": r.transport_cost,
                "spoilage_percentage": r.spoilage_percentage,
                "spoilage_loss": r.spoilage_loss,
                "expected_net_value": r.expected_net_value,
                "risk_level": r.risk_level,
                "explanation": r.explanation,
            }
            for r in results
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
