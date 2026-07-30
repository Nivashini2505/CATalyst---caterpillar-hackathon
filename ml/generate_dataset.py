"""
CATalyst — Synthetic dataset generator for demand forecasting and anomaly detection.

Produces CSVs under ml/data/:
    equipment.csv       fleet master
    sites.csv           site master (with region for weather join)
    operators.csv       operator master
    customers.csv       customer master (with segment + contract type)
    rentals.csv         historical rentals (with bulk-order labels)
    usage_logs.csv      per-day per-rental telemetry (with anomaly labels)
    weather.csv         daily weather per region
    demand_daily.csv    aggregated demand per (date, region, equipment_type)  -> forecasting target

Baked-in signals:
  - Seasonality per equipment type (snow removers in winter, concrete in dry season, etc.)
  - Weather-driven demand (heat waves -> generators, snow -> snow removers)
  - Bulk contract orders (mining / gov infrastructure) — labeled so anomaly model can ignore them
  - Injected anomalies at ~5% of usage days: idle spike, fuel mismatch, GPS loss,
    unauth operator, geofence breach, overdue return
"""

from __future__ import annotations
import csv
import math
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path

random.seed(42)  # reproducible

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = date(2023, 1, 1)
END_DATE = date(2025, 12, 31)
TOTAL_DAYS = (END_DATE - START_DATE).days + 1

# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

EQUIPMENT_TYPES = [
    # type, manufacturers, models, fuel_cap_L, base_engine_hrs, base_idle_hrs, base_fuel_L_per_hr
    ("Excavator",       ["Caterpillar", "Komatsu", "Volvo"],   ["320", "330", "PC200", "EC210"], 400, 8.0, 4.0, 18),
    ("Bulldozer",       ["Caterpillar", "Komatsu"],            ["D6", "D8", "D9", "D65"],        550, 7.5, 5.0, 22),
    ("Crane",           ["Liebherr", "Tadano", "Grove"],       ["LTM1050", "GT800", "TR250"],    600, 6.0, 6.0, 15),
    ("Grader",          ["Caterpillar", "Volvo"],              ["140M", "G940", "G780"],         350, 7.0, 5.0, 14),
    ("Loader",          ["Caterpillar", "Komatsu", "JCB"],     ["950", "WA380", "L120"],         450, 8.5, 4.5, 20),
    ("Dump_Truck",      ["Caterpillar", "Volvo"],              ["770", "A40G", "745"],           900, 9.0, 3.5, 30),
    ("Snow_Remover",    ["Caterpillar", "Vammas"],             ["PS360", "SR100"],               300, 6.0, 3.0, 12),
    ("Concrete_Mixer",  ["McNeilus", "Oshkosh"],               ["Bridgemaster", "S-Series"],     250, 5.0, 4.0, 10),
    ("Generator",       ["Cummins", "Caterpillar"],            ["C220D5", "XQ2000"],             500, 12.0, 2.0, 8),
    ("Compactor",       ["Caterpillar", "Bomag"],              ["CS56B", "BW213"],               280, 7.0, 5.0, 12),
    ("Drill_Rig",       ["Sandvik", "Atlas_Copco"],            ["DX800", "SmartRoc"],            400, 8.5, 4.0, 16),
]

REGIONS = [
    # region, climate_profile (winter_temp_c, summer_temp_c, snow_prob, rain_prob)
    ("Northeast_US",  (-4, 27, 0.35, 0.30)),
    ("Midwest_US",    (-8, 29, 0.40, 0.25)),
    ("Southeast_US",  (10, 32, 0.02, 0.40)),
    ("Southwest_US",  (8,  38, 0.01, 0.10)),
    ("West_Coast",    (9,  26, 0.05, 0.25)),
]

SITE_TYPES = [
    "construction_residential",
    "construction_commercial",
    "infrastructure_roads",
    "mining",
    "oil_gas",
]

CUSTOMER_SEGMENTS = [
    # segment, typical_qty_range, contract_prob, bulk_prob
    ("small_contractor",   (1, 2),  0.05, 0.00),
    ("mid_contractor",     (1, 4),  0.20, 0.02),
    ("enterprise_builder", (2, 8),  0.55, 0.10),
    ("mining_corp",        (5, 25), 0.90, 0.50),
    ("gov_infra",          (4, 20), 0.85, 0.35),
]

# ---------------------------------------------------------------------------
# Seasonality — multiplier by month (Jan=1 .. Dec=12) for each equipment type.
# Values are demand multipliers around a base of 1.0.
# ---------------------------------------------------------------------------
SEASONALITY = {
    "Excavator":      [0.55, 0.55, 0.90, 1.30, 1.45, 1.40, 1.30, 1.30, 1.35, 1.20, 0.80, 0.55],
    "Bulldozer":      [0.50, 0.55, 0.90, 1.35, 1.50, 1.40, 1.25, 1.25, 1.30, 1.20, 0.80, 0.55],
    "Crane":          [0.70, 0.75, 1.00, 1.20, 1.30, 1.25, 1.20, 1.20, 1.20, 1.10, 0.85, 0.70],
    "Grader":         [0.40, 0.45, 0.90, 1.40, 1.55, 1.45, 1.30, 1.30, 1.35, 1.20, 0.70, 0.45],
    "Loader":         [0.90, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.05, 1.05, 1.05, 1.00, 0.95],  # mining steady
    "Dump_Truck":     [0.90, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.05, 1.05, 1.05, 1.00, 0.95],
    "Snow_Remover":   [2.20, 1.90, 0.80, 0.20, 0.10, 0.10, 0.10, 0.10, 0.10, 0.30, 1.50, 2.30],
    "Concrete_Mixer": [0.50, 0.55, 0.95, 1.35, 1.50, 1.50, 1.40, 1.40, 1.35, 1.15, 0.80, 0.55],
    "Generator":      [0.90, 0.85, 0.85, 0.90, 1.10, 1.40, 1.60, 1.55, 1.30, 1.05, 0.95, 1.00],  # summer heat + storm
    "Compactor":      [0.45, 0.50, 0.95, 1.40, 1.55, 1.45, 1.30, 1.30, 1.35, 1.15, 0.75, 0.50],
    "Drill_Rig":      [0.95, 0.95, 1.00, 1.05, 1.05, 1.05, 1.00, 1.00, 1.00, 1.05, 1.00, 0.95],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def season_of(d: date) -> str:
    m = d.month
    if m in (12, 1, 2): return "winter"
    if m in (3, 4, 5):  return "spring"
    if m in (6, 7, 8):  return "summer"
    return "fall"


def temp_for(d: date, climate) -> float:
    """Sinusoidal daily temperature around region's summer/winter range."""
    winter_t, summer_t, _snow, _rain = climate
    day_of_year = d.timetuple().tm_yday
    # peak summer ~ day 200, peak winter ~ day 15
    phase = math.cos(2 * math.pi * (day_of_year - 200) / 365)  # 1 at summer, -1 at winter
    mean = (winter_t + summer_t) / 2
    amp = (summer_t - winter_t) / 2
    return round(mean + amp * phase + random.gauss(0, 2.5), 1)


def precipitation_for(d: date, climate) -> tuple[float, float]:
    """Return (rain_mm, snow_mm)."""
    _wt, _st, snow_prob, rain_prob = climate
    m = d.month
    is_cold = m in (11, 12, 1, 2, 3)
    snow = 0.0
    rain = 0.0
    if is_cold and random.random() < snow_prob:
        snow = round(random.uniform(2, 30), 1)
    if random.random() < rain_prob:
        rain = round(random.uniform(1, 40), 1)
    return rain, snow


# ---------------------------------------------------------------------------
# Build master tables
# ---------------------------------------------------------------------------

def build_equipment(target_units: int = 220):
    rows = []
    eid = 1000
    for _ in range(target_units):
        et_row = random.choice(EQUIPMENT_TYPES)
        et, mfgs, models, fuel_cap, base_eng, base_idle, base_fuel = et_row
        eid += 1
        rows.append({
            "equipment_id": f"EQX{eid}",
            "equipment_type": et,
            "manufacturer": random.choice(mfgs),
            "model": random.choice(models),
            "purchase_year": random.randint(2015, 2024),
            "fuel_capacity_liters": fuel_cap,
            "expected_engine_hours_per_day": base_eng,
            "expected_idle_hours_per_day": base_idle,
            "expected_fuel_per_engine_hour": base_fuel,
        })
    return rows


def build_sites(target_sites: int = 30):
    rows = []
    for i in range(target_sites):
        region, climate = random.choice(REGIONS)
        rows.append({
            "site_id": f"S{100+i:03d}",
            "site_name": f"{random.choice(['Alpha','Bravo','Delta','Echo','Foxtrot','Zulu','Nova','Ridge','Summit','Harbor'])}-{i:02d}",
            "region": region,
            "site_type": random.choice(SITE_TYPES),
            "latitude": round(random.uniform(25.0, 48.0), 5),
            "longitude": round(random.uniform(-124.0, -70.0), 5),
            "geofence_radius_m": random.choice([500, 750, 1000, 1500]),
        })
    return rows


def build_operators(target_ops: int = 60):
    rows = []
    for i in range(target_ops):
        rows.append({
            "operator_id": f"OP{200+i:03d}",
            "operator_name": f"Operator_{i:03d}",
            "license_number": f"LIC{random.randint(100000, 999999)}",
            "experience_years": random.randint(1, 25),
        })
    return rows


def build_customers(target_customers: int = 45):
    rows = []
    for i in range(target_customers):
        seg_row = random.choice(CUSTOMER_SEGMENTS)
        seg, qty_range, contract_prob, bulk_prob = seg_row
        rows.append({
            "customer_id": f"C{300+i:03d}",
            "customer_name": f"{seg.title().replace('_',' ')} {i:03d}",
            "segment": seg,
            "typical_order_min": qty_range[0],
            "typical_order_max": qty_range[1],
            "contract_probability": contract_prob,
            "bulk_probability": bulk_prob,
        })
    return rows


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

def build_weather():
    rows = []
    for region, climate in REGIONS:
        for d in daterange(START_DATE, END_DATE):
            rain, snow = precipitation_for(d, climate)
            rows.append({
                "date": d.isoformat(),
                "region": region,
                "temp_c": temp_for(d, climate),
                "precipitation_mm": rain,
                "snowfall_mm": snow,
                "season": season_of(d),
            })
    return rows


# ---------------------------------------------------------------------------
# Rentals + usage logs
# ---------------------------------------------------------------------------

def build_rentals_and_logs(equipment, sites, operators, customers):
    """Generate rentals with realistic seasonality + bulk contract events,
    then per-day usage logs with injected anomalies."""

    # index by lookups
    eq_by_type: dict[str, list] = {}
    for e in equipment:
        eq_by_type.setdefault(e["equipment_type"], []).append(e)

    site_by_id = {s["site_id"]: s for s in sites}
    all_regions = [r for r, _ in REGIONS]

    rentals = []
    usage_logs = []

    rental_seq = 5000
    log_seq = 0
    contract_seq = 700

    # For each day, roll a Poisson-ish number of new bookings, biased by seasonality
    for d in daterange(START_DATE, END_DATE):
        month_idx = d.month - 1

        # Base rate: ~6 new bookings/day, boosted by average seasonality across types
        for et, _mfg, _mdl, _fc, _be, _bi, _bf in EQUIPMENT_TYPES:
            season_mult = SEASONALITY[et][month_idx]
            # base new-bookings per (day, type) ~ 0.6 * seasonality + noise
            expected = 0.6 * season_mult
            n_new = 0
            # simple Poisson sample via successive uniforms
            L = math.exp(-expected)
            p = 1.0
            k = 0
            while True:
                p *= random.random()
                if p <= L:
                    break
                k += 1
            n_new = k

            for _ in range(n_new):
                customer = random.choice(customers)
                # bulk order roll
                is_bulk = random.random() < customer["bulk_probability"] and et in {
                    "Loader", "Dump_Truck", "Drill_Rig", "Excavator", "Bulldozer", "Compactor", "Grader"
                }
                has_contract = is_bulk or (random.random() < customer["contract_probability"])
                contract_id = None
                if has_contract:
                    contract_seq += 1
                    contract_id = f"CT{contract_seq}"

                qty = 1
                if is_bulk:
                    qty = random.randint(customer["typical_order_min"] + 3,
                                         customer["typical_order_max"] + 5)
                else:
                    qty = random.randint(customer["typical_order_min"],
                                         customer["typical_order_max"])

                site = random.choice(sites)
                # bias: mining customers prefer mining sites
                if customer["segment"] == "mining_corp":
                    mining_sites = [s for s in sites if s["site_type"] == "mining"]
                    if mining_sites:
                        site = random.choice(mining_sites)
                elif customer["segment"] == "gov_infra":
                    infra_sites = [s for s in sites if s["site_type"] == "infrastructure_roads"]
                    if infra_sites:
                        site = random.choice(infra_sites)

                # rental duration — bulk contracts run longer
                if is_bulk:
                    duration = random.randint(20, 60)
                elif has_contract:
                    duration = random.randint(10, 30)
                else:
                    duration = random.randint(3, 18)

                # allocate `qty` units of this type (or as many as fleet has)
                available_units = eq_by_type.get(et, [])
                if not available_units:
                    continue
                units_used = random.sample(
                    available_units,
                    k=min(qty, len(available_units))
                )

                for eq in units_used:
                    rental_seq += 1
                    rental_id = f"R{rental_seq}"
                    start = d
                    expected_end = start + timedelta(days=duration)
                    # overdue anomaly rolled at rental level (~4%)
                    overdue_days = 0
                    if random.random() < 0.04:
                        overdue_days = random.randint(3, 15)
                    actual_end = expected_end + timedelta(days=overdue_days)
                    if actual_end > END_DATE:
                        actual_end = END_DATE
                    status = "returned" if actual_end <= END_DATE else "active"
                    if overdue_days > 0 and status == "returned":
                        status = "overdue_returned"

                    # operator (rarely NULL — anomaly signal)
                    op_missing = random.random() < 0.03
                    operator = None if op_missing else random.choice(operators)

                    rentals.append({
                        "rental_id": rental_id,
                        "equipment_id": eq["equipment_id"],
                        "equipment_type": et,
                        "site_id": site["site_id"],
                        "region": site["region"],
                        "customer_id": customer["customer_id"],
                        "customer_segment": customer["segment"],
                        "operator_id": operator["operator_id"] if operator else "",
                        "rental_start_date": start.isoformat(),
                        "expected_return_date": expected_end.isoformat(),
                        "actual_return_date": actual_end.isoformat(),
                        "rental_days": (actual_end - start).days,
                        "quantity": 1,  # one row per unit, so quantity=1
                        "contract_id": contract_id or "",
                        "is_bulk_order": int(is_bulk),
                        "has_contract": int(has_contract),
                        "rental_status": status,
                        "overdue_days": overdue_days,
                    })

                    # Per-day usage logs across [start, actual_end]
                    day = start
                    log_end = actual_end
                    while day <= log_end and day <= END_DATE:
                        log_seq += 1
                        base_eng = eq["expected_engine_hours_per_day"]
                        base_idle = eq["expected_idle_hours_per_day"]
                        base_fuel_rate = eq["expected_fuel_per_engine_hour"]

                        # normal values with noise
                        engine_hrs = max(0.0, round(random.gauss(base_eng, 1.2), 2))
                        idle_hrs = max(0.0, round(random.gauss(base_idle, 1.0), 2))
                        # cap total at 24
                        if engine_hrs + idle_hrs > 24:
                            engine_hrs = round(engine_hrs * 24 / (engine_hrs + idle_hrs), 2)
                            idle_hrs = round(24 - engine_hrs, 2)
                        expected_fuel = engine_hrs * base_fuel_rate
                        fuel = max(0.0, round(random.gauss(expected_fuel, expected_fuel * 0.08), 2))
                        ping_count = random.randint(40, 90)
                        last_gap = round(random.uniform(0.05, 1.5), 2)
                        in_geofence = 1
                        lat = site["latitude"] + random.gauss(0, 0.002)
                        lon = site["longitude"] + random.gauss(0, 0.002)
                        active_operator = rentals[-1]["operator_id"]

                        # Inject anomalies (~5% of days)
                        is_anom = 0
                        anom_type = "none"
                        r = random.random()
                        if r < 0.010:  # idle spike
                            idle_hrs = round(random.uniform(19, 24), 2)
                            engine_hrs = round(random.uniform(0, 2), 2)
                            is_anom, anom_type = 1, "idle_spike"
                        elif r < 0.020:  # fuel mismatch (theft-like)
                            factor = random.choice([random.uniform(0.1, 0.3),
                                                    random.uniform(2.0, 4.0)])
                            fuel = round(expected_fuel * factor, 2)
                            is_anom, anom_type = 1, "fuel_mismatch"
                        elif r < 0.030:  # gps loss
                            ping_count = 0
                            last_gap = round(random.uniform(24, 72), 1)
                            is_anom, anom_type = 1, "gps_loss"
                        elif r < 0.038:  # unauth operator
                            active_operator = ""
                            is_anom, anom_type = 1, "unauth_operator"
                        elif r < 0.048:  # geofence breach
                            lat = site["latitude"] + random.uniform(0.05, 0.2) * random.choice([-1, 1])
                            lon = site["longitude"] + random.uniform(0.05, 0.2) * random.choice([-1, 1])
                            in_geofence = 0
                            is_anom, anom_type = 1, "geofence_breach"

                        # overdue flag on days past expected_end
                        overdue_flag = 1 if day > expected_end else 0
                        if overdue_flag and not is_anom:
                            is_anom, anom_type = 1, "overdue_usage"

                        usage_logs.append({
                            "log_id": f"L{log_seq}",
                            "log_date": day.isoformat(),
                            "rental_id": rental_id,
                            "equipment_id": eq["equipment_id"],
                            "equipment_type": et,
                            "site_id": site["site_id"],
                            "region": site["region"],
                            "operator_id": active_operator,
                            "engine_hours": engine_hrs,
                            "idle_hours": idle_hrs,
                            "fuel_consumed_liters": fuel,
                            "expected_fuel_liters": round(expected_fuel, 2),
                            "utilization_rate": round(engine_hrs / max(0.1, engine_hrs + idle_hrs), 3),
                            "gps_ping_count": ping_count,
                            "last_ping_gap_hours": last_gap,
                            "latitude": round(lat, 5),
                            "longitude": round(lon, 5),
                            "inside_geofence": in_geofence,
                            "overdue_flag": overdue_flag,
                            "is_bulk_order": int(is_bulk),
                            "customer_segment": customer["segment"],
                            "has_contract": int(has_contract),
                            "is_anomaly": is_anom,
                            "anomaly_type": anom_type,
                        })
                        day += timedelta(days=1)

    return rentals, usage_logs


# ---------------------------------------------------------------------------
# Aggregated daily demand — the forecasting target
# ---------------------------------------------------------------------------

def build_demand_daily(rentals):
    """For each (date, region, equipment_type) count active rentals + new bookings."""
    # index rentals for range scan
    by_key: dict[tuple, dict] = {}
    for r in rentals:
        start = date.fromisoformat(r["rental_start_date"])
        end = date.fromisoformat(r["actual_return_date"])
        d = start
        while d <= end:
            key = (d.isoformat(), r["region"], r["equipment_type"])
            slot = by_key.setdefault(key, {"units_active": 0, "new_bookings": 0, "bulk_units": 0})
            slot["units_active"] += 1
            if d == start:
                slot["new_bookings"] += 1
            if r["is_bulk_order"]:
                slot["bulk_units"] += 1
            d += timedelta(days=1)

    # fill zeros for missing combinations so the target has continuous series
    rows = []
    for d in daterange(START_DATE, END_DATE):
        d_iso = d.isoformat()
        for region, _ in REGIONS:
            for et, *_ in EQUIPMENT_TYPES:
                slot = by_key.get((d_iso, region, et), {"units_active": 0, "new_bookings": 0, "bulk_units": 0})
                rows.append({
                    "date": d_iso,
                    "region": region,
                    "equipment_type": et,
                    "units_active": slot["units_active"],
                    "new_bookings": slot["new_bookings"],
                    "bulk_units": slot["bulk_units"],
                    "month": d.month,
                    "day_of_week": d.weekday(),
                    "day_of_year": d.timetuple().tm_yday,
                    "season": season_of(d),
                    "is_weekend": int(d.weekday() >= 5),
                })
    return rows


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def write_csv(name: str, rows: list[dict]):
    path = OUT_DIR / name
    if not rows:
        path.write_text("")
        return path
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Generating dataset - {START_DATE} to {END_DATE} ({TOTAL_DAYS} days)")
    equipment = build_equipment()
    sites = build_sites()
    operators = build_operators()
    customers = build_customers()
    weather = build_weather()

    print(f"  equipment: {len(equipment)}")
    print(f"  sites:     {len(sites)}")
    print(f"  operators: {len(operators)}")
    print(f"  customers: {len(customers)}")
    print(f"  weather:   {len(weather)}")

    print("Simulating rentals + usage logs (this is the slow bit)...")
    rentals, usage_logs = build_rentals_and_logs(equipment, sites, operators, customers)
    print(f"  rentals:    {len(rentals)}")
    print(f"  usage_logs: {len(usage_logs)}")

    print("Aggregating daily demand...")
    demand = build_demand_daily(rentals)
    print(f"  demand rows: {len(demand)}")

    print("Writing CSVs...")
    # NOTE: usage_logs is ~1.27M rows (~192 MB) — too big for GitHub (100 MB
    # limit). We write the FULL file as `usage_logs_full.csv` (gitignored) and
    # then produce a stratified <20 MB `usage_logs.csv` that IS committed.
    for name, rows in [
        ("equipment.csv", equipment),
        ("sites.csv", sites),
        ("operators.csv", operators),
        ("customers.csv", customers),
        ("weather.csv", weather),
        ("rentals.csv", rentals),
        ("usage_logs_full.csv", usage_logs),
        ("demand_daily.csv", demand),
    ]:
        p = write_csv(name, rows)
        size_kb = os.path.getsize(p) / 1024
        print(f"  {name:20s} {len(rows):>8,} rows   {size_kb:>8,.1f} KB")

    # Produce the committable, GitHub-friendly reduced usage_logs.csv.
    print("Reducing usage_logs to a <20 MB committable sample...")
    try:
        from reduce_dataset import reduce_usage_logs
        reduce_usage_logs(OUT_DIR / "usage_logs_full.csv",
                          OUT_DIR / "usage_logs.csv",
                          target_mb=17.0, verbose=True)
    except Exception as e:  # pandas missing or any issue — don't fail generation
        print(f"  [warn] could not auto-reduce usage_logs.csv ({e}).")
        print(f"         Run manually: python reduce_dataset.py")

    # Quick summary — anomaly & bulk-order distribution
    anom = sum(1 for r in usage_logs if r["is_anomaly"])
    bulk = sum(1 for r in rentals if r["is_bulk_order"])
    print("\nSummary:")
    print(f"  usage_logs total:      {len(usage_logs):,}")
    print(f"  usage_logs anomalies:  {anom:,}  ({anom/max(1,len(usage_logs))*100:.2f}%)")
    print(f"  rentals total:         {len(rentals):,}")
    print(f"  bulk-order rentals:    {bulk:,}  ({bulk/max(1,len(rentals))*100:.2f}%)")
    print(f"\nAll CSVs written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
