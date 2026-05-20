"""parser 单测：覆盖 4 种类型 + 边界。"""

from __future__ import annotations

import pytest

from app.utils.parser import detect_query_type, normalize_query, split_batch_input


class TestDetectQueryType:
    @pytest.mark.parametrize(
        "value",
        [
            "TYSV00000001",
            "tysv20061x2a",  # 小写也能识别
            "TYSV00000002",
            "TYHA12345678",  # 其他 TY 开头型号
        ],
    )
    def test_asset_id(self, value: str) -> None:
        assert detect_query_type(value) == "asset_id"

    @pytest.mark.parametrize(
        "value",
        [
            "10.0.0.5",
            "10.0.0.1",
            "192.168.1.1",
            "255.255.255.255",
            "0.0.0.0",
        ],
    )
    def test_ip(self, value: str) -> None:
        assert detect_query_type(value) == "ip"

    @pytest.mark.parametrize(
        "value",
        [
            "ap-shanghai-tea-3",
            "ap-guangzhou-edgezone-1",
            "ap-beijing-tea-12",
        ],
    )
    def test_zone(self, value: str) -> None:
        assert detect_query_type(value) == "zone"

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "   ",
            "abc",
            "TY",  # 太短
            "256.256.256.256",  # 非法 IP
            "1.2.3",  # 不完整 IP
            "1.2.3.4.5",  # 多段
            "AP-Shanghai",  # 不是 zone 格式
            "TYSV",  # 长度不够（前缀+至少 4 位）
            None,  # type: ignore[arg-type]
        ],
    )
    def test_unknown(self, value: str | None) -> None:
        assert detect_query_type(value) == "unknown"

    def test_strip_whitespace(self) -> None:
        assert detect_query_type("  TYSV00000001  ") == "asset_id"
        assert detect_query_type("\tap-shanghai-tea-3\n") == "zone"


class TestNormalize:
    def test_asset_uppercase(self) -> None:
        assert normalize_query("tysv20061x2a") == "TYSV00000001"

    def test_zone_lowercase(self) -> None:
        assert normalize_query("AP-Shanghai-Tea-3") == "ap-shanghai-tea-3"

    def test_ip_unchanged(self) -> None:
        assert normalize_query(" 10.0.0.5 ") == "10.0.0.5"


class TestSplitBatch:
    def test_newline(self) -> None:
        raw = "TYSV00000001\nTYSV00000002\nTYSV00000003"
        out = split_batch_input(raw)
        assert out == ["TYSV00000001", "TYSV00000002", "TYSV00000003"]

    def test_mixed_separators(self) -> None:
        raw = "TYSV00000001; TYSV00000002, TYSV00000003\nTYSV00000001"
        out = split_batch_input(raw)
        # 去重保留顺序
        assert out == ["TYSV00000001", "TYSV00000002", "TYSV00000003"]

    def test_empty(self) -> None:
        assert split_batch_input("") == []
        assert split_batch_input("   \n  \n ") == []
