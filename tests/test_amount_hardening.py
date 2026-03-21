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
from suspicion_detector import run_all_detections
from suspicion_engine import SuspicionEngine


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


def test_direct_transfer_detector_detects_real_direction_and_deduplicates_ledgers():
    detector = DirectTransferDetector()
    cleaned_data = {
        "张三": pd.DataFrame(
            {
                "counterparty": ["某公司", "某公司"],
                "income": [5000.0, 0.0],
                "expense": [0.0, 100000.0],
                "balance": [20000.0, 120000.0],
                "date": ["2024-01-01 09:00:00", "2024-01-02 10:00:00"],
                "description": ["工资发放", "往来款支付"],
                "source_row_index": [11, 12],
                "transaction_id": ["P-1", "P-2"],
            }
        ),
        "某公司": pd.DataFrame(
            {
                "counterparty": ["张三", "张三"],
                "income": [0.0, 100000.0],
                "expense": [5000.0, 0.0],
                "balance": [500000.0, 600000.0],
                "date": ["2024-01-01 09:00:00", "2024-01-02 10:00:00"],
                "description": ["工资发放", "往来款支付"],
                "source_row_index": [101, 102],
                "transaction_id": ["C-1", "C-2"],
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
    by_direction = {item["direction"]: item for item in results}
    assert by_direction["receive"]["amount"] == 5000.0
    assert by_direction["receive"]["evidence_refs"]["source_row_index"] == 11
    assert by_direction["payment"]["amount"] == 100000.0
    assert by_direction["payment"]["evidence_refs"]["source_row_index"] == 12


def test_direct_transfer_detector_deduplicates_mirrored_bank_memos():
    detector = DirectTransferDetector()
    cleaned_data = {
        "赵峰": pd.DataFrame(
            {
                "counterparty": ["贵州锐晶科技有限公司"],
                "income": [7000.0],
                "expense": [0.0],
                "balance": [120000.0],
                "date": ["2024-05-23 10:04:14"],
                "description": ["CPSP051045 US2390 156342405230341291480"],
                "bank": ["中国银行"],
                "source_file": ["赵峰_中国银行交易流水.xlsx"],
                "source_row_index": [11],
                "transaction_id": ["P-7000"],
            }
        ),
        "贵州锐晶科技有限公司": pd.DataFrame(
            {
                "counterparty": ["赵峰"],
                "income": [0.0],
                "expense": [7000.0],
                "balance": [800000.0],
                "date": ["2024-05-23 10:04:14"],
                "description": ["CPSP051045 US2390 156342405230341291480 US"],
                "bank": ["中国银行"],
                "source_file": ["贵州锐晶科技有限公司_中国银行交易流水.xlsx"],
                "source_row_index": [91],
                "transaction_id": ["C-7000"],
            }
        ),
    }

    results = detector.detect(
        {
            "cleaned_data": cleaned_data,
            "all_persons": ["赵峰"],
            "all_companies": ["贵州锐晶科技有限公司"],
        },
        {"income_high_risk_min": 50000, "suspicion_medium_high_amount": 20000},
    )

    assert len(results) == 1
    assert results[0]["amount"] == 7000.0
    assert results[0]["direction"] == "receive"
    assert results[0]["evidence_refs"]["source_row_index"] == 11


def test_direct_transfer_detector_supports_person_only_ledgers():
    detector = DirectTransferDetector()
    cleaned_data = {
        "张三": pd.DataFrame(
            {
                "counterparty": ["某公司"],
                "income": [0.0],
                "expense": [80000.0],
                "balance": [120000.0],
                "date": ["2024-01-03 09:00:00"],
                "description": ["往来款支付"],
                "source_row_index": [21],
                "transaction_id": ["P-ONLY-1"],
            }
        )
    }

    results = detector.detect(
        {
            "cleaned_data": cleaned_data,
            "all_persons": ["张三"],
            "all_companies": ["某公司"],
        },
        {"income_high_risk_min": 50000, "suspicion_medium_high_amount": 20000},
    )

    assert len(results) == 1
    assert results[0]["person"] == "张三"
    assert results[0]["company"] == "某公司"
    assert results[0]["direction"] == "payment"
    assert results[0]["amount"] == 80000.0


def test_run_all_detections_direct_transfer_fallback_keeps_non_zero_amounts():
    cleaned_data = {
        "张三": pd.DataFrame(
            {
                "counterparty": ["某公司", "某公司"],
                "income": [5000.0, 0.0],
                "expense": [0.0, 100000.0],
                "balance": [20000.0, 120000.0],
                "date": ["2024-01-01 09:00:00", "2024-01-02 10:00:00"],
                "description": ["工资发放", "往来款支付"],
                "source_row_index": [11, 12],
                "transaction_id": ["P-1", "P-2"],
            }
        ),
        "某公司": pd.DataFrame(
            {
                "counterparty": ["张三", "张三"],
                "income": [0.0, 100000.0],
                "expense": [5000.0, 0.0],
                "balance": [500000.0, 600000.0],
                "date": ["2024-01-01 09:00:00", "2024-01-02 10:00:00"],
                "description": ["工资发放", "往来款支付"],
                "source_row_index": [101, 102],
                "transaction_id": ["C-1", "C-2"],
            }
        ),
    }

    results = run_all_detections(cleaned_data, ["张三"], ["某公司"])

    direct_transfers = results["direct_transfers"]
    assert len(direct_transfers) == 2
    assert {item["amount"] for item in direct_transfers} == {5000.0, 100000.0}
    assert {item["direction"] for item in direct_transfers} == {"receive", "payment"}


def test_run_all_detections_direct_transfer_supports_person_only_ledgers():
    cleaned_data = {
        "张三": pd.DataFrame(
            {
                "counterparty": ["某公司"],
                "income": [0.0],
                "expense": [80000.0],
                "balance": [120000.0],
                "date": ["2024-01-03 09:00:00"],
                "description": ["往来款支付"],
                "source_row_index": [21],
                "transaction_id": ["P-ONLY-1"],
            }
        )
    }

    results = run_all_detections(cleaned_data, ["张三"], ["某公司"])

    assert len(results["direct_transfers"]) == 1
    assert results["direct_transfers"][0]["direction"] == "payment"
    assert results["direct_transfers"][0]["amount"] == 80000.0


def test_cash_collision_detector_matches_legacy_for_chinese_cleaned_columns():
    cleaned_data = {
        "张三": pd.DataFrame(
            [
                {
                    "date": "2024-02-09 09:00:00",
                    "收入(元)": 0.0,
                    "支出(元)": 50000.0,
                    "现金": "是",
                    "交易摘要": "ATM取现",
                    "交易对手": "ATM",
                    "银行来源": "工行",
                    "source_row_index": 11,
                }
            ]
        ),
        "李四": pd.DataFrame(
            [
                {
                    "date": "2024-02-09 10:00:00",
                    "收入(元)": 50000.0,
                    "支出(元)": 0.0,
                    "现金": "是",
                    "交易摘要": "ATM存现",
                    "交易对手": "ATM",
                    "银行来源": "农行",
                    "source_row_index": 21,
                }
            ]
        ),
    }

    legacy = run_all_detections(cleaned_data, ["张三", "李四"], [])
    engine_results = SuspicionEngine().run_by_name(
        "cash_collision",
        {"cleaned_data": cleaned_data, "all_persons": ["张三", "李四"]},
        {"cash_time_window_hours": 48, "amount_tolerance_ratio": 0.05},
    )

    assert len(legacy["cash_collisions"]) == 1
    assert len(engine_results) == 1

    expected = legacy["cash_collisions"][0]
    actual = engine_results[0]
    for field in (
        "withdrawal_entity",
        "deposit_entity",
        "withdrawal_amount",
        "deposit_amount",
        "time_diff_hours",
        "amount_diff_ratio",
        "risk_level",
        "risk_reason",
    ):
        assert actual[field] == expected[field]


def test_cash_collision_detector_supports_categorical_cash_flags_and_wan_columns():
    cleaned_data = {
        "张三": pd.DataFrame(
            {
                "交易时间": ["2024-02-09 09:00:00"],
                "收入(万元)": pd.Categorical(["0"]),
                "支出(万元)": pd.Categorical(["5"]),
                "现金": pd.Categorical(["是"]),
                "交易摘要": pd.Categorical(["ATM取现"]),
                "交易对手": ["ATM"],
                "source_row_index": [31],
            }
        ),
        "李四": pd.DataFrame(
            {
                "交易时间": ["2024-02-09 09:30:00"],
                "收入(万元)": pd.Categorical(["5"]),
                "支出(万元)": pd.Categorical(["0"]),
                "现金": pd.Categorical(["是"]),
                "交易摘要": pd.Categorical(["ATM存现"]),
                "交易对手": ["ATM"],
                "source_row_index": [41],
            }
        ),
    }

    results = SuspicionEngine().run_by_name(
        "cash_collision",
        {"cleaned_data": cleaned_data},
        {"cash_time_window_hours": 48, "amount_tolerance_ratio": 0.05},
    )

    assert len(results) == 1
    assert results[0]["withdrawal_amount"] == 50000.0
    assert results[0]["deposit_amount"] == 50000.0
    assert results[0]["withdrawal_row"] == 31
    assert results[0]["deposit_row"] == 41


def test_suspicion_engine_adapts_cleaned_data_for_transaction_only_detectors():
    cleaned_data = {
        "张三": pd.DataFrame(
            [
                {
                    "date": "2024-01-01 09:00:00",
                    "income": 60000.0,
                    "expense": 0.0,
                    "counterparty": "来源A",
                    "description": "收入A",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-01-01 09:10:00",
                    "income": 60000.0,
                    "expense": 0.0,
                    "counterparty": "来源B",
                    "description": "收入B",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-01-01 09:20:00",
                    "income": 60000.0,
                    "expense": 0.0,
                    "counterparty": "来源C",
                    "description": "收入C",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-01-01 09:30:00",
                    "income": 60000.0,
                    "expense": 0.0,
                    "counterparty": "来源D",
                    "description": "收入D",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-01-01 09:40:00",
                    "income": 60000.0,
                    "expense": 0.0,
                    "counterparty": "来源E",
                    "description": "收入E",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-01-02 10:00:00",
                    "income": 0.0,
                    "expense": 180000.0,
                    "counterparty": "集中去向",
                    "description": "集中转出",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-01-05 11:00:00",
                    "income": 0.0,
                    "expense": 50000.0,
                    "counterparty": "固定对手方",
                    "description": "固定支出1",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-02-05 11:00:00",
                    "income": 0.0,
                    "expense": 50000.0,
                    "counterparty": "固定对手方",
                    "description": "固定支出2",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-03-05 11:00:00",
                    "income": 0.0,
                    "expense": 50000.0,
                    "counterparty": "固定对手方",
                    "description": "固定支出3",
                    "bank": "测试银行",
                },
            ]
        )
    }

    results = SuspicionEngine().run_all(
        {"cleaned_data": cleaned_data},
        {
            "daily_threshold": 5,
            "hourly_threshold": 5,
            "window_tx_threshold": 5,
            "min_amount": 10000,
            "min_occurrences": 3,
            "window_days": 7,
            "min_inflow_sources": 3,
            "min_outflow_targets": 3,
        },
    )

    for detector_name in (
        "round_amount",
        "fixed_amount",
        "fixed_frequency",
        "frequency_anomaly",
        "suspicious_pattern",
    ):
        assert detector_name in results
        assert len(results[detector_name]) >= 1
        assert all(item.get("entity_name") == "张三" for item in results[detector_name])


def test_suspicion_engine_transaction_only_detectors_handle_categorical_columns_without_optional_fields():
    cleaned_data = {
        "张三": pd.DataFrame(
            {
                "date": [
                    "2024-01-01 09:00:00",
                    "2024-01-01 09:10:00",
                    "2024-01-01 09:20:00",
                    "2024-01-01 09:30:00",
                    "2024-01-01 09:40:00",
                    "2024-01-02 10:00:00",
                    "2024-01-05 11:00:00",
                    "2024-02-05 11:00:00",
                    "2024-03-05 11:00:00",
                ],
                "income": [
                    60000.0,
                    60000.0,
                    60000.0,
                    60000.0,
                    60000.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
                "expense": [
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    180000.0,
                    50000.0,
                    50000.0,
                    50000.0,
                ],
                "counterparty": pd.Categorical(
                    [
                        "来源A",
                        "来源B",
                        "来源C",
                        "来源D",
                        "来源E",
                        "集中去向",
                        "固定对手方",
                        "固定对手方",
                        "固定对手方",
                    ]
                ),
                "description": pd.Categorical(
                    [
                        "收入A",
                        "收入B",
                        "收入C",
                        "收入D",
                        "收入E",
                        "集中转出",
                        "固定支出1",
                        "固定支出2",
                        "固定支出3",
                    ]
                ),
            }
        )
    }

    results = SuspicionEngine().run_all(
        {"cleaned_data": cleaned_data},
        {
            "daily_threshold": 5,
            "hourly_threshold": 5,
            "window_tx_threshold": 5,
            "min_amount": 10000,
            "min_occurrences": 3,
            "window_days": 7,
            "min_inflow_sources": 3,
            "min_outflow_targets": 3,
        },
    )

    for detector_name in (
        "round_amount",
        "fixed_amount",
        "fixed_frequency",
        "frequency_anomaly",
        "suspicious_pattern",
    ):
        assert detector_name in results
        assert len(results[detector_name]) >= 1
        assert all(item.get("entity_name") == "张三" for item in results[detector_name])


def test_suspicion_engine_maps_account_number_and_income_tx_type_for_cleaned_data():
    cleaned_data = {
        "张三": pd.DataFrame(
            [
                {
                    "date": "2024-01-01 09:00:00",
                    "income": 50000.0,
                    "expense": 0.0,
                    "counterparty": "某单位",
                    "description": "工资发放",
                    "account_number": "6222000011112222",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-02-01 09:00:00",
                    "income": 50000.0,
                    "expense": 0.0,
                    "counterparty": "某单位",
                    "description": "工资发放",
                    "account_number": "6222000011112222",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-03-01 09:00:00",
                    "income": 50000.0,
                    "expense": 0.0,
                    "counterparty": "某单位",
                    "description": "工资发放",
                    "account_number": "6222000011112222",
                    "bank": "测试银行",
                },
            ]
        )
    }

    engine = SuspicionEngine()
    detector_inputs = engine._build_detector_inputs("fixed_frequency", {"cleaned_data": cleaned_data})

    assert detector_inputs[0]["transactions"][0]["account"] == "6222000011112222"
    assert detector_inputs[0]["transactions"][0]["tx_type"] == "收入"

    results = engine.run_by_name(
        "fixed_frequency",
        {"cleaned_data": cleaned_data},
        {"min_occurrences": 3, "amount_tolerance": 0, "day_tolerance": 3},
    )

    assert len(results) >= 1
    assert "规律性收入模式" in results[0]["description"]


def test_suspicion_engine_suspicious_pattern_respects_account_number_boundaries():
    cleaned_data = {
        "张三": pd.DataFrame(
            [
                {
                    "date": "2024-01-01 09:00:00",
                    "income": 100000.0,
                    "expense": 0.0,
                    "counterparty": "来源A",
                    "description": "大额转入",
                    "account_number": "ACC-IN",
                    "bank": "测试银行",
                },
                {
                    "date": "2024-01-01 12:00:00",
                    "income": 0.0,
                    "expense": 90000.0,
                    "counterparty": "去向B",
                    "description": "大额转出",
                    "account_number": "ACC-OUT",
                    "bank": "测试银行",
                },
            ]
        )
    }

    results = SuspicionEngine().run_by_name(
        "suspicious_pattern",
        {"cleaned_data": cleaned_data},
        {
            "window_days": 7,
            "min_inflow_sources": 3,
            "min_outflow_targets": 3,
            "min_amount": 50000,
            "fast_in_out_hours": 24,
            "fast_in_out_ratio": 0.8,
        },
    )

    assert results == []


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
