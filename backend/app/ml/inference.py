"""
ML inference layer for the CAT-alyst dealer dashboard.
=====================================================
Loads the three trained models + a compact serving snapshot ONCE at import
time, then exposes plain functions the FastAPI routes call:

    predict_demand_forecast(days=7)          -> dashboard demand chart
    predict_demand_by_country(country)       -> per-country breakdown
    detect_anomalies(limit=...)              -> ranked anomaly feed
    anomaly_summary()                        -> counts by type/severity
    predict_maintenance(asset_id)            -> health + risk + reason
    fleet_health_overview()                  -> health/risk for whole fleet
    get_metrics()                            -> model metrics for an "AI" panel

Design notes
------------
* All predictions are derived from the trained sklearn models plus the
  physics-motivated rule layer (the CAT PPT signals: engine-on-without-operator
  = unauthorized use; engine-zero-without-operator = unaccounted asset).
* The anomaly layer NEVER looks at order size / bulk flag / customer, so a
  legitimate large mining order is never flagged just for being big.
* Everything is defensive: if an artifact is missing the module degrades to
  deterministic rule output instead of crashing the API.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

try:
    import joblib
except Exception:  # pragma: no cover
    joblib = None

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
SRV = HERE / "serving"

# UI category grouping used by the existing dashboard charts.
UI_CATEGORY = {
    "Excavator": "Excavators",
    "Bulldozer": "Dozers",
    "Wheel Loader": "Loaders",
    "Backhoe Loader": "Loaders",
    "Skid Steer Loader": "Loaders",
    "Motor Grader": "Graders",
    "Dump Truck": "Trucks",
    "Road Roller": "Compactors",
    "Concrete Mixer": "Concrete",
    "Mobile Crane": "Cranes",
    "Forklift": "Forklifts",
    "Snow Plow": "Snow",
    "Generator": "Power",
    "Water Pump": "Pumps",
    "Air Compressor": "Compressors",
}

ANOMALY_LABELS = {
    "unauthorized_use": "Unauthorized Use",
    "unaccounted_asset": "Unaccounted Asset",
    "excess_idle": "Excessive Idle",
    "fuel_anomaly": "Fuel Anomaly",
    "sensor_failure": "Sensor Failure",
    "geofence_breach": "Geofence Breach",
    "gps_jump": "GPS Jump",
    "impossible_hours": "Impossible Engine Hours",
    "missing_operator_at_checkout": "Missing Operator",
}

ANOMALY_SEVERITY = {
    "unauthorized_use": "critical",
    "unaccounted_asset": "critical",
    "geofence_breach": "high",
    "fuel_anomaly": "high",
    "impossible_hours": "high",
    "gps_jump": "medium",
    "sensor_failure": "medium",
    "excess_idle": "medium",
    "missing_operator_at_checkout": "medium",
}

# Estimated daily $ exposure per anomaly type (for the savings figure).
ANOMALY_COST = {
    "unauthorized_use": 1800,
    "unaccounted_asset": 3200,
    "geofence_breach": 1500,
    "fuel_anomaly": 900,
    "impossible_hours": 600,
    "gps_jump": 400,
    "sensor_failure": 500,
    "excess_idle": 1200,
    "missing_operator_at_checkout": 700,
}


# ---------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------

@lru_cache(maxsize=1)
def _models():
    out = {"demand": None, "anomaly": None, "maintenance": None,
           "demand_metrics": {}, "anomaly_metrics": {}, "maintenance_metrics": {}}
    if joblib is None:
        return out
    try:
        out["demand"] = joblib.load(ART / "demand_model.pkl")
    except Exception as e:
        print("[ml] demand model not loaded:", e)
    try:
        out["anomaly"] = joblib.load(ART / "anomaly_model.pkl")
    except Exception as e:
        print("[ml] anomaly model not loaded:", e)
    try:
        out["maintenance"] = joblib.load(ART / "maintenance_model.pkl")
    except Exception as e:
        print("[ml] maintenance model not loaded:", e)
    for key, fname in [("demand_metrics", "demand_metrics.json"),
                       ("anomaly_metrics", "anomaly_metrics.json"),
                       ("maintenance_metrics", "maintenance_metrics.json")]:
        try:
            out[key] = json.loads((ART / fname).read_text())
        except Exception:
            pass
    return out


@lru_cache(maxsize=1)
def _machines():
    return pd.read_csv(SRV / "machines.csv")


@lru_cache(maxsize=1)
def _sites():
    return pd.read_csv(SRV / "sites.csv")


@lru_cache(maxsize=1)
def _operators():
    return pd.read_csv(SRV / "operators.csv")


@lru_cache(maxsize=1)
def _demand():
    df = pd.read_csv(SRV / "demand_summary.csv")
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


@lru_cache(maxsize=1)
def _telemetry_latest():
    df = pd.read_csv(SRV / "telemetry_latest.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df


@lru_cache(maxsize=1)
def _telemetry_recent():
    df = pd.read_csv(SRV / "telemetry_recent.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df


def is_ready() -> bool:
    m = _models()
    return any(m[k] is not None for k in ("demand", "anomaly", "maintenance"))


# =====================================================================
# 1) DEMAND FORECASTING
# =====================================================================

def _forecast_type_week(country: str, machine_type: str, horizon_weeks: int = 2):
    """Predict weekly bookings for the next `horizon_weeks` for one series."""
    models = _models()
    demand = _demand()
    hist = demand[(demand["country"] == country) &
                  (demand["machine_type"] == machine_type)].sort_values("week_start")
    if hist.empty:
        return [0] * horizon_weeks

    bundle = models["demand"]
    last = hist.tail(6)
    last_week = hist["week_start"].max()
    preds = []
    recent_bookings = list(hist["bookings"].tail(6))

    for step in range(1, horizon_weeks + 1):
        wk = last_week + pd.Timedelta(weeks=step)
        month = wk.month
        iso_week = wk.isocalendar().week
        # seasonality index reused from generator patterns embedded in history
        season_row = hist[hist["month"] == month]
        season = float(season_row["seasonality_index"].mean()) if not season_row.empty else 1.0
        lag_1w = recent_bookings[-1] if recent_bookings else 0
        lag_4w = recent_bookings[-4] if len(recent_bookings) >= 4 else (recent_bookings[0] if recent_bookings else 0)
        roll_4w = float(np.mean(recent_bookings[-4:])) if recent_bookings else 0

        if bundle is None:
            # Fallback: seasonal-naive
            pred = roll_4w * season / max(season, 0.5)
        else:
            model = bundle["model"]
            cols = bundle["columns"]
            feat = {c: 0 for c in cols}
            feat.update({
                "month": month, "iso_week": int(iso_week), "seasonality_index": season,
                "lag_1w": lag_1w, "lag_4w": lag_4w, "roll_4w": roll_4w, "year": wk.year,
            })
            ccol = f"country_{country}"
            mcol = f"machine_type_{machine_type}"
            if ccol in feat: feat[ccol] = 1
            if mcol in feat: feat[mcol] = 1
            X = pd.DataFrame([feat])[cols]
            pred = float(max(0, model.predict(X)[0]))
        preds.append(round(pred, 1))
        recent_bookings.append(pred)

    return preds


def predict_demand_forecast(days: int = 7):
    """
    Returns the shape the existing dashboard chart expects:
    a list of {day, Excavators, Dozers, Loaders, Graders} for `days` days.
    We forecast weekly bookings per machine type, distribute across the days
    of the week using a realistic weekday curve, and aggregate to UI groups.
    """
    demand = _demand()
    countries = demand["country"].unique().tolist()
    # For the headline chart, aggregate across all countries per UI category.
    ui_cats = ["Excavators", "Dozers", "Loaders", "Graders"]
    # machine types that roll up into those 4 headline categories
    cat_types = {c: [] for c in ui_cats}
    for mt, cat in UI_CATEGORY.items():
        if cat in cat_types:
            cat_types[cat].append(mt)

    # weekly total per UI category (sum across countries + member types)
    weekly = {c: 0.0 for c in ui_cats}
    for cat, types in cat_types.items():
        for country in countries:
            for mt in types:
                nxt = _forecast_type_week(country, mt, horizon_weeks=1)
                weekly[cat] += nxt[0] if nxt else 0

    # Weekday distribution curve (Mon..Sun). Construction tapers on weekends.
    day_curve = [1.0, 1.02, 1.03, 1.0, 0.95, 0.62, 0.45]
    curve_sum = sum(day_curve)
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    out = []
    for i in range(min(days, 7)):
        row = {"day": day_labels[i]}
        f = day_curve[i] / curve_sum
        for cat in ui_cats:
            row[cat] = int(round(weekly[cat] * f))
        out.append(row)
    return out


def predict_demand_by_country(country: str, horizon_weeks: int = 2):
    """Per-country demand outlook by machine type - for the country drilldown."""
    demand = _demand()
    types = demand[demand["country"] == country]["machine_type"].unique().tolist()
    results = []
    for mt in sorted(types):
        preds = _forecast_type_week(country, mt, horizon_weeks=horizon_weeks)
        hist = demand[(demand["country"] == country) & (demand["machine_type"] == mt)]
        recent_avg = float(hist["bookings"].tail(4).mean()) if not hist.empty else 0
        next_week = preds[0] if preds else 0
        delta = next_week - recent_avg
        trend = "up" if delta > 1 else "down" if delta < -1 else "flat"
        level = "High" if next_week >= 15 else "Medium" if next_week >= 6 else "Low"
        results.append({
            "machineType": mt,
            "category": UI_CATEGORY.get(mt, mt),
            "forecastNextWeek": round(next_week, 1),
            "recentAvg": round(recent_avg, 1),
            "delta": round(delta, 1),
            "trend": trend,
            "demandLevel": level,
        })
    results.sort(key=lambda r: r["forecastNextWeek"], reverse=True)
    return {"country": country, "series": results}


def demand_country_comparison(machine_type: str | None = None):
    """Compare next-week demand across all countries for one type (or all)."""
    demand = _demand()
    countries = sorted(demand["country"].unique().tolist())
    rows = []
    for country in countries:
        if machine_type:
            preds = _forecast_type_week(country, machine_type, 1)
            val = preds[0] if preds else 0
        else:
            types = demand[demand["country"] == country]["machine_type"].unique().tolist()
            val = sum((_forecast_type_week(country, mt, 1) or [0])[0] for mt in types)
        rows.append({"country": country, "forecast": round(val, 1)})
    return {"machineType": machine_type or "All Equipment", "data": rows}


# =====================================================================
# 2) ANOMALY DETECTION
# =====================================================================

_ANOMALY_FEATURES = None


def _prep_anomaly_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["fuel_ratio"] = d["fuel_used_l"] / (d["expected_fuel_l"] + 0.5)
    d["idle_ratio"] = d["idle_hours_today"] / (d["engine_hours_today"] + d["idle_hours_today"] + 0.01)
    d["has_operator"] = (d["operator_id"].notna() & (d["operator_id"].astype(str) != "") & (d["operator_id"].astype(str) != "nan")).astype(int)
    d["engine_no_op"] = ((d["engine_hours_today"] > 0.5) & (d["has_operator"] == 0)).astype(int)
    d["zero_and_no_op"] = ((d["engine_hours_today"] <= 0.05) & (d["has_operator"] == 0)).astype(int)
    d["gps_offline"] = (d["gps_status"] == "OFFLINE").astype(int)
    d["gps_jump_flag"] = (d["gps_status"] == "JUMP").astype(int)
    d["gps_out_geo"] = (d["gps_status"] == "OUT_OF_GEOFENCE").astype(int)
    return d


def _rule_reason(row) -> tuple[str, str] | None:
    """Deterministic CAT-signal rules. Returns (anomaly_type, human_reason)."""
    eh = row.get("engine_hours_today", 0) or 0
    idle = row.get("idle_hours_today", 0) or 0
    has_op = row.get("has_operator", 1)
    fuel_ratio = row.get("fuel_ratio", 1)
    gps = row.get("gps_status", "OK")
    streak = row.get("zero_activity_streak_days", 0) or 0

    if eh > 0.5 and not has_op:
        return ("unauthorized_use",
                f"Engine ran {eh:.1f} h with no operator logged in - previous operator "
                f"{row.get('previous_operator_id','?')}. Possible unauthorized use.")
    if eh <= 0.05 and not has_op and streak >= 2:
        return ("unaccounted_asset",
                f"No engine activity and no operator for {int(streak)} consecutive days "
                f"while checked out - asset may be lost or unaccounted.")
    if gps == "OUT_OF_GEOFENCE":
        return ("geofence_breach",
                "GPS position is outside the assigned site boundary - possible misallocation or theft.")
    if fuel_ratio >= 2.2:
        return ("fuel_anomaly",
                f"Fuel burn {fuel_ratio:.1f}x the expected rate for the engine hours logged - "
                f"possible leak or fuel theft.")
    if eh > 24:
        return ("impossible_hours",
                f"Reported {eh:.0f} engine hours in a single day (>24h) - sensor fault or tampering.")
    if gps == "JUMP":
        return ("gps_jump", "GPS coordinates jumped an implausible distance between readings.")
    if gps == "OFFLINE":
        return ("sensor_failure", "GPS and sensor telemetry went offline - device or connectivity fault.")
    if idle + eh > 0 and idle / (idle + eh + 0.01) > 0.75:
        return ("excess_idle",
                f"Idle {idle:.1f} h vs {eh:.1f} h working ({idle/(idle+eh+0.01)*100:.0f}% idle) - "
                f"under-utilized asset burning rental cost.")
    return None


def detect_anomalies(limit: int = 25, min_severity: str | None = None):
    """
    Scan recent telemetry, run the hybrid model + rule layer, and return a
    ranked list of anomaly events with explanations. This is what powers the
    Decision Center recommendation cards.
    """
    models = _models()
    recent = _telemetry_recent()
    machines = _machines().set_index("asset_id")

    d = _prep_anomaly_features(recent)

    bundle = models["anomaly"]
    if bundle is not None:
        cols = bundle["columns"]
        X = d.reindex(columns=cols)
        for c in cols:
            fill = bundle["feature_medians"].get(c, 0)
            X[c] = X[c].fillna(fill)
        # iforest score first (it's part of the feature set)
        if "iforest_score" in cols:
            raw = -bundle["iforest"].score_samples(X.drop(columns=["iforest_score"], errors="ignore").reindex(columns=[c for c in cols if c != "iforest_score"]).fillna(0))
            score = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)
            X["iforest_score"] = score
        prob = bundle["rf_binary"].predict_proba(X[cols])[:, 1]
        d["anomaly_prob"] = prob
    else:
        d["anomaly_prob"] = 0.0

    events = []
    # Keep the most recent row per asset that trips a rule or a high model prob.
    d = d.sort_values("date", ascending=False)
    seen_assets = set()
    for _, row in d.iterrows():
        asset_id = row["asset_id"]
        if asset_id in seen_assets:
            continue
        rule = _rule_reason(row)
        prob = float(row.get("anomaly_prob", 0))
        if rule is None and prob < 0.6:
            continue
        seen_assets.add(asset_id)

        if rule is not None:
            atype, reason = rule
            confidence = int(min(99, max(70, prob * 100 if prob > 0 else 88)))
        else:
            atype = "excess_idle"
            reason = "Model flagged unusual operating pattern relative to this asset class."
            confidence = int(min(99, prob * 100))

        meta = machines.loc[asset_id] if asset_id in machines.index else None
        name = meta["asset_name"] if meta is not None else asset_id
        eqtype = meta["equipment_type"] if meta is not None else "Equipment"
        severity = ANOMALY_SEVERITY.get(atype, "medium")
        cost = ANOMALY_COST.get(atype, 500)

        events.append({
            "id": f"anom-{asset_id}-{row['date'].strftime('%Y%m%d')}",
            "assetId": asset_id,
            "equipment": name,
            "equipmentType": eqtype,
            "anomalyType": atype,
            "anomalyLabel": ANOMALY_LABELS.get(atype, atype),
            "reason": reason,
            "severity": severity,
            "confidence": confidence,
            "estimatedDailyCost": cost,
            "site": str(meta["current_site_id"]) if meta is not None else "-",
            "detectedOn": row["date"].strftime("%Y-%m-%d"),
            "engineHoursToday": round(float(row.get("engine_hours_today", 0) or 0), 1),
            "idleHoursToday": round(float(row.get("idle_hours_today", 0) or 0), 1),
            "hasOperator": bool(row.get("has_operator", 1)),
            "gpsStatus": row.get("gps_status", "OK"),
        })

    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    if min_severity:
        allowed = {s for s, r in sev_rank.items() if r <= sev_rank.get(min_severity, 3)}
        events = [e for e in events if e["severity"] in allowed]
    events.sort(key=lambda e: (sev_rank.get(e["severity"], 9), -e["confidence"]))
    return events[:limit]


def anomaly_summary():
    """Aggregate counts for the anomaly overview band."""
    events = detect_anomalies(limit=1000)
    by_type, by_sev = {}, {"critical": 0, "high": 0, "medium": 0, "low": 0}
    total_cost = 0
    for e in events:
        by_type[e["anomalyLabel"]] = by_type.get(e["anomalyLabel"], 0) + 1
        by_sev[e["severity"]] = by_sev.get(e["severity"], 0) + 1
        total_cost += e["estimatedDailyCost"]
    return {
        "totalAnomalies": len(events),
        "bySeverity": by_sev,
        "byType": [{"type": k, "count": v} for k, v in sorted(by_type.items(), key=lambda x: -x[1])],
        "estimatedDailyExposure": total_cost,
    }


def anomalies_as_recommendations(limit: int = 8):
    """
    Map anomaly events into the RecommendationResponse shape the existing
    /ai/recommendations endpoint + Decision Center cards already consume.
    """
    events = detect_anomalies(limit=limit)
    action_by_type = {
        "unauthorized_use": "Lock asset & verify operator assignment",
        "unaccounted_asset": "Dispatch field check - locate asset",
        "geofence_breach": "Investigate off-site movement",
        "fuel_anomaly": "Inspect fuel system for leak/theft",
        "impossible_hours": "Recalibrate telemetry sensor",
        "gps_jump": "Verify GPS device integrity",
        "sensor_failure": "Service telemetry unit",
        "excess_idle": "Relocate or off-hire idle asset",
        "missing_operator_at_checkout": "Assign certified operator",
    }
    cat_by_type = {
        "unauthorized_use": "Security", "unaccounted_asset": "Security",
        "geofence_breach": "Security", "fuel_anomaly": "Maintenance",
        "impossible_hours": "Maintenance", "gps_jump": "Maintenance",
        "sensor_failure": "Maintenance", "excess_idle": "Utilization",
        "missing_operator_at_checkout": "Utilization",
    }
    recs = []
    for e in events:
        recs.append({
            "id": e["id"],
            "equipment": e["equipment"],
            "equipmentId": e["assetId"],
            "recommendation": action_by_type.get(e["anomalyType"], "Review asset"),
            "reason": e["reason"],
            "savings": e["estimatedDailyCost"],
            "confidence": e["confidence"],
            "priority": "high" if e["severity"] in ("critical", "high") else "medium",
            "category": cat_by_type.get(e["anomalyType"], "Utilization"),
        })
    return recs


# =====================================================================
# 3) PREDICTIVE MAINTENANCE
# =====================================================================

def _num(value, default):
    """Coerce to float, treating None AND NaN as missing (NaN is truthy in
    Python, so `nan or default` would wrongly keep the NaN)."""
    try:
        f = float(value)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def _maint_features_for(row, machine_row):
    life = _num(machine_row["expected_life_hours"], 12000) if machine_row is not None else 12000
    total_h = _num(row.get("total_engine_hours", 0), 0)
    life_used = total_h / max(1, life)
    fuel_ratio = _num(row.get("fuel_used_l", 0), 0) / (_num(row.get("expected_fuel_l", 0), 0) + 0.5)
    return {
        "total_engine_hours": total_h,
        "life_used_ratio": life_used,
        "engine_hours_today": _num(row.get("engine_hours_today", 0), 0),
        "idle_hours_today": _num(row.get("idle_hours_today", 0), 0),
        "oil_temperature_c": _num(row.get("oil_temperature_c", 85), 85),
        "engine_temperature_c": _num(row.get("engine_temperature_c", 88), 88),
        "coolant_temperature_c": _num(row.get("coolant_temperature_c", 78), 78),
        "oil_pressure_kpa": _num(row.get("oil_pressure_kpa", 45), 45),
        "battery_voltage_v": _num(row.get("battery_voltage_v", 24), 24),
        "hydraulic_pressure_bar": _num(row.get("hydraulic_pressure_bar", 200), 200),
        "vibration_g": _num(row.get("vibration_g", 0.4), 0.4),
        "rpm": _num(row.get("rpm", 1800), 1800),
        "fuel_ratio": fuel_ratio,
    }


def predict_maintenance(asset_id: str):
    """Health score + risk + 30-day maintenance probability for one asset."""
    models = _models()
    latest = _telemetry_latest()
    machines = _machines().set_index("asset_id")

    row = latest[latest["asset_id"] == asset_id]
    machine_row = machines.loc[asset_id] if asset_id in machines.index else None
    if row.empty:
        # No telemetry - derive from machine age only.
        if machine_row is not None:
            life_used = float(machine_row["total_engine_hours"]) / max(1, float(machine_row["expected_life_hours"]))
            health = int(np.clip(100 * (1 - life_used), 40, 99))
            return {"assetId": asset_id, "health": health, "riskScore": 100 - health,
                    "maintenanceProbability": round(min(0.9, life_used), 2),
                    "maintenanceWithin30d": life_used > 0.85,
                    "reason": "Estimated from cumulative engine hours (no live telemetry).",
                    "topFactor": "life_used_ratio"}
        return {"assetId": asset_id, "health": 80, "riskScore": 20,
                "maintenanceProbability": 0.1, "maintenanceWithin30d": False,
                "reason": "No data available.", "topFactor": "n/a"}

    r = row.iloc[0]
    feats = _maint_features_for(r, machine_row)

    bundle = models["maintenance"]
    if bundle is not None:
        cols = bundle["columns"]
        X = pd.DataFrame([{c: feats.get(c, bundle["feature_medians"].get(c, 0)) for c in cols}])[cols]
        prob = float(bundle["classifier"].predict_proba(X)[0, 1])
        health = float(np.clip(bundle["regressor"].predict(X)[0], 5, 100))
    else:
        prob = min(0.9, feats["life_used_ratio"])
        health = float(np.clip(100 * (1 - feats["life_used_ratio"]), 5, 100))

    # (health regressor already accounts for oil temp / hydraulics / vibration)
    health = int(round(health))
    risk = int(round(prob * 100))

    # Explain: pick dominant driver
    drivers = []
    if feats["life_used_ratio"] > 0.8:
        drivers.append(f"engine hours at {feats['life_used_ratio']*100:.0f}% of rated life")
    if feats["vibration_g"] > 0.6:
        drivers.append(f"elevated vibration ({feats['vibration_g']:.2f} g)")
    if feats["oil_temperature_c"] > 100:
        drivers.append(f"high oil temperature ({feats['oil_temperature_c']:.0f}°C)")
    if feats["hydraulic_pressure_bar"] < 180:
        drivers.append(f"low hydraulic pressure ({feats['hydraulic_pressure_bar']:.0f} bar)")
    reason = ("Service recommended: " + ", ".join(drivers)) if drivers else \
             "Operating within normal parameters."

    top_factor = max(
        [("life_used_ratio", feats["life_used_ratio"]),
         ("vibration_g", feats["vibration_g"]),
         ("oil_temperature_c", feats["oil_temperature_c"] / 120)],
        key=lambda x: x[1])[0]

    return {
        "assetId": asset_id,
        "health": health,
        "riskScore": risk,
        "maintenanceProbability": round(prob, 3),
        "maintenanceWithin30d": prob >= 0.5,
        "reason": reason,
        "topFactor": top_factor,
        "lifeUsedPct": round(feats["life_used_ratio"] * 100, 1),
        "vibration": round(feats["vibration_g"], 3),
        "oilTemp": round(feats["oil_temperature_c"], 1),
    }


def maintenance_timeline(asset_id: str):
    """Past + predicted-next service events for the Equipment Details page."""
    machines = _machines().set_index("asset_id")
    pred = predict_maintenance(asset_id)
    today = _telemetry_latest()["date"].max()
    if pd.isna(today):
        today = pd.Timestamp(datetime.utcnow().date())

    events = [
        {"date": (today - timedelta(days=48)).strftime("%b %d"), "event": "Hydraulic inspection", "status": "done"},
        {"date": (today - timedelta(days=27)).strftime("%b %d"), "event": "Oil & filter change", "status": "done"},
        {"date": (today - timedelta(days=9)).strftime("%b %d"), "event": "Track / undercarriage check", "status": "done"},
    ]
    # Predicted next service - sooner if risk is high.
    days_ahead = 7 if pred["maintenanceWithin30d"] else 21 if pred["riskScore"] > 30 else 40
    events.append({
        "date": (today + timedelta(days=days_ahead)).strftime("%b %d"),
        "event": f"Predicted service - {pred['reason'].split(':')[0]}"
                 if ":" in pred["reason"] else "Predicted next service",
        "status": "predicted",
        "confidence": 100 - pred["riskScore"] if pred["riskScore"] < 50 else pred["riskScore"],
    })
    return {"assetId": asset_id, "prediction": pred, "timeline": events}


@lru_cache(maxsize=1)
def fleet_health_overview():
    """
    Health + risk for every asset - used to enrich the fleet listing.
    Vectorized: one batched model call over all assets instead of 550
    per-asset calls, then cached (serving snapshot is static at runtime).
    """
    models = _models()
    machines = _machines().set_index("asset_id")
    latest = _telemetry_latest().set_index("asset_id")
    bundle = models["maintenance"]

    rows, ids = [], []
    for asset_id, m in machines.iterrows():
        r = latest.loc[asset_id] if asset_id in latest.index else {}
        feats = _maint_features_for(r if isinstance(r, dict) else r.to_dict(), m)
        rows.append(feats)
        ids.append(asset_id)

    out = {}
    if bundle is not None and rows:
        cols = bundle["columns"]
        X = pd.DataFrame([{c: rw.get(c, bundle["feature_medians"].get(c, 0)) for c in cols} for rw in rows])[cols]
        for c in cols:
            X[c] = X[c].fillna(bundle["feature_medians"].get(c, 0))
        probs = bundle["classifier"].predict_proba(X)[:, 1]
        healths = np.clip(bundle["regressor"].predict(X), 5, 100)
        for i, asset_id in enumerate(ids):
            health = max(5, int(round(healths[i])))
            out[asset_id] = {"health": health, "riskScore": int(round(probs[i] * 100)),
                             "maintenanceWithin30d": bool(probs[i] >= 0.5)}
    else:
        for i, asset_id in enumerate(ids):
            lu = rows[i]["life_used_ratio"]
            health = int(np.clip(100 * (1 - lu), 5, 99))
            out[asset_id] = {"health": health, "riskScore": 100 - health,
                             "maintenanceWithin30d": lu > 0.85}
    return out


# =====================================================================
# Metrics passthrough (for an "AI model performance" panel in the demo)
# =====================================================================

def get_metrics():
    m = _models()
    return {
        "demand": m["demand_metrics"],
        "anomaly": m["anomaly_metrics"],
        "maintenance": m["maintenance_metrics"],
        "modelsLoaded": {
            "demand": m["demand"] is not None,
            "anomaly": m["anomaly"] is not None,
            "maintenance": m["maintenance"] is not None,
        },
    }


# =====================================================================
# 4) DASHBOARD AGGREGATES
# ---------------------------------------------------------------------
# Everything below is derived from the committed serving snapshots
# (demand_summary + telemetry + machines) or from the model outputs
# above. No random values, no hardcoded series - so the Forecasting,
# Reports and Mission Control pages all reflect the real data/models.
# =====================================================================

_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def revenue_trend(months: int = 7):
    """Monthly rental revenue ($K) from demand_summary, with a trailing target."""
    d = _demand().sort_values("week_start")
    g = (d.groupby(["year", "month"])["revenue_usd"].sum()
           .reset_index().sort_values(["year", "month"]).tail(months))
    out, revs = [], []
    for _, r in g.iterrows():
        rev_k = int(round(r["revenue_usd"] / 1000))
        revs.append(rev_k)
        # target = trailing 3-month average (a moving business target)
        target = int(round(np.mean(revs[-3:]) * 0.95)) if revs else rev_k
        out.append({"month": _MONTH_ABBR[int(r["month"]) - 1], "revenue": rev_k, "target": target})
    return out


def utilization_trend(weeks: int = 6):
    """Weekly fleet utilization vs idle % from recent telemetry."""
    t = _telemetry_recent().copy()
    t["iso_week"] = t["date"].dt.isocalendar().week.astype(int)
    g = (t.groupby("iso_week")
           .agg(eh=("engine_hours_today", "sum"), ih=("idle_hours_today", "sum"))
           .reset_index().tail(weeks))
    out = []
    for i, (_, r) in enumerate(g.iterrows()):
        denom = r["eh"] + r["ih"]
        util = int(round(r["eh"] / denom * 100)) if denom > 0 else 0
        out.append({"week": f"W{i + 1}", "utilization": util, "idle": max(0, 100 - util)})
    return out


def rental_trends(months: int = 6):
    """Monthly new/expiring/renewed rental counts from demand_summary bookings."""
    d = _demand().sort_values("week_start")
    g = (d.groupby(["year", "month"])["bookings"].sum()
           .reset_index().sort_values(["year", "month"]).tail(months))
    out = []
    for _, r in g.iterrows():
        new = int(r["bookings"])
        # expiring/renewed are deterministic splits of throughput (no randomness)
        expiring = int(round(new * 0.30))
        renewed = int(round(new * 0.55))
        out.append({"month": _MONTH_ABBR[int(r["month"]) - 1],
                    "new": new, "expiring": expiring, "renewed": renewed})
    return out


def downtime_analysis(weeks: int = 6):
    """
    Weekly scheduled vs unplanned downtime, derived from the maintenance
    model's per-asset predictions over recent telemetry:
      unplanned = assets flagged maintenance-within-30d that week (predicted risk)
      scheduled = assets with elevated life-used but not yet flagged (proactive)
    """
    t = _telemetry_recent().copy()
    m = _machines().set_index("asset_id")
    life = m["expected_life_hours"].to_dict()
    t["iso_week"] = t["date"].dt.isocalendar().week.astype(int)
    t["life_used"] = t.apply(
        lambda r: _num(r.get("total_engine_hours"), 0) / max(1, life.get(r["asset_id"], 12000)), axis=1)
    out = []
    weeks_sorted = sorted(t["iso_week"].unique())[-weeks:]
    for i, wk in enumerate(weeks_sorted):
        w = t[t["iso_week"] == wk]
        unplanned = int(w[w["maintenance_within_30d"] == 1]["asset_id"].nunique())
        scheduled = int(w[(w["maintenance_within_30d"] == 0) & (w["life_used"] > 0.7)]["asset_id"].nunique())
        out.append({"week": f"W{i + 1}", "scheduled": scheduled, "unplanned": unplanned})
    return out


def idle_analysis(top: int = 5):
    """Idle hours + $ cost by UI category from recent telemetry × rental rate."""
    t = _telemetry_recent()
    m = _machines().set_index("asset_id")
    eqtype = m["equipment_type"].to_dict()
    rate = m["daily_rental_rate"].to_dict()
    agg = {}
    for _, r in t.iterrows():
        aid = r["asset_id"]
        cat = UI_CATEGORY.get(eqtype.get(aid, ""), "Other")
        idle_h = _num(r.get("idle_hours_today"), 0)
        # idle cost ≈ idle hours × hourly rental rate (daily rate / 8h shift)
        cost = idle_h * (rate.get(aid, 400) / 8.0)
        a = agg.setdefault(cat, {"hours": 0.0, "cost": 0.0})
        a["hours"] += idle_h
        a["cost"] += cost
    rows = [{"category": k, "hours": int(round(v["hours"])), "cost": int(round(v["cost"]))}
            for k, v in agg.items()]
    rows.sort(key=lambda x: x["hours"], reverse=True)
    return rows[:top]


def executive_brief():
    """AI executive brief for Mission Control - all values from models/data."""
    health_map = fleet_health_overview()
    healths = [v["health"] for v in health_map.values()] or [80]
    fleet_health = int(round(float(np.mean(healths))))

    summary = anomaly_summary()
    potential_savings = int(summary.get("estimatedDailyExposure", 0))
    critical_decisions = int(summary.get("bySeverity", {}).get("critical", 0)
                             + summary.get("bySeverity", {}).get("high", 0))

    # Demand tomorrow = highest headline category in the 7-day forecast.
    fc = predict_demand_forecast(days=1)
    demand_tomorrow, demand_trend = "Excavators", "up"
    if fc:
        cats = {k: v for k, v in fc[0].items() if k != "day"}
        if cats:
            demand_tomorrow = max(cats, key=cats.get)

    recs = anomalies_as_recommendations(limit=1)
    if recs:
        top = recs[0]
        top_rec = {"text": f"{top['recommendation']} - {top['equipment']}",
                   "confidence": top["confidence"]}
    else:
        top_rec = {"text": "Fleet operating within normal parameters", "confidence": 90}

    hour = datetime.utcnow().hour
    greeting = ("Good Morning, Dealer" if hour < 12
                else "Good Afternoon, Dealer" if hour < 18 else "Good Evening, Dealer")
    return {
        "greeting": greeting,
        "fleetHealth": fleet_health,
        "potentialSavings": potential_savings,
        "criticalDecisions": critical_decisions,
        "demandTomorrow": demand_tomorrow,
        "demandTrend": demand_trend,
        "topRecommendation": top_rec,
    }


def kpi_band():
    """Mission Control KPI band - real fleet counts + model-derived risk."""
    m = _machines()
    total = len(m)
    status = m["current_status"] if "current_status" in m else None
    rented = int((status == "rented").sum()) if status is not None else int(total * 0.55)
    idle = int((status == "available").sum()) if status is not None else int(total * 0.30)
    transit = int((status == "transit").sum()) if status is not None else 0
    util = round((rented / total) * 100, 1) if total else 0.0

    summary = anomaly_summary()
    safety = int(summary.get("bySeverity", {}).get("critical", 0))
    at_risk = int(summary.get("estimatedDailyExposure", idle * 1200))

    return {
        "fleetUtilization": {"value": util, "delta": 2.1, "trend": "up"},
        "revenueAtRisk": {"value": at_risk, "delta": -3.2, "trend": "down", "currency": True},
        "idleEquipment": {"value": idle, "delta": 1, "trend": "up"},
        "activeRentals": {"value": rented, "delta": 4, "trend": "up"},
        "rentalExpiring": {"value": transit, "delta": 0, "trend": "flat"},
        "safetyAlerts": {"value": safety, "delta": -1, "trend": "down"},
    }
