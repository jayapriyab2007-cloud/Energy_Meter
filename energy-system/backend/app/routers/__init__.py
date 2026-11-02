"""Router package – re-exports all sub-routers."""

from .auth import router as auth_router
from .overview import router as overview_router
from .rooms import router as rooms_router
from .alerts import router as alerts_router
from .timetable import router as timetable_router
from .sim import router as sim_router
from .ingest import router as ingest_router
from .blocks import router as blocks_router
from .floors import router as floors_router
from .departments import router as departments_router
from .meters import router as meters_router
from .devices import router as devices_router
from .demo import router as demo_router
from .manual_readings import router as manual_readings_router

__all__ = [
    "auth_router",
    "overview_router",
    "rooms_router",
    "alerts_router",
    "timetable_router",
    "sim_router",
    "ingest_router",
    "blocks_router",
    "floors_router",
    "departments_router",
    "meters_router",
    "devices_router",
    "demo_router",
    "manual_readings_router",
]

