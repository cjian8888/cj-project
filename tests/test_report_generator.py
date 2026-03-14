#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report_generator 老链路聚合 explainability 回归测试。"""

import os
import sys

import pandas as pd
import pytest
from openpyxl import load_workbook

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from report_generator import (
    _generate_aggregation_summary_sheet,
    _generate_html_conclusion,
    _generate_report_conclusion,
    generate_word_report,
)


def _make_profiles():
    return {
        "张三": {
            "has_data": True,
            "summary": {
                "transaction_count": 12,
                "total_income": 300000,
                "total_expense": 200000,
            },
        }
    }


def _make_suspicions():
    return {
        "direct_transfers": [],
        "hidden_assets": {},
    }


def _make_derived_data():
    return {
        "aggregation": {
            "summary": {
                "极高风险实体数": 1,
                "高风险实体数": 0,
                "高优先线索实体数": 1,
            },
            "rankedEntities": [
                {
                    "name": "张三",
                    "riskScore": 88,
                    "riskConfidence": 0.91,
                    "riskLevel": "critical",
                    "highPriorityClueCount": 3,
                    "topEvidenceScore": 84,
                    "summary": "存在闭环和第三方中转",
                    "aggregationExplainability": {
                        "top_clues": [
                            {"description": "资金闭环: 张三 → 外围账户B → 张三"}
                        ]
                    },
                }
            ],
        }
    }


def test_generate_report_conclusion_prefers_aggregation_highlights():
    lines = _generate_report_conclusion(
        _make_profiles(),
        _make_suspicions(),
        ["张三"],
        [],
        derived_data=_make_derived_data(),
    )

    text = "\n".join(lines)
    assert "【聚合排序】" in text
    assert "张三(88.0分/置信度0.91)" in text
    assert "重点线索" in text


def test_generate_html_conclusion_prefers_aggregation_highlights():
    html = _generate_html_conclusion(
        _make_profiles(),
        _make_suspicions(),
        ["张三"],
        [],
        derived_data=_make_derived_data(),
    )

    assert "【聚合排序】" in html
    assert "张三(88.0分/置信度0.91)" in html
    assert "聚合排序识别出重点核查对象" in html


def test_generate_aggregation_summary_sheet_creates_excel_sheet(tmp_path):
    output_path = tmp_path / "aggregation.xlsx"
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _generate_aggregation_summary_sheet(writer, _make_derived_data())

    workbook = load_workbook(output_path)
    assert "聚合风险排序" in workbook.sheetnames
    sheet = workbook["聚合风险排序"]
    values = [cell for row in sheet.iter_rows(values_only=True) for cell in row if cell is not None]
    assert "极高风险实体数" in values
    assert "对象名称" in values
    assert "张三" in values


def test_generate_word_report_prefers_aggregation_highlights(tmp_path):
    docx = pytest.importorskip("docx")
    output_path = tmp_path / "aggregation.docx"

    result = generate_word_report(
        _make_profiles(),
        _make_suspicions(),
        ["张三"],
        [],
        output_path=str(output_path),
        family_summary={},
        family_assets={},
        cleaned_data={},
        derived_data=_make_derived_data(),
    )

    assert result == str(output_path)
    document = docx.Document(result)
    text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    assert "【聚合排序】" in text
    assert "张三(88.0分/置信度0.91)" in text
    assert "聚合排序识别出重点核查对象 张三(88.0分)" in text
