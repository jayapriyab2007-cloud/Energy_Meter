"""Demo Control and Scenarios Router (/api/demo).

Provides Admin capabilities:
- Setting the virtual clock (date & time)
- Triggering deterministic scenarios:
  * Scenario 1: B101 seminar hall equipment left on (Weekday 11:00 Free period, 4.8 kW)
  * Scenario 2: B101 night-time consumption (22:00, 3.0 kW)
  * Scenario 3: A204 free-period consumption (Weekday 10:00 Free period, 2.4 kW)
- Creating one-off timetable exceptions (resolves/prevents alert)
- Resetting demo state (clears alerts, resets clock, restores clean baseline state)
"""

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Alert, Audit, Reading, Room, TimetableException
from ..simulator import SIM, ingest

router = APIRouter(prefix="/api/demo", tags=["demo"])


class SetClockRequest(BaseModel):
    # e.g., "2026-11-03T11:00:00" or ISO format
    virtual_time: dt.datetime


class ScenarioRequest(BaseModel):
    scenario: int = Field(..., ge=1, le=3)


class TimetableExceptionCreate(BaseModel):
    room_id: int
    start_ts: dt.datetime
    end_ts: dt.datetime
    activity: str
    reason: Optional[str] = ""
    alert_id: Optional[int] = None


@router.get("/status")
def get_demo_status(_u: dict = Depends(require_admin)):
    """Return simulator virtual clock and running status."""
    return {
        "demo_mode": True,
        "sim_running": SIM["on"],
        "virtual_clock": SIM["clock"].isoformat() if SIM["clock"] else None,
        "step_minutes": SIM["step"],
        "active_injections": SIM["inject"],
    }


@router.post("/clock")
def set_demo_clock(body: SetClockRequest, u: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Set the virtual clock for the simulator."""
    SIM["clock"] = body.virtual_time
    db.add(Audit(who=u["sub"], what=f"set demo virtual clock to {body.virtual_time}"))
    db.commit()
    return {"ok": True, "virtual_clock": SIM["clock"].isoformat()}


@router.post("/scenario")
def trigger_scenario(body: ScenarioRequest, u: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Execute one of the 3 specified college scenarios deterministically."""
    # Ensure simulator has a base time if not set
    now_ref = SIM["clock"] or dt.datetime.now()

    if body.scenario == 1:
        # Scenario 1: B101 Seminar Hall equipment left on during Free period (11:00-12:00)
        room = db.query(Room).filter_by(name="B101").first()
        if not room:
            raise HTTPException(404, "Room B101 not found")

        # Set clock to next/current weekday at 11:00
        days_ahead = (0 - now_ref.weekday()) % 7  # Monday
        if days_ahead == 0 and now_ref.hour > 11:
            days_ahead = 1
        target_date = (now_ref + dt.timedelta(days=days_ahead)).replace(hour=11, minute=0, second=0, microsecond=0)
        # Ensure Monday-Friday
        if target_date.weekday() >= 5:
            target_date += dt.timedelta(days=(7 - target_date.weekday()))

        SIM["clock"] = target_date

        # Ingest 4 consecutive readings 10 mins apart with high load (4.8 kW)
        for i in range(4):
            ts = target_date + dt.timedelta(minutes=10 * i)
            ingest(db, room, ts, 4.8, 10 / 60, sim=True)

        SIM["clock"] = target_date + dt.timedelta(minutes=40)
        db.add(Audit(who=u["sub"], what="executed Scenario 1: B101 Seminar Hall equipment left on"))
        db.commit()

        alert = db.query(Alert).filter_by(room_id=room.id, kind="Consumption during free period", status="open").first()
        return {
            "ok": True,
            "scenario": 1,
            "room": "B101",
            "virtual_time": SIM["clock"].isoformat(),
            "alert_created": alert is not None,
            "alert_id": alert.id if alert else None,
            "details": "Injected 4.8 kW into B101 during Free period (11:00). Anomaly detected.",
        }

    elif body.scenario == 2:
        # Scenario 2: Night-time consumption in B101 at 22:00 (3.0 kW)
        room = db.query(Room).filter_by(name="B101").first()
        if not room:
            raise HTTPException(404, "Room B101 not found")

        target_date = now_ref.replace(hour=22, minute=0, second=0, microsecond=0)
        SIM["clock"] = target_date

        for i in range(4):
            ts = target_date + dt.timedelta(minutes=10 * i)
            ingest(db, room, ts, 3.0, 10 / 60, sim=True)

        SIM["clock"] = target_date + dt.timedelta(minutes=40)
        db.add(Audit(who=u["sub"], what="executed Scenario 2: B101 Night-time consumption"))
        db.commit()

        alert = db.query(Alert).filter_by(room_id=room.id, kind="Night-time consumption", status="open").first()
        return {
            "ok": True,
            "scenario": 2,
            "room": "B101",
            "virtual_time": SIM["clock"].isoformat(),
            "alert_created": alert is not None,
            "alert_id": alert.id if alert else None,
            "details": "Injected 3.0 kW into B101 at 22:00 night-time. Anomaly detected.",
        }

    elif body.scenario == 3:
        # Scenario 3: A204 CSE Lab 2 Free period usage (Weekday 10:00, 2.4 kW)
        room = db.query(Room).filter_by(name="A204").first()
        if not room:
            raise HTTPException(404, "Room A204 not found")

        days_ahead = (1 - now_ref.weekday()) % 7  # Tuesday
        target_date = (now_ref + dt.timedelta(days=days_ahead)).replace(hour=10, minute=0, second=0, microsecond=0)
        if target_date.weekday() >= 5:
            target_date += dt.timedelta(days=(7 - target_date.weekday()))

        SIM["clock"] = target_date

        for i in range(4):
            ts = target_date + dt.timedelta(minutes=10 * i)
            ingest(db, room, ts, 2.4, 10 / 60, sim=True)

        SIM["clock"] = target_date + dt.timedelta(minutes=40)
        db.add(Audit(who=u["sub"], what="executed Scenario 3: A204 free period consumption"))
        db.commit()

        alert = db.query(Alert).filter_by(room_id=room.id, kind="Consumption during free period", status="open").first()
        return {
            "ok": True,
            "scenario": 3,
            "room": "A204",
            "virtual_time": SIM["clock"].isoformat(),
            "alert_created": alert is not None,
            "alert_id": alert.id if alert else None,
            "details": "Injected 2.4 kW into A204 during 10:00 Free period. Anomaly detected.",
        }

    raise HTTPException(400, "Invalid scenario ID")


@router.post("/exception")
def create_timetable_exception(
    body: TimetableExceptionCreate,
    u: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a one-off timetable exception, closing any related open alert."""
    room = db.get(Room, body.room_id)
    if not room:
        raise HTTPException(404, "Room not found")

    exc = TimetableException(
        room_id=body.room_id,
        start_ts=body.start_ts,
        end_ts=body.end_ts,
        activity=body.activity,
        reason=body.reason or "Authorized exception",
    )
    db.add(exc)

    # If alert_id provided, mark it legitimate/resolved with note
    if body.alert_id:
        alert = db.get(Alert, body.alert_id)
        if alert:
            alert.status = "legitimate"
            alert.note = f"Exception added: {body.activity} - {body.reason}"

    db.add(Audit(who=u["sub"], what=f"created timetable exception for {room.name}: {body.activity}"))
    db.commit()
    return {"ok": True, "exception_id": exc.id}


@router.post("/reset")
def reset_demo(u: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Reset demo: clears demo alerts, active injections, and resets clock."""
    SIM["on"] = False
    SIM["inject"].clear()

    # Reset clock to start of current day 08:00
    base_today = dt.datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    SIM["clock"] = base_today

    # Remove open alerts created during testing scenarios
    db.query(Alert).delete()
    db.query(TimetableException).delete()

    db.add(Audit(who=u["sub"], what="reset demo state and alerts"))
    db.commit()

    return {
        "ok": True,
        "message": "Demo reset complete. Alerts cleared, injections reset, virtual clock reset.",
        "virtual_clock": SIM["clock"].isoformat(),
    }

