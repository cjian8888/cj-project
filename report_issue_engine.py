#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build report-package issues and the cross-entity priority board."""

from typing import Any, Dict, List, Optional, Set, Tuple

from unified_risk_model import (
    build_risk_overview,
    normalize_risk_level,
    priority_from_scores,
    risk_level_label,
    severity_from_level,
)


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


def _normalize_risk_level(value: Any) -> str:
    return normalize_risk_level(value, default="low")


def _severity_from_level(level: str, amount: float = 0.0) -> float:
    return severity_from_level(level, amount)


def _priority_from_scores(severity: float, confidence: float) -> float:
    return priority_from_scores(severity, confidence)


def _extract_evidence_refs(item: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    source_file = str(
        item.get("source_file")
        or item.get("sourceFile")
        or item.get("withdrawalSource")
        or item.get("depositSource")
        or ""
    ).strip()
    source_row = item.get("source_row_index", item.get("sourceRowIndex"))
    if source_file and source_row not in (None, ""):
        refs.append(f"{source_file}#L{int(_as_float(source_row))}")
    elif source_file:
        refs.append(source_file)
    transaction_id = str(
        item.get("transaction_id") or item.get("transactionId") or ""
    ).strip()
    if transaction_id:
        refs.append(f"tx:{transaction_id}")
    return refs


def _family_lookup(normalized_facts: Dict[str, Any]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for family in _as_list(normalized_facts.get("families")):
        if not isinstance(family, dict):
            continue
        family_name = str(family.get("family_name") or family.get("anchor") or "").strip()
        for member in _as_list(family.get("members")):
            member_name = str(member).strip()
            if member_name and family_name:
                lookup.setdefault(member_name, family_name)
    return lookup


def _entity_type_lookup(normalized_facts: Dict[str, Any]) -> Tuple[Set[str], Set[str]]:
    persons = {
        str(item.get("entity_name") or "").strip()
        for item in _as_list(normalized_facts.get("persons"))
        if isinstance(item, dict)
    }
    companies = {
        str(item.get("entity_name") or "").strip()
        for item in _as_list(normalized_facts.get("companies"))
        if isinstance(item, dict)
    }
    persons.discard("")
    companies.discard("")
    return persons, companies


def _infer_entity_type(entity_name: str, persons: Set[str], companies: Set[str]) -> str:
    if entity_name in companies:
        return "company"
    if entity_name in persons:
        return "person"
    return "unknown"


def _candidate_scope(
    primary_entity: str,
    counterparty: str,
    family_map: Dict[str, str],
    persons: Set[str],
    companies: Set[str],
) -> Dict[str, Any]:
    entity_name = primary_entity or counterparty
    company_name = ""
    if primary_entity in companies:
        company_name = primary_entity
    elif counterparty in companies:
        company_name = counterparty

    return {
        "family": family_map.get(entity_name) or family_map.get(counterparty) or "",
        "entity": entity_name,
        "entity_type": _infer_entity_type(entity_name, persons, companies),
        "company": company_name,
    }


def _top_reasons_from_summary(text: str) -> List[str]:
    content = str(text or "").strip()
    if not content:
        return []
    return [
        segment.strip()
        for segment in content.replace("；", "，").split("，")
        if segment.strip()
    ][:3]


def build_report_issues(
    analysis_cache: Dict[str, Any],
    normalized_facts: Dict[str, Any],
    report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build issue cards and a unified cross-entity priority board."""
    analysis_cache = _as_dict(analysis_cache)
    normalized_facts = _as_dict(normalized_facts)
    report = _as_dict(report)

    suspicions = _as_dict(analysis_cache.get("suspicions"))
    family_map = _family_lookup(normalized_facts)
    persons, companies = _entity_type_lookup(normalized_facts)

    issues: List[Dict[str, Any]] = []
    evidence_index: Dict[str, Dict[str, Any]] = {}
    seen: Set[Tuple[str, str, str, str]] = set()
    counters: Dict[str, int] = {}

    def register_issue(
        prefix: str,
        theme: str,
        category: str,
        scope: Dict[str, Any],
        headline: str,
        *,
        risk_level: str = "medium",
        confidence: float = 0.65,
        amount_impact: float = 0.0,
        why_flagged: Optional[List[str]] = None,
        counter_indicators: Optional[List[str]] = None,
        narrative: str = "",
        evidence_refs: Optional[List[str]] = None,
        next_actions: Optional[List[str]] = None,
        source_modules: Optional[List[str]] = None,
    ) -> None:
        normalized_headline = str(headline or "").strip()
        if not normalized_headline:
            return
        dedupe_key = (
            prefix,
            str(scope.get("entity") or "").strip(),
            str(category or "").strip(),
            normalized_headline,
        )
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)
        counters[prefix] = counters.get(prefix, 0) + 1
        issue_id = f"{prefix}-{counters[prefix]:03d}"
        normalized_risk_level = _normalize_risk_level(risk_level)
        severity = _severity_from_level(normalized_risk_level, amount_impact)
        normalized_confidence = round(max(0.05, min(1.0, confidence)), 2)
        priority = _priority_from_scores(severity, normalized_confidence)
        issue = {
            "issue_id": issue_id,
            "theme": theme,
            "category": category,
            "scope": scope,
            "headline": normalized_headline,
            "severity": severity,
            "confidence": normalized_confidence,
            "priority": priority,
            "risk_level": normalized_risk_level,
            "status": "需核查",
            "amount_impact": round(amount_impact, 2),
            "why_flagged": why_flagged or [],
            "counter_indicators": counter_indicators
            or ["需结合合同、凭证或业务背景进一步复核。"],
            "narrative": narrative or normalized_headline,
            "evidence_refs": evidence_refs or [],
            "next_actions": next_actions
            or ["补调凭证材料并核实相关交易背景。"],
            "source_modules": source_modules or [],
        }
        issues.append(issue)
        for ref in issue["evidence_refs"]:
            bucket = evidence_index.setdefault(ref, {"issue_ids": [], "ref": ref})
            bucket["issue_ids"].append(issue_id)

    conclusion = _as_dict(report.get("conclusion"))
    for item in _as_list(conclusion.get("issues")):
        if not isinstance(item, dict):
            continue
        entity_name = str(item.get("person") or item.get("entity") or "").strip()
        scope = {
            "family": family_map.get(entity_name, ""),
            "entity": entity_name,
            "entity_type": _infer_entity_type(entity_name, persons, companies),
            "company": entity_name if entity_name in companies else "",
        }
        description = str(item.get("description") or item.get("headline") or "").strip()
        register_issue(
            "CON",
            "综合研判",
            str(item.get("issue_type") or item.get("category") or "综合问题").strip()
            or "综合问题",
            scope,
            description or "正式报告研判指出存在待核查问题",
            risk_level=str(item.get("severity") or item.get("risk_level") or "medium"),
            confidence=0.68,
            why_flagged=[description] if description else [],
            narrative=description,
            source_modules=["report_conclusion"],
        )

    cash_collisions = _as_list(
        suspicions.get("cashCollisions") or suspicions.get("cash_collisions")
    )
    for item in cash_collisions:
        if not isinstance(item, dict):
            continue
        amount = max(
            _as_float(item.get("amount")),
            _as_float(item.get("withdrawal_amount")),
            _as_float(item.get("deposit_amount")),
            _as_float(item.get("amount1")),
            _as_float(item.get("amount2")),
        )
        person1 = str(item.get("person1") or item.get("from") or "").strip()
        person2 = str(item.get("person2") or item.get("to") or "").strip()
        scope = _candidate_scope(person1, person2, family_map, persons, companies)
        register_issue(
            "CASH",
            "时空线索",
            "现金碰撞",
            scope,
            f"{person1 or '未知主体'}与{person2 or '未知主体'}出现{amount:,.0f}元现金碰撞",
            risk_level=str(item.get("riskLevel") or "high"),
            confidence=0.76 if _extract_evidence_refs(item) else 0.63,
            amount_impact=amount,
            why_flagged=[
                f"取现/存现时间接近: {item.get('withdraw_time') or item.get('withdrawal_date') or item.get('time1') or '未提供'} / {item.get('deposit_time') or item.get('deposit_date') or item.get('time2') or '未提供'}",
                str(item.get("riskReason") or "现金进出节奏存在异常匹配").strip(),
            ],
            narrative=str(item.get("riskReason") or "现金取存时间与金额存在异常重合").strip(),
            evidence_refs=_extract_evidence_refs(item),
            next_actions=["核查取现用途、存现来源及对应凭证。"],
            source_modules=["cash_collision_detector"],
        )

    cash_timing_patterns = _as_list(
        suspicions.get("cashTimingPatterns") or suspicions.get("cash_timing_patterns")
    )
    for item in cash_timing_patterns:
        if not isinstance(item, dict):
            continue
        amount = max(
            _as_float(item.get("amount1")),
            _as_float(item.get("amount2")),
            _as_float(item.get("withdrawal_amount")),
            _as_float(item.get("deposit_amount")),
        )
        person1 = str(item.get("person1") or item.get("from") or "").strip()
        person2 = str(item.get("person2") or item.get("to") or "").strip()
        scope = _candidate_scope(person1, person2, family_map, persons, companies)
        register_issue(
            "TIME",
            "时空线索",
            "现金时序伴随",
            scope,
            f"{person1 or '未知主体'}与{person2 or '未知主体'}出现{amount:,.0f}元现金时序伴随",
            risk_level=str(item.get("riskLevel") or "medium"),
            confidence=0.7,
            amount_impact=amount,
            why_flagged=[
                f"时间轴: {item.get('time1') or item.get('withdrawal_date') or '未提供'} -> {item.get('time2') or item.get('deposit_date') or '未提供'}"
            ],
            narrative="同主体或关联主体在短时段内出现取现-存现伴随特征。",
            evidence_refs=_extract_evidence_refs(item),
            next_actions=["结合同行程、同地点和账户控制关系做交叉复核。"],
            source_modules=["cash_timing_detector"],
        )

    direct_transfers = _as_list(
        suspicions.get("directTransfers") or suspicions.get("direct_transfers")
    )
    for item in direct_transfers:
        if not isinstance(item, dict):
            continue
        from_name = str(item.get("from") or item.get("person") or "").strip()
        to_name = str(
            item.get("to")
            or item.get("company")
            or item.get("counterparty")
            or item.get("target")
            or ""
        ).strip()
        amount = _as_float(item.get("amount"))
        scope = _candidate_scope(from_name, to_name, family_map, persons, companies)
        register_issue(
            "FLOW",
            "关联交易",
            "直接往来",
            scope,
            f"{from_name or '未知主体'}与{to_name or '未知对手方'}发生{amount:,.0f}元直接往来",
            risk_level=str(item.get("riskLevel") or "medium"),
            confidence=0.78 if _extract_evidence_refs(item) else 0.66,
            amount_impact=amount,
            why_flagged=[
                f"交易日期: {item.get('date') or '未提供'}",
                str(item.get("description") or "存在直接资金往来").strip(),
            ],
            narrative=str(item.get("description") or "发现直接资金往来，需要核查交易背景。").strip(),
            evidence_refs=_extract_evidence_refs(item),
            next_actions=["调取交易回单、合同及对手方背景材料。"],
            source_modules=["related_party_analyzer"],
        )

    hidden_assets = suspicions.get("hiddenAssets")
    if not isinstance(hidden_assets, list):
        hidden_assets = suspicions.get("hidden_assets")
    if isinstance(hidden_assets, dict):
        flattened_hidden_assets: List[Dict[str, Any]] = []
        for owner, values in hidden_assets.items():
            for raw in _as_list(values):
                if isinstance(raw, dict):
                    enriched = dict(raw)
                    enriched.setdefault("owner", owner)
                    flattened_hidden_assets.append(enriched)
        hidden_assets = flattened_hidden_assets
    hidden_assets = _as_list(hidden_assets)
    for item in hidden_assets:
        if not isinstance(item, dict):
            continue
        owner = str(item.get("owner") or item.get("person") or item.get("name") or "").strip()
        scope = {
            "family": family_map.get(owner, ""),
            "entity": owner,
            "entity_type": _infer_entity_type(owner, persons, companies),
            "company": owner if owner in companies else "",
        }
        headline = str(item.get("description") or item.get("headline") or "").strip()
        register_issue(
            "ASSET",
            "资产核查",
            "隐形资产",
            scope,
            headline or f"{owner or '未知主体'}存在待核实隐形资产线索",
            risk_level="high",
            confidence=0.62,
            amount_impact=max(
                _as_float(item.get("amount")),
                _as_float(item.get("estimated_value")),
            ),
            why_flagged=[headline] if headline else ["当前缓存识别出未纳入常规资产盘点的线索。"],
            narrative=headline or "存在待核实的隐形资产或未申报资产线索。",
            evidence_refs=_extract_evidence_refs(item),
            next_actions=["补调权属材料、交易记录及资金来源说明。"],
            source_modules=["hidden_asset_detector"],
        )

    aml_alerts = _as_list(suspicions.get("amlAlerts") or suspicions.get("aml_alerts"))
    for item in aml_alerts:
        if not isinstance(item, dict):
            continue
        positive_count = (
            _as_float(item.get("suspicious_transaction_count"))
            + _as_float(item.get("large_transaction_count"))
            + _as_float(item.get("payment_transaction_count"))
        )
        if positive_count <= 0:
            continue
        entity_name = str(
            item.get("person") or item.get("subject") or item.get("name") or ""
        ).strip()
        scope = {
            "family": family_map.get(entity_name, ""),
            "entity": entity_name,
            "entity_type": _infer_entity_type(entity_name, persons, companies),
            "company": entity_name if entity_name in companies else "",
        }
        register_issue(
            "AML",
            "反洗钱",
            "AML预警",
            scope,
            f"{entity_name or '未知主体'}命中{int(positive_count)}项AML风险计数",
            risk_level="high" if positive_count >= 3 else "medium",
            confidence=0.64,
            amount_impact=_as_float(item.get("total_amount")),
            why_flagged=[
                f"可疑交易{int(_as_float(item.get('suspicious_transaction_count')))}笔",
                f"大额交易{int(_as_float(item.get('large_transaction_count')))}笔",
                f"支付交易{int(_as_float(item.get('payment_transaction_count')))}笔",
            ],
            narrative="AML监测维度已出现实质性命中，建议纳入重点复核。",
            evidence_refs=_extract_evidence_refs(item),
            next_actions=["复核命中规则与基础交易明细，排除误报后形成专门说明。"],
            source_modules=["aml_analyzer"],
        )

    credit_alerts = _as_list(
        suspicions.get("creditAlerts") or suspicions.get("credit_alerts")
    )
    for item in credit_alerts:
        if not isinstance(item, dict):
            continue
        entity_name = str(
            item.get("person") or item.get("subject") or item.get("name") or ""
        ).strip()
        scope = {
            "family": family_map.get(entity_name, ""),
            "entity": entity_name,
            "entity_type": _infer_entity_type(entity_name, persons, companies),
            "company": entity_name if entity_name in companies else "",
        }
        alert_text = str(
            item.get("description") or item.get("alert") or item.get("reason") or ""
        ).strip()
        register_issue(
            "CREDIT",
            "征信核查",
            "征信预警",
            scope,
            alert_text or f"{entity_name or '未知主体'}出现征信预警",
            risk_level=str(item.get("riskLevel") or "medium"),
            confidence=0.58,
            amount_impact=_as_float(item.get("amount")),
            why_flagged=[alert_text] if alert_text else ["征信缓存中存在待关注预警。"],
            narrative=alert_text or "征信信息出现预警，需结合借贷与还款行为综合判断。",
            evidence_refs=_extract_evidence_refs(item),
            next_actions=["补查征信详情、借贷凭证和还款流水。"],
            source_modules=["credit_analyzer"],
        )

    issue_refs_by_entity: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        scope = _as_dict(issue.get("scope"))
        entity_name = str(scope.get("entity") or scope.get("company") or "").strip()
        if entity_name:
            issue_refs_by_entity.setdefault(entity_name, []).append(issue)
        company_name = str(scope.get("company") or "").strip()
        if company_name and company_name != entity_name:
            issue_refs_by_entity.setdefault(company_name, []).append(issue)

    priority_board: List[Dict[str, Any]] = []
    priority_board_entities: Set[str] = set()
    for item in _as_list(normalized_facts.get("aggregation_highlights")):
        if not isinstance(item, dict):
            continue
        entity_name = str(item.get("entity") or "").strip()
        if not entity_name:
            continue
        linked_issues = issue_refs_by_entity.get(entity_name, [])
        risk_overview = build_risk_overview(
            linked_issues,
            fallback_score=item.get("risk_score", 0),
            fallback_level=item.get("risk_level", ""),
            fallback_confidence=item.get("risk_confidence", 0),
            source="aggregation_highlight",
        )
        reasons = [
            str(reason).strip()
            for reason in _as_list(item.get("top_clues"))
            if str(reason).strip()
        ]
        if not reasons:
            reasons = _top_reasons_from_summary(item.get("summary"))
        if not reasons:
            reasons = [issue["headline"] for issue in linked_issues[:3]]
        priority_board.append(
            {
                "entity_type": str(item.get("entity_type") or "").strip()
                or _infer_entity_type(entity_name, persons, companies),
                "entity_name": entity_name,
                "family_name": family_map.get(entity_name, ""),
                "priority_score": risk_overview.get("priority_score", 0.0),
                "risk_level": risk_overview.get("risk_level", "low"),
                "risk_label": risk_overview.get("risk_label", risk_level_label("low")),
                "priority_band": risk_overview.get("priority_band", "低"),
                "severity": risk_overview.get("severity", 0.0),
                "confidence": risk_overview.get("confidence", 0.0),
                "top_reasons": reasons[:3],
                "issue_refs": [issue["issue_id"] for issue in linked_issues[:5]],
            }
        )
        priority_board_entities.add(entity_name)

    for entity_name, linked_issues in issue_refs_by_entity.items():
        if not linked_issues or entity_name in priority_board_entities:
            continue
        ordered = sorted(
            linked_issues,
            key=lambda item: (
                -_as_float(item.get("priority")),
                -_as_float(item.get("severity")),
                item.get("issue_id", ""),
            ),
        )
        risk_overview = build_risk_overview(
            ordered,
            source="issue_engine",
        )
        priority_board.append(
            {
                "entity_type": _infer_entity_type(entity_name, persons, companies),
                "entity_name": entity_name,
                "family_name": family_map.get(entity_name, ""),
                "priority_score": risk_overview.get("priority_score", 0.0),
                "risk_level": risk_overview.get("risk_level", "low"),
                "risk_label": risk_overview.get("risk_label", risk_level_label("low")),
                "priority_band": risk_overview.get("priority_band", "低"),
                "severity": risk_overview.get("severity", 0.0),
                "confidence": risk_overview.get("confidence", 0.0),
                "top_reasons": [item["headline"] for item in ordered[:3]],
                "issue_refs": [item["issue_id"] for item in ordered[:5]],
            }
        )
        priority_board_entities.add(entity_name)

    priority_board.sort(
        key=lambda item: (
            -_as_float(item.get("priority_score")),
            -_as_float(item.get("confidence")),
            str(item.get("entity_name") or ""),
        )
    )

    return {
        "issues": sorted(
            issues,
            key=lambda item: (
                -_as_float(item.get("priority")),
                -_as_float(item.get("severity")),
                item.get("issue_id", ""),
            ),
        ),
        "priority_board": priority_board[:20],
        "evidence_index": evidence_index,
    }
