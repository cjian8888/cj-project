#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告 JSON Schema 定义模块 (Protocol Omega - Phase 1)

定义审计报告的标准化 JSON 结构，供 Jinja2 模板和 API 使用。
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


# ============================================================
# 报告模块定义
# ============================================================

@dataclass
class ReportMetadata:
    """报告元数据"""
    case_name: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "3.0.0"
    generator: str = "Protocol Omega Report Engine"
    core_persons: List[str] = field(default_factory=list)
    companies: List[str] = field(default_factory=list)
    date_range: Dict[str, str] = field(default_factory=dict)


@dataclass 
class SummaryModule:
    """资金概览模块"""
    total_income: float = 0.0
    total_expense: float = 0.0
    net_flow: float = 0.0
    transaction_count: int = 0
    high_risk_count: int = 0
    core_person_count: int = 0
    company_count: int = 0
    period_start: str = ""
    period_end: str = ""


@dataclass
class PersonalAssetItem:
    """个人资产条目"""
    entity_name: str = ""
    deposit_estimate: float = 0.0  # 存款估算（万元）
    wealth_holding: float = 0.0    # 理财持仓（万元）
    property_count: int = 0        # 房产套数
    property_value: float = 0.0    # 房产价值（万元）
    vehicle_count: int = 0         # 车辆数量
    total_income: float = 0.0      # 总收入
    total_expense: float = 0.0     # 总支出


@dataclass
class PersonalAssetsModule:
    """个人资产模块"""
    data: List[PersonalAssetItem] = field(default_factory=list)
    columns: List[str] = field(default_factory=lambda: [
        "户名", "存款估算(万)", "理财持仓(万)", "房产套数", 
        "房产价值(万)", "车辆数", "总收入", "总支出"
    ])


@dataclass
class SuspiciousTransaction:
    """可疑交易条目"""
    date: str = ""
    entity: str = ""
    counterparty: str = ""
    amount: float = 0.0
    direction: str = ""  # income / expense
    description: str = ""
    risk_level: str = "low"  # low / medium / high
    risk_reason: str = ""
    evidence_refs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SuspiciousTransactionsModule:
    """可疑交易模块"""
    data: List[SuspiciousTransaction] = field(default_factory=list)
    reasoning: str = ""
    total_count: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0


@dataclass
class FundCycleItem:
    """资金闭环条目"""
    cycle: List[str] = field(default_factory=list)
    cycle_str: str = ""
    length: int = 0
    total_amount: float = 0.0
    hops: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FundCyclesModule:
    """资金闭环模块"""
    data: List[FundCycleItem] = field(default_factory=list)
    total_count: int = 0
    reasoning: str = "资金闭环表明资金最终回流到起点，是典型的洗钱或利益输送结构。"


@dataclass
class CashCollisionItem:
    """现金时空伴随条目"""
    withdrawal_entity: str = ""
    deposit_entity: str = ""
    withdrawal_date: str = ""
    deposit_date: str = ""
    withdrawal_amount: float = 0.0
    deposit_amount: float = 0.0
    time_diff_hours: float = 0.0
    risk_level: str = "low"
    risk_reason: str = ""


@dataclass
class CashCollisionsModule:
    """现金时空伴随模块"""
    data: List[CashCollisionItem] = field(default_factory=list)
    total_count: int = 0
    reasoning: str = "现金在短时间内从一方取出，另一方存入，且金额相近，可能是现金过账或洗钱行为。"


@dataclass
class EvidencePack:
    """证据包 - 按实体聚合的所有发现"""
    entity: str = ""
    entity_type: str = ""  # person / company
    risk_score: int = 0
    risk_level: str = "low"
    summary: str = ""
    fund_cycles: List[Dict] = field(default_factory=list)
    high_risk_transactions: List[Dict] = field(default_factory=list)
    cash_collisions: List[Dict] = field(default_factory=list)
    periodic_income: List[Dict] = field(default_factory=list)
    sudden_changes: List[Dict] = field(default_factory=list)


@dataclass
class EvidencePacksModule:
    """证据包模块"""
    data: List[EvidencePack] = field(default_factory=list)
    total_entities: int = 0
    high_risk_entities: int = 0


# ============================================================
# 完整报告结构
# ============================================================

@dataclass
class AnalysisReport:
    """完整审计报告结构"""
    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    modules: Dict[str, Any] = field(default_factory=dict)
    
    def add_module(self, name: str, module: Any):
        """添加报告模块"""
        if hasattr(module, '__dataclass_fields__'):
            self.modules[name] = asdict(module)
        else:
            self.modules[name] = module
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "metadata": asdict(self.metadata),
            "modules": self.modules
        }
    
    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)


# ============================================================
# 报告生成 API 请求/响应模型
# ============================================================

AVAILABLE_SECTIONS = [
    "summary",
    "personal_assets", 
    "suspicious_transactions",
    "fund_cycles",
    "cash_collisions",
    "evidence_packs",
    "direct_transfers",
    "wealth_management",
    "income_analysis",
    "loan_analysis"
]

AVAILABLE_FORMATS = ["html", "json", "pdf"]


@dataclass
class ReportGenerateRequest:
    """报告生成请求"""
    sections: List[str] = field(default_factory=lambda: ["summary", "suspicious_transactions"])
    format: str = "html"
    case_name: str = "审计报告"
    include_evidence_refs: bool = True


@dataclass
class ReportGenerateResponse:
    """报告生成响应"""
    success: bool = True
    format: str = "html"
    content: str = ""
    download_url: Optional[str] = None
    error: Optional[str] = None


# ============================================================
# 审计术语映射（消除技术术语）
# ============================================================

AUDIT_TERM_MAP = {
    # 英文代码 -> 中文审计术语
    "income_spike": "资金突变",
    "cash_collision": "现金时空伴随",
    "counterparty": "交易对手",
    "balance_zeroed": "账户清空",
    "pass_through": "过账通道",
    "hub_node": "资金枢纽",
    "fund_cycle": "资金闭环",
    "bidirectional": "双向往来",
    "periodic_income": "规律性收入",
    "sudden_change": "资金突变",
    "delayed_transfer": "固定延迟转账",
    "high_risk": "高风险",
    "medium_risk": "中风险", 
    "low_risk": "低风险",
    "payment": "付款",
    "receive": "收款",
    "income": "收入",
    "expense": "支出",
}


def translate_audit_term(term: str) -> str:
    """将技术术语转换为审计术语"""
    return AUDIT_TERM_MAP.get(term, term)


def translate_risk_level(level: str) -> str:
    """将风险等级转换为中文"""
    level_map = {
        "high": "高风险",
        "medium": "中风险",
        "low": "低风险",
        "critical": "极高风险",
        "info": "信息提示"
    }
    return level_map.get(level, level)
