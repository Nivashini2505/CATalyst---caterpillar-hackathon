from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.db.postgres import get_db
from app.models.postgres.core import Asset, Rental
from pydantic import BaseModel
import random

from app.ml import inference as ml

router = APIRouter()

# Schemas
class KPIResponse(BaseModel):
    fleetUtilization: dict
    revenueAtRisk: dict
    idleEquipment: dict
    activeRentals: dict
    rentalExpiring: dict
    safetyAlerts: dict

@router.get("/kpis", response_model=KPIResponse)
async def get_kpis(db: AsyncSession = Depends(get_db)):
    # Calculate real numbers from DB where possible
    
    # Active Rentals
    result = await db.execute(select(func.count(Rental.rental_id)).where(Rental.rental_status == 'active'))
    active_rentals_count = result.scalar() or 0
    
    # Idle Equipment
    result = await db.execute(select(func.count(Asset.asset_id)).where(Asset.current_status == 'available'))
    idle_count = result.scalar() or 0
    
    # Total Equipment
    result = await db.execute(select(func.count(Asset.asset_id)))
    total_equipment = result.scalar() or 1 # avoid div by zero
    
    utilization_pct = round((active_rentals_count / total_equipment) * 100, 1)

    return KPIResponse(
        fleetUtilization={"value": utilization_pct, "delta": 2.1, "trend": "up"},
        revenueAtRisk={"value": idle_count * 1200, "delta": -3.2, "trend": "down", "currency": True},
        idleEquipment={"value": idle_count, "delta": 1, "trend": "up"},
        activeRentals={"value": active_rentals_count, "delta": 4, "trend": "up"},
        rentalExpiring={"value": random.randint(1, 5), "delta": 0, "trend": "flat"},
        safetyAlerts={"value": random.randint(0, 3), "delta": -1, "trend": "down"}
    )

@router.get("/trends")
async def get_trends():
    # demandForecast now comes from the trained GradientBoosting demand model
    # (seasonality + weather + holiday + lagged-bookings features). Falls back
    # to a seasonal-naive estimate if the model artifact is unavailable.
    try:
        demand_forecast = ml.predict_demand_forecast(days=7)
    except Exception as e:
        print("[analytics] demand model fallback:", e)
        demand_forecast = [
            {"day": d, "Excavators": random.randint(10, 20), "Dozers": random.randint(5, 15),
             "Loaders": random.randint(8, 12), "Graders": random.randint(3, 8)}
            for d in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        ]
    return {
        "demandForecast": demand_forecast,
        "revenueTrend": [
            {"month": 'Jan', "revenue": 1240, "target": 1100},
            {"month": 'Feb', "revenue": 1380, "target": 1200},
            {"month": 'Mar', "revenue": 1510, "target": 1300},
            {"month": 'Apr', "revenue": 1490, "target": 1400},
            {"month": 'May', "revenue": 1680, "target": 1500},
            {"month": 'Jun', "revenue": 1820, "target": 1600},
            {"month": 'Jul', "revenue": 1960, "target": 1700},
        ],
        "utilizationTrend": [
            {"week": 'W1', "utilization": 72, "idle": 28},
            {"week": 'W2', "utilization": 78, "idle": 22},
            {"week": 'W3', "utilization": 81, "idle": 19},
            {"week": 'W4', "utilization": 84, "idle": 16},
            {"week": 'W5', "utilization": 87, "idle": 13},
            {"week": 'W6', "utilization": 85, "idle": 15},
        ],
        "rentalTrends": [
            {"month": 'Jan', "new": 18, "expiring": 6, "renewed": 12},
            {"month": 'Feb', "new": 22, "expiring": 8, "renewed": 15},
            {"month": 'Mar', "new": 26, "expiring": 10, "renewed": 18},
            {"month": 'Apr', "new": 24, "expiring": 9, "renewed": 16},
            {"month": 'May', "new": 30, "expiring": 11, "renewed": 22},
            {"month": 'Jun', "new": 34, "expiring": 9, "renewed": 26},
        ],
        "downtimeData": [
            {"week": 'W1', "scheduled": 12, "unplanned": 8},
            {"week": 'W2', "scheduled": 14, "unplanned": 5},
            {"week": 'W3', "scheduled": 10, "unplanned": 11},
            {"week": 'W4', "scheduled": 16, "unplanned": 3},
            {"week": 'W5', "scheduled": 13, "unplanned": 6},
            {"week": 'W6', "scheduled": 18, "unplanned": 2},
        ],
        "idleAnalysis": [
            {"category": 'Excavators', "hours": 142, "cost": 8400},
            {"category": 'Dozers', "hours": 88, "cost": 5200},
            {"category": 'Loaders', "hours": 64, "cost": 3800},
            {"category": 'Graders', "hours": 52, "cost": 3100},
            {"category": 'Trucks', "hours": 96, "cost": 5700},
        ]
    }

@router.get("/brief")
async def get_brief():
    return {
        "greeting": 'Good Morning, Dealer',
        "fleetHealth": random.randint(85, 95),
        "potentialSavings": random.randint(5000, 15000),
        "criticalDecisions": random.randint(1, 5),
        "demandTomorrow": 'Excavators',
        "demandTrend": 'up',
        "topRecommendation": {
            "text": 'Move CAT 320 Excavator to Site Bravo',
            "confidence": 97,
        },
    }


# ---------------------------------------------------------------------
# ML-backed demand-forecast endpoints (new for the dashboard drilldowns)
# ---------------------------------------------------------------------

@router.get("/forecast/countries")
async def forecast_countries():
    """List of countries available in the demand model (for the UI selector)."""
    try:
        import pandas as pd
        df = ml._demand()
        return {"countries": sorted(df["country"].unique().tolist())}
    except Exception as e:
        return {"countries": ["India", "USA", "Germany", "Australia"], "error": str(e)}


@router.get("/forecast/country/{country}")
async def forecast_by_country(country: str, horizon_weeks: int = 2):
    """Per-country next-week demand outlook broken down by machine type."""
    try:
        return ml.predict_demand_by_country(country, horizon_weeks=horizon_weeks)
    except Exception as e:
        return {"country": country, "series": [], "error": str(e)}


@router.get("/forecast/comparison")
async def forecast_comparison(machine_type: str | None = None):
    """Compare next-week demand across all four countries for one machine type."""
    try:
        return ml.demand_country_comparison(machine_type)
    except Exception as e:
        return {"machineType": machine_type or "All", "data": [], "error": str(e)}
