#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公司层面风险分析模块 - 资金穿透与关联排查系统
用于报告生成中的"公司资金核查"部分，深度分析公司层面风险

功能：
1. 公司间资金往来分析（利益输送检测）
2. 公司向个人资金输送分析（洗钱风险）
3. 公司资产异常分析
4. 公司经营合理性分析
5. 综合风险评分机制
"""

import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import numpy as np
import utils
from holiday_service import get_holiday_service

logger = utils.setup_logger(__name__)


# ============================================================================
# 风险分析阈值配置（可配置）
# ============================================================================
class RiskThresholds:
    """风险分析阈值配置"""
    
    # 公司间往来阈值
    COMPANY_LARGE_TRANSFER = 100000  # 大额公司间转账阈值（10万元）
    COMPANY_HIGH_FREQ_MONTHLY = 4     # 高频转账：每月超过4笔
    COMPANY_ROUTINE_AMOUNT_VAR = 0.3  # 规律转账金额变异系数阈值
    
    # 公司向个人转账阈值
    COMPANY_TO_PERSON_LARGE = 50000   # 大额个人转账阈值（5万元）
    COMPANY_TO_PERSON_HIGH_FREQ = 6   # 高频个人转账：超过6笔/人
    COMPANY_TO_PERSON_TOTAL = 200000  # 同一人员累计转账阈值（20万元）
    
    # 资产异常阈值
    ASSET_LARGE_WITHOUT_BUSINESS = 300000  # 无业务大额支出（30万元）
    ASSET_FIXED_ASSET_RATIO = 0.5          # 固定资产占比超过总资产50%
    
    # 经营合理性阈值
    CASH_LARGE_OPERATION = 50000      # 大额现金操作（5万元）
    TIME_WORKING_HOURS_START = 9      # 工作时间开始（9点）
    TIME_WORKING_HOURS_END = 18       # 工作时间结束（18点）
    
    @classmethod
    def custom_thresholds(cls, **kwargs):
        """自定义阈值"""
        for key, value in kwargs.items():
            if hasattr(cls, key):
                setattr(cls, key, value)


# ============================================================================
# 核心风险分析函数
# ============================================================================

def analyze_company_risk(
    companies_profiles: Dict,
    company_transactions: Dict,
    core_persons: List[str],
    suspicions: Dict,
    thresholds: Optional[RiskThresholds] = None
) -> Dict:
    """
    公司层面风险分析主函数
    
    Args:
        companies_profiles: 所有公司的资金画像数据 {company_name: profile}
        company_transactions: 所有公司的交易明细 {company_name: DataFrame}
        core_persons: 核心人员名单
        suspicions: 疑点检测结果
        thresholds: 自定义阈值（可选）
    
    Returns:
        风险分析结果字典，包含：
        {
            "overall_risk_level": "低风险/关注级/高风险",
            "overall_risk_score": 0-100,
            "dimensions": {
                "inter_company_risk": {"score": 0-30, "evidence": [...]},
                "company_to_person_risk": {"score": 0-30, "evidence": [...]},
                "asset_anomaly_risk": {"score": 0-20, "evidence": [...]},
                "operational_risk": {"score": 0-20, "evidence": [...]}
            },
            "risk_exclusions": [...],
            "red_flags": [...]
        }
    """
    # 使用自定义阈值或默认阈值
    thresholds = thresholds or RiskThresholds
    
    # 初始化结果结构
    result = {
        "overall_risk_level": "低风险",
        "overall_risk_score": 0,
        "dimensions": {
            "inter_company_risk": {"score": 0, "evidence": []},
            "company_to_person_risk": {"score": 0, "evidence": []},
            "asset_anomaly_risk": {"score": 0, "evidence": []},
            "operational_risk": {"score": 0, "evidence": []}
        },
        "risk_exclusions": [],
        "red_flags": []
    }
    
    # 获取公司列表
    company_names = list(companies_profiles.keys())
    
    if not company_names:
        logger.warning("未发现公司数据，跳过公司风险分析")
        result["risk_exclusions"].append("无公司数据")
        return result
    
    logger.info(f"开始分析 {len(company_names)} 家公司的风险")
    
    # 1. 公司间资金往来分析（利益输送检测）- 0-30分
    logger.info("执行维度1: 公司间资金往来分析")
    inter_company_score, inter_company_evidence = analyze_inter_company_transfers(
        company_names, company_transactions, thresholds
    )
    result["dimensions"]["inter_company_risk"]["score"] = inter_company_score
    result["dimensions"]["inter_company_risk"]["evidence"] = inter_company_evidence
    
    # 2. 公司向个人资金输送分析（洗钱风险）- 0-30分
    logger.info("执行维度2: 公司向个人资金输送分析")
    company_to_person_score, company_to_person_evidence = analyze_company_to_person_transfers(
        company_names, company_transactions, core_persons, suspicions, thresholds
    )
    result["dimensions"]["company_to_person_risk"]["score"] = company_to_person_score
    result["dimensions"]["company_to_person_risk"]["evidence"] = company_to_person_evidence
    
    # 3. 公司资产异常分析 - 0-20分
    logger.info("执行维度3: 公司资产异常分析")
    asset_anomaly_score, asset_anomaly_evidence = analyze_asset_anomalies(
        company_names, companies_profiles, company_transactions, thresholds
    )
    result["dimensions"]["asset_anomaly_risk"]["score"] = asset_anomaly_score
    result["dimensions"]["asset_anomaly_risk"]["evidence"] = asset_anomaly_evidence
    
    # 4. 公司经营合理性分析 - 0-20分
    logger.info("执行维度4: 公司经营合理性分析")
    operational_score, operational_evidence = analyze_operational_rationality(
        company_names, companies_profiles, company_transactions, thresholds
    )
    result["dimensions"]["operational_risk"]["score"] = operational_score
    result["dimensions"]["operational_risk"]["evidence"] = operational_evidence
    
    # 5. 计算综合风险评分
    total_score = (
        result["dimensions"]["inter_company_risk"]["score"] +
        result["dimensions"]["company_to_person_risk"]["score"] +
        result["dimensions"]["asset_anomaly_risk"]["score"] +
        result["dimensions"]["operational_risk"]["score"]
    )
    result["overall_risk_score"] = total_score
    
    # 确定风险等级
    if total_score <= 30:
        result["overall_risk_level"] = "低风险"
    elif total_score <= 60:
        result["overall_risk_level"] = "关注级"
    else:
        result["overall_risk_level"] = "高风险"
    
    # 6. 生成风险排除说明
    result["risk_exclusions"] = generate_risk_exclusions(result)
    
    # 7. 生成红旗（高风险标记）
    result["red_flags"] = generate_red_flags(result)
    
    logger.info(f"公司风险分析完成: 总分 {total_score}/100, 等级 {result['overall_risk_level']}")
    
    return result


# ============================================================================
# 维度1: 公司间资金往来分析（利益输送检测）
# ============================================================================

def analyze_inter_company_transfers(
    company_names: List[str],
    company_transactions: Dict,
    thresholds: RiskThresholds
) -> Tuple[int, List[Dict]]:
    """
    分析公司间资金往来，检测利益输送
    
    检测项：
    1. 频繁转账识别
    2. 资金流向分析（多跳路径）
    3. 利益输送路径识别（闭环/复杂链路）
    4. 空壳公司识别（进账≈出账，无明显业务）
    
    Returns:
        (风险得分, 证据列表)
    """
    evidence = []
    score = 0
    
    # 构建公司间转账图
    company_graph = defaultdict(lambda: {"income": 0, "expense": 0, "transfers": []})
    
    for company in company_names:
        df = company_transactions.get(company)
        if df is None or df.empty:
            continue
        
        # 筛选公司间交易
        for idx, row in df.iterrows():
            counterparty = str(row.get('counterparty', ''))
            
            # 判断对手方是否为公司
            if any(cp in counterparty for cp in company_names if cp != company):
                direction = 'expense' if row.get('expense', 0) > 0 else 'income'
                amount = abs(row.get('expense', 0) or row.get('income', 0))
                
                if amount > 0:
                    company_graph[company][direction] += amount
                    company_graph[company]["transfers"].append({
                        "counterparty": counterparty,
                        "amount": amount,
                        "direction": direction,
                        "date": row.get('date'),
                        "description": row.get('description', '')
                    })
    
    # 1.1 检测频繁转账（评分: 0-10分）
    freq_evidences = detect_frequent_company_transfers(company_graph, company_names, thresholds)
    if freq_evidences:
        evidence.extend(freq_evidences)
        score += min(10, len(freq_evidences) * 2)
    
    # 1.2 检测资金流向和多跳路径（评分: 0-10分）
    path_evidences = detect_transfer_paths(company_graph, company_names, thresholds)
    if path_evidences:
        evidence.extend(path_evidences)
        score += min(10, len(path_evidences) * 3)
    
    # 1.3 检测利益输送闭环（评分: 0-5分）
    cycle_evidences = detect_fund_cycles(company_graph, company_names, thresholds)
    if cycle_evidences:
        evidence.extend(cycle_evidences)
        score += min(5, len(cycle_evidences) * 5)
    
    # 1.4 识别空壳公司（评分: 0-5分）
    shell_evidences = detect_shell_companies(company_graph, company_names, thresholds)
    if shell_evidences:
        evidence.extend(shell_evidences)
        score += min(5, len(shell_evidences) * 5)
    
    return score, evidence


def detect_frequent_company_transfers(
    company_graph: Dict,
    company_names: List[str],
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测公司间频繁转账
    
    检测逻辑：
    - 同一对公司间每月转账次数超过阈值
    - 金额相对固定（变异系数小）
    """
    evidences = []
    
    # 统计公司间转账频率
    transfer_pairs = defaultdict(lambda: {"count": 0, "amounts": [], "dates": []})
    
    for company, data in company_graph.items():
        for tx in data["transfers"]:
            counterparty = tx["counterparty"]
            
            # 确保counterparty是公司
            if not any(cp in counterparty for cp in company_names):
                continue
            
            # 创建配对键（按字母序，避免重复）
            pair_key = tuple(sorted([company, counterparty]))
            
            transfer_pairs[pair_key]["count"] += 1
            transfer_pairs[pair_key]["amounts"].append(tx["amount"])
            transfer_pairs[pair_key]["dates"].append(tx["date"])
    
    # 分析高频转账
    for pair, stats in transfer_pairs.items():
        if stats["count"] < thresholds.COMPANY_HIGH_FREQ_MONTHLY * 2:  # 总体需要超过2个月的高频
            continue
        
        # 计算金额变异系数
        amounts = stats["amounts"]
        if len(amounts) < 3:
            continue
        
        mean_amt = sum(amounts) / len(amounts)
        variance = sum((x - mean_amt) ** 2 for x in amounts) / len(amounts)
        std_amt = variance ** 0.5
        cv = std_amt / mean_amt if mean_amt > 0 else 999
        
        # 判断是否为规律性转账
        is_routine = cv < thresholds.COMPANY_ROUTINE_AMOUNT_VAR
        
        # 判断总金额
        total_amount = sum(amounts)
        
        evidence = {
            "type": "频繁公司间转账",
            "company_a": pair[0],
            "company_b": pair[1],
            "count": stats["count"],
            "total_amount": total_amount,
            "avg_amount": mean_amt,
            "cv": cv,
            "is_routine": is_routine,
            "description": f"{pair[0]}与{pair[1]}间发生{stats['count']}笔转账，总计{utils.format_currency(total_amount)}元，平均{utils.format_currency(mean_amt)}元/笔，变异系数{cv:.2f}"
        }
        
        if is_routine:
            evidence["strength"] = "强"
            evidence["risk_reason"] = "规律性频繁转账，可能涉及利益输送"
        else:
            evidence["strength"] = "中"
            evidence["risk_reason"] = "高频转账但金额不稳定，需关注业务背景"
        
        evidences.append(evidence)
    
    return evidences


def detect_transfer_paths(
    company_graph: Dict,
    company_names: List[str],
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测资金流转路径（多跳链路）
    
    检测逻辑：
    - A→B→C 的多跳资金流转
    - 中间节点作为中转通道
    """
    evidences = []
    
    if len(company_names) < 3:
        return evidences
    
    # 构建有向图（转账金额作为权重）
    graph = {}
    for company in company_names:
        graph[company] = []
    
    for company, data in company_graph.items():
        for tx in data["transfers"]:
            if tx["direction"] == "expense":
                counterparty = tx["counterparty"]
                # 确保counterparty是公司
                matched_cp = next((cp for cp in company_names if cp in counterparty), None)
                if matched_cp:
                    graph[company].append({
                        "to": matched_cp,
                        "amount": tx["amount"]
                    })
    
    # 检测2跳路径 (A→B→C)
    for company_a in company_names:
        for edge_a in graph.get(company_a, []):
            company_b = edge_a["to"]
            amount_ab = edge_a["amount"]
            
            for edge_b in graph.get(company_b, []):
                company_c = edge_b["to"]
                
                # 确保不回到起点
                if company_c == company_a:
                    continue
                
                amount_bc = edge_b["amount"]
                
                # 计算金额相似度（可能作为中转）
                if amount_ab > thresholds.COMPANY_LARGE_TRANSFER or \
                   amount_bc > thresholds.COMPANY_LARGE_TRANSFER:
                    
                    # 金额相似度（比例在0.8-1.2之间）
                    ratio = amount_bc / amount_ab if amount_ab > 0 else 0
                    is_similar = 0.8 <= ratio <= 1.2
                    
                    evidence = {
                        "type": "多跳资金流转",
                        "path": f"{company_a} → {company_b} → {company_c}",
                        "amount_ab": amount_ab,
                        "amount_bc": amount_bc,
                        "ratio": ratio,
                        "is_similar": is_similar,
                        "description": f"资金路径: {company_a}向{company_b}支付{utils.format_currency(amount_ab)}元，随后{company_b}向{company_c}支付{utils.format_currency(amount_bc)}元"
                    }
                    
                    if is_similar:
                        evidence["strength"] = "强"
                        evidence["risk_reason"] = f"{company_b}可能是中转通道，资金流转存在明显关联"
                    else:
                        evidence["strength"] = "中"
                        evidence["risk_reason"] = "存在多跳资金流转，需核查业务背景"
                    
                    evidences.append(evidence)
    
    return evidences


def detect_fund_cycles(
    company_graph: Dict,
    company_names: List[str],
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测资金闭环（利益输送特征）
    
    检测逻辑：
    - A→B→C→A 的闭环
    - 闭环时间较短（短期回转）
    """
    evidences = []
    
    if len(company_names) < 3:
        return evidences
    
    # 构建转账时间序列
    time_edges = []  # (date, from, to, amount)
    
    for company, data in company_graph.items():
        for tx in data["transfers"]:
            if tx["direction"] == "expense":
                counterparty = tx["counterparty"]
                matched_cp = next((cp for cp in company_names if cp in counterparty), None)
                if matched_cp and tx["date"]:
                    time_edges.append({
                        "date": pd.to_datetime(tx["date"]),
                        "from": company,
                        "to": matched_cp,
                        "amount": tx["amount"]
                    })
    
    # 按时间排序
    time_edges.sort(key=lambda x: x["date"])
    
    # 检测2步闭环 (A→B, B→A)
    for i, edge1 in enumerate(time_edges):
        for j, edge2 in enumerate(time_edges[i+1:], i+1):
            if edge1["from"] == edge2["to"] and edge1["to"] == edge2["from"]:
                # 发现闭环
                time_diff = (edge2["date"] - edge1["date"]).days
                
                if time_diff <= 30:  # 30天内闭环
                    evidence = {
                        "type": "资金闭环",
                        "path": f"{edge1['from']} → {edge1['to']} → {edge1['from']}",
                        "amount_out": edge1["amount"],
                        "amount_in": edge2["amount"],
                        "time_diff_days": time_diff,
                        "description": f"{edge1['from']}在{edge1['date'].strftime('%Y-%m-%d')}向{edge1['to']}支付{utils.format_currency(edge1['amount'])}元，{time_diff}天后收到{utils.format_currency(edge2['amount'])}元"
                    }
                    evidence["strength"] = "强"
                    evidence["risk_reason"] = "短期资金闭环，疑似利益输送或资金空转"
                    evidences.append(evidence)
    
    return evidences


def detect_shell_companies(
    company_graph: Dict,
    company_names: List[str],
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    识别空壳公司（资金中转公司）
    
    检测逻辑：
    - 进账金额 ≈ 出账金额（比例0.8-1.2）
    - 进出账频繁但无明显业务对手方
    - 交易对手主要是其他公司
    """
    evidences = []
    
    for company, data in company_graph.items():
        income = data["income"]
        expense = data["expense"]
        
        if income == 0 and expense == 0:
            continue
        
        # 计算进出比
        ratio = expense / income if income > 0 else 999
        
        # 判断是否接近1（资金中转）
        if 0.8 <= ratio <= 1.2 and min(income, expense) > thresholds.COMPANY_LARGE_TRANSFER * 2:
            # 分析交易对手方
            counterparties = set()
            for tx in data["transfers"]:
                counterparties.add(tx["counterparty"])
            
            # 判断是否主要为公司间交易
            company_counterparties = sum(
                1 for cp in counterparties
                if any(c_name in cp for c_name in company_names if c_name != company)
            )
            
            ratio_company_cp = company_counterparties / len(counterparties) if counterparties else 0
            
            if ratio_company_cp >= 0.5:  # 超过50%是对公司
                evidence = {
                    "type": "疑似空壳公司",
                    "company": company,
                    "income": income,
                    "expense": expense,
                    "ratio": ratio,
                    "company_counterparty_ratio": ratio_company_cp,
                    "description": f"{company}进账{utils.format_currency(income)}元，出账{utils.format_currency(expense)}元，进出比{ratio:.2f}，{ratio_company_cp:.0%}的交易对手为公司"
                }
                evidence["strength"] = "强"
                evidence["risk_reason"] = "资金进出匹配且主要与公司往来，疑似资金中转通道"
                evidences.append(evidence)
    
    return evidences


# ============================================================================
# 维度2: 公司向个人资金输送分析（洗钱风险）
# ============================================================================

def analyze_company_to_person_transfers(
    company_names: List[str],
    company_transactions: Dict,
    core_persons: List[str],
    suspicions: Dict,
    thresholds: RiskThresholds
) -> Tuple[int, List[Dict]]:
    """
    分析公司向个人的资金输送，检测洗钱风险
    
    检测项：
    1. 大额个人转账检测
    2. 高频个人转账
    3. 敏感对手方识别（核心人员/亲属）
    4. 资金分散模式（多个人账户分散）
    
    Returns:
        (风险得分, 证据列表)
    """
    evidence = []
    score = 0
    
    # 统计公司向个人的转账
    person_transfers = defaultdict(lambda: {"count": 0, "total": 0, "companies": set(), "details": []})
    
    for company in company_names:
        df = company_transactions.get(company)
        if df is None or df.empty:
            continue
        
        for idx, row in df.iterrows():
            counterparty = str(row.get('counterparty', '')).strip()
            amount = row.get('expense', 0)
            
            if amount <= 0:
                continue
            
            # 排除公司间交易
            if any(cp in counterparty for cp in company_names):
                continue
            
            # 排除常见非个人对手方
            exclude_keywords = ['公司', '中心', '集团', '有限', '股份', '银行', '税务', '政府', '部门']
            if any(kw in counterparty for kw in exclude_keywords):
                continue
            
            # 记录个人转账
            person_transfers[counterparty]["count"] += 1
            person_transfers[counterparty]["total"] += amount
            person_transfers[counterparty]["companies"].add(company)
            person_transfers[counterparty]["details"].append({
                "company": company,
                "amount": amount,
                "date": row.get('date'),
                "description": row.get('description', '')
            })
    
    # 2.1 检测大额个人转账（评分: 0-10分）
    large_evidences = detect_large_person_transfers(person_transfers, core_persons, thresholds)
    if large_evidences:
        evidence.extend(large_evidences)
        score += min(10, len(large_evidences) * 5)
    
    # 2.2 检测高频个人转账（评分: 0-10分）
    high_freq_evidences = detect_high_freq_person_transfers(person_transfers, thresholds)
    if high_freq_evidences:
        evidence.extend(high_freq_evidences)
        score += min(10, len(high_freq_evidences) * 3)
    
    # 2.3 检测资金分散模式（评分: 0-10分）
    dispersion_evidences = detect_fund_dispersion(person_transfers, thresholds)
    if dispersion_evidences:
        evidence.extend(dispersion_evidences)
        score += min(10, len(dispersion_evidences) * 5)
    
    # 结合疑点检测结果
    direct_transfers = suspicions.get('direct_transfers', [])
    if direct_transfers:
        for dt in direct_transfers:
            evidence.append({
                "type": "直接利益输送",
                "person": dt.get('person', ''),
                "company": dt.get('company', ''),
                "amount": dt.get('amount', 0),
                "date": dt.get('date'),
                "description": dt.get('description', ''),
                "strength": "强",
                "risk_reason": "疑似直接利益输送"
            })
        score += min(10, len(direct_transfers))
    
    return score, evidence


def detect_large_person_transfers(
    person_transfers: Dict,
    core_persons: List[str],
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测大额个人转账
    
    检测逻辑：
    - 单笔转账超过阈值
    - 累计转账超过阈值
    - 转给核心人员（高危）
    """
    evidences = []
    
    for person, stats in person_transfers.items():
        # 判断是否为核心人员
        is_core_person = any(cp in person for cp in core_persons)
        
        # 检查单笔大额转账
        for detail in stats["details"]:
            if detail["amount"] >= thresholds.COMPANY_TO_PERSON_LARGE:
                evidence = {
                    "type": "大额个人转账",
                    "company": detail["company"],
                    "person": person,
                    "amount": detail["amount"],
                    "date": detail["date"],
                    "is_core_person": is_core_person,
                    "description": f"{detail['company']}向{person}支付{utils.format_currency(detail['amount'])}元"
                }
                
                if is_core_person:
                    evidence["strength"] = "强"
                    evidence["risk_reason"] = "向核心人员进行大额转账，高度可疑"
                else:
                    evidence["strength"] = "中"
                    evidence["risk_reason"] = "大额个人转账，需核实业务背景"
                
                evidences.append(evidence)
        
        # 检查累计转账
        if stats["total"] >= thresholds.COMPANY_TO_PERSON_TOTAL:
            evidence = {
                "type": "累计大额个人转账",
                "person": person,
                "count": stats["count"],
                "total": stats["total"],
                "companies": list(stats["companies"]),
                "is_core_person": is_core_person,
                "description": f"向{person}累计支付{stats['count']}笔，总计{utils.format_currency(stats['total'])}元，涉及{len(stats['companies'])}家公司"
            }
            
            if is_core_person:
                evidence["strength"] = "强"
                evidence["risk_reason"] = "核心人员累计大额收入，疑似洗钱或利益输送"
            else:
                evidence["strength"] = "中"
                evidence["risk_reason"] = "同一人员累计大额收入，需核查"
            
            evidences.append(evidence)
    
    return evidences


def detect_high_freq_person_transfers(
    person_transfers: Dict,
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测高频个人转账
    
    检测逻辑：
    - 同一人员转账次数超过阈值
    - 来自多个公司（可能分散资金）
    """
    evidences = []
    
    for person, stats in person_transfers.items():
        if stats["count"] < thresholds.COMPANY_TO_PERSON_HIGH_FREQ:
            continue
        
        evidence = {
            "type": "高频个人转账",
            "person": person,
            "count": stats["count"],
            "total": stats["total"],
            "avg_amount": stats["total"] / stats["count"],
            "companies": list(stats["companies"]),
            "company_count": len(stats["companies"]),
            "description": f"向{person}高频转账{stats['count']}笔，平均{utils.format_currency(stats['total']/stats['count'])}元/笔，涉及{len(stats['companies'])}家公司"
        }
        
        if len(stats["companies"]) >= 2:
            evidence["strength"] = "强"
            evidence["risk_reason"] = "多公司向同一人员高频转账，疑似资金分散"
        else:
            evidence["strength"] = "中"
            evidence["risk_reason"] = "高频转账需核实业务背景"
        
        evidences.append(evidence)
    
    return evidences


def detect_fund_dispersion(
    person_transfers: Dict,
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测资金分散模式
    
    检测逻辑：
    - 同一时间段内，公司向多个个人账户转账
    - 金额相对接近（拆分洗钱）
    """
    evidences = []
    
    # 按公司分组
    company_persons = defaultdict(lambda: {"persons": set(), "total": 0, "count": 0})
    
    for person, stats in person_transfers.items():
        for detail in stats["details"]:
            company = detail["company"]
            company_persons[company]["persons"].add(person)
            company_persons[company]["total"] += detail["amount"]
            company_persons[company]["count"] += 1
    
    # 检测分散模式
    for company, stats in company_persons.items():
        if stats["count"] < 5 or len(stats["persons"]) < 3:
            continue
        
        evidence = {
            "type": "资金分散模式",
            "company": company,
            "person_count": len(stats["persons"]),
            "transfer_count": stats["count"],
            "total": stats["total"],
            "avg_per_person": stats["total"] / len(stats["persons"]),
            "description": f"{company}向{len(stats['persons'])}个个人账户转账{stats['count']}笔，总计{utils.format_currency(stats['total'])}元"
        }
        evidence["strength"] = "强"
        evidence["risk_reason"] = "资金向多个个人账户分散，疑似洗钱操作"
        evidences.append(evidence)
    
    return evidences


# ============================================================================
# 维度3: 公司资产异常分析
# ============================================================================

def analyze_asset_anomalies(
    company_names: List[str],
    companies_profiles: Dict,
    company_transactions: Dict,
    thresholds: RiskThresholds
) -> Tuple[int, List[Dict]]:
    """
    分析公司资产异常
    
    检测项：
    1. 无业务大额支出
    2. 异常费用模式（咨询费、服务费等）
    3. 固定资产异常
    4. 股东关联交易
    """
    evidence = []
    score = 0
    
    # 3.1 检测无业务大额支出（评分: 0-8分）
    large_expense_evidences = detect_large_expenses_without_business(
        company_names, company_transactions, thresholds
    )
    if large_expense_evidences:
        evidence.extend(large_expense_evidences)
        score += min(8, len(large_expense_evidences) * 2)
    
    # 3.2 检测异常费用模式（评分: 0-6分）
    abnormal_fee_evidences = detect_abnormal_fee_patterns(
        company_names, company_transactions, thresholds
    )
    if abnormal_fee_evidences:
        evidence.extend(abnormal_fee_evidences)
        score += min(6, len(abnormal_fee_evidences) * 2)
    
    # 3.3 检测固定资产异常（评分: 0-6分）
    fixed_asset_evidences = detect_fixed_asset_anomalies(
        company_names, companies_profiles, thresholds
    )
    if fixed_asset_evidences:
        evidence.extend(fixed_asset_evidences)
        score += min(6, len(fixed_asset_evidences) * 3)
    
    return score, evidence


def detect_large_expenses_without_business(
    company_names: List[str],
    company_transactions: Dict,
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测无业务大额支出
    
    检测逻辑：
    - 大额支出但对手方模糊（个人、不明公司）
    - 摘要模糊（无具体业务说明）
    """
    evidences = []
    
    for company in company_names:
        df = company_transactions.get(company)
        if df is None or df.empty:
            continue
        
        large_expenses = df[
            (df['expense'] > thresholds.ASSET_LARGE_WITHOUT_BUSINESS) &
            (~df['counterparty'].str.contains('公司|银行|税务|政府', na=False))
        ]
        
        for idx, row in large_expenses.iterrows():
            counterparty = str(row['counterparty']).strip()
            description = str(row.get('description', '')).strip()
            
            # 判断摘要是否模糊
            is_vague = not description or len(description) < 5 or \
                       any(kw in description for kw in ['往来', '款项', '转账', '划转'])
            
            evidence = {
                "type": "无业务大额支出",
                "company": company,
                "counterparty": counterparty,
                "amount": row['expense'],
                "date": row.get('date'),
                "description": description,
                "is_vague": is_vague,
                "full_description": f"{company}向{counterparty}支付{utils.format_currency(row['expense'])}元，摘要：{description}"
            }
            
            if is_vague:
                evidence["strength"] = "强"
                evidence["risk_reason"] = "大额支出对手方模糊且摘要不明确，需重点核查"
            else:
                evidence["strength"] = "中"
                evidence["risk_reason"] = "大额支出对手方为个人或非公司，需核实业务背景"
            
            evidences.append(evidence)
    
    return evidences


def detect_abnormal_fee_patterns(
    company_names: List[str],
    company_transactions: Dict,
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测异常费用模式
    
    检测逻辑：
    - 咨询费、服务费等可能掩盖支出的费用
    - 频繁或大额的此类支出
    """
    evidences = []
    
    # 可疑费用关键词
    suspicious_fee_keywords = ['咨询', '服务', '顾问', '咨询费', '服务费', '顾问费', '管理费']
    
    for company in company_names:
        df = company_transactions.get(company)
        if df is None or df.empty:
            continue
        
        # 筛选可疑费用
        suspicious_fees = df[
            df['description'].str.contains('|'.join(suspicious_fee_keywords), na=False) &
            (df['expense'] > 0)
        ]
        
        if len(suspicious_fees) < 3:  # 少于3笔不关注
            continue
        
        total_fee = suspicious_fees['expense'].sum()
        counterparty_summary = suspicious_fees.groupby('counterparty')['expense'].sum().sort_values(ascending=False)
        
        evidence = {
            "type": "异常费用模式",
            "company": company,
            "count": len(suspicious_fees),
            "total": total_fee,
            "avg": total_fee / len(suspicious_fees),
            "main_counterparties": counterparty_summary.head(3).index.tolist(),
            "description": f"{company}发生{len(suspicious_fees)}笔咨询/服务费类支出，总计{utils.format_currency(total_fee)}元"
        }
        
        if total_fee > thresholds.ASSET_LARGE_WITHOUT_BUSINESS:
            evidence["strength"] = "强"
            evidence["risk_reason"] = "咨询/服务费类支出金额较大，可能掩盖真实支出"
        else:
            evidence["strength"] = "中"
            evidence["risk_reason"] = "存在咨询/服务费类支出，需核查具体内容"
        
        evidences.append(evidence)
    
    return evidences


def detect_fixed_asset_anomalies(
    company_names: List[str],
    companies_profiles: Dict,
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测固定资产异常
    
    检测逻辑：
    - 固定资产购置与公司规模不匹配
    - 固定资产占比过高
    """
    evidences = []
    
    for company in company_names:
        profile = companies_profiles.get(company)
        if not profile:
            continue
        
        summary = profile.get('summary', {})
        total_income = summary.get('total_income', 0)
        total_expense = summary.get('total_expense', 0)
        
        if total_income == 0:
            continue
        
        # 检测固定资产购置（这里用简化的逻辑，实际需要从交易中识别）
        # 假设固定资产购置会有大额支出且对手方为设备/房地产等
        # 这里仅做示意，实际需要更精确的识别
        
        # 检测支出与收入的比例
        if total_expense > total_income * 1.5:  # 支出超过收入的1.5倍
            evidence = {
                "type": "资产购置异常",
                "company": company,
                "total_income": total_income,
                "total_expense": total_expense,
                "ratio": total_expense / total_income,
                "description": f"{company}支出{utils.format_currency(total_expense)}元是收入{utils.format_currency(total_income)}元的{total_expense/total_income:.1f}倍，支出与收入不匹配"
            }
            evidence["strength"] = "中"
            evidence["risk_reason"] = "支出远超收入，可能存在异常资产购置或资金流出"
            evidences.append(evidence)
    
    return evidences


# ============================================================================
# 维度4: 公司经营合理性分析
# ============================================================================

def analyze_operational_rationality(
    company_names: List[str],
    companies_profiles: Dict,
    company_transactions: Dict,
    thresholds: RiskThresholds
) -> Tuple[int, List[Dict]]:
    """
    分析公司经营合理性
    
    检测项：
    1. 收支匹配度
    2. 业务对手方合理性
    3. 现金操作异常
    4. 异常时间模式
    """
    evidence = []
    score = 0
    
    # 4.1 检测收支匹配度（评分: 0-8分）
    balance_evidences = detect_income_expense_mismatch(
        company_names, companies_profiles, thresholds
    )
    if balance_evidences:
        evidence.extend(balance_evidences)
        score += min(8, len(balance_evidences) * 3)
    
    # 4.2 检测现金操作异常（评分: 0-6分）
    cash_evidences = detect_cash_operation_anomalies(
        company_names, company_transactions, thresholds
    )
    if cash_evidences:
        evidence.extend(cash_evidences)
        score += min(6, len(cash_evidences) * 2)
    
    # 4.3 检测异常时间模式（评分: 0-6分）
    time_evidences = detect_abnormal_time_patterns(
        company_names, company_transactions, thresholds
    )
    if time_evidences:
        evidence.extend(time_evidences)
        score += min(6, len(time_evidences) * 2)
    
    return score, evidence


def detect_income_expense_mismatch(
    company_names: List[str],
    companies_profiles: Dict,
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测收支不匹配
    
    检测逻辑：
    - 流入流出比例异常
    - 持续净流出且无合理业务
    """
    evidences = []
    
    for company in company_names:
        profile = companies_profiles.get(company)
        if not profile:
            continue
        
        summary = profile.get('summary', {})
        total_income = summary.get('total_income', 0)
        total_expense = summary.get('total_expense', 0)
        
        if total_income == 0:
            continue
        
        # 计算收支比
        ratio = total_expense / total_income
        
        # 判断是否异常
        if ratio > 1.5:  # 支出超过收入50%以上
            evidence = {
                "type": "收支不匹配",
                "company": company,
                "income": total_income,
                "expense": total_expense,
                "ratio": ratio,
                "net_flow": total_income - total_expense,
                "description": f"{company}收入{utils.format_currency(total_income)}元，支出{utils.format_currency(total_expense)}元，收支比{ratio:.2f}，净流出{utils.format_currency(total_expense - total_income)}元"
            }
            
            if ratio > 2:
                evidence["strength"] = "强"
                evidence["risk_reason"] = "支出远超收入，经营合理性存疑"
            else:
                evidence["strength"] = "中"
                evidence["risk_reason"] = "支出偏高，需核实业务背景"
            
            evidences.append(evidence)
        elif ratio < 0.5:  # 收入远超支出50%以上
            evidence = {
                "type": "收支不匹配",
                "company": company,
                "income": total_income,
                "expense": total_expense,
                "ratio": ratio,
                "net_flow": total_income - total_expense,
                "description": f"{company}收入{utils.format_currency(total_income)}元，支出{utils.format_currency(total_expense)}元，收支比{ratio:.2f}，净流入{utils.format_currency(total_income - total_expense)}元"
            }
            evidence["strength"] = "中"
            evidence["risk_reason"] = "收入远超支出，需核实收入来源"
            evidences.append(evidence)
    
    return evidences


def detect_cash_operation_anomalies(
    company_names: List[str],
    company_transactions: Dict,
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测现金操作异常
    
    检测逻辑：
    - 大额现金存取
    - 频繁现金操作
    """
    evidences = []
    
    for company in company_names:
        df = company_transactions.get(company)
        if df is None or df.empty:
            continue
        
        # 检测现金操作（需要is_cash字段）
        if 'is_cash' in df.columns:
            cash_operations = df[df['is_cash'] == True]
            
            if len(cash_operations) > 0:
                cash_in = cash_operations['income'].sum()
                cash_out = cash_operations['expense'].sum()
                total_cash = cash_in + cash_out
                
                if total_cash >= thresholds.CASH_LARGE_OPERATION:
                    evidence = {
                        "type": "大额现金操作",
                        "company": company,
                        "count": len(cash_operations),
                        "cash_in": cash_in,
                        "cash_out": cash_out,
                        "total_cash": total_cash,
                        "description": f"{company}发生{len(cash_operations)}笔现金操作，存入{utils.format_currency(cash_in)}元，取出{utils.format_currency(cash_out)}元，总计{utils.format_currency(total_cash)}元"
                    }
                    
                    if total_cash > thresholds.CASH_LARGE_OPERATION * 5:
                        evidence["strength"] = "强"
                        evidence["risk_reason"] = "异常大额现金操作，可能涉及洗钱或隐匿资产"
                    else:
                        evidence["strength"] = "中"
                        evidence["risk_reason"] = "存在大额现金操作，需核查用途"
                    
                    evidences.append(evidence)
    
    return evidences


def detect_abnormal_time_patterns(
    company_names: List[str],
    company_transactions: Dict,
    thresholds: RiskThresholds
) -> List[Dict]:
    """
    检测异常时间模式
    
    检测逻辑：
    - 非工作时间的大额交易
    - 节假日的大额交易
    """
    evidences = []
    holiday_service = get_holiday_service()
    
    for company in company_names:
        df = company_transactions.get(company)
        if df is None or df.empty:
            continue
        
        # 确保有date字段
        if 'date' not in df.columns:
            continue
        
        # 筛选大额交易
        large_tx = df[(df['expense'] > thresholds.CASH_LARGE_OPERATION) | 
                      (df['income'] > thresholds.CASH_LARGE_OPERATION)]
        
        if len(large_tx) == 0:
            continue
        
        # 检测非工作时间交易
        abnormal_time_tx = []
        
        for idx, row in large_tx.iterrows():
            date = pd.to_datetime(row['date'])
            tx_date = date.date()
            amount = row['expense'] if row['expense'] > 0 else row['income']
            
            holiday_name = holiday_service.get_holiday_name(tx_date)
            if holiday_name:
                abnormal_time_tx.append({
                    "date": date,
                    "amount": amount,
                    "counterparty": row.get('counterparty', ''),
                    "reason": f"节假日（{holiday_name}）"
                })
            # 检查是否为周末
            elif date.weekday() >= 5:  # 5=周六, 6=周日
                abnormal_time_tx.append({
                    "date": date,
                    "amount": amount,
                    "counterparty": row.get('counterparty', ''),
                    "reason": "周末"
                })
            # 检查是否为非工作时间（如果有时分秒信息）
            elif date.hour < thresholds.TIME_WORKING_HOURS_START or \
                 date.hour >= thresholds.TIME_WORKING_HOURS_END:
                abnormal_time_tx.append({
                    "date": date,
                    "amount": amount,
                    "counterparty": row.get('counterparty', ''),
                    "reason": "非工作时间"
                })
        
        if len(abnormal_time_tx) >= 3:  # 至少3笔异常时间交易
            total_amount = sum(tx['amount'] for tx in abnormal_time_tx)
            
            evidence = {
                "type": "异常时间模式",
                "company": company,
                "count": len(abnormal_time_tx),
                "total_amount": total_amount,
                "description": (
                    f"{company}在异常时间（节假日/周末/非工作时间）发生"
                    f"{len(abnormal_time_tx)}笔大额交易，总计{utils.format_currency(total_amount)}元"
                )
            }
            evidence["strength"] = "中"
            evidence["risk_reason"] = "异常时间大额交易，需核实业务背景"
            evidences.append(evidence)
    
    return evidences


# ============================================================================
# 辅助函数：生成风险排除说明和红旗
# ============================================================================

def generate_risk_exclusions(result: Dict) -> List[str]:
    """
    生成风险排除说明
    
    根据各维度得分，生成已排除的风险
    """
    exclusions = []
    
    # 公司间往来
    if result["dimensions"]["inter_company_risk"]["score"] == 0:
        exclusions.append("无公司间异常资金往来")
    elif result["dimensions"]["inter_company_risk"]["score"] <= 5:
        exclusions.append("公司间资金往来基本正常")
    
    # 公司向个人转账
    if result["dimensions"]["company_to_person_risk"]["score"] == 0:
        exclusions.append("无公司向个人异常输送")
    elif result["dimensions"]["company_to_person_risk"]["score"] <= 5:
        exclusions.append("公司向个人转账基本正常")
    
    # 资产异常
    if result["dimensions"]["asset_anomaly_risk"]["score"] == 0:
        exclusions.append("无资产异常支出")
    elif result["dimensions"]["asset_anomaly_risk"]["score"] <= 3:
        exclusions.append("资产支出基本合理")
    
    # 经营合理性
    if result["dimensions"]["operational_risk"]["score"] == 0:
        exclusions.append("经营收支基本合理")
    elif result["dimensions"]["operational_risk"]["score"] <= 3:
        exclusions.append("经营模式基本正常")
    
    return exclusions


def generate_red_flags(result: Dict) -> List[Dict]:
    """
    生成红旗（高风险标记）
    
    从所有证据中筛选高强度的风险标记
    """
    red_flags = []
    
    for dimension_name, dimension_data in result["dimensions"].items():
        for evidence in dimension_data["evidence"]:
            if evidence.get("strength") == "强":
                red_flag = {
                    "type": evidence.get("type", "未知风险"),
                    "details": evidence.get("description", ""),
                    "reason": evidence.get("risk_reason", ""),
                    "dimension": dimension_name
                }
                red_flags.append(red_flag)
    
    return red_flags


# ============================================================================
# 格式化输出函数
# ============================================================================

def format_risk_report(result: Dict) -> str:
    """
    格式化风险分析报告
    
    Args:
        result: 风险分析结果
    
    Returns:
        格式化的报告文本
    """
    lines = []
    
    lines.append("=" * 80)
    lines.append("公司层面风险分析报告")
    lines.append("=" * 80)
    lines.append("")
    
    # 总体评价
    lines.append(f"【总体评价】")
    lines.append(f"  风险等级: {result['overall_risk_level']}")
    lines.append(f"  风险评分: {result['overall_risk_score']}/100")
    lines.append("")
    
    # 各维度评分
    lines.append("【维度评分】")
    for dim_name, dim_data in result["dimensions"].items():
        lines.append(f"  • {dim_name}: {dim_data['score']}分")
    lines.append("")
    
    # 风险排除说明
    if result["risk_exclusions"]:
        lines.append("【风险排除说明】")
        for exclusion in result["risk_exclusions"]:
            lines.append(f"  ✓ {exclusion}")
        lines.append("")
    
    # 红旗标记
    if result["red_flags"]:
        lines.append("【高风险红旗】")
        for i, flag in enumerate(result["red_flags"], 1):
            lines.append(f"  {i}. [{flag['type']}] {flag['details']}")
            lines.append(f"     原因: {flag['reason']}")
        lines.append("")
    
    # 详细证据
    lines.append("【详细证据】")
    for dim_name, dim_data in result["dimensions"].items():
        if dim_data["evidence"]:
            lines.append(f"\n{dim_name}:")
            for i, evidence in enumerate(dim_data["evidence"], 1):
                lines.append(f"  {i}. {evidence['description']}")
                lines.append(f"     强度: {evidence['strength']} | 原因: {evidence['risk_reason']}")
    
    return "\n".join(lines)


# ============================================================================
# 主函数（用于测试）
# ============================================================================

if __name__ == "__main__":
    # 测试代码
    print("公司风险分析模块已加载")
    print("使用 analyze_company_risk() 函数进行分析")
