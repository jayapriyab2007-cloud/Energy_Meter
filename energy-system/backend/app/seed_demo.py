"""Demo seed data.

This script only runs when ENV=development (the default) AND the database is
empty (no users exist).  It is clearly labelled as demo data and will never
overwrite an existing database.

The LAYOUT constant is kept here only for seeding purposes and is no longer
used in the application logic.  Production data should be managed through the
admin UI and Alembic migrations.
"""

import datetime as dt
import os
import random

from .models import Block, Department, Floor, Meter, Room, Timetable, User, Reading
from .auth import hash_password

# ---------------------------------------------------------------------------
# Demo layout: block_name -> (num_floors, rooms_per_floor)
# This is DEMO DATA ONLY – not application logic.
# ---------------------------------------------------------------------------
DEMO_LAYOUT = {
    "A": (2, 4),
    "B": (3, 4),
    "C": (2, 3),
    "D": (3, 4),
}

DEMO_DEPARTMENTS = ["Computer Science", "Electronics", "Mechanical", "Civil"]

STATUS_LABELS = {
    "Occupied": "Class",
    "Free": "No scheduled class",
    "Break": "Lunch",
}

# In-memory timetable cache for seeding
_TT: dict = {}


def _status_at(rid: int, ts: dt.datetime) -> str:
    return _TT.get(rid, {}).get((ts.weekday(), ts.hour), "Off")


def _profile(rtype: str, st: str, hour: int) -> float:
    if hour < 7 or hour >= 19:
        base = 0.15
    elif st == "Occupied":
        base = 4.0 if rtype == "Lab" else 2.0
    else:
        base = 0.3
    return max(0.05, random.gauss(base, base * 0.08))


def seed_demo(db) -> None:
    """Seed demo data if ENV=development and DB is empty."""
    env = os.getenv("ENV", "development")
    if env != "development":
        return
    if db.query(User).count():
        return   # DB already seeded – never overwrite

    random.seed(1)

    # --- Users (demo credentials, dev only) ---
    admin_pw = hash_password("admin123")
    consumer_pw = hash_password("consumer123")
    admin = User(username="admin", pw=admin_pw, role="admin")
    consumer = User(username="consumer", pw=consumer_pw, role="consumer", block="A")
    db.add_all([admin, consumer])
    db.flush()

    # --- Departments ---
    depts = {}
    for i, dname in enumerate(DEMO_DEPARTMENTS):
        d = Department(name=dname)
        db.add(d)
        db.flush()
        depts[i] = d

    # --- Blocks, floors, rooms, meters, timetables, historical readings ---
    mid = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for b_name, (num_floors, per_floor) in DEMO_LAYOUT.items():
        # Block
        blk = Block(name=b_name, description=f"Demo block {b_name}", manager_user_id=admin.id)
        db.add(blk)
        db.flush()

        for f_num in range(1, num_floors + 1):
            # Floor
            fl = Floor(block_id=blk.id, number=f_num, label=f"Floor {f_num}")
            db.add(fl)
            db.flush()

            for n in range(1, per_floor + 1):
                rtype = "Lab" if n == per_floor else "Classroom"
                room_name = f"{b_name}{f_num}{n:02d}"

                # Room (legacy meter_id kept for backward compat)
                r = Room(
                    name=room_name,
                    block=b_name,
                    floor=f_num,
                    rtype=rtype,
                    meter_id=f"METER_{room_name}",
                    level="room",
                    department_id=depts[(ord(b_name) - ord("A")) % len(depts)].id,
                )
                db.add(r)
                db.flush()

                # Meter record
                meter = Meter(
                    meter_id=f"METER_{room_name}",
                    name=f"Meter {room_name}",
                    measurement_level="room",
                    block=b_name,
                    floor=f_num,
                    room_id=r.id,
                    data_source="simulated",
                    enabled=True,
                )
                db.add(meter)

                # Timetable (Mon–Sun, 09:00–16:00)
                _TT[r.id] = {}
                for day in range(7):
                    for hour in range(9, 17):
                        if hour == 13:
                            st = "Break"
                        elif random.random() < 0.25:
                            st = "Free"
                        else:
                            st = "Occupied"
                        tt = Timetable(
                            room_id=r.id,
                            day=day,
                            hour=hour,
                            activity=STATUS_LABELS[st],
                            status=st,
                        )
                        db.add(tt)
                        _TT[r.id][(day, hour)] = st

                # Historical readings (7 days back to now)
                t = mid - dt.timedelta(days=7)
                while t <= mid + dt.timedelta(hours=8):
                    st = _status_at(r.id, t)
                    p = _profile(rtype, st, t.hour)
                    db.add(
                        Reading(
                            room_id=r.id,
                            ts=t,
                            power_kw=round(p, 3),
                            energy_kwh=round(p, 4),
                            status=st,
                            simulated=True,
                        )
                    )
                    t += dt.timedelta(hours=1)

    db.commit()
    print("[seed_demo] Demo data inserted successfully (ENV=development).")

