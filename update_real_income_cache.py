#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新缓存中的真实收入数据（修复版）

此脚本读取现有的 profiles.json，使用修复后的 _calculate_real_income_expense
重新计算真实收入，并更新到缓存中。
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from financial_profiler import _calculate_real_income_expense

def update_profiles_cache():
    """更新 profiles 缓存中的真实收入数据"""
    
    cache_path = os.path.join('output', 'analysis_cache', 'profiles.json')
    
    if not os.path.exists(cache_path):
        print(f"❌ 缓存文件不存在: {cache_path}")
        return False
    
    print(f"📖 读取缓存: {cache_path}")
    with open(cache_path, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    print(f"   共 {len(profiles)} 个实体")
    print()
    
    update_count = 0
    
    for name, profile in profiles.items():
        # 只处理个人（有 yearly_salary 的是个人）
        if 'yearly_salary' not in profile:
            continue
        
        summary = profile.get('summary', {})
        income_structure = profile.get('income_structure', {})
        wealth_mgmt = profile.get('wealth_management', {})
        fund_flow = profile.get('fund_flow', {})
        
        # 检查是否已有 offset_detail（已修复的数据）
        if 'offset_detail' in summary:
            print(f"⏭️  {name}: 已修复，跳过")
            continue
        
        # 重新计算真实收入
        try:
            real_income, real_expense, offset_detail = _calculate_real_income_expense(
                income_structure, wealth_mgmt, fund_flow
            )
            
            # 更新 summary
            old_real = summary.get('real_income', 0)
            summary['real_income'] = real_income
            summary['real_expense'] = real_expense
            summary['offset_detail'] = offset_detail
            
            # 同时更新扁平化字段（用于前端展示）
            profile['realIncome'] = real_income
            profile['realExpense'] = real_expense
            
            print(f"✅ {name}:")
            print(f"   旧真实收入: {old_real/10000:.2f}万")
            print(f"   新真实收入: {real_income/10000:.2f}万")
            print(f"   差异: {(real_income - old_real)/10000:.2f}万")
            print(f"   工资: {profile.get('yearly_salary', {}).get('summary', {}).get('total', 0)/10000:.2f}万")
            print(f"   剔除: {offset_detail['total_offset']/10000:.2f}万")
            print()
            
            update_count += 1
            
        except Exception as e:
            print(f"❌ {name}: 计算失败 - {e}")
            continue
    
    # 保存更新后的缓存
    print(f"💾 保存更新后的缓存...")
    backup_path = cache_path + '.backup_before_fix'
    
    # 创建备份
    if not os.path.exists(backup_path):
        os.rename(cache_path, backup_path)
        print(f"   备份已创建: {backup_path}")
    
    # 保存新数据
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    
    print(f"   缓存已更新: {cache_path}")
    print()
    print(f"✅ 完成! 共更新 {update_count} 个实体的真实收入数据")
    
    return True

if __name__ == '__main__':
    success = update_profiles_cache()
    sys.exit(0 if success else 1)
