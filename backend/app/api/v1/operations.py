from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor, get_default_operator_actor
from app.db.session import get_db_session
from app.schemas.operation import (
    OperationClock,
    OperationClockRead,
    OperationRead,
    OperationStart,
    OperationStateChange,
)
from app.services.operation import (
    clock_operation,
    get_operation_by_qr,
    pause_operation,
    resume_operation,
    start_operation,
)

router = APIRouter(tags=["operations"])


def require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "缺少 Idempotency-Key 请求头"},
        )
    return idempotency_key


@router.get("/operations/by-qr", response_model=OperationRead)
async def get_operation_by_qr_endpoint(
    code: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_operator_actor),
) -> dict[str, Any]:
    return await get_operation_by_qr(db, code, actor)


@router.post("/operations/{operation_id}/start", response_model=OperationRead)
async def start_operation_endpoint(
    operation_id: UUID,
    payload: OperationStart,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_operator_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await start_operation(db, operation_id, payload, actor, require_idempotency_key(idempotency_key))


@router.post("/operations/{operation_id}/clock", response_model=OperationClockRead)
async def clock_operation_endpoint(
    operation_id: UUID,
    payload: OperationClock,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_operator_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await clock_operation(db, operation_id, payload, actor, require_idempotency_key(idempotency_key))


@router.post("/operations/{operation_id}/pause", response_model=OperationRead)
async def pause_operation_endpoint(
    operation_id: UUID,
    payload: OperationStateChange,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_operator_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await pause_operation(db, operation_id, payload, actor, require_idempotency_key(idempotency_key))


@router.post("/operations/{operation_id}/resume", response_model=OperationRead)
async def resume_operation_endpoint(
    operation_id: UUID,
    payload: OperationStateChange,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_operator_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await resume_operation(db, operation_id, payload, actor, require_idempotency_key(idempotency_key))
