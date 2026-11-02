"""Seed demo dataset for realistic college campus with deterministic timetable and history.

Features:
- Campus structure read from backend/app/demo_data/campus_demo.json:
    * Block A (3 floors: Admin, CSE, CSD/IT)
    * Block B (4 floors: Biotech/MCT/ECE, B101 Seminar Hall)
    * Block C (3 floors: Civil, EEE, Automobile)
    * Block D (3 floors: Academic Block, Basic Sciences)
- Meters:
    * Room-level meter for every room (METER_<room_code>, data_source=simulated)
    * Floor-level meters for every floor in Block B
    * Building-level meters for Blocks A, B, C, D
- Timetables loaded from backend/app/demo_data/timetable_demo.csv
- 14 days of realistic hourly history consistent with timetables and power profiles
- Each status sampled >= 12 times so baseline is learned from data
- Labelled explicitly as demo data
"""

import csv
import datetime as dt
import json
import os
import random

from sqlalchemy.orm import Session

from .auth import hash_password
from .models import (
    Block,
    Department,
    Floor,
    Meter,
    Reading,
    Room,
    Timetable,
    User,
)
from .simulator import profile

DEMO_DATA_DIR = os.path.join(os.path.dirname(__file__), "demo_data")


def seed_demo(db: Session, force: bool = False) -> None:
    """Seed demo data if database is empty or force=True."""
    env = os.getenv("ENV", "development")
    if env != "development" and not force:
        return

    # Check if already seeded
    if not force and db.query(User).count() > 0:
        return

    print("[seed_demo] Initializing realistic college demo dataset...")
    random.seed(42)  # Deterministic variation for historical Gaussian noise

    # 1. Users
    admin = db.query(User).filter_by(username="admin").first()
    if not admin:
        admin = User(username="admin", pw=hash_password("admin123"), role="admin")
        db.add(admin)
        db.flush()

    consumer = db.query(User).filter_by(username="consumer").first()
    if not consumer:
        consumer = User(username="consumer", pw=hash_password("consumer123"), role="consumer", block="A")
        db.add(consumer)
        db.flush()

    # 2. Campus layout from JSON
    campus_path = os.path.join(DEMO_DATA_DIR, "campus_demo.json")
    with open(campus_path, "r", encoding="utf-8") as f:
        campus = json.load(f)

    # Departments
    dept_map = {}
    for d_data in campus["departments"]:
        dept = db.query(Department).filter_by(name=d_data["name"]).first()
        if not dept:
            dept = Department(name=d_data["name"])
            db.add(dept)
            db.flush()
        dept_map[d_data["name"]] = dept

    # Blocks, Floors, Rooms, Meters
    room_code_to_obj = {}
    for b_data in campus["blocks"]:
        blk = db.query(Block).filter_by(name=b_data["name"]).first()
        if not blk:
            blk = Block(name=b_data["name"], description=b_data["description"], manager_user_id=admin.id)
            db.add(blk)
            db.flush()

        # Building level meter
        b_meter_id = f"METER_BLD_{b_data['name']}_MAIN"
        if not db.query(Meter).filter_by(meter_id=b_meter_id).first():
            db.add(
                Meter(
                    meter_id=b_meter_id,
                    name=f"Block {b_data['name']} Main Meter",
                    measurement_level="building",
                    block=b_data["name"],
                    data_source="simulated",
                    enabled=True,
                )
            )

        for f_data in b_data["floors"]:
            fl = db.query(Floor).filter_by(block_id=blk.id, number=f_data["number"]).first()
            if not fl:
                fl = Floor(block_id=blk.id, number=f_data["number"], label=f_data["label"])
                db.add(fl)
                db.flush()

            # Floor level meter for B Block
            if b_data["name"] == "B":
                fl_meter_id = f"METER_B_FL{f_data['number']}"
                if not db.query(Meter).filter_by(meter_id=fl_meter_id).first():
                    db.add(
                        Meter(
                            meter_id=fl_meter_id,
                            name=f"Block B Floor {f_data['number']} Meter",
                            measurement_level="floor",
                            block="B",
                            floor=f_data["number"],
                            data_source="simulated",
                            enabled=True,
                        )
                    )

            for r_data in f_data["rooms"]:
                code = r_data["code"]
                rm = db.query(Room).filter_by(name=code).first()
                dept_obj = dept_map.get(r_data["dept"])
                if not rm:
                    rm = Room(
                        name=code,
                        block=b_data["name"],
                        floor=f_data["number"],
                        rtype=r_data["type"],
                        meter_id=f"METER_{code}",
                        level="room",
                        department_id=dept_obj.id if dept_obj else None,
                    )
                    db.add(rm)
                    db.flush()
                room_code_to_obj[code] = rm

                # Room level meter
                r_meter_id = f"METER_{code}"
                if not db.query(Meter).filter_by(meter_id=r_meter_id).first():
                    db.add(
                        Meter(
                            meter_id=r_meter_id,
                            name=f"{r_data['name']} Meter",
                            measurement_level="room",
                            block=b_data["name"],
                            floor=f_data["number"],
                            room_id=rm.id,
                            data_source="simulated",
                            enabled=True,
                        )
                    )

    db.flush()

    # 3. Timetables from CSV
    tt_path = os.path.join(DEMO_DATA_DIR, "timetable_demo.csv")
    existing_tt_count = db.query(Timetable).count()
    room_tt_status = {}  # (room_id, day, hour) -> (status, activity)

    if existing_tt_count == 0:
        with open(tt_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            tt_objs = []
            for row in reader:
                code = row["room_code"]
                rm = room_code_to_obj.get(code)
                if not rm:
                    continue
                day = int(row["day"])
                hour = int(row["hour"])
                status = row["status"]
                activity = row["activity"]

                tt_objs.append(
                    Timetable(
                        room_id=rm.id,
                        day=day,
                        hour=hour,
                        activity=activity,
                        status=status,
                    )
                )
                room_tt_status[(rm.id, day, hour)] = status
            db.bulk_save_objects(tt_objs)
            db.flush()
    else:
        for t in db.query(Timetable).all():
            room_tt_status[(t.room_id, t.day, t.hour)] = t.status

    # 4. Seed 14 Days History (Hourly, up to current hour)
    existing_readings = db.query(Reading).count()
    if existing_readings == 0:
        print("[seed_demo] Seeding 14 days of historical readings...")
        now_dt = dt.datetime.now()
        today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = today_start - dt.timedelta(days=14)

        readings_to_add = []
        curr = start_date
        all_rooms = list(room_code_to_obj.values())

        while curr <= now_dt:
            day = curr.weekday()
            hour = curr.hour
            for rm in all_rooms:
                st = room_tt_status.get((rm.id, day, hour), "Off")
                p = profile(rm.rtype, st, hour)
                readings_to_add.append(
                    Reading(
                        room_id=rm.id,
                        ts=curr,
                        power_kw=round(p, 3),
                        energy_kwh=round(p, 4),
                        status=st,
                        simulated=True,
                    )
                )
            curr += dt.timedelta(hours=1)

            # Flush in batches of 5000
            if len(readings_to_add) >= 5000:
                db.bulk_save_objects(readings_to_add)
                db.flush()
                readings_to_add = []

        if readings_to_add:
            db.bulk_save_objects(readings_to_add)
            db.flush()

    db.commit()
    print("[seed_demo] Realistic college demo campus successfully seeded!")
