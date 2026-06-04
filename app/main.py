"""FastAPI 应用入口。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.clients.browser_session import BrowserSession
from app.config import get_settings
from app.deps import get_host_service
from app.routers import hosts as hosts_router
from app.routers import contacts as contacts_router
from app.routers import knowledge as knowledge_router
from app.routers import workorders as workorders_router
from app.services.cache_service import cache as default_cache
from app.utils.logger import get_logger, setup_logging

settings = get_settings()
setup_logging(level=settings.app_log_level)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """生命周期钩子：启动 / 关闭。

    W2 增强（reviewer 建议-5 / 9）：
    - 启动期 DB / Redis ping 自检（失败仅 warn，不阻断启动以方便本地无依赖跑）
    - 关闭期释放 httpx clients + Redis pool + Playwright BrowserContext
    """

    log.info(
        "app.startup",
        env=settings.app_env,
        debug=settings.app_debug,
        cmdb_mode=settings.cmdb_mode,
        tcum_mode=settings.tcum_mode,
        idcrm_mode=settings.idcrm_mode,
    )

    # ── 启动自检 ──
    await _ping_redis()
    await _ping_db()

    # 浏览器登录态预检（仅日志，不强制扫码）
    if settings.tcum_mode == "browser":
        if BrowserSession.is_login_valid():
            log.info("browser.login_state_ok")
        else:
            log.warning(
                "browser.login_state_missing_or_expired",
                hint="首次访问 TCUM 时会唤起浏览器，请扫码登录",
            )

    # ── 启动定时任务 ──
    from app.scheduler import start_scheduler, shutdown_scheduler
    start_scheduler()

    # ── 重试未完成的腾讯文档推送 ──
    try:
        from app.services.workorder_service import WorkOrderService
        pending = await WorkOrderService.retry_pending_pushes()
        if pending:
            log.info("startup.retrying_pushes", count=pending)
    except Exception as exc:
        log.warning("startup.retry_pushes_failed", error=str(exc))

    try:
        yield
    finally:
        log.info("app.shutdown")
        shutdown_scheduler()
        # 关闭三 client + cache + browser
        try:
            await get_host_service().close()
        except Exception as exc:  # noqa: BLE001
            log.warning("app.close_host_service_failed", error=str(exc))
        try:
            await default_cache.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("app.close_cache_failed", error=str(exc))
        try:
            await BrowserSession.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("app.close_browser_failed", error=str(exc))


async def _ping_redis() -> None:
    """启动期 Redis ping —— 失败仅 warn 不阻断启动（cache 内部有 in-memory 降级）。"""
    try:
        await default_cache.set("startup_check", "ok", ttl=10)
        v = await default_cache.get("startup_check")
        if v == "ok":
            log.info("startup.redis_ok")
        else:
            log.warning("startup.redis_check_unexpected", got=v)
    except Exception as exc:  # noqa: BLE001
        log.warning("startup.redis_ping_failed", error=str(exc))


async def _ping_db() -> None:
    """启动期 DB ping —— 失败仅 warn 不阻断启动（W1 全 mock，W2 才真正用到 DB）。"""
    try:
        from sqlalchemy import create_engine, text

        # 用同步 engine 做一次性连接检查，避免引入 async sqlalchemy 依赖
        engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        log.info("startup.db_ok")
    except Exception as exc:  # noqa: BLE001
        log.warning("startup.db_ping_failed", error=str(exc))


def create_app() -> FastAPI:
    """工厂函数，便于测试 / 多实例。"""

    app = FastAPI(
        title="TEZ Operator API",
        version=__version__,
        description="腾讯云边缘可用区运营/运维内部工具平台",
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
        return {"status": "ok", "service": "tez-operator", "version": __version__}

    @app.get("/", tags=["meta"], include_in_schema=False)
    def root() -> dict[str, str]:
        return {"message": "TEZ Operator API. See /docs for OpenAPI."}

    # ── 业务路由 ──
    app.include_router(hosts_router.router, prefix="/api/v1")
    app.include_router(hosts_router.zone_router, prefix="/api/v1")
    app.include_router(contacts_router.router, prefix="/api/v1")
    app.include_router(knowledge_router.router, prefix="/api/v1")
    app.include_router(workorders_router.router, prefix="/api/v1")

    from app.routers import auth as auth_router
    app.include_router(auth_router.router)

    from app.routers import cost as cost_router
    app.include_router(cost_router.router)

    from app.routers import ai as ai_router
    app.include_router(ai_router.router)

    # ── 前端静态文件托管（SPA） ──
    import os
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    frontend_dist = Path(__file__).parent.parent / "web" / "dist"
    if frontend_dist.exists():
        # 静态资源（js/css/images）
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="static-assets")

        # SPA fallback：所有非 API 路径都返回 index.html，交给 Vue Router 处理
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            # 如果是具体的静态文件（如 favicon.ico），直接返回
            file_path = frontend_dist / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            # 否则返回 index.html，让 Vue Router 处理前端路由
            return FileResponse(str(frontend_dist / "index.html"))

    return app


app = create_app()
