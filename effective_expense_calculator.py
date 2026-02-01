#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
有效支出计算器

功能：
1. 识别并排除家庭内部转账
2. 识别并排除同一账户转账
3. 识别并排除理财空转
4. 识别并排除还款支出
5. 识别并排除投资支出
6. 计算有效消费
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class EffectiveExpenseThresholds:
    """有效支出计算阈值配置"""
    large_transfer_threshold: float = 100000  # 大额转账阈值（10万元）


class EffectiveExpenseCalculator:
    """
    有效支出计算器
    
    核心功能：
    1. 识别并排除非实际消费的支出
    2. 计算有效消费
    3. 提供排除明细
    """
    
    def __init__(self, thresholds: Optional[EffectiveExpenseThresholds] = None):
        """初始化计算器"""
        self.thresholds = thresholds or EffectiveExpenseThresholds()
        
        # 理财空转关键词（全面）
        self.fund_cycling_keywords = [
            '定期开户', '起息', '结清', '大额存单', 
            '申购', '赎回', '活转定', '定转活',
            '开户', '结清', '产品起息', '定期起息',
            '产品实时购买', '个人大额存单结清',
            '活转定宝', '定转活宝',  # 理财产品
        ]
        
        # 理财产品代码模式
        self.fund_product_patterns = [
            r'FSG\d+', r'FSA\w+', r'FBAE\w+',  # 民生银行
            r'D310\w+',  # 其他银行
            r'WMY\d+', r'581122\d+',  # 其他产品
        ]
        
        # 还款关键词
        self.repayment_keywords = [
            '还贷', '还款', '贷款', '按揭', 
            '利息', '本金', '收回贷款',
            '代销理财资金归集'
        ]
        
        # 投资关键词
        self.investment_keywords = [
            '投资', '股票', '基金', '债券', 
            '期货', '外汇', '证券'
        ]
        
        # 固定资产购置关键词
        self.asset_purchase_keywords = [
            '购房', '买房', '房产', '不动产',
            '购车', '汽车', '车辆', '4S店',
            '装修', '家电'
        ]
    
    def calculate(self, 
                  transactions: pd.DataFrame,
                  family_members: List[str],
                  person_name: str) -> Dict[str, Any]:
        """
        计算有效消费
        
        Args:
            transactions: 交易明细（DataFrame）
            family_members: 家庭成员列表
            person_name: 当前人员姓名
        
        Returns:
            有效消费计算结果字典
        """
        # 只分析支出交易
        expense_df = transactions[transactions['direction'] == 'expense'].copy()
        
        if expense_df.empty:
            return {
                'total_expense': 0,
                'effective_expense': 0,
                'excluded_amount': 0,
                'excluded_breakdown': {},
                'analysis_summary': '无支出数据'
            }
        
        # 初始化排除明细
        excluded_breakdown = {
            'family_transfer': 0,
            'self_transfer': 0,
            'fund_cycling': 0,
            'repayment': 0,
            'investment': 0,
            'vague_large_transfer': 0
        }
        
        # 1. 排除家庭内部转账
        family_transfer_mask = expense_df['counterparty'].isin(family_members)
        family_transfer_amount = expense_df[family_transfer_mask]['amount'].sum()
        excluded_breakdown['family_transfer'] = family_transfer_amount
        
        # 2. 排除同一账户转账
        self_transfer_mask = (expense_df['counterparty'] == person_name)
        self_transfer_amount = expense_df[self_transfer_mask]['amount'].sum()
        excluded_breakdown['self_transfer'] = self_transfer_amount
        
        # 3. 排除理财空转
        fund_cycling_mask = self._match_fund_cycling(expense_df)
        fund_cycling_amount = expense_df[fund_cycling_mask]['amount'].sum()
        excluded_breakdown['fund_cycling'] = fund_cycling_amount
        
        # 4. 排除还款支出
        repayment_mask = expense_df['description'].str.contains(
            '|'.join(self.repayment_keywords), na=False, case=False
        )
        repayment_amount = expense_df[repayment_mask]['amount'].sum()
        excluded_breakdown['repayment'] = repayment_amount
        
        # 5. 排除投资支出
        investment_mask = expense_df['description'].str.contains(
            '|'.join(self.investment_keywords), na=False, case=False
        )
        investment_amount = expense_df[investment_mask]['amount'].sum()
        excluded_breakdown['investment'] = investment_amount
        
        # 6. 排除描述为"无"的大额转账（可能是系统空转）
        vague_large_transfer_mask = (
            (expense_df['description'].isin(['无', '未知', ''])) &
            (expense_df['amount'] > self.thresholds.large_transfer_threshold)
        )
        vague_large_transfer_amount = expense_df[vague_large_transfer_mask]['amount'].sum()
        excluded_breakdown['vague_large_transfer'] = vague_large_transfer_amount
        
        # 合并所有排除条件
        excluded_mask = (
            family_transfer_mask | self_transfer_mask | fund_cycling_mask |
            repayment_mask | investment_mask | vague_large_transfer_mask
        )
        
        # 计算总支出
        total_expense = expense_df['amount'].sum()
        
        # 计算有效消费
        effective_expense = expense_df[~excluded_mask]['amount'].sum()
        
        # 计算排除金额
        excluded_amount = total_expense - effective_expense
        
        # 计算排除比例
        excluded_ratio = (excluded_amount / total_expense * 100) if total_expense > 0 else 0
        
        # 生成分析摘要
        analysis_summary = self._generate_summary(
            total_expense, effective_expense, excluded_amount,
            excluded_breakdown, excluded_ratio
        )
        
        return {
            'total_expense': total_expense,
            'effective_expense': effective_expense,
            'excluded_amount': excluded_amount,
            'excluded_ratio': excluded_ratio,
            'excluded_breakdown': excluded_breakdown,
            'effective_expense_df': expense_df[~excluded_mask],
            'excluded_df': expense_df[excluded_mask],
            'analysis_summary': analysis_summary
        }
    
    def _match_fund_cycling(self, df: pd.DataFrame) -> pd.Series:
        """匹配理财空转交易"""
        # 关键词匹配
        keyword_mask = df['description'].str.contains(
            '|'.join(self.fund_cycling_keywords), na=False, case=False
        )
        
        # 产品代码匹配
        product_mask = pd.Series([False] * len(df), index=df.index)
        for pattern in self.fund_product_patterns:
            product_mask = product_mask | df['description'].str.contains(pattern, na=False, regex=True)
        
        return keyword_mask | product_mask
    
    def _generate_summary(self,
                         total_expense: float,
                         effective_expense: float,
                         excluded_amount: float,
                         excluded_breakdown: Dict[str, float],
                         excluded_ratio: float) -> str:
        """生成分析摘要"""
        summary_parts = []
        
        # 总体情况
        summary_parts.append(f"总支出{total_expense/10000:.2f}万元中，排除{excluded_amount/10000:.2f}万元（{excluded_ratio:.1f}%），有效消费{effective_expense/10000:.2f}万元。")
        
        # 主要排除项
        main_exclusions = [
            (k, v) for k, v in excluded_breakdown.items() 
            if v > 0
        ]
        main_exclusions.sort(key=lambda x: x[1], reverse=True)
        
        if main_exclusions:
            summary_parts.append("主要排除项：")
            for name, amount in main_exclusions[:3]:  # 只显示前3项
                name_cn = {
                    'family_transfer': '家庭内部转账',
                    'self_transfer': '同一账户转账',
                    'fund_cycling': '理财空转',
                    'repayment': '还款支出',
                    'investment': '投资支出',
                    'vague_large_transfer': '大额空转'
                }.get(name, name)
                summary_parts.append(f"  - {name_cn}：{amount/10000:.2f}万元")
        
        return " ".join(summary_parts)
    
    def classify_expense(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """
        分类支出交易
        
        返回：
            增加了'expense_category'列的DataFrame
            类别：'消费'、'固定资产购置'、'投资'、'还款'、'空转'、'其他'
        """
        df = transactions.copy()
        df['expense_category'] = '其他'
        
        # 只分类支出交易
        expense_mask = df['direction'] == 'expense'
        
        # 1. 明确的消费
        explicit_consumption_keywords = [
            '消费', '超市', '餐饮', '购物', '交通',
            '医疗', '医院', '诊所', '教育', '培训',
            '旅游', '娱乐', '超市', '美团', '支付宝', '微信'
        ]
        explicit_consumption_mask = (
            expense_mask &
            df['description'].str.contains('|'.join(explicit_consumption_keywords), na=False, case=False)
        )
        df.loc[explicit_consumption_mask, 'expense_category'] = '消费'
        
        # 2. 固定资产购置
        asset_purchase_mask = (
            expense_mask &
            df['description'].str.contains('|'.join(self.asset_purchase_keywords), na=False, case=False)
        )
        df.loc[asset_purchase_mask, 'expense_category'] = '固定资产购置'
        
        # 3. 还款支出
        repayment_mask = (
            expense_mask &
            df['description'].str.contains('|'.join(self.repayment_keywords), na=False, case=False)
        )
        df.loc[repayment_mask, 'expense_category'] = '还款'
        
        # 4. 投资支出
        investment_mask = (
            expense_mask &
            df['description'].str.contains('|'.join(self.investment_keywords), na=False, case=False)
        )
        df.loc[investment_mask, 'expense_category'] = '投资'
        
        # 5. 空转（理财空转、同一账户转账、大额空转）
        fund_cycling_mask = self._match_fund_cycling(df)
        self_transfer_mask = df['counterparty'] == df['person']
        vague_large_transfer_mask = (
            (df['description'].isin(['无', '未知', ''])) &
            (df['amount'] > self.thresholds.large_transfer_threshold) &
            expense_mask
        )
        
        cycling_mask = fund_cycling_mask | self_transfer_mask | vague_large_transfer_mask
        df.loc[cycling_mask, 'expense_category'] = '空转'
        
        return df


if __name__ == '__main__':
    print("有效支出计算器模块加载成功")
