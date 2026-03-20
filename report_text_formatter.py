#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared human-readable formatting helpers for report artifacts."""

import re
from typing import Any, Dict

_ISO_DATETIME_PATTERN = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})[T ](?P<time>\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)

_APPENDIX_TITLE_MAP = {
    "appendix_a_assets_income": "附录A 资产与收入匹配",
    "appendix_b_income_loan": "附录B 异常收入与借贷",
    "appendix_c_network_penetration": "附录C 关系网络与资金穿透",
    "appendix_d_timeline_behavior": "附录D 时序与行为模式",
    "appendix_e_wallet_supplement": "附录E 电子钱包补证",
}

_QA_CHECK_TITLE_MAP = {
    "html_missing_but_index_points_html": "HTML 正式报告产物可用",
    "person_gap_explanations_visible_in_formal_txt": "TXT 个人收支解释已落地",
    "person_gap_explanations_visible_in_html_report": "HTML 个人收支解释已落地",
    "no_cycle_but_cycle_wording": "循环/团伙表述与证据一致",
    "formal_report_contains_internal_cache_path": "正式报告未暴露内部缓存路径",
    "high_risk_without_minimum_evidence": "高风险问题具备最低证据支撑",
    "high_risk_requires_traceable_evidence_refs": "高风险问题证据可追溯",
    "strong_wording_requires_evidence_support": "强结论表述与证据强度匹配",
    "benign_scenario_promoted_to_high_risk": "良性场景未被误判为高风险",
    "company_dossiers_materialized": "公司卷宗已完成落地",
    "company_issue_overview_materialized": "公司问题总览已完成落地",
    "appendix_formal_titles_consistent": "附录标题与正式章节一致",
    "appendix_formal_counts_coherent": "附录汇总数量与正文一致",
    "risk_levels_normalized": "风险等级口径已统一",
    "company_dossiers_enriched": "公司卷宗摘要信息完整",
}

_QA_PASS_SUMMARY_MAP = {
    "html_missing_but_index_points_html": "已检测到正式 HTML 报告产物，可直接用于预览与交付。",
    "person_gap_explanations_visible_in_formal_txt": "正式 TXT 报告已覆盖全部个人收支差额解释。",
    "person_gap_explanations_visible_in_html_report": "正式 HTML 报告已覆盖全部个人收支差额解释。",
    "no_cycle_but_cycle_wording": "循环或团伙类措辞仅在当前证据支持时出现。",
    "formal_report_contains_internal_cache_path": "正式报告未暴露内部缓存路径或临时目录信息。",
    "high_risk_without_minimum_evidence": "高风险问题均具备最低限度的触发依据与证据引用。",
    "high_risk_requires_traceable_evidence_refs": "高风险问题均附带可回溯的证据索引。",
    "strong_wording_requires_evidence_support": "较强结论措辞已与当前证据强度匹配。",
    "benign_scenario_promoted_to_high_risk": "未将明显良性场景抬升为高风险结论。",
    "company_dossiers_materialized": "涉案公司卷宗产物已生成，可直接纳入正式报告。",
    "company_issue_overview_materialized": "公司问题总览已可供正式报告与前端视图复用。",
    "appendix_formal_titles_consistent": "附录目录标题与正式章节标题保持一致。",
    "appendix_formal_counts_coherent": "附录汇总指标与正式章节细项数量保持一致。",
    "risk_levels_normalized": "问题卡、优先对象和卷宗已使用统一风险等级口径。",
    "company_dossiers_enriched": "公司卷宗已补全角色标签、摘要和统一风险概览。",
}

_QA_WARN_SUMMARY_MAP = {
    "company_dossiers_enriched": "公司卷宗已生成，但仍有摘要或风险概览待补齐。",
}

_QA_FAIL_SUMMARY_MAP = {
    "high_risk_without_minimum_evidence": "仍有高风险问题缺少最低限度的触发依据或证据引用，需先补齐后再定级。",
    "high_risk_requires_traceable_evidence_refs": "仍有高风险问题缺少可回溯证据索引，暂不宜直接用于正式定性。",
    "company_dossiers_enriched": "部分公司卷宗仍缺角色标签、摘要或统一风险概览，需继续补齐。",
}

_QA_DETAIL_LABEL_MAP = {
    "html_files": "HTML 文件",
    "expected_count": "应覆盖数量",
    "keywords": "命中关键词",
    "cycle_evidence_count": "循环证据数量",
    "matched_tokens": "命中措辞",
    "supported_high_risk_issue_count": "证据支撑的高风险问题数",
    "companies_count": "公司数量",
    "appendix_keys": "附录章节",
    "primary_guidance": "目录提示",
    "index_path": "索引文件",
    "exists": "索引已生成",
    "falls_back_to_txt": "已回退TXT",
    "points_to_missing_html": "仍指向缺失HTML",
}


def humanize_report_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    def _replace(match: re.Match[str]) -> str:
        date_text = match.group("date")
        time_text = match.group("time")
        return date_text if time_text == "00:00:00" else f"{date_text} {time_text}"

    return _ISO_DATETIME_PATTERN.sub(_replace, text)


def format_report_datetime(value: Any) -> str:
    return humanize_report_text(value)


def format_report_qa_check_display(item: Dict[str, Any]) -> Dict[str, str]:
    check_id = str(item.get("check_id") or "").strip()
    status = str(item.get("status") or "").strip().lower()
    message = humanize_report_text(item.get("message"))
    details = item.get("details")
    details = details if isinstance(details, dict) else {}

    if check_id == "html_missing_but_index_points_html":
        html_files = details.get("html_files")
        html_files = html_files if isinstance(html_files, list) else []
        if html_files:
            return {
                "title": "HTML 正式报告产物可用",
                "summary": "已检测到正式 HTML 报告产物，可直接用于预览与交付。",
            }
        if details.get("falls_back_to_txt"):
            return {
                "title": "正式报告入口已回退至 TXT",
                "summary": "当前未生成 HTML 报告，但目录清单已正确回退到正式 TXT 报告。",
            }
        if status == "warn":
            return {
                "title": "正式报告入口仍存在 HTML 引导风险",
                "summary": "当前未生成 HTML 报告，目录清单仍可能优先引导到 HTML，需继续收口。",
            }

    title = _QA_CHECK_TITLE_MAP.get(check_id) or (
        check_id.replace("_", " ").strip() or "QA 检查"
    )
    if status == "pass":
        summary = _QA_PASS_SUMMARY_MAP.get(check_id) or "当前检查已通过。"
    elif status == "warn":
        summary = _QA_WARN_SUMMARY_MAP.get(check_id) or "当前检查存在提示项，建议继续收口。"
    elif status == "fail":
        summary = _QA_FAIL_SUMMARY_MAP.get(check_id) or "当前检查未通过，需继续收口后再交付。"
    else:
        summary = message or "当前检查状态待确认。"

    return {"title": title, "summary": summary}


def format_report_qa_detail_label(key: Any) -> str:
    text = str(key or "").strip()
    if not text:
        return "明细"
    return _QA_DETAIL_LABEL_MAP.get(text) or text.replace("_", " ")


def format_report_qa_detail_value(key: Any, value: Any) -> str:
    key_text = str(key or "").strip()
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        items = [format_report_qa_detail_value(key, item) for item in value]
        items = [item for item in items if item]
        return "、".join(items) if items else "无"

    text = humanize_report_text(value)
    if not text:
        return "无"
    if key_text == "appendix_keys":
        return _APPENDIX_TITLE_MAP.get(text, text)
    return text


def humanize_report_artifact_payload(value: Any) -> Any:
    """Recursively humanize saved QA/report artifact payloads."""
    if isinstance(value, dict):
        normalized = {
            str(key): humanize_report_artifact_payload(item)
            for key, item in value.items()
        }
        check_id = str(value.get("check_id") or "").strip()
        status = str(value.get("status") or "").strip().lower()
        if check_id and status:
            display = format_report_qa_check_display(value)
            normalized["title"] = display["title"]
            normalized["message"] = display["summary"]
        return normalized
    if isinstance(value, list):
        return [humanize_report_artifact_payload(item) for item in value]
    if isinstance(value, str):
        return humanize_report_text(value)
    return value
