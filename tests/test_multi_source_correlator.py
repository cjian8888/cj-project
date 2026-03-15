#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""multi_source_correlator 关键回归测试。"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from multi_source_correlator import (
    correlate_express_contacts,
    correlate_hotel_cohabitants,
    run_all_correlations,
)


def test_correlate_hotel_cohabitants_applies_time_window_and_risk_level(tmp_path):
    hotel_dir = tmp_path / "公安部同住宿（定向查询）"
    hotel_dir.mkdir(parents=True, exist_ok=True)

    hotel_df = pd.DataFrame(
        [
            {
                "姓名": "李四",
                "入住日期": "2024-01-10",
                "酒店": "某酒店",
            }
        ]
    )
    hotel_df.to_excel(
        hotel_dir / "张三_公安部同住宿（定向查询）.xlsx",
        index=False,
        engine="openpyxl",
    )

    all_transactions = {
        "张三_农行": pd.DataFrame(
            [
                {
                    "date": "2024-01-20",
                    "counterparty": "李四",
                    "income": 0,
                    "expense": 50000,
                    "description": "转账",
                },
                {
                    "date": "2024-03-25",
                    "counterparty": "李四",
                    "income": 0,
                    "expense": 30000,
                    "description": "超窗交易",
                },
            ]
        )
    }

    result = correlate_hotel_cohabitants(str(tmp_path), all_transactions, ["张三"])

    assert len(result["cohabitants"]) == 1
    assert len(result["fund_correlations"]) == 1
    assert result["fund_correlations"][0]["cohabitant"] == "李四"
    assert result["fund_correlations"][0]["timing"] == "先同住后付款"
    assert result["fund_correlations"][0]["risk_level"] == "medium"


def test_correlate_express_contacts_keeps_person_field_when_iterating_namedtuples(
    tmp_path,
):
    express_dir = tmp_path / "国家邮政局快递信息（定向查询）"
    express_dir.mkdir(parents=True, exist_ok=True)

    express_df = pd.DataFrame(
        [
            {"收件人姓名": "李四", "寄件人姓名": "张三"},
        ]
    )
    express_df.to_excel(
        express_dir / "张三_国家邮政局快递信息（定向查询）.xlsx",
        index=False,
        engine="openpyxl",
    )

    all_transactions = {
        "张三_建行": pd.DataFrame(
            [
                {
                    "date": "2024-01-10",
                    "counterparty": "李四",
                    "income": 10000,
                    "expense": 0,
                    "description": "来款",
                }
            ]
        )
    }

    result = correlate_express_contacts(str(tmp_path), all_transactions, ["张三"])

    assert len(result["fund_correlations"]) == 1
    assert result["fund_correlations"][0]["person"] == "张三"
    assert result["fund_correlations"][0]["contact"] == "李四"


def test_run_all_correlations_preserves_travel_and_hotel_results_when_express_fails(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "multi_source_correlator.correlate_travel_companions",
        lambda *args, **kwargs: {"fund_correlations": [{"companion": "李四"}]},
    )
    monkeypatch.setattr(
        "multi_source_correlator.correlate_hotel_cohabitants",
        lambda *args, **kwargs: {"fund_correlations": [{"cohabitant": "王五"}]},
    )

    def _boom(*args, **kwargs):
        raise AttributeError("mock express failure")

    monkeypatch.setattr("multi_source_correlator.correlate_express_contacts", _boom)

    result = run_all_correlations(str(tmp_path), {}, ["张三"])

    assert len(result["travel_companions"]["fund_correlations"]) == 1
    assert len(result["hotel_cohabitants"]["fund_correlations"]) == 1
    assert result["express_contacts"]["fund_correlations"] == []
    assert result["summary"]["资金碰撞总数"] == 2
