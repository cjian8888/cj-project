"""
FrequencyAnomalyDetector 单元测试
测试频率异常检测器的功能。
"""
from datetime import date

import pytest

from detectors.frequency_anomaly_detector import FrequencyAnomalyDetector
from detectors.base_detector import BaseDetector
from schemas.suspicion import Suspicion, SuspicionType


class TestFrequencyAnomalyDetector:
    """FrequencyAnomalyDetector 测试套件"""

    def test_detector_inherits_base_detector(self):
        """测试检测器继承自 BaseDetector"""
        detector = FrequencyAnomalyDetector()
        assert isinstance(detector, BaseDetector)

    def test_detector_name_property(self):
        """测试 name 属性返回正确值"""
        detector = FrequencyAnomalyDetector()
        assert detector.name == "frequency_anomaly"

    def test_detector_description_property(self):
        """测试 description 属性返回正确值"""
        detector = FrequencyAnomalyDetector()
        assert "频率" in detector.description
        assert "异常" in detector.description

    def test_detector_risk_level_property(self):
        """测试 risk_level 属性返回正确值"""
        detector = FrequencyAnomalyDetector()
        assert detector.risk_level in ["高", "中", "低", "high", "medium", "low"]

    def test_detector_enabled_property(self):
        """测试 enabled 属性默认为 True"""
        detector = FrequencyAnomalyDetector()
        assert detector.enabled is True

    def test_detect_returns_list(self):
        """测试 detect 方法返回列表"""
        detector = FrequencyAnomalyDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert isinstance(result, list)

    def test_detect_with_no_transactions(self):
        """测试无交易数据时返回空列表"""
        detector = FrequencyAnomalyDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert result == []

    def test_detect_with_daily_high_frequency(self):
        """测试检测到单日高频交易"""
        detector = FrequencyAnomalyDetector()
        data = {
            "entity_name": "测试实体",
            "transactions": [
                {"tx_date": "2024-01-01 10:00:00", "amount": 10000.0, "tx_type": "收入", "counterparty": f"A{i}"}
                for i in range(15)
            ]
        }
        config = {"daily_threshold": 10, "min_amount": 5000}
        result = detector.detect(data, config)
        
        assert len(result) > 0
        assert isinstance(result[0], dict)
        assert "suspicion_id" in result[0]
        assert result[0]["suspicion_type"] == SuspicionType.FREQUENT_TRANSFER.value

    def test_detect_with_hourly_high_frequency(self):
        """测试检测到单小时高频交易"""
        detector = FrequencyAnomalyDetector()
        data = {
            "entity_name": "小时测试实体",
            "transactions": [
                {"tx_date": f"2024-01-01 10:{i:02d}:00", "amount": 10000.0, "tx_type": "收入", "counterparty": f"A{i}"}
                for i in range(10)
            ]
        }
        config = {"hourly_threshold": 5, "min_amount": 5000}
        result = detector.detect(data, config)
        
        # 应该检测到单小时高频
        hourly_results = [r for r in result if "单小时" in r["description"]]
        assert len(hourly_results) > 0

    def test_detect_returns_valid_suspicion_data(self):
        """测试返回的数据可以通过 Suspicion 模型验证"""
        detector = FrequencyAnomalyDetector()
        data = {
            "entity_name": "验证实体",
            "transactions": [
                {"tx_date": "2024-01-01 10:00:00", "amount": 10000.0, "tx_type": "收入", "counterparty": f"A{i}"}
                for i in range(20)
            ]
        }
        config = {"daily_threshold": 10, "min_amount": 5000}
        result = detector.detect(data, config)
        
        if result:
            for item in result:
                suspicion = Suspicion(**item)
                assert suspicion.suspicion_id.startswith("FR")
                assert suspicion.entity_name == "验证实体"
                assert suspicion.amount >= 0
                assert 0 <= suspicion.confidence <= 1

    def test_detect_with_low_frequency(self):
        """测试低频交易不触发检测"""
        detector = FrequencyAnomalyDetector()
        data = {
            "entity_name": "低频实体",
            "transactions": [
                {"tx_date": f"2024-01-{i+1:02d} 10:00:00", "amount": 10000.0, "tx_type": "收入", "counterparty": "A"}
                for i in range(5)
            ]
        }
        config = {"daily_threshold": 10, "min_amount": 5000}
        result = detector.detect(data, config)
        
        # 低频交易不应触发检测
        assert len(result) == 0

    def test_detect_with_low_amount(self):
        """测试小额高频交易不触发检测"""
        detector = FrequencyAnomalyDetector()
        data = {
            "entity_name": "小额高频实体",
            "transactions": [
                {"tx_date": "2024-01-01 10:00:00", "amount": 100.0, "tx_type": "收入", "counterparty": f"A{i}"}
                for i in range(20)
            ]
        }
        config = {"daily_threshold": 10, "min_amount": 5000}
        result = detector.detect(data, config)
        
        # 小额交易不应触发检测
        assert len(result) == 0

    def test_detect_with_sliding_window(self):
        """测试滑动窗口高频检测"""
        detector = FrequencyAnomalyDetector()
        # 在24小时窗口内有大量交易
        data = {
            "entity_name": "窗口测试实体",
            "transactions": [
                {"tx_date": f"2024-01-01 {i//2:02d}:{(i%2)*30:02d}:00", "amount": 20000.0, "tx_type": "收入", "counterparty": f"A{i}"}
                for i in range(20)
            ]
        }
        config = {"window_tx_threshold": 15, "window_hours": 24, "min_amount": 10000}
        result = detector.detect(data, config)
        
        # 应该检测到滑动窗口高频
        assert len(result) >= 1
