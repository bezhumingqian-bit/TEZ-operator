"""外部系统客户端：CCDB / TCUM / 数全通（IDCRM）。

每个客户端都支持 ``mock_mode``：W1 阶段账号未到位，统一返回真实感强的固定数据。
"""

from app.clients.base import BaseHTTPClient
from app.clients.ccdb import CCDBClient
from app.clients.idcrm import IDCRMClient
from app.clients.tcum import TCUMClient

__all__ = ["BaseHTTPClient", "CCDBClient", "TCUMClient", "IDCRMClient"]
