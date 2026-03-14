#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人资金特征分析模块
用于生成纪检审计报告中的描述话术和特征描写
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

import utils

@dataclass
class AnalysisThresholds:
    """分析阈值配置"""
    # 收支匹配度阈值
    income_coverage_ratio_low: float = 0.6  # 工资收入覆盖率低阈值
    income_coverage_ratio_high: float = 0.9  # 工资收入覆盖率高阈值
    extra_income_ratio_high: float = 0.3  # 额外收入占比高阈值

    # 借贷行为阈值
    borrowing_freq_high: int = 10  # 高频借贷次数阈值
    borrowing_amount_large: float = 10.0  # 大额借贷金额阈值（万元）
    borrowing_repayment_ratio_high: float = 2.0  # 借贷还款比高阈值

    # 消费特征阈值
    consumption_amount_large: float = 5.0  # 大额消费金额阈值（万元）
    consumption_freq_high: int = 5  # 高频大额消费次数阈值
    consumption_income_ratio_high: float = 1.2  # 消费收入比高阈值

    # 资金流向阈值
    transfer_freq_high: int = 20  # 高频转账次数阈值
    transfer_amount_large: float = 20.0  # 大额转账金额阈值（万元）
    account_diversity_high: int = 5  # 账户多样性高阈值

    # 现金操作阈值
    cash_amount_large: float = 5.0  # 大额现金操作阈值（万元）
    cash_freq_high: int = 5  # 高频现金操作次数阈值
    cash_single_large: float = 3.0  # 单笔大额现金操作阈值（万元）

    # 风险等级阈值
    risk_score_low: int = 30  # 关注级分数下限
    risk_score_high: int = 42  # 高风险分数下限


class PersonalFundFeatureAnalyzer:
    """
    个人资金特征分析器

    核心功能：
    1. 分析个人资金行为的五个维度
    2. 生成专业的审计描述话术
    3. 识别风险点和红旗标记
    4. 提供证据链支持
    
    注意：所有金额计算统一使用"万元"作为单位
    """

    @staticmethod
    def to_wan_yuan(amount: float, unit: str = 'fen') -> float:
        """
        转换为万元单位
        
        Args:
            amount: 金额数值
            unit: 输入单位
                  - 'fen': 分（银行流水原始单位）
                  - 'yuan': 元
                  - 'wan': 万元（不转换）
        
        Returns:
            万元单位的金额
        """
        if unit == 'fen':
            return amount / 100000  # 【修复】分 → 万元 (100000分 = 10000元 = 1万元)
        elif unit == 'yuan':
            return amount / 10000  # 元 → 万元
        elif unit == 'wan':
            return amount  # 万元 → 万元
        else:
            raise ValueError(f"不支持的单位: {unit}")

    def _normalize_transactions(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """规范化交易字段，避免因列名缺失导致分析失败。"""
        if transactions is None or not isinstance(transactions, pd.DataFrame):
            return pd.DataFrame(
                columns=[
                    "date",
                    "transaction_type",
                    "amount",
                    "counterparty",
                    "description",
                    "account",
                    "account_number",
                    "direction",
                ]
            )

        tx = transactions.copy()

        if "amount" not in tx.columns:
            tx["amount"] = 0
        tx["amount"] = utils.normalize_amount_series(tx["amount"], "amount")

        if "counterparty" not in tx.columns:
            tx["counterparty"] = ""
        tx["counterparty"] = tx["counterparty"].fillna("").astype(str)

        if "description" not in tx.columns:
            tx["description"] = ""
        tx["description"] = tx["description"].fillna("").astype(str)

        if "direction" not in tx.columns:
            tx["direction"] = "other"
        tx["direction"] = tx["direction"].fillna("other").astype(str)

        if "transaction_type" not in tx.columns:
            tx["transaction_type"] = tx["direction"].map(
                {"income": "转账收入", "expense": "转账支出"}
            ).fillna("其他")
        tx["transaction_type"] = tx["transaction_type"].fillna("其他").astype(str)

        if "account" not in tx.columns and "account_number" in tx.columns:
            tx["account"] = tx["account_number"]
        if "account_number" not in tx.columns and "account" in tx.columns:
            tx["account_number"] = tx["account"]
        if "account" not in tx.columns:
            tx["account"] = ""
        if "account_number" not in tx.columns:
            tx["account_number"] = ""

        tx["account"] = tx["account"].fillna("").astype(str)
        tx["account_number"] = tx["account_number"].fillna("").astype(str)
        return tx

    def __init__(self, thresholds: Optional[AnalysisThresholds] = None):
        """初始化分析器"""
        self.thresholds = thresholds or AnalysisThresholds()
        self.description_templates = self._init_description_templates()

    def _init_description_templates(self) -> Dict[str, List[str]]:
        """初始化描述话术模板"""
        return {
            "income_expense_mismatch": [
                "该人员工资性收入累计{wage_income:.2f}万元，但同期消费支出{total_expense:.2f}万元，存在{gap:.2f}万元的收支缺口，工资收入仅能覆盖{coverage_ratio:.1f}%的消费支出，收入结构明显失衡，存在资金来源不明风险。",
                "经分析，该人员工资性收入{wage_income:.2f}万元，收入总额{total_income:.2f}万元，但消费支出达{total_expense:.2f}万元，收支缺口{gap:.2f}万元，需核查其资金来源。"
            ],
            "borrowing_dependent": [
                "该人员存在频繁借贷行为，累计借款{borrow_total:.2f}万元，还款{repay_total:.2f}万元，借贷资金主要用于{borrow_purpose}，存在明显的资金周转压力，需核实其债务偿还能力及资金来源。",
                "该人员借贷行为频繁，借款{borrow_total:.2f}万元，涉及{borrow_count}笔，其中单笔最大借款{max_borrow:.2f}万元，存在资金周转依赖风险。"
            ],
            "extra_income_high": [
                "该人员收入中包含{income_types}等额外劳务收入，累计{extra_income:.2f}万元，占其总收入的{extra_ratio:.1f}%，但仍不足以支撑其{consumption_feature}，需进一步核查其劳务收入的真实性和稳定性。",
                "该人员额外收入{extra_income:.2f}万元，包括{income_types}等，收入结构较为复杂，需核实收入的真实性和合规性。"
            ],
            "fund_diverse_flow": [
                "该人员资金在多个账户间频繁流转，累计转账{transfer_total:.2f}万元，涉及{account_count}个账户，存在资金分散特征，需核查其资金流向和用途。",
                "该人员跨账户资金流转频繁，涉及{account_count}个账户，累计流转{transfer_total:.2f}万元，资金去向复杂，需进一步追踪。"
            ],
            "cash_abnormal": [
                "该人员存在大额现金存取行为，累计现金操作{cash_total:.2f}万元，其中单笔最大现金操作{max_single_cash:.2f}万元，现金用途{cash_usage}，需核实现金去向和用途。",
                "该人员现金操作频繁，累计{cash_count}次，涉及{cash_total:.2f}万元，需核实现金交易的合规性。"
            ],
            "normal_income": [
                "该人员工资性收入占比较高，收入结构较为合理，收支基本平衡。",
                "该人员收入来源相对稳定，未见明显异常。"
            ],
            "normal_expense": [
                "该人员消费水平与收入水平基本匹配，消费模式未见明显异常。",
                "该人员消费支出合理，未见异常大额消费。"
            ],
            "normal_borrowing": [
                "该人员借贷行为正常，未见频繁借贷情况。",
                "该人员借贷规模适中，债务风险可控。"
            ]
        }

    def analyze(self,
                 person_profile: Dict[str, Any],
                 person_transactions: pd.DataFrame,
                 family_members: Optional[List[str]] = None,
                 suspicions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行完整的个人资金特征分析

        参数:
            person_profile: 个人资金画像数据
            person_transactions: 个人交易明细（DataFrame）
            family_members: 家庭成员列表（用于识别家庭内部转账）
            suspicions: 疑点检测结果

        返回:
            分析结果字典
        """
        family_members = family_members or []
        person_transactions = self._normalize_transactions(person_transactions)

        # 执行各维度分析
        dimensions = {
            "income_expense_match": self._analyze_income_expense_match(
                person_profile, person_transactions
            ),
            "borrowing_behavior": self._analyze_borrowing_behavior(
                person_profile, person_transactions, family_members
            ),
            "consumption_pattern": self._analyze_consumption_pattern(
                person_profile, person_transactions
            ),
            "cash_flow_pattern": self._analyze_cash_flow_pattern(
                person_profile, person_transactions, family_members
            ),
            "cash_operation": self._analyze_cash_operation(
                person_transactions
            )
        }

        # 计算总体评分和风险等级
        total_score = sum(dim["score"] for dim in dimensions.values())
        evidence_score = total_score
        risk_level = self._calculate_risk_level(evidence_score)

        # 生成总体特征描述
        overall_feature = self._generate_overall_feature(dimensions, risk_level)

        # 生成审计描述话术
        audit_descriptions = self._generate_audit_descriptions(dimensions)

        # 生成风险排除说明
        risk_exclusions = self._generate_risk_exclusions(dimensions)

        # 识别红旗标记
        red_flags = self._identify_red_flags(dimensions)

        return {
            "overall_feature": overall_feature,
            "risk_level": risk_level,
            "evidence_score": evidence_score,
            "dimensions": dimensions,
            "audit_description": audit_descriptions,
            "risk_exclusions": risk_exclusions,
            "red_flags": red_flags
        }

    def _analyze_income_expense_match(self,
                                       person_profile: Dict[str, Any],
                                       transactions: pd.DataFrame) -> Dict[str, Any]:
        """
        分析收支匹配度
        
        注意：所有金额统一使用"万元"单位
        """
        # 提取数据
        # wage_income 已是万元单位（来自 profiles.total_salary）
        wage_income = person_profile.get("wage_income", 0)
        
        # total_income 来自 gen_report_final.py，已除以10000，是万元单位
        total_income = person_profile.get("total_income", 0)
        
        extra_income = total_income - wage_income

        # 计算消费支出（包含取现）
        expense_mask = transactions["transaction_type"].isin(["消费"])  # 【修复】移除转账支出、取现、提现
        # 交易数据是分，需要转换为万元
        total_expense = self.to_wan_yuan(transactions[expense_mask]["amount"].sum(), 'fen')

        # 计算关键指标
        gap = total_expense - wage_income
        coverage_ratio = (wage_income / total_expense * 100) if total_expense > 0 else 100
        extra_ratio = (extra_income / total_income * 100) if total_income > 0 else 0

        # 评分（连续评分，提升区分度）
        score = 0.0
        low_threshold_pct = self.thresholds.income_coverage_ratio_low * 100
        high_threshold_pct = self.thresholds.income_coverage_ratio_high * 100

        if coverage_ratio < low_threshold_pct:
            score += 12.0 + min(6.0, (low_threshold_pct - coverage_ratio) / 5.0)
        elif coverage_ratio < high_threshold_pct:
            score += 6.0 + min(6.0, (high_threshold_pct - coverage_ratio) / 8.0)

        if gap > 0 and total_expense > 0:
            gap_ratio = gap / total_expense
            score += min(6.0, gap_ratio * 12.0)

        high_extra_ratio_pct = self.thresholds.extra_income_ratio_high * 100
        if extra_ratio > high_extra_ratio_pct:
            score += min(4.0, (extra_ratio - high_extra_ratio_pct) / 10.0)

        score = round(min(20.0, max(0.0, score)), 1)

        # 识别额外收入类型
        extra_income_types = self._identify_extra_income_types(transactions)

        # 生成描述
        if coverage_ratio < low_threshold_pct:
            description = f"收支严重不匹配，工资收入仅能覆盖{coverage_ratio:.1f}%的消费支出，存在{gap:.2f}万元资金缺口。"
        elif coverage_ratio < high_threshold_pct:
            description = f"收支匹配度偏低，工资收入覆盖{coverage_ratio:.1f}%的消费支出，存在{gap:.2f}万元资金缺口。"
        else:
            description = f"收支基本匹配，工资收入能够覆盖消费支出。"

        # 生成证据
        evidence = [
            {"type": "工资收入", "value": f"{wage_income:.2f}万元", "description": "工资性收入总额"},
            {"type": "总收入", "value": f"{total_income:.2f}万元", "description": "总收入"},
            {"type": "消费支出", "value": f"{total_expense:.2f}万元", "description": "同期消费支出"},
            {"type": "收支缺口", "value": f"{gap:.2f}万元", "description": "资金缺口"},
            {"type": "工资覆盖率", "value": f"{coverage_ratio:.1f}%", "description": "工资对消费的覆盖比例"}
        ]

        if extra_income_types:
            evidence.append({
                "type": "额外收入类型",
                "value": "、".join(extra_income_types),
                "description": "非工资性收入类型"
            })

        return {
            "score": score,
            "description": description,
            "evidence": evidence,
            "metrics": {
                "wage_income": wage_income,
                "total_income": total_income,
                "total_expense": total_expense,
                "extra_income": extra_income,
                "gap": gap,
                "coverage_ratio": coverage_ratio,
                "extra_ratio": extra_ratio,
                "extra_income_types": extra_income_types
            }
        }

    def _analyze_borrowing_behavior(self,
                                     person_profile: Dict[str, Any],
                                     transactions: pd.DataFrame,
                                     family_members: List[str]) -> Dict[str, Any]:
        """分析借贷行为"""
        # 识别借贷交易
        borrow_mask = transactions["transaction_type"].isin(["借款", "贷款"])
        repay_mask = transactions["transaction_type"].isin(["还款"])

        borrow_txns = transactions[borrow_mask]
        repay_txns = transactions[repay_mask]

        # 计算借贷数据（交易数据是分，需要转换为万元）
        borrow_total = self.to_wan_yuan(borrow_txns["amount"].sum(), 'fen') if not borrow_txns.empty else 0
        repay_total = self.to_wan_yuan(repay_txns["amount"].sum(), 'fen') if not repay_txns.empty else 0
        borrow_count = len(borrow_txns)

        # 识别敏感对手方（非家庭成员）
        sensitive_counterparties = self._identify_sensitive_counterparties(
            borrow_txns, family_members
        )

        # 计算评分（连续评分，提升区分度）
        score = 0.0
        if borrow_count >= self.thresholds.borrowing_freq_high:
            score += 12.0 + min(
                4.0, (borrow_count - self.thresholds.borrowing_freq_high) / 5.0
            )
        elif borrow_count >= 5:
            score += 6.0 + min(4.0, (borrow_count - 5) / 5.0)
        elif borrow_count > 0:
            score += min(5.0, borrow_count * 1.2)

        # 单笔大额借贷加分
        if not borrow_txns.empty:
            max_borrow = self.to_wan_yuan(borrow_txns["amount"].max(), 'fen')
            if max_borrow >= self.thresholds.borrowing_amount_large:
                score += min(
                    5.0,
                    2.0
                    + (max_borrow - self.thresholds.borrowing_amount_large)
                    / max(self.thresholds.borrowing_amount_large, 1.0)
                    * 2.0,
                )
        else:
            max_borrow = 0.0

        # 借还比加分（借多还少风险更高）
        borrow_repay_ratio = 0.0
        if borrow_total > 0:
            if repay_total > 0:
                borrow_repay_ratio = borrow_total / repay_total
            else:
                borrow_repay_ratio = float("inf")

            if borrow_repay_ratio >= self.thresholds.borrowing_repayment_ratio_high:
                if borrow_repay_ratio == float("inf"):
                    score += 4.0
                else:
                    score += min(
                        4.0,
                        1.0
                        + (borrow_repay_ratio - self.thresholds.borrowing_repayment_ratio_high)
                        * 2.0,
                    )

        # 敏感对手方加分
        if len(sensitive_counterparties) > 0:
            score += min(4.0, 1.0 + len(sensitive_counterparties) * 1.2)

        score = round(min(20.0, max(0.0, score)), 1)

        # 生成描述
        if borrow_count >= self.thresholds.borrowing_freq_high:
            description = f"存在频繁借贷行为，累计借款{borrow_total:.2f}万元，涉及{borrow_count}笔交易，存在明显的资金周转压力。"
        elif borrow_count > 0:
            description = f"存在借贷行为，累计借款{borrow_total:.2f}万元，涉及{borrow_count}笔交易。"
        else:
            description = "未见明显借贷行为。"

        if sensitive_counterparties:
            description += f" 向{len(sensitive_counterparties)}个敏感对手方借贷。"

        # 生成证据
        evidence = [
            {"type": "借款总额", "value": f"{borrow_total:.2f}万元", "description": "累计借款金额"},
            {"type": "还款总额", "value": f"{repay_total:.2f}万元", "description": "累计还款金额"},
            {"type": "借款笔数", "value": str(borrow_count), "description": "借款交易次数"},
            {"type": "还款笔数", "value": str(len(repay_txns)), "description": "还款交易次数"}
        ]

        if not borrow_txns.empty:
            max_borrow = self.to_wan_yuan(borrow_txns["amount"].max(), 'fen')
            evidence.append({
                "type": "最大单笔借款",
                "value": f"{max_borrow:.2f}万元",
                "description": "单笔最大借款金额"
            })

        if sensitive_counterparties:
            evidence.append({
                "type": "敏感对手方",
                "value": f"{len(sensitive_counterparties)}个",
                "description": "非家庭成员的借贷对手方"
            })

        # 识别借贷用途
        borrow_purpose = self._infer_borrow_purpose(borrow_txns)

        return {
            "score": score,
            "description": description,
            "evidence": evidence,
            "metrics": {
                "borrow_total": borrow_total,
                "repay_total": repay_total,
                "borrow_count": borrow_count,
                "repay_count": len(repay_txns),
                "sensitive_counterparties": sensitive_counterparties,
                "borrow_purpose": borrow_purpose
            }
        }

    def _analyze_consumption_pattern(self,
                                      person_profile: Dict[str, Any],
                                      transactions: pd.DataFrame) -> Dict[str, Any]:
        """
        分析消费特征
        
        注意：所有金额统一使用"万元"单位
        """
        # 识别消费交易（扩展到包括日常转账、取现等，但排除投资、理财、还款等）
        consume_mask = transactions["transaction_type"].isin(["消费"])  # 【修复】移除转账支出、取现、提现
        # 排除投资、理财、还款等非消费性支出
        investment_mask = ~transactions["description"].str.contains(
            "投资|理财|基金|股票|债券|还贷|还款|贷款", na=False, case=False
        )
        consume_txns = transactions[consume_mask & investment_mask]

        # 计算消费数据（交易数据是分，需要转换为万元）
        total_consumption = self.to_wan_yuan(consume_txns["amount"].sum(), 'fen') if not consume_txns.empty else 0
        total_income = person_profile.get("total_income", 0)

        # 识别大额消费（threshold 使用万元单位，需要转换）
        large_consume_mask = consume_txns["amount"] >= self.thresholds.consumption_amount_large * 100000
        large_consumes = consume_txns[large_consume_mask]

        # 计算消费收入比
        consumption_income_ratio = (total_consumption / total_income) if total_income > 0 else 0

        # 计算评分（连续评分，提升区分度）
        score = 0.0
        if consumption_income_ratio >= self.thresholds.consumption_income_ratio_high:
            score += 12.0 + min(
                6.0,
                (consumption_income_ratio - self.thresholds.consumption_income_ratio_high)
                * 8.0,
            )
        elif consumption_income_ratio >= 0.8:
            score += 7.0 + min(5.0, (consumption_income_ratio - 0.8) * 10.0)
        elif consumption_income_ratio >= 0.5:
            score += 3.0 + min(3.0, (consumption_income_ratio - 0.5) * 6.0)

        if len(large_consumes) >= self.thresholds.consumption_freq_high:
            score += 4.0
        elif len(large_consumes) > 0:
            score += min(3.0, len(large_consumes) * 0.6)

        if not large_consumes.empty:
            max_large_consume = self.to_wan_yuan(large_consumes["amount"].max(), 'fen')
            if max_large_consume >= self.thresholds.consumption_amount_large * 2:
                score += 2.0

        score = round(min(20.0, max(0.0, score)), 1)

        # 生成描述
        if consumption_income_ratio >= self.thresholds.consumption_income_ratio_high:
            description = f"消费支出明显偏高，消费总额{total_consumption:.2f}万元，是收入的{consumption_income_ratio:.1f}倍，消费模式异常。"
        elif len(large_consumes) >= self.thresholds.consumption_freq_high:
            description = f"频繁大额消费，累计{len(large_consumes)}笔大额消费，涉及金额{large_consumes['amount'].sum()/10000:.2f}万元。"
        elif total_consumption > 0:
            description = f"消费支出{total_consumption:.2f}万元，消费水平与收入基本匹配。"
        else:
            description = "未见明显消费记录。"

        # 生成证据
        evidence = [
            {"type": "消费总额", "value": f"{total_consumption:.2f}万元", "description": "累计消费金额"},
            {"type": "消费笔数", "value": str(len(consume_txns)), "description": "消费交易次数"},
            {"type": "消费收入比", "value": f"{consumption_income_ratio * 100:.1f}%", "description": "消费占收入比例"},
            {"type": "大额消费笔数", "value": str(len(large_consumes)), "description": f"单笔超过{self.thresholds.consumption_amount_large}万元的消费次数"}
        ]

        if not large_consumes.empty:
            max_consume = self.to_wan_yuan(large_consumes["amount"].max(), 'fen')
            evidence.append({
                "type": "最大单笔消费",
                "value": f"{max_consume:.2f}万元",
                "description": "单笔最大消费金额"
            })

        # 分析消费对手方
        consume_counterparties = consume_txns["counterparty"].value_counts().head(5)
        if len(consume_counterparties) > 0:
            evidence.append({
                "type": "主要消费对手方",
                "value": "、".join(consume_counterparties.index[:3].tolist()),
                "description": "消费频率最高的三个对手方"
            })

        return {
            "score": score,
            "description": description,
            "evidence": evidence,
            "metrics": {
                "total_consumption": total_consumption,
                "consume_count": len(consume_txns),
                "large_consume_count": len(large_consumes),
                "consumption_income_ratio": consumption_income_ratio,
                "consume_counterparties": consume_counterparties.to_dict()
            }
        }

    def _analyze_cash_flow_pattern(self,
                                     person_profile: Dict[str, Any],
                                     transactions: pd.DataFrame,
                                     family_members: List[str]) -> Dict[str, Any]:
        """
        分析资金流向特征
        
        注意：所有金额统一使用"万元"单位
        """
        # 识别转账交易
        transfer_mask = transactions["transaction_type"].isin(["转账", "转账支出", "转账收入"])
        transfer_txns = transactions[transfer_mask].copy()

        # 【修复】识别并排除家庭内部转账
        if family_members and not transfer_txns.empty:
            family_mask = transfer_txns["counterparty"].isin(family_members)
            external_transfer_txns = transfer_txns[~family_mask]
            family_internal_total = self.to_wan_yuan(
                transfer_txns[family_mask]["amount"].sum(), 'fen'
            )
        else:
            external_transfer_txns = transfer_txns
            family_internal_total = 0

        # 使用外部转账计算风险和统计
        transfer_total = self.to_wan_yuan(external_transfer_txns["amount"].sum(), 'fen') if not external_transfer_txns.empty else 0
        transfer_count = len(external_transfer_txns)

        # 识别涉及账户
        account_col = "account_number" if "account_number" in transactions.columns else "account"
        accounts = transactions[account_col].unique()
        account_count = len(accounts)

        # 识别跨账户流转
        unique_counterparties = external_transfer_txns["counterparty"].nunique() if not external_transfer_txns.empty else 0

        # 计算评分（连续评分，提升区分度）
        score = 0.0
        if transfer_count >= self.thresholds.transfer_freq_high:
            score += 11.0 + min(
                4.0, (transfer_count - self.thresholds.transfer_freq_high) / 10.0
            )
        elif transfer_count >= 10:
            score += 6.0 + min(4.0, (transfer_count - 10) / 10.0)
        elif transfer_count > 0:
            score += min(4.0, transfer_count / 3.0)

        if account_count >= self.thresholds.account_diversity_high:
            score += min(
                4.0, 2.0 + (account_count - self.thresholds.account_diversity_high) * 0.5
            )
        elif account_count >= 3:
            score += 1.5

        if unique_counterparties >= 10:
            score += 2.5
        elif unique_counterparties >= 5:
            score += 1.5

        # 大额转账加分
        if not external_transfer_txns.empty:
            max_transfer = self.to_wan_yuan(external_transfer_txns["amount"].max(), 'fen')
            if max_transfer >= self.thresholds.transfer_amount_large:
                score += min(
                    4.0,
                    2.0
                    + (max_transfer - self.thresholds.transfer_amount_large)
                    / max(self.thresholds.transfer_amount_large, 1.0)
                    * 2.0,
                )
        else:
            max_transfer = 0.0

        score = round(min(20.0, max(0.0, score)), 1)

        # 生成描述
        if transfer_count >= self.thresholds.transfer_freq_high:
            description = f"资金流转频繁，累计转账{transfer_total:.2f}万元，涉及{account_count}个账户，资金去向复杂。"
        elif account_count >= self.thresholds.account_diversity_high:
            description = f"跨账户资金流转较多，涉及{account_count}个账户，存在资金分散特征。"
        elif transfer_count > 0:
            description = f"存在一定的资金流转，累计转账{transfer_total:.2f}万元。"
        else:
            description = "资金流向相对集中，未见频繁跨账户流转。"

        # 生成证据
        evidence = [
            {"type": "转账总额", "value": f"{transfer_total:.2f}万元", "description": "累计转账金额"},
            {"type": "转账笔数", "value": str(transfer_count), "description": "转账交易次数"},
            {"type": "涉及账户数", "value": str(account_count), "description": "涉及的银行账户数量"},
            {"type": "交易对手方数", "value": str(unique_counterparties), "description": "转账涉及的对手方数量"}
        ]

        if not external_transfer_txns.empty:
            max_transfer = self.to_wan_yuan(external_transfer_txns["amount"].max(), 'fen')
            evidence.append({
                "type": "最大单笔转账",
                "value": f"{max_transfer:.2f}万元",
                "description": "单笔最大转账金额"
            })

        # 分析资金主要流向
        fund_flow_directions = self._analyze_fund_flow_direction(external_transfer_txns, person_profile)
        if fund_flow_directions:
            evidence.append({
                "type": "资金主要流向",
                "value": "、".join(fund_flow_directions[:3]),
                "description": "资金主要流向领域"
            })
        if family_internal_total > 0:
            evidence.append(
                {
                    "type": "家庭内部转账",
                    "value": f"{family_internal_total:.2f}万元",
                    "description": "已从外部资金流向风险统计中排除",
                }
            )

        return {
            "score": score,
            "description": description,
            "evidence": evidence,
            "metrics": {
                "transfer_total": transfer_total,
                "transfer_count": transfer_count,
                "account_count": account_count,
                "unique_counterparties": unique_counterparties,
                "family_internal_total": family_internal_total,
                "fund_flow_directions": fund_flow_directions
            }
        }

    def _analyze_cash_operation(self,
                                 transactions: pd.DataFrame) -> Dict[str, Any]:
        """
        分析现金操作特征
        
        注意：所有金额统一使用"万元"单位
        """
        # 识别现金交易
        cash_mask = transactions["transaction_type"].isin(["存现", "取现"])
        cash_txns = transactions[cash_mask]

        # 计算现金操作数据（交易数据是分，需要转换为万元）
        cash_total = self.to_wan_yuan(cash_txns["amount"].sum(), 'fen') if not cash_txns.empty else 0
        cash_count = len(cash_txns)

        # 识别大额现金操作（threshold 使用万元单位，需要转换）
        large_cash_mask = cash_txns["amount"] >= self.thresholds.cash_amount_large * 100000
        large_cash_txns = cash_txns[large_cash_mask]

        # 计算评分（连续评分，提升区分度）
        score = 0.0
        if cash_count >= self.thresholds.cash_freq_high:
            score += 10.0 + min(4.0, (cash_count - self.thresholds.cash_freq_high) * 0.6)
        elif cash_count >= 3:
            score += 6.0 + min(3.0, (cash_count - 3) * 0.7)
        elif cash_count > 0:
            score += min(4.0, cash_count * 1.2)

        # 大额现金操作加分
        if not cash_txns.empty:
            max_single_cash = self.to_wan_yuan(cash_txns["amount"].max(), 'fen')
            if max_single_cash >= self.thresholds.cash_single_large:
                score += min(
                    4.0,
                    1.0
                    + (max_single_cash - self.thresholds.cash_single_large)
                    / max(self.thresholds.cash_single_large, 1.0)
                    * 3.0,
                )
        else:
            max_single_cash = 0.0

        if cash_total >= self.thresholds.cash_amount_large:
            score += min(
                4.0,
                1.5
                + (cash_total - self.thresholds.cash_amount_large)
                / max(self.thresholds.cash_amount_large, 1.0)
                * 2.0,
            )

        # 生成描述
        if cash_count >= self.thresholds.cash_freq_high:
            description = f"现金操作频繁，累计{cash_count}次，涉及金额{cash_total:.2f}万元，需核实现金交易合规性。"
        elif not large_cash_txns.empty:
            description = f"存在大额现金操作，单笔最大{max_single_cash:.2f}万元，需核实现金去向。"
        elif cash_count > 0:
            description = f"存在现金操作，累计{cash_count}次，涉及金额{cash_total:.2f}万元。"
        else:
            description = "未见异常现金操作。"

        # 生成证据
        evidence = [
            {"type": "现金操作总额", "value": f"{cash_total:.2f}万元", "description": "累计现金操作金额"},
            {"type": "现金操作次数", "value": str(cash_count), "description": "现金交易次数"},
            {"type": "大额现金操作次数", "value": str(len(large_cash_txns)), "description": f"单笔超过{self.thresholds.cash_amount_large}万元的次数"}
        ]

        if not cash_txns.empty:
            max_single_cash = self.to_wan_yuan(cash_txns["amount"].max(), 'fen')
            evidence.append({
                "type": "最大单笔现金操作",
                "value": f"{max_single_cash:.2f}万元",
                "description": "单笔最大现金操作金额"
            })

        # 分析现金账户分散情况
        account_col = "account" if "account" in cash_txns.columns else "account_number"
        cash_accounts = cash_txns[account_col].nunique() if (not cash_txns.empty and account_col in cash_txns.columns) else 0
        if cash_accounts > 1:
            score += min(2.0, (cash_accounts - 1) * 0.7)
            evidence.append({
                "type": "涉及现金账户数",
                "value": str(cash_accounts),
                "description": "涉及现金操作的账户数量"
            })

        score = round(min(20.0, max(0.0, score)), 1)

        return {
            "score": score,
            "description": description,
            "evidence": evidence,
            "metrics": {
                "cash_total": cash_total,
                "cash_count": cash_count,
                "large_cash_count": len(large_cash_txns),
                "max_single_cash": max_single_cash if not cash_txns.empty else 0,
                "cash_accounts": cash_accounts
            }
        }

    def _identify_extra_income_types(self, transactions: pd.DataFrame) -> List[str]:
        """识别额外收入类型"""
        income_types = []

        # 识别特定类型的收入交易（扩展识别范围）
        income_keywords = {
            "讲课费": ["讲课", "培训", "授课"],
            "评审费": ["评审", "评议"],
            "咨询费": ["咨询", "顾问"],
            "劳务费": ["劳务", "服务"],
            "稿酬": ["稿费", "版权"],
            "投资收益": ["分红", "股息", "利息", "理财", "基金"],
            "租金收入": ["租金", "租赁"],
            "经营收入": ["经营", "销售", "营业"],
            "报销收入": ["报销", "补贴"],
            "奖金收入": ["奖金", "绩效"],
            "补偿收入": ["补偿", "赔偿"]
        }

        for income_type, keywords in income_keywords.items():
            keyword_mask = transactions["description"].str.contains(
                "|".join(keywords), na=False, case=False
            )
            if keyword_mask.any():
                income_types.append(income_type)

        # 如果没有识别到具体类型，但有"转账收入"，标记为"其他劳务收入"
        if not income_types and "转账收入" in transactions["transaction_type"].values:
            income_types.append("其他劳务收入")

        return income_types

    def _identify_sensitive_counterparties(self,
                                            borrow_txns: pd.DataFrame,
                                            family_members: List[str]) -> List[str]:
        """识别敏感借贷对手方"""
        if borrow_txns.empty:
            return []

        sensitive = []
        counterparties = borrow_txns["counterparty"].unique()

        for counterparty in counterparties:
            # 排除家庭成员
            if not any(family in counterparty for family in family_members):
                sensitive.append(counterparty)

        return sensitive

    def _infer_borrow_purpose(self, borrow_txns: pd.DataFrame) -> str:
        """推断借贷用途"""
        if borrow_txns.empty:
            return "未知"

        # 从交易描述推断用途
        descriptions = borrow_txns["description"].tolist()

        # 常见用途关键词
        purpose_keywords = {
            "购房": ["购房", "买房", "房产"],
            "装修": ["装修", "家装"],
            "经营": ["经营", "生意", "公司"],
            "消费": ["消费", "购物"],
            "医疗": ["医疗", "医院"],
            "教育": ["教育", "学费", "培训"]
        }

        for purpose, keywords in purpose_keywords.items():
            for desc in descriptions:
                if any(keyword in desc for keyword in keywords):
                    return purpose

        return "日常生活周转"

    def _analyze_fund_flow_direction(self,
                                      transfer_txns: pd.DataFrame,
                                      person_profile: Dict[str, Any]) -> List[str]:
        """分析资金主要流向"""
        if transfer_txns.empty:
            return []

        # 从交易描述推断流向
        descriptions = transfer_txns["description"].tolist()

        # 常见流向关键词
        flow_keywords = {
            "理财": ["理财", "基金", "股票", "投资"],
            "房产": ["房产", "购房", "房贷"],
            "日常消费": ["超市", "商场", "购物"],
            "借贷": ["借贷", "借款", "贷款"],
            "亲友转账": ["父母", "配偶", "子女"]
        }

        flows = []
        for flow, keywords in flow_keywords.items():
            for desc in descriptions:
                if any(keyword in desc for keyword in keywords):
                    flows.append(flow)
                    break

        return list(set(flows))

    def _calculate_risk_level(self, evidence_score: float) -> str:
        """计算风险等级"""
        if evidence_score >= self.thresholds.risk_score_high:
            return "高风险"
        elif evidence_score >= self.thresholds.risk_score_low:
            return "关注级"
        else:
            return "低风险"

    def _generate_overall_feature(self,
                                   dimensions: Dict[str, Dict[str, Any]],
                                   risk_level: str) -> str:
        """生成总体特征描述"""
        # 获取各维度评分
        scores = {name: dim["score"] for name, dim in dimensions.items()}

        # 找出主要问题维度
        high_risk_dims = [name for name, score in scores.items() if score >= 15]
        medium_risk_dims = [name for name, score in scores.items() if 5 <= score < 15]

        features = []
        if high_risk_dims:
            feature_map = {
                "income_expense_match": "收支严重不匹配",
                "borrowing_behavior": "存在频繁借贷行为",
                "consumption_pattern": "消费模式异常",
                "cash_flow_pattern": "资金流向复杂",
                "cash_operation": "现金操作异常"
            }
            features.extend([feature_map.get(dim, dim) for dim in high_risk_dims])

        if features:
            return f"{'、'.join(features)}，{risk_level}"
        else:
            return f"资金行为基本正常，{risk_level}"

    def _generate_audit_descriptions(self,
                                      dimensions: Dict[str, Dict[str, Any]]) -> List[str]:
        """生成审计描述话术"""
        descriptions = []

        # 收支匹配度描述
        income_exp = dimensions["income_expense_match"]
        if income_exp["score"] >= 10:
            metrics = income_exp["metrics"]
            income_types = "、".join(metrics["extra_income_types"]) if metrics["extra_income_types"] else "无"
            template = self.description_templates["income_expense_mismatch"][0]
            descriptions.append(template.format(
                wage_income=metrics["wage_income"],
                total_expense=metrics["total_expense"],
                gap=metrics["gap"],
                coverage_ratio=metrics["coverage_ratio"]
            ))

            if metrics["extra_income"] > 0:
                template = self.description_templates["extra_income_high"][0]
                descriptions.append(template.format(
                    income_types=income_types,
                    extra_income=metrics["extra_income"],
                    extra_ratio=metrics["extra_ratio"],
                    consumption_feature="日常开销"
                ))

        # 借贷行为描述
        borrowing = dimensions["borrowing_behavior"]
        if borrowing["score"] >= 10:
            metrics = borrowing["metrics"]
            template = self.description_templates["borrowing_dependent"][0]
            descriptions.append(template.format(
                borrow_total=metrics["borrow_total"],
                repay_total=metrics["repay_total"],
                borrow_purpose=metrics["borrow_purpose"]
            ))

        # 消费特征描述
        consumption = dimensions["consumption_pattern"]
        if consumption["score"] >= 10:
            metrics = consumption["metrics"]
            if metrics["consumption_income_ratio"] >= 1.0:
                descriptions.append(
                    f"该人员消费支出明显偏高，消费总额{metrics['total_consumption']:.2f}万元，"
                    f"是收入的{metrics['consumption_income_ratio']:.1f}倍，消费模式异常。"
                )

        # 资金流向描述
        cash_flow = dimensions["cash_flow_pattern"]
        if cash_flow["score"] >= 10:
            metrics = cash_flow["metrics"]
            template = self.description_templates["fund_diverse_flow"][0]
            descriptions.append(template.format(
                transfer_total=metrics["transfer_total"],
                account_count=metrics["account_count"]
            ))

        # 现金操作描述
        cash_op = dimensions["cash_operation"]
        if cash_op["score"] >= 10:
            metrics = cash_op["metrics"]
            template = self.description_templates["cash_abnormal"][0]
            descriptions.append(template.format(
                cash_total=metrics["cash_total"],
                max_single_cash=metrics["max_single_cash"],
                cash_usage="需进一步核实" if metrics["cash_total"] > 10 else "相对正常"
            ))

        return descriptions

    def _generate_risk_exclusions(self,
                                   dimensions: Dict[str, Dict[str, Any]]) -> List[str]:
        """生成风险排除说明"""
        exclusions = []

        # 收支正常
        if dimensions["income_expense_match"]["score"] < 5:
            exclusions.append("工资收入覆盖正常，收支结构合理")

        # 消费正常
        if dimensions["consumption_pattern"]["score"] < 5:
            exclusions.append("消费水平与收入匹配，无异常消费")

        # 借贷正常
        if dimensions["borrowing_behavior"]["score"] < 5:
            exclusions.append("未见频繁借贷，债务风险可控")

        # 资金流向正常
        if dimensions["cash_flow_pattern"]["score"] < 5:
            exclusions.append("资金流向集中且合理")

        # 现金操作正常
        if dimensions["cash_operation"]["score"] < 5:
            exclusions.append("现金操作正常，无大额异常")

        return exclusions

    def _identify_red_flags(self,
                           dimensions: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
        """识别红旗标记"""
        flags = []

        # 收支严重不匹配
        income_exp = dimensions["income_expense_match"]
        if income_exp["score"] >= 20:
            flags.append({
                "type": "收支失衡",
                "description": "工资收入无法覆盖消费支出，存在较大资金缺口",
                "strength": "强"
            })

        # 频繁借贷
        borrowing = dimensions["borrowing_behavior"]
        if borrowing["score"] >= 15:
            flags.append({
                "type": "借贷频繁",
                "description": "存在频繁借贷行为，资金周转压力大",
                "strength": "强"
            })

        # 大额现金操作
        cash_op = dimensions["cash_operation"]
        if cash_op["score"] >= 15:
            flags.append({
                "type": "现金异常",
                "description": "存在大额现金操作，需核实现金去向",
                "strength": "强"
            })

        # 资金分散
        cash_flow = dimensions["cash_flow_pattern"]
        if cash_flow["score"] >= 15:
            flags.append({
                "type": "资金分散",
                "description": "资金在多个账户间频繁流转，去向复杂",
                "strength": "中"
            })

        # 消费异常
        consumption = dimensions["consumption_pattern"]
        if consumption["score"] >= 15:
            flags.append({
                "type": "消费异常",
                "description": "消费水平明显偏高，存在异常消费模式",
                "strength": "中"
            })

        return flags


def create_example_data() -> tuple:
    """创建示例数据用于测试"""
    # 个人画像数据
    person_profile = {
        "wage_income": 25.0,  # 工资收入（万元）
        "total_income": 35.0,  # 总收入（万元）
        "name": "张三",
        "id": "123456"
    }

    # 交易数据 - 60笔交易
    transaction_types = (
        ["工资"] * 8 +  # 8笔工资
        ["消费"] * 20 +  # 20笔消费
        ["转账"] * 12 +  # 12笔转账
        ["借款"] * 4 +   # 4笔借款
        ["还款"] * 4 +   # 4笔回款
        ["存现"] * 6 +   # 6笔存现
        ["取现"] * 6     # 6笔取现
    )

    amounts = (
        [20000] * 8 +  # 工资
        [5000, 8000, 12000, 6000, 9000, 7000, 10000, 8000, 6000, 5000,
         15000, 25000, 8000, 6000, 5000, 18000, 7000, 6000, 5000, 4000] +  # 消费
        [15000, 20000, 25000, 30000, 10000, 15000, 20000, 25000, 10000,
         15000, 20000, 25000] +  # 转账
        [50000, 60000, 80000, 100000] +  # 借款
        [30000, 40000, 50000, 60000] +   # 还款
        [20000, 25000, 30000, 20000, 25000, 30000] +  # 存现
        [30000, 35000, 25000, 30000, 35000, 25000]    # 取现
    )

    counterparties = (
        ["单位"] * 8 +  # 工资
        ["超市A", "商场B", "餐厅C", "商场D", "超市E", "餐厅F", "商场G", "超市H",
         "餐厅I", "超市J", "商场K", "超市L", "餐厅M", "超市N", "商场O", "商场P",
         "超市Q", "餐厅R", "超市S", "商场T"] +  # 消费
        ["账户A", "账户B", "账户C", "账户D", "账户E", "账户F", "账户G", "账户H",
         "账户I", "账户J", "账户K", "账户L"] +  # 转账
        ["李四", "王五", "赵六", "孙七"] +  # 借款
        ["李四", "王五", "赵六", "孙七"] +  # 还款
        ["银行A", "银行B", "银行C", "银行A", "银行B", "银行C"] +  # 存现
        ["银行A", "银行B", "银行C", "银行A", "银行B", "银行C"]    # 取现
    )

    descriptions = (
        ["工资收入"] * 8 +  # 工资
        ["日常消费", "购物", "餐饮", "日常消费", "超市购物", "餐饮消费", "商场购物", "超市消费",
         "餐厅消费", "超市购物", "商场购物", "超市购物", "餐厅消费", "超市消费", "商场购物", "商场购物",
         "超市购物", "餐厅消费", "超市消费", "商场购物"] +  # 消费
        ["家庭转账", "投资理财", "理财转账", "资金周转", "家庭转账", "投资理财", "理财转账", "资金周转",
         "家庭转账", "投资理财", "理财转账", "资金周转"] +  # 转账
        ["借款用于日常周转", "借款购房", "借款投资", "借款购车"] +  # 借款
        ["归还借款", "归还借款", "归还借款", "归还借款"] +  # 还款
        ["现金存入", "现金存入", "现金存入", "现金存入", "现金存入", "现金存入"] +  # 存现
        ["现金支取", "现金支取", "现金支取", "现金支取", "现金支取", "现金支取"]    # 取现
    )

    accounts = (
        ["工资账户"] * 8 +  # 工资
        ["工资账户"] * 20 +  # 消费
        ["工资账户"] * 12 +  # 转账
        ["工资账户"] * 4 +   # 借款
        ["工资账户"] * 4 +   # 还款
        ["工资账户"] * 6 +   # 存现
        ["工资账户"] * 6     # 取现
    )

    transactions_data = {
        "date": pd.date_range("2023-01-01", periods=60, freq="D").tolist(),
        "transaction_type": transaction_types,
        "amount": amounts,
        "counterparty": counterparties,
        "description": descriptions,
        "account": accounts
    }

    transactions = pd.DataFrame(transactions_data)

    # 家庭成员
    family_members = ["配偶", "儿子", "女儿"]

    return person_profile, transactions, family_members


if __name__ == "__main__":
    # 创建分析器
    analyzer = PersonalFundFeatureAnalyzer()

    # 创建示例数据
    person_profile, transactions, family_members = create_example_data()

    # 执行分析
    result = analyzer.analyze(
        person_profile=person_profile,
        person_transactions=transactions,
        family_members=family_members
    )

    # 打印结果
    print("=" * 80)
    print("个人资金特征分析报告")
    print("=" * 80)
    print(f"\n【总体特征】{result['overall_feature']}")
    print(f"【风险等级】{result['risk_level']}")
    print(f"【证据评分】{result['evidence_score']}/100")

    print("\n" + "=" * 80)
    print("各维度分析结果")
    print("=" * 80)

    for dim_name, dim_result in result["dimensions"].items():
        print(f"\n【{dim_name}】")
        print(f"  评分: {dim_result['score']}/20")
        print(f"  描述: {dim_result['description']}")
        print(f"  证据:")
        for evidence in dim_result["evidence"]:
            print(f"    - {evidence['type']}: {evidence['value']} ({evidence['description']})")

    print("\n" + "=" * 80)
    print("审计描述话术")
    print("=" * 80)

    for i, desc in enumerate(result["audit_description"], 1):
        print(f"\n{i}. {desc}")

    if result["risk_exclusions"]:
        print("\n" + "=" * 80)
        print("风险排除说明")
        print("=" * 80)
        for exclusion in result["risk_exclusions"]:
            print(f"- {exclusion}")

    if result["red_flags"]:
        print("\n" + "=" * 80)
        print("红旗标记")
        print("=" * 80)
        for flag in result["red_flags"]:
            print(f"\n【{flag['type']}】({flag['strength']})")
            print(f"  {flag['description']}")

    print("\n" + "=" * 80)
