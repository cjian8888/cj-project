#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QA guard for report-package semantic outputs."""

import os
from typing import Any, Dict, List, Optional

from unified_risk_model import build_risk_schema, normalize_risk_level


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _appendix_keys() -> List[str]:
    return [
        "appendix_a_assets_income",
        "appendix_b_income_loan",
        "appendix_c_network_penetration",
        "appendix_d_timeline_behavior",
        "appendix_e_wallet_supplement",
    ]


def _formal_content_counts(appendix_key: str, view: Dict[str, Any]) -> Dict[str, int]:
    summary = _as_dict(view.get("summary"))
    formal = _as_dict(view.get("formal_chapter"))
    if appendix_key == "appendix_a_assets_income":
        return {
            "persons_count": len(_as_list(formal.get("person_gap_items"))),
            "families_count": len(_as_list(formal.get("family_financial_rollup"))),
        }
    if appendix_key == "appendix_b_income_loan":
        return {
            "issue_count": len(_as_list(formal.get("issue_cards"))),
            "focus_entity_count": len(_as_list(formal.get("focus_entity_cards"))),
        }
    if appendix_key == "appendix_c_network_penetration":
        return {
            "priority_entity_count": len(_as_list(formal.get("priority_entities"))),
            "network_issue_count": len(_as_list(formal.get("representative_issues"))),
            "company_hotspot_count": len(_as_list(formal.get("company_hotspots"))),
        }
    if appendix_key == "appendix_d_timeline_behavior":
        return {
            "timeline_issue_count": len(_as_list(formal.get("timeline_cards"))),
            "behavior_entity_count": len(_as_list(formal.get("behavior_cards"))),
        }
    if appendix_key == "appendix_e_wallet_supplement":
        wallet_cards = _as_list(formal.get("wallet_cards"))
        subject_count = max(
            (int(_as_float(_as_dict(item).get("subject_count"))) for item in wallet_cards),
            default=0,
        )
        transaction_count = max(
            (int(_as_float(_as_dict(item).get("transaction_count"))) for item in wallet_cards),
            default=0,
        )
        issue_count = max(
            (int(_as_float(_as_dict(item).get("issue_count"))) for item in wallet_cards),
            default=0,
        )
        return {
            "subject_count": subject_count,
            "transaction_count": transaction_count,
            "issue_count": issue_count,
        }
    return {
        key: int(_as_float(value))
        for key, value in summary.items()
        if isinstance(value, (int, float, str))
    }


def _is_high_risk_issue(issue: Dict[str, Any]) -> bool:
    risk_level = str(issue.get("risk_level") or "").strip().lower()
    severity = _as_float(issue.get("severity"))
    return risk_level in {"high", "critical"} or severity >= 75


def _contains_benign_high_risk_token(text: str) -> List[str]:
    content = str(text or "").strip()
    if not content:
        return []
    tokens = [
        "工资",
        "薪资",
        "社保",
        "理财赎回",
        "理财",
        "自我转账",
        "自转",
        "放心借",
        "白条",
        "消费金融",
        "普通消费",
        "餐饮",
        "家庭往来",
        "报销",
        "网贷放款",
    ]
    return [token for token in tokens if token in content]


def _read_text(path: Optional[str]) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def _count_cycle_evidence(analysis_cache: Dict[str, Any]) -> int:
    derived_data = _as_dict(analysis_cache.get("derived_data"))
    penetration = _as_dict(derived_data.get("penetration"))
    related_party = _as_dict(
        derived_data.get("relatedParty") or derived_data.get("related_party")
    )
    aggregation = _as_dict(derived_data.get("aggregation"))
    count = 0

    fund_cycles = penetration.get("fund_cycles")
    if isinstance(fund_cycles, list):
        count += len(fund_cycles)
    elif isinstance(fund_cycles, dict):
        count += len(_as_list(fund_cycles.get("cycles")))

    count += len(_as_list(related_party.get("fund_cycles")))
    evidence_packs = aggregation.get("evidencePacks")
    if not isinstance(evidence_packs, dict):
        evidence_packs = aggregation.get("evidence_packs", {})
    for pack in evidence_packs.values():
        if not isinstance(pack, dict):
            continue
        evidence = _as_dict(pack.get("evidence"))
        count += len(_as_list(evidence.get("fund_cycles")))
    return count


def _build_check(
    check_id: str,
    status: str,
    message: str,
    *,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "message": message,
        "details": details or {},
    }


def run_report_quality_checks(
    analysis_cache: Dict[str, Any],
    report_package: Dict[str, Any],
    report: Optional[Dict[str, Any]] = None,
    *,
    report_dir: Optional[str] = None,
    formal_report_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run first-phase consistency and hygiene checks."""
    analysis_cache = _as_dict(analysis_cache)
    report_package = _as_dict(report_package)
    report = _as_dict(report)
    report_dir = report_dir or ""
    checks: List[Dict[str, Any]] = []

    html_files: List[str] = []
    if report_dir and os.path.isdir(report_dir):
        html_files = sorted(
            name for name in os.listdir(report_dir) if name.lower().endswith(".html")
        )
    if html_files:
        checks.append(
            _build_check(
                "html_missing_but_index_points_html",
                "pass",
                "HTML report artifacts detected.",
                details={"html_files": html_files},
            )
        )
    else:
        checks.append(
            _build_check(
                "html_missing_but_index_points_html",
                "warn",
                "No HTML report was generated; current index flow still has a known risk of pointing readers to HTML first.",
                details={"html_files": []},
            )
        )

    report_text = _read_text(formal_report_path)
    summary_narrative = str(
        _as_dict(report.get("conclusion")).get("summary_narrative") or ""
    ).strip()
    issue_headlines = [
        str(issue.get("headline") or "").strip()
        for issue in _as_list(report_package.get("issues"))
        if isinstance(issue, dict)
    ]
    combined_text = "\n".join([report_text, summary_narrative] + issue_headlines)
    cycle_mentions = [keyword for keyword in ("闭环", "团伙") if keyword in combined_text]
    cycle_count = _count_cycle_evidence(analysis_cache)
    if cycle_mentions and cycle_count <= 0:
        checks.append(
            _build_check(
                "no_cycle_but_cycle_wording",
                "fail",
                "Cycle or gang wording appears in report narratives, but no cycle evidence was found in the semantic fact layer.",
                details={
                    "keywords": cycle_mentions,
                    "cycle_evidence_count": cycle_count,
                },
            )
        )
    else:
        checks.append(
            _build_check(
                "no_cycle_but_cycle_wording",
                "pass",
                "Cycle wording is consistent with available evidence.",
                details={
                    "keywords": cycle_mentions,
                    "cycle_evidence_count": cycle_count,
                },
            )
        )

    path_hits = [
        token
        for token in (
            "analysis_cache/",
            "analysis_cache\\",
            "output/analysis_cache",
            "output\\analysis_cache",
            "derived_data.json::",
        )
        if token in report_text
    ]
    if path_hits:
        checks.append(
            _build_check(
                "formal_report_contains_internal_cache_path",
                "fail",
                "Formal TXT report leaks internal cache or implementation paths.",
                details={"matched_tokens": path_hits},
            )
        )
    else:
        checks.append(
            _build_check(
                "formal_report_contains_internal_cache_path",
                "pass",
                "Formal TXT report does not expose internal cache paths.",
            )
        )

    high_risk_without_evidence = []
    high_risk_without_traceable_refs = []
    for issue in _as_list(report_package.get("issues")):
        if not isinstance(issue, dict):
            continue
        if not _is_high_risk_issue(issue):
            continue
        issue_id = str(issue.get("issue_id") or "unknown").strip()
        evidence_refs = _as_list(issue.get("evidence_refs"))
        why_flagged = _as_list(issue.get("why_flagged"))
        if not evidence_refs:
            high_risk_without_traceable_refs.append(issue_id)
        if evidence_refs and why_flagged:
            continue
        high_risk_without_evidence.append(issue_id)
    if high_risk_without_evidence:
        checks.append(
            _build_check(
                "high_risk_without_minimum_evidence",
                "fail",
                "High-risk issues exist without minimum supporting rationale or evidence references.",
                details={"issue_ids": high_risk_without_evidence},
            )
        )
    else:
        checks.append(
            _build_check(
                "high_risk_without_minimum_evidence",
                "pass",
                "High-risk issues satisfy minimum evidence/rationale requirements.",
            )
        )

    if high_risk_without_traceable_refs:
        checks.append(
            _build_check(
                "high_risk_requires_traceable_evidence_refs",
                "fail",
                "High-risk issues must carry traceable evidence_refs instead of relying on narrative only.",
                details={"issue_ids": high_risk_without_traceable_refs},
            )
        )
    else:
        checks.append(
            _build_check(
                "high_risk_requires_traceable_evidence_refs",
                "pass",
                "High-risk issues carry traceable evidence references.",
            )
        )

    strong_wording_tokens = [
        token
        for token in (
            "立即启动深入调查程序",
            "明确认定",
            "可以认定",
            "高度怀疑",
        )
        if token in combined_text
    ]
    supported_high_risk_count = 0
    for issue in _as_list(report_package.get("issues")):
        if not isinstance(issue, dict) or not _is_high_risk_issue(issue):
            continue
        if _as_list(issue.get("evidence_refs")) and _as_list(issue.get("why_flagged")):
            supported_high_risk_count += 1
    if strong_wording_tokens and supported_high_risk_count < 2:
        checks.append(
            _build_check(
                "strong_wording_requires_evidence_support",
                "fail",
                "Strong wording appears in report narratives, but the semantic layer does not yet provide enough evidence-supported high-risk issues.",
                details={
                    "matched_tokens": strong_wording_tokens,
                    "supported_high_risk_issue_count": supported_high_risk_count,
                },
            )
        )
    else:
        checks.append(
            _build_check(
                "strong_wording_requires_evidence_support",
                "pass",
                "Strong wording is absent or adequately supported by evidence-rich high-risk issues.",
                details={
                    "matched_tokens": strong_wording_tokens,
                    "supported_high_risk_issue_count": supported_high_risk_count,
                },
            )
        )

    benign_high_risk_hits: List[str] = []
    for issue in _as_list(report_package.get("issues")):
        if not isinstance(issue, dict) or not _is_high_risk_issue(issue):
            continue
        issue_id = str(issue.get("issue_id") or "unknown").strip()
        text = "\n".join(
            [
                str(issue.get("headline") or "").strip(),
                str(issue.get("narrative") or "").strip(),
                "；".join(str(item).strip() for item in _as_list(issue.get("why_flagged"))),
            ]
        )
        matched_tokens = _contains_benign_high_risk_token(text)
        if matched_tokens:
            benign_high_risk_hits.append(
                f"{issue_id}:{'/'.join(matched_tokens)}"
            )
    if benign_high_risk_hits:
        checks.append(
            _build_check(
                "benign_scenario_promoted_to_high_risk",
                "warn",
                "Potentially benign scenarios were promoted into high-risk issue wording and should be manually reviewed.",
                details={"issue_hits": benign_high_risk_hits},
            )
        )
    else:
        checks.append(
            _build_check(
                "benign_scenario_promoted_to_high_risk",
                "pass",
                "No obvious benign-scenario keywords were promoted into high-risk issue wording.",
            )
        )

    coverage = _as_dict(report_package.get("coverage"))
    company_dossiers = _as_list(report_package.get("company_dossiers"))
    companies_count = int(coverage.get("companies_count", 0) or 0)
    if companies_count > 0 and not company_dossiers:
        checks.append(
            _build_check(
                "company_dossiers_materialized",
                "fail",
                "Known companies are present in coverage, but no company dossiers were materialized.",
                details={"companies_count": companies_count},
            )
        )
    else:
        checks.append(
            _build_check(
                "company_dossiers_materialized",
                "pass",
                "Company coverage is materialized in dossier outputs.",
                details={"companies_count": companies_count},
            )
        )

    appendix_views = _as_dict(report_package.get("appendix_views"))
    company_issue_overview = _as_dict(appendix_views.get("company_issue_overview"))
    company_issue_items = _as_list(company_issue_overview.get("items"))
    if companies_count > 0 and not company_issue_items:
        checks.append(
            _build_check(
                "company_issue_overview_materialized",
                "fail",
                "Known companies are present, but the company-first appendix view was not materialized.",
                details={"companies_count": companies_count},
            )
        )
    else:
        checks.append(
            _build_check(
                "company_issue_overview_materialized",
                "pass",
                "Company-first appendix view is available for downstream report rendering.",
                details={"companies_count": companies_count},
            )
        )

    appendix_index = _as_dict(appendix_views.get("appendix_index"))
    appendix_index_lookup = {
        str(item.get("appendix_key") or "").strip(): item
        for item in _as_list(appendix_index.get("items"))
        if isinstance(item, dict) and str(item.get("appendix_key") or "").strip()
    }
    appendix_title_mismatches: List[str] = []
    appendix_count_mismatches: List[str] = []
    for appendix_key in _appendix_keys():
        view = _as_dict(appendix_views.get(appendix_key))
        title = str(view.get("title") or "").strip()
        formal = _as_dict(view.get("formal_chapter"))
        formal_title = str(formal.get("title") or "").strip()
        index_item = _as_dict(appendix_index_lookup.get(appendix_key))
        index_title = str(index_item.get("title") or "").strip()
        if not formal_title:
            appendix_title_mismatches.append(f"{appendix_key}:missing_formal_title")
        elif title and formal_title != title:
            appendix_title_mismatches.append(
                f"{appendix_key}:formal_title={formal_title}|view_title={title}"
            )
        if title and index_title and index_title != title:
            appendix_title_mismatches.append(
                f"{appendix_key}:index_title={index_title}|view_title={title}"
            )

        summary = _as_dict(view.get("summary"))
        for field, formal_count in _formal_content_counts(appendix_key, view).items():
            summary_count = int(_as_float(summary.get(field)))
            if formal_count > 0 and summary_count < formal_count:
                appendix_count_mismatches.append(
                    f"{appendix_key}:{field}:summary={summary_count}<formal={formal_count}"
                )

    if appendix_title_mismatches:
        checks.append(
            _build_check(
                "appendix_formal_titles_consistent",
                "fail",
                "Appendix titles drift between summary/index views and formal chapters.",
                details={"mismatches": appendix_title_mismatches},
            )
        )
    else:
        checks.append(
            _build_check(
                "appendix_formal_titles_consistent",
                "pass",
                "Appendix summary/index titles are aligned with formal chapter titles.",
                details={"appendix_keys": _appendix_keys()},
            )
        )

    if appendix_count_mismatches:
        checks.append(
            _build_check(
                "appendix_formal_counts_coherent",
                "fail",
                "Appendix summary metrics are lower than the content exposed in formal chapters.",
                details={"mismatches": appendix_count_mismatches},
            )
        )
    else:
        checks.append(
            _build_check(
                "appendix_formal_counts_coherent",
                "pass",
                "Appendix summary metrics remain coherent with formal chapter detail counts.",
                details={"appendix_keys": _appendix_keys()},
            )
        )

    allowed_levels = set(build_risk_schema().get("allowed_levels", []))
    invalid_risk_refs: List[str] = []
    for issue in _as_list(report_package.get("issues")):
        if not isinstance(issue, dict):
            continue
        issue_id = str(issue.get("issue_id") or "unknown").strip()
        level = str(issue.get("risk_level") or "").strip().lower()
        if level and level not in allowed_levels:
            invalid_risk_refs.append(f"issue:{issue_id}:{level}")
    for item in _as_list(report_package.get("priority_board")):
        if not isinstance(item, dict):
            continue
        entity_name = str(item.get("entity_name") or "unknown").strip()
        level = str(item.get("risk_level") or "").strip().lower()
        if level and level not in allowed_levels:
            invalid_risk_refs.append(f"priority:{entity_name}:{level}")
    for dossier in company_dossiers + _as_list(report_package.get("person_dossiers")) + _as_list(
        report_package.get("family_dossiers")
    ):
        if not isinstance(dossier, dict):
            continue
        dossier_name = str(
            dossier.get("entity_name") or dossier.get("family_name") or "unknown"
        ).strip()
        overview = _as_dict(dossier.get("risk_overview"))
        level = str(overview.get("risk_level") or "").strip().lower()
        if level and level not in allowed_levels:
            invalid_risk_refs.append(f"dossier:{dossier_name}:{level}")
    if invalid_risk_refs:
        checks.append(
            _build_check(
                "risk_levels_normalized",
                "fail",
                "Semantic report outputs contain non-canonical risk levels.",
                details={"invalid_refs": invalid_risk_refs},
            )
        )
    else:
        checks.append(
            _build_check(
                "risk_levels_normalized",
                "pass",
                "Issue cards, priority board and dossiers all use canonical risk enums.",
            )
        )

    weak_company_dossiers: List[str] = []
    for dossier in company_dossiers:
        if not isinstance(dossier, dict):
            continue
        entity_name = str(dossier.get("entity_name") or "").strip()
        if not entity_name:
            continue
        issue_refs = _as_list(dossier.get("issue_refs"))
        transaction_count = int(dossier.get("transaction_count", 0) or 0)
        role_tags = _as_list(dossier.get("role_tags"))
        summary_text = str(dossier.get("summary") or "").strip()
        overview = _as_dict(dossier.get("risk_overview"))
        risk_level = normalize_risk_level(overview.get("risk_level"), default="low")
        if (issue_refs or transaction_count > 0) and (not role_tags or not summary_text):
            weak_company_dossiers.append(entity_name)
            continue
        if issue_refs and risk_level == "low":
            weak_company_dossiers.append(entity_name)
    if weak_company_dossiers:
        checks.append(
            _build_check(
                "company_dossiers_enriched",
                "warn",
                "Some company dossiers were materialized but still lack role/risk enrichment.",
                details={"companies": weak_company_dossiers},
            )
        )
    else:
        checks.append(
            _build_check(
                "company_dossiers_enriched",
                "pass",
                "Company dossiers contain role tags, summaries and unified risk overviews.",
            )
        )

    summary = {"pass": 0, "warn": 0, "fail": 0}
    for item in checks:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
    summary["total"] = len(checks)

    return {
        "summary": summary,
        "checks": checks,
    }


def render_report_quality_summary_text(report_package: Dict[str, Any]) -> str:
    """Render QA checks into a readable text summary."""
    report_package = _as_dict(report_package)
    qa_checks = _as_dict(report_package.get("qa_checks"))
    summary = _as_dict(qa_checks.get("summary"))
    checks = _as_list(qa_checks.get("checks"))
    meta = _as_dict(report_package.get("meta"))
    coverage = _as_dict(report_package.get("coverage"))

    lines: List[str] = []
    lines.append("=" * 70)
    lines.append("REPORT PACKAGE QA SUMMARY")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Case: {meta.get('case_name') or 'N/A'}")
    lines.append(f"Generated At: {meta.get('generated_at') or 'N/A'}")
    lines.append(
        "Coverage: persons={persons}, companies={companies}, families={families}".format(
            persons=int(coverage.get("persons_count", 0) or 0),
            companies=int(coverage.get("companies_count", 0) or 0),
            families=int(coverage.get("families_count", 0) or 0),
        )
    )
    lines.append("")
    lines.append(
        "Summary: total={total}, pass={passed}, warn={warn}, fail={fail}".format(
            total=int(summary.get("total", len(checks)) or 0),
            passed=int(summary.get("pass", 0) or 0),
            warn=int(summary.get("warn", 0) or 0),
            fail=int(summary.get("fail", 0) or 0),
        )
    )
    lines.append("")
    lines.append("Checks:")

    for item in checks:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown").upper()
        check_id = str(item.get("check_id") or "unknown").strip()
        message = str(item.get("message") or "").strip()
        lines.append(f"- [{status}] {check_id}: {message}")
        details = _as_dict(item.get("details"))
        for key, value in details.items():
            if isinstance(value, list):
                detail_text = ", ".join(str(v) for v in value) if value else "[]"
            else:
                detail_text = str(value)
            lines.append(f"  {key}: {detail_text}")

    lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)
