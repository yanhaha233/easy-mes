from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderImportPayload,
    WorkOrderImportResponse,
    WorkOrderImportResult,
    WorkOrderImportRow,
)
from app.services.work_order import create_work_order

PRIORITY_ALIASES = {
    "": "normal",
    "normal": "normal",
    "low": "normal",
    "standard": "normal",
    "普通": "normal",
    "正常": "normal",
    "一般": "normal",
    "high": "high",
    "高": "high",
    "高优先级": "high",
    "urgent": "urgent",
    "紧急": "urgent",
    "加急": "urgent",
}


class ImportRowError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def optional_text(value: str | None) -> str | None:
    text = clean_text(value)
    return text or None


def normalize_priority(value: str | None) -> str:
    key = clean_text(value).lower()
    priority = PRIORITY_ALIASES.get(key)
    if not priority:
        raise ImportRowError("INVALID_PRIORITY", "优先级只支持 普通/高/紧急")
    return priority


def parse_quantity(value: str | None) -> Decimal:
    text = clean_text(value).replace(",", "")
    if not text:
        raise ImportRowError("QUANTITY_REQUIRED", "数量不能为空")
    try:
        quantity = Decimal(text)
    except InvalidOperation as exc:
        raise ImportRowError("INVALID_QUANTITY", "数量格式不正确") from exc
    if quantity <= 0:
        raise ImportRowError("INVALID_QUANTITY", "数量必须大于 0")
    return quantity


def parse_due_date(value: str | None) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    normalized = text.replace("/", "-").replace(".", "-")
    try:
        parts = [int(part) for part in normalized.split("-")]
    except ValueError as exc:
        raise ImportRowError("INVALID_DUE_DATE", "交期格式应为 YYYY-MM-DD") from exc
    if len(parts) != 3:
        raise ImportRowError("INVALID_DUE_DATE", "交期格式应为 YYYY-MM-DD")
    try:
        return date(parts[0], parts[1], parts[2])
    except ValueError as exc:
        raise ImportRowError("INVALID_DUE_DATE", "交期不是有效日期") from exc


def work_order_create_from_import_row(row: WorkOrderImportRow) -> WorkOrderCreate:
    material_code = clean_text(row.material_code)
    if not material_code:
        raise ImportRowError("MATERIAL_CODE_REQUIRED", "物料编码不能为空")
    try:
        return WorkOrderCreate(
            material_code=material_code,
            quantity=parse_quantity(row.quantity),
            due_date=parse_due_date(row.due_date),
            priority=normalize_priority(row.priority),
            source="manual",
            external_ref=optional_text(row.external_ref),
            customer_name=optional_text(row.customer_name),
            remark=optional_text(row.remark),
        )
    except ValidationError as exc:
        first_error = exc.errors()[0]
        raise ImportRowError("INVALID_ROW", str(first_error.get("msg", "导入行格式不正确"))) from exc


def import_row_idempotency_key(batch_key: str, row: WorkOrderImportRow) -> str:
    raw = json.dumps(row.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{batch_key}:{raw}".encode()).hexdigest()
    return f"work-order-import:{digest}"


def row_result_from_http_error(row_no: int, error: HTTPException) -> WorkOrderImportResult:
    code = "IMPORT_ROW_FAILED"
    message = "导入失败"
    if isinstance(error.detail, dict):
        code = str(error.detail.get("code") or code)
        message = str(error.detail.get("message") or message)
    elif error.detail:
        message = str(error.detail)
    return WorkOrderImportResult(row_no=row_no, status="failed", error_code=code, error_message=message)


async def import_work_orders(
    session: AsyncSession,
    payload: WorkOrderImportPayload,
    actor: Actor,
    idempotency_key: str,
) -> dict[str, Any]:
    results: list[WorkOrderImportResult] = []
    for row in payload.rows:
        try:
            create_payload = work_order_create_from_import_row(row)
            created = await create_work_order(
                session,
                create_payload,
                actor,
                import_row_idempotency_key(idempotency_key, row),
            )
            results.append(
                WorkOrderImportResult(
                    row_no=row.row_no,
                    status="accepted",
                    work_order_no=created["work_order_no"],
                )
            )
        except ImportRowError as exc:
            await session.rollback()
            results.append(
                WorkOrderImportResult(
                    row_no=row.row_no,
                    status="failed",
                    error_code=exc.code,
                    error_message=exc.message,
                )
            )
        except HTTPException as exc:
            await session.rollback()
            results.append(row_result_from_http_error(row.row_no, exc))

    accepted_count = sum(1 for item in results if item.status == "accepted")
    response = WorkOrderImportResponse(
        total=len(results),
        accepted_count=accepted_count,
        failed_count=len(results) - accepted_count,
        items=results,
    )
    return response.model_dump(mode="json")
