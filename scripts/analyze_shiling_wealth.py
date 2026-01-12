#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析施灵的理财产品和消费习惯"""

import pandas as pd
import numpy as np

# 读取施灵的合并流水
df = pd.read_excel('output/cleaned_data/个人/施灵_合并流水.xlsx')
print(f"=" * 80)
print(f"施灵流水分析")
print(f"=" * 80)
print(f"总记录数: {len(df)}")
print(f"时间跨度: {df['交易时间'].min()} 至 {df['交易时间'].max()}")
print(f"总收入(元): {df['收入(元)'].sum():,.2f}")
print(f"总支出(元): {df['支出(元)'].sum():,.2f}")

# 分析交易摘要关键词
print(f"\n" + "=" * 80)
print("交易摘要关键词分析")
print("=" * 80)

# 理财相关关键词
wealth_keywords = ['理财', '基金', '赎回', '申购', '定期', '活期', '存款', '利息', 
                   '结息', '定存', '理财产品', '转存', '存入', '取出', '购买', '认购']

# 统计包含理财关键词的交易
wealth_df = df[df['交易摘要'].str.contains('|'.join(wealth_keywords), na=False, case=False) | 
               df['交易对手'].str.contains('|'.join(wealth_keywords), na=False, case=False)]

print(f"\n理财相关交易: {len(wealth_df)} 笔 ({len(wealth_df)/len(df)*100:.1f}%)")
print(f"  理财相关收入: {wealth_df['收入(元)'].sum():,.2f}")
print(f"  理财相关支出: {wealth_df['支出(元)'].sum():,.2f}")

# 更细致的分类
print(f"\n" + "-" * 40)
print("按关键词细分:")
for kw in wealth_keywords:
    mask = df['交易摘要'].str.contains(kw, na=False, case=False) | \
           df['交易对手'].str.contains(kw, na=False, case=False)
    count = mask.sum()
    if count > 0:
        income = df[mask]['收入(元)'].sum()
        expense = df[mask]['支出(元)'].sum()
        print(f"  {kw}: {count} 笔 | 收: {income:,.0f} | 支: {expense:,.0f}")

# 分析交易分类
print(f"\n" + "=" * 80)
print("交易分类统计")
print("=" * 80)
category_stats = df.groupby('交易分类').agg({
    '收入(元)': 'sum',
    '支出(元)': 'sum',
    '交易时间': 'count'
}).rename(columns={'交易时间': '笔数'})
category_stats = category_stats.sort_values('笔数', ascending=False)
print(category_stats.head(20))

# 找到高频交易对手（可能是理财相关）
print(f"\n" + "=" * 80)
print("高频交易对手 TOP 20")
print("=" * 80)
counterparty_stats = df.groupby('交易对手').agg({
    '收入(元)': 'sum',
    '支出(元)': 'sum',
    '交易时间': 'count'
}).rename(columns={'交易时间': '笔数'})
counterparty_stats = counterparty_stats.sort_values('笔数', ascending=False)
print(counterparty_stats.head(20))

# 详细分析理财产品交易
print(f"\n" + "=" * 80)
print("理财产品交易详细分析")
print("=" * 80)

# 寻找典型的理财产品交易模式
# 1. 购买理财产品（支出，通常是整数金额）
# 2. 赎回理财产品（收入，通常是整数金额+少量收益）
# 3. 理财收益（收入，金额较小）

# 整数金额交易（可能是本金）
large_round_income = df[(df['收入(元)'] >= 10000) & (df['收入(元)'] % 10000 == 0)]
large_round_expense = df[(df['支出(元)'] >= 10000) & (df['支出(元)'] % 10000 == 0)]

print(f"\n大额整万收入: {len(large_round_income)} 笔, 总计 {large_round_income['收入(元)'].sum():,.0f}")
print(f"大额整万支出: {len(large_round_expense)} 笔, 总计 {large_round_expense['支出(元)'].sum():,.0f}")

# 寻找"对敲"模式：同一天同一金额的收入和支出
print(f"\n" + "=" * 80)
print("潜在'对敲'分析（同日同额收支）")
print("=" * 80)

df['日期'] = pd.to_datetime(df['交易时间']).dt.date
daily_pairs = []
for date, group in df.groupby('日期'):
    incomes = group[group['收入(元)'] > 0]['收入(元)'].tolist()
    expenses = group[group['支出(元)'] > 0]['支出(元)'].tolist()
    # 找匹配
    for inc in incomes:
        if inc in expenses:
            daily_pairs.append({
                '日期': date,
                '金额': inc,
                '类型': '同日同额'
            })

print(f"同日同额收支对: {len(daily_pairs)} 对")
if daily_pairs:
    pair_df = pd.DataFrame(daily_pairs)
    print(f"涉及总金额: {pair_df['金额'].sum():,.0f}")
    print("\n金额分布:")
    print(pair_df['金额'].describe())

# 按年统计
print(f"\n" + "=" * 80)
print("分年度收支统计")
print("=" * 80)
df['年份'] = pd.to_datetime(df['交易时间']).dt.year
yearly_stats = df.groupby('年份').agg({
    '收入(元)': 'sum',
    '支出(元)': 'sum',
    '交易时间': 'count'
}).rename(columns={'交易时间': '笔数'})
yearly_stats['净流入'] = yearly_stats['收入(元)'] - yearly_stats['支出(元)']
print(yearly_stats)

# 剔除理财后的"真实"收支
print(f"\n" + "=" * 80)
print("剔除理财相关交易后的'真实'收支")
print("=" * 80)
non_wealth_df = df[~(df['交易摘要'].str.contains('|'.join(wealth_keywords), na=False, case=False) | 
                     df['交易对手'].str.contains('|'.join(wealth_keywords), na=False, case=False))]
print(f"非理财交易数: {len(non_wealth_df)} 笔")
print(f"非理财收入: {non_wealth_df['收入(元)'].sum():,.2f}")
print(f"非理财支出: {non_wealth_df['支出(元)'].sum():,.2f}")
