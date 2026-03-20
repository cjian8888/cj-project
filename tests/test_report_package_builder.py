#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report_package first-phase semantic layer regression tests."""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from investigation_report_builder import InvestigationReportBuilder
from report_dossier_builder import _build_company_summary
from report_quality_guard import REPORT_QA_GUARD_VERSION, run_report_quality_checks
from report_view_builder import _build_company_brief_summary


def _make_workspace_tmp_dir() -> Path:
    root = Path(__file__).resolve().parents[1] / "output" / "tmp_test_report_package"
    root.mkdir(parents=True, exist_ok=True)
    case_dir = root / f"case_{uuid4().hex}"
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def _make_builder(tmp_path, *, summary_narrative=""):
    analysis_cache = {
        "profiles": {
            "张三": {
                "transactionCount": 12,
                "totalIncome": 500000,
                "totalExpense": 200000,
                "account_layer_summary": {
                    "has_corporate_account_activity": True,
                    "has_mixed_personal_corporate_activity": True,
                    "dominant_layer": "corporate",
                    "note": "该主体名下同时存在个人账户与对公账户流水。",
                    "layers": {
                        "personal": {
                            "total_income": 120000,
                            "total_expense": 80000,
                        },
                        "corporate": {
                            "total_income": 380000,
                            "total_expense": 120000,
                        },
                    },
                },
                "summary": {
                    "total_income": 500000,
                    "total_expense": 200000,
                    "real_income": 400000,
                    "real_expense": 180000,
                    "offset_detail": {
                        "self_transfer": 100000,
                        "self_transfer_expense": 20000,
                        "total_offset": 100000,
                        "offset_meta": {
                            "self_transfer": {
                                "label": "本人账户互转",
                                "income_amount": 100000,
                                "expense_amount": 20000,
                                "confidence": "high",
                            }
                        },
                    },
                },
            },
            "测试科技有限公司": {
                "transactionCount": 8,
                "totalIncome": 800000,
                "totalExpense": 720000,
                "summary": {
                    "total_income": 800000,
                    "total_expense": 720000,
                },
            },
        },
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
            ],
            "aggregation": {
                "summary": {
                    "极高风险实体数": 1,
                    "高风险实体数": 0,
                    "高优先线索实体数": 1,
                },
                "ranked_entities": [
                    {
                        "name": "张三",
                        "risk_score": 88.0,
                        "risk_confidence": 0.82,
                        "risk_level": "critical",
                        "summary": "疑似过账通道；与公司存在直接往来",
                        "aggregation_explainability": {
                            "top_clues": [
                                {"description": "疑似过账通道"},
                                {"description": "与测试科技有限公司发生直接往来"},
                            ]
                        },
                    }
                ],
            },
        },
        "suspicions": {
            "directTransfers": [
                {
                    "from": "张三",
                    "to": "测试科技有限公司",
                    "amount": 300000,
                    "date": "2026-03-16T08:15:30",
                    "description": "大额往来款",
                    "riskLevel": "high",
                    "sourceFile": "张三流水.xlsx",
                    "sourceRowIndex": 88,
                    "transactionId": "TX-TEST-001",
                }
            ]
        },
        "graph_data": {},
        "metadata": {
            "version": "2026.03",
            "generatedAt": "2026-03-18T10:00:00",
            "dataFlow": "cache-first",
        },
        "walletData": {
            "available": True,
            "summary": {
                "subjectCount": 1,
                "alipayTransactionCount": 10,
                "tenpayTransactionCount": 5,
            },
        },
    }
    builder = InvestigationReportBuilder(analysis_cache, output_dir=str(tmp_path))
    report = {
        "meta": {
            "title_subject": "张三",
            "generated_at": "2026-03-18T10:05:00",
            "doc_number": "测试字号",
        },
        "family_sections": [
            {
                "anchor": "张三",
                "family_name": "张三家庭",
                "members": ["张三", "李四"],
                "member_count": 2,
                "family_summary": {"total_income": 400000, "total_expense": 180000},
                "pending_members": [{"name": "李四", "relation": "配偶"}],
            }
        ],
        "company_sections": [{"name": "测试科技有限公司"}],
        "person_sections": [],
        "conclusion": {
            "summary_narrative": summary_narrative,
            "issues": [
                {
                    "person": "张三",
                    "issue_type": "收支异常",
                    "description": "正式报告指出张三存在需核实的大额往来。",
                    "severity": "medium",
                }
            ],
        },
        "next_steps": [],
    }
    return builder, report


def test_generate_complete_txt_report_emits_report_package_and_company_dossier():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)

        report_package_path = reports_dir / "qa" / "report_package.json"
        summary_path = reports_dir / "qa" / "report_consistency_check.txt"
        index_path = reports_dir / "报告目录清单.txt"
        assert report_package_path.exists()
        assert summary_path.exists()
        assert index_path.exists()
        report_text = report_path.read_text(encoding="utf-8")
        payload = json.loads(report_package_path.read_text(encoding="utf-8"))
        summary_text = summary_path.read_text(encoding="utf-8")
        index_text = index_path.read_text(encoding="utf-8")

        assert payload["coverage"]["persons_count"] == 1
        assert payload["coverage"]["companies_count"] == 1
        assert payload["person_dossiers"][0]["account_layer_summary"]["has_corporate_account_activity"] is True
        assert payload["person_dossiers"][0]["account_layer_summary"]["corporate_layer_income"] == 380000
        assert payload["person_dossiers"][0]["account_layer_summary"]["personal_layer_income"] == 120000
        assert payload["priority_board"][0]["entity_name"] == "张三"
        assert any(
            item["entity_name"] == "测试科技有限公司"
            for item in payload["priority_board"]
        )
        assert payload["company_dossiers"][0]["entity_name"] == "测试科技有限公司"
        assert "通道节点" in payload["company_dossiers"][0]["role_tags"]
        assert payload["company_dossiers"][0]["risk_overview"]["risk_level"] == "high"
        assert payload["risk_schema"]["allowed_levels"][0] == "critical"
        assert (
            payload["appendix_views"]["company_issue_overview"]["items"][0]["entity_name"]
            == "测试科技有限公司"
        )
        assert (
            payload["appendix_views"]["appendix_a_assets_income"]["title"]
            == "附录A 资产与收入匹配"
        )
        assert (
            payload["appendix_views"]["appendix_a_assets_income"]["formal_chapter"]["title"]
            == "附录A 资产与收入匹配"
        )
        appendix_a_sections = payload["appendix_views"]["appendix_a_assets_income"][
            "formal_chapter"
        ]["formal_sections"]
        assert appendix_a_sections[0]["title"] == "一、家庭收支匹配概览"
        assert "统一语义层覆盖1名人员、1个家庭" in appendix_a_sections[0]["paragraphs"][0]
        assert (
            payload["appendix_views"]["appendix_a_assets_income"]["formal_chapter"]["recommended_actions"][0]
            == "补调张三家庭中待补成员李四的银行流水和资产资料。"
        )
        assert (
            payload["appendix_views"]["appendix_b_income_loan"]["formal_chapter"]["title"]
            == "附录B 异常收入与借贷"
        )
        appendix_b_view = payload["appendix_views"]["appendix_b_income_loan"]
        assert appendix_b_view["focus_entity_cards"] == appendix_b_view["formal_chapter"][
            "focus_entity_cards"
        ]
        assert appendix_b_view["issue_cards"] == appendix_b_view["formal_chapter"][
            "issue_cards"
        ]
        assert appendix_b_view["recommended_actions"] == appendix_b_view["formal_chapter"][
            "recommended_actions"
        ]
        assert appendix_b_view["focus_entity_cards"][0]["issue_count"] >= 1
        assert appendix_b_view["issue_cards"][0]["headline"]
        assert (
            appendix_b_view["formal_chapter"]["formal_sections"][0]["title"]
            == "一、重点对象与问题分布"
        )
        assert (
            payload["appendix_views"]["appendix_d_timeline_behavior"]["formal_chapter"]["title"]
            == "附录D 时序与行为模式"
        )
        assert (
            payload["appendix_views"]["appendix_d_timeline_behavior"]["formal_chapter"]["formal_sections"][0]["title"]
            == "一、时序与行为状态说明"
        )
        assert (
            payload["appendix_views"]["appendix_e_wallet_supplement"]["formal_chapter"]["title"]
            == "附录E 电子钱包补证"
        )
        assert (
            payload["appendix_views"]["appendix_e_wallet_supplement"]["formal_chapter"]["formal_sections"][0]["title"]
            == "一、电子钱包补证覆盖情况"
        )
        assert (
            payload["appendix_views"]["appendix_c_network_penetration"]["title"]
            == "附录C 关系网络与资金穿透"
        )
        assert (
            payload["appendix_views"]["appendix_c_network_penetration"]["formal_chapter"]["title"]
            == "附录C 关系网络与资金穿透"
        )
        appendix_c_sections = payload["appendix_views"]["appendix_c_network_penetration"][
            "formal_chapter"
        ]["formal_sections"]
        assert appendix_c_sections[0]["title"] == "一、重点对象分层研判"
        assert "统一语义层共识别2个网络重点对象" in appendix_c_sections[0]["paragraphs"][0]
        assert "张三（极高风险，优先级88.0）" in appendix_c_sections[0]["paragraphs"][0]
        assert appendix_c_sections[1]["title"] == "二、代表性关系与穿透链条"
        assert "张三与测试科技有限公司发生300,000元直接往来" in appendix_c_sections[1]["paragraphs"][0]
        assert appendix_c_sections[2]["title"] == "三、公司热点与核查方向"
        assert "角色标签集中于通道节点、疑似利益输送节点" in appendix_c_sections[2]["paragraphs"][0]
        assert (
            payload["appendix_views"]["appendix_c_network_penetration"]["formal_chapter"]["recommended_actions"][0]
            == "调取交易回单、合同及对手方背景材料。"
        )
        assert (
            payload["appendix_views"]["appendix_index"]["items"][2]["title"]
            == "附录C 关系网络与资金穿透"
        )
        assert (
            payload["appendix_views"]["company_issue_overview"]["items"][0]["next_actions"][0]
            == "调取交易回单、合同及对手方背景材料。"
        )
        assert payload["main_report_view"]["issue_count"] >= 1
        assert payload["main_report_view"]["company_issue_count"] == 1
        assert payload["main_report_view"]["high_risk_company_count"] == 1
        assert "统一语义层共归集" in payload["main_report_view"]["summary_narrative"]
        assert (
            payload["main_report_view"]["issues"][0]["why_flagged"][0]
            == "交易日期: 2026-03-16 08:15:30"
        )
        assert payload["issues"][0]["issue_id"].startswith(("FLOW-", "CON-"))
        assert payload["meta"]["generated_at"] == "2026-03-18 10:05:00"
        assert "T" not in str(payload["qa_checks"]["meta"]["generated_at"])
        assert "报告一致性检查摘要" in summary_text
        assert "正式报告入口已回退至 TXT" in summary_text
        assert "当前未生成HTML报告，优先查看'核查结果分析报告.txt'获取正式结论" in index_text
        assert "缓存生成时间: 2026-03-18 10:00:00" in report_text
        assert "缓存生成时间: 2026-03-18T10:00:00" not in report_text
        assert any(
            issue["category"] == "直接往来"
            and issue["scope"]["company"] == "测试科技有限公司"
            for issue in payload["issues"]
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_materializes_family_and_person_dossier_summaries():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)

        report_package_path = reports_dir / "qa" / "report_package.json"
        payload = json.loads(report_package_path.read_text(encoding="utf-8"))

        family_summary = payload["family_dossiers"][0]["summary"]
        person_summary = payload["person_dossiers"][0]["summary"]

        assert "张三家庭已识别成员2名" in family_summary
        assert "待补成员1名" in family_summary
        assert "重点线索：" in family_summary

        assert "张三统一风险为" in person_summary
        assert "交易笔数12笔" in person_summary
        assert "重点线索：" in person_summary
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_materializes_person_financial_gap_explanation():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report["family_sections"][0]["member_sections"] = [
            {
                "name": "张三",
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
                    }
                },
            }
        ]
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)

        report_package_path = reports_dir / "qa" / "report_package.json"
        payload = json.loads(report_package_path.read_text(encoding="utf-8"))
        financial_gap_explanation = payload["person_dossiers"][0]["financial_gap_explanation"]

        assert financial_gap_explanation["income_gap"] == 100000
        assert financial_gap_explanation["expense_gap"] == 20000
        assert "流入侧较真实收入多出10.00万元" in financial_gap_explanation["summary"]
        assert "本人账户互转10.00万" in financial_gap_explanation["summary"]
        assert financial_gap_explanation["income_offset_rows"][0]["label"] == "本人账户互转"
        assert financial_gap_explanation["income_offset_rows"][0]["rule_text"] == "测试规则"
        assert financial_gap_explanation["expense_offset_rows"][0]["amount_wan"] == 2.0
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_materializes_family_and_company_explanations():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)

        report_package_path = reports_dir / "qa" / "report_package.json"
        payload = json.loads(report_package_path.read_text(encoding="utf-8"))

        family_explanation = payload["family_dossiers"][0]["family_financial_explanation"]
        company_explanation = payload["company_dossiers"][0]["company_business_explanation"]

        assert "当前已识别成员2名，待补成员1名" in family_explanation["summary"]
        assert "待补对象为李四" in family_explanation["summary"]
        assert family_explanation["pending_member_count"] == 1
        assert family_explanation["focus_clues"]

        assert "累计流入80.00万、流出72.00万，共8笔交易" in company_explanation["summary"]
        assert "公司资金口径基本平衡，净结余8.00万元" in company_explanation["summary"]
        assert "当前角色标签为通道节点" in company_explanation["summary"]
        assert company_explanation["focus_issue_headlines"][0] == "张三与测试科技有限公司发生300,000元直接往来"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_report_quality_guard_records_known_txt_issues():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(
            tmp_path, summary_narrative="综合研判认为存在闭环团伙风险"
        )
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)

        consistency_path = reports_dir / "qa" / "report_consistency_check.json"
        payload = json.loads(consistency_path.read_text(encoding="utf-8"))
        checks = {item["check_id"]: item for item in payload["checks"]}

        assert checks["html_missing_but_index_points_html"]["status"] == "pass"
        assert checks["formal_report_contains_internal_cache_path"]["status"] == "pass"
        assert checks["no_cycle_but_cycle_wording"]["status"] == "pass"
        assert checks["appendix_formal_titles_consistent"]["status"] == "pass"
        assert checks["appendix_formal_counts_coherent"]["status"] == "pass"
        assert checks["high_risk_requires_traceable_evidence_refs"]["status"] == "pass"
        assert checks["strong_wording_requires_evidence_support"]["status"] == "pass"
        assert checks["benign_scenario_promoted_to_high_risk"]["status"] == "pass"
        assert (
            checks["person_gap_explanations_visible_in_formal_txt"]["status"] == "pass"
        )
        assert (
            checks["person_gap_explanations_visible_in_html_report"]["status"] == "pass"
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_report_quality_guard_fails_when_person_gap_explanation_missing_from_formal_txt():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report_package = builder.build_report_package(report=report)
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"
        report_path.write_text("正式报告正文未包含收支口径说明", encoding="utf-8")

        qa_checks = run_report_quality_checks(
            builder._build_analysis_cache_snapshot(),
            report_package,
            report=report,
            report_dir=str(reports_dir),
            formal_report_path=str(report_path),
        )
        checks = {item["check_id"]: item for item in qa_checks["checks"]}

        assert checks["person_gap_explanations_visible_in_formal_txt"]["status"] == "fail"
        assert (
            "张三"
            in checks["person_gap_explanations_visible_in_formal_txt"]["details"][
                "missing_entities"
            ]
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_report_quality_guard_fails_when_person_gap_explanation_missing_from_html():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report_package = builder.build_report_package(report=report)
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"
        html_path = reports_dir / "初查报告.html"
        summary = report_package["person_dossiers"][0]["financial_gap_explanation"]["summary"]
        report_path.write_text(
            f"正式报告正文\n📌 收支口径说明：{summary}\n", encoding="utf-8"
        )
        html_path.write_text("<html><body><p>HTML报告未包含口径说明</p></body></html>", encoding="utf-8")

        qa_checks = run_report_quality_checks(
            builder._build_analysis_cache_snapshot(),
            report_package,
            report=report,
            report_dir=str(reports_dir),
            formal_report_path=str(report_path),
        )
        checks = {item["check_id"]: item for item in qa_checks["checks"]}

        assert checks["person_gap_explanations_visible_in_formal_txt"]["status"] == "pass"
        assert checks["person_gap_explanations_visible_in_html_report"]["status"] == "fail"
        assert (
            "张三"
            in checks["person_gap_explanations_visible_in_html_report"]["details"][
                "missing_entities"
            ]
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_report_quality_guard_fails_when_appendix_titles_or_counts_drift():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report_package = builder.build_report_package(report=report)
        report_package["appendix_views"]["appendix_a_assets_income"]["formal_chapter"][
            "title"
        ] = "附录A 标题漂移"
        report_package["appendix_views"]["appendix_b_income_loan"]["summary"][
            "issue_count"
        ] = 0

        qa_checks = run_report_quality_checks(
            builder._build_analysis_cache_snapshot(),
            report_package,
            report=report,
        )
        checks = {item["check_id"]: item for item in qa_checks["checks"]}

        assert checks["appendix_formal_titles_consistent"]["status"] == "fail"
        assert checks["appendix_formal_counts_coherent"]["status"] == "fail"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_report_package_downgrades_legacy_high_risk_conclusion_without_traceable_evidence():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report["conclusion"]["issues"] = [
            {
                "person": "张三",
                "issue_type": "收支不匹配",
                "description": "工资收入仅24.6%，远低于正常水平。非工资收入263.22万元，建议结合收入分类结果核实构成",
                "severity": "high",
            }
        ]

        report_package = builder.build_report_package(report=report)
        legacy_issue = next(
            issue for issue in report_package["issues"] if issue["issue_id"].startswith("CON-")
        )
        checks = {item["check_id"]: item for item in report_package["qa_checks"]["checks"]}

        assert legacy_issue["risk_level"] == "medium"
        assert legacy_issue["evidence_refs"] == []
        assert any(
            "暂不提升为高风险结论" in item
            for item in legacy_issue["counter_indicators"]
        )
        assert checks["high_risk_without_minimum_evidence"]["status"] == "pass"
        assert checks["high_risk_requires_traceable_evidence_refs"]["status"] == "pass"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_report_package_moves_benign_direct_transfer_memo_out_of_trigger_basis():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        builder.suspicions["directTransfers"][0]["description"] = "20年工资及备用金"

        report_package = builder.build_report_package(report=report)
        flow_issue = next(
            issue for issue in report_package["issues"] if issue["issue_id"].startswith("FLOW-")
        )

        assert flow_issue["why_flagged"] == ["交易日期: 2026-03-16 08:15:30"]
        assert any(
            "工资/备用金" in item for item in flow_issue["counter_indicators"]
        )
        assert "复核真实性质" in flow_issue["narrative"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_report_package_strips_conflicting_legacy_company_risk_summary():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report["company_sections"] = [
            {
                "name": "测试科技有限公司",
                "narrative": (
                    "测试科技有限公司角色标签为通道节点；统一风险为高风险，优先级81.6分；"
                    "关联核心人员1名；已归集重点问题1项。"
                    "【经营规模】累计资金流入80.00万元，流出72.00万元，涉及8笔交易。"
                    "【风险评分】综合评分25/100分，评级为低风险。主要风险：与核心人员大额资金往来。"
                ),
            }
        ]

        report_package = builder.build_report_package(report=report)
        company_summary = report_package["company_dossiers"][0]["summary"]

        assert "【经营规模】" in company_summary
        assert "综合评分25/100分" not in company_summary
        assert "评级为低风险" not in company_summary
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_company_summary_distinguishes_total_and_representative_issue_counts():
    risk_overview = {
        "risk_level": "high",
        "risk_label": "高风险",
        "priority_score": 81.6,
        "issue_count": 72,
    }
    key_issue_cards = [
        {"issue_id": f"FLOW-{index:03d}", "headline": f"代表问题{index}"}
        for index in range(1, 6)
    ]

    dossier_summary = _build_company_summary(
        "测试科技有限公司",
        ["通道节点"],
        risk_overview,
        ["张三"],
        [],
        key_issue_cards,
    )
    brief_summary = _build_company_brief_summary(
        "测试科技有限公司",
        ["通道节点"],
        risk_overview,
        ["张三"],
        [],
        key_issue_cards,
    )

    assert "全量问题72项" in dossier_summary
    assert "代表问题5项" in dossier_summary
    assert "全量问题72项" in brief_summary
    assert "代表问题5项" in brief_summary


def test_report_quality_guard_fails_on_strong_wording_without_evidence_support():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(
            tmp_path, summary_narrative="建议立即启动深入调查程序"
        )
        report_package = builder.build_report_package(report=report)
        report_package["main_report_view"]["summary_narrative"] = "建议立即启动深入调查程序"
        for issue in report_package["issues"]:
            if str(issue.get("risk_level") or "").strip().lower() in {"high", "critical"}:
                issue["evidence_refs"] = []

        qa_checks = run_report_quality_checks(
            builder._build_analysis_cache_snapshot(),
            report_package,
            report=report,
        )
        checks = {item["check_id"]: item for item in qa_checks["checks"]}

        assert checks["high_risk_without_minimum_evidence"]["status"] == "fail"
        assert checks["high_risk_requires_traceable_evidence_refs"]["status"] == "fail"
        assert checks["strong_wording_requires_evidence_support"]["status"] == "fail"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_report_quality_guard_warns_on_benign_scenario_promoted_to_high_risk():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report_package = builder.build_report_package(report=report)
        for issue in report_package["issues"]:
            if str(issue.get("risk_level") or "").strip().lower() in {"high", "critical"}:
                issue["headline"] = "工资收入出现高风险异常"
                issue["narrative"] = "工资收入存在异常，建议重点核查。"
                issue["why_flagged"] = ["工资月度入账异常"]
                break

        qa_checks = run_report_quality_checks(
            builder._build_analysis_cache_snapshot(),
            report_package,
            report=report,
        )
        checks = {item["check_id"]: item for item in qa_checks["checks"]}

        assert checks["benign_scenario_promoted_to_high_risk"]["status"] == "warn"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_report_quality_guard_does_not_warn_when_benign_token_only_appears_in_rationale():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report_package = builder.build_report_package(report=report)
        for issue in report_package["issues"]:
            if str(issue.get("risk_level") or "").strip().lower() in {"high", "critical"}:
                issue["headline"] = "测试科技有限公司与张三发生300,000元直接往来"
                issue["narrative"] = "20年工资及备用金"
                issue["why_flagged"] = ["工资月度入账异常"]
                break

        qa_checks = run_report_quality_checks(
            builder._build_analysis_cache_snapshot(),
            report_package,
            report=report,
        )
        checks = {item["check_id"]: item for item in qa_checks["checks"]}

        assert checks["benign_scenario_promoted_to_high_risk"]["status"] == "pass"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_prefers_semantic_priority_and_actions():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report["next_steps"] = []
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)
        text = report_path.read_text(encoding="utf-8")

        assert "【语义层优先核查对象】:" in text
        assert "张三 | 优先级88.0 | 极高风险" in text
        assert "数据流口径: 优先复用本地分析缓存" in text
        assert "调取交易回单、合同及对手方背景材料。" in text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_report_package_evidence_refs_use_report_friendly_labels():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report_package = builder.build_report_package(report=report)
        direct_issue = next(
            item for item in (report_package.get("issues") or [])
            if item.get("issue_id") == "FLOW-001"
        )

        assert any("解析记录第88行" in ref for ref in (direct_issue.get("evidence_refs") or []))
        assert any("交易标识" in ref for ref in (direct_issue.get("evidence_refs") or []))
        assert not any("#L" in ref for ref in (direct_issue.get("evidence_refs") or []))
        assert not any("tx:" in ref for ref in (direct_issue.get("evidence_refs") or []))
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_prefers_semantic_main_report_view_over_legacy_conclusion():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report["conclusion"] = {
            "summary_narrative": "旧版综合研判",
            "issues": [
                {
                    "person": "旧对象",
                    "issue_type": "旧问题",
                    "description": "旧版问题描述",
                    "severity": "medium",
                }
            ],
        }
        report_package = builder.build_report_package(report=report)
        report_package["main_report_view"] = {
            "prefer_over_legacy": True,
            "summary_narrative": "语义层综合研判",
            "aggregation_summary": {
                "极高风险实体数": 2,
                "高风险实体数": 1,
                "高优先线索实体数": 3,
            },
            "issues": [
                {
                    "entity_name": "张三",
                    "category": "直接往来",
                    "headline": "语义层问题描述",
                    "risk_label": "高风险",
                }
            ],
        }
        builder._ensure_report_package = lambda report=None, formal_report_path=None: report_package
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)
        text = report_path.read_text(encoding="utf-8")

        assert "【正式报告综合研判】: 语义层综合研判" in text
        assert "【聚合排序】: 极高风险2个，高风险1个，高优先线索实体3个" in text
        assert "张三（直接往来）：语义层问题描述 [高风险]" in text
        assert "【正式报告综合研判】: 旧版综合研判" not in text
        assert "旧对象（旧问题）：旧版问题描述" not in text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_prefers_semantic_summary_and_next_steps_by_default():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report["conclusion"] = {
            "summary_narrative": "旧版综合研判：高风险2项，中风险5项，低风险3项。",
            "issues": [
                {
                    "person": "旧对象",
                    "issue_type": "旧问题",
                    "description": "旧版问题描述",
                    "severity": "medium",
                }
            ],
        }
        report["next_steps"] = [
            {
                "action_text": "旧版建议动作",
                "priority": "高",
                "deadline": "立即",
            }
        ]
        report_package = builder.build_report_package(report=report)
        report_package["main_report_view"]["summary_narrative"] = (
            "统一语义层共归集1项重点问题；其中高风险1项；优先核查对象为张三。"
        )
        report_package["main_report_view"].pop("prefer_over_legacy", None)
        report_package["issues"][0]["next_actions"] = ["调取交易回单、合同及对手方背景材料。"]
        builder._ensure_report_package = lambda report=None, formal_report_path=None: report_package
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)
        text = report_path.read_text(encoding="utf-8")

        assert (
            "【正式报告综合研判】: 统一语义层共归集1项重点问题；其中高风险1项；优先核查对象为张三。"
            in text
        )
        assert "高风险2项，中风险5项，低风险3项" not in text
        assert "【正式报告下一步建议】" in text
        assert "调取交易回单、合同及对手方背景材料。" in text
        assert "旧版建议动作" not in text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_adds_semantic_qa_alerts_and_downgrades_high_risk_recommendation():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        builder.suspicions["hiddenAssets"] = [{"asset_type": "房产"}]
        report_package = builder.build_report_package(report=report)
        report_package["qa_checks"] = {
            "checks": [
                {
                    "check_id": "high_risk_requires_traceable_evidence_refs",
                    "status": "fail",
                    "message": "缺少 traceable evidence refs",
                    "details": {"issue_ids": ["FLOW-001"]},
                },
                {
                    "check_id": "strong_wording_requires_evidence_support",
                    "status": "pass",
                    "message": "强定性措辞当前尚未落盘",
                    "details": {"supported_high_risk_issue_count": 1},
                },
                {
                    "check_id": "benign_scenario_promoted_to_high_risk",
                    "status": "warn",
                    "message": "存在良性场景误升风险",
                    "details": {"issue_hits": ["FLOW-001:工资"]},
                },
            ]
        }
        builder._ensure_report_package = lambda report=None, formal_report_path=None: report_package
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)
        text = report_path.read_text(encoding="utf-8")

        assert "【语义层QA提示】" in text
        assert "高风险问题缺少可追溯证据索引" in text
        assert "存在良性场景被抬升为高风险的可能" in text
        assert "➡ 建议: 先围绕高风险线索补强证据并开展进一步核实" in text
        assert "➡ 建议: 立即启动深入调查程序" not in text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_surfaces_semantic_company_risk():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)
        text = report_path.read_text(encoding="utf-8")

        assert "【语义层公司问题总览】" in text
        assert "【统一语义层附录摘要】" in text
        assert "附录C 关系网络与资金穿透" in text
        assert "附录A 资产与收入匹配" in text
        assert "附录B 异常收入与借贷" in text
        assert "附录D 时序与行为模式" in text
        assert "附录E 电子钱包补证" in text
        assert "【家庭收支与待补成员】" in text
        assert "【个人收支匹配重点】" in text
        assert "【异常收入与借贷重点对象】" in text
        assert "【重点问题卡】" in text
        assert "【一、家庭收支匹配概览】" in text
        assert "【二、个人收支与补证重点】" in text
        assert "【一、重点对象与问题分布】" in text
        assert "【二、证据与复核方向】" in text
        assert "【网络重点对象】" in text
        assert "【代表性关系与穿透问题】" in text
        assert "【涉案公司网络热点】" in text
        assert "【电子钱包补证概览】" in text
        assert "【一、时序与行为状态说明】" in text
        assert "当前未归集到可单列的现金碰撞、时序伴随或行为异常对象" in text
        assert "【一、电子钱包补证覆盖情况】" in text
        assert "【二、补证动作与链路缺口】" in text
        assert "【建议核查动作】" in text
        assert "【一、重点对象分层研判】" in text
        assert "统一语义层共识别2个网络重点对象" in text
        assert "【二、代表性关系与穿透链条】" in text
        assert "【三、公司热点与核查方向】" in text
        assert "【测试科技有限公司】" in text
        assert "统一风险: 高风险" in text
        assert "角色标签: 通道节点" in text
        assert "关联人员: 张三" in text
        assert "【正式报告公司问题清单】" in text
        assert "建议动作: 调取交易回单、合同及对手方背景材料。" in text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_strips_awkward_punctuation_sequences():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        builder.suspicions["directTransfers"][0]["description"] = "20年工资及备用金"
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)
        text = report_path.read_text(encoding="utf-8")

        assert "结合需结合" not in text
        assert "。；" not in text
        assert "。。" not in text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_report_package_appendix_c_formal_chapter_strips_awkward_sentence_joining():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)

        report_package = builder.build_report_package(report=report)
        appendix_c_sections = report_package["appendix_views"]["appendix_c_network_penetration"][
            "formal_chapter"
        ]["formal_sections"]
        formal_text = "\n".join(
            str(paragraph).strip()
            for section in appendix_c_sections
            for paragraph in (section.get("paragraphs") or [])
            if str(paragraph).strip()
        )

        assert "结合需结合" not in formal_text
        assert "。；" not in formal_text
        assert "。。" not in formal_text
        assert "反证/限制包括需结合合同、凭证或业务背景进一步复核。" in formal_text
        assert "建议优先调取交易回单、合同及对手方背景材料。" in formal_text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_prefers_main_report_view_company_items_over_dossier_and_appendix():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report["company_sections"] = [
            {"name": "测试科技有限公司", "narrative": "旧公司章节摘要"}
        ]
        report_package = builder.build_report_package(report=report)
        report_package["company_dossiers"][0]["summary"] = "卷宗旧摘要"
        report_package["company_dossiers"][0]["role_tags"] = ["卷宗角色"]
        report_package["company_dossiers"][0]["related_persons"] = ["卷宗人员"]
        report_package["company_dossiers"][0]["key_issue_cards"] = [
            {"headline": "卷宗旧问题"}
        ]
        report_package["appendix_views"]["company_issue_overview"]["items"] = [
            {
                "entity_name": "测试科技有限公司",
                "risk_level": "high",
                "risk_label": "高风险",
                "summary": "附录旧摘要",
                "role_tags": ["附录角色"],
                "related_persons": ["附录人员"],
                "key_issue_cards": [{"headline": "附录旧问题"}],
                "next_actions": ["附录旧动作。"],
            }
        ]
        report_package["main_report_view"]["company_issue_items"] = [
            {
                "entity_name": "测试科技有限公司",
                "risk_level": "high",
                "risk_label": "高风险",
                "summary": "主视图公司摘要",
                "role_tags": ["主视图角色"],
                "related_persons": ["主视图人员"],
                "related_companies": ["主视图关联公司"],
                "key_issue_cards": [{"headline": "主视图问题"}],
                "issue_refs": ["FLOW-001"],
                "next_actions": ["主视图动作。"],
            }
        ]
        builder._ensure_report_package = (
            lambda report=None, formal_report_path=None: report_package
        )
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)
        text = report_path.read_text(encoding="utf-8")

        assert "主视图公司摘要" in text
        assert "角色标签: 主视图角色" in text
        assert "关联人员: 主视图人员" in text
        assert "重点问题: 主视图问题" in text
        assert "建议动作: 主视图动作。" in text
        assert "附录旧摘要" not in text
        assert "卷宗旧摘要" not in text
        assert "旧公司章节摘要" not in text
        assert "附录角色" not in text
        assert "卷宗角色" not in text
        assert "附录旧问题" not in text
        assert "卷宗旧问题" not in text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_complete_txt_report_uses_company_dossiers_without_legacy_company_sections():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        report["company_sections"] = []
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)
        text = report_path.read_text(encoding="utf-8")

        assert "三、公司资金核查" in text
        assert "【测试科技有限公司】" in text
        assert "统一风险: 高风险" in text
        assert "角色标签: 通道节点" in text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_save_report_package_artifacts_writes_default_analysis_results_qa():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        artifact_paths = builder.save_report_package_artifacts(report=report)

        report_package_path = Path(artifact_paths["report_package_path"])
        consistency_path = Path(artifact_paths["consistency_path"])
        consistency_summary_path = Path(artifact_paths["consistency_summary_path"])

        assert report_package_path.exists()
        assert consistency_path.exists()
        assert consistency_summary_path.exists()
        assert report_package_path.parent.name == "qa"
        assert report_package_path.parent.parent.name == "analysis_results"

        payload = json.loads(report_package_path.read_text(encoding="utf-8"))
        summary_text = consistency_summary_path.read_text(encoding="utf-8")
        assert payload["family_dossiers"][0]["family_name"] == "张三家庭"
        assert payload["person_dossiers"][0]["entity_name"] == "张三"
        assert (
            payload["qa_checks"]["meta"]["qa_guard_version"]
            == REPORT_QA_GUARD_VERSION
        )
        assert (
            payload["artifact_meta"]["qa_guard_version"]
            == REPORT_QA_GUARD_VERSION
        )
        assert payload["artifact_meta"]["package_generated_at"]
        assert payload["artifact_meta"]["source_report_generated_at"]
        assert "检查结论: 共" in summary_text
        assert "报告一致性检查摘要" in summary_text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_save_report_package_artifacts_reuses_existing_default_txt_for_qa_checks():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        reports_dir = tmp_path / "analysis_results"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "核查结果分析报告.txt"

        builder.generate_complete_txt_report(str(report_path), report=report)
        artifact_paths = builder.save_report_package_artifacts(report=report)

        payload = json.loads(
            Path(artifact_paths["report_package_path"]).read_text(encoding="utf-8")
        )
        checks = {item["check_id"]: item for item in payload["qa_checks"]["checks"]}
        txt_check = checks["person_gap_explanations_visible_in_formal_txt"]

        assert txt_check["status"] == "pass"
        assert txt_check["title"] == "TXT 个人收支解释已落地"
        assert (
            txt_check["message"]
            == "正式 TXT 报告已覆盖全部个人收支差额解释。"
        )
        assert "T" not in str(payload["artifact_meta"]["package_generated_at"])
        assert "T" not in str(payload["artifact_meta"]["source_report_generated_at"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_save_report_package_artifacts_aligns_mtime_with_package_generated_at():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, report = _make_builder(tmp_path)
        artifact_paths = builder.save_report_package_artifacts(report=report)

        report_package_path = Path(artifact_paths["report_package_path"])
        consistency_path = Path(artifact_paths["consistency_path"])
        consistency_summary_path = Path(artifact_paths["consistency_summary_path"])
        payload = json.loads(report_package_path.read_text(encoding="utf-8"))
        expected_timestamp = datetime.fromisoformat(
            payload["artifact_meta"]["package_generated_at"].replace("Z", "+00:00")
        ).timestamp()

        for artifact_path in (
            report_package_path,
            consistency_path,
            consistency_summary_path,
        ):
            assert abs(artifact_path.stat().st_mtime - expected_timestamp) < 1.5
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_render_html_report_v3_prefers_report_package_conclusion_and_next_steps():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, _ = _make_builder(tmp_path)
        report = builder.build_report_v5()
        report["next_steps"] = []
        html = builder.render_html_report_v3(report)

        assert "统一语义层重点对象" in html
        assert "张三（极高风险）" in html
        assert "（critical）" not in html
        assert "（high）" not in html
        assert "测试科技有限公司发生300,000元直接往来" in html
        assert "调取交易回单、合同及对手方背景材料。" in html
        assert "来源FLOW-001" in html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_render_html_report_v3_prefers_semantic_main_report_view_summary_over_legacy_conclusion():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, _ = _make_builder(tmp_path)
        report = builder.build_report_v5()
        report["conclusion"] = {
            "summary_narrative": "旧版综合研判",
            "issues": [
                {
                    "person": "旧对象",
                    "issue_type": "旧问题",
                    "description": "旧版问题描述",
                    "severity": "medium",
                }
            ],
        }
        report_package = builder.build_report_package(report=report)
        report_package["main_report_view"] = {
            "prefer_over_legacy": True,
            "summary_narrative": "语义层综合研判",
            "issues": [
                {
                    "entity_name": "张三",
                    "category": "直接往来",
                    "headline": "语义层问题描述",
                }
            ],
        }
        builder._ensure_report_package = lambda report=None, formal_report_path=None: report_package

        html = builder.render_html_report_v3(report)

        assert "正式报告综合研判" in html
        assert "语义层综合研判" in html
        assert "语义层问题描述" in html
        assert html.index("数据来源及完整性声明") < html.index("正式报告综合研判")
        assert html.index("正式报告综合研判") < html.index("统一语义层重点对象")
        assert "旧版综合研判" not in html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_render_html_report_v3_surfaces_semantic_qa_alerts_and_cautious_banner():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, _ = _make_builder(tmp_path)
        report = builder.build_report_v5()
        report.setdefault("conclusion", {})["risk_level"] = "高风险"
        report_package = builder.build_report_package(report=report)
        report_package["qa_checks"] = {
            "checks": [
                {
                    "check_id": "high_risk_requires_traceable_evidence_refs",
                    "status": "fail",
                    "message": "缺少 traceable evidence refs",
                    "details": {"issue_ids": ["FLOW-001"]},
                },
                {
                    "check_id": "strong_wording_requires_evidence_support",
                    "status": "pass",
                    "message": "当前仅 1 项高风险问题具备充分证据",
                    "details": {"supported_high_risk_issue_count": 1},
                },
            ]
        }
        builder._ensure_report_package = lambda report=None, formal_report_path=None: report_package

        html = builder.render_html_report_v3(report)

        assert "语义层QA提示" in html
        assert "高风险问题缺少可追溯证据索引" in html
        assert "当前建议已收敛" in html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_render_html_report_v3_localizes_user_visible_english_terms():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, _ = _make_builder(tmp_path)
        report = builder.build_report_v5()
        member = report["family_sections"][0]["member_sections"][0]
        member.setdefault("data_analysis_section", {})
        member["data_analysis_section"]["large_transfer_analysis"] = {
            "threshold": 10000,
            "inflow": {
                "count": 1,
                "total": 100000,
                "transactions": [],
                "top10_counterparties": [
                    {"counterparty": "甲公司", "amount": 100000, "count": 1}
                ],
            },
            "outflow": {
                "count": 1,
                "total": 80000,
                "transactions": [],
                "top10_counterparties": [
                    {"counterparty": "乙公司", "amount": 80000, "count": 1}
                ],
            },
            "inflow_breakdown": "测试流入构成",
            "inflow_relation": "未见异常关联。",
            "outflow_breakdown": "测试流出构成",
            "outflow_relation": "未见异常关联。",
        }

        report_package = builder.build_report_package(report=report)
        report_package.setdefault("coverage", {})
        report_package["coverage"]["available_external_sources"] = [
            "property",
            "vehicle",
            "wallet",
        ]
        report_package["coverage"]["missing_sources"] = ["immigration"]
        report_package["appendix_views"]["appendix_c_network_penetration"][
            "formal_chapter"
        ]["priority_entities"] = [
            {
                "entity_name": "张三",
                "entity_type": "person",
                "risk_label": "高风险",
                "priority_score": 88.0,
                "family_name": "张三家庭",
                "top_reasons": ["疑似过账通道"],
                "issue_refs": ["FLOW-001"],
            }
        ]
        builder._ensure_report_package = lambda report=None, formal_report_path=None: report_package

        html = builder.render_html_report_v3(report)

        assert "统一语义层已接入来源: 房产、车辆、电子钱包" in html
        assert "仍缺数据源</strong>: 出入境" in html
        assert "主要资金来源对手方前10" in html
        assert "主要资金来源对手方Top 10" not in html
        assert "对象类型：个人" in html
        assert "对象类型：person" not in html
        assert "反洗钱相关问题卡" in html
        assert "征信与 AML 相关问题卡" not in html
        assert "反洗钱预警" in html
        assert "AML预警：0" not in html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_render_html_report_v3_uses_company_dossier_without_legacy_company_sections():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, _ = _make_builder(tmp_path)
        report = builder.build_report_v5()
        report["company_sections"] = []
        html = builder.render_html_report_v3(report)

        assert "测试科技有限公司及相关人员查询数据分析" in html
        assert "统一语义层公司卷宗" in html
        assert "统一语义层附录摘要" in html
        assert "家庭收支与待补成员" in html
        assert "个人收支匹配重点" in html
        assert "一、家庭收支匹配概览" in html
        assert "二、个人收支与补证重点" in html
        assert "异常收入与借贷重点对象" in html
        assert "重点问题卡" in html
        assert "一、重点对象与问题分布" in html
        assert "二、证据与复核方向" in html
        assert "附录D 时序与行为模式" in html
        assert "一、时序与行为状态说明" in html
        assert "附录E 电子钱包补证" in html
        assert "电子钱包补证概览" in html
        assert "一、电子钱包补证覆盖情况" in html
        assert "二、补证动作与链路缺口" in html
        assert "附录C 关系网络与资金穿透" in html
        assert "一、重点对象分层研判" in html
        assert "统一语义层共识别2个网络重点对象" in html
        assert "二、代表性关系与穿透链条" in html
        assert "三、公司热点与核查方向" in html
        assert "网络重点对象" in html
        assert "代表性关系与穿透问题" in html
        assert "涉案公司网络热点" in html
        assert "建议核查动作" in html
        assert "涉案公司问题：" in html
        assert "角色标签：" in html
        assert "通道节点" in html
        assert "关联人员：" in html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_render_html_report_v3_hides_legacy_company_risk_summary_when_semantic_risk_exists():
    tmp_path = _make_workspace_tmp_dir()
    try:
        builder, _ = _make_builder(tmp_path)
        report = builder.build_report_v5()
        report["company_sections"] = [
            {
                "name": "测试科技有限公司",
                "narrative": "旧版公司描述",
                "dimensions": {
                    "risk_assessment": {
                        "summary": "评级为低风险，暂未见明显异常。"
                    }
                },
            }
        ]

        html = builder.render_html_report_v3(report)

        assert "统一风险评级" in html
        assert "高风险" in html
        assert "旧五维评分补充" not in html
        assert "评级为低风险，暂未见明显异常。" not in html
        assert "全部为high风险" not in html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
