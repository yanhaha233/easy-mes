"""erp work order feedbacks

Revision ID: 0011_erp_work_order_feedbacks
Revises: 0010_clock_backfill_requests
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_erp_work_order_feedbacks"
down_revision: str | None = "0010_clock_backfill_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "erp_work_order_feedbacks",
        sa.Column("external_ref", sa.String(length=128), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_no", sa.String(length=64), nullable=False),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receipt_no", sa.String(length=64), nullable=False),
        sa.Column("actual_good_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("actual_bad_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("lot_no", sa.String(length=128), nullable=True),
        sa.Column("warehouse_code", sa.String(length=64), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["receipt_id"], ["production_receipts.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "receipt_id", name="uq_erp_work_order_feedbacks_tenant_receipt"),
    )
    op.create_index("ix_erp_work_order_feedbacks_tenant_id", "erp_work_order_feedbacks", ["tenant_id"])
    op.create_index(
        "ix_erp_work_order_feedbacks_tenant_status",
        "erp_work_order_feedbacks",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_erp_work_order_feedbacks_tenant_external_ref",
        "erp_work_order_feedbacks",
        ["tenant_id", "external_ref"],
    )
    op.create_index("ix_work_orders_tenant_external_ref", "work_orders", ["tenant_id", "external_ref"])


def downgrade() -> None:
    op.drop_index("ix_work_orders_tenant_external_ref", table_name="work_orders")
    op.drop_index("ix_erp_work_order_feedbacks_tenant_external_ref", table_name="erp_work_order_feedbacks")
    op.drop_index("ix_erp_work_order_feedbacks_tenant_status", table_name="erp_work_order_feedbacks")
    op.drop_index("ix_erp_work_order_feedbacks_tenant_id", table_name="erp_work_order_feedbacks")
    op.drop_table("erp_work_order_feedbacks")
