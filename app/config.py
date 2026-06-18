"""应用配置。

使用 pydantic-settings 从环境变量 / .env 读取，所有变量统一前缀 ``TEZ_``。

W2 起：客户端引入三态 ``mode = mock | api | browser``（参见 docs/14 § 二）。
- ``mock``    —— 不发请求，由 Impl 返回固定假数据
- ``api``     —— 走官方 OpenAPI（W2 占位，等账号到位再实现）
- ``browser`` —— 走 Playwright 自动化（W2 实现，登录态在 ``data/playwright-profile``）
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 与 app.clients.base.ClientMode 保持一致，但在 config 里独立定义避免循环 import
ClientMode = Literal["mock", "api", "browser"]


class Settings(BaseSettings):
    """全局配置类。"""

    model_config = SettingsConfigDict(
        env_prefix="TEZ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ───────── 应用 ─────────
    app_env: str = Field(default="local", description="local/dev/staging/prod")
    app_debug: bool = Field(default=True)
    app_host: str = Field(default="0.0.0.0")  # noqa: S104 - 内网部署
    app_port: int = Field(default=8000)
    app_log_level: str = Field(default="INFO")

    # ───────── DB / Redis ─────────
    database_url: str = Field(
        default="sqlite+pysqlite:///./tez_operator.db",
        description="SQLAlchemy 连接串；生产用 mysql+pymysql://...",
    )
    redis_url: str = Field(default="redis://127.0.0.1:6379/0")
    cache_default_ttl: int = Field(default=300, description="单机详情缓存 TTL（秒）")
    cache_zone_ttl: int = Field(default=600, description="Zone 列表缓存 TTL（秒）")

    # ───────── 批量查询限流（W3 reviewer 建议）─────────
    batch_concurrency: int = Field(
        default=5,
        description="batch_search 内并发查询的最大数量，防止瞬间打开过多浏览器 tab",
    )
    batch_max_size: int = Field(
        default=100,
        description="单次 batch_search / export 接受的最大条数",
    )

    # ───────── 客户端三态模式（W2 起） ─────────
    cmdb_mode: ClientMode = Field(default="mock", description="cmdb 客户端模式")
    tcum_mode: ClientMode = Field(default="mock", description="tcum 客户端模式")
    idcrm_mode: ClientMode = Field(default="mock", description="idcrm 客户端模式")
    yunxiao_mode: ClientMode = Field(default="mock", description="yunxiao 客户端模式")

    # ───────── 浏览器自动化（mode=browser 时使用） ─────────
    browser_profile_dir: str = Field(
        default="data/playwright-profile",
        description="Playwright 持久化 profile 目录（已 .gitignore）",
    )
    browser_headless: bool = Field(
        default=False,
        description="iOA 鉴权要求可视化扫码，生产建议 false",
    )
    browser_login_valid_days: int = Field(
        default=7, description="Cookies 文件 mtime 在 N 天内视为登录态有效"
    )
    browser_page_timeout_ms: int = Field(default=30000, description="单页 goto 超时(ms)")
    browser_ignore_https_errors: bool = Field(
        default=False,
        description="是否忽略浏览器自动化中的 HTTPS 证书错误；仅内网自签证书场景显式开启",
    )

    # ───────── CMDB（HTTP 客户端）─────────
    cmdb_base_url: str = Field(default="http://cmdb.example.com")
    cmdb_token: str = Field(default="")
    cmdb_caller: str = Field(default="tez-operator")
    cmdb_timeout: float = Field(default=5.0)

    # CMDB 直查（DB，可选）
    cmdb_db_host: str = Field(default="")
    cmdb_db_port: int = Field(default=3306)
    cmdb_db_user: str = Field(default="")
    cmdb_db_password: str = Field(default="")
    cmdb_db_name: str = Field(default="CMDB4")

    # ───────── TCUM ─────────
    tcum_base_url: str = Field(default="http://tcum.example.com")
    tcum_token: str = Field(default="")
    tcum_timeout: float = Field(default=5.0)

    # ───────── 数全通（IDCRM）─────────
    idcrm_base_url: str = Field(default="http://idcrm.example.com")
    idcrm_token: str = Field(default="")
    idcrm_timeout: float = Field(default=5.0)

    # ───────── 告警（企微 webhook，空则只 log） ─────────
    wecom_webhook: str = Field(default="", description="企业微信群机器人 webhook URL，空则只打日志")

    # ───────── 认证 ─────────
    jwt_secret_key: str = Field(default="", description="JWT 签名密钥，生产环境必须设置强密钥")
    password_salt: str = Field(default="", description="密码哈希 salt，生产环境必须设置")

    # ───────── AI 助手 ─────────
    # 支持任何兼容 OpenAI Chat API 格式的模型（混元/DeepSeek/GPT/CodeBuddy等）
    ai_api_base: str = Field(default="", description="AI API base URL（如 https://api.hunyuan.cloud.tencent.com/v1）")
    ai_api_key: str = Field(default="", description="API Key 或 Bearer Token")
    ai_model: str = Field(default="hunyuan-lite", description="模型名称")
    ai_max_tokens: int = Field(default=2000, description="最大输出 token 数")

    # ───────── 腾讯文档（工单同步）─────────
    tencent_doc_url: str = Field(default="", description="OnePage 腾讯文档 URL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取单例配置（带 lru_cache 便于覆盖测试）。"""

    return Settings()


# 兼容直接 import settings 的写法
settings = get_settings()
