"""
FixedAmountDetector 单元测试
测试固定金额检测器的功能。
"""
from datetime import date

import pytest

from detectors.fixed_amount_detector import FixedAmountDetector
from detectors.base_detector import BaseDetector
from schemas.suspicion import Suspicion, SuspicionType


class TestFixedAmountDetector:
    """FixedAmountDetector 测试套件"""

    def test_detector_inherits_base_detector(self):
        """测试检测器继承自 BaseDetector"""
        detector = FixedAmountDetector()
        assert isinstance(detector, BaseDetector)

    def test_detector_name_property(self):
        """测试 name 属性返回正确值"""
        detector = FixedAmountDetector()
        assert detector.name == "fixed_amount"

    def test_detector_description_property(self):
        """测试 description 属性返回正确值"""
        detector = FixedAmountDetector()
        assert "固定金额" in detector.description
        assert "检测" in detector.description

    def test_detector_risk_level_property(self):
        """测试 risk_level 属性返回正确值"""
        detector = FixedAmountDetector()
        assert detector.risk_level in ["高", "中", "低", "high", "medium", "low"]

    def test_detector_enabled_property(self):
        """测试 enabled 属性默认为 True"""
        detector = FixedAmountDetector()
        assert detector.enabled is True

    def test_detect_returns_list(self):
        """测试 detect 方法返回列表"""
        detector = FixedAmountDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert isinstance(result, list)

    def test_detect_with_no_transactions(self):
        """测试无交易数据时返回空列表"""
        detector = FixedAmountDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert result == []

    def test_detect_with_fixed_amount_pattern(self):
        """测试检测到固定金额模式"""
        detector = FixedAmountDetector()
        data = {
            "entity_name": "测试实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 50000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02", "amount": 50000.0, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-03", "amount": 50000.0, "tx_type": "收入", "counterparty": "C"},
                {"tx_date": "2024-01-04", "amount": 50000.0, "tx_type": "收入", "counterparty": "D"},
                {"tx_date": "2024-01-05", "amount": 50000.0, "tx_type": "收入", "counterparty": "E"},
            ]
        }
        config = {"min_occurrences": 3, "amount_threshold": 10000}
        result = detector.detect(data, config)
        
        assert len(result) > 0
        assert isinstance(result[0], dict)
        assert "suspicion_id" in result[0]
        assert result[0]["suspicion_type"] == SuspicionType.ROUND_AMOUNT.value
        assert "amount" in result[0]
        assert result[0]["amount"] >= 250000  # 50000 * 5

    def test_detect_returns_valid_suspicion_data(self):
        """测试返回的数据可以通过 Suspicion 模型验证"""
        detector = FixedAmountDetector()
        data = {
            "entity_name": "验证实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 10000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02", "amount": 10000.0, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-03", "amount": 10000.0, "tx_type": "收入", "counterparty": "C"},
                {"tx_date": "2024-01-04", "amount": 10000.0, "tx_type": "收入", "counterparty": "D"},
                {"tx_date": "2024-01-05", "amount": 10000.0, "tx_type": "收入", "counterparty": "E"},
                {"tx_date": "2024-01-06", "amount": 10000.0, "tx_type": "收入", "counterparty": "F"},
            ]
        }
        config = {"min_occurrences": 5}
        result = detector.detect(data, config)
        
        assert len(result) > 0
        for item in result:
            suspicion = Suspicion(**item)
            assert suspicion.suspicion_id.startswith("FA")
            assert suspicion.entity_name == "验证实体"
            assert suspicion.amount >= 0
            assert 0 <= suspicion.confidence <= 1

    def test_detect_with_irregular_amounts(self):
        """测试不规则金额不触发检测"""
        detector = FixedAmountDetector()
        data = {
            "entity_name": "不规则实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 12345.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02", "amount": 23456.0, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-03", "amount": 34567.0, "tx_type": "收入", "counterparty": "C"},
            ]
        }
        config = {"min_occurrences": 3}
        result = detector.detect(data, config)
        
        # 不同金额不应触发固定金额检测
        assert len(result) == 0

    def test_detect_with_config_thresholds(self):
        """测试配置参数影响检测结果"""
        detector = FixedAmountDetector()
        data = {
            "entity_name": "阈值测试实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 5000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02", "amount": 5000.0, "tx_type": "收入", "counterparty": "B"},
            ]
        }
        # 设置较高的 min_occurrences
        config = {"min_occurrences": 5, "amount_threshold": 1000}
        result = detector.detect(data, config)
        
        # 只有2条记录，不满足min_occurrences=5
        assert len(result) == 0

    def test_detect_with_expense_transactions(self):
        """测试支出交易也能被检测到"""
        detector = FixedAmountDetector()
        data = {
            "entity_name": "支出测试实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": -50000.0, "tx_type": "支出", "counterparty": "A"},
                {"tx_date": "2024-01-02", "amount": -50000.0, "tx_type": "支出", "counterparty": "B"},
                {"tx_date": "2024-01-03", "amount": -50000.0, "tx_type": "支出", "counterparty": "C"},
                {"tx_date": "2024-01-04", "amount": -50000.0, "tx_type": "支出", "counterparty": "D"},
                {"tx_date": "2024-01-05", "amount": -50000.0, "tx_type": "支出", "counterparty": "E"},
            ]
        }
        config = {"min_occurrences": 3}
        result = detector.detect(data, config)
        
        assert len(result) > 0
