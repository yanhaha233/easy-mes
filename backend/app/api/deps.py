from dataclasses import dataclass
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS_TOKEN_COOKIE_NAME, decode_access_token
from app.db.session import get_db_session
from app.models.master_data import Worker
from app.services.auth import is_token_revoked, load_user_by_token_subject


@dataclass(frozen=True)
class Actor:
    tenant_id: UUID
    code: str
    role: str = "planner"
    display_name: str = ""
    user_id: UUID | None = None
    worker_id: UUID | None = None
    worker_code: str | None = None
    worker_name: str | None = None


async def get_current_actor(
    db: AsyncSession = Depends(get_db_session),
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
) -> Actor:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif access_token_cookie:
        token = access_token_cookie
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "请先登录"},
        )
    try:
        payload = decode_access_token(token)
        tenant_id = UUID(str(payload["tenant_id"]))
        username = str(payload["sub"])
        token_jti = str(payload["jti"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "登录状态无效或已过期"},
        ) from exc

    if await is_token_revoked(db, tenant_id, token_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_REVOKED", "message": "登录状态已退出，请重新登录"},
        )

    user = await load_user_by_token_subject(db, tenant_id, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "登录用户不存在或已停用"},
        )
    worker = None
    if user.worker_id:
        worker = await db.get(Worker, user.worker_id)
        if worker and (worker.tenant_id != user.tenant_id or worker.deleted_at is not None or not worker.is_active):
            worker = None
    actor = Actor(
        tenant_id=user.tenant_id,
        code=user.username,
        role=user.role,
        display_name=user.display_name,
        user_id=user.id,
        worker_id=worker.id if worker else None,
        worker_code=worker.code if worker else None,
        worker_name=worker.name if worker else None,
    )
    # 认证依赖只读查询会开启隐式事务，返回前清理掉，避免连接长期挂着事务状态。
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
