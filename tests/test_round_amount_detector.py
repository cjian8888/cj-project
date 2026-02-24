"""
RoundAmountDetector 单元测试
测试整数金额检测器的功能。
"""
from datetime import date

import pytest

from detectors.round_amount_detector import RoundAmountDetector
from detectors.base_detector import BaseDetector
from schemas.suspicion import Suspicion, SuspicionType


class TestRoundAmountDetector:
    """RoundAmountDetector 测试套件"""

    def test_detector_inherits_base_detector(self):
        """测试检测器继承自 BaseDetector"""
        detector = RoundAmountDetector()
        assert isinstance(detector, BaseDetector)

    def test_detector_name_property(self):
        """测试 name 属性返回正确值"""
        detector = RoundAmountDetector()
        assert detector.name == "round_amount"

    def test_detector_description_property(self):
        """测试 description 属性返回正确值"""
        detector = RoundAmountDetector()
        assert "整数" in detector.description or "金额" in detector.description

    def test_detector_risk_level_property(self):
        """测试 risk_level 属性返回正确值"""
        detector = RoundAmountDetector()
        assert detector.risk_level in ["高", "中", "低", "high", "medium", "low"]

    def test_detector_enabled_property(self):
        """测试 enabled 属性默认为 True"""
        detector = RoundAmountDetector()
        assert detector.enabled is True

    def test_detect_returns_list(self):
        """测试 detect 方法返回列表"""
        detector = RoundAmountDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert isinstance(result, list)

    def test_detect_with_no_transactions(self):
        """测试无交易数据时返回空列表"""
        detector = RoundAmountDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert result == []

    def test_detect_with_round_amount_pattern(self):
        """测试检测到整数金额模式"""
        detector = RoundAmountDetector()
        data = {
            "entity_name": "测试实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 10000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02", "amount": 20000.0, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-03", "amount": 30000.0, "tx_type": "收入", "counterparty": "C"},
                {"tx_date": "2024-01-04", "amount": 50000.0, "tx_type": "收入", "counterparty": "D"},
                {"tx_date": "2024-01-05", "amount": 100000.0, "tx_type": "收入", "counterparty": "E"},
                {"tx_date": "2024-01-06", "amount": 50000.0, "tx_type": "收入", "counterparty": "F"},
            ]
        }
        config = {"min_occurrences": 5, "min_amount": 10000}
        result = detector.detect(data, config)
        
        assert len(result) > 0
        assert isinstance(result[0], dict)
        assert "suspicion_id" in result[0]
        assert result[0]["suspicion_type"] == SuspicionType.ROUND_AMOUNT.value

    def test_detect_with_lucky_number_pattern(self):
        """测试检测到吉利数字金额模式"""
        detector = RoundAmountDetector()
        data = {
            "entity_name": "吉利数字实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 8888.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02", "amount": 6666.0, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-03", "amount": 16888.0, "tx_type": "收入", "counterparty": "C"},
                {"tx_date": "2024-01-04", "amount": 88888.0, "tx_type": "收入", "counterparty": "D"},
                {"tx_date": "2024-01-05", "amount": 66666.0, "tx_type": "收入", "counterparty": "E"},
            ]
        }
        config = {"min_occurrences": 5, "min_amount": 5000, "lucky_numbers": ['88', '66', '168']}
        result = detector.detect(data, config)
        
        # 应该检测到吉利数字模式
        assert len(result) >= 1

    def test_detect_returns_valid_suspicion_data(self):
        """测试返回的数据可以通过 Suspicion 模型验证"""
        detector = RoundAmountDetector()
        data = {
            "entity_name": "验证实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 10000.0 * i, "tx_type": "收入", "counterparty": f"A{i}"}
                for i in range(1, 8)
            ]
        }
        config = {"min_occurrences": 5, "min_amount": 10000}
        result = detector.detect(data, config)
        
        if result:
            for item in result:
                suspicion = Suspicion(**item)
                assert suspicion.suspicion_id.startswith("RA")
                assert suspicion.entity_name == "验证实体"
                assert suspicion.amount >= 0
                assert 0 <= suspicion.confidence <= 1

    def test_detect_with_non_round_amounts(self):
        """测试非整数金额不触发检测"""
        detector = RoundAmountDetector()
        data = {
            "entity_name": "非整数实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 12345.67, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02", "amount": 23456.78, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-03", "amount": 34567.89, "tx_type": "收入", "counterparty": "C"},
            ]
        }
        config = {"min_occurrences": 3, "min_amount": 10000}
        result = detector.detect(data, config)
        
        # 非整数金额不应触发检测
        assert len(result) == 0

    def test_detect_with_config_thresholds(self):
        """测试配置参数影响检测结果"""
        detector = RoundAmountDetector()
        data = {
            "entity_name": "阈值测试实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 10000.0, "tx_type": "收入", "counterparty": "A"},
                {"tx_date": "2024-01-02", "amount": 20000.0, "tx_type": "收入", "counterparty": "B"},
                {"tx_date": "2024-01-03", "amount": 30000.0, "tx_type": "收入", "counterparty": "C"},
            ]
        }
        # 设置较高的 min_occurrences
        config = {"min_occurrences": 5, "min_amount": 5000}
        result = detector.detect(data, config)
        
        # 只有3条记录，不满足min_occurrences=5
        assert len(result) == 0
