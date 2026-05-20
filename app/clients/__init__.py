"""外部系统客户端：CCDB / TCUM / 数全通（IDCRM）。

W2 起：每个客户端支持 ``mode = mock | api | browser`` 三态（参见 docs/14 § 二）。
- ``mock``    —— 默认；返回固定虚构数据，便于测试与本地无凭据联调
- ``api``     —— 走官方 OpenAPI（W2 占位）
- ``browser`` —— 走 Playwright 自动化（TCUM 已实现，CCDB / IDCRM 占位）
"""

from app.clients.base import (
    BaseHTTPClient,
    BrowserAuthExpired,
    ClientError,
    ClientMode,
)
from app.clients.browser_session import BrowserSession
from app.clients.ccdb import CCDBClient
from app.clients.idcrm import IDCRMClient
from app.clients.tcum import TCUMClient

__all__ = [
    "BaseHTTPClient",
    "BrowserAuthExpired",
    "BrowserSession",
    "CCDBClient",
    "ClientError",
    "ClientMode",
    "IDCRMClient",
    "TCUMClient",
]
