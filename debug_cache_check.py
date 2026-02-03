#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断脚本：检查缓存文件和报告数据流 - JSON输出
"""

import json
import os

output_dir = './output'
cache_dir = os.path.join(output_dir, 'analysis_cache')

result = {}

# 检查主缓存
full_cache = os.path.join(output_dir, 'analysis_results_cache.json')
result['full_cache_exists'] = os.path.exists(full_cache)

# 检查分散缓存
result['cache_files'] = {}
files = ['profiles.json', 'profiles_full.json', 'derived_data.json', 'metadata.json', 'suspicions.json', 'graph_data.json']
for f in files:
    path = os.path.join(cache_dir, f)
    if os.path.exists(path):
        result['cache_files'][f] = {'exists': True, 'size_mb': round(os.path.getsize(path)/1024/1024, 2)}
    else:
        result['cache_files'][f] = {'exists': False}

# derived_data.json 
with open(os.path.join(cache_dir, 'derived_data.json'), 'r', encoding='utf-8') as f:
    dd = json.load(f)
result['derived_data_keys'] = list(dd.keys())

fs = dd.get('family_summary', {})
result['family_summary_keys'] = list(fs.keys()) if fs else []

if 'total_income_expense' in fs:
    result['family_summary_income_expense'] = fs['total_income_expense']
if 'total_assets' in fs:
    result['family_summary_assets'] = fs['total_assets']

# profiles_full.json 检查
pf_path = os.path.join(cache_dir, 'profiles_full.json')
if os.path.exists(pf_path):
    with open(pf_path, 'r', encoding='utf-8') as f:
        pf = json.load(f)
    result['profiles_count'] = len(pf)
    result['profile_samples'] = {}
    for name in list(pf.keys())[:3]:
        profile = pf[name]
        result['profile_samples'][name] = {
            'totalIncome': profile.get('totalIncome', 0),
            'totalExpense': profile.get('totalExpense', 0),
            'salaryTotal': profile.get('salaryTotal', 0),
            'wealthTotal': profile.get('wealthTotal', 0),
            'bankAccounts_count': len(profile.get('bankAccounts', []) or [])
        }

# report_v4.json 检查
report_path = os.path.join(output_dir, 'report_v4.json')
if os.path.exists(report_path):
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    result['report_keys'] = list(report.keys())
    
    # 检查 family_sections
    fs_list = report.get('family_sections', [])
    if fs_list:
        f0 = fs_list[0]
        result['family_sections_0_keys'] = list(f0.keys())
        summary = f0.get('family_summary', {})
        result['family_sections_0_summary'] = {
            'total_income': summary.get('total_income', 0),
            'total_expense': summary.get('total_expense', 0),
            'total_salary': summary.get('total_salary', 0)
        }

# 保存结果
with open('debug_cache_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print('Check completed. See debug_cache_result.json')
