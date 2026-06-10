"""Auth router — login, profile, password management with JWT."""
from __future__ import annotations

import time
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.persistence.postgres.session import get_db_session

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"
JWT_SECRET = settings.JWT_SECRET
JWT_EXPIRE_HOURS = 24


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str
    reference_id: Optional[int] = None


def create_jwt(user_id: int, username: str, role: str, reference_id: Optional[int] = None) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "ref_id": reference_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_jwt(credentials.credentials)


# ── Endpoints ─────────────────────────────────────────────────


@router.post("/login")
async def login(
    req: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Authenticate with username/password via pgcrypto."""
    row = await session.execute(
        text("SELECT id, username, password_hash, role, reference_id, status "
             "FROM users WHERE username = :username")
        .bindparams(username=req.username)
    )
    user = row.first()
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")

    if not user:
        await session.execute(
            text("INSERT INTO login_logs (user_id, username, ip_address, user_agent, success, fail_reason) "
                 "VALUES (NULL, :u, :ip, :ua, FALSE, 'user_not_found')")
            .bindparams(u=req.username, ip=ip, ua=ua)
        )
        await session.commit()
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    uid, username, pw_hash, role, ref_id, status = user

    if status != "ACTIVE":
        raise HTTPException(status_code=403, detail="账户已被禁用")

    verify = await session.execute(
        text("SELECT crypt(:pw, :hash) = :hash").bindparams(pw=req.password, hash=pw_hash)
    )
    if not verify.scalar():
        await session.execute(
            text("INSERT INTO login_logs (user_id, username, ip_address, user_agent, success, fail_reason) "
                 "VALUES (:uid, :u, :ip, :ua, FALSE, 'wrong_password')")
            .bindparams(uid=uid, u=username, ip=ip, ua=ua)
        )
        await session.commit()
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    await session.execute(
        text("UPDATE users SET last_login_at = NOW() WHERE id = :uid").bindparams(uid=uid)
    )
    await session.execute(
        text("INSERT INTO login_logs (user_id, username, ip_address, user_agent, success) "
             "VALUES (:uid, :u, :ip, :ua, TRUE)")
        .bindparams(uid=uid, u=username, ip=ip, ua=ua)
    )
    await session.commit()

    token = create_jwt(uid, username, role, ref_id)
    return TokenResponse(access_token=token, user_id=uid, username=username,
                         role=role, reference_id=ref_id)


@router.get("/profile")
async def get_profile(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    row = await session.execute(
        text("SELECT id, username, role, reference_id, status, created_at "
             "FROM users WHERE id = :uid").bindparams(uid=int(user["sub"]))
    )
    u = row.first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "code": 0,
        "data": {
            "id": u[0], "username": u[1], "role": u[2],
            "reference_id": u[3], "status": u[4],
            "created_at": str(u[5]) if u[5] else None,
        }
    }


@router.post("/change-password")
async def change_password(
    old_password: str, new_password: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    uid = int(user["sub"])
    row = await session.execute(
        text("SELECT password_hash FROM users WHERE id = :uid").bindparams(uid=uid)
    )
    pw_hash = row.scalar()
    if not pw_hash:
        raise HTTPException(status_code=404, detail="User not found")
    verify = await session.execute(
        text("SELECT crypt(:old, :hash) = :hash").bindparams(old=old_password, hash=pw_hash)
    )
    if not verify.scalar():
        raise HTTPException(status_code=400, detail="原密码错误")
    await session.execute(
        text("UPDATE users SET password_hash = crypt(:new, gen_salt('bf')) WHERE id = :uid")
        .bindparams(new=new_password, uid=uid)
    )
    await session.commit()
    return {"code": 0, "message": "密码修改成功"}
