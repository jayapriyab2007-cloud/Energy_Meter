def test_demo_flow_end_to_end(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 1. Start simulator
    res = client.post("/api/sim/start", headers=headers)
    assert res.status_code == 200
    assert res.json() is True
    
    # 2. Get rooms and find A204
    res = client.get("/api/rooms", headers=headers)
    assert res.status_code == 200
    rooms = res.json()
    assert len(rooms) > 0
    a204 = next((r for r in rooms if r["name"] == "A204"), rooms[0])
    
    # 3. Inject test anomaly
    res = client.post(
        "/api/sim/inject/anomaly",
        json={"room_id": a204["id"], "ticks": 6},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    
    # 4. Check overview
    res = client.get("/api/overview", headers=headers)
    assert res.status_code == 200
    overview = res.json()
    assert "current_kw" in overview
    assert "today_kwh" in overview
    assert "est_bill" in overview
    
    # 5. List alerts
    res = client.get("/api/alerts", headers=headers)
    assert res.status_code == 200
    alerts = res.json()
    
    # 6. Stop simulator
    res = client.post("/api/sim/stop", headers=headers)
    assert res.status_code == 200
    assert res.json() is False
