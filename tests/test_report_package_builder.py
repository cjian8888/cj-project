#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report_package first-phase semantic layer regression tests."""

import json
import os
import shutil
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from investigation_report_builder import InvestigationReportBuilder


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
                "summary": {
                    "total_income": 500000,
                    "total_expense": 200000,
                    "real_income": 400000,
                    "real_expense": 180000,
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
                    "date": "2026-03-16",
                    "description": "大额往来款",
                    "riskLevel": "high",
                    "sourceFile": "张三流水.xlsx",
                    "sourceRowIndex": 88,
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
        assert report_package_path.exists()
        assert summary_path.exists()
        payload = json.loads(report_package_path.read_text(encoding="utf-8"))
        summary_text = summary_path.read_text(encoding="utf-8")

        assert payload["coverage"]["persons_count"] == 1
        assert payload["coverage"]["companies_count"] == 1
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
            payload["appendix_views"]["appendix_c_network_penetration"]["title"]
            == "附录C 关系网络与资金穿透"
        )
        assert (
            payload["appendix_views"]["appendix_index"]["items"][2]["title"]
            == "附录C 关系网络与资金穿透"
        )
        assert (
            payload["appendix_views"]["company_issue_overview"]["items"][0]["next_actions"][0]
            == "调取交易回单、合同及对手方背景材料。"
        )
        assert payload["issues"][0]["issue_id"].startswith(("FLOW-", "CON-"))
        assert "REPORT PACKAGE QA SUMMARY" in summary_text
        assert any(
            issue["category"] == "直接往来"
            and issue["scope"]["company"] == "测试科技有限公司"
            for issue in payload["issues"]
        )
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

        assert checks["html_missing_but_index_points_html"]["status"] == "warn"
        assert checks["formal_report_contains_internal_cache_path"]["status"] == "fail"
        assert checks["no_cycle_but_cycle_wording"]["status"] == "fail"
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
        assert "张三 | 优先级88.0 | 风险critical" in text
        assert "调取交易回单、合同及对手方背景材料。" in text
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
        assert "【测试科技有限公司】" in text
        assert "统一风险: 高风险" in text
        assert "角色标签: 通道节点" in text
        assert "关联人员: 张三" in text
        assert "【正式报告公司问题清单】" in text
        assert "建议动作: 调取交易回单、合同及对手方背景材料。" in text
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
        assert "Summary: total=" in summary_text
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
        assert "张三（critical）" in html or "张三(high)" in html or "张三（high）" in html
        assert "测试科技有限公司发生300,000元直接往来" in html
        assert "调取交易回单、合同及对手方背景材料。" in html
        assert "来源FLOW-001" in html
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
        assert "附录C 关系网络与资金穿透" in html
        assert "涉案公司问题：" in html
        assert "角色标签：" in html
        assert "通道节点" in html
        assert "关联人员：" in html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
