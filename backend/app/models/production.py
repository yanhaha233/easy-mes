from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UuidPrimaryKeyMixin


class DocumentSequence(UuidPrimaryKeyMixin, Base):
    __tablename__ = "document_sequences"
    __table_args__ = (UniqueConstraint("tenant_id", "sequence_type", "period", name="uq_document_sequences_scope"),)

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sequence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WorkOrder(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "work_orders"
    __table_args__ = (UniqueConstraint("tenant_id", "work_order_no", name="uq_work_orders_tenant_no"),)

    work_order_no: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    material_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("materials.id"))
    material_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    material_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    material_spec_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    material_unit_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    planned_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    actual_good_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    actual_bad_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    bom_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("boms.id"))
    bom_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    routing_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("routings.id"))
    routing_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    materials: Mapped[list["WorkOrderMaterial"]] = relationship(cascade="all, delete-orphan")
    operations: Mapped[list["WorkOrderOperation"]] = relationship(cascade="all, delete-orphan")


class WorkOrderMaterial(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "work_order_materials"

    work_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_orders.id"))
    # Snapshot references: BOM versions may be changed or removed after release, so these ids intentionally
    # do not carry foreign keys that would rewrite historical work-order semantics.
    bom_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    bom_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bom_line_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    component_material_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("materials.id"))
    component_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    component_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    component_spec_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    component_unit_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    qty_per: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    loss_rate: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False, default=Decimal("0"))
    required_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    issued_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    consumed_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))


class WorkOrderOperation(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "work_order_operations"
    __table_args__ = (UniqueConstraint("work_order_id", "seq", name="uq_work_order_operations_order_seq"),)

    work_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_orders.id"))
    # Snapshot references: routing definitions are mutable master data, while released operations must remain stable.
    routing_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    routing_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    routing_operation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    work_center_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_centers.id"))
    work_center_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    work_center_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    setup_time_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_time_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    planned_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    planned_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    good_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    bad_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_operator_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    assigned_operator_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_operator_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_by_operator_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    started_by_operator_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_by_operator_name: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ClockRecord(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "clock_records"
    __table_args__ = (
        Index("ix_clock_records_tenant_ended", "tenant_id", "ended_at"),
        Index("ix_clock_records_tenant_work_center_ended", "tenant_id", "work_center_id", "ended_at"),
    )

    work_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_orders.id"))
    operation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_order_operations.id"))
    work_order_no_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operation_seq_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operation_code_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operation_name_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    work_center_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    work_center_code_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    work_center_name_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    operator_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    operator_code_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator_name_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_anomaly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_anomaly_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    time_anomaly_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    good_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    bad_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    defects: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    material_consumed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClockBackfillRequest(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "clock_backfill_requests"
    __table_args__ = (
        Index("ix_clock_backfill_requests_tenant_status", "tenant_id", "status", "created_at"),
        Index("ix_clock_backfill_requests_tenant_operation", "tenant_id", "operation_id", "created_at"),
    )

    work_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_orders.id"))
    operation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_order_operations.id"))
    clock_record_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("clock_records.id"))
    work_order_no_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_seq_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    work_center_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    work_center_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    work_center_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    applicant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    applicant_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    applicant_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    operator_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    operator_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    operator_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    good_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    bad_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    defects: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    material_consumed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProductionReceipt(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "production_receipts"
    __table_args__ = (UniqueConstraint("tenant_id", "receipt_no", name="uq_production_receipts_tenant_no"),)

    receipt_no: Mapped[str] = mapped_column(String(64), nullable=False)
    work_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_orders.id"))
    work_order_no_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    material_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("materials.id"))
    material_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    material_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    material_spec_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    material_unit_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    good_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    lot_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    warehouse_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_by: Mapped[str] = mapped_column(String(128), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class QualityRecord(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "quality_records"

    work_order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_orders.id"))
    operation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("work_order_operations.id"))
    work_order_no_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_seq_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operation_code_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operation_name_snapshot: Mapped[str | None] = mapped_column(String(128), nullable=True)
    inspector_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    inspector_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False)
    inspect_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sample_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    pass_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fail_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    disposition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class IdempotencyKey(UuidPrimaryKeyMixin, Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_idempotency_keys_tenant_key"),
        Index("ix_idempotency_keys_tenant_expires", "tenant_id", "expires_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    response_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditLog(UuidPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_entity_created", "tenant_id", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_code: Mapped[str] = mapped_column(String(128), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
