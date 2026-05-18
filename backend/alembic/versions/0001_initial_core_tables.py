"""initial core tables

Revision ID: 0001_initial
Revises: None
Create Date: 2026-05-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def common_columns() -> list[sa.Column]:
    return [
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("spec", sa.String(length=255), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("material_type", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_empty_bom", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_materials_tenant_code"),
    )
    op.create_index("ix_materials_tenant_deleted", "materials", ["tenant_id", "deleted_at"])

    op.create_table(
        "work_centers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("work_center_type", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_work_centers_tenant_code"),
    )

    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("leader_name", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_teams_tenant_code"),
    )

    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("worker_type", sa.String(length=32), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_workers_tenant_code"),
    )

    op.create_table(
        "defect_reasons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_defect_reasons_tenant_code"),
    )

    op.create_table(
        "boms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("tenant_id", "material_id", "version", name="uq_boms_tenant_material_version"),
    )

    op.create_table(
        "bom_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("boms.id"), nullable=False),
        sa.Column("component_material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("qty_per", sa.Numeric(18, 6), nullable=False),
        sa.Column("loss_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("bom_id", "line_no", name="uq_bom_lines_bom_line_no"),
    )

    op.create_table(
        "routings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("tenant_id", "material_id", "version", name="uq_routings_tenant_material_version"),
    )

    op.create_table(
        "routing_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("routing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("routings.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("operation_code", sa.String(length=64), nullable=False),
        sa.Column("operation_name", sa.String(length=128), nullable=False),
        sa.Column("work_center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("work_centers.id"), nullable=False),
        sa.Column("setup_time_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_time_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("routing_id", "seq", name="uq_routing_operations_routing_seq"),
    )

    op.create_table(
        "document_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_type", sa.String(length=32), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "sequence_type", "period", name="uq_document_sequences_scope"),
    )

    op.create_table(
        "work_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("work_order_no", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("material_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("material_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("material_spec_snapshot", sa.String(length=255), nullable=True),
        sa.Column("material_unit_snapshot", sa.String(length=32), nullable=False),
        sa.Column("planned_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("actual_good_qty", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("actual_bad_qty", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("customer_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("bom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("boms.id"), nullable=True),
        sa.Column("bom_version", sa.String(length=64), nullable=True),
        sa.Column("routing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("routings.id"), nullable=True),
        sa.Column("routing_version", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
        sa.UniqueConstraint("tenant_id", "work_order_no", name="uq_work_orders_tenant_no"),
    )
    op.create_index("ix_work_orders_tenant_status", "work_orders", ["tenant_id", "status"])

    op.create_table(
        "work_order_materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("work_orders.id"), nullable=False),
        sa.Column("bom_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bom_version", sa.String(length=64), nullable=True),
        sa.Column("bom_line_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("component_material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("component_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("component_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("component_spec_snapshot", sa.String(length=255), nullable=True),
        sa.Column("component_unit_snapshot", sa.String(length=32), nullable=False),
        sa.Column("qty_per", sa.Numeric(18, 6), nullable=False),
        sa.Column("loss_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
        sa.Column("required_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("issued_qty", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("consumed_qty", sa.Numeric(18, 6), nullable=False, server_default="0"),
        *common_columns(),
    )

    op.create_table(
        "work_order_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("work_orders.id"), nullable=False),
        sa.Column("routing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("routing_version", sa.String(length=64), nullable=True),
        sa.Column("routing_operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("operation_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("operation_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("work_center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("work_centers.id"), nullable=False),
        sa.Column("work_center_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("work_center_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("setup_time_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_time_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_duration_sec", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("good_qty", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("bad_qty", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False),
        *common_columns(),
        sa.UniqueConstraint("work_order_id", "seq", name="uq_work_order_operations_order_seq"),
    )

    op.create_table(
        "clock_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("work_orders.id"), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("work_order_operations.id"), nullable=False),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operator_code_snapshot", sa.String(length=64), nullable=True),
        sa.Column("operator_name_snapshot", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("good_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("bad_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        *common_columns(),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=128), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "key", name="uq_idempotency_keys_tenant_key"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_code", sa.String(length=128), nullable=False),
        sa.Column("from_state", sa.String(length=64), nullable=True),
        sa.Column("to_state", sa.String(length=64), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("idempotency_keys")
    op.drop_table("clock_records")
    op.drop_table("work_order_operations")
    op.drop_table("work_order_materials")
    op.drop_index("ix_work_orders_tenant_status", table_name="work_orders")
    op.drop_table("work_orders")
    op.drop_table("document_sequences")
    op.drop_table("routing_operations")
    op.drop_table("routings")
    op.drop_table("bom_lines")
    op.drop_table("boms")
    op.drop_table("defect_reasons")
    op.drop_table("workers")
    op.drop_table("teams")
    op.drop_table("work_centers")
    op.drop_index("ix_materials_tenant_deleted", table_name="materials")
    op.drop_table("materials")
