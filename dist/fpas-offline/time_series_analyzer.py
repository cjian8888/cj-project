#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
时间序列分析模块（新增 - 2026-01-11）

【模块定位】
专业的时序分析模块，用于：
1. 周期性资金检测 - 发现"每月5日固定入账5万"的养廉资金模式
2. 异常时序模式 - 发现"固定延迟转账"等规律
3. 资金波动分析 - 发现突然激增的异常模式

【审计价值】
- 周期性收入往往是"养廉资金"或固定回扣
- 规律性转账可能暗示利益输送协议
- 突然激增可能与特定事件关联

【技术实现】
- 自相关分析 (ACF) - 检测周期性
- 傅里叶变换 (FFT) - 提取主频率
- 滑动窗口统计 - 检测突变
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict

import config
import utils

logger = utils.setup_logger(__name__)


def _normalize_time_series_df(df: pd.DataFrame) -> pd.DataFrame:
    """统一标准化时序分析所依赖的日期和金额字段。"""
    if df is None or df.empty:
        return pd.DataFrame()

    normalized = df.copy()
    if 'date' in normalized.columns:
        normalized['date'] = utils.normalize_datetime_series(normalized['date'])
        normalized = normalized[normalized['date'].notna()].copy()
    for amount_col in ('income', 'expense', 'amount'):
        if amount_col in normalized.columns:
            normalized[amount_col] = utils.normalize_amount_series(
                normalized[amount_col], amount_col
            )
    normalized = utils.sort_transactions_strict(
        normalized,
        date_col='date',
        dropna_date=True,
    )
    return normalized


# ============================================================
# 周期性检测
# ============================================================

def detect_periodic_income(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_occurrences: int = 5,
    amount_tolerance: float = 0.1
) -> List[Dict]:
    """
    检测周期性收入模式
    
    审计意义：
    - 固定日期固定金额的收入可能是"养廉资金"
    - 与工资不同，这类收入往往来自特定个人或公司
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        min_occurrences: 最小出现次数
        amount_tolerance: 金额容差比例
        
    Returns:
        周期性收入列表
    """
    logger.info('='*60)
    logger.info('开始周期性收入检测')
    logger.info('='*60)
    
    periodic_patterns = []
    
    for person in core_persons:
        df = _normalize_time_series_df(all_transactions.get(person))
        if df is None or df.empty:
            continue
        
        # 只看收入
        income_df = df[df['income'] > 0].copy()
        if income_df.empty:
            continue
                
        # 【2026-03-04 优化】限制对手方数量，避免极端情况
        # 按交易频次排序，只处理高频对手方
        counterparty_counts = income_df['counterparty'].value_counts()
        top_counterparties = counterparty_counts.head(100).index  # 限制前100个对手方
        income_df_filtered = income_df[income_df['counterparty'].isin(top_counterparties)]
        
        if len(income_df_filtered) < len(income_df):
            logger.info(f"  时序分析: 从 {len(income_df)} 条记录筛选前100对手方，剩余 {len(income_df_filtered)} 条")
        
        # 按对手方分组
        for cp, group in income_df_filtered.groupby('counterparty'):
            if pd.isna(cp) or len(group) < min_occurrences:
                continue
            
            # 分析时间间隔
            group = utils.sort_transactions_strict(group, date_col='date', dropna_date=True)
            dates = group['date']
            amounts = group['income'].values
            
            # 向量化计算日期间隔
            intervals = dates.diff().dt.days.dropna()
            intervals = intervals[intervals > 0].tolist()
            
            if len(intervals) < min_occurrences - 1:
                continue
            
            # 检测周期性
            avg_interval = np.mean(intervals)
            interval_std = np.std(intervals)
            cv = interval_std / avg_interval if avg_interval > 0 else float('inf')
            
            # 检测金额一致性
            avg_amount = np.mean(amounts)
            amount_std = np.std(amounts)
            amount_cv = amount_std / avg_amount if avg_amount > 0 else float('inf')
            
            # 周期性判定：间隔CV < 0.3 且 金额CV < 容差
            is_periodic = cv < 0.3 and amount_cv < amount_tolerance
            
            if is_periodic:
                # 确定周期类型
                period_type = _classify_period(avg_interval)
                
                # 排除工资（检查是否包含工资关键词）
                is_salary = utils.contains_keywords(str(cp), config.SALARY_KEYWORDS)
                
                if not is_salary:
                    # 获取第一条记录的溯源信息
                    first_record = group.iloc[0]
                    
                    periodic_patterns.append({
                        'person': person,
                        'counterparty': str(cp),
                        'occurrences': len(group),
                        'avg_interval_days': round(avg_interval, 1),
                        'interval_cv': round(cv, 3),
                        'period_type': period_type,
                        'avg_amount': round(avg_amount, 2),
                        'amount_cv': round(amount_cv, 3),
                        'total_amount': round(sum(amounts), 2),
                        'date_range': f"{dates.iloc[0].strftime('%Y-%m-%d')} 至 {dates.iloc[-1].strftime('%Y-%m-%d')}",
                        'risk_level': 'high' if avg_amount >= config.TIME_SERIES_HIGH_RISK_AMOUNT else 'medium',
                        'confidence': _calculate_periodicity_confidence(cv, amount_cv, len(group)),
                        # 【审计溯源】原始文件和行号（取第一条记录）
                        'source_file': first_record.get('数据来源', f'cleaned_data/个人/{person}_合并流水.xlsx'),
                        'source_row_index': first_record.get('source_row_index', None)
                    })
    
    # 按金额排序
    periodic_patterns.sort(key=lambda x: -x['total_amount'])
    
    logger.info(f'发现 {len(periodic_patterns)} 个周期性收入模式')
    for p in periodic_patterns[:5]:
        logger.info(f'  {p["person"]} ← {p["counterparty"]}: {p["period_type"]}, 均额{p["avg_amount"]/10000:.2f}万, 共{p["occurrences"]}次')
    
    return periodic_patterns


def _classify_period(avg_interval_days: float) -> str:
    """分类周期类型"""
    if 25 <= avg_interval_days <= 35:
        return '月度'
    elif 6 <= avg_interval_days <= 8:
        return '周度'
    elif 13 <= avg_interval_days <= 16:
        return '双周'
    elif 85 <= avg_interval_days <= 95:
        return '季度'
    elif 360 <= avg_interval_days <= 370:
        return '年度'
    else:
        return f'约{int(avg_interval_days)}天'


def _calculate_periodicity_confidence(interval_cv: float, amount_cv: float, count: int) -> int:
    """计算周期性置信度（0-100）"""
    score = 50
    
    # 间隔规律性加分
    if interval_cv < 0.1:
        score += 25
    elif interval_cv < 0.2:
        score += 15
    elif interval_cv < 0.3:
        score += 5
    
    # 金额一致性加分
    if amount_cv < 0.05:
        score += 25
    elif amount_cv < 0.1:
        score += 15
    elif amount_cv < 0.2:
        score += 5
    
    # 次数加分
    if count >= 12:
        score += 10
    elif count >= 6:
        score += 5
    
    return min(100, score)


# ============================================================
# 突变检测
# ============================================================

def detect_sudden_changes(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    window_days: int = 30,
    threshold_multiplier: float = 3.0
) -> List[Dict]:
    """
    检测资金突变
    
    审计意义：
    - 资金突然激增可能与利益输送或非法收入有关
    - 突然减少可能是资金转移
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员
        window_days: 滑动窗口天数
        threshold_multiplier: 阈值倍数
        
    Returns:
        突变事件列表
    """
    logger.info('开始资金突变检测...')
    
    sudden_changes = []
    
    for person in core_persons:
        df = _normalize_time_series_df(all_transactions.get(person))
        if df is None or df.empty:
            continue
        
        # 按日汇总
        df = df.copy()
        daily = df.groupby(df['date'].dt.date).agg({
            'income': 'sum',
            'expense': 'sum'
        }).reset_index().sort_values('date')
        
        if len(daily) < window_days * 2:
            continue
        
        # 使用历史窗口（shift后）计算均值和标准差，避免当前值泄漏到基线
        min_history = max(5, window_days // 3)
        income_history = daily['income'].shift(1)
        daily['income_ma'] = income_history.rolling(window=window_days, min_periods=min_history).mean()
        daily['income_std'] = income_history.rolling(window=window_days, min_periods=min_history).std()
        
        # 检测突变
        for idx, row in daily.iterrows():
            if pd.isna(row['income_std']) or row['income_std'] == 0:
                continue
            
            z_score = (row['income'] - row['income_ma']) / row['income_std']
            
            if z_score > threshold_multiplier and row['income'] > config.SUDDEN_CHANGE_MIN_AMOUNT:  # 使用配置阈值
                sudden_changes.append({
                    'person': person,
                    'date': row['date'],
                    'amount': row['income'],
                    'z_score': round(z_score, 2),
                    'avg_before': round(row['income_ma'], 2),
                    'change_type': 'income_spike',
                    'risk_level': 'high' if z_score > 5 else 'medium',
                    # 【审计溯源】原始文件（基于日汇总，只能提供人员级别溯源）
                    'source_file': f'cleaned_data/个人/{person}_合并流水.xlsx',
                    'source_row_index': None  # 日汇总数据无法精确到行号
                })
    
    # 按Z值排序
    sudden_changes.sort(key=lambda x: -x['z_score'])
    
    logger.info(f'发现 {len(sudden_changes)} 个资金突变事件')
    return sudden_changes


# ============================================================
# 固定延迟转账检测
# ============================================================

def detect_delayed_transfers(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    delay_range: Tuple[int, int] = (1, 7),
    min_pairs: int = 3
) -> List[Dict]:
    """
    检测固定延迟转账模式
    
    审计意义：
    - A收入后固定N天转给B，可能暗示利益分配协议
    - 这种模式比直接转账更隐蔽
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员
        delay_range: 延迟天数范围
        min_pairs: 最小配对次数
        
    Returns:
        延迟转账模式列表
    """
    logger.info('开始固定延迟转账检测...')
    
    delayed_patterns = []
    
    for person in core_persons:
        df = _normalize_time_series_df(all_transactions.get(person))
        if df is None or df.empty:
            continue
        
        df = df.copy()
        
        # 获取收入和支出
        incomes = df[df['income'] > 10000][['date', 'income', 'counterparty', 'source_row_index', '_strict_source_row', '_strict_transaction_id']].copy()
        expenses = df[df['expense'] > 10000][['date', 'expense', 'counterparty', 'source_row_index', '_strict_source_row', '_strict_transaction_id']].copy()

        if incomes.empty or expenses.empty:
            continue

        delay_pairs = defaultdict(list)
        used_expense_indices = set()
        expense_dates_ns = expenses['date'].astype('int64').to_numpy()

        for _, inc_row in incomes.iterrows():
            inc_date = inc_row['date']
            inc_amount = inc_row['income']
            min_ts = inc_date + pd.Timedelta(days=delay_range[0])
            max_ts = inc_date + pd.Timedelta(days=delay_range[1] + 1)

            left_idx = np.searchsorted(expense_dates_ns, min_ts.value, side='left')
            right_idx = np.searchsorted(expense_dates_ns, max_ts.value, side='left')
            if left_idx >= right_idx:
                continue

            candidates = expenses.iloc[left_idx:right_idx].copy()
            if used_expense_indices:
                candidates = candidates[~candidates.index.isin(used_expense_indices)]
            if candidates.empty:
                continue

            candidates['delay'] = (
                (candidates['date'] - inc_date).dt.total_seconds() // 86400
            ).astype(int)
            candidates = candidates[
                (candidates['delay'] >= delay_range[0]) &
                (candidates['delay'] <= delay_range[1])
            ]
            if candidates.empty:
                continue

            candidates['amount_gap_ratio'] = (
                (candidates['expense'] - inc_amount).abs() /
                np.maximum(candidates['expense'], inc_amount)
            )
            candidates = candidates[candidates['amount_gap_ratio'] < 0.1]
            if candidates.empty:
                continue

            best_match = candidates.sort_values(
                ['amount_gap_ratio', 'delay', '_strict_source_row', '_strict_transaction_id'],
                kind='mergesort',
            ).iloc[0]
            used_expense_indices.add(int(best_match.name))

            delay = int(best_match['delay'])
            key = (inc_row['counterparty'], best_match['counterparty'], delay)
            delay_pairs[key].append({
                'inc_date': inc_date,
                'exp_date': best_match['date'],
                'amount': inc_amount,
                'income_row_index': inc_row.get('source_row_index'),
                'expense_row_index': best_match.get('source_row_index'),
            })

        # 筛选符合条件的模式
        for (inc_cp, exp_cp, delay), pairs in delay_pairs.items():
            if len(pairs) >= min_pairs:
                # 获取首次配对的日期作为参考
                first_pair = min(pairs, key=lambda p: p['inc_date'])
                
                delayed_patterns.append({
                    'person': person,
                    'income_from': str(inc_cp),
                    'income_counterparty': str(inc_cp),
                    'expense_to': str(exp_cp),
                    'expense_counterparty': str(exp_cp),
                    'delay_days': delay,
                    'occurrences': len(pairs),
                    'count': len(pairs),
                    'total_amount': sum(p['amount'] for p in pairs),
                    'avg_amount': sum(p['amount'] for p in pairs) / len(pairs),
                    'risk_level': 'high' if len(pairs) >= 5 else 'medium',
                    # 【审计溯源】原始文件和首次收入日期
                    'source_file': f'cleaned_data/个人/{person}_合并流水.xlsx',
                    'first_income_date': first_pair['inc_date'],
                    'source_row_index': first_pair.get('income_row_index'),
                })
    
    delayed_patterns.sort(key=lambda x: -x['total_amount'])
    
    logger.info(f'发现 {len(delayed_patterns)} 个固定延迟转账模式')
    return delayed_patterns


# ============================================================
# 综合时序分析
# ============================================================

def analyze_time_series(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """
    综合时序分析入口
    """
    logger.info('='*60)
    logger.info('开始时间序列综合分析')
    logger.info('='*60)
    
    results = {
        'periodic_income': [],
        'sudden_changes': [],
        'delayed_transfers': [],
        'summary': {}
    }
    
    # 1. 周期性收入检测
    results['periodic_income'] = detect_periodic_income(
        all_transactions, core_persons
    )
    
    # 2. 突变检测
    results['sudden_changes'] = detect_sudden_changes(
        all_transactions, core_persons
    )
    
    # 3. 固定延迟转账
    results['delayed_transfers'] = detect_delayed_transfers(
        all_transactions, core_persons
    )
    
    # 汇总
    results['summary'] = {
        '周期性收入模式': len(results['periodic_income']),
        '资金突变事件': len(results['sudden_changes']),
        '固定延迟转账': len(results['delayed_transfers'])
    }
    
    logger.info('')
    logger.info('时序分析完成:')
    for k, v in results['summary'].items():
        logger.info(f'  {k}: {v}')
    
    return results


def generate_time_series_report(results: Dict, output_dir: str) -> str:
    """生成时序分析报告（增强版）"""
    import os
    report_path = os.path.join(output_dir, '时序分析报告.txt')
    
    def safe_str(val):
        """安全转换为字符串，处理 nan 值"""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return '(未知)'
        s = str(val)
        return '(未知)' if s == 'nan' or not s else s
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('时间序列分析报告（增强版）\n')
        f.write('='*60 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        
        # 报告说明
        f.write('【报告用途】\n')
        f.write('本报告用于识别资金流动的时序模式，包括：\n')
        f.write('• 周期性收入 - 固定日期固定金额的非工资收入（疑似养廉资金）\n')
        f.write('• 资金突变 - 资金突然激增（可能与特定事件关联）\n')
        f.write('• 固定延迟转账 - 收入后固定N天转出（可能暗示利益分配协议）\n\n')
        
        f.write('【分析逻辑与规则】\n')
        f.write('1. 周期性收入: 同一对手方≥5次，间隔CV<0.3，金额CV<0.1，排除工资\n')
        f.write('2. 资金突变: Z-score>3且金额>10万元视为突变\n')
        f.write('3. 固定延迟: 收入后1-7天内有相近金额支出，出现≥3次\n\n')
        
        f.write('【可能的误判情况】\n')
        f.write('⚠ 理财产品定期到期可能被识别为周期性收入\n')
        f.write('⚠ 房租/定期返利可能产生误报\n')
        f.write('⚠ 工资发放后正常支出可能被标记为固定延迟\n\n')
        
        f.write('【人工复核重点】\n')
        f.write('★ 周期性收入: 核实收入来源是否合法\n')
        f.write('★ 高Z值突变: 核实突变原因，关联时间线事件\n')
        f.write('★ 延迟转账: 核实收入与支出的关联性\n\n')
        
        f.write('='*60 + '\n\n')
        
        # 汇总
        f.write('一、分析汇总\n')
        f.write('-'*40 + '\n')
        for k, v in results['summary'].items():
            f.write(f'{k}: {v}\n')
        f.write('\n')
        
        # 周期性收入
        if results['periodic_income']:
            f.write('二、周期性收入模式（疑似养廉资金）\n')
            f.write('-'*40 + '\n')
            f.write('★ 固定日期固定金额的非工资收入，需重点核查\n')
            f.write(f'共 {len(results["periodic_income"])} 条记录\n\n')
            for i, p in enumerate(results['periodic_income'], 1):
                f.write(f'{i}. [{p["risk_level"].upper()}] {safe_str(p["person"])} ← {safe_str(p["counterparty"])}\n')
                f.write(f'   周期: {p["period_type"]} | 均额: {p["avg_amount"]/10000:.2f}万 | 次数: {p["occurrences"]}\n')
                f.write(f'   时间范围: {p["date_range"]} | 置信度: {p["confidence"]}分\n')
            f.write('\n')
        
        # 突变事件
        if results['sudden_changes']:
            f.write('三、资金突变事件\n')
            f.write('-'*40 + '\n')
            f.write('★ 资金突然激增，可能与特定事件关联\n')
            f.write(f'共 {len(results["sudden_changes"])} 条记录\n\n')
            for i, s in enumerate(results['sudden_changes'], 1):
                f.write(f'{i}. [{s["risk_level"].upper()}] {safe_str(s["person"])} - {s["date"]}\n')
                f.write(f'   金额: {s["amount"]/10000:.2f}万 | Z值: {s["z_score"]} | 均值: {s["avg_before"]/10000:.2f}万\n')
            f.write('\n')
        
        # 延迟转账
        if results['delayed_transfers']:
            f.write('四、固定延迟转账模式\n')
            f.write('-'*40 + '\n')
            f.write('★ 收入后固定天数转出，可能暗示利益分配协议\n')
            f.write(f'共 {len(results["delayed_transfers"])} 条记录\n\n')
            for i, d in enumerate(results['delayed_transfers'], 1):
                income_from = safe_str(d.get("income_from", d.get("income_counterparty", "")))
                expense_to = safe_str(d.get("expense_to", d.get("expense_counterparty", "")))
                f.write(f'{i}. [{d["risk_level"].upper()}] {safe_str(d["person"])}: {income_from} → {expense_to}\n')
                f.write(f'   延迟: {d["delay_days"]}天 | 次数: {d["occurrences"]} | 总额: {d["total_amount"]/10000:.2f}万\n')
    
    logger.info(f'时序分析报告已生成: {report_path}')
    return report_path
