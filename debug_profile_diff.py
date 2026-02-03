#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证 profile 结构中 totalIncome vs summary.total_income 的差异
"""
import json

with open('output/analysis_cache/profiles_full.json', 'r', encoding='utf-8') as f:
    profiles = json.load(f)

result = {}
for name in ['施灵', '滕雳', '施承天']:
    p = profiles.get(name, {})
    summary = p.get('summary', {})
    result[name] = {
        'totalIncome_top': p.get("totalIncome", 0),
        'totalExpense_top': p.get("totalExpense", 0),
        'summary_total_income': summary.get("total_income", 0),
        'summary_total_expense': summary.get("total_expense", 0),
        'income_diff': p.get("totalIncome", 0) - summary.get("total_income", 0),
        'expense_diff': p.get("totalExpense", 0) - summary.get("total_expense", 0),
    }

with open('debug_profile_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('Done')
