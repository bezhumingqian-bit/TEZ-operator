"""pytest 共享 fixture 和工具函数。

消除各测试文件中重复的 _fake_host()、_make_service()、settings cache clear 等样板代码。
"""

from __future__ import annotations

import pytest

from app.schemas.host import HostInfo


# ─── 通用 fixture ───

@pytest.fixture
def clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """自动清除 settings lru_cache 的 fixture。

    用法：在需要修改环境变量的测试函数参数中声明 ``clear_settings_cache``，
    pytest 会自动在测试前后执行 cache_clear。
    """
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _fast_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """自动缩短所有浏览器测试中的 sleep 时间，加速测试执行。

    对 ``asyncio.sleep`` 做 monkeypatch，把大于 1 秒的 sleep 压缩到 0.01 秒。
    """
    import asyncio

    _orig_sleep = asyncio.sleep

    async def _fast_sleep(delay: float, *args, **kwargs) -> None:
        if delay > 1:
            delay = 0.01
        return await _orig_sleep(delay, *args, **kwargs)

    monkeypatch.setattr(asyncio, "sleep", _fast_sleep)


# ─── 假数据工厂 ───

def fake_host(
    asset_id: str = "TYSV00000001",
    ip: str = "10.0.0.1",
    zone: str = "zone_a",
    status: str = "online",
    module: str = "腾讯云边缘可用区-zone_a",
) -> HostInfo:
    """构造一个 HostInfo 假数据，用于测试。"""
    return HostInfo(
        asset_id=asset_id,
        ip=ip,
        zone=zone,
        status=status,  # type: ignore[arg-type]
        module=module,
        machine_type="S5",
        idc="idc_a",
        cabinet="A01",
        customer="customer_a",
        app_id="app_001",
        owner="alice",
        backup_owner="bob",
        create_time="2024-01-01",
        history=[],
    )


# ─── Service 工厂 ───

def make_host_service(
    *,
    cmdb_mode: str = "mock",
    tcum_mode: str = "mock",
    idcrm_mode: str = "mock",
) -> "HostService":
    """构造一个指定模式的 HostService 实例，用于单元测试。

    注意：调用前若修改了环境变量，需先 ``clear_settings_cache``。
    """
    from app.services.host_service import HostService

    return HostService(
        cmdb_mode=cmdb_mode,  # type: ignore[arg-type]
        tcum_mode=tcum_mode,  # type: ignore[arg-type]
        idcrm_mode=idcrm_mode,  # type: ignore[arg-type]
    )
