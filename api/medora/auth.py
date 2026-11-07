"""Login and role checks (Rules 6.3). Every route declares its roles; every query filters by hospital_id."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request

from medora.config import env

ALL_ROLES = {"coordinator", "clinical_lead", "nurse", "admin", "data_steward"}
TOKEN_HOURS = 12


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, dk_b64 = stored.split("$")
        dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=2**14, r=8, p=1)
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except ValueError:
        return False


def _secret() -> str:
    s = env("JWT_SECRET")
    if len(s) < 32 or s.startswith("change-me"):
        raise RuntimeError("Set JWT_SECRET in .env to a random string of at least 32 characters")
    return s


def issue(user: dict[str, Any]) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user["id"]), "hid": str(user["hospital_id"]), "role": user["role"],
                       "name": user["display_name"], "iat": now, "exp": now + TOKEN_HOURS * 3600}, _secret(), "HS256")


@dataclass(frozen=True)
class User:
    id: str
    hospital_id: str
    role: str
    name: str


def current_user(request: Request) -> User:
    h = request.headers.get("authorization", "")
    token = h[7:] if h.lower().startswith("bearer ") else request.cookies.get("medora_token", "")
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    try:
        c = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(401, "Your session ended. Sign in again.") from e
    return User(c["sub"], c["hid"], c["role"], c["name"])


def require(*roles: str) -> Any:
    allowed = set(roles) or ALL_ROLES

    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(403, "Your role cannot do this.")
        return user
    return Depends(dep)
