"""operation execution fields

Revision ID: 0002_operation_execution_fields
Revises: 0001_initial
Create Date: 2026-05-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_operation_execution_fields"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("work_order_operations", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("work_order_operations", sa.Column("started_by_operator_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("work_order_operations", sa.Column("started_by_operator_code", sa.String(length=64), nullable=True))
    op.add_column("work_order_operations", sa.Column("started_by_operator_name", sa.String(length=128), nullable=True))

    op.add_column("clock_records", sa.Column("work_order_no_snapshot", sa.String(length=64), nullable=True))
    op.add_column("clock_records", sa.Column("operation_seq_snapshot", sa.Integer(), nullable=True))
    op.add_column("clock_records", sa.Column("operation_code_snapshot", sa.String(length=64), nullable=True))
    op.add_column("clock_records", sa.Column("operation_name_snapshot", sa.String(length=128), nullable=True))
    op.add_column("clock_records", sa.Column("work_center_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("clock_records", sa.Column("work_center_code_snapshot", sa.String(length=64), nullable=True))
    op.add_column("clock_records", sa.Column("work_center_name_snapshot", sa.String(length=128), nullable=True))
    op.add_column(
        "clock_records",
        sa.Column("defects", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "clock_records",
        sa.Column("material_consumed", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.create_index("ix_clock_records_operation", "clock_records", ["operation_id", "created_at"])
    op.create_index("ix_clock_records_work_order", "clock_records", ["work_order_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_clock_records_work_order", table_name="clock_records")
    op.drop_index("ix_clock_records_operation", table_name="clock_records")
    op.drop_column("clock_records", "material_consumed")
    op.drop_column("clock_records", "defects")
    op.drop_column("clock_records", "work_center_name_snapshot")
    op.drop_column("clock_records", "work_center_code_snapshot")
    op.drop_column("clock_records", "work_center_id")
    op.drop_column("clock_records", "operation_name_snapshot")
    op.drop_column("clock_records", "operation_code_snapshot")
    op.drop_column("clock_records", "operation_seq_snapshot")
    op.drop_column("clock_records", "work_order_no_snapshot")
    op.drop_column("work_order_operations", "started_by_operator_name")
    op.drop_column("work_order_operations", "started_by_operator_code")
    op.drop_column("work_order_operations", "started_by_operator_id")
    op.drop_column("work_order_operations", "started_at")
