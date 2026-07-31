from fastapi import APIRouter
from sqlalchemy.future import select
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal
from app.models.postgres.core import Asset, Site
from pydantic import BaseModel
import hashlib
import time

from app.ml import inference as ml

router = APIRouter()

# Rated life per type (for life-used-ratio on live DB assets).
_REAL_LIFE = {"Excavator": 12000, "Dozer": 15000, "Wheel Loader": 13000,
              "Backhoe Loader": 10000, "Motor Grader": 14000, "Dump Truck": 18000,
              "Compactor": 9000, "Scraper": 16000, "Skid Steer Loader": 9000}

_live_cache = {"ts": 0.0, "data": []}   # 30s TTL cache for the live DB fetch


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
    isLive: bool = False


# Map the detailed equipment_type to the coarse UI category the Fleet filter uses.
_UI_CATEGORY = {
    "Excavator": "Excavator", "Dozer": "Dozer", "Wheel Loader": "Loader",
    "Backhoe Loader": "Loader", "Skid Steer Loader": "Loader", "Motor Grader": "Grader",
    "Dump Truck": "Truck", "Compactor": "Compactor", "Scraper": "Truck",
}

_STATUS_MAP = {"rented": "working", "available": "idle", "maintenance": "maintenance", "transit": "transit"}


async def _fetch_live_db_assets():
    """
    Fetch the REAL assets from the team's shared Postgres (Supabase), map their
    latest telemetry into the maintenance model's feature schema, and return
    them with live ML-predicted health/risk. Cached 30s. Returns [] if the DB
    is unreachable so the dashboard never breaks.
    """
    now = time.time()
    if now - _live_cache["ts"] < 30 and _live_cache["data"]:
        return _live_cache["data"]
    try:
        async with AsyncSessionLocal() as db:
            assets = (await db.execute(text(
                "SELECT asset_id, asset_name, equipment_type, model, current_status, "
                "total_engine_hours, fuel_capacity FROM assets ORDER BY asset_id"))).mappings().all()
            # Latest telemetry row per asset in one query.
            tel_rows = (await db.execute(text(
                "SELECT DISTINCT ON (asset_id) asset_id, engine_temperature, coolant_temperature, "
                "hydraulic_oil_temperature, hydraulic_pressure, battery_voltage, engine_rpm, "
                "fuel_consumption_lph, idle_hours FROM telemetry ORDER BY asset_id, timestamp DESC"))).mappings().all()
            tel = {r["asset_id"]: r for r in tel_rows}

            out = []
            for a in assets:
                aid = a["asset_id"]
                t = tel.get(aid, {})
                life = _REAL_LIFE.get(a["equipment_type"], 12000)
                teh = float(a["total_engine_hours"] or 0)
                fuel_cap = float(a["fuel_capacity"] or 300)
                fuel_lph = float(t.get("fuel_consumption_lph") or 0)
                feats = {
                    "total_engine_hours": teh,
                    "life_used_ratio": teh / max(1, life),
                    "engine_hours_today": 6.0, "idle_hours_today": 2.0,
                    "oil_temperature_c": t.get("hydraulic_oil_temperature"),
                    "engine_temperature_c": t.get("engine_temperature"),
                    "coolant_temperature_c": t.get("coolant_temperature"),
                    "battery_voltage_v": t.get("battery_voltage"),
                    "hydraulic_pressure_bar": t.get("hydraulic_pressure"),
                    "rpm": t.get("engine_rpm"),
                    "fuel_ratio": fuel_lph / max(1.0, 0.15 * fuel_cap),
                }
                hp = ml.health_from_features(feats)
                status = _STATUS_MAP.get(a["current_status"], "idle")
                if hp["maintenanceWithin30d"] and hp["riskScore"] >= 60 and status != "maintenance":
                    status = "critical"
                out.append(EquipmentUIResponse(
                    id=aid, name=a["asset_name"], model=a["model"] or "-",
                    category=_UI_CATEGORY.get(a["equipment_type"], "Excavator"),
                    image=_image_for(a["equipment_type"]),
                    site="Live Fleet (DB)", operator="-",
                    health=hp["health"], engineHours=int(teh),
                    idleHours=int(float(t.get("idle_hours") or 0)) % 24,
                    rentalRemainingDays=_stable_int(aid, 1, 30),
                    status=status, riskScore=hp["riskScore"], isLive=True,
                ))
            _live_cache["ts"] = now
            _live_cache["data"] = out
            return out
    except Exception as e:
        print("[equipment] live DB fetch skipped:", e)
        return []


def _image_for(equipment_type: str) -> str:
    """
    A reliable, labelled equipment image. machines.csv carries a placeholder
    domain (images.catrental.com) that does not resolve, so we generate a
    clean CAT-themed card labelled with the equipment type instead. This
    always loads and clearly communicates what the machine is.
    """
    label = (equipment_type or "Equipment").replace(" ", "+")
    return f"https://placehold.co/600x400/1a1d21/ffcd11.png?text={label}"


def _from_snapshot():
    """
    Serve the full 550-asset fleet from the ML serving snapshot, enriched with
    real predicted health / risk / maintenance flags. The seeded Postgres DB
    only has a handful of assets, so for the dashboard we use the richer
    simulated fleet the models were trained on.
    """
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
            image=_image_for(m["equipment_type"]),
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
    # The 8 REAL assets from the team's shared DB (with live ML predictions)
    # are listed first, followed by the richer simulated fleet the models were
    # trained on. Both are enriched by the same maintenance model.
    live = await _fetch_live_db_assets()
    try:
        if ml.is_ready():
            return live + _from_snapshot()
    except Exception as e:
        print("[equipment] snapshot path failed, falling back to DB:", e)
    if live:
        return live

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
                    image=_image_for(asset.equipment_type),
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
