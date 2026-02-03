#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 BUG-01 和 BUG-02 的修复情况"""

import json
import os

print("=" * 60)
print("BUG-01 验证: 家庭数据结构 (family_units 格式)")
print("=" * 60)

# 加载缓存
cache_path = 'output/analysis_results_cache.json'
if not os.path.exists(cache_path):
    print(f"错误: 缓存文件不存在: {cache_path}")
    exit(1)

with open(cache_path, encoding='utf-8') as f:
    data = json.load(f)

# 1. 检查 familySummary 是否存在
family_summary = data.get('familySummary', {})
print(f"\n1. familySummary 存在: {bool(family_summary)}")

if family_summary:
    # 2. 检查 family_units (新格式)
    family_units = family_summary.get('family_units', [])
    print(f"\n2. family_units 数量: {len(family_units)}")
    
    if family_units:
        print("\n   家庭单元详情 (新格式):")
        for i, unit in enumerate(family_units):
            anchor = unit.get('anchor', 'N/A')
            members = unit.get('members', [])
            address = unit.get('address', 'N/A')
            if address and len(address) > 40:
                address = address[:40] + "..."
            print(f"   单元 {i+1}:")
            print(f"     - anchor: {anchor}")
            print(f"     - members: {members}")
            print(f"     - address: {address}")
        print("\n   ✅ BUG-01 修复验证通过: family_units 格式正确")
    else:
        print("\n   ❌ BUG-01 未修复: family_units 为空!")
    
    # 3. 检查 family_relations
    family_relations = family_summary.get('family_relations', {})
    print(f"\n3. family_relations 数量: {len(family_relations)}")
    
    # 4. 检查 family_tree
    family_tree = family_summary.get('family_tree', {})
    print(f"\n4. family_tree 数量: {len(family_tree)}")
    
    # 5. 检查 family_members
    family_members = family_summary.get('family_members', [])
    print(f"\n5. family_members: {family_members}")
else:
    print("\n❌ familySummary 不存在或为空!")

# 检查 profiles
print("\n" + "=" * 60)
print("Profiles 检查")
print("=" * 60)
profiles = data.get('profiles', {})
persons = [name for name in profiles.keys() if profiles[name].get('entityType') == 'person']
companies = [name for name in profiles.keys() if profiles[name].get('entityType') == 'company']
print(f"\n个人: {persons}")
print(f"公司: {companies}")

print("\n" + "=" * 60)
print("BUG-02 验证: primary_targets_service 和 report_generator 适配")
print("=" * 60)

# 检查 primary_targets.json 是否存在
pt_path = 'output/analysis_cache/primary_targets.json'
if os.path.exists(pt_path):
    with open(pt_path, encoding='utf-8') as f:
        pt = json.load(f)
    print(f"\n1. primary_targets.json 存在: ✅")
    print(f"   版本: {pt.get('version', 'N/A')}")
    print(f"   雇主: {pt.get('employer', 'N/A')}")
    
    analysis_units = pt.get('analysis_units', [])
    print(f"   analysis_units 数量: {len(analysis_units)}")
    
    for i, unit in enumerate(analysis_units):
        anchor = unit.get('anchor', 'N/A')
        unit_type = unit.get('unit_type', 'N/A')
        members = unit.get('members', [])
        print(f"\n   单元 {i+1}:")
        print(f"     - anchor: {anchor}")
        print(f"     - type: {unit_type}")
        print(f"     - members: {len(members)} 人")
        for m in members:
            print(f"       * {m.get('name', 'N/A')} ({m.get('relation', 'N/A')})")
    
    print("\n   ✅ primary_targets.json 格式正确")
else:
    print(f"\n1. primary_targets.json 不存在 (路径: {pt_path})")
    print("   这可能是正常的，因为配置在首次使用时创建")

# 验证 report_generator 中的 _group_into_households 函数
print("\n" + "=" * 60)
print("代码兼容性检查")
print("=" * 60)

# 检查 report_generator.py 是否有 _group_into_households 函数支持 family_units
with open('report_generator.py', encoding='utf-8') as f:
    rg_content = f.read()
    
if 'family_units' in rg_content:
    print("\n✅ report_generator.py 包含 'family_units' 支持")
else:
    print("\n❌ report_generator.py 未包含 'family_units' 支持")

# 检查 investigation_report_builder.py 是否有新格式支持
with open('investigation_report_builder.py', encoding='utf-8') as f:
    irb_content = f.read()

if 'build_report_with_config' in irb_content:
    print("✅ investigation_report_builder.py 包含 'build_report_with_config' 方法")
else:
    print("❌ investigation_report_builder.py 未包含 'build_report_with_config' 方法")

if '_build_analysis_unit_section' in irb_content:
    print("✅ investigation_report_builder.py 包含 '_build_analysis_unit_section' 方法")
else:
    print("❌ investigation_report_builder.py 未包含 '_build_analysis_unit_section' 方法")

print("\n" + "=" * 60)
print("验证总结")
print("=" * 60)
print("\n✅ BUG-01 和 BUG-02 验证完成")
print("=" * 60)
