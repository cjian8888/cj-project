#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""节假日检测主流程回归测试。"""

import sys
import os
from datetime import datetime, date
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from holiday_service import HolidayService
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


def test_serialize_suspicions_uses_actual_transfer_direction_for_parties():
    serialized = serialize_suspicions(
        {
            "direct_transfers": [
                {
                    "person": "张三",
                    "company": "某公司",
                    "amount": 5000.0,
                    "date": datetime(2024, 1, 1, 9, 0, 0),
                    "direction": "receive",
                    "description": "工资发放",
                },
                {
                    "person": "张三",
                    "company": "某公司",
                    "amount": 100000.0,
                    "date": datetime(2024, 1, 2, 10, 0, 0),
                    "direction": "payment",
                    "description": "往来款支付",
                },
            ]
        }
    )

    receive_record, payment_record = serialized["directTransfers"]
    assert receive_record["from"] == "某公司"
    assert receive_record["to"] == "张三"
    assert payment_record["from"] == "张三"
    assert payment_record["to"] == "某公司"


def test_serialize_suspicions_normalizes_bank_system_transfer_memo():
    serialized = serialize_suspicions(
        {
            "direct_transfers": [
                {
                    "person": "赵峰",
                    "company": "贵州锐晶科技有限公司",
                    "amount": 7000.0,
                    "date": datetime(2024, 5, 23, 10, 4, 14),
                    "direction": "receive",
                    "description": "CPSP051045 US2390 156342405230341291480",
                    "bank": "中国银行",
                    "evidence_refs": {"channel": "其他"},
                },
                {
                    "person": "金琳",
                    "company": "某对手方",
                    "amount": 120000.0,
                    "date": datetime(2023, 2, 8, 17, 3, 45),
                    "direction": "receive",
                    "description": "网银跨行汇款 / /CHN",
                    "bank": "中国银行",
                    "evidence_refs": {"channel": "网银"},
                },
            ]
        }
    )

    cpsp_record, chn_record = serialized["directTransfers"]
    assert cpsp_record["description"] == "中行系统跨行转账附言（原始流水码已省略）"
    assert cpsp_record["evidenceRefs"]["rawDescription"].startswith("CPSP051045")
    assert chn_record["description"] == "网银跨行汇款"
    assert "rawDescription" in chn_record["evidenceRefs"]


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


def test_holiday_service_normalizes_library_string_names_to_chinese(monkeypatch):
    library_holidays = {
        date(2024, 1, 1): "New Year's Day",
        date(2024, 2, 10): "Spring Festival",
        date(2024, 2, 11): "Spring Festival",
    }

    fake_calendar = SimpleNamespace(
        is_holiday=lambda d: d in library_holidays,
        get_holiday_detail=lambda d: (d in library_holidays, library_holidays.get(d)),
        is_workday=lambda d: False,
    )
    monkeypatch.setitem(sys.modules, "chinese_calendar", fake_calendar)

    service = HolidayService()

    assert service.get_holiday_name(date(2024, 1, 1)) == "元旦"

    ranges = service.get_holiday_ranges_for_year(2024)
    assert any(name == "春节" for _, _, name in ranges)


def test_holiday_service_does_not_treat_plain_weekend_as_named_holiday(monkeypatch):
    fake_calendar = SimpleNamespace(
        is_holiday=lambda d: d.weekday() >= 5 or d == date(2024, 1, 1),
        get_holiday_detail=lambda d: (
            (True, "New Year's Day")
            if d == date(2024, 1, 1)
            else ((True, None) if d.weekday() >= 5 else (False, None))
        ),
        is_workday=lambda d: d.weekday() < 5 and d != date(2024, 1, 1),
    )
    monkeypatch.setitem(sys.modules, "chinese_calendar", fake_calendar)

    service = HolidayService()

    assert service.is_holiday(date(2024, 1, 13)) is False
    assert service.get_holiday_name(date(2024, 1, 13)) is None
    assert service.build_holiday_window(date(2024, 1, 15), date(2024, 1, 17)) == {}
