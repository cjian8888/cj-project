#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险评分引擎（新增模块 - 2026-01-11）

【模块定位】
统一管理多维度风险评分逻辑，实现：
1. 交易级风险评分 - 每笔交易的可疑程度
2. 对手方风险评分 - 对手方的风险画像
3. 账户级风险评分 - 账户整体风险水平
4. 人员级风险评分 - 核心人员综合风险

【审计价值】
- 将5000条可疑交易按风险分排序
- 审计人员直接从Top 10开始核查
- 避免"所有线索都重要=所有线索都不重要"

【评分体系】
- 0-30分: 低风险（可忽略）
- 30-50分: 中风险（需关注）
- 50-70分: 高风险（优先核查）
- 70-100分: 极高风险（立即核查）
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import re

import config
import utils

logger = utils.setup_logger(__name__)


# ============================================================
# 风险评分配置（可在config.py中覆盖）
# ============================================================

RISK_SCORE_WEIGHTS = {
    # 金额维度权重
    'amount': {
        'weight': 0.25,
        'thresholds': {
            50000: 10,      # 5万+
            100000: 20,     # 10万+
            500000: 30,     # 50万+
            1000000: 40     # 100万+
        }
    },
    # 对手方维度权重
    'counterparty': {
        'weight': 0.20,
        'unknown': 30,      # 对手方信息缺失
        'individual': 20,   # 个人转账
        'known_risky': 40,  # 已知高风险对手方
        'normal': 5         # 正常机构
    },
    # 时间维度权重
    'time': {
        'weight': 0.15,
        'holiday': 20,      # 节假日交易
        'night': 15,        # 深夜交易
        'weekend': 10       # 周末交易
    },
    # 频率维度权重
    'frequency': {
        'weight': 0.15,
        'high_frequency': 25,   # 高频交易
        'regular_pattern': 20,  # 规律性模式
        'sudden_spike': 30      # 突然激增
    },
    # 摘要维度权重
    'description': {
        'weight': 0.15,
        'empty': 15,            # 无摘要
        'cash': 20,             # 现金交易
        'suspicious_keywords': 25  # 可疑关键词
    },
    # 关联维度权重
    'correlation': {
        'weight': 0.10,
        'self_transfer': 10,    # 自我转账
        'related_party': 20,    # 关联方交易
        'fund_cycle': 40        # 资金闭环
    }
}

# 可疑关键词列表
SUSPICIOUS_DESCRIPTION_KEYWORDS = [
    '借款', '借入', '还款', '利息', '佣金', '回扣', '好处',
    '感谢', '咨询', '顾问', '服务费', '中介', '介绍'
]

# 已知高风险对手方模式
HIGH_RISK_COUNTERPARTY_PATTERNS = [
    r'.*小额贷款.*',
    r'.*典当.*',
    r'.*赌.*',
    r'.*博彩.*',
    r'.*投资咨询.*'
]


def _get_weighted_score_ceiling() -> float:
    """
    计算加权分理论上限，用于把当前分值归一化到 0-100。
    """
    amount_max = max(RISK_SCORE_WEIGHTS["amount"]["thresholds"].values())
    counterparty_max = max(
        RISK_SCORE_WEIGHTS["counterparty"]["unknown"],
        RISK_SCORE_WEIGHTS["counterparty"]["individual"],
        RISK_SCORE_WEIGHTS["counterparty"]["known_risky"],
        RISK_SCORE_WEIGHTS["counterparty"]["normal"],
    )
    time_max = (
        RISK_SCORE_WEIGHTS["time"]["holiday"]
        + RISK_SCORE_WEIGHTS["time"]["night"]
        + RISK_SCORE_WEIGHTS["time"]["weekend"]
    )
    description_max = max(
        RISK_SCORE_WEIGHTS["description"]["empty"],
        RISK_SCORE_WEIGHTS["description"]["cash"],
        RISK_SCORE_WEIGHTS["description"]["suspicious_keywords"],
    )
    correlation_max = RISK_SCORE_WEIGHTS["correlation"]["related_party"]

    weighted_ceiling = (
        amount_max * RISK_SCORE_WEIGHTS["amount"]["weight"]
        + counterparty_max * RISK_SCORE_WEIGHTS["counterparty"]["weight"]
        + time_max * RISK_SCORE_WEIGHTS["time"]["weight"]
        + description_max * RISK_SCORE_WEIGHTS["description"]["weight"]
        + correlation_max * RISK_SCORE_WEIGHTS["correlation"]["weight"]
    )
    return weighted_ceiling if weighted_ceiling > 0 else 1.0


WEIGHTED_SCORE_CEILING = _get_weighted_score_ceiling()


# ============================================================
# 辅助函数
# ============================================================

def _is_cash_transaction(row: pd.Series) -> bool:
    """
    【铁律实现】判断交易是否为现金交易
    
    优先级：
    1. is_cash 列（布尔类型，data_cleaner 内存中的格式）
    2. 现金 列（字符串 '是'，从 Excel 读取时的格式）
    3. 降级：使用关键词匹配（最后手段）
    """
    # 优先读取已计算的列
    if 'is_cash' in row.index:
        return row['is_cash'] == True
    if '现金' in row.index:
        return row['现金'] == '是'
    
    # 降级：关键词匹配
    desc = str(row.get('description', '')).lower()
    return utils.contains_keywords(desc, config.CASH_KEYWORDS)


# ============================================================
# 交易级风险评分
# ============================================================

def score_transaction(
    row: pd.Series,
    counterparty_risk_map: Dict[str, float] = None,
    is_core_person_transfer: bool = False
) -> Dict:
    """
    计算单笔交易的风险评分
    
    Args:
        row: 交易记录行
        counterparty_risk_map: 对手方风险映射
        is_core_person_transfer: 是否核心人员间转账
        
    Returns:
        风险评分详情
    """
    scores = {}
    total_score = 0
    
    # 1. 金额评分
    amount = max(row.get('income', 0) or 0, row.get('expense', 0) or 0)
    amount_score = 0
    for threshold, score in sorted(RISK_SCORE_WEIGHTS['amount']['thresholds'].items()):
        if amount >= threshold:
            amount_score = score
    scores['amount'] = amount_score
    total_score += amount_score * RISK_SCORE_WEIGHTS['amount']['weight']
    
    # 2. 对手方评分
    cp = str(row.get('counterparty', ''))
    cp_score = RISK_SCORE_WEIGHTS['counterparty']['normal']
    
    if not cp or cp == 'nan' or len(cp) < 2:
        cp_score = RISK_SCORE_WEIGHTS['counterparty']['unknown']
    elif re.match(r'^[\u4e00-\u9fa5]{2,4}$', cp):
        cp_score = RISK_SCORE_WEIGHTS['counterparty']['individual']
    elif any(re.match(p, cp) for p in HIGH_RISK_COUNTERPARTY_PATTERNS):
        cp_score = RISK_SCORE_WEIGHTS['counterparty']['known_risky']
    elif counterparty_risk_map and cp in counterparty_risk_map:
        cp_score = counterparty_risk_map[cp]
    
    scores['counterparty'] = cp_score
    total_score += cp_score * RISK_SCORE_WEIGHTS['counterparty']['weight']
    
    # 3. 时间评分
    time_score = 0
    date = row.get('date')
    if date:
        try:
            if hasattr(date, 'hour'):
                hour = date.hour
                if hour >= 22 or hour <= 6:
                    time_score += RISK_SCORE_WEIGHTS['time']['night']
            if hasattr(date, 'weekday'):
                if date.weekday() >= 5:
                    time_score += RISK_SCORE_WEIGHTS['time']['weekend']
        except (AttributeError, TypeError):
            pass
    scores['time'] = time_score
    total_score += time_score * RISK_SCORE_WEIGHTS['time']['weight']
    
    # 4. 摘要评分
    desc = str(row.get('description', ''))
    desc_score = 0
    
    if not desc or desc == 'nan':
        desc_score = RISK_SCORE_WEIGHTS['description']['empty']
    elif _is_cash_transaction(row):
        desc_score = RISK_SCORE_WEIGHTS['description']['cash']
    elif utils.contains_keywords(desc, SUSPICIOUS_DESCRIPTION_KEYWORDS):
        desc_score = RISK_SCORE_WEIGHTS['description']['suspicious_keywords']
    
    scores['description'] = desc_score
    total_score += desc_score * RISK_SCORE_WEIGHTS['description']['weight']
    
    # 5. 关联评分
    correlation_score = 0
    if is_core_person_transfer:
        correlation_score = RISK_SCORE_WEIGHTS['correlation']['related_party']
    
    scores['correlation'] = correlation_score
    total_score += correlation_score * RISK_SCORE_WEIGHTS['correlation']['weight']
    
    # 归一化到 0-100，确保与分级阈值一致
    normalized_score = min(100.0, (total_score / WEIGHTED_SCORE_CEILING) * 100.0)

    # 计算风险等级
    risk_level = 'low'
    if normalized_score >= 70:
        risk_level = 'critical'
    elif normalized_score >= 50:
        risk_level = 'high'
    elif normalized_score >= 30:
        risk_level = 'medium'
    
    return {
        'total_score': round(normalized_score, 1),
        'risk_level': risk_level,
        'breakdown': scores,
        'amount': amount,
        'counterparty': cp
    }


def explain_risk_score(
    row: pd.Series,
    result: Dict,
    account_avg_amount: float = None
) -> str:
    """
    生成风险分的自然语言解释
    
    解决"黑盒"问题：让审计员理解为什么这笔交易风险分高
    
    Args:
        row: 交易记录行
        result: score_transaction()的返回结果
        account_avg_amount: 该账户的历史平均交易额（用于倍数计算）
        
    Returns:
        人类可读的解释文本
    """
    reasons = []
    breakdown = result.get('breakdown', {})
    amount = result.get('amount', 0)
    
    # 金额解释
    if breakdown.get('amount', 0) >= 30:
        if account_avg_amount and account_avg_amount > 0:
            multiplier = amount / account_avg_amount
            if multiplier > 2:
                reasons.append(f"金额{amount/10000:.2f}万是该账户历史均值的{multiplier:.1f}倍")
            else:
                reasons.append(f"大额交易{amount/10000:.2f}万（超过50万阈值）")
        else:
            reasons.append(f"大额交易{amount/10000:.2f}万")
    elif breakdown.get('amount', 0) >= 20:
        reasons.append(f"金额{amount/10000:.2f}万超过10万阈值")
    
    # 对手方解释
    cp = result.get('counterparty', '')
    if breakdown.get('counterparty', 0) >= 30:
        reasons.append(f"对手方信息缺失或不明")
    elif breakdown.get('counterparty', 0) >= 20:
        reasons.append(f'对手方「{cp}」为个人（非机构）')
    
    # 时间解释
    if breakdown.get('time', 0) >= 15:
        date = row.get('date')
        if hasattr(date, 'hour'):
            if date.hour >= 22 or date.hour <= 6:
                reasons.append(f"发生在凌晨{date.hour}:{date.minute:02d}（深夜交易）")
        if hasattr(date, 'weekday'):
            if date.weekday() >= 5:
                reasons.append(f"发生在周末（非工作日）")
    
    # 摘要解释
    if breakdown.get('description', 0) >= 20:
        desc = str(row.get('description', ''))
        if not desc or desc == 'nan':
            reasons.append("交易摘要缺失（无法核实交易目的）")
        else:
            reasons.append(f'摘要含可疑关键词「{desc[:15]}」')
    elif breakdown.get('description', 0) >= 15:
        reasons.append("交易摘要为空或过于简短")
    
    # 关联解释
    if breakdown.get('correlation', 0) >= 20:
        reasons.append("为核心人员之间的关联交易")
    
    # 生成综合解释
    if reasons:
        explanation = f"该笔交易风险分{result['total_score']:.0f}分，主要因为：" + "；".join(reasons) + "。"
    else:
        explanation = f"该笔交易风险分{result['total_score']:.0f}分，为正常范围。"
    
    return explanation


def score_transaction_with_explanation(
    row: pd.Series,
    counterparty_risk_map: Dict[str, float] = None,
    is_core_person_transfer: bool = False,
    account_avg_amount: float = None
) -> Dict:
    """
    计算交易风险分并生成解释
    
    合并了 score_transaction 和 explain_risk_score 的功能
    """
    result = score_transaction(row, counterparty_risk_map, is_core_person_transfer)
    result['explanation'] = explain_risk_score(row, result, account_avg_amount)
    return result


# ============================================================
# 对手方风险评分
# ============================================================

def score_counterparty(
    df: pd.DataFrame,
    counterparty: str
) -> Dict:
    """
    计算对手方风险评分
    
    评分因子：
    - 交易频次
    - 交易金额
    - 交易时间分布
    - 摘要信息
    """
    cp_df = df[df['counterparty'] == counterparty]
    
    if cp_df.empty:
        return {'score': 0, 'risk_level': 'unknown'}
    
    score = 0
    factors = {}
    
    # 1. 交易次数
    tx_count = len(cp_df)
    if tx_count >= 50:
        factors['frequency'] = 30
    elif tx_count >= 20:
        factors['frequency'] = 20
    elif tx_count >= 10:
        factors['frequency'] = 10
    else:
        factors['frequency'] = 5
    score += factors['frequency']
    
    # 2. 交易金额
    total_amount = cp_df['income'].sum() + cp_df['expense'].sum()
    if total_amount >= 1000000:
        factors['amount'] = 30
    elif total_amount >= 500000:
        factors['amount'] = 20
    elif total_amount >= 100000:
        factors['amount'] = 10
    else:
        factors['amount'] = 5
    score += factors['amount']
    
    # 3. 双向往来（疑似借贷）
    has_income = cp_df['income'].sum() > 0
    has_expense = cp_df['expense'].sum() > 0
    if has_income and has_expense:
        factors['bidirectional'] = 20
        score += 20
    
    # 4. 名称风险
    if re.match(r'^[\u4e00-\u9fa5]{2,4}$', counterparty):
        factors['name_type'] = 15  # 个人名字
        score += 15
    elif any(re.match(p, counterparty) for p in HIGH_RISK_COUNTERPARTY_PATTERNS):
        factors['name_type'] = 30  # 高风险模式
        score += 30
    
    # 风险等级
    risk_level = 'low'
    if score >= 70:
        risk_level = 'critical'
    elif score >= 50:
        risk_level = 'high'
    elif score >= 30:
        risk_level = 'medium'
    
    return {
        'counterparty': counterparty,
        'score': score,
        'risk_level': risk_level,
        'factors': factors,
        'tx_count': tx_count,
        'total_amount': total_amount
    }


# ============================================================
# 账户级风险评分
# ============================================================

def score_account(df: pd.DataFrame, account_name: str) -> Dict:
    """
    计算账户整体风险评分
    
    评分因子：
    - 资金活跃度（交易频次）
    - 资金沉淀度（期末余额/总流入）
    - 资金周转率（总流出/总流入）
    - 异常交易比例
    """
    if df.empty:
        return {'score': 0, 'risk_level': 'unknown'}
    
    score = 0
    factors = {}
    
    # 1. 活跃度
    tx_count = len(df)
    if tx_count >= 500:
        factors['activity'] = 25
    elif tx_count >= 200:
        factors['activity'] = 15
    elif tx_count >= 50:
        factors['activity'] = 10
    else:
        factors['activity'] = 5
    score += factors['activity']
    
    # 2. 资金规模
    total_inflow = df['income'].sum()
    total_outflow = df['expense'].sum()
    
    if total_inflow >= 10000000:  # 1000万+
        factors['scale'] = 30
    elif total_inflow >= 1000000:  # 100万+
        factors['scale'] = 20
    elif total_inflow >= 100000:  # 10万+
        factors['scale'] = 10
    else:
        factors['scale'] = 5
    score += factors['scale']
    
    # 3. 资金周转率（高周转可能是过账）
    if total_inflow > 0:
        turnover = total_outflow / total_inflow
        if 0.9 <= turnover <= 1.1:  # 高度平衡=过账
            factors['turnover'] = 25
            score += 25
        elif turnover >= 0.8:
            factors['turnover'] = 15
            score += 15
    
    # 4. 现金交易比例 - 【铁律修复】优先使用 is_cash 列
    if 'is_cash' in df.columns:
        cash_mask = df['is_cash'] == True
    elif '现金' in df.columns:
        cash_mask = df['现金'] == '是'
    else:
        # 降级：使用关键词匹配
        cash_mask = df['description'].fillna('').str.contains('|'.join(config.CASH_KEYWORDS), na=False)
    cash_ratio = cash_mask.sum() / len(df) if len(df) > 0 else 0
    if cash_ratio >= 0.3:
        factors['cash_ratio'] = 20
        score += 20
    elif cash_ratio >= 0.1:
        factors['cash_ratio'] = 10
        score += 10
    
    # 风险等级
    risk_level = 'low'
    if score >= 70:
        risk_level = 'critical'
    elif score >= 50:
        risk_level = 'high'
    elif score >= 30:
        risk_level = 'medium'
    
    return {
        'account': account_name,
        'score': score,
        'risk_level': risk_level,
        'factors': factors,
        'tx_count': tx_count,
        'total_inflow': total_inflow,
        'total_outflow': total_outflow
    }


# ============================================================
# 批量风险评分
# ============================================================

def score_all_transactions(
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> List[Dict]:
    """
    对所有交易进行批量风险评分
    
    Returns:
        按风险分排序的交易列表
    """
    logger.info('='*60)
    logger.info('开始批量交易风险评分')
    logger.info('='*60)
    
    scored_transactions = []
    
    for entity, df in all_transactions.items():
        if df.empty:
            continue
        
        for idx, row in df.iterrows():
            # 判断是否核心人员间转账
            cp = str(row.get('counterparty', ''))
            is_core_transfer = cp in core_persons
            
            # 评分
            result = score_transaction(row, is_core_person_transfer=is_core_transfer)
            
            # 只保留中风险以上
            if result['total_score'] >= 30:
                scored_transactions.append({
                    'entity': entity,
                    'date': row.get('date'),
                    'counterparty': result['counterparty'],
                    'amount': result['amount'],
                    'description': str(row.get('description', ''))[:30],
                    'risk_score': result['total_score'],
                    'risk_level': result['risk_level'],
                    'score_breakdown': result['breakdown']
                })
    
    # 按风险分排序
    scored_transactions.sort(key=lambda x: -x['risk_score'])
    
    # 统计
    critical_count = sum(1 for t in scored_transactions if t['risk_level'] == 'critical')
    high_count = sum(1 for t in scored_transactions if t['risk_level'] == 'high')
    medium_count = sum(1 for t in scored_transactions if t['risk_level'] == 'medium')
    
    logger.info(f'评分完成: 共 {len(scored_transactions)} 笔需关注交易')
    logger.info(f'  极高风险: {critical_count} 笔')
    logger.info(f'  高风险: {high_count} 笔')
    logger.info(f'  中风险: {medium_count} 笔')
    
    return scored_transactions


def generate_risk_report(scored_transactions: List[Dict], output_dir: str) -> str:
    """
    生成风险评分报告
    """
    import os
    report_path = os.path.join(output_dir, '交易风险评分报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('交易风险评分报告\n')
        f.write('='*60 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        
        # 统计
        critical = [t for t in scored_transactions if t['risk_level'] == 'critical']
        high = [t for t in scored_transactions if t['risk_level'] == 'high']
        medium = [t for t in scored_transactions if t['risk_level'] == 'medium']
        
        f.write('一、风险概览\n')
        f.write('-'*40 + '\n')
        f.write(f'极高风险 (70-100分): {len(critical)} 笔\n')
        f.write(f'高风险 (50-70分): {len(high)} 笔\n')
        f.write(f'中风险 (30-50分): {len(medium)} 笔\n\n')
        
        # Top 20 高风险
        f.write('二、极高风险交易（Top 20，立即核查）\n')
        f.write('-'*40 + '\n')
        for i, t in enumerate(critical[:20], 1):
            date_str = str(t['date'])[:10] if t['date'] else 'N/A'
            f.write(f'{i}. [{t["risk_score"]:.0f}分] {t["entity"]} → {t["counterparty"]}\n')
            f.write(f'   金额: {t["amount"]/10000:.2f}万 | 日期: {date_str}\n')
            f.write(f'   摘要: {t["description"]}\n')
        f.write('\n')
        
        # Top 30 高风险
        f.write('三、高风险交易（Top 30，优先核查）\n')
        f.write('-'*40 + '\n')
        for i, t in enumerate(high[:30], 1):
            date_str = str(t['date'])[:10] if t['date'] else 'N/A'
            f.write(f'{i}. [{t["risk_score"]:.0f}分] {t["entity"]} → {t["counterparty"]}\n')
            f.write(f'   金额: {t["amount"]/10000:.2f}万 | 日期: {date_str}\n')
    
    logger.info(f'风险评分报告已生成: {report_path}')
    return report_path
