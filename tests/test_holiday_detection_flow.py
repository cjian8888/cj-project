#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""节假日检测主流程回归测试。"""

from datetime import datetime

import pandas as pd

import config
from api_server import serialize_suspicions
from risk_scoring import RISK_SCORE_WEIGHTS, score_transaction
from suspicion_detector import run_all_detections


def test_run_all_detections_covers_before_during_after_holiday_window():
    cleaned_data = {
        "张三": pd.DataFrame(
            [
                {
                    "date": "2024-02-09 10:00:00",
                    "income": 80000.0,
                    "expense": 0.0,
                    "counterparty": "甲公司",
                    "description": "春节前转入",
                },
                {
                    "date": "2024-02-10 11:30:00",
                    "income": 120000.0,
                    "expense": 0.0,
                    "counterparty": "乙公司",
                    "description": "春节当天转入",
                },
                {
                    "date": "2024-02-18 09:15:00",
                    "income": 0.0,
                    "expense": 90000.0,
                    "counterparty": "丙公司",
                    "description": "春节后转出",
                },
            ]
        )
    }

    results = run_all_detections(cleaned_data, [], [])

    assert "张三" in results["holiday_transactions"]
    records = results["holiday_transactions"]["张三"]
    assert len(records) == 3
    assert {item["holiday_period"] for item in records} == {"before", "during", "after"}
    assert {item["holiday_name"] for item in records} == {"春节"}


def test_serialize_suspicions_converts_holiday_transaction_fields():
    serialized = serialize_suspicions(
        {
            "holiday_transactions": {
                "张三": [
                    {
                        "date": datetime(2024, 2, 10, 11, 30, 0),
                        "amount": 120000.0,
                        "description": "春节当天转入",
                        "holiday_name": "春节",
                        "holiday_period": "during",
                        "counterparty": "乙公司",
                    }
                ]
            }
        }
    )

    record = serialized["holidayTransactions"]["张三"][0]
    assert record["holidayName"] == "春节"
    assert record["holidayPeriod"] == "during"
    assert record["date"].startswith("2024-02-10")


def test_score_transaction_adds_holiday_time_weight():
    row = pd.Series(
        {
            "date": pd.Timestamp("2024-02-10 10:00:00"),
            "income": 120000.0,
            "expense": 0.0,
            "counterparty": "某企业",
            "description": "春节交易",
        }
    )

    result = score_transaction(row)

    assert result["breakdown"]["time"] >= RISK_SCORE_WEIGHTS["time"]["holiday"]


def test_local_holiday_fallback_extends_backward_to_2020():
    expected_years = {2020, 2021, 2022, 2023, 2024, 2025, 2026}
    assert expected_years.issubset(set(config.CHINESE_HOLIDAYS.keys()))
