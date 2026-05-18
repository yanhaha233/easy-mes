"""production receipts

Revision ID: 0003_production_receipts
Revises: 0002_operation_execution_fields
Create Date: 2026-05-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_production_receipts"
down_revision: str | None = "0002_operation_execution_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "production_receipts",
        sa.Column("receipt_no", sa.String(length=64), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_no_snapshot", sa.String(length=64), nullable=False),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("material_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("material_spec_snapshot", sa.String(length=255), nullable=True),
        sa.Column("material_unit_snapshot", sa.String(length=32), nullable=False),
        sa.Column("good_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("lot_no", sa.String(length=128), nullable=True),
        sa.Column("warehouse_code", sa.String(length=64), nullable=True),
        sa.Column("received_by", sa.String(length=128), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "receipt_no", name="uq_production_receipts_tenant_no"),
    )
    op.create_index("ix_production_receipts_tenant_id", "production_receipts", ["tenant_id"])
    op.create_index(
        "ix_production_receipts_work_order",
        "production_receipts",
        ["work_order_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_production_receipts_work_order", table_name="production_receipts")
    op.drop_index("ix_production_receipts_tenant_id", table_name="production_receipts")
    op.drop_table("production_receipts")
