#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资金路径 explainability 结构化辅助方法。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import utils

REPRESENTATIVE_PATH_RETURN_LIMIT = 5


def _format_dt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, datetime) else value.strftime("%Y-%m-%d")
    text = str(value).strip()
    return text[:19]


def _normalize_nodes(values: Iterable[Any]) -> List[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _summarize_supporting_refs(payload: Dict[str, Any]) -> Dict[str, Any]:
    path_type = str(payload.get("path_type", "") or "").strip()

    if path_type == "fund_cycle":
        segments = payload.get("edge_segments", []) or []
        totals = []
        returned = []
        truncated = False
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            refs = segment.get("transaction_refs", []) or []
            returned_count = _safe_int(segment.get("transaction_refs_returned", len(refs)), len(refs))
            total_count = _safe_int(
                segment.get("transaction_refs_total", segment.get("transaction_count", returned_count)),
                returned_count,
            )
            totals.append(max(total_count, len(refs)))
            returned.append(max(returned_count, len(refs)))
            truncated = truncated or bool(segment.get("transaction_refs_truncated"))
        total = sum(totals)
        returned_total = sum(returned)
        return {
            "kind": "transaction_refs",
            "returned": returned_total,
            "total": total,
            "truncated": truncated or total > returned_total,
            "notice": (
                f"当前回传 {returned_total} 条逐跳原始流水，实际共 {total} 条"
                if total > returned_total
                else f"当前回传 {returned_total} 条逐跳原始流水"
            ),
        }

    if path_type == "third_party_relay":
        time_axis = payload.get("time_axis", []) or []
        returned_total = len(time_axis)
        total = max(_safe_int(payload.get("time_axis_total", returned_total), returned_total), returned_total)
        return {
            "kind": "time_axis",
            "returned": returned_total,
            "total": total,
            "truncated": bool(payload.get("time_axis_truncated")) or total > returned_total,
            "notice": (
                f"当前回传 {returned_total} 步时间轴事件，实际共 {total} 步"
                if total > returned_total
                else f"当前回传 {returned_total} 步时间轴事件"
            ),
        }

    if path_type == "direct_flow":
        refs = payload.get("transaction_refs", []) or []
        returned_total = len(refs)
        total = max(_safe_int(payload.get("transaction_refs_total", returned_total), returned_total), returned_total)
        return {
            "kind": "transaction_refs",
            "returned": returned_total,
            "total": total,
            "truncated": bool(payload.get("transaction_refs_truncated")) or total > returned_total,
            "notice": (
                f"当前回传 {returned_total} 条直接往来原始流水，实际共 {total} 条"
                if total > returned_total
                else f"当前回传 {returned_total} 条直接往来原始流水"
            ),
        }

    if path_type == "relationship_cluster":
        representative_paths = payload.get("representative_paths", []) or []
        total = max(
            _safe_int(
                payload.get(
                    "representative_path_total",
                    payload.get("representative_path_count", len(representative_paths)),
                ),
                len(representative_paths),
            ),
            len(representative_paths),
        )
        return {
            "kind": "representative_paths",
            "returned": len(representative_paths),
            "total": total,
            "truncated": total > len(representative_paths),
            "notice": (
                f"当前回传 {len(representative_paths)} 条代表路径，实际共 {total} 条"
                if total > len(representative_paths)
                else f"当前回传 {len(representative_paths)} 条代表路径"
            ),
        }

    return {
        "kind": "unknown",
        "returned": 0,
        "total": 0,
        "truncated": False,
        "notice": "",
    }


def _build_evidence_template(payload: Dict[str, Any]) -> Dict[str, Any]:
    path_type = str(payload.get("path_type", "") or "").strip()
    summary = str(payload.get("summary", "") or "").strip()
    inspection_points = [
        str(point).strip()
        for point in list(payload.get("inspection_points", []) or [])
        if str(point).strip()
    ]
    path = str(payload.get("path", "") or "").strip()
    support = _summarize_supporting_refs(payload)
    metrics: List[Dict[str, str]] = []

    if path_type == "fund_cycle":
        metrics = [
            {"label": "节点数", "value": str(_safe_int(payload.get("hop_count"), 0))},
            {"label": "金额口径", "value": str(payload.get("amount_basis", "path_only") or "path_only")},
        ]
        estimated_amount = _safe_float(payload.get("estimated_amount"), 0.0)
        if estimated_amount > 0:
            metrics.append({"label": "估算回流金额", "value": f"{utils.format_currency(estimated_amount)} 元"})
        bottleneck = payload.get("bottleneck_edge", {}) or {}
        if isinstance(bottleneck, dict) and bottleneck:
            metrics.append(
                {
                    "label": "瓶颈边",
                    "value": f"{bottleneck.get('from', '未知')} -> {bottleneck.get('to', '未知')}",
                }
            )
    elif path_type == "third_party_relay":
        metrics = [
            {"label": "时差", "value": f"{_safe_float(payload.get('time_diff_hours'), 0.0):.1f} 小时"},
            {"label": "差额比例", "value": f"{_safe_float(payload.get('amount_diff_ratio'), 0.0) * 100:.1f}%"},
        ]
    elif path_type == "direct_flow":
        metrics = [
            {"label": "方向", "value": str(payload.get("direction", "unknown") or "unknown")},
            {"label": "金额", "value": f"{utils.format_currency(_safe_float(payload.get('amount'), 0.0))} 元"},
        ]
    elif path_type == "relationship_cluster":
        metrics = [
            {"label": "关系簇规模", "value": str(_safe_int(payload.get("component_size"), 0))},
            {"label": "代表路径数", "value": str(_safe_int(payload.get("representative_path_count"), 0))},
        ]

    headline = path or summary or path_type or "路径证据"
    return {
        "headline": headline,
        "summary": summary,
        "key_points": inspection_points[:3],
        "metrics": metrics,
        "supporting_refs": support,
    }


def build_path_evidence_template(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _build_evidence_template(payload if isinstance(payload, dict) else {})


def get_or_build_path_evidence_template(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    existing = payload.get("evidence_template")
    if isinstance(existing, dict) and existing:
        return existing
    return build_path_evidence_template(payload)


def _representative_path_priority(item: Dict[str, Any], focus_nodes: Optional[Iterable[str]] = None) -> Tuple[float, str]:
    path_type = str(item.get("path_type", "") or "").strip()
    amount = _safe_float(item.get("amount"), 0.0)
    risk_score = _safe_float(item.get("risk_score"), 0.0)
    confidence = _safe_float(item.get("confidence"), 0.0)
    payload = item.get("path_explainability") if isinstance(item.get("path_explainability"), dict) else {}
    nodes = _normalize_nodes(item.get("nodes", []) or payload.get("nodes", []) or [])
    focus_set = {str(node).strip() for node in (focus_nodes or []) if str(node).strip()}
    matched_focus = len([node for node in nodes if node in focus_set]) if focus_set else 0
    support = _summarize_supporting_refs(payload if isinstance(payload, dict) else item)

    score = 0.0
    reasons: List[str] = []
    type_weight = {
        "fund_cycle": 42.0,
        "third_party_relay": 34.0,
        "direct_flow": 18.0,
    }.get(path_type, 8.0)
    score += type_weight
    reasons.append(f"类型权重 {type_weight:.0f}")

    if amount >= 1_000_000:
        score += 24
        reasons.append("金额 >= 100万")
    elif amount >= 500_000:
        score += 20
        reasons.append("金额 >= 50万")
    elif amount >= 100_000:
        score += 14
        reasons.append("金额 >= 10万")
    elif amount > 0:
        score += 8
        reasons.append("金额 > 0")

    score += min(22.0, risk_score / 4.0)
    if risk_score > 0:
        reasons.append(f"风险评分 {risk_score:.1f}")

    score += min(10.0, confidence * 10.0)
    if confidence > 0:
        reasons.append(f"置信度 {confidence:.2f}")

    if matched_focus > 0:
        bonus = matched_focus * 6.0
        score += bonus
        reasons.append(f"命中核查对象 {matched_focus} 个")

    if nodes:
        structural_bonus = min(6.0, len(nodes) * 1.5)
        score += structural_bonus
        reasons.append(f"链路节点 {len(nodes)} 个")

    if support.get("returned", 0) > 0:
        support_bonus = min(6.0, max(_safe_int(support.get("returned"), 0), 1))
        score += support_bonus
        reasons.append(f"支撑证据 {support.get('returned', 0)} 条")
    if support.get("truncated"):
        score -= 3.0
        reasons.append("存在截断")

    if payload.get("summary"):
        score += 2.0
        reasons.append("有路径摘要")
    if payload.get("inspection_points"):
        score += min(3.0, len(list(payload.get("inspection_points", []) or [])))
        reasons.append("有解释要点")

    return round(score, 2), "；".join(reasons[:6])


def rank_representative_paths(
    representative_paths: Optional[List[Dict[str, Any]]],
    focus_nodes: Optional[Iterable[str]] = None,
    limit: int = REPRESENTATIVE_PATH_RETURN_LIMIT,
) -> List[Dict[str, Any]]:
    paths = []
    for item in list(representative_paths or []):
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        payload = normalized.get("path_explainability")
        if isinstance(payload, dict):
            normalized["path_explainability"] = ensure_path_evidence_template(payload)
            normalized["evidence_template"] = normalized["path_explainability"].get("evidence_template", {})
        score, reason = _representative_path_priority(normalized, focus_nodes=focus_nodes)
        normalized["priority_score"] = score
        normalized["priority_reason"] = reason
        paths.append(normalized)

    paths.sort(
        key=lambda item: (
            -_safe_float(item.get("priority_score"), 0.0),
            -_safe_float(item.get("risk_score"), 0.0),
            -_safe_float(item.get("confidence"), 0.0),
            -_safe_float(item.get("amount"), 0.0),
            str(item.get("path", "") or ""),
        )
    )

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in paths:
        key = (
            str(item.get("path_type", "") or "").strip(),
            str(item.get("path", "") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max(limit, 1):
            break
    return deduped


def ensure_path_evidence_template(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload or {})
    normalized["evidence_template"] = get_or_build_path_evidence_template(normalized)
    return normalized


def build_cycle_path_explainability(
    nodes: Iterable[Any],
    path: str,
    focus_nodes: Optional[Iterable[str]] = None,
    total_amount: float = 0.0,
    search_metadata: Optional[Dict[str, Any]] = None,
    edge_segments: Optional[List[Dict[str, Any]]] = None,
    bottleneck_edge: Optional[Dict[str, Any]] = None,
    amount_basis_detail: str = "",
) -> Dict[str, Any]:
    normalized_nodes = _normalize_nodes(nodes)
    focus_set = {str(item).strip() for item in (focus_nodes or []) if str(item).strip()}
    core_nodes = [node for node in normalized_nodes if node in focus_set] if focus_set else []
    external_nodes = [node for node in normalized_nodes if node not in focus_set] if focus_set else []
    truncated = bool((search_metadata or {}).get("truncated"))
    truncated_reasons = list((search_metadata or {}).get("truncated_reasons", []) or [])

    amount_basis = "min_edge_estimate" if total_amount and total_amount > 0 else "path_only"
    summary = (
        f"闭环路径包含 {len(normalized_nodes)} 个节点"
        f"{f'，其中外围节点 {len(external_nodes)} 个' if focus_set else ''}"
        f"{f'，估算回流金额 {utils.format_currency(total_amount)} 元' if total_amount and total_amount > 0 else '，当前仅能稳定确认回流路径'}"
    )

    inspection_points = [
        f"回流路径: {path or '未知路径'}",
        f"节点构成: 核查对象 {len(core_nodes) if focus_set else '未区分'} / 外围节点 {len(external_nodes) if focus_set else '未区分'}",
        (
            f"金额口径: 最小边额估算 {utils.format_currency(total_amount)} 元"
            if total_amount and total_amount > 0
            else "金额口径: 当前仅输出路径结构，未形成稳定金额估算"
        ),
    ]
    normalized_segments = list(edge_segments or [])
    if bottleneck_edge and isinstance(bottleneck_edge, dict):
        bottleneck_label = (
            f"{bottleneck_edge.get('from', '未知')} -> {bottleneck_edge.get('to', '未知')}"
        )
        inspection_points.append(
            f"瓶颈边: {bottleneck_label}，累计金额 {utils.format_currency(float(bottleneck_edge.get('amount', 0) or 0))} 元"
        )
    if amount_basis_detail:
        inspection_points.append(f"金额依据: {amount_basis_detail}")
    if truncated:
        inspection_points.append(
            f"搜索状态: 存在截断（{'、'.join(truncated_reasons) or 'search_truncated'}）"
        )

    result = {
        "path_type": "fund_cycle",
        "path": path,
        "nodes": normalized_nodes,
        "hop_count": len(normalized_nodes),
        "core_nodes": core_nodes,
        "external_nodes": external_nodes,
        "returns_to_origin": bool(normalized_nodes),
        "amount_basis": amount_basis,
        "amount_basis_detail": amount_basis_detail,
        "estimated_amount": float(total_amount or 0),
        "edge_segments": normalized_segments,
        "bottleneck_edge": bottleneck_edge or {},
        "truncated": truncated,
        "truncated_reasons": truncated_reasons,
        "summary": summary,
        "inspection_points": inspection_points,
    }
    return ensure_path_evidence_template(result)


def build_relay_path_explainability(relay: Dict[str, Any]) -> Dict[str, Any]:
    from_node = str(relay.get("from", "")).strip()
    relay_node = str(relay.get("relay", "")).strip()
    to_node = str(relay.get("to", "")).strip()
    outflow_amount = float(relay.get("outflow_amount", 0) or 0)
    inflow_amount = float(relay.get("inflow_amount", 0) or 0)
    amount_diff = float(relay.get("amount_diff", abs(outflow_amount - inflow_amount)) or 0)
    ratio = amount_diff / max(outflow_amount, 1) if outflow_amount > 0 else 0.0
    time_diff_hours = float(relay.get("time_diff_hours", 0) or 0)
    path = f"{from_node} → {relay_node} → {to_node}".strip(" →")

    summary = (
        f"资金在 {time_diff_hours:.1f} 小时内经 {relay_node or '中间节点'} "
        f"由 {from_node or '未知'} 转向 {to_node or '未知'}，"
        f"金额差比例 {ratio * 100:.1f}%"
    )
    time_axis = [
        {
            "step": 1,
            "event_type": "outflow",
            "label": f"{from_node or '未知'} 向 {relay_node or '中间节点'} 转出",
            "time": _format_dt(relay.get("outflow_date")),
            "amount": outflow_amount,
            "source_file": str(relay.get("outflow_source_file", "") or "").strip(),
            "source_row_index": relay.get("outflow_source_row_index"),
        },
        {
            "step": 2,
            "event_type": "inflow",
            "label": f"{relay_node or '中间节点'} 向 {to_node or '未知'} 转入",
            "time": _format_dt(relay.get("inflow_date")),
            "amount": inflow_amount,
            "source_file": str(relay.get("inflow_source_file", "") or "").strip(),
            "source_row_index": relay.get("inflow_source_row_index"),
        },
    ]
    sequence_summary = (
        f"第1步 {time_axis[0]['label']}，第2步 {time_axis[1]['label']}，"
        f"两步相隔 {time_diff_hours:.1f} 小时"
    )
    time_axis_total = len(time_axis)
    inspection_points = [
        f"链路路径: {path or '未知链路'}",
        f"时间关系: {_format_dt(relay.get('outflow_date')) or '未知'} -> {_format_dt(relay.get('inflow_date')) or '未知'}（{time_diff_hours:.1f} 小时）",
        f"金额关系: 转出 {utils.format_currency(outflow_amount)} 元 / 转入 {utils.format_currency(inflow_amount)} 元 / 差额 {utils.format_currency(amount_diff)} 元",
        f"判定特征: {'快速中转' if time_diff_hours <= 24 else '延时中转'}，{'金额高度对齐' if ratio <= 0.10 else '金额存在偏差'}",
    ]

    result = {
        "path_type": "third_party_relay",
        "path": path,
        "nodes": [node for node in [from_node, relay_node, to_node] if node],
        "hop_count": 2 if relay_node else 1,
        "relay_node": relay_node,
        "outflow_date": _format_dt(relay.get("outflow_date")),
        "inflow_date": _format_dt(relay.get("inflow_date")),
        "time_diff_hours": time_diff_hours,
        "amount_basis": "matched_transfer_pair",
        "outflow_amount": outflow_amount,
        "inflow_amount": inflow_amount,
        "amount_diff": amount_diff,
        "amount_diff_ratio": ratio,
        "fast_relay": time_diff_hours <= 24,
        "amount_aligned": ratio <= 0.10,
        "time_axis": time_axis,
        "time_axis_total": time_axis_total,
        "time_axis_sample_count": time_axis_total,
        "time_axis_truncated": False,
        "sequence_summary": sequence_summary,
        "summary": summary,
        "inspection_points": inspection_points,
    }
    return ensure_path_evidence_template(result)


def build_direct_flow_path_explainability(flow: Dict[str, Any]) -> Dict[str, Any]:
    from_node = str(flow.get("from", "") or "").strip()
    to_node = str(flow.get("to", "") or "").strip()
    path = f"{from_node} → {to_node}".strip(" →")
    amount = float(flow.get("amount", 0) or 0)
    direction = str(flow.get("direction", "") or "").strip()
    transaction_refs = [
        ref for ref in list(flow.get("transaction_refs", []) or []) if isinstance(ref, dict)
    ]
    date_text = _format_dt(flow.get("date"))
    description = str(flow.get("description", "") or "").strip()
    source_file = str(flow.get("source_file", "") or "").strip()
    source_row_index = flow.get("source_row_index")

    if transaction_refs:
        if not date_text:
            date_text = _format_dt(transaction_refs[0].get("date"))
        if not description:
            description = next(
                (
                    str(ref.get("description", "") or "").strip()
                    for ref in transaction_refs
                    if str(ref.get("description", "") or "").strip()
                ),
                "",
            )
        if not source_file:
            source_file = str(transaction_refs[0].get("source_file", "") or "").strip()
        if source_row_index in (None, ""):
            source_row_index = transaction_refs[0].get("source_row_index")

    if direction == "receive":
        direction_label = "收款"
    elif direction == "pay":
        direction_label = "付款"
    else:
        direction_label = "方向待补充"

    summary = (
        f"{from_node or '未知'} 与 {to_node or '未知'} 存在直接资金往来，"
        f"单笔金额 {utils.format_currency(amount)} 元"
    )
    inspection_points = [
        f"链路路径: {path or '未知路径'}",
        f"交易时间: {date_text or '未知'}",
        f"交易方向: {direction_label}",
    ]
    if description:
        inspection_points.append(f"交易摘要: {description}")
    if len(transaction_refs) > 1:
        inspection_points.append(f"原始侧账: 已匹配 {len(transaction_refs)} 条双边流水")

    if not transaction_refs:
        transaction_refs = [
            {
                "date": date_text,
                "amount": amount,
                "source_file": source_file,
                "source_row_index": source_row_index,
                "description": description,
                "direction": direction,
                "counterparty_raw": str(flow.get("counterparty_raw", "") or "").strip(),
            }
        ]

    result = {
        "path_type": "direct_flow",
        "path": path,
        "nodes": [node for node in [from_node, to_node] if node],
        "hop_count": 1 if path else 0,
        "amount_basis": "single_transaction",
        "amount": amount,
        "direction": direction,
        "transaction_refs": transaction_refs,
        "transaction_refs_total": max(
            _safe_int(flow.get("transaction_refs_total", len(transaction_refs)), len(transaction_refs)),
            len(transaction_refs),
        ),
        "transaction_ref_sample_count": len(transaction_refs),
        "transaction_refs_truncated": False,
        "summary": summary,
        "inspection_points": inspection_points,
    }
    return ensure_path_evidence_template(result)


def build_cluster_path_explainability(
    cluster: Dict[str, Any],
    representative_paths: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    core_members = _normalize_nodes(cluster.get("core_members", []) or [])
    external_members = _normalize_nodes(cluster.get("external_members", []) or [])
    all_nodes = _normalize_nodes(cluster.get("all_nodes", []) or core_members + external_members)
    direct_flow_count = int(cluster.get("direct_flow_count", 0) or 0)
    relay_count = int(cluster.get("relay_count", 0) or 0)
    loop_count = int(cluster.get("loop_count", 0) or 0)
    relation_mix = {
        "direct_flow_count": direct_flow_count,
        "relay_count": relay_count,
        "loop_count": loop_count,
    }
    dominant_pattern = max(relation_mix.items(), key=lambda item: item[1])[0] if any(relation_mix.values()) else "mixed"
    total_amount = float(cluster.get("total_amount", 0) or 0)

    summary = (
        f"该关系簇包含核心成员 {len(core_members)} 个、外围成员 {len(external_members)} 个，"
        f"以 {'闭环' if dominant_pattern == 'loop_count' else '中转' if dominant_pattern == 'relay_count' else '直接往来' if dominant_pattern == 'direct_flow_count' else '混合'} 关系为主"
    )
    inspection_points = [
        f"成员构成: 核心 {'、'.join(core_members) or '未标注'} / 外围 {'、'.join(external_members) or '无'}",
        f"关系计数: 直接往来 {direct_flow_count} / 第三方中转 {relay_count} / 资金闭环 {loop_count}",
        (
            f"金额口径: 聚合金额估算 {utils.format_currency(total_amount)} 元"
            if total_amount > 0
            else "金额口径: 当前仅稳定识别关系结构，未形成统一金额口径"
        ),
    ]
    if representative_paths:
        inspection_points.append(f"代表路径: 已提炼 {len(representative_paths)} 条优先核查链路")
        inspection_points.append(
            "代表性路径: " + "；".join(
                str(item.get("path", "")).strip() for item in representative_paths[:3] if str(item.get("path", "")).strip()
            )
        )

    result = {
        "path_type": "relationship_cluster",
        "cluster_id": str(cluster.get("cluster_id", "")).strip(),
        "all_nodes": all_nodes,
        "core_members": core_members,
        "external_members": external_members,
        "component_size": len(all_nodes),
        "relation_mix": relation_mix,
        "dominant_pattern": dominant_pattern,
        "representative_path_count": len(representative_paths or []),
        "representative_path_total": _safe_int(
            cluster.get("representative_path_total", len(representative_paths or [])),
            len(representative_paths or []),
        ),
        "representative_paths": representative_paths or [],
        "amount_basis": "cluster_aggregate" if total_amount > 0 else "structure_only",
        "total_amount": total_amount,
        "summary": summary,
        "inspection_points": inspection_points,
    }
    return ensure_path_evidence_template(result)
