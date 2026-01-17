#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关联方资金穿透分析模块
分析核心人员之间的直接资金往来、第三方中转、资金闭环等模式
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Set
from collections import defaultdict
import config
import utils

logger = utils.setup_logger(__name__)


def analyze_related_party_flows(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
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
    
    results = {
        'direct_flows': [],           # 直接资金往来
        'third_party_relays': [],     # 第三方中转
        'fund_loops': [],             # 资金闭环
        'flow_matrix': {},            # 资金流向矩阵
        'summary': {}
    }
    
    # 1. 分析直接资金往来
    logger.info('【阶段1】分析关联人直接资金往来')
    results['direct_flows'] = _analyze_direct_flows(all_transactions, core_persons)
    
    # 2. 检测第三方中转
    logger.info('【阶段2】检测第三方中转模式')
    results['third_party_relays'] = _detect_third_party_relay(all_transactions, core_persons)
    
    # 3. 检测资金闭环
    logger.info('【阶段3】检测资金闭环')
    results['fund_loops'] = _detect_fund_loops(all_transactions, core_persons)
    
    # 4. 构建资金流向矩阵
    logger.info('【阶段4】构建资金流向矩阵')
    results['flow_matrix'] = _build_flow_matrix(results['direct_flows'], core_persons)
    
    # 5. 生成汇总
    results['summary'] = _generate_summary(results, core_persons)
    
    logger.info('')
    logger.info(f'关联方分析完成: 直接往来{len(results["direct_flows"])}笔, '
                f'第三方中转{len(results["third_party_relays"])}条链, '
                f'资金闭环{len(results["fund_loops"])}个')
    
    return results


def _analyze_direct_flows(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
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
        counterparty_series = df['counterparty'].astype(str).fillna('')
        
        for other_person in core_persons:
            if other_person == person:
                continue
            
            # 【P1修复】使用精确匹配而非 contains，避免"施灵"匹配到"施灵芝"等误判
            # 精确匹配：对手方必须完全等于核心人员名称
            mask = counterparty_series == other_person
            if mask.any():
                subset = df[mask]
                for _, row in subset.iterrows():
                    flow = {
                        'from': person,
                        'to': other_person,
                        'date': row.get('date'),
                        'amount': max(row.get('income', 0), row.get('expense', 0)),
                        'direction': 'receive' if row.get('income', 0) > 0 else 'pay',
                        'description': row.get('description', ''),
                        'counterparty_raw': str(row.get('counterparty', ''))
                    }
                    direct_flows.append(flow)
    
    logger.info(f'  发现 {len(direct_flows)} 笔关联人直接资金往来')
    return direct_flows


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
            
        # 预先过滤核心人员之间的直接转账
        counterparty_series = full_df['counterparty'].astype(str).fillna('')
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
                    'description': str(row.get('description', ''))
                })
        
        # 筛选收入
        in_mask = (~is_direct) & (~is_excluded) & (full_df['income'] >= min_amount)
        if in_mask.any():
            for _, row in full_df[in_mask].iterrows():
                person_inflows[person_name].append({
                    'date': row.get('date'),
                    'amount': row['income'],
                    'counterparty': str(row.get('counterparty', '')),
                    'description': str(row.get('description', ''))
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


def _detect_fund_loops(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    max_depth: int = 4
) -> List[Dict]:
    """
    检测资金闭环: A→B→C→A
    使用图搜索检测环路
    """
    loops = []
    
    # 构建有向图：节点为实体，边为转账
    edges = defaultdict(list)  # {from: [(to, amount, date), ...]}
    
    for entity_name, df in all_transactions.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
        
        # 提取实体名
        entity = utils.normalize_person_name(entity_name)
        if not entity:
            entity = entity_name.split('_')[0] if '_' in entity_name else entity_name
        
        # 只处理有支出的行
        expense_mask = df['expense'] > 0
        if not expense_mask.any():
            continue
            
        subset = df[expense_mask]
        for _, row in subset.iterrows():
            counterparty = str(row.get('counterparty', ''))
            edges[entity].append({
                'to': counterparty,
                'amount': row['expense'],
                'date': row.get('date')
            })
    
    # 从每个核心人员开始DFS查找环路
    for start_person in core_persons:
        visited = set()
        path = []
        _dfs_find_loops(start_person, start_person, edges, path, visited, loops, max_depth, core_persons)
    
    # 去重（同一个环可能从不同起点被发现）
    unique_loops = []
    seen_loop_keys = set()
    for loop in loops:
        # 使用排序后的节点列表作为key
        key = tuple(sorted(loop['participants']))
        if key not in seen_loop_keys:
            seen_loop_keys.add(key)
            unique_loops.append(loop)
    
    logger.info(f'  发现 {len(unique_loops)} 个资金闭环')
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


def _generate_summary(results: Dict, core_persons: List[str]) -> Dict:
    """生成关联方分析汇总"""
    direct_flows = results['direct_flows']
    relays = results['third_party_relays']
    loops = results['fund_loops']
    
    summary = {
        '关联人数量': len(core_persons),
        '直接往来笔数': len(direct_flows),
        '直接往来总金额': sum(f['amount'] for f in direct_flows),
        '第三方中转链数': len(relays),
        '高风险中转': len([r for r in relays if r['risk_level'] == 'high']),
        '资金闭环数': len(loops),
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
    """生成关联方分析报告"""
    import os
    report_path = os.path.join(output_dir, '关联方资金分析报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('关联方资金穿透分析报告\n')
        f.write('='*60 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        
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
            for i, flow in enumerate(results['direct_flows'][:30], 1):
                date_str = flow['date'].strftime('%Y-%m-%d') if hasattr(flow['date'], 'strftime') else str(flow['date'])[:10]
                direction = '←' if flow['direction'] == 'receive' else '→'
                desc = utils.safe_str(flow['description'], default='转账')[:30]
                f.write(f"{i}. [{date_str}] {flow['from']} {direction} {flow['to']}: "
                       f"{utils.format_currency(flow['amount'])} | {desc}\n")
            if len(results['direct_flows']) > 30:
                f.write(f'... 共 {len(results["direct_flows"])} 笔\n')
            f.write('\n')
        
        # 第三方中转
        if results['third_party_relays']:
            f.write('四、第三方中转链路（重点关注）\n')
            f.write('-'*40 + '\n')
            for i, relay in enumerate(results['third_party_relays'][:20], 1):
                out_date = relay['outflow_date'].strftime('%Y-%m-%d') if hasattr(relay['outflow_date'], 'strftime') else str(relay['outflow_date'])[:10]
                in_date = relay['inflow_date'].strftime('%Y-%m-%d') if hasattr(relay['inflow_date'], 'strftime') else str(relay['inflow_date'])[:10]
                f.write(f"{i}. 【{relay['risk_level'].upper()}】{relay['from']} → {relay['relay']} → {relay['to']}\n")
                f.write(f"   出: {out_date} {utils.format_currency(relay['outflow_amount'])} | "
                       f"入: {in_date} {utils.format_currency(relay['inflow_amount'])} | "
                       f"时差: {relay['time_diff_hours']:.1f}小时\n")
            if len(results['third_party_relays']) > 20:
                f.write(f'... 共 {len(results["third_party_relays"])} 条链路\n')
            f.write('\n')
        
        # 资金闭环
        if results['fund_loops']:
            f.write('五、资金闭环（疑似走账）\n')
            f.write('-'*40 + '\n')
            for i, loop in enumerate(results['fund_loops'][:10], 1):
                f.write(f"{i}. 【{loop['risk_level'].upper()}】{loop['path']}\n")
            f.write('\n')
    
    logger.info(f'关联方分析报告已生成: {report_path}')
    return report_path
