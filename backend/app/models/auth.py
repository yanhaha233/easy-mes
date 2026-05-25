from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UuidPrimaryKeyMixin


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
