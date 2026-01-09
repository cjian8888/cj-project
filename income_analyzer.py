#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常收入来源检测模块
识别非工资的规律性大额收入、来源不明收入等
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict
import config
import utils

logger = utils.setup_logger(__name__)


def detect_suspicious_income(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """
    检测可疑收入来源（增强版）
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        
    Returns:
        可疑收入分析结果
    """
    logger.info('='*60)
    logger.info('开始异常收入来源检测（增强版）')
    logger.info('='*60)
    
    results = {
        'regular_non_salary': [],       # 规律性非工资收入
        'large_individual_income': [],  # 来自个人的大额收入
        'unknown_source_income': [],    # 来源不明的大额收入
        'large_single_income': [],      # 大额单笔收入（新增）
        'same_source_multi': [],        # 同源多次收入（新增）
        'high_risk': [],                # 高风险收入汇总（新增）
        'medium_risk': [],              # 中风险收入汇总（新增）
        'summary': {}
    }
    
    # 1. 检测规律性非工资收入
    logger.info('【阶段1】检测规律性非工资收入')
    results['regular_non_salary'] = _detect_regular_non_salary(
        all_transactions, core_persons
    )
    
    # 2. 检测来自个人的大额收入
    logger.info('【阶段2】检测来自个人的大额收入')
    results['large_individual_income'] = _detect_individual_income(
        all_transactions, core_persons
    )
    
    # 3. 检测来源不明的大额收入
    logger.info('【阶段3】检测来源不明的大额收入')
    results['unknown_source_income'] = _detect_unknown_income(
        all_transactions, core_persons
    )
    
    # 4. 检测大额单笔收入（新增）
    logger.info('【阶段4】检测大额单笔收入')
    results['large_single_income'] = _detect_large_single_income(
        all_transactions, core_persons
    )
    
    # 5. 检测同源多次收入（新增）
    logger.info('【阶段5】检测同源多次收入')
    results['same_source_multi'] = _detect_same_source_multi(
        all_transactions, core_persons
    )
    
    # 6. 按风险等级分类汇总（新增）
    results['high_risk'], results['medium_risk'] = _classify_by_risk(results)
    
    # 生成汇总
    results['summary'] = {
        '规律性非工资收入': len(results['regular_non_salary']),
        '个人大额转入': len(results['large_individual_income']),
        '来源不明收入': len(results['unknown_source_income']),
        '大额单笔收入': len(results['large_single_income']),
        '同源多次收入': len(results['same_source_multi']),
        '高风险项目': len(results['high_risk']),
        '中风险项目': len(results['medium_risk'])
    }
    
    logger.info('')
    logger.info(f'异常收入检测完成:')
    for k, v in results['summary'].items():
        logger.info(f'  {k}: {v}')
    
    return results


def _detect_regular_non_salary(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_occurrences: int = 3,
    min_amount: float = config.INCOME_REGULAR_MIN
) -> List[Dict]:
    """
    检测规律性非工资收入
    
    寻找非工资来源的规律性收入，可能是：
    - 租金收入
    - 兼职收入
    - 私下业务收入（灰色收入）
    """
    regular_income = []
    
    # 工资相关关键词（用于排除）
    SALARY_EXCLUSION = config.SALARY_KEYWORDS + config.SALARY_STRONG_KEYWORDS + [
        '社保', '公积金', '养老', '医保', '失业', '工伤',
        '住房', '补贴', '津贴', '奖金', '绩效', '年终',
        '利息', '分红', '股息', '理财', '赎回', '到期'
    ]
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            # 只看收入
            income_df = df[df['income'] >= min_amount].copy()
            if income_df.empty:
                continue
            
            # 按对手方分组
            for cp in income_df['counterparty'].unique():
                cp_str = str(cp)
                if not cp_str or cp_str == 'nan':
                    continue
                
                # 排除工资来源
                if utils.contains_keywords(cp_str, SALARY_EXCLUSION):
                    continue
                if utils.contains_keywords(cp_str, config.HR_COMPANY_KEYWORDS):
                    continue
                if utils.contains_keywords(cp_str, config.KNOWN_SALARY_PAYERS):
                    continue
                
                # 排除银行/理财
                if utils.contains_keywords(cp_str, ['银行', '理财', '基金', '证券', '信托', '保险', '资产']):
                    continue
                
                # 排除公共支付平台
                if utils.contains_keywords(cp_str, config.THIRD_PARTY_PAYMENT_KEYWORDS):
                    continue
                
                cp_df = income_df[income_df['counterparty'] == cp]
                
                if len(cp_df) < min_occurrences:
                    continue
                
                # 检查规律性
                cp_df = cp_df.sort_values('date')
                dates = cp_df['date'].tolist()
                amounts = cp_df['income'].tolist()
                
                # 计算平均间隔
                if len(dates) >= 2:
                    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                    avg_interval = sum(intervals) / len(intervals)
                    
                    # 月度规律（25-35天间隔）
                    if 20 <= avg_interval <= 40:
                        # 金额稳定性
                        mean_amt = sum(amounts) / len(amounts)
                        cv = (sum((x - mean_amt)**2 for x in amounts) / len(amounts))**0.5 / mean_amt if mean_amt > 0 else 999
                        
                        if cv < 0.5:  # 金额相对稳定
                            # [FIX] 增加对摘要的二次检查，防止理财赎回被误判为规律性收入
                            # 典型的误判摘要: "约定定期到期本息转活", "活期宝转活期", "定期结息"
                            wealth_keywords = ['赎回', '到期', '本息', '转存', '理财', '结息', '收益', '分红', '活期宝', '转活', '提现', '银证']
                            
                            is_wealth_like = False
                            for idx in cp_df.index:
                                desc = str(cp_df.loc[idx, 'description'])
                                if utils.contains_keywords(desc, wealth_keywords):
                                    is_wealth_like = True
                                    break
                            
                            if is_wealth_like:
                                logger.info(f'  排除疑似理财赎回: {person} - {cp_str} (摘要含理财特征)')
                                continue

                            regular_income.append({
                                'person': person,
                                'counterparty': cp_str,
                                'occurrences': len(cp_df),
                                'avg_amount': mean_amt,
                                'total_amount': sum(amounts),
                                'avg_interval_days': avg_interval,
                                'cv': cv,
                                'date_range': (min(dates), max(dates)),
                                'possible_type': _guess_income_type(cp_str, mean_amt),
                                'risk_level': 'high' if mean_amt >= config.INCOME_LARGE_PERSONAL_MIN else 'medium' # 调高阈值
                            })
    
    # 按金额排序
    regular_income.sort(key=lambda x: -x['total_amount'])
    
    logger.info(f'  发现 {len(regular_income)} 个规律性非工资收入')
    return regular_income


def _guess_income_type(counterparty: str, amount: float) -> str:
    """推测收入类型"""
    import re
    
    # 个人转账（2-4个汉字）
    if re.match(r'^[\u4e00-\u9fa5]{2,4}$', counterparty):
        if amount >= config.LOAN_MIN_AMOUNT:
            return '个人大额转入（需关注）'
        else:
            return '个人转入'
    
    # 租金相关
    if utils.contains_keywords(counterparty, ['房租', '租金', '物业', '房东']):
        return '疑似租金收入'
    
    # 兼职/劳务
    if utils.contains_keywords(counterparty, ['劳务', '兼职', '咨询', '服务费']):
        return '疑似兼职/劳务收入'
    
    return '来源待核实'


def _detect_individual_income(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_amount: float = config.INCOME_UNKNOWN_SOURCE_MIN
) -> List[Dict]:
    """
    检测来自个人的大额收入
    
    个人对个人的大额转账需要重点关注
    """
    individual_income = []
    
    import re
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            for _, row in df.iterrows():
                if row.get('income', 0) < min_amount:
                    continue
                
                cp = str(row.get('counterparty', ''))
                
                # 判断是否为个人（2-4个汉字）
                if not re.match(r'^[\u4e00-\u9fa5]{2,4}$', cp):
                    continue
                
                # 排除核心人员之间的转账（已在其他模块分析）
                if cp in core_persons:
                    continue
                
                individual_income.append({
                    'person': person,
                    'from_individual': cp,
                    'date': row['date'],
                    'amount': row['income'],
                    'description': row.get('description', ''),
                    'risk_level': 'high' if row['income'] >= config.INCOME_HIGH_RISK_MIN else 'medium'
                })
    
    # 按金额排序
    individual_income.sort(key=lambda x: -x['amount'])
    
    logger.info(f'  发现 {len(individual_income)} 笔来自个人的大额收入')
    return individual_income


def _detect_unknown_income(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_amount: float = config.INCOME_HIGH_RISK_MIN
) -> List[Dict]:
    """
    检测来源不明的大额收入（增强版）
    
    对手方信息缺失或模糊的大额收入
    增加定期存款本息识别，减少误报
    """
    unknown_income = []
    
    # === 新增: 先识别可能的定期存款账户 ===
    # 定期存款本息特征: 固定间隔、金额递增、同一账户
    periodic_deposit_patterns = _identify_periodic_deposit_patterns(all_transactions, core_persons)
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty:
                continue
            
            for _, row in df.iterrows():
                if row.get('income', 0) < min_amount:
                    continue
                
                cp = str(row.get('counterparty', ''))
                desc = str(row.get('description', ''))
                account = str(row.get('account', ''))  # 账号
                
                # 判断是否来源不明
                is_unknown = False
                reason = ''
                
                if not cp or cp == 'nan' or len(cp) < 2:
                    is_unknown = True
                    reason = '对手方信息缺失'
                elif cp in ['未知', '其他', '个人', '转账']:
                    is_unknown = True
                    reason = '对手方信息模糊'
                elif utils.contains_keywords(desc, ['现金', '存入', 'ATM']):
                    is_unknown = True
                    reason = '现金存入（来源不明）'
                
                # === 新增: 检查是否匹配定期存款模式 ===
                if is_unknown:
                    pattern_key = f"{person}_{account}" if account else person
                    if pattern_key in periodic_deposit_patterns:
                        pattern = periodic_deposit_patterns[pattern_key]
                        # 检查日期是否与模式匹配
                        tx_date = row['date']
                        for expected_date in pattern['expected_dates']:
                            if abs((tx_date - expected_date).days) <= 7:  # 允许7天误差
                                is_unknown = False
                                reason = '疑似定期存款本息（规律性到账）'
                                break
                
                # [FIX] 增加非整数金额的判定
                if is_unknown and row['income'] % 1 != 0:
                    is_unknown = False
                
                # [FIX] 增加对理财赎回特征的排除
                if is_unknown and utils.contains_keywords(desc, ['赎回', '到期', '本息', '转存', '理财', '结息', '收益', '分红', '活期宝', '转活', '提现', '银证']):
                    continue
                
                # === 新增: 排除政府机关付款 ===
                if is_unknown and utils.contains_keywords(cp, config.GOVERNMENT_AGENCY_KEYWORDS):
                    continue
                
                if is_unknown:
                    unknown_income.append({
                        'person': person,
                        'counterparty': cp if cp and cp != 'nan' else '(无)',
                        'date': row['date'],
                        'amount': row['income'],
                        'description': desc,
                        'reason': reason,
                        'risk_level': 'high'
                    })
    
    # 按金额排序
    unknown_income.sort(key=lambda x: -x['amount'])
    
    logger.info(f'  发现 {len(unknown_income)} 笔来源不明的大额收入')
    return unknown_income


def _identify_periodic_deposit_patterns(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_occurrences: int = 4,
    interval_tolerance_days: int = 15
) -> Dict:
    """
    识别定期存款到期本息模式（新增功能）
    
    特征:
    1. 固定时间间隔（如每3个月）
    2. 金额有规律性递增（利息累积）
    3. 无对手方信息
    4. 同一账户
    
    Returns:
        pattern_key -> pattern_info 的字典
    """
    patterns = {}
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty or 'income' not in df.columns:
                continue
            
            # 获取账号列名
            account_col = None
            for col in ['account', '本方账号', '账号']:
                if col in df.columns:
                    account_col = col
                    break
            
            if not account_col:
                continue
            
            # 按账号分组分析
            for account in df[account_col].unique():
                if not account or str(account) == 'nan':
                    continue
                
                acc_df = df[df[account_col] == account].copy()
                
                # 筛选无对手方的大额收入
                unknown_mask = (
                    (acc_df['income'] > 100000) &  # 10万以上
                    (acc_df['counterparty'].fillna('').astype(str).str.len() < 3)  # 无对手方
                )
                unknown_income = acc_df[unknown_mask].sort_values('date')
                
                if len(unknown_income) < min_occurrences:
                    continue
                
                # 计算时间间隔
                dates = unknown_income['date'].tolist()
                intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                
                if len(intervals) < 2:
                    continue
                
                # 检查间隔是否稳定（标准差小于容差）
                avg_interval = sum(intervals) / len(intervals)
                variance = sum((x - avg_interval)**2 for x in intervals) / len(intervals)
                std_interval = variance ** 0.5
                
                # 典型定期存款间隔: 90天(季度)或180天(半年)或365天(年)
                is_periodic = std_interval < interval_tolerance_days
                
                if is_periodic and avg_interval > 60:  # 至少2个月间隔
                    # 检查金额是否递增（利息累积特征）
                    amounts = unknown_income['income'].tolist()
                    diffs = [amounts[i+1] - amounts[i] for i in range(len(amounts)-1)]
                    increasing_count = sum(1 for d in diffs if d > 0)
                    
                    if increasing_count >= len(diffs) * 0.6:  # 60%以上递增
                        pattern_key = f"{person}_{account}"
                        
                        # 推算未来的预期日期
                        last_date = dates[-1]
                        expected_dates = [
                            last_date + timedelta(days=int(avg_interval * i))
                            for i in range(1, 5)  # 预测未来4次
                        ]
                        
                        patterns[pattern_key] = {
                            'person': person,
                            'account': str(account),
                            'avg_interval_days': avg_interval,
                            'avg_amount': sum(amounts) / len(amounts),
                            'occurrences': len(unknown_income),
                            'last_date': last_date,
                            'expected_dates': expected_dates,
                            'pattern_type': '疑似定期存款本息'
                        }
                        
                        logger.debug(f'识别到定期存款模式: {pattern_key}, 间隔约{avg_interval:.0f}天')
    
    if patterns:
        logger.info(f'  识别到 {len(patterns)} 个定期存款模式（将从来源不明中排除）')
    
    return patterns


def _detect_large_single_income(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    threshold: float = config.INCOME_VERY_LARGE_MIN
) -> List[Dict]:
    """
    检测大额单笔收入（≥10万元）
    
    单笔超过10万元的收入需要重点关注来源
    """
    large_income = []
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty:
                continue
            
            for _, row in df.iterrows():
                income = row.get('income', 0)
                if income < threshold:
                    continue
                
                cp = str(row.get('counterparty', ''))
                desc = str(row.get('description', ''))
                
                # 排除同名对手方（自己转自己）
                if cp == person or cp in core_persons:
                    continue
                
                # 排除理财赎回、工资奖金等正常大额收入
                if utils.contains_keywords(desc, ['理财', '赎回', '到期', '兑付', '基金', '本息', '转存', '结息', '收益', '分红', '活期宝', '转活']):
                    continue
                if utils.contains_keywords(desc, config.SALARY_STRONG_KEYWORDS):
                    continue
                if utils.contains_keywords(cp, config.KNOWN_SALARY_PAYERS):
                    continue
                if utils.contains_keywords(cp, config.USER_DEFINED_SALARY_PAYERS):
                    continue
                
                # 判断收入类型和风险
                income_type = '待核实'
                risk_level = 'high'
                
                if utils.contains_keywords(cp, ['银行', '证券']):
                    income_type = '银行/证券转入'
                    risk_level = 'medium'
                elif utils.contains_keywords(desc, ['借款', '借入', '还款']):
                    income_type = '借款收入'
                    risk_level = 'high'
                elif utils.contains_keywords(desc, ['转让', '股权', '投资']):
                    income_type = '投资收益'
                    risk_level = 'medium'
                else:
                    import re
                    if re.match(r'^[\u4e00-\u9fa5]{2,4}$', cp):
                        income_type = '个人大额转入'
                        risk_level = 'high'
                
                large_income.append({
                    'person': person,
                    'counterparty': cp if cp and cp != 'nan' else '(未知)',
                    'date': row['date'],
                    'amount': income,
                    'description': desc,
                    'income_type': income_type,
                    'risk_level': risk_level
                })
    
    # 按金额排序
    large_income.sort(key=lambda x: -x['amount'])
    
    logger.info(f'  发现 {len(large_income)} 笔大额单笔收入')
    return large_income


def _detect_same_source_multi(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_count: int = 5,
    min_total: float = config.INCOME_HIGH_RISK_MIN
) -> List[Dict]:
    """
    检测同源多次收入
    
    同一来源多次转入且累计金额较大，可能是：
    - 隐性报酬
    - 业务分成
    - 利益输送
    """
    same_source = []
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            # 按对手方统计
            cp_stats = defaultdict(lambda: {'count': 0, 'total': 0, 'records': []})
            
            for _, row in df.iterrows():
                income = row.get('income', 0)
                if income <= 0:
                    continue
                
                cp = str(row.get('counterparty', ''))
                if not cp or cp == 'nan' or len(cp) < 2:
                    continue
                
                # 排除同名对手方（自己转自己）
                if cp == person or cp in core_persons:
                    continue
                
                # 排除银行/理财/工资来源
                if utils.contains_keywords(cp, ['银行', '理财', '基金', '证券', '信托', '保险', '资产']):
                    continue
                if utils.contains_keywords(cp, config.SALARY_STRONG_KEYWORDS):
                    continue
                if utils.contains_keywords(cp, config.KNOWN_SALARY_PAYERS):
                    continue
                if utils.contains_keywords(cp, config.THIRD_PARTY_PAYMENT_KEYWORDS):
                    continue
                
                # === 新增: 排除政府机关（工资/补贴是正常收入）===
                if utils.contains_keywords(cp, config.GOVERNMENT_AGENCY_KEYWORDS):
                    continue
                
                # === 新增: 排除理财产品对手方 ===
                if utils.contains_keywords(cp, config.WEALTH_PRODUCT_COUNTERPARTY_KEYWORDS):
                    continue
                
                cp_stats[cp]['count'] += 1
                cp_stats[cp]['total'] += income
                cp_stats[cp]['records'].append({
                    'date': row['date'],
                    'amount': income
                })
            
            # 筛选满足条件的
            for cp, stats in cp_stats.items():
                if stats['count'] >= min_count and stats['total'] >= min_total:
                    # 判断风险等级
                    risk_level = 'high' if stats['total'] >= config.INCOME_VERY_LARGE_MIN else 'medium'
                    
                    # 推测类型
                    import re
                    if re.match(r'^[\u4e00-\u9fa5]{2,4}$', cp):
                        source_type = '个人多次转入'
                    else:
                        source_type = '机构多次转入'
                    
                    same_source.append({
                        'person': person,
                        'counterparty': cp,
                        'count': stats['count'],
                        'total': stats['total'],
                        'avg_amount': stats['total'] / stats['count'],
                        'records': stats['records'],
                        'source_type': source_type,
                        'risk_level': risk_level
                    })
    
    # 按累计金额排序
    same_source.sort(key=lambda x: -x['total'])
    
    logger.info(f'  发现 {len(same_source)} 个同源多次收入')
    return same_source


def _classify_by_risk(results: Dict) -> tuple:
    """
    按风险等级分类汇总所有异常收入
    
    将所有检测结果按高风险和中风险分类
    """
    high_risk = []
    medium_risk = []
    
    # 规律性非工资收入
    for item in results.get('regular_non_salary', []):
        entry = {
            'type': '规律性非工资收入',
            'person': item['person'],
            'counterparty': item['counterparty'],
            'amount': item['total_amount'],
            'detail': f"共{item['occurrences']}次, 均额{item['avg_amount']:.0f}元",
            'risk_level': item['risk_level']
        }
        if item['risk_level'] == 'high':
            high_risk.append(entry)
        else:
            medium_risk.append(entry)
    
    # 个人大额转入
    for item in results.get('large_individual_income', []):
        entry = {
            'type': '个人大额转入',
            'person': item['person'],
            'counterparty': item['from_individual'],
            'amount': item['amount'],
            'detail': f"日期: {item['date']}",
            'risk_level': item['risk_level']
        }
        if item['risk_level'] == 'high':
            high_risk.append(entry)
        else:
            medium_risk.append(entry)
    
    # 来源不明收入
    for item in results.get('unknown_source_income', []):
        entry = {
            'type': '来源不明收入',
            'person': item['person'],
            'counterparty': item['counterparty'],
            'amount': item['amount'],
            'detail': item['reason'],
            'risk_level': item['risk_level']
        }
        high_risk.append(entry)  # 来源不明总是高风险
    
    # 大额单笔收入
    for item in results.get('large_single_income', []):
        entry = {
            'type': '大额单笔收入',
            'person': item['person'],
            'counterparty': item['counterparty'],
            'amount': item['amount'],
            'detail': item['income_type'],
            'risk_level': item['risk_level']
        }
        if item['risk_level'] == 'high':
            high_risk.append(entry)
        else:
            medium_risk.append(entry)
    
    # 同源多次收入
    for item in results.get('same_source_multi', []):
        entry = {
            'type': '同源多次收入',
            'person': item['person'],
            'counterparty': item['counterparty'],
            'amount': item['total'],
            'detail': f"共{item['count']}次, 均额{item['avg_amount']:.0f}元",
            'risk_level': item['risk_level']
        }
        if item['risk_level'] == 'high':
            high_risk.append(entry)
        else:
            medium_risk.append(entry)
    
    # 按金额排序
    high_risk.sort(key=lambda x: -x['amount'])
    medium_risk.sort(key=lambda x: -x['amount'])
    
    logger.info(f'  风险分类: 高风险{len(high_risk)}项, 中风险{len(medium_risk)}项')
    return high_risk, medium_risk


def generate_suspicious_income_report(results: Dict, output_dir: str) -> str:
    """生成异常收入分析报告（增强版）"""
    import os
    report_path = os.path.join(output_dir, '异常收入来源分析报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('异常收入来源分析报告（增强版）\n')
        f.write('='*60 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        
        # 汇总
        summary = results['summary']
        f.write('一、汇总统计\n')
        f.write('-'*40 + '\n')
        for k, v in summary.items():
            f.write(f'{k}: {v}\n')
        f.write('\n')
        
        # ===== 高风险项目（优先处理）=====
        if results.get('high_risk'):
            f.write('★★★ 二、高风险项目（优先核查）★★★\n')
            f.write('='*40 + '\n')
            f.write('以下项目风险较高，建议优先核实\n\n')
            for i, item in enumerate(results['high_risk'][:20], 1):
                f.write(f"{i}. 【{item['type']}】{item['person']} ← {item['counterparty']}\n")
                f.write(f"   金额: {utils.format_currency(item['amount'])}\n")
                f.write(f"   详情: {item['detail']}\n")
            f.write('\n')
        
        # ===== 中风险项目（参考信息）=====
        if results.get('medium_risk'):
            f.write('三、中风险项目（参考信息）\n')
            f.write('-'*40 + '\n')
            f.write('以下项目需酌情关注\n\n')
            for i, item in enumerate(results['medium_risk'][:15], 1):
                f.write(f"{i}. 【{item['type']}】{item['person']} ← {item['counterparty']}\n")
                f.write(f"   金额: {utils.format_currency(item['amount'])}\n")
            f.write('\n')
        
        # ===== 详细分类 =====
        f.write('='*60 + '\n')
        f.write('以下为各类型异常收入详细明细\n')
        f.write('='*60 + '\n\n')
        
        # 规律性非工资收入
        if results.get('regular_non_salary'):
            f.write('四、规律性非工资收入\n')
            f.write('-'*40 + '\n')
            for i, inc in enumerate(results['regular_non_salary'][:15], 1):
                f.write(f"{i}. 【{inc['risk_level'].upper()}】{inc['person']} ← {inc['counterparty']}\n")
                f.write(f"   共{inc['occurrences']}次, 均额{utils.format_currency(inc['avg_amount'])}, "
                       f"合计{utils.format_currency(inc['total_amount'])}\n")
                f.write(f"   推测类型: {inc['possible_type']}\n")
            f.write('\n')
        
        # 大额单笔收入
        if results.get('large_single_income'):
            f.write('五、大额单笔收入（≥10万元）\n')
            f.write('-'*40 + '\n')
            for i, inc in enumerate(results['large_single_income'][:15], 1):
                date_str = inc['date'].strftime('%Y-%m-%d') if hasattr(inc['date'], 'strftime') else str(inc['date'])[:10]
                f.write(f"{i}. 【{inc['risk_level'].upper()}】{inc['person']} ← {inc['counterparty']}\n")
                f.write(f"   金额: {utils.format_currency(inc['amount'])} ({date_str})\n")
                f.write(f"   类型: {inc['income_type']}\n")
            f.write('\n')
        
        # 同源多次收入
        if results.get('same_source_multi'):
            f.write('六、同源多次收入\n')
            f.write('-'*40 + '\n')
            for i, inc in enumerate(results['same_source_multi'][:15], 1):
                f.write(f"{i}. 【{inc['risk_level'].upper()}】{inc['person']} ← {inc['counterparty']}\n")
                f.write(f"   共{inc['count']}次, 均额{utils.format_currency(inc['avg_amount'])}, "
                       f"合计{utils.format_currency(inc['total'])}\n")
                f.write(f"   类型: {inc['source_type']}\n")
            f.write('\n')
        
        # 个人大额转入
        if results.get('large_individual_income'):
            f.write('七、来自个人的大额收入\n')
            f.write('-'*40 + '\n')
            for i, inc in enumerate(results['large_individual_income'][:20], 1):
                date_str = inc['date'].strftime('%Y-%m-%d') if hasattr(inc['date'], 'strftime') else str(inc['date'])[:10]
                f.write(f"{i}. {inc['person']} ← {inc['from_individual']}: "
                       f"{utils.format_currency(inc['amount'])} ({date_str})\n")
            f.write('\n')
        
        # 来源不明
        if results.get('unknown_source_income'):
            f.write('八、来源不明的大额收入（重点核查）\n')
            f.write('-'*40 + '\n')
            for i, inc in enumerate(results['unknown_source_income'][:15], 1):
                date_str = inc['date'].strftime('%Y-%m-%d') if hasattr(inc['date'], 'strftime') else str(inc['date'])[:10]
                f.write(f"{i}. 【{inc['risk_level'].upper()}】{inc['person']}: "
                       f"{utils.format_currency(inc['amount'])} ({date_str})\n")
                f.write(f"   原因: {inc['reason']}\n")
            f.write('\n')
    
    logger.info(f'异常收入分析报告已生成: {report_path}')
    return report_path

