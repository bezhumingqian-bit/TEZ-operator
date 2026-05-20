"""应用配置。

使用 pydantic-settings 从环境变量 / .env 读取，所有变量统一前缀 ``TEZ_``。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # ───────── Mock 模式开关（W1 全开）─────────
    ccdb_mock_mode: bool = Field(default=True)
    tcum_mock_mode: bool = Field(default=True)
    idcrm_mock_mode: bool = Field(default=True)

    # ───────── CCDB（HTTP 客户端）─────────
    ccdb_base_url: str = Field(default="http://ccdb-host:8080")
    ccdb_token: str = Field(default="")
    ccdb_caller: str = Field(default="tez-operator")
    ccdb_timeout: float = Field(default=5.0)

    # CCDB 直查（DB，可选）
    ccdb_db_host: str = Field(default="")
    ccdb_db_port: int = Field(default=3306)
    ccdb_db_user: str = Field(default="")
    ccdb_db_password: str = Field(default="")
    ccdb_db_name: str = Field(default="CCDB4")

    # ───────── TCUM ─────────
    tcum_base_url: str = Field(default="http://tcum.example.com")
    tcum_token: str = Field(default="")
    tcum_timeout: float = Field(default=5.0)

    # ───────── 数全通（IDCRM）─────────
    idcrm_base_url: str = Field(default="http://idcrm.example.com")
    idcrm_token: str = Field(default="")
    idcrm_timeout: float = Field(default=5.0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取单例配置（带 lru_cache 便于覆盖测试）。"""

    return Settings()


# 兼容直接 import settings 的写法
settings = get_settings()
