# CAT-alyst ML Training Pipeline

Reproducible pipeline for the three ML modules the dealer dashboard uses:

1. **Demand Forecasting** — GradientBoostingRegressor (weekly bookings)
2. **Anomaly Detection** — IsolationForest + RandomForest hybrid + CAT-signal rules
3. **Predictive Maintenance** — RandomForest (30-day risk) + GradientBoosting (health score)

## You usually don't need to run this

The trained artifacts and serving snapshot are **already committed** under
`backend/app/ml/artifacts/` and `backend/app/ml/serving/`, so a fresh clone
runs the demo immediately — the FastAPI app loads them at startup. Run the
pipeline only to **retrain from scratch** or regenerate the data.

## Retrain from scratch (deterministic, seed=42)

```bash
cd backend/app/ml/training

python generate_dataset.py        # -> training/data/*.csv  (telemetry_daily ~60MB, regenerable)
python train_demand_forecast.py   # -> training/artifacts/demand_model.pkl
python train_anomaly.py           # -> training/artifacts/anomaly_model.pkl
python train_maintenance.py       # -> training/artifacts/maintenance_model.pkl
python build_serving_snapshot.py  # -> copies artifacts + builds serving/ into backend/app/ml/
```

Then restart the backend; the new artifacts load automatically.

## What's committed vs generated

| Path | Committed? | Notes |
| --- | --- | --- |
| `backend/app/ml/artifacts/*.pkl` + `*_metrics.json` | ✅ | Trained models the app loads |
| `backend/app/ml/serving/*.csv` | ✅ | Compact snapshot (latest + 45-day telemetry, machines, demand) |
| `training/*.py` | ✅ | This pipeline |
| `training/data/` | ❌ gitignored | ~60 MB regenerable dataset |
| `training/artifacts/` | ❌ gitignored | Intermediate; copied to `../artifacts/` by build_serving_snapshot |

## Model performance (from `*_metrics.json`)

| Model | Metric | Value |
| --- | --- | --- |
| Demand Forecast | R² / MAE | 0.51 / 1.49 bookings |
| Anomaly Detection | AUC-ROC / type-acc | 0.9999 / 0.997 |
| Predictive Maintenance | classifier AUC / health MAE | 0.95 / 0.06 |

## Dataset (deterministic simulation)

4 countries × 15 equipment types × 3.5 years, causal simulation
(demand → rentals → telemetry → sensor degradation → maintenance →
correlated anomalies ~6%). Anomaly features **exclude** order size / bulk /
customer, so legitimate large mining orders are never flagged.
