from decimal import Decimal

from app.schemas.work_order import WorkOrderImportRow
from app.services.work_order_import import (
    ImportRowError,
    import_row_idempotency_key,
    parse_due_date,
    work_order_create_from_import_row,
)


def test_work_order_import_row_accepts_chinese_priority_and_slash_date() -> None:
    payload = work_order_create_from_import_row(
        WorkOrderImportRow(
            row_no=2,
            material_code=" P-MVP-001 ",
            quantity="1,200.5",
            due_date="2026/06/30",
            priority="紧急",
            external_ref=" SO-1001 ",
        )
    )

    assert payload.material_code == "P-MVP-001"
    assert payload.quantity == Decimal("1200.5")
    assert payload.due_date == parse_due_date("2026-6-30")
    assert payload.priority == "urgent"
    assert payload.external_ref == "SO-1001"
    assert payload.source == "manual"


def test_work_order_import_row_rejects_invalid_quantity() -> None:
    try:
        work_order_create_from_import_row(WorkOrderImportRow(row_no=1, material_code="P-MVP-001", quantity="0"))
    except ImportRowError as exc:
        assert exc.code == "INVALID_QUANTITY"
    else:
        raise AssertionError("expected invalid quantity to fail")


def test_import_row_idempotency_key_changes_with_batch_key() -> None:
    row = WorkOrderImportRow(row_no=1, material_code="P-MVP-001", quantity="10")

    assert import_row_idempotency_key("batch-a", row) == import_row_idempotency_key("batch-a", row)
    assert import_row_idempotency_key("batch-a", row) != import_row_idempotency_key("batch-b", row)
