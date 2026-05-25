from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.defaults import DEFAULT_TENANT_ID
from app.db.session import get_db_session
from app.schemas.integration import ErpFeedbackAck, ErpFeedbackRead, ErpWorkOrderAccepted, ErpWorkOrderCreate
from app.services.erp_integration import (
    accept_erp_work_order,
    ack_erp_feedback,
    list_erp_feedback,
    require_erp_api_key,
)

router = APIRouter(prefix="/integrations/erp", tags=["integrations"])


def verify_erp_api_key(x_erp_api_key: str | None = Header(default=None, alias="X-ERP-API-Key")) -> None:
    require_erp_api_key(x_erp_api_key)


@router.post(
    "/work-orders",
    response_model=ErpWorkOrderAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_erp_api_key)],
)
async def create_erp_work_order_endpoint(
    payload: ErpWorkOrderCreate,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await accept_erp_work_order(db, payload)


@router.get(
    "/work-order-feedback",
    response_model=list[ErpFeedbackRead],
    dependencies=[Depends(verify_erp_api_key)],
)
async def list_erp_feedback_endpoint(
    tenant_id: UUID = DEFAULT_TENANT_ID,
    status_filter: str = Query(default="pending", alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    return await list_erp_feedback(db, tenant_id, status_filter, limit, offset)


@router.post(
    "/work-order-feedback/{feedback_id}/ack",
    response_model=ErpFeedbackRead,
    dependencies=[Depends(verify_erp_api_key)],
)
async def ack_erp_feedback_endpoint(
    feedback_id: UUID,
    payload: ErpFeedbackAck,
    tenant_id: UUID = DEFAULT_TENANT_ID,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return await ack_erp_feedback(db, feedback_id, tenant_id, payload)
