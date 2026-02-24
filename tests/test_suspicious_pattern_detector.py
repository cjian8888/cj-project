"""
SuspiciousPatternDetector 单元测试
测试可疑模式检测器的功能。
"""
from datetime import date

import pytest

from detectors.suspicious_pattern_detector import SuspiciousPatternDetector
from detectors.base_detector import BaseDetector
from schemas.suspicion import Suspicion, SuspicionType


class TestSuspiciousPatternDetector:
    """SuspiciousPatternDetector 测试套件"""

    def test_detector_inherits_base_detector(self):
        """测试检测器继承自 BaseDetector"""
        detector = SuspiciousPatternDetector()
        assert isinstance(detector, BaseDetector)

    def test_detector_name_property(self):
        """测试 name 属性返回正确值"""
        detector = SuspiciousPatternDetector()
        assert detector.name == "suspicious_pattern"

    def test_detector_description_property(self):
        """测试 description 属性返回正确值"""
        detector = SuspiciousPatternDetector()
        assert "可疑" in detector.description or "模式" in detector.description

    def test_detector_risk_level_property(self):
        """测试 risk_level 属性返回正确值"""
        detector = SuspiciousPatternDetector()
        assert detector.risk_level in ["高", "中", "低", "high", "medium", "low"]

    def test_detector_enabled_property(self):
        """测试 enabled 属性默认为 True"""
        detector = SuspiciousPatternDetector()
        assert detector.enabled is True

    def test_detect_returns_list(self):
        """测试 detect 方法返回列表"""
        detector = SuspiciousPatternDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert isinstance(result, list)

    def test_detect_with_no_transactions(self):
        """测试无交易数据时返回空列表"""
        detector = SuspiciousPatternDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert result == []

    def test_detect_with_scatter_gather_pattern(self):
        """测试检测到分散转入集中转出模式"""
        detector = SuspiciousPatternDetector()
        data = {
            "entity_name": "测试实体",
            "transactions": [
                # 分散转入
                {"tx_date": "2024-01-01", "amount": 60000.0, "tx_type": "收入", "counterparty": "A", "account": "123"},
                {"tx_date": "2024-01-01", "amount": 70000.0, "tx_type": "收入", "counterparty": "B", "account": "123"},
                {"tx_date": "2024-01-01", "amount": 80000.0, "tx_type": "收入", "counterparty": "C", "account": "123"},
                # 集中转出
                {"tx_date": "2024-01-02", "amount": -200000.0, "tx_type": "支出", "counterparty": "D", "account": "123"},
            ]
        }
        config = {"min_inflow_sources": 3, "min_amount": 50000}
        result = detector.detect(data, config)
        
        # 应该检测到分散转入集中转出模式
        scatter_results = [r for r in result if "分散转入" in r["description"]]
        assert len(scatter_results) >= 1

    def test_detect_with_gather_scatter_pattern(self):
        """测试检测到集中转入分散转出模式"""
        detector = SuspiciousPatternDetector()
        data = {
            "entity_name": "拆分测试实体",
            "transactions": [
                # 集中转入
                {"tx_date": "2024-01-01", "amount": 300000.0, "tx_type": "收入", "counterparty": "A", "account": "123"},
                # 分散转出
                {"tx_date": "2024-01-02", "amount": -60000.0, "tx_type": "支出", "counterparty": "B", "account": "123"},
                {"tx_date": "2024-01-02", "amount": -70000.0, "tx_type": "支出", "counterparty": "C", "account": "123"},
                {"tx_date": "2024-01-02", "amount": -80000.0, "tx_type": "支出", "counterparty": "D", "account": "123"},
                {"tx_date": "2024-01-02", "amount": -90000.0, "tx_type": "支出", "counterparty": "E", "account": "123"},
            ]
        }
        config = {"min_outflow_targets": 3, "min_amount": 50000}
        result = detector.detect(data, config)
        
        # 应该检测到集中转入分散转出模式
        gather_results = [r for r in result if "集中转入" in r["description"]]
        assert len(gather_results) >= 1

    def test_detect_with_fast_in_out_pattern(self):
        """测试检测到快进快出模式"""
        detector = SuspiciousPatternDetector()
        data = {
            "entity_name": "快进快出实体",
            "transactions": [
                # 大额转入
                {"tx_date": "2024-01-01 10:00:00", "amount": 200000.0, "tx_type": "收入", "counterparty": "A", "account": "123"},
                # 短时间内转出
                {"tx_date": "2024-01-01 11:00:00", "amount": -100000.0, "tx_type": "支出", "counterparty": "B", "account": "123"},
                {"tx_date": "2024-01-01 12:00:00", "amount": -100000.0, "tx_type": "支出", "counterparty": "C", "account": "123"},
            ]
        }
        config = {"fast_in_out_hours": 24, "min_amount": 50000, "fast_in_out_ratio": 0.8}
        result = detector.detect(data, config)
        
        # 应该检测到快进快出模式
        fast_results = [r for r in result if "快进快出" in r["description"]]
        assert len(fast_results) >= 1

    def test_detect_returns_valid_suspicion_data(self):
        """测试返回的数据可以通过 Suspicion 模型验证"""
        detector = SuspiciousPatternDetector()
        data = {
            "entity_name": "验证实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 60000.0, "tx_type": "收入", "counterparty": f"A{i}", "account": "123"}
                for i in range(5)
            ] + [
                {"tx_date": "2024-01-02", "amount": -300000.0, "tx_type": "支出", "counterparty": "B", "account": "123"},
            ]
        }
        config = {"min_inflow_sources": 3, "min_amount": 50000}
        result = detector.detect(data, config)
        
        if result:
            for item in result:
                suspicion = Suspicion(**item)
                assert suspicion.suspicion_id.startswith("SP")
                assert suspicion.entity_name == "验证实体"
                assert suspicion.amount >= 0
                assert 0 <= suspicion.confidence <= 1

    def test_detect_with_normal_pattern(self):
        """测试正常模式不触发检测"""
        detector = SuspiciousPatternDetector()
        data = {
            "entity_name": "正常模式实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 50000.0, "tx_type": "收入", "counterparty": "A", "account": "123"},
                {"tx_date": "2024-01-15", "amount": 60000.0, "tx_type": "收入", "counterparty": "B", "account": "123"},
                {"tx_date": "2024-02-01", "amount": -100000.0, "tx_type": "支出", "counterparty": "C", "account": "123"},
            ]
        }
        config = {"min_inflow_sources": 3, "min_amount": 50000}
        result = detector.detect(data, config)
        
        # 正常模式不应触发检测
        assert len(result) == 0

    def test_detect_with_low_amount(self):
        """测试小额交易不触发检测"""
        detector = SuspiciousPatternDetector()
        data = {
            "entity_name": "小额测试实体",
            "transactions": [
                {"tx_date": "2024-01-01", "amount": 5000.0, "tx_type": "收入", "counterparty": f"A{i}", "account": "123"}
                for i in range(10)
            ]
        }
        config = {"min_inflow_sources": 3, "min_amount": 50000}
        result = detector.detect(data, config)
        
        # 小额交易不应触发检测
        assert len(result) == 0
