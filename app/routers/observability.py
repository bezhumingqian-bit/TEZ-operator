"""可观测性 API 路由。

提供 API 访问日志、浏览器抓取审计、截图等查询接口。
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.core.observability import (
    get_observability_summary,
    get_recent_screenshots,
    get_today_api_logs,
    get_today_browser_audit,
)

router = APIRouter(tags=["observability"])


@router.get("/api/v1/observability/summary", summary="可观测性概览")
async def observability_summary() -> dict:
    """API + 浏览器审计统计概览。"""
    return get_observability_summary()


@router.get("/api/v1/observability/api-logs", summary="API 访问日志")
async def api_logs(limit: int = Query(default=200, ge=1, le=1000)) -> list[dict]:
    """今天的 API 访问日志。"""
    return get_today_api_logs(limit=limit)


@router.get("/api/v1/observability/browser-audit", summary="浏览器抓取审计")
async def browser_audit(limit: int = Query(default=200, ge=1, le=1000)) -> list[dict]:
    """今天的浏览器抓取审计记录。"""
    return get_today_browser_audit(limit=limit)


@router.get("/api/v1/observability/screenshots", summary="浏览器截图列表")
async def screenshots(limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    """最近的浏览器截图列表。"""
    return get_recent_screenshots(limit=limit)


@router.get("/api/v1/observability/screenshots/{filename}", summary="查看截图")
async def screenshot_file(filename: str) -> FileResponse:
    """查看指定截图文件。"""
    from pathlib import Path

    filepath = Path("data/observability/browser_audit/screenshots") / filename
    if not filepath.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="截图不存在")

    return FileResponse(str(filepath), media_type="image/png")
