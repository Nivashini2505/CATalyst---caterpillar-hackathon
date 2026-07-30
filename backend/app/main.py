from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from beanie import init_beanie
from app.db.mongodb import get_database
from app.models.mongo.users import User, Operator, SiteManager, Dealer, Notification, LoginHistory
from app.api.v1 import auth, site_manager, dealer, operator, equipment, analytics, ai, sites, operators, live
from app.db.postgres import engine
from sqlalchemy import text

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup MongoDB
    await connect_to_mongo()
    db = await get_database()
    await init_beanie(database=db, document_models=[User, Operator, SiteManager, Dealer, Notification, LoginHistory])
    
    # Startup PostgreSQL
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        
        # Automatically create all Postgres tables if they don't exist
        from app.models.postgres.core import Base
        await conn.run_sync(Base.metadata.create_all)
    print("*" * 50)
    print("SUCCESS: Connected to Local PostgreSQL Database!")
    print("*" * 50)

    # Warm the ML models + serving snapshot so the first dashboard request
    # is instant during the demo. Never let this block/kill startup.
    try:
        from app.ml import inference as ml
        if ml.is_ready():
            ml.fleet_health_overview()   # caches health/risk for all assets
            print("SUCCESS: ML models loaded and fleet health warmed.")
        else:
            print("WARNING: ML artifacts not found - endpoints will use fallbacks.")
    except Exception as e:
        print(f"WARNING: ML warmup skipped ({e}). API still starts.")

    yield
    # Shutdown
    await close_mongo_connection()
    await engine.dispose()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Smart Rental Tracking API", lifespan=lifespan)

# Allow React/Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to Smart Rental Tracking API"}

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(site_manager.router, prefix="/api/v1/manager", tags=["Site Manager Workflows"])
app.include_router(dealer.router, prefix="/api/v1/dealer", tags=["Dealer Workflows"])
app.include_router(operator.router, prefix="/api/v1/operator", tags=["Operator Workflows"])
app.include_router(equipment.router, prefix="/api/v1/equipment", tags=["Dashboard - Equipment"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Dashboard - Analytics"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["Dashboard - AI"])
app.include_router(sites.router, prefix="/api/v1/sites", tags=["Dashboard - Sites"])
app.include_router(operators.router, prefix="/api/v1/dashboard-operators", tags=["Dashboard - Operators"])
app.include_router(live.router, prefix="/api/v1/live", tags=["Dashboard - Live"])
