#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
有效消费计算器 - 重新定义版

修复：
1. 严格定义"有效消费"为日常消费（<10万）
2. 排除所有大额支出（资产购置、大额转账、大额理财）
3. 排除投资、还款等非消费支出
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class StrictExpenseThresholds:
    """严格消费阈值配置"""
    daily_expense_max = 100000  # 日常消费最大金额（10万元）
    asset_purchase_keywords = ['购车', '买房', '房产', '不动产', '装修', '家电']
    investment_keywords = ['理财', '基金', '证券', '大额存单', 'FSG', 'FSA', 'FBAE']


class StrictExpenseCalculator:
    """
    严格有效消费计算器
    
    核心功能：
    1. 只保留"真正的日常消费"（<10万）
    2. 排除所有大额支出（资产购置、大额转账、大额理财）
    3. 排除投资、还款等非消费支出
    """
    
    def __init__(self, thresholds: Optional[StrictExpenseThresholds] = None):
        """初始化计算器"""
        self.thresholds = thresholds or StrictExpenseThresholds()
    
    def calculate(self, 
                  transactions: pd.DataFrame,
                  family_members: List[str],
                  person_name: str) -> Dict[str, Any]:
        """
        计算严格的有效消费（只包括日常消费）
        """
        
        # 只分析支出交易
        expense_df = transactions[transactions['direction'] == 'expense'].copy()
        
        if expense_df.empty:
            return {
                'total_expense': 0,
                'effective_expense': 0,
                'excluded_amount': 0,
                'excluded_ratio': 0,
                'analysis_summary': '无支出数据'
            }
        
        # === 步骤1：识别日常消费 ===
        
        # 1.1 严格金额限制：只保留 <10万 的交易
        daily_expense_mask = expense_df['amount'] < self.thresholds.daily_expense_max
        
        daily_expense_df = expense_df[daily_expense_mask]
        
        # 1.2 排除资产购置
        asset_purchase_mask = daily_expense_df['description'].str.contains(
            '|'.join(self.thresholds.asset_purchase_keywords), na=False, case=False
        )
        
        # 1.3 排除投资
        investment_mask = daily_expense_df['description'].str.contains(
            '|'.join(self.thresholds.investment_keywords), na=False, case=False
        )
        
        # 1.4 排除还款
        repayment_mask = daily_expense_df['description'].str.contains(
            '还款|还贷|按揭', na=False, case=False
        )
        
        # 1.5 排除家庭内部转账
        family_transfer_mask = daily_expense_df['counterparty'].isin(family_members)
        
        # 1.6 排除同一账户转账
        self_transfer_mask = daily_expense_df['counterparty'] == person_name
        
        # 合并所有排除条件
        strict_exclude_mask = (
            asset_purchase_mask | investment_mask | repayment_mask |
            family_transfer_mask | self_transfer_mask
        )
        
        # 最终日常消费
        strict_daily_expense_df = daily_expense_df[~strict_exclude_mask]
        
        # 计算统计数据
        total_expense = expense_df['amount'].sum()
        effective_expense = strict_daily_expense_df['amount'].sum()
        excluded_amount = total_expense - effective_expense
        excluded_ratio = (excluded_amount / total_expense * 100) if total_expense > 0 else 0
        
        # 按金额段统计
        bins = [0, 10000, 50000, 100000]
        labels = ['<1万', '1-5万', '5-10万']
        strict_daily_expense_df['amount_range'] = pd.cut(
            strict_daily_expense_df['amount'], bins=bins, labels=labels, right=False
        )
        
        amount_distribution = strict_daily_expense_df['amount_range'].value_counts().to_dict()
        
        # 生成分析摘要
        summary = self._generate_summary(
            total_expense, effective_expense, excluded_amount,
            excluded_ratio, amount_distribution
        )
        
        return {
            'total_expense': total_expense,
            'effective_expense': effective_expense,
            'excluded_amount': excluded_amount,
            'excluded_ratio': excluded_ratio,
            'effective_expense_df': strict_daily_expense_df,
            'amount_distribution': amount_distribution,
            'analysis_summary': summary
        }
    
    def _generate_summary(self,
                         total_expense: float,
                         effective_expense: float,
                         excluded_amount: float,
                         excluded_ratio: float,
                         amount_distribution: Dict[str, int]) -> str:
        """生成分析摘要"""
        
        summary_parts = []
        summary_parts.append(
            f"总支出{total_expense/10000:.2f}万元中，排除{excluded_amount/10000:.2f}万元（{excluded_ratio:.1f}%），"
        )
        summary_parts.append(f"严格的有效消费{effective_expense/10000:.2f}万元。")
        
        # 金额分布
        summary_parts.append("金额分布：")
        for range_label in ['<1万', '1-5万', '5-10万']:
            count = amount_distribution.get(range_label, 0)
            summary_parts.append(f"  • {range_label}：{count}笔")
        
        summary_parts.append("注：有效消费仅包括<10万元的日常消费，排除资产购置、投资、还款等大额支出。")
        
        return " ".join(summary_parts)


if __name__ == '__main__':
    print("严格有效消费计算器模块加载成功")
