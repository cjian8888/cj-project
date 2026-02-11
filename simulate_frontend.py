#!/usr/bin/env python3
"""
完整模拟前端生成报告流程
"""
import sys
import json
sys.path.insert(0, '.')
from investigation_report_builder import load_investigation_report_builder
from report_config.primary_targets_service import PrimaryTargetsService

print("=" * 80)
print("【模拟前端】报告生成流程")
print("=" * 80)

# 1. 加载配置（模拟前端获取配置）
print("\n1. 加载归集配置...")
service = PrimaryTargetsService(data_dir='./data', output_dir='./output')
config, msg, is_new = service.get_or_create_config()
print(f"   ✓ 配置加载成功: {len(config.analysis_units)} 个分析单元")
for i, unit in enumerate(config.analysis_units):
    print(f"      单元{i+1}: {unit.anchor} - {unit.members}")

# 2. 加载报告构建器
print("\n2. 加载报告构建器...")
builder = load_investigation_report_builder('./output')
print(f"   ✓ Builder加载成功")
print(f"      - 核心人员: {builder._core_persons}")
print(f"      - 公司: {builder._companies}")

# 3. 设置配置
print("\n3. 设置用户配置...")
builder.set_primary_config(config)

# 4. 生成V5报告（模拟前端调用 /api/investigation-report/generate-with-config）
print("\n4. 生成V5报告...")
report = builder.build_report_v5(config=config)
print(f"   ✓ 报告生成成功")
print(f"   报告结构: {list(report.keys())}")

# 5. 检查报告数据结构
print("\n" + "=" * 80)
print("【报告数据结构检查】")
print("=" * 80)

# 5.1 Meta信息
meta = report.get("meta", {})
print(f"\n5.1 Meta信息:")
print(f"   文号: {meta.get('doc_number')}")
print(f"   案件背景: {meta.get('case_background')[:50]}...")
print(f"   核心人员: {meta.get('core_persons')}")
print(f"   公司: {[c[:10]+'...' for c in meta.get('companies', [])]}")

# 5.2 PART A: 家庭核查部分
print(f"\n5.2 PART A - 家庭核查部分:")
family_sections = report.get("family_sections", [])
print(f"   家庭数量: {len(family_sections)}")
for i, fs in enumerate(family_sections):
    print(f"\n   家庭{i+1}: {fs.get('family_name')}")
    print(f"      - 成员: {fs.get('members')}")
    print(f"      - 成员数: {fs.get('member_count')}")
    summary = fs.get('family_summary', {})
    print(f"      - 总收入: {summary.get('total_income', 0)/10000:.2f} 万元")
    print(f"      - 总支出: {summary.get('total_expense', 0)/10000:.2f} 万元")
    print(f"      - 成员详情数: {len(fs.get('member_sections', []))}")

# 5.3 PART B: 个人核查部分
print(f"\n5.3 PART B - 个人核查部分:")
person_sections = report.get("person_sections", [])
print(f"   个人数量: {len(person_sections)}")
for i, ps in enumerate(person_sections):
    name = ps.get('name')
    relation = ps.get('relation')
    asset = ps.get('asset_income_section', {})
    bank = asset.get('bank_deposits', {})
    print(f"\n   {i+1}. {name} ({relation})")
    print(f"      - 银行卡数: {bank.get('bank_count', 0)}")
    print(f"      - 总余额: {bank.get('total_balance', 0):,.2f} 元")
    print(f"      - 账户详情数: {len(bank.get('accounts', []))}")

# 6. 模拟前端渲染HTML
print("\n" + "=" * 80)
print("【模拟前端渲染HTML】")
print("=" * 80)

def render_html(report):
    meta = report.get("meta", {})
    family_sections = report.get("family_sections", [])
    person_sections = report.get("person_sections", [])
    
    format_wan = lambda x: f"{((x or 0) / 10000):.2f}"
    format_currency = lambda x: f"{x or 0:,.0f}"
    
    primary_family = family_sections[0] if family_sections else {}
    family_summary = primary_family.get("family_summary", {})
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>初查报告</title>
    <style>
        body {{ font-family: 'SimSun', serif; margin: 40px; line-height: 1.8; }}
        .header {{ text-align: center; margin-bottom: 40px; border-bottom: 2px solid #333; padding-bottom: 20px; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ font-size: 18px; border-left: 4px solid #c00; padding-left: 10px; margin-bottom: 20px; }}
        .section h3 {{ font-size: 14px; margin: 20px 0 10px 0; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 12px; }}
        th, td {{ border: 1px solid #999; padding: 8px; text-align: left; }}
        th {{ background: #f0f0f0; font-weight: bold; }}
        .summary-box {{ background: #f8f9fa; padding: 20px; border-radius: 4px; margin: 20px 0; border: 1px solid #ddd; }}
        .amount {{ text-align: right; font-family: 'Consolas', monospace; }}
        .highlight {{ color: #c00; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>资金穿透核查初查报告</h1>
        <div style="font-size: 14px; color: #666;">
            生成时间: {meta.get('generated_at', '')[:10] if meta.get('generated_at') else '2026-02-11'}
        </div>
    </div>

    <div class="section">
        <h2>一、核查对象</h2>
        <p><strong>核心人员:</strong> {', '.join(meta.get('core_persons', []))}</p>
        <p><strong>涉及公司:</strong> {', '.join([c[:15]+'...' if len(c)>15 else c for c in meta.get('companies', [])])}</p>
    </div>

    <div class="section">
        <h2>二、家庭概况 ({primary_family.get('family_name', '')})</h2>
        <div class="summary-box">
            <strong>家庭资产汇总</strong><br>
            总收入: <span class="highlight">{format_wan(family_summary.get('total_income', 0))} 万元</span> | 
            总支出: <span class="highlight">{format_wan(family_summary.get('total_expense', 0))} 万元</span> | 
            工资占比: {family_summary.get('salary_ratio', 0):.1f}%<br>
            银行存款: {format_wan(family_summary.get('total_bank_balance', 0))} 万元 |
            成员数: {family_summary.get('member_count', 0)} 人
        </div>
        <table>
            <tr><th>关系</th><th>姓名</th><th>有数据</th></tr>
            {''.join([f"<tr><td>{m.get('relation', '-')}</td><td>{m.get('name', '-')}</td><td>{'✓' if m.get('has_data') else '✗'}</td></tr>" for m in primary_family.get('member_sections', [])])}
        </table>
    </div>
"""
    
    # 添加个人详情
    for ps in person_sections:
        name = ps.get('name', '')
        relation = ps.get('relation', '')
        asset = ps.get('asset_income_section', {})
        bank = asset.get('bank_deposits', {})
        
        html += f"""
    <div class="section">
        <h2>三、{name} ({relation}) 资金分析</h2>
        
        <h3>3.1 银行存款情况</h3>
        <p>共 <span class="highlight">{bank.get('bank_count', 0)}</span> 张银行卡，
           总余额 <span class="highlight">{format_currency(bank.get('total_balance', 0))}</span> 元</p>
        
        <table>
            <tr><th>序号</th><th>银行</th><th>卡号</th><th>账户类型</th><th>余额</th></tr>
            {''.join([f"<tr><td>{i+1}</td><td>{acc.get('反馈单位', acc.get('bank_name', '-'))}</td><td>{acc.get('卡号', acc.get('account_number', '-'))}</td><td>{acc.get('账户类别', acc.get('account_type', '-'))}</td><td class='amount'>{format_currency(acc.get('账户余额', acc.get('balance', 0)))}</td></tr>" for i, acc in enumerate(bank.get('accounts', [])[:5])])}
        </table>
        {(f"<p style='color: #888;'>... 共 {bank.get('bank_count', 0)} 张卡，仅显示前5张</p>" if bank.get('bank_count', 0) > 5 else "")}
    </div>
"""
    
    html += """
</body>
</html>"""
    return html

# 生成HTML
html = render_html(report)

# 保存HTML
output_path = "output/analysis_results/模拟前端生成报告.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n✅ HTML报告已生成: {output_path}")
print(f"   文件大小: {len(html)} 字符")

# 打印HTML预览
print("\n" + "=" * 80)
print("【生成的HTML预览 - 前2000字符】")
print("=" * 80)
print(html[:2000])
print("\n... [省略后续内容] ...")
