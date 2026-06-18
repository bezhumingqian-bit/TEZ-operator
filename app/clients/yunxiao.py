"""云霄平台 — 客户端工厂（三态分发）。"""

from __future__ import annotations

from app.clients.base import ClientMode
from app.clients.yunxiao_mock import mock_query_host_machines, mock_query_inventory
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class YunxiaoClient:
    """云霄平台客户端 — 按 mode 分发实现。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._mode: ClientMode = settings.yunxiao_mode
        log.info("yunxiao_client_init", mode=self._mode)

    @property
    def mode(self) -> ClientMode:
        return self._mode

    async def query_host_machines(
        self,
        zone: str | None = None,
        machine_type: str | None = None,
        instance_family: str | None = None,
    ) -> list[dict]:
        """查询母机管理页面的母机数据。"""
        if self._mode == "mock":
            return await mock_query_host_machines(zone, machine_type, instance_family)

        if self._mode == "browser":
            from app.clients.yunxiao_browser import YunxiaoBrowserImpl
            impl = YunxiaoBrowserImpl()
            try:
                return await impl.query_host_machines(zone, machine_type, instance_family)
            finally:
                await impl.close()

        raise NotImplementedError(f"yunxiao mode={self._mode} 未实现")

    async def query_inventory(
        self,
        zone: str | None = None,
        instance_family: str | None = None,
        instance_type: str | None = None,
    ) -> list[dict]:
        """查询新机型库存页面数据。"""
        if self._mode == "mock":
            return await mock_query_inventory(zone, instance_family, instance_type)

        if self._mode == "browser":
            from app.clients.yunxiao_browser import YunxiaoBrowserImpl
            impl = YunxiaoBrowserImpl()
            try:
                return await impl.query_inventory(zone, instance_family, instance_type)
            finally:
                await impl.close()

        raise NotImplementedError(f"yunxiao mode={self._mode} 未实现")

    async def close(self) -> None:
        pass
