"""
Train predictive-maintenance models.

Two heads:
  - CLASSIFIER: RandomForest — will this asset need maintenance within 30 days?
                target = maintenance_within_30d  (label already engineered in
                the dataset by joining telemetry to maintenance_history).
  - REGRESSOR: GradientBoosting — continuous health score (100 - predicted
               probability of maintenance-needed scaled 0..100), which the
               dealer dashboard already renders on Fleet + Equipment Details.

Features: sensor-driven only (engine hours, oil/coolant/hydraulic pressures,
temperatures, vibration, battery voltage, fuel efficiency drift).
"""

from __future__ import annotations
import json, joblib
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report, mean_absolute_error

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ART = HERE / "artifacts"
ART.mkdir(exist_ok=True)

print("Loading telemetry_daily.csv + machines.csv...")
tel = pd.read_csv(DATA / "telemetry_daily.csv")
mach = pd.read_csv(DATA / "machines.csv")[["asset_id","expected_life_hours","equipment_type","purchase_year"]]

df = tel.merge(mach, on="asset_id", how="left")
df["life_used_ratio"] = df["total_engine_hours"] / df["expected_life_hours"].clip(lower=1)
df["fuel_ratio"] = df["fuel_used_l"] / (df["expected_fuel_l"] + 0.5)

FEATURES = [
    "total_engine_hours","life_used_ratio","engine_hours_today","idle_hours_today",
    "oil_temperature_c","engine_temperature_c","coolant_temperature_c",
    "oil_pressure_kpa","battery_voltage_v","hydraulic_pressure_bar",
    "vibration_g","rpm","fuel_ratio",
]
X = df[FEATURES].copy()
for c in X.columns:
    X[c] = X[c].fillna(X[c].median())
y_cls = df["maintenance_within_30d"].astype(int)
# Continuous health score (0..100). Calibrated so a fresh machine reads high
# (green on the dashboard) and health degrades with life used + sensor stress:
#   new  (life 0.1) -> ~95, mid (0.5) -> ~80, worn (1.0) -> ~58,
#   over-life (>1)  -> clamped, then extra penalties for hot oil / weak
#   hydraulics / heavy vibration / low battery.
lu = df["life_used_ratio"].clip(0, 1.3)
health_target = np.clip(
    98
    - 40 * lu
    - np.where(df["oil_temperature_c"].fillna(85) > 100, 12, 0)
    - np.where(df["hydraulic_pressure_bar"].fillna(200) < 180, 8, 0)
    - np.where(df["vibration_g"].fillna(0.4) > 0.7, 8, 0)
    - np.where(df["battery_voltage_v"].fillna(24) < 23.5, 5, 0),
    5, 99,
).round(1)

print(f"Rows: {len(df):,}   maintenance-within-30d rate: {y_cls.mean()*100:.2f}%")

# ---- Classifier ----
print("\nTraining maintenance classifier (30-day horizon)...")
X_train, X_test, yc_train, yc_test, yh_train, yh_test = train_test_split(
    X, y_cls, health_target, test_size=0.2, stratify=y_cls, random_state=42
)
clf = RandomForestClassifier(
    n_estimators=250, max_depth=16, min_samples_leaf=5,
    class_weight="balanced", n_jobs=-1, random_state=42
)
clf.fit(X_train, yc_train)
prob = clf.predict_proba(X_test)[:, 1]
auc = roc_auc_score(yc_test, prob)
print(f"AUC-ROC: {auc:.4f}")
print(classification_report(yc_test, (prob >= 0.5).astype(int), digits=4))

# ---- Regressor for health score ----
print("\nTraining health-score regressor...")
reg = GradientBoostingRegressor(
    n_estimators=200, max_depth=5, learning_rate=0.08, random_state=42
)
reg.fit(X_train, yh_train)
h_pred = np.clip(reg.predict(X_test), 5, 100)
mae = mean_absolute_error(yh_test, h_pred)
print(f"Health-score MAE: {mae:.2f}  (target range 5..100)")

fi = pd.DataFrame({"feature": X.columns, "importance": clf.feature_importances_}) \
        .sort_values("importance", ascending=False).head(15)
print("\nTop features for maintenance risk:")
print(fi.to_string(index=False))

metrics = {
    "classifier": "RandomForest / 30-day maintenance horizon",
    "regressor": "GradientBoosting / continuous health 5..100",
    "n_rows": int(len(df)),
    "maintenance_rate_pct": round(float(y_cls.mean() * 100), 2),
    "classifier_AUC": round(float(auc), 4),
    "regressor_MAE": round(float(mae), 3),
    "features": list(X.columns),
    "top_features": fi.to_dict("records"),
}
print("\nMetrics:", json.dumps({k: v for k, v in metrics.items() if k not in ("features","top_features")}, indent=2))

joblib.dump({
    "classifier": clf,
    "regressor": reg,
    "columns": list(X.columns),
    "feature_medians": X.median().to_dict(),
}, ART / "maintenance_model.pkl", compress=3)   # compress -> keep artifact GitHub-friendly
with open(ART / "maintenance_metrics.json", "w") as f: json.dump(metrics, f, indent=2)
print("\nSaved artifacts to", ART)
