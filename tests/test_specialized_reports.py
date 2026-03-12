#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专项 txt 报告生成逻辑回归测试。"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from specialized_reports import SpecializedReportGenerator


def _make_generator(tmp_path, analysis_results=None, profiles=None, suspicions=None):
    output_dir = tmp_path / "output" / "analysis_results"
    cache_dir = tmp_path / "output" / "analysis_cache"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return SpecializedReportGenerator(
        analysis_results=analysis_results or {},
        profiles=profiles or {},
        suspicions=suspicions or {},
        output_dir=str(output_dir),
    )


def test_asset_report_prefers_auto_config_and_does_not_fabricate_property_value(tmp_path):
    generator = _make_generator(tmp_path)
    cache_dir = tmp_path / "output" / "analysis_cache"

    (cache_dir / "primary_targets.auto.json").write_text(
        json.dumps(
            {
                "analysis_units": [
                    {
                        "anchor": "候海焱",
                        "members": ["候海焱", "周伟", "周天健"],
                        "member_details": [
                            {"name": "候海焱", "relation": "本人", "has_data": True},
                            {"name": "周伟", "relation": "配偶", "has_data": False},
                            {"name": "周天健", "relation": "女儿", "has_data": False},
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (cache_dir / "precisePropertyData.json").write_text(
        json.dumps(
            {
                "310000000000000001": [
                    {
                        "owner_name": "候海焱",
                        "owner_id": "310000000000000001",
                        "location": "测试路1号101室",
                        "area": "88.50平方米",
                        "usage": "居住",
                        "register_date": "2024-01-01",
                        "transaction_amount": 0,
                        "source_file": "property.xlsx",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = generator._generate_asset_report()

    assert "家庭单元数: 1 个" in report
    assert "房产总成交价: 信息缺失" in report
    assert "成交价: 未获取" in report
    assert "估值:" not in report
    assert "平方米㎡" not in report


def test_asset_report_dedupes_analysis_units_in_auto_config(tmp_path):
    generator = _make_generator(tmp_path)
    cache_dir = tmp_path / "output" / "analysis_cache"

    (cache_dir / "primary_targets.auto.json").write_text(
        json.dumps(
            {
                "analysis_units": [
                    {"anchor": "候海焱", "members": ["候海焱", "周伟"]},
                    {"anchor": "候海焱", "members": ["候海焱", "周伟"]},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = generator._generate_asset_report()

    assert "家庭单元数: 1 个" in report


def test_penetration_report_marks_missing_amount_instead_of_zero(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "relatedParty": {
                "fund_loops": [
                    {
                        "participants": ["张三", "李四"],
                        "path": "张三 → 李四 → 张三",
                        "length": 2,
                        "risk_level": "medium",
                    }
                ]
            }
        },
    )

    report = generator._generate_penetration_report()

    assert "总资金: 未提供" in report
    assert "总资金: ¥0.00" not in report


def test_income_report_uses_special_scope_wording_for_unknown_source(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "income": {
                "unknown_source_income": [],
                "details": [],
            }
        },
    )

    report = generator._generate_income_report()

    assert "对手方缺失的大额入账分析（专项口径）" in report
    assert "不等同于正式报告中的“来源待核实收入”" in report
    assert "未发现符合本专项口径的对手方缺失大额入账" in report


def test_time_series_report_filters_tiny_periodic_income_noise(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "timeSeries": {
                "periodic_income": [
                    {
                        "person": "张三",
                        "counterparty": "应付活期储蓄存款利息",
                        "occurrences": 26,
                        "avg_amount": 0.01,
                        "total_amount": 0.26,
                        "date_range": ["2018-03-21", "2024-06-21"],
                    },
                    {
                        "person": "张三",
                        "counterparty": "某咨询公司",
                        "occurrences": 4,
                        "avg_amount": 3000,
                        "total_amount": 12000,
                        "date_range": ["2024-01-01", "2024-04-01"],
                    },
                ]
            }
        },
    )

    report = generator._generate_time_series_report()

    assert "应付活期储蓄存款利息" not in report
    assert "某咨询公司" in report


def test_time_series_report_filters_tiny_day_transaction_details(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "timeSeries": {
                "sudden_changes": [
                    {
                        "person": "张三",
                        "change_type": "income_spike",
                        "date": "2024-01-01",
                        "amount": 200000,
                        "z_score": 4.2,
                        "avg_before": 1000,
                    }
                ]
            }
        },
    )
    generator._get_day_transactions = lambda person, date: [  # type: ignore[method-assign]
        {
            "time": "00:00",
            "amount": 0.01,
            "counterparty": "应付活期储蓄存款利息",
            "category": "其他",
            "type_info": {"icon": "✅", "type": "正常交易", "detail": ""},
        },
        {
            "time": "10:30",
            "amount": 5000,
            "counterparty": "某咨询公司",
            "category": "其他",
            "type_info": {"icon": "⚠️", "type": "可疑交易", "detail": "测试"},
        },
    ]

    report = generator._generate_time_series_report()

    assert "应付活期储蓄存款利息" not in report
    assert "某咨询公司" in report


def test_suspicion_report_filters_small_cash_collision_noise(tmp_path):
    generator = _make_generator(
        tmp_path,
        suspicions={
            "cashCollisions": [
                {
                    "withdrawal_entity": "张三",
                    "deposit_entity": "李四",
                    "withdrawal_date": "2024-01-01",
                    "deposit_date": "2024-01-01",
                    "withdrawal_amount": 100,
                    "deposit_amount": 100,
                },
                {
                    "withdrawal_entity": "张三",
                    "deposit_entity": "李四",
                    "withdrawal_date": "2024-02-01",
                    "deposit_date": "2024-02-01",
                    "withdrawal_amount": 20000,
                    "deposit_amount": 19800,
                },
            ]
        },
    )

    report = generator._generate_suspicion_report()

    assert "¥100.00 元" not in report
    assert "¥2.00万 元" in report


def test_loan_report_filters_tiny_platform_summary_noise(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "loan": {
                "online_loan_platforms": [
                    {"platform": "有钱花", "amount": 0.06, "direction": "expense", "person": "张三"},
                    {"platform": "借呗", "amount": 20000, "direction": "expense", "person": "张三"},
                ]
            }
        },
    )

    report = generator._generate_loan_report()

    assert "有钱花" not in report
    assert "借呗" in report


def test_income_report_filters_benign_loan_disbursement_entries(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "income": {
                "large_single_income": [
                    {
                        "person": "张三",
                        "amount": 1_000_000,
                        "counterparty": "公积金贷款总额核算放款专户",
                        "description": "正常",
                    },
                    {
                        "person": "张三",
                        "amount": 800_000,
                        "counterparty": "王五",
                        "description": "个人大额转入",
                    },
                ]
            }
        },
    )

    report = generator._generate_income_report()

    assert "公积金贷款总额核算放款专户" not in report
    assert "王五" in report


def test_income_report_filters_benign_periodic_and_same_source_entries(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "income": {
                "regular_non_salary": [
                    {
                        "person": "张三",
                        "counterparty": "个贷系统平账专户",
                        "occurrences": 6,
                        "avg_amount": 20000,
                        "total_amount": 120000,
                        "description": "住房贷款放款",
                    },
                    {
                        "person": "张三",
                        "counterparty": "某咨询公司",
                        "occurrences": 4,
                        "avg_amount": 5000,
                        "total_amount": 20000,
                    },
                ],
                "same_source_multi": [
                    {
                        "person": "张三",
                        "counterparty": "个贷系统平账专户",
                        "count": 3,
                        "total": 150000,
                        "avg_amount": 50000,
                        "description": "贷款放款",
                    },
                    {
                        "person": "张三",
                        "counterparty": "王五",
                        "count": 3,
                        "total": 90000,
                        "avg_amount": 30000,
                    },
                ],
            }
        },
    )

    report = generator._generate_income_report()

    assert "个贷系统平账专户" not in report
    assert "某咨询公司" in report
    assert "王五" in report


def test_penetration_report_estimates_cycle_amount_from_graph_edges(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "relatedParty": {
                "fund_loops": [
                    {
                        "path": "张三 → 李四 → 王五 → 张三",
                        "length": 3,
                        "risk_level": "high",
                    }
                ]
            }
        },
    )
    cache_dir = tmp_path / "output" / "analysis_cache"
    (cache_dir / "graph_data.json").write_text(
        json.dumps(
            {
                "edges": [
                    {"from": "张三", "to": "李四", "value": 30},
                    {"from": "李四", "to": "王五", "value": 12},
                    {"from": "王五", "to": "张三", "value": 18},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = generator._generate_penetration_report()

    assert "估算闭环金额: ¥12.00万 元" in report


def test_penetration_report_suppresses_tiny_estimated_cycle_amounts(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "relatedParty": {
                "fund_loops": [
                    {
                        "path": "张三 → 李四 → 张三",
                        "length": 2,
                        "risk_level": "medium",
                    }
                ]
            }
        },
    )
    cache_dir = tmp_path / "output" / "analysis_cache"
    (cache_dir / "graph_data.json").write_text(
        json.dumps(
            {
                "edges": [
                    {"from": "张三", "to": "李四", "value": 0.5},
                    {"from": "李四", "to": "张三", "value": 0.8},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = generator._generate_penetration_report()

    assert "估算闭环金额" not in report
    assert "总资金: 未提供" in report
