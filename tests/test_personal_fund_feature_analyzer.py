#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""个人资金特征分析器回归测试。"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from personal_fund_feature_analyzer import PersonalFundFeatureAnalyzer


def test_authoritative_income_expense_analysis_overrides_legacy_consumption_logic():
    analyzer = PersonalFundFeatureAnalyzer()
    transactions = pd.DataFrame(
        [
            {
                "date": "2025-01-01",
                "transaction_type": "转账收入",
                "amount": 10000,
                "counterparty": "某公司",
                "description": "普通入账",
                "account": "A001",
            }
        ]
    )

    result = analyzer.analyze(
        person_profile={
            "name": "赵峰",
            "id": "321182197708011010",
            "wage_income": 33.2119,
            "total_income": 246.103032,
        },
        person_transactions=transactions,
        family_members=[],
        suspicions=None,
        income_expense_match_analysis={
            "score": 20,
            "risk_level": "高风险",
            "description": (
                "该人员工资性收入累计33.21万元，但同期有效消费支出261.23万元，"
                "存在228.02万元的巨额收支缺口。"
            ),
            "evidence": [{"type": "真实工资收入", "value": "33.21万元"}],
            "metrics": {
                "real_salary": 33.2119,
                "effective_expense": 261.234279,
                "total_income": 246.103032,
                "gap": 228.022379,
                "coverage_ratio": 12.713454,
                "extra_income": 212.891132,
                "extra_ratio": 86.50488,
                "extra_income_types": ["可核实合法收入", "来源待核实收入"],
            },
        },
    )

    income_expense = result["dimensions"]["income_expense_match"]

    assert income_expense["score"] == 20.0
    assert income_expense["description"].startswith("该人员工资性收入累计33.21万元")
    assert income_expense["metrics"]["analysis_basis"] == "income_expense_match_analysis"
    assert "工资收入覆盖正常" not in result["risk_exclusions"]
    assert "消费水平与收入匹配，无异常消费" not in result["risk_exclusions"]
    assert "收支严重不匹配" in result["overall_feature"]
    assert any("巨额收支缺口" in item for item in result["audit_description"])
