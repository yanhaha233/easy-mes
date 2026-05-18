from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import Actor
from app.core.defaults import DEFAULT_OPERATOR_CODE
from app.models.master_data import Worker
from app.models.production import ClockRecord, IdempotencyKey, WorkOrder, WorkOrderOperation
from app.schemas.operation import (
    OperationClock,
    OperationClockRead,
    OperationRead,
    OperationStart,
    OperationStateChange,
)
from app.services.audit import write_audit_log
from app.services.work_order import business_error, payload_hash, utcnow


async def load_worker(session: AsyncSession, tenant_id: UUID, operator_code: str | None) -> Worker | None:
    code = operator_code or DEFAULT_OPERATOR_CODE
    return await session.scalar(
        select(Worker).where(
            Worker.tenant_id == tenant_id,
            Worker.code == code,
            Worker.deleted_at.is_(None),
            Worker.is_active.is_(True),
        )
    )


def operator_snapshot(worker: Worker | None, fallback_code: str) -> tuple[UUID | None, str, str]:
    if worker:
        return worker.id, worker.code, worker.name
    return None, fallback_code, "默认操作员"


async def load_operation_with_order(
    session: AsyncSession,
    operation_id: UUID,
    actor: Actor,
    *,
    lock: bool = False,
) -> tuple[WorkOrderOperation, WorkOrder]:
    operation_stmt = select(WorkOrderOperation).where(
        WorkOrderOperation.id == operation_id,
        WorkOrderOperation.tenant_id == actor.tenant_id,
        WorkOrderOperation.deleted_at.is_(None),
    )
    if lock:
        operation_stmt = operation_stmt.with_for_update()
    operation = await session.scalar(operation_stmt)
    if not operation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工序不存在")

    order_stmt = (
        select(WorkOrder)
        .options(selectinload(WorkOrder.operations))
        .where(
            WorkOrder.id == operation.work_order_id,
            WorkOrder.tenant_id == actor.tenant_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    if lock:
        order_stmt = order_stmt.with_for_update()
    work_order = await session.scalar(order_stmt)
    if not work_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return operation, work_order


def serialize_operation(operation: WorkOrderOperation, work_order: WorkOrder) -> dict[str, Any]:
    return OperationRead(
        id=operation.id,
        tenant_id=operation.tenant_id,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
        deleted_at=operation.deleted_at,
        work_order_id=work_order.id,
        work_order_no=work_order.work_order_no,
        work_order_status=work_order.status,
        material_code=work_order.material_code_snapshot,
        material_name=work_order.material_name_snapshot,
        seq=operation.seq,
        operation_code=operation.operation_code_snapshot,
        operation_name=operation.operation_name_snapshot,
        work_center_id=operation.work_center_id,
        work_center_code=operation.work_center_code_snapshot,
        work_center_name=operation.work_center_name_snapshot,
        setup_time_sec=operation.setup_time_sec,
        unit_time_sec=operation.unit_time_sec,
        planned_duration_sec=operation.planned_duration_sec,
        planned_qty=operation.planned_qty,
        good_qty=operation.good_qty,
        bad_qty=operation.bad_qty,
        status=operation.status,
        started_at=operation.started_at,
        started_by_operator_code=operation.started_by_operator_code,
        started_by_operator_name=operation.started_by_operator_name,
    ).model_dump(mode="json")


async def get_operation_by_qr(session: AsyncSession, code: str, actor: Actor) -> dict[str, Any]:
    operation: WorkOrderOperation | None = None
    try:
        operation_id = UUID(code)
    except ValueError:
        operation_id = None

    if operation_id:
        operation = await session.scalar(
            select(WorkOrderOperation).where(
                WorkOrderOperation.id == operation_id,
                WorkOrderOperation.tenant_id == actor.tenant_id,
                WorkOrderOperation.deleted_at.is_(None),
            )
        )
    if not operation:
        work_order = await session.scalar(
            select(WorkOrder)
            .options(selectinload(WorkOrder.operations))
            .where(
                WorkOrder.work_order_no == code,
                WorkOrder.tenant_id == actor.tenant_id,
                WorkOrder.deleted_at.is_(None),
            )
        )
        if not work_order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="二维码未匹配到工序或工单")
        candidate_status = {"ready", "in_progress", "paused"}
        operations = sorted(work_order.operations, key=lambda item: item.seq)
        operation = next((item for item in operations if item.status in candidate_status), None) or operations[0]
        return serialize_operation(operation, work_order)

    work_order = await session.get(WorkOrder, operation.work_order_id)
    if not work_order or work_order.tenant_id != actor.tenant_id or work_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return serialize_operation(operation, work_order)


async def start_operation(
    session: AsyncSession,
    operation_id: UUID,
    payload: OperationStart,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    now = utcnow()
    hashed = payload_hash({"operation_id": str(operation_id), "payload": payload.model_dump(mode="json")})

    async with session.begin():
        cached = await session.scalar(
            select(IdempotencyKey)
            .where(IdempotencyKey.tenant_id == actor.tenant_id, IdempotencyKey.key == idempotency_key)
            .with_for_update()
        )
        if cached:
            if cached.request_hash != hashed:
                business_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "同一幂等键重复提交了不同请求体",
                )
            return cached.response_body

        operation, work_order = await load_operation_with_order(session, operation_id, actor, lock=True)
        if operation.status != "ready":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_OPERATION_STATUS",
                f"当前工序状态为 {operation.status}，不能开工",
            )
        if work_order.status not in {"pending", "scheduled"}:
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_WORK_ORDER_STATUS",
                f"当前工单状态为 {work_order.status}，不能开工",
            )

        worker = await load_worker(session, actor.tenant_id, payload.operator_code)
        operator_id, operator_code, operator_name = operator_snapshot(worker, payload.operator_code or actor.code)
        old_order_status = work_order.status
        operation.status = "in_progress"
        operation.started_at = now
        operation.started_by_operator_id = operator_id
        operation.started_by_operator_code = operator_code
        operation.started_by_operator_name = operator_name
        work_order.status = "in_progress"

        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=operator_code,
            entity_type="operation",
            entity_id=operation.id,
            action="start",
            from_state="ready",
            to_state="in_progress",
            detail={"work_order_no": work_order.work_order_no, "operation_seq": operation.seq},
        )
        if old_order_status != work_order.status:
            await write_audit_log(
                session,
                tenant_id=actor.tenant_id,
                actor_code=operator_code,
                entity_type="work_order",
                entity_id=work_order.id,
                action="start",
                from_state=old_order_status,
                to_state=work_order.status,
                detail={"operation_id": str(operation.id), "operation_seq": operation.seq},
            )
        await session.flush()
        await session.refresh(work_order, attribute_names=["updated_at"])
        await session.refresh(operation, attribute_names=["updated_at"])
        response = serialize_operation(operation, work_order)
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed,
                response_body=response,
                expires_at=now + timedelta(hours=24),
            )
        )

    return response


async def pause_operation(
    session: AsyncSession,
    operation_id: UUID,
    payload: OperationStateChange,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    now = utcnow()
    hashed = payload_hash(
        {"operation_id": str(operation_id), "action": "pause", "payload": payload.model_dump(mode="json")}
    )

    async with session.begin():
        cached = await session.scalar(
            select(IdempotencyKey)
            .where(IdempotencyKey.tenant_id == actor.tenant_id, IdempotencyKey.key == idempotency_key)
            .with_for_update()
        )
        if cached:
            if cached.request_hash != hashed:
                business_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "同一幂等键重复提交了不同请求体",
                )
            return cached.response_body

        operation, work_order = await load_operation_with_order(session, operation_id, actor, lock=True)
        if operation.status != "in_progress":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_OPERATION_STATUS",
                f"当前工序状态为 {operation.status}，不能暂停",
            )
        if work_order.status != "in_progress":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_WORK_ORDER_STATUS",
                f"当前工单状态为 {work_order.status}，不能暂停",
            )

        worker = await load_worker(session, actor.tenant_id, payload.operator_code)
        _, operator_code, _ = operator_snapshot(
            worker,
            payload.operator_code or operation.started_by_operator_code or actor.code,
        )
        operation.status = "paused"
        work_order.status = "paused"
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=operator_code,
            entity_type="operation",
            entity_id=operation.id,
            action="pause",
            from_state="in_progress",
            to_state="paused",
            detail={
                "work_order_no": work_order.work_order_no,
                "operation_seq": operation.seq,
                "reason": payload.reason,
            },
        )
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=operator_code,
            entity_type="work_order",
            entity_id=work_order.id,
            action="pause",
            from_state="in_progress",
            to_state="paused",
            detail={"operation_id": str(operation.id), "operation_seq": operation.seq, "reason": payload.reason},
        )
        await session.flush()
        await session.refresh(work_order, attribute_names=["updated_at"])
        await session.refresh(operation, attribute_names=["updated_at"])
        response = serialize_operation(operation, work_order)
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed,
                response_body=response,
                expires_at=now + timedelta(hours=24),
            )
        )
    return response


async def resume_operation(
    session: AsyncSession,
    operation_id: UUID,
    payload: OperationStateChange,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    now = utcnow()
    hashed = payload_hash(
        {"operation_id": str(operation_id), "action": "resume", "payload": payload.model_dump(mode="json")}
    )

    async with session.begin():
        cached = await session.scalar(
            select(IdempotencyKey)
            .where(IdempotencyKey.tenant_id == actor.tenant_id, IdempotencyKey.key == idempotency_key)
            .with_for_update()
        )
        if cached:
            if cached.request_hash != hashed:
                business_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "同一幂等键重复提交了不同请求体",
                )
            return cached.response_body

        operation, work_order = await load_operation_with_order(session, operation_id, actor, lock=True)
        if operation.status != "paused":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_OPERATION_STATUS",
                f"当前工序状态为 {operation.status}，不能恢复",
            )
        if work_order.status != "paused":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_WORK_ORDER_STATUS",
                f"当前工单状态为 {work_order.status}，不能恢复",
            )

        worker = await load_worker(session, actor.tenant_id, payload.operator_code)
        _, operator_code, _ = operator_snapshot(
            worker,
            payload.operator_code or operation.started_by_operator_code or actor.code,
        )
        operation.status = "in_progress"
        work_order.status = "in_progress"
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=operator_code,
            entity_type="operation",
            entity_id=operation.id,
            action="resume",
            from_state="paused",
            to_state="in_progress",
            detail={
                "work_order_no": work_order.work_order_no,
                "operation_seq": operation.seq,
                "reason": payload.reason,
            },
        )
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=operator_code,
            entity_type="work_order",
            entity_id=work_order.id,
            action="resume",
            from_state="paused",
            to_state="in_progress",
            detail={"operation_id": str(operation.id), "operation_seq": operation.seq, "reason": payload.reason},
        )
        await session.flush()
        await session.refresh(work_order, attribute_names=["updated_at"])
        await session.refresh(operation, attribute_names=["updated_at"])
        response = serialize_operation(operation, work_order)
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed,
                response_body=response,
                expires_at=now + timedelta(hours=24),
            )
        )
    return response


def validate_clock_payload(payload: OperationClock) -> None:
    if payload.good_qty + payload.bad_qty <= 0:
        business_error(status.HTTP_400_BAD_REQUEST, "INVALID_CLOCK_QTY", "合格数和不良数合计必须大于 0")
    defect_qty = sum((item.qty for item in payload.defects), Decimal("0"))
    if defect_qty != payload.bad_qty:
        business_error(status.HTTP_400_BAD_REQUEST, "DEFECT_QTY_MISMATCH", "不良原因数量合计必须等于不良数")


async def clock_operation(
    session: AsyncSession,
    operation_id: UUID,
    payload: OperationClock,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    validate_clock_payload(payload)
    now = utcnow()
    hashed = payload_hash({"operation_id": str(operation_id), "payload": payload.model_dump(mode="json")})

    async with session.begin():
        cached = await session.scalar(
            select(IdempotencyKey)
            .where(IdempotencyKey.tenant_id == actor.tenant_id, IdempotencyKey.key == idempotency_key)
            .with_for_update()
        )
        if cached:
            if cached.request_hash != hashed:
                business_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "同一幂等键重复提交了不同请求体",
                )
            return cached.response_body

        operation, work_order = await load_operation_with_order(session, operation_id, actor, lock=True)
        if operation.status != "in_progress":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_OPERATION_STATUS",
                f"当前工序状态为 {operation.status}，不能报工",
            )
        if not operation.started_at:
            business_error(status.HTTP_400_BAD_REQUEST, "OPERATION_NOT_STARTED", "工序缺少开工时间，不能报工")

        worker = await load_worker(
            session,
            actor.tenant_id,
            payload.operator_code or operation.started_by_operator_code,
        )
        operator_id, operator_code, operator_name = operator_snapshot(
            worker,
            payload.operator_code or operation.started_by_operator_code or actor.code,
        )

        clock_record = ClockRecord(
            tenant_id=actor.tenant_id,
            work_order_id=work_order.id,
            operation_id=operation.id,
            work_order_no_snapshot=work_order.work_order_no,
            operation_seq_snapshot=operation.seq,
            operation_code_snapshot=operation.operation_code_snapshot,
            operation_name_snapshot=operation.operation_name_snapshot,
            work_center_id=operation.work_center_id,
            work_center_code_snapshot=operation.work_center_code_snapshot,
            work_center_name_snapshot=operation.work_center_name_snapshot,
            operator_id=operator_id,
            operator_code_snapshot=operator_code,
            operator_name_snapshot=operator_name,
            started_at=operation.started_at,
            ended_at=now,
            good_qty=payload.good_qty,
            bad_qty=payload.bad_qty,
            defects=[item.model_dump(mode="json") for item in payload.defects],
            material_consumed=[item.model_dump(mode="json") for item in payload.actual_materials],
            remark=payload.remark,
        )
        session.add(clock_record)

        operation.good_qty += payload.good_qty
        operation.bad_qty += payload.bad_qty
        operation.status = "done"
        work_order.actual_good_qty += payload.good_qty
        work_order.actual_bad_qty += payload.bad_qty

        operations = sorted(work_order.operations, key=lambda item: item.seq)
        next_operation = next(
            (item for item in operations if item.seq > operation.seq and item.status == "pending"),
            None,
        )
        if next_operation:
            next_operation.status = "ready"
        elif all(item.status == "done" for item in operations):
            old_order_status = work_order.status
            work_order.status = "completed"
            await write_audit_log(
                session,
                tenant_id=actor.tenant_id,
                actor_code=operator_code,
                entity_type="work_order",
                entity_id=work_order.id,
                action="complete",
                from_state=old_order_status,
                to_state="completed",
                detail={"operation_id": str(operation.id), "operation_seq": operation.seq},
            )

        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=operator_code,
            entity_type="operation",
            entity_id=operation.id,
            action="clock",
            from_state="in_progress",
            to_state="done",
            detail={
                "work_order_no": work_order.work_order_no,
                "good_qty": str(payload.good_qty),
                "bad_qty": str(payload.bad_qty),
                "next_operation_id": str(next_operation.id) if next_operation else None,
            },
        )
        await session.flush()
        await session.refresh(work_order, attribute_names=["updated_at"])
        await session.refresh(operation, attribute_names=["updated_at"])
        response = OperationClockRead(
            operation=OperationRead.model_validate(serialize_operation(operation, work_order)),
            work_order_status=work_order.status,
            next_operation_id=next_operation.id if next_operation else None,
            clock_record_id=clock_record.id,
        ).model_dump(mode="json")
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed,
                response_body=response,
                expires_at=now + timedelta(hours=24),
            )
        )

    return response
