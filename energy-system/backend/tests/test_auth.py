def test_login_success(client):
    res = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["role"] == "admin"

def test_login_invalid(client):
    res = client.post("/api/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == 401

def test_consumer_login(client):
    res = client.post("/api/login", json={"username": "consumer", "password": "consumer123"})
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "consumer"
    assert data["block"] == "A"
