"""worker operation skills

Revision ID: 0009_worker_operation_skills
Revises: 0008_auth_runtime_indexes
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_worker_operation_skills"
down_revision: str | None = "0008_auth_runtime_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worker_operation_skills",
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_code", sa.String(length=64), nullable=False),
        sa.Column("operation_name_snapshot", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "worker_id", "operation_code", name="uq_worker_operation_skills_scope"),
    )
    op.create_index("ix_worker_operation_skills_tenant_id", "worker_operation_skills", ["tenant_id"])
    op.create_index(
        "ix_worker_operation_skills_operation",
        "worker_operation_skills",
        ["tenant_id", "operation_code", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_worker_operation_skills_operation", table_name="worker_operation_skills")
    op.drop_index("ix_worker_operation_skills_tenant_id", table_name="worker_operation_skills")
    op.drop_table("worker_operation_skills")
