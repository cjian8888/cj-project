#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正式报告关键口径单元测试。"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from investigation_report_builder import (
    InvestigationReportBuilder,
    load_investigation_report_builder,
)
from report_config.primary_targets_schema import (
    AnalysisUnit,
    AnalysisUnitMember,
    PrimaryTargetsConfig,
)


def _make_builder(profile, derived_data=None):
    analysis_cache = {
        "profiles": {"张三": profile},
        "derived_data": derived_data or {},
        "suspicions": {},
        "graph_data": {},
        "metadata": {},
    }
    return InvestigationReportBuilder(analysis_cache, output_dir="output")


def test_build_report_v4_missing_primary_config_logs_info_and_falls_back(monkeypatch, caplog):
    builder = _make_builder({"summary": {}})

    monkeypatch.setattr(
        "report_config.primary_targets_service.PrimaryTargetsService.load_config",
        lambda self: (None, "配置文件不存在"),
    )
    monkeypatch.setattr(
        builder,
        "_build_families_from_config_or_cache",
        lambda all_persons, config=None: {
            "张三": {
                "anchor": "张三",
                "members": ["张三"],
                "unit_type": "individual",
                "member_details": [],
            }
        },
    )
    monkeypatch.setattr(builder, "_build_v4_preface", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        builder, "_build_v4_family_section", lambda family_info: {"member_sections": []}
    )
    monkeypatch.setattr(
        builder, "_build_enhanced_company_section", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(builder, "_build_v4_conclusion", lambda *args, **kwargs: {})
    monkeypatch.setattr(builder, "_build_v4_next_steps", lambda *args, **kwargs: [])

    with caplog.at_level(logging.INFO):
        report = builder.build_report_v4()

    assert report["family_sections"] == [{"member_sections": []}]
    assert any(
        record.levelno == logging.INFO
        and "未加载正式归集配置" in record.message
        for record in caplog.records
    )
    assert not any(
        record.levelno >= logging.WARNING and "归集配置" in record.message
        for record in caplog.records
    )


def test_income_match_analysis_separates_raw_and_real_metrics():
    profile = {
        "summary": {
            "total_income": 1_000_000,
            "total_expense": 800_000,
            "real_income": 700_000,
            "real_expense": 600_000,
            "offset_detail": {
                "self_transfer": 100_000,
                "business_reimbursement": 50_000,
                "offset_meta": {
                    "self_transfer": {
                        "income_amount": 100_000,
                        "confidence": "high",
                    },
                    "business_reimbursement": {
                        "income_amount": 50_000,
                        "confidence": "high",
                    },
                },
            },
        },
        "yearly_salary": {
            "summary": {
                "total": 200_000,
            }
        },
    }

    builder = _make_builder(profile)
    result = builder._build_income_match_analysis_v4("张三", profile)

    assert result["total_inflow"] == 1_000_000
    assert result["total_outflow"] == 800_000
    assert result["real_income"] == 700_000
    assert result["real_expense"] == 600_000
    assert result["salary_total"] == 200_000
    assert result["other_income_wan"] == 50.0
    assert result["expense_income_ratio"] == 0.857
    assert result["offset_rule_rows"][0]["name"] == "本人账户互转"
    assert result["offset_rule_rows"][1]["name"] == "单位报销/业务往来款"


def test_income_match_low_severity_does_not_trigger_report_escalation():
    profile = {
        "summary": {
            "real_income": 1_000_000,
            "real_expense": 1_050_000,
        },
        "yearly_salary": {
            "summary": {
                "total": 600_000,
            }
        },
    }

    builder = _make_builder(profile)
    result = builder._build_income_match_analysis_v4("张三", profile)

    assert result["review_severity"] == "low"
    assert result["need_further_verification"] is False


def test_conclusion_and_next_steps_skip_low_severity_income_match_items():
    builder = _make_builder({"summary": {}})
    person_sections = [
        {
            "name": "低风险人员",
            "data_analysis_section": {
                "income_match_analysis": {
                    "salary_ratio": 60.0,
                    "expense_income_ratio": 1.05,
                    "need_further_verification": False,
                },
                "counterparty_analysis": {
                    "inflow": {"third_party": 0, "total": 1}
                },
                "property_analysis": {"has_data": False, "has_payment_record": True},
            },
            "asset_income_section": {},
        },
        {
            "name": "高风险人员",
            "data_analysis_section": {
                "income_match_analysis": {
                    "salary_ratio": 10.0,
                    "expense_income_ratio": 1.6,
                    "need_further_verification": True,
                    "other_income_wan": 90.0,
                    "real_income_wan": 100.0,
                },
                "counterparty_analysis": {
                    "inflow": {"third_party": 0, "total": 1}
                },
                "property_analysis": {"has_data": False, "has_payment_record": True},
            },
            "asset_income_section": {},
        },
    ]

    conclusion = builder._build_v4_conclusion(person_sections, [])
    next_steps = builder._build_v4_next_steps(person_sections, [])

    assert conclusion["issue_count"] == 1
    assert conclusion["issues"][0]["person"] == "高风险人员"
    assert all("低风险人员" not in item["action_text"] for item in next_steps)
    assert any("高风险人员工资收入占比仅10.0%" in item["action_text"] for item in next_steps)


def test_v4_conclusion_prefers_aggregation_highlights_for_summary():
    builder = _make_builder(
        {"summary": {}},
        derived_data={
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
                        "summary": "存在闭环和中转",
                        "aggregationExplainability": {
                            "top_clues": [
                                {"description": "资金闭环: 张三 → 外围账户B → 张三"}
                            ]
                        },
                    }
                ],
                "evidencePacks": {
                    "张三": {
                        "risk_score": 88,
                        "risk_confidence": 0.91,
                        "risk_level": "critical",
                        "summary": "存在闭环和中转",
                        "high_priority_clue_count": 3,
                        "aggregation_explainability": {
                            "top_clues": [
                                {"description": "资金闭环: 张三 → 外围账户B → 张三"}
                            ]
                        },
                    }
                },
            }
        },
    )

    conclusion = builder._build_v4_conclusion([{"name": "张三", "data_analysis_section": {}}], [])

    assert conclusion["aggregation_highlights"][0]["entity"] == "张三"
    assert any(issue["issue_type"] == "聚合高风险排序" for issue in conclusion["issues"])
    assert "张三(88.0分/置信度0.91)" in conclusion["summary_narrative"]


def test_counterparty_analysis_uses_classification_for_personal_transfer_income():
    profile = {
        "summary": {
            "total_income": 1_000_000,
            "total_expense": 500_000,
            "real_income": 700_000,
            "real_expense": 400_000,
            "offset_detail": {
                "self_transfer": 200_000,
                "wealth_principal": 100_000,
                "family_transfer_in": 0,
                "total_offset": 300_000,
            },
        },
        "yearly_salary": {
            "summary": {
                "total": 200_000,
            }
        },
        "fund_flow": {
            "cash_income": 50_000,
            "cash_expense": 10_000,
        },
        "income_classification": {
            "unknown_details": [
                {
                    "amount": 150_000,
                    "counterparty": "李四",
                    "reason": "个人转账",
                }
            ],
            "classification_basis": "real_income_basis",
            "reason_breakdown": {
                "legitimate": {"工资性收入": 200_000},
                "unknown": {"个人转账": 150_000},
            },
            "business_reimbursement_income": 10_000,
        },
    }
    derived_data = {
        "large_transactions": [
            {
                "person": "张三",
                "counterparty": "王五",
                "direction": "income",
                "amount": 5_000_000,
            },
            {
                "person": "张三",
                "counterparty": "赵六",
                "direction": "expense",
                "amount": 60_000,
            },
        ]
    }

    builder = _make_builder(profile, derived_data=derived_data)
    result = builder._build_counterparty_analysis_v4("张三", profile)

    assert result["inflow"]["total"] == 1_000_000
    assert result["inflow"]["real_total"] == 700_000
    assert result["inflow"]["personal_transfers"] == 150_000
    assert result["inflow"]["raw_values"]["other"] == 600_000
    assert result["inflow"]["deduct_values"]["other"] == 300_000
    assert result["inflow"]["real_values"]["other"] == 350_000
    assert "个人转账15.00万元" in result["inflow"]["narrative"]
    assert "总资金流入100.00万元" in result["inflow"]["narrative"]
    assert result["classification_basis"] == "real_income_basis"
    assert result["classification_rule_rows"][0]["name"] == "合法收入"
    assert result["classification_rule_rows"][1]["name"] == "来源待核实收入"
    assert "工资性收入20.00万元" in result["classification_rule_rows"][0]["rules"]


def test_real_income_composition_rows_sum_to_real_income():
    profile = {
        "summary": {
            "real_income": 1_054_082.40,
        },
        "yearly_salary": {
            "summary": {
                "total": 42_620.59,
            }
        },
        "income_classification": {
            "legitimate_income": 67_346.71,
            "unknown_income": 986_735.69,
            "suspicious_income": 0,
            "reason_breakdown": {
                "legitimate": {
                    "工资性收入": 38_200,
                    "工资性收入(机构/代发单位)": 29_000,
                    "投资收益": 146.71,
                },
                "unknown": {
                    "来源不明": 412_700,
                    "第三方支付小额转入": 386_735.69,
                    "个人转账": 187_300,
                },
            },
        },
    }

    builder = _make_builder(profile)
    result = builder._build_real_income_composition_rows(profile)

    assert result["real_income_wan"] == 105.41
    assert sum(item["amount"] for item in result["rows"]) == result["real_income"]
    assert result["rows"][0]["name"] == "工资性收入"
    assert result["rows"][0]["amount"] == 42_620.59
    assert any(item["name"] == "来源不明" for item in result["rows"])
    assert any(item["name"] == "第三方支付小额转入" for item in result["rows"])


def test_report_title_subject_prefers_first_family_anchor():
    builder = _make_builder({"summary": {}})
    preface = {"persons_queried": ["彭伟"]}
    family_sections = [{"family_name": "彭水生家庭", "anchor_name": "彭水生"}]
    person_sections = [{"name": "彭伟"}]

    assert (
        builder._derive_report_title_subject(family_sections, person_sections, preface)
        == "彭水生"
    )


def test_build_personal_background_filters_invalid_employer_and_falls_back():
    profile = {"id_info": {"employer": "上海交大"}}
    derived_data = {
        "family_tree": {
            "张三": [
                {
                    "姓名": "张三",
                    "出生日期": "19900101",
                    "籍贯": "上海市",
                    "从业单位": "待业",
                    "职业": "无业",
                }
            ]
        }
    }

    builder = _make_builder(profile, derived_data=derived_data)
    result = builder._build_personal_background("张三", profile)

    assert result["employer"] == "上海交大"


def test_build_personal_background_suppresses_non_employer_text():
    profile = {"id_info": {}}
    derived_data = {
        "family_tree": {
            "张三": [
                {
                    "姓名": "张三",
                    "出生日期": "19900101",
                    "籍贯": "上海市",
                    "从业单位": "机械工程及自动化",
                    "职业": "无业",
                }
            ]
        }
    }

    builder = _make_builder(profile, derived_data=derived_data)
    result = builder._build_personal_background("张三", profile)

    assert result["employer"] == "信息待补充"


def test_build_salary_income_uses_actual_salary_year_span():
    profile = {
        "yearly_salary": {
            "yearly": {
                "2024": {"total": 100_000},
                "2025": {"total": 200_000},
            },
            "summary": {
                "total": 300_000,
                "avg_monthly": 12_500,
            },
        }
    }
    builder = InvestigationReportBuilder(
        {
            "profiles": {"张三": profile},
            "derived_data": {},
            "suspicions": {},
            "graph_data": {},
            "metadata": {"date_range": {"start": "2020-01-01", "end": "2026-12-31"}},
        },
        output_dir="output",
    )

    result = builder._build_salary_income_v4("张三", profile)

    assert result["start_year"] == "2024"
    assert result["end_year"] == "2025"
    assert "张三2024年至2025年共取得工资收入30.00万元" in result["narrative"]
    assert "2026年" not in result["narrative"]


def test_build_report_v4_prefers_injected_primary_config_over_disk_fallback():
    profile = {"summary": {}}
    builder = InvestigationReportBuilder(
        {
            "profiles": {"张三": profile},
            "derived_data": {},
            "suspicions": {},
            "graph_data": {},
            "metadata": {},
        },
        output_dir="output",
    )
    config = PrimaryTargetsConfig(
        analysis_units=[
            AnalysisUnit(
                anchor="张三",
                members=["张三"],
                member_details=[
                    AnalysisUnitMember(
                        name="张三",
                        relation="本人",
                    )
                ],
            )
        ],
        include_companies=[],
        doc_number="测试文号",
    )

    builder.set_primary_config(config)
    report = builder.build_report_v4()

    assert report["meta"]["doc_number"] == "测试文号"
    assert report["meta"]["title_subject"] == "张三"
    assert report["family_sections"][0]["family_name"] == "张三"
    assert report["person_sections"][0]["name"] == "张三"


def test_build_family_data_from_config_includes_external_property_and_vehicle_assets():
    builder = InvestigationReportBuilder(
        {
            "profiles": {
                "张三": {
                    "has_data": True,
                    "summary": {"net_flow": 0},
                    "wealth_management": {"estimated_holding": 0},
                    "vehicles": [{"号牌号码": "沪A12345"}],
                }
            },
            "derived_data": {},
            "suspicions": {},
            "graph_data": {},
            "metadata": {"id_to_name_map": {"310101199001010011": "张三"}},
            "precisePropertyData": {
                "310101199001010011": [{"location": "测试路1号101室"}]
            },
            "vehicleData": {
                "310101199001010011": [{"号牌号码": "沪A12345"}]
            },
        },
        output_dir="output",
    )
    config = PrimaryTargetsConfig(
        analysis_units=[
            AnalysisUnit(
                anchor="张三",
                members=["张三"],
                unit_type="family",
            )
        ]
    )

    family_data = builder._build_family_data_from_config(config)
    summary = family_data["all_family_summaries"]["张三"]["total_assets"]

    assert summary["property_count"] == 1
    assert summary["vehicle_count"] == 1


def test_load_builder_keeps_valid_profiles_when_first_entity_has_no_income(tmp_path):
    cache_dir = tmp_path / "analysis_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    (cache_dir / "profiles.json").write_text(
        json.dumps(
            {
                "待补成员": {"summary": {}},
                "张三": {"totalIncome": 10000, "summary": {"total_income": 10000}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for filename, payload in {
        "derived_data.json": {},
        "suspicions.json": {},
        "graph_data.json": {},
        "metadata.json": {"persons": ["张三"], "companies": []},
    }.items():
        (cache_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    builder = load_investigation_report_builder(str(tmp_path))

    assert builder is not None
    assert "张三" in builder.profiles
    assert builder.profiles["张三"]["totalIncome"] == 10000


def test_load_builder_reads_phase2_external_cache_files(tmp_path):
    cache_dir = tmp_path / "analysis_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "profiles.json": {
            "张三": {"totalIncome": 10000, "summary": {"total_income": 10000}}
        },
        "derived_data.json": {},
        "suspicions.json": {},
        "graph_data.json": {},
        "metadata.json": {"id_to_name_map": {"310101199001010011": "张三"}},
        "flightData.json": {
            "310101199001010011": {"completed": [{"flight_no": "MU5123"}]}
        },
        "railwayData.json": {
            "310101199001010011": {"tickets": [{"train_no": "G123"}]}
        },
        "coaddressData.json": {
            "310101199001010011": [{"name": "李四", "id_number": "310101199002020022"}]
        },
    }
    for filename, payload in files.items():
        (cache_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    builder = load_investigation_report_builder(str(tmp_path))

    assert builder is not None
    travel = builder._get_external_travel_data("张三")
    assert travel["flight"]["completed"][0]["flight_no"] == "MU5123"
    assert travel["railway"]["tickets"][0]["train_no"] == "G123"
    assert builder._external_coaddress_cache["310101199001010011"][0]["name"] == "李四"


def test_counterparty_analysis_prefers_reason_breakdown_amount_over_truncated_details():
    profile = {
        "summary": {
            "total_income": 1_000_000,
            "total_expense": 100_000,
            "real_income": 500_000,
            "real_expense": 80_000,
            "offset_detail": {
                "self_transfer": 500_000,
                "wealth_principal": 0,
                "family_transfer_in": 0,
                "total_offset": 500_000,
            },
        },
        "yearly_salary": {"summary": {"total": 100_000}},
        "fund_flow": {"cash_income": 0, "cash_expense": 0},
        "income_classification": {
            "reason_breakdown": {
                "unknown": {
                    "个人转账": 200_000,
                    "来源不明": 200_000,
                }
            },
            "unknown_details": [
                {
                    "amount": 150_000,
                    "counterparty": "李四",
                    "reason": "个人转账",
                }
            ],
        },
    }

    builder = _make_builder(profile)
    result = builder._build_counterparty_analysis_v4("张三", profile)

    assert result["inflow"]["personal_transfers"] == 200_000
    assert "个人转账20.00万元" in result["inflow"]["narrative"]


def test_person_section_income_classification_reads_current_field_names():
    profile = {
        "summary": {
            "real_income": 500_000,
        },
        "yearly_salary": {
            "summary": {
                "total": 120_000,
            }
        },
        "income_classification": {
            "legitimate_income": 300_000,
            "unknown_income": 150_000,
            "suspicious_income": 50_000,
        },
    }

    builder = _make_builder(profile)
    result = builder._build_person_section_3_income("张三", profile)

    assert result["income_classification"]["legitimate"] == 300_000
    assert result["income_classification"]["unknown"] == 150_000
    assert result["income_classification"]["suspicious"] == 50_000


def test_fund_flow_analysis_uses_current_unknown_income_metric():
    profile = {
        "summary": {
            "real_income": 500_000,
        },
        "yearly_salary": {
            "summary": {
                "total": 50_000,
            }
        },
        "income_classification": {
            "unknown_income": 200_000,
        },
    }

    builder = _make_builder(profile)
    result = builder._analyze_fund_flow("张三", profile)

    assert result.risk_level in {"medium", "high"}
    assert "来源待核实收入20.0万元" in result.narrative


def test_family_section_prefers_member_details_relation_consistently():
    profiles = {
        "张三": {"summary": {"real_income": 100000, "real_expense": 80000}},
        "李四": {
            "summary": {
                "real_income": 80000,
                "real_expense": 50000,
                "total_income": 80000,
                "total_expense": 50000,
            },
            "yearly_salary": {"summary": {"total": 30000}},
        },
    }
    builder = InvestigationReportBuilder(
        {
            "profiles": profiles,
            "derived_data": {
                "family_units_v2": [
                    {
                        "anchor": "张三",
                        "members": ["张三", "李四"],
                        "member_details": [
                            {"name": "张三", "relation": "本人"},
                            {"name": "李四", "relation": "配偶"},
                        ],
                    }
                ]
            },
            "suspicions": {},
            "graph_data": {},
            "metadata": {},
        },
        output_dir="output",
    )
    builder.set_primary_config(
        PrimaryTargetsConfig(
            analysis_units=[
                AnalysisUnit(
                    anchor="张三",
                    members=["张三", "李四"],
                    unit_type="family",
                    member_details=[
                        AnalysisUnitMember(name="张三", relation="本人", has_data=True),
                        AnalysisUnitMember(name="李四", relation="配偶", has_data=True),
                    ],
                )
            ]
        )
    )

    family_section = builder._build_v4_family_section(
        {
            "anchor": "张三",
            "members": ["张三", "李四"],
            "unit_type": "family",
            "member_details": [
                {"name": "张三", "relation": "本人"},
                {"name": "李四", "relation": "配偶"},
            ],
        }
    )

    assert family_section["members"] == ["张三", "李四"]
    assert family_section["family_summary"]["member_relations"][1]["relation"] == "配偶"
    assert family_section["member_sections"][1]["relation"] == "配偶"


def test_family_section_keeps_pending_members_without_profiles():
    profiles = {
        "张三": {"summary": {"real_income": 100000, "real_expense": 80000}},
    }
    builder = InvestigationReportBuilder(
        {
            "profiles": profiles,
            "derived_data": {},
            "suspicions": {},
            "graph_data": {},
            "metadata": {},
        },
        output_dir="output",
    )

    family_section = builder._build_v4_family_section(
        {
            "anchor": "张三",
            "members": ["张三", "李四", "王五"],
            "unit_type": "family",
            "member_details": [
                {"name": "张三", "relation": "本人", "has_data": True},
                {"name": "李四", "relation": "配偶", "has_data": False},
                {"name": "王五", "relation": "子女", "has_data": False},
            ],
        }
    )

    assert family_section["members"] == ["张三", "李四", "王五"]
    assert [m["name"] for m in family_section["pending_members"]] == ["李四", "王五"]
    assert family_section["pending_members"][0]["relation"] == "配偶"


def test_get_effective_family_units_filters_ghost_units_without_profile_overlap():
    builder = InvestigationReportBuilder(
        {
            "profiles": {
                "候海焱": {"summary": {"real_income": 1000, "real_expense": 500}},
            },
            "derived_data": {
                "family_units_v2": [
                    {
                        "anchor": "侯海焱",
                        "householder": "侯海焱",
                        "members": ["侯海焱", "周伟", "周天健"],
                    },
                    {
                        "anchor": "候海焱",
                        "householder": "候海焱",
                        "members": ["候海焱"],
                    },
                ],
                "all_family_summaries": {
                    "候海焱": {
                        "householder": "候海焱",
                        "family_members": ["候海焱"],
                    }
                },
            },
            "suspicions": {},
            "graph_data": {},
            "metadata": {},
        },
        output_dir="output",
    )

    effective_units = builder._get_effective_family_units()

    assert len(effective_units) == 1
    assert effective_units[0]["anchor"] == "候海焱"
    assert effective_units[0]["members"] == ["候海焱"]


def test_complete_txt_report_marks_real_metrics_and_pending_members(tmp_path):
    profiles = {
        "张三": {
            "transactionCount": 12,
            "summary": {
                "total_income": 500000,
                "total_expense": 300000,
                "real_income": 400000,
                "real_expense": 200000,
                "offset_detail": {
                    "self_transfer": 100000,
                    "offset_meta": {
                        "self_transfer": {
                            "income_amount": 100000,
                            "confidence": "high",
                        }
                    },
                },
            },
            "yearly_salary": {
                "yearly": {"2024": {"total": 120000, "transaction_count": 12}},
                "summary": {"total": 120000, "years": 1},
            },
            "income_classification": {
                "unknown_income": 50000,
                "classification_basis": "real_income_basis",
                "reason_breakdown": {
                    "legitimate": {"工资性收入": 120000},
                    "unknown": {"个人转账": 50000},
                },
            },
        }
    }
    builder = InvestigationReportBuilder(
        {
            "profiles": profiles,
            "derived_data": {
                "family_units_v2": [
                    {
                        "anchor": "张三",
                        "members": ["张三", "李四"],
                        "member_details": [
                            {"name": "张三", "relation": "本人", "has_data": True},
                            {"name": "李四", "relation": "配偶", "has_data": False},
                        ],
                    }
                ]
            },
            "suspicions": {},
            "graph_data": {},
            "metadata": {},
        },
        output_dir=str(tmp_path),
    )

    report_path = tmp_path / "核查结果分析报告.txt"
    builder.generate_complete_txt_report(str(report_path))
    text = report_path.read_text(encoding="utf-8")

    assert "家庭真实收入: 40.00 万元" in text
    assert "家庭真实支出: 20.00 万元" in text
    assert "待补数据成员: 李四" in text
    assert "真实收入40.00万元" in text
    assert "原始流入50.00万元" in text
    assert "真实收入剔除依据" in text
    assert "本人账户互转: 10.00万元，置信度高" in text
    assert "真实收入构成分析" in text
    assert "工资性收入: 12.00万元" in text
    assert "来源待核实收入5.0万元" in text
    assert "来源不明收入5.0万元" not in text


def test_travel_analysis_uses_phase2_profile_fields_and_correlation_results():
    profile = {
        "flight_records": {"completed": [{"flight_no": "MU5123"}]},
        "railway_records": {"tickets": [{"train_no": "G123"}]},
        "hotel_records": [{"hotel_name": "某酒店", "stay_date": "2024-01-12"}],
    }
    derived_data = {
        "correlation": {
            "travel_companions": {
                "fund_correlations": [
                    {
                        "person": "张三",
                        "companion": "李四",
                        "travel_type": "航班",
                        "travel_date": "2024-01-10",
                        "transaction_date": "2024-01-12",
                        "amount": 50000,
                        "direction": "income",
                        "timing": "先同行后收款",
                        "risk_level": "high",
                    }
                ],
                "companion_summary": {
                    "李四": {
                        "count": 3,
                        "persons": ["张三"],
                        "is_multi_person": False,
                        "risk_level": "high",
                    }
                },
            },
            "hotel_cohabitants": {
                "fund_correlations": [
                    {
                        "person": "张三",
                        "cohabitant": "王五",
                        "stay_date": "2024-01-12",
                        "transaction_date": "2024-01-13",
                        "amount": 20000,
                        "direction": "expense",
                        "timing": "先同住后付款",
                        "risk_level": "medium",
                    }
                ],
                "cohabitants": [{"person": "张三", "cohabitant": "王五"}],
            },
        }
    }

    builder = _make_builder(profile, derived_data=derived_data)
    result = builder._build_travel_analysis_v4("张三", profile)

    assert result["flight_count"] == 1
    assert result["railway_count"] == 1
    assert result["hotel_count"] == 1
    assert result["travel_correlation_count"] == 1
    assert result["hotel_correlation_count"] == 1
    assert result["high_frequency_count"] == 1
    assert result["travel_fund_correlations"][0]["companion"] == "李四"
    assert result["hotel_fund_correlations"][0]["cohabitant"] == "王五"
    assert result["has_suspicious_travel"] is True
    assert "同行资金碰撞1条" in result["narrative"]
    assert "同住宿资金碰撞1条" in result["narrative"]


def test_travel_analysis_excludes_single_non_multi_companion_from_high_frequency_summary():
    profile = {
        "hotel_records": [{"hotel_name": "某酒店", "stay_date": "2024-01-12"}],
    }
    derived_data = {
        "correlation": {
            "travel_companions": {
                "fund_correlations": [],
                "companion_summary": {
                    "李四": {
                        "count": 1,
                        "persons": ["张三"],
                        "is_multi_person": False,
                        "risk_level": "medium",
                    }
                },
            },
            "hotel_cohabitants": {
                "fund_correlations": [],
                "cohabitants": [],
            },
        }
    }

    builder = _make_builder(profile, derived_data=derived_data)
    result = builder._build_travel_analysis_v4("张三", profile)

    assert result["high_frequency_count"] == 0
    assert result["high_frequency_companions"] == []
    assert "高频或多人同行对象" not in result["narrative"]


def test_render_html_report_v3_formats_dates_and_property_area_cleanly():
    profile = {
        "entityName": "张三",
        "summary": {
            "total_income": 100000,
            "total_expense": 50000,
            "real_income": 80000,
            "real_expense": 40000,
            "salary_ratio": 0.25,
        },
        "yearly_salary": {
            "summary": {"total": 20000},
            "yearly": {},
            "details": [],
        },
        "properties": [
            {
                "location": "东明路355弄61号302室",
                "area": "124.70平方米",
                "register_date": "2024-01-02T00:00:00",
                "ownership_type": "单独所有",
            }
        ],
        "bank_accounts_official": [],
        "bank_accounts": [],
        "vehicles": [],
        "transactions": [],
        "coaddress_persons": [],
        "coviolation_vehicles": [],
    }
    derived_data = {
        "correlation": {
            "travel_companions": {
                "fund_correlations": [
                    {
                        "person": "张三",
                        "companion": "李四",
                        "travel_type": "航班",
                        "travel_date": 20240105,
                        "transaction_date": "2024-01-06T13:14:15",
                        "amount": 50000,
                        "timing": "先同行后收款",
                        "risk_level": "high",
                    }
                ],
                "companion_summary": {
                    "李四": {
                        "count": 2,
                        "persons": ["张三"],
                        "is_multi_person": False,
                        "risk_level": "high",
                    }
                },
            },
            "hotel_cohabitants": {
                "fund_correlations": [],
                "cohabitants": [],
            },
        }
    }

    builder = _make_builder(profile, derived_data=derived_data)
    section = builder.build_v4_person_section("张三")
    report = {
        "meta": {
            "doc_number": "测试字号",
            "generation_options": {"sections": ["assets", "risks"]},
            "title_subject": "张三",
        },
        "preface": {},
        "family_sections": [],
        "person_sections": [section],
        "company_sections": [],
    }

    html = builder.render_html_report_v3(report)

    assert "124.70平方米平方米" not in html
    assert "房屋面积124.70平方米" in html
    assert "2024-01-02T00:00:00" not in html
    assert "2024-01-02" in html
    assert "20240105" not in html
    assert "2024-01-05" in html
    assert "2024-01-06T13:14:15" not in html
    assert "2024-01-06 13:14:15" in html


def test_related_party_analysis_includes_coaddress_and_coviolation_clues():
    profile = {
        "coaddress_persons": [
            {
                "name": "李四",
                "id_number": "310101199002020022",
                "relation_to_head": "配偶",
                "hukou_address": "上海市闵行区某路1号",
                "employer": "某公司",
            }
        ],
        "coviolation_vehicles": [
            {
                "name": "王五",
                "id_number": "310101199003030033",
                "plate_number": "沪A12345",
                "violation_count": 2,
            }
        ],
    }

    builder = _make_builder(profile)
    result = builder._build_person_section_7_related_party("张三", profile)

    assert result["bidirectional_relations"] == []
    assert result["coaddress_relations"][0]["name"] == "李四"
    assert result["coaddress_relations"][0]["relation_to_head"] == "配偶"
    assert result["coviolation_relations"][0]["plate_number"] == "沪A12345"
    assert result["residence_relation_summary"] == "同住址1人，同车违章1条。"
    assert "识别同住址关系1人" in result["narrative"]

def test_fund_flow_analysis_without_suspicious_counterparty_uses_fallback_wording():
    profile = {
        "summary": {"real_income": 500_000},
        "income_classification": {
            "unknown_income": 200_000,
            "reason_breakdown": {"unknown": {"来源不明": 50_000}},
        },
        "yearly_salary": {"summary": {"total": 50_000}},
    }

    builder = _make_builder(profile)
    result = builder._analyze_fund_flow("张三", profile)

    assert "来源待核实收入20.0万元" in result.narrative
    assert "狭义来源不明5.0万元" in result.narrative
    assert "0笔" not in result.narrative


def test_generate_complete_txt_report_prefers_provided_report_object(tmp_path):
    profile = {
        "summary": {
            "total_income": 500000,
            "total_expense": 250000,
            "real_income": 400000,
            "real_expense": 200000,
            "offset_detail": {
                "self_transfer": 100000,
                "offset_meta": {
                    "self_transfer": {
                        "income_amount": 100000,
                        "confidence": "high",
                    }
                },
            },
        },
        "transactionCount": 12,
    }
    builder = _make_builder(profile)
    report = {
        "meta": {"title_subject": "张三"},
        "family_sections": [
            {
                "anchor": "张三",
                "family_name": "张三",
                "members": ["张三", "李四"],
                "member_count": 2,
                "family_summary": {
                    "total_income": 400000,
                    "total_expense": 200000,
                },
                "pending_members": [{"name": "李四", "relation": "配偶"}],
                "member_sections": [
                    {
                        "name": "张三",
                        "relation": "本人",
                        "asset_income_section": {
                            "salary_income": {
                                "total": 120000,
                                "avg_yearly": 120000,
                                "years_count": 1,
                                "yearly_breakdown": {
                                    "2024": {"total": 120000, "transaction_count": 12}
                                },
                            }
                        },
                        "data_analysis_section": {
                            "income_match_analysis": {
                                "offset_rule_rows": [
                                    {
                                        "name": "本人账户互转",
                                        "amount_wan": 10.0,
                                        "confidence_text": "高",
                                        "rule_text": "测试规则",
                                    }
                                ]
                            },
                            "counterparty_analysis": {
                                "real_income_composition": {
                                    "rows": [
                                        {
                                            "name": "工资性收入",
                                            "amount_wan": 12.0,
                                            "ratio": 30.0,
                                            "note": "严格工资口径",
                                        }
                                    ],
                                    "real_income_wan": 40.0,
                                }
                            },
                        },
                        "unified_analysis": {
                            "overview": {"risk_level": "low", "risk_score": 18},
                            "key_findings": [
                                {"description": "测试发现", "impact": "需持续关注"}
                            ],
                        },
                    }
                ],
            }
        ],
        "company_sections": [],
        "conclusion": {
            "summary_narrative": "这是正式报告综合研判",
            "issues": [
                {
                    "person": "张三",
                    "issue_type": "收支不匹配",
                    "description": "测试问题",
                    "severity": "medium",
                }
            ],
        },
        "next_steps": [
            {
                "action_text": "测试建议",
                "priority": "高",
                "deadline": "7日内",
            }
        ],
    }

    report_path = tmp_path / "核查结果分析报告.txt"
    builder.generate_complete_txt_report(str(report_path), report=report)
    text = report_path.read_text(encoding="utf-8")

    assert "家庭成员数: 2 人" in text
    assert "待补数据成员: 李四" in text
    assert "测试发现（影响：需持续关注）" in text
    assert "这是正式报告综合研判" in text
    assert "测试建议（优先级高，期限7日内）" in text


def test_generate_complete_txt_report_includes_aggregation_highlights(tmp_path):
    builder = _make_builder({"summary": {}})
    report = {
        "meta": {"doc_number": "测试", "generated_at": "2026-03-14T12:00:00"},
        "preface": {"persons_queried": ["张三"], "companies_queried": []},
        "family_sections": [],
        "person_sections": [],
        "company_sections": [],
        "conclusion": {
            "summary_narrative": "聚合排序识别出重点对象",
            "issues": [],
            "aggregation_summary": {
                "极高风险实体数": 1,
                "高风险实体数": 1,
                "高优先线索实体数": 2,
            },
            "aggregation_highlights": [
                {"entity": "张三", "risk_score": 88.0},
                {"entity": "李四", "risk_score": 72.0},
            ],
        },
        "next_steps": [],
    }

    report_path = tmp_path / "aggregation_report.txt"
    builder.generate_complete_txt_report(str(report_path), report=report)
    text = report_path.read_text(encoding="utf-8")

    assert "【聚合排序】: 极高风险1个，高风险1个，高优先线索实体2个" in text
    assert "聚合排序识别重点对象: 张三(88.0分)、李四(72.0分)" in text


def test_income_expense_match_uses_non_salary_wording_not_unknown_income():
    profile = {
        "summary": {
            "real_income": 1_898_402.51,
            "real_expense": 1_008_709.74,
        },
        "yearly_salary": {
            "summary": {
                "total": 42_620.59,
            }
        },
        "income_classification": {
            "unknown_income": 986_735.69,
        },
    }

    builder = _make_builder(profile)
    result = builder._analyze_income_expense_match("张三", profile)

    assert "非工资收入185.58万元" in result.narrative
    assert "185.58万元来源不明" not in result.narrative


def test_property_analysis_marks_missing_value_without_wan_placeholder():
    profile = {
        "properties": [
            {
                "房地坐落": "上海市某路1号",
                "登记时间": "2024-01-01",
                "共有人名称": "李四,310101199001010000",
            }
        ]
    }

    builder = _make_builder(profile)
    result = builder._build_property_analysis_v4("张三", profile)

    assert result["has_data"] is True
    assert result["value_available"] is False
    assert result["value_text"] == "成交价信息缺失"
    assert "房产总交易价格信息缺失" in result["narrative"]


def test_build_family_summary_v5_uses_yuan_inputs_and_outputs_wan():
    builder = InvestigationReportBuilder(
        {
            "profiles": {},
            "derived_data": {},
            "suspicions": {},
            "graph_data": {},
            "metadata": {},
        },
        output_dir="output",
    )

    result = builder._build_family_summary_v5(
        [
            {
                "member_sections": [{"name": "张三"}],
                "family_overview": {
                    "assets_overview": {
                        "property_value": 500_000,
                        "bank_balance": 100_000,
                        "wealth_holding": 50_000,
                    }
                },
            }
        ]
    )

    assert result["total_assets_summary"]["property_value_wan"] == 50.0
    assert result["total_assets_summary"]["bank_balance_wan"] == 10.0
    assert result["total_assets_summary"]["wealth_holding_wan"] == 5.0
    assert result["total_assets_summary"]["total_assets_wan"] == 65.0
    assert "总资产约65.0万元" in result["narrative"]
