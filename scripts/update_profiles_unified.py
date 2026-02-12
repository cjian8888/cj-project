#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
升级 profiles.json 为统一格式

将 profiles.json 从简化版升级为包含完整原始数据的统一格式，
这样报告生成器就不再需要同时维护 profiles.json 和 profiles_full.json。

使用方法:
    python scripts/update_profiles_unified.py
"""

import json
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def update_profiles_unified():
    """升级 profiles.json 为统一格式"""
    
    cache_dir = os.path.join('output', 'analysis_cache')
    simple_path = os.path.join(cache_dir, 'profiles.json')
    full_path = os.path.join(cache_dir, 'profiles_full.json')
    backup_path = os.path.join(cache_dir, 'profiles.json.backup')
    
    # 检查文件是否存在
    if not os.path.exists(simple_path):
        print(f"❌ 错误: {simple_path} 不存在")
        return False
    
    # 【2026-02-12 改进】profiles_full.json 已弃用
    # 如果 profiles_full.json 不存在，说明数据已经是统一格式
    if not os.path.exists(full_path):
        print(f"ℹ️  {full_path} 不存在")
        print("   说明 profiles.json 已经是统一格式，无需升级")
        return True
    
    try:
        # 读取简化版和完整版
        print(f"📖 读取简化版: {simple_path}")
        with open(simple_path, 'r', encoding='utf-8') as f:
            profiles_simple = json.load(f)
        
        print(f"📖 读取完整版: {full_path}")
        with open(full_path, 'r', encoding='utf-8') as f:
            profiles_full = json.load(f)
        
        # 创建备份
        print(f"💾 创建备份: {backup_path}")
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(profiles_simple, f, ensure_ascii=False, indent=2)
        
        # 合并数据：以完整版为基础，添加简化版的扁平字段
        profiles_unified = {}
        for name, full_data in profiles_full.items():
            simple_data = profiles_simple.get(name, {})
            
            # 创建统一格式：完整原始数据 + 前端扁平字段
            unified = dict(full_data)  # 复制完整数据
            
            # 添加/更新前端扁平字段（如果不存在）
            unified['entityName'] = simple_data.get('entityName', name)
            unified['totalIncome'] = simple_data.get('totalIncome', full_data.get('summary', {}).get('total_income', 0))
            unified['totalExpense'] = simple_data.get('totalExpense', full_data.get('summary', {}).get('total_expense', 0))
            unified['transactionCount'] = simple_data.get('transactionCount', full_data.get('summary', {}).get('transaction_count', 0))
            
            # 保留其他资产字段
            for key in ['properties', 'properties_precise', 'vehicles', 'wealth_products', 
                       'securities', 'insurance', 'bank_accounts_official']:
                if key in simple_data:
                    unified[key] = simple_data[key]
            
            profiles_unified[name] = unified
        
        # 保存统一版
        print(f"💾 保存统一版: {simple_path}")
        with open(simple_path, 'w', encoding='utf-8') as f:
            json.dump(profiles_unified, f, ensure_ascii=False, indent=2)
        
        # 统计信息
        print()
        print("✅ 升级完成!")
        print(f"   - 实体数量: {len(profiles_unified)}")
        
        # 验证数据
        first_person = list(profiles_unified.keys())[0]
        first_data = profiles_unified[first_person]
        print(f"   - 验证 {first_person}:")
        print(f"     * entityName (扁平): {first_data.get('entityName')}")
        print(f"     * totalIncome (扁平): {first_data.get('totalIncome')}")
        print(f"     * yearly_salary (完整): {'存在' if 'yearly_salary' in first_data else '缺失'}")
        print(f"     * summary (完整): {'存在' if 'summary' in first_data else '缺失'}")
        print(f"     * bank_accounts (完整): {'存在' if 'bank_accounts' in first_data else '缺失'}")
        
        # 可选：删除 profiles_full.json（如果不再需要）
        # os.remove(full_path)
        # print(f"   - 已删除: {full_path}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = update_profiles_unified()
    sys.exit(0 if success else 1)
