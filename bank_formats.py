#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多数据源配置模块 - 支持不同银行格式的数据导入
"""

from typing import Dict, List, Optional
import pandas as pd


# ============== 银行格式配置 ==============

BANK_FORMATS = {
    # 工商银行格式
    'ICBC': {
        'name': '中国工商银行',
        'column_mapping': {
            '交易日期': 'date',
            '交易时间': 'time',
            '收入金额': 'income',
            '支出金额': 'expense',
            '交易余额': 'balance',
            '对方户名': 'counterparty',
            '对方账号': 'counterparty_account',
            '摘要': 'description',
            '交易流水号': 'transaction_id',
            '本方账号': 'account_number'
        },
        'date_format': '%Y-%m-%d',
        'encoding': 'utf-8',
        'skip_rows': 0,
        'header_row': 0
    },
    
    # 建设银行格式
    'CCB': {
        'name': '中国建设银行',
        'column_mapping': {
            '交易日期': 'date',
            '贷方发生额': 'income',
            '借方发生额': 'expense',
            '余额': 'balance',
            '对手账户名称': 'counterparty',
            '对手账号': 'counterparty_account',
            '交易摘要': 'description',
            '流水号': 'transaction_id',
            '账号': 'account_number'
        },
        'date_format': '%Y%m%d',
        'encoding': 'gbk',
        'skip_rows': 1,
        'header_row': 0
    },
    
    # 农业银行格式
    'ABC': {
        'name': '中国农业银行',
        'column_mapping': {
            '日期': 'date',
            '存入': 'income',
            '支取': 'expense',
            '余额': 'balance',
            '对方户名': 'counterparty',
            '备注': 'description',
            '账号': 'account_number'
        },
        'date_format': '%Y-%m-%d',
        'encoding': 'utf-8',
        'skip_rows': 0,
        'header_row': 0
    },
    
    # 中国银行格式
    'BOC': {
        'name': '中国银行',
        'column_mapping': {
            '交易日期': 'date',
            '贷': 'income',
            '借': 'expense',
            '账户余额': 'balance',
            '收/付方名称': 'counterparty',
            '摘要': 'description',
            '交易卡号/账号': 'account_number'
        },
        'date_format': '%Y/%m/%d',
        'encoding': 'utf-8',
        'skip_rows': 0,
        'header_row': 0
    },
    
    # 招商银行格式
    'CMB': {
        'name': '招商银行',
        'column_mapping': {
            '交易日': 'date',
            '入账金额': 'income',
            '支出金额': 'expense',
            '账户余额': 'balance',
            '交易对方': 'counterparty',
            '交易摘要': 'description',
            '卡号': 'account_number'
        },
        'date_format': '%Y-%m-%d',
        'encoding': 'utf-8',
        'skip_rows': 0,
        'header_row': 0
    },
    
    # 通用格式（默认）
    'GENERIC': {
        'name': '通用格式',
        'column_mapping': {
            '交易时间': 'date',
            '收入(元)': 'income',
            '支出(元)': 'expense',
            '余额(元)': 'balance',
            '交易对手': 'counterparty',
            '交易摘要': 'description',
            '本方账号': 'account_number',
            '所属银行': 'bank_name'
        },
        'date_format': None,  # 自动检测
        'encoding': 'utf-8',
        'skip_rows': 0,
        'header_row': 0
    }
}


def detect_bank_format(df: pd.DataFrame) -> str:
    """
    自动检测银行格式
    
    Args:
        df: 原始数据DataFrame
        
    Returns:
        银行格式代码 (如 'ICBC', 'CCB', 'GENERIC')
    """
    columns = set(df.columns.tolist())
    
    best_match = 'GENERIC'
    best_score = 0
    
    for bank_code, config in BANK_FORMATS.items():
        if bank_code == 'GENERIC':
            continue
            
        mapping = config['column_mapping']
        match_count = len(set(mapping.keys()) & columns)
        match_ratio = match_count / len(mapping)
        
        if match_ratio > best_score:
            best_score = match_ratio
            best_match = bank_code
    
    # 至少匹配50%的列才认为是该银行格式
    if best_score < 0.5:
        best_match = 'GENERIC'
    
    return best_match


def normalize_dataframe(df: pd.DataFrame, bank_format: str = None) -> pd.DataFrame:
    """
    将银行特定格式转换为标准格式
    
    Args:
        df: 原始数据DataFrame
        bank_format: 银行格式代码，None则自动检测
        
    Returns:
        标准化后的DataFrame
    """
    if bank_format is None:
        bank_format = detect_bank_format(df)
    
    config = BANK_FORMATS.get(bank_format, BANK_FORMATS['GENERIC'])
    
    # 复制数据
    result_df = df.copy()
    
    # 列名映射
    rename_map = {}
    for orig_col, std_col in config['column_mapping'].items():
        if orig_col in result_df.columns:
            rename_map[orig_col] = std_col
    
    result_df = result_df.rename(columns=rename_map)
    
    # 日期格式转换
    if 'date' in result_df.columns and config['date_format']:
        try:
            result_df['date'] = pd.to_datetime(
                result_df['date'], 
                format=config['date_format']
            )
        except (ValueError, TypeError):
            # 自动检测格式
            result_df['date'] = pd.to_datetime(result_df['date'])
    
    # 确保金额列为数值
    for col in ['income', 'expense', 'balance']:
        if col in result_df.columns:
            result_df[col] = pd.to_numeric(result_df[col], errors='coerce').fillna(0)
    
    return result_df


def get_supported_banks() -> List[Dict]:
    """获取支持的银行列表"""
    return [
        {'code': code, 'name': config['name']}
        for code, config in BANK_FORMATS.items()
    ]


def add_custom_bank_format(
    code: str,
    name: str,
    column_mapping: Dict[str, str],
    date_format: str = None,
    encoding: str = 'utf-8'
):
    """
    添加自定义银行格式
    
    Args:
        code: 银行代码
        name: 银行名称
        column_mapping: 列名映射
        date_format: 日期格式
        encoding: 文件编码
    """
    BANK_FORMATS[code] = {
        'name': name,
        'column_mapping': column_mapping,
        'date_format': date_format,
        'encoding': encoding,
        'skip_rows': 0,
        'header_row': 0
    }
