#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对手方判断工具模块

提供统一的对手方排除逻辑和理财产品识别功能，
消除 income_analyzer.py 和 loan_analyzer.py 中的代码重复。

创建日期: 2026-01-11
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

import config
import utils


class ExclusionContext(Enum):
    """排除判断的上下文场景"""
    BIDIRECTIONAL = "bidirectional"      # 双向资金往来检测
    LOAN_PATTERN = "loan_pattern"        # 借贷模式判断
    LOAN_PAIRS = "loan_pairs"            # 借贷配对分析
    NO_REPAYMENT = "no_repayment"        # 无还款借贷检测
    INCOME_REGULAR = "income_regular"     # 规律性收入检测
    INCOME_UNKNOWN = "income_unknown"     # 来源不明检测


@dataclass
class WealthIdentificationResult:
    """理财产品识别结果"""
    is_wealth: bool
    reason: str = ""
    confidence: str = "low"  # low, medium, high


def _get_base_exclusion_keywords() -> List[str]:
    """
    获取所有场景通用的基础排除关键词
    
    Returns:
        基础排除关键词列表
    """
    return (
        config.THIRD_PARTY_PAYMENT_KEYWORDS +
        config.KNOWN_SALARY_PAYERS +
        config.USER_DEFINED_SALARY_PAYERS
    )


def _get_wealth_exclusion_keywords() -> List[str]:
    """
    获取理财产品相关排除关键词
    
    Returns:
        理财产品排除关键词列表
    """
    return (
        config.WEALTH_PRODUCT_COUNTERPARTY_KEYWORDS +
        config.WEALTH_MANAGEMENT_KEYWORDS
    )


def _get_institution_keywords() -> List[str]:
    """
    获取机构/公司相关关键词
    
    Returns:
        机构关键词列表
    """
    return ['公司', '有限', '集团', '银行']


def _get_bank_system_keywords() -> List[str]:
    """
    获取银行系统账户关键词
    
    Returns:
        银行系统关键词列表
    """
    return ['代付', '代收', '业务专户', '清算', '头寸', '备付', '研究所', '研究院']


def should_exclude_counterparty_base(
    cp: str, 
    person: str, 
    core_persons: List[str]
) -> bool:
    """
    基础对手方排除检查（适用于所有场景）
    
    Args:
        cp: 对手方名称
        person: 当前人员
        core_persons: 核心人员列表
        
    Returns:
        是否应该排除
    """
    # 1. 空值或无效值
    if not cp or cp == 'nan' or len(cp) < 2:
        return True
    
    # 2. 自己转自己
    if cp == person or cp in core_persons:
        return True
    
    # 3. 第三方支付平台
    if utils.contains_keywords(cp, config.THIRD_PARTY_PAYMENT_KEYWORDS):
        return True
    
    return False


def should_exclude_counterparty(
    cp: str,
    person: str,
    core_persons: List[str],
    context: ExclusionContext
) -> bool:
    """
    统一的对手方排除检查函数
    
    根据不同的上下文场景，应用不同的排除规则。
    
    Args:
        cp: 对手方名称
        person: 当前人员
        core_persons: 核心人员列表
        context: 排除判断的上下文场景
        
    Returns:
        是否应该排除
    """
    # 基础排除检查
    if should_exclude_counterparty_base(cp, person, core_persons):
        return True
    
    # 根据场景应用额外规则
    if context == ExclusionContext.BIDIRECTIONAL:
        # 双向资金往来：排除发薪单位
        if utils.contains_keywords(cp, config.KNOWN_SALARY_PAYERS):
            return True
        if utils.contains_keywords(cp, config.USER_DEFINED_SALARY_PAYERS):
            return True
            
    elif context == ExclusionContext.LOAN_PATTERN:
        # 借贷模式判断：排除理财、政府、公司
        if utils.contains_keywords(cp, _get_wealth_exclusion_keywords()):
            return True
        if utils.contains_keywords(cp, config.GOVERNMENT_AGENCY_KEYWORDS):
            return True
        if utils.contains_keywords(cp, _get_institution_keywords()):
            return True
            
    elif context == ExclusionContext.LOAN_PAIRS:
        # 借贷配对分析：排除发薪、机构、银行系统、理财
        if utils.contains_keywords(cp, config.SALARY_STRONG_KEYWORDS):
            return True
        if utils.contains_keywords(cp, config.KNOWN_SALARY_PAYERS):
            return True
        if utils.contains_keywords(cp, config.USER_DEFINED_SALARY_PAYERS):
            return True
        if utils.contains_keywords(cp, _get_institution_keywords()):
            return True
        if utils.contains_keywords(cp, _get_bank_system_keywords()):
            return True
        if utils.contains_keywords(cp, _get_wealth_exclusion_keywords()):
            return True
            
    elif context == ExclusionContext.NO_REPAYMENT:
        # 无还款借贷：排除发薪、机构、银行系统、理财、政府
        if utils.contains_keywords(cp, config.SALARY_STRONG_KEYWORDS):
            return True
        if utils.contains_keywords(cp, config.KNOWN_SALARY_PAYERS):
            return True
        if utils.contains_keywords(cp, config.USER_DEFINED_SALARY_PAYERS):
            return True
        if utils.contains_keywords(cp, _get_institution_keywords()):
            return True
        if utils.contains_keywords(cp, _get_bank_system_keywords()):
            return True
        if utils.contains_keywords(cp, _get_wealth_exclusion_keywords()):
            return True
        if utils.contains_keywords(cp, config.GOVERNMENT_AGENCY_KEYWORDS):
            return True
            
    elif context == ExclusionContext.INCOME_REGULAR:
        # 规律性收入：排除工资、银行理财、第三方支付
        salary_exclusion = (
            config.SALARY_KEYWORDS + 
            config.SALARY_STRONG_KEYWORDS + 
            ['社保', '公积金', '养老', '医保', '失业', '工伤',
             '住房', '补贴', '津贴', '奖金', '绩效', '年终',
             '利息', '分红', '股息', '理财', '赎回', '到期']
        )
        if utils.contains_keywords(cp, salary_exclusion):
            return True
        if utils.contains_keywords(cp, config.HR_COMPANY_KEYWORDS):
            return True
        if utils.contains_keywords(cp, ['银行', '理财', '基金', '证券', '信托', '保险', '资产']):
            return True
            
    elif context == ExclusionContext.INCOME_UNKNOWN:
        # 来源不明检测：排除政府机关
        if utils.contains_keywords(cp, config.GOVERNMENT_AGENCY_KEYWORDS):
            return True
    
    return False


def identify_wealth_management_transaction(
    desc: str, 
    amount: float,
    counterparty: str = "",
    require_high_confidence: bool = False
) -> WealthIdentificationResult:
    """
    统一的理财产品识别函数
    
    合并了原来的 _is_wealth_management_transaction 和 _should_exclude_large_income 功能，
    提供更精确的理财产品识别。
    
    Args:
        desc: 交易摘要
        amount: 交易金额
        counterparty: 对手方（可选）
        require_high_confidence: 是否要求高可信度才返回True
        
    Returns:
        WealthIdentificationResult 包含识别结果、原因和可信度
    """
    desc = str(desc) if desc else ""
    counterparty = str(counterparty) if counterparty else ""
    
    # ========== 高可信度规则（明确的理财交易）==========
    
    # 规则1: 摘要中直接包含强理财关键词
    WEALTH_STRONG_KEYWORDS = [
        '赎回', '到期', '本息', '理财', '结息', '基金赎回', '基金申购',
        '活期宝', '余额宝', '天天宝', '如意宝', '银证转账', '证转银', '银转证',
        '定期到期', '本息转活', '约定定期'
    ]
    if utils.contains_keywords(desc, WEALTH_STRONG_KEYWORDS):
        return WealthIdentificationResult(True, '摘要含强理财关键词', 'high')
    
    # 规则1b: 对手方包含"证券"关键词（证券转账）
    if counterparty and ('证券' in counterparty or '证劵' in counterparty):
        if '转银' in desc or '转出' in desc or '转账' in desc:
            return WealthIdentificationResult(True, '证券转银行', 'high')
    
    # 规则2: 匹配知名理财产品白名单
    if utils.contains_keywords(desc, config.KNOWN_WEALTH_PRODUCTS):
        return WealthIdentificationResult(True, '匹配知名理财产品白名单', 'high')
    
    # 规则3: 对手方是理财产品
    if counterparty and utils.contains_keywords(counterparty, config.WEALTH_PRODUCT_COUNTERPARTY_KEYWORDS):
        return WealthIdentificationResult(True, '对手方为理财产品', 'high')
    
    # ========== 中可信度规则（较可能是理财交易）==========
    
    # 规则4: 扩展理财关键词
    WEALTH_MEDIUM_KEYWORDS = [
        '转存', '分红', '收益', '转活', '提现', '银证', '定期',
        '添利', '安心计划', 'T计划', '安存宝', '碧乐活', '新客理财',
        '持有期', '固收', '稳享', '中短债', '日开',
        '基金代码', '申购撤销', '基金转换', '份额', '认购'
    ]
    if utils.contains_keywords(desc, WEALTH_MEDIUM_KEYWORDS):
        return WealthIdentificationResult(True, '摘要含理财关键词', 'medium')
    
    # 规则5: 纯数字摘要（1-4位）- 银行内部理财产品代码
    if desc:
        desc_clean = desc.strip()
        if re.match(r'^\d{1,4}$', desc_clean):
            return WealthIdentificationResult(True, f'数字代码({desc_clean})疑似理财产品', 'medium')
    
    # 规则6: 摘要以产品编号开头 (如 "5811221079交银理财")
    if desc and re.match(r'^\d{6,}', desc):
        return WealthIdentificationResult(True, '产品编号格式', 'medium')
    
    # 规则7: 理财产品代码前缀
    if desc and re.match(r'^(WMY|EW|TZ|LCT|YEB)\d+', desc, re.IGNORECASE):
        return WealthIdentificationResult(True, '理财产品代码前缀', 'medium')
    
    # ========== 低可信度规则（可能是理财，需谨慎）==========
    
    min_amount = config.WEALTH_IDENTIFICATION_MIN_AMOUNT
    amount_unit = config.WEALTH_ROUND_AMOUNT_UNIT
    
    # 规则8: 整万金额 + 无对手方信息（可能是理财本金赎回）
    # 注意：这个规则可能过度排除，所以设为低可信度
    if amount >= min_amount and amount % amount_unit == 0:
        if not counterparty or counterparty == 'nan' or len(counterparty) < 2:
            return WealthIdentificationResult(True, '整万金额无对手方(疑似理财本金赎回)', 'low')
    
    # 规则9: 金额含利息尾数模式（非整万金额 + 无对手方）
    # 注意：同样设为低可信度，以允许更细致的人工审查
    if amount >= min_amount and (not counterparty or counterparty == 'nan' or len(counterparty) < 2):
        remainder = amount % amount_unit
        if remainder > 0:
            return WealthIdentificationResult(True, '金额含利息尾数(疑似本息)', 'low')
    
    # 未匹配任何规则
    return WealthIdentificationResult(False, '', '')


def is_wealth_management_transaction(
    desc: str, 
    amount: float,
    counterparty: str = "",
    min_confidence: str = "low"
) -> Tuple[bool, str]:
    """
    判断交易是否为理财产品相关交易（兼容旧接口）
    
    Args:
        desc: 交易摘要
        amount: 交易金额
        counterparty: 对手方（可选）
        min_confidence: 最低可信度要求 ("low", "medium", "high")
        
    Returns:
        (是否为理财交易, 原因)
    """
    result = identify_wealth_management_transaction(desc, amount, counterparty)
    
    if not result.is_wealth:
        return False, ''
    
    # 根据可信度要求过滤
    confidence_levels = {'low': 0, 'medium': 1, 'high': 2}
    required_level = confidence_levels.get(min_confidence, 0)
    actual_level = confidence_levels.get(result.confidence, 0)
    
    if actual_level >= required_level:
        return True, result.reason
    else:
        return False, ''


def should_exclude_large_income(desc: str, cp: str, income: float) -> bool:
    """
    判断是否应该排除这笔大额收入（兼容旧接口）
    
    Args:
        desc: 交易摘要
        cp: 对手方
        income: 收入金额
        
    Returns:
        是否应该排除
    """
    # 排除工资奖金
    if utils.contains_keywords(desc, config.SALARY_STRONG_KEYWORDS):
        return True
    if utils.contains_keywords(cp, config.KNOWN_SALARY_PAYERS):
        return True
    if utils.contains_keywords(cp, config.USER_DEFINED_SALARY_PAYERS):
        return True
    
    # 理财产品识别
    # 使用中等可信度要求，避免过度排除
    is_wealth, _ = is_wealth_management_transaction(desc, income, cp, min_confidence="medium")
    return is_wealth


def is_individual_name(name: str) -> bool:
    """
    判断名称是否为个人姓名（2-4个汉字）
    
    Args:
        name: 名称字符串
        
    Returns:
        是否为个人姓名格式
    """
    if not name:
        return False
    return bool(re.match(r'^[\u4e00-\u9fa5]{2,4}$', name))
