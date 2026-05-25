from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.defaults import DEFAULT_TENANT_ID
from app.schemas.work_order import Priority

FeedbackStatus = Literal["pending", "acked", "failed"]


class ErpWorkOrderCreate(BaseModel):
    tenant_id: UUID = DEFAULT_TENANT_ID
    external_ref: str = Field(min_length=1, max_length=128)
    material_code: str = Field(min_length=1, max_length=64)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    due_date: date | None = None
    priority: Priority = "normal"
    customer_name: str | None = Field(default=None, max_length=128)
    remark: str | None = None


class ErpWorkOrderAccepted(BaseModel):
    work_order_no: str
    external_ref: str
    status: str


class ErpFeedbackRead(BaseModel):
    id: UUID
    external_ref: str
    work_order_no: str
    receipt_no: str
    actual_good_qty: Decimal
    actual_bad_qty: Decimal
    lot_no: str | None = None
    warehouse_code: str | None = None
    completed_at: datetime
    status: FeedbackStatus
    attempt_count: int
    last_attempt_at: datetime | None = None
    last_error: str | None = None
    acked_at: datetime | None = None
    request_payload: dict
    response_payload: dict | None = None


class ErpFeedbackAck(BaseModel):
    response_payload: dict | None = None
