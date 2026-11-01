"""GET /api/alerts, PATCH /api/alerts/{aid}"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Alert, Audit, Department, Room
from ..schemas import AlertNote

router = APIRouter(prefix="/api", tags=["alerts"])


def _my_room_ids(db: Session, u: dict):
    q = db.query(Room)
    if u["role"] != "admin" and u.get("block"):
        q = q.filter(Room.block == u["block"])
    return [r.id for r in q.all()]


@router.get("/alerts")
def list_alerts(u: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = _my_room_ids(db, u)
    rows = (
        db.query(Alert, Room)
        .join(Room, Alert.room_id == Room.id)
        .filter(Alert.room_id.in_(ids))
        .order_by(Alert.id.desc())
        .limit(100)
        .all()
    )
    fields = ("id", "ts", "kind", "severity", "power", "baseline",
              "explanation", "action", "status", "note")
    out = []
    for a, r in rows:
        item = {c: getattr(a, c) for c in fields}
        item["room_id"] = r.id
        item["room"] = r.name
        item["block"] = r.block
        item["floor"] = r.floor
        item["department"] = r.department.name if r.department else "Unassigned"
        out.append(item)
    return out


@router.patch("/alerts/{aid}")
def patch_alert(aid: int, body: AlertNote, u: dict = Depends(require_admin),
                db: Session = Depends(get_db)):
    a = db.get(Alert, aid)
    if not a:
        raise HTTPException(404, "Alert not found")
    a.status = body.status
    a.note = body.note
    db.add(Audit(who=u["sub"], what=f"alert {aid} -> {body.status}"))
    db.commit()
    return {"ok": True}

