"""Tests for POST /api/manual-readings and manual ingestion pipeline."""

import datetime as dt
import pytest
from app.models import Alert, Meter, Reading, Room, Timetable
from app.simulator import SIM


@pytest.fixture(autouse=True)
def reset_sim():
    SIM["clock"] = None
    SIM["on"] = False
    yield
    SIM["clock"] = None


def test_consumer_forbidden_from_manual_readings(client, consumer_token):
    headers = {"Authorization": f"Bearer {consumer_token}"}
    payload = {
        "room": "A204",
        "power_kw": 2.5,
    }
    res = client.post("/api/manual-readings", json=payload, headers=headers)
    assert res.status_code == 403


def test_invalid_parameters_validation(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Power > 100
    res1 = client.post(
        "/api/manual-readings",
        json={"room": "A204", "power_kw": 105.0},
        headers=headers,
    )
    assert res1.status_code == 422

    # 2. Power < 0
    res2 = client.post(
        "/api/manual-readings",
        json={"room": "A204", "power_kw": -1.0},
        headers=headers,
    )
    assert res2.status_code == 422

    # 3. Invalid repeat count (e.g. 5)
    res3 = client.post(
        "/api/manual-readings",
        json={"room": "A204", "power_kw": 2.0, "repeat_count": 5},
        headers=headers,
    )
    assert res3.status_code == 422

    # 4. Timestamp > 5 minutes in future
    future_time = (dt.datetime.now() + dt.timedelta(minutes=15)).isoformat()
    res4 = client.post(
        "/api/manual-readings",
        json={"room": "A204", "power_kw": 2.0, "ts": future_time},
        headers=headers,
    )
    assert res4.status_code == 422


def test_disabled_meter_rejected(client, admin_token, db_session):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Find meter for C101 and disable it
    room = db_session.query(Room).filter_by(name="C101").first()
    meter = db_session.query(Meter).filter_by(room_id=room.id, measurement_level="room").first()
    meter.enabled = False
    db_session.commit()

    res = client.post(
        "/api/manual-readings",
        json={"room": "C101", "power_kw": 1.5},
        headers=headers,
    )
    assert res.status_code == 400
    assert "disabled" in res.text.lower()

    # Re-enable
    meter.enabled = True
    db_session.commit()


def test_free_period_alert_triggered_by_manual_readings(client, admin_token, db_session):
    """3 readings of 2.4 kW in a Free slot raise exactly 1 free-period alert."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Stop simulator to isolate manual readings
    client.post("/api/sim/stop", headers=headers)

    # Find a free slot for A204
    room = db_session.query(Room).filter_by(name="A204").first()
    # Clear any existing alerts for A204
    db_session.query(Alert).filter_by(room_id=room.id).delete()
    db_session.commit()

    # Find a Free slot in timetable
    tt = db_session.query(Timetable).filter_by(room_id=room.id, status="Free").first()
    assert tt is not None

    # Pick a past date that matches tt.day
    today = dt.date.today()
    days_back = (today.weekday() - tt.day) % 7
    if days_back == 0:
        days_back = 7
    target_date = today - dt.timedelta(days=days_back)
    target_dt = dt.datetime(target_date.year, target_date.month, target_date.day, tt.hour, 30)

    # Submit 3 readings of 2.4 kW spaced by 5 minutes
    res = client.post(
        "/api/manual-readings",
        json={
            "room": "A204",
            "power_kw": 2.4,
            "ts": target_dt.isoformat(),
            "repeat_count": 3,
            "interval_min": 5.0,
            "voltage": 230.0,
            "current_a": 10.4,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["readings_stored"] == 3
    assert data["timetable_status"] == "Free"
    assert data["new_alerts_count"] == 1
    assert data["alerts"][0]["kind"] in ("Consumption during free period", "Free-Period Consumption", "Equipment Left On")


def test_normal_draw_during_free_period_raises_no_alert(client, admin_token, db_session):
    """3 readings of normal draw (0.1 kW) during Free period raise 0 alerts."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    room = db_session.query(Room).filter_by(name="B102").first()
    db_session.query(Alert).filter_by(room_id=room.id).delete()
    db_session.commit()

    tt = db_session.query(Timetable).filter_by(room_id=room.id, status="Free").first()
    assert tt is not None
    today = dt.date.today()
    days_back = (today.weekday() - tt.day) % 7
    if days_back == 0:
        days_back = 7
    target_date = today - dt.timedelta(days=days_back)
    target_dt = dt.datetime(target_date.year, target_date.month, target_date.day, tt.hour, 35)

    res = client.post(
        "/api/manual-readings",
        json={
            "room": "B102",
            "power_kw": 0.1,  # Below idle/free threshold
            "ts": target_dt.isoformat(),
            "repeat_count": 3,
            "interval_min": 5.0,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["readings_stored"] == 3
    assert data["new_alerts_count"] == 0


def test_night_time_consumption_alert(client, admin_token, db_session):
    """Reading at 22:15 (outside timetable / night) raises an alert."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    room = db_session.query(Room).filter_by(name="B101").first()
    db_session.query(Alert).filter_by(room_id=room.id).delete()
    db_session.commit()

    yesterday = dt.date.today() - dt.timedelta(days=1)
    night_dt = dt.datetime(yesterday.year, yesterday.month, yesterday.day, 22, 15)
    res = client.post(
        "/api/manual-readings",
        json={
            "room": "B101",
            "power_kw": 3.0,
            "ts": night_dt.isoformat(),
            "repeat_count": 3,
            "interval_min": 5.0,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["new_alerts_count"] == 1
    assert data["alerts"][0]["kind"] in ("Night-time consumption", "Night-Time Anomaly", "Equipment Left On")


def test_chart_endpoint_returns_manual_source(client, admin_token, db_session):
    """Verify that room live points return source='manual'."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    room = db_session.query(Room).filter_by(name="C102").first()
    past_time = dt.datetime.now() - dt.timedelta(hours=1)

    res = client.post(
        "/api/manual-readings",
        json={
            "room": "C102",
            "power_kw": 1.8,
            "ts": past_time.isoformat(),
            "repeat_count": 1,
        },
        headers=headers,
    )
    assert res.status_code == 200

    # Fetch live points
    res_live = client.get(f"/api/rooms/{room.id}/live", headers=headers)
    assert res_live.status_code == 200
    points = res_live.json()["points"]
    # Check that at least one point has source == 'manual'
    manual_pts = [p for p in points if p.get("source") == "manual"]
    assert len(manual_pts) >= 1
    assert manual_pts[-1]["kw"] == 1.8


def test_duplicate_timestamp_ignored(client, admin_token, db_session):
    """Duplicate timestamp for the same room should be safely ignored."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    room = db_session.query(Room).filter_by(name="A101").first()
    sample_dt = dt.datetime.now() - dt.timedelta(hours=2)

    # First send
    r1 = client.post(
        "/api/manual-readings",
        json={"room": "A101", "power_kw": 0.5, "ts": sample_dt.isoformat(), "repeat_count": 1},
        headers=headers,
    )
    assert r1.status_code == 200
    assert r1.json()["readings_stored"] == 1

    # Second send with identical timestamp
    r2 = client.post(
        "/api/manual-readings",
        json={"room": "A101", "power_kw": 0.5, "ts": sample_dt.isoformat(), "repeat_count": 1},
        headers=headers,
    )
    assert r2.status_code == 200
    # Duplicate is ignored
    assert r2.json()["readings_stored"] == 0


def test_e2e_manual_reading_to_assistant_explanation(client, admin_token, db_session):
    """End-to-end: Manual input triggers an alert -> Assistant explains why."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    room = db_session.query(Room).filter_by(name="C201").first()
    db_session.query(Alert).filter_by(room_id=room.id).delete()
    db_session.commit()

    yesterday = dt.date.today() - dt.timedelta(days=1)
    night_dt = dt.datetime(yesterday.year, yesterday.month, yesterday.day, 23, 15)
    res_input = client.post(
        "/api/manual-readings",
        json={
            "room": "C201",
            "power_kw": 4.5,
            "ts": night_dt.isoformat(),
            "repeat_count": 3,
            "interval_min": 5.0,
        },
        headers=headers,
    )
    assert res_input.status_code == 200
    assert res_input.json()["new_alerts_count"] == 1

    # Now ask the assistant
    res_ast = client.post(
        "/api/assistant",
        json={"q": "Why was an alert raised for C201?"},
        headers=headers,
    )
    assert res_ast.status_code == 200
    ast_data = res_ast.json()
    assert "C201" in ast_data["a"]
    assert "Measured draw" in ast_data["a"]
    assert "baseline" in ast_data["a"].lower()
    assert "investigate" in ast_data["a"].lower() or "suggested action" in ast_data["a"].lower()
