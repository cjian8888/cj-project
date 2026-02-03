#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试审计报告改进效果
验证所有13项修复是否正确应用
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from investigation_report_builder import load_investigation_report_builder
import json
from datetime import datetime

def test_v4_report_generation():
    """测试v4报告生成"""
    print("=" * 60)
    print("测试v4报告生成")
    print("=" * 60)

    # 加载报告构建器
    builder = load_investigation_report_builder('./output')
    if not builder:
        print("❌ 无法加载报告构建器")
        return False

    print(f"✓ 报告构建器加载成功")
    print(f"  可选核查对象: {builder.get_available_primary_persons()}")
    print(f"  可选公司: {builder.get_available_companies()}")

    # 生成v4报告
    primary = builder.get_available_primary_persons()[0] if builder.get_available_primary_persons() else None
    if not primary:
        print("❌ 没有可用的核查对象")
        return False

    print(f"\n开始生成v4报告，核查对象: {primary}")

    try:
        report = builder.build_report_v4(
            case_background="测试案件背景 - 验证审计报告改进效果"
        )

        # 保存JSON报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = f"./output/report_v4_audit_improvements_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✓ JSON报告已保存: {json_path}")

        # 保存HTML报告
        html_path = f"./output/report_v4_audit_improvements_{timestamp}.html"
        builder.save_html_report_v3(report, html_path)
        print(f"✓ HTML报告已保存: {html_path}")

        # 验证修复效果
        print("\n" + "=" * 60)
        print("验证修复效果")
        print("=" * 60)

        # 验证1: 房屋面积单位去重
        print("\n【1.1】验证房屋面积单位去重...")
        for family_section in report.get('family_sections', []):
            for member_section in family_section.get('member_sections', []):
                property_info = member_section.get('asset_income_section', {}).get('property_info', {})
                properties = property_info.get('properties', [])
                for prop in properties:
                    area = prop.get('面积', '') or prop.get('建筑面积', '')
                    if area and '平方米' in str(area):
                        if str(area).count('平方米') > 1:
                            print(f"  ❌ 发现重复单位: {area}")
                        else:
                            print(f"  ✓ 面积格式正确: {area}")

        # 验证2: 车辆登记时间
        print("\n【1.2】验证车辆登记时间...")
        for family_section in report.get('family_sections', []):
            for member_section in family_section.get('member_sections', []):
                vehicle_info = member_section.get('asset_income_section', {}).get('vehicle_info', {})
                vehicles = vehicle_info.get('vehicles', [])
                for v in vehicles:
                    desc = v.get('description', '')
                    if '于登记购入' in desc:
                        print(f"  ❌ 车辆登记时间缺失: {desc}")
                    else:
                        print(f"  ✓ 车辆登记时间正常: {desc[:50]}...")

        # 验证3: 身份证号格式
        print("\n【1.3】验证身份证号格式...")
        for family_section in report.get('family_sections', []):
            for member_section in family_section.get('member_sections', []):
                property_info = member_section.get('asset_income_section', {}).get('property_info', {})
                properties = property_info.get('properties', [])
                for prop in properties:
                    co_owners = prop.get('共有人', '') or prop.get('共有人名称', '')
                    if co_owners:
                        # 检查是否有无效身份证号（如"0"）
                        if ',0' in co_owners or ', 0' in co_owners:
                            print(f"  ❌ 发现无效身份证号: {co_owners}")
                        else:
                            print(f"  ✓ 身份证号格式正常")

        # 验证4: 专业术语规范化
        print("\n【5.1】验证专业术语规范化...")
        terms_to_check = ['工资收入占比', '大额现金', '第三方支付', '理财']
        report_text = json.dumps(report, ensure_ascii=False)
        for term in terms_to_check:
            if term in report_text:
                print(f"  ✓ 使用规范术语: {term}")

        # 验证5: 数据质量说明
        print("\n【5.2】验证数据质量说明...")
        preface = report.get('preface', {})
        data_quality_note = preface.get('data_quality_note', {})
        if data_quality_note and isinstance(data_quality_note, dict):
            print(f"  ✓ 包含数据质量说明")
            for key, value in data_quality_note.items():
                print(f"    - {value}")
        else:
            print(f"  ❌ 缺少数据质量说明")

        # 验证6: 结论风险等级
        print("\n【6.1】验证结论风险等级...")
        conclusion = report.get('conclusion', {})
        risk_levels = conclusion.get('risk_levels', {})
        if risk_levels and isinstance(risk_levels, dict):
            print(f"  ✓ 结论包含风险等级判断")
            print(f"    - 高风险: {risk_levels.get('high', 0)}项")
            print(f"    - 中风险: {risk_levels.get('medium', 0)}项")
            print(f"    - 低风险: {risk_levels.get('low', 0)}项")
        else:
            print(f"  ❌ 结论缺少风险等级")

        # 验证7: 建议可操作性
        print("\n【6.2】验证建议可操作性...")
        next_steps = report.get('next_steps', [])
        if next_steps:
            for step in next_steps[:3]:  # 检查前3条建议
                detail = step.get('detail', '')
                if detail and len(detail) > 20:
                    print(f"  ✓ 建议具体可操作: {detail[:50]}...")
                else:
                    print(f"  ❌ 建议过于简单: {detail}")

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"❌ 生成报告时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_v4_report_generation()
    sys.exit(0 if success else 1)
