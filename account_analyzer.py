#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户分析模块 - 资金穿透与关联排查系统
识别银行卡与虚拟账户，分析账户间资金流转关系
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Tuple
import utils
import config

logger = utils.setup_logger(__name__)

def classify_accounts(df: pd.DataFrame) -> Dict:
    """
    对账户进行分类
    
    Returns:
        Dict: {
            'physical_cards': [], # 实体卡
            'virtual_accounts': [], # 虚拟/内部账户
            'wealth_accounts': [], # 明确的理财账户
            'mapping': {} # 账号 -> 类型的映射
        }
    """
    if 'account_id' not in df.columns:
        # 尝试使用可能的列名
        for col in ['本方账号', '账号', '卡号']:
            if col in df.columns:
                df['account_id'] = df[col]
                break
        else:
            return {'error': 'No account column found'}

    accounts = df['account_id'].dropna().unique()
    classification = {
        'physical_cards': [],
        'virtual_accounts': [],
        'wealth_accounts': [],
        'mapping': {}
    }
    
    for acct in accounts:
        acct_str = str(acct).strip()
        account_type = 'virtual' # 默认为虚拟
        
        # 规则1: 标准银联卡/Visa/Master (位数+前缀)
        # 62/60开头, 16-19位 -> 银联借记卡
        # 4/5开头, 16位 -> 信用卡
        if re.match(r'^(62|60|4\d|5\d)\d{13,17}$', acct_str):
            account_type = 'physical'
            
        # 规则2: 交易特征增强
        # 如果是虚拟卡格式，但有POS消费、ATM取款，可能是旧式卡或特殊卡
        sub_df = df[df['account_id'] == acct]
        desc_text = ' '.join(sub_df['description'].fillna('').astype(str).tolist())
        
        if account_type == 'virtual':
            if any(k in desc_text for k in ['POS', 'ATM', '消费', '支付宝', '微信']):
                # 即使格式不像，但有消费特征，仍归类为实体卡/主账户
                account_type = 'physical'
        
        # 规则3: 理财特征
        # 如果包含强理财关键词
        if any(k in desc_text for k in ['基金', '理财', '分红', '结息']) and account_type == 'virtual':
            account_type = 'wealth'
            
        # 记录
        if account_type == 'physical':
            classification['physical_cards'].append(acct_str)
        elif account_type == 'wealth':
            classification['wealth_accounts'].append(acct_str)
        else:
            classification['virtual_accounts'].append(acct_str)
            
        classification['mapping'][acct_str] = account_type
        
    return classification

def analyze_internal_transfers(df: pd.DataFrame, account_map: Dict) -> Dict:
    """
    分析内部转账关系 (资金划转图谱)
    主账户 -> 理财账户 -> 赎回
    """
    internal_graph = []
    
    # 填充account_id列
    if 'account_id' not in df.columns and '本方账号' in df.columns:
        df['account_id'] = df['本方账号']
        
    # 需要对摘要进行清洗，提取出对方账号信息(如果存在)
    # 这里主要依靠近似的金额匹配和时间匹配，或者显式的转账记录
    
    # 方法：按时间排序，寻找同一持有人名下不同账号的"流出-流入"配对
    df_sorted = df.sort_values('date')
    
    # 窗口匹配：时间差在60秒内，金额相同，一进一出
    # 这需要两行数据
    # 为简化计算，我们遍历所有"内部转账"特征的交易
    
    # 1. 识别内部转账交易
    # 很多银行流水里，对方账号如果是自己的其他卡，会在对手方字段显示，或者摘要显示"卡卡转账"
    
    # 简化版：仅统计各账户的角色
    account_roles = {}
    for acct, atype in account_map.items():
        sub_df = df[df['account_id'] == acct]
        total_in = sub_df['income'].sum()
        total_out = sub_df['expense'].sum()
        
        # 理财特征
        wealth_keywords = ['理财', '基金', '证券', '定存']
        is_wealth_related = sub_df['description'].astype(str).apply(lambda x: any(k in x for k in wealth_keywords)).any()
        
        account_roles[acct] = {
            'type': atype,
            'total_in': total_in,
            'total_out': total_out,
            'is_wealth_related': is_wealth_related
        }
        
    return {
        'roles': account_roles,
        'graph': internal_graph
    }

def generate_account_report(df: pd.DataFrame, entity_name: str) -> str:
    """
    生成账户分析报告文本
    """
    # 1. 分类
    class_result = classify_accounts(df)
    
    # 2. 统计
    roles = analyze_internal_transfers(df, class_result['mapping'])['roles']
    
    report = f"\n【{entity_name} 账户架构深度分析】\n"
    report += "-"*60 + "\n"
    
    # 实体卡
    phy_cards = class_result['physical_cards']
    report += f"1. 实体主力账户 (共{len(phy_cards)}张)\n"
    report += "   (推测为实际持有的银行卡，用于日常收支)\n"
    for card in phy_cards:
        stats = roles.get(card, {})
        report += f"   - 卡号: {card}\n"
        report += f"     收: {utils.format_currency(stats.get('total_in',0))} | 支: {utils.format_currency(stats.get('total_out',0))}\n"
    
    # 理财/虚拟账户
    virt_accts = class_result['virtual_accounts'] + class_result['wealth_accounts']
    report += f"\n2. 内部/理财子账户 (共{len(virt_accts)}个)\n"
    report += "   (推测为银行系统生成的定期/理财/基金专属账号，非实体卡)\n"
    
    # 聚合统计
    wealth_in = sum(roles[a]['total_in'] for a in virt_accts if a in roles)
    wealth_out = sum(roles[a]['total_out'] for a in virt_accts if a in roles)
    
    report += f"   子账户沉淀资金池: {utils.format_currency(wealth_in)} (流入) / {utils.format_currency(wealth_out)} (流出)\n"
    
    # 列出几个典型的活跃子账户
    active_subs = sorted(virt_accts, key=lambda x: roles.get(x, {}).get('total_in', 0), reverse=True)[:5]
    if active_subs:
        report += "   主要活跃子账户:\n"
        for acct in active_subs:
            stats = roles.get(acct, {})
            tag = " [理财相关]" if stats.get('is_wealth_related') else ""
            report += f"   - {acct}{tag}: 流转 {utils.format_currency(stats.get('total_in',0))}\n"

    return report
