from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import EntityRead
from app.schemas.work_order import OperationStatus, WorkOrderStatus


class DefectInput(BaseModel):
    reason_code: str = Field(min_length=1, max_length=64)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


class ActualMaterialInput(BaseModel):
    material_code: str = Field(min_length=1, max_length=64)
    qty: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    lot_no: str | None = Field(default=None, max_length=128)


class OperationStart(BaseModel):
    operator_code: str | None = Field(default=None, max_length=64)
    remark: str | None = None


class OperationStateChange(BaseModel):
    operator_code: str | None = Field(default=None, max_length=64)
    reason: str | None = None


class OperationClock(BaseModel):
    good_qty: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    bad_qty: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    defects: list[DefectInput] = Field(default_factory=list)
    actual_materials: list[ActualMaterialInput] = Field(default_factory=list)
    operator_code: str | None = Field(default=None, max_length=64)
    client_timestamp: datetime | None = None
    remark: str | None = None


class OperationRead(EntityRead):
    work_order_id: UUID
    work_order_no: str
    work_order_status: WorkOrderStatus
    material_code: str
    material_name: str
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
    started_at: datetime | None = None
    started_by_operator_code: str | None = None
    started_by_operator_name: str | None = None


class OperationClockRead(BaseModel):
    operation: OperationRead
    work_order_status: WorkOrderStatus
    next_operation_id: UUID | None = None
    clock_record_id: UUID
