#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接生成报告并保存为HTML
模拟前端调用后端API
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from investigation_report_builder import InvestigationReportBuilder, load_investigation_report_builder
from report_config.primary_targets_service import PrimaryTargetsService

def main():
    print("=" * 80)
    print("直接生成HTML报告")
    print("=" * 80)
    
    # 1. 加载归集配置
    print("\n1. 加载归集配置...")
    service = PrimaryTargetsService(data_dir="./data", output_dir="./output")
    config, msg, is_new = service.get_or_create_config()
    
    if config is None:
        print(f"❌ 配置加载失败: {msg}")
        return
    
    print(f"✅ 配置加载成功: {len(config.analysis_units)} 个分析单元")
    
    # 2. 加载报告构建器
    print("\n2. 加载报告构建器...")
    builder = load_investigation_report_builder("./output")
    
    if builder is None:
        print("❌ 缓存数据不存在")
        return
    
    # 3. 设置配置
    builder.set_primary_config(config)
    
    # 4. 生成报告数据
    print("\n3. 生成报告数据 (build_report_v5)...")
    report = builder.build_report_v5(
        config=config,
        case_background=config.case_notes,
        data_scope=None,
    )
    
    print(f"✅ 报告数据生成完成")
    print(f"   - 家庭章节: {len(report.get('family_sections', []))}")
    print(f"   - 个人章节: {len(report.get('person_sections', []))}")
    print(f"   - 公司章节: {len(report.get('company_sections', []))}")
    
    # 5. 渲染HTML
    print("\n4. 渲染HTML模板...")
    html_content = builder.render_html_report_v3(report)
    
    print(f"✅ HTML渲染完成，长度: {len(html_content)} 字符")
    
    # 6. 保存到文件
    output_path = "./output/analysis_results/初查报告.html"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ 报告已保存: {output_path}")
    
    # 7. 返回HTML内容供查看
    return html_content, report

if __name__ == "__main__":
    html, report = main()
    
    # 打印摘要信息
    print("\n" + "=" * 80)
    print("报告生成完成!")
    print("=" * 80)
    print(f"\n文件路径: ./output/analysis_results/初查报告.html")
    print(f"HTML大小: {len(html)} 字符")
