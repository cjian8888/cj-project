#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常收入来源检测模块
识别非工资的规律性大额收入、来源不明收入等

重构说明 (2026-01-11):
- 使用 counterparty_utils 统一理财产品识别逻辑
- 使用 config.py 中的阈值替代硬编码
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from collections import defaultdict
import config
import utils
from counterparty_utils import (
    is_wealth_management_transaction,
    should_exclude_large_income,
    is_individual_name,
    ExclusionContext
)
from wealth_account_analyzer import integrate_with_income_analyzer

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
        'potential_bribe_installment': [],  # 【新增】疑似分期受贿
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
    
    # 6. 【新增】分期受贿风险检测
    logger.info('【阶段6】检测疑似分期受贿')
    results['potential_bribe_installment'] = _detect_potential_bribe_installment(
        all_transactions, core_persons
    )
    
    # 7. 按风险等级分类汇总（新增）
    results['high_risk'], results['medium_risk'] = _classify_by_risk(results)
    
    # 生成汇总
    results['summary'] = {
        '规律性非工资收入': len(results['regular_non_salary']),
        '个人大额转入': len(results['large_individual_income']),
        '来源不明收入': len(results['unknown_source_income']),
        '大额单笔收入': len(results['large_single_income']),
        '同源多次收入': len(results['same_source_multi']),
        '疑似分期受贿': len(results['potential_bribe_installment']),
        '高风险项目': len(results['high_risk']),
        '中风险项目': len(results['medium_risk'])
    }
    
    logger.info('')
    logger.info(f'异常收入检测完成:')
    for k, v in results['summary'].items():
        logger.info(f'  {k}: {v}')
    
    return results


def _extract_counterparty_from_description(desc: str) -> str:
    """
    【P4 优化】从摘要中提取对手方信息
    
    常见模式：
    - "转账 张三" -> "张三"
    - "来自:李四" -> "李四"
    - "代发 某某公司" -> "某某公司"
    - "支付宝转账-王五" -> "王五"
    
    Args:
        desc: 交易摘要
        
    Returns:
        提取到的对手方名称，如果提取失败返回空字符串
    """
    import re
    
    if not desc or desc == 'nan':
        return ''
    
    desc = str(desc).strip()
    
    # 模式1: "转账 张三" 或 "转账给张三"
    match = re.search(r'转账[给到]?\s*([^\s,，;；\d]{2,10})', desc)
    if match:
        return match.group(1)
    
    # 模式2: "来自:李四" 或 "来自李四"
    match = re.search(r'来自[:：]?\s*([^\s,，;；\d]{2,10})', desc)
    if match:
        return match.group(1)
    
    # 模式3: "代发 某某公司"
    match = re.search(r'代发\s*([^\s,，;；\d]{2,20})', desc)
    if match:
        return match.group(1)
    
    # 模式4: "支付宝转账-王五"
    match = re.search(r'[-—]\s*([^\s,，;；\d]{2,10})$', desc)
    if match:
        return match.group(1)
    
    # 模式5: "付款人:某某"
    match = re.search(r'付款人[:：]?\s*([^\s,，;；\d]{2,10})', desc)
    if match:
        return match.group(1)
    
    # 模式6: 某些银行摘要末尾是对手方 "网银转账 张三丰"
    match = re.search(r'(?:网银|手机银行|A跨行)转账?\s+([^\s,，;；\d]{2,10})$', desc)
    if match:
        return match.group(1)
    
    # 模式7: 理财产品到账 "理财产品到账-ABC理财"
    if '理财' in desc or '赎回' in desc:
        match = re.search(r'[-—]\s*(.{2,20}理财.{0,10})$', desc)
        if match:
            return match.group(1)
    
    return ''


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
                    
                    # 月度规律（使用配置阈值）
                    interval_min = config.REGULAR_INCOME_INTERVAL_MIN
                    interval_max = config.REGULAR_INCOME_INTERVAL_MAX
                    cv_threshold = config.REGULAR_INCOME_CV_THRESHOLD
                    
                    if interval_min <= avg_interval <= interval_max:
                        # 金额稳定性
                        mean_amt = sum(amounts) / len(amounts)
                        cv = (sum((x - mean_amt)**2 for x in amounts) / len(amounts))**0.5 / mean_amt if mean_amt > 0 else 999
                        
                        if cv < cv_threshold:  # 金额相对稳定
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

                            # 取第一条记录的溯源信息
                            first_row = cp_df.iloc[0]
                            
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
                                'risk_level': 'high' if mean_amt >= config.INCOME_LARGE_PERSONAL_MIN else 'medium',
                                # 【溯源铁律】原始文件和行号（取第一条记录）
                                'source_file': f'cleaned_data/个人/{person}_合并流水.xlsx',
                                'source_row_index': first_row.get('source_row_index', None)
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
                    # 【修复】如果原始描述为空，生成有意义的描述
                    'description': row.get('description', '') if row.get('description') and str(row.get('description')) != 'nan' else f'来自个人: {cp}',
                    'risk_level': 'high' if row['income'] >= config.INCOME_HIGH_RISK_MIN else 'medium',
                    # 【行号定位】添加原始行号
                    'source_row_index': row.get('source_row_index', None),
                    'source_file': f'cleaned_data/个人/{person}_合并流水.xlsx'
                })
    
    # 按金额排序
    individual_income.sort(key=lambda x: -x['amount'])
    
    logger.info(f'  发现 {len(individual_income)} 笔来自个人的大额收入')
    return individual_income


# 注意: _is_wealth_management_transaction 已迁移至 counterparty_utils.py
# 现在使用 from counterparty_utils import is_wealth_management_transaction


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
    
    # 先识别可能的定期存款账户
    # 定期存款本息特征: 固定间隔、金额递增、同一账户
    periodic_deposit_patterns = _identify_periodic_deposit_patterns(all_transactions, core_persons)
    
    for person in core_persons:
            for key, df in all_transactions.items():
                if person not in key or '公司' in key:
                    continue
                
                if df.empty:
                    continue
                
                # 【重构】优先使用WealthAccountAnalyzer进行账户分类和交易识别
                df_processed = df.copy()
                wealth_analysis_success = False
                
                try:
                    from wealth_account_analyzer import integrate_with_income_analyzer
                    df_processed = integrate_with_income_analyzer(df, person)
                    wealth_analysis_success = True
                    
                    # 统计分类结果
                    category_counts = df_processed['category'].value_counts().to_dict()
                    non_unknown = {k: v for k, v in category_counts.items() if k != 'unknown'}
                    if non_unknown:
                        logger.info(f'[WealthAccountAnalyzer] {person}: 识别出{sum(non_unknown.values())}笔特定交易')
                        for cat, count in non_unknown.items():
                            logger.info(f'  - {cat}: {count}笔')
                except Exception as e:
                    logger.warning(f'[WealthAccountAnalyzer] {person} 分析失败，使用备用识别: {e}')
                    df_processed['category'] = 'unknown'
                    df_processed['category_confidence'] = 0.0
                
                for _, row in df_processed.iterrows():
                    if row.get('income', 0) < min_amount:
                        continue
                    continue
                
                cp = str(row.get('counterparty', ''))
                desc = str(row.get('description', ''))
                account = str(row.get('account', ''))  # 账号
                
                # 【P4 优化】对手方缺失时尝试从摘要中提取
                if not cp or cp == 'nan' or len(cp) < 2:
                    extracted_cp = _extract_counterparty_from_description(desc)
                    if extracted_cp:
                        cp = extracted_cp
                        logger.debug(f'  从摘要提取对手方: {person} - {cp}')
                
                # 判断是否来源不明
                is_unknown = False
                reason = ''
                
                if not cp or cp == 'nan' or len(cp) < 2:
                    is_unknown = True
                    reason = '对手方信息缺失'
                elif cp in ['未知', '其他', '个人', '转账']:
                    is_unknown = True
                    reason = '对手方信息模糊'
                elif utils.contains_keywords(desc, ['现金', '存入', 'ATM']) and not utils.contains_keywords(desc, ['添利', '理财', '活期宝']):
                    is_unknown = True
                    reason = '现金存入（来源不明）'
                
                # 【重构】理财产品识别 - 优先使用WealthAccountAnalyzer结果
                if is_unknown:
                    # 方法1: 优先使用WealthAccountAnalyzer的分类结果
                    category = str(row.get('category', 'unknown'))
                    confidence = float(row.get('category_confidence', 0.0))
                    
                    # 使用config中的置信度阈值
                    if category in ['wealth_redemption', 'wealth_purchase'] and confidence >= config.WEALTH_CONFIDENCE_THRESHOLD_MEDIUM:
                        is_unknown = False
                        reason = f'WealthAccountAnalyzer识别({category}, 置信度{confidence:.2f}, 阈值{config.WEALTH_CONFIDENCE_THRESHOLD_MEDIUM})'
                        logger.info(f'[理财识别] {person} {row["income"]/10000:.2f}万 - {reason}')
                    elif category in ['securities_inflow', 'securities_outflow'] and confidence >= config.SECURITIES_CONFIDENCE_THRESHOLD:
                        is_unknown = False
                        reason = f'银证转账识别({category}, 置信度{confidence:.2f}, 阈值{config.SECURITIES_CONFIDENCE_THRESHOLD})'
                        logger.debug(f'[银证识别] {person} {row["income"]/10000:.2f}万 - {reason}')
                    
                    # 方法2: 原有识别函数作为fallback
                    if is_unknown:
                        is_wealth_mgmt, wealth_reason = is_wealth_management_transaction(desc, row['income'], cp)
                        if is_wealth_mgmt:
                            is_unknown = False
                            logger.debug(f'  理财识别(fallback): {person} {row["income"]/10000:.2f}万 - {wealth_reason}')
                
                # 检查是否匹配定期存款模式
                if is_unknown:
                    pattern_key = f"{person}_{account}" if account else person
                    if pattern_key in periodic_deposit_patterns:
                        pattern = periodic_deposit_patterns[pattern_key]
                        tx_date = row['date']
                        for expected_date in pattern['expected_dates']:
                            if abs((tx_date - expected_date).days) <= 7:
                                is_unknown = False
                                reason = '疑似定期存款本息（规律性到账）'
                                break
                
                # 非整数金额（有小数点）通常是利息，排除
                if is_unknown and row['income'] % 1 != 0:
                    is_unknown = False
                
                # 排除政府机关付款
                if is_unknown and utils.contains_keywords(cp, config.GOVERNMENT_AGENCY_KEYWORDS):
                    continue
                
                if is_unknown:
                    # 【P5 优化】添加可追溯信息
                    bank = str(row.get('bank', ''))
                    account_full = str(row.get('account', ''))
                    # 账户号码部分隐藏（显示前4后4位）
                    if len(account_full) > 8:
                        account_display = account_full[:4] + '****' + account_full[-4:]
                    else:
                        account_display = account_full
                    
                    unknown_income.append({
                        'person': person,
                        'counterparty': cp if cp and cp != 'nan' else '(无)',
                        'date': row['date'],
                        'amount': row['income'],
                        'description': desc,
                        'reason': reason,
                        'risk_level': 'high',
                        # 【P5 新增】追溯字段
                        'account': account_display,
                        'bank': bank,
                        'source_file': f'cleaned_data/个人/{person}_合并流水.xlsx',
                        # 【行号定位】添加原始行号
                        'source_row_index': row.get('source_row_index', None)
                    })
    
    # 按金额排序
    unknown_income.sort(key=lambda x: -x['amount'])
    
    # 【新增】统计WealthAccountAnalyzer识别效果
    if unknown_income:
        logger.info(f'【收入分析结果】')
        logger.info(f'  - 总大额收入: {len([x for x in unknown_income if x.get("amount", 0) > 0]) + len(unknown_income)}笔')
        logger.info(f'  - WealthAccountAnalyzer已识别: 从来源不明中排除')
        logger.info(f'  - 剩余来源不明: {len(unknown_income)}笔')
    
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


# 注意: _should_exclude_large_income 已迁移至 counterparty_utils.py
# 现在使用 from counterparty_utils import should_exclude_large_income


def _determine_income_type_and_risk(cp: str, desc: str) -> tuple:
    """
    判断收入类型和风险等级
    
    Args:
        cp: 对手方
        desc: 交易摘要
        
    Returns:
        (收入类型, 风险等级)
    """
    import re
    
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
        if re.match(r'^[\u4e00-\u9fa5]{2,4}$', cp):
            income_type = '个人大额转入'
            risk_level = 'high'
    
    return income_type, risk_level


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
                
                # 排除理财产品相关交易（使用统一的排除函数）
                if should_exclude_large_income(desc, cp, income):
                    continue
                
                # 判断收入类型和风险
                income_type, risk_level = _determine_income_type_and_risk(cp, desc)
                
                large_income.append({
                    'person': person,
                    'counterparty': cp if cp and cp != 'nan' else '(未知)',
                    'date': row['date'],
                    'amount': income,
                    # 【修复】确保 description 有值，使用 income_type 作为回退
                    'description': desc if desc and desc != 'nan' else income_type,
                    'income_type': income_type,
                    'risk_level': risk_level,
                    # 【行号定位】添加原始行号
                    'source_row_index': row.get('source_row_index', None),
                    'source_file': f'cleaned_data/个人/{person}_合并流水.xlsx'
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
                        'risk_level': risk_level,
                        # 【溯源铁律】原始文件（聚合类型，无单条行号）
                        'source_file': f'cleaned_data/个人/{person}_合并流水.xlsx',
                        'source_row_index': None  # 聚合多条，无单一行号
                    })
    
    # 按累计金额排序
    same_source.sort(key=lambda x: -x['total'])
    
    logger.info(f'  发现 {len(same_source)} 个同源多次收入')
    return same_source


def _calculate_confidence_score(item: Dict, item_type: str) -> int:
    """
    计算可信度评分（0-100分）
    
    评分越高，表示该项越可能是真正的异常收入
    
    评分因子：
    - 金额大小（+10~+30）
    - 对手方信息完整度（+10~+20）
    - 交易频次（+5~+15）
    - 风险等级（+10~+20）
    - 摘要信息丰富度（+5~+15）
    """
    score = 50  # 基础分
    
    # 1. 金额因子
    amount = item.get('amount', item.get('total_amount', item.get('total', 0)))
    if amount >= 500000:  # 50万以上
        score += 30
    elif amount >= 100000:  # 10万以上
        score += 20
    elif amount >= 50000:  # 5万以上
        score += 10
    
    # 2. 对手方信息因子
    cp = item.get('counterparty', item.get('from_individual', ''))
    if cp and cp != '(无)' and cp != '(未知)' and len(cp) >= 2:
        # 有对手方信息，但如果是个人名字（2-4字汉字）加分
        import re
        if re.match(r'^[\u4e00-\u9fa5]{2,4}$', cp):
            score += 15  # 个人转账更可疑
        else:
            score += 10
    elif not cp or cp in ['(无)', '(未知)', 'nan']:
        score += 20  # 无对手方信息更可疑
    
    # 3. 交易频次因子（针对规律性收入和同源多次）
    occurrences = item.get('occurrences', item.get('count', 1))
    if occurrences >= 10:
        score += 15
    elif occurrences >= 5:
        score += 10
    elif occurrences >= 3:
        score += 5
    
    # 4. 风险等级因子
    risk_level = item.get('risk_level', 'medium')
    if risk_level == 'high':
        score += 20
    else:
        score += 10
    
    # 5. 类型特定调整
    if item_type == '来源不明收入':
        score += 10  # 来源不明总是更可疑
    elif item_type == '个人大额转入':
        score += 5
    
    # 限制在 0-100 范围
    return min(100, max(0, score))


def _generate_unique_key(person: str, counterparty: str, date, amount) -> str:
    """
    生成交易唯一标识
    
    Args:
        person: 人员名称
        counterparty: 对手方
        date: 日期
        amount: 金额
        
    Returns:
        唯一标识字符串
    """
    # 【P2修复】统一日期格式化
    date_str = utils.format_date_str(date) if date else 'unknown'
    # 金额四舍五入到百元，避免微小差异导致重复
    amount_key = int(round(float(amount) / 100) * 100) if amount else 0
    return f"{person}|{counterparty}|{date_str}|{amount_key}"


def _add_risk_entry(item: Dict, entry_type: str, item_type: str,
                    high_risk: List, medium_risk: List,
                    seen_transactions: set) -> None:
    """
    添加风险条目到对应列表
    
    Args:
        item: 原始条目
        entry_type: 条目类型（如'规律性非工资收入'）
        item_type: 项目类型（用于计算可信度）
        high_risk: 高风险列表
        medium_risk: 中风险列表
        seen_transactions: 已见交易集合
    """
    # 生成唯一标识 + 提取日期和描述
    date_value = None
    description = ''
    
    if entry_type == '规律性非工资收入':
        unique_key = f"{item['person']}|{item['counterparty']}|REGUL{int(item['total_amount'])}"
        description = f"共{item['occurrences']}次, 均额{item['avg_amount']:.0f}元, {item.get('possible_type', '')}"
        counterparty = item['counterparty']
        amount = item['total_amount']
        # 尝试从 date_range 获取第一个日期
        date_range = item.get('date_range')
        if date_range and isinstance(date_range, (list, tuple)) and len(date_range) > 0:
            date_value = date_range[0]
    elif entry_type == '个人大额转入':
        unique_key = _generate_unique_key(
            item['person'], item['from_individual'], item['date'], item['amount']
        )
        description = str(item.get('description', '')) if item.get('description') and str(item.get('description')) != 'nan' else '个人大额转入'
        counterparty = item['from_individual']
        amount = item['amount']
        date_value = item.get('date')
    elif entry_type == '来源不明收入':
        unique_key = _generate_unique_key(
            item['person'], item['counterparty'], item['date'], item['amount']
        )
        description = item.get('reason', '') or item.get('description', '') or '来源不明'
        counterparty = item['counterparty']
        amount = item['amount']
        date_value = item.get('date')
    elif entry_type == '大额单笔收入':
        unique_key = _generate_unique_key(
            item['person'], item['counterparty'], item['date'], item['amount']
        )
        description = item.get('income_type', '') or item.get('description', '') or '大额收入'
        counterparty = item['counterparty']
        amount = item['amount']
        date_value = item.get('date')
    elif entry_type == '同源多次收入':
        unique_key = f"{item['person']}|{item['counterparty']}|MUL{int(item['total'])}"
        description = f"共{item['count']}次, 均额{item['avg_amount']:.0f}元, {item.get('source_type', '')}"
        counterparty = item['counterparty']
        amount = item['total']
        # 尝试从 records 获取第一个日期
        records = item.get('records', [])
        if records and len(records) > 0:
            date_value = records[0].get('date')
    else:
        return
    
    # 去重
    if unique_key in seen_transactions:
        return
    seen_transactions.add(unique_key)
    
    # 创建条目 - 【修复】添加 date 和 description 字段，统一使用 source_row_index
    entry = {
        'type': entry_type,
        'person': item['person'],
        'counterparty': counterparty,
        'amount': amount,
        'date': date_value,  # 【修复】添加日期字段
        'description': description,  # 【修复】使用 description 替代 detail
        'detail': description,  # 保留旧字段兼容
        'risk_level': item['risk_level'],
        'confidence': _calculate_confidence_score(item, item_type),
        # 【P5 新增】复制追溯字段
        'account': item.get('account', ''),
        'bank': item.get('bank', ''),
        'source_file': item.get('source_file', f"cleaned_data/个人/{item['person']}_合并流水.xlsx"),
        # 【修复】统一使用 source_row_index 供前端显示
        'source_row_index': item.get('source_row_index', None),
        'source_row': item.get('source_row_index', None)  # 保留旧字段兼容
    }
    
    # 添加到对应列表
    if entry_type == '来源不明收入' or item['risk_level'] == 'high':
        high_risk.append(entry)
    else:
        medium_risk.append(entry)


def _classify_by_risk(results: Dict) -> tuple:
    """
    按风险等级分类汇总所有异常收入（增强版）
    
    新增功能：
    1. 去重 - 避免同一笔交易在多个类别中重复出现
    2. 可信度评分 - 每个项目增加 0-100 的可信度评分
    """
    high_risk = []
    medium_risk = []
    seen_transactions = set()
    
    # 规律性非工资收入
    for item in results.get('regular_non_salary', []):
        _add_risk_entry(item, '规律性非工资收入', '规律性非工资收入',
                      high_risk, medium_risk, seen_transactions)
    
    # 个人大额转入
    for item in results.get('large_individual_income', []):
        _add_risk_entry(item, '个人大额转入', '个人大额转入',
                      high_risk, medium_risk, seen_transactions)
    
    # 来源不明收入
    for item in results.get('unknown_source_income', []):
        _add_risk_entry(item, '来源不明收入', '来源不明收入',
                      high_risk, medium_risk, seen_transactions)
    
    # 大额单笔收入
    for item in results.get('large_single_income', []):
        _add_risk_entry(item, '大额单笔收入', '大额单笔收入',
                      high_risk, medium_risk, seen_transactions)
    
    # 同源多次收入
    for item in results.get('same_source_multi', []):
        _add_risk_entry(item, '同源多次收入', '同源多次收入',
                      high_risk, medium_risk, seen_transactions)
    
    # 按可信度+金额综合排序（可信度优先，金额次之）
    high_risk.sort(key=lambda x: (-x['confidence'], -x['amount']))
    medium_risk.sort(key=lambda x: (-x['confidence'], -x['amount']))
    
    logger.info(f'  风险分类: 高风险{len(high_risk)}项, 中风险{len(medium_risk)}项')
    logger.info(f'  去重效果: 已过滤{len(seen_transactions)}个唯一交易')
    return high_risk, medium_risk


def _write_report_header(f) -> None:
    """
    写入报告头部（含用途说明、逻辑依据、误判提示、复核重点）
    
    Args:
        f: 文件对象
    """
    f.write('异常收入来源分析报告（增强版）\n')
    f.write('='*60 + '\n')
    f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
    
    # 报告说明
    f.write('【报告用途】\n')
    f.write('本报告用于识别核心人员的异常收入来源，包括：\n')
    f.write('• 规律性非工资收入 - 非发薪单位的定期转入\n')
    f.write('• 个人大额转入 - 来自个人的≥5万元转入\n')
    f.write('• 来源不明收入 - 对手方信息缺失的大额收入\n')
    f.write('• 同源多次收入 - 同一来源多次转入且累计金额较大\n')
    f.write('• 疑似分期受贿 - 同一个人每月固定金额转入\n\n')
    
    f.write('【分析逻辑与规则】\n')
    f.write('1. 规律性非工资: 同一对手方≥3次转入，金额变异系CV<0.3，排除已知发薪单位\n')
    f.write('2. 个人大额转入: 来自2-4字汉字姓名的≥5万元收入\n')
    f.write('3. 来源不明: 对手方为空/nan且金额≥1万元\n')
    f.write('4. 同源多次: 同一对手方≥5次转入且累计≥1万元\n')
    f.write('5. 分期受贿: 个人每月转入≥1万元，持续≥4个月，CV<0.5\n\n')
    
    f.write('【可能的误判情况】\n')
    f.write('⚠ 理财产品到期、赎回可能被误识别为异常收入(已部分过滤)\n')
    f.write('⚠ 家庭成员间的资金往来可能被标记为疑似分期受贿\n')
    f.write('⚠ 兑职/商业投资收益可能产生误报\n')
    f.write('⚠ 港澳台同胞汇款可能被标记为来源不明\n\n')
    
    f.write('【人工复核重点】\n')
    f.write('★ 疑似分期受贿: 重点关注，核实统一转入者身份\n')
    f.write('★ 大额个人转入: 核实对手方与本人的关系\n')
    f.write('★ 来源不明: 调取银行原始凭证核实真实来源\n\n')
    
    f.write('='*60 + '\n\n')


def _write_summary_section(f, summary: Dict) -> None:
    """
    写入汇总统计部分
    
    Args:
        f: 文件对象
        summary: 汇总数据
    """
    f.write('一、汇总统计\n')
    f.write('-'*40 + '\n')
    for k, v in summary.items():
        f.write(f'{k}: {v}\n')
    f.write('\n')


def _write_high_risk_section(f, high_risk: List) -> None:
    """
    写入高风险项目部分
    
    Args:
        f: 文件对象
        high_risk: 高风险项目列表
    """
    f.write('★★★ 二、高风险项目（优先核查）★★★\n')
    f.write('='*40 + '\n')
    f.write('以下项目风险较高，建议优先核实\n')
    f.write('（可信度评分: 0-100分，分数越高越需关注）\n\n')
    f.write(f'共 {len(high_risk)} 条记录\n\n')
    for i, item in enumerate(high_risk, 1):
        confidence = item.get('confidence', 50)
        f.write(f"{i}. 【{item['type']}】{item['person']} ← {item['counterparty']} [可信度:{confidence}分]\n")
        f.write(f"   金额: {utils.format_currency(item['amount'])}\n")
        f.write(f"   详情: {item['detail']}\n")
        # 【P5 新增】追溯信息
        bank = item.get('bank', '')
        account = item.get('account', '')
        source_file = item.get('source_file', '')
        if bank or account:
            f.write(f"   ▶ 追溯: {bank} {account}\n")
        if source_file:
            f.write(f"   ▶ 文件: {source_file}\n")
    f.write('\n')


def _write_medium_risk_section(f, medium_risk: List) -> None:
    """
    写入中风险项目部分
    
    Args:
        f: 文件对象
        medium_risk: 中风险项目列表
    """
    f.write('三、中风险项目（参考信息）\n')
    f.write('-'*40 + '\n')
    f.write('以下项目需酌情关注\n\n')
    f.write(f'共 {len(medium_risk)} 条记录\n\n')
    for i, item in enumerate(medium_risk, 1):
        f.write(f"{i}. 【{item['type']}】{item['person']} ← {item['counterparty']}\n")
        f.write(f"   金额: {utils.format_currency(item['amount'])}\n")
    f.write('\n')


def _write_regular_non_salary_section(f, regular_non_salary: List) -> None:
    """
    写入规律性非工资收入部分
    
    Args:
        f: 文件对象
        regular_non_salary: 规律性非工资收入列表
    """
    f.write('四、规律性非工资收入\n')
    f.write('-'*40 + '\n')
    f.write(f'共 {len(regular_non_salary)} 条记录\n\n')
    for i, inc in enumerate(regular_non_salary, 1):
        f.write(f"{i}. 【{inc['risk_level'].upper()}】{inc['person']} ← {inc['counterparty']}\n")
        f.write(f"   共{inc['occurrences']}次, 均额{utils.format_currency(inc['avg_amount'])}, "
               f"合计{utils.format_currency(inc['total_amount'])}\n")
        f.write(f"   推测类型: {inc['possible_type']}\n")
    f.write('\n')


def _write_large_single_income_section(f, large_single_income: List) -> None:
    """
    写入大额单笔收入部分
    
    Args:
        f: 文件对象
        large_single_income: 大额单笔收入列表
    """
    f.write('五、大额单笔收入（≥10万元）\n')
    f.write('-'*40 + '\n')
    f.write(f'共 {len(large_single_income)} 条记录\n\n')
    for i, inc in enumerate(large_single_income, 1):
        date_str = inc['date'].strftime('%Y-%m-%d') if hasattr(inc['date'], 'strftime') else str(inc['date'])[:10]
        f.write(f"{i}. 【{inc['risk_level'].upper()}】{inc['person']} ← {inc['counterparty']}\n")
        f.write(f"   金额: {utils.format_currency(inc['amount'])} ({date_str})\n")
        f.write(f"   类型: {inc['income_type']}\n")
    f.write('\n')


def _write_same_source_multi_section(f, same_source_multi: List) -> None:
    """
    写入同源多次收入部分
    
    Args:
        f: 文件对象
        same_source_multi: 同源多次收入列表
    """
    f.write('六、同源多次收入\n')
    f.write('-'*40 + '\n')
    f.write(f'共 {len(same_source_multi)} 条记录\n\n')
    for i, inc in enumerate(same_source_multi, 1):
        f.write(f"{i}. 【{inc['risk_level'].upper()}】{inc['person']} ← {inc['counterparty']}\n")
        f.write(f"   共{inc['count']}次, 均额{utils.format_currency(inc['avg_amount'])}, "
               f"合计{utils.format_currency(inc['total'])}\n")
        f.write(f"   类型: {inc['source_type']}\n")
    f.write('\n')


def _write_large_individual_income_section(f, large_individual_income: List) -> None:
    """
    写入个人大额转入部分
    
    Args:
        f: 文件对象
        large_individual_income: 个人大额转入列表
    """
    f.write('七、来自个人的大额收入\n')
    f.write('-'*40 + '\n')
    f.write(f'共 {len(large_individual_income)} 条记录\n\n')
    for i, inc in enumerate(large_individual_income, 1):
        date_str = inc['date'].strftime('%Y-%m-%d') if hasattr(inc['date'], 'strftime') else str(inc['date'])[:10]
        f.write(f"{i}. {inc['person']} ← {inc['from_individual']}: "
               f"{utils.format_currency(inc['amount'])} ({date_str})\n")
    f.write('\n')


def _write_unknown_source_income_section(f, unknown_source_income: List) -> None:
    """
    写入来源不明收入部分
    
    Args:
        f: 文件对象
        unknown_source_income: 来源不明收入列表
    """
    f.write('八、来源不明的大额收入（重点核查）\n')
    f.write('-'*40 + '\n')
    f.write('【说明】这些交易的对手方信息在原始银行数据中缺失，需核实资金来源。\n')
    f.write('【追溯】每条记录包含账户和文件信息，便于在 Excel 中定位复核。\n\n')
    f.write(f'共 {len(unknown_source_income)} 条记录\n\n')
    for i, inc in enumerate(unknown_source_income, 1):
        date_str = inc['date'].strftime('%Y-%m-%d') if hasattr(inc['date'], 'strftime') else str(inc['date'])[:10]
        f.write(f"{i}. 【{inc['risk_level'].upper()}】{inc['person']}: "
               f"{utils.format_currency(inc['amount'])} ({date_str})\n")
        f.write(f"   原因: {inc['reason']}\n")
        desc = inc.get('description', '')
        if desc and desc != 'nan':
            f.write(f"   摘要: {desc[:50]}\n")
        # 【P5 新增】追溯信息
        bank = inc.get('bank', '')
        account = inc.get('account', '')
        source_file = inc.get('source_file', '')
        if bank or account:
            f.write(f"   ▶ 追溯: {bank} {account}\n")
        if source_file:
            f.write(f"   ▶ 文件: {source_file}\n")
    f.write('\n')


def generate_suspicious_income_report(results: Dict, output_dir: str) -> str:
    """生成异常收入分析报告（增强版）"""
    import os
    report_path = os.path.join(output_dir, '异常收入来源分析报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        # 写入报告头部
        _write_report_header(f)
        
        # 写入汇总统计
        _write_summary_section(f, results['summary'])
        
        # 写入高风险项目
        if results.get('high_risk'):
            _write_high_risk_section(f, results['high_risk'])
        
        # 写入中风险项目
        if results.get('medium_risk'):
            _write_medium_risk_section(f, results['medium_risk'])
        
        # 写入详细分类
        f.write('='*60 + '\n')
        f.write('以下为各类型异常收入详细明细\n')
        f.write('='*60 + '\n\n')
        
        # 规律性非工资收入
        if results.get('regular_non_salary'):
            _write_regular_non_salary_section(f, results['regular_non_salary'])
        
        # 大额单笔收入
        if results.get('large_single_income'):
            _write_large_single_income_section(f, results['large_single_income'])
        
        # 同源多次收入
        if results.get('same_source_multi'):
            _write_same_source_multi_section(f, results['same_source_multi'])
        
        # 个人大额转入
        if results.get('large_individual_income'):
            _write_large_individual_income_section(f, results['large_individual_income'])
        
        # 来源不明收入
        if results.get('unknown_source_income'):
            _write_unknown_source_income_section(f, results['unknown_source_income'])
        
        # 【新增】疑似分期受贿
        if results.get('potential_bribe_installment'):
            _write_potential_bribe_section(f, results['potential_bribe_installment'])
    
    logger.info(f'异常收入分析报告已生成: {report_path}')
    return report_path


def _write_potential_bribe_section(f, bribe_items: List[Dict]) -> None:
    """写入疑似分期受贿部分"""
    f.write('\n')
    f.write('★★★ 重点关注：疑似分期受贿（高风险）★★★\n')
    f.write('-'*60 + '\n')
    f.write('【特征】从同一个人（非发薪单位）处每月收到固定金额\n')
    f.write('【风险】此类收入可能是分期受贿、利益输送或掩盖性质的款项\n\n')
    
    f.write(f'共 {len(bribe_items)} 条记录\n\n')
    for i, item in enumerate(bribe_items, 1):
        f.write(f'{i}. 【{item["risk_level"].upper()}】{item["person"]} ← {item["counterparty"]}\n')
        f.write(f'   金额: 月均 {item["avg_amount"]/10000:.2f}万 (波动系数: {item["cv"]:.2f})\n')
        f.write(f'   时间: {item["months"]}个月, 共{item["occurrences"]}笔\n')
        f.write(f'   总额: {item["total_amount"]/10000:.2f}万\n')
        f.write(f'   风险因素: {item["risk_factors"]}\n\n')


def _detect_potential_bribe_installment(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    min_occurrences: int = 4,  # 至少4次
    min_amount: float = 10000,  # 至少1万元/次
    max_cv: float = 0.5        # 金额波动系数 ≤ 0.5
) -> List[Dict]:
    """
    检测疑似分期受贿
    
    【核心逻辑】
    从同一个人（非发薪单位）处每月收到固定金额，可能是：
    - 分期受贿
    - 约定的利益输送
    - 隐蔽的咨询费/介绍费
    
    【排除条件】
    1. 排除已知发薪单位
    2. 排除金融机构/政府机关
    3. 排除对手方是公司（注册组织）
    4. 只关注对手方是个人姓名（2-4个汉字）
    
    【高风险特征】
    1. 金额稳定（CV < 0.5）
    2. 频率规律（月度）
    3. 对手方是个人
    4. 金额较大（> 1万/月）
    
    Args:
        all_transactions: 所有交易数据
        core_persons: 核心人员列表
        min_occurrences: 最少出现次数
        min_amount: 最低金额阈值
        max_cv: 最大变异系数
        
    Returns:
        疑似分期受贿列表
    """
    import re
    
    suspicious_items = []
    
    # 排除关键词
    EXCLUDE_KEYWORDS = (
        config.SALARY_STRONG_KEYWORDS +
        config.KNOWN_SALARY_PAYERS +
        config.USER_DEFINED_SALARY_PAYERS +
        config.WEALTH_MANAGEMENT_KEYWORDS +
        config.GOVERNMENT_AGENCY_KEYWORDS +
        ['银行', '公司', '有限', '集团', '股份', '合伙', '基金', '证券', 
         '保险', '信托', '投资', '理财', '资产', '管理']
    )
    
    for person in core_persons:
        for key, df in all_transactions.items():
            if person not in key or '公司' in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            # 只分析收入
            income_df = df[df['income'] >= min_amount].copy()
            if income_df.empty:
                continue
            
            # 按对手方分组
            for cp in income_df['counterparty'].unique():
                cp_str = str(cp).strip()
                
                # 跳过无效对手方
                if not cp_str or cp_str == 'nan' or len(cp_str) < 2:
                    continue
                
                # 跳过自己
                if cp_str == person or cp_str in core_persons:
                    continue
                
                # 【关键】只关注个人姓名（2-4个汉字）
                if not re.match(r'^[\u4e00-\u9fa5]{2,4}$', cp_str):
                    continue
                
                # 排除已知机构/发薪单位
                if utils.contains_keywords(cp_str, EXCLUDE_KEYWORDS):
                    continue
                
                cp_df = income_df[income_df['counterparty'] == cp].copy()
                
                if len(cp_df) < min_occurrences:
                    continue
                
                # 计算统计特征
                cp_df = cp_df.sort_values('date')
                dates = cp_df['date'].tolist()
                amounts = cp_df['income'].tolist()
                
                # 计算月份跨度
                months = set(d.strftime('%Y-%m') for d in dates)
                
                # 需要至少跨4个月
                if len(months) < 4:
                    continue
                
                # 计算平均间隔
                if len(dates) >= 2:
                    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                    avg_interval = sum(intervals) / len(intervals)
                else:
                    avg_interval = 0
                
                # 计算金额稳定性
                mean_amount = sum(amounts) / len(amounts)
                variance = sum((x - mean_amount) ** 2 for x in amounts) / len(amounts)
                std_amount = variance ** 0.5
                cv = std_amount / mean_amount if mean_amount > 0 else 999
                
                # 【核心判断条件】
                # 1. 金额稳定（CV < 0.5）
                # 2. 月度规律（间隔20-40天）
                # 3. 金额较大（月均 > 1万）
                is_stable = cv < max_cv
                is_monthly = 20 <= avg_interval <= 40
                is_significant = mean_amount >= min_amount
                
                if is_stable and is_significant:
                    # 计算风险等级
                    risk_factors = []
                    risk_score = 0
                    
                    if cv < 0.2:
                        risk_factors.append('金额极其稳定')
                        risk_score += 3
                    elif cv < 0.3:
                        risk_factors.append('金额非常稳定')
                        risk_score += 2
                    else:
                        risk_factors.append('金额相对稳定')
                        risk_score += 1
                    
                    if is_monthly:
                        risk_factors.append('月度规律明显')
                        risk_score += 2
                    
                    if mean_amount >= 50000:
                        risk_factors.append('金额超过5万/月')
                        risk_score += 3
                    elif mean_amount >= 20000:
                        risk_factors.append('金额超过2万/月')
                        risk_score += 2
                    
                    if len(months) >= 12:
                        risk_factors.append('持续时间超过1年')
                        risk_score += 2
                    elif len(months) >= 6:
                        risk_factors.append('持续时间超过半年')
                        risk_score += 1
                    
                    # 检查摘要是否有可疑特征
                    suspicious_desc_keywords = ['咨询', '介绍', '感谢', '借', '还', '费']
                    for idx in cp_df.index:
                        desc = str(cp_df.loc[idx, 'description'])
                        if utils.contains_keywords(desc, suspicious_desc_keywords):
                            risk_factors.append(f'摘要可疑: {desc[:20]}')
                            risk_score += 1
                            break
                    
                    risk_level = 'high' if risk_score >= 5 else 'medium'
                    
                    suspicious_items.append({
                        'person': person,
                        'counterparty': cp_str,
                        'occurrences': len(cp_df),
                        'months': len(months),
                        'avg_amount': mean_amount,
                        'total_amount': sum(amounts),
                        'avg_interval_days': avg_interval,
                        'cv': cv,
                        'risk_level': risk_level,
                        'risk_score': risk_score,
                        'risk_factors': '; '.join(risk_factors),
                        'first_date': min(dates),
                        'last_date': max(dates),
                        # 【溯源铁律】原始文件和行号
                        'source_file': f'cleaned_data/个人/{person}_合并流水.xlsx',
                        'source_row_index': cp_df.iloc[0].get('source_row_index', None)  # 取第一条记录
                    })
    
    # 按风险分排序
    suspicious_items.sort(key=lambda x: (-x['risk_score'], -x['total_amount']))
    
    # Rename suspicious_items to bribe_items for consistency with the user's provided log message
    bribe_items = suspicious_items 
    logger.info(f'检测到 {len(bribe_items)} 个疑似分期受贿模式')
    for item in bribe_items[:3]:
        logger.warning(f'    ★ [{item["risk_level"].upper()}] {item["person"]} ← {item["counterparty"]}: '
                      f'月均{item["avg_amount"]/10000:.2f}万, 持续{item["months"]}个月')
    
    return bribe_items


# ========== Phase 2: 大额交易明细提取 (2026-01-20 新增) ==========

def extract_large_transactions(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    threshold: float = 10000
) -> List[Dict]:
    """
    提取大额交易明细
    
    【Phase 2 - 2026-01-20】
    功能:
    1. 从所有核心人员的交易中提取大额交易(默认≥1万元)
    2. 返回完整的表格字段结构,用于报告生成
    3. 按金额降序排列
    4. 自动判断风险等级
    
    Args:
        all_transactions: 所有交易数据字典 {person_name: DataFrame}
        core_persons: 核心人员列表
        threshold: 大额交易阈值(默认10000元)
        
    Returns:
        大额交易列表,每笔交易包含:
        - person: 人员姓名
        - date: 交易日期
        - amount: 交易金额
        - direction: 交易方向(income/expense)
        - counterparty: 对手方
        - description: 交易摘要
        - account_number: 账号(部分隐藏)
        - bank_name: 银行名称
        - risk_level: 风险等级(low/medium/high)
    """
    logger.info(f'正在提取大额交易(阈值: {utils.format_currency(threshold)})...')
    
    large_transactions = []
    
    for person in core_persons:
        if person not in all_transactions:
            continue
        
        df = all_transactions[person]
        
        if df.empty:
            continue
        
        for _, row in df.iterrows():
            income = row.get('income', 0) or 0
            expense = row.get('expense', 0) or 0
            amount = max(income, expense)
            
            # 只提取大额交易
            if amount < threshold:
                continue
            
            # 判断交易方向
            direction = 'income' if income > 0 else 'expense'
            
            # 获取账号信息
            account_number = str(row.get('account_number', ''))
            if account_number and account_number not in ['', 'nan', 'None']:
                # 部分隐藏账号
                if len(account_number) > 8:
                    account_masked = account_number[:4] + '****' + account_number[-4:]
                else:
                    account_masked = account_number[:2] + '****' + account_number[-2:]
            else:
                account_masked = '未知'
            
            # 获取银行名称
            bank_name = str(row.get('银行来源', row.get('所属银行', '未知'))).strip()
            if bank_name in ['', 'nan', 'None']:
                bank_name = '未知'
            
            # 获取对手方
            counterparty = str(row.get('counterparty', '未知')).strip()
            if counterparty in ['', 'nan', 'None', '\\N']:
                counterparty = '未知'
            
            # 获取交易摘要
            description = str(row.get('description', '')).strip()
            if description in ['', 'nan', 'None']:
                description = '无'
            
            # 判断风险等级
            risk_level = _determine_transaction_risk_level(
                amount, direction, counterparty, description
            )
            
            # 构建交易记录
            transaction = {
                'person': person,
                'date': row['date'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['date']) else '未知',
                'amount': float(amount),
                'direction': direction,
                'counterparty': counterparty,
                'description': description,
                'account_number': account_masked,
                'bank_name': bank_name,
                'risk_level': risk_level
            }
            
            large_transactions.append(transaction)
    
    # 按金额降序排列
    large_transactions.sort(key=lambda x: x['amount'], reverse=True)
    
    logger.info(f'提取完成: 共{len(large_transactions)}笔大额交易')
    
    # 统计信息
    if large_transactions:
        total_amount = sum(t['amount'] for t in large_transactions)
        high_risk_count = sum(1 for t in large_transactions if t['risk_level'] == 'high')
        logger.info(f'大额交易总额: {utils.format_currency(total_amount)}, 高风险: {high_risk_count}笔')
    
    return large_transactions


def _determine_transaction_risk_level(
    amount: float,
    direction: str,
    counterparty: str,
    description: str
) -> str:
    """
    判断交易风险等级
    
    Args:
        amount: 交易金额
        direction: 交易方向
        counterparty: 对手方
        description: 交易摘要
        
    Returns:
        风险等级: 'low', 'medium', 'high'
    """
    # 高风险特征
    high_risk_keywords = ['现金', '取现', '存现', '个人', '未知', '借款', '还款']
    
    # 低风险特征
    low_risk_keywords = ['工资', '代发', '社保', '公积金', '退休金', '养老金']
    
    # 判断逻辑
    risk_score = 0
    
    # 1. 金额因素
    if amount >= 100000:  # ≥10万
        risk_score += 3
    elif amount >= 50000:  # ≥5万
        risk_score += 2
    else:  # 1-5万
        risk_score += 1
    
    # 2. 对手方因素
    if counterparty in ['未知', '']:
        risk_score += 2
    elif is_individual_name(counterparty):
        risk_score += 1
    
    # 3. 摘要关键词
    desc_lower = description.lower()
    if any(keyword in desc_lower for keyword in high_risk_keywords):
        risk_score += 2
    elif any(keyword in desc_lower for keyword in low_risk_keywords):
        risk_score -= 2
    
    # 4. 收入方向的个人转账更可疑
    if direction == 'income' and is_individual_name(counterparty):
        risk_score += 1
    
    # 综合判断
    if risk_score >= 5:
        return 'high'
    elif risk_score >= 3:
        return 'medium'
    else:
        return 'low'
