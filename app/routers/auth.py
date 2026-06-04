"""认证路由：登录 / 当前用户 / 用户管理。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db_session
from app.models.user import User, ROLE_PERMISSIONS, has_permission
from app.utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ─── JWT 工具 ───

import hashlib
import hmac
import json
import base64
import time

SECRET_KEY = "tez-operator-jwt-secret-2026"  # 生产环境应从环境变量读取
TOKEN_EXPIRE_DAYS = 7


def _hash_password(password: str) -> str:
    """简单的密码哈希（SHA256 + salt）。"""
    salt = "tez_salt_2026"
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    return _hash_password(password) == password_hash


def _create_token(user_id: int, username: str, role: str) -> str:
    """创建 JWT-like token（简化版，不依赖 pyjwt）。"""
    payload = {
        "uid": user_id,
        "sub": username,
        "role": role,
        "exp": int(time.time()) + TOKEN_EXPIRE_DAYS * 86400,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.HMAC(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload_b64}.{sig}"


def _decode_token(token: str) -> dict | None:
    """解码并验证 token。"""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.HMAC(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
        if sig != expected_sig:
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ─── 依赖注入：获取当前用户 ───

from fastapi import Request


async def get_current_user(request: Request, session: AsyncSession = Depends(get_db_session)) -> User:
    """从请求头中提取 token，验证并返回当前用户。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header[7:]
    payload = _decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user = await session.execute(select(User).where(User.id == payload["uid"]))
    user = user.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    return user


def require_role(*roles: str):
    """角色权限依赖：要求当前用户是指定角色之一。"""
    async def checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return user
    return checker


# ─── Schemas ───

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4)
    display_name: str = ""
    role: str = Field(default="viewer", pattern="^(admin|ops|viewer)$")


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = Field(None, pattern="^(admin|ops|viewer)$")
    is_active: bool | None = None
    password: str | None = None


class UserInfo(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    permissions: list[str]
    created_at: datetime | None = None
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


# ─── 端点 ───

@router.post("/login", response_model=LoginResponse, summary="登录")
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db_session)):
    """用户名密码登录，返回 JWT token。"""
    user = await session.execute(select(User).where(User.username == payload.username))
    user = user.scalar_one_or_none()

    if not user or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已禁用")

    # 更新最后登录时间
    user.last_login_at = datetime.now()
    await session.commit()

    token = _create_token(user.id, user.username, user.role)
    return LoginResponse(
        token=token,
        user={
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "permissions": ROLE_PERMISSIONS.get(user.role, []),
        },
    )


@router.get("/me", summary="获取当前登录用户信息")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "permissions": ROLE_PERMISSIONS.get(user.role, []),
    }


# ─── 用户管理（仅 admin）───

@router.get("/users", summary="用户列表（仅admin）")
async def list_users(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role("admin")),
):
    result = await session.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return {
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "role": u.role,
                "is_active": u.is_active,
                "permissions": ROLE_PERMISSIONS.get(u.role, []),
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            }
            for u in users
        ]
    }


@router.post("/users", status_code=201, summary="创建用户（仅admin）")
async def create_user(
    payload: UserCreate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role("admin")),
):
    # 检查用户名重复
    existing = await session.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=payload.username,
        password_hash=_hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        role=payload.role,
    )
    session.add(user)
    await session.commit()
    return {"id": user.id, "username": user.username, "role": user.role}


@router.put("/users/{user_id}", summary="更新用户（仅admin）")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_role("admin")),
):
    user = await session.execute(select(User).where(User.id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = _hash_password(payload.password)

    await session.commit()
    return {"id": user.id, "username": user.username, "role": user.role}


@router.delete("/users/{user_id}", status_code=204, summary="删除用户（仅admin）")
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_role("admin")),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    user = await session.execute(select(User).where(User.id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    await session.delete(user)
    await session.commit()


# ─── 个人设置（当前用户自助）───

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=4)


class UpdateProfileRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)


@router.put("/me/password", summary="修改密码")
async def change_password(
    payload: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """当前用户修改自己的密码。"""
    if not _verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")

    user.password_hash = _hash_password(payload.new_password)
    await session.commit()
    return {"message": "密码修改成功"}


@router.put("/me/profile", summary="修改个人信息")
async def update_profile(
    payload: UpdateProfileRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """当前用户修改显示名。"""
    user.display_name = payload.display_name
    await session.commit()
    return {"message": "修改成功", "display_name": user.display_name}
