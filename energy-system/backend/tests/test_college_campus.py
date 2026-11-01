"""Tests verifying the realistic college campus layout and deterministic timetables."""

import pytest
from app.models import Block, Department, Floor, Meter, Room, Timetable


def test_campus_blocks_and_floors(db_session):
    blocks = {b.name: len(b.floors) for b in db_session.query(Block).all()}
    # Requirement: A 3 floors, B 4 floors, C 3 floors, D 3 floors
    assert blocks["A"] == 3
    assert blocks["B"] == 4
    assert blocks["C"] == 3
    assert blocks["D"] == 3


def test_b101_seminar_hall_is_demo_room(db_session):
    b101 = db_session.query(Room).filter_by(name="B101").first()
    assert b101 is not None
    assert b101.block == "B"
    assert b101.floor == 1
    assert b101.rtype == "Seminar Hall"


def test_department_room_associations(db_session):
    # Check that rooms have associated departments
    rooms = db_session.query(Room).all()
    assert len(rooms) >= 49
    for r in rooms:
        assert r.department_id is not None
        assert r.department is not None

    # Check key departments exist
    dept_names = [d.name for d in db_session.query(Department).all()]
    assert any("Computer Science and Engineering" in name for name in dept_names)
    assert any("Biotechnology" in name for name in dept_names)
    assert any("Mechatronics" in name for name in dept_names)
    assert any("Civil Engineering" in name for name in dept_names)


def test_b101_timetable_exact_schedule(db_session):
    """Verify B101 Seminar Hall schedule matches specification exactly."""
    b101 = db_session.query(Room).filter_by(name="B101").first()
    assert b101 is not None

    tt_slots = {
        (t.day, t.hour): (t.status, t.activity)
        for t in db_session.query(Timetable).filter_by(room_id=b101.id).all()
    }

    # Mon-Fri (days 0 to 4)
    for day in range(5):
        # 09:00-11:00 Occupied: Guest lecture / workshop
        assert tt_slots[(day, 9)][0] == "Occupied"
        assert tt_slots[(day, 10)][0] == "Occupied"
        # 11:00-12:00 Free
        assert tt_slots[(day, 11)][0] == "Free"
        # 12:00-13:00 Occupied: Department seminar
        assert tt_slots[(day, 12)][0] == "Occupied"
        # 13:00-14:00 Break: Lunch
        assert tt_slots[(day, 13)][0] == "Break"
        # 14:00-16:00 Occupied: Placement talk / technical event
        assert tt_slots[(day, 14)][0] == "Occupied"
        assert tt_slots[(day, 15)][0] == "Occupied"
        # 16:00-17:00 Free
        assert tt_slots[(day, 16)][0] == "Free"

    # Saturday (day 5)
    assert tt_slots[(5, 10)][0] == "Occupied"
    assert tt_slots[(5, 11)][0] == "Occupied"
    assert tt_slots[(5, 9)][0] == "Free"
    assert tt_slots[(5, 12)][0] == "Free"


def test_a204_free_at_10_on_weekdays(db_session):
    """A204 (CSE lab) must be Free from 10:00 to 11:00 every weekday."""
    a204 = db_session.query(Room).filter_by(name="A204").first()
    assert a204 is not None

    tt_slots = {
        (t.day, t.hour): t.status
        for t in db_session.query(Timetable).filter_by(room_id=a204.id).all()
    }
    for day in range(5):
        assert tt_slots[(day, 10)] == "Free", f"A204 day {day} hour 10 was not Free"


def test_no_timetable_gaps_or_overlaps(db_session):
    """Every room must have exactly 8 slots per day (09:00-17:00 for 7 days = 56 slots)."""
    rooms = db_session.query(Room).all()
    for rm in rooms:
        slots = db_session.query(Timetable).filter_by(room_id=rm.id).all()
        assert len(slots) == 56, f"Room {rm.name} has {len(slots)} slots, expected 56"
        pairs = set((t.day, t.hour) for t in slots)
        assert len(pairs) == 56, f"Room {rm.name} has duplicate timetable hours"


def test_floor_and_building_meters_exist_and_isolated(db_session):
    """Floor-level meters on Block B and building-level meters per block exist."""
    # Block B floor meters (Floor 1, 2, 3, 4)
    b_floors = db_session.query(Meter).filter_by(measurement_level="floor", block="B").all()
    assert len(b_floors) == 4

    # Building level meters (A, B, C, D)
    bld_meters = db_session.query(Meter).filter_by(measurement_level="building").all()
    assert len(bld_meters) == 4
    blocks_with_meters = set(m.block for m in bld_meters)
    assert blocks_with_meters == {"A", "B", "C", "D"}

