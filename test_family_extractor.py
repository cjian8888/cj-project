#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试家庭关系提取（验证从业单位字段）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from family_analyzer import extract_family_from_census

# 测试提取
data_directory = "./data"
person_name = "施灵"

print("=" * 60)
print(f"测试提取 {person_name} 的户籍数据")
print("=" * 60)

members = extract_family_from_census(data_directory, person_name)

print(f"\n提取到 {len(members)} 名成员:")
for m in members:
    print(f"\n  姓名: {m.get('姓名')}")
    print(f"  性别: {m.get('性别')}")
    print(f"  出生日期: {m.get('出生日期')}")
    print(f"  籍贯: {m.get('籍贯')}")
    print(f"  从业单位: {m.get('从业单位')}")
    print(f"  职业: {m.get('职业')}")
    print(f"  所有字段: {list(m.keys())}")
