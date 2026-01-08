#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金流向可视化模块
生成Mermaid格式和HTML格式的资金流向图
让审计人员更直观地看到资金流向
"""

import os
from datetime import datetime
from typing import Dict, List
from collections import defaultdict
import pandas as pd
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
            
            if amount >= 10000:  # 只显示大于1万的
                amount_str = f"{amount/10000:.1f}万" if amount >= 10000 else f"{amount:.0f}元"
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
                rate = pair.get('annual_rate', 0)
                
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
                inc_type = item['type']
                
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
    """生成HTML交互式可视化"""
    
    html_path = os.path.join(output_dir, '资金流向可视化.html')
    
    # 计算资金流向统计
    flow_stats = _calculate_flow_stats(all_transactions, core_persons)
    
    # 获取涉案公司列表（从main.py传入，这里通过loan_results获取）
    involved_companies = []
    for key in all_transactions.keys():
        base_name = os.path.basename(key).replace('_合并流水', '').replace('.xlsx', '')
        if '公司' in base_name or '有限' in base_name:
            involved_companies.append(base_name)
    
    # 准备节点和边的数据
    nodes = []
    edges = []
    node_set = set()
    
    # === 1. 添加核心人员节点（红色大节点）===
    for person in core_persons:
        nodes.append({
            'id': person,
            'label': person,
            'group': 'core',
            'size': 35,
            'font': {'size': 16, 'color': '#ffffff'}
        })
        node_set.add(person)
    
    # === 2. 添加涉案公司节点（橙色方形大节点 - 突出显示）===
    for company in involved_companies:
        if company not in node_set:
            # 公司名称截取显示
            display_name = company[:8] + '...' if len(company) > 10 else company
            nodes.append({
                'id': company,
                'label': f'🏢 {display_name}',  # 添加建筑物图标
                'group': 'involved_company',     # 使用专门的涉案公司组
                'size': 40,                      # 更大尺寸
                'shape': 'box',                  # 方形
                'font': {'size': 14, 'color': '#ffffff', 'bold': True},
                'borderWidth': 3,
                'shadow': True
            })
            node_set.add(company)
    
    # === 噪音过滤列表 ===
    NOISE_KEYWORDS = [
        '理财', '基金', '资产管理', '增利', '存管', '清算', '头寸', '备付',
        '代销', '保证金', '划转', '过渡', '暂挂', '待处理', '结息',
        'EB', '专户', '款项', '内部', '碧乐活', '瑞赢', '睿赢'
    ]
    
    def is_noise_node(name):
        """判断是否为噪音节点（理财产品、银行内部账户等）"""
        for kw in NOISE_KEYWORDS:
            if kw in name:
                return True
        return False
    
    # === 3. 筛选边：分层策略 ===
    all_sorted_flows = sorted(flow_stats.items(), key=lambda x: -x[1]['total'])
    
    # 3.1 核心人员之间的交易（最重要，全部保留）
    core_to_core_edges = []
    for (u, v), stats in all_sorted_flows:
        if u in core_persons and v in core_persons:
            core_to_core_edges.append(((u, v), stats))
    
    # 3.2 核心人员与涉案公司的交易（重要）
    core_to_company_edges = []
    for (u, v), stats in all_sorted_flows:
        u_is_core = u in core_persons
        v_is_core = v in core_persons
        u_is_company = u in involved_companies
        v_is_company = v in involved_companies
        
        if (u_is_core and v_is_company) or (u_is_company and v_is_core):
            core_to_company_edges.append(((u, v), stats))
    
    # 3.3 核心人员与外部个人/机构的交易（过滤噪音，保留大额）
    core_to_other_edges = []
    for (u, v), stats in all_sorted_flows:
        u_is_core = u in core_persons
        v_is_core = v in core_persons
        
        # 只要一方是核心人员，另一方不是
        if (u_is_core or v_is_core) and not (u_is_core and v_is_core):
            other_party = v if u_is_core else u
            # 跳过涉案公司（已在上面处理）
            if other_party in involved_companies:
                continue
            # 跳过噪音节点
            if is_noise_node(other_party):
                continue
            # 金额阈值：5万以上
            if stats['total'] >= 50000:
                core_to_other_edges.append(((u, v), stats))
    
    # 3.4 涉案公司之间的交易
    company_to_company_edges = []
    for (u, v), stats in all_sorted_flows:
        if u in involved_companies and v in involved_companies:
            company_to_company_edges.append(((u, v), stats))
    
    # === 4. 合并边（按优先级，控制总数）===
    final_edges_data = (
        core_to_core_edges[:20] +           # 核心人员间：最多20条
        core_to_company_edges[:20] +        # 核心-公司：最多20条
        core_to_other_edges[:30] +          # 核心-外部：最多30条（已过滤噪音）
        company_to_company_edges[:10]       # 公司间：最多10条
    )
    
    logger.info(f'  边统计: 核心间{len(core_to_core_edges)}, 核心-公司{len(core_to_company_edges)}, '
                f'核心-外部{len(core_to_other_edges)}, 公司间{len(company_to_company_edges)}')
    
    # === 5. 添加边和对手方节点 ===
    for (from_node, to_node), stats in final_edges_data:
        # 添加新节点
        for node in [from_node, to_node]:
            if node not in node_set:
                is_core = node in core_persons
                is_company = node in involved_companies or '公司' in node or '有限' in node
                
                # 节点标签截取
                label = node[:6] + '...' if len(node) > 8 else node
                
                # 确定节点类型
                if is_core:
                    group = 'core'
                    size = 30
                elif is_company:
                    group = 'company'
                    size = 25
                else:
                    group = 'other'
                    size = 18
                
                nodes.append({
                    'id': node,
                    'label': label,
                    'group': group,
                    'size': size
                })
                node_set.add(node)
        
        # 添加边（根据金额设置线条粗细）
        amount_wan = stats['total'] / 10000
        width = min(1 + amount_wan / 10, 10)  # 1-10之间
        
        edges.append({
            'from': from_node,
            'to': to_node,
            'value': amount_wan,
            'width': width,
            'title': f"{from_node} → {to_node}\\n金额: {amount_wan:.1f}万元 ({stats['count']}笔)",
            'arrows': 'to'
        })
    
    # 生成HTML
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>资金流向可视化 - 纪检审计系统</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }}
        .header {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 20px;
            text-align: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header p {{
            color: #aaa;
            font-size: 14px;
        }}
        .container {{
            display: flex;
            height: calc(100vh - 100px);
        }}
        .sidebar {{
            width: 300px;
            background: rgba(255,255,255,0.05);
            padding: 20px;
            overflow-y: auto;
        }}
        .sidebar h3 {{
            color: #00d2ff;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .stat-card h4 {{
            color: #fff;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .stat-card .value {{
            font-size: 24px;
            font-weight: bold;
            color: #00d2ff;
        }}
        .stat-card .desc {{
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }}
        .risk-high {{
            border-left: 4px solid #ff4757;
        }}
        .risk-medium {{
            border-left: 4px solid #ffa502;
        }}
        .legend {{
            margin-top: 20px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 10px;
        }}
        .network-container {{
            flex: 1;
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            margin: 10px;
        }}
        #network {{
            width: 100%;
            height: 100%;
        }}
        .tooltip {{
            position: absolute;
            background: rgba(0,0,0,0.9);
            color: #fff;
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            pointer-events: none;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>💰 资金流向可视化分析</h1>
        <p>生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")} | 共 {len(nodes)} 个节点, {len(edges)} 条资金流向</p>
    </div>
    
    <div class="container">
        <div class="sidebar">
            <h3>📊 数据概览</h3>
            
            <div class="stat-card">
                <h4>核心人员</h4>
                <div class="value">{len(core_persons)}</div>
                <div class="desc">{', '.join(core_persons)}</div>
            </div>
            
            <div class="stat-card risk-high">
                <h4>🔴 高风险项目</h4>
                <div class="value">{len(income_results.get('high_risk', []))}</div>
                <div class="desc">建议优先核查</div>
            </div>
            
            <div class="stat-card risk-medium">
                <h4>🟡 中风险项目</h4>
                <div class="value">{len(income_results.get('medium_risk', []))}</div>
                <div class="desc">需酌情关注</div>
            </div>
            
            <div class="stat-card">
                <h4>借贷配对</h4>
                <div class="value">{len(loan_results.get('loan_pairs', []))}</div>
            </div>
            
            <div class="stat-card">
                <h4>无还款借贷</h4>
                <div class="value">{len(loan_results.get('no_repayment_loans', []))}</div>
                <div class="desc">疑似利益输送</div>
            </div>
            
            <h3>🎨 图例说明</h3>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color" style="background: #ff6b6b;"></div>
                    <span>🔴 核心人员</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ff9800; border-radius: 3px;"></div>
                    <span>🏢 涉案公司（重点）</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #4ecdc4;"></div>
                    <span>🔵 其他关联方</span>
                </div>
            </div>
            
            <h3 style="margin-top: 20px;">📊 资金流向统计</h3>
            <p style="font-size: 12px; color: #888; line-height: 1.8;">
                • 核心人员间: {len(core_to_core_edges)}笔<br>
                • 公司间交易: {len(company_to_company_edges)}笔<br>
                • 核心-外部: {len(core_to_other_edges)}笔<br>
                • 线条越粗金额越大
            </p>
            
            <h3 style="margin-top: 20px;">💡 操作提示</h3>
            <p style="font-size: 12px; color: #888; line-height: 1.8;">
                • 拖拽节点可调整位置<br>
                • 滚轮缩放视图<br>
                • 悬停查看交易详情<br>
                • 导航按钮在右下角
            </p>
        </div>
        
        <div class="network-container">
            <div id="network"></div>
        </div>
    </div>
    
    <script>
        // 节点数据
        var nodes = new vis.DataSet({json.dumps([
            {
                'id': n['id'],
                'label': n['label'],
                'group': n['group'],
                'size': n['size'],
                'font': {'color': '#fff', 'size': 14}
            } for n in nodes
        ], ensure_ascii=False)});
        
        // 边数据
        var edges = new vis.DataSet({json.dumps([
            {
                'from': e['from'],
                'to': e['to'],
                'value': e['value'],
                'title': e['title'],
                'arrows': 'to',
                'color': {'color': '#00d2ff', 'opacity': 0.8},
                'smooth': {'type': 'curvedCW', 'roundness': 0.2}
            } for e in edges
        ], ensure_ascii=False)});
        
        // 网络配置
        var container = document.getElementById('network');
        var data = {{
            nodes: nodes,
            edges: edges
        }};
        var options = {{
            nodes: {{
                shape: 'dot',
                borderWidth: 2,
                shadow: true,
                font: {{
                    color: '#fff',
                    size: 14,
                    face: 'Microsoft YaHei'
                }}
            }},
            edges: {{
                width: 2,
                shadow: true,
                smooth: {{
                    type: 'curvedCW',
                    roundness: 0.2
                }}
            }},
            groups: {{
                core: {{
                    color: {{
                        background: '#ff6b6b',
                        border: '#c0392b',
                        highlight: {{
                            background: '#e74c3c',
                            border: '#c0392b'
                        }}
                    }},
                    font: {{ color: '#ffffff' }}
                }},
                company: {{
                    color: {{
                        background: '#9b59b6',
                        border: '#8e44ad',
                        highlight: {{
                            background: '#8e44ad',
                            border: '#7d3c98'
                        }}
                    }},
                    font: {{ color: '#ffffff' }},
                    shape: 'box'
                }},
                involved_company: {{
                    color: {{
                        background: '#ff9800',
                        border: '#e65100',
                        highlight: {{
                            background: '#ffa726',
                            border: '#fb8c00'
                        }}
                    }},
                    font: {{ color: '#ffffff', size: 14 }},
                    shape: 'box',
                    shadow: {{
                        enabled: true,
                        color: 'rgba(255,152,0,0.5)',
                        size: 10
                    }},
                    borderWidth: 3
                }},
                other: {{
                    color: {{
                        background: '#4ecdc4',
                        border: '#1abc9c',
                        highlight: {{
                            background: '#1abc9c',
                            border: '#16a085'
                        }}
                    }}
                }}
            }},
            physics: {{
                stabilization: {{
                    iterations: 300,
                    fit: true
                }},
                barnesHut: {{
                    gravitationalConstant: -5000,
                    springLength: 200,
                    springConstant: 0.01,
                    centralGravity: 0.3
                }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100,
                navigationButtons: true,
                keyboard: true
            }}
        }};
        
        var network = new vis.Network(container, data, options);
        
        // 点击事件
        network.on('click', function(params) {{
            if (params.nodes.length > 0) {{
                var nodeId = params.nodes[0];
                console.log('点击节点:', nodeId);
            }}
        }});
    </script>
</body>
</html>
'''
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f'  HTML可视化已生成: {html_path}')
    return html_path


def _calculate_flow_stats(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """计算资金流向统计（修复版 - 支持中英文列名）"""
    
    flow_stats = defaultdict(lambda: {'count': 0, 'total': 0})
    
    # 列名映射（支持中英文）
    COLUMN_MAP = {
        'counterparty': ['counterparty', '交易对手', '对手方', '对方户名'],
        'income': ['income', '收入(元)', '收入', '贷方金额'],
        'expense': ['expense', '支出(元)', '支出', '借方金额']
    }
    
    def get_column_value(row, standard_name, columns_list):
        """获取列值，支持多种列名"""
        for col_name in columns_list:
            if col_name in row.index:
                return row.get(col_name, '')
        return ''
    
    def has_column(df, standard_name, columns_list):
        """检查是否存在某类列"""
        for col_name in columns_list:
            if col_name in df.columns:
                return True
        return False
    
    # 遍历所有实体的交易数据（包括个人和公司）
    for entity_name, df in all_transactions.items():
        if df.empty:
            continue
        
        # 检查是否有对手方列（中英文均可）
        if not has_column(df, 'counterparty', COLUMN_MAP['counterparty']):
            logger.debug(f'跳过 {entity_name}: 无对手方列')
            continue
        
        # 1. 规范化源节点名称 (修复路径前缀导致无法匹配核心人员的问题)
        # 从完整路径中提取文件名
        base_name = os.path.basename(entity_name)
        # 去除后缀和标识
        source_node = base_name.replace('_合并流水', '').replace('.xlsx', '')
        
        for _, row in df.iterrows():
            # 获取对手方（支持中英文列名）
            cp = str(get_column_value(row, 'counterparty', COLUMN_MAP['counterparty']))
            
            # 过滤无效对手方
            if not cp or cp == 'nan' or len(cp) < 2:
                continue
            
            # 排除自己转自己
            if cp in source_node or source_node in cp:
                continue
            
            # 获取收入（支持中英文列名）
            income_val = get_column_value(row, 'income', COLUMN_MAP['income'])
            income = float(income_val) if income_val and income_val != '' else 0
            
            # 获取支出（支持中英文列名）
            expense_val = get_column_value(row, 'expense', COLUMN_MAP['expense'])
            expense = float(expense_val) if expense_val and expense_val != '' else 0
            
            # 收入：对手方 -> 当前实体
            if income > 0:
                flow_stats[(cp, source_node)]['count'] += 1
                flow_stats[(cp, source_node)]['total'] += income
            
            # 支出：当前实体 -> 对手方
            if expense > 0:
                flow_stats[(source_node, cp)]['count'] += 1
                flow_stats[(source_node, cp)]['total'] += expense
    
    logger.info(f'  资金流向统计: 共{len(flow_stats)}条边')
    return flow_stats


def _safe_node_id(name: str) -> str:
    """生成安全的Mermaid节点ID"""
    import re
    # 只保留字母、数字和中文
    safe = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', name)
    if not safe:
        safe = 'node'
    return safe[:20]  # 限制长度


import json
