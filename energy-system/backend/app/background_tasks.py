"""Background task: mark devices offline and create alerts/events.

Run ``start_offline_checker(SessionLocal)`` once at startup.
The checker wakes every DEVICE_CHECK_INTERVAL_SEC seconds (default 60).

Rules:
* A device is "offline" if last_seen is older than DEVICE_OFFLINE_TIMEOUT_SEC.
* On transition online -> offline: create a DeviceEvent("offline") and an Alert
  on the meter's associated room (if any).
* Offline consumption is never shown as zero; the Alert wording makes clear that
  "no data" does not mean "no consumption".
* On reconnection the heartbeat endpoint emits a "reconnected" event; this
  checker does not need to handle it.
"""

import datetime as dt
import os
import threading
import time

from sqlalchemy.orm import Session

from .models import Alert, DeviceEvent, IoTDevice, Meter, Room

OFFLINE_TIMEOUT = int(os.getenv("DEVICE_OFFLINE_TIMEOUT_SEC", "120"))
CHECK_INTERVAL = int(os.getenv("DEVICE_CHECK_INTERVAL_SEC", "60"))


def _check_devices(SessionLocal) -> None:
    db: Session = SessionLocal()
    try:
        now = time.time()
        devices = db.query(IoTDevice).filter(IoTDevice.enabled == True).all()
        for device in devices:
            if not device.last_seen:
                continue
            age = now - device.last_seen
            is_offline = age > OFFLINE_TIMEOUT

            # Check whether we already have an open offline alert for this device
            last_event = (
                db.query(DeviceEvent)
                .filter_by(device_id=device.id)
                .order_by(DeviceEvent.ts.desc())
                .first()
            )
            already_flagged = (
                last_event is not None and last_event.event_type == "offline"
            )

            if is_offline and not already_flagged:
                # Create an offline event
                db.add(DeviceEvent(
                    device_id=device.id,
                    event_type="offline",
                    details=(
                        f"No heartbeat for {int(age)}s "
                        f"(threshold {OFFLINE_TIMEOUT}s). "
                        "Consumption data is unavailable – do not assume zero use."
                    ),
                ))

                # Create an Alert on the room if this meter is room-level
                meter: Meter | None = db.get(Meter, device.meter_id)
                if meter and meter.measurement_level == "room" and meter.room_id:
                    room: Room | None = db.get(Room, meter.room_id)
                    if room:
                        existing_alert = db.query(Alert).filter_by(
                            room_id=room.id, kind="Device offline", status="open"
                        ).first()
                        if not existing_alert:
                            db.add(Alert(
                                room_id=room.id,
                                ts=dt.datetime.utcnow(),
                                kind="Device offline",
                                severity="High",
                                power=None,
                                baseline=None,
                                explanation=(
                                    f"Device '{device.name}' (meter {meter.meter_id}) "
                                    f"has not sent data for {int(age // 60)} minutes. "
                                    "No readings are available; this does not indicate zero consumption. "
                                    "Please investigate the device connection."
                                ),
                                action="Check device power and network. Do not assume zero consumption.",
                            ))

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _offline_checker_loop(SessionLocal) -> None:
    while True:
        time.sleep(CHECK_INTERVAL)
        _check_devices(SessionLocal)


def start_offline_checker(SessionLocal) -> None:
    """Start the background offline-checker thread."""
    t = threading.Thread(
        target=_offline_checker_loop,
        args=(SessionLocal,),
        daemon=True,
        name="device-offline-checker",
    )
    t.start()

