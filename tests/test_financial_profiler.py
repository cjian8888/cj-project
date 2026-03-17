#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金画像分析模块单元测试
"""

import pytest
import pandas as pd
from datetime import datetime
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from financial_profiler import (
    _calculate_stable_cv, calculate_income_structure,
    analyze_fund_flow, analyze_wealth_management,
    generate_profile_report, extract_large_cash,
    categorize_transactions, analyze_wealth_holdings,
    extract_bank_accounts, calculate_yearly_salary,  # Phase 1.2/2.1 新增
    build_company_profile, _calculate_real_income_expense  # Phase 2.3 新增
)


class TestCalculateStableCV:
    """测试变异系数计算函数"""
    
    def test_calculate_cv_empty_list(self):
        """测试空列表"""
        result = _calculate_stable_cv([])
        assert result == 999
    
    def test_calculate_cv_single_value(self):
        """测试单个值"""
        result = _calculate_stable_cv([1000])
        assert result == 0  # 标准差为0
    
    def test_calculate_cv_stable_values(self):
        """测试稳定值"""
        result = _calculate_stable_cv([1000, 1001, 999, 1000, 1001])
        assert result < 0.01  # 变异系数应该很小
    
    def test_calculate_cv_variable_values(self):
        """测试变化值"""
        result = _calculate_stable_cv([100, 1000, 5000, 10000])
        assert result > 0.5  # 变异系数应该较大
    
    def test_calculate_cv_with_outliers(self):
        """测试带异常值"""
        values = [1000, 1001, 999, 1000, 10000]  # 最后一个是异常值
        result_with_removal = _calculate_stable_cv(values, remove_outliers=True)
        result_without_removal = _calculate_stable_cv(values, remove_outliers=False)
        # 剔除异常值后CV应该更小
        assert result_with_removal < result_without_removal


class TestCalculateIncomeStructure:
    """测试收支结构计算函数"""
    
    def test_calculate_income_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame(columns=['date', 'income', 'expense', 'counterparty', 'description'])
        result = calculate_income_structure(df, '张伟')
        assert result['total_inflow'] == 0
        assert result['total_expense'] == 0
        assert result['salary_income'] == 0
    
    def test_calculate_income_basic(self):
        """测试基础计算"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [10000, 5000],
            'expense': [0, 2000],
            'counterparty': ['公司', '超市'],
            'description': ['工资', '购物']
        })
        result = calculate_income_structure(df, '张伟')
        assert result['total_inflow'] == 15000
        assert result['total_expense'] == 2000
        assert result['net_flow'] == 13000
    
    def test_calculate_income_self_transfer(self):
        """测试同名转账识别"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [10000, 5000],
            'expense': [0, 0],
            'counterparty': ['公司', '张伟'],
            'description': ['工资', '本人转入']
        })
        result = calculate_income_structure(df, '张伟')
        assert result['self_transfer_income'] == 5000
        assert result['external_income'] == 10000
    
    def test_calculate_income_salary_detection(self):
        """测试工资识别"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [10000, 5000],
            'expense': [0, 0],
            'counterparty': ['某某公司', '超市'],
            'description': ['工资', '购物']
        })
        result = calculate_income_structure(df, '张伟')
        assert result['salary_income'] > 0
        assert len(result['salary_details']) > 0
    
    def test_calculate_income_yearly_stats(self):
        """测试年度统计"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-02-01', '2023-01-01']),
            'income': [10000, 5000, 8000],
            'expense': [0, 0, 0],
            'counterparty': ['公司', '公司', '公司'],
            'description': ['工资', '工资', '工资']
        })
        result = calculate_income_structure(df, '张伟')
        assert 'yearly_stats' in result
        assert 'monthly_stats' in result
    
    def test_calculate_income_result_structure(self):
        """测试结果结构"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [10000],
            'expense': [0],
            'counterparty': ['公司'],
            'description': ['工资']
        })
        result = calculate_income_structure(df, '张伟')
        expected_keys = [
            'date_range', 'total_inflow', 'total_income', 'self_transfer_income',
            'external_income', 'total_expense', 'net_flow', 'salary_income',
            'non_salary_income', 'salary_ratio', 'salary_details',
            'yearly_stats', 'monthly_stats', 'transaction_count'
        ]
        for key in expected_keys:
            assert key in result


class TestAnalyzeFundFlow:
    """测试资金去向分析函数"""
    
    def test_analyze_fund_flow_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame(columns=['date', 'income', 'expense', 'counterparty', 'description'])
        result = analyze_fund_flow(df)
        assert result['third_party_expense'] == 0
        assert result['third_party_income'] == 0
    
    def test_analyze_fund_flow_third_party(self):
        """测试第三方支付识别"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [0, 1000],
            'expense': [500, 0],
            'counterparty': ['支付宝', '微信'],
            'description': ['支付宝支付', '微信收入']
        })
        result = analyze_fund_flow(df)
        assert result['third_party_expense'] > 0
        assert result['third_party_income'] > 0
    
    def test_analyze_fund_flow_counterparty_stats(self):
        """测试对手方统计"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [1000, 2000, 3000],
            'expense': [0, 0, 0],
            'counterparty': ['公司A', '公司B', '公司A'],
            'description': ['工资', '奖金', '工资']
        })
        result = analyze_fund_flow(df)
        assert 'counterparty_stats' in result
        assert 'top_counterparties' in result
        assert len(result['top_counterparties']) <= 10
    
    def test_analyze_fund_flow_result_structure(self):
        """测试结果结构"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [1000],
            'expense': [0],
            'counterparty': ['公司'],
            'description': ['工资']
        })
        result = analyze_fund_flow(df)
        expected_keys = [
            'third_party_amount', 'third_party_expense', 'third_party_expense_count',
            'third_party_expense_transactions', 'third_party_income', 'third_party_income_count',
            'third_party_income_transactions', 'third_party_transactions', 'third_party_count',
            'third_party_ratio', 'counterparty_stats', 'top_counterparties'
        ]
        for key in expected_keys:
            assert key in result


class TestAnalyzeWealthManagement:
    """测试理财产品分析函数"""
    
    def test_analyze_wealth_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame(columns=['date', 'income', 'expense', 'counterparty', 'description'])
        result = analyze_wealth_management(df, '张伟')
        assert result['wealth_purchase'] == 0
        assert result['wealth_redemption'] == 0
        assert result['wealth_income'] == 0
    
    def test_analyze_wealth_self_transfer(self):
        """测试自我转账识别"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [5000, 0],
            'expense': [0, 5000],
            'counterparty': ['张伟', '张伟'],
            'description': ['本人转入', '本人转出']
        })
        result = analyze_wealth_management(df, '张伟')
        assert result['self_transfer_income'] > 0
        assert result['self_transfer_expense'] > 0
    
    def test_analyze_wealth_loan_detection(self):
        """测试贷款识别"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [100000],
            'expense': [0],
            'counterparty': ['银行'],
            'description': ['贷款发放']
        })
        result = analyze_wealth_management(df, '张伟')
        assert result['loan_inflow'] > 0
    
    def test_analyze_wealth_refund_detection(self):
        """测试退款识别"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [1000],
            'expense': [0],
            'counterparty': ['商家'],
            'description': ['退款']
        })
        result = analyze_wealth_management(df, '张伟')
        assert result['refund_inflow'] > 0
    
    def test_analyze_wealth_product_detection(self):
        """测试理财产品识别"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [0, 10500],
            'expense': [10000, 0],
            'counterparty': ['银行', '银行'],
            'description': ['理财购买', '理财赎回']
        })
        result = analyze_wealth_management(df, '张伟')
        assert result['wealth_purchase'] > 0
        assert result['wealth_redemption'] > 0
    
    def test_analyze_wealth_category_stats(self):
        """测试分类统计"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [0, 10500],
            'expense': [10000, 0],
            'counterparty': ['银行', '银行'],
            'description': ['基金申购', '基金赎回']
        })
        result = analyze_wealth_management(df, '张伟')
        assert 'category_stats' in result
        assert 'yearly_stats' in result

    def test_analyze_wealth_separates_business_reimbursement(self):
        """测试将单位报销/业务往来款从理财赎回中剥离"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [0, 10500, 4210],
            'expense': [10000, 0, 0],
            'counterparty': ['银行', '银行', '上海爱斯达克汽车空调系统有限公司'],
            'description': ['理财购买', '理财赎回', '2024032902783448>>理想汽车新项目交流及用餐']
        })
        result = analyze_wealth_management(df, '张伟')
        assert result['wealth_purchase'] == 10000
        assert result['wealth_redemption'] == 10500
        assert result['business_reimbursement_income'] == 4210
        assert result['business_reimbursement_count'] == 1

    def test_analyze_wealth_result_structure(self):
        """测试结果结构"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [1000],
            'expense': [0],
            'counterparty': ['公司'],
            'description': ['工资']
        })
        result = analyze_wealth_management(df, '张伟')
        expected_keys = [
            'wealth_purchase', 'wealth_purchase_count', 'wealth_purchase_transactions',
            'wealth_redemption', 'wealth_redemption_count', 'wealth_redemption_transactions',
            'business_reimbursement_income', 'business_reimbursement_count',
            'business_reimbursement_transactions',
            'wealth_income', 'wealth_income_count', 'wealth_income_transactions',
            'net_wealth_flow', 'real_wealth_profit', 'self_transfer_income',
            'self_transfer_expense', 'self_transfer_count', 'self_transfer_transactions',
            'loan_inflow', 'refund_inflow', 'category_stats', 'yearly_stats',
            'total_transactions', 'estimated_holding', 'holding_structure'
        ]
        for key in expected_keys:
            assert key in result

    def test_real_income_formula_does_not_double_subtract_deposit_redemption(self):
        """测试定期存款不再被重复剔除"""
        income_structure = {
            "total_income": 1_000_000,
            "total_expense": 900_000,
        }
        wealth_management = {
            "self_transfer_income": 0,
            "self_transfer_expense": 0,
            "wealth_purchase": 300_000,
            "wealth_redemption": 280_000,
            "wealth_income": 0,
            "business_reimbursement_income": 0,
            "loan_inflow": 0,
            "refund_inflow": 0,
            "deposit_purchase": 100_000,
            "deposit_redemption": 80_000,
        }
        fund_flow = {}

        real_income, real_expense, offset_detail = _calculate_real_income_expense(
            income_structure, wealth_management, fund_flow
        )

        assert real_income == 720000
        assert real_expense == 600000
        assert offset_detail["wealth_principal"] == 200000
        assert offset_detail["deposit_redemption"] == 80000


class TestAnalyzeWealthHoldings:
    """测试理财产品持有估算函数"""
    
    def test_analyze_holdings_empty_lists(self):
        """测试空列表"""
        holding, details = analyze_wealth_holdings([], [])
        assert holding == 0
        assert details == []
    
    def test_analyze_holdings_no_redemptions(self):
        """测试无赎回记录"""
        purchases = [
            {'日期': datetime(2024, 1, 1), '金额': 10000, '摘要': '理财购买'},
            {'日期': datetime(2024, 2, 1), '金额': 20000, '摘要': '理财购买'}
        ]
        holding, details = analyze_wealth_holdings(purchases, [])
        assert holding == 30000
        assert len(details) == 2
    
    def test_analyze_holdings_with_redemptions(self):
        """测试有赎回记录"""
        purchases = [
            {'日期': datetime(2024, 1, 1), '金额': 10000, '摘要': '理财购买'},
            {'日期': datetime(2024, 2, 1), '金额': 20000, '摘要': '理财购买'}
        ]
        redemptions = [
            {'日期': datetime(2024, 3, 1), '金额': 10500, '摘要': '理财赎回'}
        ]
        holding, details = analyze_wealth_holdings(purchases, redemptions)
        # 应该匹配一笔购买，剩余一笔未赎回
        assert holding > 0
        assert len(details) >= 1


class TestGenerateProfileReport:
    """测试画像报告生成函数"""
    
    def test_generate_profile_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame(columns=['date', 'income', 'expense', 'counterparty', 'description'])
        result = generate_profile_report(df, '张伟')
        assert result['entity_name'] == '张伟'
        assert result['has_data'] is False
    
    def test_generate_profile_basic(self):
        """测试基础报告生成"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [10000, 5000],
            'expense': [0, 2000],
            'counterparty': ['公司', '超市'],
            'description': ['工资', '购物']
        })
        result = generate_profile_report(df, '张伟')
        assert result['entity_name'] == '张伟'
        assert result['has_data'] is True
        assert 'income_structure' in result
        assert 'fund_flow' in result
        assert 'wealth_management' in result
        assert 'summary' in result
    
    def test_generate_profile_summary(self):
        """测试汇总信息"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [10000, 5000, 4210],
            'expense': [0, 2000, 0],
            'counterparty': ['公司', '超市', '上海爱斯达克汽车空调系统有限公司'],
            'description': ['工资', '购物', '2024032902783448>>理想汽车新项目交流及用餐']
        })
        result = generate_profile_report(df, '张伟')
        summary = result['summary']
        assert 'total_income' in summary
        assert 'total_expense' in summary
        assert 'net_flow' in summary
        assert 'real_income' in summary
        assert 'real_expense' in summary
        assert 'salary_ratio' in summary
        assert 'third_party_ratio' in summary
        assert 'business_reimbursement' in summary['offset_detail']

    def test_generate_profile_income_classification_matches_real_income_basis(self):
        """测试收入分类合计与真实收入主口径一致"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [10000, 5000, 3000],
            'expense': [0, 0, 0],
            'counterparty': ['某公司', '张伟', '某商户'],
            'description': ['工资', '本人转入', '退款']
        })
        result = generate_profile_report(df, '张伟')
        income_classification = result['income_classification']
        classified_total = (
            income_classification['legitimate_income']
            + income_classification['unknown_income']
            + income_classification['suspicious_income']
        )

        assert round(result['summary']['real_income'], 2) == 10000
        assert round(classified_total, 2) == 10000
        assert income_classification['excluded_income'] == 8000

    def test_generate_profile_business_reimbursement_aligns_with_real_income(self):
        """测试单位报销/业务往来款剔除与真实收入主口径一致"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-03-29', '2024-03-30']),
            'income': [4210, 10000],
            'expense': [0, 0],
            'counterparty': ['上海爱斯达克汽车空调系统有限公司', '某公司'],
            'description': ['2024032902783448>>理想汽车新项目交流及用餐', '代发工资']
        })
        result = generate_profile_report(df, '张伟')
        income_classification = result['income_classification']
        classified_total = (
            income_classification['legitimate_income']
            + income_classification['unknown_income']
            + income_classification['suspicious_income']
        )

        assert round(result['summary']['real_income'], 2) == 10000
        assert round(classified_total, 2) == 10000
        assert round(result['summary']['offset_detail']['business_reimbursement'], 2) == 4210

    def test_generate_profile_blank_internal_bank_product_adjustment_aligns_real_income(self):
        """测试内部账户的空白大额入账会从真实收入中剔除"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-11-22 00:00:00', '2024-11-23 09:00:00']),
            'income': [104212.55, 10000],
            'expense': [0, 0],
            'counterparty': ['', '某公司'],
            'description': ['', '工资'],
            'account_number': ['103324757001001', '6222000011112222'],
        })
        result = generate_profile_report(df, '张伟')
        income_classification = result['income_classification']
        classified_total = (
            income_classification['legitimate_income']
            + income_classification['unknown_income']
            + income_classification['suspicious_income']
        )

        assert round(result['summary']['real_income'], 2) == 10000
        assert round(classified_total, 2) == 10000
        assert round(income_classification['excluded_breakdown']['bank_product_adjustment'], 2) == 104212.55

    def test_generate_profile_anjiafei_counts_as_real_income(self):
        """测试安家费应计入真实收入而非单位报销"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-02-27', '2024-03-30']),
            'income': [360000, 10000],
            'expense': [0, 0],
            'counterparty': ['上海空间电源研究所', '某公司'],
            'description': ['代发报销 PAY02发放安家费', '代发工资']
        })
        result = generate_profile_report(df, '张伟')
        income_classification = result['income_classification']
        classified_total = (
            income_classification['legitimate_income']
            + income_classification['unknown_income']
            + income_classification['suspicious_income']
        )

        assert round(result['summary']['real_income'], 2) == 370000
        assert round(classified_total, 2) == 370000
        assert round(result['summary']['offset_detail']['business_reimbursement'], 2) == 0

    def test_generate_profile_family_transfer_alias_aligns_with_real_income(self):
        """测试家庭成员别名互转会同步影响真实收入与剔除明细"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [15000, 8000],
            'expense': [0, 0],
            'counterparty': ['候海焱6222', '某公司'],
            'description': ['家庭转账', '工资']
        })
        result = generate_profile_report(df, '测试人员', family_members=['侯海焱'])
        summary = result['summary']
        income_classification = result['income_classification']

        assert round(summary['real_income'], 2) == 8000
        assert round(summary['offset_detail']['family_transfer_in'], 2) == 15000
        assert summary['offset_detail']['family_transfer_in_count'] == 1
        assert summary['offset_detail']['offset_meta']['family_transfer']['matching_mode'] == 'alias_match'
        assert income_classification['excluded_breakdown']['family_transfer'] == 15000
        assert income_classification['classification_basis'] == 'real_income_basis'

    def test_generate_profile_attaches_salary_reference_metadata(self):
        """测试收入分类结果补充严格工资口径参考值"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [10000, 15000],
            'expense': [0, 0],
            'counterparty': ['某公司', '某公司'],
            'description': ['工资', '代发工资'],
        })
        result = generate_profile_report(df, '张伟')
        income_classification = result['income_classification']

        assert income_classification['salary_reference_income'] == result['yearly_salary']['summary']['total']
        assert income_classification['salary_classified_income'] > 0
        assert '工资性收入' in income_classification['salary_like_reasons']
        assert 'salary_reference_basis' in income_classification

    def test_generate_profile_aligns_salary_reference_with_excluded_income(self):
        """测试被剔除的伪工资交易不会继续留在工资参考口径中"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [10000, 5000],
            'expense': [0, 0],
            'counterparty': ['某公司', '某公司'],
            'description': ['代发工资', '网银互联还款 工资'],
        })
        result = generate_profile_report(df, '张伟')
        income_classification = result['income_classification']
        income_structure = result['income_structure']
        yearly_salary = result['yearly_salary']

        assert round(income_classification['excluded_breakdown']['bank_product_adjustment'], 2) == 5000
        assert round(income_structure['salary_income'], 2) == 10000
        assert len(income_structure['salary_details']) == 1
        assert round(yearly_salary['summary']['total'], 2) == 10000
        assert round(yearly_salary['summary']['gross_total_before_exclusion'], 2) == 15000
        assert round(yearly_salary['summary']['excluded_overlap_total'], 2) == 5000
        assert round(income_classification['salary_reference_income'], 2) == 10000
        assert round(income_classification['salary_reference_gross_income'], 2) == 15000
        assert income_classification['salary_reference_basis'] == 'yearly_salary_summary_total_excluded_aligned'

    def test_generate_profile_supports_wan_unit_columns_and_invalid_dates(self):
        """万元列头和脏日期不应导致画像流程崩溃"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01', '坏日期'],
            '收入(万元)': ['1.5', '0'],
            '支出(万元)': ['0', '0'],
            '交易对手': ['某公司', '某公司'],
            '交易摘要': ['工资', '工资']
        })
        result = generate_profile_report(df, '张伟')
        assert result['has_data'] is True
        assert round(result['summary']['total_income'], 2) == 15000.0


class TestExtractLargeCash:
    """测试大额现金提取函数"""
    
    def test_extract_large_cash_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame(columns=['date', 'income', 'expense', 'counterparty', 'description'])
        result = extract_large_cash(df)
        assert result == []
    
    def test_extract_large_cash_with_cash_transactions(self):
        """测试现金交易"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [50000, 0],
            'expense': [0, 30000],
            'counterparty': ['银行', '银行'],
            'description': ['现金存入', '现金支取']
        })
        result = extract_large_cash(df, threshold=20000)
        assert len(result) == 2
    
    def test_extract_large_cash_below_threshold(self):
        """测试低于阈值"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [10000],
            'expense': [0],
            'counterparty': ['银行'],
            'description': ['现金存入']
        })
        result = extract_large_cash(df, threshold=20000)
        assert len(result) == 0
    
    def test_extract_large_cash_risk_level(self):
        """测试风险等级"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [50000, 100000, 200000],
            'expense': [0, 0, 0],
            'counterparty': ['银行', '银行', '银行'],
            'description': ['现金存入', '现金存入', '现金存入']
        })
        result = extract_large_cash(df, threshold=20000)
        assert len(result) == 3
        # 检查风险等级
        risk_levels = [r['risk_level'] for r in result]
        assert 'low' in risk_levels or 'medium' in risk_levels or 'high' in risk_levels


def test_calculate_yearly_salary_recognizes_bank_payroll_channel():
    """测试银联代付工资通道会进入年度工资统计"""
    df = pd.DataFrame({
        'date': pd.to_datetime(['2024-01-15']),
        'income': [8050.19],
        'expense': [0],
        'counterparty': [''],
        'description': ['银联入账/张伟/9558****5512-银联代付'],
    })

    result = calculate_yearly_salary(df, '张伟')

    assert result['summary']['total'] == 8050.19
    assert result['details'][0]['reason'] == '摘要含强工资关键词'


class TestCategorizeTransactions:
    """测试交易分类函数"""
    
    def test_categorize_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame(columns=['date', 'income', 'expense', 'counterparty', 'description'])
        result = categorize_transactions(df)
        assert result['salary'] == []
        assert result['non_salary'] == []
        assert result['third_party'] == []
    
    def test_categorize_salary_transactions(self):
        """测试工资分类"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [10000],
            'expense': [0],
            'counterparty': ['公司'],
            'description': ['工资']
        })
        result = categorize_transactions(df)
        assert len(result['salary']) == 1
        assert len(result['non_salary']) == 0
    
    def test_categorize_third_party_transactions(self):
        """测试第三方支付分类"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [0],
            'expense': [500],
            'counterparty': ['支付宝'],
            'description': ['支付宝支付']
        })
        result = categorize_transactions(df)
        assert len(result['third_party']) == 1
    
    def test_categorize_cash_transactions(self):
        """测试现金交易分类"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [50000],
            'expense': [0],
            'counterparty': ['银行'],
            'description': ['现金存入']
        })
        result = categorize_transactions(df)
        assert len(result['cash']) == 1
    
    def test_categorize_large_amount_transactions(self):
        """测试大额交易分类"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [100000],
            'expense': [0],
            'counterparty': ['公司'],
            'description': ['转账']
        })
        result = categorize_transactions(df)
        assert len(result['large_amount']) == 1
    
    def test_categorize_result_structure(self):
        """测试结果结构"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [10000],
            'expense': [0],
            'counterparty': ['公司'],
            'description': ['工资']
        })
        result = categorize_transactions(df)
        expected_keys = ['salary', 'non_salary', 'third_party', 'cash', 
                        'large_amount', 'property', 'vehicle', 'other']
        for key in expected_keys:
            assert key in result


# ========== Phase 1.2/2.1 新增测试 (2026-01-21) ==========

class TestExtractBankAccounts:
    """测试银行账户提取函数"""
    
    def test_extract_bank_accounts_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame(columns=['date', 'income', 'expense', 'account_number'])
        result = extract_bank_accounts(df)
        assert result == []
    
    def test_extract_bank_accounts_single_account(self):
        """测试单个账户"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [1000, 2000, 0],
            'expense': [0, 0, 500],
            'account_number': ['6222021234567890', '6222021234567890', '6222021234567890'],
            '银行来源': ['工商银行', '工商银行', '工商银行']
        })
        result = extract_bank_accounts(df, '张伟')
        assert len(result) == 1
        assert result[0]['account_number'] == '6222021234567890'
        assert result[0]['transaction_count'] == 3
        assert result[0]['total_income'] == 3000
        assert result[0]['total_expense'] == 500
    
    def test_extract_bank_accounts_multiple_accounts(self):
        """测试多个账户"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [1000, 2000, 3000],
            'expense': [0, 0, 0],
            'account_number': ['6222021234567890', '6228480001234567', '6222021234567890'],
            '银行来源': ['工商银行', '建设银行', '工商银行']
        })
        result = extract_bank_accounts(df, '张伟')
        assert len(result) == 2
        # 按交易笔数排序，工商银行账户有2笔在前
        assert result[0]['transaction_count'] == 2
        assert result[1]['transaction_count'] == 1
    
    def test_extract_bank_accounts_with_account_type(self):
        """测试账户类型识别"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [1000, 2000],
            'expense': [0, 0],
            'account_number': ['6222021234567890', 'LCT001234'],
            'account_type': ['借记卡', '理财账户'],
            'is_real_bank_card': [True, False],
            '银行来源': ['工商银行', '工商银行']
        })
        result = extract_bank_accounts(df)
        assert len(result) == 2
        real_cards = [a for a in result if a['is_real_bank_card']]
        other_accounts = [a for a in result if not a['is_real_bank_card']]
        assert len(real_cards) == 1
        assert len(other_accounts) == 1
    
    def test_extract_bank_accounts_date_range(self):
        """测试日期范围"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-06-15', '2024-12-31']),
            'income': [1000, 2000, 3000],
            'expense': [0, 0, 0],
            'account_number': ['6222021234567890', '6222021234567890', '6222021234567890']
        })
        result = extract_bank_accounts(df)
        assert len(result) == 1
        assert result[0]['first_transaction_date'].year == 2024
        assert result[0]['first_transaction_date'].month == 1
        assert result[0]['last_transaction_date'].month == 12

    def test_extract_bank_accounts_parses_string_amounts_and_balance(self):
        """字符串金额和余额应按元口径安全提取"""
        df = pd.DataFrame({
            'date': ['2024-01-01'],
            'income': ['100万'],
            'expense': ['0'],
            'balance': ['1.5万'],
            'account_number': ['6222021234567890']
        })
        result = extract_bank_accounts(df)
        assert len(result) == 1
        assert result[0]['total_income'] == 1000000.0
        assert result[0]['last_balance'] == 15000.0


class TestCalculateYearlySalary:
    """测试年度工资统计函数"""
    
    def test_calculate_yearly_salary_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame(columns=['date', 'income', 'expense', 'counterparty', 'description'])
        result = calculate_yearly_salary(df)
        assert result['summary']['total'] == 0
        assert result['yearly'] == {}
        assert result['details'] == []
    
    def test_calculate_yearly_salary_single_year(self):
        """测试单年度"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-15', '2024-02-15', '2024-03-15']),
            'income': [10000, 12000, 11000],
            'expense': [0, 0, 0],
            'counterparty': ['公司', '公司', '公司'],
            'description': ['工资', '工资', '工资']
        })
        result = calculate_yearly_salary(df, '张伟')
        assert '2024' in result['yearly']
        assert result['yearly']['2024']['total'] == 33000
        assert result['yearly']['2024']['transaction_count'] == 3
        assert result['summary']['years_count'] == 1
    
    def test_calculate_yearly_salary_multiple_years(self):
        """测试多年度"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2023-12-15', '2024-01-15', '2024-02-15']),
            'income': [10000, 12000, 11000],
            'expense': [0, 0, 0],
            'counterparty': ['公司', '公司', '公司'],
            'description': ['工资', '工资', '工资']
        })
        result = calculate_yearly_salary(df, '张伟')
        assert result['summary']['years_count'] >= 1
    
    def test_calculate_yearly_salary_monthly_breakdown(self):
        """测试月度明细"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-15', '2024-01-25', '2024-02-15']),
            'income': [5000, 3000, 10000],
            'expense': [0, 0, 0],
            'counterparty': ['公司', '公司', '公司'],
            'description': ['工资', '奖金', '工资']
        })
        result = calculate_yearly_salary(df, '张伟')
        if '2024' in result['yearly']:
            months = result['yearly']['2024'].get('months', {})
            if '01' in months:
                assert months['01']['count'] >= 1
    
    def test_calculate_yearly_salary_summary(self):
        """测试汇总统计"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-15', '2024-02-15']),
            'income': [10000, 10000],
            'expense': [0, 0],
            'counterparty': ['公司', '公司'],
            'description': ['工资', '工资']
        })
        result = calculate_yearly_salary(df, '张伟')
        summary = result['summary']
        assert 'total' in summary
        assert 'years_count' in summary
        assert 'avg_yearly' in summary
        assert 'avg_monthly' in summary


# ========== Phase 2.3 公司画像测试 (2026-01-21) ==========

class TestBuildCompanyProfile:
    """测试公司画像生成函数"""
    
    def test_build_company_profile_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame(columns=['date', 'income', 'expense', 'counterparty', 'description'])
        result = build_company_profile(df, '测试公司')
        assert result['entity_name'] == '测试公司'
        assert result['entity_type'] == 'company'
        assert result['has_data'] is False
    
    def test_build_company_profile_basic(self):
        """测试基础公司画像生成"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [100000, 50000, 0],
            'expense': [0, 0, 30000],
            'counterparty': ['客户A', '客户B', '供应商C'],
            'description': ['货款', '销售收入', '采购支付']
        })
        result = build_company_profile(df, '测试公司')
        assert result['entity_name'] == '测试公司'
        assert result['entity_type'] == 'company'
        assert result['has_data'] is True
        assert 'income_structure' in result
        assert 'fund_flow' in result
        assert 'summary' in result
    
    def test_build_company_profile_company_specific(self):
        """测试公司特有分析字段"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [100000, 0, 0],
            'expense': [0, 50000, 30000],
            'counterparty': ['客户公司', '张三', '银行ATM'],
            'description': ['货款', '转账给个人', '现金取款']
        })
        result = build_company_profile(df, '测试公司')
        assert 'company_specific' in result
        company_specific = result['company_specific']
        assert 'to_individual_transfers' in company_specific
        assert 'cash_withdrawal_pattern' in company_specific
    
    def test_build_company_profile_result_structure(self):
        """测试结果结构完整性"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [100000],
            'expense': [0],
            'counterparty': ['客户'],
            'description': ['货款']
        })
        result = build_company_profile(df, '测试公司')
        expected_keys = [
            'entity_name', 'entity_type', 'has_data',
            'income_structure', 'fund_flow', 'wealth_management',
            'large_cash', 'categories', 'company_specific', 'summary'
        ]
        for key in expected_keys:
            assert key in result, f"缺少字段: {key}"
    
    def test_build_company_profile_summary(self):
        """测试汇总信息"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [100000, 0],
            'expense': [0, 30000],
            'counterparty': ['客户', '供应商'],
            'description': ['货款', '采购']
        })
        result = build_company_profile(df, '测试公司')
        summary = result['summary']
        assert 'total_income' in summary
        assert 'total_expense' in summary
        assert 'net_flow' in summary
        assert 'real_income' in summary
        assert 'real_expense' in summary
        assert summary['total_income'] == 100000
        assert summary['total_expense'] == 30000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
