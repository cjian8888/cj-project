"""
Pydantic Schema 单元测试
测试 Transaction、Suspicion、Profile 三个核心模型的验证功能。
"""
import time
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from schemas.transaction import Transaction, TransactionBatch
from schemas.suspicion import Suspicion, SuspicionReport, SuspicionSeverity, SuspicionType
from schemas.profile import Profile, ProfileMetrics, ProfileComparison, ProfileCollection


class TestTransaction:
    def test_valid_transaction(self):
        tx = Transaction(
            tx_date=date(2024, 1, 15),
            amount=10000.0,
            tx_type="收入",
            counterparty="测试公司",
            account="6222021234567890123",
            bank="工商银行"
        )
        assert tx.amount == 10000.0
        assert tx.tx_type == "收入"
        assert tx.is_income() is True

    def test_transaction_from_string_date(self):
        tx = Transaction(
            tx_date="2024-01-15",
            amount="¥10,000.00",
            tx_type="支出",
            counterparty="测试供应商",
            account="6222021234567890123",
            bank="工商银行"
        )
        assert tx.tx_date == date(2024, 1, 15)
        assert tx.amount == 10000.0
        assert tx.is_expense() is True

    def test_invalid_transaction_type(self):
        with pytest.raises(ValidationError):
            Transaction(
                tx_date=date(2024, 1, 15),
                amount=10000.0,
                tx_type="无效类型",
                counterparty="测试公司",
                account="6222021234567890123",
                bank="工商银行"
            )

    def test_transaction_amount_range(self):
        with pytest.raises(ValidationError):
            Transaction(
                tx_date=date(2024, 1, 15),
                amount=1e13,
                tx_type="收入",
                counterparty="测试公司",
                account="6222021234567890123",
                bank="工商银行"
            )

    def test_empty_counterparty(self):
        with pytest.raises(ValidationError):
            Transaction(
                tx_date=date(2024, 1, 15),
                amount=10000.0,
                tx_type="收入",
                counterparty="   ",
                account="6222021234567890123",
                bank="工商银行"
            )


class TestTransactionBatch:
    def test_batch_validation(self):
        txs = [
            Transaction(
                tx_date=date(2024, 1, i),
                amount=float(i * 1000),
                tx_type="收入",
                counterparty=f"公司{i}",
                account=f"account{i}",
                bank="工商银行"
            )
            for i in range(1, 11)
        ]
        batch = TransactionBatch(transactions=txs)
        assert len(batch.transactions) == 10
        assert batch.get_total_amount() == sum(t.amount for t in txs)

    def test_batch_income_expense(self):
        txs = [
            Transaction(tx_date=date(2024, 1, 1), amount=10000, tx_type="收入", counterparty="A", account="1", bank="ICBC"),
            Transaction(tx_date=date(2024, 1, 2), amount=-5000, tx_type="支出", counterparty="B", account="1", bank="ICBC"),
            Transaction(tx_date=date(2024, 1, 3), amount=8000, tx_type="收入", counterparty="C", account="1", bank="ICBC"),
        ]
        batch = TransactionBatch(transactions=txs)
        assert batch.get_income_total() == 18000
        assert batch.get_expense_total() == 5000


class TestSuspicion:
    def test_valid_suspicion(self):
        suspicion = Suspicion(
            suspicion_id="S001",
            suspicion_type=SuspicionType.CASH_COLLISION,
            severity=SuspicionSeverity.HIGH,
            description="发现大额现金交易",
            amount=500000.0,
            entity_name="张三"
        )
        assert suspicion.severity == SuspicionSeverity.HIGH
        assert suspicion.confidence == 0.5

    def test_suspicion_severity_enum(self):
        suspicion = Suspicion(
            suspicion_id="S002",
            suspicion_type=SuspicionType.DIRECT_TRANSFER,
            severity="中",
            description="可疑转账",
            amount=100000.0,
            entity_name="李四"
        )
        assert suspicion.severity == SuspicionSeverity.MEDIUM

    def test_invalid_confidence(self):
        with pytest.raises(ValidationError):
            Suspicion(
                suspicion_id="S003",
                suspicion_type=SuspicionType.LARGE_CASH,
                severity=SuspicionSeverity.LOW,
                description="测试",
                amount=1000.0,
                entity_name="测试",
                confidence=1.5
            )

    def test_related_transactions_limit(self):
        suspicion = Suspicion(
            suspicion_id="S004",
            suspicion_type=SuspicionType.OTHER,
            severity=SuspicionSeverity.MEDIUM,
            description="测试",
            amount=1000.0,
            entity_name="测试",
            related_transactions=[f"TX{i}" for i in range(100)]
        )
        assert len(suspicion.related_transactions) == 100


class TestSuspicionReport:
    def test_report_risk_counts(self):
        suspicions = [
            Suspicion(
                suspicion_id=f"S{i}",
                suspicion_type=SuspicionType.CASH_COLLISION,
                severity=SuspicionSeverity.HIGH if i < 3 else SuspicionSeverity.MEDIUM,
                description=f"疑点{i}",
                amount=float(i * 10000),
                entity_name="测试"
            )
            for i in range(5)
        ]
        report = SuspicionReport(
            report_id="R001",
            entity_name="测试实体",
            suspicions=suspicions
        )
        assert report.get_high_risk_count() == 3
        assert report.get_medium_risk_count() == 2
        assert report.get_low_risk_count() == 0


class TestProfile:
    def test_valid_profile(self):
        profile = Profile(
            profile_id="P001",
            entity_type="个人",
            name="张三",
            metrics=ProfileMetrics(
                total_income=1000000.0,
                total_expense=500000.0,
                transaction_count=100,
                cash_ratio=0.3
            )
        )
        assert profile.name == "张三"
        assert profile.metrics.total_income == 1000000.0
        assert profile.get_cash_intensity() == "中"

    def test_profile_cash_intensity_levels(self):
        profile_high = Profile(
            profile_id="P002",
            entity_type="个人",
            name="高现金用户",
            metrics=ProfileMetrics(cash_ratio=0.6)
        )
        profile_low = Profile(
            profile_id="P003",
            entity_type="个人",
            name="低现金用户",
            metrics=ProfileMetrics(cash_ratio=0.1)
        )
        assert profile_high.get_cash_intensity() == "高"
        assert profile_low.get_cash_intensity() == "低"

    def test_invalid_entity_type(self):
        with pytest.raises(ValidationError):
            Profile(
                profile_id="P004",
                entity_type="无效类型",
                name="测试",
                metrics=ProfileMetrics()
            )

    def test_profile_high_frequency(self):
        profile = Profile(
            profile_id="P005",
            entity_type="公司",
            name="高频交易公司",
            metrics=ProfileMetrics(transaction_count=200)
        )
        assert profile.is_high_frequency(threshold=100) is True
        assert profile.is_high_frequency(threshold=300) is False


class TestProfileCollection:
    def test_collection_totals(self):
        profiles = [
            Profile(
                profile_id=f"P{i}",
                entity_type="个人",
                name=f"用户{i}",
                metrics=ProfileMetrics(
                    total_income=float(i * 100000),
                    total_expense=float(i * 50000)
                ),
                risk_score=float(i * 20)
            )
            for i in range(1, 6)
        ]
        collection = ProfileCollection(
            collection_id="C001",
            profiles=profiles
        )
        assert collection.get_total_income() == 1500000.0
        assert collection.get_total_expense() == 750000.0

    def test_high_risk_profiles(self):
        profiles = [
            Profile(
                profile_id=f"P{i}",
                entity_type="个人",
                name=f"用户{i}",
                metrics=ProfileMetrics(),
                risk_score=float(i * 25)
            )
            for i in range(5)
        ]
        collection = ProfileCollection(collection_id="C002", profiles=profiles)
        high_risk = collection.get_high_risk_profiles(threshold=70.0)
        assert len(high_risk) == 2


class TestPerformance:
    def test_transaction_batch_performance(self):
        txs_data = [
            {
                "tx_date": "2024-01-15",
                "amount": 10000.0 + i,
                "tx_type": "收入" if i % 2 == 0 else "支出",
                "counterparty": f"公司{i % 100}",
                "account": f"account{i % 10}",
                "bank": "工商银行"
            }
            for i in range(100000)
        ]

        start = time.time()
        batch = TransactionBatch(transactions=txs_data)
        elapsed = time.time() - start

        assert len(batch.transactions) == 100000
        assert elapsed < 5.0, f"10万条记录验证耗时 {elapsed:.2f} 秒，超过5秒限制"

    def test_profile_performance(self):
        profiles_data = [
            {
                "profile_id": f"P{i}",
                "entity_type": "个人" if i % 2 == 0 else "公司",
                "name": f"实体{i}",
                "metrics": {
                    "total_income": float(i * 10000),
                    "total_expense": float(i * 5000),
                    "transaction_count": i * 10
                }
            }
            for i in range(10000)
        ]

        start = time.time()
        profiles = [Profile(**p) for p in profiles_data]
        elapsed = time.time() - start

        assert len(profiles) == 10000
        assert elapsed < 2.0, f"1万条画像验证耗时 {elapsed:.2f} 秒"

    def test_suspicion_performance(self):
        suspicions_data = [
            {
                "suspicion_id": f"S{i}",
                "suspicion_type": SuspicionType.CASH_COLLISION,
                "severity": SuspicionSeverity.HIGH,
                "description": f"疑点描述{i}",
                "amount": float(i * 10000),
                "entity_name": f"实体{i % 100}"
            }
            for i in range(50000)
        ]

        start = time.time()
        suspicions = [Suspicion(**s) for s in suspicions_data]
        elapsed = time.time() - start

        assert len(suspicions) == 50000
        assert elapsed < 3.0, f"5万条疑点验证耗时 {elapsed:.2f} 秒"
