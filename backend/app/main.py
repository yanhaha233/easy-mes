from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.health import router as health_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.master_data import router as master_data_router
from app.api.v1.operations import router as operation_router
from app.api.v1.quality import router as quality_router
from app.api.v1.reports import router as report_router
from app.api.v1.work_orders import router as work_order_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.request_context import REQUEST_ID_HEADER, TRACE_ID_HEADER
from app.db.session import dispose_engine
from app.middleware.request_context import RequestContextMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[REQUEST_ID_HEADER, TRACE_ID_HEADER],
        )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(integrations_router, prefix=settings.api_v1_prefix)
    app.include_router(master_data_router, prefix=settings.api_v1_prefix)
    app.include_router(work_order_router, prefix=settings.api_v1_prefix)
    app.include_router(operation_router, prefix=settings.api_v1_prefix)
    app.include_router(quality_router, prefix=settings.api_v1_prefix)
    app.include_router(dashboard_router, prefix=settings.api_v1_prefix)
    app.include_router(report_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
