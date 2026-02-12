#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速更新family_tree数据（仅更新从业单位等字段）
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from family_analyzer import build_family_tree

# 加载现有缓存
with open("./output/analysis_cache/derived_data.json", 'r', encoding='utf-8') as f:
    derived_data = json.load(f)

print("开始重新构建family_tree...")

# 从现有数据获取核心人员列表
family_tree_old = derived_data.get("family_tree", {})
core_persons = list(family_tree_old.keys())
print(f"核心人员: {core_persons}")

# 重新构建family_tree（使用修复后的提取函数）
data_directory = "./data"
family_tree_new = build_family_tree(core_persons, data_directory)

# 更新derived_data
derived_data["family_tree"] = family_tree_new

# 保存回文件
with open("./output/analysis_cache/derived_data.json", 'w', encoding='utf-8') as f:
    json.dump(derived_data, f, ensure_ascii=False, indent=2)

print("\n✅ family_tree已更新!")

# 验证
print("\n验证更新结果:")
for person, members in family_tree_new.items():
    print(f"\n{person}:")
    for m in members[:2]:  # 只显示前2个成员
        print(f"  - {m.get('姓名')}: 从业单位={m.get('从业单位', 'N/A')}, 籍贯={m.get('籍贯', 'N/A')}")
