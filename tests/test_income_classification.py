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


def test_installment_adjustment_is_excluded_from_real_income():
    """测试转分期/账单分期冲销不计入真实收入"""
    transaction = {
        'date': pd.Timestamp('2024-03-23'),
        'amount': 170928.52,
        'counterparty': '',
        'description': '转分期-合并分期分6期',
        'income': 170928.52,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['excluded_income'] == 170928.52
    assert result['unknown_income'] == 0
    assert result['excluded_breakdown']['installment_adjustment'] == 170928.52
    assert result['excluded_details'][0]['rule_bucket'] == 'installment_adjustment'


def test_severance_income_is_classified_as_legitimate():
    """测试离职补偿识别为正经合法收入"""
    transaction = {
        'date': pd.Timestamp('2024-06-28'),
        'amount': 252421.67,
        'counterparty': '上海衡山虹妇幼医院',
        'description': '离职补偿金',
        'income': 252421.67,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['legitimate_income'] == 252421.67
    assert result['excluded_income'] == 0
    assert result['legitimate_details'][0]['reason'] == '离职补偿/劳动补偿'


def test_bank_product_adjustment_is_excluded():
    """测试银行卡产品回摆/还款冲销不计入真实收入"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 84606.00,
        'counterparty': '',
        'description': '网银互联还款8771',
        'income': 84606.00,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['excluded_income'] == 84606.00
    assert result['excluded_breakdown']['bank_product_adjustment'] == 84606.00
    assert result['excluded_details'][0]['reason'] == '银行卡产品回摆/还款冲销（已剔除）'


def test_blank_large_income_on_internal_account_is_excluded_as_bank_product():
    """测试内部账户的空白大额入账会按疑似银行产品剔除"""
    transaction = {
        'date': pd.Timestamp('2024-11-22 00:00:00'),
        'amount': 104212.55,
        'counterparty': '',
        'description': '',
        'income': 104212.55,
        'account_number': '103324757001001',
    }
    wealth_result = {
        'account_classification': {
            '103324757001001': {
                'type': 'internal',
                'features': {
                    'has_same_day_pair': True,
                    'has_interest_tail': True,
                },
            }
        }
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员', wealth_result=wealth_result)

    assert result['excluded_income'] == 104212.55
    assert result['excluded_breakdown']['bank_product_adjustment'] == 104212.55
    assert result['unknown_income'] == 0
    assert result['excluded_details'][0]['reason'] == '疑似银行产品空白记账（已剔除）'


def test_repeated_blank_large_income_on_primary_account_is_excluded_as_bank_product():
    """测试主账户的重复空白大额记账会按疑似银行产品剔除"""
    transactions = [
        {
            'date': pd.Timestamp('2024-10-06 00:00:00'),
            'amount': 33473.13,
            'counterparty': '',
            'description': '',
            'income': 33473.13,
            'account_number': '6221482883736688',
        },
        {
            'date': pd.Timestamp('2024-12-28 00:00:00'),
            'amount': 57000.00,
            'counterparty': '',
            'description': '',
            'income': 57000.00,
            'account_number': '6221482883736688',
        },
    ]
    wealth_result = {
        'account_classification': {
            '6221482883736688': {
                'type': 'primary',
                'features': {
                    'has_same_day_pair': True,
                    'has_interest_tail': True,
                },
            }
        }
    }

    df = pd.DataFrame(transactions)
    result = classify_income_sources(df, entity_name='测试人员', wealth_result=wealth_result)

    assert result['excluded_income'] == 90473.13
    assert result['excluded_breakdown']['bank_product_adjustment'] == 90473.13
    assert result['unknown_income'] == 0


def test_repeated_blank_frequent_income_on_bank_product_account_is_excluded():
    """测试银行产品特征账户上的高频空白入账不会继续计入待核实收入"""
    transactions = [
        {
            'date': pd.Timestamp('2024-01-05 00:00:00'),
            'amount': 7890.00,
            'counterparty': '',
            'description': '',
            'income': 7890.00,
            'account_number': '6221482883736688',
        },
        {
            'date': pd.Timestamp('2024-02-05 00:00:00'),
            'amount': 7890.00,
            'counterparty': '',
            'description': '',
            'income': 7890.00,
            'account_number': '6221482883736688',
        },
        {
            'date': pd.Timestamp('2024-03-05 00:00:00'),
            'amount': 7890.00,
            'counterparty': '',
            'description': '',
            'income': 7890.00,
            'account_number': '6221482883736688',
        },
    ]
    wealth_result = {
        'account_classification': {
            '6221482883736688': {
                'type': 'primary',
                'features': {
                    'has_same_day_pair': True,
                    'has_interest_tail': True,
                },
            }
        }
    }

    df = pd.DataFrame(transactions)
    result = classify_income_sources(df, entity_name='测试人员', wealth_result=wealth_result)

    assert result['excluded_income'] == 23670.0
    assert result['excluded_breakdown']['bank_product_adjustment'] == 23670.0
    assert result['unknown_income'] == 0


def test_hospital_regular_income_is_classified_as_salary_institution():
    """测试医院规律性或正常入账会识别为机构工资收入"""
    transaction = {
        'date': pd.Timestamp('2024-01-05'),
        'amount': 3584.10,
        'counterparty': '上海衡山虹妇幼医院',
        'description': '正常',
        'income': 3584.10,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['legitimate_income'] == 3584.10
    assert result['legitimate_details'][0]['reason'] == '工资性收入(机构/代发单位)'


def test_bank_payroll_channel_is_classified_as_salary_income():
    """测试银联代付类工资通道入账会识别为工资性收入"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 8050.19,
        'counterparty': '',
        'description': '银联入账/测试人员/9558****5512-银联代付',
        'income': 8050.19,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['legitimate_income'] == 8050.19
    assert result['legitimate_details'][0]['reason'] == '工资性收入(代付工资渠道)'


def test_personal_support_income_is_classified_as_legitimate():
    """测试抚养费/生活支持不会继续压成个人转账"""
    transaction = {
        'date': pd.Timestamp('2024-07-08'),
        'amount': 6000.0,
        'counterparty': '马尚德',
        'description': '20240708抚养费',
        'income': 6000.0,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['legitimate_income'] == 6000.0
    assert result['legitimate_details'][0]['reason'] == '亲友生活支持/抚养费'


def test_payment_platform_company_is_not_misclassified_as_salary_income():
    """测试支付平台公司入账不会被误判为机构工资收入"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 14998.23,
        'counterparty': '支付宝（中国）网络技术有限公司',
        'description': '充值交易',
        'income': 14998.23,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['legitimate_income'] == 0
    assert result['unknown_income'] == 14998.23
    assert result['unknown_details'][0]['reason'] == '支付平台渠道入账'


def test_payment_channel_alias_is_not_misclassified_as_individual_transfer():
    """测试微信转账这类通道别名不会被误判为个人转账"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 5888.0,
        'counterparty': '微信转账',
        'description': '财付通-微信转账',
        'income': 5888.0,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['unknown_income'] == 5888.0
    assert result['unknown_details'][0]['reason'] == '支付平台渠道入账'
    assert result['unknown_details'][0]['rule_bucket'] == 'payment_platform_channel'


def test_bank_cross_transfer_is_split_from_generic_source_unknown():
    """测试网银跨行汇款会单列为待核实跨行汇款而不是泛化来源不明"""
    transaction = {
        'date': pd.Timestamp('2024-01-15'),
        'amount': 107688.8,
        'counterparty': '',
        'description': '网银跨行汇款CHN',
        'income': 107688.8,
    }

    df = pd.DataFrame([transaction])
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['unknown_income'] == 107688.8
    assert result['unknown_details'][0]['reason'] == '银行跨行汇款待核实'
    assert result['unknown_details'][0]['rule_bucket'] == 'bank_cross_transfer'


def test_bank_system_adjustment_is_excluded_from_real_income():
    """测试银行系统的补款/还款记账不会继续计入真实收入"""
    transactions = [
        {
            'date': pd.Timestamp('2025-01-08 21:08:01'),
            'amount': 9900.05,
            'counterparty': '',
            'description': '还款成功 , 谢谢 !',
            'income': 9900.05,
            'source_file': 'boc.xlsx',
        },
        {
            'date': pd.Timestamp('2025-02-08 21:08:15'),
            'amount': 20000.00,
            'counterparty': '',
            'description': '无法足额扣款，请补足账户余额',
            'income': 20000.00,
            'source_file': 'boc.xlsx',
        },
    ]

    df = pd.DataFrame(transactions)
    result = classify_income_sources(df, entity_name='测试人员')

    assert round(result['excluded_income'], 2) == 29900.05
    assert round(result['excluded_breakdown']['bank_product_adjustment'], 2) == 29900.05
    assert result['unknown_income'] == 0


def test_repeated_bank_cross_transfer_with_companion_markers_is_excluded():
    """测试带有银行系统伴随记账的重复CHN跨行汇款会整体下沉为银行产品调整"""
    transactions = [
        {
            'date': pd.Timestamp('2025-01-08 15:43:52'),
            'amount': 9901.00,
            'counterparty': '',
            'description': '网银跨行汇款CHN',
            'income': 9901.00,
            'source_file': 'boc.xlsx',
        },
        {
            'date': pd.Timestamp('2025-01-08 21:08:01'),
            'amount': 9900.05,
            'counterparty': '',
            'description': '还款成功 , 谢谢 !',
            'income': 9900.05,
            'source_file': 'boc.xlsx',
        },
        {
            'date': pd.Timestamp('2025-02-08 17:51:48'),
            'amount': 29733.00,
            'counterparty': '',
            'description': '网银跨行汇款CHN',
            'income': 29733.00,
            'source_file': 'boc.xlsx',
        },
        {
            'date': pd.Timestamp('2025-02-08 21:08:15'),
            'amount': 20000.00,
            'counterparty': '',
            'description': '无法足额扣款，请补足账户余额',
            'income': 20000.00,
            'source_file': 'boc.xlsx',
        },
        {
            'date': pd.Timestamp('2025-03-11 15:38:32'),
            'amount': 29784.00,
            'counterparty': '',
            'description': '网银跨行汇款CHN',
            'income': 29784.00,
            'source_file': 'boc.xlsx',
        },
    ]

    df = pd.DataFrame(transactions)
    result = classify_income_sources(df, entity_name='测试人员')

    assert round(result['excluded_breakdown']['bank_product_adjustment'], 2) == 99318.05
    assert result['unknown_income'] == 0
    excluded_reasons = {item['reason'] for item in result['excluded_details']}
    assert '网银跨行汇款配套银行记账（已剔除）' in excluded_reasons
    assert '银行系统还款/补款记账（已剔除）' in excluded_reasons


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


def test_anjiafei_is_treated_as_legitimate_income():
    """测试安家费不应因摘要含报销而被剔除"""
    transactions = [
        {
            'date': pd.Timestamp('2024-02-27'),
            'amount': 360000,
            'counterparty': '上海空间电源研究所',
            'description': '代发报销 PAY02发放安家费',
            'income': 360000
        }
    ]

    df = pd.DataFrame(transactions)
    result = classify_income_sources(df, entity_name='测试人员')

    assert result['legitimate_income'] == 360000
    assert result['business_reimbursement_income'] == 0
    assert result['excluded_income'] == 0


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
