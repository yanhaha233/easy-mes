from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import Actor, get_default_actor
from app.db.session import get_db_session
from app.models.production import WorkOrder
from app.schemas.work_order import (
    KittingCheckRead,
    ProductionReceiptCreate,
    WorkOrderCancel,
    WorkOrderCreate,
    WorkOrderListItem,
    WorkOrderRead,
    WorkOrderReceiptResponse,
    WorkOrderTraceabilityRead,
)
from app.services.work_order import (
    cancel_work_order,
    confirm_work_order,
    create_work_order,
    get_work_order_traceability,
    kitting_check,
    receive_work_order,
    schedule_work_order,
    serialize_work_order,
)

router = APIRouter(tags=["work-orders"])


@router.post("/work-orders", response_model=WorkOrderRead, status_code=status.HTTP_201_CREATED)
async def create_work_order_endpoint(
    payload: WorkOrderCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "缺少 Idempotency-Key 请求头"},
        )
    return await create_work_order(db, payload, actor, idempotency_key)


@router.post("/work-orders/{work_order_no}/confirm", response_model=WorkOrderRead)
async def confirm_work_order_endpoint(
    work_order_no: str,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> dict[str, Any]:
    return await confirm_work_order(db, work_order_no, actor)


@router.post("/work-orders/{work_order_no}/cancel", response_model=WorkOrderRead)
async def cancel_work_order_endpoint(
    work_order_no: str,
    payload: WorkOrderCancel,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "缺少 Idempotency-Key 请求头"},
        )
    return await cancel_work_order(db, work_order_no, payload, actor, idempotency_key)


@router.post("/work-orders/{work_order_no}/schedule", response_model=WorkOrderRead)
async def schedule_work_order_endpoint(
    work_order_no: str,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> dict[str, Any]:
    return await schedule_work_order(db, work_order_no, actor)


@router.post("/work-orders/{work_order_no}/kitting-check", response_model=KittingCheckRead)
async def kitting_check_endpoint(
    work_order_no: str,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> dict[str, Any]:
    return await kitting_check(db, work_order_no, actor)


@router.post("/work-orders/{work_order_no}/receipt", response_model=WorkOrderReceiptResponse)
async def receive_work_order_endpoint(
    work_order_no: str,
    payload: ProductionReceiptCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "缺少 Idempotency-Key 请求头"},
        )
    return await receive_work_order(db, work_order_no, payload, actor, idempotency_key)


@router.get("/work-orders/{work_order_no}/traceability", response_model=WorkOrderTraceabilityRead)
async def get_work_order_traceability_endpoint(
    work_order_no: str,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> dict[str, Any]:
    return await get_work_order_traceability(db, work_order_no, actor)


@router.get("/work-orders", response_model=dict)
async def list_work_orders(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    keyword: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    filters = [WorkOrder.tenant_id == actor.tenant_id, WorkOrder.deleted_at.is_(None)]
    if status_filter:
        filters.append(WorkOrder.status == status_filter)
    if keyword:
        pattern = f"%{keyword}%"
        filters.append(
            or_(
                WorkOrder.work_order_no.ilike(pattern),
                WorkOrder.external_ref.ilike(pattern),
                WorkOrder.material_code_snapshot.ilike(pattern),
                WorkOrder.material_name_snapshot.ilike(pattern),
            )
        )

    total = await db.scalar(select(func.count()).select_from(WorkOrder).where(*filters))
    result = await db.scalars(
        select(WorkOrder).where(*filters).order_by(WorkOrder.created_at.desc()).limit(limit).offset(offset)
    )
    items = [
        WorkOrderListItem(
            id=row.id,
            tenant_id=row.tenant_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
            work_order_no=row.work_order_no,
            material_code=row.material_code_snapshot,
            material_name=row.material_name_snapshot,
            planned_qty=row.planned_qty,
            actual_good_qty=row.actual_good_qty,
            actual_bad_qty=row.actual_bad_qty,
            due_date=row.due_date,
            priority=row.priority,
            source=row.source,
            status=row.status,
            customer_name=row.customer_name,
            created_by=row.created_by,
        ).model_dump(mode="json")
        for row in list(result)
    ]
    return {"total": total or 0, "items": items}


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderRead)
async def get_work_order(
    work_order_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
) -> dict[str, Any]:
    result = await db.scalars(
        select(WorkOrder)
        .options(selectinload(WorkOrder.materials), selectinload(WorkOrder.operations))
        .where(
            WorkOrder.id == work_order_id,
            WorkOrder.tenant_id == actor.tenant_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    work_order = result.first()
    if not work_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return serialize_work_order(work_order)
