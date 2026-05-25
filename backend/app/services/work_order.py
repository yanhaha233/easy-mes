from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import Actor
from app.core.defaults import DEFAULT_OPERATOR_CODE
from app.models.auth import UserAccount
from app.models.master_data import (
    Bom,
    BomLine,
    Material,
    Routing,
    RoutingOperation,
    WorkCenter,
    Worker,
    WorkerOperationSkill,
)
from app.models.production import (
    AuditLog,
    ClockRecord,
    DocumentSequence,
    IdempotencyKey,
    ProductionReceipt,
    QualityRecord,
    WorkOrder,
    WorkOrderMaterial,
    WorkOrderOperation,
)
from app.schemas.work_order import (
    ProductionReceiptCreate,
    WorkOrderCancel,
    WorkOrderCreate,
    WorkOrderRead,
    WorkOrderSchedule,
)
from app.services.audit import write_audit_log

PRODUCIBLE_MATERIAL_TYPES = {"product", "semi_finished"}


def business_error(http_status: int, code: str, message: str, detail: dict[str, Any] | None = None) -> None:
    error_detail: dict[str, Any] = {"code": code, "message": message}
    if detail:
        error_detail.update(detail)
    raise HTTPException(status_code=http_status, detail=error_detail)


def utcnow() -> datetime:
    return datetime.now(UTC)


def payload_hash(body: Any) -> str:
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def request_hash(payload: WorkOrderCreate) -> str:
    return payload_hash(payload.model_dump(mode="json"))


def confirm_request_hash(work_order_no: str) -> str:
    return payload_hash({"work_order_no": work_order_no, "action": "confirm"})


def schedule_request_hash(work_order_no: str, payload: WorkOrderSchedule) -> str:
    return payload_hash(
        {"work_order_no": work_order_no, "action": "schedule", "payload": payload.model_dump(mode="json")}
    )


def receipt_request_hash(work_order_no: str, payload: ProductionReceiptCreate) -> str:
    return payload_hash({"work_order_no": work_order_no, "payload": payload.model_dump(mode="json")})


def moneyless_decimal(value: Decimal) -> str:
    return format(value, "f")


def ceil_seconds(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def derive_work_order_status(work_order: WorkOrder, operations: list[WorkOrderOperation]) -> str:
    if work_order.status in {"draft", "closed", "cancelled"}:
        return work_order.status

    active_operations = [item for item in operations if item.deleted_at is None and item.status != "cancelled"]
    if not active_operations:
        return work_order.status
    if all(item.status == "done" for item in active_operations):
        return "completed"
    if any(item.status in {"in_progress", "reporting"} for item in active_operations):
        return "in_progress"
    if all(item.status == "paused" for item in active_operations):
        return "paused"
    if any(item.status == "ready" for item in active_operations):
        return "scheduled"
    if all(item.status == "pending" for item in active_operations):
        return "pending"
    return work_order.status


def sync_work_order_status_from_operations(
    work_order: WorkOrder,
    operations: list[WorkOrderOperation],
) -> tuple[str, str]:
    old_status = work_order.status
    work_order.status = derive_work_order_status(work_order, operations)
    return old_status, work_order.status


async def next_work_order_no(session: AsyncSession, tenant_id: UUID, now: datetime) -> str:
    period = now.strftime("%Y%m")
    await session.execute(
        pg_insert(DocumentSequence)
        .values(
            tenant_id=tenant_id,
            sequence_type="work_order",
            period=period,
            current_value=0,
        )
        .on_conflict_do_nothing(constraint="uq_document_sequences_scope")
    )
    sequence = await session.scalar(
        select(DocumentSequence)
        .where(
            DocumentSequence.tenant_id == tenant_id,
            DocumentSequence.sequence_type == "work_order",
            DocumentSequence.period == period,
        )
        .with_for_update()
    )
    if not sequence:
        business_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "SEQUENCE_NOT_FOUND", "工单号序列生成失败")
    sequence.current_value += 1
    sequence.updated_at = now
    return f"WO-{period}-{sequence.current_value:04d}"


async def next_receipt_no(session: AsyncSession, tenant_id: UUID, now: datetime) -> str:
    period = now.strftime("%Y%m")
    await session.execute(
        pg_insert(DocumentSequence)
        .values(
            tenant_id=tenant_id,
            sequence_type="production_receipt",
            period=period,
            current_value=0,
        )
        .on_conflict_do_nothing(constraint="uq_document_sequences_scope")
    )
    sequence = await session.scalar(
        select(DocumentSequence)
        .where(
            DocumentSequence.tenant_id == tenant_id,
            DocumentSequence.sequence_type == "production_receipt",
            DocumentSequence.period == period,
        )
        .with_for_update()
    )
    if not sequence:
        business_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "SEQUENCE_NOT_FOUND", "入库单号序列生成失败")
    sequence.current_value += 1
    sequence.updated_at = now
    return f"IN-{period}-{sequence.current_value:04d}"


def active_window_filter(model: type[Bom] | type[Routing], now: datetime) -> list[Any]:
    return [
        model.status == "active",
        model.deleted_at.is_(None),
        or_(model.effective_from.is_(None), model.effective_from <= now),
        or_(model.effective_to.is_(None), model.effective_to > now),
    ]


async def load_material(session: AsyncSession, payload: WorkOrderCreate, actor: Actor) -> Material:
    material = await session.scalar(
        select(Material)
        .where(
            Material.tenant_id == actor.tenant_id,
            Material.code == payload.material_code,
            Material.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if not material:
        business_error(status.HTTP_400_BAD_REQUEST, "MATERIAL_NOT_FOUND", "物料不存在")
    if not material.is_active:
        business_error(status.HTTP_400_BAD_REQUEST, "MATERIAL_INACTIVE", "物料已停用")
    if material.material_type not in PRODUCIBLE_MATERIAL_TYPES:
        business_error(status.HTTP_400_BAD_REQUEST, "MATERIAL_NOT_PRODUCIBLE", "物料不是可生产类型")
    return material


async def load_active_bom(session: AsyncSession, material: Material, now: datetime, actor: Actor) -> Bom | None:
    boms = list(
        await session.scalars(
            select(Bom)
            .options(selectinload(Bom.lines).selectinload(BomLine.component_material))
            .where(Bom.tenant_id == actor.tenant_id, Bom.material_id == material.id, *active_window_filter(Bom, now))
            .order_by(Bom.created_at.desc())
        )
    )
    if len(boms) > 1:
        business_error(status.HTTP_409_CONFLICT, "MULTIPLE_ACTIVE_BOMS", "同一物料存在多个激活 BOM")
    return boms[0] if boms else None


async def load_active_routing(session: AsyncSession, material: Material, now: datetime, actor: Actor) -> Routing:
    routings = list(
        await session.scalars(
            select(Routing)
            .options(selectinload(Routing.operations).selectinload(RoutingOperation.work_center))
            .where(
                Routing.tenant_id == actor.tenant_id,
                Routing.material_id == material.id,
                *active_window_filter(Routing, now),
            )
            .order_by(Routing.created_at.desc())
        )
    )
    if not routings:
        business_error(status.HTTP_400_BAD_REQUEST, "ACTIVE_ROUTING_NOT_FOUND", "没有激活的工艺路线")
    if len(routings) > 1:
        business_error(status.HTTP_409_CONFLICT, "MULTIPLE_ACTIVE_ROUTINGS", "同一物料存在多个激活工艺路线")
    return routings[0]


def build_material_rows(
    work_order: WorkOrder,
    bom: Bom | None,
    material: Material,
    planned_qty: Decimal,
) -> list[WorkOrderMaterial]:
    if not bom:
        if material.allow_empty_bom:
            return []
        business_error(status.HTTP_400_BAD_REQUEST, "ACTIVE_BOM_NOT_FOUND", "没有激活的 BOM")

    rows: list[WorkOrderMaterial] = []
    for line in sorted(bom.lines, key=lambda item: item.line_no):
        component = line.component_material
        if not component or component.deleted_at is not None or not component.is_active:
            business_error(status.HTTP_400_BAD_REQUEST, "COMPONENT_MATERIAL_NOT_FOUND", "BOM 子件物料不存在或已停用")
        required_qty = planned_qty * line.qty_per * (Decimal("1") + line.loss_rate)
        rows.append(
            WorkOrderMaterial(
                tenant_id=work_order.tenant_id,
                bom_id=bom.id,
                bom_version=bom.version,
                bom_line_id=line.id,
                component_material_id=component.id,
                component_code_snapshot=component.code,
                component_name_snapshot=component.name,
                component_spec_snapshot=component.spec,
                component_unit_snapshot=component.unit,
                qty_per=line.qty_per,
                loss_rate=line.loss_rate,
                required_qty=required_qty,
                issued_qty=Decimal("0"),
                consumed_qty=Decimal("0"),
            )
        )
    if not rows and not material.allow_empty_bom:
        business_error(status.HTTP_400_BAD_REQUEST, "ACTIVE_BOM_NOT_FOUND", "激活 BOM 没有子件明细")
    return rows


def build_operation_rows(work_order: WorkOrder, routing: Routing, planned_qty: Decimal) -> list[WorkOrderOperation]:
    active_operations = [operation for operation in routing.operations if operation.is_active]
    active_operations.sort(key=lambda item: item.seq)
    if not active_operations:
        business_error(status.HTTP_400_BAD_REQUEST, "ROUTING_OPERATIONS_EMPTY", "工艺路线没有有效工序")

    rows: list[WorkOrderOperation] = []
    for operation in active_operations:
        work_center: WorkCenter | None = operation.work_center
        if not work_center or work_center.deleted_at is not None or not work_center.is_active:
            business_error(status.HTTP_400_BAD_REQUEST, "WORK_CENTER_NOT_FOUND", "工序绑定的工位不存在或已停用")
        planned_duration = operation.setup_time_sec + ceil_seconds(Decimal(operation.unit_time_sec) * planned_qty)
        rows.append(
            WorkOrderOperation(
                tenant_id=work_order.tenant_id,
                routing_id=routing.id,
                routing_version=routing.version,
                routing_operation_id=operation.id,
                seq=operation.seq,
                operation_code_snapshot=operation.operation_code,
                operation_name_snapshot=operation.operation_name,
                work_center_id=work_center.id,
                work_center_code_snapshot=work_center.code,
                work_center_name_snapshot=work_center.name,
                setup_time_sec=operation.setup_time_sec,
                unit_time_sec=operation.unit_time_sec,
                planned_duration_sec=planned_duration,
                planned_qty=planned_qty,
                good_qty=Decimal("0"),
                bad_qty=Decimal("0"),
                status="pending",
            )
        )
    return rows


async def load_schedule_operator(session: AsyncSession, tenant_id: UUID, operator_code: str | None) -> Worker:
    code = operator_code or DEFAULT_OPERATOR_CODE
    worker = await session.scalar(
        select(Worker).where(
            Worker.tenant_id == tenant_id,
            Worker.code == code,
            Worker.deleted_at.is_(None),
            Worker.is_active.is_(True),
        )
    )
    if not worker:
        business_error(status.HTTP_400_BAD_REQUEST, "OPERATOR_NOT_FOUND", f"操作员 {code} 不存在或已停用")
    if worker.worker_type != "operator":
        business_error(status.HTTP_400_BAD_REQUEST, "WORKER_NOT_OPERATOR", f"{code} 不是操作员")
    return worker


async def worker_operation_skill_codes(session: AsyncSession, worker: Worker) -> set[str]:
    rows = await session.scalars(
        select(WorkerOperationSkill.operation_code).where(
            WorkerOperationSkill.tenant_id == worker.tenant_id,
            WorkerOperationSkill.worker_id == worker.id,
            WorkerOperationSkill.deleted_at.is_(None),
            WorkerOperationSkill.is_active.is_(True),
        )
    )
    return set(rows)


async def ensure_worker_can_run_operations(
    session: AsyncSession,
    worker: Worker,
    operations: list[WorkOrderOperation],
) -> None:
    skill_codes = await worker_operation_skill_codes(session, worker)
    missing_operations = [
        operation for operation in operations if operation.operation_code_snapshot not in skill_codes
    ]
    if missing_operations:
        business_error(
            status.HTTP_400_BAD_REQUEST,
            "OPERATOR_OPERATION_SKILL_MISSING",
            f"操作员 {worker.code} 不具备部分工序权限",
            {
                "operator_code": worker.code,
                "operator_name": worker.name,
                "operations": [
                    {
                        "operation_seq": operation.seq,
                        "operation_code": operation.operation_code_snapshot,
                        "operation_name": operation.operation_name_snapshot,
                    }
                    for operation in missing_operations
                ],
            },
        )


def assign_operation_to_worker(operation: WorkOrderOperation, worker: Worker) -> None:
    operation.assigned_operator_id = worker.id
    operation.assigned_operator_code = worker.code
    operation.assigned_operator_name = worker.name


def serialize_work_order(work_order: WorkOrder) -> dict[str, Any]:
    materials = sorted(work_order.materials, key=lambda item: item.component_code_snapshot)
    operations = sorted(work_order.operations, key=lambda item: item.seq)
    return WorkOrderRead(
        id=work_order.id,
        tenant_id=work_order.tenant_id,
        created_at=work_order.created_at,
        updated_at=work_order.updated_at,
        deleted_at=work_order.deleted_at,
        work_order_no=work_order.work_order_no,
        source=work_order.source,
        external_ref=work_order.external_ref,
        material_id=work_order.material_id,
        material={
            "code": work_order.material_code_snapshot,
            "name": work_order.material_name_snapshot,
            "spec": work_order.material_spec_snapshot,
            "unit": work_order.material_unit_snapshot,
        },
        planned_qty=work_order.planned_qty,
        actual_good_qty=work_order.actual_good_qty,
        actual_bad_qty=work_order.actual_bad_qty,
        due_date=work_order.due_date,
        priority=work_order.priority,
        customer_name=work_order.customer_name,
        status=work_order.status,
        bom={
            "id": work_order.bom_id,
            "version": work_order.bom_version,
            "material_lines": len(materials),
        },
        routing={
            "id": work_order.routing_id,
            "version": work_order.routing_version,
            "operation_lines": len(operations),
        },
        created_by=work_order.created_by,
        remark=work_order.remark,
        materials_required=[
            {
                "id": row.id,
                "tenant_id": row.tenant_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "deleted_at": row.deleted_at,
                "component_material_id": row.component_material_id,
                "material_code": row.component_code_snapshot,
                "material_name": row.component_name_snapshot,
                "material_spec": row.component_spec_snapshot,
                "unit": row.component_unit_snapshot,
                "qty_per": row.qty_per,
                "loss_rate": row.loss_rate,
                "required_qty": row.required_qty,
                "issued_qty": row.issued_qty,
                "consumed_qty": row.consumed_qty,
            }
            for row in materials
        ],
        operations=[
            {
                "id": row.id,
                "tenant_id": row.tenant_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "deleted_at": row.deleted_at,
                "seq": row.seq,
                "operation_code": row.operation_code_snapshot,
                "operation_name": row.operation_name_snapshot,
                "work_center_id": row.work_center_id,
                "work_center_code": row.work_center_code_snapshot,
                "work_center_name": row.work_center_name_snapshot,
                "setup_time_sec": row.setup_time_sec,
                "unit_time_sec": row.unit_time_sec,
                "planned_duration_sec": row.planned_duration_sec,
                "planned_qty": row.planned_qty,
                "good_qty": row.good_qty,
                "bad_qty": row.bad_qty,
                "status": row.status,
                "assigned_operator_code": row.assigned_operator_code,
                "assigned_operator_name": row.assigned_operator_name,
                "started_at": row.started_at,
                "started_by_operator_code": row.started_by_operator_code,
                "started_by_operator_name": row.started_by_operator_name,
            }
            for row in operations
        ],
    ).model_dump(mode="json")


async def create_work_order(
    session: AsyncSession,
    payload: WorkOrderCreate,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    now = utcnow()
    hashed_payload = request_hash(payload)

    async with session.begin():
        cached = await session.scalar(
            select(IdempotencyKey)
            .where(
                IdempotencyKey.tenant_id == actor.tenant_id,
                IdempotencyKey.key == idempotency_key,
            )
            .with_for_update()
        )
        if cached:
            if cached.request_hash != hashed_payload:
                business_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "同一幂等键重复提交了不同请求体",
                )
            return cached.response_body

        material = await load_material(session, payload, actor)
        bom = await load_active_bom(session, material, now, actor)
        routing = await load_active_routing(session, material, now, actor)
        work_order_no = await next_work_order_no(session, actor.tenant_id, now)
        initial_status = "draft" if payload.source == "manual" else "pending"

        work_order = WorkOrder(
            tenant_id=actor.tenant_id,
            work_order_no=work_order_no,
            source=payload.source,
            external_ref=payload.external_ref,
            material_id=material.id,
            material_code_snapshot=material.code,
            material_name_snapshot=material.name,
            material_spec_snapshot=material.spec,
            material_unit_snapshot=material.unit,
            planned_qty=payload.quantity,
            actual_good_qty=Decimal("0"),
            actual_bad_qty=Decimal("0"),
            due_date=payload.due_date,
            priority=payload.priority,
            customer_name=payload.customer_name,
            status=initial_status,
            bom_id=bom.id if bom else None,
            bom_version=bom.version if bom else None,
            routing_id=routing.id,
            routing_version=routing.version,
            created_by=actor.code,
            remark=payload.remark,
        )
        work_order.materials = build_material_rows(work_order, bom, material, payload.quantity)
        work_order.operations = build_operation_rows(work_order, routing, payload.quantity)
        session.add(work_order)
        await session.flush()

        response = serialize_work_order(work_order)
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed_payload,
                response_body=response,
                expires_at=now + timedelta(hours=24),
            )
        )
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=actor.code,
            entity_type="work_order",
            entity_id=work_order.id,
            action="create",
            to_state=work_order.status,
            detail={
                "work_order_no": work_order.work_order_no,
                "planned_qty": moneyless_decimal(work_order.planned_qty),
                "material_code": work_order.material_code_snapshot,
            },
        )

    return response


async def load_work_order_by_no(
    session: AsyncSession,
    work_order_no: str,
    actor: Actor,
    *,
    lock: bool = False,
) -> WorkOrder:
    stmt = (
        select(WorkOrder)
        .options(selectinload(WorkOrder.materials), selectinload(WorkOrder.operations))
        .where(
            WorkOrder.work_order_no == work_order_no,
            WorkOrder.tenant_id == actor.tenant_id,
            WorkOrder.deleted_at.is_(None),
        )
    )
    if lock:
        stmt = stmt.with_for_update()
    work_order = await session.scalar(stmt)
    if not work_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return work_order


async def confirm_work_order(
    session: AsyncSession,
    work_order_no: str,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    now = utcnow()
    hashed_payload = confirm_request_hash(work_order_no)

    async with session.begin():
        cached = await session.scalar(
            select(IdempotencyKey)
            .where(
                IdempotencyKey.tenant_id == actor.tenant_id,
                IdempotencyKey.key == idempotency_key,
            )
            .with_for_update()
        )
        if cached:
            if cached.request_hash != hashed_payload:
                business_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "同一幂等键重复提交了不同请求体",
                )
            return cached.response_body

        work_order = await load_work_order_by_no(session, work_order_no, actor, lock=True)
        if work_order.status != "draft":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_WORK_ORDER_STATUS",
                f"当前工单状态为 {work_order.status}，不能确认",
            )
        work_order.status = "pending"
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=actor.code,
            entity_type="work_order",
            entity_id=work_order.id,
            action="confirm",
            from_state="draft",
            to_state="pending",
            detail={"work_order_no": work_order.work_order_no},
        )
        await session.flush()
        await session.refresh(work_order, attribute_names=["updated_at"])
        response = serialize_work_order(work_order)
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed_payload,
                response_body=response,
                expires_at=now + timedelta(hours=24),
            )
        )
        return response


async def schedule_work_order(
    session: AsyncSession,
    work_order_no: str,
    actor: Actor,
    idempotency_key: str,
    payload: WorkOrderSchedule | None = None,
) -> dict[str, Any]:
    payload = payload or WorkOrderSchedule()
    now = utcnow()
    hashed_payload = schedule_request_hash(work_order_no, payload)

    async with session.begin():
        cached = await session.scalar(
            select(IdempotencyKey)
            .where(
                IdempotencyKey.tenant_id == actor.tenant_id,
                IdempotencyKey.key == idempotency_key,
            )
            .with_for_update()
        )
        if cached:
            if cached.request_hash != hashed_payload:
                business_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "同一幂等键重复提交了不同请求体",
                )
            return cached.response_body

        work_order = await load_work_order_by_no(session, work_order_no, actor, lock=True)
        if work_order.status != "pending":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_WORK_ORDER_STATUS",
                f"当前工单状态为 {work_order.status}，不能派工",
            )
        operations = sorted(work_order.operations, key=lambda item: item.seq)
        first_pending = next((item for item in operations if item.status == "pending"), None)
        if not first_pending:
            business_error(status.HTTP_400_BAD_REQUEST, "NO_PENDING_OPERATION", "没有可派工的待处理工序")
        assignment_by_seq = {item.operation_seq: item.operator_code for item in payload.operation_assignments}
        unknown_assignment_seqs = [seq for seq in assignment_by_seq if seq not in {item.seq for item in operations}]
        if unknown_assignment_seqs:
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "UNKNOWN_OPERATION_ASSIGNMENT",
                f"派工工序不存在: {', '.join(str(seq) for seq in sorted(unknown_assignment_seqs))}",
            )
        pending_operations = [operation for operation in operations if operation.status == "pending"]
        needs_default_operator = any(operation.seq not in assignment_by_seq for operation in pending_operations)
        default_operator = (
            await load_schedule_operator(session, actor.tenant_id, payload.operator_code)
            if needs_default_operator
            else None
        )
        operator_cache: dict[str, Worker] = {default_operator.code: default_operator} if default_operator else {}
        operation_assignments: list[dict[str, Any]] = []
        for operation in pending_operations:
            operator_code = assignment_by_seq.get(operation.seq)
            if not operator_code and default_operator:
                operator_code = default_operator.code
            if not operator_code:
                business_error(status.HTTP_400_BAD_REQUEST, "OPERATOR_NOT_ASSIGNED", "存在未指定操作员的工序")
            assigned_operator = operator_cache.get(operator_code)
            if not assigned_operator:
                assigned_operator = await load_schedule_operator(session, actor.tenant_id, operator_code)
                operator_cache[operator_code] = assigned_operator
            await ensure_worker_can_run_operations(session, assigned_operator, [operation])
            assign_operation_to_worker(operation, assigned_operator)
            operation_assignments.append(
                {
                    "operation_seq": operation.seq,
                    "operation_code": operation.operation_code_snapshot,
                    "operator_code": assigned_operator.code,
                    "operator_name": assigned_operator.name,
                }
            )
        work_order.status = "scheduled"
        first_pending.status = "ready"
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=actor.code,
            entity_type="work_order",
            entity_id=work_order.id,
            action="schedule",
            from_state="pending",
            to_state="scheduled",
            detail={
                "ready_operation_id": str(first_pending.id),
                "ready_operation_seq": first_pending.seq,
                "assignments": operation_assignments,
            },
        )
        first_pending_operator = next(
            item for item in operation_assignments if item["operation_seq"] == first_pending.seq
        )
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=actor.code,
            entity_type="operation",
            entity_id=first_pending.id,
            action="ready",
            from_state="pending",
            to_state="ready",
            detail={
                "work_order_no": work_order.work_order_no,
                "operation_seq": first_pending.seq,
                "assigned_operator_code": first_pending_operator["operator_code"],
                "assigned_operator_name": first_pending_operator["operator_name"],
            },
        )
        await session.flush()
        await session.refresh(work_order, attribute_names=["updated_at"])
        for operation in operations:
            await session.refresh(operation, attribute_names=["updated_at"])
        response = serialize_work_order(work_order)
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed_payload,
                response_body=response,
                expires_at=now + timedelta(hours=24),
            )
        )
        return response


async def cancel_work_order(
    session: AsyncSession,
    work_order_no: str,
    payload: WorkOrderCancel,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    now = utcnow()
    hashed_payload = payload_hash({"work_order_no": work_order_no, "payload": payload.model_dump(mode="json")})

    async with session.begin():
        cached = await session.scalar(
            select(IdempotencyKey)
            .where(
                IdempotencyKey.tenant_id == actor.tenant_id,
                IdempotencyKey.key == idempotency_key,
            )
            .with_for_update()
        )
        if cached:
            if cached.request_hash != hashed_payload:
                business_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "同一幂等键重复提交了不同请求体",
                )
            return cached.response_body

        work_order = await load_work_order_by_no(session, work_order_no, actor, lock=True)
        if work_order.status in {"closed", "cancelled"}:
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_WORK_ORDER_STATUS",
                f"当前工单状态为 {work_order.status}，不能取消",
            )
        from_state = work_order.status
        active_wip_operations = [
            operation
            for operation in work_order.operations
            if operation.status in {"in_progress", "reporting", "paused"}
        ]
        if active_wip_operations and not payload.allow_abandon_wip:
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "CANCEL_HAS_ACTIVE_WIP",
                "工单存在已开工或暂停的工序，请先报工处理在制品，或明确允许放弃在制品后再取消",
                {
                    "operations": [
                        {
                            "operation_id": str(operation.id),
                            "operation_seq": operation.seq,
                            "operation_code": operation.operation_code_snapshot,
                            "status": operation.status,
                            "started_by_operator_code": operation.started_by_operator_code,
                            "started_by_operator_name": operation.started_by_operator_name,
                        }
                        for operation in sorted(active_wip_operations, key=lambda item: item.seq)
                    ]
                },
            )
        active_wip_operation_ids = {operation.id for operation in active_wip_operations}
        changed_operations = []
        for operation in work_order.operations:
            if operation.status not in {"done", "cancelled"}:
                old_operation_status = operation.status
                operation.status = "cancelled"
                changed_operations.append(operation)
                await write_audit_log(
                    session,
                    tenant_id=actor.tenant_id,
                    actor_code=actor.code,
                    entity_type="operation",
                    entity_id=operation.id,
                    action="cancel",
                    from_state=old_operation_status,
                    to_state="cancelled",
                    detail={
                        "work_order_no": work_order.work_order_no,
                        "operation_seq": operation.seq,
                        "reason": payload.reason,
                        "abandoned_wip": operation.id in active_wip_operation_ids,
                    },
                )
        work_order.status = "cancelled"
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=actor.code,
            entity_type="work_order",
            entity_id=work_order.id,
            action="cancel",
            from_state=from_state,
            to_state="cancelled",
            detail={
                "work_order_no": work_order.work_order_no,
                "reason": payload.reason,
                "allow_abandon_wip": payload.allow_abandon_wip,
                "abandoned_wip_operations": [
                    {
                        "operation_id": str(operation.id),
                        "operation_seq": operation.seq,
                        "operation_code": operation.operation_code_snapshot,
                        "started_by_operator_code": operation.started_by_operator_code,
                        "started_by_operator_name": operation.started_by_operator_name,
                    }
                    for operation in sorted(active_wip_operations, key=lambda item: item.seq)
                ],
            },
        )
        await session.flush()
        await session.refresh(work_order, attribute_names=["updated_at"])
        for operation in changed_operations:
            await session.refresh(operation, attribute_names=["updated_at"])
        response = serialize_work_order(work_order)
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed_payload,
                response_body=response,
                expires_at=now + timedelta(hours=24),
            )
        )
    return response


async def kitting_check(session: AsyncSession, work_order_no: str, actor: Actor) -> dict[str, Any]:
    work_order = await load_work_order_by_no(session, work_order_no, actor)
    # MVP 暂不接 WMS：只返回工单物料需求清单，库存可用量按需求量回填，避免 MES 跨库读取库存。
    return {
        "work_order_no": work_order.work_order_no,
        "is_complete": True,
        "mode": "manual_without_wms",
        "shortage": [
            {
                "material_code": row.component_code_snapshot,
                "material_name": row.component_name_snapshot,
                "required_qty": row.required_qty,
                "available_qty": row.required_qty,
                "shortage_qty": Decimal("0"),
                "expected_arrival": None,
            }
            for row in sorted(work_order.materials, key=lambda item: item.component_code_snapshot)
        ],
        "checked_at": utcnow(),
    }


def serialize_clock_record(record: ClockRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "deleted_at": record.deleted_at,
        "operation_id": record.operation_id,
        "operation_seq": record.operation_seq_snapshot,
        "operation_code": record.operation_code_snapshot,
        "operation_name": record.operation_name_snapshot,
        "work_center_id": record.work_center_id,
        "work_center_code": record.work_center_code_snapshot,
        "work_center_name": record.work_center_name_snapshot,
        "operator_id": record.operator_id,
        "operator_code": record.operator_code_snapshot,
        "operator_name": record.operator_name_snapshot,
        "started_at": record.started_at,
        "ended_at": record.ended_at,
        "elapsed_seconds": record.elapsed_seconds,
        "time_anomaly": record.time_anomaly,
        "time_anomaly_reason": record.time_anomaly_reason,
        "time_anomaly_detail": record.time_anomaly_detail,
        "good_qty": record.good_qty,
        "bad_qty": record.bad_qty,
        "defects": record.defects,
        "material_consumed": record.material_consumed,
        "remark": record.remark,
    }


def serialize_production_receipt(receipt: ProductionReceipt) -> dict[str, Any]:
    return {
        "id": receipt.id,
        "tenant_id": receipt.tenant_id,
        "created_at": receipt.created_at,
        "updated_at": receipt.updated_at,
        "deleted_at": receipt.deleted_at,
        "receipt_no": receipt.receipt_no,
        "work_order_id": receipt.work_order_id,
        "work_order_no": receipt.work_order_no_snapshot,
        "material_id": receipt.material_id,
        "material": {
            "code": receipt.material_code_snapshot,
            "name": receipt.material_name_snapshot,
            "spec": receipt.material_spec_snapshot,
            "unit": receipt.material_unit_snapshot,
        },
        "good_qty": receipt.good_qty,
        "lot_no": receipt.lot_no,
        "warehouse_code": receipt.warehouse_code,
        "received_by": receipt.received_by,
        "received_at": receipt.received_at,
        "remark": receipt.remark,
    }


def serialize_quality_record_for_trace(record: QualityRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "deleted_at": record.deleted_at,
        "operation_id": record.operation_id,
        "operation_seq": record.operation_seq_snapshot,
        "operation_code": record.operation_code_snapshot,
        "operation_name": record.operation_name_snapshot,
        "inspector_code": record.inspector_code_snapshot,
        "inspector_name": record.inspector_name_snapshot,
        "inspect_type": record.inspect_type,
        "sample_qty": record.sample_qty,
        "pass_qty": record.pass_qty,
        "fail_qty": record.fail_qty,
        "result": record.result,
        "disposition": record.disposition,
        "inspected_at": record.inspected_at,
        "remark": record.remark,
    }


async def receive_work_order(
    session: AsyncSession,
    work_order_no: str,
    payload: ProductionReceiptCreate,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    now = utcnow()
    hashed_payload = receipt_request_hash(work_order_no, payload)

    async with session.begin():
        cached = await session.scalar(
            select(IdempotencyKey)
            .where(
                IdempotencyKey.tenant_id == actor.tenant_id,
                IdempotencyKey.key == idempotency_key,
            )
            .with_for_update()
        )
        if cached:
            if cached.request_hash != hashed_payload:
                business_error(
                    status.HTTP_409_CONFLICT,
                    "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "同一幂等键重复提交了不同请求体",
                )
            return cached.response_body

        work_order = await load_work_order_by_no(session, work_order_no, actor, lock=True)
        if work_order.status != "completed":
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "INVALID_WORK_ORDER_STATUS",
                f"当前工单状态为 {work_order.status}，只有 completed 才能完工入库",
            )
        if work_order.actual_good_qty <= 0:
            business_error(status.HTTP_400_BAD_REQUEST, "NO_GOOD_QTY_TO_RECEIVE", "工单没有可入库的合格数量")

        received_qty = await session.scalar(
            select(func.coalesce(func.sum(ProductionReceipt.good_qty), Decimal("0"))).where(
                ProductionReceipt.tenant_id == actor.tenant_id,
                ProductionReceipt.work_order_id == work_order.id,
                ProductionReceipt.deleted_at.is_(None),
            )
        )
        received_qty = received_qty or Decimal("0")
        remaining_qty = work_order.actual_good_qty - received_qty
        if remaining_qty <= 0:
            business_error(status.HTTP_400_BAD_REQUEST, "NO_REMAINING_QTY_TO_RECEIVE", "工单合格数量已全部入库")

        good_qty = payload.good_qty or remaining_qty
        if good_qty > remaining_qty:
            business_error(
                status.HTTP_400_BAD_REQUEST,
                "RECEIPT_QTY_EXCEEDS_REMAINING",
                f"入库数量不能超过剩余可入库数量 {moneyless_decimal(remaining_qty)}",
            )

        receipt = ProductionReceipt(
            tenant_id=actor.tenant_id,
            receipt_no=await next_receipt_no(session, actor.tenant_id, now),
            work_order_id=work_order.id,
            work_order_no_snapshot=work_order.work_order_no,
            material_id=work_order.material_id,
            material_code_snapshot=work_order.material_code_snapshot,
            material_name_snapshot=work_order.material_name_snapshot,
            material_spec_snapshot=work_order.material_spec_snapshot,
            material_unit_snapshot=work_order.material_unit_snapshot,
            good_qty=good_qty,
            lot_no=payload.lot_no,
            warehouse_code=payload.warehouse_code,
            received_by=actor.code,
            received_at=now,
            remark=payload.remark,
        )
        session.add(receipt)
        await session.flush()

        next_remaining_qty = remaining_qty - good_qty
        from_state = work_order.status
        if next_remaining_qty <= 0:
            work_order.status = "closed"

        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=actor.code,
            entity_type="production_receipt",
            entity_id=receipt.id,
            action="receive",
            detail={
                "receipt_no": receipt.receipt_no,
                "work_order_no": work_order.work_order_no,
                "good_qty": moneyless_decimal(receipt.good_qty),
                "lot_no": receipt.lot_no,
                "warehouse_code": receipt.warehouse_code,
            },
        )
        if work_order.status == "closed":
            await write_audit_log(
                session,
                tenant_id=actor.tenant_id,
                actor_code=actor.code,
                entity_type="work_order",
                entity_id=work_order.id,
                action="close",
                from_state=from_state,
                to_state="closed",
                detail={
                    "work_order_no": work_order.work_order_no,
                    "receipt_no": receipt.receipt_no,
                    "received_qty": moneyless_decimal(receipt.good_qty),
                },
            )
            from app.services.erp_integration import create_erp_feedback_if_needed

            await create_erp_feedback_if_needed(session, work_order, receipt)

        await session.flush()
        await session.refresh(work_order, attribute_names=["updated_at"])
        await session.refresh(receipt)
        response = {"work_order": serialize_work_order(work_order), "receipt": serialize_production_receipt(receipt)}
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed_payload,
                response_body=jsonable_encoder(response),
                expires_at=now + timedelta(hours=24),
            )
        )
    return response


def serialize_audit_event(event: AuditLog, actor_names: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "id": event.id,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "action": event.action,
        "actor_code": event.actor_code,
        "actor_name": actor_names.get(event.actor_code) if actor_names else None,
        "from_state": event.from_state,
        "to_state": event.to_state,
        "detail": event.detail,
        "created_at": event.created_at,
    }


def trace_title_for_audit(event: AuditLog) -> str:
    if event.entity_type == "work_order":
        if event.action == "close":
            return "完工入库关单"
        if event.action == "pause":
            return "工单暂停"
        if event.action == "resume":
            return "工单恢复"
        if event.action == "cancel":
            return "取消工单"
        labels = {
            "create": "创建工单",
            "confirm": "确认工单",
            "schedule": "派工",
            "start": "工单开工",
            "complete": "工单完工",
        }
        return labels.get(event.action, f"工单 {event.action}")
    if event.entity_type == "operation":
        if event.action == "pause":
            return "工序暂停"
        if event.action == "resume":
            return "工序恢复"
        if event.action == "quality_pause":
            return "巡检不合格停线"
        labels = {
            "ready": "工序就绪",
            "start": "工序开工",
            "clock": "工序报工",
        }
        return labels.get(event.action, f"工序 {event.action}")
    if event.entity_type == "production_receipt":
        labels = {
            "receive": "完工入库",
        }
        return labels.get(event.action, f"入库 {event.action}")
    if event.entity_type == "quality_record":
        labels = {
            "first_article": "首件检验",
            "patrol": "过程巡检",
            "final": "终检",
        }
        return labels.get(event.action, f"质检 {event.action}")
    return event.action


async def load_actor_names(session: AsyncSession, tenant_id: UUID, codes: set[str]) -> dict[str, str]:
    if not codes:
        return {}
    actor_names: dict[str, str] = {}
    workers = list(
        await session.scalars(
            select(Worker).where(
                Worker.tenant_id == tenant_id,
                Worker.code.in_(codes),
                Worker.deleted_at.is_(None),
            )
        )
    )
    for worker in workers:
        actor_names[worker.code] = worker.name

    missing_codes = codes - set(actor_names)
    if missing_codes:
        users = list(
            await session.scalars(
                select(UserAccount).where(
                    UserAccount.tenant_id == tenant_id,
                    UserAccount.username.in_(missing_codes),
                    UserAccount.deleted_at.is_(None),
                )
            )
        )
        for user in users:
            actor_names[user.username] = user.display_name
    return actor_names


async def get_work_order_traceability(session: AsyncSession, work_order_no: str, actor: Actor) -> dict[str, Any]:
    work_order = await load_work_order_by_no(session, work_order_no, actor)
    operation_ids = [operation.id for operation in work_order.operations]

    clock_records = list(
        await session.scalars(
            select(ClockRecord)
            .where(
                ClockRecord.tenant_id == actor.tenant_id,
                ClockRecord.work_order_id == work_order.id,
                ClockRecord.deleted_at.is_(None),
            )
            .order_by(ClockRecord.started_at.asc(), ClockRecord.created_at.asc())
        )
    )
    receipts = list(
        await session.scalars(
            select(ProductionReceipt)
            .where(
                ProductionReceipt.tenant_id == actor.tenant_id,
                ProductionReceipt.work_order_id == work_order.id,
                ProductionReceipt.deleted_at.is_(None),
            )
            .order_by(ProductionReceipt.received_at.asc(), ProductionReceipt.created_at.asc())
        )
    )
    quality_records = list(
        await session.scalars(
            select(QualityRecord)
            .where(
                QualityRecord.tenant_id == actor.tenant_id,
                QualityRecord.work_order_id == work_order.id,
                QualityRecord.deleted_at.is_(None),
            )
            .order_by(QualityRecord.inspected_at.asc(), QualityRecord.created_at.asc())
        )
    )
    audit_filters = [
        (AuditLog.entity_type == "work_order") & (AuditLog.entity_id == work_order.id),
    ]
    if operation_ids:
        audit_filters.append((AuditLog.entity_type == "operation") & (AuditLog.entity_id.in_(operation_ids)))
    if receipts:
        audit_filters.append(
            (AuditLog.entity_type == "production_receipt")
            & (AuditLog.entity_id.in_([receipt.id for receipt in receipts]))
        )
    if quality_records:
        audit_filters.append(
            (AuditLog.entity_type == "quality_record")
            & (AuditLog.entity_id.in_([record.id for record in quality_records]))
        )
    audit_events = list(
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.tenant_id == actor.tenant_id, or_(*audit_filters))
            .order_by(AuditLog.created_at.asc())
        )
    )

    actor_codes = {
        code
        for code in [
            *(event.actor_code for event in audit_events),
            *(record.operator_code_snapshot for record in clock_records),
            *(receipt.received_by for receipt in receipts),
            *(record.inspector_code_snapshot for record in quality_records),
        ]
        if code
    }
    actor_names = await load_actor_names(session, actor.tenant_id, actor_codes)
    work_order_payload = serialize_work_order(work_order)
    audit_timeline = [
        {
            "event_type": "audit",
            "title": trace_title_for_audit(event),
            "occurred_at": event.created_at,
            "actor_code": event.actor_code,
            "actor_name": actor_names.get(event.actor_code),
            "operation_seq": event.detail.get("operation_seq") if event.detail else None,
            "good_qty": None,
            "bad_qty": None,
            "detail": event.detail or {},
        }
        for event in audit_events
    ]
    clock_timeline = [
        {
            "event_type": "clock",
            "title": f"报工 {record.good_qty}/{record.bad_qty}",
            "occurred_at": record.ended_at,
            "actor_code": record.operator_code_snapshot,
            "actor_name": record.operator_name_snapshot or actor_names.get(record.operator_code_snapshot or ""),
            "operation_seq": record.operation_seq_snapshot,
            "good_qty": record.good_qty,
            "bad_qty": record.bad_qty,
            "detail": {
                "operation_name": record.operation_name_snapshot,
                "work_center": record.work_center_name_snapshot,
                "remark": record.remark,
                "elapsed_seconds": record.elapsed_seconds,
                "time_anomaly": record.time_anomaly,
                "time_anomaly_reason": record.time_anomaly_reason,
                "time_anomaly_detail": record.time_anomaly_detail,
            },
        }
        for record in clock_records
    ]
    receipt_timeline = [
        {
            "event_type": "receipt",
            "title": f"完工入库 {receipt.good_qty}",
            "occurred_at": receipt.received_at,
            "actor_code": receipt.received_by,
            "actor_name": actor_names.get(receipt.received_by),
            "operation_seq": None,
            "good_qty": receipt.good_qty,
            "bad_qty": None,
            "detail": {
                "receipt_no": receipt.receipt_no,
                "lot_no": receipt.lot_no,
                "warehouse_code": receipt.warehouse_code,
            },
        }
        for receipt in receipts
    ]
    quality_timeline = [
        {
            "event_type": "quality",
            "title": f"质检 {record.inspect_type} {record.result}",
            "occurred_at": record.inspected_at,
            "actor_code": record.inspector_code_snapshot,
            "actor_name": record.inspector_name_snapshot or actor_names.get(record.inspector_code_snapshot or ""),
            "operation_seq": record.operation_seq_snapshot,
            "good_qty": record.pass_qty,
            "bad_qty": record.fail_qty,
            "detail": {
                "operation_name": record.operation_name_snapshot,
                "sample_qty": str(record.sample_qty),
                "disposition": record.disposition,
            },
        }
        for record in quality_records
    ]
    timeline = sorted(
        [*audit_timeline, *clock_timeline, *receipt_timeline, *quality_timeline],
        key=lambda item: item["occurred_at"],
    )

    return {
        "work_order_no": work_order.work_order_no,
        "status": work_order.status,
        "material": work_order_payload["material"],
        "planned_qty": work_order.planned_qty,
        "actual_good_qty": work_order.actual_good_qty,
        "actual_bad_qty": work_order.actual_bad_qty,
        "materials_required": work_order_payload["materials_required"],
        "operations": work_order_payload["operations"],
        "clock_records": [serialize_clock_record(record) for record in clock_records],
        "receipts": [serialize_production_receipt(receipt) for receipt in receipts],
        "quality_records": [serialize_quality_record_for_trace(record) for record in quality_records],
        "audit_events": [serialize_audit_event(event, actor_names) for event in audit_events],
        "timeline": timeline,
    }
