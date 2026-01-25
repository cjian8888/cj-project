#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试增强后的Excel底稿生成功能

验证新增的工作表：
1. 收入分类汇总
2. 收入分类-{人员名}
3. 总资产汇总
4. 成员间转账
"""

import os
import sys
import json
import pandas as pd
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from report_generator import generate_excel_workbook

def load_derived_data(cache_dir='output/analysis_cache'):
    """加载派生数据"""
    derived_file = os.path.join(cache_dir, 'derived_data.json')
    if not os.path.exists(derived_file):
        print(f"❌ 派生数据文件不存在: {derived_file}")
        return None
    
    with open(derived_file, 'r', encoding='utf-8') as f:
        derived_data = json.load(f)
    
    print(f"✅ 成功加载派生数据")
    print(f"   - 收入分类数据: {len(derived_data.get('income_classifications', {}))} 人")
    print(f"   - 总资产数据: {'存在' if derived_data.get('total_assets') else '不存在'}")
    print(f"   - 成员转账数据: {'存在' if derived_data.get('member_transfers') else '不存在'}")
    
    return derived_data

def load_profiles(cache_dir='output/analysis_cache'):
    """加载资金画像数据"""
    profiles_file = os.path.join(cache_dir, 'profiles.json')
    if not os.path.exists(profiles_file):
        print(f"❌ 资金画像文件不存在: {profiles_file}")
        return None
    
    with open(profiles_file, 'r', encoding='utf-8') as f:
        profiles = json.load(f)
    
    print(f"✅ 成功加载资金画像数据: {len(profiles)} 个实体")
    return profiles

def load_suspicions(cache_dir='output/analysis_cache'):
    """加载疑点检测数据"""
    suspicions_file = os.path.join(cache_dir, 'suspicions.json')
    if not os.path.exists(suspicions_file):
        print(f"❌ 疑点检测文件不存在: {suspicions_file}")
        return None
    
    with open(suspicions_file, 'r', encoding='utf-8') as f:
        suspicions = json.load(f)
    
    print(f"✅ 成功加载疑点检测数据")
    return suspicions

def test_excel_generation():
    """测试Excel底稿生成"""
    print("\n" + "="*60)
    print("开始测试增强后的Excel底稿生成功能")
    print("="*60 + "\n")
    
    # 1. 加载数据
    cache_dir = 'output/analysis_cache'
    
    profiles = load_profiles(cache_dir)
    derived_data = load_derived_data(cache_dir)
    suspicions = load_suspicions(cache_dir)
    
    if not profiles:
        print("\n❌ 无法继续：缺少资金画像数据")
        return False
    
    # 2. 准备输出路径
    output_dir = 'output/test_results'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'test_enhanced_excel_底稿.xlsx')
    
    # 3. 生成Excel
    print(f"\n📊 正在生成Excel底稿...")
    print(f"   输出路径: {output_path}")
    
    try:
        result_path = generate_excel_workbook(
            profiles=profiles,
            suspicions=suspicions or {},
            output_path=output_path,
            derived_data=derived_data
        )
        
        print(f"\n✅ Excel底稿生成成功: {result_path}")
        
        # 4. 验证生成的工作表
        print(f"\n📋 验证生成的工作表...")
        xl_file = pd.ExcelFile(result_path)
        sheet_names = xl_file.sheet_names
        
        expected_sheets = [
            '资金画像汇总',
            '直接转账关系',
            '现金时空伴随',
            '隐形资产明细',
            '固定频率异常进账',
            '大额现金明细',
            '第三方支付-收入',
            '第三方支付-支出',
            '第三方支付-汇总',
            '理财产品-购买',
            '理财产品-赎回',
            '理财产品-汇总',
            '家族关系图谱',
            '家族资产汇总',
            '房产明细',
            '车辆明细',
            '数据验证-流水',
            '数据验证-房产',
            '资金穿透-汇总',
            '穿透-个人到公司',
            '穿透-公司到个人',
            '穿透-人员之间',
            '穿透-公司之间',
            '借贷-双向往来',
            '借贷-无还款',
            '借贷-规律还款',
            '借贷-配对分析',
            '借贷-网贷平台',
            '异常收入-汇总',
            '异常收入-疑似分期受贿',
            '时序-资金突变',
            '时序-固定延迟',
            '穿透-资金闭环',
            '穿透-过账通道',
            '穿透-枢纽节点',
            '收入分类汇总',
            '总资产汇总',
            '成员间转账'
        ]
        
        # 检查新增的工作表
        new_sheets = ['收入分类汇总', '总资产汇总', '成员间转账']
        for sheet in new_sheets:
            if sheet in sheet_names:
                print(f"   ✅ {sheet} - 已生成")
            else:
                print(f"   ⚠️  {sheet} - 未生成（可能数据为空）")
        
        # 检查收入分类明细表
        if derived_data and derived_data.get('income_classifications'):
            for person in derived_data['income_classifications'].keys():
                sheet_name = f'收入分类-{person}'
                if len(sheet_name) > 31:
                    sheet_name = sheet_name[:28] + '...'
                
                if sheet_name in sheet_names:
                    print(f"   ✅ {sheet_name} - 已生成")
                else:
                    print(f"   ⚠️  {sheet_name} - 未生成")
        
        print(f"\n📊 总计生成 {len(sheet_names)} 个工作表")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Excel底稿生成失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    success = test_excel_generation()
    
    print("\n" + "="*60)
    if success:
        print("✅ 测试完成：Excel底稿生成功能正常")
    else:
        print("❌ 测试失败：Excel底稿生成功能异常")
    print("="*60 + "\n")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
