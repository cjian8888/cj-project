#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全类型转换工具模块

提供统一的、健壮的数据类型转换函数，供所有数据提取器使用。
"""

from typing import Optional
import pandas as pd


def safe_str(value) -> Optional[str]:
    """
    安全转换为字符串

    Args:
        value: 任意值

    Returns:
        字符串或None（如果值为空）
    """
    if pd.isna(value) or value is None:
        return None
    return str(value).strip()


def safe_float(value) -> Optional[float]:
    """
    安全转换为浮点数

    Args:
        value: 任意值

    Returns:
        浮点数或None（如果转换失败或值为空）
    """
    if pd.isna(value) or value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value) -> Optional[int]:
    """
    安全转换为整数

    Args:
        value: 任意值

    Returns:
        整数或None（如果转换失败或值为空）
    """
    if pd.isna(value) or value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def safe_date(value) -> Optional[str]:
    """
    安全转换为日期字符串(YYYY-MM-DD格式)

    Args:
        value: 日期值（可以是字符串、datetime对象等）

    Returns:
        日期字符串或None（如果转换失败或值为空）
    """
    if pd.isna(value) or value is None:
        return None
    try:
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)[:10]
    except (ValueError, TypeError):
        return None


def safe_datetime(value) -> Optional[str]:
    """
    安全转换为日期时间字符串(YYYY-MM-DD HH:MM:SS格式)

    Args:
        value: 日期时间值

    Returns:
        日期时间字符串或None（如果转换失败或值为空）
    """
    if pd.isna(value) or value is None:
        return None
    try:
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value).strip()[:19]
    except (ValueError, TypeError):
        return None


def extract_id_from_filename(filename: str) -> Optional[str]:
    """
    从文件名中提取身份证号

    提取规则：
    - 匹配18位数字（标准身份证号）
    - 匹配17位数字+X/x（最后一位为X的身份证号）

    Args:
        filename: 文件名

    Returns:
        身份证号或None（如果未找到）
    """
    import re

    # 匹配18位身份证号（17位数字+1位数字或X）
    patterns = [
        r"(\d{17}[\dXx])",  # 标准18位
        r"(\d{18})",  # 纯18位数字
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(1).upper()

    return None


def normalize_column_name(col_name: str) -> str:
    """
    标准化列名

    将各种变体的列名统一转换为标准格式

    Args:
        col_name: 原始列名

    Returns:
        标准化后的列名
    """
    import re

    if not col_name:
        return ""

    # 转换为小写并去除空格
    col = str(col_name).lower().strip()

    # 移除特殊字符
    col = re.sub(r"[^\w\u4e00-\u9fa5]", "", col)

    return col
