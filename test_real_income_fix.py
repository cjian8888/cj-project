#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试真实收入计算修复
"""

import json
import sys
sys.path.insert(0, '.')

from financial_profiler import _calculate_real_income_expense

# 加载施灵的数据
with open('output/analysis_cache/profiles.json', 'r') as f:
    profiles = json.load(f)

sl = profiles['施灵']
income_structure = sl['income_structure']
wealth_management = sl['wealth_management']
fund_flow = sl['fund_flow']

print('=== 施灵真实收入计算测试 ===')
print()

# 旧的计算方式（错误）
self_in = wealth_management['self_transfer_income']
self_out = wealth_management['self_transfer_expense']
wealth_buy = wealth_management['wealth_purchase']
wealth_redeem = wealth_management['wealth_redemption']
loan_in = wealth_management['loan_inflow']
refund_in = wealth_management['refund_inflow']

old_offset = min(self_in, self_out) + min(wealth_buy, wealth_redeem) + loan_in + refund_in
old_real_income = income_structure['total_income'] - old_offset

print('【旧计算方式（错误）】')
print(f'  总收入: {income_structure["total_income"]/10000:.2f}万')
print(f'  剔除: {old_offset/10000:.2f}万')
print(f'  真实收入: {old_real_income/10000:.2f}万')
print()

# 新的计算方式（修复）
real_income, real_expense, offset_detail = _calculate_real_income_expense(
    income_structure, wealth_management, fund_flow
)

print('【新计算方式（修复）】')
print(f'  总收入: {income_structure["total_income"]/10000:.2f}万')
print(f'  剔除合计: {offset_detail["total_offset"]/10000:.2f}万')
print(f'    - 自我转账: {offset_detail["self_transfer"]/10000:.2f}万')
print(f'    - 理财本金: {offset_detail["wealth_principal"]/10000:.2f}万')
print(f'    - 理财历史存量: {offset_detail["wealth_historical"]/10000:.2f}万')
print(f'    - 定存到期: {offset_detail["deposit_redemption"]/10000:.2f}万')
print(f'    - 贷款: {offset_detail["loan"]/10000:.2f}万')
print(f'    - 退款: {offset_detail["refund"]/10000:.2f}万')
print(f'  真实收入: {real_income/10000:.2f}万')
print()

print('【对比】')
print(f'  旧真实收入: {old_real_income/10000:.2f}万')
print(f'  新真实收入: {real_income/10000:.2f}万')
print(f'  差异: {(real_income - old_real_income)/10000:.2f}万')
print()

print('【工资收入】')
salary = sl['yearly_salary']['summary']['total']
print(f'  工资收入: {salary/10000:.2f}万')
print(f'  占真实收入比例: {salary/real_income*100:.1f}%' if real_income > 0 else '  N/A')
