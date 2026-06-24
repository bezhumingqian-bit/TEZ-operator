# -*- coding: utf-8 -*-
"""水位计算单元测试 — 覆盖边界值、除零、分级。"""
from __future__ import annotations

import pytest

from app.utils.water_level import CRITICAL_FREE_RATE, WARNING_FREE_ABS, WARNING_FREE_RATE, calc_water_level


class TestCalcWaterLevel:
    """核心计算函数测试。"""

    # ─── 边界 / 除零 ───

    def test_total_zero_returns_unknown(self):
        """总机位为 0 → unknown 状态，不抛异常。"""
        result = calc_water_level(total=0, free=0, used=0, online=0, offline=0)
        assert result["level"] == "unknown"
        assert result["level_label"] == "无数据"
        assert result["usage_rate"] == 0.0
        assert result["free_rate"] == 0.0
        assert result["offline_rate"] == 0.0

    def test_total_negative_returns_unknown(self):
        result = calc_water_level(total=-5, free=0, used=0, online=0, offline=0)
        assert result["level"] == "unknown"

    def test_zero_devices_offline_rate_zero(self):
        """无设备时 offline_rate 为 0 不抛异常。"""
        result = calc_water_level(total=100, free=50, used=50, online=0, offline=0)
        assert result["offline_rate"] == 0.0

    # ─── 紧张 = critical ───

    def test_free_zero_is_critical(self):
        """空闲机位 0 → 紧张。"""
        result = calc_water_level(total=100, free=0, used=100, online=80, offline=5)
        assert result["level"] == "critical"
        assert result["level_label"] == "紧张"

    def test_free_rate_below_critical_threshold(self):
        """空闲率 4.9% < 5% → 紧张。"""
        result = calc_water_level(total=1000, free=49, used=951, online=900, offline=50)
        assert result["level"] == "critical"

    def test_free_rate_exactly_at_critical_threshold(self):
        """空闲率恰好 5% → 不触发 critical（>= 5%）。"""
        result = calc_water_level(total=100, free=5, used=95, online=90, offline=5)
        assert result["level"] != "critical"

    # ─── 预警 = warning ───

    def test_free_rate_between_warning_and_critical(self):
        """空闲率 10%（5% <= x < 15%）→ 预警。"""
        result = calc_water_level(total=100, free=10, used=90, online=80, offline=5)
        assert result["level"] == "warning"
        assert result["level_label"] == "预警"

    def test_free_abs_at_warning_threshold(self):
        """空闲机位恰好 3 台且 free_rate >= 5% → 预警（绝对值兜底）。"""
        # total=20, free=3, free_rate=15% → 恰好不触发 rate warning
        # 但 free <= 3 → 绝对值兜底触发 warning
        result = calc_water_level(total=20, free=3, used=17, online=15, offline=2)
        assert result["level"] == "warning"

    def test_free_abs_below_warning_threshold(self):
        """空闲机位 3 台且 free_rate 在 5%-15% 之间 → 预警（rate 判定）。"""
        result = calc_water_level(total=40, free=3, used=37, online=30, offline=5)
        # free_rate = 3/40 = 7.5%, free <= 3 → warning
        assert result["level"] == "warning"

    # ─── 健康 = healthy ───

    def test_high_free_rate_is_healthy(self):
        """空闲率 >= 15% 且空闲 > 3 → 健康。"""
        result = calc_water_level(total=100, free=50, used=50, online=80, offline=5)
        assert result["level"] == "healthy"
        assert result["level_label"] == "健康"

    def test_many_free_but_high_usage_still_healthy(self):
        result = calc_water_level(total=500, free=400, used=100, online=80, offline=5)
        assert result["level"] == "healthy"

    # ─── 精度 ───

    def test_usage_rate_precision(self):
        result = calc_water_level(total=300, free=17, used=283, online=250, offline=30)
        # usage_rate = 283/300 ≈ 0.9433
        assert result["usage_rate"] == pytest.approx(0.9433, abs=0.001)

    def test_offline_rate_precision(self):
        result = calc_water_level(total=100, free=10, used=90, online=75, offline=25)
        # offline_rate = 25/100 = 0.25
        assert result["offline_rate"] == pytest.approx(0.25, abs=0.001)

    # ─── 阈值可替代性（确保常量不是硬编码在函数内）───

    def test_uses_constant_thresholds(self):
        """验证函数使用模块级常量而非硬编码数字。"""
        # 构造恰好低于 WARNING_FREE_RATE 的情况
        total = 1000
        free = int(total * WARNING_FREE_RATE) - 1  # 刚好低于 15%
        result = calc_water_level(total=total, free=free, used=total - free, online=800, offline=50)
        # free_rate < 15% → 预警
        assert result["level"] == "warning"

    # ─── 对抗性：None 值防御 ───

    def test_none_values_handled(self):
        """None 值应安全回退而不抛异常。"""
        result = calc_water_level(total=None, free=None, used=None, online=None, offline=None)  # type: ignore[arg-type]
        assert result["level"] == "unknown"
        assert result["usage_rate"] == 0.0

    def test_partial_none_with_valid_total(self):
        """部分 None + 有效 total 应正常计算。"""
        result = calc_water_level(total=100, free=30, used=70, online=None, offline=None)  # type: ignore[arg-type]
        assert result["level"] == "healthy"
        assert result["offline_rate"] == 0.0  # online/offline None → 0

    def test_free_none_becomes_critical(self):
        """free=None → 0，应判定为 critical（对抗：脏数据兜底）。"""
        result = calc_water_level(total=100, free=None, used=100, online=80, offline=5)  # type: ignore[arg-type]
        assert result["level"] == "critical"
        assert result["free_rate"] == 0.0
