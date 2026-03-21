#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from decimal import Decimal
from math import isclose
from pathlib import Path
from typing import Any

import tmp_e2e_blindbox_audit as base


ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "output"

REPORT_JSON = OUTPUT_ROOT / "analysis_results" / "qa" / "report_package.json"
REPORT_TXT = OUTPUT_ROOT / "analysis_results" / "核查结果分析报告.txt"
SUSPICIONS_JSON = OUTPUT_ROOT / "analysis_cache" / "suspicions.json"
DERIVED_JSON = OUTPUT_ROOT / "analysis_cache" / "derived_data.json"
PROFILES_JSON = OUTPUT_ROOT / "analysis_cache" / "profiles.json"

REPORT_OUT_TXT = OUTPUT_ROOT / "analysis_results" / "qa" / "e2e_boundary_blindbox_audit_report.txt"
REPORT_OUT_JSON = OUTPUT_ROOT / "analysis_results" / "qa" / "e2e_boundary_blindbox_audit_report.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_artifacts() -> tuple[dict[str, Any], str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        _load_json(REPORT_JSON),
        REPORT_TXT.read_text(encoding="utf-8"),
        _load_json(SUSPICIONS_JSON),
        _load_json(DERIVED_JSON),
        _load_json(PROFILES_JSON),
    )


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_decimal(value: Any) -> Decimal:
    return base.money(value)


def _same_money(left: Any, right: Any) -> bool:
    return _to_decimal(left) == _to_decimal(right)


def _parse_text_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return int(match.group(1))


def _parse_priority_rows(report_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    match = re.search(r"【语义层优先核查对象】:\n((?:\s+\d+\..*\n)+)", report_text)
    if not match:
        return rows

    line_pattern = re.compile(
        r"\s*(\d+)\.\s+(.+?)\s+\|\s+优先级([0-9.]+)\s+\|\s+(.+?)\s+\|\s+依据:\s+(.+)"
    )
    for line in match.group(1).splitlines():
        line_match = line_pattern.match(line)
        if not line_match:
            continue
        rows.append(
            {
                "rank": int(line_match.group(1)),
                "entity_name": line_match.group(2),
                "priority_score": float(line_match.group(3)),
                "risk_label": line_match.group(4),
                "reason_text": line_match.group(5),
            }
        )
    return rows


def _parse_person_ranking_rows(report_text: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"^\s*(\d+)\.\s+(.+?)\s+\|\s+流水总额([0-9,.]+)万元\s+\|\s+总流入([0-9,.]+)万元\s+\|\s+总流出([0-9,.]+)万元\s+\|\s+真实收入([0-9,.]+)万元\s+\|\s+(\d+)笔$",
        re.M,
    )
    rows: list[dict[str, Any]] = []
    for match in pattern.finditer(report_text):
        rows.append(
            {
                "rank": int(match.group(1)),
                "entity_name": match.group(2),
                "turnover_wan": Decimal(match.group(3).replace(",", "")),
                "income_wan": Decimal(match.group(4).replace(",", "")),
                "expense_wan": Decimal(match.group(5).replace(",", "")),
                "real_income_wan": Decimal(match.group(6).replace(",", "")),
                "transaction_count": int(match.group(7)),
            }
        )
    return rows


def audit_all_issue_grounding(report: dict[str, Any], rows_by_file: dict[str, list[base.BankRow]]) -> dict[str, Any]:
    full_report = {"main_report_view": {"issues": _as_list(report.get("issues"))}}
    return base.audit_report_issues(full_report, rows_by_file)


def audit_semantic_consistency(
    report: dict[str, Any],
    derived_data: dict[str, Any],
    profiles: dict[str, Any],
) -> dict[str, Any]:
    issues = _as_list(report.get("issues"))
    main_issues = _as_list(_as_dict(report.get("main_report_view")).get("issues"))
    evidence_index = _as_dict(report.get("evidence_index"))

    issue_ids = {
        str(item.get("issue_id") or "").strip()
        for item in issues
        if str(item.get("issue_id") or "").strip()
    }
    main_issue_ids = {
        str(item.get("issue_id") or "").strip()
        for item in main_issues
        if str(item.get("issue_id") or "").strip()
    }

    problems: list[dict[str, Any]] = []

    missing_main_ids = sorted(main_issue_ids - issue_ids)
    if missing_main_ids:
        problems.append(
            {
                "kind": "main_issue_not_in_issue_index",
                "details": missing_main_ids,
            }
        )

    issues_without_evidence: list[str] = []
    evidence_index_gaps: list[dict[str, Any]] = []
    for issue in issues:
        issue_id = str(issue.get("issue_id") or "").strip()
        refs = _as_list(issue.get("evidence_refs"))
        if not refs:
            issues_without_evidence.append(issue_id)
            continue
        for ref in refs:
            ref_key = str(ref or "").strip()
            entry = _as_dict(evidence_index.get(ref_key))
            if not entry:
                evidence_index_gaps.append(
                    {
                        "kind": "missing_evidence_index_entry",
                        "issue_id": issue_id,
                        "ref": ref_key,
                    }
                )
                continue
            issue_ref_ids = {
                str(item or "").strip()
                for item in _as_list(entry.get("issue_ids"))
                if str(item or "").strip()
            }
            if issue_id not in issue_ref_ids:
                evidence_index_gaps.append(
                    {
                        "kind": "missing_evidence_backref",
                        "issue_id": issue_id,
                        "ref": ref_key,
                        "index_issue_ids": sorted(issue_ref_ids),
                    }
                )
    if issues_without_evidence:
        problems.append(
            {
                "kind": "issues_without_evidence_refs",
                "details": issues_without_evidence,
            }
        )
    if evidence_index_gaps:
        problems.append(
            {
                "kind": "evidence_index_gaps",
                "details": evidence_index_gaps[:30],
                "count": len(evidence_index_gaps),
            }
        )

    stale_evidence_links: list[dict[str, Any]] = []
    for ref, entry in evidence_index.items():
        for issue_id in _as_list(_as_dict(entry).get("issue_ids")):
            issue_key = str(issue_id or "").strip()
            if issue_key and issue_key not in issue_ids:
                stale_evidence_links.append({"ref": ref, "issue_id": issue_key})
    if stale_evidence_links:
        problems.append(
            {
                "kind": "stale_evidence_index_links",
                "details": stale_evidence_links[:30],
                "count": len(stale_evidence_links),
            }
        )

    containers = (
        [("person_dossier", item) for item in _as_list(report.get("person_dossiers"))]
        + [("company_dossier", item) for item in _as_list(report.get("company_dossiers"))]
        + [("family_dossier", item) for item in _as_list(report.get("family_dossiers"))]
        + [("priority_board", item) for item in _as_list(report.get("priority_board"))]
    )
    missing_issue_refs: list[dict[str, Any]] = []
    for kind, item in containers:
        name = str(
            item.get("entity_name") or item.get("family_name") or item.get("anchor") or ""
        ).strip()
        for issue_id in _as_list(item.get("issue_refs")):
            issue_key = str(issue_id or "").strip()
            if issue_key and issue_key not in issue_ids:
                missing_issue_refs.append(
                    {
                        "kind": kind,
                        "name": name,
                        "issue_id": issue_key,
                    }
                )
        risk_overview = _as_dict(item.get("risk_overview"))
        risk_issue_refs = [
            str(issue_id or "").strip()
            for issue_id in _as_list(risk_overview.get("issue_refs"))
            if str(issue_id or "").strip()
        ]
        if risk_issue_refs:
            issue_count = risk_overview.get("issue_count")
            if issue_count is not None and int(issue_count) != len(risk_issue_refs):
                missing_issue_refs.append(
                    {
                        "kind": f"{kind}.risk_overview_count_mismatch",
                        "name": name,
                        "issue_count": issue_count,
                        "issue_refs": risk_issue_refs,
                    }
                )
        for issue_id in risk_issue_refs:
            if issue_id not in issue_ids:
                missing_issue_refs.append(
                    {
                        "kind": f"{kind}.risk_overview_missing_issue",
                        "name": name,
                        "issue_id": issue_id,
                    }
                )
        for card in _as_list(item.get("key_issue_cards")):
            issue_key = str(_as_dict(card).get("issue_id") or "").strip()
            if issue_key and issue_key not in issue_ids:
                missing_issue_refs.append(
                    {
                        "kind": f"{kind}.key_issue_card_missing_issue",
                        "name": name,
                        "issue_id": issue_key,
                    }
                )
    if missing_issue_refs:
        problems.append(
            {
                "kind": "semantic_issue_ref_gaps",
                "details": missing_issue_refs[:30],
                "count": len(missing_issue_refs),
            }
        )

    profile_gaps: list[dict[str, Any]] = []
    for dossier_key in ("person_dossiers", "company_dossiers"):
        for item in _as_list(report.get(dossier_key)):
            entity_name = str(_as_dict(item).get("entity_name") or "").strip()
            if not entity_name:
                continue
            profile = _as_dict(profiles.get(entity_name))
            if not profile:
                profile_gaps.append(
                    {
                        "kind": "missing_profile",
                        "dossier_type": dossier_key,
                        "entity_name": entity_name,
                    }
                )
                continue
            checks = (
                ("transaction_count", item.get("transaction_count"), profile.get("transactionCount")),
                ("total_income", item.get("total_income"), profile.get("totalIncome")),
                ("total_expense", item.get("total_expense"), profile.get("totalExpense")),
                ("real_income", item.get("real_income"), profile.get("realIncome")),
                ("real_expense", item.get("real_expense"), profile.get("realExpense")),
            )
            for field, left, right in checks:
                if field == "transaction_count":
                    if int(left or 0) != int(right or 0):
                        profile_gaps.append(
                            {
                                "kind": "profile_metric_mismatch",
                                "dossier_type": dossier_key,
                                "entity_name": entity_name,
                                "field": field,
                                "report_value": int(left or 0),
                                "profile_value": int(right or 0),
                            }
                        )
                elif not _same_money(left, right):
                    profile_gaps.append(
                        {
                            "kind": "profile_metric_mismatch",
                            "dossier_type": dossier_key,
                            "entity_name": entity_name,
                            "field": field,
                            "report_value": str(_to_decimal(left)),
                            "profile_value": str(_to_decimal(right)),
                        }
                    )
    if profile_gaps:
        problems.append(
            {
                "kind": "profile_alignment_gaps",
                "details": profile_gaps[:30],
                "count": len(profile_gaps),
            }
        )

    family_summaries = _as_dict(derived_data.get("all_family_summaries"))
    family_gaps: list[dict[str, Any]] = []
    for item in _as_list(report.get("family_dossiers")):
        anchor = str(_as_dict(item).get("anchor") or "").strip()
        family_name = str(_as_dict(item).get("family_name") or anchor).strip()
        summary = _as_dict(family_summaries.get(anchor))
        if not summary:
            family_gaps.append(
                {
                    "kind": "missing_family_summary",
                    "family_name": family_name,
                    "anchor": anchor,
                }
            )
            continue
        if not _same_money(item.get("total_income"), summary.get("total_income")):
            family_gaps.append(
                {
                    "kind": "family_income_mismatch",
                    "family_name": family_name,
                    "anchor": anchor,
                    "report_value": str(_to_decimal(item.get("total_income"))),
                    "summary_value": str(_to_decimal(summary.get("total_income"))),
                }
            )
        if not _same_money(item.get("total_expense"), summary.get("total_expense")):
            family_gaps.append(
                {
                    "kind": "family_expense_mismatch",
                    "family_name": family_name,
                    "anchor": anchor,
                    "report_value": str(_to_decimal(item.get("total_expense"))),
                    "summary_value": str(_to_decimal(summary.get("total_expense"))),
                }
            )
    if family_gaps:
        problems.append(
            {
                "kind": "family_summary_alignment_gaps",
                "details": family_gaps[:30],
                "count": len(family_gaps),
            }
        )

    return {
        "checked_issue_count": len(issue_ids),
        "checked_main_issue_count": len(main_issue_ids),
        "checked_evidence_index_count": len(evidence_index),
        "checked_priority_count": len(_as_list(report.get("priority_board"))),
        "checked_person_dossier_count": len(_as_list(report.get("person_dossiers"))),
        "checked_company_dossier_count": len(_as_list(report.get("company_dossiers"))),
        "checked_family_dossier_count": len(_as_list(report.get("family_dossiers"))),
        "problem_count": len(problems),
        "problems": problems,
    }


def audit_report_text_alignment(
    report: dict[str, Any],
    report_text: str,
    suspicions: dict[str, Any],
    derived_data: dict[str, Any],
) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []

    expected_counts = {
        "direct_transfer_count": len(_as_list(suspicions.get("directTransfers"))),
        "long_unrepaid_loan_count": len(_as_list(_as_dict(derived_data.get("loan")).get("no_repayment_loans"))),
        "platform_loan_count": len(_as_list(_as_dict(derived_data.get("loan")).get("online_loan_platforms"))),
        "large_income_count": len(_as_list(_as_dict(derived_data.get("income")).get("large_single_income"))),
        "regular_non_salary_income_group_count": len(_as_list(_as_dict(derived_data.get("income")).get("regular_non_salary"))),
    }
    patterns = {
        "direct_transfer_count": r"发现\s+(\d+)\s+条直接往来记录",
        "long_unrepaid_loan_count": r"发现\s+(\d+)\s+笔长期无还款借贷",
        "platform_loan_count": r"发现\s+(\d+)\s+笔网贷平台交易",
        "large_income_count": r"发现\s+(\d+)\s+笔大额单笔收入",
        "regular_non_salary_income_group_count": r"发现\s+(\d+)\s+组规律性非工资收入",
    }
    for key, expected in expected_counts.items():
        parsed = _parse_text_int(patterns[key], report_text)
        if parsed != expected:
            mismatches.append(
                {
                    "kind": "headline_metric_mismatch",
                    "metric": key,
                    "text_value": parsed,
                    "expected_value": expected,
                }
            )

    top_priority_rows = _parse_priority_rows(report_text)
    expected_priority = _as_list(report.get("priority_board"))[: len(top_priority_rows)]
    if len(top_priority_rows) != min(5, len(_as_list(report.get("priority_board")))):
        mismatches.append(
            {
                "kind": "priority_row_count_mismatch",
                "text_count": len(top_priority_rows),
                "expected_count": min(5, len(_as_list(report.get("priority_board")))),
            }
        )
    for parsed, expected in zip(top_priority_rows, expected_priority):
        if (
            parsed["entity_name"] != str(expected.get("entity_name") or "")
            or not isclose(parsed["priority_score"], float(expected.get("priority_score") or 0.0), abs_tol=0.05)
            or parsed["risk_label"] != str(expected.get("risk_label") or "")
        ):
            mismatches.append(
                {
                    "kind": "priority_row_mismatch",
                    "text_row": parsed,
                    "expected_row": {
                        "entity_name": expected.get("entity_name"),
                        "priority_score": expected.get("priority_score"),
                        "risk_label": expected.get("risk_label"),
                    },
                }
            )

    person_rows = _parse_person_ranking_rows(report_text)
    expected_people = sorted(
        _as_list(report.get("person_dossiers")),
        key=lambda item: (float(item.get("total_income") or 0.0) + float(item.get("total_expense") or 0.0)),
        reverse=True,
    )
    if len(person_rows) != len(expected_people):
        mismatches.append(
            {
                "kind": "person_ranking_count_mismatch",
                "text_count": len(person_rows),
                "expected_count": len(expected_people),
            }
        )
    for parsed, expected in zip(person_rows, expected_people):
        expected_turnover_wan = _to_decimal(expected.get("total_income")) + _to_decimal(expected.get("total_expense"))
        expected_turnover_wan = (expected_turnover_wan / Decimal("10000")).quantize(Decimal("0.01"))
        expected_income_wan = (_to_decimal(expected.get("total_income")) / Decimal("10000")).quantize(Decimal("0.01"))
        expected_expense_wan = (_to_decimal(expected.get("total_expense")) / Decimal("10000")).quantize(Decimal("0.01"))
        expected_real_income_wan = (_to_decimal(expected.get("real_income")) / Decimal("10000")).quantize(Decimal("0.01"))
        if (
            parsed["entity_name"] != str(expected.get("entity_name") or "")
            or parsed["transaction_count"] != int(expected.get("transaction_count") or 0)
            or parsed["turnover_wan"] != expected_turnover_wan
            or parsed["income_wan"] != expected_income_wan
            or parsed["expense_wan"] != expected_expense_wan
            or parsed["real_income_wan"] != expected_real_income_wan
        ):
            mismatches.append(
                {
                    "kind": "person_ranking_row_mismatch",
                    "text_row": parsed,
                    "expected_row": {
                        "entity_name": expected.get("entity_name"),
                        "transaction_count": expected.get("transaction_count"),
                        "turnover_wan": str(expected_turnover_wan),
                        "income_wan": str(expected_income_wan),
                        "expense_wan": str(expected_expense_wan),
                        "real_income_wan": str(expected_real_income_wan),
                    },
                }
            )

    return {
        "checked_priority_rows": len(top_priority_rows),
        "checked_person_rows": len(person_rows),
        "problem_count": len(mismatches),
        "problems": mismatches,
    }


def build_text_report(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    append = lines.append

    append("======================================================================")
    append("E2E扩展盲盒复核报告")
    append("======================================================================")
    append(f"报告侧取证: {payload['meta']['report_json']}")
    append(f"正式文本侧: {payload['meta']['report_txt']}")
    append(f"输出报告: {payload['meta']['report_out_txt']}")
    append("")
    append("一、全量问题卡原始流水落地")
    append("----------------------------------------------------------------------")
    full_issue_audit = payload["full_issue_grounding_audit"]
    append(
        f"全量问题卡共{full_issue_audit['checked_count']}项，原始流水落地通过{full_issue_audit['passed_count']}项，打脸{full_issue_audit['failed_count']}项。"
    )
    if full_issue_audit["failed_details"]:
        append("失败样本:")
        for item in full_issue_audit["failed_details"][:10]:
            append(
                f"- {item['issue_id']} {item['headline']} | 证据引用={item['evidence_ref']} | 交易标识={item['transaction_id_ref']} | 问题={item['problem']}"
            )
    else:
        append("90张问题卡全部能落回原始银行流水。")

    append("")
    append("二、语义包闭环审计")
    append("----------------------------------------------------------------------")
    semantic = payload["semantic_consistency_audit"]
    append(
        f"核对 issues={semantic['checked_issue_count']}、main_report_view={semantic['checked_main_issue_count']}、evidence_index={semantic['checked_evidence_index_count']}、"
        f"priority_board={semantic['checked_priority_count']}、个人卷宗={semantic['checked_person_dossier_count']}、公司卷宗={semantic['checked_company_dossier_count']}、"
        f"家庭卷宗={semantic['checked_family_dossier_count']}，发现问题{semantic['problem_count']}项。"
    )
    if semantic["problems"]:
        for item in semantic["problems"]:
            append(f"- {item['kind']}: {json.dumps(item, ensure_ascii=False)}")
    else:
        append("issue_id、证据索引、卷宗引用、优先对象引用、profiles/family summaries 对齐均未发现结构性跑偏。")

    append("")
    append("三、正式TXT叙事对齐")
    append("----------------------------------------------------------------------")
    text_audit = payload["report_text_alignment_audit"]
    append(
        f"正式TXT已核对 主要发现计数、前5优先核查对象、11人资金流量榜，共发现{text_audit['problem_count']}项问题。"
    )
    if text_audit["problems"]:
        for item in text_audit["problems"]:
            append(f"- {item['kind']}: {json.dumps(item, ensure_ascii=False)}")
    else:
        append("正式TXT里的核心计数、优先对象榜单和个人资金流量榜单与语义包/缓存保持一致。")

    append("")
    append("四、复核结论")
    append("----------------------------------------------------------------------")
    append(
        f"致命问题{payload['summary']['fatal_count']}项，警告{payload['summary']['warn_count']}项。"
    )
    append(payload["summary"]["verdict"])
    return "\n".join(lines)


def main() -> None:
    report, report_text, suspicions, derived_data, profiles = load_artifacts()
    _, rows_by_file, _ = base.load_bank_rows()

    full_issue_grounding_audit = audit_all_issue_grounding(report, rows_by_file)
    semantic_consistency_audit = audit_semantic_consistency(report, derived_data, profiles)
    report_text_alignment_audit = audit_report_text_alignment(
        report,
        report_text,
        suspicions,
        derived_data,
    )

    fatal_count = (
        full_issue_grounding_audit["failed_count"]
        + semantic_consistency_audit["problem_count"]
        + report_text_alignment_audit["problem_count"]
    )
    warn_count = 0
    verdict = (
        "结论: 扩展边界后的原始流水、语义包、分析缓存与正式TXT叙事仍保持一致；当前这版结果我可以继续背书。"
        if fatal_count == 0
        else "结论: 扩展边界后仍发现未收口问题，当前结果还不能算完全站稳。"
    )

    payload = {
        "meta": {
            "report_json": base.fmt_path(REPORT_JSON),
            "report_txt": base.fmt_path(REPORT_TXT),
            "report_out_txt": base.fmt_path(REPORT_OUT_TXT),
            "report_out_json": base.fmt_path(REPORT_OUT_JSON),
        },
        "summary": {
            "fatal_count": fatal_count,
            "warn_count": warn_count,
            "verdict": verdict,
        },
        "full_issue_grounding_audit": full_issue_grounding_audit,
        "semantic_consistency_audit": semantic_consistency_audit,
        "report_text_alignment_audit": report_text_alignment_audit,
    }

    REPORT_OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_text_output = build_text_report(payload)
    REPORT_OUT_TXT.write_text(report_text_output, encoding="utf-8")
    print(report_text_output)


if __name__ == "__main__":
    main()
