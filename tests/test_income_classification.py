#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收入分类单元测试 (2026-01-25 新增）
测试 financial_profiler.py 中的收入分类逻辑
"""

import pytest
import pandas as pd
from financial_profiler import classify_income_sources


def test_salary_income():
    """测试工资性收入识别"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 10000,
        'counterparty': '上海浦东新区财政局',
        'description': '代发工资',
        'income': 10000
    }
    
    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['legitimate_income'] == 10000
    assert result['legitimate_count'] == 1
    assert '工资' in result['legitimate_details'][0]['reason']


def test_government_income():
    """测试政府机关收入识别"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 5000,
        'counterparty': '上海市公积金中心',
        'description': '公积金',
        'income': 5000
    }
    
    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['legitimate_income'] == 5000
    assert result['legitimate_count'] == 1
    assert '政府' in result['legitimate_details'][0]['reason']


def test_pension_income():
    """测试养老金收入识别"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 8000,
        'counterparty': '社保局',
        'description': '职业年金',
        'income': 8000
    }
    
    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['legitimate_income'] == 8000
    assert result['legitimate_count'] == 1
    assert '养老金' in result['legitimate_details'][0]['reason']


def test_investment_income():
    """测试投资收益识别"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 50000,
        'counterparty': '申万宏源证券有限公司',
        'description': '理财赎回',
        'income': 50000
    }
    
    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['legitimate_income'] == 50000
    assert result['legitimate_count'] == 1
    assert '投资' in result['legitimate_details'][0]['reason']


def test_cash_deposit():
    """测试大额现金存入识别"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 100000,
        'counterparty': 'nan',
        'description': '现金存入',
        'income': 100000
    }
    
    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['suspicious_income'] == 100000
    assert result['suspicious_count'] == 1
    assert '现金' in result['suspicious_details'][0]['reason']


def test_loan_platform():
    """测试借贷平台识别"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 50000,
        'counterparty': '蚂蚁借呗',
        'description': '借款',
        'income': 50000
    }
    
    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['suspicious_income'] == 50000
    assert result['suspicious_count'] == 1
    assert '借贷' in result['suspicious_details'][0]['reason']


def test_personal_transfer():
    """测试个人转账识别"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 5000,
        'counterparty': '张三',
        'description': '转账',
        'income': 5000
    }
    
    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['unknown_income'] == 5000
    assert result['unknown_count'] == 1
    assert '个人转账' in result['unknown_details'][0]['reason']


def test_refund_income():
    """测试退款识别"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 1000,
        'counterparty': '某商户',
        'description': '退款',
        'income': 1000
    }
    
    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['legitimate_income'] == 1000
    assert result['legitimate_count'] == 1
    assert '退款' in result['legitimate_details'][0]['reason']


def test_empty_dataframe():
    """测试空DataFrame处理"""
    df = pd.DataFrame()
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['legitimate_income'] == 0
    assert result['unknown_income'] == 0
    assert result['suspicious_income'] == 0


def test_ratio_calculation():
    """测试比例计算"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-15'),
            'amount': 10000,
            'counterparty': '财政局',
            'description': '工资',
            'income': 10000
        },
        {
            'date': pd.Timestamp('2024-01-16'),
            'amount': 5000,
            'counterparty': '张三',
            'description': '转账',
            'income': 5000
        },
        {
            'date': pd.Timestamp('2024-01-17'),
            'amount': 5000,
            'counterparty': '李四',
            'description': '转账',
            'income': 5000
        }
    ]
    
    df = pd.DataFrame(transactions)
    result = classify_income_sources(df, entity_name='测试人员')
    
    total = 20000
    assert result['legitimate_ratio'] == 0.5  # 10000/20000
    assert result['unknown_ratio'] == 0.5  # 10000/20000
    assert result['suspicious_ratio'] == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
