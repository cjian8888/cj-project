#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
借贷行为分析模块
检测双向资金往来关系（借入+还款模式）、网贷平台往来等

重构说明 (2026-01-11):
- 使用 counterparty_utils 统一对手方排除逻辑
- 使用 config.py 中的阈值替代硬编码
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
from collections import defaultdict
import config
import utils
from counterparty_utils import (
    should_exclude_counterparty,
    ExclusionContext
)

logger = utils.setup_logger(__name__)


def analyze_loan_behaviors(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """
    分析借贷行为（增强版）
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        
    Returns:
        借贷行为分析结果
    """
    logger.info('='*60)
    logger.info('开始借贷行为分析（增强版）')
    logger.info('='*60)
    
    results = {
        'bidirectional_flows': [],      # 双向资金往来（疑似借贷）
        'online_loan_platforms': [],    # 网贷平台往来
        'regular_repayments': [],       # 规律性还款
        'loan_pairs': [],               # 借贷配对（新增）
        'no_repayment_loans': [],       # 无还款借贷（新增）
        'abnormal_interest': [],        # 异常利息（新增）
        'loan_network': {},             # 借贷网络（新增）
        'summary': {}
    }
    
    # 1. 检测双向资金往来
    logger.info('【阶段1】检测双向资金往来')
    results['bidirectional_flows'] = _detect_bidirectional_flows(
        all_transactions, core_persons
    )
    
    # 2. 检测网贷平台往来
    logger.info('【阶段2】检测网贷平台往来')
    results['online_loan_platforms'] = _detect_online_loans(
        all_transactions, core_persons
    )
    
    # 3. 检测规律性还款模式
    logger.info('【阶段3】检测规律性还款模式')
    results['regular_repayments'] = _detect_regular_repayments(
        all_transactions, core_persons
    )
    
    # 4. 借贷配对分析（新增）
    logger.info('【阶段4】借贷配对分析')
    results['loan_pairs'] = _detect_loan_pairs(
        all_transactions, core_persons
    )
    
    # 5. 无还款借贷检测（新增）
    logger.info('【阶段5】无还款借贷检测')
    results['no_repayment_loans'] = _detect_no_repayment_loans(
        all_transactions, core_persons
    )
    
    # 6. 异常利息检测（新增）
    logger.info('【阶段6】异常利息检测')
    results['abnormal_interest'] = _detect_abnormal_interest(
        results['loan_pairs']
    )
    
    # 7. 借贷网络分析（新增）
    logger.info('【阶段7】借贷网络分析')
    results['loan_network'] = _analyze_loan_network(
        results['loan_pairs'], core_persons
    )
    
    # 生成汇总
    results['summary'] = {
        '双向往来关系数': len(results['bidirectional_flows']),
        '网贷平台交易数': len(results['online_loan_platforms']),
        '规律还款模式数': len(results['regular_repayments']),
        '借贷配对数': len(results['loan_pairs']),
        '无还款借贷数': len(results['no_repayment_loans']),
        '异常利息数': len(results['abnormal_interest']),
        '借贷网络节点数': len(results['loan_network'].get('nodes', []))
    }
    
    logger.info('')
    logger.info(f'借贷行为分析完成:')
    for k, v in results['summary'].items():
        logger.info(f'  {k}: {v}')
    
    return results


# 注意: _should_exclude_counterparty_for_bidirectional 已迁移至 counterparty_utils.py
# 使用 should_exclude_counterparty(cp, person, core_persons, ExclusionContext.BIDIRECTIONAL)


# 注意: _should_exclude_counterparty_for_loan_pattern 已迁移至 counterparty_utils.py
# 使用 should_exclude_counterparty(cp, person, core_persons, ExclusionContext.LOAN_PATTERN)


def _calculate_loan_pattern(ratio: float) -> Tuple[bool, str]:
    """
    计算借贷模式
    
    Args:
        ratio: 支出/收入比例
        
    Returns:
        (是否为借贷模式, 借贷类型)
    """
    ratio_min = config.LOAN_PAIR_RATIO_MIN
    ratio_max = config.LOAN_PAIR_RATIO_MAX
    
    if 0.8 <= ratio <= ratio_max:
        # 还款金额接近借入金额，典型借贷
        return True, '疑似借贷（还款≈借入）'
    elif ratio > ratio_max:
        # 还款远多于借入，可能是分期还款+利息
        return True, '疑似借贷（分期还款）'
    elif ratio < 0.8 and ratio > 0:
        # 借入多于还款，可能是正在还款中
        return True, '疑似借贷（未还清）'
    
    return False, 'unknown'


def _detect_bidirectional_flows(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_amount: float = config.LOAN_MIN_AMOUNT,
    min_transactions: int = 2
) -> List[Dict]:
    """
    检测双向资金往来
    
    如果与某对手方既有收入又有支出，且金额较大，可能是借贷关系
    """
    bidirectional = []
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            # 按对手方统计收支
            counterparty_stats = defaultdict(lambda: {
                'income_count': 0, 'income_total': 0, 'income_records': [],
                'expense_count': 0, 'expense_total': 0, 'expense_records': []
            })
            
            for _, row in df.iterrows():
                cp = str(row.get('counterparty', ''))
                if not cp or cp == 'nan' or len(cp) < 2:
                    continue
                
                # 排除对手方（使用统一的排除逻辑）
                if should_exclude_counterparty(cp, person, core_persons, ExclusionContext.BIDIRECTIONAL):
                    continue
                
                if row.get('income', 0) >= min_amount:
                    counterparty_stats[cp]['income_count'] += 1
                    counterparty_stats[cp]['income_total'] += row['income']
                    counterparty_stats[cp]['income_records'].append({
                        'date': row['date'],
                        'amount': row['income'],
                        'description': row.get('description', ''),
                        # 【审计溯源】原始文件和行号
                        'source_file': row.get('数据来源', ''),
                        'source_row_index': row.get('source_row_index', None)
                    })
                
                if row.get('expense', 0) >= min_amount:
                    counterparty_stats[cp]['expense_count'] += 1
                    counterparty_stats[cp]['expense_total'] += row['expense']
                    counterparty_stats[cp]['expense_records'].append({
                        'date': row['date'],
                        'amount': row['expense'],
                        'description': row.get('description', ''),
                        # 【审计溯源】原始文件和行号
                        'source_file': row.get('数据来源', ''),
                        'source_row_index': row.get('source_row_index', None)
                    })
            
            # 筛选双向往来
            for cp, stats in counterparty_stats.items():
                if stats['income_count'] >= min_transactions and stats['expense_count'] >= min_transactions:
                    # 排除对手方（使用统一的排除逻辑）
                    if should_exclude_counterparty(cp, person, core_persons, ExclusionContext.LOAN_PATTERN):
                        continue
                    
                    # 计算借贷特征
                    ratio = stats['expense_total'] / stats['income_total'] if stats['income_total'] > 0 else 0
                    
                    # 判断是否为借贷模式
                    is_loan_pattern, loan_type = _calculate_loan_pattern(ratio)
                    
                    if is_loan_pattern:
                        # 取第一条收入记录的溯源信息
                        first_income_record = stats['income_records'][0] if stats['income_records'] else {}
                        
                        bidirectional.append({
                            'person': person,
                            'counterparty': cp,
                            'income_count': stats['income_count'],
                            'income_total': stats['income_total'],
                            'expense_count': stats['expense_count'],
                            'expense_total': stats['expense_total'],
                            'ratio': ratio,
                            'loan_type': loan_type,
                            'first_income_date': min(r['date'] for r in stats['income_records']),
                            'last_expense_date': max(r['date'] for r in stats['expense_records']),
                            'risk_level': 'high' if stats['income_total'] >= config.LOAN_BIDIRECTIONAL_HIGH_RISK else 'medium',
                            # 【溯源铁律】原始文件和行号（取第一条收入记录）
                            'source_file': first_income_record.get('source_file', f'cleaned_data/个人/{person}_合并流水.xlsx'),
                            'source_row_index': first_income_record.get('source_row_index', None)
                        })
    
    # 按金额排序
    bidirectional.sort(key=lambda x: -x['income_total'])
    
    logger.info(f'  发现 {len(bidirectional)} 个双向资金往来关系')
    return bidirectional


def _detect_online_loans(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> List[Dict]:
    """检测网贷平台往来"""
    
    # 常见网贷平台关键词
    ONLINE_LOAN_KEYWORDS = [
        # 消费金融
        '花呗', '借呗', '白条', '金条', '微粒贷', '有钱花',
        '马上消费', '招联金融', '捷信', '即科金融', '中邮消费',
        # 网贷平台
        '拍拍贷', '人人贷', '陆金所', '宜人贷', '你我贷',
        '360借条', '分期乐', '趣店', '乐信',
        # 银行消费贷
        '消费贷', '信用贷', '快贷', 'e贷',
        # 汽车金融
        '汽车金融', '车贷', '通用金融', '宝马金融', '大众金融'
    ]
    
    online_loans = []
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty:
                continue
            
            for _, row in df.iterrows():
                cp = str(row.get('counterparty', ''))
                desc = str(row.get('description', ''))
                
                if utils.contains_keywords(cp, ONLINE_LOAN_KEYWORDS) or \
                   utils.contains_keywords(desc, ONLINE_LOAN_KEYWORDS):
                    
                    amount = max(row.get('income', 0), row.get('expense', 0))
                    direction = 'income' if row.get('income', 0) > 0 else 'expense'
                    
                    # 识别平台名称
                    platform = '未知平台'
                    for kw in ONLINE_LOAN_KEYWORDS:
                        if kw in cp or kw in desc:
                            platform = kw
                            break
                    
                    online_loans.append({
                        'person': person,
                        'platform': platform,
                        'counterparty': cp,
                        'date': row['date'],
                        'amount': amount,
                        'direction': direction,
                        'description': desc,
                        'risk_level': 'high' if amount >= config.LOAN_HIGH_RISK_MIN else 'medium',
                        # 【审计溯源】原始文件和行号
                        'source_file': row.get('数据来源', f'cleaned_data/个人/{person}_合并流水.xlsx'),
                        'source_row_index': row.get('source_row_index', None)
                    })
    
    # 按日期排序
    online_loans.sort(key=lambda x: x['date'])
    
    logger.info(f'  发现 {len(online_loans)} 笔网贷平台交易')
    return online_loans


def _detect_regular_repayments(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_occurrences: int = 3
) -> List[Dict]:
    """
    检测规律性还款模式
    
    寻找每月固定日期向同一对手方支出的记录（非工资性质）
    """
    regular_repayments = []
    
    # 还款相关关键词
    REPAYMENT_KEYWORDS = [
        '还款', '贷款', '分期', '月供', '归还', '扣款',
        '金融', '消费贷', '信用贷', '车贷', '房贷'
    ]
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            # 只看支出
            expense_df = df[df['expense'] > 0].copy()
            if expense_df.empty:
                continue
            
            expense_df['day'] = expense_df['date'].dt.day
            expense_df['month_key'] = expense_df['date'].apply(utils.get_month_key)
            
            # 按对手方+日期分组
            for cp in expense_df['counterparty'].unique():
                cp_str = str(cp)
                if not cp_str or cp_str == 'nan':
                    continue
                
                cp_df = expense_df[expense_df['counterparty'] == cp]
                
                if len(cp_df) < min_occurrences:
                    continue
                
                # 检查是否有固定日期
                day_counts = cp_df['day'].value_counts()
                most_common_day = day_counts.index[0]
                day_count = day_counts.iloc[0]
                
                if day_count >= min_occurrences:
                    # 检查金额稳定性
                    amounts = cp_df[cp_df['day'] == most_common_day]['expense'].tolist()
                    if len(amounts) >= min_occurrences:
                        mean_amt = sum(amounts) / len(amounts)
                        cv = (sum((x - mean_amt)**2 for x in amounts) / len(amounts))**0.5 / mean_amt if mean_amt > 0 else 999
                        
                        if cv < 0.3:  # 金额稳定
                            # 检查是否有还款特征
                            has_repayment_feature = utils.contains_keywords(
                                cp_str, REPAYMENT_KEYWORDS
                            )
                            
                            # 获取第一条记录的溯源信息
                            first_record = cp_df[cp_df['day'] == most_common_day].iloc[0]
                            
                            regular_repayments.append({
                                'person': person,
                                'counterparty': cp_str,
                                'day_of_month': most_common_day,
                                'occurrences': day_count,
                                'avg_amount': mean_amt,
                                'total_amount': sum(amounts),
                                'cv': cv,
                                'is_likely_loan': has_repayment_feature,
                                'date_range': (
                                    cp_df['date'].min(),
                                    cp_df['date'].max()
                                ),
                                'risk_level': 'high' if has_repayment_feature else 'medium',
                                # 【审计溯源】原始文件和行号（取第一条记录）
                                'source_file': first_record.get('数据来源', f'cleaned_data/个人/{person}_合并流水.xlsx'),
                                'source_row_index': first_record.get('source_row_index', None)
                            })
    
    # 按金额排序
    regular_repayments.sort(key=lambda x: -x['total_amount'])
    
    logger.info(f'  发现 {len(regular_repayments)} 个规律还款模式')
    return regular_repayments


# 注意: _should_exclude_counterparty_for_loan_pairs 已迁移至 counterparty_utils.py
# 使用 should_exclude_counterparty(cp, person, core_persons, ExclusionContext.LOAN_PAIRS)


def _calculate_loan_risk_level(income_amt: float, annual_rate: float) -> Tuple[str, List[str]]:
    """
    计算借贷风险等级
    
    Args:
        income_amt: 借入金额
        annual_rate: 年化利率
        
    Returns:
        (风险等级, 风险原因列表)
    """
    risk_level = 'medium'
    risk_reason = []
    
    usury_rate = config.LOAN_USURY_RATE
    interest_free_min = config.LOAN_INTEREST_FREE_MIN
    large_threshold = config.LOAN_LARGE_NO_REPAY_MIN
    
    if annual_rate > usury_rate:
        risk_level = 'high'
        risk_reason.append(f'年化利率{annual_rate:.1f}%超过{usury_rate}%红线')
    elif annual_rate < 0.1 and income_amt >= interest_free_min:
        risk_level = 'high'
        risk_reason.append(f'大额借贷({utils.format_currency(income_amt)})无息或低息')
    elif income_amt >= large_threshold:
        risk_level = 'high'
        risk_reason.append(f'借贷金额超过{large_threshold/10000:.0f}万元')
    
    return risk_level, risk_reason


def _create_loan_pair_entry(person: str, cp_str: str, income_row, expense_row,
                           days_diff: int, income_amt: float, expense_amt: float) -> Dict:
    """
    创建借贷配对条目
    
    Args:
        person: 人员名称
        cp_str: 对手方
        income_row: 收入记录
        expense_row: 支出记录
        days_diff: 天数差
        income_amt: 收入金额
        expense_amt: 支出金额
        
    Returns:
        借贷配对条目
    """
    # 计算隐含利率
    interest_rate = ((expense_amt - income_amt) / income_amt) * 100 if income_amt > 0 else 0
    annual_rate = (interest_rate / days_diff * 365) if days_diff > 0 else 0
    
    # 判断风险等级
    risk_level, risk_reason = _calculate_loan_risk_level(income_amt, annual_rate)
    
    return {
        'person': person,
        'counterparty': cp_str,
        'loan_date': income_row['date'],
        'repay_date': expense_row['date'],
        'loan_amount': income_amt,
        'repay_amount': expense_amt,
        'days': days_diff,
        'interest_rate': interest_rate,
        'annual_rate': annual_rate,
        'risk_level': risk_level,
        'risk_reason': '; '.join(risk_reason) if risk_reason else '正常',
        'loan_desc': income_row.get('description', ''),
        'repay_desc': expense_row.get('description', ''),
        # 【审计溯源】借入记录的原始文件和行号
        'loan_source_file': income_row.get('数据来源', f'cleaned_data/个人/{person}_合并流水.xlsx'),
        'loan_source_row': income_row.get('source_row_index', None),
        # 【审计溯源】还款记录的原始文件和行号
        'repay_source_file': expense_row.get('数据来源', ''),
        'repay_source_row': expense_row.get('source_row_index', None)
    }


def _detect_loan_pairs(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    time_window_days: int = None,
    amount_tolerance: float = None
) -> List[Dict]:
    """
    借贷配对分析 - 智能匹配借入和还款记录
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        time_window_days: 时间窗口（天），默认使用配置
        amount_tolerance: 金额容差，默认使用配置
    
    Returns:
        借贷配对列表
    """
    # 使用配置文件中的阈值
    if time_window_days is None:
        time_window_days = config.LOAN_TIME_WINDOW_DAYS
    if amount_tolerance is None:
        amount_tolerance = config.LOAN_AMOUNT_TOLERANCE
    
    ratio_min = config.LOAN_PAIR_RATIO_MIN
    ratio_max = config.LOAN_PAIR_RATIO_MAX
    
    loan_pairs = []
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            # 按对手方分组
            for cp in df['counterparty'].unique():
                cp_str = str(cp)
                if not cp_str or cp_str == 'nan' or len(cp_str) < 2:
                    continue
                
                # 排除对手方（使用统一的排除逻辑）
                if should_exclude_counterparty(cp_str, person, core_persons, ExclusionContext.LOAN_PAIRS):
                    continue
                
                cp_df = df[df['counterparty'] == cp].copy()
                
                # 分离收入和支出
                incomes = cp_df[cp_df['income'] > config.LOAN_MIN_MATCH_AMOUNT].copy()
                expenses = cp_df[cp_df['expense'] > config.LOAN_MIN_MATCH_AMOUNT].copy()
                
                if incomes.empty or expenses.empty:
                    continue
                
                # 尝试配对
                for _, income_row in incomes.iterrows():
                    income_date = income_row['date']
                    income_amt = income_row['income']
                    
                    # 在时间窗口内查找可能的还款
                    for _, expense_row in expenses.iterrows():
                        expense_date = expense_row['date']
                        expense_amt = expense_row['expense']
                        
                        # 还款应在借入之后
                        if expense_date <= income_date:
                            continue
                        
                        # 时间窗口检查
                        days_diff = (expense_date - income_date).days
                        if days_diff > time_window_days:
                            continue
                        
                        # 金额匹配检查（允许利息）
                        ratio = expense_amt / income_amt if income_amt > 0 else 0
                        
                        # 只接受还款≥借入的配对（真正的借贷）
                        if ratio_min <= ratio <= ratio_max:
                            loan_pairs.append(_create_loan_pair_entry(
                                person, cp_str, income_row, expense_row,
                                days_diff, income_amt, expense_amt
                            ))
    
    # 按借贷金额排序
    loan_pairs.sort(key=lambda x: -x['loan_amount'])
    
    logger.info(f'  发现 {len(loan_pairs)} 个借贷配对')
    return loan_pairs


# 注意: _should_exclude_counterparty_for_no_repayment 已迁移至 counterparty_utils.py
# 使用 should_exclude_counterparty(cp, person, core_persons, ExclusionContext.NO_REPAYMENT)


def _create_no_repayment_entry(person: str, cp_str: str, income_row,
                              days_since: int, total_repaid: float,
                              income_amt: float) -> Dict:
    """
    创建无还款借贷条目
    
    Args:
        person: 人员名称
        cp_str: 对手方
        income_row: 收入记录
        days_since: 距今天数
        total_repaid: 已还款金额
        income_amt: 收入金额
        
    Returns:
        无还款借贷条目
    """
    repay_ratio = total_repaid / income_amt if income_amt > 0 else 0
    risk_level = 'high' if income_amt >= 50000 else 'medium'
    
    return {
        'person': person,
        'counterparty': cp_str,
        'income_date': income_row['date'],
        'income_amount': income_amt,
        'days_since': days_since,
        'total_repaid': total_repaid,
        'repay_ratio': repay_ratio,
        'risk_level': risk_level,
        'description': income_row.get('description', ''),
        'risk_reason': f'{days_since}天未还款，还款比例仅{repay_ratio*100:.1f}%',
        # 【审计溯源】原始文件和行号
        'source_file': income_row.get('数据来源', f'cleaned_data/个人/{person}_合并流水.xlsx'),
        'source_row_index': income_row.get('source_row_index', None)
    }


def _detect_no_repayment_loans(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_amount: float = config.INCOME_LARGE_PERSONAL_MIN,
    min_days: int = 180
) -> List[Dict]:
    """
    无还款借贷检测 - 发现可能的利益输送
    
    检测大额收入但长期无对应还款的情况
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        min_amount: 最小金额（元）
        min_days: 最小天数（天）
    
    Returns:
        无还款借贷列表
    """
    no_repayment = []
    current_date = datetime.now()
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            # 按对手方统计
            for cp in df['counterparty'].unique():
                cp_str = str(cp)
                if not cp_str or cp_str == 'nan' or len(cp_str) < 2:
                    continue
                
                # 排除对手方（使用统一的排除逻辑）
                if should_exclude_counterparty(cp_str, person, core_persons, ExclusionContext.NO_REPAYMENT):
                    continue
                
                cp_df = df[df['counterparty'] == cp].copy()
                
                # 查找大额收入
                large_incomes = cp_df[cp_df['income'] >= min_amount].copy()
                
                if large_incomes.empty:
                    continue
                
                # 检查每笔大额收入
                for _, income_row in large_incomes.iterrows():
                    income_date = income_row['date']
                    income_amt = income_row['income']
                    
                    # 计算距今天数
                    days_since = (current_date - income_date).days
                    
                    if days_since < min_days:
                        continue
                    
                    # 查找该日期之后的还款
                    future_expenses = cp_df[
                        (cp_df['date'] > income_date) &
                        (cp_df['expense'] > 0)
                    ]
                    
                    total_repaid = future_expenses['expense'].sum()
                    repay_ratio = total_repaid / income_amt if income_amt > 0 else 0
                    
                    # 如果还款比例低于50%，视为无还款
                    if repay_ratio < 0.5:
                        no_repayment.append(_create_no_repayment_entry(
                            person, cp_str, income_row,
                            days_since, total_repaid, income_amt
                        ))
    
    # 按金额排序
    no_repayment.sort(key=lambda x: -x['income_amount'])
    
    logger.info(f'  发现 {len(no_repayment)} 个无还款借贷')
    return no_repayment


def _detect_abnormal_interest(
    loan_pairs: List[Dict],
    normal_rate_range: Tuple[float, float] = (4.0, 24.0)
) -> List[Dict]:
    """
    异常利息检测 - 识别高利贷或零息贷
    
    Args:
        loan_pairs: 借贷配对列表
        normal_rate_range: 正常年化利率范围（%）
    
    Returns:
        异常利息列表
    """
    abnormal = []
    
    for pair in loan_pairs:
        annual_rate = pair.get('annual_rate', 0)
        loan_amount = pair.get('loan_amount', 0)
        
        is_abnormal = False
        abnormal_type = ''
        
        # 高利贷检测（年化超过24%）
        if annual_rate > normal_rate_range[1]:
            is_abnormal = True
            if annual_rate > 36:
                abnormal_type = '超高利贷（超过36%红线）'
            else:
                abnormal_type = '高利贷（超过24%）'
        
        # 零息或低息大额借贷检测
        elif annual_rate < normal_rate_range[0] and loan_amount >= 50000:
            is_abnormal = True
            if annual_rate < 0.1:
                abnormal_type = '疑似无息借贷（可能利益输送）'
            else:
                abnormal_type = f'低息借贷（年化{annual_rate:.1f}%）'
        
        if is_abnormal:
            abnormal.append({
                **pair,
                'abnormal_type': abnormal_type
            })
    
    logger.info(f'  发现 {len(abnormal)} 个异常利息')
    return abnormal


def _analyze_loan_network(
    loan_pairs: List[Dict],
    core_persons: List[str]
) -> Dict:
    """
    借贷网络分析 - 构建借贷关系图谱
    
    Args:
        loan_pairs: 借贷配对列表
        core_persons: 核心人员列表
    
    Returns:
        借贷网络数据
    """
    network = {
        'nodes': [],
        'edges': [],
        'chains': [],
        'hubs': []
    }
    
    # 构建节点和边
    node_set = set()
    edge_stats = defaultdict(lambda: {'count': 0, 'total_amount': 0, 'pairs': []})
    
    for pair in loan_pairs:
        person = pair['person']
        counterparty = pair['counterparty']
        
        node_set.add(person)
        node_set.add(counterparty)
        
        edge_key = f"{person}→{counterparty}"
        edge_stats[edge_key]['count'] += 1
        edge_stats[edge_key]['total_amount'] += pair['loan_amount']
        edge_stats[edge_key]['pairs'].append(pair)
    
    # 生成节点列表
    for node in node_set:
        is_core = node in core_persons
        network['nodes'].append({
            'name': node,
            'is_core_person': is_core,
            'type': 'core' if is_core else 'related'
        })
    
    # 生成边列表
    for edge_key, stats in edge_stats.items():
        parts = edge_key.split('→')
        network['edges'].append({
            'from': parts[0],
            'to': parts[1],
            'count': stats['count'],
            'total_amount': stats['total_amount'],
            'avg_amount': stats['total_amount'] / stats['count']
        })
    
    # 识别借贷中心（hub）- 与多人有借贷关系的节点
    person_connections = defaultdict(set)
    for edge in network['edges']:
        person_connections[edge['from']].add(edge['to'])
        person_connections[edge['to']].add(edge['from'])
    
    for person, connections in person_connections.items():
        if len(connections) >= 3:
            network['hubs'].append({
                'person': person,
                'connection_count': len(connections),
                'connections': list(connections)
            })
    
    # 按连接数排序
    network['hubs'].sort(key=lambda x: -x['connection_count'])
    
    logger.info(f'  借贷网络: {len(network["nodes"])}个节点, {len(network["edges"])}条边, {len(network["hubs"])}个中心节点')
    return network


def _write_report_header(f) -> None:
    """写入报告头部（含用途说明、逻辑依据、误判提示、复核重点）"""
    f.write('借贷行为分析报告（增强版）\n')
    f.write('='*60 + '\n')
    f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
    
    # 报告说明
    f.write('【报告用途】\n')
    f.write('本报告用于识别核心人员之间的借贷关系，包括：双向资金往来、规律还款、\n')
    f.write('无还款大额收入（疑似利益输送）、网贷平台交易、异常利息等。\n\n')
    
    f.write('【分析逻辑与规则】\n')
    f.write('1. 双向往来检测：与同一对手方既有收入又有支出（≥5万元），支出/收入比0.7-1.3\n')
    f.write('2. 无还款借贷：大额收入(≥5万)后180天内未还款或还款<50%\n')
    f.write('3. 规律还款：每月固定日期向同一对手方支出，金额变异系数CV<0.3\n')
    f.write('4. 借贷配对：收入后365天内有金额相近的支出，计算隐含年化利率\n')
    f.write('5. 异常利息：年化利率>24%为高利贷，<4%且金额>5万为疑似无息借贷\n\n')
    
    f.write('【可能的误判情况】\n')
    f.write('⚠ 理财申赎可能被误识别为借贷（已部分过滤但不完全）\n')
    f.write('⚠ 家庭成员间的日常资金往来可能被标记为借贷\n')
    f.write('⚠ 企业代发工资、报销等正常业务可能产生"规律还款"误报\n')
    f.write('⚠ "现金"作为对手方的借贷分析无实际意义\n\n')
    
    f.write('【人工复核重点】\n')
    f.write('★ 无还款借贷：核实收入性质，是否为借款还是其他收入\n')
    f.write('★ 双向往来：核实是否为真实借贷还是理财/代购等\n')
    f.write('★ 异常利息：重点关注无息大额借贷，可能为利益输送\n\n')
    
    f.write('='*60 + '\n\n')


def _write_summary_section(f, summary: Dict) -> None:
    """写入汇总统计部分"""
    f.write('一、汇总统计\n')
    f.write('-'*40 + '\n')
    for k, v in summary.items():
        f.write(f'{k}: {v}\n')
    f.write('\n')


def _write_bidirectional_flows_section(f, flows: List[Dict]) -> None:
    """写入双向资金往来部分"""
    f.write('二、双向资金往来（疑似借贷）\n')
    f.write('-'*40 + '\n')
    f.write(f'共 {len(flows)} 条记录\n\n')
    for i, flow in enumerate(flows, 1):
        f.write(f"{i}. 【{flow['risk_level'].upper()}】{flow['person']} ↔ {flow['counterparty']}\n")
        f.write(f"   收入: {flow['income_count']}笔 {utils.format_currency(flow['income_total'])}\n")
        f.write(f"   支出: {flow['expense_count']}笔 {utils.format_currency(flow['expense_total'])}\n")
        f.write(f"   判断: {flow['loan_type']}\n")
    f.write('\n')


def _write_loan_pairs_section(f, pairs: List[Dict]) -> None:
    """写入借贷配对分析部分"""
    f.write('三、借贷配对分析（新增）\n')
    f.write('-'*40 + '\n')
    f.write('智能匹配借入和还款记录，计算隐含利率\n\n')
    f.write(f'共 {len(pairs)} 条记录\n\n')
    for i, pair in enumerate(pairs, 1):
        f.write(f"{i}. 【{pair['risk_level'].upper()}】{pair['person']} ↔ {pair['counterparty']}\n")
        f.write(f"   借入: {pair['loan_date'].strftime('%Y-%m-%d')} {utils.format_currency(pair['loan_amount'])}\n")
        f.write(f"   还款: {pair['repay_date'].strftime('%Y-%m-%d')} {utils.format_currency(pair['repay_amount'])}\n")
        f.write(f"   周期: {pair['days']}天\n")
        f.write(f"   利率: {pair['interest_rate']:.2f}% (年化{pair['annual_rate']:.1f}%)\n")
        f.write(f"   风险: {pair['risk_reason']}\n")
    f.write('\n')


def _write_no_repayment_loans_section(f, loans: List[Dict]) -> None:
    """写入无还款借贷检测部分"""
    f.write('四、无还款借贷检测（疑似利益输送）\n')
    f.write('-'*40 + '\n')
    f.write('大额收入但长期无对应还款的情况\n\n')
    f.write(f'共 {len(loans)} 条记录\n\n')
    for i, loan in enumerate(loans, 1):
        f.write(f"{i}. 【{loan['risk_level'].upper()}】{loan['person']} ← {loan['counterparty']}\n")
        f.write(f"   收入: {loan['income_date'].strftime('%Y-%m-%d')} {utils.format_currency(loan['income_amount'])}\n")
        f.write(f"   距今: {loan['days_since']}天\n")
        f.write(f"   已还: {utils.format_currency(loan['total_repaid'])} ({loan['repay_ratio']*100:.1f}%)\n")
        f.write(f"   风险: {loan['risk_reason']}\n")
    f.write('\n')


def _write_abnormal_interest_section(f, abnormal: List[Dict]) -> None:
    """写入异常利息检测部分"""
    f.write('五、异常利息检测\n')
    f.write('-'*40 + '\n')
    f.write('识别高利贷（>24%）和疑似无息借贷（<4%）\n\n')
    f.write(f'共 {len(abnormal)} 条记录\n\n')
    for i, item in enumerate(abnormal, 1):
        f.write(f"{i}. 【{item['risk_level'].upper()}】{item['person']} ↔ {item['counterparty']}\n")
        f.write(f"   金额: {utils.format_currency(item['loan_amount'])}\n")
        f.write(f"   年化利率: {item['annual_rate']:.1f}%\n")
        f.write(f"   异常类型: {item['abnormal_type']}\n")
    f.write('\n')


def _write_loan_network_section(f, network: Dict) -> None:
    """写入借贷网络分析部分"""
    f.write('六、借贷网络分析\n')
    f.write('-'*40 + '\n')
    f.write(f"网络规模: {len(network['nodes'])}个节点, {len(network['edges'])}条借贷关系\n\n")
    
    if network['hubs']:
        f.write('借贷中心节点（与多人有借贷关系）:\n')
        for i, hub in enumerate(network['hubs'], 1):
            f.write(f"{i}. {hub['person']}: 与{hub['connection_count']}人有借贷往来\n")
            f.write(f"   关联人: {', '.join(hub['connections'])}\n")
    f.write('\n')


def _write_online_loans_section(f, online_loans: List[Dict]) -> None:
    """写入网贷平台往来记录部分"""
    f.write('七、网贷平台往来记录\n')
    f.write('-'*40 + '\n')
    
    # 按平台汇总
    platform_stats = defaultdict(lambda: {'count': 0, 'total': 0})
    for loan in online_loans:
        platform_stats[loan['platform']]['count'] += 1
        platform_stats[loan['platform']]['total'] += loan['amount']
    
    for platform, stats in sorted(platform_stats.items(), key=lambda x: -x[1]['total']):
        f.write(f"  {platform}: {stats['count']}笔, 合计{utils.format_currency(stats['total'])}\n")
    f.write('\n')


def _write_regular_repayments_section(f, repayments: List[Dict]) -> None:
    """写入规律性还款模式部分"""
    f.write('八、规律性还款模式\n')
    f.write('-'*40 + '\n')
    f.write(f'共 {len(repayments)} 条记录\n\n')
    for i, rep in enumerate(repayments, 1):
        f.write(f"{i}. {rep['person']} → {rep['counterparty']}\n")
        f.write(f"   每月{rep['day_of_month']}日, 均额{utils.format_currency(rep['avg_amount'])}, "
               f"共{rep['occurrences']}次, 合计{utils.format_currency(rep['total_amount'])}\n")
    f.write('\n')


def generate_loan_report(results: Dict, output_dir: str) -> str:
    """生成借贷行为分析报告（增强版）"""
    import os
    report_path = os.path.join(output_dir, '借贷行为分析报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        _write_report_header(f)
        
        # 汇总
        _write_summary_section(f, results['summary'])
        
        # 双向往来
        if results['bidirectional_flows']:
            _write_bidirectional_flows_section(f, results['bidirectional_flows'])
        
        # 借贷配对（新增）
        if results.get('loan_pairs'):
            _write_loan_pairs_section(f, results['loan_pairs'])
        
        # 无还款借贷（新增）
        if results.get('no_repayment_loans'):
            _write_no_repayment_loans_section(f, results['no_repayment_loans'])
        
        # 异常利息（新增）
        if results.get('abnormal_interest'):
            _write_abnormal_interest_section(f, results['abnormal_interest'])
        
        # 借贷网络（新增）
        if results.get('loan_network') and results['loan_network'].get('hubs'):
            _write_loan_network_section(f, results['loan_network'])
        
        # 网贷平台
        if results['online_loan_platforms']:
            _write_online_loans_section(f, results['online_loan_platforms'])
        
        # 规律还款
        if results['regular_repayments']:
            _write_regular_repayments_section(f, results['regular_repayments'])
    
    logger.info(f'借贷行为分析报告已生成: {report_path}')
    return report_path
