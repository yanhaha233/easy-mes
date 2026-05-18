from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class DefectSummaryItem(BaseModel):
    reason_code: str
    reason_name: str
    category: str | None = None
    bad_qty: Decimal
    clock_count: int


class DefectRecordItem(BaseModel):
    work_order_no: str | None = None
    operation_seq: int | None = None
    operation_name: str | None = None
    work_center_code: str | None = None
    work_center_name: str | None = None
    operator_code: str | None = None
    operator_name: str | None = None
    ended_at: datetime
    reason_code: str
    reason_name: str
    qty: Decimal
    remark: str | None = None


class DefectReportRead(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    total_bad_qty: Decimal
    total_clock_records: int
    items: list[DefectSummaryItem]
    recent_records: list[DefectRecordItem]


class OutputWorkCenterItem(BaseModel):
    work_center_code: str
    work_center_name: str
    good_qty: Decimal
    bad_qty: Decimal
    total_qty: Decimal
    clock_count: int


class OutputMaterialItem(BaseModel):
    material_code: str
    material_name: str
    material_unit: str
    good_qty: Decimal
    bad_qty: Decimal
    total_qty: Decimal
    work_order_count: int


class OutputRecordItem(BaseModel):
    work_order_no: str | None = None
    material_code: str | None = None
    material_name: str | None = None
    material_unit: str | None = None
    operation_seq: int | None = None
    operation_name: str | None = None
    work_center_code: str | None = None
    work_center_name: str | None = None
    operator_code: str | None = None
    operator_name: str | None = None
    ended_at: datetime
    good_qty: Decimal
    bad_qty: Decimal
    total_qty: Decimal
    remark: str | None = None


class OutputReportRead(BaseModel):
    report_date: date
    total_good_qty: Decimal
    total_bad_qty: Decimal
    total_output_qty: Decimal
    clock_count: int
    work_order_count: int
    by_work_center: list[OutputWorkCenterItem]
    by_material: list[OutputMaterialItem]
    recent_records: list[OutputRecordItem]


class OeeWorkCenterItem(BaseModel):
    work_center_code: str
    work_center_name: str
    work_center_type: str | None = None
    planned_run_minutes: Decimal
    actual_run_minutes: Decimal
    oee: Decimal
    good_qty: Decimal
    bad_qty: Decimal
    total_qty: Decimal
    clock_count: int


class OeeReportRead(BaseModel):
    report_date: date
    planned_minutes_per_work_center: int
    total_actual_minutes: Decimal
    average_oee: Decimal
    items: list[OeeWorkCenterItem]
