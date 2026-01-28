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
    
    # ====================================================================
    # 【P0 修复 - 2026-01-18】恢复流水号去重
    # 审计原则：交易流水号是银行出具的唯一电子凭证，不同流水号的交易不应被删除
    # ====================================================================
    
    # 第一步：基于流水号去重（如果有可靠的流水号）
    has_valid_tx_id = (
        'transaction_id' in df.columns and
        df['transaction_id'].notna().sum() > len(df) * 0.5  # 超过50%的记录有流水号
    )
    
    if has_valid_tx_id:
        # 流水号可用：完全相同的流水号才视为重复
        tx_id_col = df['transaction_id'].astype(str).str.strip()
        # 排除空值和占位符
        valid_tx_ids = ~tx_id_col.isin(['', 'nan', 'None', 'N/A', '-'])
        
        # 对有有效流水号的记录：按流水号去重（保留第一条）
        if valid_tx_ids.sum() > 0:
            df_with_tx_id = df[valid_tx_ids].copy()
            df_without_tx_id = df[~valid_tx_ids].copy()
            
            # 按流水号去重
            original_with_tx_id = len(df_with_tx_id)
            df_with_tx_id_dedup = df_with_tx_id.drop_duplicates(
                subset=['transaction_id'], keep='first'
            )
            tx_id_dups_removed = original_with_tx_id - len(df_with_tx_id_dedup)
            
            if tx_id_dups_removed > 0:
                logger.info(f'基于流水号去重: 移除 {tx_id_dups_removed} 条完全重复记录')
            
            # 合并回来，继续处理无流水号的部分
            df = pd.concat([df_with_tx_id_dedup, df_without_tx_id], ignore_index=True)
            df = df.sort_values('date').reset_index(drop=True)
            # 重新计算临时列
            df['_timestamp'] = df['date'].astype('int64') // 10**9
            df['_amount_rounded'] = (df['income'].fillna(0) + df['expense'].fillna(0)).round(2)
        else:
            logger.info('流水号字段存在但均无效，将使用启发式去重')
    else:
        logger.info('无可靠流水号字段，将使用启发式去重')
    
    # 【修复】流水号去重后 df 索引已变化，需重新创建 duplicates_mask
    duplicates_mask = pd.Series(False, index=df.index)
    dedup_details = []  # 重置去重详情
    
    # 第二步：启发式规则去重（针对无流水号或作为补充检查）
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
                # 【修复】大额交易保护：5万元以上交易需要更严格的验证
                current_amount = current['_amount_rounded']
                if current_amount >= config.ASSET_LARGE_AMOUNT_THRESHOLD:  # 5万元
                    # 大额交易：必须有相同的交易流水号才能去重（如果有流水号）
                    has_tx_id = ('transaction_id' in df.columns 
                                and pd.notna(current.get('transaction_id'))
                                and pd.notna(next_record.get('transaction_id')))
                    if has_tx_id:
                        if current.get('transaction_id') != next_record.get('transaction_id'):
                            continue  # 流水号不同，不去重大额交易
                    else:
                        # 无流水号的大额交易：记录警告但不自动去重
                        logger.warning(f'发现疑似重复大额交易(¥{current_amount:.2f})，需人工复核，暂不自动去重')
                        continue
                
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
    
    # ========== Phase 1: 账户类型识别 (2026-01-20 新增) ==========
    
    # 7.1 账户类型识别 (借记卡/信用卡/理财账户/证券账户)
    def classify_account_type(account_num: str, description: str, bank_name: str) -> str:
        """
        识别账户类型
        
        Args:
            account_num: 账号
            description: 交易摘要
            bank_name: 银行名称
            
        Returns:
            账户类型: 借记卡/信用卡/理财账户/证券账户
        """
        account_str = str(account_num).strip()
        desc_str = str(description).upper()
        bank_str = str(bank_name).upper()
        
        # 1. 基于账号长度和特征判断
        account_len = len(account_str.replace(' ', ''))
        
        # 理财账户/证券账户特征
        if any(kw in desc_str for kw in ['理财', '基金', '证券', '股票', '债券']):
            if any(kw in bank_str for kw in ['证券', '基金']):
                return '证券账户'
            return '理财账户'
        
        # 基于账号长度判断
        if 16 <= account_len <= 19:
            # 标准银行卡长度
            # 信用卡通常以特定数字开头
            if account_str.startswith(('4', '5', '6')):
                # 进一步通过摘要判断
                if any(kw in desc_str for kw in ['信用卡', '贷记卡', 'CREDIT', '透支', '还款']):
                    return '信用卡'
                return '借记卡'
            return '借记卡'
        elif account_len < 16:
            # 短账号可能是理财或证券账户
            if any(kw in desc_str for kw in ['证券', '股票']):
                return '证券账户'
            return '理财账户'
        else:
            # 超长账号
            return '其他'
    
    # 7.2 账户类别识别 (个人/对公/联名)
    def classify_account_category(account_num: str, counterparty: str, description: str) -> str:
        """
        识别账户类别
        
        Args:
            account_num: 账号
            counterparty: 对手方
            description: 交易摘要
            
        Returns:
            账户类别: 个人账户/对公账户/联名账户
        """
        desc_str = str(description).upper()
        cp_str = str(counterparty).upper()
        
        # 对公账户特征
        if any(kw in desc_str for kw in ['对公', '公司', '企业', '单位']):
            return '对公账户'
        if any(kw in cp_str for kw in ['公司', '企业', '有限', '股份', '集团']):
            return '对公账户'
        
        # 联名账户特征
        if any(kw in desc_str for kw in ['联名', '共同', '夫妻']):
            return '联名账户'
        
        # 默认为个人账户
        return '个人账户'
    
    # 7.3 真实银行卡识别 (过滤基金/理财/证券账户)
    def is_real_bank_card(account_num: str, account_type: str, bank_name: str) -> bool:
        """
        判断是否为真实银行卡
        
        Args:
            account_num: 账号
            account_type: 账户类型
            bank_name: 银行名称
            
        Returns:
            是否为真实银行卡
        """
        account_str = str(account_num).strip()
        bank_str = str(bank_name).upper()
        
        # 排除条件1: 账户类型为理财或证券
        if account_type in ['理财账户', '证券账户']:
            return False
        
        # 排除条件2: 账号长度异常 (非16-19位)
        account_len = len(account_str.replace(' ', ''))
        if account_len < 16 or account_len > 19:
            return False
        
        # 排除条件3: 银行名称包含基金/证券关键词
        if any(kw in bank_str for kw in ['基金', '证券', '资管', '信托']):
            return False
        
        # 排除条件4: 账号包含特殊关键词
        if any(kw in account_str.upper() for kw in ['FUND', 'SEC', '基金', '理财']):
            return False
        
        return True
    
    # 应用账户类型识别
    normalized['account_type'] = normalized.apply(
        lambda row: classify_account_type(
            row['account_number'],
            row['description'],
            row.get('银行来源', bank_name or '')
        ),
        axis=1
    )
    
    # 应用账户类别识别
    normalized['account_category'] = normalized.apply(
        lambda row: classify_account_category(
            row['account_number'],
            row['counterparty'],
            row['description']
        ),
        axis=1
    )
    
    # 应用真实银行卡识别
    normalized['is_real_bank_card'] = normalized.apply(
        lambda row: is_real_bank_card(
            row['account_number'],
            row['account_type'],
            row.get('银行来源', bank_name or '')
        ),
        axis=1
    )
    
    logger.info(f'账户类型识别完成: {normalized["is_real_bank_card"].sum()}张真实银行卡, '
                f'{(~normalized["is_real_bank_card"]).sum()}个非银行卡账户')
    
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
    
    # ========== 刑侦级指标字段 (Phase 0.1 - 2026-01-18 新增) ==========
    
    # 9. 余额归零标志 - 判断交易后余额是否清空
    # 余额低于阈值（默认10元）视为"清空"，这是洗钱/过桥资金的典型特征
    normalized['is_balance_zeroed'] = normalized['balance'].apply(
        lambda x: x < config.BALANCE_ZERO_THRESHOLD if pd.notna(x) and x >= 0 else False
    )
    
    # 10. 交易渠道分类 - 识别网银/ATM/柜面/手机银行等渠道
    def classify_transaction_channel(description: str) -> str:
        """根据交易摘要分类交易渠道"""
        desc = str(description).upper()
        for channel, keywords in config.TRANSACTION_CHANNEL_KEYWORDS.items():
            if any(kw.upper() in desc for kw in keywords):
                return channel
        return '其他'
    
    normalized['transaction_channel'] = normalized['description'].apply(classify_transaction_channel)
    
    # 11. 敏感词提取 - 标记包含敏感词的交易
    def extract_sensitive_keywords(description: str) -> str:
        """从交易摘要中提取敏感词"""
        desc = str(description)
        found = [kw for kw in config.SENSITIVE_KEYWORDS if kw in desc]
        return ','.join(found) if found else ''
    
    normalized['sensitive_keywords'] = normalized['description'].apply(extract_sensitive_keywords)
    
    # 12. 原始行索引 - 保留原始Excel行号用于审计追溯
    # 审计人员可通过此字段快速定位原始凭证
    normalized['source_row_index'] = df.index + 2  # +2 是因为 Excel 从1开始计数且有表头
    
    # ========== 内存优化 ==========
    # 【内存优化】优化数据类型以节省内存
    # 金额列：保持 float64 确保审计精度
    normalized['income'] = normalized['income'].astype('float64')
    normalized['expense'] = normalized['expense'].astype('float64')
    normalized['balance'] = normalized['balance'].astype('float64')
    
    # 文本列：转为 category 类型节省内存（这是内存优化的关键）
    for col in ['description', 'counterparty', '数据来源', '银行来源', 'account_number', 'transaction_id',
                'transaction_channel', 'sensitive_keywords',
                'account_type', 'account_category']:  # Phase 1 新增 account_type, account_category
        if col in normalized.columns:
            normalized[col] = normalized[col].astype('category')
    
    # 布尔列：转为 bool 类型
    for col in ['is_cash', 'is_balance_zeroed', 'is_real_bank_card']:  # Phase 1 新增 is_real_bank_card
        if col in normalized.columns:
            normalized[col] = normalized[col].astype('bool')
    
    logger.info(f'字段标准化完成,有效记录: {len(normalized)}条 (已优化数据类型)')
    
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
    
    # Phase 0.4: 添加累计统计字段（用于识别分次规避大额的行为）
    # 当日累计：识别当日多笔小额累加超过大额阈值的情况
    # 当月累计：识别月度累计异常
    if 'date' in df_final.columns and not df_final.empty:
        try:
            # 创建日期和月份分组键
            df_final['_date_key'] = df_final['date'].dt.date
            df_final['_month_key'] = df_final['date'].dt.to_period('M')
            
            # 计算当日累计收入/支出
            df_final['daily_cumulative_income'] = df_final.groupby('_date_key')['income'].cumsum()
            df_final['daily_cumulative_expense'] = df_final.groupby('_date_key')['expense'].cumsum()
            
            # 计算当月累计收入/支出
            df_final['monthly_cumulative_income'] = df_final.groupby('_month_key')['income'].cumsum()
            df_final['monthly_cumulative_expense'] = df_final.groupby('_month_key')['expense'].cumsum()
            
            # 删除临时分组键
            df_final = df_final.drop(['_date_key', '_month_key'], axis=1)
            
            logger.info(f'  已添加累计统计字段 (当日/当月累计收支)')
        except Exception as e:
            logger.warning(f'  累计统计字段计算失败: {e}')
    
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


def _prepare_display_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    准备显示数据（清洗、分类、列名映射）
    
    Args:
        df: 原始DataFrame
    
    Returns:
        处理后的显示DataFrame
    """
    df_disp = df.copy()
    
    # 数据清洗
    if '数据来源' in df_disp.columns:
        df_disp['数据来源'] = df_disp['数据来源'].apply(lambda x: str(x).split('/')[-1].split('\\')[-1])
    if 'is_cash' in df_disp.columns:
        df_disp['is_cash'] = df_disp['is_cash'].apply(lambda x: '是' if x is True else '')
    
    # 自动化交易分类打标
    def refine_category(row):
        text = str(row.get('description', '')) + ' ' + str(row.get('counterparty', ''))
        sorted_cats = sorted(config.TRANSACTION_CATEGORIES.items(), key=lambda x: x[1]['priority'])
        for cat_name, conf in sorted_cats:
            if utils.contains_keywords(text, conf['keywords']):
                return cat_name
        return '其他'
    
    df_disp['category'] = df_disp.apply(refine_category, axis=1)
    
    # 【铁律】使用统一的列名映射（来自 config.py）
    col_mapping = config.COLUMN_MAPPING
    
    # 【铁律】使用统一的列顺序（来自 config.py）
    desired_order = config.COLUMN_ORDER
    
    # 重排与重命名
    existing_cols = [c for c in desired_order if c in df_disp.columns]
    process_cols = set(desired_order)
    other_cols = [c for c in df_disp.columns if c not in process_cols]
    df_disp = df_disp[existing_cols + other_cols]
    df_disp = df_disp.rename(columns=col_mapping)
    
    return df_disp


def _create_excel_formats(workbook) -> Dict:
    """
    创建Excel格式
    
    Args:
        workbook: ExcelWriter workbook对象
    
    Returns:
        格式字典
    """
    # 表头样式：浅灰背景，深色字，加粗，边框
    header_fmt = workbook.add_format({
        'bold': True,
        'valign': 'vcenter',
        'align': 'center',
        'fg_color': '#EFEFEF',
        'border': 1,
        'font_name': '微软雅黑',
        'font_size': 10
    })
    
    # 会计金额格式：千分位，0显示为"-"，对齐
    accounting_fmt = workbook.add_format({
        'num_format': '_ * #,##0.00_ ;_ * -#,##0.00_ ;_ * "-"??_ ;_ @_ ',
        'font_name': 'Arial',
        'font_size': 10
    })
    
    # 日期格式：yyyy-mm-dd hh:mm:ss
    date_fmt = workbook.add_format({
        'num_format': 'yyyy-mm-dd hh:mm:ss',
        'font_name': 'Arial',
        'font_size': 10,
        'align': 'left'
    })
    
    # 普通文本：微软雅黑
    text_fmt = workbook.add_format({
        'font_name': '微软雅黑',
        'font_size': 10,
        'valign': 'vcenter'
    })
    
    return {
        'header': header_fmt,
        'accounting': accounting_fmt,
        'date': date_fmt,
        'text': text_fmt
    }


def _apply_excel_formatting(worksheet, df_disp: pd.DataFrame, formats: Dict):
    """
    应用Excel格式化
    
    Args:
        worksheet: Excel工作表对象
        df_disp: 显示DataFrame
        formats: 格式字典
    """
    # 写入表头（覆盖默认格式）
    for col_num, value in enumerate(df_disp.columns.values):
        worksheet.write(0, col_num, value, formats['header'])
    
    # 遍历每列及数据，计算最佳宽度
    for i, col_name in enumerate(df_disp.columns):
        # 基础列宽：取表头长度
        max_len = len(str(col_name)) * 2
        
        # 采样前100行数据计算长度
        sample = df_disp[col_name].iloc[:100].astype(str)
        if not sample.empty:
            data_max_len = sample.map(lambda x: len(x.encode('gbk'))).max()
            max_len = max(max_len, data_max_len)
        
        # 设置宽度限制和特定格式
        col_fmt = formats['text']
        width = max_len + 2
        
        if '时间' in col_name:
            width = 23
            col_fmt = formats['date']
        elif any(c in col_name for c in ['收入', '支出', '余额', '金额']):
            width = max(width, 15)
            col_fmt = formats['accounting']
        elif '摘要' in col_name:
            width = min(width, 50)
        elif '账号' in col_name:
            width = max(width, 22)
        
        # 应用列宽和格式
        worksheet.set_column(i, i, width, col_fmt)
    
    # 消除绿色小三角 (忽略数字存为文本错误)
    worksheet.ignore_errors({'number_stored_as_text': 'A1:XFD1048576'})
    
    # 冻结首行
    worksheet.freeze_panes(1, 0)
    
    # 开启筛选
    worksheet.autofilter(0, 0, len(df_disp), len(df_disp.columns) - 1)


# ============================================================
# P2 优化：Parquet 高性能存储
# ============================================================

def save_as_parquet(df: pd.DataFrame, output_path: str) -> bool:
    """
    保存为 Parquet 格式（高性能中间存储）
    
    【P2 优化 - 2026-01-18】
    Parquet 相比 Excel 的优势：
    - 读取速度快 10-50 倍
    - 文件体积小 50-70%
    - 支持列式存储，按需读取列
    
    Args:
        df: 要保存的 DataFrame
        output_path: 输出路径（.parquet 后缀）
        
    Returns:
        是否保存成功
    """
    if df.empty:
        logger.warning(f'空 DataFrame，跳过 Parquet 保存')
        return False
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 保存为 Parquet（使用 pyarrow 引擎）
        df.to_parquet(
            output_path,
            engine='pyarrow',
            compression='snappy',  # 平衡压缩率和速度
            index=False
        )
        
        logger.info(f'Parquet 文件已保存: {output_path}')
        return True
        
    except ImportError:
        logger.warning('pyarrow 未安装，跳过 Parquet 保存。可通过 pip install pyarrow 安装')
        return False
    except Exception as e:
        logger.error(f'Parquet 保存失败: {e}')
        return False


def load_from_parquet_or_excel(parquet_path: str, excel_path: str) -> pd.DataFrame:
    """
    优先从 Parquet 加载，如不存在则从 Excel 加载
    
    【P2 优化 - 2026-01-18】
    加载顺序：
    1. 优先尝试 Parquet（快）
    2. 回退到 Excel（慢但兼容）
    
    Args:
        parquet_path: Parquet 文件路径
        excel_path: Excel 文件路径
        
    Returns:
        加载的 DataFrame
    """
    # 优先尝试 Parquet
    if os.path.exists(parquet_path):
        try:
            df = pd.read_parquet(parquet_path)
            logger.debug(f'从 Parquet 加载: {parquet_path}')
            return df
        except Exception as e:
            logger.warning(f'Parquet 加载失败: {e}，回退到 Excel')
    
    # 回退到 Excel
    if os.path.exists(excel_path):
        try:
            df = pd.read_excel(excel_path, dtype=str)
            logger.debug(f'从 Excel 加载: {excel_path}')
            return df
        except Exception as e:
            logger.error(f'Excel 加载失败: {e}')
            return pd.DataFrame()
    
    logger.warning(f'文件不存在: {parquet_path} 或 {excel_path}')
    return pd.DataFrame()


def save_cleaned_data_dual_format(df: pd.DataFrame, base_path: str, entity_name: str):
    """
    同时保存为 Excel 和 Parquet 格式
    
    Args:
        df: 清洗后的 DataFrame
        base_path: 基础目录路径
        entity_name: 实体名称（用于文件名）
    """
    # Excel 路径（供人阅读）
    excel_path = os.path.join(base_path, f'{entity_name}_cleaned.xlsx')
    
    # Parquet 路径（供程序快速读取）
    parquet_dir = os.path.join(os.path.dirname(base_path), 'parquet')
    parquet_path = os.path.join(parquet_dir, f'{entity_name}.parquet')
    
    # 保存 Excel
    save_formatted_excel(df, excel_path)
    
    # 保存 Parquet
    save_as_parquet(df, parquet_path)


def save_formatted_excel(df: pd.DataFrame, output_path: str):
    """
    保存为美观的Excel格式（专家级优化版）：
    1. 智能列宽：根据内容长度自动调整，彻底解决 ######
    2. 视觉降噪：强制移除"数字存为文本"的绿色小三角
    3. 会计格式：0值显示为"-"，金额更易读
    4. 彻底汉化与清洗
    """
    # 1. 准备显示数据
    df_disp = _prepare_display_data(df)
    
    # 2. 保存并格式化
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            sheet_name = '交易流水'
            df_disp.to_excel(writer, index=False, sheet_name=sheet_name)
            
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
            # 创建格式
            formats = _create_excel_formats(workbook)
            
            # 应用格式化
            _apply_excel_formatting(worksheet, df_disp, formats)
 
    except PermissionError:
        logger.warning(f'无法保存文件 {output_path}: 文件可能被占用，请关闭Excel后重试。')
    except Exception as e:
        logger.error(f'格式化保存Excel失败: {str(e)}, 回退到普通保存')
        try:
            df_disp.to_excel(output_path, index=False)
        except PermissionError:
            logger.warning(f'无法保存文件 {output_path}: 文件可能被占用。')
