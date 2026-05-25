import logging
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

router = APIRouter(tags=["health"])
logger = logging.getLogger("app.health")
SERVICE_NAME = "easy-mes"


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@router.get("/health/ready")
async def readiness_check(response: Response, db: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.warning("database readiness check failed", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unavailable",
            "service": SERVICE_NAME,
            "checks": {"database": "unavailable"},
        }
    return {"status": "ready", "service": SERVICE_NAME, "checks": {"database": "ok"}}
