from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import EntityRead

Priority = Literal["normal", "high", "urgent"]
WorkOrderSource = Literal["manual", "erp"]
WorkOrderStatus = Literal["draft", "pending", "scheduled", "in_progress", "paused", "completed", "closed", "cancelled"]
OperationStatus = Literal["pending", "ready", "in_progress", "reporting", "paused", "done", "cancelled"]


class WorkOrderCreate(BaseModel):
    material_code: str = Field(min_length=1, max_length=64)
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    due_date: date | None = None
    priority: Priority = "normal"
    source: WorkOrderSource = "manual"
    external_ref: str | None = Field(default=None, max_length=128)
    customer_name: str | None = Field(default=None, max_length=128)
    remark: str | None = None


class ProductionReceiptCreate(BaseModel):
    good_qty: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    lot_no: str | None = Field(default=None, max_length=128)
    warehouse_code: str | None = Field(default=None, max_length=64)
    remark: str | None = None


class WorkOrderCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=255)
    allow_abandon_wip: bool = False


class WorkOrderOperationAssignment(BaseModel):
    operation_seq: int = Field(gt=0)
    operator_code: str = Field(min_length=1, max_length=64)


class WorkOrderSchedule(BaseModel):
    operator_code: str | None = Field(default=None, max_length=64)
    operation_assignments: list[WorkOrderOperationAssignment] = Field(default_factory=list)


class WorkOrderMaterialRead(EntityRead):
    component_material_id: UUID
    material_code: str
    material_name: str
    material_spec: str | None = None
    unit: str
    qty_per: Decimal
    loss_rate: Decimal
    required_qty: Decimal
    issued_qty: Decimal
    consumed_qty: Decimal


class WorkOrderOperationRead(EntityRead):
    seq: int
    operation_code: str
    operation_name: str
    work_center_id: UUID
    work_center_code: str
    work_center_name: str
    setup_time_sec: int
    unit_time_sec: int
    planned_duration_sec: int
    planned_qty: Decimal
    good_qty: Decimal
    bad_qty: Decimal
    status: OperationStatus
    assigned_operator_code: str | None = None
    assigned_operator_name: str | None = None
    started_at: datetime | None = None
    started_by_operator_code: str | None = None
    started_by_operator_name: str | None = None


class WorkOrderMaterialSnapshot(BaseModel):
    code: str
    name: str
    spec: str | None = None
    unit: str


class WorkOrderBomSnapshot(BaseModel):
    id: UUID | None = None
    version: str | None = None
    material_lines: int


class WorkOrderRoutingSnapshot(BaseModel):
    id: UUID | None = None
    version: str | None = None
    operation_lines: int


class WorkOrderRead(EntityRead):
    work_order_no: str
    source: WorkOrderSource
    external_ref: str | None = None
    material_id: UUID
    material: WorkOrderMaterialSnapshot
    planned_qty: Decimal
    actual_good_qty: Decimal
    actual_bad_qty: Decimal
    due_date: date | None = None
    priority: Priority
    customer_name: str | None = None
    status: WorkOrderStatus
    bom: WorkOrderBomSnapshot
    routing: WorkOrderRoutingSnapshot
    created_by: str
    remark: str | None = None
    materials_required: list[WorkOrderMaterialRead]
    operations: list[WorkOrderOperationRead]


class WorkOrderListItem(EntityRead):
    work_order_no: str
    material_code: str
    material_name: str
    planned_qty: Decimal
    actual_good_qty: Decimal
    actual_bad_qty: Decimal
    due_date: date | None = None
    priority: Priority
    source: WorkOrderSource
    status: WorkOrderStatus
    customer_name: str | None = None
    created_by: str
    created_at: datetime
    assigned_operator_codes: list[str] = Field(default_factory=list)
    assigned_operator_names: list[str] = Field(default_factory=list)


class KittingShortageItem(BaseModel):
    material_code: str
    material_name: str
    required_qty: Decimal
    available_qty: Decimal
    shortage_qty: Decimal
    expected_arrival: date | None = None


class KittingCheckRead(BaseModel):
    work_order_no: str
    is_complete: bool
    mode: str
    shortage: list[KittingShortageItem]
    checked_at: datetime


class ProductionReceiptRead(EntityRead):
    receipt_no: str
    work_order_id: UUID
    work_order_no: str
    material_id: UUID
    material: WorkOrderMaterialSnapshot
    good_qty: Decimal
    lot_no: str | None = None
    warehouse_code: str | None = None
    received_by: str
    received_at: datetime
    remark: str | None = None


class WorkOrderReceiptResponse(BaseModel):
    work_order: WorkOrderRead
    receipt: ProductionReceiptRead


class TraceClockRecordRead(EntityRead):
    operation_id: UUID
    operation_seq: int | None = None
    operation_code: str | None = None
    operation_name: str | None = None
    work_center_id: UUID | None = None
    work_center_code: str | None = None
    work_center_name: str | None = None
    operator_id: UUID | None = None
    operator_code: str | None = None
    operator_name: str | None = None
    started_at: datetime
    ended_at: datetime
    elapsed_seconds: int | None = None
    time_anomaly: bool = False
    time_anomaly_reason: str | None = None
    time_anomaly_detail: dict[str, Any] | None = None
    good_qty: Decimal
    bad_qty: Decimal
    defects: list
    material_consumed: list
    remark: str | None = None


class TraceQualityRecordRead(EntityRead):
    operation_id: UUID | None = None
    operation_seq: int | None = None
    operation_code: str | None = None
    operation_name: str | None = None
    inspector_code: str
    inspector_name: str
    inspect_type: str
    sample_qty: Decimal
    pass_qty: Decimal
    fail_qty: Decimal
    result: str
    disposition: str | None = None
    inspected_at: datetime
    remark: str | None = None


class TraceAuditEventRead(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID | None = None
    action: str
    actor_code: str
    actor_name: str | None = None
    from_state: str | None = None
    to_state: str | None = None
    detail: dict
    created_at: datetime


class TraceTimelineEvent(BaseModel):
    event_type: str
    title: str
    occurred_at: datetime
    actor_code: str | None = None
    actor_name: str | None = None
    operation_seq: int | None = None
    good_qty: Decimal | None = None
    bad_qty: Decimal | None = None
    detail: dict


class WorkOrderTraceabilityRead(BaseModel):
    work_order_no: str
    status: WorkOrderStatus
    material: WorkOrderMaterialSnapshot
    planned_qty: Decimal
    actual_good_qty: Decimal
    actual_bad_qty: Decimal
    materials_required: list[WorkOrderMaterialRead]
    operations: list[WorkOrderOperationRead]
    clock_records: list[TraceClockRecordRead]
    receipts: list[ProductionReceiptRead]
    quality_records: list[TraceQualityRecordRead]
    audit_events: list[TraceAuditEventRead]
    timeline: list[TraceTimelineEvent]
