#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关联方资金穿透分析模块
分析核心人员之间的直接资金往来、第三方中转、资金闭环等模式
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
import config
import utils
from counterparty_utils import is_payment_platform_counterparty
from name_normalizer import normalize_for_matching, is_same_person
import fund_penetration
import risk_scoring
from utils.family_relation_utils import build_family_pair_keys, is_family_pair
from utils.path_explainability import (
    build_cluster_path_explainability,
    build_direct_flow_path_explainability,
    build_relay_path_explainability,
    rank_representative_paths,
)

logger = utils.setup_logger(__name__)
DIRECT_FLOW_MIRROR_MATCH_TOLERANCE_SECONDS = 5


def _normalize_risk_score(score: float) -> float:
    return risk_scoring.normalize_risk_score(score)


def _normalize_confidence(confidence: float) -> float:
    return risk_scoring.normalize_confidence(confidence)


def _score_to_level(score: float) -> str:
    return risk_scoring.score_to_risk_level(score)


def _coerce_direct_flow_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    if isinstance(parsed, pd.Timestamp):
        return parsed.to_pydatetime()
    return parsed if isinstance(parsed, datetime) else None


def _build_direct_flow_transaction_ref(flow: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "date": flow.get("date"),
        "amount": float(flow.get("amount", 0) or 0),
        "source_file": flow.get("source_file", ""),
        "source_row_index": flow.get("source_row_index"),
        "description": flow.get("description", ""),
        "direction": str(
            flow.get("observation_direction") or flow.get("direction") or ""
        ).strip(),
        "counterparty_raw": str(flow.get("counterparty_raw", "") or "").strip(),
        "observed_entity": str(flow.get("observed_entity", "") or "").strip(),
    }


def _finalize_direct_flow_record(flow: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(flow)
    refs = list(record.get("transaction_refs", []) or [])
    if not refs:
        refs = [_build_direct_flow_transaction_ref(record)]
    record["transaction_refs"] = refs
    record["transaction_refs_total"] = max(
        int(record.get("transaction_refs_total", len(refs)) or len(refs)),
        len(refs),
    )
    return record


def _merge_mirrored_direct_flows(
    left: Dict[str, Any], right: Dict[str, Any]
) -> Dict[str, Any]:
    pay_flow = (
        left
        if str(left.get("observation_direction", "")).strip().lower() == "pay"
        else right
    )
    receive_flow = right if pay_flow is left else left
    refs = [
        _build_direct_flow_transaction_ref(pay_flow),
        _build_direct_flow_transaction_ref(receive_flow),
    ]

    merged = dict(pay_flow)
    merged["date"] = pay_flow.get("date") or receive_flow.get("date")
    merged["description"] = (
        str(pay_flow.get("description", "") or "").strip()
        or str(receive_flow.get("description", "") or "").strip()
    )
    merged["relationship_context"] = (
        "family"
        if any(
            str(item.get("relationship_context", "")).strip().lower() == "family"
            for item in (left, right)
        )
        else str(pay_flow.get("relationship_context", "") or "").strip()
        or str(receive_flow.get("relationship_context", "") or "").strip()
    )
    merged["transaction_refs"] = refs
    merged["transaction_refs_total"] = len(refs)
    merged["source_file"] = pay_flow.get("source_file") or receive_flow.get(
        "source_file", ""
    )
    merged["source_row_index"] = pay_flow.get(
        "source_row_index"
    ) or receive_flow.get("source_row_index")
    merged["counterparty_raw"] = pay_flow.get(
        "counterparty_raw"
    ) or receive_flow.get("counterparty_raw", "")
    merged["observed_entity"] = pay_flow.get("observed_entity") or receive_flow.get(
        "observed_entity", ""
    )
    merged["observation_direction"] = "pay"
    merged["direction"] = "pay"
    return _finalize_direct_flow_record(merged)


def _dedupe_mirrored_direct_flows(
    direct_flows: List[Dict[str, Any]],
    tolerance_seconds: int = DIRECT_FLOW_MIRROR_MATCH_TOLERANCE_SECONDS,
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str, float], List[Tuple[int, Dict[str, Any]]]] = defaultdict(
        list
    )

    for index, flow in enumerate(direct_flows):
        from_node = str(flow.get("from", "") or "").strip()
        to_node = str(flow.get("to", "") or "").strip()
        amount = round(float(flow.get("amount", 0) or 0), 2)
        grouped[(from_node, to_node, amount)].append((index, flow))

    deduped: List[Dict[str, Any]] = []
    for items in grouped.values():
        items.sort(
            key=lambda item: (
                _coerce_direct_flow_datetime(item[1].get("date")) or datetime.max,
                item[0],
            )
        )
        consumed: Set[int] = set()

        for index, flow in items:
            if index in consumed:
                continue

            flow_dt = _coerce_direct_flow_datetime(flow.get("date"))
            flow_observation = str(
                flow.get("observation_direction", "") or ""
            ).strip().lower()
            matched_index: Optional[int] = None
            matched_flow: Optional[Dict[str, Any]] = None
            matched_diff: Optional[float] = None

            for other_index, other in items:
                if other_index == index or other_index in consumed:
                    continue

                other_observation = str(
                    other.get("observation_direction", "") or ""
                ).strip().lower()
                if {flow_observation, other_observation} != {"pay", "receive"}:
                    continue

                other_dt = _coerce_direct_flow_datetime(other.get("date"))
                if flow_dt is None or other_dt is None:
                    continue

                diff_seconds = abs((flow_dt - other_dt).total_seconds())
                if diff_seconds > tolerance_seconds:
                    continue

                if matched_diff is None or diff_seconds < matched_diff:
                    matched_index = other_index
                    matched_flow = other
                    matched_diff = diff_seconds

            if matched_index is not None and matched_flow is not None:
                consumed.add(index)
                consumed.add(matched_index)
                deduped.append(_merge_mirrored_direct_flows(flow, matched_flow))
                continue

            consumed.add(index)
            deduped.append(_finalize_direct_flow_record(flow))

    deduped.sort(
        key=lambda flow: (
            _coerce_direct_flow_datetime(flow.get("date")) or datetime.max,
            str(flow.get("from", "") or "").strip(),
            str(flow.get("to", "") or "").strip(),
            float(flow.get("amount", 0) or 0),
        )
    )
    return deduped


def analyze_related_party_flows(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    profiles: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """
    分析关联方之间的资金往来
    
    Args:
        all_transactions: 所有交易数据 {entity_name: DataFrame}
        core_persons: 核心关联人员列表
        
    Returns:
        关联方资金分析结果
    """
    logger.info('='*60)
    logger.info('开始关联方资金穿透分析')
    logger.info('='*60)
    family_pair_keys = build_family_pair_keys(core_persons, profiles or {})
    
    results = {
        'direct_flows': [],           # 直接资金往来
        'third_party_relays': [],     # 第三方中转
        'fund_loops': [],             # 资金闭环
        'discovered_nodes': [],       # 新发现的外围节点
        'relationship_clusters': [],  # 关系簇
        'flow_matrix': {},            # 资金流向矩阵
        'analysis_metadata': {},      # 分析过程元数据
        'summary': {}
    }
    
    # 1. 分析直接资金往来
    logger.info('【阶段1】分析关联人直接资金往来')
    results['direct_flows'] = _analyze_direct_flows(
        all_transactions,
        core_persons,
        family_pair_keys=family_pair_keys,
    )
    
    # 2. 检测第三方中转
    logger.info('【阶段2】检测第三方中转模式')
    results['third_party_relays'] = _detect_third_party_relay(all_transactions, core_persons)
    results['analysis_metadata']['third_party_relays'] = {
        'returned_count': len(results['third_party_relays']),
        'time_window_hours': 72,
        'amount_tolerance': 0.15,
        'truncated': False,
    }
    
    # 3. 检测资金闭环
    logger.info('【阶段3】检测资金闭环')
    results['fund_loops'], results['analysis_metadata']['fund_loops'] = _detect_fund_loops(
        all_transactions,
        core_persons,
        return_metadata=True,
    )
    
    # 4. 构建资金流向矩阵
    logger.info('【阶段4】构建资金流向矩阵')
    results['flow_matrix'] = _build_flow_matrix(results['direct_flows'], core_persons)

    # 5. 生成外围节点与关系簇
    logger.info('【阶段5】提取外围节点与关系簇')
    results['discovered_nodes'] = _extract_discovered_nodes(results, core_persons)
    results['relationship_clusters'] = _build_relationship_clusters(
        results,
        core_persons,
        family_pair_keys=family_pair_keys,
    )
    
    # 6. 生成汇总
    results['summary'] = _generate_summary(results, core_persons)
    
    logger.info('')
    logger.info(f'关联方分析完成: 直接往来{len(results["direct_flows"])}笔, '
                f'第三方中转{len(results["third_party_relays"])}条链, '
                f'资金闭环{len(results["fund_loops"])}个, '
                f'外围节点{len(results["discovered_nodes"])}个')
    
    return results


def _analyze_direct_flows(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    family_pair_keys: Optional[Set[frozenset[str]]] = None,
) -> List[Dict]:
    """分析核心人员之间的直接资金往来 (性能优化版)"""
    direct_flows = []
    
    # 预先筛选出所有属于个人的交易并重构结构，提高访问速度
    person_dfs = {}
    for key, df in all_transactions.items():
        if '公司' not in key:
            entity_name = key.split('_')[0] if '_' in key else key
            if any(p in entity_name for p in core_persons):
                # 规范化列名
                if df.empty or 'counterparty' not in df.columns:
                    continue
                person_dfs[entity_name] = df
    
    for person, df in person_dfs.items():
        counterparty_series = utils.normalize_text_series(df['counterparty'])
        
        for other_person in core_persons:
            if other_person == person:
                continue
            
            # 【P1修复】使用标准化后的精确匹配
            # 先对名称进行标准化（去空格、括号内容、全角转半角），再精确比对
            # 这样可以处理"张 三"、"张三（个人）"等情况
            other_norm = normalize_for_matching(other_person)
            mask = counterparty_series.apply(lambda x: normalize_for_matching(x) == other_norm)
            if mask.any():
                subset = df[mask]
                for _, row in subset.iterrows():
                    income_amount = float(row.get('income', 0) or 0)
                    expense_amount = float(row.get('expense', 0) or 0)
                    is_receive = income_amount > 0
                    sender = other_person if is_receive else person
                    receiver = person if is_receive else other_person
                    flow = {
                        'from': sender,
                        'to': receiver,
                        'date': row.get('date'),
                        'amount': max(income_amount, expense_amount),
                        'direction': 'pay',
                        'observation_direction': 'receive' if is_receive else 'pay',
                        'observed_entity': person,
                        'description': row.get('description', ''),
                        'counterparty_raw': str(row.get('counterparty', '')),
                        'relationship_context': (
                            'family' if is_family_pair(person, other_person, family_pair_keys) else 'external'
                        ),
                        # 【审计溯源】原始文件和行号
                        'source_file': row.get('数据来源', ''),
                        'source_row_index': row.get('source_row_index', None)
                    }
                    direct_flows.append(flow)

    deduped_flows = _dedupe_mirrored_direct_flows(direct_flows)
    logger.info(
        f'  发现 {len(direct_flows)} 条关联人直接往来侧账记录, '
        f'去重后 {len(deduped_flows)} 笔唯一交易'
    )
    return deduped_flows


def _get_excluded_relay_keywords() -> List[str]:
    """
    获取应排除的公共支付平台/常见消费对手方关键词列表
    
    这些是公共通道，不应被视为真正的"中间人"
    
    Returns:
        排除关键词列表
    """
    return [
        # 第三方支付平台
        '财付通', '支付宝', '微信支付', 'ALIPAY', 'TENPAY', '银联',
        '京东支付', '云闪付', '翼支付', '壹钱包', '网银在线',
        # 电商平台
        '淘宝', '天猫', '京东', '拼多多', '美团', '饿了么', '滴滴',
        # 银行内部交易
        '本行', '跨行', '手续费', '利息', '年费', '转存',
        # 其他公共服务
        '中国移动', '中国联通', '中国电信', '国家电网', '水务', '燃气',
        '保险', '社保', '公积金'
    ]


def _is_excluded_relay(counterparty: str, excluded_keywords: List[str]) -> bool:
    """
    检查是否为应排除的中间人
    
    Args:
        counterparty: 对手方名称
        excluded_keywords: 排除关键词列表
    
    Returns:
        是否应排除
    """
    if not counterparty:
        return True
    if is_payment_platform_counterparty(counterparty):
        return True
    cp_upper = counterparty.upper()
    return any(kw.upper() in cp_upper for kw in excluded_keywords)


def _collect_person_flows(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    excluded_keywords: List[str],
    min_amount: float
) -> tuple:
    """
    收集所有关联人的支出和收入记录
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        excluded_keywords: 排除关键词列表
        min_amount: 最低金额门槛
    
    Returns:
        (person_outflows, person_inflows) 元组
    """
    person_outflows = defaultdict(list)
    person_inflows = defaultdict(list)
    
    for person_name in core_persons:
        # 查找该人员的所有交易
        person_dfs_to_process = []
        for key, df in all_transactions.items():
            if person_name in key and '公司' not in key:
                person_dfs_to_process.append(df)
        
        if not person_dfs_to_process:
            continue
            
        full_df = pd.concat(person_dfs_to_process)
        if full_df.empty or 'counterparty' not in full_df.columns:
            continue
        full_df = utils.sort_transactions_strict(full_df, date_col='date', dropna_date=True)
        if full_df.empty:
            continue
            
        # 预先过滤核心人员之间的直接转账
        counterparty_series = utils.normalize_text_series(full_df['counterparty'])
        core_person_pattern = '|'.join([p for p in core_persons if p != person_name])
        is_direct = counterparty_series.str.contains(core_person_pattern, na=False)
        
        # 预先过滤排除平台
        is_excluded = counterparty_series.map(lambda x: _is_excluded_relay(x, excluded_keywords))
        
        # 筛选支出
        out_mask = (~is_direct) & (~is_excluded) & (full_df['expense'] >= min_amount)
        if out_mask.any():
            for _, row in full_df[out_mask].iterrows():
                person_outflows[person_name].append({
                    'date': row.get('date'),
                    'amount': row['expense'],
                    'counterparty': str(row.get('counterparty', '')),
                    'description': str(row.get('description', '')),
                    # 【审计溯源】原始文件和行号
                    'source_file': row.get('数据来源', ''),
                    'source_row_index': row.get('source_row_index', None)
                })
        
        # 筛选收入
        in_mask = (~is_direct) & (~is_excluded) & (full_df['income'] >= min_amount)
        if in_mask.any():
            for _, row in full_df[in_mask].iterrows():
                person_inflows[person_name].append({
                    'date': row.get('date'),
                    'amount': row['income'],
                    'counterparty': str(row.get('counterparty', '')),
                    'description': str(row.get('description', '')),
                    # 【审计溯源】原始文件和行号
                    'source_file': row.get('数据来源', ''),
                    'source_row_index': row.get('source_row_index', None)
                })
    
    return person_outflows, person_inflows


def _find_relay_chains(
    person_outflows: Dict,
    person_inflows: Dict,
    core_persons: List[str],
    time_window_hours: int,
    amount_tolerance: float
) -> List[Dict]:
    """
    寻找 A→C→B 模式的中转链
    
    Args:
        person_outflows: 人员支出记录
        person_inflows: 人员收入记录
        core_persons: 核心人员列表
        time_window_hours: 时间窗口（小时）
        amount_tolerance: 金额容差比例
    
    Returns:
        中转链列表
    """
    relay_chains = []
    time_delta = timedelta(hours=time_window_hours)
    
    for person_a in core_persons:
        for person_b in core_persons:
            if person_a == person_b:
                continue
            
            for outflow in person_outflows[person_a]:
                for inflow in person_inflows[person_b]:
                    # 检查是否同一中间人（对手方匹配）
                    if outflow['counterparty'] != inflow['counterparty']:
                        continue
                    
                    # 跳过空对手方或nan
                    cp = outflow['counterparty'].strip()
                    if not cp or cp.lower() == 'nan':
                        continue
                    
                    # 检查时间窗口
                    if outflow['date'] is None or inflow['date'] is None:
                        continue
                    
                    time_diff = inflow['date'] - outflow['date']
                    if time_diff < timedelta(0) or time_diff > time_delta:
                        continue
                    
                    # 检查金额相近
                    if not utils.is_amount_similar(outflow['amount'], inflow['amount'], amount_tolerance):
                        continue
                    
                    # 发现中转链
                    relay = {
                        'from': person_a,
                        'relay': outflow['counterparty'],
                        'to': person_b,
                        'outflow_date': outflow['date'],
                        'inflow_date': inflow['date'],
                        'time_diff_hours': time_diff.total_seconds() / 3600,
                        'outflow_amount': outflow['amount'],
                        'inflow_amount': inflow['amount'],
                        'amount_diff': abs(outflow['amount'] - inflow['amount']),
                        'outflow_desc': outflow['description'],
                        'inflow_desc': inflow['description'],
                        'outflow_source_file': outflow.get('source_file', ''),
                        'outflow_source_row_index': outflow.get('source_row_index'),
                        'inflow_source_file': inflow.get('source_file', ''),
                        'inflow_source_row_index': inflow.get('source_row_index'),
                        'risk_level': _assess_relay_risk(time_diff, outflow['amount'], inflow['amount'])
                    }
                    relay_chains.append(relay)
    
    return relay_chains


def _deduplicate_and_sort_relays(relay_chains: List[Dict]) -> List[Dict]:
    """
    去重并排序中转链
    
    Args:
        relay_chains: 原始中转链列表
    
    Returns:
        去重排序后的中转链列表
    """
    # 去重（同一中转链可能被多次匹配）
    unique_chains = []
    seen_keys = set()
    for relay in relay_chains:
        key = (relay['from'], relay['relay'], relay['to'],
               str(relay['outflow_date'])[:10], str(relay['inflow_date'])[:10])
        if key not in seen_keys:
            seen_keys.add(key)
            unique_chains.append(relay)
    
    # 按风险等级和金额排序
    unique_chains.sort(key=lambda x: (
        {'high': 0, 'medium': 1, 'low': 2}.get(x['risk_level'], 3),
        -x['outflow_amount']
    ))
    
    return unique_chains


def _detect_third_party_relay(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    time_window_hours: int = 72,
    amount_tolerance: float = 0.15,
    min_amount: float = config.PENETRATION_MIN_AMOUNT  # 最低金额门槛：1万元
) -> List[Dict]:
    """
    检测第三方中转模式: A→C→B（A、B为关联人，C为中间人）
    
    算法：
    1. 收集所有关联人的支出记录
    2. 收集所有关联人的收入记录
    3. 寻找 A支出→C，C→B收入 的配对（时间窗口内、金额相近）
    
    过滤规则：
    - 排除公共支付平台（财付通、支付宝等）作为中间人
    - 金额必须 >= min_amount（默认1万元）
    """
    # 获取排除关键词
    excluded_keywords = _get_excluded_relay_keywords()
    
    # 收集所有关联人的支出和收入记录
    person_outflows, person_inflows = _collect_person_flows(
        all_transactions, core_persons, excluded_keywords, min_amount
    )
    
    # 寻找 A→C→B 模式
    relay_chains = _find_relay_chains(
        person_outflows, person_inflows, core_persons,
        time_window_hours, amount_tolerance
    )
    
    # 去重和排序
    unique_chains = _deduplicate_and_sort_relays(relay_chains)
    unique_chains = [_enrich_relay_record(relay) for relay in unique_chains]
    unique_chains.sort(
        key=lambda item: (
            -item.get('risk_score', 0),
            -float(item.get('outflow_amount', 0) or 0),
            float(item.get('time_diff_hours', 9999) or 9999),
        )
    )
    
    logger.info(f'  发现 {len(unique_chains)} 条第三方中转链 (已过滤支付平台和小额交易)')
    return unique_chains


def _assess_relay_risk(time_diff: timedelta, outflow_amount: float, inflow_amount: float) -> str:
    """评估中转风险等级"""
    hours = time_diff.total_seconds() / 3600
    amount_diff_ratio = abs(outflow_amount - inflow_amount) / max(outflow_amount, 1)
    
    # 高风险：24小时内、金额几乎相同、金额较大
    if hours <= 24 and amount_diff_ratio <= 0.05 and outflow_amount >= config.PENETRATION_MIN_AMOUNT:
        return 'high'
    # 中风险：48小时内、金额相近
    elif hours <= 48 and amount_diff_ratio <= 0.10:
        return 'medium'
    else:
        return 'low'


def _enrich_relay_record(relay: Dict) -> Dict:
    """为第三方中转链补充统一评分、置信度和证据。"""
    outflow_amount = float(relay.get('outflow_amount', 0) or 0)
    inflow_amount = float(relay.get('inflow_amount', 0) or 0)
    amount_diff_ratio = abs(outflow_amount - inflow_amount) / max(outflow_amount, 1)
    time_diff_hours = float(relay.get('time_diff_hours', 0) or 0)

    base_score = {
        'low': 28,
        'medium': 52,
        'high': 72,
        'critical': 88,
    }.get(str(relay.get('risk_level', 'medium')), 52)

    if outflow_amount >= 1_000_000:
        base_score += 18
    elif outflow_amount >= 500_000:
        base_score += 14
    elif outflow_amount >= 100_000:
        base_score += 10
    elif outflow_amount >= 50_000:
        base_score += 6

    if time_diff_hours <= 24:
        base_score += 8
    elif time_diff_hours <= 48:
        base_score += 4

    if amount_diff_ratio <= 0.05:
        base_score += 6
    elif amount_diff_ratio <= 0.10:
        base_score += 3

    confidence = 0.55
    if time_diff_hours <= 24:
        confidence += 0.12
    elif time_diff_hours <= 48:
        confidence += 0.08
    if amount_diff_ratio <= 0.05:
        confidence += 0.12
    elif amount_diff_ratio <= 0.10:
        confidence += 0.08
    if outflow_amount >= 100_000:
        confidence += 0.10

    evidence = [
        f"形成链路 {relay.get('from', '未知')} → {relay.get('relay', '未知')} → {relay.get('to', '未知')}",
        f"时差 {time_diff_hours:.1f} 小时",
        f"金额差比例 {amount_diff_ratio * 100:.1f}%",
    ]
    if outflow_amount > 0:
        evidence.append(f"中转金额 {utils.format_currency(outflow_amount)} 元")

    risk_score = _normalize_risk_score(base_score)
    path_explainability = build_relay_path_explainability(relay)
    enriched = dict(relay)
    enriched.update(
        {
            'risk_score': risk_score,
            'risk_level': _score_to_level(risk_score),
            'confidence': _normalize_confidence(confidence),
            'evidence': evidence,
            'path_explainability': path_explainability,
        }
    )
    return enriched


def _detect_fund_loops(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    max_depth: int = 4,
    return_metadata: bool = False,
) -> List[Dict]:
    """
    检测资金闭环: A→B→C→A
    复用强版资金图搜索，避免外围节点回流漏检。
    """
    personal_data = {}
    company_data = {}
    companies = []

    for entity_name, df in all_transactions.items():
        if df is None or df.empty:
            continue

        normalized_name = utils.normalize_person_name(entity_name)
        if not normalized_name:
            normalized_name = entity_name.split('_')[0] if '_' in entity_name else entity_name

        if '公司' in entity_name or '公司' in normalized_name:
            company_data[normalized_name] = df
            companies.append(normalized_name)
        else:
            personal_data[normalized_name] = df

    money_graph = fund_penetration.build_money_graph(
        personal_data,
        company_data,
        core_persons,
        companies,
    )
    raw_cycles = money_graph.find_cycles(
        min_length=3,
        max_length=max_depth,
        key_nodes=core_persons + companies,
        timeout_seconds=30,
    )
    cycle_meta = dict(getattr(money_graph, 'last_cycle_search_meta', {}) or {})

    unique_loops = []
    seen_loop_keys = set()
    normalized_core_names = {normalize_for_matching(person) for person in core_persons}

    for cycle in raw_cycles:
        participants = cycle[:-1] if cycle and cycle[0] == cycle[-1] else cycle
        if len(participants) < 2:
            continue

        key = tuple(sorted(participants))
        if key in seen_loop_keys:
            continue
        seen_loop_keys.add(key)

        core_count = sum(
            1 for node in participants if normalize_for_matching(str(node)) in normalized_core_names
        )
        external_count = len(participants) - core_count

        loop_record = fund_penetration.build_cycle_record(
            cycle,
            money_graph,
            focus_nodes=core_persons + companies,
            search_metadata=cycle_meta,
        )
        loop_record.update(
            {
                'participants': participants,
                'nodes': participants,
                'core_node_count': core_count,
                'external_node_count': external_count,
            }
        )
        if not loop_record.get('is_valid_cycle', True):
            continue
        unique_loops.append(loop_record)

    logger.info(f'  发现 {len(unique_loops)} 个资金闭环')
    if return_metadata:
        return unique_loops, cycle_meta
    return unique_loops


def _dfs_find_loops(
    current: str,
    start: str,
    edges: Dict,
    path: List,
    visited: Set,
    loops: List,
    max_depth: int,
    core_persons: List[str]
):
    """DFS查找资金闭环"""
    if len(path) >= max_depth:
        return
    
    path.append(current)
    
    for edge in edges.get(current, []):
        next_node = edge['to']
        
        # 跳过自循环（同一人转给自己）
        if next_node == current:
            continue
        
        # 找到闭环
        if next_node == start and len(path) >= 2:
            # 检查是否有至少2个不同的参与者
            unique_participants = set(path)
            if len(unique_participants) >= 2:
                # 检查是否涉及至少2个核心人员
                core_in_path = sum(1 for p in unique_participants 
                                   if any(cp in p for cp in core_persons))
                if core_in_path >= 2:
                    loop = {
                        'participants': path.copy(),
                        'path': ' → '.join(path) + f' → {start}',
                        'length': len(path),
                        'unique_count': len(unique_participants),
                        'risk_level': 'high' if len(unique_participants) >= 3 else 'medium'
                    }
                    loops.append(loop)
            continue
        
        # 继续搜索（只在涉及核心人员时进行深度搜索）
        if next_node not in visited:
            # 检查是否包含其他核心人员
            involves_core = any(p in next_node for p in core_persons)
            if involves_core or len(path) < 2:
                visited.add(next_node)
                _dfs_find_loops(next_node, start, edges, path, visited, loops, max_depth, core_persons)
                visited.discard(next_node)
    
    path.pop()


def _build_flow_matrix(direct_flows: List[Dict], core_persons: List[str]) -> Dict:
    """构建资金流向矩阵"""
    matrix = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'total': 0}))
    
    for flow in direct_flows:
        from_person = flow['from']
        to_person = flow['to']
        amount = flow['amount']
        
        if flow['direction'] == 'pay':
            matrix[from_person][to_person]['count'] += 1
            matrix[from_person][to_person]['total'] += amount
        else:
            matrix[to_person][from_person]['count'] += 1
            matrix[to_person][from_person]['total'] += amount
    
    # 转换为普通字典
    result = {}
    for from_p in matrix:
        result[from_p] = dict(matrix[from_p])
    
    return result


def _extract_discovered_nodes(results: Dict, core_persons: List[str]) -> List[Dict]:
    """从中转链和闭环中提取外围节点。"""
    core_name_set = {normalize_for_matching(person) for person in core_persons}
    node_stats = defaultdict(
        lambda: {
            'name': '',
            'occurrences': 0,
            'relation_types': set(),
            'linked_cores': set(),
            'total_amount': 0.0,
            'max_risk': 'low',
        }
    )
    risk_order = {'low': 1, 'medium': 2, 'high': 3}

    for relay in results.get('third_party_relays', []):
        relay_name = str(relay.get('relay', '')).strip()
        if not relay_name:
            continue
        if is_payment_platform_counterparty(relay_name):
            continue
        key = normalize_for_matching(relay_name)
        if key in core_name_set:
            continue

        stat = node_stats[key]
        stat['name'] = relay_name
        stat['occurrences'] += 1
        stat['relation_types'].add('third_party_relay')
        stat['linked_cores'].update(
            {
                str(relay.get('from', '')).strip(),
                str(relay.get('to', '')).strip(),
            }
        )
        stat['total_amount'] += float(relay.get('outflow_amount', 0) or 0)
        relay_risk = str(relay.get('risk_level', 'low'))
        if risk_order.get(relay_risk, 0) > risk_order.get(stat['max_risk'], 0):
            stat['max_risk'] = relay_risk

    for loop in results.get('fund_loops', []):
        participants = loop.get('participants') or loop.get('nodes') or []
        for node in participants:
            node_name = str(node).strip()
            if not node_name:
                continue
            if is_payment_platform_counterparty(node_name):
                continue
            key = normalize_for_matching(node_name)
            if key in core_name_set:
                continue

            stat = node_stats[key]
            stat['name'] = node_name
            stat['occurrences'] += 1
            stat['relation_types'].add('fund_loop')
            for participant in participants:
                participant_name = str(participant).strip()
                if normalize_for_matching(participant_name) in core_name_set:
                    stat['linked_cores'].add(participant_name)
            loop_risk = str(loop.get('risk_level', 'medium'))
            if risk_order.get(loop_risk, 0) > risk_order.get(stat['max_risk'], 0):
                stat['max_risk'] = loop_risk

    discovered_nodes = []
    for stat in node_stats.values():
        linked_cores = sorted(name for name in stat['linked_cores'] if name)
        relation_types = sorted(stat['relation_types'])
        risk_score = 38 + len(relation_types) * 10 + len(linked_cores) * 4 + min(15, stat['occurrences'] * 2)
        if stat['total_amount'] >= 1_000_000:
            risk_score += 18
        elif stat['total_amount'] >= 500_000:
            risk_score += 14
        elif stat['total_amount'] >= 100_000:
            risk_score += 10
        elif stat['total_amount'] > 0:
            risk_score += 6

        confidence = 0.50
        if len(relation_types) >= 2:
            confidence += 0.15
        elif relation_types:
            confidence += 0.10
        if linked_cores:
            confidence += min(0.15, len(linked_cores) * 0.05)
        if stat['total_amount'] > 0:
            confidence += 0.10

        evidence = [
            f"关联类型: {'、'.join(relation_types) or '未标注'}",
            f"关联核心对象 {len(linked_cores)} 个",
            f"在疑点结构中出现 {stat['occurrences']} 次",
        ]
        if stat['total_amount'] > 0:
            evidence.append(f"累计金额估算 {utils.format_currency(stat['total_amount'])} 元")

        normalized_score = _normalize_risk_score(risk_score)
        discovered_nodes.append(
            {
                'name': stat['name'],
                'node_type': 'external',
                'occurrences': stat['occurrences'],
                'relation_types': relation_types,
                'linked_cores': linked_cores,
                'total_amount': stat['total_amount'],
                'risk_score': normalized_score,
                'risk_level': _score_to_level(normalized_score),
                'confidence': _normalize_confidence(confidence),
                'evidence': evidence,
            }
        )

    discovered_nodes.sort(
        key=lambda item: (
            -item['risk_score'],
            -item['occurrences'],
            -item['total_amount'],
            item['name'],
        )
    )
    return discovered_nodes


def _is_family_core_group(
    core_members: List[str],
    family_pair_keys: Optional[Set[frozenset[str]]] = None,
) -> bool:
    if len(core_members) < 2 or not family_pair_keys:
        return False

    for idx, left in enumerate(core_members):
        for right in core_members[idx + 1:]:
            if not is_family_pair(left, right, family_pair_keys):
                return False
    return True


def _build_relationship_clusters(
    results: Dict,
    core_persons: List[str],
    family_pair_keys: Optional[Set[frozenset[str]]] = None,
) -> List[Dict]:
    """构建包含核心人员和外围节点的关系簇。"""
    adjacency = defaultdict(set)
    cluster_stats = defaultdict(lambda: {'direct_flow_count': 0, 'relay_count': 0, 'loop_count': 0, 'total_amount': 0.0})

    def _collect_representative_paths(component_nodes: Set[str]) -> List[Dict]:
        candidates = []

        for loop in results.get('fund_loops', []):
            participants = set(loop.get('participants') or loop.get('nodes') or [])
            path_explainability = loop.get('path_explainability') or {}
            if participants and participants.issubset(component_nodes):
                candidates.append(
                    {
                        'path_type': 'fund_cycle',
                        'path': str(loop.get('path', '')).strip(),
                        'nodes': list(path_explainability.get('nodes') or list(participants)),
                        'amount': float(loop.get('total_amount', 0) or 0),
                        'risk_score': float(loop.get('risk_score', 0) or 0),
                        'confidence': float(loop.get('confidence', 0) or 0),
                        'summary': str(path_explainability.get('summary', '') or '').strip(),
                        'inspection_points': list(path_explainability.get('inspection_points', []) or []),
                        'path_explainability': path_explainability,
                    }
                )

        for relay in results.get('third_party_relays', []):
            nodes = {
                str(relay.get('from', '')).strip(),
                str(relay.get('relay', '')).strip(),
                str(relay.get('to', '')).strip(),
            }
            nodes.discard('')
            path_explainability = relay.get('path_explainability') or build_relay_path_explainability(relay)
            if nodes and nodes.issubset(component_nodes):
                candidates.append(
                    {
                        'path_type': 'third_party_relay',
                        'path': str(path_explainability.get('path', '') or f"{relay.get('from', '未知')} → {relay.get('relay', '未知')} → {relay.get('to', '未知')}").strip(),
                        'nodes': list(path_explainability.get('nodes') or nodes),
                        'amount': float(relay.get('outflow_amount', 0) or 0),
                        'risk_score': float(relay.get('risk_score', 0) or 0),
                        'confidence': float(relay.get('confidence', 0) or 0),
                        'summary': str(path_explainability.get('summary', '') or '').strip(),
                        'inspection_points': list(path_explainability.get('inspection_points', []) or []),
                        'path_explainability': path_explainability,
                    }
                )

        for flow in results.get('direct_flows', []):
            from_node = str(flow.get('from', '')).strip()
            to_node = str(flow.get('to', '')).strip()
            if from_node and to_node and {from_node, to_node}.issubset(component_nodes):
                path_explainability = build_direct_flow_path_explainability(flow)
                candidates.append(
                    {
                        'path_type': 'direct_flow',
                        'path': str(path_explainability.get('path', '') or f"{from_node} → {to_node}").strip(),
                        'nodes': list(path_explainability.get('nodes') or [from_node, to_node]),
                        'amount': float(flow.get('amount', 0) or 0),
                        'risk_score': float(flow.get('amount', 0) or 0),
                        'summary': str(path_explainability.get('summary', '') or '').strip(),
                        'inspection_points': list(path_explainability.get('inspection_points', []) or []),
                        'path_explainability': path_explainability,
                    }
                )

        return rank_representative_paths(
            candidates,
            focus_nodes=core_persons,
            limit=max(len(candidates), 1),
        )

    def _add_edge(node_a: str, node_b: str, stat_key: str, amount: float = 0.0):
        if not node_a or not node_b or node_a == node_b:
            return
        adjacency[node_a].add(node_b)
        adjacency[node_b].add(node_a)
        cluster_stats[(min(node_a, node_b), max(node_a, node_b))][stat_key] += 1
        cluster_stats[(min(node_a, node_b), max(node_a, node_b))]['total_amount'] += amount

    for flow in results.get('direct_flows', []):
        _add_edge(
            str(flow.get('from', '')).strip(),
            str(flow.get('to', '')).strip(),
            'direct_flow_count',
            float(flow.get('amount', 0) or 0),
        )

    for relay in results.get('third_party_relays', []):
        from_person = str(relay.get('from', '')).strip()
        relay_name = str(relay.get('relay', '')).strip()
        to_person = str(relay.get('to', '')).strip()
        amount = float(relay.get('outflow_amount', 0) or 0)
        _add_edge(from_person, relay_name, 'relay_count', amount)
        _add_edge(relay_name, to_person, 'relay_count', amount)

    for loop in results.get('fund_loops', []):
        participants = loop.get('participants') or loop.get('nodes') or []
        if not participants:
            continue
        cycle_nodes = participants + [participants[0]]
        for idx in range(len(cycle_nodes) - 1):
            _add_edge(
                str(cycle_nodes[idx]).strip(),
                str(cycle_nodes[idx + 1]).strip(),
                'loop_count',
                float(loop.get('total_amount', 0) or 0),
            )

    visited = set()
    core_name_set = {normalize_for_matching(person) for person in core_persons}
    clusters = []

    for core_person in core_persons:
        if core_person in visited:
            continue
        if core_person not in adjacency:
            continue

        stack = [core_person]
        component = set()
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            stack.extend(neighbor for neighbor in adjacency[node] if neighbor not in visited)

        core_members = sorted(
            node for node in component if normalize_for_matching(node) in core_name_set
        )
        external_members = sorted(
            node
            for node in component
            if normalize_for_matching(node) not in core_name_set
            and not is_payment_platform_counterparty(node)
        )

        if not core_members:
            continue

        relation_types = set()
        direct_flow_count = 0
        relay_count = 0
        loop_count = 0
        total_amount = 0.0

        for edge_key, stat in cluster_stats.items():
            if edge_key[0] in component and edge_key[1] in component:
                direct_flow_count += stat['direct_flow_count']
                relay_count += stat['relay_count']
                loop_count += stat['loop_count']
                total_amount += stat['total_amount']
                if stat['direct_flow_count']:
                    relation_types.add('direct_flow')
                if stat['relay_count']:
                    relation_types.add('third_party_relay')
                if stat['loop_count']:
                    relation_types.add('fund_loop')

        family_cluster = (
            not external_members
            and relay_count == 0
            and loop_count == 0
            and _is_family_core_group(core_members, family_pair_keys)
        )

        if family_cluster:
            risk_score = 8
            if direct_flow_count >= 20:
                risk_score += 8
            elif direct_flow_count >= 8:
                risk_score += 5
            elif direct_flow_count > 0:
                risk_score += 3

            if total_amount >= 1_000_000:
                risk_score += 10
            elif total_amount >= 500_000:
                risk_score += 7
            elif total_amount >= 100_000:
                risk_score += 4
            elif total_amount > 0:
                risk_score += 2
        else:
            risk_score = 35 + direct_flow_count * 4 + relay_count * 8 + loop_count * 15
            risk_score += min(12, len(external_members) * 3)
            if total_amount >= 1_000_000:
                risk_score += 18
            elif total_amount >= 500_000:
                risk_score += 14
            elif total_amount >= 100_000:
                risk_score += 10
            elif total_amount > 0:
                risk_score += 6

        confidence = 0.50
        if loop_count > 0:
            confidence += 0.18
        if relay_count > 0:
            confidence += 0.12
        if direct_flow_count > 0:
            confidence += 0.08
        if total_amount > 0:
            confidence += 0.10
        if family_cluster:
            confidence -= 0.10

        evidence = [
            f"核心成员 {len(core_members)} 个，外围成员 {len(external_members)} 个",
            f"直接往来/中转/闭环 = {direct_flow_count}/{relay_count}/{loop_count}",
            f"关系类型: {'、'.join(sorted(relation_types)) or '未标注'}",
        ]
        if family_cluster:
            evidence.append("命中家庭成员关系，当前按家庭内部资金往来降级展示")
        if total_amount > 0:
            evidence.append(f"聚合金额估算 {utils.format_currency(total_amount)} 元")

        normalized_score = _normalize_risk_score(risk_score)
        ranked_representative_paths = _collect_representative_paths(component)
        representative_paths = ranked_representative_paths[:5]
        cluster_payload = {
            'cluster_id': f'cluster_{len(clusters) + 1}',
            'core_members': core_members,
            'external_members': external_members,
            'all_nodes': sorted(component),
            'relation_types': sorted(relation_types),
            'direct_flow_count': direct_flow_count,
            'relay_count': relay_count,
            'loop_count': loop_count,
            'total_amount': total_amount,
            'risk_score': normalized_score,
            'risk_level': _score_to_level(normalized_score),
            'confidence': _normalize_confidence(confidence),
            'evidence': evidence,
            'relationship_context': 'family' if family_cluster else 'external',
            'representative_path_total': len(ranked_representative_paths),
        }
        cluster_payload['path_explainability'] = build_cluster_path_explainability(
            cluster_payload,
            representative_paths=representative_paths,
        )
        clusters.append(
            cluster_payload
        )

    clusters.sort(
        key=lambda item: (
            -item['risk_score'],
            -item['loop_count'],
            -item['relay_count'],
            -item['total_amount'],
        )
    )
    return clusters


def _generate_summary(results: Dict, core_persons: List[str]) -> Dict:
    """生成关联方分析汇总"""
    direct_flows = results['direct_flows']
    relays = results['third_party_relays']
    loops = results['fund_loops']
    discovered_nodes = results.get('discovered_nodes', [])
    relationship_clusters = results.get('relationship_clusters', [])
    
    summary = {
        '关联人数量': len(core_persons),
        '直接往来笔数': len(direct_flows),
        '直接往来总金额': sum(f['amount'] for f in direct_flows),
        '第三方中转链数': len(relays),
        '高风险中转': len([r for r in relays if r['risk_level'] == 'high']),
        '资金闭环数': len(loops),
        '外围节点数': len(discovered_nodes),
        '关系簇数': len(relationship_clusters),
        '高频中间人': _find_frequent_relays(relays)
    }
    
    return summary


def _find_frequent_relays(relays: List[Dict], min_count: int = 2) -> List[Dict]:
    """找出高频中间人"""
    relay_counter = defaultdict(lambda: {'count': 0, 'total_amount': 0, 'chains': []})
    
    for relay in relays:
        name = relay['relay']
        relay_counter[name]['count'] += 1
        relay_counter[name]['total_amount'] += relay['outflow_amount']
        relay_counter[name]['chains'].append(f"{relay['from']}→{relay['to']}")
    
    frequent = []
    for name, data in relay_counter.items():
        if data['count'] >= min_count:
            frequent.append({
                'name': name,
                'count': data['count'],
                'total_amount': data['total_amount'],
                'chains': list(set(data['chains']))
            })
    
    frequent.sort(key=lambda x: -x['count'])
    return frequent


def generate_related_party_report(results: Dict, output_dir: str) -> str:
    """生成关联方分析报告（增强版）"""
    import os
    report_path = os.path.join(output_dir, '关联方资金分析报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('关联方资金穿透分析报告（增强版）\n')
        f.write('='*60 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        
        # 报告说明
        f.write('【报告用途】\n')
        f.write('本报告分析核心人员之间的资金往来，包括：\n')
        f.write('• 直接资金往来 - 核心人员之间的转账\n')
        f.write('• 第三方中转 - A→C→B 模式的资金中转\n')
        f.write('• 资金闭环 - A→B→C→A 形式的资金回流\n\n')
        
        f.write('【分析逻辑与规则】\n')
        f.write('1. 直接往来: 对手方与核心人员名精确匹配\n')
        f.write('2. 第三方中转: 72小时内、金额相近(15%容差)、排除公共支付平台\n')
        f.write('3. 资金闭环: DFS搜索>=2个核心人员参与的路径\n\n')
        
        f.write('【可能的误判情况】\n')
        f.write('⚠ 家庭成员间的正常转账可能被标记为直接往来\n')
        f.write('⚠ 同一地区同名人哥可能被误判为关联方\n')
        f.write('⚠ 结婚/离婚财产分割可能形成伪闭环\n\n')
        
        f.write('【人工复核重点】\n')
        f.write('★ 第三方中转: 核实中间人身份\n')
        f.write('★ 高频中间人: 核实是否为掂客\n')
        f.write('★ 资金闭环: 核实闭环形成原因\n\n')
        
        f.write('='*60 + '\n\n')
        
        # 汇总
        summary = results['summary']
        f.write('一、汇总统计\n')
        f.write('-'*40 + '\n')
        f.write(f"核心关联人数量: {summary['关联人数量']}\n")
        f.write(f"直接往来: {summary['直接往来笔数']} 笔, 金额 {utils.format_currency(summary['直接往来总金额'])}\n")
        f.write(f"第三方中转: {summary['第三方中转链数']} 条链路 (高风险 {summary['高风险中转']} 条)\n")
        f.write(f"资金闭环: {summary['资金闭环数']} 个\n\n")
        
        # 高频中间人
        if summary['高频中间人']:
            f.write('二、高频中间人/账户（掮客嫌疑）\n')
            f.write('-'*40 + '\n')
            for i, relay in enumerate(summary['高频中间人'][:10], 1):
                f.write(f"{i}. {relay['name']}: 出现{relay['count']}次, "
                       f"涉及金额{utils.format_currency(relay['total_amount'])}\n")
                f.write(f"   涉及链路: {', '.join(relay['chains'][:5])}\n")
            f.write('\n')
        
        # 直接往来明细
        if results['direct_flows']:
            f.write('三、关联人直接资金往来明细\n')
            f.write('-'*40 + '\n')
            f.write(f'共 {len(results["direct_flows"])} 笔记录\n\n')
            for i, flow in enumerate(results['direct_flows'], 1):
                date_str = flow['date'].strftime('%Y-%m-%d') if hasattr(flow['date'], 'strftime') else str(flow['date'])[:10]
                direction = '←' if flow['direction'] == 'receive' else '→'
                desc = utils.safe_str(flow['description'], default='转账')[:30]
                f.write(f"{i}. [{date_str}] {flow['from']} {direction} {flow['to']}: "
                       f"{utils.format_currency(flow['amount'])} | {desc}\n")
            f.write('\n')
        
        # 第三方中转
        if results['third_party_relays']:
            f.write('四、第三方中转链路（重点关注）\n')
            f.write('-'*40 + '\n')
            f.write(f'共 {len(results["third_party_relays"])} 条链路\n\n')
            for i, relay in enumerate(results['third_party_relays'], 1):
                out_date = relay['outflow_date'].strftime('%Y-%m-%d') if hasattr(relay['outflow_date'], 'strftime') else str(relay['outflow_date'])[:10]
                in_date = relay['inflow_date'].strftime('%Y-%m-%d') if hasattr(relay['inflow_date'], 'strftime') else str(relay['inflow_date'])[:10]
                f.write(f"{i}. 【{relay['risk_level'].upper()}】{relay['from']} → {relay['relay']} → {relay['to']}\n")
                f.write(f"   出: {out_date} {utils.format_currency(relay['outflow_amount'])} | "
                       f"入: {in_date} {utils.format_currency(relay['inflow_amount'])} | "
                       f"时差: {relay['time_diff_hours']:.1f}小时\n")
            f.write('\n')
        
        # 资金闭环
        if results['fund_loops']:
            f.write('五、资金闭环（疑似走账）\n')
            f.write('-'*40 + '\n')
            f.write(f'共 {len(results["fund_loops"])} 个闭环\n\n')
            for i, loop in enumerate(results['fund_loops'], 1):
                f.write(f"{i}. 【{loop['risk_level'].upper()}】{loop['path']}\n")
            f.write('\n')
    
    logger.info(f'关联方分析报告已生成: {report_path}')
    return report_path
# ========== Phase 4: 调查单位往来统计 (2026-01-20 新增) ==========

def analyze_investigation_unit_flows(
    df: pd.DataFrame,
    entity_name: str
) -> Dict:
    """
    分析与调查单位的资金往来
    
    【Phase 4 - 2026-01-20】
    功能:
    1. 读取配置中的调查单位关键词
    2. 筛选与调查单位相关的交易记录
    3. 统计总收入、总支出、交易笔数
    4. 识别高频往来和大额交易
    5. 返回详细的往来分析结果
    
    Args:
        df: 交易DataFrame
        entity_name: 实体名称
    
    Returns:
        调查单位往来分析结果,包含:
        - has_flows: 是否有往来
        - total_income: 从调查单位收到的总金额
        - total_expense: 向调查单位支付的总金额
        - net_flow: 净流入(收入-支出)
        - income_count: 收入笔数
        - expense_count: 支出笔数
        - income_details: 收入明细列表
        - expense_details: 支出明细列表
        - matched_units: 匹配到的调查单位列表
    """
    logger.info(f'正在分析{entity_name}与调查单位的资金往来...')
    
    # 读取配置中的调查单位关键词
    investigation_keywords = config.INVESTIGATION_UNIT_KEYWORDS
    
    # 如果配置为空,返回空结果
    if not investigation_keywords:
        logger.info('未配置调查单位关键词,跳过分析')
        return {
            'has_flows': False,
            'total_income': 0.0,
            'total_expense': 0.0,
            'net_flow': 0.0,
            'income_count': 0,
            'expense_count': 0,
            'income_details': [],
            'expense_details': [],
            'matched_units': [],
            'config_empty': True
        }
    
    if df.empty:
        logger.warning(f'{entity_name}无交易数据')
        return {
            'has_flows': False,
            'total_income': 0.0,
            'total_expense': 0.0,
            'net_flow': 0.0,
            'income_count': 0,
            'expense_count': 0,
            'income_details': [],
            'expense_details': [],
            'matched_units': [],
            'config_empty': False
        }
    
    # 初始化统计变量
    total_income = 0.0
    total_expense = 0.0
    income_details = []
    expense_details = []
    matched_units = set()
    
    # 遍历交易记录,筛选与调查单位相关的交易
    for _, row in df.iterrows():
        counterparty = str(row.get('counterparty', '')).strip()
        description = str(row.get('description', '')).strip()
        
        # 检查对手方或摘要是否包含调查单位关键词
        is_investigation_unit = False
        matched_keyword = None
        
        for keyword in investigation_keywords:
            if keyword in counterparty or keyword in description:
                is_investigation_unit = True
                matched_keyword = keyword
                matched_units.add(keyword)
                break
        
        if not is_investigation_unit:
            continue
        
        # 构建交易记录
        date_str = row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else '未知'
        
        # 收入交易
        if row['income'] > 0:
            amount = row['income']
            total_income += amount
            income_details.append({
                'date': date_str,
                'amount': float(amount),
                'counterparty': counterparty,
                'description': description,
                'matched_keyword': matched_keyword
            })
        
        # 支出交易
        if row['expense'] > 0:
            amount = row['expense']
            total_expense += amount
            expense_details.append({
                'date': date_str,
                'amount': float(amount),
                'counterparty': counterparty,
                'description': description,
                'matched_keyword': matched_keyword
            })
    
    # 计算净流入
    net_flow = total_income - total_expense
    
    # 按金额降序排序
    income_details.sort(key=lambda x: x['amount'], reverse=True)
    expense_details.sort(key=lambda x: x['amount'], reverse=True)
    
    # 判断是否有往来
    has_flows = (total_income > 0 or total_expense > 0)
    
    if has_flows:
        logger.info(f'与调查单位往来: 收入{utils.format_currency(total_income)}({len(income_details)}笔), '
                    f'支出{utils.format_currency(total_expense)}({len(expense_details)}笔), '
                    f'净流入{utils.format_currency(net_flow)}')
        logger.info(f'匹配到的调查单位: {", ".join(matched_units)}')
    else:
        logger.info('未发现与调查单位的资金往来')
    
    return {
        'has_flows': has_flows,
        'total_income': float(total_income),
        'total_expense': float(total_expense),
        'net_flow': float(net_flow),
        'income_count': len(income_details),
        'expense_count': len(expense_details),
        'income_details': income_details[:50],  # 只保留前50笔
        'expense_details': expense_details[:50],
        'matched_units': list(matched_units),
        'config_empty': False
    }
