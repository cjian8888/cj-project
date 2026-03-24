#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚合排序结果消费辅助方法。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import utils

logger = utils.setup_logger(__name__)


def _normalize_entity_name(name: Any) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    return utils.normalize_person_name(text) or utils.normalize_name(text) or text


def extract_aggregation_payload(
    aggregation: Any = None,
    derived_data: Optional[Dict[str, Any]] = None,
    analysis_results: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """从聚合器实例、derived_data 或 analysis_results 中提取聚合结果。"""
    candidates = [aggregation]
    if isinstance(derived_data, dict):
        candidates.append(derived_data.get("aggregation"))
    if isinstance(analysis_results, dict):
        candidates.append(analysis_results.get("aggregation"))

    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, dict):
            return candidate
        to_dict = getattr(candidate, "to_dict", None)
        if callable(to_dict):
            try:
                payload = to_dict()
            except Exception as exc:
                logger.warning(f"提取 aggregation payload 失败: {exc}")
                continue
            if isinstance(payload, dict):
                return payload
    return {}


def normalize_aggregation_ranked_entities(
    aggregation_payload: Dict[str, Any],
    scope_entities: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """标准化聚合排序实体，供报告和前端复用。"""
    ranked = aggregation_payload.get("rankedEntities")
    if not isinstance(ranked, list):
        ranked = aggregation_payload.get("ranked_entities", [])
    if not isinstance(ranked, list):
        return []

    scope_norm = {
        _normalize_entity_name(name)
        for name in (scope_entities or [])
        if _normalize_entity_name(name)
    }

    normalized_items: List[Dict[str, Any]] = []
    for item in ranked:
        if not isinstance(item, dict):
            continue
        entity_name = str(item.get("name") or item.get("entity") or "").strip()
        if not entity_name:
            continue

        entity_norm = _normalize_entity_name(entity_name)
        if scope_norm and entity_norm not in scope_norm:
            continue

        explainability = item.get("aggregationExplainability")
        if not isinstance(explainability, dict):
            explainability = item.get("aggregation_explainability", {})
        if not isinstance(explainability, dict):
            explainability = {}

        top_clues = explainability.get("top_clues", [])
        if not isinstance(top_clues, list):
            top_clues = []

        risk_score = float(item.get("riskScore", item.get("risk_score", 0)) or 0)
        risk_confidence = float(
            item.get("riskConfidence", item.get("risk_confidence", 0.05)) or 0.05
        )
        high_priority_clue_count = int(
            float(
                item.get(
                    "highPriorityClueCount",
                    item.get("high_priority_clue_count", 0),
                )
                or 0
            )
        )
        top_evidence_score = float(
            item.get("topEvidenceScore", item.get("top_evidence_score", 0)) or 0
        )
        evidence_count = int(float(item.get("evidenceCount", item.get("evidence_count", 0)) or 0))
        normalized_items.append(
            {
                "name": entity_name,
                "entity": entity_name,
                "entity_type": str(
                    item.get("entityType", item.get("entity_type", ""))
                ).strip(),
                "risk_score": risk_score,
                "risk_confidence": risk_confidence,
                "risk_level": str(
                    item.get("riskLevel", item.get("risk_level", "low")) or "low"
                ).lower(),
                "high_priority_clue_count": high_priority_clue_count,
                "top_evidence_score": top_evidence_score,
                "evidence_count": evidence_count,
                "summary": str(item.get("summary", "") or "").strip(),
                "reasons": [
                    str(reason).strip()
                    for reason in (item.get("reasons", []) or [])
                    if str(reason).strip()
                ],
                "top_clues": [
                    str(clue.get("description", "")).strip()
                    for clue in top_clues[:3]
                    if isinstance(clue, dict) and str(clue.get("description", "")).strip()
                ],
                "aggregation_explainability": explainability,
            }
        )

    normalized_items.sort(
        key=lambda item: (
            -item["risk_score"],
            -item["risk_confidence"],
            -item["top_evidence_score"],
            -item["high_priority_clue_count"],
            -item["evidence_count"],
            item["name"],
        )
    )
    return normalized_items


def build_aggregation_overview(
    aggregation: Any = None,
    derived_data: Optional[Dict[str, Any]] = None,
    analysis_results: Optional[Dict[str, Any]] = None,
    scope_entities: Optional[Iterable[str]] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """构建聚合排序摘要。"""
    payload = extract_aggregation_payload(
        aggregation=aggregation,
        derived_data=derived_data,
        analysis_results=analysis_results,
    )
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    ranked = normalize_aggregation_ranked_entities(payload, scope_entities=scope_entities)
    highlights = [
        item for item in ranked if item["risk_score"] >= 50 or item["high_priority_clue_count"] > 0
    ][:limit]
    avg_score = round(
        sum(item["risk_score"] for item in ranked) / len(ranked),
        1,
    ) if ranked else 0.0

    if summary.get("极高风险实体数", 0) > 0 or any(item["risk_score"] >= 80 for item in highlights):
        risk_assessment = "高风险"
    elif summary.get("高风险实体数", 0) > 0 or any(item["risk_score"] >= 60 for item in highlights):
        risk_assessment = "关注级"
    elif highlights:
        risk_assessment = "低风险"
    else:
        risk_assessment = ""

    return {
        "summary": summary,
        "ranked": ranked,
        "highlights": highlights,
        "avg_score": avg_score,
        "risk_assessment": risk_assessment,
        "analysis_metadata": payload.get("analysisMetadata", payload.get("analysis_metadata", {})),
    }


def annotate_focus_entities_with_graph(
    entities: List[Dict[str, Any]],
    graph_nodes: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """补充重点对象是否在当前图谱采样中可见。"""
    visible_map: Dict[str, Dict[str, Any]] = {}
    for node in graph_nodes or []:
        if not isinstance(node, dict):
            continue
        candidate_names = [
            node.get("label"),
            node.get("id"),
            node.get("name"),
        ]
        for candidate in candidate_names:
            normalized = _normalize_entity_name(candidate)
            if normalized and normalized not in visible_map:
                visible_map[normalized] = node

    annotated: List[Dict[str, Any]] = []
    for item in entities:
        normalized = _normalize_entity_name(item.get("name") or item.get("entity"))
        node = visible_map.get(normalized)
        annotated_item = dict(item)
        annotated_item["in_graph"] = bool(node)
        if isinstance(node, dict):
            annotated_item["graph_node_id"] = node.get("id")
            annotated_item["graph_group"] = node.get("group")
        annotated.append(annotated_item)
    return annotated
