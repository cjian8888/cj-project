#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 analysis_results_cache.json 中的 familySummary 结构
"""
import json

with open('./output/analysis_results_cache.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 查找 familySummary
# 可能的键名: familySummary, family_summary
fs = data.get('familySummary') or data.get('family_summary') or {}

result = {
    'cache_keys': list(data.keys()),
    'familySummary_key_found': 'familySummary' in data or 'family_summary' in data,
    'familySummary_structure': {
        'keys': list(fs.keys()) if fs else [],
        'family_members': fs.get('family_members', []),
        'total_income_expense': fs.get('total_income_expense', {}),
        'total_assets': fs.get('total_assets', {}),
    }
}

with open('debug_main_cache.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('Done')
