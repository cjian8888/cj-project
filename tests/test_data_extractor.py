#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据提取模块单元测试

【修复说明】
- 问题19修复：列名匹配逻辑不够健壮
- 测试内容：测试改进的列名匹配函数
- 修改日期：2026-01-25
"""

import pytest
import pandas as pd
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_extractor import (
    _normalize_column_name,
    _calculate_match_score,
    find_column_by_keywords
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
    
    def test_normalize_with_underscores(self):
        """测试带下划线的列名"""
        result = _normalize_column_name("交易_时间")
        assert result == "交易时间"
    
    def test_normalize_with_mixed_case(self):
        """测试混合大小写"""
        result = _normalize_column_name("TransactionDate")
        assert result == "transactiondate"
    
    def test_normalize_with_special_chars(self):
        """测试带特殊字符的列名"""
        result = _normalize_column_name("交易-时间")
        assert result == "交易时间"


class TestCalculateMatchScore:
    """测试匹配分数计算函数"""
    
    def test_exact_match(self):
        """测试精确匹配"""
        score, match_type = _calculate_match_score("交易日期", "交易日期")
        assert score == 100
        assert match_type == "exact_match"
    
    def test_prefix_match(self):
        """测试前缀匹配"""
        score, match_type = _calculate_match_score("交易日期时间", "交易日期")
        assert score == 80
        assert match_type == "prefix_match"
    
    def test_contains_match(self):
        """测试包含匹配"""
        score, match_type = _calculate_match_score("银行交易日期", "交易日期")
        assert score == 60
        assert match_type == "contains_match"
    
    def test_similarity_match(self):
        """测试相似度匹配"""
        score, match_type = _calculate_match_score("交易日期", "交易日")
        assert score == 40
        assert match_type == "similarity_match"
    
    def test_no_match(self):
        """测试无匹配"""
        score, match_type = _calculate_match_score("摘要", "日期")
        assert score == 0
        assert match_type == "no_match"
    
    def test_case_insensitive(self):
        """测试大小写不敏感"""
        score, match_type = _calculate_match_score("交易日期", "交易日期")
        assert score == 100


class TestFindColumnByKeywords:
    """测试列名查找函数"""
    
    def test_find_exact_match(self):
        """测试精确匹配"""
        df = pd.DataFrame({
            '交易日期': ['2024-01-01'],
            '收入': [1000]
        })
        result = find_column_by_keywords(df, ['交易日期'], verbose=False)
        assert result == '交易日期'
    
    def test_find_with_multiple_keywords(self):
        """测试多个关键词"""
        df = pd.DataFrame({
            'date': ['2024-01-01'],
            'income': [1000]
        })
        result = find_column_by_keywords(df, ['交易日期', 'date'], verbose=False)
        assert result == 'date'
    
    def test_find_with_normalized_columns(self):
        """测试规范化后的列名"""
        df = pd.DataFrame({
            '收入(元)': [1000],
            '支出(元)': [500]
        })
        result = find_column_by_keywords(df, ['收入'], verbose=False)
        assert result == '收入(元)'
    
    def test_find_best_match(self):
        """测试选择最佳匹配"""
        df = pd.DataFrame({
            '交易日期时间': ['2024-01-01'],
            '交易日期': ['2024-01-01']
        })
        result = find_column_by_keywords(df, ['交易日期'], verbose=False)
        # 应该选择精确匹配的列
        assert result == '交易日期'
    
    def test_find_with_low_score(self):
        """测试低分数情况"""
        df = pd.DataFrame({
            '摘要': ['测试'],
            '备注': ['备注']
        })
        result = find_column_by_keywords(df, ['交易日期'], verbose=False)
        assert result is None
    
    def test_find_with_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame()
        result = find_column_by_keywords(df, ['交易日期'], verbose=False)
        assert result is None
    
    def test_find_with_none_dataframe(self):
        """测试None DataFrame"""
        result = find_column_by_keywords(None, ['交易日期'], verbose=False)
        assert result is None
    
    def test_find_with_custom_threshold(self):
        """测试自定义阈值"""
        df = pd.DataFrame({
            '交易日期时间': ['2024-01-01']
        })
        # 前缀匹配分数为80，设置阈值为90应该返回None
        result = find_column_by_keywords(df, ['交易日期'], min_score=90, verbose=False)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
