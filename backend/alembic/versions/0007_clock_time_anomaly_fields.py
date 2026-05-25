"""clock time anomaly fields

Revision ID: 0007_clock_time_anomaly_fields
Revises: 0006_operation_assignment_fields
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_clock_time_anomaly_fields"
down_revision: str | None = "0006_operation_assignment_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("clock_records", sa.Column("elapsed_seconds", sa.Integer(), nullable=True))
    op.add_column(
        "clock_records",
        sa.Column("time_anomaly", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("clock_records", sa.Column("time_anomaly_reason", sa.String(length=64), nullable=True))
    op.add_column("clock_records", sa.Column("time_anomaly_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index("ix_clock_records_time_anomaly", "clock_records", ["tenant_id", "time_anomaly", "ended_at"])


def downgrade() -> None:
    op.drop_index("ix_clock_records_time_anomaly", table_name="clock_records")
    op.drop_column("clock_records", "time_anomaly_detail")
    op.drop_column("clock_records", "time_anomaly_reason")
    op.drop_column("clock_records", "time_anomaly")
    op.drop_column("clock_records", "elapsed_seconds")
