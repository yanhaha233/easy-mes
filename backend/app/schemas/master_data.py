from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import EntityRead

MaterialType = Literal["product", "semi_finished", "raw_material", "packing", "tooling"]
WorkCenterType = Literal["workstation", "equipment", "line", "inspection"]
WorkerType = Literal["operator", "inspector", "planner", "manager"]
MasterStatus = Literal["draft", "active", "inactive"]


class MaterialBase(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    spec: str | None = Field(default=None, max_length=255)
    unit: str = Field(min_length=1, max_length=32)
    material_type: MaterialType
    is_active: bool = True
    allow_empty_bom: bool = False
    remark: str | None = None


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    spec: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    material_type: MaterialType | None = None
    is_active: bool | None = None
    allow_empty_bom: bool | None = None
    remark: str | None = None


class MaterialRead(MaterialBase, EntityRead):
    pass


class WorkCenterBase(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    work_center_type: WorkCenterType = "workstation"
    location: str | None = Field(default=None, max_length=128)
    is_active: bool = True
    remark: str | None = None


class WorkCenterCreate(WorkCenterBase):
    pass


class WorkCenterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    work_center_type: WorkCenterType | None = None
    location: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None
    remark: str | None = None


class WorkCenterRead(WorkCenterBase, EntityRead):
    pass


class TeamBase(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    leader_name: str | None = Field(default=None, max_length=128)
    is_active: bool = True
    remark: str | None = None


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    leader_name: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None
    remark: str | None = None


class TeamRead(TeamBase, EntityRead):
    pass


class WorkerBase(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    worker_type: WorkerType = "operator"
    team_id: UUID | None = None
    is_active: bool = True
    remark: str | None = None


class WorkerCreate(WorkerBase):
    pass


class WorkerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    worker_type: WorkerType | None = None
    team_id: UUID | None = None
    is_active: bool | None = None
    remark: str | None = None


class WorkerRead(WorkerBase, EntityRead):
    pass


class OperationSkillOptionRead(BaseModel):
    operation_code: str
    operation_name: str


class WorkerOperationSkillRead(EntityRead):
    worker_id: UUID
    operation_code: str
    operation_name: str | None = None
    is_active: bool
    remark: str | None = None


class WorkerOperationSkillUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_codes: list[str] = Field(default_factory=list)


class DefectReasonBase(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    is_active: bool = True
    remark: str | None = None


class DefectReasonCreate(DefectReasonBase):
    pass


class DefectReasonUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None
    remark: str | None = None


class DefectReasonRead(DefectReasonBase, EntityRead):
    pass


class BomLineCreate(BaseModel):
    component_material_id: UUID
    line_no: int = Field(gt=0)
    qty_per: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    loss_rate: Decimal = Field(default=Decimal("0"), ge=0, max_digits=9, decimal_places=6)
    remark: str | None = None


class BomLineRead(BomLineCreate, EntityRead):
    component_material_code: str | None = None
    component_material_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BomCreate(BaseModel):
    material_id: UUID
    version: str = Field(min_length=1, max_length=64)
    status: MasterStatus = "draft"
    remark: str | None = None
    lines: list[BomLineCreate] = Field(default_factory=list)


class BomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MasterStatus | None = None
    remark: str | None = None
    lines: list[BomLineCreate] | None = None


class BomRead(EntityRead):
    material_id: UUID
    version: str
    status: str
    remark: str | None = None
    lines: list[BomLineRead] = Field(default_factory=list)


class RoutingOperationCreate(BaseModel):
    seq: int = Field(gt=0)
    operation_code: str = Field(min_length=1, max_length=64)
    operation_name: str = Field(min_length=1, max_length=128)
    work_center_id: UUID
    setup_time_sec: int = Field(default=0, ge=0)
    unit_time_sec: int = Field(default=0, ge=0)
    is_active: bool = True
    remark: str | None = None


class RoutingOperationRead(RoutingOperationCreate, EntityRead):
    work_center_code: str | None = None
    work_center_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RoutingCreate(BaseModel):
    material_id: UUID
    version: str = Field(min_length=1, max_length=64)
    status: MasterStatus = "draft"
    remark: str | None = None
    operations: list[RoutingOperationCreate] = Field(default_factory=list)


class RoutingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MasterStatus | None = None
    remark: str | None = None
    operations: list[RoutingOperationCreate] | None = None


class RoutingRead(EntityRead):
    material_id: UUID
    version: str
    status: str
    remark: str | None = None
    operations: list[RoutingOperationRead] = Field(default_factory=list)
