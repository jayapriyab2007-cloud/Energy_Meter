# Smart Energy Intelligence & Monitoring System

Cloud-connected, timetable-aware campus energy monitoring. React + FastAPI + SQLAlchemy (SQLite for dev, PostgreSQL for deployment).

## Run
```
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload     # http://localhost:8000/docs
cd frontend && npm install && npm run dev                                          # http://localhost:5173
```
Sign in as `admin / admin123` (full control) or `consumer / consumer123` (Block A only). Click **Start simulator**, open **Live monitoring**, press **Inject test anomaly**, then watch **Alerts** (the core demo: Room A204 style free-period alert, then resolve with a note).
Set `DATABASE_URL=postgresql+psycopg2://...`, `JWT_SECRET`, `DEVICE_KEY` for real deployments.

## Specification summary
**Architecture:** ESP32 + meter -> HTTPS `POST /api/ingest` (MQTT/TLS planned) -> FastAPI validation -> SQL database -> anomaly engine -> React dashboards (3 s polling; WebSockets planned).
**Hierarchy:** Block -> Floor -> Room -> Meter + room timetable. Demo layout is data (`LAYOUT` in `main.py`), 4 blocks with different floor counts. Each meter stores a measurement level (demo: room-level only).
**Anomaly engine** (same code for simulated and hardware readings): per-room baseline per timetable status from history (default 0.3 kW until 12 samples). Rules: (A) free/lunch usage above max(2x baseline, baseline+0.8 kW) for 3 consecutive readings; (B) night-time usage out of hours; (C) spike >3x recent average with no schedule change. One open alert per room and type; alerts carry explanation and action; admin can resolve, mark legitimate or false positive with notes. A free slot does not prove an empty room, so alerts are worded as "investigate".
**Roles:** admin (all blocks, timetable edit, alerts, simulator); consumer (own block, read-only).
**Billing/forecast:** tariff x kWh, labelled as estimates; 7-day moving-average forecast.
**Assistant:** keyword intents answered only from queried database values (an LLM can later be put in front of these same permission-checked functions).

## REST API (Swagger at /docs)
`POST /api/login` · `GET /api/overview` · `GET /api/rooms` · `GET /api/rooms/{id}/live` · `GET /api/alerts` · `PATCH /api/alerts/{id}` · `GET|PUT /api/timetable/{room}` · `POST /api/sim/start|stop` · `POST /api/sim/inject/anomaly` · `POST /api/ingest` (header `X-Device-Key`) · `GET /api/forecast` · `POST /api/assistant`
ESP32 test: `curl -X POST localhost:8000/api/ingest -H "X-Device-Key: esp32-demo-key" -H "Content-Type: application/json" -d '{"room":"A204","power_kw":2.4}'`

## Database
users, rooms (with meter_id, level, last_seen), timetables, meter_readings (status + simulated flag), alerts, audit_logs.

## Not yet built (roadmap vs. the full spec)
Block/floor/room/meter CRUD screens and departments; separate iot_devices, heartbeats and offline alerts; floor/building meters and allocation; timetable exceptions and CSV import; budgets/targets tables and threshold notifications; notifications; CSV/PDF reports; Alembic migrations; MQTT broker; WebSockets; LLM-backed assistant; automated tests; per-device credentials; cloud deployment. Build these in the order of the 11-phase plan.
Safety: mains-connected meters must be installed by a qualified electrician; use a meter with an isolated RS-485/Modbus interface.
