# Smart Energy Intelligence & Monitoring System

Cloud-connected, timetable-aware campus energy monitoring. React + Vite frontend with FastAPI + SQLAlchemy + Alembic backend (SQLite for dev, PostgreSQL for deployment).

## Quickstart

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload     # http://localhost:8000/docs
cd frontend && npm install && npm run dev                                          # http://localhost:5173
```

- **Admin Login:** `admin` / `admin123` (Full control)
- **Consumer Login:** `consumer` / `consumer123` (Block A scoped)

---

## College Campus Demo Guide

### End-to-End Demo Script (B101 Seminar Hall)
1. **Sign in** as `admin` / `admin123`.
2. Open the **Timetable** tab and select `B101 - Floor 1 (Seminar Hall) [Administration]`.
   - Observe the deterministic schedule: Monday–Friday 11:00–12:00 is scheduled as **Free period**.
3. Open the **Demo control** tab.
   - Click **Run Seminar Hall demo** (Scenario 1).
   - This sets the virtual clock to a weekday 11:00 (during the Free period) and injects 4.8 kW draw (AC, projector, and audio equipment left on).
4. Navigate to the **Alerts** tab:
   - Notice the high-severity alert: `B101 | Consumption during free period`.
   - The alert displays measured draw (~4.8 kW) against the learned baseline (~0.4 kW), with wording recommending investigation.
5. In the alert row, click **Add exception**:
   - Enter `Setup for 12:00 seminar` and reason `Audiovisual check and rehearsal`.
   - The alert is updated to **legitimate** with the note attached, and the schedule override prevents further false alerts.
6. Open the **Assistant** tab:
   - Ask: `"Why was an alert raised for the seminar hall?"` or `"Which block uses the most power?"`.
   - The assistant answers directly using real queried database values.
7. Return to **Demo control** and click **Reset demo** to restore clean baseline history.

---

### Campus Directory

- **Block A (Administration & Computing - 3 Floors):**
  - **Floor 1 (Administration):** A101 (Principal's Office), A102 (Administration Office), A103 (Accounts Office), A104 (Conference Room).
  - **Floor 2 (CSE):** A201 (Classroom 1), A202 (Classroom 2), A203 (CSE Lab 1), A204 (CSE Lab 2 - Free at 10:00 weekdays).
  - **Floor 3 (CSD & IT):** A301 (CSD Classroom), A302 (CSD Lab), A303 (IT Classroom), A304 (IT Lab).
- **Block B (Bio, ECE & Mechatronics - 4 Floors):**
  - **Floor 1:** B101 (Seminar Hall - Main Demo Room), B102 (Biotech Classroom), B103 (Biotech Lab 1), B104 (Biotech Lab 2).
  - **Floor 2 (MCT & ECE):** B201 (MCT Classroom), B202 (MCT Lab), B203 (MCT Workshop), B204 (ECE Classroom 1).
  - **Floor 3 (ECE & MCT):** B301 (ECE Classroom 2), B302 (ECE Lab 1), B303 (ECE Lab 2), B304 (MCT Classroom 2).
  - **Floor 4:** B401 (ECE Classroom 3), B402 (ECE Lab 3), B403 (Biotech Classroom 2), B404 (Faculty Room).
- **Block C (Core Engineering - 3 Floors):**
  - **Floor 1 (Civil):** C101 (Civil Classroom), C102 (Survey Lab), C103 (Concrete Lab).
  - **Floor 2 (EEE):** C201 (EEE Classroom), C202 (EEE Lab), C203 (Machines Lab Workshop).
  - **Floor 3 (Automobile):** C301 (Automobile Classroom), C302 (Automobile Lab), C303 (Automobile Workshop).
- **Block D (Academic Block & Basic Sciences - 3 Floors):**
  - 12 rooms across 3 floors (Physics, Chemistry, Maths, Tutorial rooms, Language Lab, Innovation Lab).

---

### B101 Seminar Hall Schedule

| Day | 09:00 - 11:00 | 11:00 - 12:00 | 12:00 - 13:00 | 13:00 - 14:00 | 14:00 - 16:00 | 16:00 - 17:00 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mon - Fri** | Occupied (Guest lecture / workshop) | **Free (Free period)** | Occupied (Dept seminar) | **Break (Lunch)** | Occupied (Placement talk / tech event) | **Free (Free period)** |
| **Saturday** | Free (09:00 - 10:00) | Occupied: Placement training (10:00 - 12:00) | Free (12:00 - 13:00) | Off (13:00+) | Off | Off |
| **Sunday** | Off | Off | Off | Off | Off | Off |

---

### Metering Architecture & Levels
- **Room-level meters:** Every room has a dedicated simulated meter (`METER_<room_code>`). Anomaly detection runs strictly on room-level meters.
- **Floor-level meters:** Floor aggregate meters installed on every floor of Block B (`METER_B_FL1` to `METER_B_FL4`).
- **Building-level meters:** Building aggregate meters for all blocks (`METER_BLD_<Block>_MAIN`).
- *Note:* Floor and building meters never trigger room-attributed alerts.
