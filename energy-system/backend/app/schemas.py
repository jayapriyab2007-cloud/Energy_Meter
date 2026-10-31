"""Pydantic v2 schemas for request validation and response serialisation.

Sections
--------
Auth            Login request and token response
Pagination      Generic page envelope
Blocks          Block CRUD
Floors          Floor CRUD
Rooms           Room CRUD
Departments     Department CRUD
Meters          Meter CRUD
Devices         IoT device registration and heartbeat
Alerts          Alert patch
Timetable       Cell update
Simulator       Inject / control
Ingest          Legacy hardware ingest
Overview        Summary response
Assistant       Chat
"""

from __future__ import annotations

import datetime as dt
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic pagination envelope."""

    items: List[T]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    token: str
    role: str
    block: Optional[str]


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


class BlockCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    manager_user_id: Optional[int] = None


class BlockUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    manager_user_id: Optional[int] = None


class BlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    manager_user_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Floors
# ---------------------------------------------------------------------------


class FloorCreate(BaseModel):
    block_id: int
    number: int = Field(..., ge=1)
    label: Optional[str] = None


class FloorUpdate(BaseModel):
    label: Optional[str] = None


class FloorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    block_id: int
    number: int
    label: Optional[str] = None


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    block_id: Optional[int] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    block_id: Optional[int] = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    block_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------


class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)
    block: str = Field(..., min_length=1, max_length=10)
    floor: int = Field(..., ge=1)
    rtype: str = Field(..., pattern="^(Classroom|Lab|Office|Auditorium|Other)$")
    meter_id: Optional[str] = None
    department_id: Optional[int] = None


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    block: Optional[str] = None
    floor: Optional[int] = Field(None, ge=1)
    rtype: Optional[str] = None
    meter_id: Optional[str] = None
    department_id: Optional[int] = None


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    block: str
    floor: int
    rtype: str
    meter_id: Optional[str] = None
    department_id: Optional[int] = None
    level: str


# ---------------------------------------------------------------------------
# Meters
# ---------------------------------------------------------------------------

VALID_LEVELS = ("room", "floor", "building")
VALID_SOURCES = ("simulated", "hardware")


class MeterCreate(BaseModel):
    meter_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1)
    measurement_level: str = Field(..., pattern="^(room|floor|building)$")
    block: Optional[str] = None
    floor: Optional[int] = None
    room_id: Optional[int] = None
    data_source: str = Field("simulated", pattern="^(simulated|hardware)$")
    enabled: bool = True

    @model_validator(mode="after")
    def check_location(self) -> "MeterCreate":
        if self.measurement_level == "room" and self.room_id is None:
            raise ValueError("room_id is required for room-level meters")
        if self.measurement_level == "floor" and (self.block is None or self.floor is None):
            raise ValueError("block and floor are required for floor-level meters")
        if self.measurement_level == "building" and self.block is None:
            raise ValueError("block is required for building-level meters")
        return self


class MeterUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    data_source: Optional[str] = Field(None, pattern="^(simulated|hardware)$")


class MeterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    meter_id: str
    name: str
    measurement_level: str
    block: Optional[str] = None
    floor: Optional[int] = None
    room_id: Optional[int] = None
    data_source: str
    enabled: bool


# ---------------------------------------------------------------------------
# IoT Devices
# ---------------------------------------------------------------------------


class DeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    meter_id: int  # FK to meters.id


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None


class DeviceRegistered(BaseModel):
    """Returned only once on registration – contains the plaintext key."""
    id: int
    name: str
    plaintext_key: str


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    meter_id: int
    enabled: bool
    last_seen: Optional[float] = None
    online: bool


class HeartbeatRequest(BaseModel):
    device_id: int
    device_key: str
    firmware_version: Optional[str] = None


class HeartbeatResponse(BaseModel):
    ok: bool
    server_time: str


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


ALERT_STATUSES = ("open", "resolved", "legitimate", "false_positive")


class AlertNote(BaseModel):
    status: str = Field(..., pattern="^(open|resolved|legitimate|false_positive)$")
    note: str = ""


# ---------------------------------------------------------------------------
# Timetable
# ---------------------------------------------------------------------------


class TimetableCell(BaseModel):
    day: int = Field(..., ge=0, le=6)
    hour: int = Field(..., ge=0, le=23)
    status: str = Field(..., pattern="^(Occupied|Free|Break)$")


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------


class InjectRequest(BaseModel):
    room_id: int
    ticks: int = Field(6, ge=1, le=60)


# ---------------------------------------------------------------------------
# Hardware ingest (legacy)
# ---------------------------------------------------------------------------


class IngestRequest(BaseModel):
    room: str
    power_kw: float = Field(..., ge=0, le=1000)
    interval_min: float = Field(5, ge=0.5, le=60)
    ts: Optional[dt.datetime] = None


# ---------------------------------------------------------------------------
# Assistant
# ---------------------------------------------------------------------------


class AssistantQuery(BaseModel):
    q: str = Field(..., min_length=1)

