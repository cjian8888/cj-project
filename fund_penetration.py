#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金穿透分析模块（增强版 v2.0）

【核心升级 - 2026-01-11】
从单步统计升级为图论路径挖掘：
1. 多跳路径追踪: 发现 A→B→C→D 的复杂资金链路
2. 资金闭环检测: 识别 A→B→C→A 的利益回流模式
3. 过账通道识别: 发现流量巨大但余额归零的中转节点

审计价值:
- 单步分析只能发现"A给B钱"，无法发现通过空壳公司中转的利益输送
- 图算法可以追踪"自然人→空壳A→空壳B→亲属"的多跳链路
"""

import os
import re
import pandas as pd
from typing import Dict, List, Set, Tuple
from datetime import datetime
from collections import defaultdict

import config
import utils
import risk_scoring
from utils.path_explainability import build_cycle_path_explainability

logger = utils.setup_logger(__name__)

TRANSACTION_REF_RETURN_LIMIT = 200


# ============================================================
# 资金图数据结构 (MoneyGraph)
# ============================================================


class MoneyGraph:
    """
    有向资金图 - 用于多跳路径分析

    审计应用场景：
    - 节点: 人员/公司
    - 边: 资金往来 (带金额和时间属性)
    - 路径: A→B→C 的资金链路
    - 闭环: A→B→C→A 的利益回流
    """

    def __init__(self):
        # 邻接表: source -> [(target, amount, date), ...]
        self.edges = defaultdict(list)
        # 节点集合
        self.nodes = set()
        # 节点类型: person/company
        self.node_types = {}
        # 节点流量统计: node -> {inflow, outflow}
        self.node_flows = defaultdict(lambda: {"inflow": 0, "outflow": 0})
        # 最近一次闭环搜索的元数据
        self.last_cycle_search_meta = {}

    def add_edge(
        self,
        source: str,
        target: str,
        amount: float,
        date,
        edge_type: str = "transfer",
        supporting_transactions: List[Dict] = None,
        transaction_count: int = 0,
        supporting_transactions_total: int = 0,
        supporting_transactions_truncated: bool = False,
        supporting_transactions_limit: int = TRANSACTION_REF_RETURN_LIMIT,
    ):
        """添加资金边"""
        self.nodes.add(source)
        self.nodes.add(target)
        self.edges[source].append(
            {
                "target": target,
                "amount": amount,
                "date": date,
                "type": edge_type,
                "supporting_transactions": list(supporting_transactions or []),
                "transaction_count": int(transaction_count or 0),
                "supporting_transactions_total": int(supporting_transactions_total or transaction_count or 0),
                "supporting_transactions_truncated": bool(supporting_transactions_truncated),
                "supporting_transactions_limit": int(supporting_transactions_limit or TRANSACTION_REF_RETURN_LIMIT),
            }
        )
        # 更新流量统计
        self.node_flows[source]["outflow"] += amount
        self.node_flows[target]["inflow"] += amount

    def set_node_type(self, node: str, node_type: str):
        """设置节点类型"""
        self.node_types[node] = node_type

    def find_all_paths(
        self, source: str, target: str, max_depth: int = 5
    ) -> List[List[str]]:
        """
        使用DFS查找从source到target的所有路径

        Args:
            source: 起点
            target: 终点
            max_depth: 最大搜索深度（跳数）

        Returns:
            路径列表，每个路径是节点序列
        """
        paths = []

        def dfs(current: str, path: List[str], visited: Set[str]):
            if len(path) > max_depth + 1:
                return

            if current == target and len(path) > 1:
                paths.append(path.copy())
                return

            for edge in self.edges.get(current, []):
                next_node = edge["target"]
                if next_node not in visited or next_node == target:
                    visited.add(next_node)
                    path.append(next_node)
                    dfs(next_node, path, visited)
                    path.pop()
                    if next_node != target:
                        visited.discard(next_node)

        dfs(source, [source], {source})
        return paths

    def find_cycles(
        self,
        min_length: int = 3,
        max_length: int = 4,
        key_nodes: List[str] = None,
        timeout_seconds: int = 30,
    ) -> List[List[str]]:
        """
        检测资金闭环（利益回流）- 性能优化版

        审计意义：
        - A→B→C→A 闭环说明资金最终回流到起点
        - 这是典型的洗钱或利益输送结构

        性能优化：
        1. 只从关键节点（核心人员/公司）开始搜索
        2. 添加超时机制
        3. 排除公共支付平台

        Args:
            min_length: 最小闭环长度
            max_length: 最大闭环长度
            key_nodes: 关键节点列表（只从这些节点开始搜索）
            timeout_seconds: 超时时间

        Returns:
            闭环列表
        """
        import time

        start_time = time.time()
        cycles = []
        timed_out = False
        search_node_truncated = False
        cycle_limit_hit = False
        max_cycles = 100

        # 公共节点排除列表（这些节点连接太多人，不是真正的闭环）
        # 【优化 2026-01-11】使用更精确的匹配规则
        PUBLIC_NODES_EXACT = ["支付宝", "微信", "财付通", "银联"]  # 完整匹配
        PUBLIC_NODES_CONTAINS = ["理财产品", "余额宝", "零钱通"]  # 包含匹配

        def is_public_node(node: str) -> bool:
            """
            判断是否为公共节点

            【优化】区分以下情况:
            1. 支付平台: 完整匹配 (支付宝、微信等)
            2. 银行: 需要更精确判断，"XX银行"是银行，"XX银行业务咨询公司"是可疑公司
            3. 理财: 只匹配明确的理财产品名称
            """
            if not node:
                return False

            # 完整匹配支付平台
            if node in PUBLIC_NODES_EXACT:
                return True

            # 包含匹配理财产品
            for pub in PUBLIC_NODES_CONTAINS:
                if pub in node:
                    return True

            # 银行的精确判断：只有纯银行名称才排除
            # "银行" 在名称中 且 没有 "公司"、"咨询"、"服务" 等后缀
            if "银行" in node:
                suspicious_suffixes = ["公司", "咨询", "服务", "代理", "中介", "担保"]
                if not any(suffix in node for suffix in suspicious_suffixes):
                    return True

            # 基金公司判断：只排除正规基金公司
            if "基金" in node and "销售" not in node and "代理" not in node:
                # 正规基金公司名称通常包含"基金管理"
                if "基金管理" in node or node.endswith("基金"):
                    return True

            return False

        def dfs_cycle(start: str, current: str, path: List[str], visited: Set[str]):
            nonlocal timed_out, cycle_limit_hit
            # 超时检查
            if time.time() - start_time > timeout_seconds:
                timed_out = True
                return

            if len(path) > max_length:
                return

            for edge in self.edges.get(current, []):
                next_node = edge["target"]

                # 跳过公共节点
                if is_public_node(next_node):
                    continue

                # 找到闭环
                if next_node == start and len(path) >= min_length:
                    cycles.append(path + [start])
                    if len(cycles) >= max_cycles:  # 限制最多100个闭环
                        cycle_limit_hit = True
                        return
                    continue

                # 继续搜索
                if next_node not in visited:
                    visited.add(next_node)
                    path.append(next_node)
                    dfs_cycle(start, next_node, path, visited)
                    path.pop()
                    visited.discard(next_node)

        # 确定搜索起点
        search_nodes = (
            key_nodes
            if key_nodes
            else [
                n for n in self.nodes if self.node_types.get(n) in ["person", "company"]
            ]
        )
        requested_start_nodes = len(search_nodes)

        # 如果还是太多，只取前50个
        if len(search_nodes) > 50:
            search_node_truncated = True
            search_nodes = search_nodes[:50]

        logger.info(
            f"  闭环搜索: 从 {len(search_nodes)} 个关键节点开始（超时{timeout_seconds}秒）"
        )

        # 从关键节点开始搜索闭环
        for node in search_nodes:
            if cycle_limit_hit:
                logger.warning(f"  闭环搜索达到结果上限 {max_cycles}，提前截断")
                break
            if time.time() - start_time > timeout_seconds:
                logger.warning(f"  闭环搜索超时（已找到 {len(cycles)} 个）")
                timed_out = True
                break
            if not is_public_node(node):
                dfs_cycle(node, node, [node], {node})

        # 去重（同一闭环可能从不同起点被发现）
        unique_cycles = []
        seen = set()
        for cycle in cycles:
            # 标准化闭环表示（从最小节点开始）
            min_idx = cycle.index(min(cycle[:-1]))  # 排除最后一个（与第一个相同）
            normalized = tuple(cycle[min_idx:-1] + cycle[:min_idx])
            if normalized not in seen:
                seen.add(normalized)
                unique_cycles.append(cycle)

        truncated_reasons = []
        if search_node_truncated:
            truncated_reasons.append("search_nodes_capped")
        if cycle_limit_hit:
            truncated_reasons.append("result_limit_hit")
        if timed_out:
            truncated_reasons.append("timeout")

        self.last_cycle_search_meta = {
            "timed_out": timed_out,
            "search_node_truncated": search_node_truncated,
            "cycle_limit_hit": cycle_limit_hit,
            "truncated": bool(truncated_reasons),
            "truncated_reasons": truncated_reasons,
            "requested_start_nodes": requested_start_nodes,
            "searched_start_nodes": len(search_nodes),
            "returned_count": len(unique_cycles),
            "raw_count": len(cycles),
            "timeout_seconds": timeout_seconds,
            "max_cycles": max_cycles,
        }

        return unique_cycles

    def identify_pass_through_channels(
        self, threshold_ratio: float = 0.9
    ) -> List[Dict]:
        """
        识别过账通道：流量巨大但进出平衡的节点

        审计意义：
        - 过账通道是资金"过客"，收多少立刻转走多少
        - 常见于空壳公司、马甲账户

        Args:
            threshold_ratio: 进出比例阈值（越接近1越是过账）

        Returns:
            过账通道列表
        """
        channels = []

        for node, flows in self.node_flows.items():
            inflow = flows["inflow"]
            outflow = flows["outflow"]

            if inflow == 0 or outflow == 0:
                continue

            # 计算进出比例
            ratio = min(inflow, outflow) / max(inflow, outflow)

            if (
                ratio >= threshold_ratio and inflow >= config.FUND_FLOW_MIN_AMOUNT
            ):  # 使用配置阈值
                channels.append(
                    {
                        "node": node,
                        "inflow": inflow,
                        "outflow": outflow,
                        "ratio": ratio,
                        "net_retention": abs(inflow - outflow),
                        "node_type": self.node_types.get(node, "unknown"),
                        "risk_level": "high" if ratio > 0.95 else "medium",
                    }
                )

        # 按流量排序
        channels.sort(key=lambda x: -(x["inflow"] + x["outflow"]))
        return channels

    def get_node_degree(self, node: str) -> Tuple[int, int]:
        """获取节点的入度和出度"""
        out_degree = len(self.edges.get(node, []))
        in_degree = sum(
            1 for edges in self.edges.values() for e in edges if e["target"] == node
        )
        return in_degree, out_degree

    def get_hub_nodes(self, min_degree: int = 5) -> List[Dict]:
        """
        识别资金枢纽节点（与多方有往来）

        审计意义：
        - 枢纽节点可能是关键控制人或中转站
        """
        hubs = []
        for node in self.nodes:
            in_deg, out_deg = self.get_node_degree(node)
            total_deg = in_deg + out_deg
            if total_deg >= min_degree:
                hubs.append(
                    {
                        "node": node,
                        "in_degree": in_deg,
                        "out_degree": out_deg,
                        "total_degree": total_deg,
                        "node_type": self.node_types.get(node, "unknown"),
                    }
                )

        hubs.sort(key=lambda x: -x["total_degree"])
        return hubs


def _estimate_cycle_amount(money_graph: MoneyGraph, cycle: List[str]) -> float:
    """按闭环路径的最小边额估算可回流金额。"""
    if not cycle:
        return 0.0

    nodes = list(cycle)
    if len(nodes) > 1 and nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    if len(nodes) < 2:
        return 0.0

    edge_amounts = []
    path_nodes = nodes + [nodes[0]]
    for idx in range(len(path_nodes) - 1):
        source = path_nodes[idx]
        target = path_nodes[idx + 1]
        amount = sum(
            float(edge.get("amount", 0) or 0)
            for edge in money_graph.edges.get(source, [])
            if edge.get("target") == target
        )
        if amount > 0:
            edge_amounts.append(amount)

    return round(min(edge_amounts), 2) if edge_amounts else 0.0


def _supporting_ref_sort_key(ref: Dict) -> Tuple[float, str]:
    """按金额优先、时间次之排序支撑交易样本，保证展示稳定。"""
    try:
        amount = abs(float(ref.get("amount", 0) or 0))
    except (TypeError, ValueError, AttributeError):
        amount = 0.0
    return (
        amount,
        str(ref.get("date", "") or ""),
    )


def _build_cycle_edge_segments(money_graph: MoneyGraph, cycle: List[str]) -> List[Dict]:
    """按闭环路径提取每一跳的累计金额口径。"""
    if not cycle:
        return []

    nodes = list(cycle)
    if len(nodes) > 1 and nodes[0] == nodes[-1]:
        nodes = nodes[:-1]
    if len(nodes) < 2:
        return []

    segments = []
    path_nodes = nodes + [nodes[0]]
    for idx in range(len(path_nodes) - 1):
        source = path_nodes[idx]
        target = path_nodes[idx + 1]
        matched_edges = [
            edge for edge in money_graph.edges.get(source, [])
            if edge.get("target") == target
        ]
        amount = round(
            sum(float(edge.get("amount", 0) or 0) for edge in matched_edges),
            2,
        )
        edge_types = sorted(
            {
                str(edge.get("type", "")).strip()
                for edge in matched_edges
                if str(edge.get("type", "")).strip()
            }
        )
        transaction_refs_total = sum(
            int(
                edge.get(
                    "supporting_transactions_total",
                    edge.get("transaction_count", 0),
                )
                or 0
            )
            for edge in matched_edges
        )
        matched_refs = [
            ref
            for edge in matched_edges
            for ref in list(edge.get("supporting_transactions", []) or [])
            if isinstance(ref, dict)
        ]
        matched_refs = sorted(
            matched_refs,
            key=_supporting_ref_sort_key,
            reverse=True,
        )
        transaction_refs = matched_refs[:TRANSACTION_REF_RETURN_LIMIT]
        transaction_refs_returned = len(transaction_refs)
        transaction_refs_total = max(transaction_refs_total, transaction_refs_returned)
        segments.append(
            {
                "index": idx + 1,
                "from": source,
                "to": target,
                "amount": amount,
                "edge_types": edge_types,
                "date_available": any(edge.get("date") is not None for edge in matched_edges),
                "time_basis": "aggregated_counterparty_total",
                "transaction_count": transaction_refs_total,
                "transaction_refs_total": transaction_refs_total,
                "transaction_ref_sample_count": transaction_refs_returned,
                "transaction_refs_returned": transaction_refs_returned,
                "transaction_refs_truncated": transaction_refs_total > transaction_refs_returned,
                "transaction_refs_limit": TRANSACTION_REF_RETURN_LIMIT,
                "transaction_refs": transaction_refs,
            }
        )
    return segments


def build_cycle_record(
    cycle: List[str],
    money_graph: MoneyGraph,
    focus_nodes: List[str] = None,
    search_metadata: Dict = None,
) -> Dict:
    """将原始闭环节点序列转换为带评分和解释的统一记录。"""
    focus_set = set(focus_nodes or [])
    nodes = list(cycle or [])
    if len(nodes) > 1 and nodes[0] == nodes[-1]:
        nodes = nodes[:-1]

    path_nodes = nodes + [nodes[0]] if nodes else []
    path = " → ".join(path_nodes) if path_nodes else "未知路径"
    unique_count = len(set(nodes))
    external_node_count = sum(1 for node in nodes if focus_set and node not in focus_set)
    estimated_amount = _estimate_cycle_amount(money_graph, cycle)
    edge_segments = _build_cycle_edge_segments(money_graph, cycle)
    positive_segments = [segment for segment in edge_segments if float(segment.get("amount", 0) or 0) > 0]
    bottleneck_edge = min(
        positive_segments,
        key=lambda item: float(item.get("amount", 0) or 0),
    ) if positive_segments else {}
    amount_basis_detail = (
        "按闭环每一跳的累计金额取最小边额，作为可稳定确认的回流金额上限"
        if positive_segments
        else "当前资金图仅稳定确认闭环路径，未形成可用边级金额口径"
    )

    risk_score = 45 + max(0, unique_count - 2) * 8
    if estimated_amount >= 1_000_000:
        risk_score += 20
    elif estimated_amount >= 500_000:
        risk_score += 16
    elif estimated_amount >= 100_000:
        risk_score += 12
    elif estimated_amount >= 50_000:
        risk_score += 8
    elif estimated_amount > 0:
        risk_score += 4
    if external_node_count > 0:
        risk_score += min(15, external_node_count * 5)

    confidence = 0.55
    if unique_count >= 3:
        confidence += 0.10
    if estimated_amount > 0:
        confidence += 0.15
    if external_node_count > 0:
        confidence += 0.10
    if search_metadata and search_metadata.get("truncated"):
        confidence -= 0.15

    evidence = [
        f"形成闭环路径: {path}",
        f"涉及 {unique_count} 个唯一节点",
    ]
    if external_node_count > 0:
        evidence.append(f"包含 {external_node_count} 个外围节点")
    if estimated_amount > 0:
        evidence.append(f"最小边额估算 {utils.format_currency(estimated_amount)} 元")
    else:
        evidence.append("当前无法稳定估算闭环金额")
    if search_metadata and search_metadata.get("truncated"):
        reasons = ",".join(search_metadata.get("truncated_reasons", [])) or "搜索截断"
        evidence.append(f"闭环搜索存在截断: {reasons}")

    normalized_score = risk_scoring.normalize_risk_score(risk_score)
    path_explainability = build_cycle_path_explainability(
        nodes=nodes,
        path=path,
        focus_nodes=focus_nodes,
        total_amount=estimated_amount,
        search_metadata=search_metadata,
        edge_segments=edge_segments,
        bottleneck_edge=bottleneck_edge,
        amount_basis_detail=amount_basis_detail,
    )
    return {
        "nodes": nodes,
        "participants": nodes,
        "path": path,
        "length": len(nodes),
        "unique_count": unique_count,
        "external_node_count": external_node_count,
        "total_amount": estimated_amount,
        "risk_score": normalized_score,
        "risk_level": risk_scoring.score_to_risk_level(normalized_score),
        "confidence": risk_scoring.normalize_confidence(confidence),
        "evidence": evidence,
        "path_explainability": path_explainability,
    }


def _enrich_pass_through_channel(channel: Dict) -> Dict:
    """为过账通道补充统一评分与解释字段。"""
    inflow = float(channel.get("inflow", 0) or 0)
    outflow = float(channel.get("outflow", 0) or 0)
    ratio = float(channel.get("ratio", 0) or 0)
    gross_amount = max(inflow, outflow)

    risk_score = 40
    if ratio >= 0.98:
        risk_score += 25
    elif ratio >= 0.95:
        risk_score += 20
    elif ratio >= 0.90:
        risk_score += 15
    else:
        risk_score += 8

    if gross_amount >= 1_000_000:
        risk_score += 20
    elif gross_amount >= 500_000:
        risk_score += 15
    elif gross_amount >= 100_000:
        risk_score += 10
    elif gross_amount > 0:
        risk_score += 5

    confidence = 0.60
    if ratio >= 0.95:
        confidence += 0.15
    elif ratio >= 0.90:
        confidence += 0.10
    if gross_amount >= 100_000:
        confidence += 0.10

    evidence = [
        f"进出比达到 {ratio * 100:.1f}%",
        f"总流量 {utils.format_currency(inflow + outflow)} 元",
        f"净沉淀 {utils.format_currency(abs(inflow - outflow))} 元",
    ]

    normalized_score = risk_scoring.normalize_risk_score(risk_score)
    enriched = dict(channel)
    enriched.update(
        {
            "risk_score": normalized_score,
            "risk_level": risk_scoring.score_to_risk_level(normalized_score),
            "confidence": risk_scoring.normalize_confidence(confidence),
            "evidence": evidence,
        }
    )
    return enriched


# ============================================================
# 构建资金图
# ============================================================


def build_money_graph(
    personal_data: Dict[str, pd.DataFrame],
    company_data: Dict[str, pd.DataFrame],
    core_persons: List[str],
    companies: List[str],
) -> MoneyGraph:
    """
    从交易数据构建资金图

    【P0 修复 - 2026-01-18】改为累计金额判定
    审计原则：边的权重应基于两点间"累计发生额"而非单笔金额
    这样可以避免"蚂蚁搬家"（多笔小额转账）漏查
    """
    graph = MoneyGraph()

    # 设置节点类型
    for person in core_persons:
        graph.set_node_type(person, "person")
    for company in companies:
        graph.set_node_type(company, "company")

    def _add_edges_from_data(entity_name: str, df: pd.DataFrame):
        """从单个实体的交易数据添加边（基于累计金额）"""
        if df.empty or "counterparty" not in df.columns:
            return

        # 按对手方聚合累计金额
        df_copy = df.copy()
        df_copy["counterparty"] = df_copy["counterparty"].astype(str).fillna("")

        # 过滤无效对手方
        df_copy = df_copy[
            (df_copy["counterparty"] != "")
            & (df_copy["counterparty"] != "nan")
            & (df_copy["counterparty"].str.len() >= 2)
        ]

        if df_copy.empty:
            return

        def _build_supporting_refs(group_df: pd.DataFrame, amount_col: str, direction: str) -> List[Dict]:
            if group_df.empty or amount_col not in group_df.columns:
                return []
            sorted_df = group_df.sort_values(by=amount_col, ascending=False, na_position="last")
            refs = []
            for _, tx in sorted_df.head(TRANSACTION_REF_RETURN_LIMIT).iterrows():
                amount = tx.get(amount_col, 0)
                refs.append(
                    {
                        "date": str(tx.get("date", "") or "")[:19],
                        "amount": float(amount or 0),
                        "description": str(tx.get("description", "") or "").strip(),
                        "source_file": str(tx.get("数据来源", "") or "").strip(),
                        "source_row_index": tx.get("source_row_index"),
                        "direction": direction,
                        "counterparty_raw": str(tx.get("counterparty", "") or "").strip(),
                    }
                )
            return refs

        # 按对手方聚合并保留原始交易引用
        for cp, cp_group in df_copy.groupby("counterparty", sort=False):
            total_income = float(cp_group["income"].sum()) if "income" in cp_group.columns else 0.0
            total_expense = float(cp_group["expense"].sum()) if "expense" in cp_group.columns else 0.0

            # 累计金额超过阈值才添加边
            if total_income > config.GRAPH_EDGE_MIN_AMOUNT:
                # 收入边：对手方 -> 当前实体
                income_rows = cp_group[cp_group["income"] > 0] if "income" in cp_group.columns else cp_group.iloc[0:0]
                graph.add_edge(
                    cp,
                    entity_name,
                    total_income,
                    None,
                    "income",
                    supporting_transactions=_build_supporting_refs(income_rows, "income", "income"),
                    transaction_count=len(income_rows),
                    supporting_transactions_total=len(income_rows),
                    supporting_transactions_truncated=len(income_rows) > TRANSACTION_REF_RETURN_LIMIT,
                    supporting_transactions_limit=TRANSACTION_REF_RETURN_LIMIT,
                )

            if total_expense > config.GRAPH_EDGE_MIN_AMOUNT:
                # 支出边：当前实体 -> 对手方
                expense_rows = cp_group[cp_group["expense"] > 0] if "expense" in cp_group.columns else cp_group.iloc[0:0]
                graph.add_edge(
                    entity_name,
                    cp,
                    total_expense,
                    None,
                    "expense",
                    supporting_transactions=_build_supporting_refs(expense_rows, "expense", "expense"),
                    transaction_count=len(expense_rows),
                    supporting_transactions_total=len(expense_rows),
                    supporting_transactions_truncated=len(expense_rows) > TRANSACTION_REF_RETURN_LIMIT,
                    supporting_transactions_limit=TRANSACTION_REF_RETURN_LIMIT,
                )

    # 从个人数据添加边
    for person_name, df in personal_data.items():
        _add_edges_from_data(person_name, df)

    # 从公司数据添加边
    for company_name, df in company_data.items():
        _add_edges_from_data(company_name, df)

    logger.info(
        f"资金图构建完成: {len(graph.nodes)} 节点, {sum(len(e) for e in graph.edges.values())} 条边（基于累计金额）"
    )
    return graph


def _df_to_results(
    subset: pd.DataFrame, 发起方: str, 接收方: str, 方向: str
) -> List[Dict]:
    """将DataFrame子集转换为结果列表"""
    if subset.empty:
        return []
    res = []
    for _, row in subset.iterrows():
        res.append(
            {
                "发起方": 发起方,
                "接收方": 接收方,
                "交易对方原文": str(row.get("counterparty", "")),
                "日期": row.get("date"),
                "收入": row.get("income", 0),
                "支出": row.get("expense", 0),
                "摘要": row.get("description", ""),
                "方向": 方向,
            }
        )
    return res


def _analyze_graph_deep_analysis(
    money_graph: MoneyGraph, core_persons: List[str], companies: List[str]
) -> Dict:
    """
    图论深度分析

    Args:
        money_graph: 资金图
        core_persons: 核心人员列表
        companies: 公司列表

    Returns:
        图论分析结果
    """
    results = {
        "fund_cycles": [],
        "pass_through_channels": [],
        "hub_nodes": [],
        "multi_hop_paths": [],
        "graph_stats": {},
        "analysis_metadata": {},
    }

    # 检测资金闭环
    logger.info("【阶段0.1】检测资金闭环（利益回流）...")
    key_nodes = core_persons + companies
    raw_cycles = money_graph.find_cycles(
        min_length=3, max_length=4, key_nodes=key_nodes, timeout_seconds=30
    )
    cycle_meta = dict(getattr(money_graph, "last_cycle_search_meta", {}) or {})
    results["fund_cycles"] = [
        build_cycle_record(
            cycle,
            money_graph,
            focus_nodes=key_nodes,
            search_metadata=cycle_meta,
        )
        for cycle in raw_cycles
    ]
    results["analysis_metadata"]["fund_cycles"] = cycle_meta
    logger.info(f"  发现 {len(results['fund_cycles'])} 个资金闭环")

    # 识别过账通道
    logger.info("【阶段0.2】识别过账通道（空壳/马甲）...")
    raw_channels = money_graph.identify_pass_through_channels(
        threshold_ratio=0.85
    )
    results["pass_through_channels"] = [
        _enrich_pass_through_channel(channel) for channel in raw_channels
    ]
    results["analysis_metadata"]["pass_through_channels"] = {
        "threshold_ratio": 0.85,
        "returned_count": len(results["pass_through_channels"]),
        "truncated": False,
    }
    logger.info(f"  发现 {len(results['pass_through_channels'])} 个过账通道")

    # 分析资金枢纽节点
    logger.info("【阶段0.3】分析资金枢纽节点...")
    results["hub_nodes"] = money_graph.get_hub_nodes(min_degree=5)
    logger.info(f"  发现 {len(results['hub_nodes'])} 个枢纽节点")

    # 多跳路径分析
    logger.info("【阶段0.4】追踪多跳资金路径（核心人员→公司）...")
    import time

    path_start_time = time.time()
    path_timeout = 30
    max_paths = 50

    for person in core_persons:
        if time.time() - path_start_time > path_timeout:
            logger.warning(f"  多跳路径搜索超时")
            break
        for company in companies:
            if len(results["multi_hop_paths"]) >= max_paths:
                break
            paths = money_graph.find_all_paths(person, company, max_depth=3)
            for path in paths[:5]:
                if len(path) > 2:
                    results["multi_hop_paths"].append(
                        {
                            "source": person,
                            "target": company,
                            "path": path,
                            "hops": len(path) - 1,
                            "path_str": " → ".join(path),
                        }
                    )
    logger.info(f"  发现 {len(results['multi_hop_paths'])} 条多跳路径")

    # 图统计
    results["graph_stats"] = {
        "total_nodes": len(money_graph.nodes),
        "total_edges": sum(len(e) for e in money_graph.edges.values()),
        "person_nodes": len(
            [n for n, t in money_graph.node_types.items() if t == "person"]
        ),
        "company_nodes": len(
            [n for n, t in money_graph.node_types.items() if t == "company"]
        ),
    }

    return results


def _analyze_direct_transactions(
    personal_data: Dict[str, pd.DataFrame],
    company_data: Dict[str, pd.DataFrame],
    core_persons: List[str],
    companies: List[str],
) -> Dict:
    """
    直接往来检测

    Args:
        personal_data: 个人数据
        company_data: 公司数据
        core_persons: 核心人员列表
        companies: 公司列表

    Returns:
        直接往来结果
    """
    results = {
        "person_to_company": [],
        "company_to_person": [],
        "person_to_person": [],
        "company_to_company": [],
    }

    # 预处理公司关键词
    company_patterns = {c: _extract_company_keywords(c) for c in companies}

    # 1. 检测个人→公司的资金往来
    logger.info("【阶段1】检测个人→涉案公司的资金往来")
    for person_name, df in personal_data.items():
        if df.empty or "counterparty" not in df.columns:
            continue

        counterparty_series = df["counterparty"].astype(str).fillna("")

        for company, keywords in company_patterns.items():
            mask = counterparty_series.str.contains(
                "|".join(re.escape(k) for k in keywords), na=False, regex=True
            )
            if mask.any():
                results["person_to_company"].extend(
                    _df_to_results(df[mask], person_name, company, "个人→公司")
                )

    logger.info(f"  发现 {len(results['person_to_company'])} 笔个人→公司交易")

    # 2. 检测公司→个人的资金往来
    logger.info("【阶段2】检测涉案公司→个人的资金往来")
    for company_name, df in company_data.items():
        if df.empty or "counterparty" not in df.columns:
            continue

        counterparty_series = df["counterparty"].astype(str).fillna("")

        for person in core_persons:
            mask = counterparty_series.str.contains(person, na=False)
            if mask.any():
                results["company_to_person"].extend(
                    _df_to_results(df[mask], company_name, person, "公司→个人")
                )

    logger.info(f"  发现 {len(results['company_to_person'])} 笔公司→个人交易")

    # 3. 检测核心人员之间的资金往来
    logger.info("【阶段3】检测核心人员之间的资金往来")
    for person_name, df in personal_data.items():
        if df.empty or "counterparty" not in df.columns:
            continue

        counterparty_series = df["counterparty"].astype(str).fillna("")

        for other_person in core_persons:
            if other_person == person_name:
                continue

            mask = counterparty_series.str.contains(other_person, na=False)
            if mask.any():
                results["person_to_person"].extend(
                    _df_to_results(df[mask], person_name, other_person, "个人→个人")
                )

    logger.info(f"  发现 {len(results['person_to_person'])} 笔核心人员间交易")

    # 4. 检测涉案公司之间的资金往来
    logger.info("【阶段4】检测涉案公司之间的资金往来")
    for company_name, df in company_data.items():
        if df.empty or "counterparty" not in df.columns:
            continue

        counterparty_series = df["counterparty"].astype(str).fillna("")

        for other_company, keywords in company_patterns.items():
            if other_company == company_name:
                continue

            mask = counterparty_series.str.contains(
                "|".join(re.escape(k) for k in keywords), na=False, regex=True
            )
            if mask.any():
                results["company_to_company"].extend(
                    _df_to_results(df[mask], company_name, other_company, "公司→公司")
                )

    logger.info(f"  发现 {len(results['company_to_company'])} 笔涉案公司间交易")

    return results


def analyze_fund_penetration(
    personal_data: Dict[str, pd.DataFrame],
    company_data: Dict[str, pd.DataFrame],
    core_persons: List[str],
    companies: List[str],
) -> Dict:
    """
    资金穿透分析（增强版 v2.0）

    包含:
    1. 直接往来检测（原有功能）
    2. 图论深度分析（新增）:
       - 多跳路径追踪
       - 资金闭环检测
       - 过账通道识别
       - 资金枢纽分析
    """
    logger.info("=" * 60)
    logger.info("开始资金穿透分析（增强版 v2.0 - 图论深度分析）")
    logger.info("=" * 60)

    results = {
        "person_to_company": [],
        "company_to_person": [],
        "person_to_person": [],
        "company_to_company": [],
        "fund_cycles": [],
        "pass_through_channels": [],
        "hub_nodes": [],
        "multi_hop_paths": [],
        "graph_stats": {},
        "summary": {},
    }

    # ===== 阶段0: 构建资金图 =====
    logger.info("【阶段0】构建资金图...")
    money_graph = build_money_graph(
        personal_data, company_data, core_persons, companies
    )

    # ===== 阶段0.1-0.4: 图论深度分析 =====
    graph_results = _analyze_graph_deep_analysis(money_graph, core_persons, companies)
    results.update(graph_results)

    # ===== 原有逻辑: 直接往来检测 =====
    direct_results = _analyze_direct_transactions(
        personal_data, company_data, core_persons, companies
    )
    results.update(direct_results)

    # 生成汇总统计
    results["summary"] = _generate_summary(results)

    logger.info("")
    logger.info("资金穿透分析完成（增强版 v2.0）")
    logger.info("【直接往来】")
    logger.info(f"  个人→公司: {len(results['person_to_company'])} 笔")
    logger.info(f"  公司→个人: {len(results['company_to_person'])} 笔")
    logger.info(f"  个人→个人: {len(results['person_to_person'])} 笔")
    logger.info(f"  公司→公司: {len(results['company_to_company'])} 笔")
    logger.info("【图论深度分析】")
    logger.info(f"  资金闭环: {len(results['fund_cycles'])} 个")
    logger.info(f"  过账通道: {len(results['pass_through_channels'])} 个")
    logger.info(f"  资金枢纽: {len(results['hub_nodes'])} 个")
    logger.info(f"  多跳路径: {len(results['multi_hop_paths'])} 条")

    return results


def _extract_company_keywords(company_name: str) -> List[str]:
    """提取公司名关键词用于模糊匹配"""
    keywords = [company_name]

    # 移除常见后缀
    suffixes = ["有限公司", "股份有限公司", "有限责任公司", "科技", "技术"]
    name = company_name
    for suffix in suffixes:
        name = name.replace(suffix, "")

    if name and len(name) >= 2:
        keywords.append(name)

    # 提取核心词汇
    if "北京" in company_name:
        core = (
            company_name.replace("北京", "").replace("有限公司", "").replace("科技", "")
        )
        if core and len(core) >= 2:
            keywords.append(core)
    if "贵州" in company_name:
        core = (
            company_name.replace("贵州", "").replace("有限公司", "").replace("科技", "")
        )
        if core and len(core) >= 2:
            keywords.append(core)

    return list(set(keywords))


def _match_company(counterparty: str, keywords: List[str]) -> bool:
    """检查对手方是否匹配公司关键词"""
    if not counterparty:
        return False

    for keyword in keywords:
        if keyword in counterparty:
            return True
    return False


def _generate_summary(results: Dict) -> Dict:
    """生成资金穿透汇总统计"""
    summary = {
        "个人→公司笔数": len(results["person_to_company"]),
        "个人→公司总金额": 0,
        "公司→个人笔数": len(results["company_to_person"]),
        "公司→个人总金额": 0,
        "核心人员间笔数": len(results["person_to_person"]),
        "核心人员间总金额": 0,
        "涉案公司间笔数": len(results["company_to_company"]),
        "涉案公司间总金额": 0,
    }

    for item in results["person_to_company"]:
        summary["个人→公司总金额"] += item["收入"] + item["支出"]

    for item in results["company_to_person"]:
        summary["公司→个人总金额"] += item["收入"] + item["支出"]

    for item in results["person_to_person"]:
        summary["核心人员间总金额"] += item["收入"] + item["支出"]

    for item in results["company_to_company"]:
        summary["涉案公司间总金额"] += item["收入"] + item["支出"]

    return summary


def _write_penetration_summary(f, summary: Dict) -> None:
    """写入汇总统计部分"""
    f.write("一、汇总统计\n")
    f.write("-" * 40 + "\n")
    f.write(
        f"个人→涉案公司: {summary['个人→公司笔数']} 笔, 金额 {summary['个人→公司总金额'] / 10000:.2f} 万元\n"
    )
    f.write(
        f"涉案公司→个人: {summary['公司→个人笔数']} 笔, 金额 {summary['公司→个人总金额'] / 10000:.2f} 万元\n"
    )
    f.write(
        f"核心人员之间: {summary['核心人员间笔数']} 笔, 金额 {summary['核心人员间总金额'] / 10000:.2f} 万元\n"
    )
    f.write(
        f"涉案公司之间: {summary['涉案公司间笔数']} 笔, 金额 {summary['涉案公司间总金额'] / 10000:.2f} 万元\n\n"
    )


def _write_transaction_details(f, items: List[Dict], title: str) -> None:
    """写入交易明细部分"""
    f.write(f"{title}\n")
    f.write("-" * 40 + "\n")
    f.write(f"共 {len(items)} 笔记录\n\n")
    for i, item in enumerate(items, 1):
        date_str = (
            item["日期"].strftime("%Y-%m-%d")
            if hasattr(item["日期"], "strftime")
            else str(item["日期"])[:10]
        )
        amount = item["收入"] if item["收入"] > 0 else item["支出"]
        direction = "收入" if item["收入"] > 0 else "支出"
        desc = utils.safe_str(item["摘要"], default="转账")[:20]
        f.write(
            f"{i}. [{date_str}] {item['发起方']} → {item['接收方']}: {utils.format_currency(amount)}({direction}), 摘要:{desc}\n"
        )
    f.write("\n")


def _write_fund_cycles_section(f, cycles: List[Dict], meta: Dict = None) -> None:
    """写入资金闭环部分"""
    f.write("六、资金闭环（利益回流铁证）\n")
    f.write("-" * 40 + "\n")
    f.write("★ 资金闭环说明资金最终回流到起点，是典型的洗钱或利益输送结构\n")
    f.write(f"共 {len(cycles)} 个闭环\n\n")
    if meta and meta.get("truncated"):
        reasons = "、".join(meta.get("truncated_reasons", [])) or "搜索截断"
        f.write(f"⚠ 本次闭环搜索存在截断: {reasons}（超时阈值 {meta.get('timeout_seconds', 30)} 秒）\n\n")
    for i, cycle in enumerate(cycles, 1):
        if isinstance(cycle, dict):
            f.write(f"{i}. 【{str(cycle.get('risk_level', 'medium')).upper()}】{cycle.get('path', '未知路径')}\n")
            if cycle.get("total_amount"):
                f.write(f"   估算金额: {utils.format_currency(cycle.get('total_amount', 0))} 元\n")
            if cycle.get("risk_score") is not None:
                f.write(f"   风险评分: {cycle.get('risk_score', 0):.1f} | 置信度: {float(cycle.get('confidence', 0) or 0):.2f}\n")
            evidence = cycle.get("evidence") or []
            if evidence:
                f.write(f"   证据摘要: {'；'.join(str(item) for item in evidence[:3])}\n")
        else:
            f.write(f"{i}. {' → '.join(cycle)}\n")
    f.write("\n")


def _write_pass_through_channels_section(f, channels: List[Dict]) -> None:
    """写入过账通道部分"""
    f.write("七、过账通道（疑似空壳/马甲账户）\n")
    f.write("-" * 40 + "\n")
    f.write("★ 进出金额高度平衡（收多少立刻转走多少），常见于空壳公司\n")
    f.write(f"共 {len(channels)} 个记录\n\n")
    for i, ch in enumerate(channels, 1):
        f.write(f"{i}. 【{ch['risk_level'].upper()}】{ch['node']}\n")
        f.write(
            f"   进账: {ch['inflow'] / 10000:.2f}万 | 出账: {ch['outflow'] / 10000:.2f}万 | 进出比: {ch['ratio'] * 100:.1f}%\n"
        )
        if ch.get("risk_score") is not None:
            f.write(f"   风险评分: {ch.get('risk_score', 0):.1f} | 置信度: {float(ch.get('confidence', 0) or 0):.2f}\n")
        evidence = ch.get("evidence") or []
        if evidence:
            f.write(f"   证据摘要: {'；'.join(str(item) for item in evidence[:2])}\n")
    f.write("\n")


def _write_hub_nodes_section(f, hubs: List[Dict]) -> None:
    """写入资金枢纽节点部分"""
    f.write("八、资金枢纽节点（关键控制人/中转站）\n")
    f.write("-" * 40 + "\n")
    f.write("★ 与多方有资金往来的关键节点\n")
    f.write(f"共 {len(hubs)} 个记录\n\n")
    for i, hub in enumerate(hubs, 1):
        f.write(f"{i}. {hub['node']} ({hub['node_type']})\n")
        f.write(
            f"   入度: {hub['in_degree']} | 出度: {hub['out_degree']} | 总连接: {hub['total_degree']}\n"
        )
    f.write("\n")


def _write_multi_hop_paths_section(f, paths: List[Dict]) -> None:
    """写入多跳资金路径部分"""
    f.write("九、多跳资金路径（复杂利益输送链路）\n")
    f.write("-" * 40 + "\n")
    f.write("★ 2跳以上的资金链路，可能通过中间人/空壳公司中转\n")
    f.write(f"共 {len(paths)} 条路径\n\n")
    for i, path in enumerate(paths, 1):
        f.write(f"{i}. [{path['hops']}跳] {path['path_str']}\n")
    f.write("\n")


def _write_graph_stats_section(f, stats: Dict) -> None:
    """写入资金图统计部分"""
    f.write("十、资金图统计\n")
    f.write("-" * 40 + "\n")
    f.write(f"总节点数: {stats.get('total_nodes', 0)}\n")
    f.write(f"总边数: {stats.get('total_edges', 0)}\n")
    f.write(f"人员节点: {stats.get('person_nodes', 0)}\n")
    f.write(f"公司节点: {stats.get('company_nodes', 0)}\n")


def generate_penetration_report(results: Dict, output_dir: str) -> str:
    """
    生成资金穿透分析报告

    Args:
        results: 分析结果
        output_dir: 输出目录

    Returns:
        报告文件路径
    """
    report_path = os.path.join(output_dir, "资金穿透分析报告.txt")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("资金穿透分析报告（增强版）\n")
        f.write("=" * 60 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")

        # 报告说明
        f.write("【报告用途】\n")
        f.write("本报告用于深度分析资金流动关系，包括：\n")
        f.write("• 个人与涉案公司的资金往来\n")
        f.write("• 资金闭环（资金回流铁证）\n")
        f.write("• 过账通道（疑似空壳公司）\n")
        f.write("• 资金枢纽节点（关键控制人）\n")
        f.write("• 多跳资金路径（复杂利益输送链）\n\n")

        f.write("【分析逻辑与规则】\n")
        f.write(
            "1. 资金闭环: 使用 Tarjan 算法检测强连通分量，发现 A→B→C→A 形式的资金回流\n"
        )
        f.write("2. 过账通道: 进出金额比例&gt;90%，说明资金只是过境而不沉淀\n")
        f.write("3. 枢纽节点: 连接数&gt;3，与多方有资金往来\n")
        f.write("4. 多跳路径: BFS 搜索 2 跳以上的资金链路\n\n")

        f.write("【可能的误判情况】\n")
        f.write("⚠ 支付宝/微信等公共通道可能形成伪闭环\n")
        f.write("⚠ 正常业务往来可能被识别为过账通道\n")
        f.write("⚠ 第三方支付可能导致枢纽节点误报\n\n")

        f.write("【人工复核重点】\n")
        f.write("★ 资金闭环: 重点关注，核实闭环形成原因\n")
        f.write("★ 过账通道: 核实该账户的业务实质\n")
        f.write("★ 枢纽节点: 核实该人/公司在业务中的角色\n\n")

        f.write("=" * 60 + "\n\n")

        # 汇总统计
        _write_penetration_summary(f, results["summary"])

        # 详细明细
        if results["person_to_company"]:
            _write_transaction_details(
                f, results["person_to_company"], "二、个人→涉案公司明细"
            )

        if results["company_to_person"]:
            _write_transaction_details(
                f, results["company_to_person"], "三、涉案公司→个人明细"
            )

        if results["person_to_person"]:
            _write_transaction_details(
                f, results["person_to_person"], "四、核心人员之间明细"
            )

        if results["company_to_company"]:
            _write_transaction_details(
                f, results["company_to_company"], "五、涉案公司之间明细"
            )

        # ===== 新增: 图论深度分析结果 =====
        f.write("\n")
        f.write("=" * 60 + "\n")
        f.write("★★★ 图论深度分析结果 ★★★\n")
        f.write("=" * 60 + "\n\n")

        # 资金闭环
        if results.get("fund_cycles"):
            _write_fund_cycles_section(
                f,
                results["fund_cycles"],
                (results.get("analysis_metadata") or {}).get("fund_cycles"),
            )

        # 过账通道
        if results.get("pass_through_channels"):
            _write_pass_through_channels_section(f, results["pass_through_channels"])

        # 资金枢纽
        if results.get("hub_nodes"):
            _write_hub_nodes_section(f, results["hub_nodes"])

        # 多跳路径
        if results.get("multi_hop_paths"):
            _write_multi_hop_paths_section(f, results["multi_hop_paths"])

        # 图统计
        if results.get("graph_stats"):
            _write_graph_stats_section(f, results["graph_stats"])

    logger.info(f"资金穿透报告已生成: {report_path}")
    return report_path
