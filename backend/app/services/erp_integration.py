from __future__ import annotations

import hashlib
import hmac
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import Actor
from app.core.config import settings
from app.models.production import ErpWorkOrderFeedback, ProductionReceipt, WorkOrder
from app.schemas.integration import ErpFeedbackAck, ErpFeedbackRead, ErpWorkOrderAccepted, ErpWorkOrderCreate
from app.schemas.work_order import WorkOrderCreate
from app.services.audit import write_audit_log
from app.services.work_order import create_work_order, utcnow

ERP_ACTOR_CODE = "erp"


def require_erp_api_key(api_key: str | None) -> None:
    configured = settings.erp_integration_api_key
    if configured is None or not configured.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ERP_INTEGRATION_DISABLED", "message": "ERP integration API key is not configured"},
        )
    if not api_key or not hmac.compare_digest(api_key, configured.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_ERP_API_KEY", "message": "ERP API key is invalid"},
        )


def erp_idempotency_key(tenant_id: UUID, external_ref: str) -> str:
    digest = hashlib.sha256(f"{tenant_id}:{external_ref}".encode()).hexdigest()
    return f"erp:{digest}"


def serialize_erp_feedback(row: ErpWorkOrderFeedback) -> dict[str, Any]:
    return ErpFeedbackRead(
        id=row.id,
        external_ref=row.external_ref,
        work_order_no=row.work_order_no,
        receipt_no=row.receipt_no,
        actual_good_qty=row.actual_good_qty,
        actual_bad_qty=row.actual_bad_qty,
        lot_no=row.lot_no,
        warehouse_code=row.warehouse_code,
        completed_at=row.completed_at,
        status=row.status,
        attempt_count=row.attempt_count,
        last_attempt_at=row.last_attempt_at,
        last_error=row.last_error,
        acked_at=row.acked_at,
        request_payload=row.request_payload,
        response_payload=row.response_payload,
    ).model_dump(mode="json")


async def load_existing_erp_work_order(
    session: AsyncSession,
    payload: ErpWorkOrderCreate,
) -> WorkOrder | None:
    return await session.scalar(
        select(WorkOrder)
        .options(selectinload(WorkOrder.materials), selectinload(WorkOrder.operations))
        .where(
            WorkOrder.tenant_id == payload.tenant_id,
            WorkOrder.source == "erp",
            WorkOrder.external_ref == payload.external_ref,
            WorkOrder.deleted_at.is_(None),
        )
    )


def ensure_existing_work_order_matches(existing: WorkOrder, payload: ErpWorkOrderCreate) -> None:
    if existing.material_code_snapshot != payload.material_code or existing.planned_qty != payload.quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ERP_WORK_ORDER_CONFLICT",
                "message": "ERP work order already exists with different material or quantity",
                "work_order_no": existing.work_order_no,
            },
        )


async def accept_erp_work_order(session: AsyncSession, payload: ErpWorkOrderCreate) -> dict[str, Any]:
    existing = await load_existing_erp_work_order(session, payload)
    if existing:
        ensure_existing_work_order_matches(existing, payload)
        return ErpWorkOrderAccepted(
            work_order_no=existing.work_order_no,
            external_ref=existing.external_ref or payload.external_ref,
            status=existing.status,
        ).model_dump(mode="json")

    actor = Actor(tenant_id=payload.tenant_id, code=ERP_ACTOR_CODE, role="admin", display_name="ERP")
    created = await create_work_order(
        session,
        WorkOrderCreate(
            material_code=payload.material_code,
            quantity=payload.quantity,
            due_date=payload.due_date,
            priority=payload.priority,
            source="erp",
            external_ref=payload.external_ref,
            customer_name=payload.customer_name,
            remark=payload.remark,
        ),
        actor,
        erp_idempotency_key(payload.tenant_id, payload.external_ref),
    )
    return ErpWorkOrderAccepted(
        work_order_no=created["work_order_no"],
        external_ref=payload.external_ref,
        status=created["status"],
    ).model_dump(mode="json")


def build_erp_feedback_payload(work_order: WorkOrder, receipt: ProductionReceipt) -> dict[str, Any]:
    return jsonable_encoder(
        {
            "external_ref": work_order.external_ref,
            "work_order_no": work_order.work_order_no,
            "receipt_no": receipt.receipt_no,
            "status": work_order.status,
            "actual_good_qty": work_order.actual_good_qty,
            "actual_bad_qty": work_order.actual_bad_qty,
            "lot_no": receipt.lot_no,
            "warehouse_code": receipt.warehouse_code,
            "completed_at": receipt.received_at,
        }
    )


async def create_erp_feedback_if_needed(
    session: AsyncSession,
    work_order: WorkOrder,
    receipt: ProductionReceipt,
) -> ErpWorkOrderFeedback | None:
    if work_order.source != "erp" or not work_order.external_ref:
        return None

    payload = build_erp_feedback_payload(work_order, receipt)
    feedback = ErpWorkOrderFeedback(
        tenant_id=work_order.tenant_id,
        external_ref=work_order.external_ref,
        work_order_id=work_order.id,
        work_order_no=work_order.work_order_no,
        receipt_id=receipt.id,
        receipt_no=receipt.receipt_no,
        actual_good_qty=work_order.actual_good_qty,
        actual_bad_qty=work_order.actual_bad_qty,
        lot_no=receipt.lot_no,
        warehouse_code=receipt.warehouse_code,
        completed_at=receipt.received_at,
        status="pending",
        attempt_count=0,
        request_payload=payload,
    )
    session.add(feedback)
    await session.flush()
    await write_audit_log(
        session,
        tenant_id=work_order.tenant_id,
        actor_code=ERP_ACTOR_CODE,
        entity_type="erp_work_order_feedback",
        entity_id=feedback.id,
        action="create",
        detail={"external_ref": work_order.external_ref, "receipt_no": receipt.receipt_no},
    )
    return feedback


async def list_erp_feedback(
    session: AsyncSession,
    tenant_id: UUID,
    status_filter: str,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    rows = list(
        await session.scalars(
            select(ErpWorkOrderFeedback)
            .where(
                ErpWorkOrderFeedback.tenant_id == tenant_id,
                ErpWorkOrderFeedback.status == status_filter,
                ErpWorkOrderFeedback.deleted_at.is_(None),
            )
            .order_by(ErpWorkOrderFeedback.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
    )
    return [serialize_erp_feedback(row) for row in rows]


async def ack_erp_feedback(
    session: AsyncSession,
    feedback_id: UUID,
    tenant_id: UUID,
    payload: ErpFeedbackAck,
) -> dict[str, Any]:
    feedback = await session.scalar(
        select(ErpWorkOrderFeedback)
        .where(
            ErpWorkOrderFeedback.id == feedback_id,
            ErpWorkOrderFeedback.tenant_id == tenant_id,
            ErpWorkOrderFeedback.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ERP feedback record does not exist")

    feedback.status = "acked"
    feedback.acked_at = utcnow()
    feedback.response_payload = payload.response_payload
    await session.commit()
    await session.refresh(feedback)
    return serialize_erp_feedback(feedback)
