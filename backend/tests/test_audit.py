import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.services.audit import write_audit_log


class FakeSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, item: object) -> None:
        self.added.append(item)


def test_write_audit_log_json_encodes_detail_values() -> None:
    session = FakeSession()
    tenant_id = uuid4()
    entity_id = uuid4()
    happened_at = datetime(2026, 5, 25, tzinfo=UTC)

    asyncio.run(
        write_audit_log(
            session,
            tenant_id=tenant_id,
            actor_code="planner",
            entity_type="material",
            entity_id=entity_id,
            action="update",
            detail={"qty": Decimal("1.500000"), "entity_id": entity_id, "happened_at": happened_at},
        )
    )

    audit_log = session.added[0]
    assert audit_log.detail == {
        "qty": 1.5,
        "entity_id": str(entity_id),
        "happened_at": "2026-05-25T00:00:00+00:00",
    }
