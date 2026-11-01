import requests, datetime as dt
base = dt.datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
for i in range(3):
    ts = (base + dt.timedelta(minutes=5*i)).isoformat()
    r = requests.post("http://localhost:8000/api/ingest",
        headers={"X-Device-Key": "esp32-demo-key"},
        json={"room": "A204", "power_kw": 2.4, "ts": ts})
    print(r.json())