"""Smart Energy Intelligence & Monitoring System – FastAPI entry point.

Run:
  uvicorn app.main:app --reload
  (SQLite by default; set DATABASE_URL env var for PostgreSQL)

Secrets expected in environment:
  JWT_SECRET            – required in production (ENV != development)
  DATABASE_URL          – defaults to sqlite:///./energy.db
  TARIFF_PER_KWH        – defaults to 7.5
  BUDGET_KWH            – defaults to 6000
  DEVICE_KEY            – legacy single-key for /api/ingest (defaults to esp32-demo-key in dev)
  DEVICE_OFFLINE_TIMEOUT_SEC – default 120
  DEVICE_CHECK_INTERVAL_SEC  – default 60
"""

import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import SessionLocal, engine
from .models import Base
from .seed_demo import seed_demo
from .simulator import sim_loop
from .background_tasks import start_offline_checker

# Routers
from .routers import (
    auth_router,
    overview_router,
    rooms_router,
    alerts_router,
    timetable_router,
    sim_router,
    ingest_router,
    blocks_router,
    floors_router,
    departments_router,
    meters_router,
    devices_router,
    demo_router,
)

app = FastAPI(
    title="Smart Energy Intelligence & Monitoring System",
    description=(
        "Campus electricity monitoring with timetable-aware anomaly detection. "
        "All cost values are estimates, never official bills."
    ),
    version="1.0.0",
)

# Allow the Vite dev server to reach the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
for r in (
    auth_router,
    overview_router,
    rooms_router,
    alerts_router,
    timetable_router,
    sim_router,
    ingest_router,
    blocks_router,
    floors_router,
    departments_router,
    meters_router,
    devices_router,
    demo_router,
):
    app.include_router(r)


@app.on_event("startup")
def startup() -> None:
    # Create any new tables (safe: does not drop existing data)
    Base.metadata.create_all(engine)

    # Seed demo data only in development and only when the DB is empty
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()

    # Start simulator background thread
    threading.Thread(
        target=sim_loop,
        args=(SessionLocal,),
        daemon=True,
        name="simulator",
    ).start()

    # Start device offline-checker
    start_offline_checker(SessionLocal)
