"""quality records

Revision ID: 0004_quality_records
Revises: 0003_production_receipts
Create Date: 2026-05-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_quality_records"
down_revision: str | None = "0003_production_receipts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quality_records",
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("work_order_no_snapshot", sa.String(length=64), nullable=False),
        sa.Column("operation_seq_snapshot", sa.Integer(), nullable=True),
        sa.Column("operation_code_snapshot", sa.String(length=64), nullable=True),
        sa.Column("operation_name_snapshot", sa.String(length=128), nullable=True),
        sa.Column("inspector_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("inspector_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("inspect_type", sa.String(length=32), nullable=False),
        sa.Column("sample_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("pass_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("fail_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("disposition", sa.String(length=64), nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["operation_id"], ["work_order_operations.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quality_records_tenant_id", "quality_records", ["tenant_id"])
    op.create_index("ix_quality_records_work_order", "quality_records", ["work_order_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_quality_records_work_order", table_name="quality_records")
    op.drop_index("ix_quality_records_tenant_id", table_name="quality_records")
    op.drop_table("quality_records")
