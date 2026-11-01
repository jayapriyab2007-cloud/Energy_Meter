"""GET /api/timetable/{rid}, PUT /api/timetable/{rid}"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Audit, Room, Timetable
from ..schemas import TimetableCell
from ..simulator import STATUS_LABELS, load_tt

router = APIRouter(prefix="/api", tags=["timetable"])

STATUS_LABELS_MAP = {
    "Occupied": "Class",
    "Free": "No scheduled class",
    "Break": "Lunch",
}


def _room_ok(db: Session, u: dict, rid: int) -> Room:
    r = db.get(Room, rid)
    if not r or (u["role"] != "admin" and u.get("block") and r.block != u["block"]):
        raise HTTPException(404, "Room not found")
    return r


@router.get("/timetable/{rid}")
def get_timetable(rid: int, u: dict = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    _room_ok(db, u, rid)
    return [
        {"day": t.day, "hour": t.hour, "status": t.status, "activity": t.activity}
        for t in db.query(Timetable).filter_by(room_id=rid)
    ]


@router.put("/timetable/{rid}")
def put_timetable(rid: int, cell: TimetableCell, u: dict = Depends(require_admin),
                  db: Session = Depends(get_db)):
    _room_ok(db, u, rid)
    existing = (
        db.query(Timetable)
        .filter_by(room_id=rid, day=cell.day, hour=cell.hour)
        .first()
    )
    t = existing or Timetable(room_id=rid, day=cell.day, hour=cell.hour)
    t.status = cell.status
    t.activity = STATUS_LABELS_MAP[cell.status]
    db.add(t)
    db.add(Audit(who=u["sub"], what=f"timetable room {rid} day={cell.day} hour={cell.hour}"))
    db.commit()
    load_tt(db, rid)
    return {"ok": True}

