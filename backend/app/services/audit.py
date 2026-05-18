from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.production import AuditLog


async def write_audit_log(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor_code: str,
    entity_type: str,
    action: str,
    entity_id: UUID | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
    detail: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_code=actor_code,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            from_state=from_state,
            to_state=to_state,
            detail=detail or {},
        )
    )
