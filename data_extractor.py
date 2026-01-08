#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据提取模块 - 资金穿透与关联排查系统
负责从PDF和Excel文件中提取结构化数据
"""

import os
import pandas as pd
import pdfplumber
from typing import Dict, List, Tuple
import config
import utils

logger = utils.setup_logger(__name__)


def extract_clues_from_pdf(pdf_path: str) -> Tuple[List[str], List[str]]:
    """
    从PDF线索文件中提取核心人员名单和涉案公司名单
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        (核心人员列表, 涉案公司列表)
    """
    logger.info(f'正在提取PDF线索: {pdf_path}')
    
    persons = set()
    companies = set()
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ''
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + '\n'
            
            # 提取人名
            names = utils.extract_chinese_name(full_text)
            persons.update(names)
            
            # 提取公司名
            company_names = utils.extract_company_name(full_text)
            companies.update(company_names)
            
            logger.info(f'提取到 {len(persons)} 个人名, {len(companies)} 个公司名')
            
    except Exception as e:
        logger.error(f'提取PDF失败: {pdf_path}, 错误: {str(e)}')
    
    return list(persons), list(companies)


def find_column_by_keywords(df: pd.DataFrame, keywords: List[str]) -> str:
    """
    根据关键词列表查找DataFrame中的列名
    
    Args:
        df: DataFrame
        keywords: 关键词列表
        
    Returns:
        匹配到的列名,未找到返回None
    """
    columns = df.columns.tolist()
    
    for keyword in keywords:
        for col in columns:
            if keyword.lower() in str(col).lower():
                return col
    
    return None


def normalize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    标准化交易数据
    
    Args:
        df: 原始交易DataFrame
        
    Returns:
        标准化后的DataFrame
    """
    logger.info('正在标准化交易数据...')
    
    normalized = pd.DataFrame()
    
    # 查找并映射字段
    date_col = find_column_by_keywords(df, config.DATE_COLUMNS)
    desc_col = find_column_by_keywords(df, config.DESCRIPTION_COLUMNS)
    income_col = find_column_by_keywords(df, config.INCOME_COLUMNS)
    expense_col = find_column_by_keywords(df, config.EXPENSE_COLUMNS)
    counterparty_col = find_column_by_keywords(df, config.COUNTERPARTY_COLUMNS)
    balance_col = find_column_by_keywords(df, config.BALANCE_COLUMNS)
    
    # 必需字段检查
    if not date_col:
        logger.warning('未找到日期列,尝试使用第一列')
        date_col = df.columns[0]
    
    if not desc_col:
        logger.warning('未找到摘要列')
    
    # 标准化日期
    normalized['date'] = df[date_col].apply(utils.parse_date)
    
    # 标准化摘要
    if desc_col:
        normalized['description'] = df[desc_col].apply(utils.clean_text)
    else:
        normalized['description'] = ''
    
    # 标准化金额
    if income_col:
        normalized['income'] = df[income_col].apply(utils.format_amount)
    else:
        normalized['income'] = 0.0
    
    if expense_col:
        normalized['expense'] = df[expense_col].apply(utils.format_amount)
    else:
        normalized['expense'] = 0.0
    
    # 标准化对手方
    if counterparty_col:
        normalized['counterparty'] = df[counterparty_col].apply(utils.clean_text)
    else:
        normalized['counterparty'] = ''
    
    # 标准化余额
    if balance_col:
        normalized['balance'] = df[balance_col].apply(utils.format_amount)
    else:
        normalized['balance'] = 0.0
    
    # 移除无效行(没有日期的行)
    normalized = normalized[normalized['date'].notna()]
    
    # 按日期排序
    normalized = normalized.sort_values('date').reset_index(drop=True)
    
    logger.info(f'标准化完成,有效交易记录: {len(normalized)} 条')
    
    return normalized


def read_excel_transactions(excel_path: str) -> pd.DataFrame:
    """
    读取Excel流水文件
    
    Args:
        excel_path: Excel文件路径
        
    Returns:
        标准化后的交易DataFrame
    """
    logger.info(f'正在读取Excel流水: {excel_path}')
    
    try:
        # 尝试读取Excel
        df = pd.read_excel(excel_path)
        
        # 跳过可能的标题行(查找包含"日期"或"交易"的行作为表头)
        header_row = 0
        for i in range(min(10, len(df))):
            row_text = ' '.join([str(x) for x in df.iloc[i].values])
            if '日期' in row_text or '交易' in row_text or 'date' in row_text.lower():
                header_row = i
                break
        
        if header_row > 0:
            df = pd.read_excel(excel_path, header=header_row)
        
        logger.info(f'读取到 {len(df)} 行原始数据')
        
        # 标准化数据
        normalized_df = normalize_transactions(df)
        
        return normalized_df
        
    except Exception as e:
        logger.error(f'读取Excel失败: {excel_path}, 错误: {str(e)}')
        return pd.DataFrame()


def load_all_transactions(directory: str, target_names: List[str] = None) -> Dict[str, pd.DataFrame]:
    """
    加载目录下所有Excel流水文件(支持递归扫描)
    
    Args:
        directory: 目录路径
        target_names: 目标人员/公司名单,用于文件名匹配(可选)
        
    Returns:
        字典: {文件名: 交易DataFrame}
    """
    logger.info(f'正在扫描目录(递归): {directory}')
    
    all_transactions = {}
    
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith(('.xlsx', '.xls')) and not filename.startswith('~'):
                # 检查是否为线索文件或输出文件
                if any(keyword in filename for keyword in config.CLUE_FILE_KEYWORDS):
                    continue
                if filename == config.OUTPUT_EXCEL_FILE:
                    continue
                
                file_path = os.path.join(root, filename)
                df = read_excel_transactions(file_path)
                
                if not df.empty:
                    # 提取文件名作为标识(去除扩展名)
                    file_key = os.path.splitext(filename)[0]
                    # 如果有重复文件名，添加前缀区分
                    if file_key in all_transactions:
                        parent_dir = os.path.basename(root)
                        file_key = f"{parent_dir}_{file_key}"
                        
                    all_transactions[file_key] = df
                    logger.info(f'已加载: {file_path}, 记录数: {len(df)}')
    
    logger.info(f'共加载 {len(all_transactions)} 个流水文件')
    
    return all_transactions


def find_clue_files(directory: str) -> List[str]:
    """
    递归查找目录下的线索PDF文件
    
    Args:
        directory: 目录路径
        
    Returns:
        PDF文件路径列表
    """
    logger.info(f'正在递归查找线索文件: {directory}')
    
    clue_files = []
    all_pdfs = []
    
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.pdf'):
                file_path = os.path.join(root, filename)
                all_pdfs.append(file_path)
                # 检查是否包含线索关键词
                if any(keyword in filename for keyword in config.CLUE_FILE_KEYWORDS):
                    clue_files.append(file_path)
                    logger.info(f'找到线索文件: {file_path}')
    
    if not clue_files:
        # 【重要修复】不再将所有PDF当作线索文件。
        # 原逻辑会把征信报告等非线索PDF作为人员名单来源，
        # 导致提取出大量无效"人员"（如"贸易融资"、"银行股"等片段）。
        # 现在仅依赖文件名中的人员识别。
        logger.info('未找到带特定关键词的线索PDF，跳过PDF人名提取环节')
        clue_files = []
    
    logger.info(f'共找到 {len(clue_files)} 个线索文件')
    
    return clue_files


def extract_all_clues(directory: str) -> Tuple[List[str], List[str]]:
    """
    提取目录下所有线索文件中的人员和公司名单
    
    Args:
        directory: 目录路径
        
    Returns:
        (核心人员列表, 涉案公司列表)
    """
    clue_files = find_clue_files(directory)
    
    all_persons = set()
    all_companies = set()
    
    for clue_file in clue_files:
        persons, companies = extract_clues_from_pdf(clue_file)
        all_persons.update(persons)
        all_companies.update(companies)
    
    logger.info(f'汇总提取: {len(all_persons)} 个人名, {len(all_companies)} 个公司名')
    
    return list(all_persons), list(all_companies)


def get_transactions_by_entity(all_transactions: Dict[str, pd.DataFrame], 
                               entity_name: str) -> pd.DataFrame:
    """
    获取特定人员或公司的所有交易记录
    
    Args:
        all_transactions: 所有交易数据字典
        entity_name: 人员或公司名称
        
    Returns:
        该实体的交易DataFrame
    """
    # 查找文件名包含该实体名称的流水
    matching_dfs = []
    
    for file_key, df in all_transactions.items():
        if entity_name in file_key:
            matching_dfs.append(df)
    
    if matching_dfs:
        combined = pd.concat(matching_dfs, ignore_index=True)
        combined = combined.sort_values('date').reset_index(drop=True)
        return combined
    
    return pd.DataFrame()
