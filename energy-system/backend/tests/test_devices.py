def test_devices_and_heartbeat(client, admin_token):
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}
    
    # 1. Create a meter first
    res = client.post(
        "/api/meters",
        json={
            "meter_id": "METER_ESP32_TEST",
            "name": "Test Meter for Device",
            "measurement_level": "building",
            "block": "B",
            "data_source": "hardware",
        },
        headers=admin_hdr,
    )
    assert res.status_code == 201
    meter_id = res.json()["id"]
    
    # 2. Register an IoT device
    res = client.post(
        "/api/devices",
        json={"name": "ESP32_Test_Unit_01", "meter_id": meter_id},
        headers=admin_hdr,
    )
    assert res.status_code == 201
    dev_data = res.json()
    device_id = dev_data["id"]
    plaintext_key = dev_data["plaintext_key"]
    assert plaintext_key is not None
    
    # 3. List devices
    res = client.get("/api/devices", headers=admin_hdr)
    assert res.status_code == 200
    devices = res.json()
    assert any(d["id"] == device_id for d in devices)
    
    # 4. Device Heartbeat with wrong key should fail
    res = client.post(
        "/api/heartbeat",
        json={"device_id": device_id, "device_key": "wrong_key", "firmware_version": "v1.0.0"},
    )
    assert res.status_code == 401
    
    # 5. Device Heartbeat with correct key
    res = client.post(
        "/api/heartbeat",
        json={"device_id": device_id, "device_key": plaintext_key, "firmware_version": "v1.0.0"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    
    # 6. Verify device is online now
    res = client.get(f"/api/devices/{device_id}", headers=admin_hdr)
    assert res.status_code == 200
    assert res.json()["online"] is True
