from typing import Any

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor, get_current_actor
from app.db.session import get_db_session
from app.schemas.auth import CurrentUserRead, LoginRequest, LoginResponse
from app.services.auth import login, revoke_access_token

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
async def login_endpoint(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await login(db, payload.tenant_id, payload.username, payload.password)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_endpoint(
    _actor: Actor = Depends(get_current_actor),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    token = authorization.split(" ", 1)[1].strip() if authorization else ""
    await revoke_access_token(db, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me", response_model=CurrentUserRead)
async def current_user_endpoint(actor: Actor = Depends(get_current_actor)) -> dict[str, Any]:
    if actor.user_id is None:
        raise RuntimeError("Authenticated actor is missing user_id")
    return {
        "id": actor.user_id,
        "tenant_id": actor.tenant_id,
        "username": actor.code,
        "display_name": actor.display_name,
        "role": actor.role,
        "worker_id": actor.worker_id,
        "worker_code": actor.worker_code,
        "worker_name": actor.worker_name,
    }
