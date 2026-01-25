#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
银行格式模块单元测试

【修复说明】
- 问题20修复：银行格式检测准确率低
- 测试内容：测试改进的银行格式检测函数
- 修改日期：2026-01-25
"""

import pytest
import pandas as pd
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bank_formats import (
    _normalize_column_name,
    _calculate_column_match_score,
    _calculate_bank_format_score,
    detect_bank_format,
    COLUMN_WEIGHTS
)


class TestNormalizeColumnName:
    """测试列名规范化函数"""
    
    def test_normalize_with_spaces(self):
        """测试带空格的列名"""
        result = _normalize_column_name("  交易日期  ")
        assert result == "交易日期"
    
    def test_normalize_with_parentheses(self):
        """测试带括号的列名"""
        result = _normalize_column_name("收入(元)")
        assert result == "收入元"
    
    def test_normalize_with_chinese_parentheses(self):
        """测试带中文括号的列名"""
        result = _normalize_column_name("收入（元）")
        assert result == "收入元"
    
    def test_normalize_with_underscores(self):
        """测试带下划线的列名"""
        result = _normalize_column_name("交易_时间")
        assert result == "交易时间"
    
    def test_normalize_with_hyphens(self):
        """测试带连字符的列名"""
        result = _normalize_column_name("交易-时间")
        assert result == "交易时间"


class TestCalculateColumnMatchScore:
    """测试列名匹配分数计算函数"""
    
    def test_exact_match(self):
        """测试精确匹配"""
        df = pd.DataFrame({'交易日期': ['2024-01-01']})
        score, match_type = _calculate_column_match_score('交易日期', '交易日期', df)
        assert score == 1.0
        assert match_type == 'exact_match'
    
    def test_prefix_match(self):
        """测试前缀匹配"""
        score, match_type = _calculate_column_match_score('交易日期时间', '交易日期')
        assert score == 0.8
        assert match_type == 'prefix_match'
    
    def test_contains_match(self):
        """测试包含匹配"""
        score, match_type = _calculate_column_match_score('银行交易日期', '交易日期')
        assert score == 0.6
        assert match_type == 'contains_match'
    
    def test_similarity_match(self):
        """测试相似度匹配"""
        score, match_type = _calculate_column_match_score('交易日', '交易日期')
        assert score == 0.4
        assert match_type == 'similarity_match'
    
    def test_no_match(self):
        """测试无匹配"""
        score, match_type = _calculate_column_match_score('摘要', '日期')
        assert score == 0.0
        assert match_type == 'no_match'


class TestCalculateBankFormatScore:
    """测试银行格式分数计算函数"""
    
    def test_icbc_format_high_score(self):
        """测试工商银行格式高分"""
        df = pd.DataFrame({
            '交易日期': ['2024-01-01'],
            '交易时间': ['12:00:00'],
            '收入金额': [1000],
            '支出金额': [500],
            '交易余额': [500],
            '对方户名': ['张三'],
            '对方账号': ['123456'],
            '交易摘要': ['工资'],
            '交易流水号': ['123'],
            '本方账号': ['789']
        })
        
        from bank_formats import BANK_FORMATS
        score, details = _calculate_bank_format_score(df, BANK_FORMATS['ICBC'], verbose=False)
        
        # 应该匹配所有列，分数接近1.0
        assert score > 0.9
        assert details['matched_count'] == len(BANK_FORMATS['ICBC']['column_mapping'])
    
    def test_ccb_format_high_score(self):
        """测试建设银行格式高分"""
        df = pd.DataFrame({
            '交易日期': ['20240101'],
            '贷方发生额': [1000],
            '借方发生额': [500],
            '余额': [500],
            '对手账户名称': ['张三'],
            '对手账号': ['123456'],
            '交易摘要': ['工资'],
            '流水号': ['123'],
            '账号': ['789']
        })
        
        from bank_formats import BANK_FORMATS
        score, details = _calculate_bank_format_score(df, BANK_FORMATS['CCB'], verbose=False)
        
        # 应该匹配所有列，分数接近1.0
        assert score > 0.9
        assert details['matched_count'] == len(BANK_FORMATS['CCB']['column_mapping'])
    
    def test_partial_match_score(self):
        """测试部分匹配分数"""
        df = pd.DataFrame({
            '交易日期': ['2024-01-01'],
            '收入金额': [1000],
            '支出金额': [500]
        })
        
        from bank_formats import BANK_FORMATS
        score, details = _calculate_bank_format_score(df, BANK_FORMATS['ICBC'], verbose=False)
        
        # 只匹配了部分列，分数应该较低
        assert 0.3 < score < 0.6
        assert details['matched_count'] < len(BANK_FORMATS['ICBC']['column_mapping'])
    
    def test_weighted_score(self):
        """测试加权分数"""
        df = pd.DataFrame({
            '交易日期': ['2024-01-01'],  # 高权重列
            '收入金额': [1000],           # 高权重列
            '支出金额': [500],            # 高权重列
            '交易摘要': ['工资']            # 低权重列
        })
        
        from bank_formats import BANK_FORMATS
        score, details = _calculate_bank_format_score(df, BANK_FORMATS['ICBC'], verbose=False)
        
        # 匹配了高权重列，分数应该较高
        assert score > 0.5


class TestDetectBankFormat:
    """测试银行格式检测函数"""
    
    def test_detect_icbc_format(self):
        """测试检测工商银行格式"""
        df = pd.DataFrame({
            '交易日期': ['2024-01-01'],
            '交易时间': ['12:00:00'],
            '收入金额': [1000],
            '支出金额': [500],
            '交易余额': [500],
            '对方户名': ['张三'],
            '对方账号': ['123456'],
            '交易摘要': ['工资'],
            '交易流水号': ['123'],
            '本方账号': ['789']
        })
        
        result = detect_bank_format(df, verbose=False)
        assert result == 'ICBC'
    
    def test_detect_ccb_format(self):
        """测试检测建设银行格式"""
        df = pd.DataFrame({
            '交易日期': ['20240101'],
            '贷方发生额': [1000],
            '借方发生额': [500],
            '余额': [500],
            '对手账户名称': ['张三'],
            '对手账号': ['123456'],
            '交易摘要': ['工资'],
            '流水号': ['123'],
            '账号': ['789']
        })
        
        result = detect_bank_format(df, verbose=False)
        assert result == 'CCB'
    
    def test_detect_generic_format(self):
        """测试检测通用格式"""
        df = pd.DataFrame({
            '交易时间': ['2024-01-01'],
            '收入(元)': [1000],
            '支出(元)': [500],
            '余额(元)': [500],
            '交易对手': ['张三'],
            '交易摘要': ['工资']
        })
        
        result = detect_bank_format(df, verbose=False)
        assert result == 'GENERIC'
    
    def test_detect_with_low_score(self):
        """测试低分数情况"""
        df = pd.DataFrame({
            '摘要': ['测试'],
            '备注': ['备注']
        })
        
        result = detect_bank_format(df, verbose=False)
        # 分数太低，应该返回通用格式
        assert result == 'GENERIC'
    
    def test_detect_with_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame()
        
        result = detect_bank_format(df, verbose=False)
        assert result == 'GENERIC'
    
    def test_detect_with_none_dataframe(self):
        """测试None DataFrame"""
        result = detect_bank_format(None, verbose=False)
        assert result == 'GENERIC'


class TestColumnWeights:
    """测试列权重配置"""
    
    def test_date_column_weight(self):
        """测试日期列权重"""
        assert COLUMN_WEIGHTS['date'] == 3.0
    
    def test_income_column_weight(self):
        """测试收入列权重"""
        assert COLUMN_WEIGHTS['income'] == 2.0
    
    def test_expense_column_weight(self):
        """测试支出列权重"""
        assert COLUMN_WEIGHTS['expense'] == 2.0
    
    def test_balance_column_weight(self):
        """测试余额列权重"""
        assert COLUMN_WEIGHTS['balance'] == 1.5
    
    def test_description_column_weight(self):
        """测试摘要列权重"""
        assert COLUMN_WEIGHTS['description'] == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
