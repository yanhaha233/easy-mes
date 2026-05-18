from dataclasses import dataclass
from uuid import UUID

from app.core.defaults import DEFAULT_OPERATOR_CODE, DEFAULT_PLANNER_CODE, DEFAULT_TENANT_ID


@dataclass(frozen=True)
class Actor:
    tenant_id: UUID
    code: str


async def get_default_actor() -> Actor:
    return Actor(tenant_id=DEFAULT_TENANT_ID, code=DEFAULT_PLANNER_CODE)


async def get_default_operator_actor() -> Actor:
    return Actor(tenant_id=DEFAULT_TENANT_ID, code=DEFAULT_OPERATOR_CODE)
