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
        'description': '利息收入',
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
    assert result['suspicious_details'][0]['rule_bucket'] == 'cash_large'


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
    assert result['unknown_details'][0]['rule_bucket'] == 'individual_transfer'


def test_insurance_income_by_counterparty():
    """测试保险机构对手方即使摘要为空也能识别"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 4288.74,
        'counterparty': '中国平安财产保险股份有限公司',
        'description': '-',
        'income': 4288.74,
        'category': '投资理财',
        'account_type': '借记卡',
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['legitimate_income'] == 4288.74
    assert result['unknown_income'] == 0
    assert result['legitimate_details'][0]['reason'] == '保险赔付/返还'
    assert result['legitimate_details'][0]['rule_bucket'] == 'insurance_income'


def test_insurance_agent_payment_remains_insurance_income():
    """测试保险代理赔付款经支付通道入账时仍识别为保险"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 200,
        'counterparty': '携程保险代理有限公司',
        'description': '（特约）携程保代（代付接口机票赔付款）',
        'income': 200,
        'category': '投资理财',
        'account_type': '借记卡',
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['legitimate_income'] == 200
    assert result['legitimate_details'][0]['reason'] == '保险赔付/返还'


def test_wealth_redemption_fallback_is_excluded():
    """测试带理财产品编码的回款会作为待拆分理财回款剔除"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 60000,
        'counterparty': '',
        'description': '0191190017现金添利3号',
        'income': 60000,
        'category': '其他',
        'account_type': '借记卡',
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['excluded_income'] == 60000
    assert result['unknown_income'] == 0
    assert result['excluded_breakdown']['wealth_redemption'] == 60000
    assert result['excluded_details'][0]['rule_bucket'] == 'wealth_redemption'


def test_securities_transfer_is_excluded_as_wealth_redemption():
    """测试证转银/第三方存管回款会兜底剔除"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 100000,
        'counterparty': '中国银河证券股份有限公司（客户）',
        'description': '第三方存管保证金转活期',
        'income': 100000,
        'category': '投资理财',
        'account_type': '对公结算账户',
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['excluded_income'] == 100000
    assert result['excluded_breakdown']['wealth_redemption'] == 100000


def test_atm_cash_deposit_small_is_not_source_unknown():
    """测试ATM/CRS存款会被识别为现金存入而非来源不明"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 9800,
        'counterparty': 'nan',
        'description': 'ATM存款',
        'income': 9800,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['unknown_income'] == 9800
    assert result['unknown_details'][0]['reason'] == '小额现金存入'
    assert result['unknown_details'][0]['rule_bucket'] == 'cash_small'


def test_blank_large_income_gets_structured_unknown_reason():
    """测试对手方和摘要双空的大额入账单列为空白字段大额入账"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 20000,
        'counterparty': 'nan',
        'description': 'nan',
        'income': 20000,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['unknown_income'] == 20000
    assert result['unknown_details'][0]['reason'] == '空白字段大额入账'
    assert result['unknown_details'][0]['rule_bucket'] == 'blank_large'


def test_blank_frequent_income_gets_structured_unknown_reason():
    """测试双空白且重复出现的小额入账会被标记为高频结构化入账"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-15'),
            'amount': 30,
            'counterparty': 'nan',
            'description': 'nan',
            'income': 30,
        },
        {
            'date': pd.Timestamp('2024-01-16'),
            'amount': 30,
            'counterparty': 'nan',
            'description': 'nan',
            'income': 30,
        },
        {
            'date': pd.Timestamp('2024-01-17'),
            'amount': 30,
            'counterparty': 'nan',
            'description': 'nan',
            'income': 30,
        },
    ]

    df = pd.DataFrame(transactions)
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['unknown_income'] == 90
    assert result['unknown_details'][0]['reason'] == '空白字段高频入账'
    assert result['unknown_details'][0]['rule_bucket'] == 'blank_frequent'


def test_refund_income():
    """测试退款会从真实收入分类中剔除"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 1000,
        'counterparty': '某商户',
        'description': '退款',
        'income': 1000
    }
    
    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['legitimate_income'] == 0
    assert result['excluded_income'] == 1000
    assert result['excluded_count'] == 1
    assert '退款' in result['excluded_details'][0]['reason']


def test_business_reimbursement_income():
    """测试单位报销/业务往来款从真实收入分类中剔除"""
    transactions = [
        {
            'date': pd.Timestamp('2024-03-29'),
            'amount': 4210,
            'counterparty': '上海爱斯达克汽车空调系统有限公司',
            'description': '2024032902783448>>理想汽车新项目交流及用餐',
            'income': 4210
        },
        {
            'date': pd.Timestamp('2024-03-30'),
            'amount': 10000,
            'counterparty': '上海爱斯达克汽车空调系统有限公司',
            'description': '代发工资',
            'income': 10000
        }
    ]

    df = pd.DataFrame(transactions)
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['business_reimbursement_income'] == 4210
    assert result['business_reimbursement_count'] == 1
    assert '单位报销/业务往来款' in result['business_reimbursement_details'][0]['reason']
    assert result['legitimate_income'] == 10000
    assert result['excluded_income'] == 4210


def test_empty_dataframe():
    """测试空DataFrame处理"""
    df = pd.DataFrame()
    result = classify_income_sources(df, entity_name='测试人员')
    
    assert result['legitimate_income'] == 0
    assert result['unknown_income'] == 0
    assert result['suspicious_income'] == 0
    assert result['excluded_income'] == 0


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


def test_self_transfer_is_excluded_from_real_income_classification():
    """测试本人互转会从真实收入分类中剔除"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-15'),
            'amount': 10000,
            'counterparty': '测试人员',
            'description': '本人转入',
            'income': 10000
        },
        {
            'date': pd.Timestamp('2024-01-16'),
            'amount': 8000,
            'counterparty': '财政局',
            'description': '工资',
            'income': 8000
        }
    ]

    df = pd.DataFrame(transactions)
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['excluded_income'] == 10000
    assert result['legitimate_income'] == 8000


def test_family_transfer_is_excluded_from_real_income_classification():
    """测试家庭成员转入会从真实收入分类中剔除"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-15'),
            'amount': 12000,
            'counterparty': '李四',
            'description': '家庭转账',
            'income': 12000
        },
        {
            'date': pd.Timestamp('2024-01-16'),
            'amount': 6000,
            'counterparty': '张三',
            'description': '普通转账',
            'income': 6000
        }
    ]

    df = pd.DataFrame(transactions)
    result = classify_income_sources(
        df, entity_name='测试人员', family_members=['李四']
    )

    assert result['excluded_income'] == 12000
    assert result['unknown_income'] == 6000


def test_family_transfer_alias_is_excluded_from_real_income_classification():
    """测试家庭成员别名/账号后缀也会被识别并剔除"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-15'),
            'amount': 15000,
            'counterparty': '候海焱6222',
            'description': '家庭转账',
            'income': 15000
        },
        {
            'date': pd.Timestamp('2024-01-16'),
            'amount': 6000,
            'counterparty': '张三',
            'description': '普通转账',
            'income': 6000
        }
    ]

    df = pd.DataFrame(transactions)
    result = classify_income_sources(
        df, entity_name='测试人员', family_members=['侯海焱']
    )

    assert result['excluded_income'] == 15000
    assert result['excluded_breakdown']['family_transfer'] == 15000
    assert result['excluded_details'][0]['rule_bucket'] == 'family_transfer'
    assert result['excluded_details'][0]['confidence'] == 'medium'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
