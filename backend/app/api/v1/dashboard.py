from datetime import UTC, datetime, time
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor, require_roles
from app.db.session import get_db_session
from app.models.production import ClockRecord, WorkOrder, WorkOrderOperation
from app.schemas.dashboard import WorkOrderDashboardRead

router = APIRouter(tags=["dashboard"])


def start_of_day(value: datetime) -> datetime:
    return datetime.combine(value.date(), time.min, tzinfo=UTC)


def end_of_day(value: datetime) -> datetime:
    return datetime.combine(value.date(), time.max, tzinfo=UTC)


@router.get("/dashboard/work-orders", response_model=WorkOrderDashboardRead)
async def get_work_order_dashboard(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(require_roles("planner", "admin")),
) -> dict[str, Any]:
    status_rows = await db.execute(
        select(WorkOrder.status, func.count())
        .where(WorkOrder.tenant_id == actor.tenant_id, WorkOrder.deleted_at.is_(None))
        .group_by(WorkOrder.status)
    )
    status_counts = {status: count for status, count in status_rows.all()}
    total = sum(status_counts.values())

    ready_operations = await db.scalar(
        select(func.count())
        .select_from(WorkOrderOperation)
        .where(
            WorkOrderOperation.tenant_id == actor.tenant_id,
            WorkOrderOperation.deleted_at.is_(None),
            WorkOrderOperation.status == "ready",
        )
    )
    in_progress_operations = await db.scalar(
        select(func.count())
        .select_from(WorkOrderOperation)
        .where(
            WorkOrderOperation.tenant_id == actor.tenant_id,
            WorkOrderOperation.deleted_at.is_(None),
            WorkOrderOperation.status == "in_progress",
        )
    )
    now = datetime.now(UTC)
    output = await db.execute(
        select(
            func.coalesce(func.sum(ClockRecord.good_qty), 0),
            func.coalesce(func.sum(ClockRecord.bad_qty), 0),
        ).where(
            ClockRecord.tenant_id == actor.tenant_id,
            ClockRecord.deleted_at.is_(None),
            ClockRecord.ended_at >= start_of_day(now),
            ClockRecord.ended_at <= end_of_day(now),
        )
    )
    actual_good_qty, actual_bad_qty = output.one()

    return {
        "total": total,
        "draft": status_counts.get("draft", 0),
        "pending": status_counts.get("pending", 0),
        "scheduled": status_counts.get("scheduled", 0),
        "in_progress": status_counts.get("in_progress", 0),
        "completed": status_counts.get("completed", 0),
        "ready_operations": ready_operations or 0,
        "in_progress_operations": in_progress_operations or 0,
        "actual_good_qty": actual_good_qty or Decimal("0"),
        "actual_bad_qty": actual_bad_qty or Decimal("0"),
    }
