#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证报告生成的数据一致性（简化版）
"""
import json
import sys
sys.path.insert(0, '.')

from investigation_report_builder import load_investigation_report_builder

# 加载报告构建器
builder = load_investigation_report_builder('./output')
if not builder:
    print('Failed to load builder')
    exit(1)

print('Builder loaded successfully')

# 检查 derived_data 中的 family_summary
fs = builder.derived_data.get('family_summary', {})
print(f'derived_data.family_summary.family_members: {fs.get("family_members", [])}')
print(f'derived_data.family_summary.total_income: {fs.get("total_income_expense", {}).get("total_income", 0):,.2f}')

# 测试 _build_family_summary_v4
members = ['施灵', '滕雳', '施承天']
summary = builder._build_family_summary_v4('施灵', members)

result = {
    'cached_family_members': fs.get('family_members', []),
    'cached_total_income': fs.get('total_income_expense', {}).get('total_income', 0),
    'report_members': members,
    'report_total_income': summary.get('total_income', 0),
    'report_total_expense': summary.get('total_expense', 0),
}

# 计算预期值
profiles = builder.profiles
expected_income = sum(profiles.get(m, {}).get('totalIncome', 0) or 0 for m in members)
expected_expense = sum(profiles.get(m, {}).get('totalExpense', 0) or 0 for m in members)
result['expected_from_profiles'] = {
    'total_income': expected_income,
    'total_expense': expected_expense,
}

# 检查匹配
result['income_matches_expected'] = abs(result['report_total_income'] - expected_income) < 1
result['income_diff'] = result['report_total_income'] - expected_income

with open('debug_report_verify.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\nReport total_income: {result['report_total_income']:,.2f}")
print(f"Expected total_income: {expected_income:,.2f}")
print(f"Match: {result['income_matches_expected']}")
