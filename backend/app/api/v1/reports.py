from collections import defaultdict
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor, get_any_authenticated_actor
from app.db.session import get_db_session
from app.models.master_data import DefectReason, WorkCenter
from app.models.production import ClockRecord, WorkOrder
from app.schemas.report import DefectReportRead, OeeReportRead, OutputReportRead

router = APIRouter(tags=["reports"])


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


def empty_output_summary() -> dict[str, Any]:
    return {"good_qty": Decimal("0"), "bad_qty": Decimal("0"), "clock_count": 0}


def minutes_from_seconds(seconds: int) -> Decimal:
    return (Decimal(seconds) / Decimal("60")).quantize(Decimal("0.01"))


def rate(actual_minutes: Decimal, planned_minutes: Decimal) -> Decimal:
    if planned_minutes <= 0:
        return Decimal("0")
    return (actual_minutes / planned_minutes).quantize(Decimal("0.0001"))


@router.get("/reports/defects", response_model=DefectReportRead)
async def get_defect_report(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_any_authenticated_actor),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, Any]:
    filters = [ClockRecord.tenant_id == actor.tenant_id, ClockRecord.deleted_at.is_(None), ClockRecord.bad_qty > 0]
    if date_from:
        filters.append(ClockRecord.ended_at >= start_of_day(date_from))
    if date_to:
        filters.append(ClockRecord.ended_at <= end_of_day(date_to))

    records = list(await db.scalars(select(ClockRecord).where(*filters).order_by(ClockRecord.ended_at.desc())))
    reasons = list(
        await db.scalars(
            select(DefectReason).where(
                DefectReason.tenant_id == actor.tenant_id,
                DefectReason.deleted_at.is_(None),
            )
        )
    )
    reason_map = {reason.code: reason for reason in reasons}

    summary: dict[str, dict[str, Any]] = defaultdict(lambda: {"bad_qty": Decimal("0"), "clock_ids": set()})
    recent_records: list[dict[str, Any]] = []

    for record in records:
        defects = record.defects or []
        if not defects:
            defects = [{"reason_code": "UNKNOWN", "qty": str(record.bad_qty)}]

        for defect in defects:
            reason_code = str(defect.get("reason_code") or "UNKNOWN")
            qty = to_decimal(defect.get("qty"))
            if qty <= 0:
                continue
            reason = reason_map.get(reason_code)
            summary[reason_code]["bad_qty"] += qty
            summary[reason_code]["clock_ids"].add(record.id)
            recent_records.append(
                {
                    "work_order_no": record.work_order_no_snapshot,
                    "operation_seq": record.operation_seq_snapshot,
                    "operation_name": record.operation_name_snapshot,
                    "work_center_code": record.work_center_code_snapshot,
                    "work_center_name": record.work_center_name_snapshot,
                    "operator_code": record.operator_code_snapshot,
                    "operator_name": record.operator_name_snapshot,
                    "ended_at": record.ended_at,
                    "reason_code": reason_code,
                    "reason_name": reason.name if reason else "未分类不良",
                    "qty": qty,
                    "remark": record.remark,
                }
            )

    items = []
    for reason_code, data in summary.items():
        reason = reason_map.get(reason_code)
        items.append(
            {
                "reason_code": reason_code,
                "reason_name": reason.name if reason else "未分类不良",
                "category": reason.category if reason else None,
                "bad_qty": data["bad_qty"],
                "clock_count": len(data["clock_ids"]),
            }
        )
    items.sort(key=lambda item: item["bad_qty"], reverse=True)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "total_bad_qty": sum((item["bad_qty"] for item in items), Decimal("0")),
        "total_clock_records": len(records),
        "items": items,
        "recent_records": recent_records[:50],
    }


@router.get("/reports/output", response_model=OutputReportRead)
async def get_output_report(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_any_authenticated_actor),
    report_date: date | None = Query(default=None, alias="date"),
) -> dict[str, Any]:
    target_date = report_date or datetime.now(UTC).date()
    records = list(
        await db.scalars(
            select(ClockRecord)
            .where(
                ClockRecord.tenant_id == actor.tenant_id,
                ClockRecord.deleted_at.is_(None),
                ClockRecord.ended_at >= start_of_day(target_date),
                ClockRecord.ended_at <= end_of_day(target_date),
            )
            .order_by(ClockRecord.ended_at.desc())
        )
    )

    work_orders: dict[Any, WorkOrder] = {}
    work_order_ids = {record.work_order_id for record in records}
    if work_order_ids:
        work_orders = {
            work_order.id: work_order
            for work_order in await db.scalars(
                select(WorkOrder).where(
                    WorkOrder.tenant_id == actor.tenant_id,
                    WorkOrder.id.in_(work_order_ids),
                    WorkOrder.deleted_at.is_(None),
                )
            )
        }

    work_center_summary: dict[str, dict[str, Any]] = defaultdict(empty_output_summary)
    material_summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"good_qty": Decimal("0"), "bad_qty": Decimal("0"), "work_order_ids": set()}
    )
    recent_records: list[dict[str, Any]] = []

    for record in records:
        good_qty = record.good_qty or Decimal("0")
        bad_qty = record.bad_qty or Decimal("0")
        work_order = work_orders.get(record.work_order_id)

        work_center_code = record.work_center_code_snapshot or "UNKNOWN"
        work_center_data = work_center_summary[work_center_code]
        work_center_data["work_center_code"] = work_center_code
        work_center_data["work_center_name"] = record.work_center_name_snapshot or "未指定工位"
        work_center_data["good_qty"] += good_qty
        work_center_data["bad_qty"] += bad_qty
        work_center_data["clock_count"] += 1

        material_code = work_order.material_code_snapshot if work_order else "UNKNOWN"
        material_data = material_summary[material_code]
        material_data["material_code"] = material_code
        material_data["material_name"] = work_order.material_name_snapshot if work_order else "未关联产品"
        material_data["material_unit"] = work_order.material_unit_snapshot if work_order else "件"
        material_data["good_qty"] += good_qty
        material_data["bad_qty"] += bad_qty
        material_data["work_order_ids"].add(record.work_order_id)

        recent_records.append(
            {
                "work_order_no": record.work_order_no_snapshot,
                "material_code": work_order.material_code_snapshot if work_order else None,
                "material_name": work_order.material_name_snapshot if work_order else None,
                "material_unit": work_order.material_unit_snapshot if work_order else None,
                "operation_seq": record.operation_seq_snapshot,
                "operation_name": record.operation_name_snapshot,
                "work_center_code": record.work_center_code_snapshot,
                "work_center_name": record.work_center_name_snapshot,
                "operator_code": record.operator_code_snapshot,
                "operator_name": record.operator_name_snapshot,
                "ended_at": record.ended_at,
                "good_qty": good_qty,
                "bad_qty": bad_qty,
                "total_qty": good_qty + bad_qty,
                "remark": record.remark,
            }
        )

    by_work_center = []
    for data in work_center_summary.values():
        by_work_center.append(
            {
                "work_center_code": data["work_center_code"],
                "work_center_name": data["work_center_name"],
                "good_qty": data["good_qty"],
                "bad_qty": data["bad_qty"],
                "total_qty": data["good_qty"] + data["bad_qty"],
                "clock_count": data["clock_count"],
            }
        )
    by_work_center.sort(key=lambda item: item["total_qty"], reverse=True)

    by_material = []
    for data in material_summary.values():
        by_material.append(
            {
                "material_code": data["material_code"],
                "material_name": data["material_name"],
                "material_unit": data["material_unit"],
                "good_qty": data["good_qty"],
                "bad_qty": data["bad_qty"],
                "total_qty": data["good_qty"] + data["bad_qty"],
                "work_order_count": len(data["work_order_ids"]),
            }
        )
    by_material.sort(key=lambda item: item["total_qty"], reverse=True)

    total_good_qty = sum((record.good_qty for record in records), Decimal("0"))
    total_bad_qty = sum((record.bad_qty for record in records), Decimal("0"))

    return {
        "report_date": target_date,
        "total_good_qty": total_good_qty,
        "total_bad_qty": total_bad_qty,
        "total_output_qty": total_good_qty + total_bad_qty,
        "clock_count": len(records),
        "work_order_count": len(work_order_ids),
        "by_work_center": by_work_center,
        "by_material": by_material,
        "recent_records": recent_records[:50],
    }


@router.get("/reports/oee", response_model=OeeReportRead)
async def get_oee_report(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_any_authenticated_actor),
    report_date: date | None = Query(default=None, alias="date"),
    planned_minutes: int = Query(default=480, ge=1, le=1440),
) -> dict[str, Any]:
    target_date = report_date or datetime.now(UTC).date()
    work_centers = list(
        await db.scalars(
            select(WorkCenter)
            .where(
                WorkCenter.tenant_id == actor.tenant_id,
                WorkCenter.deleted_at.is_(None),
                WorkCenter.is_active.is_(True),
            )
            .order_by(WorkCenter.code)
        )
    )
    records = list(
        await db.scalars(
            select(ClockRecord)
            .where(
                ClockRecord.tenant_id == actor.tenant_id,
                ClockRecord.deleted_at.is_(None),
                ClockRecord.ended_at >= start_of_day(target_date),
                ClockRecord.ended_at <= end_of_day(target_date),
            )
            .order_by(ClockRecord.ended_at.desc())
        )
    )

    summary: dict[str, dict[str, Any]] = {}
    for work_center in work_centers:
        summary[work_center.code] = {
            "work_center_code": work_center.code,
            "work_center_name": work_center.name,
            "work_center_type": work_center.work_center_type,
            "actual_seconds": 0,
            "good_qty": Decimal("0"),
            "bad_qty": Decimal("0"),
            "clock_count": 0,
        }

    for record in records:
        work_center_code = record.work_center_code_snapshot or "UNKNOWN"
        data = summary.setdefault(
            work_center_code,
            {
                "work_center_code": work_center_code,
                "work_center_name": record.work_center_name_snapshot or "未指定工位",
                "work_center_type": None,
                "actual_seconds": 0,
                "good_qty": Decimal("0"),
                "bad_qty": Decimal("0"),
                "clock_count": 0,
            },
        )
        duration_seconds = max(int((record.ended_at - record.started_at).total_seconds()), 0)
        data["actual_seconds"] += duration_seconds
        data["good_qty"] += record.good_qty or Decimal("0")
        data["bad_qty"] += record.bad_qty or Decimal("0")
        data["clock_count"] += 1

    planned_minutes_decimal = Decimal(planned_minutes)
    items = []
    for data in summary.values():
        actual_minutes = minutes_from_seconds(data["actual_seconds"])
        good_qty = data["good_qty"]
        bad_qty = data["bad_qty"]
        items.append(
            {
                "work_center_code": data["work_center_code"],
                "work_center_name": data["work_center_name"],
                "work_center_type": data["work_center_type"],
                "planned_run_minutes": planned_minutes_decimal,
                "actual_run_minutes": actual_minutes,
                "oee": rate(actual_minutes, planned_minutes_decimal),
                "good_qty": good_qty,
                "bad_qty": bad_qty,
                "total_qty": good_qty + bad_qty,
                "clock_count": data["clock_count"],
            }
        )
    items.sort(key=lambda item: (item["actual_run_minutes"], item["total_qty"]), reverse=True)

    total_actual_minutes = sum((item["actual_run_minutes"] for item in items), Decimal("0"))
    total_planned_minutes = planned_minutes_decimal * Decimal(len(items))

    return {
        "report_date": target_date,
        "planned_minutes_per_work_center": planned_minutes,
        "total_actual_minutes": total_actual_minutes,
        "average_oee": rate(total_actual_minutes, total_planned_minutes),
        "items": items,
    }
