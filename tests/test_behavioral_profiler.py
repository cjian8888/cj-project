#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行为特征画像单元测试 (2026-01-25 新增）
测试 behavioral_profiler.py 中的行为检测逻辑
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from behavioral_profiler import (
    is_financial_product_transaction,
    filter_financial_transactions,
    detect_fast_in_out,
    detect_structuring,
    detect_dormant_activation
)


def test_financial_product_detection():
    """测试理财产品识别"""
    # 理财产品交易
    transaction = pd.Series({
        'counterparty': '申万宏源证券有限公司',
        'description': '理财赎回',
        'income': 50000,
        'expense': 0
    })
    
    assert is_financial_product_transaction(transaction) == True
    
    # 非理财产品交易
    transaction2 = pd.Series({
        'counterparty': '张三',
        'description': '转账',
        'income': 5000,
        'expense': 0
    })
    
    assert is_financial_product_transaction(transaction2) == False


def test_financial_keywords():
    """测试各种理财关键词"""
    keywords = [
        '理财', '基金', '证券', '申购', '赎回',
        '存管', '清算', '产品', '结构性存款',
        '华泰证券', '国泰君安', '海通证券',
        '招商证券', '中信证券', '广发证券',
        '汇添富', '易方达', '华夏基金', '嘉实基金'
    ]
    
    for keyword in keywords:
        transaction = pd.Series({
            'counterparty': keyword,
            'description': '交易',
            'income': 10000,
            'expense': 0
        })
        assert is_financial_product_transaction(transaction) == True


def test_filter_financial_transactions():
    """测试过滤理财交易"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-15'),
            'counterparty': '申万宏源证券',
            'description': '理财赎回',
            'income': 50000,
            'expense': 0
        },
        {
            'date': pd.Timestamp('2024-01-16'),
            'counterparty': '张三',
            'description': '转账',
            'income': 5000,
            'expense': 0
        },
        {
            'date': pd.Timestamp('2024-01-17'),
            'counterparty': '万联证券',
            'description': '基金申购',
            'income': 0,
            'expense': 30000
        }
    ]
    
    df = pd.DataFrame(transactions)
    filtered_df = filter_financial_transactions(df)
    
    # 应该只保留非理财交易
    assert len(filtered_df) == 1
    assert filtered_df.iloc[0]['counterparty'] == '张三'


def test_fast_in_out_detection():
    """测试快进快出检测"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-15 10:00:00'),
            'counterparty': '张三',
            'description': '转账',
            'income': 100000,
            'expense': 0,
            'balance': 100000
        },
        {
            'date': pd.Timestamp('2024-01-15 14:00:00'),
            'counterparty': '李四',
            'description': '转账',
            'income': 0,
            'expense': 99000,
            'balance': 1000
        }
    ]
    
    df = pd.DataFrame(transactions)
    patterns = detect_fast_in_out(df, exclude_financial=False)
    
    assert len(patterns) == 1
    assert patterns[0]['type'] == 'fast_in_out'
    assert patterns[0]['hours_diff'] == 4.0


def test_fast_in_out_with_financial_filter():
    """测试快进快出检测（排除理财）"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-15 10:00:00'),
            'counterparty': '申万宏源证券',
            'description': '理财赎回',
            'income': 100000,
            'expense': 0,
            'balance': 100000
        },
        {
            'date': pd.Timestamp('2024-01-15 14:00:00'),
            'counterparty': '某公司',
            'description': '转账',
            'income': 0,
            'expense': 99000,
            'balance': 1000
        }
    ]
    
    df = pd.DataFrame(transactions)
    
    # 不排除理财交易
    patterns_no_filter = detect_fast_in_out(df, exclude_financial=False)
    assert len(patterns_no_filter) == 1
    
    # 排除理财交易
    patterns_with_filter = detect_fast_in_out(df, exclude_financial=True)
    assert len(patterns_with_filter) == 0


def test_structuring_detection():
    """测试整进散出检测"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-15'),
            'counterparty': '某公司',
            'description': '收入',
            'income': 100000,
            'expense': 0
        },
        {
            'date': pd.Timestamp('2024-01-16'),
            'counterparty': '张三',
            'description': '转账',
            'income': 0,
            'expense': 30000
        },
        {
            'date': pd.Timestamp('2024-01-17'),
            'counterparty': '李四',
            'description': '转账',
            'income': 0,
            'expense': 30000
        },
        {
            'date': pd.Timestamp('2024-01-18'),
            'counterparty': '王五',
            'description': '转账',
            'income': 0,
            'expense': 40000
        }
    ]
    
    df = pd.DataFrame(transactions)
    patterns = detect_structuring(df, exclude_financial=False)
    
    assert len(patterns) == 1
    assert patterns[0]['type'] == 'large_in_split_out'
    assert patterns[0]['split_count'] == 3


def test_dormant_activation():
    """测试休眠激活检测"""
    transactions = [
        {
            'date': pd.Timestamp('2023-01-15'),
            'counterparty': '某公司',
            'description': '工资',
            'income': 10000,
            'expense': 0
        },
        {
            'date': pd.Timestamp('2024-01-15'),
            'counterparty': '某公司',
            'description': '大额转账',
            'income': 100000,
            'expense': 0
        }
    ]
    
    df = pd.DataFrame(transactions)
    patterns = detect_dormant_activation(df)
    
    assert len(patterns) == 1
    assert patterns[0]['type'] == 'dormant_activation'
    assert patterns[0]['dormant_days'] >= 180


def test_empty_dataframe():
    """测试空DataFrame处理"""
    df = pd.DataFrame()
    
    assert len(filter_financial_transactions(df)) == 0
    assert len(detect_fast_in_out(df)) == 0
    assert len(detect_structuring(df)) == 0
    assert len(detect_dormant_activation(df)) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
