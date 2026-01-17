#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金流向可视化模块 (重构版)
生成Mermaid格式和HTML格式的资金流向图
让审计人员更直观地看到资金流向

重构说明 (2026-01-09):
- 将HTML模板提取到外部文件 templates/flow_visualization.html
- 添加 _prepare_graph_data 函数分离数据准备逻辑
- 代码更清晰，模板修改更方便
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Tuple
from collections import defaultdict
import pandas as pd
import config
import utils

logger = utils.setup_logger(__name__)


def generate_flow_visualizations(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    loan_results: Dict,
    income_results: Dict,
    output_dir: str
) -> Dict[str, str]:
    """
    生成资金流向可视化文件
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        loan_results: 借贷分析结果
        income_results: 异常收入分析结果
        output_dir: 输出目录
    
    Returns:
        生成的文件路径字典
    """
    logger.info('='*60)
    logger.info('开始生成资金流向可视化')
    logger.info('='*60)
    
    output_files = {}
    
    # 1. 生成Mermaid格式的资金流向图
    logger.info('【阶段1】生成Mermaid资金流向图')
    mermaid_path = _generate_mermaid_flow(
        all_transactions, core_persons, loan_results, income_results, output_dir
    )
    output_files['mermaid'] = mermaid_path
    
    # 2. 生成HTML交互式图表
    logger.info('【阶段2】生成HTML交互式图表')
    html_path = _generate_html_visualization(
        all_transactions, core_persons, loan_results, income_results, output_dir
    )
    output_files['html'] = html_path
    
    logger.info('')
    logger.info(f'可视化生成完成:')
    for k, v in output_files.items():
        logger.info(f'  {k}: {v}')
    
    return output_files


def _generate_mermaid_flow(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    loan_results: Dict,
    income_results: Dict,
    output_dir: str
) -> str:
    """生成Mermaid格式的资金流向图"""
    
    report_path = os.path.join(output_dir, '资金流向图.md')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('# 资金流向可视化报告\n\n')
        f.write(f'**生成时间**: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        f.write('> 本报告使用Mermaid格式生成，可在支持Mermaid的Markdown预览器中查看\n\n')
        
        # ===== 1. 核心人员资金网络 =====
        f.write('## 一、核心人员资金网络\n\n')
        f.write('展示核心人员之间以及与主要对手方的资金往来关系\n\n')
        
        f.write('```mermaid\n')
        f.write('graph LR\n')
        f.write('    %% 核心人员资金流向图\n')
        
        # 统计每个核心人员的主要资金往来
        flow_stats = _calculate_flow_stats(all_transactions, core_persons)
        
        # 定义节点样式
        f.write('    \n')
        f.write('    %% 节点样式定义\n')
        for person in core_persons:
            safe_id = _safe_node_id(person)
            f.write(f'    {safe_id}["{person}"]\n')
            f.write(f'    style {safe_id} fill:#ff6b6b,stroke:#333,stroke-width:2px,color:#fff\n')
        
        # 添加资金流向边
        f.write('    \n')
        f.write('    %% 资金流向\n')
        edge_count = 0
        for (from_node, to_node), stats in sorted(flow_stats.items(), key=lambda x: -x[1]['total']):
            if edge_count >= 20:  # 限制边数
                break
            
            from_id = _safe_node_id(from_node)
            to_id = _safe_node_id(to_node)
            amount = stats['total']
            count = stats['count']
            
            if amount >= config.DISPLAY_AMOUNT_THRESHOLD:  # 只显示大于阈值的
                amount_str = f"{amount/config.UNIT_WAN:.1f}万" if amount >= config.UNIT_WAN else f"{amount:.0f}元"
                f.write(f'    {from_id} -->|"{amount_str} ({count}笔)"| {to_id}\n')
                edge_count += 1
        
        f.write('```\n\n')
        
        # ===== 2. 借贷关系图 =====
        if loan_results.get('loan_pairs') or loan_results.get('bidirectional_flows'):
            f.write('## 二、借贷关系图\n\n')
            f.write('展示借贷配对和双向资金往来关系\n\n')
            
            f.write('```mermaid\n')
            f.write('graph TB\n')
            f.write('    %% 借贷关系图\n')
            
            # 双向往来
            for i, flow in enumerate(loan_results.get('bidirectional_flows', [])[:10]):
                person = flow['person']
                cp = flow['counterparty']
                income = flow['income_total']
                expense = flow['expense_total']
                
                person_id = _safe_node_id(person)
                cp_id = _safe_node_id(cp)
                
                income_str = f"{income/10000:.1f}万" if income >= 10000 else f"{income:.0f}"
                expense_str = f"{expense/10000:.1f}万" if expense >= 10000 else f"{expense:.0f}"
                
                f.write(f'    {cp_id}["🔄 {cp}"] -->|"收入{income_str}"| {person_id}["{person}"]\n')
                f.write(f'    {person_id} -->|"支出{expense_str}"| {cp_id}\n')
            
            # 借贷配对
            for i, pair in enumerate(loan_results.get('loan_pairs', [])[:5]):
                person = pair['person']
                cp = pair['counterparty']
                loan_amt = pair['loan_amount']
                repay_amt = pair['repay_amount']
                
                person_id = _safe_node_id(person)
                cp_id = _safe_node_id(f"借_{cp}")
                
                loan_str = f"{loan_amt/10000:.1f}万"
                repay_str = f"{repay_amt/10000:.1f}万"
                
                f.write(f'    {cp_id}["💰 {cp}"] -->|"借入{loan_str}"| {person_id}["{person}"]\n')
                f.write(f'    {person_id} -->|"还款{repay_str}"| {cp_id}\n')
            
            f.write('```\n\n')
        
        # ===== 3. 无还款借贷（疑似利益输送）=====
        if loan_results.get('no_repayment_loans'):
            f.write('## 三、无还款借贷（疑似利益输送）\n\n')
            f.write('> ⚠️ 以下收入长期无对应还款，需重点核查\n\n')
            
            f.write('```mermaid\n')
            f.write('graph LR\n')
            f.write('    %% 无还款借贷\n')
            
            for i, loan in enumerate(loan_results['no_repayment_loans'][:10]):
                person = loan['person']
                cp = loan['counterparty']
                amount = loan['income_amount']
                days = loan['days_since']
                
                person_id = _safe_node_id(person)
                cp_id = _safe_node_id(f"无还_{cp}_{i}")
                
                amount_str = f"{amount/10000:.1f}万"
                
                f.write(f'    {cp_id}["⚠️ {cp}"] -->|"{amount_str} ({days}天未还)"| {person_id}["{person}"]\n')
                f.write(f'    style {cp_id} fill:#ff9800,stroke:#333,stroke-width:2px\n')
            
            f.write('```\n\n')
        
        # ===== 4. 异常收入来源 =====
        if income_results.get('high_risk'):
            f.write('## 四、高风险异常收入\n\n')
            f.write('> 🔴 以下收入来源存在较高风险\n\n')
            
            f.write('```mermaid\n')
            f.write('graph LR\n')
            f.write('    %% 高风险异常收入\n')
            
            for i, item in enumerate(income_results['high_risk'][:15]):
                person = item['person']
                cp = item['counterparty']
                amount = item['amount']
                
                person_id = _safe_node_id(person)
                cp_id = _safe_node_id(f"风险_{cp}_{i}")
                
                amount_str = f"{amount/10000:.1f}万" if amount >= 10000 else f"{amount:.0f}元"
                
                f.write(f'    {cp_id}["🔴 {cp[:10]}"] -->|"{amount_str}"| {person_id}["{person}"]\n')
            
            f.write('```\n\n')
        
        # ===== 5. 网贷平台使用情况 =====
        if loan_results.get('online_loans'):
            f.write('## 五、网贷平台使用情况\n\n')
            
            # 按平台分组统计
            platform_stats = defaultdict(lambda: {'count': 0, 'total': 0})
            for loan in loan_results['online_loans']:
                platform = loan.get('platform', '其他')
                platform_stats[platform]['count'] += 1
                platform_stats[platform]['total'] += loan.get('amount', 0)
            
            f.write('| 平台 | 笔数 | 金额 |\n')
            f.write('|------|------|------|\n')
            for platform, stats in sorted(platform_stats.items(), key=lambda x: -x[1]['total']):
                amount_str = f"¥{stats['total']/10000:.2f}万" if stats['total'] >= 10000 else f"¥{stats['total']:.0f}"
                f.write(f"| {platform} | {stats['count']} | {amount_str} |\n")
            f.write('\n')
        
        # ===== 6. 图例说明 =====
        f.write('---\n\n')
        f.write('## 图例说明\n\n')
        f.write('| 符号 | 含义 |\n')
        f.write('|------|------|\n')
        f.write('| 🔴 | 高风险项目 |\n')
        f.write('| ⚠️ | 警告/需关注 |\n')
        f.write('| 🔄 | 双向往来 |\n')
        f.write('| 💰 | 借贷关系 |\n')
        f.write('| 红色节点 | 核心人员 |\n')
        f.write('| 橙色节点 | 可疑对手方 |\n')
        f.write('\n')
    
    logger.info(f'  Mermaid资金流向图已生成: {report_path}')
    return report_path


def _generate_html_visualization(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    loan_results: Dict,
    income_results: Dict,
    output_dir: str
) -> str:
    """
    生成HTML交互式可视化（重构版）
    使用外部模板文件，逻辑与样式分离
    """
    from template_engine import render_template
    
    html_path = os.path.join(output_dir, '资金流向可视化.html')
    
    # 计算资金流向统计
    flow_stats = _calculate_flow_stats(all_transactions, core_persons)
    
    # 获取涉案公司列表
    involved_companies = []
    for key in all_transactions.keys():
        base_name = os.path.basename(key).replace('_合并流水', '').replace('.xlsx', '')
        if '公司' in base_name or '有限' in base_name:
            involved_companies.append(base_name)
    
    # 准备节点和边的数据
    nodes, edges, edge_stats = _prepare_graph_data(
        flow_stats, core_persons, involved_companies
    )
    
    # 准备节点JSON
    nodes_json = json.dumps([
        {
            'id': n['id'],
            'label': n['label'],
            'group': n['group'],
            'size': n['size'],
            'font': {'color': '#fff', 'size': 14}
        } for n in nodes
    ], ensure_ascii=False)
    
    # 准备边JSON
    edges_json = json.dumps([
        {
            'from': e['from'],
            'to': e['to'],
            'value': e['value'],
            'title': e['title'],
            'arrows': 'to',
            'color': {'color': '#00d2ff', 'opacity': 0.8},
            'smooth': {'type': 'curvedCW', 'roundness': 0.2}
        } for e in edges
    ], ensure_ascii=False)
    
    # 读取本地 vis-network.min.js（用于内联到 HTML，实现离线渲染）
    vis_js_paths = [
        os.path.join(os.path.dirname(__file__), 'dashboard/node_modules/vis-network/standalone/umd/vis-network.min.js'),
        os.path.join(os.path.dirname(__file__), 'node_modules/vis-network/standalone/umd/vis-network.min.js'),
    ]
    vis_js_content = ''
    for vis_js_path in vis_js_paths:
        if os.path.exists(vis_js_path):
            try:
                with open(vis_js_path, 'r', encoding='utf-8') as f:
                    vis_js_content = f.read()
                logger.info(f'已加载本地 vis-network: {vis_js_path}')
                break
            except Exception as e:
                logger.warning(f'读取 vis-network 失败: {e}')
    
    if not vis_js_content:
        logger.warning('未找到本地 vis-network，模板将使用空 JS（离线可能无法渲染）')
    
    # 渲染模板
    try:
        html_content = render_template('flow_visualization.html', {
            'GENERATE_TIME': datetime.now().strftime("%Y年%m月%d日 %H:%M:%S"),
            'NODE_COUNT': len(nodes),
            'EDGE_COUNT': len(edges),
            'CORE_PERSON_COUNT': len(core_persons),
            'CORE_PERSON_NAMES': ', '.join(core_persons),
            'HIGH_RISK_COUNT': len(income_results.get('high_risk', [])),
            'MEDIUM_RISK_COUNT': len(income_results.get('medium_risk', [])),
            'LOAN_PAIR_COUNT': len(loan_results.get('loan_pairs', [])),
            'NO_REPAY_COUNT': len(loan_results.get('no_repayment_loans', [])),
            'CORE_EDGE_COUNT': edge_stats['core'],
            'COMPANY_EDGE_COUNT': edge_stats['company'],
            'OTHER_EDGE_COUNT': edge_stats['other'],
            'NODES_JSON': nodes_json,
            'EDGES_JSON': edges_json,
            'VIS_JS_CONTENT': vis_js_content,  # 新增：内联 vis-network JS
        })
    except FileNotFoundError:
        # 如果模板文件不存在，使用内置简化版
        logger.warning('模板文件不存在，使用内置简化版')
        html_content = _generate_fallback_html(nodes_json, edges_json, core_persons)
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f'  HTML可视化已生成: {html_path}')
    return html_path


def _prepare_graph_data(flow_stats: Dict, core_persons: List[str], 
                        involved_companies: List[str]) -> Tuple[List, List, Dict]:
    """
    准备图形数据（节点和边）
    
    Returns:
        (nodes, edges, edge_stats)
    """
    nodes = []
    edges = []
    node_set = set()
    
    # 噪音过滤关键词
    NOISE_KEYWORDS = [
        '理财', '基金', '资产管理', '增利', '存管', '清算', '头寸', '备付',
        '代销', '保证金', '划转', '过渡', '暂挂', '待处理', '结息',
        'EB', '专户', '款项', '内部', '碧乐活', '瑞赢', '睿赢'
    ]
    
    def is_noise_node(name):
        return any(kw in name for kw in NOISE_KEYWORDS)
    
    # 1. 添加核心人员节点
    for person in core_persons:
        nodes.append({
            'id': person,
            'label': person,
            'group': 'core',
            'size': 35
        })
        node_set.add(person)
    
    # 2. 添加涉案公司节点
    for company in involved_companies:
        if company not in node_set:
            display_name = company[:8] + '...' if len(company) > 10 else company
            nodes.append({
                'id': company,
                'label': f'🏢 {display_name}',
                'group': 'involved_company',
                'size': 40
            })
            node_set.add(company)
    
    # 3. 筛选并分类边
    all_sorted_flows = sorted(flow_stats.items(), key=lambda x: -x[1]['total'])
    
    edge_data = []
    for (u, v), stats in all_sorted_flows:
        if is_noise_node(u) or is_noise_node(v):
            continue
            
        # Determine node types
        u_core = u in core_persons
        v_core = v in core_persons
        u_company = u in involved_companies
        v_company = v in involved_companies
        
        # Check if it is an interaction between core entities (Person-Person, Person-Company, Company-Company)
        is_core_interaction = (u_core or u_company) and (v_core or v_company)
        
        # Only filter by threshold if it is NOT a core interaction
        # This ensures all connections between key entities are shown regardless of amount
        if not is_core_interaction:
            if stats['total'] < config.DISPLAY_AMOUNT_THRESHOLD:
                continue
        
        if u_core and v_core:
            edge_type = 'core'
        elif u_company and v_company:
            edge_type = 'company_inner'
        elif u_company or v_company:
            edge_type = 'company'
        else:
            edge_type = 'other'
        
        edge_data.append(((u, v), stats, edge_type))
    
    # 4. 限制边数量
    # 核心人员间、涉案公司间的交易全部保留
    core_edges = [e for e in edge_data if e[2] == 'core']
    company_inner_edges = [e for e in edge_data if e[2] == 'company_inner']
    
    # 其他交易按金额排名限制数量
    company_edges = [e for e in edge_data if e[2] == 'company'][:30]
    other_edges = [e for e in edge_data if e[2] == 'other'][:30]
    
    final_edges = core_edges + company_inner_edges + company_edges + other_edges
    
    # 统计
    edge_stats = {
        'core': len(core_edges),
        'company': len(company_inner_edges) + len(company_edges),
        'other': len(other_edges)
    }
    
    # 5. 添加边和新节点
    for (from_node, to_node), stats, edge_type in final_edges:
        for node in [from_node, to_node]:
            if node not in node_set:
                is_company = '公司' in node or '有限' in node
                label = node[:6] + '...' if len(node) > 8 else node
                group = 'company' if is_company else 'other'
                size = 25 if is_company else 18
                
                nodes.append({
                    'id': node,
                    'label': label,
                    'group': group,
                    'size': size
                })
                node_set.add(node)
        
        amount_wan = stats['total'] / 10000
        edges.append({
            'from': from_node,
            'to': to_node,
            'value': amount_wan,
            'title': f"{from_node} → {to_node}\\n金额: {amount_wan:.1f}万元 ({stats['count']}笔)"
        })
    
    return nodes, edges, edge_stats


def _generate_fallback_html(nodes_json: str, edges_json: str, 
                            core_persons: List[str]) -> str:
    """生成备用HTML（当模板文件不存在时使用）- 使用本地 vis-network，支持离线"""
    # 尝试读取本地 vis-network.min.js
    vis_js_paths = [
        os.path.join(os.path.dirname(__file__), 'dashboard/node_modules/vis-network/standalone/umd/vis-network.min.js'),
        os.path.join(os.path.dirname(__file__), 'node_modules/vis-network/standalone/umd/vis-network.min.js'),
    ]
    
    vis_js_content = None
    for vis_js_path in vis_js_paths:
        if os.path.exists(vis_js_path):
            try:
                with open(vis_js_path, 'r', encoding='utf-8') as f:
                    vis_js_content = f.read()
                logger.info(f'已加载本地 vis-network: {vis_js_path}')
                break
            except Exception as e:
                logger.warning(f'读取 vis-network 失败: {e}')
    
    if not vis_js_content:
        logger.error('无法找到本地 vis-network.min.js，图谱将无法渲染')
        return '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>资金流向 - 错误</title>
<style>body{font-family:Microsoft YaHei;background:#1a1a2e;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
.error{text-align:center;}.error h1{color:#ff6b6b;}.error p{color:#888;}</style>
</head><body>
<div class="error">
<h1>⚠️ 图谱渲染失败</h1>
<p>未找到 vis-network 库文件，请确保已安装前端依赖：</p>
<code style="color:#00d2ff;">cd dashboard && npm install</code>
</div>
</body></html>'''
    
    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>资金流向</title>
<script>{vis_js_content}</script>
<style>body{{margin:0;padding:0;background:#1a1a2e;}}#network{{width:100vw;height:100vh;}}</style>
</head><body>
<div id="network"></div>
<script>
var nodes = new vis.DataSet({nodes_json});
var edges = new vis.DataSet({edges_json});
var network = new vis.Network(document.getElementById('network'), 
    {{nodes:nodes,edges:edges}}, {{physics:{{stabilization:{{iterations:200}}}}}});
</script>
</body></html>'''


def _calculate_flow_stats(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """计算资金流向统计（支持中英文列名）"""
    
    flow_stats = defaultdict(lambda: {'count': 0, 'total': 0})
    
    # 列名映射（支持中英文）
    COLUMN_MAP = {
        'counterparty': ['counterparty', '交易对手', '对手方', '对方户名'],
        'income': ['income', '收入(元)', '收入', '贷方金额'],
        'expense': ['expense', '支出(元)', '支出', '借方金额']
    }
    
    def get_column_value(row, columns_list):
        """获取列值，支持多种列名"""
        for col_name in columns_list:
            if col_name in row.index:
                return row.get(col_name, '')
        return ''
    
    def has_column(df, columns_list):
        """检查是否存在某类列（使用集合操作优化性能）"""
        return not set(columns_list).isdisjoint(df.columns)
    
    # 遍历所有实体的交易数据
    for entity_name, df in all_transactions.items():
        if df.empty:
            continue
        
        # 检查是否有对手方列
        if not has_column(df, COLUMN_MAP['counterparty']):
            logger.debug(f'跳过 {entity_name}: 无对手方列')
            continue
        
        # 规范化源节点名称
        base_name = os.path.basename(entity_name)
        source_node = base_name.replace('_合并流水', '').replace('.xlsx', '')
        
        for _, row in df.iterrows():
            # 获取对手方
            counterparty = str(get_column_value(row, COLUMN_MAP['counterparty']))
            if not counterparty or counterparty == 'nan':
                continue
            
            # 获取金额
            income = 0
            expense = 0
            
            income_val = get_column_value(row, COLUMN_MAP['income'])
            if income_val and str(income_val) != 'nan':
                try:
                    income = float(income_val)
                except (ValueError, TypeError):
                    income = 0
            
            expense_val = get_column_value(row, COLUMN_MAP['expense'])
            if expense_val and str(expense_val) != 'nan':
                try:
                    expense = float(expense_val)
                except (ValueError, TypeError):
                    expense = 0
            
            # 记录资金流向
            if income > 0:
                # 收入：对手方 -> 本人
                flow_stats[(counterparty, source_node)]['count'] += 1
                flow_stats[(counterparty, source_node)]['total'] += income
            
            if expense > 0:
                # 支出：本人 -> 对手方
                flow_stats[(source_node, counterparty)]['count'] += 1
                flow_stats[(source_node, counterparty)]['total'] += expense
    
    return dict(flow_stats)


def _safe_node_id(name: str) -> str:
    """生成安全的Mermaid节点ID"""
    # 移除特殊字符，只保留字母、数字、中文
    import re
    safe_id = re.sub(r'[^\w\u4e00-\u9fa5]', '_', str(name))
    # 确保不以数字开头
    if safe_id and safe_id[0].isdigit():
        safe_id = 'N_' + safe_id
    return safe_id or 'unknown'
