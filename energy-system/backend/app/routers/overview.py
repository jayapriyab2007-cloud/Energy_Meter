"""GET /api/overview, GET /api/forecast, POST /api/assistant"""

import os
import time

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Alert, Reading, Room
from ..schemas import AssistantQuery
from ..simulator import SIM

router = APIRouter(prefix="/api", tags=["overview"])

TARIFF = float(os.getenv("TARIFF_PER_KWH", "7.5"))
BUDGET_KWH = float(os.getenv("BUDGET_KWH", "6000"))


def _my_rooms(db: Session, u: dict):
    q = db.query(Room)
    if u["role"] != "admin" and u.get("block"):
        return q.filter(Room.block == u["block"]).all()
    return q.all()


def _totals(db: Session, rooms):
    ids = [r.id for r in rooms]
    latest = db.query(func.max(Reading.ts)).scalar()
    if latest is None:
        import datetime as dt
        latest = dt.datetime.utcnow()
    d0 = latest.replace(hour=0, minute=0, second=0, microsecond=0)
    m0 = d0.replace(day=1)

    def E(since):
        return db.query(
            func.coalesce(func.sum(Reading.energy_kwh), 0)
        ).filter(Reading.room_id.in_(ids), Reading.ts >= since).scalar()

    return ids, latest, d0, E(d0), E(m0)


@router.get("/overview")
def overview(u: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    rooms = _my_rooms(db, u)
    ids, latest, d0, today, month = _totals(db, rooms)

    cur = db.query(
        func.coalesce(func.sum(Reading.power_kw), 0)
    ).filter(Reading.room_id.in_(ids), Reading.ts == latest).scalar()

    rows = (
        db.query(Reading.ts, Reading.energy_kwh, Room.block)
        .join(Room)
        .filter(Reading.room_id.in_(ids), Reading.ts >= d0)
        .all()
    )
    hourly, blocks = {}, {}
    for ts, e, b in rows:
        hourly[ts.hour] = hourly.get(ts.hour, 0) + e
        blocks[b] = blocks.get(b, 0) + e

    now = time.time()
    return {
        "as_of": latest,
        "current_kw": round(cur, 2),
        "today_kwh": round(today, 1),
        "month_kwh": round(month, 1),
        "est_bill": round(month * TARIFF),
        "budget_pct": round(month / BUDGET_KWH * 100, 1),
        "tariff": TARIFF,
        "open_alerts": db.query(Alert).filter(
            Alert.room_id.in_(ids), Alert.status == "open"
        ).count(),
        "meters": len(rooms),
        "online": sum(1 for r in rooms if now - (r.last_seen or 0) < 30),
        "hourly": [{"hour": f"{h:02d}:00", "kwh": round(v, 1)}
                   for h, v in sorted(hourly.items())],
        "blocks": [{"block": b, "kwh": round(v, 1)}
                   for b, v in sorted(blocks.items())],
        "sim": SIM["on"],
    }


@router.get("/forecast")
def forecast(u: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = [r.id for r in _my_rooms(db, u)]
    days: dict = {}
    for ts, e in db.query(Reading.ts, Reading.energy_kwh).filter(
        Reading.room_id.in_(ids)
    ):
        days[ts.date()] = days.get(ts.date(), 0) + e

    ks = sorted(days)[:-1][-7:]  # last 7 complete days
    avg = sum(days[k] for k in ks) / max(len(ks), 1)

    return {
        "daily": [{"day": k.isoformat()[5:], "kwh": round(days[k], 1)} for k in ks],
        "avg_daily_kwh": round(avg, 1),
        "month_kwh": round(avg * 30),
        "month_cost": round(avg * 30 * TARIFF),
        "budget_pct": round(avg * 30 / BUDGET_KWH * 100, 1),
        "method": "7-day moving average (statistical estimate, not an official bill)",
    }


@router.post("/assistant")
def assistant(body: AssistantQuery, u: dict = Depends(get_current_user),
              db: Session = Depends(get_db)):
    q = body.q.lower()
    o = overview(u, db)

    if "bill" in q or "cost" in q:
        return {"a": (f"Estimated bill this month so far: Rs {o['est_bill']:,} "
                      f"({o['month_kwh']} kWh at Rs {TARIFF}/kWh). This is an estimate.")}
    if "block" in q and o["blocks"]:
        top = max(o["blocks"], key=lambda x: x["kwh"])
        return {"a": f"Block {top['block']} has used the most today: {top['kwh']} kWh."}
    if "room" in q or "most" in q or "highest" in q:
        ids, _, d0, _, _ = _totals(db, _my_rooms(db, u))
        r = (
            db.query(Room.name, func.sum(Reading.energy_kwh))
            .join(Reading)
            .filter(Reading.ts >= d0, Room.id.in_(ids))
            .group_by(Room.name)
            .order_by(func.sum(Reading.energy_kwh).desc())
            .first()
        )
        return {"a": f"Highest room today: {r[0]} with {r[1]:.1f} kWh." if r else "No data yet."}
    if "alert" in q or "why" in q or "anomal" in q:
        ids2 = [r.id for r in _my_rooms(db, u)]
        open_alerts = (
            db.query(Alert, Room.name)
            .join(Room)
            .filter(Alert.room_id.in_(ids2), Alert.status == "open")
            .order_by(Alert.id.desc())
            .limit(1)
            .all()
        )
        if open_alerts:
            a, rname = open_alerts[0]
            return {"a": f"{rname}: {a.kind}. {a.explanation}"}
        return {"a": "There are no open alerts."}
    if "power" in q or "demand" in q:
        return {"a": f"Current demand is {o['current_kw']} kW across {o['meters']} meters."}
    return {
        "a": (f"Today: {o['today_kwh']} kWh used, {o['current_kw']} kW now, "
              f"{o['open_alerts']} open alerts. Ask about bill, block, room, alerts or demand.")
    }

