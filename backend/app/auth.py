"""Password hashing, signed token helpers, and FastAPI auth dependency."""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import SECRET_KEY, TOKEN_TTL_HOURS
from .database import db

security = HTTPBearer(auto_error=False)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")

# Role hierarchy: customer < agent(staff) < supervisor < admin.
# Agent-facing features are available to staff/supervisor/admin.
AGENT_ROLES = {"staff", "supervisor", "admin"}
# Assignment/team-management features require supervisor or admin.
SUPERVISOR_ROLES = {"supervisor", "admin"}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"pbkdf2$100000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_b64, digest_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(user_id: int, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": int(time.time()) + TOKEN_TTL_HOURS * 3600,
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64url(
        hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest()
    )
    return f"{body}.{signature}"


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        body, signature = token.split(".", 1)
        expected = _b64url(
            hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_unb64url(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except (ValueError, json.JSONDecodeError):
        return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT id, username, role, display_name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已失效")
    user = get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user


def require_agent(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in AGENT_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无客服权限")
    return user


def require_supervisor(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in SUPERVISOR_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要主管或管理员权限")
    return user


def now_text() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
