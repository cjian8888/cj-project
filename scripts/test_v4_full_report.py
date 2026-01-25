#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 v4 完整报告生成

验证 build_report_v4() 方法生成完整报告的正确性
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from investigation_report_builder import load_investigation_report_builder


def test_v4_full_report():
    """测试 v4 完整报告生成"""
    print("=" * 60)
    print("测试 v4 完整报告生成")
    print("=" * 60)
    
    builder = load_investigation_report_builder('./output')
    if not builder:
        print("❌ 无法加载报告构建器")
        return False
    
    try:
        # 无配置调用（使用默认）
        report = builder.build_report_v4()
        
        print("\n✅ build_report_v4() 调用成功")
        print(f"\n报告版本: {report['meta']['version']}")
        print(f"生成时间: {report['meta']['generated_at']}")
        
        # 开篇引言
        preface = report.get('preface', {})
        print(f"\n【开篇引言】")
        print(f"  查询人员: {len(preface.get('persons_queried', []))} 人")
        print(f"  查询公司: {len(preface.get('companies_queried', []))} 家")
        print(f"  数据范围: {preface.get('data_period', '')}")
        
        # 个人章节
        person_sections = report.get('person_sections', [])
        print(f"\n【个人章节】 共 {len(person_sections)} 节")
        for section in person_sections[:2]:  # 只打印前2个
            name = section.get('name', '')
            salary = section.get('asset_income_section', {}).get('salary_income', {})
            print(f"  - {name}: 工资{salary.get('total_wan', 0):.2f}万元")
        
        # 公司章节
        company_sections = report.get('company_sections', [])
        print(f"\n【公司章节】 共 {len(company_sections)} 节")
        for cs in company_sections[:2]:
            print(f"  - {cs.get('company_name', '')}")
        
        # 综合研判
        conclusion = report.get('conclusion', {})
        print(f"\n【综合研判】")
        print(f"  发现问题: {conclusion.get('issue_count', 0)} 项")
        print(f"  研判意见: {conclusion.get('summary_narrative', '')}")
        
        # 下一步工作计划
        next_steps = report.get('next_steps', [])
        print(f"\n【下一步工作计划】 共 {len(next_steps)} 项")
        for step in next_steps[:3]:
            print(f"  - [{step.get('action_type', '')}] {step.get('action_text', '')[:50]}...")
        
        # 保存完整报告
        output_path = './output/report_v4.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✅ 完整报告已保存到: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_v4_full_report()
    print("\n" + "=" * 60)
    print("测试结果:", "✅ 通过" if success else "❌ 失败")
    print("=" * 60)
    sys.exit(0 if success else 1)
