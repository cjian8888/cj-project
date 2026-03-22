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
import warnings

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_cleaner import (
    deduplicate_transactions, validate_data_quality,
    standardize_bank_fields, generate_cleaning_report,
    clean_and_merge_files, save_formatted_excel,
    _read_transaction_file,
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
            'date': pd.to_datetime(['2024-01-01 10:00:00', '2024-01-01 10:00:00']),
            'income': [1000, 1000],
            'expense': [0, 0],
            'counterparty': ['公司', '公司'],
            'description': ['工资', '工资']
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 1
        assert stats['duplicates'] == 1

    def test_deduplicate_prefers_transaction_id_even_when_coverage_is_low(self):
        """只要单行有有效流水号，就应优先按流水号精确去重"""
        df = pd.DataFrame({
            'date': pd.to_datetime([
                '2024-01-01 10:00:00',
                '2024-01-01 10:05:00',
                '2024-01-01 10:10:00',
            ]),
            'income': [1000, 1000, 500],
            'expense': [0, 0, 0],
            'counterparty': ['甲公司', '甲公司', '乙公司'],
            'description': ['工资', '工资', '补贴'],
            'transaction_id': ['TX-001', 'TX-001', ''],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 2
        assert stats['duplicates'] == 1

    def test_deduplicate_transaction_id_keeps_principal_and_fee_rows(self):
        """同一流水号下的主交易和手续费属于合法双分录，不能再压成一条"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-02-09 15:27:30', '2025-02-09 15:27:30']),
            'income': [0, 0],
            'expense': [500000, 9],
            'counterparty': ['北京鑫兴航科技有限公司', ''],
            'description': ['对公转账', '账户转账手续费'],
            'transaction_id': ['1020013L31739086049635167', '1020013L31739086049635167'],
            '数据来源': ['中国建设银行交易流水.xlsx', '中国建设银行交易流水.xlsx'],
            'source_row_index': [11, 12],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 2
        assert stats['duplicates'] == 0
        assert set(result['expense'].astype(float).tolist()) == {500000.0, 9.0}

    def test_deduplicate_transaction_id_keeps_opposite_direction_pair_rows(self):
        """同一流水号下一进一出的合法双分录不能被流水号去重误删"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-02-04 10:58:48', '2025-02-04 10:58:48']),
            'income': [0, 110000],
            'expense': [110000, 0],
            'counterparty': ['于巧云', '于巧云'],
            'description': ['', ''],
            'transaction_id': ['ECT0001J70340000', 'ECT0001J70340000'],
            'account_number': ['6222600220004293728', '6222600220004293728'],
            '数据来源': ['交通银行交易流水.xlsx', '交通银行交易流水.xlsx'],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 2
        assert stats['duplicates'] == 0
        assert sorted(result['income'].astype(float).tolist()) == [0.0, 110000.0]
        assert sorted(result['expense'].astype(float).tolist()) == [0.0, 110000.0]

    def test_deduplicate_placeholder_transaction_id_keeps_distinct_rows(self):
        """占位流水号 '-' 不能再把不同日期/金额的合法记录压成一条"""
        df = pd.DataFrame({
            'date': pd.to_datetime([
                '2025-03-21 00:07:54',
                '2025-06-21 00:31:15',
            ]),
            'income': [0.17, 0.18],
            'expense': [0, 0],
            'counterparty': ['', ''],
            'description': ['利息存入', '利息存入'],
            'transaction_id': ['-', '-'],
            '数据来源': ['中国建设银行交易流水.xlsx', '中国建设银行交易流水.xlsx'],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 2
        assert stats['duplicates'] == 0

    def test_deduplicate_transaction_id_collapses_same_sign_same_amount_mirror_rows(self):
        """同流水号/同方向/同金额的银行镜像重复应继续视为重复，只保留一条"""
        df = pd.DataFrame({
            'date': pd.to_datetime([
                '2024-12-07 15:29:36',
                '2024-11-22 00:00:00',
            ]),
            'income': [104212.55, 104212.55],
            'expense': [0, 0],
            'counterparty': ['', ''],
            'description': ['', ''],
            'transaction_id': [
                'ORXTNA2412073100020000012145',
                'ORXTNA2412073100020000012145',
            ],
            'account_number': ['103324757001001', '103324757001001'],
            '数据来源': ['招商银行股份有限公司交易流水.xlsx', '招商银行股份有限公司交易流水.xlsx'],
            'source_row_index': [1626, 1642],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 1
        assert stats['duplicates'] == 1
        assert float(result.iloc[0]['income']) == 104212.55

    def test_deduplicate_exact_blank_natural_key_template_rows(self):
        """无流水号且对手方/摘要全空的模板重复行应按精确自然键去重"""
        df = pd.DataFrame({
            'date': pd.to_datetime([
                '2024-06-29 00:00:00',
                '2024-06-29 00:00:00',
                '2024-06-29 00:00:00',
            ]),
            'income': [8.71, 8.71, 8.71],
            'expense': [0, 0, 0],
            'counterparty': ['', '', ''],
            'description': ['', '', ''],
            'account_number': ['6221482883736688'] * 3,
            'transaction_id': ['', '', ''],
            '数据来源': ['上海银行交易流水.xlsx'] * 3,
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 1
        assert stats['duplicates'] == 2

    def test_deduplicate_zero_amount_exact_natural_key_rows(self):
        """无流水号的零金额信息行，只要自然键完全一致也应压重"""
        df = pd.DataFrame({
            'date': pd.to_datetime([
                '2023-06-21 00:00:00',
                '2023-06-21 00:00:00',
            ]),
            'income': [0, 0],
            'expense': [0, 0],
            'counterparty': ['', ''],
            'description': ['个人活期结息', '个人活期结息'],
            'account_number': ['335801100399267', '335801100399267'],
            'transaction_id': ['', ''],
            '数据来源': ['中国农业银行交易流水.xlsx'] * 2,
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 1
        assert stats['duplicates'] == 1

    def test_deduplicate_same_amount_same_summary_one_second_apart_is_not_removed_without_balance_anchor(self):
        """同账号同金额同摘要但仅相差 1 秒的连续转账，不应再被粗暴去重"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01 10:00:00', '2024-01-01 10:00:01']),
            'income': [0, 0],
            'expense': [5000, 5000],
            'counterparty': ['贵州锐晶科技有限公司', '贵州锐晶科技有限公司'],
            'description': ['对公转账', '对公转账'],
            'account_number': ['6222000011112222', '6222000011112222'],
            'transaction_channel': ['网银', '网银'],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 2
        assert stats['duplicates'] == 0

    def test_deduplicate_different_transaction_ids_are_never_heuristically_merged(self):
        """不同非空流水号的交易，即使特征高度相似也不能再被启发式误删"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-05-22 11:22:14', '2024-05-22 11:22:15']),
            'income': [0, 0],
            'expense': [3.57, 3.57],
            'counterparty': ['', ''],
            'description': ['支付宝-上海盒马网络科技有限公司', '支付宝-上海盒马网络科技有限公司'],
            'account_number': ['2470649_156', '2470649_156'],
            'balance': [329.30, 329.30],
            'transaction_channel': ['第三方支付', '第三方支付'],
            'transaction_id': ['TX001', 'TX002'],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 2
        assert stats['duplicates'] == 0
    
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

    def test_deduplicate_same_prefix_but_different_balance_not_removed(self):
        """同金额同前缀摘要但余额不同时不应误删"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01 10:00:00', '2024-01-01 10:00:01']),
            'income': [5000, 5000],
            'expense': [0, 0],
            'counterparty': ['代发平台', '代发平台'],
            'description': ['batch-pay-0001-A', 'batch-pay-0001-B'],
            'balance': [120000, 115000],
            'account_number': ['6222000011112222', '6222000011112222'],
            'transaction_channel': ['网银', '网银'],
            'source_file': ['工资批次.xlsx', '工资批次.xlsx'],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 2
        assert stats['duplicates'] == 0

    def test_deduplicate_same_amount_same_summary_but_different_account_not_removed(self):
        """同金额同摘要但账号不同不应误删"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01 10:00:00', '2024-01-01 10:00:01']),
            'income': [2000, 2000],
            'expense': [0, 0],
            'counterparty': ['某公司', '某公司'],
            'description': ['工资发放', '工资发放'],
            'account_number': ['6222000011112222', '6222000011113333'],
            'transaction_channel': ['手机银行', '手机银行'],
            'source_file': ['工资批次.xlsx', '工资批次.xlsx'],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 2
        assert stats['duplicates'] == 0

    def test_deduplicate_uses_strong_signals_when_counterparty_missing(self):
        """对手方缺失时可借助强特征确认重复"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01 10:00:00', '2024-01-01 10:00:01']),
            'income': [3000, 3000],
            'expense': [0, 0],
            'counterparty': ['', ''],
            'description': ['批量代发', '批量代发'],
            'balance': [98000, 98000],
            'account_number': ['6222000011112222', '6222000011112222'],
            'transaction_channel': ['网银', '网银'],
            'source_file': ['工资批次.xlsx', '工资批次.xlsx'],
        })
        result, stats = deduplicate_transactions(df)
        assert len(result) == 1
        assert stats['duplicates'] == 1


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
        assert result.empty
        assert '缺少日期字段' in report['warnings']
        assert report['valid_rows'] == 0
        assert report['removed_rows'] == 2

    def test_validate_all_missing_dates_returns_empty_dataframe(self):
        """测试日期全空时整批记录被剔除"""
        df = pd.DataFrame({
            'date': [pd.NaT, pd.NaT],
            'income': [0, 0],
            'expense': [0, 0],
            'description': ['回执', '回执']
        })
        result, report = validate_data_quality(df)

        assert result.empty
        assert '缺少日期字段' in report['warnings']
        assert report['invalid_rows'] == [0, 1]
        assert report['valid_rows'] == 0
        assert report['removed_rows'] == 2

    def test_validate_keeps_account_only_placeholder_rows_without_dates(self):
        """无日期但仅包含账号查询反馈的记录，应保留在主流水笔数口径中"""
        df = pd.DataFrame({
            'date': [pd.NaT, pd.NaT],
            'income': [0, 0],
            'expense': [0, 0],
            'description': ['', ''],
            'counterparty': ['', ''],
            'account_number': ['980200018624738', '97280150300025111'],
            'transaction_id': ['', ''],
        })
        result, report = validate_data_quality(df)

        assert len(result) == 2
        assert '缺少日期字段' in report['warnings']
        assert '无日期的信息型查询反馈记录' in str(report['warnings'])
        assert report['valid_rows'] == 2
        assert report['removed_rows'] == 0
        assert report['audit_alerts']['missing_date_placeholders']['count'] == 2
    
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

    def test_validate_invalid_transaction_status_rows_are_removed(self):
        """失败/冲正/退汇等状态应从主流水剔除"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']),
            'income': [1000, 2000, 3000],
            'expense': [0, 0, 0],
            'description': ['工资', '冲正', '奖金'],
            'transaction_status': ['交易成功', '冲正成功', '交易失败'],
        })
        result, report = validate_data_quality(df)
        assert len(result) == 1
        assert '无效交易状态记录' in str(report['warnings'])
        assert report['audit_alerts']['invalid_transaction_status']['count'] == 2
    
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

    def test_validate_abnormal_empty_description_alert(self):
        """摘要大面积缺失时应给出更强审计提示"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']),
            'income': [1000, 2000, 3000, 4000],
            'expense': [0, 0, 0, 0],
            'description': ['', '', '', '工资']
        })
        result, report = validate_data_quality(df)
        assert '异常空摘要' in str(report['warnings'])
        assert report['audit_alerts']['empty_description']['count'] == 3

    def test_validate_abnormal_zero_balance_alert(self):
        """大量零余额时应提示核查余额缺失或过桥清空"""
        df = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04']),
            'income': [1000, 2000, 3000, 4000],
            'expense': [0, 0, 0, 0],
            'balance': [0, 0, 0, 100],
            'description': ['工资', '奖金', '补贴', '报销']
        })
        result, report = validate_data_quality(df)
        assert '异常零余额' in str(report['warnings'])
        assert report['audit_alerts']['zero_balance']['count'] == 3

    def test_validate_repeated_date_segment_alert(self):
        """同一时间戳批量重复时应输出日期段异常提示"""
        df = pd.DataFrame({
            'date': pd.to_datetime([
                '2024-01-01 10:00:00',
                '2024-01-01 10:00:00',
                '2024-01-01 10:00:00',
                '2024-01-02 09:00:00',
            ]),
            'income': [1000, 1000, 1000, 2000],
            'expense': [0, 0, 0, 0],
            'description': ['工资', '工资', '工资', '奖金']
        })
        result, report = validate_data_quality(df)
        assert '异常重复日期段' in str(report['warnings'])
        assert report['audit_alerts']['repeated_date_segments']['segments'] == 1
    
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

    def test_standardize_unknown_debit_credit_flag_does_not_default_to_expense(self):
        """借贷标志缺失且无明确收入关键词时，不应被默认记成支出"""
        df = pd.DataFrame({
            '交易时间': ['2024-12-05 23:59:59'],
            '交易金额': ['1053.42'],
            '借贷标志': [None],
            '交易摘要': ['利息'],
        })
        result = standardize_bank_fields(df)
        assert float(result.iloc[0]['income']) == 0.0
        assert float(result.iloc[0]['expense']) == 0.0
    
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

    def test_standardize_with_common_counterparty_header(self):
        """测试常见交易对手列名也能标准化"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '交易对手': ['某某公司']
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

    def test_standardize_with_transaction_status(self):
        """测试交易状态列标准化"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '交易状态': ['交易失败'],
        })
        result = standardize_bank_fields(df)
        assert 'transaction_status' in result.columns
        assert result.iloc[0]['transaction_status'] == '交易失败'

    def test_standardize_accepts_transaction_success_status_column_name(self):
        """真实银行文件中的“交易是否成功”也应映射到 transaction_status"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '交易是否成功': ['交易失败'],
        })
        result = standardize_bank_fields(df)
        assert result.iloc[0]['transaction_status'] == '交易失败'

    def test_standardize_preserves_signed_amounts_with_debit_credit_flag(self):
        """带借贷标志的负数金额应保留原始符号，不能被绝对值化"""
        df = pd.DataFrame({
            '交易时间': ['2025-06-29 15:41:00'],
            '交易金额': ['-320000.00'],
            '借贷标志': ['出'],
            '交易摘要': ['往来款'],
            '交易对方名称': ['武汉志航电子科技有限公司'],
        })
        result = standardize_bank_fields(df)
        assert float(result.iloc[0]['income']) == 0.0
        assert float(result.iloc[0]['expense']) == -320000.0
    
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

    def test_standardize_personal_card_not_flipped_by_company_counterparty(self):
        """个人银行卡不能因为对手方是公司就被误判为对公账户"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '本方账号': ['6222600220004293728'],
            '交易对方名称': ['支付宝（中国）网络技术有限公司'],
            '交易摘要': ['网上支付退款']
        })
        result = standardize_bank_fields(df, bank_name='交通银行', entity_name='于巧云')
        assert result.iloc[0]['account_type'] == '借记卡'
        assert result.iloc[0]['account_category'] == '个人账户'
        assert bool(result.iloc[0]['is_real_bank_card']) is True

    def test_standardize_short_numeric_account_still_identified_as_corporate(self):
        """个人主体下的短位纯数字账号仍应识别为对公账户"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [88000],
            '借贷标志': ['贷'],
            '本方账号': ['496271366239'],
            '交易对方名称': ['北京智晟睿科技有限公司'],
            '交易摘要': ['IBPS1021000999962024010530562210']
        })
        result = standardize_bank_fields(df, bank_name='中国银行', entity_name='王永安')
        assert result.iloc[0]['account_type'] == '对公结算账户'
        assert result.iloc[0]['account_category'] == '对公账户'
        assert bool(result.iloc[0]['is_real_bank_card']) is True

    def test_standardize_parses_wan_unit_values(self):
        """金额字段中的万/万元应统一换算为元"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': ['100万'],
            '借贷标志': ['贷'],
            '交易余额': ['1.5万']
        })
        result = standardize_bank_fields(df)
        assert result.iloc[0]['income'] == 1000000.0
        assert result.iloc[0]['balance'] == 15000.0

    def test_standardize_supports_unit_in_column_name_and_invalid_date(self):
        """列头带万元且日期异常时不应崩溃"""
        df = pd.DataFrame({
            '交易时间': [45292, '坏日期'],
            '收入(万元)': ['1.2', '0'],
            '摘要': ['工资', '奖金']
        })
        result = standardize_bank_fields(df)
        assert result.iloc[0]['income'] == 12000.0
        assert pd.notna(result.iloc[0]['date'])
        assert pd.isna(result.iloc[1]['date'])

    def test_standardize_handles_categorical_account_and_transaction_id(self):
        """Categorical 文本列不应因 fillna 写入新类别而崩溃"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01', '2024-01-02'],
            '交易金额': [1000, 2000],
            '借贷标志': ['贷', '借'],
            '本方账号': pd.Categorical(['6222000011112222', None]),
            '交易流水号': pd.Categorical(['TX001', None]),
            '交易摘要': ['工资', '还款'],
        })
        result = standardize_bank_fields(df)
        assert result.iloc[0]['account_number'] == '6222000011112222'
        assert result.iloc[1]['account_number'] == ''
        assert result.iloc[0]['transaction_id'] == 'TX001'
        assert result.iloc[1]['transaction_id'] == ''

    def test_standardize_handles_categorical_description_and_counterparty(self):
        """description / counterparty 为 Categorical 时也应稳定清洗"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01', '2024-01-02'],
            '交易金额': [1000, 2000],
            '借贷标志': ['贷', '借'],
            '交易摘要': pd.Categorical([' 工资入账 ', None]),
            '交易对手': pd.Categorical([' 某某公司 ', None]),
        })
        result = standardize_bank_fields(df)
        assert result.iloc[0]['description'] == '工资入账'
        assert result.iloc[1]['description'] == ''
        assert result.iloc[0]['counterparty'] == '某某公司'
        assert result.iloc[1]['counterparty'] == ''

    def test_standardize_keeps_salary_signal_from_transaction_type_when_summary_is_weak(self):
        """交易摘要仅为“正常”时，仍应保留交易类型里的工资语义"""
        df = pd.DataFrame({
            '交易时间': ['2025-05-25 03:32:30'],
            '交易金额': [4500],
            '借贷标志': ['进'],
            '交易类型': ['工资'],
            '交易摘要': ['正常'],
            '交易对方名称': [None],
        })
        result = standardize_bank_fields(df)
        assert result.iloc[0]['description'] == '工资 正常'

    def test_standardize_keeps_cash_signal_from_transaction_type_when_summary_is_weak(self):
        """交易摘要仅为“正常”时，仍应保留交易类型里的现金语义并标记 is_cash"""
        df = pd.DataFrame({
            '交易时间': ['2024-08-18 16:47:14'],
            '交易金额': [10000],
            '借贷标志': ['进'],
            '交易类型': ['ATM存款'],
            '交易摘要': ['正常'],
            '交易对方名称': [None],
        })
        result = standardize_bank_fields(df)
        assert result.iloc[0]['description'] == 'ATM存款 正常'
        assert bool(result.iloc[0]['is_cash']) is True


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

    def test_read_transaction_file_preserves_leading_zero_txid(self, tmp_path):
        """读取 Excel 时应保留流水号前导零"""
        test_file = tmp_path / "leading_zero.xlsx"
        pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': ['100'],
            '借贷标志': ['贷'],
            '交易流水号': ['00000000125'],
        }).to_excel(test_file, index=False)

        result = _read_transaction_file(str(test_file))

        assert str(result.iloc[0]['交易流水号']) == '00000000125'

    def test_clean_merge_empty_file_list(self):
        """测试空文件列表"""
        result, stats = clean_and_merge_files([], '张伟')
        assert result.empty

    def test_clean_merge_supports_csv(self):
        """测试 CSV 文件也可进入标准清洗流程"""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, '工商银行.csv')
            pd.DataFrame({
                '交易时间': ['2024-01-01'],
                '交易金额': ['100万'],
                '借贷标志': ['贷']
            }).to_csv(csv_path, index=False, encoding='utf-8-sig')

            result, stats = clean_and_merge_files([csv_path], '张伟')

            assert len(result) == 1
            assert result.iloc[0]['income'] == 1000000.0
            assert stats['final_rows'] == 1
    
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

    def test_clean_merge_drops_file_when_all_dates_missing(self, tmp_path):
        """测试整份日期全空文件不会混入最终清洗结果"""
        test_file = tmp_path / "invalid_dates.xlsx"
        pd.DataFrame({
            '交易时间': [None, None],
            '本方账号': ['6222000000000001', '6222000000000002'],
            '交易金额': [None, None],
            '借贷标志': [None, None],
            '交易摘要': ['超出查询年限', '超出查询年限'],
        }).to_excel(test_file, index=False)

        result, stats = clean_and_merge_files([str(test_file)], '张伟')

        assert result.empty
        assert stats['total_original'] == 2
        assert stats['total_valid'] == 0
        assert stats['final_rows'] == 0
        assert stats['file_stats'][0]['valid_rows'] == 0

    def test_clean_merge_skips_empty_frames_without_concat_futurewarning(self, tmp_path):
        """测试空清洗结果不会参与 concat 并触发 FutureWarning"""
        invalid_file = tmp_path / "invalid_dates.xlsx"
        valid_file = tmp_path / "valid.xlsx"

        pd.DataFrame({
            '交易时间': [None, None],
            '本方账号': ['6222000000000001', '6222000000000002'],
            '交易金额': [None, None],
            '借贷标志': [None, None],
            '交易摘要': ['超出查询年限', '超出查询年限'],
        }).to_excel(invalid_file, index=False)

        pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '交易金额': [1000],
            '借贷标志': ['贷'],
            '交易摘要': ['工资'],
        }).to_excel(valid_file, index=False)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            result, stats = clean_and_merge_files(
                [str(invalid_file), str(valid_file)], '张伟'
            )

        future_warnings = [
            warning for warning in caught if issubclass(warning.category, FutureWarning)
        ]
        assert not future_warnings
        assert len(result) == 1
        assert stats['total_original'] == 3
        assert stats['total_valid'] == 1
        assert stats['final_rows'] == 1


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
