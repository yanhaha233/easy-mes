from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.defaults import DEFAULT_TENANT_ID

UserRole = Literal["planner", "operator", "inspector", "admin"]


class LoginRequest(BaseModel):
    tenant_id: UUID = DEFAULT_TENANT_ID
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class CurrentUserRead(BaseModel):
    id: UUID
    tenant_id: UUID
    username: str
    display_name: str
    role: UserRole
    worker_id: UUID | None = None
    worker_code: str | None = None
    worker_name: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: CurrentUserRead
