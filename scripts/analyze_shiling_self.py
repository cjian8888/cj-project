#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析施灵自我转账情况"""

import pandas as pd

df = pd.read_excel('output/cleaned_data/个人/施灵_合并流水.xlsx')

# 分析与自己账户之间的转账
self_transfer = df[df['交易对手'].str.contains('施灵', na=False)]
print('=' * 80)
print('施灵自我转账分析')
print('=' * 80)
print(f'自我转账总笔数: {len(self_transfer)}')

income_col = '收入(元)'
expense_col = '支出(元)'

income_count = len(self_transfer[self_transfer[income_col] > 0])
expense_count = len(self_transfer[self_transfer[expense_col] > 0])
income_sum = self_transfer[income_col].sum()
expense_sum = self_transfer[expense_col].sum()

print(f'  收入笔数: {income_count}')
print(f'  支出笔数: {expense_count}')
print(f'  自我转账收入总额: {income_sum:,.2f}')
print(f'  自我转账支出总额: {expense_sum:,.2f}')

print('\n自我转账的交易摘要分布:')
print(self_transfer['交易摘要'].value_counts().head(20))

# 查看部分自我转账样例
print('\n自我转账样例(收入):')
sample = self_transfer[self_transfer[income_col] > 0][['交易时间', income_col, '交易对手', '交易摘要', '所属银行']].head(10)
print(sample.to_string())

print('\n自我转账样例(支出):')
sample = self_transfer[self_transfer[expense_col] > 0][['交易时间', expense_col, '交易对手', '交易摘要', '所属银行']].head(10)
print(sample.to_string())

# 分析如果剔除自我转账后的真实收支
print('\n' + '=' * 80)
print('剔除自我转账后的"真实"收支')
print('=' * 80)
non_self = df[~df['交易对手'].str.contains('施灵', na=False)]
print(f'非自我转账交易: {len(non_self)} 笔')
print(f'  真实收入: {non_self[income_col].sum():,.2f}')
print(f'  真实支出: {non_self[expense_col].sum():,.2f}')

# 理财产品的全貌
print('\n' + '=' * 80)
print('理财产品全貌分析')
print('=' * 80)

# 识别理财相关交易
wealth_keywords = ['理财', '基金', '赎回', '申购', '定期', '活期', '定存', '理财产品', '转存', '认购', '购买']
mask = df['交易摘要'].str.contains('|'.join(wealth_keywords), na=False, case=False) | \
       df['交易对手'].str.contains('|'.join(wealth_keywords), na=False, case=False)

# 还要识别基金公司
fund_companies = ['基金', '证券', '中登', '托管']
mask2 = df['交易对手'].str.contains('|'.join(fund_companies), na=False, case=False)

wealth_df = df[mask | mask2]

# 按交易类型分类：购入 vs 赎回
wealth_purchase = wealth_df[wealth_df[expense_col] > 0]
wealth_redemption = wealth_df[wealth_df[income_col] > 0]

print(f'理财购入交易: {len(wealth_purchase)} 笔, 总金额: {wealth_purchase[expense_col].sum():,.2f}')
print(f'理财赎回交易: {len(wealth_redemption)} 笔, 总金额: {wealth_redemption[income_col].sum():,.2f}')
print(f'理财净投入: {wealth_purchase[expense_col].sum() - wealth_redemption[income_col].sum():,.2f}')

# 按年统计理财
wealth_df_copy = wealth_df.copy()
wealth_df_copy['年份'] = pd.to_datetime(wealth_df_copy['交易时间']).dt.year
yearly = wealth_df_copy.groupby('年份').agg({
    income_col: 'sum',
    expense_col: 'sum'
}).rename(columns={income_col: '赎回', expense_col: '购入'})
yearly['净投入'] = yearly['购入'] - yearly['赎回']
print('\n年度理财统计:')
print(yearly)

# 统计理财收益（利息/结息部分）
interest_mask = df['交易摘要'].str.contains('利息|结息|收益', na=False, case=False)
interest_df = df[interest_mask & (df[income_col] > 0)]
print(f'\n理财收益/利息: {len(interest_df)} 笔, 总金额: {interest_df[income_col].sum():,.2f}')
