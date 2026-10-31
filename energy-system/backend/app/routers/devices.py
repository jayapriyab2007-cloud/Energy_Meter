"""IoT device management and heartbeat – /api/devices, /api/heartbeat

Registration flow:
  POST /api/devices  ->  returns plaintext_key once (stored hashed)
  POST /api/heartbeat  ->  device checks in with its device_id + key

Per-device credentials mean each ESP32 has a unique secret.
The plaintext key is never stored or re-returned.
"""

import secrets
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..auth import hash_password, verify_password
from ..database import get_db
from ..models import Audit, DeviceEvent, DeviceHeartbeat, IoTDevice, Meter, Alert
from ..schemas import (
    DeviceCreate,
    DeviceOut,
    DeviceRegistered,
    DeviceUpdate,
    HeartbeatRequest,
    HeartbeatResponse,
)

router = APIRouter(tags=["devices"])

# Devices are considered offline after this many seconds without a heartbeat/reading.
OFFLINE_TIMEOUT = int(__import__("os").getenv("DEVICE_OFFLINE_TIMEOUT_SEC", "120"))


def _is_online(device: IoTDevice) -> bool:
    return bool(device.last_seen) and (time.time() - device.last_seen) < OFFLINE_TIMEOUT


# ---------------------------------------------------------------------------
# Device CRUD
# ---------------------------------------------------------------------------


@router.get("/api/devices", response_model=List[DeviceOut])
def list_devices(
    meter_id: Optional[int] = Query(None),
    enabled: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _u: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(IoTDevice)
    if meter_id is not None:
        q = q.filter(IoTDevice.meter_id == meter_id)
    if enabled is not None:
        q = q.filter(IoTDevice.enabled == enabled)
    devices = q.offset((page - 1) * page_size).limit(page_size).all()
    return [
        DeviceOut(
            id=d.id,
            name=d.name,
            meter_id=d.meter_id,
            enabled=d.enabled,
            last_seen=d.last_seen or None,
            online=_is_online(d),
        )
        for d in devices
    ]


@router.post("/api/devices", response_model=DeviceRegistered, status_code=201)
def register_device(body: DeviceCreate, u: dict = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """Register a new IoT device and return its plaintext key (only shown once)."""
    if not db.get(Meter, body.meter_id):
        raise HTTPException(404, "Meter not found")
    if db.query(IoTDevice).filter_by(name=body.name).first():
        raise HTTPException(409, f"Device name '{body.name}' already exists")

    plaintext_key = secrets.token_urlsafe(32)
    device = IoTDevice(
        name=body.name,
        meter_id=body.meter_id,
        key_hash=hash_password(plaintext_key),
        enabled=True,
    )
    db.add(device)
    db.add(Audit(who=u["sub"], what=f"registered device {body.name}"))
    db.commit()
    db.refresh(device)

    return DeviceRegistered(
        id=device.id,
        name=device.name,
        plaintext_key=plaintext_key,
    )


@router.get("/api/devices/{did}", response_model=DeviceOut)
def get_device(did: int, _u: dict = Depends(get_current_user),
               db: Session = Depends(get_db)):
    d = db.get(IoTDevice, did)
    if not d:
        raise HTTPException(404, "Device not found")
    return DeviceOut(
        id=d.id, name=d.name, meter_id=d.meter_id,
        enabled=d.enabled, last_seen=d.last_seen or None, online=_is_online(d),
    )


@router.patch("/api/devices/{did}", response_model=DeviceOut)
def update_device(did: int, body: DeviceUpdate, u: dict = Depends(require_admin),
                  db: Session = Depends(get_db)):
    d = db.get(IoTDevice, did)
    if not d:
        raise HTTPException(404, "Device not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    db.add(Audit(who=u["sub"], what=f"updated device {did}"))
    db.commit()
    db.refresh(d)
    return DeviceOut(
        id=d.id, name=d.name, meter_id=d.meter_id,
        enabled=d.enabled, last_seen=d.last_seen or None, online=_is_online(d),
    )


@router.delete("/api/devices/{did}", status_code=204)
def delete_device(did: int, u: dict = Depends(require_admin),
                  db: Session = Depends(get_db)):
    d = db.get(IoTDevice, did)
    if not d:
        raise HTTPException(404, "Device not found")
    db.delete(d)
    db.add(Audit(who=u["sub"], what=f"deleted device {did}"))
    db.commit()


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


@router.post("/api/heartbeat", response_model=HeartbeatResponse)
def heartbeat(body: HeartbeatRequest, db: Session = Depends(get_db)):
    """Device heartbeat – called periodically by ESP32 to signal it is alive."""
    device = db.get(IoTDevice, body.device_id)
    if not device or not device.enabled:
        raise HTTPException(401, "Unknown or disabled device")
    if not verify_password(body.device_key, device.key_hash):
        raise HTTPException(401, "Invalid device key")

    was_online = _is_online(device)
    device.last_seen = time.time()
    if body.firmware_version:
        device.firmware_version = body.firmware_version

    db.add(DeviceHeartbeat(device_id=device.id, firmware_version=body.firmware_version))

    # Emit a "reconnected" event if the device was previously offline
    if not was_online and device.last_seen:
        db.add(DeviceEvent(
            device_id=device.id,
            event_type="reconnected",
            details="Device sent a heartbeat after being offline.",
        ))

    db.commit()
    import datetime as dt
    return HeartbeatResponse(ok=True, server_time=dt.datetime.utcnow().isoformat())

