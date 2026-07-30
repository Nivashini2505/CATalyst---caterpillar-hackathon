"""
Train anomaly detection.
Approach: HYBRID = deterministic rules + IsolationForest + RandomForest.

Why hybrid, not just a single model:
  - CAT PPT signals (engine_hours > 0 with operator empty, or engine_hours = 0
    with operator empty on active rental) are hard rules — no reason to leave
    those to a probabilistic model that might miss them.
  - Behavioural weirdness (excess idle patterns, fuel drift) is fuzzy —
    Isolation Forest handles that well.
  - We also train a RandomForestClassifier on the labelled anomalies so we can
    output an anomaly TYPE + confidence per row.

CRITICAL: features exclude anything that could be confounded with legitimate
bulk mining orders — no customer_id, is_bulk_order, contract_id, or quantity.
That keeps a 500-unit BHP order from getting flagged as suspicious just for
being big.
"""

from __future__ import annotations
import json, joblib
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ART = HERE / "artifacts"
ART.mkdir(exist_ok=True)

print("Loading telemetry_daily.csv (this is the big one)...")
tel = pd.read_csv(DATA / "telemetry_daily.csv")
print(f"loaded {len(tel):,} telemetry rows")

# Behavioural / physics features. Deliberately no customer/bulk fields.
FEATURES = [
    "engine_hours_today","idle_hours_today","total_engine_hours",
    "fuel_used_l","expected_fuel_l","fuel_level_pct",
    "engine_temperature_c","oil_pressure_kpa","coolant_temperature_c",
    "oil_temperature_c","battery_voltage_v","hydraulic_pressure_bar",
    "vibration_g","rpm","network_strength_pct","zero_activity_streak_days",
]
# Derived features that make signals crisper
tel["fuel_ratio"] = tel["fuel_used_l"] / (tel["expected_fuel_l"] + 0.5)
tel["idle_ratio"] = tel["idle_hours_today"] / (tel["engine_hours_today"] + tel["idle_hours_today"] + 0.01)
tel["has_operator"] = (tel["operator_id"].notna() & (tel["operator_id"].astype(str) != "")).astype(int)
tel["engine_no_op"] = ((tel["engine_hours_today"] > 0.5) & (tel["has_operator"] == 0)).astype(int)  # CAT PPT signal 1
tel["zero_and_no_op"] = ((tel["engine_hours_today"] <= 0.05) & (tel["has_operator"] == 0)).astype(int)  # CAT PPT signal 2
tel["gps_offline"] = (tel["gps_status"] == "OFFLINE").astype(int)
tel["gps_jump_flag"] = (tel["gps_status"] == "JUMP").astype(int)
tel["gps_out_geo"] = (tel["gps_status"] == "OUT_OF_GEOFENCE").astype(int)

FEATURES = FEATURES + ["fuel_ratio","idle_ratio","has_operator","engine_no_op","zero_and_no_op","gps_offline","gps_jump_flag","gps_out_geo"]

# Fill sensor-null (sensor_failure rows) with per-column median so tree models cope
X = tel[FEATURES].copy()
for c in X.columns:
    med = X[c].median()
    X[c] = X[c].fillna(med)
y = tel["is_anomaly"].astype(int)
y_type = tel["anomaly_type"].fillna("normal")

print(f"anomaly rate in dataset: {y.mean()*100:.2f}%")

# ------------------------------------------------------------------
# 1) IsolationForest — unsupervised behavioural outlier score
# ------------------------------------------------------------------
print("\nTraining IsolationForest (unsupervised)...")
iforest = IsolationForest(
    n_estimators=200, contamination=0.07,
    max_samples=min(len(X), 50000), random_state=42, n_jobs=-1
)
iforest.fit(X.sample(min(len(X), 100000), random_state=42))
# Score: negative = more anomalous. Convert to 0..1 anomaly_score.
raw = -iforest.score_samples(X)
X["iforest_score"] = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)

# ------------------------------------------------------------------
# 2) RandomForestClassifier — supervised (flag + type-aware)
# ------------------------------------------------------------------
print("\nTraining RandomForestClassifier (supervised, binary)...")
X_train, X_test, y_train, y_test, yt_train, yt_test = train_test_split(
    X, y, y_type, test_size=0.2, stratify=y, random_state=42
)
rf = RandomForestClassifier(
    n_estimators=250, max_depth=18, min_samples_leaf=5,
    class_weight="balanced", n_jobs=-1, random_state=42
)
rf.fit(X_train, y_train)
prob = rf.predict_proba(X_test)[:, 1]
pred = (prob >= 0.5).astype(int)

auc = roc_auc_score(y_test, prob)
print(f"AUC-ROC: {auc:.4f}")
print("Confusion matrix (rows=true, cols=pred):")
print(confusion_matrix(y_test, pred))
print("Classification report:")
print(classification_report(y_test, pred, digits=4))

# Feature importance
fi = pd.DataFrame({"feature": X.columns, "importance": rf.feature_importances_}) \
        .sort_values("importance", ascending=False).head(15)
print("\nTop features:")
print(fi.to_string(index=False))

# ------------------------------------------------------------------
# 3) Multi-class classifier for anomaly TYPE (skip 'normal')
#    Only trained on the flagged rows.
# ------------------------------------------------------------------
print("\nTraining anomaly-type classifier (multi-class over flagged rows)...")
mask = y == 1
X_fl = X[mask]
yt_fl = y_type[mask]
Xf_train, Xf_test, ytf_train, ytf_test = train_test_split(
    X_fl, yt_fl, test_size=0.2, stratify=yt_fl, random_state=42
)
rf_type = RandomForestClassifier(
    n_estimators=200, max_depth=15, min_samples_leaf=3,
    class_weight="balanced", n_jobs=-1, random_state=42
)
rf_type.fit(Xf_train, ytf_train)
type_pred = rf_type.predict(Xf_test)
print(f"Anomaly-type accuracy on flagged holdout: {(type_pred == ytf_test).mean():.4f}")

metrics = {
    "model": "Hybrid (IsolationForest + RandomForest + type-classifier)",
    "n_rows": int(len(tel)),
    "anomaly_rate_pct": round(float(y.mean() * 100), 2),
    "AUC_ROC": round(float(auc), 4),
    "type_accuracy_on_flagged": round(float((type_pred == ytf_test).mean()), 4),
    "features": list(X.columns),
    "top_features": fi.to_dict("records"),
    "target": "is_anomaly",
    "type_classes": sorted(list(y_type.unique())),
}
print("\nMetrics:", json.dumps({k: v for k, v in metrics.items() if k not in ("features","top_features","type_classes")}, indent=2))

joblib.dump({
    "iforest": iforest,
    "rf_binary": rf,
    "rf_type": rf_type,
    "columns": list(X.columns),
    "feature_medians": X.median().to_dict(),
}, ART / "anomaly_model.pkl", compress=3)   # compress -> keep artifact GitHub-friendly
with open(ART / "anomaly_metrics.json", "w") as f: json.dump(metrics, f, indent=2)
print("\nSaved artifacts to", ART)
