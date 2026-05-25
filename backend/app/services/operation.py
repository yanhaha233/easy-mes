from __future__ import annotations

from datetime import datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, case, false, or_, select
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
from app.services.work_order import business_error, ensure_worker_can_run_operations, payload_hash, utcnow

QUICK_REPORT_THRESHOLD_SECONDS = 60


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


async def load_worker_by_id(session: AsyncSession, tenant_id: UUID, worker_id: UUID) -> Worker | None:
    worker = await session.get(Worker, worker_id)
    if worker and worker.tenant_id == tenant_id and worker.deleted_at is None and worker.is_active:
        return worker
    return None


def operator_snapshot(worker: Worker | None, fallback_code: str) -> tuple[UUID | None, str, str]:
    if worker:
        return worker.id, worker.code, worker.name
    return None, fallback_code, "默认操作员"


async def resolve_operator(
    session: AsyncSession,
    actor: Actor,
    operator_code: str | None = None,
) -> tuple[UUID | None, str, str]:
    if actor.role != "admin" and not actor.worker_id and not actor.worker_code:
        business_error(status.HTTP_403_FORBIDDEN, "OPERATOR_ACCOUNT_NOT_LINKED", "当前账号未绑定操作员档案")
    if operator_code:
        if actor.role != "admin" and actor.worker_code != operator_code:
            business_error(status.HTTP_403_FORBIDDEN, "OPERATOR_CODE_MISMATCH", "不能代替其他操作员操作")
        worker = await load_worker(session, actor.tenant_id, operator_code)
        if not worker:
            business_error(status.HTTP_400_BAD_REQUEST, "OPERATOR_NOT_FOUND", f"操作员 {operator_code} 不存在或已停用")
        return operator_snapshot(worker, operator_code)
    if actor.worker_id:
        worker = await load_worker_by_id(session, actor.tenant_id, actor.worker_id)
        if not worker:
            business_error(status.HTTP_400_BAD_REQUEST, "OPERATOR_NOT_FOUND", "当前账号绑定的操作员不存在或已停用")
        return operator_snapshot(worker, actor.worker_code or actor.code)
    if actor.worker_code:
        worker = await load_worker(session, actor.tenant_id, actor.worker_code)
        if not worker:
            business_error(status.HTTP_400_BAD_REQUEST, "OPERATOR_NOT_FOUND", "当前账号绑定的操作员不存在或已停用")
        return operator_snapshot(worker, actor.worker_code)
    worker = await load_worker(session, actor.tenant_id, None)
    return operator_snapshot(worker, actor.code)


def ensure_actor_owns_started_operation(operation: WorkOrderOperation, actor: Actor) -> None:
    if actor.role == "admin" or operation.status not in {"in_progress", "paused"}:
        return
    if not operation.started_by_operator_id:
        return
    if actor.worker_id != operation.started_by_operator_id:
        business_error(status.HTTP_403_FORBIDDEN, "OPERATION_OWNED_BY_OTHER", "该工序已由其他操作员处理")


def assigned_to_actor_filter(operation: WorkOrderOperation, actor: Actor) -> bool:
    if actor.role == "admin":
        return True
    if operation.assigned_operator_id and actor.worker_id == operation.assigned_operator_id:
        return True
    return bool(operation.assigned_operator_code and actor.worker_code == operation.assigned_operator_code)


def ensure_actor_can_operate(operation: WorkOrderOperation, actor: Actor) -> None:
    if operation.status == "ready" and not assigned_to_actor_filter(operation, actor):
        business_error(status.HTTP_403_FORBIDDEN, "OPERATION_NOT_ASSIGNED_TO_YOU", "该工序未派给当前操作员")
    ensure_actor_owns_started_operation(operation, actor)


def effective_operation_planned_qty(operation: WorkOrderOperation, work_order: WorkOrder) -> Decimal:
    previous_operations = [item for item in work_order.operations if item.seq < operation.seq]
    if not previous_operations:
        return operation.planned_qty
    previous_operation = max(previous_operations, key=lambda item: item.seq)
    if previous_operation.status != "done":
        return operation.planned_qty
    return previous_operation.good_qty


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
        planned_qty=effective_operation_planned_qty(operation, work_order),
        good_qty=operation.good_qty,
        bad_qty=operation.bad_qty,
        status=operation.status,
        assigned_operator_code=operation.assigned_operator_code,
        assigned_operator_name=operation.assigned_operator_name,
        started_at=operation.started_at,
        started_by_operator_code=operation.started_by_operator_code,
        started_by_operator_name=operation.started_by_operator_name,
    ).model_dump(mode="json")


async def list_workbench_operations(
    session: AsyncSession,
    actor: Actor,
    statuses: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    allowed_statuses = {"ready", "in_progress", "paused"}
    requested_statuses = [item for item in statuses if item in allowed_statuses] or ["paused", "in_progress", "ready"]
    status_rank = case(
        (WorkOrderOperation.status == "paused", 0),
        (WorkOrderOperation.status == "in_progress", 1),
        (WorkOrderOperation.status == "ready", 2),
        else_=9,
    )
    filters = [
        WorkOrderOperation.tenant_id == actor.tenant_id,
        WorkOrderOperation.deleted_at.is_(None),
        WorkOrderOperation.status.in_(requested_statuses),
        WorkOrder.tenant_id == actor.tenant_id,
        WorkOrder.deleted_at.is_(None),
        WorkOrder.status.notin_(["closed", "cancelled"]),
    ]
    if actor.role != "admin":
        assigned_conditions = []
        if actor.worker_id:
            assigned_conditions.append(WorkOrderOperation.assigned_operator_id == actor.worker_id)
        if actor.worker_code:
            assigned_conditions.append(WorkOrderOperation.assigned_operator_code == actor.worker_code)
        assigned_ready_filter = and_(
            WorkOrderOperation.status == "ready",
            or_(*assigned_conditions) if assigned_conditions else false(),
        )
        own_running_filters = [
            WorkOrderOperation.status.in_(["paused", "in_progress"]),
            WorkOrderOperation.started_by_operator_id.is_not(None),
            WorkOrderOperation.started_by_operator_id == actor.worker_id,
        ]
        filters.append(or_(assigned_ready_filter, and_(*own_running_filters)))

    rows = list(
        (
            await session.execute(
                select(WorkOrderOperation, WorkOrder)
                .join(WorkOrder, WorkOrder.id == WorkOrderOperation.work_order_id)
                .options(selectinload(WorkOrder.operations))
                .where(*filters)
                .order_by(status_rank, WorkOrderOperation.updated_at.desc(), WorkOrderOperation.seq.asc())
                .limit(limit)
            )
        ).all()
    )
    return [serialize_operation(operation, work_order) for operation, work_order in rows]


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
        if operation:
            ensure_actor_can_operate(operation, actor)
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
        operation = (
            next(
                (
                    item
                    for item in operations
                    if item.status in {"paused", "in_progress"}
                    and (actor.role == "admin" or item.started_by_operator_id == actor.worker_id)
                ),
                None,
            )
            or next(
                (item for item in operations if item.status == "ready" and assigned_to_actor_filter(item, actor)),
                None,
            )
            or (
                next((item for item in operations if item.status in candidate_status), None)
                if actor.role == "admin"
                else None
            )
        )
        if not operation:
            business_error(status.HTTP_403_FORBIDDEN, "NO_ASSIGNED_OPERATION", "没有派给当前操作员的可处理工序")
        ensure_actor_can_operate(operation, actor)
        return serialize_operation(operation, work_order)

    work_order = await session.scalar(
        select(WorkOrder)
        .options(selectinload(WorkOrder.operations))
        .where(WorkOrder.id == operation.work_order_id)
    )
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
        ensure_actor_can_operate(operation, actor)
        if operation.status != "ready":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_OPERATION_STATUS",
                f"当前工序状态为 {operation.status}，不能开工",
            )
        if work_order.status not in {"pending", "scheduled", "in_progress"}:
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_WORK_ORDER_STATUS",
                f"当前工单状态为 {work_order.status}，不能开工",
            )

        operations = sorted(work_order.operations, key=lambda item: item.seq)
        sync_operation_plan_from_previous_good(operation, operations)
        operator_id, operator_code, operator_name = await resolve_operator(session, actor, payload.operator_code)
        if operator_id:
            worker = await load_worker_by_id(session, actor.tenant_id, operator_id)
            if worker:
                await ensure_worker_can_run_operations(session, worker, [operation])
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
        ensure_actor_can_operate(operation, actor)
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

        _, operator_code, _ = await resolve_operator(session, actor, payload.operator_code)
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
        ensure_actor_can_operate(operation, actor)
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

        _, operator_code, _ = await resolve_operator(session, actor, payload.operator_code)
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


def decimal_text(value: Decimal) -> str:
    return format(value, "f")


def validate_clock_quantity_against_plan(operation: WorkOrderOperation, payload: OperationClock) -> None:
    reported_qty = payload.good_qty + payload.bad_qty
    already_reported_qty = operation.good_qty + operation.bad_qty
    remaining_qty = operation.planned_qty - already_reported_qty
    if reported_qty > remaining_qty:
        business_error(
            status.HTTP_400_BAD_REQUEST,
            "CLOCK_QTY_EXCEEDS_OPERATION_PLAN",
            (
                f"本次报工数量 {decimal_text(reported_qty)} 超过工序剩余计划数 "
                f"{decimal_text(remaining_qty)}，不能报工"
            ),
        )


def pass_good_qty_to_next_operation(current_operation: WorkOrderOperation, next_operation: WorkOrderOperation) -> None:
    next_operation.planned_qty = current_operation.good_qty
    run_seconds = (Decimal(next_operation.unit_time_sec) * next_operation.planned_qty).to_integral_value(
        rounding=ROUND_CEILING
    )
    next_operation.planned_duration_sec = next_operation.setup_time_sec + int(run_seconds)


def sync_operation_plan_from_previous_good(
    operation: WorkOrderOperation,
    operations: list[WorkOrderOperation],
) -> None:
    previous_operations = [item for item in operations if item.seq < operation.seq]
    if not previous_operations:
        return
    previous_operation = max(previous_operations, key=lambda item: item.seq)
    if previous_operation.status != "done":
        return
    pass_good_qty_to_next_operation(previous_operation, operation)


def sync_work_order_actual_qty(work_order: WorkOrder, operations: list[WorkOrderOperation]) -> None:
    last_operation = operations[-1] if operations else None
    work_order.actual_good_qty = (
        last_operation.good_qty if last_operation and last_operation.status == "done" else Decimal("0")
    )
    work_order.actual_bad_qty = sum((item.bad_qty for item in operations), Decimal("0"))


def build_clock_time_anomaly(
    operation: WorkOrderOperation,
    payload: OperationClock,
    ended_at: datetime,
) -> tuple[int, bool, str | None, dict[str, Any] | None]:
    elapsed_seconds = max(0, int((ended_at - operation.started_at).total_seconds())) if operation.started_at else 0
    is_quick_report = elapsed_seconds < QUICK_REPORT_THRESHOLD_SECONDS
    if not is_quick_report:
        return elapsed_seconds, False, None, None

    detail = {
        "elapsed_seconds": elapsed_seconds,
        "threshold_seconds": QUICK_REPORT_THRESHOLD_SECONDS,
        "planned_duration_sec": operation.planned_duration_sec,
        "operation_seq": operation.seq,
        "reported_qty": str(payload.good_qty + payload.bad_qty),
        "server_started_at": operation.started_at.isoformat() if operation.started_at else None,
        "server_ended_at": ended_at.isoformat(),
    }
    return elapsed_seconds, True, "quick_report", detail


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
        ensure_actor_can_operate(operation, actor)
        if operation.status != "in_progress":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_OPERATION_STATUS",
                f"当前工序状态为 {operation.status}，不能报工",
            )
        if not operation.started_at:
            business_error(status.HTTP_400_BAD_REQUEST, "OPERATION_NOT_STARTED", "工序缺少开工时间，不能报工")
        operations = sorted(work_order.operations, key=lambda item: item.seq)
        sync_operation_plan_from_previous_good(operation, operations)
        validate_clock_quantity_against_plan(operation, payload)

        operator_id, operator_code, operator_name = await resolve_operator(session, actor, payload.operator_code)
        elapsed_seconds, time_anomaly, time_anomaly_reason, time_anomaly_detail = build_clock_time_anomaly(
            operation,
            payload,
            now,
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
            elapsed_seconds=elapsed_seconds,
            time_anomaly=time_anomaly,
            time_anomaly_reason=time_anomaly_reason,
            time_anomaly_detail=time_anomaly_detail,
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

        next_operation = next(
            (item for item in operations if item.seq > operation.seq and item.status == "pending"),
            None,
        )
        if next_operation:
            pass_good_qty_to_next_operation(operation, next_operation)
            next_operation.status = "ready"
            if not next_operation.assigned_operator_id and not next_operation.assigned_operator_code:
                if operator_id:
                    worker = await load_worker_by_id(session, actor.tenant_id, operator_id)
                    if worker:
                        await ensure_worker_can_run_operations(session, worker, [next_operation])
                next_operation.assigned_operator_id = operation.assigned_operator_id or operator_id
                next_operation.assigned_operator_code = operation.assigned_operator_code or operator_code
                next_operation.assigned_operator_name = operation.assigned_operator_name or operator_name
            sync_work_order_actual_qty(work_order, operations)
        elif all(item.status == "done" for item in operations):
            sync_work_order_actual_qty(work_order, operations)
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
                detail={
                    "operation_id": str(operation.id),
                    "operation_seq": operation.seq,
                    "actual_good_qty": str(work_order.actual_good_qty),
                    "actual_bad_qty": str(work_order.actual_bad_qty),
                },
            )
        else:
            sync_work_order_actual_qty(work_order, operations)

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
                "elapsed_seconds": elapsed_seconds,
                "time_anomaly": time_anomaly,
                "time_anomaly_reason": time_anomaly_reason,
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
            elapsed_seconds=elapsed_seconds,
            time_anomaly=time_anomaly,
            time_anomaly_reason=time_anomaly_reason,
            time_anomaly_detail=time_anomaly_detail,
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
