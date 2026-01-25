#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据质量评分算法
验证修复后的评分逻辑是否正常工作
"""

import pandas as pd
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_validator import validate_transaction_data


def create_test_data_case_1():
    """
    测试用例1：高质量数据（少量警告，大量记录）
    预期：评分应该较高（>80分）
    """
    print("\n" + "="*60)
    print("测试用例1：高质量数据（1000条记录，5个警告）")
    print("="*60)
    
    data = {
        'date': pd.date_range('2024-01-01', periods=1000, freq='D'),
        'description': [f'交易{i}' for i in range(1000)],
        'income': [1000.0] * 1000,
        'expense': [0.0] * 1000,
        'balance': [10000.0 + i * 1000.0 for i in range(1000)]
    }
    df = pd.DataFrame(data)
    
    result = validate_transaction_data(df, '测试实体1')
    print(f"状态: {result['status']}")
    print(f"记录数: {result['record_count']}")
    print(f"质量评分: {result['quality_score']}")
    print(f"质量等级: {result['data_quality_label']}")
    print(f"警告数量: {len(result['warnings'])}")
    
    return result


def create_test_data_case_2():
    """
    测试用例2：低质量数据（大量警告，少量记录）
    预期：评分应该较低（<50分）
    """
    print("\n" + "="*60)
    print("测试用例2：低质量数据（50条记录，10个警告）")
    print("="*60)
    
    data = {
        'date': pd.date_range('2024-01-01', periods=50, freq='D'),
        'description': [f'交易{i}' for i in range(50)],
        'income': [1000.0] * 50,
        'expense': [0.0] * 50,
        'balance': [10000.0 + i * 1000.0 for i in range(50)]
    }
    df = pd.DataFrame(data)
    
    # 添加一些空值
    df.loc[10:15, 'balance'] = None
    df.loc[20:25, 'description'] = None
    
    result = validate_transaction_data(df, '测试实体2')
    print(f"状态: {result['status']}")
    print(f"记录数: {result['record_count']}")
    print(f"质量评分: {result['quality_score']}")
    print(f"质量等级: {result['data_quality_label']}")
    print(f"警告数量: {len(result['warnings'])}")
    
    return result


def create_test_data_case_3():
    """
    测试用例3：中等质量数据（中等警告，中等记录）
    预期：评分应该中等（50-80分）
    """
    print("\n" + "="*60)
    print("测试用例3：中等质量数据（200条记录，8个警告）")
    print("="*60)
    
    data = {
        'date': pd.date_range('2024-01-01', periods=200, freq='D'),
        'description': [f'交易{i}' for i in range(200)],
        'income': [1000.0] * 200,
        'expense': [0.0] * 200,
        'balance': [10000.0 + i * 1000.0 for i in range(200)]
    }
    df = pd.DataFrame(data)
    
    # 添加一些空值
    df.loc[30:40, 'balance'] = None
    
    result = validate_transaction_data(df, '测试实体3')
    print(f"状态: {result['status']}")
    print(f"记录数: {result['record_count']}")
    print(f"质量评分: {result['quality_score']}")
    print(f"质量等级: {result['data_quality_label']}")
    print(f"警告数量: {len(result['warnings'])}")
    
    return result


def create_test_data_case_4():
    """
    测试用例4：相同警告数，不同数据量
    验证数据量因素是否生效
    """
    print("\n" + "="*60)
    print("测试用例4：验证数据量因素（相同警告数，不同数据量）")
    print("="*60)
    
    # 小数据集：100条记录，5个警告
    data_small = {
        'date': pd.date_range('2024-01-01', periods=100, freq='D'),
        'description': [f'交易{i}' for i in range(100)],
        'income': [1000.0] * 100,
        'expense': [0.0] * 100,
        'balance': [10000.0 + i * 1000.0 for i in range(100)]
    }
    df_small = pd.DataFrame(data_small)
    df_small.loc[10:15, 'balance'] = None  # 5个警告
    
    result_small = validate_transaction_data(df_small, '小数据集')
    print(f"\n小数据集（100条记录，5个警告）:")
    print(f"  质量评分: {result_small['quality_score']}")
    print(f"  警告密度: {len(result_small['warnings'])/100*100:.2f}%")
    
    # 大数据集：1000条记录，5个警告
    data_large = {
        'date': pd.date_range('2024-01-01', periods=1000, freq='D'),
        'description': [f'交易{i}' for i in range(1000)],
        'income': [1000.0] * 1000,
        'expense': [0.0] * 1000,
        'balance': [10000.0 + i * 1000.0 for i in range(1000)]
    }
    df_large = pd.DataFrame(data_large)
    df_large.loc[100:105, 'balance'] = None  # 5个警告
    
    result_large = validate_transaction_data(df_large, '大数据集')
    print(f"\n大数据集（1000条记录，5个警告）:")
    print(f"  质量评分: {result_large['quality_score']}")
    print(f"  警告密度: {len(result_large['warnings'])/1000*100:.2f}%")
    
    print(f"\n验证结果: {'✓ 通过' if result_large['quality_score'] > result_small['quality_score'] else '✗ 失败'}")
    print(f"  大数据集评分应该更高（警告密度更低）")
    
    return result_small, result_large


def main():
    """运行所有测试用例"""
    print("\n" + "="*60)
    print("数据质量评分算法测试")
    print("="*60)
    
    results = []
    
    # 运行测试用例
    results.append(('测试用例1', create_test_data_case_1()))
    results.append(('测试用例2', create_test_data_case_2()))
    results.append(('测试用例3', create_test_data_case_3()))
    results.append(('测试用例4', create_test_data_case_4()))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, result in results:
        if isinstance(result, tuple):
            # 测试用例4返回两个结果
            continue
        print(f"\n{name}:")
        print(f"  评分: {result['quality_score']} ({result['data_quality_label']})")
        print(f"  状态: {result['status']}")
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == '__main__':
    main()
