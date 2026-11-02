"""POST /api/sim/start|stop, POST /api/sim/inject/anomaly"""

from fastapi import APIRouter, Depends, HTTPException
from ..auth import require_admin
from ..schemas import InjectRequest
from ..simulator import SIM

router = APIRouter(prefix="/api/sim", tags=["simulator"])


@router.get("/status")
def sim_status(_u: dict = Depends(require_admin)):
    return {"on": SIM["on"]}


@router.post("/inject/anomaly")
def inject_anomaly(body: InjectRequest, _u: dict = Depends(require_admin)):
    SIM["inject"][body.room_id] = body.ticks
    return {"ok": True}


@router.post("/{action}")
def sim_control(action: str, _u: dict = Depends(require_admin)):
    if action not in ("start", "stop"):
        raise HTTPException(404, "Unknown action")
    SIM["on"] = action == "start"
    return SIM["on"]

