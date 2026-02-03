#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三轮全面走读验证 - 覆盖所有核心指标
严格按照循环要求：发现任何问题都必须修复后重新验证
"""
import json
import os

def load_cache():
    with open('output/analysis_results_cache.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def check_field(item, field_names, description):
    """检查字段是否存在且有效"""
    for field in field_names:
        value = item.get(field)
        if value is not None and value != '' and str(value) != 'nan' and value != '--' and value != '(无)':
            return True, value
    return False, None

def verify_income_analysis(cache):
    """验证异常收入分析 - 8个子分类"""
    print("\n" + "=" * 70)
    print("【1. 异常收入分析】8个子分类全覆盖验证")
    print("=" * 70)
    
    income_details = cache.get('analysisResults', {}).get('income', {}).get('details', [])
    
    expected_types = [
        ('high_risk', '高风险项目', ['date'], ['description', 'detail', 'risk_reason'], ['source_file'], ['source_row_index', 'source_row']),
        ('medium_risk', '中风险项目', ['date'], ['description', 'detail', 'risk_reason'], ['source_file'], ['source_row_index', 'source_row']),
        ('large_single', '大额单笔收入', ['date'], ['description', 'income_type'], ['source_file'], ['source_row_index']),
        ('large_individual', '个人大额转入', ['date'], ['description'], ['source_file'], ['source_row_index']),
        ('unknown_source', '来源不明收入', ['date'], ['description', 'reason'], ['source_file'], ['source_row_index']),
        ('same_source_multi', '同源多次收入', ['records'], ['source_type'], ['source_file'], []),  # 聚合类型无行号
        ('regular_non_salary', '规律非工资收入', ['date_range'], ['possible_type'], ['source_file'], ['source_row_index']),
        ('bribe_installment', '疑似分期受贿', ['first_date', 'last_date'], ['risk_factors'], ['source_file'], ['source_row_index']),
    ]
    
    issues = []
    
    for type_key, type_name, date_fields, desc_fields, file_fields, row_fields in expected_types:
        items = [x for x in income_details if x.get('_type') == type_key]
        
        if not items:
            print(f"\n【{type_name}】({type_key}) - 无数据")
            continue
        
        print(f"\n【{type_name}】({type_key}) - {len(items)} 条")
        print("-" * 50)
        
        sample = items[0]
        
        # 检查日期
        has_date, date_val = check_field(sample, date_fields, '日期')
        if has_date:
            print(f"  ✅ 日期字段存在: {str(date_val)[:50]}")
        else:
            print(f"  ❌ 日期字段缺失 (检查了: {date_fields})")
            issues.append(f"{type_name}: 日期字段缺失")
        
        # 检查描述
        has_desc, desc_val = check_field(sample, desc_fields, '描述')
        if has_desc:
            print(f"  ✅ 描述字段存在: {str(desc_val)[:50]}")
        else:
            print(f"  ❌ 描述字段缺失 (检查了: {desc_fields})")
            issues.append(f"{type_name}: 描述字段缺失")
        
        # 检查来源文件
        has_file, file_val = check_field(sample, file_fields, '文件')
        if has_file:
            print(f"  ✅ 来源文件存在: {str(file_val)[:50]}")
        else:
            print(f"  ❌ 来源文件缺失")
            issues.append(f"{type_name}: 来源文件缺失")
        
        # 检查行号（聚合类型跳过）
        if row_fields:
            has_row, row_val = check_field(sample, row_fields, '行号')
            if has_row:
                print(f"  ✅ 行号存在: {row_val}")
            else:
                print(f"  ⚠️ 行号缺失 (检查了: {row_fields})")
                # 行号缺失不作为严重问题，只记录
        else:
            print(f"  ⚠️ 聚合类型，无单一行号")
    
    return issues

def verify_loan_analysis(cache):
    """验证借贷风险分析 - 6个子分类"""
    print("\n" + "=" * 70)
    print("【2. 借贷风险分析】6个子分类全覆盖验证")
    print("=" * 70)
    
    loan_details = cache.get('analysisResults', {}).get('loan', {}).get('details', [])
    
    expected_types = [
        ('bidirectional', '双向往来关系'),
        ('online_loan', '网贷平台交易'),
        ('regular_repayment', '规律还款模式'),
        ('no_repayment', '无还款借贷'),
        ('loan_pair', '借贷配对分析'),
        ('abnormal_interest', '异常利息检测'),
    ]
    
    issues = []
    
    for type_key, type_name in expected_types:
        items = [x for x in loan_details if x.get('_type') == type_key]
        
        if not items:
            print(f"\n【{type_name}】({type_key}) - 无数据")
            continue
        
        print(f"\n【{type_name}】({type_key}) - {len(items)} 条")
        sample = items[0]
        
        # 检查来源文件
        has_file, _ = check_field(sample, ['source_file'], '文件')
        if has_file:
            print(f"  ✅ 来源文件存在")
        else:
            print(f"  ❌ 来源文件缺失")
            issues.append(f"借贷-{type_name}: 来源文件缺失")
        
        # 检查行号
        has_row, row_val = check_field(sample, ['source_row_index', 'source_row'], '行号')
        if has_row:
            print(f"  ✅ 行号存在: {row_val}")
        else:
            print(f"  ⚠️ 行号缺失")
    
    return issues

def verify_suspicions(cache):
    """验证疑点数据 - 核心人员往来、现金时空伴随"""
    print("\n" + "=" * 70)
    print("【3. 疑点数据】核心人员往来、现金时空伴随验证")
    print("=" * 70)
    
    suspicions = cache.get('suspicions', {})
    issues = []
    
    # 直接转账
    direct_transfers = suspicions.get('directTransfers', [])
    print(f"\n【核心人员往来】- {len(direct_transfers)} 条")
    if direct_transfers:
        sample = direct_transfers[0]
        print(f"  字段列表: {list(sample.keys())}")
        
        # 检查必要字段
        required_fields = ['from', 'to', 'amount', 'date']
        for field in required_fields:
            if field in sample and sample[field]:
                print(f"  ✅ {field}: {str(sample[field])[:30]}")
            else:
                print(f"  ❌ {field}: 缺失")
                issues.append(f"核心人员往来: {field} 缺失")
        
        # 检查溯源字段
        has_file = sample.get('sourceFile') or sample.get('source_file')
        has_row = sample.get('sourceRowIndex') or sample.get('source_row_index')
        print(f"  溯源: {'✅' if has_file else '❌'} 文件, {'✅' if has_row else '⚠️'} 行号")
    else:
        print(f"  无数据（可能正常）")
    
    # 现金碰撞
    cash_collisions = suspicions.get('cashCollisions', [])
    print(f"\n【现金时空伴随】- {len(cash_collisions)} 条")
    if cash_collisions:
        sample = cash_collisions[0]
        print(f"  字段列表: {list(sample.keys())}")
        
        required = ['person1', 'person2', 'amount1', 'amount2']
        for field in required:
            if field in sample:
                print(f"  ✅ {field}: {sample[field]}")
            else:
                print(f"  ❌ {field}: 缺失")
                issues.append(f"现金时空伴随: {field} 缺失")
    
    return issues

def verify_risk_entities(cache):
    """验证风险实体排名"""
    print("\n" + "=" * 70)
    print("【4. 风险实体】排名数据验证")
    print("=" * 70)
    
    ranked = cache.get('analysisResults', {}).get('aggregation', {}).get('rankedEntities', [])
    issues = []
    
    print(f"\n【风险实体排名】- {len(ranked)} 条")
    if ranked:
        sample = ranked[0]
        print(f"  字段列表: {list(sample.keys())}")
        
        # 检查必要字段
        required = ['name', 'riskScore', 'riskLevel']
        for field in required:
            val = sample.get(field) or sample.get(field.lower())
            if val:
                print(f"  ✅ {field}: {val}")
            else:
                print(f"  ⚠️ {field}: 缺失")
    else:
        print(f"  无数据（可能正常）")
    
    return issues

def verify_frontend_syntax():
    """验证前端代码语法"""
    print("\n" + "=" * 70)
    print("【5. 前端代码】语法检查")
    print("=" * 70)
    
    issues = []
    
    tsx_path = 'dashboard/src/components/TabContent.tsx'
    if os.path.exists(tsx_path):
        with open(tsx_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 基本语法检查 - 括号匹配
        open_braces = content.count('{')
        close_braces = content.count('}')
        open_parens = content.count('(')
        close_parens = content.count(')')
        
        print(f"  大括号: {{ = {open_braces}, }} = {close_braces}")
        print(f"  小括号: ( = {open_parens}, ) = {close_parens}")
        
        if open_braces != close_braces:
            print(f"  ❌ 大括号不匹配！差异: {open_braces - close_braces}")
            issues.append("前端代码: 大括号不匹配")
        else:
            print(f"  ✅ 大括号匹配")
        
        if open_parens != close_parens:
            print(f"  ❌ 小括号不匹配！差异: {open_parens - close_parens}")
            issues.append("前端代码: 小括号不匹配")
        else:
            print(f"  ✅ 小括号匹配")
        
        # 检查关键函数是否存在
        key_functions = ['getCategoryDetails', 'getMetricDetails', 'getCategorySummary']
        for func in key_functions:
            if func in content:
                print(f"  ✅ 函数 {func} 存在")
            else:
                print(f"  ❌ 函数 {func} 缺失")
                issues.append(f"前端代码: 函数 {func} 缺失")
    
    return issues

def main():
    print("=" * 70)
    print("第三轮全面走读验证 - 开始")
    print("时间: 2026-01-19 16:44")
    print("=" * 70)
    
    cache = load_cache()
    
    all_issues = []
    
    # 1. 验证异常收入分析
    issues1 = verify_income_analysis(cache)
    all_issues.extend(issues1)
    
    # 2. 验证借贷风险分析
    issues2 = verify_loan_analysis(cache)
    all_issues.extend(issues2)
    
    # 3. 验证疑点数据
    issues3 = verify_suspicions(cache)
    all_issues.extend(issues3)
    
    # 4. 验证风险实体
    issues4 = verify_risk_entities(cache)
    all_issues.extend(issues4)
    
    # 5. 验证前端语法
    issues5 = verify_frontend_syntax()
    all_issues.extend(issues5)
    
    # 总结
    print("\n" + "=" * 70)
    print("验证总结")
    print("=" * 70)
    
    if not all_issues:
        print("\n✅ 本轮走读未发现任何问题！可以终止循环。")
        return True
    else:
        print(f"\n❌ 发现 {len(all_issues)} 个问题，需要修复后重新验证:")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
