from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import Actor
from app.models.master_data import Worker
from app.models.production import IdempotencyKey, QualityRecord, WorkOrder, WorkOrderOperation
from app.schemas.quality import InspectType, QualityRecordCreate, QualityRecordRead
from app.services.audit import write_audit_log
from app.services.work_order import business_error, payload_hash, sync_work_order_status_from_operations, utcnow


def serialize_quality_record(record: QualityRecord) -> dict[str, Any]:
    return QualityRecordRead(
        id=record.id,
        tenant_id=record.tenant_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        deleted_at=record.deleted_at,
        work_order_id=record.work_order_id,
        operation_id=record.operation_id,
        work_order_no=record.work_order_no_snapshot,
        operation_seq=record.operation_seq_snapshot,
        operation_code=record.operation_code_snapshot,
        operation_name=record.operation_name_snapshot,
        inspector_code=record.inspector_code_snapshot,
        inspector_name=record.inspector_name_snapshot,
        inspect_type=record.inspect_type,
        sample_qty=record.sample_qty,
        pass_qty=record.pass_qty,
        fail_qty=record.fail_qty,
        result=record.result,
        disposition=record.disposition,
        inspected_at=record.inspected_at,
        remark=record.remark,
    ).model_dump(mode="json")


async def load_work_order(session: AsyncSession, work_order_no: str, actor: Actor) -> WorkOrder:
    work_order = await session.scalar(
        select(WorkOrder)
        .options(selectinload(WorkOrder.operations))
        .where(
            WorkOrder.tenant_id == actor.tenant_id,
            WorkOrder.work_order_no == work_order_no,
            WorkOrder.deleted_at.is_(None),
        )
    )
    if not work_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return work_order


def pick_operation(
    work_order: WorkOrder,
    inspect_type: InspectType,
    operation_id: object | None,
) -> WorkOrderOperation | None:
    operations = sorted(work_order.operations, key=lambda item: item.seq)
    if operation_id:
        operation = next((item for item in operations if item.id == operation_id), None)
        if not operation:
            business_error(status.HTTP_400_BAD_REQUEST, "OPERATION_NOT_IN_WORK_ORDER", "工序不属于该工单")
        return operation
    if not operations:
        return None
    if inspect_type == "final":
        return operations[-1]
    return operations[0]


async def find_active_worker_by_code(session: AsyncSession, tenant_id: UUID, code: str) -> Worker | None:
    return await session.scalar(
        select(Worker).where(
            Worker.tenant_id == tenant_id,
            Worker.code == code,
            Worker.deleted_at.is_(None),
            Worker.is_active.is_(True),
        )
    )


async def find_active_worker_by_id(session: AsyncSession, tenant_id: UUID, worker_id: UUID) -> Worker | None:
    worker = await session.get(Worker, worker_id)
    if worker and worker.tenant_id == tenant_id and worker.deleted_at is None and worker.is_active:
        return worker
    return None


async def load_inspector(session: AsyncSession, actor: Actor, inspector_code: str | None) -> Worker:
    if actor.role != "admin" and not actor.worker_id and not actor.worker_code:
        business_error(status.HTTP_403_FORBIDDEN, "INSPECTOR_ACCOUNT_NOT_LINKED", "当前账号未绑定质检员档案")

    if inspector_code and actor.role != "admin" and actor.worker_code != inspector_code:
        business_error(status.HTTP_403_FORBIDDEN, "INSPECTOR_CODE_MISMATCH", "不能代替其他质检员确认")

    if inspector_code:
        worker = await find_active_worker_by_code(session, actor.tenant_id, inspector_code)
    elif actor.worker_id:
        worker = await find_active_worker_by_id(session, actor.tenant_id, actor.worker_id)
    elif actor.worker_code:
        worker = await find_active_worker_by_code(session, actor.tenant_id, actor.worker_code)
    else:
        worker = None

    if not worker:
        business_error(status.HTTP_400_BAD_REQUEST, "INSPECTOR_NOT_FOUND", "质检员不存在或已停用")
    if worker.worker_type != "inspector":
        business_error(status.HTTP_400_BAD_REQUEST, "WORKER_NOT_INSPECTOR", "质检确认人必须是质检员")
    return worker


async def create_quality_record(
    session: AsyncSession,
    inspect_type: InspectType,
    payload: QualityRecordCreate,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    now = utcnow()
    hashed = payload_hash(
        {"inspect_type": inspect_type, "payload": payload.model_dump(mode="json")}
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

        work_order = await load_work_order(session, payload.work_order_no, actor)
        operation = pick_operation(work_order, inspect_type, payload.operation_id)
        inspector = await load_inspector(session, actor, payload.inspector_code)
        inspector_code = inspector.code
        inspector_name = inspector.name

        record = QualityRecord(
            tenant_id=actor.tenant_id,
            work_order_id=work_order.id,
            operation_id=operation.id if operation else None,
            work_order_no_snapshot=work_order.work_order_no,
            operation_seq_snapshot=operation.seq if operation else None,
            operation_code_snapshot=operation.operation_code_snapshot if operation else None,
            operation_name_snapshot=operation.operation_name_snapshot if operation else None,
            inspector_code_snapshot=inspector_code,
            inspector_name_snapshot=inspector_name,
            inspect_type=inspect_type,
            sample_qty=payload.sample_qty,
            pass_qty=payload.pass_qty,
            fail_qty=payload.fail_qty,
            result=payload.result,
            disposition=payload.disposition,
            inspected_at=now,
            remark=payload.remark,
        )
        session.add(record)

        if inspect_type == "patrol" and payload.result == "fail" and operation and operation.status == "in_progress":
            old_order_status = work_order.status
            operation.status = "paused"
            _, new_order_status = sync_work_order_status_from_operations(
                work_order,
                sorted(work_order.operations, key=lambda item: item.seq),
            )
            await write_audit_log(
                session,
                tenant_id=actor.tenant_id,
                actor_code=inspector_code,
                entity_type="operation",
                entity_id=operation.id,
                action="quality_pause",
                from_state="in_progress",
                to_state="paused",
                detail={"work_order_no": work_order.work_order_no, "quality_result": payload.result},
            )
            if old_order_status != new_order_status:
                await write_audit_log(
                    session,
                    tenant_id=actor.tenant_id,
                    actor_code=inspector_code,
                    entity_type="work_order",
                    entity_id=work_order.id,
                    action="quality_pause",
                    from_state=old_order_status,
                    to_state=new_order_status,
                    detail={"operation_id": str(operation.id), "operation_seq": operation.seq},
                )

        await session.flush()
        await session.refresh(record)
        response = serialize_quality_record(record)
        await write_audit_log(
            session,
            tenant_id=actor.tenant_id,
            actor_code=inspector_code,
            entity_type="quality_record",
            entity_id=record.id,
            action=inspect_type,
            detail={
                "work_order_no": work_order.work_order_no,
                "operation_seq": record.operation_seq_snapshot,
                "result": record.result,
                "sample_qty": str(record.sample_qty),
                "fail_qty": str(record.fail_qty),
            },
        )
        session.add(
            IdempotencyKey(
                tenant_id=actor.tenant_id,
                key=idempotency_key,
                request_hash=hashed,
                response_body=jsonable_encoder(response),
                expires_at=now + timedelta(hours=24),
            )
        )
    return response


async def list_quality_records(
    session: AsyncSession,
    actor: Actor,
    *,
    work_order_no: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    filters = [QualityRecord.tenant_id == actor.tenant_id, QualityRecord.deleted_at.is_(None)]
    if work_order_no:
        filters.append(QualityRecord.work_order_no_snapshot == work_order_no)

    total = await session.scalar(select(func.count()).select_from(QualityRecord).where(*filters))
    records = list(
        await session.scalars(
            select(QualityRecord).where(*filters).order_by(QualityRecord.inspected_at.desc()).limit(limit).offset(offset)
        )
    )
    return {"total": total or 0, "items": [serialize_quality_record(record) for record in records]}
