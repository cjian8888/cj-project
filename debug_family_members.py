#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 family_summary 的 family_members 和 profiles 中有数据的成员
"""
import json

with open('output/analysis_cache/derived_data.json', 'r', encoding='utf-8') as f:
    dd = json.load(f)

with open('output/analysis_cache/profiles_full.json', 'r', encoding='utf-8') as f:
    profiles = json.load(f)

family_summary = dd.get('family_summary', {})
family_members = family_summary.get('family_members', [])

result = {
    'family_members': family_members,
    'profiles_entities': list(profiles.keys()),
    'member_data': {},
    'comparison': {}
}

for m in family_members:
    p = profiles.get(m, {})
    result['member_data'][m] = {
        'has_data': p.get('has_data', False),
        'totalIncome': p.get('totalIncome', 0),
        'totalExpense': p.get('totalExpense', 0),
        'summary_total_income': p.get('summary', {}).get('total_income', 0),
        'summary_total_expense': p.get('summary', {}).get('total_expense', 0),
    }

# 从 family_members 计算（模拟 calculate_family_summary 的逻辑）
calc_income = 0
calc_expense = 0
for m in family_members:
    p = profiles.get(m, {})
    if p.get('has_data'):
        s = p.get('summary', {})
        calc_income += s.get('total_income', 0)
        calc_expense += s.get('total_expense', 0)

# 缓存的值
tie = family_summary.get('total_income_expense', {})

result['comparison'] = {
    'calculated_from_profiles': {
        'total_income': calc_income,
        'total_expense': calc_expense,
    },
    'cached_family_summary': {
        'total_income': tie.get("total_income", 0),
        'total_expense': tie.get("total_expense", 0),
    },
    'difference': {
        'income': calc_income - tie.get("total_income", 0),
        'expense': calc_expense - tie.get("total_expense", 0),
    }
}

with open('debug_family_members_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('Done')
