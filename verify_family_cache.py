#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证缓存中的家庭数据识别问题
"""

import json

# 加载缓存
with open('output/analysis_results_cache.json', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 60)
print("缓存中的家庭数据验证")
print("=" * 60)

# 1. 检查 familySummary 是否存在
family_summary = data.get('familySummary', {})
print(f"\n1. familySummary 存在: {bool(family_summary)}")

if family_summary:
    # 2. 检查 family_units
    family_units = family_summary.get('family_units', [])
    print(f"\n2. family_units 数量: {len(family_units)}")
    
    if family_units:
        print("\n   家庭单元详情:")
        for i, unit in enumerate(family_units):
            print(f"   单元 {i+1}:")
            print(f"     - anchor: {unit.get('anchor', 'N/A')}")
            print(f"     - members: {unit.get('members', [])}")
            print(f"     - address: {unit.get('address', 'N/A')}")
    else:
        print("   ❌ family_units 为空!")
    
    # 3. 检查 family_relations
    family_relations = family_summary.get('family_relations', {})
    print(f"\n3. family_relations 数量: {len(family_relations)}")
    
    if family_relations:
        print("\n   家庭关系详情:")
        for person, relations in family_relations.items():
            print(f"   {person}:")
            for rel_type, names in relations.items():
                if names:
                    print(f"     - {rel_type}: {names}")
    else:
        print("   ❌ family_relations 为空!")
    
    # 4. 检查 family_tree
    family_tree = family_summary.get('family_tree', {})
    print(f"\n4. family_tree 数量: {len(family_tree)}")
    
    if family_tree:
        print("\n   家族树详情:")
        for person, members in family_tree.items():
            print(f"   {person}: {len(members)} 名成员")
            for member in members[:3]:  # 只显示前3个
                print(f"     - {member.get('姓名', 'N/A')} ({member.get('与户主关系', 'N/A')})")
            if len(members) > 3:
                print(f"     ... 还有 {len(members)-3} 名成员")
    else:
        print("   ❌ family_tree 为空!")
    
    # 5. 检查 family_members
    family_members = family_summary.get('family_members', [])
    print(f"\n5. family_members 数量: {len(family_members)}")
    print(f"   成员列表: {family_members}")
else:
    print("\n❌ familySummary 不存在或为空!")

# 6. 检查 profiles 中的人员
print("\n" + "=" * 60)
print("6. profiles 中的人员列表")
print("=" * 60)
profiles = data.get('profiles', {})
persons = [name for name in profiles.keys() if profiles[name].get('entityType') == 'person']
companies = [name for name in profiles.keys() if profiles[name].get('entityType') == 'company']
print(f"个人: {persons}")
print(f"公司: {companies}")

# 7. 检查是否有 analysis_cache 目录结构
print("\n" + "=" * 60)
print("7. 检查 analysis_cache 目录结构")
print("=" * 60)
import os
cache_dir = './output/analysis_cache'
if os.path.exists(cache_dir):
    print(f"analysis_cache 目录存在")
    files = os.listdir(cache_dir)
    print(f"目录内容: {files}")
else:
    print(f"❌ analysis_cache 目录不存在")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
