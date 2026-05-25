"""operation assignment fields

Revision ID: 0006_operation_assignment_fields
Revises: 0005_user_accounts
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_operation_assignment_fields"
down_revision: str | None = "0005_user_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "work_order_operations",
        sa.Column("assigned_operator_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("work_order_operations", sa.Column("assigned_operator_code", sa.String(length=64), nullable=True))
    op.add_column("work_order_operations", sa.Column("assigned_operator_name", sa.String(length=128), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE work_order_operations AS operation
            SET
                assigned_operator_id = COALESCE(operation.started_by_operator_id, worker.id),
                assigned_operator_code = COALESCE(operation.started_by_operator_code, worker.code),
                assigned_operator_name = COALESCE(operation.started_by_operator_name, worker.name)
            FROM workers AS worker
            WHERE worker.tenant_id = operation.tenant_id
              AND worker.code = 'default_operator'
              AND worker.deleted_at IS NULL
              AND worker.is_active IS TRUE
              AND operation.status IN ('pending', 'ready', 'in_progress', 'reporting', 'paused')
              AND operation.assigned_operator_id IS NULL
              AND operation.assigned_operator_code IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("work_order_operations", "assigned_operator_name")
    op.drop_column("work_order_operations", "assigned_operator_code")
    op.drop_column("work_order_operations", "assigned_operator_id")
