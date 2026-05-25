from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import create_access_token, decode_access_token, verify_password
from app.models.auth import RevokedToken, UserAccount
from app.schemas.auth import CurrentUserRead, LoginResponse


def serialize_current_user(user: UserAccount) -> dict:
    return CurrentUserRead(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        worker_id=user.worker_id,
        worker_code=user.worker.code if user.worker else None,
        worker_name=user.worker.name if user.worker else None,
    ).model_dump(mode="json")


async def authenticate_user(session: AsyncSession, tenant_id: UUID, username: str, password: str) -> UserAccount:
    user = await session.scalar(
        select(UserAccount)
        .options(selectinload(UserAccount.worker))
        .where(
            UserAccount.tenant_id == tenant_id,
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


async def login(session: AsyncSession, tenant_id: UUID, username: str, password: str) -> dict:
    user = await authenticate_user(session, tenant_id, username, password)
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
        select(UserAccount)
        .options(selectinload(UserAccount.worker))
        .where(
            UserAccount.tenant_id == tenant_id,
            UserAccount.username == username,
            UserAccount.deleted_at.is_(None),
            UserAccount.is_active.is_(True),
        )
    )


async def is_token_revoked(session: AsyncSession, tenant_id: UUID, jti: str) -> bool:
    now = datetime.now(UTC)
    revoked_token_id = await session.scalar(
        select(RevokedToken.id).where(
            RevokedToken.tenant_id == tenant_id,
            RevokedToken.jti == jti,
            RevokedToken.expires_at > now,
        )
    )
    return revoked_token_id is not None


async def revoke_access_token(session: AsyncSession, token: str) -> None:
    try:
        payload = decode_access_token(token)
        tenant_id = UUID(str(payload["tenant_id"]))
        jti = str(payload["jti"])
        subject = str(payload["sub"])
        expires_at = datetime.fromtimestamp(int(payload["exp"]), UTC)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "登录状态无效或已过期"},
        ) from exc

    existing = await session.scalar(
        select(RevokedToken).where(
            RevokedToken.tenant_id == tenant_id,
            RevokedToken.jti == jti,
        )
    )
    if existing is None:
        session.add(
            RevokedToken(
                tenant_id=tenant_id,
                jti=jti,
                subject=subject,
                expires_at=expires_at,
            )
        )
    await session.commit()
