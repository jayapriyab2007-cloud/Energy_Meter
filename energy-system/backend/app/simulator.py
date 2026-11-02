"""Simulator engine for Smart Energy System with college profile and timetable-awareness.

Responsibilities:
- SIM state: on/off, virtual clock, injects
- profile(): deterministic realistic kW draws based on room type and timetable status:
    * Classroom: 1.8 occupied / 0.3 free
    * Lab: 4.0 occupied / 0.4 free
    * Workshop: 6.0 occupied / 0.4 free
    * Office: 1.5 occupied / 0.4 free
    * Seminar Hall: 5.5 occupied / 0.4 free
    * Out of hours: 0.15 to 0.2 kW
- status_at(): checks TimetableException first (suppressing false anomaly if authorized), then Timetable
- baseline(): calculates learned baseline from history (cold-start fallback if < 12 samples)
- detect(): evaluates room-level anomalies (worded "investigate", not "waste")
- ingest(): records reading for room and triggers detect()
"""

import datetime as dt
import random
import time
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Alert, Reading, Room, Timetable, TimetableException

# ---------------------------------------------------------------------------
# Shared simulator state
# ---------------------------------------------------------------------------

SIM: dict = {
    "on": False,
    "clock": None,   # virtual datetime
    "step": 10,      # minutes per tick
    "inject": {},    # room_id -> {"ticks": count, "kw": add_power}
}

# In-memory timetable cache: room_id -> {(day, hour): status}
TT: dict = {}

STATUS_LABELS = {
    "Occupied": "Class",
    "Free": "No scheduled class",
    "Break": "Lunch",
}


def load_tt(db: Session, rid: int) -> None:
    """Load or reload timetable for a room into memory cache."""
    TT[rid] = {
        (t.day, t.hour): t.status
        for t in db.query(Timetable).filter_by(room_id=rid)
    }


def status_at(db: Session, rid: int, ts: dt.datetime) -> str:
    """Return status at ts. Checks active TimetableException first."""
    # Check one-off timetable exception
    exc = (
        db.query(TimetableException)
        .filter(
            TimetableException.room_id == rid,
            TimetableException.start_ts <= ts,
            TimetableException.end_ts > ts,
        )
        .first()
    )
    if exc:
        return "Occupied"

    if rid not in TT:
        load_tt(db, rid)
    return TT[rid].get((ts.weekday(), ts.hour), "Off")


def profile(rtype: str, st: str, hour: int) -> float:
    """Return typical kW draw with ~8% Gaussian noise per specification:
    - classroom 1.8 kW occupied / 0.3 free
    - lab 4.0 / 0.4
    - workshop 6.0 / 0.4
    - office 1.5 / 0.4
    - seminar hall 5.5 / 0.4
    - out of hours (before 7 or after 19, or Sun): 0.15 to 0.2 kW
    """
    if hour < 7 or hour >= 19 or st == "Off":
        base = 0.18
    elif st == "Occupied":
        if rtype == "Seminar Hall":
            base = 5.5
        elif rtype == "Workshop":
            base = 6.0
        elif rtype == "Lab":
            base = 4.0
        elif rtype == "Office":
            base = 1.5
        else:  # Classroom or default
            base = 1.8
    else:  # Free or Break (Lunch)
        base = 0.4 if rtype in ("Seminar Hall", "Workshop", "Lab", "Office") else 0.3

    return max(0.05, random.gauss(base, base * 0.08))


def baseline(db: Session, rid: int, st: str, ts: dt.datetime) -> tuple[float, int]:
    """Historical average power for (room, status) pair.
    Excludes recent 3 hours so ongoing anomalies don't distort baseline.
    """
    q = (
        db.query(func.avg(Reading.power_kw), func.count())
        .filter(
            Reading.room_id == rid,
            Reading.status == st,
            Reading.ts < ts - dt.timedelta(hours=3),
            Reading.power_kw < 2.0,  # exclude severe historical outliers
        )
        .one()
    )
    avg, n = q
    # Default fallback if under 12 samples
    fallback = 0.4
    return (float(avg) if (avg is not None and n >= 12) else fallback), (n or 0)


def detect(db: Session, room: Room, ts: dt.datetime, p: float, st: str) -> None:
    """Timetable-aware anomaly detection (room-level only).
    Wording uses 'investigate' rather than 'waste'.
    """
    if getattr(room, "level", "room") != "room":
        return  # Building or floor level meters must NEVER trigger room anomalies

    rows = (
        db.query(Reading)
        .filter(Reading.room_id == room.id, Reading.ts <= ts)
        .order_by(Reading.ts.desc())
        .limit(7)
        .all()
    )
    last3 = rows[:3]
    prev = rows[1:7]
    base, n = baseline(db, room.id, st, ts)
    kind = None

    # Rule A: Sustained off-hours / free-period usage (3 consecutive readings above threshold)
    if len(last3) == 3 and all(r.status == st for r in last3):
        thr = max(1.8 * base, base + 0.6)
        if all(r.power_kw > thr for r in last3):
            if st in ("Free", "Break"):
                kind = "Consumption during free period"
            elif st == "Off" and (ts.hour < 7 or ts.hour >= 19 or ts.weekday() == 6):
                kind = "Night-time consumption"

    # Rule B: Sudden power spike (> 3x recent average during active occupancy periods)
    if not kind and len(prev) >= 4 and all(r.status == st for r in prev) and st == "Occupied" and p > 1.2:
        avg = sum(r.power_kw for r in prev) / len(prev)
        if p > 3.0 * avg:
            kind = "Sudden power spike"

    if not kind:
        return

    # Check if an open alert of this kind already exists for this room
    if db.query(Alert).filter_by(room_id=room.id, kind=kind, status="open").first():
        return

    mins = (
        int((last3[0].ts - last3[2].ts).total_seconds() / 60)
        if kind != "Sudden power spike" and len(last3) >= 3
        else 0
    )
    if mins:
        why = (
            f"Timetable status was '{st}' for {mins} minutes, but average power stayed at "
            f"{p:.1f} kW against a historical {st} baseline of {base:.1f} kW."
        )
    else:
        recent_avg = sum(r.power_kw for r in prev) / len(prev) if prev else base
        why = (
            f"Power jumped to {p:.1f} kW from a recent average of {recent_avg:.1f} kW "
            f"with no change in schedule."
        )

    if n < 12:
        why += " (baseline from default: little history — please investigate)"
    else:
        why += " Please investigate whether equipment was left on or an unrecorded activity occurred."

    db.add(
        Alert(
            room_id=room.id,
            ts=ts,
            kind=kind,
            severity="High" if p > 3 * base else "Medium",
            power=round(p, 2),
            baseline=round(base, 2),
            explanation=why,
            action=(
                "Check whether equipment or lighting is running legitimately. "
                "If it is a scheduled meeting or workshop, add a timetable exception."
            ),
        )
    )


def ingest(
    db: Session,
    room: Room,
    ts: dt.datetime,
    p: float,
    hours: float,
    sim: bool = True,
    data_source: Optional[str] = None,
    voltage: Optional[float] = None,
    current_a: Optional[float] = None,
) -> None:
    """Ingest a room reading and run anomaly detection.

    data_source: 'simulated', 'hardware', or 'manual'.
    """
    st = status_at(db, room.id, ts)
    source_str = data_source or ("simulated" if sim else "hardware")
    db.add(
        Reading(
            room_id=room.id,
            ts=ts,
            power_kw=round(p, 3),
            energy_kwh=round(p * hours, 4),
            status=st,
            simulated=sim,
            data_source=source_str,
            voltage=voltage,
            current_a=current_a,
        )
    )
    room.last_seen = time.time()
    db.flush()
    detect(db, room, ts, p, st)


def sim_loop(SessionLocal) -> None:
    """Simulator background loop."""
    while True:
        time.sleep(2)
        if not SIM["on"]:
            continue
        db: Session = SessionLocal()
        try:
            if SIM["clock"] is None:
                SIM["clock"] = db.query(func.max(Reading.ts)).scalar() or dt.datetime.now()

            SIM["clock"] += dt.timedelta(minutes=SIM["step"])
            ts = SIM["clock"]

            rooms = db.query(Room).all()
            for r in rooms:
                p = profile(r.rtype, status_at(db, r.id, ts), ts.hour)
                # Check injected load
                inj = SIM["inject"].get(r.id)
                if inj:
                    ticks = inj.get("ticks", 0) if isinstance(inj, dict) else inj
                    add_kw = inj.get("kw", 2.4) if isinstance(inj, dict) else 2.4
                    if ticks > 0:
                        p += add_kw
                        if isinstance(inj, dict):
                            inj["ticks"] -= 1
                        else:
                            SIM["inject"][r.id] -= 1
                ingest(db, r, ts, p, SIM["step"] / 60)

            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
