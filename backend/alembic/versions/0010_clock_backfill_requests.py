"""clock backfill requests

Revision ID: 0010_clock_backfill_requests
Revises: 0009_worker_operation_skills
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_clock_backfill_requests"
down_revision: str | None = "0009_worker_operation_skills"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clock_backfill_requests",
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clock_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("work_order_no_snapshot", sa.String(length=64), nullable=False),
        sa.Column("operation_seq_snapshot", sa.Integer(), nullable=False),
        sa.Column("operation_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("operation_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("work_center_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_center_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("work_center_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("applicant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("applicant_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("applicant_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operator_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("operator_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("requested_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("good_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("bad_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("defects", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("material_consumed", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_remark", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["clock_record_id"], ["clock_records.id"]),
        sa.ForeignKeyConstraint(["operation_id"], ["work_order_operations.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clock_backfill_requests_tenant_id", "clock_backfill_requests", ["tenant_id"])
    op.create_index(
        "ix_clock_backfill_requests_tenant_status",
        "clock_backfill_requests",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_clock_backfill_requests_tenant_operation",
        "clock_backfill_requests",
        ["tenant_id", "operation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_clock_backfill_requests_tenant_operation", table_name="clock_backfill_requests")
    op.drop_index("ix_clock_backfill_requests_tenant_status", table_name="clock_backfill_requests")
    op.drop_index("ix_clock_backfill_requests_tenant_id", table_name="clock_backfill_requests")
    op.drop_table("clock_backfill_requests")
