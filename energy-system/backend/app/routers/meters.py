"""CRUD for Meters – /api/meters

Meters track physical or simulated electricity meters.
measurement_level: "room" | "floor" | "building"
data_source:       "simulated" | "hardware"
Building/floor meters must never be attributed to individual rooms
(enforced by the measurement_level field; the anomaly engine only
runs for room-level meters).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Audit, Meter
from ..schemas import MeterCreate, MeterOut, MeterUpdate

router = APIRouter(prefix="/api/meters", tags=["meters"])


@router.get("", response_model=List[MeterOut])
def list_meters(
    measurement_level: Optional[str] = Query(None),
    block: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _u: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Meter)
    if measurement_level:
        q = q.filter(Meter.measurement_level == measurement_level)
    if block:
        q = q.filter(Meter.block == block)
    if enabled is not None:
        q = q.filter(Meter.enabled == enabled)
    return q.offset((page - 1) * page_size).limit(page_size).all()


@router.post("", response_model=MeterOut, status_code=201)
def create_meter(body: MeterCreate, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    if db.query(Meter).filter_by(meter_id=body.meter_id).first():
        raise HTTPException(409, f"Meter ID '{body.meter_id}' already exists")
    meter = Meter(**body.model_dump())
    db.add(meter)
    db.add(Audit(who=u["sub"], what=f"created meter {body.meter_id}"))
    db.commit()
    db.refresh(meter)
    return meter


@router.get("/{mid}", response_model=MeterOut)
def get_meter(mid: int, _u: dict = Depends(get_current_user),
              db: Session = Depends(get_db)):
    m = db.get(Meter, mid)
    if not m:
        raise HTTPException(404, "Meter not found")
    return m


@router.patch("/{mid}", response_model=MeterOut)
def update_meter(mid: int, body: MeterUpdate, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    m = db.get(Meter, mid)
    if not m:
        raise HTTPException(404, "Meter not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(m, k, v)
    db.add(Audit(who=u["sub"], what=f"updated meter {mid}"))
    db.commit()
    db.refresh(m)
    return m


@router.patch("/{mid}/enable")
def enable_meter(mid: int, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    m = db.get(Meter, mid)
    if not m:
        raise HTTPException(404, "Meter not found")
    m.enabled = True
    db.add(Audit(who=u["sub"], what=f"enabled meter {mid}"))
    db.commit()
    return {"ok": True, "enabled": True}


@router.patch("/{mid}/disable")
def disable_meter(mid: int, u: dict = Depends(require_admin),
                  db: Session = Depends(get_db)):
    m = db.get(Meter, mid)
    if not m:
        raise HTTPException(404, "Meter not found")
    m.enabled = False
    db.add(Audit(who=u["sub"], what=f"disabled meter {mid}"))
    db.commit()
    return {"ok": True, "enabled": False}


@router.delete("/{mid}", status_code=204)
def delete_meter(mid: int, u: dict = Depends(require_admin),
                 db: Session = Depends(get_db)):
    m = db.get(Meter, mid)
    if not m:
        raise HTTPException(404, "Meter not found")
    db.delete(m)
    db.add(Audit(who=u["sub"], what=f"deleted meter {mid}"))
    db.commit()

