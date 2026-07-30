"""
Standalone ML demo server — verify the 3 AI features WITHOUT MongoDB/Postgres.

This mounts only the ML-backed routers (demand forecast, anomaly detection,
predictive maintenance) so you can check them instantly. The full app
(app.main) also needs the databases; this file does not.

Run:
    cd backend
    pip install -r requirements.txt
    python run_ml_demo.py

Then open http://127.0.0.1:8010/docs  (interactive API — click "Try it out")
Or just hit the URLs printed below in a browser.
"""
import os
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/unused")
os.environ.setdefault("POSTGRES_URI", "postgresql://u:p@localhost:5432/unused")
os.environ.setdefault("SECRET_KEY", "demo-key")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import analytics, ai, equipment

app = FastAPI(title="CAT-alyst ML Demo (DB-free)")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Demand Forecasting"])
app.include_router(ai.router,        prefix="/api/v1/ai",        tags=["Anomaly Detection"])
app.include_router(equipment.router, prefix="/api/v1/equipment", tags=["Predictive Maintenance"])


@app.get("/")
def index():
    return {
        "message": "CAT-alyst ML demo is running. Open /docs to try each feature.",
        "feature_1_demand_forecast": [
            "/api/v1/analytics/trends",
            "/api/v1/analytics/forecast/countries",
            "/api/v1/analytics/forecast/country/USA",
            "/api/v1/analytics/forecast/comparison?machine_type=Excavator",
        ],
        "feature_2_anomaly_detection": [
            "/api/v1/ai/recommendations",
            "/api/v1/ai/anomalies?limit=10",
            "/api/v1/ai/anomalies/summary",
        ],
        "feature_3_predictive_maintenance": [
            "/api/v1/equipment",
            "/api/v1/equipment/MAC00002/maintenance-forecast",
        ],
        "model_metrics": "/api/v1/ai/model-metrics",
    }


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("  CAT-alyst ML demo server")
    print("  Open:  http://127.0.0.1:8010/docs")
    print("  Or:    http://127.0.0.1:8010/   (lists all feature URLs)")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8010)
