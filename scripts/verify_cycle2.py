#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二轮走读验证 - 模拟前端数据转换后验证
"""
import json

def load_cache():
    with open('output/analysis_results_cache.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def simulate_frontend_transform(item, category_type):
    """模拟前端的 getCategoryDetails 转换逻辑"""
    desc_raw = item.get('description') or item.get('risk_reason') or item.get('reason') or ''
    
    if category_type == 'large_single':
        description = item.get('income_type') or (desc_raw if desc_raw and desc_raw != 'nan' else '大额单笔收入')
    elif category_type == 'large_individual':
        description = desc_raw if desc_raw and desc_raw != 'nan' else f"来自个人: {item.get('from_individual') or item.get('counterparty') or '未知'}"
    elif category_type == 'same_source_multi':
        description = f"{item.get('source_type') or '多次转入'}, 共{item.get('count') or 0}次"
    elif category_type == 'regular_non_salary':
        description = item.get('possible_type') or f"规律性收入, 共{item.get('occurrences') or 0}次"
    elif category_type == 'bribe_installment':
        factors = item.get('risk_factors') or []
        description = '; '.join(factors[:2]) if factors else f"疑似分期, 共{item.get('occurrences') or 0}期"
    else:
        description = desc_raw if desc_raw and desc_raw != 'nan' else '--'
    
    # 日期处理
    date_value = item.get('date') or item.get('first_income_date') or item.get('first_date')
    if not date_value and item.get('date_range'):
        dr = item.get('date_range')
        date_value = dr[0] if isinstance(dr, list) else dr
    if not date_value and item.get('records') and isinstance(item.get('records'), list) and len(item.get('records')) > 0:
        # 从 records 数组中获取第一个日期
        date_value = item.get('records')[0].get('date') or item.get('records')[0].get('time')
    if not date_value:
        date_value = item.get('last_date')
    
    return {
        'name': item.get('person') or item.get('receiver') or '未知',
        'counterparty': item.get('source') or item.get('counterparty') or item.get('payer') or item.get('from_individual') or '--',
        'amount': item.get('amount') or item.get('avg_amount') or item.get('total_amount') or item.get('total') or item.get('income_amount') or 0,
        'date': date_value,
        'description': description,
        'source_file': item.get('source_file'),
        'source_row_index': item.get('source_row_index'),
    }

def verify_all(cache):
    """验证所有类型"""
    print("=" * 70)
    print("第二轮走读验证 - 模拟前端转换")
    print("=" * 70)
    
    income_details = cache.get('analysisResults', {}).get('income', {}).get('details', [])
    
    types_to_check = [
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
    
    for type_key, type_name in types_to_check:
        items = [x for x in income_details if x.get('_type') == type_key]
        
        if not items:
            continue
        
        print(f"\n【{type_name}】({type_key}) - {len(items)} 条")
        print("-" * 50)
        
        # 模拟前端转换
        sample_raw = items[0]
        sample = simulate_frontend_transform(sample_raw, type_key)
        
        # 验证
        checks = []
        
        # 日期
        if sample['date']:
            checks.append(f"✅ 日期: {sample['date']}")
        else:
            checks.append(f"❌ 日期: 缺失")
            all_passed = False
        
        # 描述
        if sample['description'] and sample['description'] != '--':
            checks.append(f"✅ 描述: {sample['description'][:40]}...")
        else:
            checks.append(f"❌ 描述: 缺失")
            all_passed = False
        
        # 溯源
        if sample['source_file']:
            checks.append(f"✅ 文件: {str(sample['source_file'])[:30]}...")
        else:
            checks.append(f"❌ 文件: 缺失")
            all_passed = False
        
        if sample['source_row_index'] is not None:
            checks.append(f"✅ 行号: {sample['source_row_index']}")
        elif type_key in ['same_source_multi']:
            checks.append(f"⚠️ 行号: 聚合类型无单一行号")
        else:
            checks.append(f"❌ 行号: 缺失")
        
        for c in checks:
            print(f"  {c}")
    
    # 借贷分析
    loan_details = cache.get('analysisResults', {}).get('loan', {}).get('details', [])
    
    loan_types = [
        ('bidirectional', '双向往来'),
        ('online_loan', '网贷平台'),
        ('regular_repayment', '规律还款'),
        ('no_repayment', '无还款借贷'),
    ]
    
    print("\n" + "=" * 70)
    print("【借贷风险分析】验证")
    print("=" * 70)
    
    for type_key, type_name in loan_types:
        items = [x for x in loan_details if x.get('_type') == type_key]
        if not items:
            continue
        
        sample = items[0]
        print(f"\n【{type_name}】- {len(items)} 条")
        
        has_file = '✅' if sample.get('source_file') else '❌'
        has_row = '✅' if sample.get('source_row_index') is not None else '⚠️'
        print(f"  溯源: {has_file} 文件, {has_row} 行号")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有验证通过！")
    else:
        print("⚠️ 存在部分问题")
    print("=" * 70)
    
    return all_passed

if __name__ == "__main__":
    cache = load_cache()
    verify_all(cache)
