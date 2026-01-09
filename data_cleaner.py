#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据清洗模块 - 资金穿透与关联排查系统
负责数据去重、验证和标准化
"""

import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
import config
import utils

logger = utils.setup_logger(__name__)


def deduplicate_transactions(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    智能去重交易记录
    
    Args:
        df: 交易DataFrame
        
    Returns:
        (去重后的DataFrame, 统计信息字典)
    """
    if df.empty:
        return df, {'original': 0, 'duplicates': 0, 'final': 0}
    
    original_count = len(df)
    logger.info(f'开始去重,原始记录数: {original_count}')
    
    # 排序以确保一致性
    df = df.sort_values('date').reset_index(drop=True)
    
    # 创建去重键
    df['_timestamp'] = df['date'].astype('int64') // 10**9  # 转为秒级时间戳
    df['_amount_rounded'] = df['income'].fillna(0) + df['expense'].fillna(0)
    df['_amount_rounded'] = df['_amount_rounded'].round(2)
    
    # DEBUG: 打印前几行数据，检查是否有大量重复值
    if len(df) > 0:
        logger.debug(f"去重前数据采样 (Top 5):")
        for i in range(min(5, len(df))):
            row = df.iloc[i]
            tx_id = row.get('transaction_id', 'N/A')
            ts = row.get('_timestamp', 'N/A')
            amt = row.get('_amount_rounded', 'N/A')
            logger.debug(f"  Row {i}: ID={tx_id}, Time={ts}, Amt={amt}")
            
    # 标记潜在重复组
    # 同一账号、相近时间(容差范围内)、相同金额的交易可能是重复
    duplicates_mask = pd.Series(False, index=df.index)
    dedup_details = []  # 记录去重详情
    
    # 优先使用交易流水号去重
    # 鉴于发现部分银行流水号存在异常（虽然看起来有效但导致大量误判重复），
    # 且为保证数据完整性，我们暂时禁用基于流水号的强去重。
    # 改为在启发式去重中作为参考，或完全忽略。
    # 根据调试结果，建议完全忽略流水号，依靠时间+金额+对手方+摘要来去重。
    
    # ... (原有流水号去重逻辑已注释) ...
    
    # 继续使用启发式规则检查（针对无流水号或流水号不可靠的情况）
    for idx in range(len(df) - 1):
        if duplicates_mask[idx]:
            continue
            
        current = df.iloc[idx]
        
        # 查找后续记录中的潜在重复
        for next_idx in range(idx + 1, min(idx + 20, len(df))):  # 只检查后续20条
            if duplicates_mask[next_idx]:
                continue
                
            next_record = df.iloc[next_idx]
            
            # 流水号检查已被移除，因为发现它不可靠
            
            # 时间差检查
            time_diff = abs(current['_timestamp'] - next_record['_timestamp'])
            if time_diff > config.DEDUP_TIME_TOLERANCE_SECONDS:
                break  # 后续记录时间差太大,跳出
            
            # 金额检查
            amount_match = abs(current['_amount_rounded'] - next_record['_amount_rounded']) < 0.01
            
            # 对手方检查(如果有)
            counterparty_match = True
            if current['counterparty'] and next_record['counterparty']:
                counterparty_match = current['counterparty'] == next_record['counterparty']
                
            # 摘要检查(如果有)
            # 增加摘要检查可以防止不同用途的相同金额交易被误删
            desc_match = True
            if current['description'] and next_record['description']:
                # 简单对比前10个字符，避免细微差别
                desc1 = str(current['description'])[:10]
                desc2 = str(next_record['description'])[:10]
                desc_match = desc1 == desc2
            
            # 如果时间、金额、对手方、摘要都匹配,标记为重复
            if amount_match and counterparty_match and desc_match:
                duplicates_mask[next_idx] = True
                # 记录被删除的重复记录详情
                dedup_details.append({
                    '原始行号': next_idx,
                    '日期': next_record.get('date'),
                    '金额': next_record.get('_amount_rounded'),
                    '对手方': next_record.get('counterparty', ''),
                    '摘要': str(next_record.get('description', ''))[:30],
                    '与行': idx,
                    '去重原因': '时间+金额+对手方+摘要相同'
                })
    
    # 移除重复记录
    df_dedup = df[~duplicates_mask].copy()
    
    # 清理临时列
    df_dedup = df_dedup.drop(['_timestamp', '_amount_rounded'], axis=1)
    
    duplicate_count = duplicates_mask.sum()
    final_count = len(df_dedup)
    
    stats = {
        'original': original_count,
        'duplicates': duplicate_count,
        'final': final_count,
        'dedup_rate': f'{duplicate_count/original_count*100:.2f}%' if original_count > 0 else '0%',
        'dedup_details': dedup_details  # 新增：去重详情
    }
    
    logger.info(f'去重完成: 原始{original_count}条, 去重{duplicate_count}条, '
                f'保留{final_count}条 (去重率: {stats["dedup_rate"]})')
    
    return df_dedup, stats


def validate_data_quality(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    验证数据质量
    
    Args:
        df: 交易DataFrame
        
    Returns:
        (验证后的DataFrame, 质量报告字典)
    """
    logger.info('开始数据质量验证...')
    
    quality_report = {
        'total_rows': len(df),
        'invalid_rows': [],
        'warnings': []
    }
    
    if df.empty:
        return df, quality_report
    
    valid_mask = pd.Series(True, index=df.index)
    
    # 1. 检查必需字段
    if 'date' not in df.columns or df['date'].isna().all():
        logger.error('缺少日期字段')
        quality_report['warnings'].append('缺少日期字段')
        return df, quality_report
    
    # 标记日期缺失的行
    invalid_date = df['date'].isna()
    if invalid_date.any():
        quality_report['invalid_rows'].extend(
            df[invalid_date].index.tolist()
        )
        quality_report['warnings'].append(f'发现{invalid_date.sum()}条记录日期缺失')
        valid_mask &= ~invalid_date
    
    # 2. 检查金额逻辑
    total_amount = df['income'].fillna(0) + df['expense'].fillna(0)
    
    # 金额异常检测
    zero_amount = total_amount == 0
    if zero_amount.any():
        quality_report['warnings'].append(f'发现{zero_amount.sum()}条零金额记录')
    
    # 金额超大检测
    large_amount = total_amount > config.MAX_AMOUNT_THRESHOLD
    if large_amount.any():
        quality_report['warnings'].append(
            f'发现{large_amount.sum()}条超大金额记录(>{utils.format_currency(config.MAX_AMOUNT_THRESHOLD)})'
        )
    
    # 3. 检查数据完整性
    empty_description = df['description'].isna() | (df['description'] == '')
    if empty_description.any():
        quality_report['warnings'].append(f'{empty_description.sum()}条记录缺少摘要')
    
    # 移除无效行
    df_valid = df[valid_mask].copy()
    
    quality_report['valid_rows'] = len(df_valid)
    quality_report['removed_rows'] = len(df) - len(df_valid)
    
    logger.info(f'数据验证完成: 总计{len(df)}条, 有效{len(df_valid)}条, '
                f'移除{quality_report["removed_rows"]}条')
    
    if quality_report['warnings']:
        for warning in quality_report['warnings']:
            logger.warning(warning)
    
    return df_valid, quality_report


def standardize_bank_fields(df: pd.DataFrame, bank_name: str = None) -> pd.DataFrame:
    """
    标准化银行字段(增强版,支持真实银行数据格式)
    
    Args:
        df: 原始DataFrame
        bank_name: 银行名称(用于特殊处理)
        
    Returns:
        标准化后的DataFrame
    """
    logger.info(f'标准化银行字段,银行: {bank_name or "未知"}')
    
    normalized = pd.DataFrame()
    
    # 1. 日期字段 - 支持"交易时间"
    date_col = None
    for col_name in config.BANK_FIELD_MAPPING.get('transaction_time', []):
        if col_name in df.columns:
            date_col = col_name
            break
    
    if not date_col:
        # 回退到原有逻辑
        for col_name in config.DATE_COLUMNS:
            if col_name in df.columns:
                date_col = col_name
                break
    
    if date_col:
        normalized['date'] = df[date_col].apply(utils.parse_date)
    else:
        logger.warning('未找到日期列')
        normalized['date'] = None
    
    # 2. 摘要字段 - 支持"交易摘要"
    desc_col = None
    for col_name in config.BANK_FIELD_MAPPING.get('summary', []):
        if col_name in df.columns:
            desc_col = col_name
            break
    
    if desc_col:
        normalized['description'] = df[desc_col].apply(utils.clean_text)
    else:
        normalized['description'] = ''
    
    # 3. 金额字段 - 重要!需要处理借贷标志
    amount_col = None
    for col_name in config.BANK_FIELD_MAPPING.get('transaction_amount', []):
        if col_name in df.columns:
            amount_col = col_name
            break
    
    debit_credit_col = None
    for col_name in config.BANK_FIELD_MAPPING.get('debit_credit_flag', []):
        if col_name in df.columns:
            debit_credit_col = col_name
            break
    
    if amount_col and debit_credit_col:
        # 根据借贷标志分配收入/支出
        normalized['income'] = 0.0
        normalized['expense'] = 0.0
        
        for idx, row in df.iterrows():
            amount = utils.format_amount(row[amount_col])
            flag = str(row[debit_credit_col]).strip().upper()
            
            # 贷/C/CREDIT/进 = 收入
            if flag in ['贷', 'C', 'CREDIT', '贷方', '进', '收']:
                normalized.at[idx, 'income'] = amount
                normalized.at[idx, 'expense'] = 0.0
            # 借/D/DEBIT/出 = 支出
            elif flag in ['借', 'D', 'DEBIT', '借方', '出', '支', '付']:
                normalized.at[idx, 'income'] = 0.0
                normalized.at[idx, 'expense'] = amount
            else:
                # 无法判断,根据摘要推测
                desc = str(row.get(desc_col, '')).lower()
                if any(kw in desc for kw in ['存入', '转入', '收入', '工资']):
                    normalized.at[idx, 'income'] = amount
                    normalized.at[idx, 'expense'] = 0.0
                else:
                    normalized.at[idx, 'income'] = 0.0
                    normalized.at[idx, 'expense'] = amount
    else:
        # 回退到原有逻辑
        logger.warning('未找到借贷标志,使用原有收支字段逻辑')
        income_col = None
        for col_name in config.INCOME_COLUMNS:
            if col_name in df.columns:
                income_col = col_name
                break
        
        expense_col = None
        for col_name in config.EXPENSE_COLUMNS:
            if col_name in df.columns:
                expense_col = col_name
                break
        
        if income_col:
            normalized['income'] = df[income_col].apply(utils.format_amount)
        else:
            normalized['income'] = 0.0
        
        if expense_col:
            normalized['expense'] = df[expense_col].apply(utils.format_amount)
        else:
            normalized['expense'] = 0.0
    
    # 4. 对手方字段 - 支持"交易对方名称"
    counterparty_col = None
    for col_name in config.BANK_FIELD_MAPPING.get('counterparty_name', []):
        if col_name in df.columns:
            counterparty_col = col_name
            break
    
    if counterparty_col:
        normalized['counterparty'] = df[counterparty_col].apply(utils.clean_text)
    else:
        normalized['counterparty'] = ''
    
    # 5. 余额字段 - 支持"交易余额"
    balance_col = None
    for col_name in config.BANK_FIELD_MAPPING.get('balance', []):
        if col_name in df.columns:
            balance_col = col_name
            break
    
    if balance_col:
        normalized['balance'] = df[balance_col].apply(utils.format_amount)
    else:
        normalized['balance'] = 0.0
    
    # 6. 现金标志
    # 6. 现金标志 (修正：仅识别物理现金)
    # 策略1：优先根据摘要关键词判断（最准确）
    is_cash_by_desc = normalized['description'].apply(
        lambda x: utils.contains_keywords(str(x), config.CASH_KEYWORDS)
    )
    
    
    # 策略2：检查银行现金标志列 (已禁用宽泛匹配)
    # 用户反馈：银行的"现金交易"标志包含了转账/POS等非物理现金操作
    # 因此，我们不再信任"现金交易"这个词。除非标志列明确包含"现钞"这种极强指示词。
    is_cash_by_flag = pd.Series(False, index=df.index)
    cash_col = None
    for col_name in config.BANK_FIELD_MAPPING.get('cash_flag', []):
        if col_name in df.columns:
            cash_col = col_name
            break
            
    if cash_col:
        # 只匹配"现钞"、"ATM"。对于"现金"或"现金交易"这种宽泛词予以忽略
        def is_strict_physical_cash(val):
            s = str(val).strip().upper()
            # 排除'现金交易'，因为它通常指即时结算而非物理现金
            if '现金交易' in s: 
                return False
            # 只有极强的物理特征才保留
            return '现钞' in s or 'ATM' in s
            
        is_cash_by_flag = df[cash_col].apply(is_strict_physical_cash)
        
    normalized['is_cash'] = is_cash_by_desc | is_cash_by_flag
    
    # 7. 账号字段(用于去重)
    account_col = None
    for col_name in config.BANK_FIELD_MAPPING.get('account_number', []):
        if col_name in df.columns:
            account_col = col_name
            break
    
    if account_col:
        normalized['account_number'] = df[account_col].astype(str)
    else:
        normalized['account_number'] = ''
    
    # 8. 交易流水号(用于精确去重)
    tx_id_col = None
    for col_name in config.BANK_FIELD_MAPPING.get('transaction_id', []):
        if col_name in df.columns:
            tx_id_col = col_name
            break
    
    if tx_id_col:
        normalized['transaction_id'] = df[tx_id_col].astype(str).str.strip()
    else:
        normalized['transaction_id'] = ''
    
    logger.info(f'字段标准化完成,有效记录: {len(normalized)}条')
    
    return normalized


def generate_cleaning_report(entity_name: str, 
                             file_stats: List[Dict],
                             final_stats: Dict) -> pd.DataFrame:
    """
    生成清洗报告
    
    Args:
        entity_name: 实体名称
        file_stats: 各文件统计列表
        final_stats: 最终统计
        
    Returns:
        报告DataFrame
    """
    report_data = []
    
    # 各文件的统计
    for stat in file_stats:
        report_data.append({
            '对象': entity_name,
            '文件名': stat['filename'],
            '银行': stat.get('bank', '未知'),
            '原始行数': stat['original_rows'],
            '有效行数': stat['valid_rows'],
            '去重行数': stat.get('duplicates', 0),
            '处理时间': stat.get('process_time', '-')
        })
    
    # 汇总行
    report_data.append({
        '对象': entity_name,
        '文件名': '【汇总】',
        '银行': f'共{len(file_stats)}家银行',
        '原始行数': final_stats['total_original'],
        '有效行数': final_stats['total_valid'],
        '去重行数': final_stats['total_duplicates'],
        '处理时间': final_stats.get('total_time', '-')
    })
    
    return pd.DataFrame(report_data)


def clean_and_merge_files(file_list: List[str], entity_name: str) -> Tuple[pd.DataFrame, Dict]:
    """
    清洗并合并多个文件
    
    Args:
        file_list: 文件路径列表
        entity_name: 实体名称
        
    Returns:
        (合并后的DataFrame, 统计信息)
    """
    logger.info(f'开始清洗合并 {entity_name} 的数据,共{len(file_list)}个文件')
    
    all_dfs = []
    file_stats = []
    
    start_time = datetime.now()
    
    for filepath in file_list:
        file_start = datetime.now()
        filename = os.path.basename(filepath)  # 跨平台：使用os.path.basename替代split('/')
        
        # 提取银行名称
        bank_name = utils.extract_bank_name(filename)
        
        logger.info(f'处理文件: {filename}, 银行: {bank_name}')
        
        try:
            # 读取Excel
            df_raw = pd.read_excel(filepath)
            original_rows = len(df_raw)
            
            # 标准化字段
            df_normalized = standardize_bank_fields(df_raw, bank_name)
            
            # 数据验证
            df_valid, quality_report = validate_data_quality(df_normalized)
            
            # 添加来源信息
            df_valid['数据来源'] = filename
            df_valid['银行来源'] = bank_name
            
            all_dfs.append(df_valid)
            
            file_time = (datetime.now() - file_start).total_seconds()
            
            file_stats.append({
                'filename': filename,
                'bank': bank_name,
                'original_rows': original_rows,
                'valid_rows': len(df_valid),
                'duplicates': quality_report.get('removed_rows', 0),
                'process_time': f'{file_time:.2f}s'
            })
            
        except Exception as e:
            logger.error(f'处理文件失败: {filename}, 错误: {str(e)}')
            file_stats.append({
                'filename': filename,
                'bank': bank_name,
                'original_rows': 0,
                'valid_rows': 0,
                'duplicates': 0,
                'process_time': 'ERROR'
            })
    
    # 合并所有数据
    if not all_dfs:
        logger.error(f'{entity_name} 没有有效数据')
        return pd.DataFrame(), {}
    
    df_merged = pd.concat(all_dfs, ignore_index=True)
    
    # 去重
    df_final, dedup_stats = deduplicate_transactions(df_merged)
    
    # 按时间排序
    df_final = df_final.sort_values('date').reset_index(drop=True)
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    final_stats = {
        'entity': entity_name,
        'file_count': len(file_list),
        'total_original': sum(s['original_rows'] for s in file_stats),
        'total_valid': len(df_merged),
        'total_duplicates': dedup_stats['duplicates'],
        'final_rows': len(df_final),
        'total_time': f'{total_time:.2f}s',
        'file_stats': file_stats
    }
    
    logger.info(f'{entity_name} 清洗合并完成: {len(file_list)}个文件, '
                f'{final_stats["total_original"]}行 → {final_stats["final_rows"]}行')
    
    return df_final, final_stats


def save_formatted_excel(df: pd.DataFrame, output_path: str):
    """
    保存为美观的Excel格式（专家级优化版）：
    1. 智能列宽：根据内容长度自动调整，彻底解决 ######
    2. 视觉降噪：强制移除“数字存为文本”的绿色小三角
    3. 会计格式：0值显示为"-"，金额更易读
    4. 彻底汉化与清洗
    """
    # 1. 创建副本并清洗
    df_disp = df.copy()
    
    # 数据清洗
    if '数据来源' in df_disp.columns:
        df_disp['数据来源'] = df_disp['数据来源'].apply(lambda x: str(x).split('/')[-1].split('\\')[-1])
    if 'is_cash' in df_disp.columns:
        df_disp['is_cash'] = df_disp['is_cash'].apply(lambda x: '是' if x is True else '')

    # === 自动化交易分类打标 ===
    # 依据config规则对每一行进行分类
    def refine_category(row):
        # 能够明确属于理财赎回/购买方向的，优先判定
        # 这里使用简单关键词匹配逻辑，结合优先级
        text = str(row.get('description', '')) + ' ' + str(row.get('counterparty', ''))
        
        # 遍历配置的分类规则
        # 按优先级排序 (数字越小优先级越高)
        sorted_cats = sorted(config.TRANSACTION_CATEGORIES.items(), key=lambda x: x[1]['priority'])
        
        for cat_name, conf in sorted_cats:
            if utils.contains_keywords(text, conf['keywords']):
                return cat_name
                
        return '其他'

    df_disp['category'] = df_disp.apply(refine_category, axis=1)

    # 列名映射
    col_mapping = {
        'date': '交易时间',
        'income': '收入(元)',
        'expense': '支出(元)',
        'balance': '余额(元)',
        'counterparty': '交易对手',
        'description': '交易摘要',
        'category': '交易分类', # 新增列
        'bank_source': '所属银行',
        '银行来源': '所属银行',
        'account_number': '本方账号',
        'is_cash': '现金',  # 简化为现金
        '数据来源': '来源文件',
        'transaction_id': '流水号'
    }
    
    # 期望顺序
    desired_order = [
        'date', 'income', 'expense', 'balance', 
        'counterparty', 'description', 'category', # 将分类放在摘要旁边
        '银行来源', 'account_number', 'is_cash', '数据来源'
    ]
    
    # 重排与重命名
    existing_cols = [c for c in desired_order if c in df_disp.columns]
    process_cols = set(desired_order)
    other_cols = [c for c in df_disp.columns if c not in process_cols]
    df_disp = df_disp[existing_cols + other_cols]
    df_disp = df_disp.rename(columns=col_mapping)
    
    # 2. 保存并格式化
    # 2. 保存并格式化
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            sheet_name = '交易流水'
            df_disp.to_excel(writer, index=False, sheet_name=sheet_name)
            
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
            # --- 样式定义 ---
            
            # 1. 表头样样式：浅灰背景，深色字，加粗，边框
            header_fmt = workbook.add_format({
                'bold': True,
                'valign': 'vcenter',
                'align': 'center',
                'fg_color': '#EFEFEF', # 更专业的浅灰
                'border': 1,
                'font_name': '微软雅黑',
                'font_size': 10
            })
            
            # 2. 会计金额格式：千分位，0显示为"-"，对齐
            # 格式串: Positive; Negative; Zero; Text
            accounting_fmt = workbook.add_format({
                'num_format': '_ * #,##0.00_ ;_ * -#,##0.00_ ;_ * "-"??_ ;_ @_ ',
                'font_name': 'Arial', # 数字用Arial更好看
                'font_size': 10
            })
            
            # 3. 日期格式：yyyy-mm-dd hh:mm:ss
            date_fmt = workbook.add_format({
                'num_format': 'yyyy-mm-dd hh:mm:ss',
                'font_name': 'Arial',
                'font_size': 10,
                'align': 'left' # 靠左对齐，防止井号视觉误差
            })
            
            # 4. 普通文本：微软雅黑
            text_fmt = workbook.add_format({
                'font_name': '微软雅黑',
                'font_size': 10,
                'valign': 'vcenter'
            })
            
            # --- 应用格式与智能列宽 ---
            
            # 写入表头（覆盖默认格式）
            for col_num, value in enumerate(df_disp.columns.values):
                worksheet.write(0, col_num, value, header_fmt)
            
            # 遍历每列及数据，计算最佳宽度
            for i, col_name in enumerate(df_disp.columns):
                # 基础列宽：取表头长度
                max_len = len(str(col_name)) * 2 # 中文约占2宽
                
                # 采样前100行数据计算长度
                sample = df_disp[col_name].iloc[:100].astype(str)
                if not sample.empty:
                    data_max_len = sample.map(lambda x: len(x.encode('gbk'))).max() # 使用GBK字节长度更准
                    max_len = max(max_len, data_max_len)
                
                # 设置宽度限制和特定格式
                col_fmt = text_fmt # 默认格式
                width = max_len + 2 # 增加一点padding
                
                if '时间' in col_name:
                    width = 23 # 强制足够宽，彻底消灭######
                    col_fmt = date_fmt
                elif any(c in col_name for c in ['收入', '支出', '余额', '金额']):
                    width = max(width, 15) # 金额至少15宽
                    col_fmt = accounting_fmt
                elif '摘要' in col_name:
                    width = min(width, 50) # 摘要最宽50，防止过宽
                elif '账号' in col_name:
                    width = max(width, 22) # 账号通常较长
                
                # 应用列宽和格式
                worksheet.set_column(i, i, width, col_fmt)
            
            # --- 消除绿色小三角 (忽略数字存为文本错误) ---
            # 这里的范围是整个工作表
            worksheet.ignore_errors({'number_stored_as_text': 'A1:XFD1048576'})
            
            # 冻结首行
            worksheet.freeze_panes(1, 0)
            
            # 开启筛选
            worksheet.autofilter(0, 0, len(df_disp), len(df_disp.columns) - 1)

    except PermissionError:
        logger.warning(f'无法保存文件 {output_path}: 文件可能被占用，请关闭Excel后重试。')           
    except Exception as e:
        logger.error(f'格式化保存Excel失败: {str(e)}, 回退到普通保存')
        try:
            df_disp.to_excel(output_path, index=False)
        except PermissionError:
            logger.warning(f'无法保存文件 {output_path}: 文件可能被占用。')
