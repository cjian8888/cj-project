#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专项 txt 报告生成逻辑回归测试。"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from specialized_reports import SpecializedReportGenerator


def _make_generator(
    tmp_path, analysis_results=None, profiles=None, suspicions=None, input_dir=None
):
    output_dir = tmp_path / "output" / "analysis_results"
    cache_dir = tmp_path / "output" / "analysis_cache"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return SpecializedReportGenerator(
        analysis_results=analysis_results or {},
        profiles=profiles or {},
        suspicions=suspicions or {},
        output_dir=str(output_dir),
        input_dir=str(input_dir) if input_dir else None,
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


def test_primary_analysis_units_prefers_user_config_over_auto_snapshot(tmp_path):
    data_dir = tmp_path / "custom_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    generator = _make_generator(tmp_path, input_dir=data_dir)
    cache_dir = tmp_path / "output" / "analysis_cache"

    (cache_dir / "primary_targets.auto.json").write_text(
        json.dumps(
            {"analysis_units": [{"anchor": "自动户主", "members": ["自动户主"]}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (data_dir / "primary_targets.json").write_text(
        json.dumps(
            {
                "analysis_units": [
                    {"anchor": "用户户主", "members": ["用户户主", "配偶"]}
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    units = generator._load_primary_analysis_units()

    assert units[0]["anchor"] == "用户户主"
    assert units[0]["members"] == ["用户户主", "配偶"]


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

    assert "闭环金额: 当前闭环结果仅输出路径与风险等级" in report
    assert "总资金: ¥0.00" not in report


def test_penetration_report_prefers_structured_path_explainability(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "relatedParty": {
                "third_party_relays": [
                    {
                        "from": "张三",
                        "relay": "外围账户B",
                        "to": "李四",
                        "outflow_amount": 180000,
                        "inflow_amount": 178000,
                        "amount_diff": 2000,
                        "time_diff_hours": 6.0,
                        "risk_level": "high",
                        "risk_score": 82,
                        "confidence": 0.9,
                        "path_explainability": {
                            "summary": "资金在 6.0 小时内经 外围账户B 由 张三 转向 李四，金额差比例 1.1%",
                            "inspection_points": [
                                "链路路径: 张三 → 外围账户B → 李四",
                                "时间关系: 2024-01-01 10:00:00 -> 2024-01-01 16:00:00（6.0 小时）",
                            ],
                            "sequence_summary": "第1步 张三 向 外围账户B 转出，第2步 外围账户B 向 李四 转入，两步相隔 6.0 小时",
                            "time_axis_total": 5,
                            "time_axis": [
                                {
                                    "step": 1,
                                    "time": "2024-01-01 10:00:00",
                                    "label": "张三 向 外围账户B 转出",
                                    "amount": 180000,
                                    "source_file": "zhangsan.xlsx",
                                    "source_row_index": 10,
                                },
                                {
                                    "step": 2,
                                    "time": "2024-01-01 16:00:00",
                                    "label": "外围账户B 向 李四 转入",
                                    "amount": 178000,
                                    "source_file": "lisi.xlsx",
                                    "source_row_index": 11,
                                },
                            ],
                        },
                    }
                ],
                "relationship_clusters": [
                    {
                        "cluster_id": "cluster_1",
                        "core_members": ["张三", "李四"],
                        "external_members": ["外围账户B"],
                        "direct_flow_count": 1,
                        "relay_count": 1,
                        "loop_count": 1,
                        "risk_score": 84,
                        "confidence": 0.88,
                        "path_explainability": {
                            "summary": "该关系簇包含核心成员 2 个、外围成员 1 个，以闭环关系为主",
                            "inspection_points": [
                                "成员构成: 核心 张三、李四 / 外围 外围账户B",
                                "关系计数: 直接往来 1 / 第三方中转 1 / 资金闭环 1",
                            ],
                        },
                    }
                ],
            },
            "penetration": {
                "fund_cycles": [
                    {
                        "path": "张三 → 外围账户B → 李四 → 张三",
                        "length": 3,
                        "risk_level": "high",
                        "risk_score": 86,
                        "confidence": 0.91,
                        "path_explainability": {
                            "summary": "闭环路径包含 3 个节点，其中外围节点 1 个，估算回流金额 180000.00 元",
                            "inspection_points": [
                                "回流路径: 张三 → 外围账户B → 李四 → 张三",
                                "节点构成: 核查对象 2 / 外围节点 1",
                            ],
                            "edge_segments": [
                                {
                                    "index": 1,
                                    "from": "张三",
                                    "to": "外围账户B",
                                    "amount": 180000,
                                    "transaction_refs_total": 4,
                                    "transaction_refs": [
                                        {
                                            "date": "2024-01-01 10:00:00",
                                            "amount": 180000,
                                            "source_file": "zhangsan.xlsx",
                                            "source_row_index": 10,
                                        }
                                    ],
                                },
                                {"index": 2, "from": "外围账户B", "to": "李四", "amount": 178000},
                                {"index": 3, "from": "李四", "to": "张三", "amount": 180000},
                            ],
                            "bottleneck_edge": {"from": "外围账户B", "to": "李四", "amount": 178000},
                        },
                    }
                ]
            },
        },
    )

    report = generator._generate_penetration_report()

    assert "路径摘要: 闭环路径包含 3 个节点" in report
    assert "路径解释: 回流路径: 张三 → 外围账户B → 李四 → 张三" in report
    assert "边级金额:" in report
    assert "第1跳 张三 -> 外围账户B ¥18.00万 元" in report
    assert "原始流水: 2024-01-01 10:00:00 ¥18.00万 元 zhangsan.xlsx 第10行" in report
    assert "原始流水样本: 当前展示 1 条，实际共 4 条" in report
    assert "路径摘要: 资金在 6.0 小时内经 外围账户B 由 张三 转向 李四" in report
    assert "时间轴摘要:" in report
    assert "时间轴:" in report
    assert "原始流水: zhangsan.xlsx 第10行" in report
    assert "时间轴样本: 当前展示 2 步，实际共 5 步" in report
    assert "路径摘要: 该关系簇包含核心成员 2 个、外围成员 1 个" in report


def test_penetration_report_includes_aggregation_focus_ranking(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "aggregation": {
                "summary": {
                    "极高风险实体数": 1,
                    "高风险实体数": 1,
                    "高优先线索实体数": 1,
                },
                "rankedEntities": [
                    {
                        "name": "张三",
                        "riskScore": 88,
                        "riskConfidence": 0.91,
                        "riskLevel": "critical",
                        "highPriorityClueCount": 3,
                        "summary": "存在闭环和第三方中转",
                        "aggregationExplainability": {
                            "top_clues": [
                                {"description": "资金闭环: 张三 → 外围账户B → 张三"}
                            ]
                        },
                    }
                ],
            }
        },
        profiles={"张三": {"has_data": True}},
    )

    report = generator._generate_penetration_report()

    assert "【重点核查对象排序】" in report
    assert "对象名称: 张三" in report
    assert "风险评分: 88.0" in report
    assert "重点线索: 资金闭环: 张三 → 外围账户B → 张三" in report


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
    assert "闭环金额: 当前闭环结果仅输出路径与风险等级" in report


def test_penetration_report_prefers_strong_penetration_cycles_over_related_party_loops(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "relatedParty": {
                "fund_loops": [
                    {
                        "path": "张三 → 弱节点 → 张三",
                        "length": 2,
                        "risk_level": "medium",
                    }
                ]
            },
            "penetration": {
                "analysis_metadata": {
                    "fund_cycles": {
                        "truncated": True,
                        "truncated_reasons": ["timeout"],
                        "timeout_seconds": 30,
                    }
                },
                "fund_cycles": [
                    {
                        "nodes": ["张三", "外围账户B", "外围账户C"],
                        "path": "张三 → 外围账户B → 外围账户C → 张三",
                        "length": 3,
                        "risk_score": 88,
                        "risk_level": "high",
                        "confidence": 0.81,
                        "evidence": ["形成闭环路径", "包含 2 个外围节点"],
                    }
                ]
            },
        },
    )

    report = generator._generate_penetration_report()

    assert "张三 → 外围账户B → 外围账户C → 张三" in report
    assert "张三 → 弱节点 → 张三" not in report
    assert "本次闭环搜索存在截断" in report
    assert "风险评分: 88.0" in report
    assert "置信度: 0.81" in report


def test_penetration_report_includes_discovered_nodes_and_relationship_clusters(tmp_path):
    generator = _make_generator(
        tmp_path,
        analysis_results={
            "relatedParty": {
                "discovered_nodes": [
                    {
                        "name": "外围账户B",
                        "relation_types": ["third_party_relay", "fund_loop"],
                        "linked_cores": ["张三", "李四"],
                        "occurrences": 3,
                        "total_amount": 120000,
                        "risk_score": 76,
                        "risk_level": "high",
                        "confidence": 0.78,
                        "evidence": ["关联类型: 第三方中转、资金闭环", "关联核心对象 2 个"],
                    }
                ],
                "relationship_clusters": [
                    {
                        "cluster_id": "cluster_1",
                        "core_members": ["张三", "李四"],
                        "external_members": ["外围账户B"],
                        "relation_types": ["third_party_relay", "fund_loop"],
                        "direct_flow_count": 1,
                        "relay_count": 2,
                        "loop_count": 1,
                        "total_amount": 240000,
                        "risk_score": 84,
                        "risk_level": "high",
                        "confidence": 0.83,
                        "evidence": ["核心成员 2 个，外围成员 1 个", "直接往来/中转/闭环 = 1/2/1"],
                        "path_explainability": {
                            "summary": "该关系簇包含核心成员 2 个、外围成员 1 个，以中转关系为主",
                            "inspection_points": ["成员构成: 核心 张三、李四 / 外围 外围账户B"],
                            "representative_paths": [
                                {
                                    "path_type": "third_party_relay",
                                    "path": "张三 → 外围账户B → 李四",
                                    "amount": 120000,
                                    "risk_score": 82,
                                    "priority_score": 96.5,
                                    "priority_reason": "类型权重 34；金额 >= 10万；风险评分 82.0",
                                    "path_explainability": {
                                        "summary": "资金在 6.0 小时内经 外围账户B 由 张三 转向 李四，金额差比例 1.1%",
                                        "inspection_points": ["链路路径: 张三 → 外围账户B → 李四"],
                                        "evidence_template": {
                                            "supporting_refs": {
                                                "notice": "当前回传 2 步时间轴事件，实际共 2 步"
                                            }
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        },
    )

    report = generator._generate_penetration_report()

    assert "三、外围节点发现" in report
    assert "外围账户B" in report
    assert "关联核心对象: 张三、李四" in report
    assert "第三方中转、资金闭环" in report
    assert "四、关系簇识别" in report
    assert "关系簇ID: cluster_1" in report
    assert "直接往来/中转/闭环: 1/2/1" in report
    assert "代表路径:" in report
    assert "[第三方中转] 张三 → 外围账户B → 李四" in report
    assert "优先级: 96.5" in report
    assert "摘要: 资金在 6.0 小时内经 外围账户B 由 张三 转向 李四" in report
    assert "证据: 当前回传 2 步时间轴事件，实际共 2 步" in report
    assert "风险评分: 76.0" in report
    assert "风险评分: 84.0" in report
