from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import EntityRead

InspectType = Literal["first_article", "patrol", "final"]
InspectResult = Literal["pass", "fail", "concession"]


class QualityRecordCreate(BaseModel):
    work_order_no: str = Field(min_length=1, max_length=64)
    operation_id: UUID | None = None
    sample_qty: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    pass_qty: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    fail_qty: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    result: InspectResult
    inspector_code: str | None = Field(default=None, max_length=64)
    disposition: str | None = Field(default=None, max_length=64)
    remark: str | None = None

    @model_validator(mode="after")
    def validate_sample_qty(self) -> "QualityRecordCreate":
        if self.pass_qty + self.fail_qty != self.sample_qty:
            raise ValueError("pass_qty + fail_qty must equal sample_qty")
        if self.fail_qty > 0 and self.result == "pass":
            raise ValueError("result cannot be pass when fail_qty is greater than 0")
        return self


class QualityRecordRead(EntityRead):
    work_order_id: UUID
    operation_id: UUID | None = None
    work_order_no: str
    operation_seq: int | None = None
    operation_code: str | None = None
    operation_name: str | None = None
    inspector_code: str
    inspector_name: str
    inspect_type: InspectType
    sample_qty: Decimal
    pass_qty: Decimal
    fail_qty: Decimal
    result: InspectResult
    disposition: str | None = None
    inspected_at: datetime
    remark: str | None = None
