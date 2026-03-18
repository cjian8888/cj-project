#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build family/person/company dossiers for the unified report package."""

from typing import Any, Dict, Iterable, List, Optional

from unified_risk_model import build_risk_overview, normalize_risk_level


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


def _unique_texts(values: Iterable[Any]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        ordered.append(text)
        seen.add(text)
    return ordered


def _issues_by_scope(issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_scope: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        scope = _as_dict(issue.get("scope"))
        entity_name = str(scope.get("entity") or "").strip()
        company_name = str(scope.get("company") or "").strip()
        family_name = str(scope.get("family") or "").strip()
        if entity_name:
            by_scope.setdefault(f"entity::{entity_name}", []).append(issue)
        if company_name:
            by_scope.setdefault(f"company::{company_name}", []).append(issue)
        if family_name:
            by_scope.setdefault(f"family::{family_name}", []).append(issue)
    return by_scope


def _issue_refs(issue_cards: Iterable[Dict[str, Any]]) -> List[str]:
    return sorted(
        {
            str(item.get("issue_id") or "").strip()
            for item in issue_cards
            if isinstance(item, dict) and str(item.get("issue_id") or "").strip()
        }
    )


def _aggregation_lookup(normalized_facts: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for item in _as_list(normalized_facts.get("aggregation_highlights")):
        if not isinstance(item, dict):
            continue
        entity_name = str(item.get("entity") or "").strip()
        if entity_name:
            lookup[entity_name] = item
    return lookup


def _company_section_lookup(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for item in _as_list(report.get("company_sections")):
        if not isinstance(item, dict):
            continue
        company_name = str(item.get("name") or item.get("company_name") or "").strip()
        if company_name:
            lookup[company_name] = item
    return lookup


def _build_key_issue_cards(
    issue_cards: Iterable[Dict[str, Any]], limit: int = 5
) -> List[Dict[str, Any]]:
    ordered = sorted(
        (item for item in issue_cards if isinstance(item, dict)),
        key=lambda item: (
            -_as_float(item.get("priority")),
            -_as_float(item.get("severity")),
            str(item.get("issue_id") or ""),
        ),
    )
    cards: List[Dict[str, Any]] = []
    for item in ordered[:limit]:
        cards.append(
            {
                "issue_id": str(item.get("issue_id") or "").strip(),
                "category": str(item.get("category") or "").strip(),
                "headline": str(item.get("headline") or item.get("narrative") or "").strip(),
                "risk_level": normalize_risk_level(item.get("risk_level"), default="low"),
                "priority": round(_as_float(item.get("priority")), 1),
            }
        )
    return cards


def _merge_issue_cards(*groups: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()
    for group in groups:
        for item in group:
            if not isinstance(item, dict):
                continue
            issue_id = str(item.get("issue_id") or "").strip()
            if not issue_id or issue_id in seen:
                continue
            merged.append(item)
            seen.add(issue_id)
    return merged


def _extract_company_context(
    company_name: str, company_section: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    section = _as_dict(company_section)
    dimensions = _as_dict(section.get("dimensions"))
    person_transfers = _as_dict(dimensions.get("person_transfers"))
    inter_company_flows = _as_dict(dimensions.get("inter_company_flows"))
    major_counterparties = _as_dict(dimensions.get("major_counterparties"))
    behavioral = _as_dict(dimensions.get("behavioral_patterns"))
    risk_assessment = _as_dict(dimensions.get("risk_assessment"))

    related_persons = _unique_texts(
        item.get("person")
        for item in _as_list(person_transfers.get("transfers"))
        if isinstance(item, dict)
    )
    related_companies = _unique_texts(
        item.get("company") or item.get("name")
        for item in _as_list(inter_company_flows.get("flows"))
        if isinstance(item, dict)
    )

    behavioral_flags: List[str] = []
    fast_in_out = _as_dict(behavioral.get("fast_in_out"))
    structuring = _as_dict(behavioral.get("structuring"))
    if int(fast_in_out.get("total", 0) or 0) > 0:
        behavioral_flags.append(f"快进快出{int(fast_in_out.get('total', 0) or 0)}条")
    if int(structuring.get("total", 0) or 0) > 0:
        behavioral_flags.append(
            f"整进散出/散进整出{int(structuring.get('total', 0) or 0)}条"
        )

    return {
        "company_name": company_name,
        "related_persons": related_persons,
        "related_companies": [item for item in related_companies if item != company_name],
        "major_inflows": _as_list(major_counterparties.get("top_customers"))[:5],
        "major_outflows": _as_list(major_counterparties.get("top_suppliers"))[:5],
        "behavioral_flags": behavioral_flags,
        "behavioral_fast_in_out_total": int(fast_in_out.get("total", 0) or 0),
        "has_company_flows": bool(inter_company_flows.get("has_flows")),
        "legacy_risk_level": risk_assessment.get("level") or section.get("overall_risk_level") or "",
        "legacy_risk_score": risk_assessment.get("score") or section.get("overall_risk_score") or 0,
        "legacy_summary": str(section.get("narrative") or "").strip(),
    }


def _derive_company_role_tags(
    company: Dict[str, Any],
    issue_cards: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> List[str]:
    total_income = _as_float(company.get("total_income", 0))
    total_expense = _as_float(company.get("total_expense", 0))
    transaction_count = int(company.get("transaction_count", 0) or 0)
    related_persons = _as_list(context.get("related_persons"))
    related_companies = _as_list(context.get("related_companies"))
    issue_categories = {
        str(item.get("category") or "").strip() for item in issue_cards if isinstance(item, dict)
    }
    fast_in_out_total = int(context.get("behavioral_fast_in_out_total", 0) or 0)

    tags: List[str] = []
    if total_income > 0 and total_income >= max(total_expense, 1.0) * 1.35:
        tags.append("汇集节点")
    if total_expense > 0 and total_expense >= max(total_income, 1.0) * 1.35:
        tags.append("分发节点")
    if total_income > 0 and total_expense > 0 and transaction_count > 0:
        balance_ratio = min(total_income, total_expense) / max(total_income, total_expense)
        if balance_ratio >= 0.72 or fast_in_out_total > 0:
            tags.append("通道节点")
    if related_persons and (related_companies or context.get("has_company_flows")):
        tags.append("桥接节点")
    if related_persons and (
        "直接往来" in issue_categories
        or "现金碰撞" in issue_categories
        or fast_in_out_total > 0
        or "通道节点" in tags
    ):
        tags.append("疑似利益输送节点")
    return _unique_texts(tags)


def _build_company_summary(
    entity_name: str,
    role_tags: List[str],
    risk_overview: Dict[str, Any],
    related_persons: List[str],
    related_companies: List[str],
    key_issue_cards: List[Dict[str, Any]],
    legacy_summary: str = "",
) -> str:
    parts: List[str] = []
    if role_tags:
        parts.append(f"角色标签为{'、'.join(role_tags)}")
    parts.append(
        f"统一风险为{risk_overview.get('risk_label', '低风险')}，优先级{risk_overview.get('priority_score', 0)}分"
    )
    if related_persons:
        parts.append(f"关联核心人员{len(related_persons)}名")
    if related_companies:
        parts.append(f"关联公司{len(related_companies)}家")
    if key_issue_cards:
        parts.append(f"已归集重点问题{len(key_issue_cards)}项")
    elif legacy_summary:
        parts.append("已回收旧公司分析摘要")
    summary = "；".join(parts)
    if legacy_summary:
        return f"{entity_name}{summary}。{legacy_summary}" if summary else legacy_summary
    return f"{entity_name}{summary}。" if summary else f"{entity_name}已生成公司卷宗。"


def build_report_dossiers(
    normalized_facts: Dict[str, Any],
    report: Optional[Dict[str, Any]] = None,
    issues: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build object-level dossiers from semantic facts and issue cards."""
    normalized_facts = _as_dict(normalized_facts)
    report = _as_dict(report)
    issues = _as_list(issues)

    issue_lookup = _issues_by_scope(issues)
    aggregation_lookup = _aggregation_lookup(normalized_facts)
    company_sections = _company_section_lookup(report)

    family_dossiers: List[Dict[str, Any]] = []
    for family in _as_list(normalized_facts.get("families")):
        if not isinstance(family, dict):
            continue
        family_name = str(family.get("family_name") or family.get("anchor") or "").strip()
        members = _unique_texts(_as_list(family.get("members")))
        member_issue_cards = []
        member_aggregation_scores = []
        member_aggregation_levels = []
        member_aggregation_confidence = []
        for member in members:
            member_issue_cards.extend(issue_lookup.get(f"entity::{member}", []))
            aggregation_item = aggregation_lookup.get(member, {})
            if aggregation_item:
                member_aggregation_scores.append(aggregation_item.get("risk_score", 0))
                member_aggregation_levels.append(aggregation_item.get("risk_level", ""))
                member_aggregation_confidence.append(
                    aggregation_item.get("risk_confidence", 0)
                )
        linked_issues = _merge_issue_cards(
            issue_lookup.get(f"family::{family_name}", []),
            member_issue_cards,
        )
        risk_overview = build_risk_overview(
            linked_issues,
            fallback_score=max((_as_float(item) for item in member_aggregation_scores), default=0.0),
            fallback_level=max(
                member_aggregation_levels,
                key=lambda item: {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}.get(
                    normalize_risk_level(item, default="low"),
                    0,
                ),
                default="low",
            ),
            fallback_confidence=max(
                (_as_float(item) for item in member_aggregation_confidence), default=0.0
            ),
            source="family_dossier",
        )
        family_dossiers.append(
            {
                "family_name": family_name,
                "anchor": str(family.get("anchor") or family_name).strip(),
                "members": members,
                "member_count": int(family.get("member_count", len(members))),
                "pending_members": _unique_texts(_as_list(family.get("pending_members"))),
                "total_income": _as_float(family.get("total_income", 0)),
                "total_expense": _as_float(family.get("total_expense", 0)),
                "risk_overview": risk_overview,
                "key_issue_cards": _build_key_issue_cards(linked_issues),
                "issue_refs": _issue_refs(linked_issues),
            }
        )

    person_dossiers: List[Dict[str, Any]] = []
    for person in _as_list(normalized_facts.get("persons")):
        if not isinstance(person, dict):
            continue
        entity_name = str(person.get("entity_name") or "").strip()
        if not entity_name:
            continue
        linked_issues = _merge_issue_cards(issue_lookup.get(f"entity::{entity_name}", []))
        aggregation_item = aggregation_lookup.get(entity_name, {})
        risk_overview = build_risk_overview(
            linked_issues,
            fallback_score=aggregation_item.get("risk_score", 0),
            fallback_level=aggregation_item.get("risk_level", ""),
            fallback_confidence=aggregation_item.get("risk_confidence", 0),
            source="person_dossier",
        )
        person_dossiers.append(
            {
                "entity_type": "person",
                "entity_name": entity_name,
                "transaction_count": int(person.get("transaction_count", 0) or 0),
                "total_income": _as_float(person.get("total_income", 0)),
                "total_expense": _as_float(person.get("total_expense", 0)),
                "real_income": _as_float(person.get("real_income", 0)),
                "real_expense": _as_float(person.get("real_expense", 0)),
                "family_name": next(
                    (
                        family.get("family_name")
                        for family in family_dossiers
                        if entity_name in _as_list(family.get("members"))
                    ),
                    "",
                ),
                "risk_overview": risk_overview,
                "key_issue_cards": _build_key_issue_cards(linked_issues),
                "issue_refs": _issue_refs(linked_issues),
            }
        )

    company_dossiers: List[Dict[str, Any]] = []
    for company in _as_list(normalized_facts.get("companies")):
        if not isinstance(company, dict):
            continue
        entity_name = str(company.get("entity_name") or "").strip()
        if not entity_name:
            continue
        linked_issues = _merge_issue_cards(
            issue_lookup.get(f"entity::{entity_name}", []),
            issue_lookup.get(f"company::{entity_name}", []),
        )
        company_context = _extract_company_context(
            entity_name,
            company_sections.get(entity_name, {}),
        )
        related_persons = _unique_texts(
            list(company_context.get("related_persons", []))
            + [
                _as_dict(item.get("scope")).get("entity")
                for item in linked_issues
                if _as_dict(item.get("scope")).get("entity")
                and _as_dict(item.get("scope")).get("entity") != entity_name
            ]
        )
        related_companies = _unique_texts(
            list(company_context.get("related_companies", []))
            + [
                _as_dict(item.get("scope")).get("company")
                for item in linked_issues
                if _as_dict(item.get("scope")).get("company")
                and _as_dict(item.get("scope")).get("company") != entity_name
            ]
        )
        aggregation_item = aggregation_lookup.get(entity_name, {})
        risk_overview = build_risk_overview(
            linked_issues,
            fallback_score=aggregation_item.get("risk_score", company_context.get("legacy_risk_score", 0)),
            fallback_level=aggregation_item.get("risk_level", company_context.get("legacy_risk_level", "")),
            fallback_confidence=aggregation_item.get("risk_confidence", 0),
            source="company_dossier",
        )
        role_tags = _derive_company_role_tags(
            company,
            linked_issues,
            {
                **company_context,
                "related_persons": related_persons,
                "related_companies": related_companies,
            },
        )
        key_issue_cards = _build_key_issue_cards(linked_issues)
        company_dossiers.append(
            {
                "entity_type": "company",
                "entity_name": entity_name,
                "transaction_count": int(company.get("transaction_count", 0) or 0),
                "total_income": _as_float(company.get("total_income", 0)),
                "total_expense": _as_float(company.get("total_expense", 0)),
                "role_tags": role_tags,
                "risk_overview": risk_overview,
                "related_persons": related_persons[:10],
                "related_companies": related_companies[:10],
                "major_inflows": _as_list(company_context.get("major_inflows"))[:5],
                "major_outflows": _as_list(company_context.get("major_outflows"))[:5],
                "behavioral_flags": _as_list(company_context.get("behavioral_flags"))[:5],
                "key_issue_cards": key_issue_cards,
                "issue_refs": _issue_refs(linked_issues),
                "summary": _build_company_summary(
                    entity_name,
                    role_tags,
                    risk_overview,
                    related_persons,
                    related_companies,
                    key_issue_cards,
                    legacy_summary=str(company_context.get("legacy_summary") or "").strip(),
                ),
            }
        )

    return {
        "family_dossiers": family_dossiers,
        "person_dossiers": person_dossiers,
        "company_dossiers": company_dossiers,
    }
