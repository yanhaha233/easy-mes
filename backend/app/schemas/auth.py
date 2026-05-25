from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

UserRole = Literal["planner", "operator", "inspector", "admin"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class CurrentUserRead(BaseModel):
    id: UUID
    tenant_id: UUID
    username: str
    display_name: str
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: CurrentUserRead
