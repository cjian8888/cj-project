#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared risk normalization helpers for semantic report outputs."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


RISK_LEVEL_ORDER = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}

RISK_LEVEL_LABELS = {
    "critical": "极高风险",
    "high": "高风险",
    "medium": "中风险",
    "low": "低风险",
    "info": "提示",
}

_RISK_LEVEL_MAPPING = {
    "critical": "critical",
    "极高": "critical",
    "极高风险": "critical",
    "重大": "critical",
    "high": "high",
    "高": "high",
    "高风险": "high",
    "关注级": "medium",
    "medium": "medium",
    "中": "medium",
    "中风险": "medium",
    "moderate": "medium",
    "low": "low",
    "低": "low",
    "低风险": "low",
    "normal": "low",
    "info": "info",
    "提示": "info",
    "一般提示": "info",
}


def _as_float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_risk_level(value: Any, default: str = "low") -> str:
    """Normalize legacy Chinese/English labels into one stable enum."""
    text = str(value or "").strip().lower()
    normalized = _RISK_LEVEL_MAPPING.get(text)
    if normalized:
        return normalized
    if not text:
        return default
    return default


def risk_level_rank(value: Any) -> int:
    """Return a sortable risk rank."""
    return RISK_LEVEL_ORDER.get(normalize_risk_level(value), 0)


def risk_level_label(value: Any) -> str:
    """Return the human-readable Chinese label for a normalized level."""
    return RISK_LEVEL_LABELS.get(normalize_risk_level(value), "低风险")


def severity_from_level(level: Any, amount: float = 0.0) -> float:
    """Map normalized risk levels into a report severity score."""
    normalized_level = normalize_risk_level(level)
    base = {
        "critical": 90.0,
        "high": 78.0,
        "medium": 58.0,
        "low": 32.0,
        "info": 15.0,
    }.get(normalized_level, 32.0)
    if amount >= 1_000_000:
        base += 10
    elif amount >= 100_000:
        base += 5
    elif amount <= 0:
        base -= 3
    return round(max(5.0, min(100.0, base)), 1)


def priority_from_scores(severity: float, confidence: float) -> float:
    """Combine severity and confidence into a stable priority score."""
    return round(max(0.0, min(100.0, severity * 0.72 + confidence * 28.0)), 1)


def risk_level_from_score(score: Any) -> str:
    """Map unified scores into the canonical risk enum."""
    value = _as_float(score)
    if value >= 85:
        return "critical"
    if value >= 70:
        return "high"
    if value >= 45:
        return "medium"
    if value >= 15:
        return "low"
    return "info"


def priority_band_label(priority_score: Any, risk_level: Any = "") -> str:
    """Render unified priority into the current TXT/HTML readable bucket."""
    score = _as_float(priority_score)
    level = normalize_risk_level(risk_level)
    if score >= 80 or level in {"critical", "high"}:
        return "高"
    if score >= 60 or level == "medium":
        return "中"
    return "低"


def pick_highest_risk_level(levels: Iterable[Any], default: str = "low") -> str:
    """Choose the highest normalized level from a sequence."""
    best = normalize_risk_level(default, default=default)
    best_rank = risk_level_rank(best)
    for level in levels:
        normalized = normalize_risk_level(level, default=default)
        rank = risk_level_rank(normalized)
        if rank > best_rank:
            best = normalized
            best_rank = rank
    return best


def build_risk_overview(
    issue_cards: Iterable[Dict[str, Any]],
    *,
    fallback_score: Any = 0.0,
    fallback_level: Any = "",
    fallback_confidence: Any = 0.0,
    fallback_severity: Any = 0.0,
    source: str = "",
) -> Dict[str, Any]:
    """Build a stable risk overview for priority boards and dossiers."""
    normalized_cards: List[Dict[str, Any]] = [
        item for item in issue_cards if isinstance(item, dict)
    ]
    issue_refs = [
        str(item.get("issue_id") or "").strip()
        for item in normalized_cards
        if str(item.get("issue_id") or "").strip()
    ]
    derived_priority = max((_as_float(item.get("priority")) for item in normalized_cards), default=0.0)
    derived_severity = max((_as_float(item.get("severity")) for item in normalized_cards), default=0.0)
    derived_confidence = max(
        (_as_float(item.get("confidence")) for item in normalized_cards), default=0.0
    )
    derived_level = pick_highest_risk_level(
        [item.get("risk_level") for item in normalized_cards],
        default="info" if normalized_cards else "low",
    )

    fallback_level_normalized = normalize_risk_level(fallback_level, default="low")
    fallback_score_value = _as_float(fallback_score)
    fallback_severity_value = _as_float(fallback_severity)
    if fallback_score_value > 0 and fallback_severity_value <= 0:
        fallback_severity_value = max(
            severity_from_level(fallback_level_normalized),
            min(100.0, fallback_score_value),
        )
    if fallback_severity_value <= 0 and fallback_level_normalized:
        fallback_severity_value = severity_from_level(fallback_level_normalized)

    priority_score = round(max(derived_priority, fallback_score_value), 1)
    severity = round(max(derived_severity, fallback_severity_value), 1)
    confidence = round(max(derived_confidence, _as_float(fallback_confidence)), 2)
    risk_level = pick_highest_risk_level(
        [derived_level, fallback_level_normalized, risk_level_from_score(priority_score)],
        default="low",
    )

    if priority_score <= 0 and severity > 0:
        priority_score = priority_from_scores(severity, confidence or 0.55)
    if severity <= 0 and priority_score > 0:
        severity = max(
            severity_from_level(risk_level),
            round(priority_score * 0.88, 1),
        )

    return {
        "risk_level": risk_level,
        "risk_label": risk_level_label(risk_level),
        "priority_score": round(priority_score, 1),
        "priority_band": priority_band_label(priority_score, risk_level),
        "severity": round(severity, 1),
        "confidence": round(confidence, 2),
        "issue_count": len(issue_refs),
        "issue_refs": issue_refs,
        "source": source or ("issue_engine" if normalized_cards else "fallback"),
    }


def build_risk_schema() -> Dict[str, Any]:
    """Expose the current unified risk schema inside report_package."""
    return {
        "allowed_levels": ["critical", "high", "medium", "low", "info"],
        "level_labels": dict(RISK_LEVEL_LABELS),
        "priority_score_bands": [
            {"level": "critical", "min_score": 85},
            {"level": "high", "min_score": 70},
            {"level": "medium", "min_score": 45},
            {"level": "low", "min_score": 15},
            {"level": "info", "min_score": 0},
        ],
        "status_enums": ["lead", "suspicious", "high_confidence", "corroborated"],
    }


_WEALTH_KEYWORDS = [
    "理财",
    "申购",
    "赎回",
    "本息",
    "结息",
    "分红",
    "财富",
    "余额宝",
    "零钱通",
    "基金",
]


def _iter_records(table: Any) -> List[Dict[str, Any]]:
    if isinstance(table, list):
        return [item for item in table if isinstance(item, dict)]
    to_dict = getattr(table, "to_dict", None)
    if callable(to_dict):
        try:
            records = to_dict("records")
        except TypeError:
            records = []
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    return []


def calculate_financial_ratio(
    table: Any,
    income_col: str = "收入(元)",
    transaction_desc_col: str = "交易摘要",
) -> float:
    """Estimate the share of wealth-management income in total income."""
    total_income = 0.0
    wealth_income = 0.0
    for row in _iter_records(table):
        amount = _as_float(row.get(income_col) or row.get("income") or row.get("收入"))
        if amount <= 0:
            continue
        total_income += amount
        description = str(
            row.get(transaction_desc_col) or row.get("摘要") or row.get("description") or ""
        )
        if any(keyword in description for keyword in _WEALTH_KEYWORDS):
            wealth_income += amount
    if total_income <= 0:
        return 0.0
    return round(max(0.0, min(1.0, wealth_income / total_income)), 4)


def calculate_family_transfer_ratio(
    table: Any,
    counterparty_col: str = "交易对手",
    family_members: Iterable[str] = (),
) -> float:
    """Estimate the ratio of transactions involving family members."""
    records = _iter_records(table)
    normalized_family = {
        str(item).strip() for item in family_members if str(item or "").strip()
    }
    if not records or not normalized_family:
        return 0.0
    family_hits = 0
    considered = 0
    for row in records:
        counterparty = str(
            row.get(counterparty_col) or row.get("counterparty") or row.get("对手方") or ""
        ).strip()
        if not counterparty:
            continue
        considered += 1
        if counterparty in normalized_family:
            family_hits += 1
    if considered <= 0:
        return 0.0
    return round(max(0.0, min(1.0, family_hits / considered)), 4)


@dataclass
class UnifiedRiskScore:
    total_score: float
    risk_level: str
    confidence: float
    reason: str
    details: Dict[str, Any]


class UnifiedRiskModel:
    """Compatibility wrapper for the legacy unified risk model interface."""

    def calculate_score(
        self,
        entity_name: str,
        evidence: Dict[str, Any],
        financial_ratio: float = 0.0,
        family_ratio: float = 0.0,
    ) -> UnifiedRiskScore:
        evidence = evidence if isinstance(evidence, dict) else {}

        money_loops = [item for item in evidence.get("money_loops", []) if isinstance(item, dict)]
        transit_channels = [
            item for item in evidence.get("transit_channels", []) if isinstance(item, dict)
        ]
        relay_chains = [item for item in evidence.get("relay_chains", []) if isinstance(item, dict)]
        relationship_clusters = [
            item for item in evidence.get("relationship_clusters", []) if isinstance(item, dict)
        ]
        discovered_nodes = [
            item for item in evidence.get("discovered_nodes", []) if isinstance(item, dict)
        ]
        direct_relations = [
            item for item in evidence.get("direct_relations", []) if isinstance(item, dict)
        ]
        wallet_summaries = [
            item for item in evidence.get("wallet_summaries", []) if isinstance(item, dict)
        ]
        wallet_alerts = [item for item in evidence.get("wallet_alerts", []) if isinstance(item, dict)]
        ml_anomalies = [item for item in evidence.get("ml_anomalies", []) if isinstance(item, dict)]
        related_entities = [
            str(item).strip()
            for item in evidence.get("related_entities", [])
            if str(item or "").strip()
        ]

        money_loop_score = min(
            28.0,
            max((_as_float(item.get("risk_score")) * 0.22 for item in money_loops), default=0.0)
            + max(0, len(money_loops) - 1) * 2.5,
        )

        channel_ratio = 0.0
        transit_channel = evidence.get("transit_channel", {})
        if isinstance(transit_channel, dict):
            in_amount = _as_float(transit_channel.get("in"))
            out_amount = _as_float(transit_channel.get("out"))
            if in_amount > 0 and out_amount > 0:
                channel_ratio = min(in_amount, out_amount) / max(in_amount, out_amount)
        max_channel_score = max(
            (_as_float(item.get("risk_score")) for item in transit_channels), default=0.0
        )
        channel_node_types = {
            str(item.get("node_type") or "").strip().lower()
            for item in transit_channels
            if item.get("node_type")
        }
        channel_multiplier = 0.72 if "person" in channel_node_types and "company" not in channel_node_types else 1.0
        channel_score = min(
            22.0,
            max_channel_score * 0.18 * channel_multiplier
            + (6.0 if channel_ratio >= 0.9 else 0.0),
        )

        relay_score = min(
            20.0,
            max((_as_float(item.get("risk_score")) * 0.18 for item in relay_chains), default=0.0)
            + max(0, len(relay_chains) - 1) * 2.0,
        )

        cluster_score = min(
            20.0,
            max(
                (
                    _as_float(item.get("risk_score")) * 0.18
                    + _as_float(item.get("loop_count")) * 1.4
                    + _as_float(item.get("relay_count")) * 1.2
                )
                for item in relationship_clusters
            )
            if relationship_clusters
            else 0.0,
        )

        external_node_score = min(
            16.0,
            sum(
                max(2.0, _as_float(item.get("risk_score")) * 0.08 + _as_float(item.get("occurrences")) * 1.2)
                for item in discovered_nodes[:3]
            ),
        )

        family_direct_relation_count = sum(
            1
            for item in direct_relations
            if str(item.get("relationship_context") or "").strip().lower() == "family"
        )
        all_family_direct = bool(direct_relations) and family_direct_relation_count == len(
            direct_relations
        )
        direct_total_amount = sum(_as_float(item.get("amount")) for item in direct_relations)
        direct_relation_score = 0.0
        if direct_relations:
            direct_relation_score = min(
                18.0,
                (direct_total_amount / 100000.0) * (0.9 if all_family_direct else 2.3),
            )

        wallet_summary_score = min(
            16.0,
            sum(
                _as_float(item.get("risk_score")) * 0.16
                + _as_float(item.get("bank_card_overlap_count")) * 1.2
                + _as_float(item.get("alias_match_count")) * 1.2
                + _as_float(item.get("phone_overlap_count")) * 1.0
                + min(4.0, _as_float(item.get("third_party_total")) / 100000.0 * 0.6)
                + min(3.0, _as_float(item.get("transaction_count")) * 0.02)
                for item in wallet_summaries[:3]
            ),
        )
        wallet_alert_score = min(
            18.0,
            sum(
                _as_float(item.get("risk_score")) * 0.18
                + (4.0 if normalize_risk_level(item.get("risk_level")) in {"high", "critical"} else 0.0)
                + min(2.0, _as_float(item.get("amount")) / 100000.0 * 0.5)
                for item in wallet_alerts[:3]
            ),
        )

        ml_score = min(
            12.0,
            max((_as_float(item.get("risk_score")) * 0.12 for item in ml_anomalies), default=0.0),
        )

        total_score = (
            money_loop_score
            + channel_score
            + relay_score
            + cluster_score
            + external_node_score
            + direct_relation_score
            + wallet_summary_score
            + wallet_alert_score
            + ml_score
        )

        if financial_ratio > 0:
            total_score -= min(10.0, financial_ratio * 16.0)
        if family_ratio > 0:
            total_score -= min(8.0, family_ratio * 18.0)
        if all_family_direct and channel_score <= 0 and relay_score <= 0 and cluster_score <= 0:
            total_score -= 8.0
        total_score = round(max(0.0, min(100.0, total_score)), 1)

        confidence_candidates = [
            _as_float(item.get("confidence"))
            for bucket in (
                money_loops,
                transit_channels,
                relay_chains,
                relationship_clusters,
                discovered_nodes,
                direct_relations,
                wallet_summaries,
                wallet_alerts,
                ml_anomalies,
            )
            for item in bucket
            if isinstance(item, dict)
        ]
        confidence = max(confidence_candidates or [0.68])
        if _as_dict(evidence.get("money_loop_meta")).get("truncated"):
            confidence *= 0.82
        if _as_dict(evidence.get("relay_meta")).get("truncated"):
            confidence *= 0.9
        if _as_dict(evidence.get("relationship_meta")).get("truncated"):
            confidence *= 0.9
        total_records = int(_as_float(evidence.get("total_records")))
        if total_records >= 3000:
            confidence *= 0.96
        confidence = round(max(0.6, min(0.98, confidence)), 2)

        if total_score >= 70:
            risk_level = "CRITICAL"
        elif total_score >= 45:
            risk_level = "HIGH"
        elif total_score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        reason_parts: List[str] = []
        if money_loop_score > 0:
            reason_parts.append("资金闭环")
        if channel_score > 0:
            reason_parts.append("过账通道")
        if relay_score > 0:
            reason_parts.append("第三方中转")
        if cluster_score > 0:
            reason_parts.append("关系簇")
        if external_node_score > 0 or related_entities:
            reason_parts.append("外围节点")
        if direct_relation_score > 0:
            reason_parts.append("家庭内部直接往来" if all_family_direct else "直接往来")
        if wallet_summary_score > 0 or wallet_alert_score > 0:
            reason_parts.append("电子钱包")
        if ml_score > 0:
            reason_parts.append("异常交易")
        if not reason_parts:
            reason_parts.append("未见显著风险线索")

        details = {
            "money_loop_score": round(money_loop_score, 1),
            "channel_score": round(channel_score, 1),
            "relay_score": round(relay_score, 1),
            "cluster_score": round(cluster_score, 1),
            "external_node_score": round(external_node_score, 1),
            "entity_score": round(min(10.0, len(set(related_entities)) * 1.5), 1),
            "direct_relation_score": round(direct_relation_score, 1),
            "wallet_summary_score": round(wallet_summary_score, 1),
            "wallet_alert_score": round(wallet_alert_score, 1),
            "ml_score": round(ml_score, 1),
            "evidence_summary": {
                "money_loop_count": len(money_loops),
                "relay_count": len(relay_chains),
                "cluster_count": len(relationship_clusters),
                "external_node_count": len(discovered_nodes),
                "direct_relation_count": len(direct_relations),
                "family_direct_relation_count": family_direct_relation_count,
                "wallet_summary_count": len(wallet_summaries),
                "wallet_alert_count": len(wallet_alerts),
            },
        }

        return UnifiedRiskScore(
            total_score=total_score,
            risk_level=risk_level,
            confidence=confidence,
            reason="、".join(_unique_reason_parts(reason_parts)),
            details=details,
        )


def _unique_reason_parts(parts: Iterable[str]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for part in parts:
        text = str(part or "").strip()
        if not text or text in seen:
            continue
        ordered.append(text)
        seen.add(text)
    return ordered
