"""云霄平台 — 客户端工厂（三态分发：mock / browser / api）。"""

from __future__ import annotations

from app.clients.base import ClientMode
from app.clients.yunxiao_mock import mock_query_host_machines, mock_query_inventory
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class YunxiaoClient:
    """云霄平台客户端 — 按 mode 分发实现。

    mode 取值：
    - mock:   本地模拟数据
    - browser: Playwright DOM 自动化（legacy，headless 下不稳定）
    - api:     直接调云霄内部 CGI 接口（推荐，headless 稳定）
    """

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
        is_empty_host: bool = False,
        zones: list[str] | None = None,
        region: str | None = None,
    ) -> list[dict]:
        """查询母机管理页面的母机数据。"""
        if self._mode == "mock":
            rows = await mock_query_host_machines(zone, machine_type, instance_family)
            if is_empty_host:
                rows = [r for r in rows if str(r.get("is_empty_host") or "").strip() in ("是", "1", "true", "True")]
            return rows

        if self._mode == "api":
            from app.clients.yunxiao_api import YunxiaoApiClient
            impl = YunxiaoApiClient()
            try:
                return await impl.query_host_machines(
                    zone, zones=zones, region=region, machine_type=machine_type,
                    instance_family=instance_family, is_empty_host=is_empty_host,
                )
            finally:
                await impl.close()

        if self._mode == "browser":
            from app.clients.yunxiao_browser import YunxiaoBrowserImpl
            impl = YunxiaoBrowserImpl()
            try:
                return await impl.query_host_machines(
                    zone, zones=zones, region=region, machine_type=machine_type,
                    instance_family=instance_family, is_empty_host=is_empty_host,
                )
            finally:
                await impl.close()

        raise NotImplementedError(f"yunxiao mode={self._mode} 未实现")

    async def query_host_by_keyword(self, keyword: str) -> list[dict]:
        """按固资号 / IP 精确查单台母机。"""
        if self._mode == "mock":
            rows = await mock_query_host_machines(None, None, None)
            kw = (keyword or "").strip().upper()
            return [
                r for r in rows
                if kw in (r.get("asset_id") or "").upper() or kw in (r.get("ip") or "").upper()
            ]

        if self._mode == "api":
            from app.clients.yunxiao_api import YunxiaoApiClient
            impl = YunxiaoApiClient()
            try:
                return await impl.query_host_by_keyword(keyword)
            finally:
                await impl.close()

        if self._mode == "browser":
            from app.clients.yunxiao_browser import YunxiaoBrowserImpl
            impl = YunxiaoBrowserImpl()
            try:
                return await impl.query_host_by_keyword(keyword)
            finally:
                await impl.close()

        raise NotImplementedError(f"yunxiao mode={self._mode} 未实现")

    async def query_inventory(
        self,
        zone: str | None = None,
        instance_family: str | None = None,
        instance_type: str | None = None,
        zones: list[str] | None = None,
        region: str | None = None,
    ) -> list[dict]:
        """查询新机型库存页面数据。"""
        if self._mode == "mock":
            return await mock_query_inventory(zone, instance_family, instance_type)

        if self._mode == "api":
            from app.clients.yunxiao_api import YunxiaoApiClient
            impl = YunxiaoApiClient()
            try:
                return await impl.query_inventory(
                    zone, zones=zones, region=region,
                    instance_family=instance_family, instance_type=instance_type,
                )
            finally:
                await impl.close()

        if self._mode == "browser":
            from app.clients.yunxiao_browser import YunxiaoBrowserImpl
            impl = YunxiaoBrowserImpl()
            try:
                return await impl.query_inventory(
                    zone, zones=zones, region=region,
                    instance_family=instance_family, instance_type=instance_type,
                )
            finally:
                await impl.close()

        raise NotImplementedError(f"yunxiao mode={self._mode} 未实现")

    async def close(self) -> None:
        pass
