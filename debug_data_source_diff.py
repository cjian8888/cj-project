#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断报告数据来源差异
"""
import json

# 1. 读取缓存的 family_summary
with open('output/analysis_cache/derived_data.json', 'r', encoding='utf-8') as f:
    dd = json.load(f)
cache_summary = dd.get('family_summary', {})

# 2. 读取报告的 family_summary  
with open('output/report_v4.json', 'r', encoding='utf-8') as f:
    report = json.load(f)
report_summary = report.get('family_sections', [{}])[0].get('family_summary', {})

# 3. 从 profiles_full.json 计算
with open('output/analysis_cache/profiles_full.json', 'r', encoding='utf-8') as f:
    profiles = json.load(f)

# 计算三个成员的合计
members = ['施灵', '滕雳', '施承天']
calculated_income = sum(profiles.get(m, {}).get('totalIncome', 0) or 0 for m in members)
calculated_expense = sum(profiles.get(m, {}).get('totalExpense', 0) or 0 for m in members)
calculated_salary = sum(profiles.get(m, {}).get('salaryTotal', 0) or 0 for m in members)

result = {
    'cache_family_summary': {
        'total_income': cache_summary.get('total_income_expense', {}).get('total_income', 0),
        'total_expense': cache_summary.get('total_income_expense', {}).get('total_expense', 0),
    },
    'report_family_summary': {
        'total_income': report_summary.get('total_income', 0),
        'total_expense': report_summary.get('total_expense', 0),
        'total_salary': report_summary.get('total_salary', 0),
        'salary_ratio': report_summary.get('salary_ratio', 0),
    },
    'calculated_from_profiles': {
        'total_income': calculated_income,
        'total_expense': calculated_expense,
        'total_salary': calculated_salary,
    },
    'individual_profiles': {}
}

for m in members:
    p = profiles.get(m, {})
    result['individual_profiles'][m] = {
        'totalIncome': p.get('totalIncome', 0),
        'totalExpense': p.get('totalExpense', 0),
        'salaryTotal': p.get('salaryTotal', 0),
    }

with open('debug_data_source_diff.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('Done. See debug_data_source_diff.json')
