"""Tests for Demo scenarios, alert raising, duplicate suppression, and demo reset."""

import pytest
from app.models import Alert, Room, TimetableException


def test_demo_scenario_1_b101_free_period(client, admin_token, db_session):
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    # Reset first
    client.post("/api/demo/reset", headers=admin_hdr)

    # Trigger Scenario 1: B101 seminar hall equipment left on (11:00 Free period)
    res = client.post("/api/demo/scenario", json={"scenario": 1}, headers=admin_hdr)
    assert res.status_code == 200
    data = res.json()
    assert data["alert_created"] is True
    assert data["room"] == "B101"

    # Verify exactly 1 alert in DB for B101
    b101 = db_session.query(Room).filter_by(name="B101").first()
    alerts = db_session.query(Alert).filter_by(room_id=b101.id, status="open").all()
    assert len(alerts) == 1
    a = alerts[0]
    assert a.kind == "Consumption during free period"
    assert a.power >= 4.0
    assert "investigate" in a.explanation.lower()

    # Idempotency / Duplicate rejection: Running scenario 1 again must NOT create duplicate alerts
    res2 = client.post("/api/demo/scenario", json={"scenario": 1}, headers=admin_hdr)
    assert res2.status_code == 200
    alerts_after = db_session.query(Alert).filter_by(room_id=b101.id, status="open").all()
    assert len(alerts_after) == 1


def test_demo_scenario_2_b101_night_time(client, admin_token, db_session):
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}
    client.post("/api/demo/reset", headers=admin_hdr)

    # Trigger Scenario 2: B101 night-time consumption (22:00)
    res = client.post("/api/demo/scenario", json={"scenario": 2}, headers=admin_hdr)
    assert res.status_code == 200
    data = res.json()
    assert data["alert_created"] is True

    b101 = db_session.query(Room).filter_by(name="B101").first()
    alerts = db_session.query(Alert).filter_by(room_id=b101.id, status="open").all()
    assert len(alerts) == 1
    assert alerts[0].kind == "Night-time consumption"


def test_demo_scenario_3_a204_free_period(client, admin_token, db_session):
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}
    client.post("/api/demo/reset", headers=admin_hdr)

    # Trigger Scenario 3: A204 CSE Lab 2 Free period (10:00)
    res = client.post("/api/demo/scenario", json={"scenario": 3}, headers=admin_hdr)
    assert res.status_code == 200
    data = res.json()
    assert data["alert_created"] is True

    a204 = db_session.query(Room).filter_by(name="A204").first()
    alerts = db_session.query(Alert).filter_by(room_id=a204.id, status="open").all()
    assert len(alerts) == 1
    assert alerts[0].kind == "Consumption during free period"


def test_timetable_exception_resolves_and_suppresses_alert(client, admin_token, db_session):
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}
    client.post("/api/demo/reset", headers=admin_hdr)

    # 1. Trigger Scenario 1
    client.post("/api/demo/scenario", json={"scenario": 1}, headers=admin_hdr)
    b101 = db_session.query(Room).filter_by(name="B101").first()
    alert = db_session.query(Alert).filter_by(room_id=b101.id, status="open").first()
    assert alert is not None

    # 2. Admin adds a timetable exception
    import datetime as dt
    start_ts = alert.ts - dt.timedelta(minutes=15)
    end_ts = alert.ts + dt.timedelta(hours=2)

    res = client.post(
        "/api/demo/exception",
        json={
            "room_id": b101.id,
            "start_ts": start_ts.isoformat(),
            "end_ts": end_ts.isoformat(),
            "activity": "Setup for 12:00 seminar",
            "reason": "Audiovisual check and rehearsal",
            "alert_id": alert.id,
        },
        headers=admin_hdr,
    )
    assert res.status_code == 200

    # 3. Verify alert status is updated to legitimate with note
    db_session.refresh(alert)
    assert alert.status == "legitimate"
    assert "Setup for 12:00 seminar" in alert.note

    # 4. Verify exception is stored
    exc = db_session.query(TimetableException).filter_by(room_id=b101.id).first()
    assert exc is not None
    assert exc.activity == "Setup for 12:00 seminar"


def test_demo_reset_clears_alerts_and_restores_clean_state(client, admin_token, db_session):
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    # Trigger scenario
    client.post("/api/demo/scenario", json={"scenario": 1}, headers=admin_hdr)
    assert db_session.query(Alert).count() >= 1

    # Reset
    res = client.post("/api/demo/reset", headers=admin_hdr)
    assert res.status_code == 200
    assert db_session.query(Alert).count() == 0
    assert db_session.query(TimetableException).count() == 0

