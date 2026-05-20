"""structlog 日志初始化。"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def setup_logging(level: str = "INFO") -> None:
    """配置 structlog + 标准库 logging。

    输出 JSON 格式（生产）或 KeyValue（本地 debug），统一带时间戳和级别。
    """

    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        stream=sys.stdout,
    )

    # 本地开发用更易读的渲染器，其他环境用 JSON
    is_tty = sys.stdout.isatty()
    renderer: Any = (
        structlog.dev.ConsoleRenderer(colors=is_tty)
        if is_tty
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """便捷获取一个 BoundLogger。"""

    return structlog.get_logger(name)
