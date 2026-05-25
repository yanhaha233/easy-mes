from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor, get_current_actor
from app.db.session import get_db_session
from app.schemas.auth import CurrentUserRead, LoginRequest, LoginResponse
from app.services.auth import login

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
async def login_endpoint(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await login(db, payload.username, payload.password)


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
    }
