#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证报告生成流程

使用步骤：
1. 运行完整分析（生成缓存）
2. 生成前端HTML报告（使用缓存）
3. 验证HTML报告中的财务数据
"""

import asyncio
import logging
import os
import json
import re
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

print("="*80)
print("报告生成流程验证")
print("="*80)
print()


async def test_full_analysis():
    """步骤1：运行完整分析"""
    print("【步骤1】运行完整分析...")
    
    from api_server import AnalysisConfig, run_analysis_refactored
    
    config = AnalysisConfig(
        inputDirectory="data",
        outputDirectory="output",
        cashThreshold=50000,
        modules=None,
    )
    
    results = run_analysis_refactored(config)
    
    print(f"✓ 分析完成")
    print(f"  结果键: {list(results.keys())}")
    print(f"  家庭汇总: {results.get('analysisResults', {}).get('family_summary', {})}")
    print()
    
    # 检查缓存文件
    cache_dir = Path("output/analysis_cache")
    print("【步骤1.5】检查缓存文件...")
    print(f"  缓存目录: {cache_dir.absolute()}")
    
    required_files = [
        "profiles.json",
        "derived_data.json",
        "graph_data.json",
    ]
    
    for filename in required_files:
        file_path = cache_dir / filename
        if file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            print(f"    ✓ {filename} ({size_kb:.2f} KB)")
        else:
            print(f"    ✗ {filename} (不存在)")
    
    print()


async def test_frontend_report():
    """步骤2：通过前端API生成HTML报告"""
    print("【步骤2】通过前端API生成HTML报告...")
    
    import urllib.request
    
    # API 端点
    api_url = "http://localhost:8888/api/investigation-report/generate-with-config"
    
    try:
        import urllib.request, ssl(timeout=600) as client:
            response = await client.post(
                api_url,
                json={
                    "case_background": "测试报告",
                    "data_scope": "",
                },
                headers={"Content-Type": "application/json"},
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("success"):
                    print("✓ API 调用成功")
                    
                    if result.get("report"):
                        report = result["report"]
                        print(f"  报告结构: {list(report.keys())}")
                        
                        # 检查家庭财务数据
                        family = report.get("family", {})
                        family_summary = family.get("summary", {})
                        
                        print(f"  家庭汇总字段: {list(family_summary.keys())}")
                        
                        if "total_income" in family_summary:
                            income = family_summary["total_income"]
                            print(f"    ✓ 总收入: ¥{income:.2f} 万元")
                        else:
                            print(f"    ✗ 缺少 total_income")
                        
                        if "total_expense" in family_summary:
                            expense = family_summary["total_expense"]
                            print(f"    ✓ 总支出: ¥{expense:.2f} 万元")
                        else:
                            print(f"    ✗ 缺少 total_expense")
                        
                        if "net_flow" in family_summary:
                            net = family_summary["net_flow"]
                            print(f"    ✓ 净流入: ¥{net:.2f} 万元")
                        else:
                            print(f"    ✗ 缺少 net_flow")
                        
                else:
                    print(f"✗ API 返回错误: {result.get('error', 'Unknown error')}")
                    
            else:
                print(f"✗ HTTP 错误: {response.status_code}")
                
    except Exception as e:
        print(f"✗ API 调用失败: {e}")


async def test_html_file():
    """步骤3：检查生成的HTML文件"""
    print("【步骤3】检查生成的HTML文件...")
    
    html_path = Path("output/analysis_results/初查报告.html")
    
    if not html_path.exists():
        print(f"  ✗ HTML 文件不存在: {html_path}")
        return
    
    size_kb = html_path.stat().st_size / 1024
    print(f"  ✓ HTML 文件存在: {html_path}")
    print(f"  文件大小: {size_kb:.2f} KB")
    
    # 检查 HTML 内容
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # 检查财务数据
    import re
    
    # 查找总收入
    income_match = re.search(r'资金总流入[^>]*>[^<]*([0-9,.]+)\s*万元', html_content)
    if income_match:
        income_value = income_match.group(1)
        if float(income_value) > 0:
            print(f"  ✓ 总收入: ¥{income_value} 万元")
        else:
            print(f"  ❌ 总收入为 0")
    else:
        print(f"  ❌ 未找到总收入字段")
    
    # 查找总支出
    expense_match = re.search(r'资金总流出[^>]*>[^<]*([0-9,.]+)\s*万元', html_content)
    if expense_match:
        expense_value = expense_match.group(1)
        if float(expense_value) > 0:
            print(f"  ✓ 总支出: ¥{expense_value} 万元")
        else:
            print(f"  ❌ 总支出为 0")
    else:
        print(f"  ❌ 未找到总支出字段")
    
    # 查找净流入
    net_match = re.search(r'对外净流入[^>]*>[^<]*([0-9,.]+)\s*万元', html_content)
    if net_match:
        net_value = net_match.group(1)
        print(f"  ✓ 净流入: ¥{net_value} 万元")
    else:
        print(f"  ❌ 未找到净流入字段")
    
    print()


async def main():
    """主函数"""
    print()
    print("="*80)
    print("开始验证...")
    print("="*80)
    print()
    
    try:
        # 步骤1：运行完整分析（跳过，耗时太长）
        # await test_full_analysis()
        
        # 步骤2：通过前端API生成HTML报告
        await test_frontend_report()
        
        # 步骤3：检查生成的HTML文件
        await test_html_file()
        
        print()
        print("="*80)
        print("验证完成！")
        print("="*80)
        print()
        print("【总结】")
        print(" 如果所有检查都通过（✓），说明修复成功")
        print(" 如果有 ✗ 标记，说明需要进一步修复")
        print()
        
    except Exception as e:
        print(f"验证失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
