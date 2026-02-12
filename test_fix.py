#!/usr/bin/env python3
import importlib
import financial_profiler
importlib.reload(financial_profiler)

from financial_profiler import _calculate_real_income_expense
import json

profiles = json.load(open('output/analysis_cache/profiles.json'))
sl = profiles['施灵']

real_income, real_expense, offset_detail = _calculate_real_income_expense(
    sl['income_structure'],
    sl['wealth_management'],
    sl['fund_flow']
)

print('=== 修复效果验证 ===')
print()
print('旧真实收入: 2234.77万')
print(f'新真实收入: {real_income/10000:.2f}万')
print(f'差异: {real_income/10000 - 2234.77:.2f}万')
print()
print('剔除详情:')
for k, v in offset_detail.items():
    if k != 'total_offset':
        print(f'  - {k}: {v/10000:.2f}万')
print(f'  合计剔除: {offset_detail["total_offset"]/10000:.2f}万')
print()
salary = sl['yearly_salary']['summary']['total']
print(f'工资收入: {salary/10000:.2f}万')
if real_income > 0:
    print(f'占真实收入比例: {salary/real_income*100:.1f}%')
