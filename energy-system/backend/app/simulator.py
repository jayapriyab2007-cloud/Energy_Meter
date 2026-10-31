"""Simulator engine extracted from the original main.py.

Responsibilities
----------------
* ``SIM`` – shared state dict (on/off, virtual clock, injections).
* ``profile()``      – generate a plausible kW reading for a room type / timetable status.
* ``status_at()``    – look up timetable status at a given timestamp (cached in ``TT``).
* ``load_tt()``      – (re)load timetable cache for a room.
* ``baseline()``     – compute historical average power for a room/status pair.
* ``detect()``       – run anomaly detection rules and create an Alert if needed.
* ``ingest()``       – persist a reading and run detection.
* ``sim_loop()``     – background thread: advances virtual clock, calls ingest for every room.

The detection wording uses "investigate" rather than "waste" per the ground rules.
"""

import datetime as dt
import random
import time

from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import Alert, Reading, Room, Timetable

# ---------------------------------------------------------------------------
# Shared simulator state
# ---------------------------------------------------------------------------

SIM: dict = {
    "on": False,
    "clock": None,   # virtual datetime
    "step": 10,      # minutes per tick
    "inject": {},    # room_id -> remaining anomaly ticks
}

# In-memory timetable cache: room_id -> {(day, hour): status}
TT: dict = {}

STATUS_LABELS = {
    "Occupied": "Class",
    "Free": "No scheduled class",
    "Break": "Lunch",
}


# ---------------------------------------------------------------------------
# Timetable helpers
# ---------------------------------------------------------------------------


def load_tt(db: Session, rid: int) -> None:
    """Load (or reload) the timetable for room *rid* into the TT cache."""
    TT[rid] = {
        (t.day, t.hour): t.status
        for t in db.query(Timetable).filter_by(room_id=rid)
    }


def status_at(db: Session, rid: int, ts: dt.datetime) -> str:
    """Return the timetable status string for room *rid* at datetime *ts*."""
    if rid not in TT:
        load_tt(db, rid)
    return TT[rid].get((ts.weekday(), ts.hour), "Off")


# ---------------------------------------------------------------------------
# Power profile
# ---------------------------------------------------------------------------


def profile(rtype: str, st: str, hour: int) -> float:
    """Return a simulated kW draw with Gaussian noise."""
    if hour < 7 or hour >= 19:
        base = 0.15
    elif st == "Occupied":
        base = 4.0 if rtype == "Lab" else 2.0
    else:
        base = 0.3
    return max(0.05, random.gauss(base, base * 0.08))


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def baseline(db: Session, rid: int, st: str, ts: dt.datetime) -> tuple[float, int]:
    """Return (avg_power_kw, sample_count) for *rid* in timetable status *st*.

    Only looks at readings older than 3 hours so live anomalies don't skew the
    baseline.  Falls back to 0.3 kW if fewer than 12 samples exist (cold-start).
    """
    q = (
        db.query(func.avg(Reading.power_kw), func.count())
        .filter(
            Reading.room_id == rid,
            Reading.status == st,
            Reading.ts < ts - dt.timedelta(hours=3),
            Reading.power_kw < 1.0,
        )
        .one()
    )
    avg, n = q
    return (avg if n >= 12 else 0.3), n


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------


def detect(db: Session, room: Room, ts: dt.datetime, p: float, st: str) -> None:
    """Apply anomaly rules and create an Alert if warranted.

    Rules (unchanged from original):
    A  – sustained high power during free / break / off periods
    B  – sudden spike > 3x recent average with no schedule change
    Alert wording says "investigate", not "waste".
    """
    rows = (
        db.query(Reading)
        .filter(Reading.room_id == room.id, Reading.ts <= ts)
        .order_by(Reading.ts.desc())
        .limit(7)
        .all()
    )
    last3, prev = rows[:3], rows[1:7]
    base, n = baseline(db, room.id, st, ts)
    kind = None

    # Rule A – sustained off-hours / free-period use
    if len(last3) == 3 and all(r.status == st for r in last3):
        thr = max(2 * base, base + 0.8)
        if all(r.power_kw > thr for r in last3):
            if st in ("Free", "Break"):
                kind = "Consumption during free period"
            elif st == "Off" and (ts.hour < 7 or ts.hour >= 19):
                kind = "Night-time consumption"

    # Rule B – sudden spike
    if not kind and len(prev) >= 4 and all(r.status == st for r in prev) and p > 1:
        avg = sum(r.power_kw for r in prev) / len(prev)
        if p > 3 * avg:
            kind = "Sudden power spike"

    if not kind:
        return
    # Suppress if an open alert of the same type already exists for this room
    if db.query(Alert).filter_by(room_id=room.id, kind=kind, status="open").first():
        return

    mins = (
        int((last3[0].ts - last3[2].ts).total_seconds() / 60)
        if kind != "Sudden power spike"
        else 0
    )
    if mins:
        why = (
            f"Timetable status was '{st}' for {mins} minutes, but average power stayed at "
            f"{p:.1f} kW against a historical {st} baseline of {base:.1f} kW."
        )
    else:
        recent_avg = sum(r.power_kw for r in prev) / len(prev)
        why = (
            f"Power jumped to {p:.1f} kW from a recent average of {recent_avg:.1f} kW "
            f"with no change in schedule."
        )

    if n < 12:
        why += " (baseline from default: insufficient history — please investigate)"
    else:
        why += " Please investigate to determine whether use is expected."

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
                "If it is a scheduled meeting or event, add a timetable exception."
            ),
        )
    )


# ---------------------------------------------------------------------------
# Ingest helper
# ---------------------------------------------------------------------------


def ingest(
    db: Session,
    room: Room,
    ts: dt.datetime,
    p: float,
    hours: float,
    sim: bool = True,
) -> None:
    """Persist a reading and run anomaly detection."""
    st = status_at(db, room.id, ts)
    db.add(
        Reading(
            room_id=room.id,
            ts=ts,
            power_kw=round(p, 3),
            energy_kwh=round(p * hours, 4),
            status=st,
            simulated=sim,
        )
    )
    room.last_seen = time.time()
    db.flush()
    detect(db, room, ts, p, st)


# ---------------------------------------------------------------------------
# Simulator loop (background thread)
# ---------------------------------------------------------------------------


def sim_loop(SessionLocal) -> None:
    """Advance the virtual clock and emit readings for every enabled room."""
    while True:
        time.sleep(2)
        if not SIM["on"]:
            continue
        db: Session = SessionLocal()
        try:
            if SIM["clock"] is None:
                SIM["clock"] = db.query(func.max(Reading.ts)).scalar()

            SIM["clock"] += dt.timedelta(minutes=SIM["step"])
            ts = SIM["clock"]

            rooms = db.query(Room).all()
            for r in rooms:
                p = profile(r.rtype, status_at(db, r.id, ts), ts.hour)
                if SIM["inject"].get(r.id, 0) > 0:
                    p += 2.4
                    SIM["inject"][r.id] -= 1
                ingest(db, r, ts, p, SIM["step"] / 60)

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

