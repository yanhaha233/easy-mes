from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.models.auth import UserAccount
from app.schemas.auth import CurrentUserRead, LoginResponse


def serialize_current_user(user: UserAccount) -> dict:
    return CurrentUserRead(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    ).model_dump(mode="json")


async def authenticate_user(session: AsyncSession, username: str, password: str) -> UserAccount:
    user = await session.scalar(
        select(UserAccount).where(
            UserAccount.username == username,
            UserAccount.deleted_at.is_(None),
        )
    )
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "用户名或密码错误"},
        )
    return user


async def login(session: AsyncSession, username: str, password: str) -> dict:
    user = await authenticate_user(session, username, password)
    token, expires_at = create_access_token(subject=user.username, role=user.role, tenant_id=str(user.tenant_id))
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return LoginResponse(
        access_token=token,
        expires_at=expires_at,
        user=CurrentUserRead.model_validate(serialize_current_user(user)),
    ).model_dump(mode="json")


async def load_user_by_token_subject(session: AsyncSession, tenant_id: UUID, username: str) -> UserAccount | None:
    return await session.scalar(
        select(UserAccount).where(
            UserAccount.tenant_id == tenant_id,
            UserAccount.username == username,
            UserAccount.deleted_at.is_(None),
            UserAccount.is_active.is_(True),
        )
    )
