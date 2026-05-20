"""FastAPI 依赖注入。"""

from __future__ import annotations

from app.services.host_service import HostService

_host_service_singleton: HostService | None = None


def get_host_service() -> HostService:
    """单例 HostService（FastAPI Depends 使用）。"""

    global _host_service_singleton
    if _host_service_singleton is None:
        _host_service_singleton = HostService()
    return _host_service_singleton


def set_host_service(service: HostService | None) -> None:
    """测试用：覆盖单例。"""

    global _host_service_singleton
    _host_service_singleton = service
