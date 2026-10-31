"""Authentication utilities.

* Password hashing/verification using bcrypt (passlib).
* JWT creation and decoding (PyJWT).
* FastAPI dependency functions: ``get_current_user``, ``require_admin``.

Secrets are read from environment variables.  The JWT_SECRET has no hard-coded
fallback outside development mode (controlled by ENV=development).
"""

import os
import datetime as dt
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from passlib.context import CryptContext

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ENV = os.getenv("ENV", "development")
_default_secret = "change-me-in-production" if _ENV == "development" else None
SECRET: str = os.getenv("JWT_SECRET", _default_secret)  # type: ignore[assignment]
if not SECRET:
    raise RuntimeError("JWT_SECRET environment variable must be set in production.")

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "24"))

# ---------------------------------------------------------------------------
# Password hashing
# Direct bcrypt implementation (avoids passlib 72-byte test incompatibility in bcrypt >= 4.1)
# ---------------------------------------------------------------------------

import bcrypt


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password* with a per-call random salt."""
    # Truncate to 72 bytes if needed per bcrypt specification
    pw_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    try:
        pw_bytes = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Legacy SHA-256 hash – kept ONLY to support pre-existing seed data.
# New users are stored with bcrypt.  Remove once DB is re-seeded.
# ---------------------------------------------------------------------------

import hashlib  # noqa: E402


def _legacy_hash(username: str, password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), username.encode(), 50000).hex()


def verify_any_hash(username: str, plain: str, hashed: str) -> bool:
    """Accept both bcrypt (new) and legacy PBKDF2 (old seed data)."""
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        return verify_password(plain, hashed)
    return _legacy_hash(username, plain) == hashed


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_token(payload: dict) -> str:
    """Return a signed JWT that expires in TOKEN_EXPIRE_HOURS hours."""
    data = payload.copy()
    data["exp"] = dt.datetime.utcnow() + dt.timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(data, SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT; raise 401 on any failure."""
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")


# ---------------------------------------------------------------------------
# FastAPI dependency functions
# ---------------------------------------------------------------------------


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Extract and validate the Bearer JWT from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    return decode_token(authorization.split(" ", 1)[1])


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Raise 403 if the caller is not an admin."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrators only")
    return current_user

