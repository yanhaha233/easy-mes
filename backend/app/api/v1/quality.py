from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Actor, get_default_actor
from app.db.session import get_db_session
from app.schemas.quality import QualityRecordCreate, QualityRecordRead
from app.services.quality import create_quality_record, list_quality_records

router = APIRouter(tags=["quality"])


def require_idempotency_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "缺少 Idempotency-Key 请求头"},
        )
    return idempotency_key


@router.post("/quality/first-article", response_model=QualityRecordRead)
async def create_first_article_record(
    payload: QualityRecordCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await create_quality_record(
        db, "first_article", payload, actor, require_idempotency_key(idempotency_key)
    )


@router.post("/quality/patrol", response_model=QualityRecordRead)
async def create_patrol_record(
    payload: QualityRecordCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await create_quality_record(db, "patrol", payload, actor, require_idempotency_key(idempotency_key))


@router.post("/quality/final", response_model=QualityRecordRead)
async def create_final_record(
    payload: QualityRecordCreate,
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await create_quality_record(db, "final", payload, actor, require_idempotency_key(idempotency_key))


@router.get("/quality/records", response_model=dict)
async def get_quality_records(
    db: AsyncSession = Depends(get_db_session),
    actor: Actor = Depends(get_default_actor),
    work_order_no: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await list_quality_records(db, actor, work_order_no=work_order_no, limit=limit, offset=offset)
