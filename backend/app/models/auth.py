from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UuidPrimaryKeyMixin
from app.models.master_data import Worker


class UserAccount(UuidPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "user_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uq_user_accounts_tenant_username"),)

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    worker_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workers.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    worker: Mapped[Worker | None] = relationship()


class RevokedToken(UuidPrimaryKeyMixin, Base):
    __tablename__ = "revoked_tokens"
    __table_args__ = (
        UniqueConstraint("tenant_id", "jti", name="uq_revoked_tokens_tenant_jti"),
        Index("ix_revoked_tokens_tenant_expires", "tenant_id", "expires_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    jti: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
