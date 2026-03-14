"""
TimeAnomalyDetector 单元测试
测试时间异常检测器的功能。
"""
from datetime import date, datetime

import pandas as pd
import pytest

from detectors.time_anomaly_detector import TimeAnomalyDetector
from detectors.base_detector import BaseDetector
from schemas.suspicion import Suspicion, SuspicionType


class TestTimeAnomalyDetector:
    """TimeAnomalyDetector 测试套件"""

    def test_detector_inherits_base_detector(self):
        """测试检测器继承自 BaseDetector"""
        detector = TimeAnomalyDetector()
        assert isinstance(detector, BaseDetector)

    def test_detector_name_property(self):
        """测试 name 属性返回正确值"""
        detector = TimeAnomalyDetector()
        assert detector.name == "time_anomaly"

    def test_detector_description_property(self):
        """测试 description 属性返回正确值"""
        detector = TimeAnomalyDetector()
        assert "时间" in detector.description
        assert "异常" in detector.description

    def test_detector_risk_level_property(self):
        """测试 risk_level 属性返回正确值"""
        detector = TimeAnomalyDetector()
        assert detector.risk_level in ["高", "中", "低", "high", "medium", "low"]

    def test_detector_enabled_property(self):
        """测试 enabled 属性默认为 True"""
        detector = TimeAnomalyDetector()
        assert detector.enabled is True

    def test_detect_returns_list(self):
        """测试 detect 方法返回列表"""
        detector = TimeAnomalyDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert isinstance(result, list)

    def test_detect_with_no_transactions(self):
        """测试无交易数据时返回空列表"""
        detector = TimeAnomalyDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert result == []

    def test_detect_with_off_hours_transactions(self):
        """测试检测到非工作时段交易"""
        detector = TimeAnomalyDetector()
        data = {
            "entity_name": "测试实体",
            "transactions": [
                {"tx_date": "2024-01-01 23:30:00", "amount": 60000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02 02:15:00", "amount": 55000.0, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-03 04:00:00", "amount": 70000.0, "tx_type": "收入", "counterparty": "C"},
            ]
        }
        config = {"min_amount": 50000}
        result = detector.detect(data, config)
        
        assert len(result) > 0
        assert isinstance(result[0], dict)
        assert "suspicion_id" in result[0]
        assert result[0]["suspicion_type"] == SuspicionType.UNUSUAL_TIME.value

    def test_detect_with_weekend_transactions(self):
        """测试检测到周末大额交易"""
        detector = TimeAnomalyDetector()
        # 2024-01-06 是周六
        data = {
            "entity_name": "周末测试实体",
            "transactions": [
                {"tx_date": "2024-01-06", "amount": 100000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-07", "amount": 80000.0, "tx_type": "收入", "counterparty": "B"},
            ]
        }
        config = {"weekend_threshold": 50000, "min_amount": 50000}
        result = detector.detect(data, config)
        
        # 应该检测到周末交易
        assert len(result) >= 1

    def test_detect_with_holiday_transactions(self):
        """测试检测到节假日大额交易"""
        detector = TimeAnomalyDetector()
        # 2024-02-10 是春节期间
        data = {
            "entity_name": "节假日测试实体",
            "transactions": [
                {"tx_date": "2024-02-10", "amount": 100000.0, "tx_type": "收入", "counterparty": "A"},
            ]
        }
        config = {"holiday_threshold": 50000, "min_amount": 50000}
        result = detector.detect(data, config)
        
        # 应该检测到节假日交易
        assert len(result) >= 1

    def test_detect_supports_cleaned_data_input(self):
        """测试检测器兼容 SuspicionEngine 的 cleaned_data 输入结构"""
        detector = TimeAnomalyDetector()
        data = {
            "cleaned_data": {
                "引擎测试实体": pd.DataFrame(
                    [
                        {
                            "date": "2024-02-10 23:30:00",
                            "income": 120000.0,
                            "expense": 0.0,
                            "counterparty": "A",
                            "description": "春节夜间交易",
                        }
                    ]
                )
            }
        }
        result = detector.detect(data, {"min_amount": 50000})

        assert len(result) >= 1
        assert any(item["entity_name"] == "引擎测试实体" for item in result)

    def test_detect_returns_valid_suspicion_data(self):
        """测试返回的数据可以通过 Suspicion 模型验证"""
        detector = TimeAnomalyDetector()
        data = {
            "entity_name": "验证实体",
            "transactions": [
                {"tx_date": "2024-01-01 23:00:00", "amount": 60000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02 01:00:00", "amount": 70000.0, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-03 03:00:00", "amount": 80000.0, "tx_type": "收入", "counterparty": "C"},
            ]
        }
        config = {"min_amount": 50000}
        result = detector.detect(data, config)
        
        if result:
            for item in result:
                suspicion = Suspicion(**item)
                assert suspicion.suspicion_id.startswith("TA")
                assert suspicion.entity_name == "验证实体"
                assert suspicion.amount >= 0
                assert 0 <= suspicion.confidence <= 1

    def test_detect_with_normal_hours(self):
        """测试正常时段交易不触发检测"""
        detector = TimeAnomalyDetector()
        # 使用非节假日的日期 (2024-01-15 是周一)
        data = {
            "entity_name": "正常时段实体",
            "transactions": [
                {"tx_date": "2024-01-15 10:00:00", "amount": 60000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-16 14:00:00", "amount": 55000.0, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-17 16:00:00", "amount": 70000.0, "tx_type": "收入", "counterparty": "C"},
            ]
        }
        config = {"min_amount": 50000}
        result = detector.detect(data, config)
        
        # 正常时段且非节假日/周末不应检测到时间异常
        assert len(result) == 0

    def test_detect_with_low_amount(self):
        """测试小额非工作时段交易不触发检测"""
        detector = TimeAnomalyDetector()
        data = {
            "entity_name": "小额测试实体",
            "transactions": [
                {"tx_date": "2024-01-01 23:30:00", "amount": 1000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02 02:15:00", "amount": 2000.0, "tx_type": "收入", "counterparty": "B"},
            ]
        }
        config = {"min_amount": 5000}
        result = detector.detect(data, config)
        
        # 小额交易不应触发检测
        assert len(result) == 0
