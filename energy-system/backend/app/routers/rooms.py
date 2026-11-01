"""GET /api/rooms, GET /api/rooms/{rid}/live"""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Department, Reading, Room

router = APIRouter(prefix="/api", tags=["rooms"])


def _my_rooms(db: Session, u: dict):
    q = db.query(Room)
    if u["role"] != "admin" and u.get("block"):
        return q.filter(Room.block == u["block"]).all()
    return q.all()


def _room_ok(db: Session, u: dict, rid: int) -> Room:
    r = db.get(Room, rid)
    if not r or (u["role"] != "admin" and u.get("block") and r.block != u["block"]):
        raise HTTPException(404, "Room not found")
    return r


@router.get("/rooms")
def list_rooms(u: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for r in _my_rooms(db, u):
        latest = (
            db.query(Reading)
            .filter_by(room_id=r.id)
            .order_by(Reading.ts.desc())
            .first()
        )
        dept_name = r.department.name if r.department else "Unassigned"
        out.append({
            "id": r.id,
            "name": r.name,
            "block": r.block,
            "floor": r.floor,
            "type": r.rtype,
            "department": dept_name,
            "meter": r.meter_id,
            "power": latest.power_kw if latest else None,
            "status": latest.status if latest else None,
            "source": "simulated" if latest and latest.simulated else "hardware",
        })
    return out


@router.get("/rooms/{rid}/live")
def room_live(rid: int, u: dict = Depends(get_current_user),
              db: Session = Depends(get_db)):
    r = _room_ok(db, u, rid)
    rows = (
        db.query(Reading)
        .filter_by(room_id=rid)
        .order_by(Reading.ts.desc())
        .limit(60)
        .all()[::-1]
    )
    return {
        "room": r.name,
        "online": time.time() - (r.last_seen or 0) < 30,
        "points": [
            {"t": x.ts.strftime("%a %H:%M"), "kw": x.power_kw, "status": x.status}
            for x in rows
        ],
    }

