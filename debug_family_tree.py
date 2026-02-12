#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查family_tree中的户籍数据
"""

import json

with open("./output/analysis_cache/derived_data.json", 'r', encoding='utf-8') as f:
    derived = json.load(f)

print("=" * 80)
print("family_tree 数据检查")
print("=" * 80)

family_tree = derived.get("family_tree", {})
print(f"\nfamily_tree 类型: {type(family_tree)}")
print(f"family_tree 键: {list(family_tree.keys()) if isinstance(family_tree, dict) else 'N/A'}")

if family_tree:
    for anchor, members in list(family_tree.items())[:2]:
        print(f"\n{'='*60}")
        print(f"户主: {anchor}")
        print(f"成员数量: {len(members) if isinstance(members, list) else 'N/A'}")
        
        if isinstance(members, list) and len(members) > 0:
            for m in members[:3]:
                print(f"\n  成员: {m.get('姓名', 'N/A')}")
                print(f"    性别: {m.get('性别', 'N/A')}")
                print(f"    出生日期: {m.get('出生日期', 'N/A')}")
                print(f"    籍贯: {m.get('籍贯', 'N/A')}")
                print(f"    从业单位: {m.get('从业单位', 'N/A')}")
                print(f"    所有字段: {list(m.keys())}")
