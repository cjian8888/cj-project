#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工资分析模块回归测试
"""

import os
import sys

import pandas as pd
import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from salary_analyzer import analyze_income_structure, identify_salary_transactions


@pytest.fixture
def patched_salary_config(monkeypatch):
    monkeypatch.setattr(config, "SALARY_STRONG_KEYWORDS", ["工资"])
    monkeypatch.setattr(config, "SALARY_KEYWORDS", ["工资"])
    monkeypatch.setattr(config, "KNOWN_SALARY_PAYERS", ["测试发薪单位"])
    monkeypatch.setattr(config, "USER_DEFINED_SALARY_PAYERS", [])
    monkeypatch.setattr(config, "EXCLUDED_REIMBURSEMENT_KEYWORDS", ["报销"])
    monkeypatch.setattr(config, "WEALTH_REDEMPTION_KEYWORDS", ["赎回", "理财"])


def test_identify_salary_transactions_deduplicates_overlapping_matches(
    patched_salary_config,
):
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-15", "2024-02-15", "2024-03-15"]),
            "income": [10000.0, 10000.0, 10000.0],
            "counterparty": ["测试发薪单位", "测试发薪单位", "测试发薪单位"],
            "description": ["代发工资", "代发工资", "代发工资"],
        }
    )

    salary_df, stats = identify_salary_transactions(df, "测试人员")

    assert len(salary_df) == 3
    assert salary_df["income"].sum() == 30000.0
    assert stats["by_strong_keyword"] == 3
    assert stats["by_payer"] == 3
    assert stats["by_regular_pattern"] == 0
    assert stats["deduplicated_overlap"] == 3


def test_analyze_income_structure_salary_ratio_never_exceeds_one(
    patched_salary_config,
):
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-15", "2024-02-15", "2024-03-15", "2024-03-20"]
            ),
            "income": [10000.0, 10000.0, 10000.0, 5000.0],
            "counterparty": [
                "测试发薪单位",
                "测试发薪单位",
                "测试发薪单位",
                "其他来款方",
            ],
            "description": ["代发工资", "代发工资", "代发工资", "奖金"],
        }
    )

    result = analyze_income_structure(df, "测试人员")

    assert result["salary_income"] == 30000.0
    assert result["total_income"] == 35000.0
    assert result["salary_ratio"] == pytest.approx(30000.0 / 35000.0)
