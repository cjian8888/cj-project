#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
疑点碰撞检测模块 - 资金穿透与关联排查系统
实现核心侦查算法,发现异常交易模式
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict
import config
import utils

logger = utils.setup_logger(__name__)


def detect_direct_transfer(all_transactions: Dict[str, pd.DataFrame],
                          core_persons: List[str],
                          involved_companies: List[str]) -> List[Dict]:
    """
    检测核心人员与涉案公司之间的直接转账
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员名单
        involved_companies: 涉案公司名单
        
    Returns:
        直接转账记录列表
    """
    logger.info('正在检测直接资金往来...')
    
    direct_transfers = []
    
    # 遍历每个人员的交易
    for person in core_persons:
        person_key = None
        for key in all_transactions.keys():
            if person in key:
                person_key = key
                break
        
        if not person_key:
            continue
        
        df = all_transactions[person_key]
        
        # 检查对手方是否为涉案公司
        for _, row in df.iterrows():
            counterparty = row['counterparty']
            
            for company in involved_companies:
                if company in counterparty:
                    transfer = {
                        'person': person,
                        'company': company,
                        'date': row['date'],
                        'description': row['description'],
                        'amount': max(row['income'], row['expense']),
                        'direction': 'receive' if row['income'] > 0 else 'pay',
                        'risk_level': 'high'
                    }
                    direct_transfers.append(transfer)
    
    logger.info(f'发现 {len(direct_transfers)} 笔直接资金往来')
    
    return direct_transfers


def detect_cash_time_collision(all_transactions: Dict[str, pd.DataFrame],
                               core_persons: List[str],
                               involved_companies: List[str]) -> List[Dict]:
    """
    现金时空伴随分析
    检测取现后短时间内的存现配对
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员名单
        involved_companies: 涉案公司名单
        
    Returns:
        时空伴随配对列表
    """
    logger.info('正在执行现金时空伴随分析...')
    
    # 收集所有现金取款记录
    withdrawals = []
    for entity_name, df in all_transactions.items():
        for _, row in df.iterrows():
            if utils.contains_keywords(row['description'], config.CASH_KEYWORDS):
                if row['expense'] > 0:  # 取现
                    withdrawals.append({
                        'entity': entity_name,
                        'date': row['date'],
                        'amount': row['expense'],
                        'description': row['description'],
                        'record': row.to_dict()
                    })
    
    # 收集所有现金存款记录
    deposits = []
    for entity_name, df in all_transactions.items():
        for _, row in df.iterrows():
            if utils.contains_keywords(row['description'], config.CASH_KEYWORDS):
                if row['income'] > 0:  # 存现
                    deposits.append({
                        'entity': entity_name,
                        'date': row['date'],
                        'amount': row['income'],
                        'description': row['description'],
                        'record': row.to_dict()
                    })
    
    # 匹配取现-存现配对
    collisions = []
    
    for withdrawal in withdrawals:
        for deposit in deposits:
            # 不能是同一个实体
            if withdrawal['entity'] == deposit['entity']:
                continue
            
            # 检查时间窗口
            if not utils.is_within_time_window(
                withdrawal['date'], 
                deposit['date'],
                config.CASH_TIME_WINDOW_HOURS
            ):
                continue
            
            # 检查取现在存现之前
            if withdrawal['date'] > deposit['date']:
                continue
            
            # 检查金额相近
            if not utils.is_amount_similar(
                withdrawal['amount'],
                deposit['amount'],
                config.AMOUNT_TOLERANCE_RATIO
            ):
                continue
            
            # 计算时间差
            time_diff_hours = (deposit['date'] - withdrawal['date']).total_seconds() / 3600
            
            # 判断风险等级
            if time_diff_hours <= 24 and \
               utils.is_amount_similar(withdrawal['amount'], deposit['amount'], 0.01):
                risk_level = 'high'
            elif time_diff_hours <= 48:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            
            collision = {
                'withdrawal_entity': withdrawal['entity'],
                'deposit_entity': deposit['entity'],
                'withdrawal_date': withdrawal['date'],
                'deposit_date': deposit['date'],
                'time_diff_hours': time_diff_hours,
                'withdrawal_amount': withdrawal['amount'],
                'deposit_amount': deposit['amount'],
                'amount_diff': abs(withdrawal['amount'] - deposit['amount']),
                'amount_diff_ratio': abs(withdrawal['amount'] - deposit['amount']) / withdrawal['amount'],
                'risk_level': risk_level,
                'withdrawal_record': withdrawal['record'],
                'deposit_record': deposit['record']
            }
            
            collisions.append(collision)
    
    # 按风险等级和时间差排序
    collisions.sort(key=lambda x: (
        {'high': 0, 'medium': 1, 'low': 2}[x['risk_level']],
        x['time_diff_hours']
    ))
    
    logger.info(f'发现 {len(collisions)} 对现金时空伴随记录')
    
    return collisions


def detect_hidden_assets(all_transactions: Dict[str, pd.DataFrame]) -> Dict[str, List[Dict]]:
    """
    检测隐形资产购置
    
    Args:
        all_transactions: 所有交易数据
        
    Returns:
        隐形资产字典 {entity: [资产记录]}
    """
    logger.info('正在检测隐形资产...')
    
    hidden_assets = defaultdict(list)
    
    # 排除关键词 (针对公司业务支出误判)
    exclude_kws = ['干燥', '设备', '净化', '工程', '材料', '生产线', '货款', '合同']
    
    for entity_name, df in all_transactions.items():
        # 疑似购房
        for _, row in df.iterrows():
            if row['expense'] >= config.PROPERTY_THRESHOLD:
                # 组合描述和对手方进行检查
                text_to_check = str(row['description']) + ' ' + str(row['counterparty'])
                
                # 排除工业/商业用途
                if any(k in text_to_check for k in exclude_kws):
                     continue
                     
                if utils.contains_keywords(text_to_check, config.PROPERTY_KEYWORDS):
                    asset = {
                        'type': 'property',
                        'date': row['date'],
                        'amount': row['expense'],
                        'description': row['description'],
                        'counterparty': row['counterparty'],
                        'risk_level': 'high' if row['expense'] >= config.SUSPICION_PROPERTY_HIGH_RISK else 'medium',
                        'record': row.to_dict()
                    }
                    hidden_assets[entity_name].append(asset)
        
        # 疑似购车
        for _, row in df.iterrows():
            if row['expense'] >= config.VEHICLE_THRESHOLD:
                # 组合描述和对手方进行检查
                text_to_check = str(row['description']) + ' ' + str(row['counterparty'])
                
                if any(k in text_to_check for k in exclude_kws):
                     continue

                if utils.contains_keywords(text_to_check, config.VEHICLE_KEYWORDS):
                    asset = {
                        'type': 'vehicle',
                        'date': row['date'],
                        'amount': row['expense'],
                        'description': row['description'],
                        'counterparty': row['counterparty'],
                        'risk_level': 'high' if row['expense'] >= config.SUSPICION_VEHICLE_HIGH_RISK else 'medium',
                        'record': row.to_dict()
                    }
                    hidden_assets[entity_name].append(asset)
    
    total_count = sum(len(assets) for assets in hidden_assets.values())
    logger.info(f'发现 {total_count} 笔疑似资产购置')
    
    return dict(hidden_assets)


def detect_fixed_frequency(all_transactions: Dict[str, pd.DataFrame]) -> Dict[str, List[Dict]]:
    """
    检测固定频率异常进账（排除工资、社保等正常收入）
    
    Args:
        all_transactions: 所有交易数据
        
    Returns:
        固定频率记录字典 {entity: [异常记录]}
    """
    logger.info('正在检测固定频率异常进账...')
    
    fixed_frequency = defaultdict(list)
    
    # 扩展的工资/正常收入关键词（用于排除）
    SALARY_EXCLUSION_KEYWORDS = config.SALARY_KEYWORDS + config.SALARY_STRONG_KEYWORDS + [
        '社保', '公积金', '养老', '医保', '失业保险', '工伤保险',
        '住房', '补贴', '津贴', '奖金', '绩效', '年终',
        '利息', '分红', '股息'
    ]
    
    # 已知发薪单位关键词（排除）
    HR_KEYWORDS = config.HR_COMPANY_KEYWORDS + config.KNOWN_SALARY_PAYERS
    
    for entity_name, df in all_transactions.items():
        # 只关注收入，且金额>=100元（排除银行利息等微小金额）
        income_df = df[df['income'] >= 100].copy()
        
        if len(income_df) < config.FIXED_FREQUENCY_MIN_OCCURRENCES:
            continue
        
        # 排除工资性收入（更严格的过滤）
        def is_likely_salary(row):
            desc = str(row.get('description', ''))
            cp = str(row.get('counterparty', ''))
            # 摘要包含工资关键词
            if utils.contains_keywords(desc, SALARY_EXCLUSION_KEYWORDS):
                return True
            # 对手方是人力资源公司
            if utils.contains_keywords(cp, HR_KEYWORDS):
                return True
            return False
        
        non_salary_income = income_df[~income_df.apply(is_likely_salary, axis=1)].copy()
        
        if len(non_salary_income) < config.FIXED_FREQUENCY_MIN_OCCURRENCES:
            continue
        
        # 按月分组,查找每月同一天的收入
        non_salary_income['day'] = non_salary_income['date'].dt.day
        non_salary_income['month_key'] = non_salary_income['date'].apply(utils.get_month_key)
        
        # 按金额范围分组(±10%)
        amount_groups = defaultdict(list)
        
        for _, row in non_salary_income.iterrows():
            # 查找相似金额的组
            found_group = False
            for base_amount in list(amount_groups.keys()):
                if utils.is_amount_similar(
                    row['income'],
                    base_amount,
                    config.FIXED_FREQUENCY_AMOUNT_TOLERANCE
                ):
                    amount_groups[base_amount].append(row.to_dict())
                    found_group = True
                    break
            
            if not found_group:
                amount_groups[row['income']].append(row.to_dict())
        
        # 检查每个金额组是否有固定频率
        for base_amount, records in amount_groups.items():
            if len(records) < config.FIXED_FREQUENCY_MIN_OCCURRENCES:
                continue
            
            # 检查日期是否相近
            days = [r['date'].day for r in records]
            avg_day = sum(days) / len(days)
            
            # 检查是否在容差范围内
            in_tolerance = all(
                abs(day - avg_day) <= config.FIXED_FREQUENCY_DATE_TOLERANCE
                for day in days
            )
            
            if in_tolerance:
                pattern = {
                    'entity': entity_name,
                    'amount_avg': base_amount,
                    'day_avg': int(avg_day),
                    'occurrences': len(records),
                    'records': records,
                    'date_range': (
                        min(r['date'] for r in records),
                        max(r['date'] for r in records)
                    ),
                    'risk_level': 'high' if len(records) >= 6 else 'medium'
                }
                fixed_frequency[entity_name].append(pattern)
    
    total_count = sum(len(patterns) for patterns in fixed_frequency.values())
    logger.info(f'发现 {total_count} 个固定频率异常进账模式')
    
    return dict(fixed_frequency)


def detect_cash_timing_pattern(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    date_tolerance_days: int = 3
) -> List[Dict]:
    """
    现金存取相似时间点排查
    检测关联人在相近日期的现金存取配对
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员名单
        date_tolerance_days: 日期容差天数
        
    Returns:
        现金时间点配对列表
    """
    logger.info('正在检测现金存取时间点模式...')
    
    # 收集所有核心人员的现金交易
    cash_records = []
    for person in core_persons:
        for key, df in all_transactions.items():
            if person in key and '公司' not in key:
                for _, row in df.iterrows():
                    desc = str(row.get('description', ''))
                    if utils.contains_keywords(desc, config.CASH_KEYWORDS):
                        cash_records.append({
                            'person': person,
                            'date': row.get('date'),
                            'type': 'withdraw' if row.get('expense', 0) > 0 else 'deposit',
                            'amount': max(row.get('income', 0), row.get('expense', 0)),
                            'description': desc
                        })
    
    # 查找时间相近的配对
    patterns = []
    for i, rec1 in enumerate(cash_records):
        for rec2 in cash_records[i+1:]:
            # 不同人
            if rec1['person'] == rec2['person']:
                continue
            
            # 时间相近
            if rec1['date'] is None or rec2['date'] is None:
                continue
            
            time_diff = abs((rec1['date'] - rec2['date']).days)
            if time_diff > date_tolerance_days:
                continue
            
            # 金额相近
            if not utils.is_amount_similar(rec1['amount'], rec2['amount'], 0.15):
                continue
            
            pattern = {
                'person1': rec1['person'],
                'person2': rec2['person'],
                'person1_type': rec1['type'],
                'person2_type': rec2['type'],
                'person1_date': rec1['date'],
                'person2_date': rec2['date'],
                'date_diff_days': time_diff,
                'person1_amount': rec1['amount'],
                'person2_amount': rec2['amount'],
                'risk_level': 'high' if time_diff <= 1 and rec1['type'] != rec2['type'] else 'medium'
            }
            patterns.append(pattern)
    
    # 去重（A-B和B-A视为同一配对）
    unique_patterns = []
    seen = set()
    for p in patterns:
        key = tuple(sorted([p['person1'], p['person2']]) + [str(p['person1_date'])[:10]])
        if key not in seen:
            seen.add(key)
            unique_patterns.append(p)
    
    logger.info(f'发现 {len(unique_patterns)} 对现金时间点配对')
    return unique_patterns


def detect_holiday_transactions(
    all_transactions: Dict[str, pd.DataFrame],
    amount_threshold: float = None
) -> Dict[str, List[Dict]]:
    """
    节假日/特殊时段交易检测（升级版）
    
    检测：
    1. 法定节假日期间及前后的大额交易（支持时间窗口）
    2. 周末频繁大额操作
    3. 非工作时间网银转账
    
    核心改进：
    - 自动根据数据时间范围生成节假日配置
    - 节前3天、节后2天都纳入检测（送礼/回礼高峰）
    - 区分"节前"、"节中"、"节后"不同风险等级
    
    Args:
        all_transactions: 所有交易数据
        amount_threshold: 大额阈值
        
    Returns:
        异常交易字典 {类型: [记录列表]}
    """
    logger.info('正在检测节假日/特殊时段交易...')
    
    if amount_threshold is None:
        amount_threshold = config.HOLIDAY_LARGE_AMOUNT_THRESHOLD
    
    results = {
        'holiday': [],    # 节假日窗口大额交易
        'weekend': [],    # 周末大额交易
        'night': []       # 非工作时间交易
    }
    
    # 使用新的节假日检测器（自动识别数据时间范围）
    try:
        from holiday_utils import HolidayDetector
        
        # 从配置读取窗口参数
        holiday_config = getattr(config, 'HOLIDAY_DETECTION_CONFIG', {})
        days_before = holiday_config.get('days_before', 3)
        days_after = holiday_config.get('days_after', 2)
        
        # 创建检测器
        detector = HolidayDetector.from_transactions(
            all_transactions, days_before, days_after
        )
        
        logger.info(f'节假日检测窗口: 节前{days_before}天 + 节中 + 节后{days_after}天')
        
    except ImportError:
        logger.warning('holiday_utils模块未找到，使用传统检测方式')
        detector = None
        # 回退到传统方式
        holiday_dates = set()
        holiday_names = {}
        for year, holidays in config.CHINESE_HOLIDAYS.items():
            for start_str, end_str, name in holidays:
                start = datetime.strptime(start_str, '%Y-%m-%d')
                end = datetime.strptime(end_str, '%Y-%m-%d')
                current = start
                while current <= end:
                    holiday_dates.add(current.date())
                    holiday_names[current.date()] = name
                    current += timedelta(days=1)
    
    for entity_name, df in all_transactions.items():
        for _, row in df.iterrows():
            date = row.get('date')
            if date is None:
                continue
            
            amount = max(row.get('income', 0), row.get('expense', 0))
            if amount < amount_threshold:
                continue
            
            record_base = {
                'entity': entity_name,
                'date': date,
                'amount': amount,
                'direction': 'income' if row.get('income', 0) > 0 else 'expense',
                'description': row.get('description', ''),
                'counterparty': row.get('counterparty', '')
            }
            
            # 获取日期对象
            if hasattr(date, 'date'):
                date_only = date.date()
            else:
                date_only = date
            
            # 检查节假日窗口
            if detector:
                is_holiday, holiday_name, period = detector.is_holiday_window(date_only)
                if is_holiday:
                    record = record_base.copy()
                    record['holiday_name'] = holiday_name
                    record['period'] = period  # 'before', 'during', 'after'
                    record['period_label'] = {
                        'before': '节前',
                        'during': '节中', 
                        'after': '节后'
                    }.get(period, period)
                    
                    # 风险等级：节前送礼最可疑
                    if period == 'before' and amount >= amount_threshold:
                        record['risk_level'] = 'high'
                        record['risk_reason'] = f'{holiday_name}节前大额交易'
                    elif period == 'during' and amount >= amount_threshold * 2:
                        record['risk_level'] = 'high'
                        record['risk_reason'] = f'{holiday_name}期间特大额交易'
                    elif period == 'after' and amount >= amount_threshold:
                        record['risk_level'] = 'medium'
                        record['risk_reason'] = f'{holiday_name}节后回礼可能'
                    else:
                        record['risk_level'] = 'medium'
                        record['risk_reason'] = f'{holiday_name}期间大额交易'
                    
                    results['holiday'].append(record)
            else:
                # 传统方式
                if date_only in holiday_dates:
                    record = record_base.copy()
                    record['holiday_name'] = holiday_names.get(date_only, '节假日')
                    record['period'] = 'during'
                    record['period_label'] = '节中'
                    record['risk_level'] = 'high' if amount >= amount_threshold * 2 else 'medium'
                    results['holiday'].append(record)
            
            # 检查周末
            if config.WEEKEND_DETECTION_ENABLED:
                if hasattr(date, 'weekday'):
                    weekday = date.weekday()
                    if weekday >= 5:  # 5=周六, 6=周日
                        record = record_base.copy()
                        record['weekday'] = '周六' if weekday == 5 else '周日'
                        record['risk_level'] = 'medium'
                        results['weekend'].append(record)
            
            # 检查非工作时间
            if hasattr(date, 'hour'):
                hour = date.hour
                if hour >= config.NON_WORKING_HOURS_START or hour < config.NON_WORKING_HOURS_END:
                    record = record_base.copy()
                    record['time'] = date.strftime('%H:%M:%S') if hasattr(date, 'strftime') else str(date)
                    record['risk_level'] = 'medium'
                    results['night'].append(record)
    
    # 统计各时段
    holiday_by_period = {'before': 0, 'during': 0, 'after': 0}
    for r in results['holiday']:
        period = r.get('period', 'during')
        holiday_by_period[period] = holiday_by_period.get(period, 0) + 1
    
    logger.info(f'发现节假日窗口交易 {len(results["holiday"])} 笔 '
                f'(节前{holiday_by_period["before"]}/节中{holiday_by_period["during"]}/节后{holiday_by_period["after"]}), '
                f'周末交易 {len(results["weekend"])} 笔, '
                f'非工作时间 {len(results["night"])} 笔')
    
    return results


def detect_amount_patterns(all_transactions: Dict[str, pd.DataFrame]) -> Dict[str, List[Dict]]:
    """
    特定金额模式检测
    
    检测：
    1. 整数金额偏好（如10万整）
    2. 拆分规避监管（多笔接近5万元）
    3. 吉利数尾号（如X88/X66）
    
    Args:
        all_transactions: 所有交易数据
        
    Returns:
        异常模式字典
    """
    logger.info('正在检测特定金额模式...')
    
    results = {
        'round_amounts': [],      # 整数金额偏好
        'split_avoidance': [],    # 拆分规避
        'lucky_tails': []         # 吉利数尾号
    }
    
    for entity_name, df in all_transactions.items():
        round_count = 0
        split_candidates = []
        lucky_count = 0
        
        entity_records = {'round': [], 'split': [], 'lucky': []}
        
        for _, row in df.iterrows():
            amount = max(row.get('income', 0), row.get('expense', 0))
            
            # 1. 检测整数金额偏好
            if amount >= config.ROUND_AMOUNT_THRESHOLD:
                if amount % 10000 == 0:  # 是万的整数倍
                    round_count += 1
                    entity_records['round'].append({
                        'date': row.get('date'),
                        'amount': amount,
                        'description': row.get('description', '')
                    })
            
            # 2. 检测拆分规避（接近5万元）
            threshold = config.SPLIT_AMOUNT_THRESHOLD
            lower = threshold * (1 - config.SPLIT_AMOUNT_TOLERANCE)
            if lower <= amount < threshold:
                split_candidates.append({
                    'date': row.get('date'),
                    'amount': amount,
                    'description': row.get('description', ''),
                    'counterparty': row.get('counterparty', '')
                })
            
            # 3. 检测吉利数尾号
            amount_str = str(int(amount))
            for lucky in config.LUCKY_TAIL_NUMBERS:
                if amount_str.endswith(lucky) and amount >= config.SUSPICION_LUCKY_NUMBER_MIN:
                    lucky_count += 1
                    entity_records['lucky'].append({
                        'date': row.get('date'),
                        'amount': amount,
                        'lucky_tail': lucky,
                        'description': row.get('description', '')
                    })
                    break
        
        # 判断是否存在整数偏好
        if round_count >= config.ROUND_AMOUNT_MIN_COUNT:
            results['round_amounts'].append({
                'entity': entity_name,
                'count': round_count,
                'records': entity_records['round'][:10],  # 限制记录数
                'risk_level': 'medium'
            })
        
        # 判断是否存在拆分规避
        if len(split_candidates) >= config.SPLIT_DETECTION_COUNT:
            # 进一步检查是否短时间内连续
            split_candidates.sort(key=lambda x: x['date'] if x['date'] else datetime.min)
            results['split_avoidance'].append({
                'entity': entity_name,
                'count': len(split_candidates),
                'records': split_candidates[:10],
                'risk_level': 'high' if len(split_candidates) >= 5 else 'medium'
            })
        
        # 吉利数统计
        if lucky_count >= 3:
            results['lucky_tails'].append({
                'entity': entity_name,
                'count': lucky_count,
                'records': entity_records['lucky'][:10],
                'risk_level': 'low'
            })
    
    logger.info(f'发现整数金额偏好 {len(results["round_amounts"])} 个实体, '
                f'拆分规避 {len(results["split_avoidance"])} 个实体, '
                f'吉利数尾号 {len(results["lucky_tails"])} 个实体')
    
    return results


def run_all_detections(all_transactions: Dict[str, pd.DataFrame],
                      core_persons: List[str],
                      involved_companies: List[str]) -> Dict:
    """
    运行所有疑点检测算法
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员名单
        involved_companies: 涉案公司名单
        
    Returns:
        所有疑点汇总字典
    """
    logger.info('=' * 60)
    logger.info('开始执行全面疑点检测')
    logger.info('=' * 60)
    
    suspicions = {}
    
    # 1. 直接输送检测
    suspicions['direct_transfers'] = detect_direct_transfer(
        all_transactions, core_persons, involved_companies
    )
    
    # 2. 现金时空伴随
    suspicions['cash_collisions'] = detect_cash_time_collision(
        all_transactions, core_persons, involved_companies
    )
    
    # 3. 隐形资产
    suspicions['hidden_assets'] = detect_hidden_assets(all_transactions)
    
    # 4. 固定频率异常
    suspicions['fixed_frequency'] = detect_fixed_frequency(all_transactions)
    
    # 5. 现金存取时间点模式（新增）
    suspicions['cash_timing_patterns'] = detect_cash_timing_pattern(
        all_transactions, core_persons
    )
    
    # 6. 节假日/特殊时段交易（新增）
    suspicions['holiday_transactions'] = detect_holiday_transactions(all_transactions)
    
    # 7. 特定金额模式（新增）
    suspicions['amount_patterns'] = detect_amount_patterns(all_transactions)
    
    # 统计
    total_suspicions = (
        len(suspicions['direct_transfers']) +
        len(suspicions['cash_collisions']) +
        sum(len(v) for v in suspicions['hidden_assets'].values()) +
        sum(len(v) for v in suspicions['fixed_frequency'].values()) +
        len(suspicions['cash_timing_patterns']) +
        sum(len(v) for v in suspicions['holiday_transactions'].values()) +
        sum(len(v) for v in suspicions['amount_patterns'].values())
    )
    
    logger.info('=' * 60)
    logger.info(f'疑点检测完成,共发现 {total_suspicions} 个疑点')
    logger.info('=' * 60)
    
    return suspicions

