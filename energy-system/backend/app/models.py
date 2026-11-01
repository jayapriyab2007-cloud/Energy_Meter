"""SQLAlchemy ORM models for the Smart Energy system.

All existing tables are preserved verbatim.
New tables for Stage 1 are appended below:
  Campus structure: Block, Floor, Department
  Room gets an optional department_id FK.
  Infrastructure: Meter, IoTDevice, DeviceHeartbeat, DeviceEvent
"""

import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# ---------------------------------------------------------------------------
# Existing tables (unchanged semantics)
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    pw = Column(String)          # password hash
    role = Column(String)        # "admin" | "consumer"
    block = Column(String, nullable=True)  # consumer scoping


class Block(Base):
    """A physical campus block/building."""

    __tablename__ = "blocks"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    manager_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    manager = relationship("User", foreign_keys=[manager_user_id])
    floors = relationship("Floor", back_populates="block", cascade="all, delete-orphan")
    departments = relationship("Department", back_populates="block")


class Floor(Base):
    """A floor within a Block."""

    __tablename__ = "floors"
    id = Column(Integer, primary_key=True)
    block_id = Column(Integer, ForeignKey("blocks.id"), nullable=False)
    number = Column(Integer, nullable=False)
    label = Column(String, nullable=True)

    block = relationship("Block", back_populates="floors")


class Department(Base):
    """Academic or administrative department."""

    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    block_id = Column(Integer, ForeignKey("blocks.id"), nullable=True)

    block = relationship("Block", back_populates="departments")
    rooms = relationship("Room", back_populates="department")


class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    block = Column(String, index=True)
    floor = Column(Integer)
    rtype = Column(String)       # "Lab" | "Classroom" | ...
    meter_id = Column(String)    # legacy reference kept for backwards compat
    level = Column(String, default="room")
    last_seen = Column(Float, default=0)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    department = relationship("Department", back_populates="rooms")
    meters = relationship("Meter", back_populates="room", foreign_keys="Meter.room_id")


class Timetable(Base):
    __tablename__ = "timetables"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), index=True)
    day = Column(Integer)   # 0=Monday ... 6=Sunday
    hour = Column(Integer)  # 0-23
    activity = Column(String)
    status = Column(String)


class TimetableException(Base):
    """Temporary or one-off timetable override/exception for a room."""

    __tablename__ = "timetable_exceptions"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), index=True)
    start_ts = Column(DateTime, nullable=False, index=True)
    end_ts = Column(DateTime, nullable=False, index=True)
    activity = Column(String, nullable=False)
    reason = Column(String, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    room = relationship("Room", backref="exceptions")


class Reading(Base):
    __tablename__ = "meter_readings"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), index=True)
    ts = Column(DateTime, index=True)
    power_kw = Column(Float)
    energy_kwh = Column(Float)
    status = Column(String)
    simulated = Column(Boolean, default=True)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"))
    ts = Column(DateTime)
    kind = Column(String)
    severity = Column(String)
    power = Column(Float)
    baseline = Column(Float)
    explanation = Column(String)
    action = Column(String)
    status = Column(String, default="open")
    note = Column(String, default="")


class Audit(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=dt.datetime.utcnow)
    who = Column(String)
    what = Column(String)


# ---------------------------------------------------------------------------
# New Stage 1 tables – infrastructure
# ---------------------------------------------------------------------------


class Meter(Base):
    """Physical or simulated meter.

    measurement_level: "room" | "floor" | "building"
    data_source:       "simulated" | "hardware"
    enabled:           soft-disable flag
    """

    __tablename__ = "meters"
    id = Column(Integer, primary_key=True)
    meter_id = Column(String, unique=True, index=True)  # human-readable ID
    name = Column(String)
    measurement_level = Column(String)
    block = Column(String, nullable=True)
    floor = Column(Integer, nullable=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)
    data_source = Column(String, default="simulated")
    enabled = Column(Boolean, default=True)

    room = relationship("Room", back_populates="meters", foreign_keys=[room_id])
    devices = relationship("IoTDevice", back_populates="meter")


class IoTDevice(Base):
    """An ESP32 (or similar) device that submits readings.

    key_hash: bcrypt hash of the per-device secret key.
              The plaintext is returned exactly once at registration.
    """

    __tablename__ = "iot_devices"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    meter_id = Column(Integer, ForeignKey("meters.id"))
    key_hash = Column(String)
    last_seen = Column(Float, default=0)  # epoch seconds
    firmware_version = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)

    meter = relationship("Meter", back_populates="devices")
    heartbeats = relationship("DeviceHeartbeat", back_populates="device",
                              cascade="all, delete-orphan")
    events = relationship("DeviceEvent", back_populates="device",
                          cascade="all, delete-orphan")


class DeviceHeartbeat(Base):
    __tablename__ = "device_heartbeats"
    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("iot_devices.id"))
    ts = Column(DateTime, default=dt.datetime.utcnow)
    firmware_version = Column(String, nullable=True)

    device = relationship("IoTDevice", back_populates="heartbeats")


class DeviceEvent(Base):
    __tablename__ = "device_events"
    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey("iot_devices.id"))
    ts = Column(DateTime, default=dt.datetime.utcnow)
    event_type = Column(String)   # "offline" | "reconnected" | "error"
    details = Column(String, nullable=True)

    device = relationship("IoTDevice", back_populates="events")
