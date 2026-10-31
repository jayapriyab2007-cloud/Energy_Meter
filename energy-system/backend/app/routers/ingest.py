"""POST /api/ingest – legacy ESP32/hardware ingestion path.

Uses a global device key from DEVICE_KEY env var for backward compatibility.
New devices should use the per-device key system in /api/devices.
"""

import datetime as dt
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Reading, Room
from ..schemas import IngestRequest
from ..simulator import ingest

router = APIRouter(prefix="/api", tags=["ingest"])

_LEGACY_DEVICE_KEY = os.getenv("DEVICE_KEY", "esp32-demo-key")


@router.post("/ingest")
def hw_ingest(
    body: IngestRequest,
    x_device_key: str = Header(None),
    db: Session = Depends(get_db),
):
    """Accept a reading from a hardware device (legacy single-key auth)."""
    if x_device_key != _LEGACY_DEVICE_KEY:
        raise HTTPException(401, "Unknown device key")

    r = db.query(Room).filter_by(name=body.room).first()
    if not r:
        raise HTTPException(404, "Meter not registered")

    ts = (body.ts or dt.datetime.now()).replace(microsecond=0)
    if db.query(Reading).filter_by(room_id=r.id, ts=ts).first():
        return {"duplicate": True}

    ingest(db, r, ts, body.power_kw, body.interval_min / 60, sim=False)
    db.commit()
    return {"ok": True}

