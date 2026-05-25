from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor, get_current_actor
from app.core.config import settings
from app.core.security import ACCESS_TOKEN_COOKIE_NAME
from app.db.session import get_db_session
from app.schemas.auth import CurrentUserRead, LoginRequest, LoginResponse
from app.services.auth import login, revoke_access_token

router = APIRouter(tags=["auth"])


def cookie_secure() -> bool:
    return settings.app_env.lower() != "local"


def set_access_token_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


def clear_access_token_cookie(response: Response) -> None:
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


def bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


@router.post("/auth/login", response_model=LoginResponse)
async def login_endpoint(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await login(db, payload.tenant_id, payload.username, payload.password)
    set_access_token_cookie(response, str(result["access_token"]))
    return result


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_endpoint(
    response: Response,
    _actor: Actor = Depends(get_current_actor),
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    token = bearer_token(authorization) or access_token_cookie or ""
    await revoke_access_token(db, token)
    clear_access_token_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


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
