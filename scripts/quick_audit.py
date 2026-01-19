#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速审计缓存字段"""
import json
import os

cache_path = "output/analysis_results_cache.json"
with open(cache_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 60)
print("字段完整性审计")
print("=" * 60)

# 检查 income details
inc_details = data.get('analysisResults', {}).get('income', {}).get('details', [])
print(f"\n[income.details] 共 {len(inc_details)} 条")

# 按 _type 分组统计
type_stats = {}
missing_date = 0
missing_risk_reason = 0
missing_source_row = 0

for item in inc_details:
    t = item.get('_type', 'unknown')
    if t not in type_stats:
        type_stats[t] = {'count': 0, 'sample_keys': None, 'sample': None}
    type_stats[t]['count'] += 1
    if type_stats[t]['sample_keys'] is None:
        type_stats[t]['sample_keys'] = list(item.keys())
        type_stats[t]['sample'] = item
    
    # 检查缺失字段
    if not item.get('date'):
        missing_date += 1
    if not item.get('risk_reason') and not item.get('description'):
        missing_risk_reason += 1
    if not item.get('source_row_index') and not item.get('source_row'):
        missing_source_row += 1

print(f"\n缺失统计:")
print(f"  - 缺少日期: {missing_date}")
print(f"  - 缺少风险说明: {missing_risk_reason}")
print(f"  - 缺少行号: {missing_source_row}")

print(f"\n按类型分组:")
for t, stats in type_stats.items():
    print(f"\n  [{t}] 共 {stats['count']} 条")
    print(f"    字段: {stats['sample_keys']}")
    sample = stats['sample']
    print(f"    date字段: {sample.get('date', 'N/A')}")
    print(f"    risk_reason: {sample.get('risk_reason', 'N/A')}")
    print(f"    description: {sample.get('description', 'N/A')}")
    print(f"    source_row_index: {sample.get('source_row_index', 'N/A')}")
    print(f"    source_row: {sample.get('source_row', 'N/A')}")

# 检查 loan details
print("\n" + "=" * 60)
loan_details = data.get('analysisResults', {}).get('loan', {}).get('details', [])
print(f"\n[loan.details] 共 {len(loan_details)} 条")

loan_type_stats = {}
for item in loan_details:
    t = item.get('_type', 'unknown')
    if t not in loan_type_stats:
        loan_type_stats[t] = {'count': 0, 'sample_keys': None, 'sample': None}
    loan_type_stats[t]['count'] += 1
    if loan_type_stats[t]['sample_keys'] is None:
        loan_type_stats[t]['sample_keys'] = list(item.keys())
        loan_type_stats[t]['sample'] = item

for t, stats in loan_type_stats.items():
    print(f"\n  [{t}] 共 {stats['count']} 条")
    print(f"    字段: {stats['sample_keys']}")
    sample = stats['sample']
    print(f"    source_row_index: {sample.get('source_row_index', 'N/A')}")
    print(f"    source_row: {sample.get('source_row', 'N/A')}")
