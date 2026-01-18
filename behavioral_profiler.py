#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行为特征画像模块 (Phase 0.2 - 2026-01-18 新增)

【模块定位】
实现刑侦级行为特征检测：
1. 快进快出 (Fast-In-Fast-Out) - 洗钱/过桥资金典型特征
2. 整进散出/散进整出 (Structuring) - 规避监管特征
3. 休眠激活 (Dormant Activation) - 账户异常激活

【审计价值】
- 识别资金过账、洗钱、规避监管等行为模式
- 每条检测结果可追溯到具体交易行
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

import config
import utils

logger = utils.setup_logger(__name__)


# ============================================================
# 配置参数
# ============================================================

# 快进快出检测参数
FAST_IN_OUT_TIME_WINDOW_HOURS = 24      # 时间窗口（小时）
FAST_IN_OUT_SAME_DAY = True             # 是否检测当天进出
FAST_IN_OUT_MIN_AMOUNT = 10000          # 最低金额（1万）
FAST_IN_OUT_AMOUNT_RATIO = 0.8          # 进出金额匹配比例

# 整进散出检测参数
STRUCTURING_MIN_SPLIT_COUNT = 3         # 最少拆分笔数
STRUCTURING_AMOUNT_TOLERANCE = 0.2      # 金额匹配容差（20%）
STRUCTURING_TIME_WINDOW_DAYS = 7        # 时间窗口（天）

# 休眠激活检测参数
DORMANT_MIN_DAYS = 180                  # 休眠期最少天数
DORMANT_ACTIVATION_MIN_AMOUNT = 50000   # 激活后大额阈值


# ============================================================
# 快进快出检测 (Fast-In-Fast-Out)
# ============================================================

def detect_fast_in_out(
    df: pd.DataFrame,
    time_window_hours: int = FAST_IN_OUT_TIME_WINDOW_HOURS,
    min_amount: float = FAST_IN_OUT_MIN_AMOUNT,
    balance_threshold: float = None
) -> List[Dict]:
    """
    检测资金快进快出模式（洗钱/过桥资金典型特征）
    
    规则：
    1. 有大额收入(>min_amount)
    2. 在时间窗口内有接近金额的支出
    3. 支出后余额接近归零（可选）
    
    Args:
        df: 交易DataFrame（需包含 date, income, expense, balance 列）
        time_window_hours: 时间窗口（小时）
        min_amount: 触发检测的最低金额
        balance_threshold: 余额归零阈值（None则不检查）
        
    Returns:
        快进快出模式列表
    """
    if df.empty:
        return []
    
    if balance_threshold is None:
        balance_threshold = getattr(config, 'BALANCE_ZERO_THRESHOLD', 10.0)
    
    # 确保按时间排序
    df = df.sort_values('date').reset_index(drop=True)
    
    patterns = []
    
    # 获取所有收入记录
    income_mask = df['income'].fillna(0) >= min_amount
    income_records = df[income_mask]
    
    for idx, income_row in income_records.iterrows():
        income_date = income_row['date']
        income_amount = income_row['income']
        
        if not isinstance(income_date, (datetime, pd.Timestamp)):
            continue
        
        # 查找时间窗口内的支出
        window_end = income_date + timedelta(hours=time_window_hours)
        
        expense_mask = (
            (df['date'] > income_date) &
            (df['date'] <= window_end) &
            (df['expense'].fillna(0) >= min_amount * FAST_IN_OUT_AMOUNT_RATIO)
        )
        
        expense_candidates = df[expense_mask]
        
        for exp_idx, expense_row in expense_candidates.iterrows():
            expense_amount = expense_row['expense']
            balance_after = expense_row.get('balance', None)
            
            # 检查金额匹配（支出应接近收入）
            amount_ratio = expense_amount / income_amount if income_amount > 0 else 0
            if amount_ratio < FAST_IN_OUT_AMOUNT_RATIO or amount_ratio > 1.2:
                continue
            
            # 检查余额归零（可选）
            balance_zeroed = False
            if balance_after is not None and pd.notna(balance_after):
                balance_zeroed = balance_after < balance_threshold
            
            # 计算时间差
            time_diff = expense_row['date'] - income_date
            hours_diff = time_diff.total_seconds() / 3600
            
            patterns.append({
                'type': 'fast_in_out',
                'risk_level': 'high' if balance_zeroed else 'medium',
                'income_date': income_date,
                'income_amount': income_amount,
                'income_counterparty': str(income_row.get('counterparty', '')),
                'expense_date': expense_row['date'],
                'expense_amount': expense_amount,
                'expense_counterparty': str(expense_row.get('counterparty', '')),
                'hours_diff': round(hours_diff, 1),
                'balance_after': balance_after,
                'balance_zeroed': balance_zeroed,
                'income_row_idx': idx,
                'expense_row_idx': exp_idx,
                'description': f"资金停留{hours_diff:.1f}小时后转出，{'余额归零' if balance_zeroed else '余额未归零'}"
            })
    
    logger.info(f"快进快出检测完成：发现 {len(patterns)} 个模式")
    return patterns


# ============================================================
# 整进散出/散进整出检测 (Structuring)
# ============================================================

def detect_structuring(
    df: pd.DataFrame,
    min_large_amount: float = 50000,
    min_split_count: int = STRUCTURING_MIN_SPLIT_COUNT,
    time_window_days: int = STRUCTURING_TIME_WINDOW_DAYS
) -> List[Dict]:
    """
    检测资金拆分/归集模式（规避监管特征）
    
    整进散出：一笔大额进来，多笔小额出去（总额接近）
    散进整出：多笔小额进来，一笔大额出去（总额接近）
    
    Args:
        df: 交易DataFrame
        min_large_amount: 大额交易阈值
        min_split_count: 最少拆分笔数
        time_window_days: 时间窗口（天）
        
    Returns:
        资金拆分/归集模式列表
    """
    if df.empty:
        return []
    
    df = df.sort_values('date').reset_index(drop=True)
    patterns = []
    
    # --- 检测整进散出 (Large-In, Split-Out) ---
    large_income_mask = df['income'].fillna(0) >= min_large_amount
    large_incomes = df[large_income_mask]
    
    for idx, income_row in large_incomes.iterrows():
        income_date = income_row['date']
        income_amount = income_row['income']
        
        if not isinstance(income_date, (datetime, pd.Timestamp)):
            continue
        
        # 查找时间窗口内的多笔支出
        window_end = income_date + timedelta(days=time_window_days)
        
        expense_mask = (
            (df['date'] > income_date) &
            (df['date'] <= window_end) &
            (df['expense'].fillna(0) > 0) &
            (df['expense'].fillna(0) < income_amount * 0.6)  # 单笔小于大额的60%
        )
        
        small_expenses = df[expense_mask]
        
        if len(small_expenses) >= min_split_count:
            total_expense = small_expenses['expense'].sum()
            ratio = total_expense / income_amount if income_amount > 0 else 0
            
            # 总支出应接近收入（80%-120%）
            if 0.8 <= ratio <= 1.2:
                patterns.append({
                    'type': 'large_in_split_out',
                    'risk_level': 'high',
                    'trigger_date': income_date,
                    'large_amount': income_amount,
                    'large_counterparty': str(income_row.get('counterparty', '')),
                    'split_count': len(small_expenses),
                    'split_total': total_expense,
                    'split_ratio': round(ratio, 2),
                    'time_window_days': time_window_days,
                    'description': f"大额收入{income_amount/10000:.1f}万后，{len(small_expenses)}笔分散支出共{total_expense/10000:.1f}万"
                })
    
    # --- 检测散进整出 (Split-In, Large-Out) ---
    large_expense_mask = df['expense'].fillna(0) >= min_large_amount
    large_expenses = df[large_expense_mask]
    
    for idx, expense_row in large_expenses.iterrows():
        expense_date = expense_row['date']
        expense_amount = expense_row['expense']
        
        if not isinstance(expense_date, (datetime, pd.Timestamp)):
            continue
        
        # 查找时间窗口内之前的多笔收入
        window_start = expense_date - timedelta(days=time_window_days)
        
        income_mask = (
            (df['date'] >= window_start) &
            (df['date'] < expense_date) &
            (df['income'].fillna(0) > 0) &
            (df['income'].fillna(0) < expense_amount * 0.6)  # 单笔小于大额的60%
        )
        
        small_incomes = df[income_mask]
        
        if len(small_incomes) >= min_split_count:
            total_income = small_incomes['income'].sum()
            ratio = total_income / expense_amount if expense_amount > 0 else 0
            
            # 总收入应接近支出（80%-120%）
            if 0.8 <= ratio <= 1.2:
                patterns.append({
                    'type': 'split_in_large_out',
                    'risk_level': 'high',
                    'trigger_date': expense_date,
                    'large_amount': expense_amount,
                    'large_counterparty': str(expense_row.get('counterparty', '')),
                    'split_count': len(small_incomes),
                    'split_total': total_income,
                    'split_ratio': round(ratio, 2),
                    'time_window_days': time_window_days,
                    'description': f"{len(small_incomes)}笔分散收入共{total_income/10000:.1f}万后，大额支出{expense_amount/10000:.1f}万"
                })
    
    logger.info(f"整进散出/散进整出检测完成：发现 {len(patterns)} 个模式")
    return patterns


# ============================================================
# 休眠激活检测 (Dormant Activation)
# ============================================================

def detect_dormant_activation(
    df: pd.DataFrame,
    dormant_min_days: int = DORMANT_MIN_DAYS,
    activation_min_amount: float = DORMANT_ACTIVATION_MIN_AMOUNT
) -> List[Dict]:
    """
    检测休眠账户激活模式
    
    规则：
    1. 账户连续N天(默认180天)无交易
    2. 突然发生大额资金进出
    
    Args:
        df: 交易DataFrame
        dormant_min_days: 休眠期最少天数
        activation_min_amount: 激活后大额交易阈值
        
    Returns:
        休眠激活模式列表
    """
    if df.empty or len(df) < 2:
        return []
    
    df = df.sort_values('date').reset_index(drop=True)
    patterns = []
    
    # 计算每笔交易与上一笔的时间间隔
    df['prev_date'] = df['date'].shift(1)
    df['days_gap'] = (df['date'] - df['prev_date']).dt.days
    
    # 查找休眠期后的大额交易
    for idx in range(1, len(df)):
        row = df.iloc[idx]
        days_gap = row['days_gap']
        
        if pd.isna(days_gap):
            continue
        
        # 检查是否有足够长的休眠期
        if days_gap >= dormant_min_days:
            # 检查激活后是否有大额交易
            amount = max(row.get('income', 0) or 0, row.get('expense', 0) or 0)
            
            if amount >= activation_min_amount:
                direction = '收入' if (row.get('income', 0) or 0) > (row.get('expense', 0) or 0) else '支出'
                
                patterns.append({
                    'type': 'dormant_activation',
                    'risk_level': 'high',
                    'dormant_days': int(days_gap),
                    'activation_date': row['date'],
                    'activation_amount': amount,
                    'activation_direction': direction,
                    'counterparty': str(row.get('counterparty', '')),
                    'prev_transaction_date': row['prev_date'],
                    'row_idx': idx,
                    'description': f"账户休眠{int(days_gap)}天后，突发{direction}{amount/10000:.1f}万"
                })
    
    # 清理临时列
    df.drop(['prev_date', 'days_gap'], axis=1, inplace=True, errors='ignore')
    
    logger.info(f"休眠激活检测完成：发现 {len(patterns)} 个模式")
    return patterns


# ============================================================
# 综合行为分析入口
# ============================================================

def analyze_behavioral_patterns(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """
    综合行为特征画像分析
    
    Args:
        all_transactions: 所有交易数据 {entity_name: DataFrame}
        core_persons: 核心人员列表
        
    Returns:
        行为特征分析结果
    """
    logger.info('='*60)
    logger.info('开始行为特征画像分析 (Phase 0.2)')
    logger.info('='*60)
    
    results = {
        'fast_in_out': [],
        'structuring': [],
        'dormant_activation': [],
        'summary': {}
    }
    
    for entity, df in all_transactions.items():
        if df.empty:
            continue
        
        logger.info(f"分析 {entity} 的行为特征...")
        
        # 1. 快进快出检测
        fifo_patterns = detect_fast_in_out(df)
        for p in fifo_patterns:
            p['entity'] = entity
        results['fast_in_out'].extend(fifo_patterns)
        
        # 2. 整进散出/散进整出检测
        structuring_patterns = detect_structuring(df)
        for p in structuring_patterns:
            p['entity'] = entity
        results['structuring'].extend(structuring_patterns)
        
        # 3. 休眠激活检测
        dormant_patterns = detect_dormant_activation(df)
        for p in dormant_patterns:
            p['entity'] = entity
        results['dormant_activation'].extend(dormant_patterns)
    
    # 汇总统计
    results['summary'] = {
        'fast_in_out_count': len(results['fast_in_out']),
        'structuring_count': len(results['structuring']),
        'dormant_activation_count': len(results['dormant_activation']),
        'total_patterns': (
            len(results['fast_in_out']) + 
            len(results['structuring']) + 
            len(results['dormant_activation'])
        )
    }
    
    logger.info(f"行为特征画像分析完成:")
    logger.info(f"  - 快进快出: {results['summary']['fast_in_out_count']} 个")
    logger.info(f"  - 整进散出/散进整出: {results['summary']['structuring_count']} 个")
    logger.info(f"  - 休眠激活: {results['summary']['dormant_activation_count']} 个")
    
    return results


def generate_behavioral_report(results: Dict, output_dir: str) -> str:
    """
    生成行为特征画像报告
    """
    import os
    report_path = os.path.join(output_dir, '行为特征画像报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('行为特征画像分析报告\n')
        f.write('='*60 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        
        # 快进快出
        f.write('一、快进快出模式（洗钱/过桥资金特征）\n')
        f.write('-'*40 + '\n')
        fifo = results.get('fast_in_out', [])
        if fifo:
            for i, p in enumerate(fifo[:20], 1):
                f.write(f"{i}. [{p['entity']}] {p['description']}\n")
                f.write(f"   收入: {p['income_amount']/10000:.2f}万 ← {p['income_counterparty']}\n")
                f.write(f"   支出: {p['expense_amount']/10000:.2f}万 → {p['expense_counterparty']}\n\n")
        else:
            f.write("未检测到快进快出模式。\n\n")
        
        # 整进散出
        f.write('\n二、整进散出/散进整出模式（规避监管特征）\n')
        f.write('-'*40 + '\n')
        structuring = results.get('structuring', [])
        if structuring:
            for i, p in enumerate(structuring[:20], 1):
                f.write(f"{i}. [{p['entity']}] {p['description']}\n")
                f.write(f"   类型: {'整进散出' if p['type'] == 'large_in_split_out' else '散进整出'}\n")
                f.write(f"   大额方: {p['large_counterparty']}\n\n")
        else:
            f.write("未检测到整进散出/散进整出模式。\n\n")
        
        # 休眠激活
        f.write('\n三、休眠激活模式（账户异常激活）\n')
        f.write('-'*40 + '\n')
        dormant = results.get('dormant_activation', [])
        if dormant:
            for i, p in enumerate(dormant[:20], 1):
                f.write(f"{i}. [{p['entity']}] {p['description']}\n")
                f.write(f"   对手方: {p['counterparty']}\n\n")
        else:
            f.write("未检测到休眠激活模式。\n\n")
    
    logger.info(f'行为特征画像报告已生成: {report_path}')
    return report_path


# ============================================================
# Phase 0.3: 资金沉淀与去向分析 (2026-01-18 新增)
# ============================================================

def calculate_fund_retention_rate(df: pd.DataFrame) -> Dict:
    """
    计算资金留存率 = (总流入-总流出)/总流入
    
    审计意义：
    - 留存率<10%: 过账嫌疑（资金"过路财神"）
    - 留存率>90%: 资金沉淀（储蓄或消费）
    - 留存率50%-70%: 正常消费模式
    
    Args:
        df: 交易DataFrame
        
    Returns:
        留存率分析结果
    """
    if df.empty:
        return {
            'total_inflow': 0,
            'total_outflow': 0,
            'retention_rate': 0,
            'risk_level': 'unknown',
            'description': '无交易数据'
        }
    
    total_inflow = df['income'].fillna(0).sum()
    total_outflow = df['expense'].fillna(0).sum()
    
    if total_inflow == 0:
        retention_rate = 0
        risk_type = 'no_income'
    else:
        retention_rate = (total_inflow - total_outflow) / total_inflow
    
    # 风险等级判断
    if retention_rate < 0.1:
        risk_level = 'high'
        risk_type = 'pass_through'  # 过账
        description = f'留存率极低({retention_rate*100:.1f}%)，疑似过账账户'
    elif retention_rate < 0.3:
        risk_level = 'medium'
        risk_type = 'low_retention'
        description = f'留存率较低({retention_rate*100:.1f}%)，资金周转快'
    elif retention_rate > 0.9:
        risk_level = 'low'
        risk_type = 'accumulation'  # 沉淀
        description = f'留存率高({retention_rate*100:.1f}%)，资金沉淀明显'
    else:
        risk_level = 'low'
        risk_type = 'normal'
        description = f'留存率正常({retention_rate*100:.1f}%)'
    
    return {
        'total_inflow': total_inflow,
        'total_outflow': total_outflow,
        'net_flow': total_inflow - total_outflow,
        'retention_rate': round(retention_rate, 4),
        'retention_percent': f'{retention_rate*100:.1f}%',
        'risk_level': risk_level,
        'risk_type': risk_type,
        'description': description
    }


def analyze_counterparty_frequency(
    df: pd.DataFrame,
    core_persons: List[str] = None,
    min_frequency: int = 5,
    max_amount: float = 5000,
    period_days: int = 30
) -> List[Dict]:
    """
    分析非核心关联人的高频小额往来
    
    审计意义：
    - 高频小额往来可能是地下钱庄、网络赌博、虚假交易的特征
    - 排除核心人员后，剩余的高频对手方值得关注
    
    Args:
        df: 交易DataFrame
        core_persons: 核心人员列表（将被排除）
        min_frequency: 高频阈值（月均次数）
        max_amount: 小额阈值
        period_days: 统计周期（天）
        
    Returns:
        可疑高频对手方列表
    """
    if df.empty:
        return []
    
    if core_persons is None:
        core_persons = []
    
    # 确保有对手方列
    if 'counterparty' not in df.columns:
        return []
    
    # 筛选小额交易
    df_small = df[
        ((df['income'].fillna(0) > 0) & (df['income'].fillna(0) <= max_amount)) |
        ((df['expense'].fillna(0) > 0) & (df['expense'].fillna(0) <= max_amount))
    ].copy()
    
    if df_small.empty:
        return []
    
    # 统计对手方频次
    cp_stats = df_small.groupby('counterparty').agg({
        'income': ['count', 'sum'],
        'expense': ['count', 'sum']
    }).reset_index()
    cp_stats.columns = ['counterparty', 'income_count', 'income_sum', 'expense_count', 'expense_sum']
    cp_stats['total_count'] = cp_stats['income_count'] + cp_stats['expense_count']
    cp_stats['total_amount'] = cp_stats['income_sum'].fillna(0) + cp_stats['expense_sum'].fillna(0)
    
    # 计算月均频次
    if 'date' in df.columns:
        date_range = (df['date'].max() - df['date'].min()).days
        months = max(date_range / 30, 1)
    else:
        months = 1
    
    cp_stats['monthly_freq'] = cp_stats['total_count'] / months
    
    # 筛选高频对手方
    suspicious = []
    for _, row in cp_stats.iterrows():
        cp = str(row['counterparty'])
        
        # 排除空值和核心人员
        if not cp or cp == 'nan' or cp in core_persons:
            continue
        
        # 排除常见正规机构
        if utils.contains_keywords(cp, ['支付宝', '微信', '银行', '财付通', '京东']):
            continue
        
        if row['monthly_freq'] >= min_frequency:
            suspicious.append({
                'counterparty': cp,
                'total_count': int(row['total_count']),
                'monthly_freq': round(row['monthly_freq'], 1),
                'total_amount': row['total_amount'],
                'avg_amount': row['total_amount'] / row['total_count'] if row['total_count'] > 0 else 0,
                'risk_level': 'high' if row['monthly_freq'] >= min_frequency * 2 else 'medium',
                'description': f"月均{row['monthly_freq']:.1f}次小额往来，总计{row['total_count']}笔"
            })
    
    # 按频次排序
    suspicious.sort(key=lambda x: -x['monthly_freq'])
    
    logger.info(f"对手方频次分析完成：发现 {len(suspicious)} 个高频小额对手方")
    return suspicious


def analyze_fund_sedimentation(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """
    综合资金沉淀分析（Phase 0.3 入口）
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        
    Returns:
        资金沉淀分析结果
    """
    logger.info('='*60)
    logger.info('开始资金沉淀与去向分析 (Phase 0.3)')
    logger.info('='*60)
    
    results = {
        'retention_rates': {},
        'suspicious_counterparties': [],
        'pass_through_accounts': [],
        'summary': {}
    }
    
    for entity, df in all_transactions.items():
        if df.empty:
            continue
        
        logger.info(f"分析 {entity} 的资金沉淀...")
        
        # 1. 计算留存率
        retention = calculate_fund_retention_rate(df)
        retention['entity'] = entity
        results['retention_rates'][entity] = retention
        
        # 标记过账账户
        if retention['risk_type'] == 'pass_through':
            results['pass_through_accounts'].append(entity)
        
        # 2. 对手方频次分析
        cp_analysis = analyze_counterparty_frequency(df, core_persons)
        for cp in cp_analysis:
            cp['entity'] = entity
        results['suspicious_counterparties'].extend(cp_analysis)
    
    # 汇总
    results['summary'] = {
        'total_entities': len(results['retention_rates']),
        'pass_through_count': len(results['pass_through_accounts']),
        'suspicious_counterparties_count': len(results['suspicious_counterparties'])
    }
    
    logger.info(f"资金沉淀分析完成:")
    logger.info(f"  - 过账账户: {len(results['pass_through_accounts'])} 个")
    logger.info(f"  - 可疑高频对手方: {len(results['suspicious_counterparties'])} 个")
    
    return results

