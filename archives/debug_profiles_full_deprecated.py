#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查profiles_full.json的完整数据
"""

import json
import os

profiles_path = "./output/analysis_cache/profiles_full.json"
if os.path.exists(profiles_path):
    print(f"加载: {profiles_path}")
    print(f"文件大小: {os.path.getsize(profiles_path) / 1024 / 1024:.2f} MB")
    
    with open(profiles_path, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    print(f"\n人员数量: {len(profiles)}")
    print("\n" + "=" * 80)
    
    for name, profile in list(profiles.items())[:2]:
        print(f"\n姓名: {name}")
        print("-" * 40)
        
        # 工资数据
        print("【yearlySalary】")
        yearly_salary = profile.get("yearlySalary", {})
        if yearly_salary:
            print(f"  yearly: {yearly_salary.get('yearly', {})}")
            print(f"  summary: {yearly_salary.get('summary', {})}")
        else:
            print("  无工资数据")
        
        # 单位信息
        print("\n【id_info / 单位信息】")
        id_info = profile.get("id_info", {})
        if id_info:
            print(f"  employer: {id_info.get('employer', 'N/A')}")
            print(f"  从业单位: {id_info.get('从业单位', 'N/A')}")
        else:
            # 尝试其他字段
            employer = profile.get("employer", profile.get("从业单位", "N/A"))
            print(f"  employer (其他字段): {employer}")
        
        # 交易数据
        print("\n【transactions】")
        transactions = profile.get("transactions", [])
        if transactions:
            print(f"  数量: {len(transactions)}")
            if len(transactions) > 0:
                print(f"  示例: {transactions[0]}")
        else:
            print("  无交易数据")
        
        # 查看所有顶级键
        print(f"\n【所有字段】")
        print(f"  {list(profile.keys())}")
        
        print("\n" + "=" * 80)
else:
    print(f"文件不存在: {profiles_path}")
