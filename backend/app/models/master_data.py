from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UuidPrimaryKeyMixin


class Material(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "materials"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_materials_tenant_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    spec: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    material_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_empty_bom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkCenter(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "work_centers"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_work_centers_tenant_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    work_center_type: Mapped[str] = mapped_column(String(32), nullable=False)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class Team(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_teams_tenant_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    leader_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    workers: Mapped[list["Worker"]] = relationship(back_populates="team")


class Worker(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "workers"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_workers_tenant_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    worker_type: Mapped[str] = mapped_column(String(32), nullable=False)
    team_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("teams.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    team: Mapped[Team | None] = relationship(back_populates="workers")
    operation_skills: Mapped[list["WorkerOperationSkill"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="worker",
    )


class WorkerOperationSkill(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "worker_operation_skills"
    __table_args__ = (
        UniqueConstraint("tenant_id", "worker_id", "operation_code", name="uq_worker_operation_skills_scope"),
        Index("ix_worker_operation_skills_operation", "tenant_id", "operation_code", "is_active"),
    )

    worker_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workers.id"), nullable=False)
    operation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_name_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    worker: Mapped[Worker] = relationship(back_populates="operation_skills")


class DefectReason(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "defect_reasons"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_defect_reasons_tenant_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class Bom(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "boms"
    __table_args__ = (UniqueConstraint("tenant_id", "material_id", "version", name="uq_boms_tenant_material_version"),)

    material_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("materials.id"))
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    material: Mapped[Material] = relationship(foreign_keys=[material_id])
    lines: Mapped[list["BomLine"]] = relationship(cascade="all, delete-orphan", back_populates="bom")


class BomLine(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "bom_lines"
    __table_args__ = (UniqueConstraint("bom_id", "line_no", name="uq_bom_lines_bom_line_no"),)

    bom_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("boms.id"))
    component_material_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("materials.id"))
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_per: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    loss_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, default=Decimal("0"))
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    bom: Mapped[Bom] = relationship(back_populates="lines")
    component_material: Mapped[Material] = relationship(foreign_keys=[component_material_id])

    @property
    def component_material_code(self) -> str | None:
        return self.component_material.code if self.component_material else None

    @property
    def component_material_name(self) -> str | None:
        return self.component_material.name if self.component_material else None


class Routing(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "routings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "material_id", "version", name="uq_routings_tenant_material_version"),
    )

    material_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("materials.id"))
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    material: Mapped[Material] = relationship(foreign_keys=[material_id])
    operations: Mapped[list["RoutingOperation"]] = relationship(cascade="all, delete-orphan", back_populates="routing")


class RoutingOperation(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "routing_operations"
    __table_args__ = (UniqueConstraint("routing_id", "seq", name="uq_routing_operations_routing_seq"),)

    routing_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("routings.id"))
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_name: Mapped[str] = mapped_column(String(128), nullable=False)
    work_center_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_centers.id"))
    setup_time_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_time_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    routing: Mapped[Routing] = relationship(back_populates="operations")
    work_center: Mapped[WorkCenter] = relationship()

    @property
    def work_center_code(self) -> str | None:
        return self.work_center.code if self.work_center else None

    @property
    def work_center_name(self) -> str | None:
        return self.work_center.name if self.work_center else None
