from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor, get_default_actor, get_default_operator_actor
from app.db.session import get_db_session
from app.schemas.operation import (
    OperationBackfillRequestCreate,
    OperationBackfillRequestRead,
    OperationBackfillReview,
    OperationClock,
    OperationClockRead,
    OperationRead,
    OperationStart,
    OperationStateChange,
)
from app.services.operation import (
    approve_backfill_request,
    clock_operation,
    create_backfill_request,
    get_operation_by_qr,
    list_backfill_requests,
    list_workbench_operations,
    pause_operation,
    reject_backfill_request,
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


@router.get("/operations/workbench", response_model=list[OperationRead])
async def list_operation_workbench_endpoint(
    statuses: str = Query(default="paused,in_progress,ready"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_operator_actor),
) -> list[dict[str, Any]]:
    status_list = [item.strip() for item in statuses.split(",") if item.strip()]
    return await list_workbench_operations(db, actor, status_list, limit)


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


@router.post("/operations/{operation_id}/backfill-requests", response_model=OperationBackfillRequestRead)
async def create_backfill_request_endpoint(
    operation_id: UUID,
    payload: OperationBackfillRequestCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_operator_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await create_backfill_request(db, operation_id, payload, actor, require_idempotency_key(idempotency_key))


@router.get("/operation-backfill-requests", response_model=dict)
async def list_backfill_requests_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> dict[str, Any]:
    return await list_backfill_requests(db, actor, status_filter=status_filter, limit=limit, offset=offset)


@router.post("/operation-backfill-requests/{request_id}/approve", response_model=OperationBackfillRequestRead)
async def approve_backfill_request_endpoint(
    request_id: UUID,
    payload: OperationBackfillReview,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await approve_backfill_request(db, request_id, payload, actor, require_idempotency_key(idempotency_key))


@router.post("/operation-backfill-requests/{request_id}/reject", response_model=OperationBackfillRequestRead)
async def reject_backfill_request_endpoint(
    request_id: UUID,
    payload: OperationBackfillReview,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await reject_backfill_request(db, request_id, payload, actor, require_idempotency_key(idempotency_key))


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
