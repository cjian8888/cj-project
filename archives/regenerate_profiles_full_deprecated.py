#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性脚本：从完整缓存生成 profiles_full.json

此脚本从 analysis_results_cache.json 提取完整的 profiles 数据，
保存为 profiles_full.json 供报告构建器使用。

使用方法:
    python scripts/regenerate_profiles_full.py
"""

import json
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def regenerate_profiles_full():
    """从完整缓存生成 profiles_full.json"""
    
    # 路径配置
    cache_path = os.path.join('output', 'analysis_results_cache.json')
    output_dir = os.path.join('output', 'analysis_cache')
    output_path = os.path.join(output_dir, 'profiles_full.json')
    
    # 检查源文件是否存在
    if not os.path.exists(cache_path):
        print(f"❌ 错误: 源文件不存在: {cache_path}")
        return False
    
    try:
        # 读取完整缓存
        print(f"📖 读取完整缓存: {cache_path}")
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 提取 profiles 数据
        profiles = data.get('profiles', {})
        
        if not profiles:
            print("⚠️  警告: profiles 数据为空")
            return False
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存完整版 profiles
        print(f"💾 保存完整 profiles: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
        
        # 统计信息
        entity_count = len(profiles)
        total_bank_accounts = sum(
            len(p.get('bankAccounts', []))
            for p in profiles.values()
        )
        total_salary_entries = sum(
            len(p.get('yearlySalary', {}).get('details', []))
            for p in profiles.values()
        )
        
        print(f"✅ 成功生成 profiles_full.json")
        print(f"   - 实体数量: {entity_count}")
        print(f"   - 银行账户总数: {total_bank_accounts}")
        print(f"   - 工资记录总数: {total_salary_entries}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return False


if __name__ == '__main__':
    success = regenerate_profiles_full()
    sys.exit(0 if success else 1)
