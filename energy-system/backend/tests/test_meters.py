def test_meters_crud_and_enable(client, admin_token):
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}
    
    # 1. Create a building level meter
    res = client.post(
        "/api/meters",
        json={
            "meter_id": "METER_BLD_A_MAIN",
            "name": "Block A Main Meter",
            "measurement_level": "building",
            "block": "A",
            "data_source": "hardware",
            "enabled": True,
        },
        headers=admin_hdr,
    )
    assert res.status_code == 201
    meter_data = res.json()
    mid = meter_data["id"]
    assert meter_data["measurement_level"] == "building"
    assert meter_data["data_source"] == "hardware"
    
    # 2. Disable meter
    res = client.patch(f"/api/meters/{mid}/disable", headers=admin_hdr)
    assert res.status_code == 200
    assert res.json()["enabled"] is False
    
    # 3. Enable meter
    res = client.patch(f"/api/meters/{mid}/enable", headers=admin_hdr)
    assert res.status_code == 200
    assert res.json()["enabled"] is True
    
    # 4. Filter meters
    res = client.get("/api/meters?measurement_level=building", headers=admin_hdr)
    assert res.status_code == 200
    meters = res.json()
    assert any(m["id"] == mid for m in meters)
    
    # 5. Clean up
    res = client.delete(f"/api/meters/{mid}", headers=admin_hdr)
    assert res.status_code == 204
