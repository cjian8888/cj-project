#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 v4 专业报告格式输出

验证 build_v4_person_section() 方法的输出是否符合专业模版
"""

import json
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from investigation_report_builder import load_investigation_report_builder


def test_v4_person_section():
    """测试 v4 个人章节构建"""
    print("=" * 60)
    print("测试 v4 专业报告格式输出")
    print("=" * 60)
    
    # 加载报告构建器
    builder = load_investigation_report_builder('./output')
    if not builder:
        print("❌ 无法加载报告构建器，请确保已运行分析并生成缓存")
        return False
    
    # 获取可用的核查对象
    persons = builder.get_available_primary_persons()
    print(f"\n可用核查对象: {persons}")
    
    if not persons:
        print("❌ 无可用核查对象")
        return False
    
    # 测试第一个人员
    test_person = persons[0]
    print(f"\n测试对象: {test_person}")
    print("-" * 60)
    
    # 调用 v4 方法
    try:
        section = builder.build_v4_person_section(test_person, "本人")
        
        # 打印关键结构
        print("\n✅ build_v4_person_section() 调用成功")
        
        # 资产收入部分
        asset_income = section.get('asset_income_section', {})
        print("\n【资产收入情况】")
        
        # 工资收入
        salary = asset_income.get('salary_income', {})
        print(f"  工资总额: {salary.get('total_wan', 0):.2f} 万元")
        print(f"  年度数量: {salary.get('years_count', 0)} 年")
        print(f"  年度分拆: {salary.get('yearly_breakdown', [])}")
        print(f"  叙事文本: {salary.get('narrative', '')[:100]}...")
        
        # 银行存款
        bank_dep = asset_income.get('bank_deposits', {})
        print(f"\n  银行余额: {bank_dep.get('total_balance_wan', 0):.2f} 万元")
        print(f"  账户数量: {bank_dep.get('bank_count', 0)} 个")
        
        # 数据分析部分
        data_analysis = section.get('data_analysis_section', {})
        print("\n【数据分析】")
        
        # 收支匹配分析
        income_match = data_analysis.get('income_match_analysis', {})
        print(f"  总流入: {income_match.get('total_inflow', 0)/10000:.2f} 万元")
        print(f"  总流出: {income_match.get('total_outflow', 0)/10000:.2f} 万元")
        print(f"  工资占比: {income_match.get('salary_ratio', 0):.1f}%")
        print(f"  分析结论: {income_match.get('narrative', '')[:100]}...")
        
        # 大额存取现分析
        cash_analysis = data_analysis.get('large_cash_analysis', {})
        print(f"\n  现金收入: {cash_analysis.get('income', 0)/10000:.2f} 万元")
        print(f"  现金支出: {cash_analysis.get('expense', 0)/10000:.2f} 万元")
        print(f"  分析文本: {cash_analysis.get('narrative', '')}")
        
        # 大额转账分析
        transfer_analysis = data_analysis.get('large_transfer_analysis', {})
        print(f"\n  大额流入笔数: {transfer_analysis.get('inflow', {}).get('count', 0)}")
        print(f"  大额流出笔数: {transfer_analysis.get('outflow', {}).get('count', 0)}")
        
        # 保存完整输出
        output_path = './output/test_v4_section.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(section, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✅ 完整输出已保存到: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_v4_person_section()
    print("\n" + "=" * 60)
    print("测试结果:", "✅ 通过" if success else "❌ 失败")
    print("=" * 60)
    sys.exit(0 if success else 1)
