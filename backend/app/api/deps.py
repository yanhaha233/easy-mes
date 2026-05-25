from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.services.auth import load_user_by_token_subject


@dataclass(frozen=True)
class Actor:
    tenant_id: UUID
    code: str
    role: str = "planner"
    display_name: str = ""
    user_id: UUID | None = None


async def get_current_actor(
    db: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "请先登录"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
        tenant_id = UUID(str(payload["tenant_id"]))
        username = str(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "登录状态无效或已过期"},
        ) from exc

    user = await load_user_by_token_subject(db, tenant_id, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "登录用户不存在或已停用"},
        )
    actor = Actor(
        tenant_id=user.tenant_id,
        code=user.username,
        role=user.role,
        display_name=user.display_name,
        user_id=user.id,
    )
    await db.rollback()
    return actor


def require_roles(*allowed_roles: str):
    async def dependency(actor: Actor = Depends(get_current_actor)) -> Actor:
        if actor.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN_ROLE", "message": "当前角色无权执行该操作"},
            )
        return actor

    return dependency


async def get_default_actor(actor: Actor = Depends(require_roles("planner", "admin"))) -> Actor:
    return actor


async def get_default_operator_actor(actor: Actor = Depends(require_roles("operator", "admin"))) -> Actor:
    return actor


async def get_any_authenticated_actor(actor: Actor = Depends(get_current_actor)) -> Actor:
    return actor
