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
import pandas as pd
from typing import Dict, List, Set, Tuple
from datetime import datetime
from collections import defaultdict

import utils

logger = utils.setup_logger(__name__)


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
        self.node_flows = defaultdict(lambda: {'inflow': 0, 'outflow': 0})
    
    def add_edge(self, source: str, target: str, amount: float, date, edge_type: str = 'transfer'):
        """添加资金边"""
        self.nodes.add(source)
        self.nodes.add(target)
        self.edges[source].append({
            'target': target,
            'amount': amount,
            'date': date,
            'type': edge_type
        })
        # 更新流量统计
        self.node_flows[source]['outflow'] += amount
        self.node_flows[target]['inflow'] += amount
    
    def set_node_type(self, node: str, node_type: str):
        """设置节点类型"""
        self.node_types[node] = node_type
    
    def find_all_paths(self, source: str, target: str, max_depth: int = 5) -> List[List[str]]:
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
                next_node = edge['target']
                if next_node not in visited or next_node == target:
                    visited.add(next_node)
                    path.append(next_node)
                    dfs(next_node, path, visited)
                    path.pop()
                    if next_node != target:
                        visited.discard(next_node)
        
        dfs(source, [source], {source})
        return paths
    
    def find_cycles(self, min_length: int = 3, max_length: int = 4, 
                     key_nodes: List[str] = None, timeout_seconds: int = 30) -> List[List[str]]:
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
        
        # 公共节点排除列表（这些节点连接太多人，不是真正的闭环）
        # 【优化 2026-01-11】使用更精确的匹配规则
        PUBLIC_NODES_EXACT = ['支付宝', '微信', '财付通', '银联']  # 完整匹配
        PUBLIC_NODES_CONTAINS = ['理财产品', '余额宝', '零钱通']  # 包含匹配
        
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
            if '银行' in node:
                suspicious_suffixes = ['公司', '咨询', '服务', '代理', '中介', '担保']
                if not any(suffix in node for suffix in suspicious_suffixes):
                    return True
            
            # 基金公司判断：只排除正规基金公司
            if '基金' in node and '销售' not in node and '代理' not in node:
                # 正规基金公司名称通常包含"基金管理"
                if '基金管理' in node or node.endswith('基金'):
                    return True
            
            return False
        
        def dfs_cycle(start: str, current: str, path: List[str], visited: Set[str]):
            # 超时检查
            if time.time() - start_time > timeout_seconds:
                return
            
            if len(path) > max_length:
                return
            
            for edge in self.edges.get(current, []):
                next_node = edge['target']
                
                # 跳过公共节点
                if is_public_node(next_node):
                    continue
                
                # 找到闭环
                if next_node == start and len(path) >= min_length:
                    cycles.append(path + [start])
                    if len(cycles) >= 100:  # 限制最多100个闭环
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
        search_nodes = key_nodes if key_nodes else [
            n for n in self.nodes 
            if self.node_types.get(n) in ['person', 'company']
        ]
        
        # 如果还是太多，只取前50个
        if len(search_nodes) > 50:
            search_nodes = search_nodes[:50]
        
        logger.info(f'  闭环搜索: 从 {len(search_nodes)} 个关键节点开始（超时{timeout_seconds}秒）')
        
        # 从关键节点开始搜索闭环
        for node in search_nodes:
            if time.time() - start_time > timeout_seconds:
                logger.warning(f'  闭环搜索超时（已找到 {len(cycles)} 个）')
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
        
        return unique_cycles
    
    def identify_pass_through_channels(self, threshold_ratio: float = 0.9) -> List[Dict]:
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
            inflow = flows['inflow']
            outflow = flows['outflow']
            
            if inflow == 0 or outflow == 0:
                continue
            
            # 计算进出比例
            ratio = min(inflow, outflow) / max(inflow, outflow)
            
            if ratio >= threshold_ratio and inflow >= 100000:  # 至少10万流量
                channels.append({
                    'node': node,
                    'inflow': inflow,
                    'outflow': outflow,
                    'ratio': ratio,
                    'net_retention': abs(inflow - outflow),
                    'node_type': self.node_types.get(node, 'unknown'),
                    'risk_level': 'high' if ratio > 0.95 else 'medium'
                })
        
        # 按流量排序
        channels.sort(key=lambda x: -(x['inflow'] + x['outflow']))
        return channels
    
    def get_node_degree(self, node: str) -> Tuple[int, int]:
        """获取节点的入度和出度"""
        out_degree = len(self.edges.get(node, []))
        in_degree = sum(1 for edges in self.edges.values() for e in edges if e['target'] == node)
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
                hubs.append({
                    'node': node,
                    'in_degree': in_deg,
                    'out_degree': out_deg,
                    'total_degree': total_deg,
                    'node_type': self.node_types.get(node, 'unknown')
                })
        
        hubs.sort(key=lambda x: -x['total_degree'])
        return hubs


# ============================================================
# 构建资金图
# ============================================================

def build_money_graph(
    personal_data: Dict[str, pd.DataFrame],
    company_data: Dict[str, pd.DataFrame],
    core_persons: List[str],
    companies: List[str]
) -> MoneyGraph:
    """
    从交易数据构建资金图
    """
    graph = MoneyGraph()
    
    # 设置节点类型
    for person in core_persons:
        graph.set_node_type(person, 'person')
    for company in companies:
        graph.set_node_type(company, 'company')
    
    # 从个人数据添加边
    for person_name, df in personal_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
        
        for _, row in df.iterrows():
            cp = str(row.get('counterparty', ''))
            if not cp or cp == 'nan' or len(cp) < 2:
                continue
            
            income = row.get('income', 0) or 0
            expense = row.get('expense', 0) or 0
            date = row.get('date')
            
            if income > 10000:  # 1万以上才计入图
                graph.add_edge(cp, person_name, income, date, 'income')
            if expense > 10000:
                graph.add_edge(person_name, cp, expense, date, 'expense')
    
    # 从公司数据添加边
    for company_name, df in company_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
        
        for _, row in df.iterrows():
            cp = str(row.get('counterparty', ''))
            if not cp or cp == 'nan' or len(cp) < 2:
                continue
            
            income = row.get('income', 0) or 0
            expense = row.get('expense', 0) or 0
            date = row.get('date')
            
            if income > 10000:
                graph.add_edge(cp, company_name, income, date, 'income')
            if expense > 10000:
                graph.add_edge(company_name, cp, expense, date, 'expense')
    
    logger.info(f'资金图构建完成: {len(graph.nodes)} 节点, {sum(len(e) for e in graph.edges.values())} 条边')
    return graph


def _df_to_results(subset: pd.DataFrame, 发起方: str, 接收方: str, 方向: str) -> List[Dict]:
    """将DataFrame子集转换为结果列表"""
    if subset.empty:
        return []
    res = []
    for _, row in subset.iterrows():
        res.append({
            '发起方': 发起方,
            '接收方': 接收方,
            '交易对方原文': str(row.get('counterparty', '')),
            '日期': row.get('date'),
            '收入': row.get('income', 0),
            '支出': row.get('expense', 0),
            '摘要': row.get('description', ''),
            '方向': 方向
        })
    return res


def _analyze_graph_deep_analysis(
    money_graph: MoneyGraph,
    core_persons: List[str],
    companies: List[str]
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
        'fund_cycles': [],
        'pass_through_channels': [],
        'hub_nodes': [],
        'multi_hop_paths': [],
        'graph_stats': {}
    }
    
    # 检测资金闭环
    logger.info('【阶段0.1】检测资金闭环（利益回流）...')
    key_nodes = core_persons + companies
    results['fund_cycles'] = money_graph.find_cycles(
        min_length=3, max_length=4, key_nodes=key_nodes, timeout_seconds=30
    )
    logger.info(f'  发现 {len(results["fund_cycles"])} 个资金闭环')
    
    # 识别过账通道
    logger.info('【阶段0.2】识别过账通道（空壳/马甲）...')
    results['pass_through_channels'] = money_graph.identify_pass_through_channels(threshold_ratio=0.85)
    logger.info(f'  发现 {len(results["pass_through_channels"])} 个过账通道')
    
    # 分析资金枢纽节点
    logger.info('【阶段0.3】分析资金枢纽节点...')
    results['hub_nodes'] = money_graph.get_hub_nodes(min_degree=5)
    logger.info(f'  发现 {len(results["hub_nodes"])} 个枢纽节点')
    
    # 多跳路径分析
    logger.info('【阶段0.4】追踪多跳资金路径（核心人员→公司）...')
    import time
    path_start_time = time.time()
    path_timeout = 30
    max_paths = 50
    
    for person in core_persons:
        if time.time() - path_start_time > path_timeout:
            logger.warning(f'  多跳路径搜索超时')
            break
        for company in companies:
            if len(results['multi_hop_paths']) >= max_paths:
                break
            paths = money_graph.find_all_paths(person, company, max_depth=3)
            for path in paths[:5]:
                if len(path) > 2:
                    results['multi_hop_paths'].append({
                        'source': person,
                        'target': company,
                        'path': path,
                        'hops': len(path) - 1,
                        'path_str': ' → '.join(path)
                    })
    logger.info(f'  发现 {len(results["multi_hop_paths"])} 条多跳路径')
    
    # 图统计
    results['graph_stats'] = {
        'total_nodes': len(money_graph.nodes),
        'total_edges': sum(len(e) for e in money_graph.edges.values()),
        'person_nodes': len([n for n, t in money_graph.node_types.items() if t == 'person']),
        'company_nodes': len([n for n, t in money_graph.node_types.items() if t == 'company'])
    }
    
    return results


def _analyze_direct_transactions(
    personal_data: Dict[str, pd.DataFrame],
    company_data: Dict[str, pd.DataFrame],
    core_persons: List[str],
    companies: List[str]
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
        'person_to_company': [],
        'company_to_person': [],
        'person_to_person': [],
        'company_to_company': []
    }
    
    # 预处理公司关键词
    company_patterns = {c: _extract_company_keywords(c) for c in companies}
    
    # 1. 检测个人→公司的资金往来
    logger.info('【阶段1】检测个人→涉案公司的资金往来')
    for person_name, df in personal_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
        
        counterparty_series = df['counterparty'].astype(str).fillna('')
        
        for company, keywords in company_patterns.items():
            mask = counterparty_series.str.contains('|'.join(keywords), na=False, regex=True)
            if mask.any():
                results['person_to_company'].extend(_df_to_results(df[mask], person_name, company, '个人→公司'))
    
    logger.info(f'  发现 {len(results["person_to_company"])} 笔个人→公司交易')
    
    # 2. 检测公司→个人的资金往来
    logger.info('【阶段2】检测涉案公司→个人的资金往来')
    for company_name, df in company_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
            
        counterparty_series = df['counterparty'].astype(str).fillna('')
        
        for person in core_persons:
            mask = counterparty_series.str.contains(person, na=False)
            if mask.any():
                results['company_to_person'].extend(_df_to_results(df[mask], company_name, person, '公司→个人'))
    
    logger.info(f'  发现 {len(results["company_to_person"])} 笔公司→个人交易')
    
    # 3. 检测核心人员之间的资金往来
    logger.info('【阶段3】检测核心人员之间的资金往来')
    for person_name, df in personal_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
            
        counterparty_series = df['counterparty'].astype(str).fillna('')
        
        for other_person in core_persons:
            if other_person == person_name:
                continue
            
            mask = counterparty_series.str.contains(other_person, na=False)
            if mask.any():
                results['person_to_person'].extend(_df_to_results(df[mask], person_name, other_person, '个人→个人'))
    
    logger.info(f'  发现 {len(results["person_to_person"])} 笔核心人员间交易')
    
    # 4. 检测涉案公司之间的资金往来
    logger.info('【阶段4】检测涉案公司之间的资金往来')
    for company_name, df in company_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
            
        counterparty_series = df['counterparty'].astype(str).fillna('')
        
        for other_company, keywords in company_patterns.items():
            if other_company == company_name:
                continue
                
            mask = counterparty_series.str.contains('|'.join(keywords), na=False, regex=True)
            if mask.any():
                results['company_to_company'].extend(_df_to_results(df[mask], company_name, other_company, '公司→公司'))
    
    logger.info(f'  发现 {len(results["company_to_company"])} 笔涉案公司间交易')
    
    return results


def analyze_fund_penetration(
    personal_data: Dict[str, pd.DataFrame],
    company_data: Dict[str, pd.DataFrame],
    core_persons: List[str],
    companies: List[str]
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
    logger.info('='*60)
    logger.info('开始资金穿透分析（增强版 v2.0 - 图论深度分析）')
    logger.info('='*60)
    
    results = {
        'person_to_company': [],
        'company_to_person': [],
        'person_to_person': [],
        'company_to_company': [],
        'fund_cycles': [],
        'pass_through_channels': [],
        'hub_nodes': [],
        'multi_hop_paths': [],
        'graph_stats': {},
        'summary': {}
    }
    
    # ===== 阶段0: 构建资金图 =====
    logger.info('【阶段0】构建资金图...')
    money_graph = build_money_graph(personal_data, company_data, core_persons, companies)
    
    # ===== 阶段0.1-0.4: 图论深度分析 =====
    graph_results = _analyze_graph_deep_analysis(money_graph, core_persons, companies)
    results.update(graph_results)
    
    # ===== 原有逻辑: 直接往来检测 =====
    direct_results = _analyze_direct_transactions(personal_data, company_data, core_persons, companies)
    results.update(direct_results)
    
    # 生成汇总统计
    results['summary'] = _generate_summary(results)
    
    logger.info('')
    logger.info('资金穿透分析完成（增强版 v2.0）')
    logger.info('【直接往来】')
    logger.info(f'  个人→公司: {len(results["person_to_company"])} 笔')
    logger.info(f'  公司→个人: {len(results["company_to_person"])} 笔')
    logger.info(f'  个人→个人: {len(results["person_to_person"])} 笔')
    logger.info(f'  公司→公司: {len(results["company_to_company"])} 笔')
    logger.info('【图论深度分析】')
    logger.info(f'  资金闭环: {len(results["fund_cycles"])} 个')
    logger.info(f'  过账通道: {len(results["pass_through_channels"])} 个')
    logger.info(f'  资金枢纽: {len(results["hub_nodes"])} 个')
    logger.info(f'  多跳路径: {len(results["multi_hop_paths"])} 条')
    
    return results


def _extract_company_keywords(company_name: str) -> List[str]:
    """提取公司名关键词用于模糊匹配"""
    keywords = [company_name]
    
    # 移除常见后缀
    suffixes = ['有限公司', '股份有限公司', '有限责任公司', '科技', '技术']
    name = company_name
    for suffix in suffixes:
        name = name.replace(suffix, '')
    
    if name and len(name) >= 2:
        keywords.append(name)
    
    # 提取核心词汇
    if '北京' in company_name:
        core = company_name.replace('北京', '').replace('有限公司', '').replace('科技', '')
        if core and len(core) >= 2:
            keywords.append(core)
    if '贵州' in company_name:
        core = company_name.replace('贵州', '').replace('有限公司', '').replace('科技', '')
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
        '个人→公司笔数': len(results['person_to_company']),
        '个人→公司总金额': 0,
        '公司→个人笔数': len(results['company_to_person']),
        '公司→个人总金额': 0,
        '核心人员间笔数': len(results['person_to_person']),
        '核心人员间总金额': 0,
        '涉案公司间笔数': len(results['company_to_company']),
        '涉案公司间总金额': 0,
    }
    
    for item in results['person_to_company']:
        summary['个人→公司总金额'] += item['收入'] + item['支出']
    
    for item in results['company_to_person']:
        summary['公司→个人总金额'] += item['收入'] + item['支出']
        
    for item in results['person_to_person']:
        summary['核心人员间总金额'] += item['收入'] + item['支出']
        
    for item in results['company_to_company']:
        summary['涉案公司间总金额'] += item['收入'] + item['支出']
    
    return summary


def _write_penetration_summary(f, summary: Dict) -> None:
    """写入汇总统计部分"""
    f.write('一、汇总统计\n')
    f.write('-'*40 + '\n')
    f.write(f'个人→涉案公司: {summary["个人→公司笔数"]} 笔, 金额 {summary["个人→公司总金额"]/10000:.2f} 万元\n')
    f.write(f'涉案公司→个人: {summary["公司→个人笔数"]} 笔, 金额 {summary["公司→个人总金额"]/10000:.2f} 万元\n')
    f.write(f'核心人员之间: {summary["核心人员间笔数"]} 笔, 金额 {summary["核心人员间总金额"]/10000:.2f} 万元\n')
    f.write(f'涉案公司之间: {summary["涉案公司间笔数"]} 笔, 金额 {summary["涉案公司间总金额"]/10000:.2f} 万元\n\n')


def _write_transaction_details(f, items: List[Dict], title: str) -> None:
    """写入交易明细部分"""
    f.write(f'{title}\n')
    f.write('-'*40 + '\n')
    for i, item in enumerate(items[:20], 1):
        date_str = item['日期'].strftime('%Y-%m-%d') if hasattr(item['日期'], 'strftime') else str(item['日期'])[:10]
        amount = item['收入'] if item['收入'] > 0 else item['支出']
        direction = '收入' if item['收入'] > 0 else '支出'
        desc = utils.safe_str(item['摘要'], default='转账')[:20]
        f.write(f'{i}. [{date_str}] {item["发起方"]} → {item["接收方"]}: {utils.format_currency(amount)}({direction}), 摘要:{desc}\n')
    if len(items) > 20:
        f.write(f'... 共 {len(items)} 笔，仅显示前20笔\n')
    f.write('\n')


def _write_fund_cycles_section(f, cycles: List[List[str]]) -> None:
    """写入资金闭环部分"""
    f.write('六、资金闭环（利益回流铁证）\n')
    f.write('-'*40 + '\n')
    f.write('★ 资金闭环说明资金最终回流到起点，是典型的洗钱或利益输送结构\n\n')
    for i, cycle in enumerate(cycles[:10], 1):
        f.write(f'{i}. {" → ".join(cycle)}\n')
    if len(cycles) > 10:
        f.write(f'... 共 {len(cycles)} 个闭环\n')
    f.write('\n')


def _write_pass_through_channels_section(f, channels: List[Dict]) -> None:
    """写入过账通道部分"""
    f.write('七、过账通道（疑似空壳/马甲账户）\n')
    f.write('-'*40 + '\n')
    f.write('★ 进出金额高度平衡（收多少立刻转走多少），常见于空壳公司\n\n')
    for i, ch in enumerate(channels[:10], 1):
        f.write(f'{i}. 【{ch["risk_level"].upper()}】{ch["node"]}\n')
        f.write(f'   进账: {ch["inflow"]/10000:.2f}万 | 出账: {ch["outflow"]/10000:.2f}万 | 进出比: {ch["ratio"]*100:.1f}%\n')
    if len(channels) > 10:
        f.write(f'... 共 {len(channels)} 个\n')
    f.write('\n')


def _write_hub_nodes_section(f, hubs: List[Dict]) -> None:
    """写入资金枢纽节点部分"""
    f.write('八、资金枢纽节点（关键控制人/中转站）\n')
    f.write('-'*40 + '\n')
    f.write('★ 与多方有资金往来的关键节点\n\n')
    for i, hub in enumerate(hubs[:10], 1):
        f.write(f'{i}. {hub["node"]} ({hub["node_type"]})\n')
        f.write(f'   入度: {hub["in_degree"]} | 出度: {hub["out_degree"]} | 总连接: {hub["total_degree"]}\n')
    if len(hubs) > 10:
        f.write(f'... 共 {len(hubs)} 个\n')
    f.write('\n')


def _write_multi_hop_paths_section(f, paths: List[Dict]) -> None:
    """写入多跳资金路径部分"""
    f.write('九、多跳资金路径（复杂利益输送链路）\n')
    f.write('-'*40 + '\n')
    f.write('★ 2跳以上的资金链路，可能通过中间人/空壳公司中转\n\n')
    for i, path in enumerate(paths[:15], 1):
        f.write(f'{i}. [{path["hops"]}跳] {path["path_str"]}\n')
    if len(paths) > 15:
        f.write(f'... 共 {len(paths)} 条路径\n')
    f.write('\n')


def _write_graph_stats_section(f, stats: Dict) -> None:
    """写入资金图统计部分"""
    f.write('十、资金图统计\n')
    f.write('-'*40 + '\n')
    f.write(f'总节点数: {stats.get("total_nodes", 0)}\n')
    f.write(f'总边数: {stats.get("total_edges", 0)}\n')
    f.write(f'人员节点: {stats.get("person_nodes", 0)}\n')
    f.write(f'公司节点: {stats.get("company_nodes", 0)}\n')


def generate_penetration_report(results: Dict, output_dir: str) -> str:
    """
    生成资金穿透分析报告
    
    Args:
        results: 分析结果
        output_dir: 输出目录
        
    Returns:
        报告文件路径
    """
    report_path = os.path.join(output_dir, '资金穿透分析报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('资金穿透分析报告\n')
        f.write('='*60 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        
        # 汇总统计
        _write_penetration_summary(f, results['summary'])
        
        # 详细明细
        if results['person_to_company']:
            _write_transaction_details(f, results['person_to_company'], '二、个人→涉案公司明细')
        
        if results['company_to_person']:
            _write_transaction_details(f, results['company_to_person'], '三、涉案公司→个人明细')
            
        if results['person_to_person']:
            _write_transaction_details(f, results['person_to_person'], '四、核心人员之间明细')
            
        if results['company_to_company']:
            _write_transaction_details(f, results['company_to_company'], '五、涉案公司之间明细')
        
        # ===== 新增: 图论深度分析结果 =====
        f.write('\n')
        f.write('='*60 + '\n')
        f.write('★★★ 图论深度分析结果 ★★★\n')
        f.write('='*60 + '\n\n')
        
        # 资金闭环
        if results.get('fund_cycles'):
            _write_fund_cycles_section(f, results['fund_cycles'])
        
        # 过账通道
        if results.get('pass_through_channels'):
            _write_pass_through_channels_section(f, results['pass_through_channels'])
        
        # 资金枢纽
        if results.get('hub_nodes'):
            _write_hub_nodes_section(f, results['hub_nodes'])
        
        # 多跳路径
        if results.get('multi_hop_paths'):
            _write_multi_hop_paths_section(f, results['multi_hop_paths'])
        
        # 图统计
        if results.get('graph_stats'):
            _write_graph_stats_section(f, results['graph_stats'])
    
    logger.info(f'资金穿透报告已生成: {report_path}')
    return report_path
