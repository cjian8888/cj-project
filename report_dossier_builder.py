#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build family/person/company dossiers for the unified report package."""

import re
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


def _person_section_lookup(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}

    for family in _as_list(report.get("family_sections")):
        if not isinstance(family, dict):
            continue
        for section in _as_list(family.get("member_sections")):
            if not isinstance(section, dict):
                continue
            name = str(section.get("name") or section.get("person_name") or "").strip()
            if name:
                lookup[name] = section

    for section in _as_list(report.get("person_sections")):
        if not isinstance(section, dict):
            continue
        name = str(section.get("name") or section.get("person_name") or "").strip()
        if name:
            lookup[name] = section

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


def _sanitize_legacy_company_summary(legacy_summary: str) -> str:
    text = str(legacy_summary or "").strip()
    if not text:
        return ""

    banned_tokens = ("统一风险", "综合评分", "评级为", "风险评分", "优先级")
    section_markers = [
        "【经营规模】",
        "【核心人员往来】",
        "【公司间往来】",
        "【行为特征】",
        "【主要对手方】",
        "【风险评分】",
        "【风险评估】",
    ]
    positions = sorted(
        (
            (text.find(marker), marker)
            for marker in section_markers
            if text.find(marker) >= 0
        ),
        key=lambda item: item[0],
    )

    if positions:
        extracted: List[str] = []
        for index, (start, _marker) in enumerate(positions):
            end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
            chunk = text[start:end].strip("；。 ")
            if not chunk or any(token in chunk for token in banned_tokens):
                continue
            extracted.append(chunk.rstrip("。") + "。")
        return "".join(extracted).strip()

    if any(token in text for token in banned_tokens):
        return ""
    return text.rstrip("。") + "。"


def _format_wan_amount(value: Any) -> str:
    return f"{_as_float(value) / 10000:.2f}万"


def _format_priority_score(value: Any) -> str:
    return f"{_as_float(value):.1f}"


def _family_display_name(family_name: str) -> str:
    name = str(family_name or "").strip()
    if not name:
        return "该家庭"
    return name if name.endswith("家庭") else f"{name}家庭"


def _extract_reason_texts(
    aggregation_item: Optional[Dict[str, Any]] = None,
    key_issue_cards: Optional[Iterable[Dict[str, Any]]] = None,
    limit: int = 3,
) -> List[str]:
    aggregation_item = _as_dict(aggregation_item)
    reason_texts: List[str] = []

    for clue in _as_list(aggregation_item.get("top_clues")):
        if isinstance(clue, dict):
            text = str(
                clue.get("description")
                or clue.get("summary")
                or clue.get("headline")
                or clue.get("name")
                or ""
            ).strip()
        else:
            text = str(clue or "").strip()
        if text:
            reason_texts.append(text.rstrip("。； "))

    if not reason_texts:
        summary_text = str(aggregation_item.get("summary") or "").strip()
        if "重点线索：" in summary_text:
            clue_text = summary_text.split("重点线索：", 1)[1]
            reason_texts.extend(
                part.rstrip("。； ")
                for part in re.split(r"[、；]", clue_text)
                if str(part or "").strip()
            )

    if not reason_texts and key_issue_cards is not None:
        for item in key_issue_cards:
            if not isinstance(item, dict):
                continue
            text = str(
                item.get("headline") or item.get("category") or item.get("issue_id") or ""
            ).strip()
            if text:
                reason_texts.append(text.rstrip("。； "))

    return _unique_texts(reason_texts)[:limit]


def _build_issue_count_parts(
    risk_overview: Dict[str, Any],
    key_issue_cards: Iterable[Dict[str, Any]],
) -> List[str]:
    total_issue_count = int(_as_float(_as_dict(risk_overview).get("issue_count")))
    representative_issue_count = len(
        [item for item in key_issue_cards if isinstance(item, dict) or str(item).strip()]
    )

    parts: List[str] = []
    if total_issue_count > 0:
        parts.append(f"全量问题{total_issue_count}项")
    if representative_issue_count > 0 and representative_issue_count != total_issue_count:
        parts.append(f"代表问题{representative_issue_count}项")
    elif representative_issue_count > 0 and total_issue_count <= 0:
        parts.append(f"代表问题{representative_issue_count}项")
    return parts


def _build_family_summary(
    family_name: str,
    members: List[str],
    pending_members: List[str],
    total_income: Any,
    total_expense: Any,
    risk_overview: Dict[str, Any],
    key_issue_cards: List[Dict[str, Any]],
    aggregation_items: Optional[Iterable[Dict[str, Any]]] = None,
) -> str:
    display_name = _family_display_name(family_name)
    parts: List[str] = []

    if members:
        parts.append(f"已识别成员{len(members)}名")
    if pending_members:
        parts.append(f"待补成员{len(pending_members)}名")

    parts.append(
        f"统一风险为{risk_overview.get('risk_label', '低风险')}，优先级{_format_priority_score(risk_overview.get('priority_score'))}分"
    )

    if _as_float(total_income) > 0 or _as_float(total_expense) > 0:
        parts.append(
            f"家庭收支{_format_wan_amount(total_income)}/{_format_wan_amount(total_expense)}"
        )

    parts.extend(_build_issue_count_parts(risk_overview, key_issue_cards))

    reason_texts: List[str] = []
    for item in aggregation_items or []:
        reason_texts.extend(_extract_reason_texts(item, limit=2))
    reason_texts = _unique_texts(reason_texts)
    if not reason_texts:
        reason_texts = _extract_reason_texts(key_issue_cards=key_issue_cards, limit=2)
    if reason_texts:
        parts.append("重点线索：" + "、".join(reason_texts[:2]))

    return f"{display_name}{'；'.join(parts)}。"


def _build_person_summary(
    entity_name: str,
    family_name: str,
    transaction_count: Any,
    real_income: Any,
    real_expense: Any,
    risk_overview: Dict[str, Any],
    key_issue_cards: List[Dict[str, Any]],
    aggregation_item: Optional[Dict[str, Any]] = None,
) -> str:
    parts: List[str] = []
    normalized_family_name = str(family_name or "").strip()
    if normalized_family_name and normalized_family_name not in {
        entity_name,
        f"{entity_name}家庭",
    }:
        parts.append(f"所属家庭{normalized_family_name}")

    parts.append(
        f"统一风险为{risk_overview.get('risk_label', '低风险')}，优先级{_format_priority_score(risk_overview.get('priority_score'))}分"
    )

    if int(transaction_count or 0) > 0:
        parts.append(f"交易笔数{int(transaction_count or 0)}笔")
    elif _as_float(real_income) > 0 or _as_float(real_expense) > 0:
        parts.append(
            f"实际收支{_format_wan_amount(real_income)}/{_format_wan_amount(real_expense)}"
        )

    parts.extend(_build_issue_count_parts(risk_overview, key_issue_cards))

    reason_texts = _extract_reason_texts(
        aggregation_item=aggregation_item,
        key_issue_cards=key_issue_cards,
        limit=2,
    )
    if reason_texts:
        parts.append("重点线索：" + "、".join(reason_texts))

    return f"{entity_name}{'；'.join(parts)}。"


_OFFSET_BUCKET_SPECS: Tuple[Tuple[str, str], ...] = (
    ("self_transfer", "本人账户互转"),
    ("wealth_principal", "理财/定存本金回流"),
    ("family_transfer", "家庭成员互转"),
    ("business_reimbursement", "单位报销/业务往来款"),
    ("loan", "贷款发放"),
    ("refund", "退款/冲正"),
    ("bank_product_adjustment", "银行卡产品回摆/还款冲销"),
    ("installment_adjustment", "账单分期/银行产品冲销"),
)

_CONFIDENCE_TEXT = {
    "high": "高",
    "medium": "中",
    "low": "低",
}


def _build_offset_rule_lookup(person_section: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    data_analysis = _as_dict(_as_dict(person_section).get("data_analysis_section"))
    income_match = _as_dict(data_analysis.get("income_match_analysis"))
    for row in _as_list(income_match.get("offset_rule_rows")):
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if name:
            lookup[name] = row
    return lookup


def _build_offset_rows(
    offset_detail: Dict[str, Any],
    rule_lookup: Dict[str, Dict[str, Any]],
    direction: str,
) -> List[Dict[str, Any]]:
    offset_meta = _as_dict(offset_detail.get("offset_meta"))
    amount_key = "income_amount" if direction == "income" else "expense_amount"
    rows: List[Dict[str, Any]] = []

    fallback_keys = {
        ("income", "self_transfer"): "self_transfer",
        ("expense", "self_transfer"): "self_transfer_expense",
        ("income", "wealth_principal"): "wealth_principal",
        ("income", "family_transfer"): "family_transfer_in",
        ("expense", "family_transfer"): "family_transfer_out",
        ("income", "business_reimbursement"): "business_reimbursement",
        ("income", "loan"): "loan",
        ("income", "refund"): "refund",
    }

    for bucket, default_label in _OFFSET_BUCKET_SPECS:
        meta = _as_dict(offset_meta.get(bucket))
        label = str(meta.get("label") or default_label).strip() or default_label
        amount = _as_float(meta.get(amount_key))
        fallback_key = fallback_keys.get((direction, bucket))
        if amount <= 0 and fallback_key:
            amount = _as_float(offset_detail.get(fallback_key))
        if amount <= 0:
            continue
        confidence = str(meta.get("confidence") or "").strip().lower()
        rule_row = _as_dict(rule_lookup.get(label))
        rows.append(
            {
                "bucket": bucket,
                "direction": direction,
                "label": label,
                "amount": amount,
                "amount_wan": round(amount / 10000, 2),
                "confidence": confidence,
                "confidence_text": str(
                    rule_row.get("confidence_text")
                    or _CONFIDENCE_TEXT.get(confidence, "未标注")
                ).strip(),
                "rule_text": str(rule_row.get("rule_text") or "").strip(),
            }
        )

    rows.sort(
        key=lambda item: (-_as_float(item.get("amount")), str(item.get("label") or ""))
    )
    return rows


def _format_offset_row_brief(rows: List[Dict[str, Any]], limit: int = 2) -> str:
    return "、".join(
        f"{str(row.get('label') or '').strip()}{_format_wan_amount(row.get('amount'))}"
        for row in rows[:limit]
        if str(row.get("label") or "").strip()
    )


def _describe_balance_state(income: float, expense: float, label: str) -> str:
    if income <= 0 and expense <= 0:
        return ""

    net_amount = income - expense
    diff = abs(net_amount)
    base = max(income, expense, 1.0)
    trend = "净结余" if net_amount >= 0 else "净流出"
    if diff <= base * 0.12:
        return f"{label}基本平衡，{trend}{diff / 10000:.2f}万元"
    return f"{label}{trend}{diff / 10000:.2f}万元"


def _is_small_gap(total_amount: float, gap_amount: float) -> bool:
    return gap_amount <= max(50000.0, max(total_amount, 1.0) * 0.08)


def _build_person_financial_gap_explanation(
    person: Dict[str, Any],
    person_section: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    raw_income = max(0.0, _as_float(person.get("total_income")))
    raw_expense = max(0.0, _as_float(person.get("total_expense")))
    real_income = max(0.0, _as_float(person.get("real_income")))
    real_expense = max(0.0, _as_float(person.get("real_expense")))
    income_gap = max(0.0, raw_income - real_income)
    expense_gap = max(0.0, raw_expense - real_expense)
    offset_detail = _as_dict(person.get("offset_detail"))
    rule_lookup = _build_offset_rule_lookup(person_section)
    income_offset_rows = _build_offset_rows(offset_detail, rule_lookup, "income")
    expense_offset_rows = _build_offset_rows(offset_detail, rule_lookup, "expense")

    raw_balance_summary = _describe_balance_state(raw_income, raw_expense, "原始口径收支")
    real_balance_summary = _describe_balance_state(real_income, real_expense, "真实口径收支")

    summary_parts: List[str] = []
    if raw_balance_summary:
        summary_parts.append(raw_balance_summary)
    if real_balance_summary:
        summary_parts.append(real_balance_summary)

    if income_gap <= 0:
        summary_parts.append("流入侧原始口径与真实收入基本一致，说明需剔除项目较少")
    else:
        income_reason_text = _format_offset_row_brief(income_offset_rows)
        if _is_small_gap(raw_income, income_gap):
            if income_reason_text:
                summary_parts.append(
                    f"流入侧仅剔除{income_gap / 10000:.2f}万元，主要为{income_reason_text}"
                )
            else:
                summary_parts.append(f"流入侧仅剔除{income_gap / 10000:.2f}万元")
        else:
            if income_reason_text:
                summary_parts.append(
                    f"流入侧较真实收入多出{income_gap / 10000:.2f}万元，主要因{income_reason_text}被剔除"
                )
            else:
                summary_parts.append(
                    f"流入侧较真实收入多出{income_gap / 10000:.2f}万元，当前未提炼出明确剔除桶"
                )

    if expense_gap <= 0:
        summary_parts.append("流出侧原始口径与真实支出基本一致，说明需剔除项目较少")
    else:
        expense_reason_text = _format_offset_row_brief(expense_offset_rows)
        if _is_small_gap(raw_expense, expense_gap):
            if expense_reason_text:
                summary_parts.append(
                    f"流出侧仅剔除{expense_gap / 10000:.2f}万元，主要为{expense_reason_text}"
                )
            else:
                summary_parts.append(f"流出侧仅剔除{expense_gap / 10000:.2f}万元")
        else:
            if expense_reason_text:
                summary_parts.append(
                    f"流出侧较真实支出多出{expense_gap / 10000:.2f}万元，主要因{expense_reason_text}被剔除"
                )
            else:
                summary_parts.append(
                    f"流出侧较真实支出多出{expense_gap / 10000:.2f}万元，当前未提炼出明确剔除桶"
                )

    return {
        "summary": "；".join(part for part in summary_parts if part).strip("；") + "。",
        "raw_balance_summary": raw_balance_summary,
        "real_balance_summary": real_balance_summary,
        "income_gap": income_gap,
        "expense_gap": expense_gap,
        "income_offset_rows": income_offset_rows[:3],
        "expense_offset_rows": expense_offset_rows[:3],
    }


def _build_family_financial_explanation(
    family_name: str,
    members: List[str],
    pending_members: List[str],
    total_income: Any,
    total_expense: Any,
    key_issue_cards: List[Dict[str, Any]],
    aggregation_items: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    member_count = len(members)
    pending_count = len(pending_members)
    income_amount = max(0.0, _as_float(total_income))
    expense_amount = max(0.0, _as_float(total_expense))
    coverage_summary = (
        f"当前已识别成员{member_count}名，待补成员{pending_count}名"
        if pending_count > 0
        else f"当前已识别成员{member_count}名，成员流水覆盖完整"
    )
    balance_summary = _describe_balance_state(
        income_amount,
        expense_amount,
        "当前已覆盖成员家庭收支",
    )

    reason_texts: List[str] = []
    for item in aggregation_items or []:
        reason_texts.extend(_extract_reason_texts(item, limit=2))
    reason_texts = _unique_texts(reason_texts)
    if not reason_texts:
        reason_texts = _extract_reason_texts(key_issue_cards=key_issue_cards, limit=3)

    summary_parts = [coverage_summary]
    if pending_count > 0:
        summary_parts.append(
            f"当前收支仅覆盖已取得银行流水画像的成员，待补对象为{'、'.join(pending_members[:3])}"
        )
    if balance_summary:
        summary_parts.append(balance_summary)
    if reason_texts:
        summary_parts.append(f"重点线索集中在{'、'.join(reason_texts[:2])}")

    return {
        "summary": "；".join(part for part in summary_parts if part).strip("；") + "。",
        "coverage_summary": coverage_summary,
        "balance_summary": balance_summary,
        "pending_members": pending_members[:5],
        "focus_clues": reason_texts[:3],
        "member_count": member_count,
        "pending_member_count": pending_count,
    }


def _build_company_business_explanation(
    company: Dict[str, Any],
    role_tags: List[str],
    related_persons: List[str],
    related_companies: List[str],
    behavioral_flags: List[str],
    key_issue_cards: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total_income = max(0.0, _as_float(company.get("total_income")))
    total_expense = max(0.0, _as_float(company.get("total_expense")))
    transaction_count = int(_as_float(company.get("transaction_count")))
    scale_summary = (
        f"累计流入{_format_wan_amount(total_income)}、流出{_format_wan_amount(total_expense)}"
        if total_income > 0 or total_expense > 0
        else ""
    )
    if transaction_count > 0:
        scale_summary = (
            f"{scale_summary}，共{transaction_count}笔交易" if scale_summary else f"共{transaction_count}笔交易"
        )

    balance_summary = _describe_balance_state(total_income, total_expense, "公司资金口径")
    role_summary = (
        f"当前角色标签为{'、'.join(role_tags[:3])}"
        if role_tags
        else "当前未沉淀出稳定角色标签"
    )

    relation_parts: List[str] = []
    if related_persons:
        relation_parts.append(f"关联核心人员{len(related_persons)}名")
    if related_companies:
        relation_parts.append(f"关联公司{len(related_companies)}家")
    relation_summary = "；".join(relation_parts)

    focus_headlines = [
        str(item.get("headline") or "").strip()
        for item in key_issue_cards
        if isinstance(item, dict) and str(item.get("headline") or "").strip()
    ]

    summary_parts = [part for part in [scale_summary, balance_summary, role_summary, relation_summary] if part]
    if behavioral_flags:
        summary_parts.append(f"行为特征包括{'、'.join(behavioral_flags[:2])}")
    elif focus_headlines:
        summary_parts.append(f"代表问题为{focus_headlines[0]}")

    return {
        "summary": "；".join(summary_parts).strip("；") + "。" if summary_parts else "",
        "scale_summary": scale_summary,
        "balance_summary": balance_summary,
        "role_summary": role_summary,
        "relation_summary": relation_summary,
        "behavioral_flags": behavioral_flags[:3],
        "focus_issue_headlines": focus_headlines[:3],
    }


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
    sanitized_legacy_summary = _sanitize_legacy_company_summary(legacy_summary)
    if role_tags:
        parts.append(f"角色标签为{'、'.join(role_tags)}")
    parts.append(
        f"统一风险为{risk_overview.get('risk_label', '低风险')}，优先级{risk_overview.get('priority_score', 0)}分"
    )
    if related_persons:
        parts.append(f"关联核心人员{len(related_persons)}名")
    if related_companies:
        parts.append(f"关联公司{len(related_companies)}家")
    issue_count_parts = _build_issue_count_parts(risk_overview, key_issue_cards)
    if issue_count_parts:
        parts.extend(issue_count_parts)
    elif sanitized_legacy_summary:
        parts.append("已回收旧公司分析摘要")
    summary = "；".join(parts)
    if sanitized_legacy_summary:
        return (
            f"{entity_name}{summary}。{sanitized_legacy_summary}"
            if summary
            else sanitized_legacy_summary
        )
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
    person_sections = _person_section_lookup(report)

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
        key_issue_cards = _build_key_issue_cards(linked_issues)
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
        pending_members = _unique_texts(_as_list(family.get("pending_members")))
        family_dossiers.append(
            {
                "family_name": family_name,
                "anchor": str(family.get("anchor") or family_name).strip(),
                "members": members,
                "member_count": int(family.get("member_count", len(members))),
                "pending_members": pending_members,
                "total_income": _as_float(family.get("total_income", 0)),
                "total_expense": _as_float(family.get("total_expense", 0)),
                "risk_overview": risk_overview,
                "key_issue_cards": key_issue_cards,
                "issue_refs": _issue_refs(linked_issues),
                "family_financial_explanation": _build_family_financial_explanation(
                    family_name,
                    members,
                    pending_members,
                    family.get("total_income", 0),
                    family.get("total_expense", 0),
                    key_issue_cards,
                    (aggregation_lookup.get(member, {}) for member in members),
                ),
                "summary": _build_family_summary(
                    family_name,
                    members,
                    pending_members,
                    family.get("total_income", 0),
                    family.get("total_expense", 0),
                    risk_overview,
                    key_issue_cards,
                    (aggregation_lookup.get(member, {}) for member in members),
                ),
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
        key_issue_cards = _build_key_issue_cards(linked_issues)
        person_section = person_sections.get(entity_name, {})
        family_name = next(
            (
                family.get("family_name")
                for family in family_dossiers
                if entity_name in _as_list(family.get("members"))
            ),
            "",
        )
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
                "family_name": family_name,
                "risk_overview": risk_overview,
                "key_issue_cards": key_issue_cards,
                "issue_refs": _issue_refs(linked_issues),
                "account_layer_summary": _as_dict(
                    person.get("account_layer_summary")
                ),
                "financial_gap_explanation": _build_person_financial_gap_explanation(
                    person,
                    person_section,
                ),
                "summary": _build_person_summary(
                    entity_name,
                    family_name,
                    person.get("transaction_count", 0),
                    person.get("real_income", 0),
                    person.get("real_expense", 0),
                    risk_overview,
                    key_issue_cards,
                    aggregation_item,
                ),
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
                "company_business_explanation": _build_company_business_explanation(
                    company,
                    role_tags,
                    related_persons[:10],
                    related_companies[:10],
                    _as_list(company_context.get("behavioral_flags"))[:5],
                    key_issue_cards,
                ),
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
