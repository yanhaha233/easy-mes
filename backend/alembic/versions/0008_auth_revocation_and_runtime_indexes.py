"""auth revocation and runtime indexes

Revision ID: 0008_auth_runtime_indexes
Revises: 0007_clock_time_anomaly_fields
Create Date: 2026-05-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_auth_runtime_indexes"
down_revision: str | None = "0007_clock_time_anomaly_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "jti", name="uq_revoked_tokens_tenant_jti"),
    )
    op.create_index("ix_revoked_tokens_tenant_expires", "revoked_tokens", ["tenant_id", "expires_at"])
    op.create_index(
        "ix_audit_logs_tenant_entity_created",
        "audit_logs",
        ["tenant_id", "entity_type", "entity_id", "created_at"],
    )
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])
    op.create_index("ix_clock_records_tenant_ended", "clock_records", ["tenant_id", "ended_at"])
    op.create_index(
        "ix_clock_records_tenant_work_center_ended",
        "clock_records",
        ["tenant_id", "work_center_id", "ended_at"],
    )
    op.create_index("ix_idempotency_keys_tenant_expires", "idempotency_keys", ["tenant_id", "expires_at"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_tenant_expires", table_name="idempotency_keys")
    op.drop_index("ix_clock_records_tenant_work_center_ended", table_name="clock_records")
    op.drop_index("ix_clock_records_tenant_ended", table_name="clock_records")
    op.drop_index("ix_audit_logs_tenant_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_entity_created", table_name="audit_logs")
    op.drop_index("ix_revoked_tokens_tenant_expires", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
