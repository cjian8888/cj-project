import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fund_penetration
import related_party_analyzer


def test_fund_cycles_deduplicate_mirrored_transfers():
    personal_data = {
        "张三": pd.DataFrame(
            [
                {"date": "2026-01-01 10:00:00", "income": 0, "expense": 50000, "counterparty": "李四", "description": "转账", "数据来源": "zhangsan.xlsx", "source_row_index": 1},
                {"date": "2026-01-01 12:01:00", "income": 50000, "expense": 0, "counterparty": "王五", "description": "转账", "数据来源": "zhangsan.xlsx", "source_row_index": 2},
            ]
        ),
        "李四": pd.DataFrame(
            [
                {"date": "2026-01-01 10:02:00", "income": 50000, "expense": 0, "counterparty": "张三", "description": "转账", "数据来源": "lisi.xlsx", "source_row_index": 3},
                {"date": "2026-01-01 11:00:00", "income": 0, "expense": 50000, "counterparty": "王五", "description": "转账", "数据来源": "lisi.xlsx", "source_row_index": 4},
            ]
        ),
        "王五": pd.DataFrame(
            [
                {"date": "2026-01-01 11:02:00", "income": 50000, "expense": 0, "counterparty": "李四", "description": "转账", "数据来源": "wangwu.xlsx", "source_row_index": 5},
                {"date": "2026-01-01 12:00:00", "income": 0, "expense": 50000, "counterparty": "张三", "description": "转账", "数据来源": "wangwu.xlsx", "source_row_index": 6},
            ]
        ),
    }

    results = fund_penetration.analyze_fund_penetration(
        personal_data=personal_data,
        company_data={},
        core_persons=["张三", "李四", "王五"],
        companies=[],
    )

    assert len(results["fund_cycles"]) == 1
    cycle = results["fund_cycles"][0]
    assert cycle["total_amount"] == 50000
    assert cycle["temporal_match"]["matched_amount"] == 50000


def test_fund_cycles_require_temporal_sequence():
    personal_data = {
        "张三": pd.DataFrame(
            [
                {"date": "2026-02-01 10:00:00", "income": 0, "expense": 50000, "counterparty": "李四", "description": "转账", "数据来源": "zhangsan.xlsx", "source_row_index": 1},
            ]
        ),
        "李四": pd.DataFrame(
            [
                {"date": "2026-04-01 10:00:00", "income": 0, "expense": 50000, "counterparty": "王五", "description": "转账", "数据来源": "lisi.xlsx", "source_row_index": 2},
            ]
        ),
        "王五": pd.DataFrame(
            [
                {"date": "2025-01-01 10:00:00", "income": 0, "expense": 50000, "counterparty": "张三", "description": "转账", "数据来源": "wangwu.xlsx", "source_row_index": 3},
            ]
        ),
    }

    results = fund_penetration.analyze_fund_penetration(
        personal_data=personal_data,
        company_data={},
        core_persons=["张三", "李四", "王五"],
        companies=[],
    )

    assert results["fund_cycles"] == []
    assert results["analysis_metadata"]["fund_cycles"]["filtered_out_count"] >= 1


def test_fund_cycles_exclude_salary_edges_globally():
    all_transactions = {
        "赵峰": pd.DataFrame(
            [
                {"date": "2026-01-01 09:00:00", "income": 0, "expense": 50000, "counterparty": "北京鑫兴航科技有限公司", "description": "电子汇出", "数据来源": "zhaofeng.xlsx", "source_row_index": 1},
                {"date": "2026-01-03 09:02:00", "income": 50000, "expense": 0, "counterparty": "中国科学院过程工程研究所", "description": "工资发放", "数据来源": "zhaofeng.xlsx", "source_row_index": 2},
            ]
        ),
        "北京鑫兴航科技有限公司": pd.DataFrame(
            [
                {"date": "2026-01-01 09:01:00", "income": 50000, "expense": 0, "counterparty": "赵峰", "description": "来账", "数据来源": "company.xlsx", "source_row_index": 3},
                {"date": "2026-01-02 10:00:00", "income": 0, "expense": 50000, "counterparty": "中国科学院过程工程研究所", "description": "项目付款", "数据来源": "company.xlsx", "source_row_index": 4},
            ]
        ),
        "中国科学院过程工程研究所": pd.DataFrame(
            [
                {"date": "2026-01-02 10:01:00", "income": 50000, "expense": 0, "counterparty": "北京鑫兴航科技有限公司", "description": "项目收款", "数据来源": "institute.xlsx", "source_row_index": 5},
                {"date": "2026-01-03 09:00:00", "income": 0, "expense": 50000, "counterparty": "赵峰", "description": "工资发放", "数据来源": "institute.xlsx", "source_row_index": 6},
            ]
        ),
    }

    penetration_results = fund_penetration.analyze_fund_penetration(
        personal_data=all_transactions,
        company_data={},
        core_persons=["赵峰"],
        companies=["北京鑫兴航科技有限公司"],
    )
    related_party_results = related_party_analyzer.analyze_related_party_flows(
        all_transactions,
        ["赵峰"],
    )

    assert penetration_results["fund_cycles"] == []
    assert related_party_results["fund_loops"] == []
