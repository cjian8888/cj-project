#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
疑点检测模块 - 实现版
用于检测资金流向中的异常模式和可疑交易
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from itertools import combinations
import config
import utils

logger = utils.setup_logger(__name__)


def detect_cash_time_collision(withdrawals: pd.DataFrame, deposits: pd.DataFrame, entity_name: str) -> List[Dict]:
    """
    检测现金时空伴随（Pandas 优化版）
    
    使用 Pandas 合并操作代替嵌套循环，大幅提升大数据量下的性能。
    输出字段已适配 report_generator.py 的需求。
    
    Args:
        withdrawals: 取现交易 DataFrame (必须包含 date, amount 等列)
        deposits: 存现交易 DataFrame (必须包含 date, amount 等列)
        entity_name: 当前账户持有人名称
    
    Returns:
        检测到的伴随交易列表
    """
    collisions = []
    
    if withdrawals.empty or deposits.empty:
        return collisions
    
    # 1. 准备数据：添加辅助列用于交叉连接
    # 使用 .copy() 避免修改原始 DataFrame（关键修复：防止数据污染）
    wd = withdrawals.copy()
    dp = deposits.copy()
    wd['join_key'] = 1
    dp['join_key'] = 1
    
    # 2. 执行交叉连接 (寻找所有可能的存取现组合)
    # 注意：在极大数据量(>10万条)下，这可能消耗内存。但对于通常的审计数据(几千-几万条)是极快的。
    merged = pd.merge(wd, dp, on='join_key', suffixes=('_wd', '_dp'))
    
    # 3. 计算时间差和金额差
    # 确保日期列是datetime类型
    merged['time_diff'] = (merged['date_dp'] - merged['date_wd']).abs()
    # 将时间差转换为小时
    merged['hours_diff'] = merged['time_diff'].dt.total_seconds() / 3600
    
    merged['amount_wd'] = merged['amount_wd'].fillna(0)
    merged['amount_dp'] = merged['amount_dp'].fillna(0)
    merged['amount_diff_abs'] = (merged['amount_wd'] - merged['amount_dp']).abs()
    
    # 计算金额差异比率 (相对于取现金额)
    # 避免除以0
    merged['amount_ratio'] = np.where(
        merged['amount_wd'] > 0,
        merged['amount_diff_abs'] / merged['amount_wd'],
        1.0
    )
    
    # 4. 应用阈值筛选
    # 时间窗口：配置的小时数
    time_mask = merged['hours_diff'] <= config.CASH_TIME_WINDOW_HOURS
    
    # 金额容差：配置的比率
    amount_mask = merged['amount_ratio'] <= config.AMOUNT_TOLERANCE_RATIO
    
    # 5. 筛选符合条件的记录
    valid_collisions = merged[time_mask & amount_mask]
    
    # 6. 格式化结果 (适配 report_generator.py 字段要求)
    if not valid_collisions.empty:
        for _, row in valid_collisions.iterrows():
            # 简单的风险等级判定
            if row['hours_diff'] < 4 and row['amount_ratio'] < 0.01:
                risk = 'high'
            elif row['hours_diff'] < 24:
                risk = 'medium'
            else:
                risk = 'low'
                
            collisions.append({
                'withdrawal_entity': entity_name,  # 取现方
                'deposit_entity': entity_name,      # 存现方
                'withdrawal_date': row['date_wd'],
                'deposit_date': row['date_dp'],
                'withdrawal_bank': row.get('银行来源_wd', '未知'),
                'deposit_bank': row.get('银行来源_dp', '未知'),
                'withdrawal_source': row.get('数据来源_wd', '未知'),
                'deposit_source': row.get('数据来源_dp', '未知'),
                'time_diff_hours': round(row['hours_diff'], 2), # 字段名适配
                'withdrawal_amount': row['amount_wd'],
                'deposit_amount': row['amount_dp'],
                'amount_diff': round(row['amount_diff_abs'], 2), # 字段名适配
                'amount_diff_ratio': round(row['amount_ratio'], 2),
                'risk_level': risk,
                'risk_reason': f"取现{row['amount_wd']}元与存现{row['amount_dp']}元时间间隔{row['hours_diff']:.1f}小时内，金额接近"
            })
            
    return collisions


def detect_cross_entity_cash_collision(
    all_withdrawals: List[Dict],
    all_deposits: List[Dict],
    time_window_hours: float = config.CASH_TIME_WINDOW_HOURS,
    amount_tolerance: float = config.AMOUNT_TOLERANCE_RATIO
) -> List[Dict]:
    """
    跨实体现金碰撞检测 - 核心审计功能
    
    检测不同人之间的现金取存时空伴随模式，这是识别洗钱、利益输送的关键手段。
    
    典型场景:
    - Person A 在 ATM 取现 5万
    - Person B 30分钟后在同一/附近 ATM 存入 5万
    
    Args:
        all_withdrawals: 所有实体的取现记录列表 [{entity, date, amount, bank, ...}, ...]
        all_deposits: 所有实体的存现记录列表 [{entity, date, amount, bank, ...}, ...]
        time_window_hours: 时间窗口（小时）
        amount_tolerance: 金额容差比例
    
    Returns:
        跨实体现金碰撞列表
    """
    collisions = []
    
    if not all_withdrawals or not all_deposits:
        return collisions
    
    # 按时间排序以优化搜索
    sorted_withdrawals = sorted(all_withdrawals, key=lambda x: x['date'])
    sorted_deposits = sorted(all_deposits, key=lambda x: x['date'])
    
    for wd in sorted_withdrawals:
        wd_entity = wd['entity']
        wd_date = wd['date']
        wd_amount = wd['amount']
        
        for dp in sorted_deposits:
            dp_entity = dp['entity']
            dp_date = dp['date']
            dp_amount = dp['amount']
            
            # 跳过同一实体的记录（单实体内碰撞在其他函数处理）
            if wd_entity == dp_entity:
                continue
            
            # 存现应在取现之后（或同时）
            if dp_date < wd_date:
                continue
            
            # 计算时间差
            time_diff = (dp_date - wd_date).total_seconds() / 3600
            
            # 超出时间窗口则跳过
            if time_diff > time_window_hours:
                continue
            
            # 检查金额匹配
            amount_diff = abs(wd_amount - dp_amount)
            amount_ratio = amount_diff / wd_amount if wd_amount > 0 else 1.0
            
            if amount_ratio <= amount_tolerance:
                # 判断风险等级
                if time_diff < 2 and amount_ratio < 0.01:
                    risk = 'high'
                    risk_desc = '极高相关性'
                elif time_diff < 12 and amount_ratio < 0.05:
                    risk = 'high'
                    risk_desc = '高度可疑'
                elif time_diff < 24:
                    risk = 'medium'
                    risk_desc = '需进一步核查'
                else:
                    risk = 'low'
                    risk_desc = '可能巧合'
                
                collisions.append({
                    'withdrawal_entity': wd_entity,
                    'deposit_entity': dp_entity,
                    'withdrawal_date': wd_date,
                    'deposit_date': dp_date,
                    'withdrawal_amount': wd_amount,
                    'deposit_amount': dp_amount,
                    'withdrawal_bank': wd.get('bank', '未知'),
                    'deposit_bank': dp.get('bank', '未知'),
                    'withdrawal_source': wd.get('source_file', ''),
                    'deposit_source': dp.get('source_file', ''),
                    'time_diff_hours': round(time_diff, 2),
                    'amount_diff': round(amount_diff, 2),
                    'amount_diff_ratio': round(amount_ratio, 4),
                    'risk_level': risk,
                    'risk_reason': f"[跨实体] {wd_entity}取现{wd_amount/10000:.2f}万 → "
                                   f"{dp_entity}存现{dp_amount/10000:.2f}万, "
                                   f"时差{time_diff:.1f}小时, {risk_desc}"
                })
    
    return collisions


def run_all_detections(cleaned_data: Dict, all_persons: List[str], all_companies: List[str]) -> Dict:
    """
    运行所有疑点检测的主入口
    
    Args:
        cleaned_data: 清洗后的交易数据 {entity_name: DataFrame}
        all_persons: 所有核心人员名单
        all_companies: 所有涉案公司名单
    
    Returns:
        包含所有检测结果的字典
    """
    logger.info('开始执行疑点检测...')
    
    results = {
        'direct_transfers': [],          # 直接资金往来
        'cash_collisions': [],            # 现金时空伴随
        'hidden_assets': {},              # 隐形资产
        'fixed_frequency': {},           # 固定频率异常
        'cash_timing_patterns': [],       # 现金时间点配对
        'holiday_transactions': {},      # 节假日/特殊时段
        'amount_patterns': {}            # 金额模式异常
    }
    
    # ============================
    # 1. 现金时空伴随检测
    # ============================
    logger.info('  -> 正在检测现金时空伴随...')
    
    # 【铁律修复】现金交易识别：直接读取 cleaned_data 中已标记的 is_cash / 现金 列
    # 不再重复用关键词匹配，复用 data_cleaner 的计算结果
    def get_cash_transactions(df: pd.DataFrame) -> pd.DataFrame:
        """
        从 DataFrame 中提取现金交易记录
        
        优先级：
        1. is_cash 列（布尔类型，data_cleaner 内存中的格式）
        2. 现金 列（字符串 '是'，从 Excel 读取时的格式）
        3. 降级：如果都没有，使用关键词匹配（最后手段）
        """
        if 'is_cash' in df.columns:
            # 直接使用已计算的布尔列
            return df[df['is_cash'] == True].copy()
        elif '现金' in df.columns:
            # 从 Excel 读取时，现金列是字符串 '是' 或 ''
            return df[df['现金'] == '是'].copy()
        else:
            # 降级：没有现金标记列，使用关键词匹配（兼容旧数据）
            logger.warning('  ⚠️ 未找到现金标记列，降级为关键词匹配')
            def is_cash_by_keyword(row):
                desc = str(row.get('description', '')).lower()
                for kw in config.CASH_KEYWORDS:
                    if kw in desc:
                        return True
                return False
            return df[df.apply(is_cash_by_keyword, axis=1)].copy()

    # 收集所有实体的取现和存现记录（用于跨实体检测）
    all_withdrawals = []
    all_deposits = []

    for entity_name, df in cleaned_data.items():
        if df.empty:
            continue
            
        # 【铁律】直接读取已标记的现金列
        cash_df = get_cash_transactions(df)
        if cash_df.empty:
            continue
        
        # 拆分为取现和存现
        # 注意：根据实际列名调整，这里假设 amount 为正数，或者分列 income/expense
        # 如果是单列 amount，正负表示方向；如果是双列，income表示进，expense表示出
        
        # 策略：如果有 income/expense 列
        if 'income' in cash_df.columns and 'expense' in cash_df.columns:
            withdrawals = cash_df[cash_df['expense'] > 0].copy()
            deposits = cash_df[cash_df['income'] > 0].copy()
            # 标准化金额列为 amount
            withdrawals['amount'] = withdrawals['expense']
            deposits['amount'] = deposits['income']
        else:
            # 只有单列 amount 的情况（假设负数为支出）
            withdrawals = cash_df[cash_df['amount'] < 0].copy()
            deposits = cash_df[cash_df['amount'] > 0].copy()
            withdrawals['amount'] = withdrawals['amount'].abs()
            deposits['amount'] = deposits['amount']

        # 执行单实体内检测
        collisions = detect_cash_time_collision(withdrawals, deposits, entity_name)
        
        if collisions:
            logger.info(f'    [{entity_name}] 发现 {len(collisions)} 处现金时空伴随(单实体)')
            results['cash_collisions'].extend(collisions)
        
        # 收集取现和存现记录用于跨实体检测
        for _, row in withdrawals.iterrows():
            bank_val = row.get('银行来源', row.get('bank', ''))
            source_val = row.get('数据来源', row.get('source_file', ''))
            all_withdrawals.append({
                'entity': entity_name,
                'date': row['date'],
                'amount': row['amount'],
                'bank': str(bank_val) if bank_val and str(bank_val) != 'nan' else '',
                'source_file': str(source_val) if source_val and str(source_val) != 'nan' else '',
                'description': row.get('description', '')
            })
        
        for _, row in deposits.iterrows():
            bank_val = row.get('银行来源', row.get('bank', ''))
            source_val = row.get('数据来源', row.get('source_file', ''))
            all_deposits.append({
                'entity': entity_name,
                'date': row['date'],
                'amount': row['amount'],
                'bank': str(bank_val) if bank_val and str(bank_val) != 'nan' else '',
                'source_file': str(source_val) if source_val and str(source_val) != 'nan' else '',
                'description': row.get('description', '')
            })
    
    # ============================
    # 1.1 跨实体现金碰撞检测（核心审计功能）
    # ============================
    if all_withdrawals and all_deposits:
        logger.info('  -> 正在检测跨实体现金碰撞（洗钱模式识别）...')
        cross_collisions = detect_cross_entity_cash_collision(all_withdrawals, all_deposits)
        
        if cross_collisions:
            logger.info(f'    发现 {len(cross_collisions)} 处跨实体现金碰撞')
            results['cash_collisions'].extend(cross_collisions)
            
    # ============================
    # 2. 直接资金往来检测 (修复：适配 report_generator 需求)
    # ============================
    logger.info('  -> 正在分析直接资金往来...')
    
    # 检测核心人员与涉案公司之间的直接资金往来
    for person in all_persons:
        for company in all_companies:
            if person in cleaned_data and company in cleaned_data:
                
                # 检测：人员 -> 公司 (支出)
                df_person = cleaned_data[person]
                transfers_out = df_person[df_person['counterparty'].str.contains(company, na=False)]
                if not transfers_out.empty:
                    for _, row in transfers_out.iterrows():
                        amount = row.get('expense', 0)
                        # 简单的风险定级
                        if amount > config.INCOME_HIGH_RISK_MIN:
                            risk = 'high'
                        elif amount > 50000:
                            risk = 'medium'
                        else:
                            risk = 'low'
                            
                        # 提取上下文信息 (处理 category 类型和 NaN)
                        bank_val = row.get('银行来源', None)
                        source_val = row.get('数据来源', None)
                        bank = str(bank_val) if bank_val is not None and str(bank_val) != 'nan' else ''
                        source_file = str(source_val) if source_val is not None and str(source_val) != 'nan' else ''
                        
                        results['direct_transfers'].append({
                            'person': person,
                            'company': company,
                            'date': row['date'],
                            'amount': amount,
                            'direction': 'payment',  # 付款
                            'description': row.get('description', ''),
                            'bank': bank,
                            'source_file': source_file,
                            'risk_level': risk
                        })
                
                # 检测：公司 -> 人员 (收入)
                df_company = cleaned_data[company]
                transfers_in = df_company[df_company['counterparty'].str.contains(person, na=False)]
                if not transfers_in.empty:
                    for _, row in transfers_in.iterrows():
                        amount = row.get('income', 0)
                        # 简单的风险定级
                        if amount > config.INCOME_HIGH_RISK_MIN:
                            risk = 'high'
                        elif amount > 50000:
                            risk = 'medium'
                        else:
                            risk = 'low'
                        
                        # 提取上下文信息 (处理 category 类型和 NaN)
                        bank_val = row.get('银行来源', None)
                        source_val = row.get('数据来源', None)
                        bank = str(bank_val) if bank_val is not None and str(bank_val) != 'nan' else ''
                        source_file = str(source_val) if source_val is not None and str(source_val) != 'nan' else ''
                            
                        results['direct_transfers'].append({
                            'person': person,
                            'company': company,
                            'date': row['date'],
                            'amount': amount,
                            'direction': 'receive',  # 收款
                            'description': row.get('description', ''),
                            'bank': bank,
                            'source_file': source_file,
                            'risk_level': risk
                        })
                    
    # 其他检测模块 (holiday, fixed_frequency 等) 保持为空/TODO，
    # 待后续完善或添加具体的 Analyzer 模块。
    
    total_found = len(results['cash_collisions']) + len(results['direct_transfers'])
    logger.info(f'✓ 疑点检测完成，共发现 {total_found} 条有效线索')
    
    return results
