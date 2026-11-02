"""POST /api/manual-readings – Admin endpoint for manual meter readings.

Used by administrators on the "Input data" page to feed test readings for any room,
verify real-time telemetry updates, and evaluate anomaly detection rules before hardware is deployed.
"""

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Alert, Audit, Meter, Reading, Room
from ..simulator import baseline, ingest, status_at

router = APIRouter(prefix="/api", tags=["manual-readings"])


class ManualReadingCreate(BaseModel):
    room: str = Field(..., min_length=1, description="Room code, e.g. A204 or B101")
    power_kw: float = Field(..., ge=0.0, le=100.0, description="Power in kW (0 to 100)")
    voltage: Optional[float] = Field(None, ge=0.0, le=500.0)
    current_a: Optional[float] = Field(None, ge=0.0, le=500.0)
    ts: Optional[dt.datetime] = Field(None, description="Timestamp (default now)")
    repeat_count: int = Field(1, description="Number of readings (1, 3, or 6)")
    interval_min: float = Field(5.0, ge=0.5, le=60.0, description="Minutes between readings")


@router.post("/manual-readings")
def post_manual_readings(
    body: ManualReadingCreate,
    u: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only manual reading ingestion.

    - Verifies room exists and has an enabled room-level meter.
    - Rejects timestamps > 5 minutes in the future.
    - Feeds readings through the unified ingest/detection pipeline with data_source='manual'.
    - Skips duplicate timestamps.
    - Returns timetable status, normal baseline draw, stored readings count, and newly generated alerts.
    """
    if body.repeat_count not in (1, 3, 6):
        raise HTTPException(422, "repeat_count must be 1, 3, or 6")

    # 1. Resolve room
    room = db.query(Room).filter(Room.name.ilike(body.room.strip())).first()
    if not room:
        raise HTTPException(404, f"Room '{body.room}' not found")

    # 2. Check room-level meter
    meter = db.query(Meter).filter_by(room_id=room.id, measurement_level="room").first()
    if not meter:
        raise HTTPException(404, f"No room-level meter found for room '{room.name}'")
    if not meter.enabled:
        raise HTTPException(400, f"Meter for room '{room.name}' is disabled")

    # 3. Validate timestamp
    from ..simulator import SIM
    effective_now = SIM.get("clock") or dt.datetime.now()
    base_ts = (body.ts or effective_now).replace(microsecond=0)
    now_limit = dt.datetime.now() + dt.timedelta(minutes=5)
    if base_ts > now_limit:
        raise HTTPException(422, "Timestamp cannot be more than 5 minutes in the future")

    # Capture open alerts prior to ingestion
    pre_alert_ids = set(a.id for a in db.query(Alert).filter_by(room_id=room.id, status="open").all())

    stored_count = 0
    st_at_time = status_at(db, room.id, base_ts)
    base_kw, n_samples = baseline(db, room.id, st_at_time, base_ts)

    # Ingest repeat readings sequentially, working backwards up to base_ts so base_ts is the latest reading
    interval_hours = body.interval_min / 60.0
    for i in range(body.repeat_count - 1, -1, -1):
        cur_ts = base_ts - dt.timedelta(minutes=body.interval_min * i)
        # Duplicate check on (room_id, ts)
        if db.query(Reading).filter_by(room_id=room.id, ts=cur_ts).first():
            continue

        ingest(
            db=db,
            room=room,
            ts=cur_ts,
            p=body.power_kw,
            hours=interval_hours,
            sim=False,
            data_source="manual",
            voltage=body.voltage,
            current_a=body.current_a,
        )
        stored_count += 1

    db.commit()

    # Capture newly generated alerts
    post_alerts = db.query(Alert).filter_by(room_id=room.id, status="open").all()
    new_alerts = [a for a in post_alerts if a.id not in pre_alert_ids]

    # Audit log
    db.add(
        Audit(
            who=u["sub"],
            what=(
                f"manual reading for {room.name}: {body.power_kw} kW x{body.repeat_count} "
                f"at {base_ts.strftime('%Y-%m-%d %H:%M')}"
            ),
        )
    )
    db.commit()

    return {
        "ok": True,
        "room": room.name,
        "readings_stored": stored_count,
        "timetable_status": st_at_time,
        "normal_baseline_kw": round(base_kw, 2),
        "history_samples": n_samples,
        "new_alerts_count": len(new_alerts),
        "alert_ids": [a.id for a in new_alerts],
        "alerts": [
            {
                "id": a.id,
                "kind": a.kind,
                "severity": a.severity,
                "explanation": a.explanation,
                "action": a.action,
            }
            for a in new_alerts
        ],
    }
