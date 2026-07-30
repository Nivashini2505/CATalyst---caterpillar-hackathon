from fastapi import APIRouter
from sqlalchemy.future import select
from app.db.postgres import AsyncSessionLocal
from app.models.postgres.core import Asset, Site, Assignment
from pydantic import BaseModel
import hashlib

from app.ml import inference as ml

router = APIRouter()


def _stable_int(seed: str, lo: int, hi: int) -> int:
    """Deterministic value in [lo, hi] from a string seed (stable across calls,
    so the UI doesn't flicker on every refresh - replaces random.randint)."""
    h = int(hashlib.md5(str(seed).encode()).hexdigest(), 16)
    return lo + (h % (hi - lo + 1))

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
            rentalRemainingDays=_stable_int(aid, 1, 30),
            status=status,
            riskScore=int(hp["riskScore"]),
        ))
    return out


@router.get("", response_model=list[EquipmentUIResponse])
async def get_all_equipment():
    # Prefer the ML serving snapshot (richer fleet + real predicted health).
    # No DB dependency here, so the fleet list keeps working even if Postgres
    # is down during the demo.
    try:
        if ml.is_ready():
            return _from_snapshot()
    except Exception as e:
        print("[equipment] snapshot path failed, falling back to DB:", e)

    # Fallback: original DB-backed path. Open a session manually so a missing
    # DB doesn't break dependency resolution before we even get here.
    try:
        async with AsyncSessionLocal() as db:
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
                # Deterministic health from the maintenance model where possible,
                # else a stable value derived from the asset id (no randomness).
                try:
                    pm = ml.predict_maintenance(asset.asset_id)
                    health = int(pm["health"])
                    risk = int(pm["riskScore"])
                except Exception:
                    health = _stable_int(asset.asset_id + "h", 60, 100)
                    risk = 100 - health
                eq = EquipmentUIResponse(
                    id=asset.asset_id, name=asset.asset_name, model=asset.model or "Unknown",
                    category=asset.equipment_type or "Excavator",
                    image=asset.image_url or "https://images.unsplash.com/photo-1581094288338-2314dddb7a14?w=800&q=80",
                    site=site_name, operator="Unassigned", health=health,
                    engineHours=int(asset.total_engine_hours or 0),
                    idleHours=0 if ui_status == "working" else _stable_int(asset.asset_id + "i", 0, 20),
                    rentalRemainingDays=_stable_int(asset.asset_id, 1, 30), status=ui_status, riskScore=risk,
                )
                response_data.append(eq)
            return response_data
    except Exception as e:
        print("[equipment] DB fallback unavailable:", e)
        return []


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
