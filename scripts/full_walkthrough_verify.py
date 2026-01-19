#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面走读验证脚本
验证所有核心指标的数据完整性
"""
import json
import os

def load_cache():
    with open('output/analysis_results_cache.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def verify_income_details(cache):
    """验证异常收入分析的8个子分类"""
    print("\n" + "=" * 70)
    print("【异常收入分析】全面验证")
    print("=" * 70)
    
    income_details = cache.get('analysisResults', {}).get('income', {}).get('details', [])
    
    # 按 _type 分组
    type_groups = {}
    for item in income_details:
        t = item.get('_type', 'unknown')
        if t not in type_groups:
            type_groups[t] = []
        type_groups[t].append(item)
    
    # 期望的8个分类
    expected_types = [
        ('high_risk', '高风险项目'),
        ('medium_risk', '中风险项目'),
        ('large_single', '大额单笔收入'),
        ('large_individual', '个人大额转入'),
        ('unknown_source', '来源不明收入'),
        ('same_source_multi', '同源多次收入'),
        ('regular_non_salary', '规律非工资收入'),
        ('bribe_installment', '疑似分期受贿'),
    ]
    
    all_passed = True
    issues = []
    
    for type_key, type_name in expected_types:
        items = type_groups.get(type_key, [])
        
        print(f"\n【{type_name}】({type_key}) - {len(items)} 条")
        print("-" * 50)
        
        if len(items) == 0:
            print("  ⚠️ 无数据")
            continue
        
        # 检查必要字段
        sample = items[0]
        
        # 检查1: 日期字段
        has_date = sample.get('date') or sample.get('first_date') or sample.get('first_income_date') or sample.get('date_range')
        date_value = sample.get('date') or sample.get('first_date') or sample.get('first_income_date')
        if type_key in ['same_source_multi', 'regular_non_salary', 'bribe_installment']:
            # 聚合类型可能没有单一日期
            date_check = "⚠️ 聚合类型(可接受)"
        elif has_date:
            date_check = f"✅ 有日期: {date_value}"
        else:
            date_check = "❌ 缺少日期"
            all_passed = False
            issues.append(f"{type_name}: 缺少日期字段")
        print(f"  日期: {date_check}")
        
        # 检查2: 描述/说明字段
        has_desc = sample.get('description') or sample.get('risk_reason') or sample.get('detail') or sample.get('reason')
        desc_value = sample.get('description') or sample.get('risk_reason') or sample.get('detail') or sample.get('reason') or ''
        if desc_value and str(desc_value) != 'nan' and desc_value != '(无)':
            desc_check = f"✅ 有描述: {str(desc_value)[:40]}..."
        else:
            desc_check = "❌ 缺少描述"
            all_passed = False
            issues.append(f"{type_name}: 缺少描述字段")
        print(f"  描述: {desc_check}")
        
        # 检查3: 溯源字段
        has_source_file = sample.get('source_file')
        has_source_row = sample.get('source_row_index') or sample.get('source_row')
        
        if has_source_file:
            print(f"  来源文件: ✅ {str(has_source_file)[:50]}")
        else:
            print(f"  来源文件: ❌ 缺失")
            all_passed = False
            issues.append(f"{type_name}: 缺少来源文件")
        
        if has_source_row is not None and has_source_row != 'None':
            print(f"  行号: ✅ {has_source_row}")
        elif type_key in ['same_source_multi']:
            print(f"  行号: ⚠️ 聚合类型无单一行号(可接受)")
        else:
            print(f"  行号: ❌ 缺失")
            if type_key not in ['same_source_multi']:
                issues.append(f"{type_name}: 缺少行号")
        
        # 显示样本数据
        print(f"  样本字段列表: {list(sample.keys())}")
    
    return all_passed, issues

def verify_loan_details(cache):
    """验证借贷风险分析的子分类"""
    print("\n" + "=" * 70)
    print("【借贷风险分析】全面验证")
    print("=" * 70)
    
    loan_details = cache.get('analysisResults', {}).get('loan', {}).get('details', [])
    
    # 按 _type 分组
    type_groups = {}
    for item in loan_details:
        t = item.get('_type', 'unknown')
        if t not in type_groups:
            type_groups[t] = []
        type_groups[t].append(item)
    
    expected_types = [
        ('bidirectional', '双向往来关系'),
        ('online_loan', '网贷平台交易'),
        ('regular_repayment', '规律还款模式'),
        ('no_repayment', '无还款借贷'),
        ('loan_pair', '借贷配对分析'),
        ('abnormal_interest', '异常利息检测'),
    ]
    
    all_passed = True
    issues = []
    
    for type_key, type_name in expected_types:
        items = type_groups.get(type_key, [])
        
        if len(items) == 0:
            continue
            
        print(f"\n【{type_name}】({type_key}) - {len(items)} 条")
        print("-" * 50)
        
        sample = items[0]
        
        # 检查溯源字段
        has_source_file = sample.get('source_file')
        has_source_row = sample.get('source_row_index') or sample.get('source_row')
        
        if has_source_file:
            print(f"  来源文件: ✅ {str(has_source_file)[:50]}")
        else:
            print(f"  来源文件: ❌ 缺失")
            all_passed = False
            issues.append(f"{type_name}: 缺少来源文件")
        
        if has_source_row is not None:
            print(f"  行号: ✅ {has_source_row}")
        else:
            print(f"  行号: ⚠️ 缺失")
        
        print(f"  样本字段列表: {list(sample.keys())}")
    
    return all_passed, issues

def verify_suspicions(cache):
    """验证疑点数据"""
    print("\n" + "=" * 70)
    print("【疑点数据】全面验证")
    print("=" * 70)
    
    suspicions = cache.get('suspicions', {})
    all_passed = True
    issues = []
    
    # 直接转账
    direct_transfers = suspicions.get('directTransfers', [])
    print(f"\n【核心人员往来】- {len(direct_transfers)} 条")
    if direct_transfers:
        sample = direct_transfers[0]
        print(f"  字段: {list(sample.keys())}")
        has_source = sample.get('sourceFile') or sample.get('source_file')
        has_row = sample.get('sourceRowIndex') or sample.get('source_row_index')
        print(f"  溯源: {'✅' if has_source else '❌'} 文件, {'✅' if has_row else '❌'} 行号")
    
    # 现金碰撞
    cash_collisions = suspicions.get('cashCollisions', [])
    print(f"\n【现金时空伴随】- {len(cash_collisions)} 条")
    if cash_collisions:
        sample = cash_collisions[0]
        print(f"  字段: {list(sample.keys())}")
    
    return all_passed, issues

def verify_frontend_mapping(cache):
    """验证前端字段映射覆盖"""
    print("\n" + "=" * 70)
    print("【前端字段映射】验证")
    print("=" * 70)
    
    # 读取 TabContent.tsx 检查字段映射
    tsx_path = 'dashboard/src/components/TabContent.tsx'
    if os.path.exists(tsx_path):
        with open(tsx_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键字段映射
        checks = [
            ('source_row_index', '行号字段'),
            ('source_file', '来源文件字段'),
            ('description', '描述字段'),
            ('formatAuditDateTime', '日期格式化'),
        ]
        
        print("\n前端代码检查:")
        for field, name in checks:
            if field in content:
                print(f"  ✅ {name} ({field}) - 已处理")
            else:
                print(f"  ❌ {name} ({field}) - 未找到")
    
    return True, []

def main():
    print("=" * 70)
    print("全面走读验证 - 开始")
    print("=" * 70)
    
    cache = load_cache()
    
    all_issues = []
    
    # 1. 验证异常收入
    passed1, issues1 = verify_income_details(cache)
    all_issues.extend(issues1)
    
    # 2. 验证借贷分析
    passed2, issues2 = verify_loan_details(cache)
    all_issues.extend(issues2)
    
    # 3. 验证疑点数据
    passed3, issues3 = verify_suspicions(cache)
    all_issues.extend(issues3)
    
    # 4. 验证前端映射
    passed4, issues4 = verify_frontend_mapping(cache)
    all_issues.extend(issues4)
    
    # 总结
    print("\n" + "=" * 70)
    print("验证总结")
    print("=" * 70)
    
    if not all_issues:
        print("\n✅ 所有验证通过！")
    else:
        print(f"\n❌ 发现 {len(all_issues)} 个问题:")
        for issue in all_issues:
            print(f"  - {issue}")
    
    return len(all_issues) == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
