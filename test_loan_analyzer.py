#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
借贷行为分析模块 - 单元测试
测试新增的高级分析功能
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import loan_analyzer
import utils

def create_test_data():
    """创建测试数据"""
    
    # 测试场景1: 正常借贷（有借有还）
    test_data_1 = pd.DataFrame([
        {
            'date': datetime(2024, 1, 15),
            'counterparty': '张三',
            'income': 50000,
            'expense': 0,
            'description': '借款'
        },
        {
            'date': datetime(2024, 7, 15),
            'counterparty': '张三',
            'income': 0,
            'expense': 52000,
            'description': '还款'
        }
    ])
    
    # 测试场景2: 无还款借贷（疑似利益输送）
    test_data_2 = pd.DataFrame([
        {
            'date': datetime(2023, 1, 1),
            'counterparty': '李四',
            'income': 100000,
            'expense': 0,
            'description': '大额收入'
        }
    ])
    
    # 测试场景3: 高利贷
    test_data_3 = pd.DataFrame([
        {
            'date': datetime(2024, 1, 1),
            'counterparty': '王五',
            'income': 30000,
            'expense': 0,
            'description': '借入'
        },
        {
            'date': datetime(2024, 4, 1),
            'counterparty': '王五',
            'income': 0,
            'expense': 36000,
            'description': '还款'
        }
    ])
    
    # 合并测试数据
    all_data = pd.concat([test_data_1, test_data_2, test_data_3], ignore_index=True)
    
    return {
        '朱明': all_data
    }

def test_loan_analyzer():
    """测试借贷分析器"""
    
    print('='*60)
    print('借贷行为分析模块 - 单元测试')
    print('='*60)
    print()
    
    # 创建测试数据
    test_transactions = create_test_data()
    core_persons = ['朱明']
    
    # 执行分析
    print('开始执行借贷行为分析...')
    print()
    
    results = loan_analyzer.analyze_loan_behaviors(
        test_transactions,
        core_persons
    )
    
    # 打印结果
    print()
    print('='*60)
    print('测试结果汇总')
    print('='*60)
    print()
    
    for key, value in results['summary'].items():
        print(f'{key}: {value}')
    
    print()
    print('-'*60)
    print('借贷配对详情')
    print('-'*60)
    
    if results['loan_pairs']:
        for i, pair in enumerate(results['loan_pairs'], 1):
            print(f"\n{i}. {pair['person']} ↔ {pair['counterparty']}")
            print(f"   借入: {pair['loan_date'].strftime('%Y-%m-%d')} {pair['loan_amount']:,.0f}元")
            print(f"   还款: {pair['repay_date'].strftime('%Y-%m-%d')} {pair['repay_amount']:,.0f}元")
            print(f"   周期: {pair['days']}天")
            print(f"   年化利率: {pair['annual_rate']:.1f}%")
            print(f"   风险: {pair['risk_reason']}")
    else:
        print('未发现借贷配对')
    
    print()
    print('-'*60)
    print('无还款借贷详情')
    print('-'*60)
    
    if results['no_repayment_loans']:
        for i, loan in enumerate(results['no_repayment_loans'], 1):
            print(f"\n{i}. {loan['person']} ← {loan['counterparty']}")
            print(f"   收入: {loan['income_date'].strftime('%Y-%m-%d')} {loan['income_amount']:,.0f}元")
            print(f"   距今: {loan['days_since']}天")
            print(f"   还款比例: {loan['repay_ratio']*100:.1f}%")
            print(f"   风险: {loan['risk_reason']}")
    else:
        print('未发现无还款借贷')
    
    print()
    print('-'*60)
    print('异常利息详情')
    print('-'*60)
    
    if results['abnormal_interest']:
        for i, item in enumerate(results['abnormal_interest'], 1):
            print(f"\n{i}. {item['person']} ↔ {item['counterparty']}")
            print(f"   金额: {item['loan_amount']:,.0f}元")
            print(f"   年化利率: {item['annual_rate']:.1f}%")
            print(f"   异常类型: {item['abnormal_type']}")
    else:
        print('未发现异常利息')
    
    print()
    print('='*60)
    print('测试完成！')
    print('='*60)
    
    return results

if __name__ == '__main__':
    test_loan_analyzer()
