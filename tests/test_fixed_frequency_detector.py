"""
FixedFrequencyDetector 单元测试
测试固定频率异常检测器的功能。
"""
from datetime import date

import pytest
from pydantic import ValidationError

from detectors.fixed_frequency_detector import FixedFrequencyDetector
from schemas.suspicion import Suspicion, SuspicionSeverity, SuspicionType


class TestFixedFrequencyDetector:
    """FixedFrequencyDetector 测试套件"""

    def test_detector_inherits_base_detector(self):
        """测试检测器继承自 BaseDetector"""
        detector = FixedFrequencyDetector()
        from detectors.base_detector import BaseDetector
        assert isinstance(detector, BaseDetector)

    def test_detector_name_property(self):
        """测试 name 属性返回正确值"""
        detector = FixedFrequencyDetector()
        assert detector.name == "fixed_frequency"

    def test_detector_description_property(self):
        """测试 description 属性返回正确值"""
        detector = FixedFrequencyDetector()
        assert "频率" in detector.description
        assert "检测" in detector.description

    def test_detector_risk_level_property(self):
        """测试 risk_level 属性返回正确值"""
        detector = FixedFrequencyDetector()
        assert detector.risk_level in ["高", "中", "低", "high", "medium", "low"]

    def test_detector_enabled_property(self):
        """测试 enabled 属性默认为 True"""
        detector = FixedFrequencyDetector()
        assert detector.enabled is True

    def test_detect_returns_list(self):
        """测试 detect 方法返回列表"""
        detector = FixedFrequencyDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert isinstance(result, list)

    def test_detect_with_no_transactions(self):
        """测试无交易数据时返回空列表"""
        detector = FixedFrequencyDetector()
        data = {"transactions": []}
        config = {}
        result = detector.detect(data, config)
        assert result == []

    def test_detect_with_fixed_frequency_income(self):
        """测试检测到固定频率收入模式"""
        detector = FixedFrequencyDetector()
        data = {
            "entity_name": "测试实体",
            "transactions": [
                {
                    "tx_date": "2024-01-01",
                    "amount": 5000.0,
                    "tx_type": "收入",
                    "counterparty": "公司A",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-02-01",
                    "amount": 5000.0,
                    "tx_type": "收入",
                    "counterparty": "公司A",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-03-01",
                    "amount": 5000.0,
                    "tx_type": "收入",
                    "counterparty": "公司A",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                }
            ]
        }
        config = {
            "min_occurrences": 3,
            "amount_tolerance": 0.1,
            "day_tolerance": 3
        }
        result = detector.detect(data, config)
        
        assert len(result) > 0
        # 验证返回的是字典列表，符合 Suspicion 模型
        assert isinstance(result[0], dict)
        assert "suspicion_id" in result[0]
        assert "suspicion_type" in result[0]
        assert "severity" in result[0]
        assert "description" in result[0]
        assert "amount" in result[0]
        assert "entity_name" in result[0]

    def test_detect_with_fixed_frequency_expense(self):
        """测试检测到固定频率支出模式"""
        detector = FixedFrequencyDetector()
        data = {
            "entity_name": "测试实体",
            "transactions": [
                {
                    "tx_date": "2024-01-15",
                    "amount": -3000.0,
                    "tx_type": "支出",
                    "counterparty": "个人B",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-02-15",
                    "amount": -3000.0,
                    "tx_type": "支出",
                    "counterparty": "个人B",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-03-15",
                    "amount": -3000.0,
                    "tx_type": "支出",
                    "counterparty": "个人B",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                }
            ]
        }
        config = {
            "min_occurrences": 3,
            "amount_tolerance": 0.1,
            "day_tolerance": 3
        }
        result = detector.detect(data, config)
        
        assert len(result) > 0
        assert result[0]["suspicion_type"] == SuspicionType.FREQUENT_TRANSFER.value

    def test_detect_returns_valid_suspicion_data(self):
        """测试返回的数据可以通过 Suspicion 模型验证"""
        detector = FixedFrequencyDetector()
        data = {
            "entity_name": "验证实体",
            "transactions": [
                {
                    "tx_date": "2024-01-01",
                    "amount": 10000.0,
                    "tx_type": "收入",
                    "counterparty": "公司C",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-02-01",
                    "amount": 10000.0,
                    "tx_type": "收入",
                    "counterparty": "公司C",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-03-01",
                    "amount": 10000.0,
                    "tx_type": "收入",
                    "counterparty": "公司C",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-04-01",
                    "amount": 10000.0,
                    "tx_type": "收入",
                    "counterparty": "公司C",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                }
            ]
        }
        config = {}
        result = detector.detect(data, config)
        
        # 验证每个结果都能通过 Suspicion 模型验证
        for item in result:
            suspicion = Suspicion(**item)
            assert suspicion.suspicion_id.startswith("FF")
            assert suspicion.entity_name == "验证实体"
            assert suspicion.amount >= 0
            assert 0 <= suspicion.confidence <= 1

    def test_detect_with_irregular_pattern(self):
        """测试不规则模式不触发检测"""
        detector = FixedFrequencyDetector()
        data = {
            "entity_name": "不规则实体",
            "transactions": [
                {
                    "tx_date": "2024-01-01",
                    "amount": 5000.0,
                    "tx_type": "收入",
                    "counterparty": "公司D",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-01-15",
                    "amount": 8000.0,
                    "tx_type": "收入",
                    "counterparty": "公司E",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-03-20",
                    "amount": 3000.0,
                    "tx_type": "收入",
                    "counterparty": "公司F",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                }
            ]
        }
        config = {
            "min_occurrences": 3,
            "amount_tolerance": 0.1,
            "day_tolerance": 3
        }
        result = detector.detect(data, config)
        
        # 不规则模式应该返回空列表或较少的疑点
        assert len(result) == 0

    def test_detect_with_config_thresholds(self):
        """测试配置参数影响检测结果"""
        detector = FixedFrequencyDetector()
        data = {
            "entity_name": "阈值测试实体",
            "transactions": [
                {
                    "tx_date": "2024-01-01",
                    "amount": 5000.0,
                    "tx_type": "收入",
                    "counterparty": "公司G",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-02-01",
                    "amount": 5000.0,
                    "tx_type": "收入",
                    "counterparty": "公司G",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                }
            ]
        }
        # 设置 min_occurrences=3，但只有2条记录
        config = {"min_occurrences": 3}
        result = detector.detect(data, config)
        
        # 应该检测不到固定频率
        assert len(result) == 0

    def test_detect_with_partial_fixed_pattern(self):
        """测试部分固定模式检测"""
        detector = FixedFrequencyDetector()
        data = {
            "entity_name": "混合模式实体",
            "transactions": [
                # 固定频率组 1
                {
                    "tx_date": "2024-01-01",
                    "amount": 5000.0,
                    "tx_type": "收入",
                    "counterparty": "公司H",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-02-01",
                    "amount": 5000.0,
                    "tx_type": "收入",
                    "counterparty": "公司H",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                {
                    "tx_date": "2024-03-01",
                    "amount": 5000.0,
                    "tx_type": "收入",
                    "counterparty": "公司H",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                },
                # 随机交易
                {
                    "tx_date": "2024-01-20",
                    "amount": 1234.56,
                    "tx_type": "支出",
                    "counterparty": "商店I",
                    "account": "6222021234567890123",
                    "bank": "工商银行"
                }
            ]
        }
        config = {"min_occurrences": 3}
        result = detector.detect(data, config)
        
        # 应该检测到一个固定频率模式
        assert len(result) >= 1
