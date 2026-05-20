"""统一 API 响应包络。"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一返回结构，保持与 11 文档示例一致。"""

    code: int = Field(default=0, description="0=成功，非 0=错误")
    message: str = Field(default="ok")
    data: T | None = Field(default=None)


class ErrorResponse(BaseModel):
    code: int = 1
    message: str
    detail: str | None = None
