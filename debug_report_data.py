#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试报告数据结构
检查实际的profiles数据
"""

import json
import os

# 加载实际的profiles数据
profiles_path = "./output/analysis_cache/profiles.json"
if os.path.exists(profiles_path):
    with open(profiles_path, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    print("=" * 80)
    print("实际的profiles数据结构")
    print("=" * 80)
    
    for name, profile in list(profiles.items())[:3]:  # 只检查前3个人
        print(f"\n{'='*40}")
        print(f"姓名: {name}")
        print(f"{'='*40}")
        
        # 检查工资数据
        print("\n【工资数据】")
        yearly_salary = profile.get("yearlySalary", {})
        print(f"  yearlySalary 类型: {type(yearly_salary)}")
        print(f"  yearlySalary 内容: {json.dumps(yearly_salary, ensure_ascii=False, indent=2)[:500]}")
        
        # 检查户籍/单位信息
        print("\n【单位信息】")
        id_info = profile.get("id_info", {})
        print(f"  id_info: {json.dumps(id_info, ensure_ascii=False, indent=2) if id_info else 'None'}")
        
        # 检查原始数据中的单位
        summary = profile.get("summary", {})
        print(f"  summary: {json.dumps(summary, ensure_ascii=False, indent=2)[:300] if summary else 'None'}")
        
        # 检查employer
        print(f"  profile.get('employer'): {profile.get('employer', 'Not found')}")
        print(f"  profile.get('从业单位'): {profile.get('从业单位', 'Not found')}")
        
        # 检查是否有transactions
        print("\n【交易数据】")
        transactions = profile.get("transactions", [])
        print(f"  transactions数量: {len(transactions) if transactions else 0}")
        
else:
    print(f"文件不存在: {profiles_path}")

# 检查derived_data
print("\n" + "=" * 80)
print("检查derived_data中的家庭数据")
print("=" * 80)

derived_path = "./output/analysis_cache/derived_data.json"
if os.path.exists(derived_path):
    with open(derived_path, 'r', encoding='utf-8') as f:
        derived = json.load(f)
    
    family_summary = derived.get("family_summary", {})
    print(f"\nfamily_summary: {json.dumps(family_summary, ensure_ascii=False, indent=2)[:800]}")
    
    family_relations = derived.get("family_relations", {})
    print(f"\nfamily_relations数量: {len(family_relations)}")
    for name, relations in list(family_relations.items())[:2]:
        print(f"  {name}: {json.dumps(relations, ensure_ascii=False, indent=2)[:300]}")
