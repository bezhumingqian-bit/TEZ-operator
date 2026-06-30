"""可观测性模块：API 访问日志 + 浏览器抓取审计。

提供两个核心能力：
1. APIAccessLogger — 记录每次 API 请求的完整链路
2. BrowserAuditLogger — 记录每次 Playwright 访问外部平台的截图和结果

日志和截图统一存储在 data/observability/ 目录。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.utils.logger import get_logger

log = get_logger(__name__)

# 存储根目录
_OBS_DIR = Path("data/observability")
_API_LOG_DIR = _OBS_DIR / "api_logs"
_BROWSER_DIR = _OBS_DIR / "browser_audit"
_SCREENSHOTS_DIR = _BROWSER_DIR / "screenshots"


def _ensure_dirs() -> None:
    for d in (_API_LOG_DIR, _BROWSER_DIR, _SCREENSHOTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


_ensure_dirs()


# ════════════════════════════════════════════════════════════════
# 1. API 访问日志
# ════════════════════════════════════════════════════════════════

class APIAccessLogger:
    """记录每次 API 请求的完整链路，输出到结构化 JSON 日志。

    用法（FastAPI middleware 中）:
        logger = APIAccessLogger()
        await logger.log_request(request, response, duration_ms)
    """

    def __init__(self) -> None:
        _ensure_dirs()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._file = _API_LOG_DIR / f"access_{today}.jsonl"

    async def log_request(
        self,
        *,
        method: str = "",
        path: str = "",
        status_code: int = 0,
        duration_ms: float = 0,
        client_ip: str = "",
        user_agent: str = "",
        error: str = "",
    ) -> None:
        """记录一条 API 访问日志（JSONL 格式）。"""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "path": path,
            "status": status_code,
            "duration_ms": round(duration_ms, 1),
            "client_ip": client_ip,
            "user_agent": user_agent[:200] if user_agent else "",
            "os": _parse_os(user_agent),
            "error": error[:500] if error else "",
        }

        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            log.warning("api_access_log.write_failed", error=str(exc))

        # 慢请求告警
        if duration_ms > 10000:
            log.warning("api_access.slow_request", method=method, path=path,
                        duration_ms=round(duration_ms, 1), status=status_code)
        elif duration_ms > 3000:
            log.info("api_access.slow_request", method=method, path=path,
                     duration_ms=round(duration_ms, 1), status=status_code)

        # 错误请求告警
        if status_code >= 500:
            log.error("api_access.server_error", method=method, path=path,
                      status=status_code, error=error[:200])
        elif status_code >= 400:
            log.warning("api_access.client_error", method=method, path=path,
                        status=status_code)


# ════════════════════════════════════════════════════════════════
# 2. 浏览器抓取审计
# ════════════════════════════════════════════════════════════════

class BrowserAuditLogger:
    """记录每次 Playwright 访问外部平台的完整过程。

    每次访问自动：
    - 记录目标 URL、平台名、操作类型
    - 截图（访问后页面）
    - 记录是否成功、耗时、行数
    - 失败时记录异常信息和额外截图

    用法:
        audit = BrowserAuditLogger(platform="tcum", operation="search")
        audit.mark_start()
        try:
            ...  # Playwright 操作
            audit.mark_success(rows=50, screenshot=page)
        except Exception as e:
            audit.mark_failure(error=str(e), screenshot=page)
    """

    def __init__(self, platform: str, operation: str) -> None:
        _ensure_dirs()
        self.platform = platform
        self.operation = operation
        self._start_ts: float | None = None
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + f"_{platform}_{operation}"

    def mark_start(self) -> None:
        """标记操作开始。"""
        self._start_ts = time.time()
        log.info(
            "browser_audit.start",
            platform=self.platform,
            operation=self.operation,
            session=self._session_id,
        )

    def mark_success(self, *, rows: int = 0, screenshot=None) -> None:
        """标记操作成功。"""
        duration_ms = (time.time() - (self._start_ts or time.time())) * 1000
        self._take_screenshot(screenshot, suffix="success")
        self._write_record("success", duration_ms=duration_ms, rows=rows)
        log.info(
            "browser_audit.success",
            platform=self.platform,
            operation=self.operation,
            session=self._session_id,
            duration_ms=round(duration_ms),
            rows=rows,
        )

    def mark_failure(self, *, error: str = "", screenshot=None) -> None:
        """标记操作失败。"""
        duration_ms = (time.time() - (self._start_ts or time.time())) * 1000
        self._take_screenshot(screenshot, suffix="error")
        self._write_record("failure", duration_ms=duration_ms, error=error)
        log.warning(
            "browser_audit.failure",
            platform=self.platform,
            operation=self.operation,
            session=self._session_id,
            duration_ms=round(duration_ms),
            error=error[:200],
        )

    def mark_login_required(self, *, screenshot=None) -> None:
        """标记需要登录。"""
        self._take_screenshot(screenshot, suffix="login_required")
        self._write_record("login_required", duration_ms=0)
        log.warning(
            "browser_audit.login_required",
            platform=self.platform,
            operation=self.operation,
            session=self._session_id,
        )

    def _take_screenshot(self, page, *, suffix: str) -> str | None:
        """保存截图，返回文件路径。"""
        if page is None:
            return None
        try:
            filename = f"{self._session_id}_{suffix}.png"
            filepath = _SCREENSHOTS_DIR / filename
            import asyncio
            # page.screenshot 是 async，需要事件循环
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(page.screenshot(path=str(filepath), full_page=False))
            except RuntimeError:
                # 没有运行中的事件循环，同步方式
                import asyncio as _asyncio
                _asyncio.run(page.screenshot(path=str(filepath), full_page=False))
            return str(filepath)
        except Exception as exc:
            log.debug("browser_audit.screenshot_failed", error=str(exc))
            return None

    def _write_record(
        self, status: str, *, duration_ms: float = 0, rows: int = 0, error: str = ""
    ) -> None:
        """写入审计记录到 JSONL 文件。"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filepath = _BROWSER_DIR / f"audit_{today}.jsonl"
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": self._session_id,
            "platform": self.platform,
            "operation": self.operation,
            "status": status,
            "duration_ms": round(duration_ms, 1),
            "rows": rows,
            "error": error[:500] if error else "",
        }
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            log.warning("browser_audit.write_failed", error=str(exc))


# ════════════════════════════════════════════════════════════════
# 3. 查询接口（供前端看板展示）
# ════════════════════════════════════════════════════════════════

def get_today_api_logs(limit: int = 200) -> list[dict]:
    """获取今天的 API 访问日志（最近的 N 条）。"""
    _ensure_dirs()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = _API_LOG_DIR / f"access_{today}.jsonl"
    if not filepath.exists():
        return []
    entries = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries[-limit:]


def get_today_browser_audit(limit: int = 200) -> list[dict]:
    """获取今天的浏览器抓取审计记录。"""
    _ensure_dirs()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = _BROWSER_DIR / f"audit_{today}.jsonl"
    if not filepath.exists():
        return []
    entries = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries[-limit:]


def get_recent_screenshots(limit: int = 50) -> list[dict]:
    """获取最近的浏览器截图列表。"""
    _ensure_dirs()
    files = sorted(_SCREENSHOTS_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "filename": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "ts": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        for f in files[:limit]
    ]


def get_observability_summary() -> dict:
    """获取可观测性概览（API + 浏览器审计统计）。"""
    api_logs = get_today_api_logs(limit=1000)
    browser_audit = get_today_browser_audit(limit=1000)

    # API 统计
    total_api = len(api_logs)
    api_errors = sum(1 for e in api_logs if e.get("status", 0) >= 400)
    api_slow = sum(1 for e in api_logs if e.get("duration_ms", 0) > 3000)
    api_avg_duration = sum(e.get("duration_ms", 0) for e in api_logs) / max(total_api, 1)

    # 浏览器统计
    total_browser = len(browser_audit)
    browser_failures = sum(1 for e in browser_audit if e.get("status") == "failure")
    browser_success = sum(1 for e in browser_audit if e.get("status") == "success")
    browser_login = sum(1 for e in browser_audit if e.get("status") == "login_required")

    # 操作系统分布
    os_distribution: dict[str, int] = {}
    for e in api_logs:
        os_name = e.get("os", "unknown")
        os_distribution[os_name] = os_distribution.get(os_name, 0) + 1

    return {
        "api": {
            "total_requests": total_api,
            "errors_4xx_5xx": api_errors,
            "slow_requests_gt3s": api_slow,
            "avg_duration_ms": round(api_avg_duration, 1),
        },
        "browser": {
            "total_operations": total_browser,
            "success": browser_success,
            "failures": browser_failures,
            "login_required": browser_login,
            "success_rate": round(browser_success / max(total_browser, 1) * 100, 1),
        },
        "os_distribution": os_distribution,
    }


# ════════════════════════════════════════════════════════════════
# 4. 工具函数
# ════════════════════════════════════════════════════════════════

def _parse_os(user_agent: str) -> str:
    """从 User-Agent 中解析操作系统类型。

    Returns:
        "Windows", "macOS", "Linux", "Android", "iOS", 或 "unknown"
    """
    if not user_agent:
        return "unknown"
    ua = user_agent
    if "Windows NT" in ua:
        return "Windows"
    if "Mac OS X" in ua or "macOS" in ua or "Macintosh" in ua:
        return "macOS"
    if "Linux" in ua and "Android" not in ua:
        return "Linux"
    if "Android" in ua:
        return "Android"
    if "iPhone" in ua or "iPad" in ua or "iOS" in ua:
        return "iOS"
    return "unknown"
