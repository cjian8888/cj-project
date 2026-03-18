#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the unified semantic report package and appendix views."""

from typing import Any, Dict, Iterable, List, Optional

from unified_risk_model import build_risk_schema, normalize_risk_level, risk_level_label


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


def _issue_sort_key(item: Dict[str, Any]) -> Any:
    return (
        -_as_float(item.get("priority")),
        -_as_float(item.get("severity")),
        str(item.get("issue_id") or ""),
    )


def _dossier_sort_key(item: Dict[str, Any]) -> Any:
    overview = _as_dict(item.get("risk_overview"))
    return (
        -_as_float(overview.get("priority_score")),
        -_as_float(overview.get("confidence")),
        str(item.get("entity_name") or item.get("family_name") or ""),
    )


def _issue_lookup(issues: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_id = str(issue.get("issue_id") or "").strip()
        if issue_id:
            lookup[issue_id] = issue
    return lookup


def _issue_brief(issue: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "issue_id": str(issue.get("issue_id") or "").strip(),
        "category": str(issue.get("category") or "").strip(),
        "headline": str(issue.get("headline") or issue.get("narrative") or "").strip(),
        "risk_level": normalize_risk_level(issue.get("risk_level"), default="low"),
        "risk_label": risk_level_label(issue.get("risk_level")),
        "priority": round(_as_float(issue.get("priority")), 1),
        "severity": round(_as_float(issue.get("severity")), 1),
    }


def _item_count(view: Dict[str, Any]) -> int:
    for key in ("item_count", "total_count"):
        if key in view:
            return int(_as_float(view.get(key)))
    items = _as_list(view.get("items"))
    if items:
        return len(items)
    summary = _as_dict(view.get("summary"))
    for key in (
        "item_count",
        "total_count",
        "issue_count",
        "companies_with_issues",
        "subject_count",
        "entity_count",
    ):
        if key in summary:
            return int(_as_float(summary.get(key)))
    return 0


def _build_suspicion_summary(
    normalized_facts: Dict[str, Any], issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    counts = _as_dict(normalized_facts.get("suspicion_summary"))
    non_zero_items = [
        {"name": key, "count": int(_as_float(value))}
        for key, value in counts.items()
        if int(_as_float(value)) > 0
    ]
    non_zero_items.sort(key=lambda item: (-item["count"], item["name"]))
    return {
        "title": "疑点命中概览",
        "summary": {
            "total_hits": sum(item["count"] for item in non_zero_items),
            "issue_card_count": len(issues),
            "active_buckets": len(non_zero_items),
        },
        "counts": {key: int(_as_float(value)) for key, value in counts.items()},
        "items": non_zero_items,
    }


def _build_aggregation_summary(
    normalized_facts: Dict[str, Any], priority_board: List[Dict[str, Any]]
) -> Dict[str, Any]:
    highlights = []
    for item in _as_list(normalized_facts.get("aggregation_highlights"))[:10]:
        if not isinstance(item, dict):
            continue
        entity_name = str(item.get("entity") or "").strip()
        if not entity_name:
            continue
        highlights.append(
            {
                "entity_name": entity_name,
                "entity_type": str(item.get("entity_type") or "").strip(),
                "risk_score": round(_as_float(item.get("risk_score")), 1),
                "risk_confidence": round(_as_float(item.get("risk_confidence")), 2),
                "risk_level": normalize_risk_level(item.get("risk_level"), default="low"),
                "risk_label": risk_level_label(item.get("risk_level")),
                "summary": str(item.get("summary") or "").strip(),
                "top_clues": _unique_texts(_as_list(item.get("top_clues")))[:3],
            }
        )
    summary = _as_dict(normalized_facts.get("aggregation_summary"))
    return {
        "title": "聚合排序概览",
        "summary": {
            **summary,
            "priority_board_count": len(priority_board),
            "highlight_count": len(highlights),
        },
        "items": highlights,
    }


def _build_company_issue_overview(
    issue_payload: Dict[str, Any], dossier_payload: Dict[str, Any]
) -> Dict[str, Any]:
    issues = sorted(
        (
            issue
            for issue in _as_list(issue_payload.get("issues"))
            if isinstance(issue, dict)
        ),
        key=_issue_sort_key,
    )
    issue_lookup = _issue_lookup(issues)
    company_dossiers = sorted(
        (
            dossier
            for dossier in _as_list(dossier_payload.get("company_dossiers"))
            if isinstance(dossier, dict)
        ),
        key=_dossier_sort_key,
    )

    items: List[Dict[str, Any]] = []
    high_risk_company_count = 0
    companies_with_issues = 0
    for dossier in company_dossiers:
        entity_name = str(dossier.get("entity_name") or "").strip()
        if not entity_name:
            continue
        risk_overview = _as_dict(dossier.get("risk_overview"))
        risk_level = normalize_risk_level(risk_overview.get("risk_level"), default="low")
        if risk_level in {"critical", "high"}:
            high_risk_company_count += 1

        linked_issues = [
            issue_lookup[issue_id]
            for issue_id in _as_list(dossier.get("issue_refs"))
            if issue_id in issue_lookup
        ]
        if linked_issues:
            companies_with_issues += 1
        next_actions = _unique_texts(
            action
            for issue in linked_issues
            for action in _as_list(issue.get("next_actions"))
        )[:5]
        key_issue_cards = _as_list(dossier.get("key_issue_cards"))[:5]
        if not key_issue_cards and linked_issues:
            key_issue_cards = [_issue_brief(issue) for issue in linked_issues[:5]]

        items.append(
            {
                "entity_name": entity_name,
                "risk_level": risk_level,
                "risk_label": str(risk_overview.get("risk_label") or risk_level_label(risk_level)),
                "priority_score": round(_as_float(risk_overview.get("priority_score")), 1),
                "confidence": round(_as_float(risk_overview.get("confidence")), 2),
                "role_tags": _unique_texts(_as_list(dossier.get("role_tags")))[:8],
                "summary": str(dossier.get("summary") or "").strip(),
                "issue_refs": _unique_texts(_as_list(dossier.get("issue_refs"))),
                "related_persons": _unique_texts(_as_list(dossier.get("related_persons")))[:10],
                "related_companies": _unique_texts(_as_list(dossier.get("related_companies")))[:10],
                "key_issue_cards": key_issue_cards,
                "next_actions": next_actions,
            }
        )

    return {
        "title": "公司问题总览",
        "summary": {
            "company_count": len(items),
            "companies_with_issues": companies_with_issues,
            "high_risk_company_count": high_risk_company_count,
        },
        "items": items,
    }


def _build_appendix_a_assets_income(
    normalized_facts: Dict[str, Any], dossier_payload: Dict[str, Any]
) -> Dict[str, Any]:
    families = _as_list(normalized_facts.get("families"))
    coverage = _as_dict(normalized_facts.get("coverage"))
    person_dossiers = sorted(
        (
            dossier
            for dossier in _as_list(dossier_payload.get("person_dossiers"))
            if isinstance(dossier, dict)
        ),
        key=_dossier_sort_key,
    )

    items: List[Dict[str, Any]] = []
    negative_gap_count = 0
    for dossier in person_dossiers:
        entity_name = str(dossier.get("entity_name") or "").strip()
        if not entity_name:
            continue
        real_income = _as_float(
            dossier.get("real_income")
            if dossier.get("real_income") not in (None, "")
            else dossier.get("total_income")
        )
        real_expense = _as_float(
            dossier.get("real_expense")
            if dossier.get("real_expense") not in (None, "")
            else dossier.get("total_expense")
        )
        income_gap = round(real_income - real_expense, 2)
        if income_gap < 0:
            negative_gap_count += 1
        risk_overview = _as_dict(dossier.get("risk_overview"))
        items.append(
            {
                "entity_name": entity_name,
                "family_name": str(dossier.get("family_name") or "").strip(),
                "total_income": round(_as_float(dossier.get("total_income")), 2),
                "total_expense": round(_as_float(dossier.get("total_expense")), 2),
                "real_income": round(real_income, 2),
                "real_expense": round(real_expense, 2),
                "income_gap": income_gap,
                "expense_income_ratio": round(real_expense / real_income, 3)
                if real_income > 0
                else None,
                "risk_level": normalize_risk_level(risk_overview.get("risk_level"), default="low"),
                "risk_label": str(risk_overview.get("risk_label") or risk_level_label(risk_overview.get("risk_level"))),
                "issue_refs": _unique_texts(_as_list(dossier.get("issue_refs"))),
                "key_issue_cards": _as_list(dossier.get("key_issue_cards"))[:3],
            }
        )

    family_rollup = []
    pending_family_count = 0
    for family in families:
        if not isinstance(family, dict):
            continue
        pending_members = _unique_texts(_as_list(family.get("pending_members")))
        if pending_members:
            pending_family_count += 1
        family_rollup.append(
            {
                "family_name": str(family.get("family_name") or family.get("anchor") or "").strip(),
                "anchor": str(family.get("anchor") or "").strip(),
                "member_count": int(_as_float(family.get("member_count"))),
                "pending_members": pending_members,
                "total_income": round(_as_float(family.get("total_income")), 2),
                "total_expense": round(_as_float(family.get("total_expense")), 2),
            }
        )

    return {
        "title": "附录A 资产与收入匹配",
        "summary": {
            "persons_count": len(items),
            "families_count": len(family_rollup),
            "negative_gap_count": negative_gap_count,
            "pending_family_count": pending_family_count,
            "property_record_count": int(_as_float(coverage.get("property_record_count"))),
            "vehicle_record_count": int(_as_float(coverage.get("vehicle_record_count"))),
        },
        "items": items,
        "family_rollup": family_rollup,
    }


def _build_appendix_b_income_loan(
    issue_payload: Dict[str, Any], dossier_payload: Dict[str, Any]
) -> Dict[str, Any]:
    categories = {"直接往来", "征信预警", "AML预警", "隐形资产", "综合问题"}
    issues = [
        issue
        for issue in sorted(_as_list(issue_payload.get("issues")), key=_issue_sort_key)
        if isinstance(issue, dict) and str(issue.get("category") or "").strip() in categories
    ]
    items: List[Dict[str, Any]] = []
    for issue in issues[:20]:
        scope = _as_dict(issue.get("scope"))
        items.append(
            {
                "issue_id": str(issue.get("issue_id") or "").strip(),
                "entity_name": str(scope.get("entity") or scope.get("company") or "").strip(),
                "family_name": str(scope.get("family") or "").strip(),
                "category": str(issue.get("category") or "").strip(),
                "headline": str(issue.get("headline") or issue.get("narrative") or "").strip(),
                "risk_level": normalize_risk_level(issue.get("risk_level"), default="low"),
                "risk_label": risk_level_label(issue.get("risk_level")),
                "priority": round(_as_float(issue.get("priority")), 1),
                "amount_impact": round(_as_float(issue.get("amount_impact")), 2),
                "next_actions": _unique_texts(_as_list(issue.get("next_actions")))[:3],
            }
        )

    focus_entities = _unique_texts(
        str(item.get("entity_name") or "").strip()
        for item in items
        if str(item.get("entity_name") or "").strip()
    )
    person_issue_refs = sum(
        len(_as_list(dossier.get("issue_refs")))
        for dossier in _as_list(dossier_payload.get("person_dossiers"))
        if isinstance(dossier, dict)
    )

    return {
        "title": "附录B 异常收入与借贷",
        "summary": {
            "issue_count": len(items),
            "focus_entity_count": len(focus_entities),
            "direct_transfer_count": len([item for item in items if item["category"] == "直接往来"]),
            "credit_alert_count": len([item for item in items if item["category"] == "征信预警"]),
            "aml_alert_count": len([item for item in items if item["category"] == "AML预警"]),
            "person_issue_ref_count": person_issue_refs,
        },
        "items": items,
        "focus_entities": focus_entities[:10],
    }


def _build_appendix_c_network_penetration(
    issue_payload: Dict[str, Any],
    dossier_payload: Dict[str, Any],
    company_issue_overview: Dict[str, Any],
) -> Dict[str, Any]:
    categories = {"直接往来", "现金碰撞", "现金时序伴随"}
    issues = [
        issue
        for issue in sorted(_as_list(issue_payload.get("issues")), key=_issue_sort_key)
        if isinstance(issue, dict) and str(issue.get("category") or "").strip() in categories
    ]
    priority_board = [
        item
        for item in _as_list(issue_payload.get("priority_board"))
        if isinstance(item, dict)
    ]
    focus_entities = []
    for item in priority_board[:10]:
        focus_entities.append(
            {
                "entity_name": str(item.get("entity_name") or "").strip(),
                "entity_type": str(item.get("entity_type") or "").strip(),
                "family_name": str(item.get("family_name") or "").strip(),
                "priority_score": round(_as_float(item.get("priority_score")), 1),
                "risk_level": normalize_risk_level(item.get("risk_level"), default="low"),
                "risk_label": str(item.get("risk_label") or risk_level_label(item.get("risk_level"))),
                "top_reasons": _unique_texts(_as_list(item.get("top_reasons")))[:3],
                "issue_refs": _unique_texts(_as_list(item.get("issue_refs")))[:5],
            }
        )

    connection_highlights = []
    for issue in issues[:10]:
        scope = _as_dict(issue.get("scope"))
        connection_highlights.append(
            {
                "issue_id": str(issue.get("issue_id") or "").strip(),
                "entity_name": str(scope.get("entity") or "").strip(),
                "company_name": str(scope.get("company") or "").strip(),
                "category": str(issue.get("category") or "").strip(),
                "headline": str(issue.get("headline") or "").strip(),
                "risk_level": normalize_risk_level(issue.get("risk_level"), default="low"),
                "priority": round(_as_float(issue.get("priority")), 1),
            }
        )

    company_items = _as_list(company_issue_overview.get("items"))[:8]
    network_entity_count = len(
        _unique_texts(
            list(
                str(item.get("entity_name") or "").strip()
                for item in focus_entities
                if str(item.get("entity_name") or "").strip()
            )
            + [
                str(item.get("entity_name") or "").strip()
                for item in company_items
                if str(item.get("entity_name") or "").strip()
            ]
        )
    )

    return {
        "title": "附录C 关系网络与资金穿透",
        "summary": {
            "entity_count": network_entity_count,
            "priority_entity_count": len(focus_entities),
            "network_issue_count": len(connection_highlights),
            "company_hotspot_count": len(company_items),
        },
        "items": focus_entities,
        "connection_highlights": connection_highlights,
        "company_hotspots": company_items,
    }


def _build_appendix_d_timeline_behavior(
    issue_payload: Dict[str, Any], dossier_payload: Dict[str, Any]
) -> Dict[str, Any]:
    categories = {"现金碰撞", "现金时序伴随"}
    timeline_items = []
    for issue in sorted(_as_list(issue_payload.get("issues")), key=_issue_sort_key):
        if not isinstance(issue, dict):
            continue
        if str(issue.get("category") or "").strip() not in categories:
            continue
        scope = _as_dict(issue.get("scope"))
        timeline_items.append(
            {
                "issue_id": str(issue.get("issue_id") or "").strip(),
                "entity_name": str(scope.get("entity") or "").strip(),
                "company_name": str(scope.get("company") or "").strip(),
                "category": str(issue.get("category") or "").strip(),
                "headline": str(issue.get("headline") or "").strip(),
                "risk_level": normalize_risk_level(issue.get("risk_level"), default="low"),
                "risk_label": risk_level_label(issue.get("risk_level")),
                "priority": round(_as_float(issue.get("priority")), 1),
            }
        )

    behavior_items = []
    for dossier in sorted(_as_list(dossier_payload.get("company_dossiers")), key=_dossier_sort_key):
        if not isinstance(dossier, dict):
            continue
        flags = _unique_texts(_as_list(dossier.get("behavioral_flags")))
        if not flags:
            continue
        overview = _as_dict(dossier.get("risk_overview"))
        behavior_items.append(
            {
                "entity_name": str(dossier.get("entity_name") or "").strip(),
                "risk_level": normalize_risk_level(overview.get("risk_level"), default="low"),
                "risk_label": str(overview.get("risk_label") or risk_level_label(overview.get("risk_level"))),
                "behavioral_flags": flags[:5],
                "issue_refs": _unique_texts(_as_list(dossier.get("issue_refs")))[:5],
            }
        )

    return {
        "title": "附录D 时序与行为模式",
        "summary": {
            "timeline_issue_count": len(timeline_items),
            "behavior_entity_count": len(behavior_items),
            "item_count": len(timeline_items) + len(behavior_items),
        },
        "items": timeline_items,
        "behavior_items": behavior_items,
    }


def _build_appendix_e_wallet_supplement(
    normalized_facts: Dict[str, Any], issue_payload: Dict[str, Any]
) -> Dict[str, Any]:
    coverage = _as_dict(normalized_facts.get("coverage"))
    available_sources = set(_as_list(coverage.get("available_external_sources")))
    wallet_available = "wallet" in available_sources
    wallet_subject_count = int(_as_float(coverage.get("wallet_subject_count")))
    wallet_transaction_count = int(_as_float(coverage.get("wallet_transaction_count")))

    wallet_issues = [
        issue
        for issue in sorted(_as_list(issue_payload.get("issues")), key=_issue_sort_key)
        if isinstance(issue, dict)
        and any(
            "wallet" in str(module or "").strip().lower()
            for module in _as_list(issue.get("source_modules"))
        )
    ]

    next_actions = (
        ["继续补调订单、聊天、实名绑定与登录轨迹等补充材料。"]
        if wallet_available
        else ["当前未接入电子钱包缓存，建议补调微信、支付宝、财付通明细。"] 
    )
    if wallet_issues:
        next_actions = _unique_texts(
            action
            for issue in wallet_issues
            for action in _as_list(issue.get("next_actions"))
        )[:5] or next_actions

    items = [
        {
            "status": "已接入" if wallet_available else "待补调",
            "subject_count": wallet_subject_count,
            "transaction_count": wallet_transaction_count,
            "issue_count": len(wallet_issues),
            "next_actions": next_actions,
        }
    ]

    return {
        "title": "附录E 电子钱包补证",
        "summary": {
            "wallet_available": wallet_available,
            "subject_count": wallet_subject_count,
            "transaction_count": wallet_transaction_count,
            "issue_count": len(wallet_issues),
        },
        "items": items,
    }


def _build_appendix_index(appendix_views: Dict[str, Any]) -> Dict[str, Any]:
    ordered_keys = [
        "appendix_a_assets_income",
        "appendix_b_income_loan",
        "appendix_c_network_penetration",
        "appendix_d_timeline_behavior",
        "appendix_e_wallet_supplement",
    ]

    items = []
    for key in ordered_keys:
        view = _as_dict(appendix_views.get(key))
        title = str(view.get("title") or "").strip()
        if not title:
            continue
        summary = _as_dict(view.get("summary"))
        item_count = _item_count(view)
        summary_line = ""
        if key == "appendix_a_assets_income":
            summary_line = (
                f"覆盖{int(_as_float(summary.get('persons_count')))}名人员、"
                f"{int(_as_float(summary.get('families_count')))}个家庭，"
                f"收支倒挂{int(_as_float(summary.get('negative_gap_count')))}人。"
            )
        elif key == "appendix_b_income_loan":
            summary_line = (
                f"归集{int(_as_float(summary.get('issue_count')))}项异常收入/借贷相关问题，"
                f"涉及{int(_as_float(summary.get('focus_entity_count')))}个对象。"
            )
        elif key == "appendix_c_network_penetration":
            summary_line = (
                f"提炼{int(_as_float(summary.get('priority_entity_count')))}个网络重点对象，"
                f"关联穿透问题{int(_as_float(summary.get('network_issue_count')))}项。"
            )
        elif key == "appendix_d_timeline_behavior":
            summary_line = (
                f"归集时序问题{int(_as_float(summary.get('timeline_issue_count')))}项，"
                f"行为异常对象{int(_as_float(summary.get('behavior_entity_count')))}个。"
            )
        elif key == "appendix_e_wallet_supplement":
            status_label = "已接入" if summary.get("wallet_available") else "待补调"
            summary_line = (
                f"电子钱包状态{status_label}，覆盖{int(_as_float(summary.get('subject_count')))}个主体，"
                f"摘要交易{int(_as_float(summary.get('transaction_count')))}笔。"
            )
        items.append(
            {
                "appendix_key": key,
                "title": title,
                "item_count": item_count,
                "summary_line": summary_line or f"已归集{item_count}条摘要内容。",
            }
        )

    return {
        "title": "统一语义层附录摘要",
        "summary": {
            "appendix_count": len(items),
            "total_count": sum(int(_as_float(item.get("item_count"))) for item in items),
        },
        "items": items,
    }


def build_report_package_view(
    normalized_facts: Dict[str, Any],
    issue_payload: Dict[str, Any],
    dossier_payload: Dict[str, Any],
    qa_checks: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the first-phase semantic report package."""
    normalized_facts = _as_dict(normalized_facts)
    issue_payload = _as_dict(issue_payload)
    dossier_payload = _as_dict(dossier_payload)

    issues = sorted(
        (
            issue
            for issue in _as_list(issue_payload.get("issues"))
            if isinstance(issue, dict)
        ),
        key=_issue_sort_key,
    )
    priority_board = [
        item
        for item in _as_list(issue_payload.get("priority_board"))
        if isinstance(item, dict)
    ]
    family_dossiers = sorted(
        (
            dossier
            for dossier in _as_list(dossier_payload.get("family_dossiers"))
            if isinstance(dossier, dict)
        ),
        key=_dossier_sort_key,
    )
    person_dossiers = sorted(
        (
            dossier
            for dossier in _as_list(dossier_payload.get("person_dossiers"))
            if isinstance(dossier, dict)
        ),
        key=_dossier_sort_key,
    )
    company_dossiers = sorted(
        (
            dossier
            for dossier in _as_list(dossier_payload.get("company_dossiers"))
            if isinstance(dossier, dict)
        ),
        key=_dossier_sort_key,
    )

    appendix_views: Dict[str, Any] = {}
    appendix_views["suspicion_summary"] = _build_suspicion_summary(
        normalized_facts, issues
    )
    appendix_views["aggregation_summary"] = _build_aggregation_summary(
        normalized_facts, priority_board
    )
    appendix_views["company_issue_overview"] = _build_company_issue_overview(
        issue_payload, {"company_dossiers": company_dossiers}
    )
    appendix_views["appendix_a_assets_income"] = _build_appendix_a_assets_income(
        normalized_facts,
        {
            "family_dossiers": family_dossiers,
            "person_dossiers": person_dossiers,
            "company_dossiers": company_dossiers,
        },
    )
    appendix_views["appendix_b_income_loan"] = _build_appendix_b_income_loan(
        {"issues": issues, "priority_board": priority_board},
        {
            "family_dossiers": family_dossiers,
            "person_dossiers": person_dossiers,
            "company_dossiers": company_dossiers,
        },
    )
    appendix_views["appendix_c_network_penetration"] = _build_appendix_c_network_penetration(
        {"issues": issues, "priority_board": priority_board},
        {"company_dossiers": company_dossiers},
        appendix_views["company_issue_overview"],
    )
    appendix_views["appendix_d_timeline_behavior"] = _build_appendix_d_timeline_behavior(
        {"issues": issues},
        {"company_dossiers": company_dossiers},
    )
    appendix_views["appendix_e_wallet_supplement"] = _build_appendix_e_wallet_supplement(
        normalized_facts,
        {"issues": issues},
    )
    appendix_views["appendix_index"] = _build_appendix_index(appendix_views)

    evidence_index = {
        ref: {
            **_as_dict(value),
            "issue_ids": _unique_texts(_as_list(_as_dict(value).get("issue_ids"))),
        }
        for ref, value in _as_dict(issue_payload.get("evidence_index")).items()
        if str(ref).strip()
    }

    return {
        "meta": _as_dict(normalized_facts.get("meta")),
        "coverage": _as_dict(normalized_facts.get("coverage")),
        "risk_schema": build_risk_schema(),
        "priority_board": priority_board,
        "issues": issues,
        "family_dossiers": family_dossiers,
        "person_dossiers": person_dossiers,
        "company_dossiers": company_dossiers,
        "appendix_views": appendix_views,
        "evidence_index": evidence_index,
        "qa_checks": _as_dict(qa_checks),
    }
