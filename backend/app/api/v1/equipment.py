from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.postgres import get_db
from app.models.postgres.core import Asset, Site, Assignment
from pydantic import BaseModel
import random

from app.ml import inference as ml

router = APIRouter()

# Schema for frontend
class EquipmentUIResponse(BaseModel):
    id: str
    name: str
    model: str
    category: str
    image: str
    site: str
    operator: str
    health: int
    engineHours: int
    idleHours: int
    rentalRemainingDays: int
    status: str
    riskScore: int


# Map the detailed equipment_type to the coarse UI category the Fleet filter uses.
_UI_CATEGORY = {
    "Excavator": "Excavator", "Bulldozer": "Dozer", "Wheel Loader": "Loader",
    "Backhoe Loader": "Loader", "Skid Steer Loader": "Loader", "Motor Grader": "Grader",
    "Dump Truck": "Truck", "Road Roller": "Compactor", "Concrete Mixer": "Compactor",
    "Mobile Crane": "Excavator", "Forklift": "Loader", "Snow Plow": "Truck",
    "Generator": "Truck", "Water Pump": "Truck", "Air Compressor": "Truck",
}

_STATUS_MAP = {"rented": "working", "available": "idle", "maintenance": "maintenance", "transit": "transit"}


def _from_snapshot():
    """
    Serve the full 550-asset fleet from the ML serving snapshot, enriched with
    real predicted health / risk / maintenance flags. The seeded Postgres DB
    only has a handful of assets, so for the dashboard we use the richer
    simulated fleet the models were trained on.
    """
    import pandas as pd
    machines = ml._machines()
    latest = ml._telemetry_latest().set_index("asset_id")
    sites = ml._sites().set_index("site_id")
    health_map = ml.fleet_health_overview()

    out = []
    for _, m in machines.iterrows():
        aid = m["asset_id"]
        hp = health_map.get(aid, {"health": 80, "riskScore": 20, "maintenanceWithin30d": False})
        # live-ish idle + status
        idle_hours = 0
        operator = "Unassigned"
        status = _STATUS_MAP.get(m["current_status"], "idle")
        if aid in latest.index:
            row = latest.loc[aid]
            idle_hours = int(round(float(row.get("idle_hours_today", 0) or 0)))
            op = row.get("operator_id", "")
            operator = str(op) if op and str(op) != "nan" else "Unassigned"
        if hp["maintenanceWithin30d"] and status not in ("maintenance",):
            status = "critical" if hp["riskScore"] >= 60 else status
        site_name = "Dealer Yard"
        if m["current_site_id"] in sites.index:
            site_name = sites.loc[m["current_site_id"]]["site_name"]

        out.append(EquipmentUIResponse(
            id=aid,
            name=m["asset_name"],
            model=m["model"],
            category=_UI_CATEGORY.get(m["equipment_type"], "Excavator"),
            image=m.get("image_url") or "https://images.unsplash.com/photo-1581094288338-2314dddb7a14?w=800&q=80",
            site=site_name,
            operator=operator,
            health=int(hp["health"]),
            engineHours=int(float(m.get("total_engine_hours", 0) or 0)),
            idleHours=idle_hours,
            rentalRemainingDays=random.randint(1, 30),
            status=status,
            riskScore=int(hp["riskScore"]),
        ))
    return out


@router.get("", response_model=list[EquipmentUIResponse])
async def get_all_equipment(db: AsyncSession = Depends(get_db)):
    # Prefer the ML serving snapshot (richer fleet + real predicted health).
    try:
        if ml.is_ready():
            return _from_snapshot()
    except Exception as e:
        print("[equipment] snapshot path failed, falling back to DB:", e)

    # Fallback: original DB-backed path.
    result = await db.execute(select(Asset))
    assets = result.scalars().all()
    response_data = []
    for asset in assets:
        site_name = "Dealer Yard"
        if asset.current_site_id:
            site_result = await db.execute(select(Site).where(Site.site_id == asset.current_site_id))
            site = site_result.scalar_one_or_none()
            if site:
                site_name = site.site_name
        ui_status = "idle"
        if asset.current_status == "rented":
            ui_status = "working"
        elif asset.current_status == "maintenance":
            ui_status = "maintenance"
        health = random.randint(60, 100)
        eq = EquipmentUIResponse(
            id=asset.asset_id, name=asset.asset_name, model=asset.model or "Unknown",
            category=asset.equipment_type or "Excavator",
            image=asset.image_url or "https://images.unsplash.com/photo-1581094288338-2314dddb7a14?w=800&q=80",
            site=site_name, operator="Unassigned", health=health,
            engineHours=int(asset.total_engine_hours or 0),
            idleHours=random.randint(0, 20) if ui_status != "working" else 0,
            rentalRemainingDays=random.randint(1, 30), status=ui_status, riskScore=100 - health,
        )
        response_data.append(eq)
    return response_data


@router.get("/{asset_id}/maintenance-forecast")
async def get_maintenance_forecast(asset_id: str):
    """
    Predictive-maintenance detail for one asset: health, 30-day risk, the
    dominant driver, and a past+predicted service timeline. Powers the
    Equipment Details maintenance panel.
    """
    try:
        return ml.maintenance_timeline(asset_id)
    except Exception as e:
        return {"assetId": asset_id, "error": str(e), "timeline": []}
