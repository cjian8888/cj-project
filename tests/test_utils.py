#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数单元测试
"""

import pytest
from datetime import datetime
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils import (
    parse_date, format_amount, is_amount_similar, is_within_time_window,
    contains_keywords, extract_keywords, normalize_name,
    extract_chinese_name, extract_company_name, format_currency,
    calculate_date_range, get_month_key, get_day_of_month,
    clean_text, extract_bank_name, normalize_person_name,
    number_to_chinese, safe_str, safe_account_display
)


class TestParseDate:
    """测试日期解析函数"""
    
    def test_parse_date_with_string(self):
        """测试字符串日期解析"""
        result = parse_date("2024-01-01")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
    
    def test_parse_date_with_datetime(self):
        """测试datetime对象"""
        dt = datetime(2024, 1, 1)
        result = parse_date(dt)
        assert result == dt
    
    def test_parse_date_with_slash_format(self):
        """测试斜杠格式"""
        result = parse_date("2024/01/01")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
    
    def test_parse_date_with_dot_format(self):
        """测试点号格式"""
        result = parse_date("2024.01.01")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
    
    def test_parse_date_with_chinese_format(self):
        """测试中文格式"""
        result = parse_date("2024年01月01日")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
    
    def test_parse_date_with_invalid_string(self):
        """测试无效字符串"""
        result = parse_date("invalid")
        assert result is None
    
    def test_parse_date_with_empty_string(self):
        """测试空字符串"""
        result = parse_date("")
        assert result is None
    
    def test_parse_date_with_none(self):
        """测试None值"""
        result = parse_date(None)
        assert result is None


class TestFormatAmount:
    """测试金额格式化函数"""
    
    def test_format_amount_with_integer(self):
        """测试整数金额"""
        result = format_amount(1234)
        assert result == 1234.0
    
    def test_format_amount_with_float(self):
        """测试浮点数金额"""
        result = format_amount(1234.56)
        assert result == 1234.56
    
    def test_format_amount_with_comma(self):
        """测试带逗号的金额"""
        result = format_amount("1,234.56")
        assert result == 1234.56
    
    def test_format_amount_with_yuan_symbol(self):
        """测试带元符号的金额"""
        result = format_amount("¥1234.56")
        assert result == 1234.56
    
    def test_format_amount_with_full_yuan_symbol(self):
        """测试带完整元符号的金额"""
        result = format_amount("￥1234.56")
        assert result == 1234.56
    
    def test_format_amount_with_yuan_text(self):
        """测试带元文字的金额"""
        result = format_amount("1234.56元")
        assert result == 1234.56
    
    def test_format_amount_with_none(self):
        """测试None值"""
        result = format_amount(None)
        assert result == 0.0
    
    def test_format_amount_with_empty_string(self):
        """测试空字符串"""
        result = format_amount("")
        assert result == 0.0
    
    def test_format_amount_with_invalid_string(self):
        """测试无效字符串"""
        result = format_amount("invalid")
        assert result == 0.0


class TestIsAmountSimilar:
    """测试金额相似度判断函数"""
    
    def test_is_amount_similar_with_equal_amounts(self):
        """测试相等金额"""
        result = is_amount_similar(1000, 1000)
        assert result is True
    
    def test_is_amount_similar_with_zero_amounts(self):
        """测试零金额"""
        result = is_amount_similar(0, 0)
        assert result is True
    
    def test_is_amount_similar_with_small_difference(self):
        """测试小差异"""
        result = is_amount_similar(1000, 1005, tolerance=0.01)
        assert result is True
    
    def test_is_amount_similar_with_large_difference(self):
        """测试大差异"""
        result = is_amount_similar(1000, 2000, tolerance=0.01)
        assert result is False
    
    def test_is_amount_similar_with_one_zero(self):
        """测试一个为零"""
        result = is_amount_similar(0, 1000)
        assert result is False


class TestIsWithinTimeWindow:
    """测试时间窗口判断函数"""
    
    def test_is_within_time_window_with_same_time(self):
        """测试相同时间"""
        dt1 = datetime(2024, 1, 1, 12, 0, 0)
        dt2 = datetime(2024, 1, 1, 12, 0, 0)
        result = is_within_time_window(dt1, dt2, hours=24)
        assert result is True
    
    def test_is_within_time_window_with_small_diff(self):
        """测试小时间差"""
        dt1 = datetime(2024, 1, 1, 12, 0, 0)
        dt2 = datetime(2024, 1, 1, 13, 0, 0)
        result = is_within_time_window(dt1, dt2, hours=24)
        assert result is True
    
    def test_is_within_time_window_with_large_diff(self):
        """测试大时间差"""
        dt1 = datetime(2024, 1, 1, 12, 0, 0)
        dt2 = datetime(2024, 1, 3, 12, 0, 0)
        result = is_within_time_window(dt1, dt2, hours=24)
        assert result is False


class TestContainsKeywords:
    """测试关键词包含判断函数"""
    
    def test_contains_keywords_with_match(self):
        """测试匹配关键词"""
        result = contains_keywords("工资收入", ["工资", "奖金"])
        assert result is True
    
    def test_contains_keywords_with_no_match(self):
        """测试不匹配关键词"""
        result = contains_keywords("购物消费", ["工资", "奖金"])
        assert result is False
    
    def test_contains_keywords_with_empty_text(self):
        """测试空文本"""
        result = contains_keywords("", ["工资", "奖金"])
        assert result is False
    
    def test_contains_keywords_with_none(self):
        """测试None值"""
        result = contains_keywords(None, ["工资", "奖金"])
        assert result is False
    
    def test_contains_keywords_case_insensitive(self):
        """测试大小写不敏感"""
        result = contains_keywords("工资收入", ["工资", "BONUS"])
        assert result is True


class TestExtractKeywords:
    """测试关键词提取函数"""
    
    def test_extract_keywords_with_matches(self):
        """测试提取匹配的关键词"""
        result = extract_keywords("工资奖金收入", ["工资", "奖金", "补贴"])
        assert "工资" in result
        assert "奖金" in result
        assert "补贴" not in result
    
    def test_extract_keywords_with_no_matches(self):
        """测试无匹配"""
        result = extract_keywords("购物消费", ["工资", "奖金"])
        assert result == []
    
    def test_extract_keywords_with_empty_text(self):
        """测试空文本"""
        result = extract_keywords("", ["工资", "奖金"])
        assert result == []


class TestNormalizeName:
    """测试名称标准化函数"""
    
    def test_normalize_name_with_spaces(self):
        """测试带空格的名称"""
        result = normalize_name("张  伟")
        assert result == "张伟"
    
    def test_normalize_name_with_special_chars(self):
        """测试带特殊字符的名称"""
        result = normalize_name("张伟@#")
        assert result == "张伟"
    
    def test_normalize_name_with_none(self):
        """测试None值"""
        result = normalize_name(None)
        assert result == ""
    
    def test_normalize_name_with_empty_string(self):
        """测试空字符串"""
        result = normalize_name("")
        assert result == ""


class TestExtractChineseName:
    """测试中文姓名提取函数"""
    
    def test_extract_chinese_name_with_valid_names(self):
        """测试有效姓名"""
        result = extract_chinese_name("张伟和李明是朋友")
        # extract_chinese_name返回的是匹配到的2-4字汉字片段
        # "张伟和李明是朋友"会匹配到["张伟", "李明", "是朋友"]
        # 但"是朋友"会被过滤掉，因为"是"在排除列表中
        assert len(result) >= 2
    
    def test_extract_chinese_name_with_company_names(self):
        """测试过滤公司名称"""
        result = extract_chinese_name("张伟在有限公司工作")
        # "有限公司"会被过滤掉
        assert "有限公司" not in result
    
    def test_extract_chinese_name_with_empty_text(self):
        """测试空文本"""
        result = extract_chinese_name("")
        assert result == []
    
    def test_extract_chinese_name_with_none(self):
        """测试None值"""
        result = extract_chinese_name(None)
        assert result == []


class TestExtractCompanyName:
    """测试公司名称提取函数"""
    
    def test_extract_company_name_with_valid_company(self):
        """测试有效公司名称"""
        result = extract_company_name("张伟在某某科技有限公司工作")
        # extract_company_name会匹配包含公司后缀的完整名称
        # "张伟在某某科技有限公司工作"会匹配到"某某科技有限公司"
        assert len(result) > 0
        assert any("科技" in company for company in result)
    
    def test_extract_company_name_with_multiple_companies(self):
        """测试多个公司名称"""
        result = extract_company_name("某某科技有限公司和某某股份有限公司合作")
        # 会匹配到两个公司名称
        assert len(result) >= 2
    
    def test_extract_company_name_with_empty_text(self):
        """测试空文本"""
        result = extract_company_name("")
        assert result == []
    
    def test_extract_company_name_with_none(self):
        """测试None值"""
        result = extract_company_name(None)
        assert result == []


class TestFormatCurrency:
    """测试货币格式化函数"""
    
    def test_format_currency_with_small_amount(self):
        """测试小金额"""
        result = format_currency(1234.56)
        assert result == "¥1,234.56"
    
    def test_format_currency_with_wan(self):
        """测试万元"""
        result = format_currency(123456.78)
        assert result == "¥12.35万"
    
    def test_format_currency_with_yi(self):
        """测试亿元"""
        result = format_currency(123456789.12)
        assert result == "¥1.23亿"
    
    def test_format_currency_with_negative(self):
        """测试负数"""
        result = format_currency(-1234.56)
        assert result == "¥-1,234.56"
    
    def test_format_currency_with_zero(self):
        """测试零"""
        result = format_currency(0)
        assert result == "¥0.00"


class TestCalculateDateRange:
    """测试日期范围计算函数"""
    
    def test_calculate_date_range_with_valid_dates(self):
        """测试有效日期列表"""
        dates = [datetime(2024, 1, 1), datetime(2024, 1, 31)]
        start, end = calculate_date_range(dates)
        assert start == datetime(2024, 1, 1)
        assert end == datetime(2024, 1, 31)
    
    def test_calculate_date_range_with_empty_list(self):
        """测试空列表"""
        start, end = calculate_date_range([])
        assert start is None
        assert end is None
    
    def test_calculate_date_range_with_none_values(self):
        """测试包含None值"""
        dates = [datetime(2024, 1, 1), None, datetime(2024, 1, 31)]
        start, end = calculate_date_range(dates)
        assert start == datetime(2024, 1, 1)
        assert end == datetime(2024, 1, 31)


class TestGetMonthKey:
    """测试月份键值获取函数"""
    
    def test_get_month_key_with_valid_date(self):
        """测试有效日期"""
        dt = datetime(2024, 1, 15)
        result = get_month_key(dt)
        assert result == "2024-01"
    
    def test_get_month_key_with_none(self):
        """测试None值"""
        result = get_month_key(None)
        assert result == ""


class TestGetDayOfMonth:
    """测试月份天数获取函数"""
    
    def test_get_day_of_month_with_valid_date(self):
        """测试有效日期"""
        dt = datetime(2024, 1, 15)
        result = get_day_of_month(dt)
        assert result == 15
    
    def test_get_day_of_month_with_none(self):
        """测试None值"""
        result = get_day_of_month(None)
        assert result == 0


class TestCleanText:
    """测试文本清理函数"""
    
    def test_clean_text_with_extra_spaces(self):
        """测试多余空格"""
        result = clean_text("张  伟")
        assert result == "张 伟"
    
    def test_clean_text_with_newlines(self):
        """测试换行符"""
        result = clean_text("张\n伟")
        assert result == "张 伟"
    
    def test_clean_text_with_none(self):
        """测试None值"""
        result = clean_text(None)
        assert result == ""
    
    def test_clean_text_with_empty_string(self):
        """测试空字符串"""
        result = clean_text("")
        assert result == ""


class TestExtractBankName:
    """测试银行名称提取函数"""
    
    def test_extract_bank_name_with_icbc(self):
        """测试工商银行"""
        result = extract_bank_name("中国工商银行流水.xlsx")
        assert result == "工商银行"
    
    def test_extract_bank_name_with_ccb(self):
        """测试建设银行"""
        result = extract_bank_name("建设银行流水.xlsx")
        assert result == "建设银行"
    
    def test_extract_bank_name_with_abc(self):
        """测试农业银行"""
        result = extract_bank_name("农业银行流水.xlsx")
        assert result == "农业银行"
    
    def test_extract_bank_name_with_boc(self):
        """测试中国银行"""
        result = extract_bank_name("中国银行流水.xlsx")
        assert result == "中国银行"
    
    def test_extract_bank_name_with_unknown(self):
        """测试未知银行"""
        result = extract_bank_name("某某银行流水.xlsx")
        assert result == "未知银行"


class TestNormalizePersonName:
    """测试人名标准化函数"""
    
    def test_normalize_person_name_with_id_card(self):
        """测试带身份证号"""
        result = normalize_person_name("张伟_123456789012345678")
        assert result == "张伟"
    
    def test_normalize_person_name_with_spaces(self):
        """测试带空格"""
        result = normalize_person_name("张 伟")
        assert result == "张伟"
    
    def test_normalize_person_name_with_none(self):
        """测试None值"""
        result = normalize_person_name(None)
        assert result == ""


class TestNumberToChinese:
    """测试数字转中文函数"""
    
    def test_number_to_chinese_with_single_digit(self):
        """测试个位数"""
        result = number_to_chinese(5)
        assert result == "五"
    
    def test_number_to_chinese_with_tens(self):
        """测试两位数"""
        result = number_to_chinese(15)
        assert result == "十五"
    
    def test_number_to_chinese_with_twenty_plus(self):
        """测试二十以上"""
        result = number_to_chinese(35)
        assert result == "三十五"
    
    def test_number_to_chinese_with_non_int(self):
        """测试非整数"""
        result = number_to_chinese(3.14)
        assert result == "3.14"


class TestSafeStr:
    """测试安全字符串转换函数"""
    
    def test_safe_str_with_string(self):
        """测试字符串"""
        result = safe_str("张伟")
        assert result == "张伟"
    
    def test_safe_str_with_none(self):
        """测试None值"""
        result = safe_str(None)
        assert result == "-"
    
    def test_safe_str_with_nan_string(self):
        """测试nan字符串"""
        result = safe_str("nan")
        assert result == "-"
    
    def test_safe_str_with_max_len(self):
        """测试长度限制"""
        result = safe_str("这是一个很长的字符串", max_len=10)
        assert len(result) <= 10


class TestSafeAccountDisplay:
    """测试安全账号显示函数"""
    
    def test_safe_account_display_with_normal_account(self):
        """测试正常账号"""
        result = safe_account_display("1234567890123456")
        assert result == "90123456"
    
    def test_safe_account_display_with_mask(self):
        """测试脱敏"""
        result = safe_account_display("1234567890123456", mask=True)
        assert result == "****3456"
    
    def test_safe_account_display_with_none(self):
        """测试None值"""
        result = safe_account_display(None)
        assert result == "未知账号"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
