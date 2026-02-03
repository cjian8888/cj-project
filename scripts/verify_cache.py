#!/usr/bin/env python3
import json

with open('output/analysis_results_cache.json', encoding='utf-8') as f:
    data = json.load(f)

ar = data.get('analysisResults', {})
loan = ar.get('loan', {})
income = ar.get('income', {})

print("=" * 60)
print("缓存验证结果")
print("=" * 60)
print()
print(f"loan.summary: {loan.get('summary', {})}")
print(f"loan.details 数量: {len(loan.get('details', []))}")
if loan.get('details'):
    print(f"  首条记录: {loan['details'][0]}")
print()
print(f"income.summary: {income.get('summary', {})}")
print(f"income.details 数量: {len(income.get('details', []))}")
if income.get('details'):
    print(f"  首条记录: {income['details'][0]}")
print()
print("=" * 60)
