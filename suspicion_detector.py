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
    # 添加临时key用于cross join (笛卡尔积)
    withdrawals['join_key'] = 1
    deposits['join_key'] = 1
    
    # 2. 执行交叉连接 (寻找所有可能的存取现组合)
    # 注意：在极大数据量(>10万条)下，这可能消耗内存。但对于通常的审计数据(几千-几万条)是极快的。
    merged = pd.merge(withdrawals, deposits, on='join_key', suffixes=('_wd', '_dp'))
    
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
                'time_diff_hours': round(row['hours_diff'], 2), # 字段名适配
                'withdrawal_amount': row['amount_wd'],
                'deposit_amount': row['amount_dp'],
                'amount_diff': round(row['amount_diff_abs'], 2), # 字段名适配
                'amount_diff_ratio': round(row['amount_ratio'], 2),
                'risk_level': risk,
                'risk_reason': f"取现{row['amount_wd']}元与存现{row['amount_dp']}元时间间隔{row['hours_diff']:.1f}小时内，金额接近"
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
    
    # 现金交易关键词匹配函数
    def is_cash_transaction(row):
        desc = str(row.get('description', '')).lower()
        # 简单的关键词匹配，也可以用 utils.contains_keywords
        for kw in config.CASH_KEYWORDS:
            if kw in desc:
                return True
        return False

    for entity_name, df in cleaned_data.items():
        if df.empty:
            continue
            
        # 筛选出现金交易
        # 假设 'income' > 0 代表存现/进账, 'expense' > 0 代表取现/出账
        # 具体逻辑视 data_cleaner 的标准而定，这里假设有 income/expense 列
        
        cash_df = df[df.apply(is_cash_transaction, axis=1)].copy()
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

        # 执行检测
        collisions = detect_cash_time_collision(withdrawals, deposits, entity_name)
        
        if collisions:
            logger.info(f'    [{entity_name}] 发现 {len(collisions)} 处现金时空伴随')
            results['cash_collisions'].extend(collisions)
            
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
                            
                        results['direct_transfers'].append({
                            'person': person,
                            'company': company,
                            'date': row['date'],
                            'amount': amount,
                            'direction': 'payment',  # 付款
                            'description': row.get('description', ''),
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
                            
                        results['direct_transfers'].append({
                            'person': person,
                            'company': company,
                            'date': row['date'],
                            'amount': amount,
                            'direction': 'receive',  # 收款
                            'description': row.get('description', ''),
                            'risk_level': risk
                        })
                    
    # 其他检测模块 (holiday, fixed_frequency 等) 保持为空/TODO，
    # 待后续完善或添加具体的 Analyzer 模块。
    
    total_found = len(results['cash_collisions']) + len(results['direct_transfers'])
    logger.info(f'✓ 疑点检测完成，共发现 {total_found} 条有效线索')
    
    return results
