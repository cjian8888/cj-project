#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据清洗模块单元测试
"""

import pytest
import pandas as pd
from datetime import datetime
import sys
import os
import tempfile

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_cleaner import (
    deduplicate_transactions, validate_data_quality,
    standardize_bank_fields, generate_cleaning_report,
    clean_and_merge_files, save_formatted_excel
)


class TestDeduplicateTransactions:
    """测试交易去重函数"""
    
    def test_deduplicate_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame()
        result, stats = deduplicate_transactions(df)
        assert result.empty
        assert stats['original'] == 0
        assert stats['duplicates'] == 0
        assert stats['final'] == 0
    
    def test_deduplicate_no_duplicates(self):
        """测试无重复数据"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [1000, 2000, 3000],
            'expense': [0, 0, 0],
            'counterparty': ['A', 'B', 'C'],
            'description': ['工资', '奖金', '补贴']
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 3
        assert stats['duplicates'] == 0
    
    def test_deduplicate_with_duplicates(self):
        """测试有重复数据"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01 10:00:00', '2024-01-01 10:00:01']),
            'income': [1000, 1000],
            'expense': [0, 0],
            'counterparty': ['公司', '公司'],
            'description': ['工资', '工资']
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 1
        assert stats['duplicates'] == 1
    
    def test_deduplicate_large_amount_protection(self):
        """测试大额交易保护"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01 10:00:00', '2024-01-01 10:00:01']),
            'income': [100000, 100000],
            'expense': [0, 0],
            'counterparty': ['公司', '公司'],
            'description': ['工资', '工资'],
            'transaction_id': ['123', '456']
        })
        result, stats = deduplicate_transactions(df)
        # 大额交易流水号不同，不应去重
        assert len(result) == 2
    
    def test_deduplicate_stats_structure(self):
        """测试统计信息结构"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [1000],
            'expense': [0],
            'counterparty': ['A'],
            'description': ['工资']
        })
        result, stats = deduplicate_transactions(df)
        assert 'original' in stats
        assert 'duplicates' in stats
        assert 'final' in stats
        assert 'dedup_rate' in stats
        assert 'dedup_details' in stats

    def test_deduplicate_same_amount_opposite_direction_not_removed(self):
        """同金额反方向交易不应互相去重"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01 10:00:00', '2024-01-01 10:00:01']),
            'income': [1000, 0],
            'expense': [0, 1000],
            'counterparty': ['A公司', 'A公司'],
            'description': ['转账', '转账']
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 2
        assert stats['duplicates'] == 0


class TestValidateDataQuality:
    """测试数据质量验证函数"""
    
    def test_validate_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame()
        result, report = validate_data_quality(df)
        assert result.empty
        assert report['total_rows'] == 0
    
    def test_validate_missing_date_column(self):
        """测试缺少日期列"""
        df = pd.DataFrame({
            'income': [1000, 2000],
            'expense': [0, 0]
        })
        result, report = validate_data_quality(df)
        assert '缺少日期字段' in report['warnings']
    
    def test_validate_missing_dates(self):
        """测试缺失日期值"""
        df = pd.DataFrame({
            'date': [pd.NaT, datetime(2024, 1, 2)],
            'income': [1000, 2000],
            'expense': [0, 0],
            'description': ['工资', '奖金']
        })
        result, report = validate_data_quality(df)
        assert len(result) == 1
        assert '日期缺失' in str(report['warnings'])
    
    def test_validate_zero_amount(self):
        """测试零金额检测"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [0, 1000],
            'expense': [0, 0],
            'description': ['测试', '工资']
        })
        result, report = validate_data_quality(df)
        assert '零金额记录' in str(report['warnings'])
    
    def test_validate_empty_description(self):
        """测试空摘要检测"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'income': [1000, 2000],
            'expense': [0, 0],
            'description': ['', '工资']
        })
        result, report = validate_data_quality(df)
        assert '缺少摘要' in str(report['warnings'])
    
    def test_validate_report_structure(self):
        """测试报告结构"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [1000],
            'expense': [0],
            'description': ['工资']
        })
        result, report = validate_data_quality(df)
        assert 'total_rows' in report
        assert 'invalid_rows' in report
        assert 'warnings' in report
        assert 'valid_rows' in report
        assert 'removed_rows' in report


class TestStandardizeBankFields:
    """测试银行字段标准化函数"""
    
    def test_standardize_with_date_column(self):
        """测试日期列标准化"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01', '2024-01-02'],
            '交易金额': [1000, 2000],
            '借贷标志': ['贷', '贷']
        })
        result = standardize_bank_fields(df)
        assert 'date' in result.columns
        assert len(result) == 2
    
    def test_standardize_with_debit_credit_flag(self):
        """测试借贷标志处理"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01', '2024-01-02'],
            '交易金额': [1000, 2000],
            '借贷标志': ['贷', '借']
        })
        result = standardize_bank_fields(df)
        assert result.iloc[0]['income'] == 1000
        assert result.iloc[0]['expense'] == 0
        assert result.iloc[1]['income'] == 0
        assert result.iloc[1]['expense'] == 2000
    
    def test_standardize_with_counterparty(self):
        """测试对手方标准化"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '交易对方名称': ['某某公司']
        })
        result = standardize_bank_fields(df)
        assert 'counterparty' in result.columns
        assert result.iloc[0]['counterparty'] == '某某公司'
    
    def test_standardize_with_balance(self):
        """测试余额标准化"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '交易余额': [5000]
        })
        result = standardize_bank_fields(df)
        assert 'balance' in result.columns
        assert result.iloc[0]['balance'] == 5000
    
    def test_standardize_cash_detection(self):
        """测试现金交易检测"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '交易摘要': ['现金存入']
        })
        result = standardize_bank_fields(df)
        assert 'is_cash' in result.columns
        assert result.iloc[0]['is_cash'] == True
    
    def test_standardize_required_columns(self):
        """测试必需列存在"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷']
        })
        result = standardize_bank_fields(df)
        required_cols = ['date', 'income', 'expense', 'counterparty', 
                        'description', 'balance', 'is_cash']
        for col in required_cols:
            assert col in result.columns

    def test_standardize_negative_sign_normalization_without_dc_flag(self):
        """无借贷标志时，负值应自动翻转到对侧字段"""
        df = pd.DataFrame({
            '交易日期': ['2024-01-01', '2024-01-02'],
            '收入': [-1000, 0],
            '支出': [0, -2000],
            '摘要': ['测试1', '测试2']
        })
        result = standardize_bank_fields(df)
        assert result.iloc[0]['income'] == 0
        assert result.iloc[0]['expense'] == 1000
        assert result.iloc[1]['income'] == 2000
        assert result.iloc[1]['expense'] == 0

    def test_standardize_company_entity_account_category(self):
        """公司主体应按对公账户口径识别"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [15000],
            '借贷标志': ['贷'],
            '本方账号': ['123456789012'],
            '交易摘要': ['货款回款']
        })
        result = standardize_bank_fields(df, bank_name='中国银行', entity_name='某某科技有限公司')
        assert result.iloc[0]['account_category'] == '对公账户'
        assert result.iloc[0]['account_type'] == '对公结算账户'
        assert bool(result.iloc[0]['is_real_bank_card']) is True


class TestGenerateCleaningReport:
    """测试清洗报告生成函数"""
    
    def test_generate_report_basic(self):
        """测试基础报告生成"""
        file_stats = [
            {'filename': 'test1.xlsx', 'bank': '工商银行', 
             'original_rows': 100, 'valid_rows': 95, 'duplicates': 5, 'process_time': '1.0s'}
        ]
        final_stats = {
            'total_original': 100,
            'total_valid': 95,
            'total_duplicates': 5,
            'total_time': '1.0s'
        }
        result = generate_cleaning_report('张伟', file_stats, final_stats)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2  # 1个文件 + 1个汇总行
    
    def test_generate_report_columns(self):
        """测试报告列"""
        file_stats = [
            {'filename': 'test1.xlsx', 'bank': '工商银行', 
             'original_rows': 100, 'valid_rows': 95, 'duplicates': 5, 'process_time': '1.0s'}
        ]
        final_stats = {
            'total_original': 100,
            'total_valid': 95,
            'total_duplicates': 5,
            'total_time': '1.0s'
        }
        result = generate_cleaning_report('张伟', file_stats, final_stats)
        expected_cols = ['对象', '文件名', '银行', '原始行数', '有效行数', '去重行数', '处理时间']
        for col in expected_cols:
            assert col in result.columns
    
    def test_generate_report_summary_row(self):
        """测试汇总行"""
        file_stats = [
            {'filename': 'test1.xlsx', 'bank': '工商银行', 
             'original_rows': 100, 'valid_rows': 95, 'duplicates': 5, 'process_time': '1.0s'}
        ]
        final_stats = {
            'total_original': 100,
            'total_valid': 95,
            'total_duplicates': 5,
            'total_time': '1.0s'
        }
        result = generate_cleaning_report('张伟', file_stats, final_stats)
        summary_row = result.iloc[-1]
        assert summary_row['文件名'] == '【汇总】'
        assert summary_row['银行'] == '共1家银行'


class TestCleanAndMergeFiles:
    """测试清洗合并文件函数"""
    
    def test_clean_merge_empty_file_list(self):
        """测试空文件列表"""
        result, stats = clean_and_merge_files([], '张伟')
        assert result.empty
        assert stats == {}
    
    def test_clean_merge_with_valid_files(self, tmp_path):
        """测试有效文件处理"""
        # 创建测试Excel文件
        test_file = tmp_path / "test.xlsx"
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '交易摘要': ['工资']
        })
        df.to_excel(test_file, index=False)
        
        result, stats = clean_and_merge_files([str(test_file)], '张伟')
        assert len(result) > 0
        assert 'entity' in stats
        assert 'file_count' in stats
        assert stats['file_count'] == 1
    
    def test_clean_merge_stats_structure(self, tmp_path):
        """测试统计信息结构"""
        test_file = tmp_path / "test.xlsx"
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '交易摘要': ['工资']
        })
        df.to_excel(test_file, index=False)
        
        result, stats = clean_and_merge_files([str(test_file)], '张伟')
        expected_keys = ['entity', 'file_count', 'total_original', 
                        'total_valid', 'total_duplicates', 'final_rows', 
                        'total_time', 'file_stats']
        for key in expected_keys:
            assert key in stats


class TestSaveFormattedExcel:
    """测试格式化Excel保存函数"""
    
    def test_save_formatted_excel_basic(self, tmp_path):
        """测试基础Excel保存"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [1000],
            'expense': [0],
            'counterparty': ['公司'],
            'description': ['工资']
        })
        output_path = tmp_path / "output.xlsx"
        save_formatted_excel(df, str(output_path))
        assert output_path.exists()
    
    def test_save_formatted_excel_with_cash_flag(self, tmp_path):
        """测试现金标志处理"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [1000],
            'expense': [0],
            'counterparty': ['公司'],
            'description': ['工资'],
            'is_cash': [True]
        })
        output_path = tmp_path / "output.xlsx"
        save_formatted_excel(df, str(output_path))
        assert output_path.exists()
    
    def test_save_formatted_excel_column_mapping(self, tmp_path):
        """测试列名映射"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01']),
            'income': [1000],
            'expense': [0],
            'counterparty': ['公司'],
            'description': ['工资']
        })
        output_path = tmp_path / "output.xlsx"
        save_formatted_excel(df, str(output_path))
        
        # 读取保存的文件验证列名
        result_df = pd.read_excel(output_path)
        assert '交易时间' in result_df.columns
        assert '收入(元)' in result_df.columns
        assert '支出(元)' in result_df.columns
        assert '交易对手' in result_df.columns
        assert '交易摘要' in result_df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
