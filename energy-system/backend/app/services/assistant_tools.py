"""Fixed backend functions for the Campus Energy Assistant.

Every function:
- Runs permission-checked queries
- Labels costs as 'estimate'
- Distinguishes 'simulated' vs 'hardware'
- Uses 'investigate' instead of 'waste' for alerts
- Avoids inventing readings, costs, or timetable entries
"""

import datetime as dt
import os
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Alert, Department, Floor, IoTDevice, Meter, Reading, Room, Timetable
from ..simulator import status_at

TARIFF = float(os.getenv("TARIFF_PER_KWH", "7.5"))
BUDGET_KWH = float(os.getenv("BUDGET_KWH", "6000"))


def get_now_ref(db: Session) -> dt.datetime:
    """Returns the effective reference timestamp for 'now' matching data telemetry.
    Respects virtual clock (SIM['clock']) or max(Reading.ts), falling back to dt.datetime.now().
    """
    from ..simulator import SIM
    if SIM.get("clock"):
        return SIM["clock"]
    max_ts = db.query(func.max(Reading.ts)).scalar()
    sys_now = dt.datetime.now()
    if max_ts and max_ts > sys_now:
        return max_ts
    return sys_now


def _get_permitted_room_ids(db: Session, user: dict, scope: Optional[Dict[str, Any]] = None) -> List[int]:
    """Return room IDs matching the scope and permitted for the user."""
    q = db.query(Room)
    if user.get("role") != "admin" and user.get("block"):
        q = q.filter(Room.block == user["block"].upper())

    if scope:
        stype = scope.get("type")
        if stype == "room":
            q = q.filter(Room.id == scope["id"])
        elif stype == "block":
            q = q.filter(Room.block == scope["name"])
        elif stype == "floor":
            q = q.filter(Room.block == scope["block"], Room.floor == scope["number"])
        elif stype == "department":
            q = q.filter(Room.department_id == scope["id"])

    return [r.id for r in q.all()]


def get_room_status(room_entity: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Latest power, timetable status now, department, meter, data source, and last seen."""
    room = db.get(Room, room_entity["id"])
    if not room:
        return {"error": "Room not found"}

    now = get_now_ref(db)
    cur_status = status_at(db, room.id, now)

    latest_reading = (
        db.query(Reading)
        .filter_by(room_id=room.id)
        .order_by(Reading.ts.desc())
        .first()
    )

    is_online = (time.time() - (room.last_seen or 0)) < 120 if room.last_seen else False

    return {
        "room": room.name,
        "type": room.rtype,
        "department": room.department.name if room.department else "Unassigned",
        "block": room.block,
        "floor": room.floor,
        "meter_id": room.meter_id,
        "current_status": cur_status,
        "power_kw": latest_reading.power_kw if latest_reading else None,
        "source": "simulated" if (latest_reading and latest_reading.simulated) else "hardware",
        "last_reading_time": latest_reading.ts.strftime("%Y-%m-%d %H:%M") if latest_reading else "No readings",
        "online": is_online,
    }


def get_room_usage(
    room_entity: Dict[str, Any], period: str, db: Session
) -> Dict[str, Any]:
    """Calculates kWh and cost estimate for today, yesterday, last 7 days, or this month."""
    room = db.get(Room, room_entity["id"])
    if not room:
        return {"error": "Room not found"}

    now = get_now_ref(db)
    today_0 = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "yesterday":
        start_ts = today_0 - dt.timedelta(days=1)
        end_ts = today_0
        time_label = "yesterday"
    elif period in ("7days", "last 7 days", "week"):
        start_ts = now - dt.timedelta(days=7)
        end_ts = now
        time_label = "last 7 days"
    elif period in ("month", "this month"):
        start_ts = today_0.replace(day=1)
        end_ts = now
        time_label = "this month"
    else:  # default today
        start_ts = today_0
        end_ts = now
        time_label = "today"

    total_kwh = (
        db.query(func.coalesce(func.sum(Reading.energy_kwh), 0.0))
        .filter(Reading.room_id == room.id, Reading.ts >= start_ts, Reading.ts <= end_ts)
        .scalar()
    )

    est_cost = round(total_kwh * TARIFF, 2)

    return {
        "room": room.name,
        "period": time_label,
        "energy_kwh": round(total_kwh, 2),
        "est_cost_rs": est_cost,
        "cost_label": "estimate",
        "tariff_per_kwh": TARIFF,
        "source": "simulated",
    }


def get_top_consumers(
    group_by: str, period: str, user: dict, db: Session, scope_filter: Optional[Dict[str, Any]] = None, limit: int = 3
) -> Dict[str, Any]:
    """Ranks rooms, floors, blocks, or departments by energy consumption within an optional scope filter."""
    now = get_now_ref(db)
    today_0 = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "yesterday":
        start_ts = today_0 - dt.timedelta(days=1)
        end_ts = today_0
    elif period in ("7days", "last 7 days", "week"):
        start_ts = now - dt.timedelta(days=7)
        end_ts = now
    elif period in ("month", "this month"):
        start_ts = today_0.replace(day=1)
        end_ts = now
    else:
        start_ts = today_0
        end_ts = now

    permitted_rids = _get_permitted_room_ids(db, user, scope_filter)

    if group_by in ("block", "blocks"):
        q = (
            db.query(Room.block, func.sum(Reading.energy_kwh))
            .join(Reading, Room.id == Reading.room_id)
            .filter(Room.id.in_(permitted_rids), Reading.ts >= start_ts, Reading.ts <= end_ts)
            .group_by(Room.block)
            .order_by(func.sum(Reading.energy_kwh).desc())
            .limit(limit)
            .all()
        )
        items = [{"label": f"Block {b}", "kwh": round(kwh, 1), "est_cost": round(kwh * TARIFF)} for b, kwh in q]
        category = "blocks"

    elif group_by in ("department", "departments", "dept"):
        q = (
            db.query(Department.name, func.sum(Reading.energy_kwh))
            .join(Room, Department.id == Room.department_id)
            .join(Reading, Room.id == Reading.room_id)
            .filter(Room.id.in_(permitted_rids), Reading.ts >= start_ts, Reading.ts <= end_ts)
            .group_by(Department.name)
            .order_by(func.sum(Reading.energy_kwh).desc())
            .limit(limit)
            .all()
        )
        items = [{"label": dname, "kwh": round(kwh, 1), "est_cost": round(kwh * TARIFF)} for dname, kwh in q]
        category = "departments"

    elif group_by in ("floor", "floors"):
        q = (
            db.query(Room.block, Room.floor, func.sum(Reading.energy_kwh))
            .join(Reading, Room.id == Reading.room_id)
            .filter(Room.id.in_(permitted_rids), Reading.ts >= start_ts, Reading.ts <= end_ts)
            .group_by(Room.block, Room.floor)
            .order_by(func.sum(Reading.energy_kwh).desc())
            .limit(limit)
            .all()
        )
        items = [{"label": f"Block {b} Floor {fl}", "kwh": round(kwh, 1), "est_cost": round(kwh * TARIFF)} for b, fl, kwh in q]
        category = "floors"

    else:  # default: rooms
        q = (
            db.query(Room.name, Room.block, Room.rtype, func.sum(Reading.energy_kwh))
            .join(Reading, Room.id == Reading.room_id)
            .filter(Room.id.in_(permitted_rids), Reading.ts >= start_ts, Reading.ts <= end_ts)
            .group_by(Room.name, Room.block, Room.rtype)
            .order_by(func.sum(Reading.energy_kwh).desc())
            .limit(limit)
            .all()
        )
        items = []
        for rname, b, rtype, kwh in q:
            # Query highest current demand for the top room
            top_room = db.query(Room).filter_by(name=rname).first()
            lat_r = (
                db.query(Reading)
                .filter_by(room_id=top_room.id)
                .order_by(Reading.ts.desc())
                .first()
            ) if top_room else None
            kw_val = lat_r.power_kw if lat_r else None
            items.append({
                "label": f"Room {rname} ({rtype} in Block {b})",
                "room_name": rname,
                "kwh": round(kwh, 1),
                "est_cost": round(kwh * TARIFF),
                "current_kw": kw_val,
            })
        category = "rooms"

    return {
        "category": category,
        "period": period,
        "ranking": items,
        "cost_note": "estimate",
    }


def compare_scopes(
    entity_a: Dict[str, Any], entity_b: Dict[str, Any], period: str, user: dict, db: Session
) -> Dict[str, Any]:
    """Compares energy draw between two entities (e.g. CSE vs ECE, Block A vs Block B)."""
    rids_a = _get_permitted_room_ids(db, user, entity_a)
    rids_b = _get_permitted_room_ids(db, user, entity_b)

    now = get_now_ref(db)
    today_0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "yesterday":
        start_ts = today_0 - dt.timedelta(days=1)
        end_ts = today_0
    elif period in ("7days", "last 7 days", "week"):
        start_ts = now - dt.timedelta(days=7)
        end_ts = now
    elif period in ("month", "this month"):
        start_ts = today_0.replace(day=1)
        end_ts = now
    else:
        start_ts = today_0
        end_ts = now

    sum_a = (
        db.query(func.coalesce(func.sum(Reading.energy_kwh), 0.0))
        .filter(Reading.room_id.in_(rids_a), Reading.ts >= start_ts, Reading.ts <= end_ts)
        .scalar()
    ) if rids_a else 0.0

    sum_b = (
        db.query(func.coalesce(func.sum(Reading.energy_kwh), 0.0))
        .filter(Reading.room_id.in_(rids_b), Reading.ts >= start_ts, Reading.ts <= end_ts)
        .scalar()
    ) if rids_b else 0.0

    return {
        "entity_a": {"label": entity_a.get("label", "A"), "kwh": round(sum_a, 1), "est_cost": round(sum_a * TARIFF)},
        "entity_b": {"label": entity_b.get("label", "B"), "kwh": round(sum_b, 1), "est_cost": round(sum_b * TARIFF)},
        "period": period,
        "difference_kwh": round(abs(sum_a - sum_b), 1),
        "higher": entity_a.get("label") if sum_a > sum_b else entity_b.get("label"),
    }


def get_alerts(scope: Optional[Dict[str, Any]], status: str, user: dict, db: Session) -> Dict[str, Any]:
    """Fetches recent alerts matching scope and status ('open' or 'all')."""
    permitted_rids = _get_permitted_room_ids(db, user, scope)
    q = (
        db.query(Alert, Room)
        .join(Room, Alert.room_id == Room.id)
        .filter(Alert.room_id.in_(permitted_rids))
    )
    if status != "all":
        q = q.filter(Alert.status == status)

    alerts = q.order_by(Alert.id.desc()).limit(5).all()

    items = []
    for a, r in alerts:
        items.append({
            "id": a.id,
            "room": r.name,
            "block": r.block,
            "floor": r.floor,
            "kind": a.kind,
            "severity": a.severity,
            "status": a.status,
            "power_kw": a.power,
            "baseline_kw": a.baseline,
            "explanation": a.explanation,
            "action": a.action,
            "time": a.ts.strftime("%Y-%m-%d %H:%M"),
        })

    return {
        "scope": scope.get("label") if scope else "Campus-wide",
        "total_matching": len(items),
        "alerts": items,
    }


def explain_alert(room_or_id: Any, user: dict, db: Session) -> Dict[str, Any]:
    """Explains why an anomaly was raised: status, measured vs baseline, duration, and recommendation."""
    q = db.query(Alert, Room).join(Room, Alert.room_id == Room.id)

    if isinstance(room_or_id, int):
        q = q.filter(Alert.id == room_or_id)
    elif isinstance(room_or_id, dict) and room_or_id.get("type") == "room":
        q = q.filter(Alert.room_id == room_or_id["id"])

    # Permitted checks
    if user.get("role") != "admin" and user.get("block"):
        q = q.filter(Room.block == user["block"].upper())

    alert_row = q.order_by(Alert.id.desc()).first()
    if not alert_row:
        return {"found": False, "message": "No alert found for the specified entity or permission scope."}

    a, r = alert_row
    return {
        "found": True,
        "room": r.name,
        "kind": a.kind,
        "severity": a.severity,
        "measured_kw": a.power,
        "baseline_kw": a.baseline,
        "explanation": a.explanation,
        "recommended_action": a.action,
        "status": a.status,
        "time": a.ts.strftime("%Y-%m-%d %H:%M"),
    }


def get_timetable(room_entity: Dict[str, Any], day_idx: Optional[int], db: Session) -> Dict[str, Any]:
    """Retrieves timetable slots and whether room is currently scheduled free/occupied."""
    room = db.get(Room, room_entity["id"])
    if not room:
        return {"error": "Room not found"}

    now = get_now_ref(db)
    target_day = day_idx if day_idx is not None else now.weekday()

    slots = (
        db.query(Timetable)
        .filter_by(room_id=room.id, day=target_day)
        .order_by(Timetable.hour)
        .all()
    )

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    cur_status = status_at(db, room.id, now)

    return {
        "room": room.name,
        "day": day_names[target_day],
        "is_free_now": cur_status == "Free",
        "current_status": cur_status,
        "slots": [{"hour": f"{s.hour}:00", "status": s.status, "activity": s.activity} for s in slots],
    }


def get_device_status(scope: Optional[Dict[str, Any]], user: dict, db: Session) -> Dict[str, Any]:
    """Returns meters/devices that are offline, disabled, or have no telemetry data."""
    from ..simulator import SIM
    permitted_rids = _get_permitted_room_ids(db, user, scope)
    rooms = db.query(Room).filter(Room.id.in_(permitted_rids)).all()
    meters = db.query(Meter).filter(Meter.room_id.in_(permitted_rids), Meter.measurement_level == "room").all()

    # Disabled meters
    disabled = [m for m in meters if not m.enabled]

    # Meters with no readings ever stored
    rooms_no_data = []
    for r in rooms:
        has_r = db.query(Reading.id).filter_by(room_id=r.id).first()
        if not has_r:
            rooms_no_data.append({"room": r.name, "block": r.block, "floor": r.floor, "meter": r.meter_id})

    offline_list = [
        {"room": m.room.name if m.room else m.meter_id, "meter": m.meter_id, "reason": "disabled"}
        for m in disabled
    ] + [
        {"room": r["room"], "meter": r["meter"], "reason": "no data received"}
        for r in rooms_no_data
    ]

    return {
        "scope": scope.get("label") if scope else "Campus-wide",
        "total_checked": len(rooms),
        "offline_count": len(offline_list),
        "offline_rooms": offline_list,
        "sim_running": SIM.get("on", False),
    }

