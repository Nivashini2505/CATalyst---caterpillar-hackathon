"""
Build a compact 'serving snapshot' the FastAPI backend can load fast at
runtime, plus copy the trained model artifacts into the repo so the whole
thing is self-contained after a git pull.

Outputs -> CATalyst---caterpillar-hackathon/backend/app/ml/
  artifacts/*.pkl, *_metrics.json           (trained models)
  serving/machines.csv                       (550 assets, full)
  serving/demand_summary.csv                 (weekly demand history)
  serving/telemetry_latest.csv               (most-recent row per asset)
  serving/telemetry_recent.csv               (last 30 days, for anomaly feed)
  serving/sites.csv, customers.csv, operators.csv
"""

from __future__ import annotations
import shutil
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent          # backend/app/ml/training
DATA = HERE / "data"
ART = HERE / "artifacts"

# The ML module lives one level up (backend/app/ml). Serving snapshot +
# committed artifacts are written there so the FastAPI app loads them.
DEST = HERE.parent
DEST_ART = DEST / "artifacts"
DEST_SRV = DEST / "serving"
DEST_ART.mkdir(parents=True, exist_ok=True)
DEST_SRV.mkdir(parents=True, exist_ok=True)

print("Copying model artifacts...")
for f in ART.glob("*"):
    shutil.copy2(f, DEST_ART / f.name)
    print("  ", f.name)

print("Copying reference tables...")
for name in ["machines.csv", "sites.csv", "customers.csv", "operators.csv", "demand_summary.csv"]:
    shutil.copy2(DATA / name, DEST_SRV / name)
    print("  ", name)

print("Building telemetry snapshots...")
tel = pd.read_csv(DATA / "telemetry_daily.csv")
tel["date"] = pd.to_datetime(tel["date"])

# Latest row per asset (current fleet state)
latest = tel.sort_values("date").groupby("asset_id").tail(1)
latest.to_csv(DEST_SRV / "telemetry_latest.csv", index=False)
print(f"   telemetry_latest.csv  ({len(latest)} rows)")

# Last 45 days across the fleet (for the live anomaly feed)
cutoff = tel["date"].max() - pd.Timedelta(days=45)
recent = tel[tel["date"] >= cutoff]
recent.to_csv(DEST_SRV / "telemetry_recent.csv", index=False)
print(f"   telemetry_recent.csv  ({len(recent)} rows, since {cutoff.date()})")

print("\nDone. Serving snapshot written to", DEST)
