#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查profiles_full.json - 详细检查所有可能的工资和单位字段
"""

import json
import os

profiles_path = "./output/analysis_cache/profiles_full.json"
with open(profiles_path, 'r', encoding='utf-8') as f:
    profiles = json.load(f)

print("=" * 80)
print("详细数据检查")
print("=" * 80)

for name, profile in list(profiles.items())[:3]:
    print(f"\n{'='*60}")
    print(f"姓名: {name}")
    print(f"{'='*60}")
    
    # 检查所有字段
    print(f"\n所有字段: {list(profile.keys())}")
    
    # 1. 检查yearly_salary (下划线)
    print("\n【yearly_salary (下划线)】")
    yearly_salary = profile.get("yearly_salary", {})
    print(f"  类型: {type(yearly_salary)}")
    print(f"  内容: {json.dumps(yearly_salary, ensure_ascii=False, indent=2)[:800] if yearly_salary else 'None/Empty'}")
    
    # 2. 检查yearlySalary (驼峰)
    print("\n【yearlySalary (驼峰)】")
    yearlySalary = profile.get("yearlySalary", {})
    print(f"  类型: {type(yearlySalary)}")
    print(f"  内容: {json.dumps(yearlySalary, ensure_ascii=False, indent=2)[:800] if yearlySalary else 'None/Empty'}")
    
    # 3. 检查summary中的工资
    print("\n【summary中的工资】")
    summary = profile.get("summary", {})
    if summary:
        print(f"  summary: {json.dumps(summary, ensure_ascii=False, indent=2)[:600]}")
    else:
        print("  无summary")
    
    # 4. 检查bank_accounts
    print("\n【bank_accounts】")
    bank_accounts = profile.get("bank_accounts", [])
    print(f"  数量: {len(bank_accounts)}")
    if bank_accounts:
        print(f"  示例: {bank_accounts[0]}")
    
    # 5. 检查是否有id_info或其他单位信息
    print("\n【所有可能含单位信息的字段】")
    for key in profile.keys():
        if any(kw in key.lower() for kw in ['id', 'info', 'employer', '单位', 'work', 'company', 'position', '职务']):
            value = profile.get(key)
            print(f"  {key}: {type(value)} - {str(value)[:100]}")

print("\n" + "=" * 80)
print("关键发现总结")
print("=" * 80)
