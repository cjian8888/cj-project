#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证新生成的缓存数据一致性
"""
import json
import os

# 检查两个缓存文件
cache1 = './output/analysis_results_cache.json'
cache2 = './output/analysis_cache/derived_data.json'

result = {}

# 检查主缓存
if os.path.exists(cache1):
    with open(cache1, 'r', encoding='utf-8') as f:
        data = json.load(f)
    fs = data.get('familySummary', {})
    result['main_cache'] = {
        'path': cache1,
        'family_summary_keys': list(fs.keys()) if fs else [],
        'total_income': fs.get('total_income_expense', {}).get('total_income', 0),
        'total_expense': fs.get('total_income_expense', {}).get('total_expense', 0),
    }

# 检查分散缓存
if os.path.exists(cache2):
    with open(cache2, 'r', encoding='utf-8') as f:
        data = json.load(f)
    fs = data.get('family_summary', {})
    result['derived_data'] = {
        'path': cache2,
        'family_summary_keys': list(fs.keys()) if fs else [],
        'total_income': fs.get('total_income_expense', {}).get('total_income', 0),
        'total_expense': fs.get('total_income_expense', {}).get('total_expense', 0),
    }

# 检查 profiles_full.json 来计算预期值
pf_path = './output/analysis_cache/profiles_full.json'
if os.path.exists(pf_path):
    with open(pf_path, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    members = ['施灵', '滕雳', '施承天']
    calc_income = sum(profiles.get(m, {}).get('totalIncome', 0) or 0 for m in members)
    calc_expense = sum(profiles.get(m, {}).get('totalExpense', 0) or 0 for m in members)
    result['expected_from_profiles'] = {
        'total_income': calc_income,
        'total_expense': calc_expense,
    }

with open('debug_cache_verify.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('Done. See debug_cache_verify.json')
