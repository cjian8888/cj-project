#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面数据和报告审计脚本
"""
import json
import os
import sys
sys.path.insert(0, '.')

def audit_cache_data():
    """审计缓存数据一致性"""
    print("=" * 60)
    print("【审计1】数据一致性审计")
    print("=" * 60)
    
    cache_dir = './output/analysis_cache'
    issues = []
    
    # 加载数据
    try:
        with open(os.path.join(cache_dir, 'profiles.json'), 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        with open(os.path.join(cache_dir, 'derived_data.json'), 'r', encoding='utf-8') as f:
            derived_data = json.load(f)
        with open(os.path.join(cache_dir, 'metadata.json'), 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"❌ 无法加载缓存文件: {e}")
        return []
    
    print(f"缓存版本: {metadata.get('version', '未知')}")
    print(f"生成时间: {metadata.get('generatedAt', '未知')}")
    print(f"人员数量: {len(metadata.get('persons', []))}")
    print(f"公司数量: {len(metadata.get('companies', []))}")
    print()
    
    # 检查 profiles 数据完整性
    print("【检查点1.1】Profiles 数据完整性")
    for name, profile in profiles.items():
        entity_type = profile.get('entityType', 'unknown')
        income = profile.get('totalIncome', 0) or 0
        expense = profile.get('totalExpense', 0) or 0
        tx_count = profile.get('transactionCount', 0) or 0
        
        print(f"  {name} ({entity_type}): 收入={income/10000:.2f}万, 支出={expense/10000:.2f}万, 交易数={tx_count}")
        
        # 检查异常情况
        if income == 0 and expense == 0 and tx_count > 0:
            issues.append(f"数据异常: {name} 有 {tx_count} 条交易但收支为0")
        if income < 0 or expense < 0:
            issues.append(f"数据异常: {name} 存在负值 (收入={income}, 支出={expense})")
    
    # 检查 family_summary
    print()
    print("【检查点1.2】Family Summary 一致性")
    family_summary = derived_data.get('family_summary', {})
    if family_summary:
        fs_members = family_summary.get('family_members', [])
        fs_income = family_summary.get('total_income_expense', {}).get('total_income', 0)
        fs_expense = family_summary.get('total_income_expense', {}).get('total_expense', 0)
        
        print(f"  家庭成员: {fs_members}")
        print(f"  家庭总收入: {fs_income/10000:.2f}万")
        print(f"  家庭总支出: {fs_expense/10000:.2f}万")
        
        # 验证一致性
        expected_income = sum(profiles.get(m, {}).get('totalIncome', 0) or 0 for m in fs_members)
        expected_expense = sum(profiles.get(m, {}).get('totalExpense', 0) or 0 for m in fs_members)
        income_diff = abs(fs_income - expected_income)
        expense_diff = abs(fs_expense - expected_expense)
        
        if income_diff < 1:
            print(f"  ✅ 收入一致性: 通过 (差异={income_diff:.2f})")
        else:
            print(f"  ❌ 收入一致性: 失败 (差异={income_diff:.2f})")
            issues.append(f"family_summary 收入与 profiles 不一致: 差异={income_diff:.2f}")
        
        if expense_diff < 1:
            print(f"  ✅ 支出一致性: 通过 (差异={expense_diff:.2f})")
        else:
            print(f"  ❌ 支出一致性: 失败 (差异={expense_diff:.2f})")
            issues.append(f"family_summary 支出与 profiles 不一致: 差异={expense_diff:.2f}")
    else:
        print("  ❌ family_summary 为空!")
        issues.append("derived_data 中 family_summary 为空")
    
    # 检查分析结果
    print()
    print("【检查点1.3】分析结果完整性")
    loan = derived_data.get('loan', {})
    income_analysis = derived_data.get('income', {})
    
    loan_summary = loan.get('summary', {})
    print(f"  借贷分析: 双向往来={loan_summary.get('双向往来关系数', 0)}, 网贷={loan_summary.get('网贷平台交易数', 0)}")
    
    income_summary = income_analysis.get('summary', {})
    print(f"  收入分析: 规律非工资={income_summary.get('规律性非工资收入', 0)}")
    
    return issues

def audit_report_files():
    """审计报告文件完整性"""
    print()
    print("=" * 60)
    print("【审计2】报告文件审计")
    print("=" * 60)
    
    issues = []
    results_dir = './output/analysis_results'
    
    if not os.path.exists(results_dir):
        print(f"❌ 报告目录不存在: {results_dir}")
        issues.append("报告目录不存在")
        return issues
    
    # 列出所有报告文件
    print("【检查点2.1】报告文件列表")
    report_files = []
    for f in os.listdir(results_dir):
        filepath = os.path.join(results_dir, f)
        if os.path.isfile(filepath):
            size = os.path.getsize(filepath)
            report_files.append((f, size))
            print(f"  {f}: {size/1024:.1f} KB")
    
    # 检查必要报告
    print()
    print("【检查点2.2】必要报告检查")
    required_reports = ['资金核查底稿.xlsx']
    for required in required_reports:
        found = any(f[0] == required for f in report_files)
        if found:
            print(f"  ✅ {required}")
        else:
            print(f"  ❌ {required} 缺失")
            issues.append(f"必要报告缺失: {required}")
    
    # 检查 HTML 报告
    html_reports = [f for f in report_files if f[0].endswith('.html')]
    print()
    print(f"【检查点2.3】HTML 报告: {len(html_reports)} 个")
    for name, size in html_reports:
        if size < 1000:
            print(f"  ⚠️ {name}: 文件过小 ({size} bytes)")
            issues.append(f"HTML报告文件过小: {name}")
        else:
            print(f"  ✅ {name}: {size/1024:.1f} KB")
    
    return issues

def audit_report_content():
    """审计报告内容质量"""
    print()
    print("=" * 60)
    print("【审计3】报告内容审计")
    print("=" * 60)
    
    issues = []
    
    # 查找最新的 HTML 报告
    results_dir = './output/analysis_results'
    html_files = [f for f in os.listdir(results_dir) if f.endswith('.html')]
    
    if not html_files:
        print("❌ 无 HTML 报告可审计")
        issues.append("无HTML报告")
        return issues
    
    # 选择最新的报告
    latest_html = sorted(html_files)[-1]
    html_path = os.path.join(results_dir, latest_html)
    
    print(f"审计报告: {latest_html}")
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"  文件大小: {len(content)/1024:.1f} KB")
    print(f"  总字符数: {len(content)}")
    
    # 检查关键内容
    print()
    print("【检查点3.1】关键内容检查")
    
    checks = [
        ('标题', '<title>'),
        ('样式表', '<style>'),
        ('表格', '<table'),
        ('金额数据', '元'),
        ('日期数据', '2'),
    ]
    
    for name, pattern in checks:
        count = content.count(pattern)
        if count > 0:
            print(f"  ✅ {name}: 出现 {count} 次")
        else:
            print(f"  ⚠️ {name}: 未找到")
    
    # 检查占位符残留
    print()
    print("【检查点3.2】占位符检查")
    placeholders = ['{{', '}}', 'TODO', 'FIXME', 'undefined', 'null', 'NaN']
    for ph in placeholders:
        count = content.count(ph)
        if count > 0:
            print(f"  ⚠️ 占位符 '{ph}': 出现 {count} 次")
            if ph in ['undefined', 'null', 'NaN']:
                issues.append(f"报告中存在异常值: {ph}")
        else:
            print(f"  ✅ 无 '{ph}'")
    
    return issues

def audit_report_builder():
    """审计报告构建器功能"""
    print()
    print("=" * 60)
    print("【审计4】报告构建器功能审计")
    print("=" * 60)
    
    issues = []
    
    try:
        from investigation_report_builder import load_investigation_report_builder
        
        builder = load_investigation_report_builder('./output')
        if not builder:
            print("❌ 无法加载报告构建器")
            issues.append("报告构建器加载失败")
            return issues
        
        print("✅ 报告构建器加载成功")
        print(f"  Profiles: {len(builder.profiles)} 个")
        print(f"  Derived Data 键: {list(builder.derived_data.keys())[:5]}...")
        print(f"  身份证映射: {len(builder._id_to_name_map)} 条")
        
        # 测试报告生成
        print()
        print("【检查点4.1】测试报告生成")
        members = list(builder.profiles.keys())[:3]
        if members:
            anchor = members[0]
            summary = builder._build_family_summary_v4(anchor, members)
            print(f"  测试成员: {members}")
            print(f"  生成收入: {summary.get('total_income', 0)/10000:.2f}万")
            print(f"  生成支出: {summary.get('total_expense', 0)/10000:.2f}万")
            
            # 验证
            expected = sum(builder.profiles.get(m, {}).get('totalIncome', 0) or 0 for m in members)
            diff = abs(summary.get('total_income', 0) - expected)
            if diff < 1:
                print(f"  ✅ 计算一致性: 通过")
            else:
                print(f"  ❌ 计算一致性: 差异={diff:.2f}")
                issues.append(f"报告生成计算不一致: 差异={diff:.2f}")
        
    except Exception as e:
        print(f"❌ 报告构建器审计失败: {e}")
        issues.append(f"报告构建器审计异常: {e}")
    
    return issues

def main():
    print("=" * 60)
    print("  资金穿透审计系统 - 全面后台审计")
    print("  审计时间: 2026-02-03")
    print("=" * 60)
    print()
    
    all_issues = []
    
    # 执行各项审计
    all_issues.extend(audit_cache_data())
    all_issues.extend(audit_report_files())
    all_issues.extend(audit_report_content())
    all_issues.extend(audit_report_builder())
    
    # 汇总
    print()
    print("=" * 60)
    print("【审计汇总】")
    print("=" * 60)
    
    if all_issues:
        print(f"❌ 发现 {len(all_issues)} 个问题:")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("✅ 审计通过，未发现问题")
    
    # 保存审计结果
    result = {
        'audit_time': '2026-02-03',
        'issues_count': len(all_issues),
        'issues': all_issues,
        'status': 'PASS' if not all_issues else 'ISSUES_FOUND'
    }
    
    with open('./output/audit_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"审计结果已保存到: ./output/audit_result.json")
    
    return all_issues

if __name__ == '__main__':
    main()
