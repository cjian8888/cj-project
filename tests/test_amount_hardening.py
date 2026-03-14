#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""金额单位与脏日期防御回归测试。"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from company_info_extractor import _safe_capital_wan
from data_validator import validate_transaction_data
from database import DatabaseManager
from detectors.direct_transfer_detector import DirectTransferDetector
from detectors.frequency_anomaly_detector import FrequencyAnomalyDetector
from real_salary_income_analyzer import RealSalaryIncomeAnalyzer
from specialized_reports import SpecializedReportGenerator


def _make_generator(tmp_path):
    output_dir = tmp_path / "output" / "analysis_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    return SpecializedReportGenerator(
        analysis_results={},
        profiles={},
        suspicions={},
        output_dir=str(output_dir),
    )


def test_company_capital_helper_keeps_wan_semantics():
    assert _safe_capital_wan("1亿") == 10000.0
    assert _safe_capital_wan("3829.6") == 3829.6


def test_validate_transaction_data_handles_dirty_amounts_and_dates():
    df = pd.DataFrame(
        {
            "date": ["2024/01/01", "not-a-date"],
            "description": ["收入", "支出"],
            "income": ["100万", None],
            "expense": [None, "1.5万"],
            "balance": ["200万", "198.5万"],
        }
    )

    result = validate_transaction_data(df, "张三")

    assert result["record_count"] == 2
    assert any("日期无法解析" in warning for warning in result["warnings"])


def test_specialized_report_supports_wan_amount_header(tmp_path):
    cleaned_dir = tmp_path / "output" / "cleaned_data" / "个人"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    file_path = cleaned_dir / "张三_合并流水.xlsx"
    pd.DataFrame(
        {
            "交易时间": ["2024/01/15 09:30:00"],
            "收入(万元)": ["100"],
            "交易对手": ["某公司"],
            "交易摘要": ["工资发放"],
            "交易分类": ["工资"],
        }
    ).to_excel(file_path, index=False)

    generator = _make_generator(tmp_path)

    transactions = generator._get_day_transactions("张三", "2024-01-15")

    assert len(transactions) == 1
    assert transactions[0]["amount"] == 1000000.0
    assert transactions[0]["time"] == "09:30"


def test_real_salary_income_analyzer_uses_wan_output_without_double_division():
    analyzer = RealSalaryIncomeAnalyzer()
    transactions = pd.DataFrame(
        {
            "direction": ["income"],
            "counterparty": ["某单位工资专户"],
            "description": ["工资发放"],
            "amount": ["1万"],
            "date": ["2024/01/15"],
        }
    )

    result = analyzer.analyze(transactions, "张三")

    assert result["total_salary"] == 1.0
    assert result["average_salary"] == 1.0
    assert "识别出工资收入1.00万元" in result["summary"]


def test_frequency_anomaly_detector_parses_excel_date_and_amount():
    detector = FrequencyAnomalyDetector()

    parsed = detector._parse_transactions(
        [
            {"tx_date": 45292, "tx_time": "08:30", "amount": "1万"},
            {"tx_date": "2024-01-02", "tx_time": "09:00", "amount": "2万"},
        ]
    )

    assert len(parsed) == 2
    assert parsed[0]["amount"] == 10000.0
    assert parsed[0]["datetime"].strftime("%H:%M") == "08:30"


def test_direct_transfer_detector_handles_dirty_amount_strings():
    detector = DirectTransferDetector()
    cleaned_data = {
        "张三": pd.DataFrame(
            {
                "counterparty": ["某公司"],
                "expense": ["10万"],
                "balance": ["20万"],
                "date": ["2024-01-01"],
                "description": ["转账"],
            }
        ),
        "某公司": pd.DataFrame(
            {
                "counterparty": ["张三"],
                "income": ["5万"],
                "balance": ["50万"],
                "date": ["2024-01-02"],
                "description": ["回款"],
            }
        ),
    }

    results = detector.detect(
        {
            "cleaned_data": cleaned_data,
            "all_persons": ["张三"],
            "all_companies": ["某公司"],
        },
        {"income_high_risk_min": 50000, "suspicion_medium_high_amount": 20000},
    )

    assert len(results) == 2
    assert results[0]["amount"] in {100000.0, 50000.0}
    assert results[0]["evidence_refs"]["balance_after"] in {200000.0, 500000.0}


def test_database_manager_normalizes_dirty_amounts_before_persist(tmp_path):
    db = DatabaseManager(db_path=str(tmp_path / "audit.db"))
    df = pd.DataFrame(
        {
            "date": ["2024/01/15", 45292],
            "income": ["1万", "100万"],
            "expense": [0, ""],
            "balance": ["2万", None],
            "counterparty": ["某公司", "某公司"],
            "description": ["入账", "入账"],
            "account": ["6222", "6222"],
            "transaction_type": ["收入", "收入"],
            "source_file": ["a.xlsx", "b.xlsx"],
        }
    )

    inserted = db.insert_transactions("张三", df, "person")
    stored = db.get_transactions(entity_name="张三").sort_values("income").reset_index(
        drop=True
    )

    assert inserted == 2
    assert stored.loc[0, "income"] == 10000.0
    assert stored.loc[1, "income"] == 1000000.0
    assert "45292" not in "".join(stored["date"].astype(str).tolist())
