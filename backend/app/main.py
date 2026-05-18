from fastapi import FastAPI

from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.health import router as health_router
from app.api.v1.master_data import router as master_data_router
from app.api.v1.operations import router as operation_router
from app.api.v1.quality import router as quality_router
from app.api.v1.reports import router as report_router
from app.api.v1.work_orders import router as work_order_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(master_data_router, prefix=settings.api_v1_prefix)
    app.include_router(work_order_router, prefix=settings.api_v1_prefix)
    app.include_router(operation_router, prefix=settings.api_v1_prefix)
    app.include_router(quality_router, prefix=settings.api_v1_prefix)
    app.include_router(dashboard_router, prefix=settings.api_v1_prefix)
    app.include_router(report_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
