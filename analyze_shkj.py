#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析上海空间电源研究所为什么没被识别为工资
"""

import pandas as pd

df = pd.read_excel('./output/cleaned_data/个人/马尚德_合并流水.xlsx')
df['date'] = pd.to_datetime(df['date'])

# 筛选上海空间电源研究所的收入
income = df[(df['income'] > 0) & (df['counterparty'].str.contains('上海空间电源研究所', na=False))].sort_values('date')

print('=' * 100)
print('上海空间电源研究所收入分析')
print('=' * 100)

print(f'\n总计: {len(income)}笔, {income["income"].sum()/10000:.2f}万元')
print(f'时间范围: {income["date"].min()} 至 {income["date"].max()}')

# 月份统计
months = set(income['date'].dt.to_period('M'))
print(f'跨越月份数: {len(months)}')
print(f'交易频率: {len(income)/len(months):.2f} 次/月')

# 金额统计
amounts = income['income'].tolist()
mean_amt = sum(amounts) / len(amounts)
std_amt = (sum((x - mean_amt) ** 2 for x in amounts) / len(amounts)) ** 0.5
cv = std_amt / mean_amt

print(f'\n金额统计:')
print(f'  均值: {mean_amt:,.0f} 元')
print(f'  标准差: {std_amt:,.0f} 元')
print(f'  变异系数CV: {cv:.2f}')
print(f'  最小值: {min(amounts):,.0f} 元')
print(f'  最大值: {max(amounts):,.0f} 元')

# 检查双向交易
all_trans = df[df['counterparty'].str.contains('上海空间电源研究所', na=False)]
total_income = all_trans['income'].sum()
total_expense = all_trans['expense'].sum()
print(f'\n双向交易检查:')
print(f'  总收入: {total_income:,.0f} 元')
print(f'  总支出: {total_expense:,.0f} 元')
print(f'  支出/收入比: {total_expense/total_income*100:.1f}%')

# 判断为什么没被识别
print('\n' + '=' * 100)
print('未被识别原因分析:')
print('=' * 100)

reasons = []

# 检查交易次数
if len(income) < 6:
    reasons.append(f'❌ 交易次数不足({len(income)}笔 < 6笔)')
else:
    reasons.append(f'✅ 交易次数充足({len(income)}笔 >= 6笔)')

# 检查月份连续性
if len(months) < 6:
    reasons.append(f'❌ 月份跨度不足({len(months)}个月 < 6个月)')
else:
    reasons.append(f'✅ 月份跨度充足({len(months)}个月 >= 6个月)')

# 检查交易频率
freq = len(income) / len(months)
if freq <= 0.7:
    reasons.append(f'❌ 交易频率过低({freq:.2f} <= 0.7)')
else:
    reasons.append(f'✅ 交易频率充足({freq:.2f} > 0.7)')

# 检查金额范围
if mean_amt < 1000 or mean_amt > 50000:
    reasons.append(f'❌ 平均金额超出范围({mean_amt:,.0f}元 不在1000-50000元范围内)')
else:
    reasons.append(f'✅ 平均金额在合理范围({mean_amt:,.0f}元)')

# 检查金额稳定性
if cv >= 0.8:
    reasons.append(f'❌ 金额波动过大(CV={cv:.2f} >= 0.8)')
else:
    reasons.append(f'✅ 金额相对稳定(CV={cv:.2f} < 0.8)')

# 检查双向交易
if total_expense > total_income * 0.5:
    reasons.append(f'❌ 存在大额反向交易(支出/收入={total_expense/total_income*100:.1f}% > 50%)')
else:
    reasons.append(f'✅ 无明显借贷特征(支出/收入={total_expense/total_income*100:.1f}%)')

for reason in reasons:
    print(reason)

print('\n' + '=' * 100)
print('详细交易记录:')
print('=' * 100)
print(income[['date', 'income', 'description', 'counterparty']].to_string(index=False))

print('\n' + '=' * 100)
print('结论:')
print('=' * 100)

# 统计失败原因
failed = [r for r in reasons if r.startswith('❌')]
if failed:
    print(f'上海空间电源研究所的收入未被识别,因为有{len(failed)}个条件不满足:')
    for r in failed:
        print(f'  {r}')
else:
    print('⚠️ 所有条件都满足,但仍未被识别,可能是其他原因(如摘要关键词检查等)')
