from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.config import settings
from app.models.production import ProductionReceipt, WorkOrder
from app.services.erp_integration import build_erp_feedback_payload, require_erp_api_key


def test_require_erp_api_key_rejects_invalid_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "erp_integration_api_key", SecretStr("secret-key"))

    with pytest.raises(HTTPException) as exc_info:
        require_erp_api_key("wrong-key")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "INVALID_ERP_API_KEY"


def test_build_erp_feedback_payload_contains_receipt_and_actual_quantities() -> None:
    completed_at = datetime(2026, 5, 25, 10, 30, tzinfo=UTC)
    work_order = WorkOrder(
        external_ref="ERP-MO-001",
        work_order_no="WO202605250001",
        status="closed",
        actual_good_qty=Decimal("98.000000"),
        actual_bad_qty=Decimal("2.000000"),
    )
    receipt = ProductionReceipt(
        receipt_no="RC202605250001",
        lot_no="FG-001",
        warehouse_code="FG-01",
        received_at=completed_at,
    )

    payload = build_erp_feedback_payload(work_order, receipt)

    assert payload == {
        "external_ref": "ERP-MO-001",
        "work_order_no": "WO202605250001",
        "receipt_no": "RC202605250001",
        "status": "closed",
        "actual_good_qty": 98.0,
        "actual_bad_qty": 2.0,
        "lot_no": "FG-001",
        "warehouse_code": "FG-01",
        "completed_at": "2026-05-25T10:30:00+00:00",
    }
