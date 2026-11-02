"""Comprehensive test suite for AI Energy Assistant.

Tests:
1. Status, usage, timetable, and alerts across every Block (A, B, C, D) and departments.
2. Permission scoping: Admin access vs Block A consumer (C102 / Block B denied without data leak).
3. Ambiguity & unknown entity handling.
4. Explanations for alerts (Seminar Hall B101, Room A204).
5. Follow-up conversation context.
"""

import pytest
from app.simulator import SIM


@pytest.fixture(autouse=True)
def reset_sim():
    SIM["clock"] = None
    SIM["on"] = False
    yield
    SIM["clock"] = None
    SIM["on"] = False


@pytest.mark.parametrize("room_code, expected_block", [
    ("A204", "A"),
    ("B101", "B"),
    ("C102", "C"),
    ("D301", "D"),
])
def test_assistant_room_status_all_blocks(client, admin_token, room_code, expected_block):
    """Test that any room across all blocks can be queried by admin."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/assistant", json={"q": f"What is the status of room {room_code}?"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "a" in data
    assert f"Room {room_code}" in data["a"]
    assert "kW" in data["a"]
    assert "estimate" in data["a"].lower()


@pytest.mark.parametrize("dept_query, expected_dept_substr", [
    ("CSE", "Computer Science"),
    ("Civil", "Civil"),
    ("ECE", "Electronics"),
    ("Biotechnology", "Biotechnology"),
    ("MCT", "Mechatronics"),
])
def test_assistant_department_queries(client, admin_token, dept_query, expected_dept_substr):
    """Test that any department can be queried."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/assistant", json={"q": f"How much power is {dept_query} department using today?"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert expected_dept_substr in data["a"]
    assert "kWh" in data["a"]
    assert "estimate" in data["a"].lower()


def test_consumer_permission_boundary_enforced(client, consumer_token):
    """A Block A consumer asking about C102 or Block B must receive access denied with no data."""
    headers = {"Authorization": f"Bearer {consumer_token}"}

    # Query room in Block C
    res = client.post("/api/assistant", json={"q": "What is the status of room C102?"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "Access denied" in data["a"]
    assert "kW" not in data["a"]
    assert "kWh" not in data["a"]

    # Query Block B
    res_b = client.post("/api/assistant", json={"q": "How much energy did Block B use today?"}, headers=headers)
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert "Access denied" in data_b["a"]


def test_consumer_can_query_own_block(client, consumer_token):
    """A Block A consumer can query A204 in their assigned block."""
    headers = {"Authorization": f"Bearer {consumer_token}"}
    res = client.post("/api/assistant", json={"q": "What is the power draw of A204?"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "Room A204" in data["a"]
    assert "Access denied" not in data["a"]


def test_ambiguous_room_query(client, admin_token):
    """Querying an ambiguous generic term lists candidate rooms rather than guessing."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/assistant", json={"q": "Tell me about lab"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "multiple rooms" in data["a"].lower() or "specify" in data["a"].lower()


def test_alert_explanation_a204(client, admin_token):
    """Verify alert explanation for A204 using stored alert data."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Trigger Scenario 3 for A204
    client.post("/api/demo/scenario", json={"scenario": 3}, headers=headers)

    res = client.post("/api/assistant", json={"q": "Why was an alert raised for A204?"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "A204" in data["a"]
    assert "baseline" in data["a"].lower()
    assert "kW" in data["a"]


def test_alert_explanation_seminar_hall(client, admin_token):
    """Verify alert explanation for B101 seminar hall."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Trigger Scenario 1 for B101
    client.post("/api/demo/scenario", json={"scenario": 1}, headers=headers)

    res = client.post("/api/assistant", json={"q": "Why was an alert raised for the seminar hall?"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "B101" in data["a"]
    assert "investigate" in data["a"].lower() or "baseline" in data["a"].lower()


def test_timetable_inquiry(client, admin_token):
    """Verify timetable inquiry for a room."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/assistant", json={"q": "Is B101 free now?"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "B101" in data["a"]
    assert "scheduled as" in data["a"].lower() or "status" in data["a"].lower()


def test_compare_departments(client, admin_token):
    """Verify comparison between two departments."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/assistant", json={"q": "Compare CSE vs ECE this week"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "Comparison" in data["a"]
    assert "kWh" in data["a"]


def test_follow_up_conversation_context(client, admin_token):
    """Verify follow-up questions preserve context."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Step 1: Ask about Room C101
    r1 = client.post("/api/assistant", json={"q": "Status of room C101"}, headers=headers)
    assert r1.status_code == 200
    ctx = r1.json().get("context")

    # Step 2: Follow up with "and yesterday?"
    r2 = client.post("/api/assistant", json={"q": "and yesterday?", "context": ctx}, headers=headers)
    assert r2.status_code == 200
    data2 = r2.json()
    assert "C101" in data2["a"]
    assert "yesterday" in data2["a"].lower()


def test_ranking_target_vs_scope_filter(client, admin_token):
    """Verify target vs scope filter separation:
    - 'which room consumes more power in A block' returns a room in Block A and scope is Block A rooms, today.
    - 'which block uses the most power today' returns a block.
    - 'which room uses the most in CSE' returns a CSE room.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Room in A block
    r1 = client.post("/api/assistant", json={"q": "which room consumes more power in A block"}, headers=headers)
    assert r1.status_code == 200
    d1 = r1.json()
    assert "Block A" in d1["a"]
    assert "A" in d1["a"]  # Contains an A block room like A204 or A101
    assert "kWh" in d1["a"]
    assert "kW" in d1["a"] or "demand" in d1["a"]
    assert "Block A rooms, today" in d1["scope"]

    # 2. Block ranking
    r2 = client.post("/api/assistant", json={"q": "which block uses the most power today"}, headers=headers)
    assert r2.status_code == 200
    d2 = r2.json()
    assert "Block" in d2["a"]
    assert "kWh" in d2["a"]
    assert "Campus blocks, today" in d2["scope"]

    # 3. Room in CSE department
    r3 = client.post("/api/assistant", json={"q": "which room uses the most in CSE"}, headers=headers)
    assert r3.status_code == 200
    d3 = r3.json()
    assert "kWh" in d3["a"]
    assert "CSE" in d3["scope"] or "Computer Science" in d3["scope"]


def test_alert_inquiry_when_no_alerts_raised(client, admin_token):
    """When a room has no alerts, the assistant states 'No alerts have been raised for Room ...',
    and provides latest reading, timetable status, and normal baseline.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post("/api/assistant", json={"q": "Why was an alert raised for C303?"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "No alerts have been raised for Room C303" in data["a"]
    assert "Current power draw" in data["a"]
    assert "Timetable status now" in data["a"]
    assert "Normal baseline draw" in data["a"]


