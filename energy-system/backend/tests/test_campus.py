def test_blocks_crud(client, admin_token, consumer_token):
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}
    consumer_hdr = {"Authorization": f"Bearer {consumer_token}"}
    
    # List blocks
    res = client.get("/api/blocks", headers=consumer_hdr)
    assert res.status_code == 200
    blocks = res.json()
    assert len(blocks) >= 4  # A, B, C, D from demo seed
    
    # Create block as consumer should fail (403)
    res = client.post("/api/blocks", json={"name": "TestBlockE"}, headers=consumer_hdr)
    assert res.status_code == 403
    
    # Create block as admin
    res = client.post("/api/blocks", json={"name": "TestBlockE", "description": "New Block"}, headers=admin_hdr)
    assert res.status_code == 201
    created = res.json()
    bid = created["id"]
    assert created["name"] == "TestBlockE"
    
    # Duplicate block creation should fail (409)
    res = client.post("/api/blocks", json={"name": "TestBlockE"}, headers=admin_hdr)
    assert res.status_code == 409
    
    # Update block
    res = client.patch(f"/api/blocks/{bid}", json={"description": "Updated"}, headers=admin_hdr)
    assert res.status_code == 200
    assert res.json()["description"] == "Updated"
    
    # Floors CRUD
    res = client.post("/api/floors", json={"block_id": bid, "number": 1, "label": "Ground"}, headers=admin_hdr)
    assert res.status_code == 201
    fid = res.json()["id"]
    
    res = client.get(f"/api/floors?block_id={bid}", headers=admin_hdr)
    assert res.status_code == 200
    floors = res.json()
    assert len(floors) == 1
    
    # Departments CRUD
    res = client.post("/api/departments", json={"name": "Aerospace Dept", "block_id": bid}, headers=admin_hdr)
    assert res.status_code == 201
    did = res.json()["id"]
    
    res = client.get("/api/departments", headers=admin_hdr)
    assert res.status_code == 200
    depts = res.json()
    assert any(d["id"] == did for d in depts)
    
    # Delete floor, department, block
    assert client.delete(f"/api/floors/{fid}", headers=admin_hdr).status_code == 204
    assert client.delete(f"/api/departments/{did}", headers=admin_hdr).status_code == 204
    assert client.delete(f"/api/blocks/{bid}", headers=admin_hdr).status_code == 204
