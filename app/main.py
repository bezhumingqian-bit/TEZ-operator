"""FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import hosts as hosts_router
from app.utils.logger import get_logger, setup_logging

settings = get_settings()
setup_logging(level=settings.app_log_level)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """生命周期钩子：启动 / 关闭。"""

    log.info(
        "app.startup",
        env=settings.app_env,
        debug=settings.app_debug,
        ccdb_mock=settings.ccdb_mock_mode,
        tcum_mock=settings.tcum_mock_mode,
        idcrm_mock=settings.idcrm_mock_mode,
    )
    try:
        yield
    finally:
        log.info("app.shutdown")


def create_app() -> FastAPI:
    """工厂函数，便于测试 / 多实例。"""

    app = FastAPI(
        title="TEZ Operator API",
        version="0.1.0",
        description="腾讯云边缘可用区运营/运维内部工具平台 — M1 资源查询统一接口",
        lifespan=lifespan,
    )

    # 内部工具，CORS 全开（部署在内网）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 健康检查 ──
    @app.get("/health", tags=["meta"], summary="健康检查")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "tez-operator", "version": "0.1.0"}

    @app.get("/", tags=["meta"], include_in_schema=False)
    def root() -> dict[str, str]:
        return {"message": "TEZ Operator API. See /docs for OpenAPI."}

    # ── 业务路由 ──
    app.include_router(hosts_router.router, prefix="/api/v1")
    app.include_router(hosts_router.zone_router, prefix="/api/v1")

    return app


app = create_app()
