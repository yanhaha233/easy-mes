from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete

from app.db.session import AsyncSessionLocal, engine
from app.models.auth import RevokedToken
from app.models.production import IdempotencyKey


async def cleanup_expired_runtime_data() -> dict[str, int]:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        revoked_result = await session.execute(delete(RevokedToken).where(RevokedToken.expires_at <= now))
        idempotency_result = await session.execute(delete(IdempotencyKey).where(IdempotencyKey.expires_at <= now))
        await session.commit()
    return {
        "revoked_tokens": int(revoked_result.rowcount or 0),
        "idempotency_keys": int(idempotency_result.rowcount or 0),
    }


async def async_main() -> None:
    try:
        result = await cleanup_expired_runtime_data()
        print("Expired runtime data cleaned.")
        print(f"  revoked_tokens={result['revoked_tokens']}")
        print(f"  idempotency_keys={result['idempotency_keys']}")
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
