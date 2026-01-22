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


# ============================================================
# 初查报告结构定义 (2026-01-20 新增)
# v3.0 增强 (2026-01-22)
# ============================================================

# ---------- v3.0 新增：主核查配置相关 ----------

@dataclass
class PrimarySubjectConfig:
    """主核查对象配置"""
    name: str = ""                          # 被核查人姓名
    id_number: str = ""                     # 身份证号（完整18位）
    position: str = ""                      # 职务（可选）
    employer: str = ""                      # 工作单位（可选）
    entry_date: str = ""                    # 入职时间（用于时空碰撞）
    promotion_date: str = ""                # 提拔时间（用于时空碰撞）
    verified_monthly_income: float = 0.0    # 已核实月均工资


@dataclass
class CollisionTarget:
    """碰撞目标公司"""
    name: str = ""                          # 公司名称
    type: str = ""                          # 类型：供应商/承包商/中标代理
    risk_level: str = "medium"              # 风险等级：high/medium/low
    note: str = ""                          # 备注


@dataclass
class SensitivePerson:
    """敏感人员"""
    name: str = ""                          # 姓名
    relation: str = ""                      # 关系：供应商法人/中标代理/其他


@dataclass
class InvestigationConfig:
    """主核查配置（渐进式配置支持）"""
    # 主核查对象
    primary_subject: PrimarySubjectConfig = field(default_factory=PrimarySubjectConfig)
    
    # 基本信息补全
    basic_info_supplement: List[Dict] = field(default_factory=list)
    
    # 家庭成员
    family_members: List[Dict] = field(default_factory=list)
    
    # 调查单位
    investigation_unit_name: str = ""
    investigation_unit_keywords: List[str] = field(default_factory=list)
    
    # 白名单（排除不预警）
    excluded_companies: List[str] = field(default_factory=list)
    
    # 碰撞目标（必须排查）
    collision_targets: List[CollisionTarget] = field(default_factory=list)
    
    # 敏感人员
    sensitive_persons: List[SensitivePerson] = field(default_factory=list)
    
    # 数据时间范围
    data_scope_auto_detect: bool = True
    data_scope_start: str = ""
    data_scope_end: str = ""
    
    # 报告元信息
    doc_number: str = ""
    case_source: str = ""


# ---------- v3.0 新增：模块二 - 时空碰撞分析 ----------

@dataclass
class TimelineCollision:
    """时空碰撞结果"""
    asset_type: str = ""                    # 房产/车辆
    asset_description: str = ""             # 资产描述
    registration_date: str = ""             # 登记时间
    related_event: str = ""                 # 相关事件：入职/提拔
    event_date: str = ""                    # 事件时间
    time_gap_months: int = 0                # 时间差（月）
    fund_source_found: bool = False         # 本人流水是否查见支付
    fund_source_amount: float = 0.0         # 查见的支付金额
    risk_level: str = "medium"              # 风险等级
    verdict: str = ""                       # 判定文案


@dataclass
class TimelineCollisionModule:
    """时空碰撞分析模块"""
    collisions: List[TimelineCollision] = field(default_factory=list)
    total_count: int = 0
    high_risk_count: int = 0
    reasoning: str = "资产购置时间与入职/提拔时间相近，且本人流水未见支付记录，需重点核实资金来源。"


# ---------- v3.0 新增：模块二 - 负债压力分析 ----------

@dataclass
class DebtStressAnalysis:
    """负债压力分析"""
    total_loan_platforms: int = 0           # 网贷平台数
    loan_platform_names: List[str] = field(default_factory=list)  # 平台名称列表
    total_loan_count: int = 0               # 网贷笔数
    total_loan_amount: float = 0.0          # 网贷总额
    has_multi_head_lending: bool = False    # 是否多头借贷（≥3个平台）
    repayment_pressure: float = 0.0         # 月均还款额
    risk_level: str = "low"                 # 低/中/高
    verdict: str = ""                       # 判定文案


# ---------- v3.0 新增：模块五 - 自动生成建议 ----------

@dataclass
class AutoGeneratedAction:
    """自动生成的下一步建议"""
    action_type: str = ""                   # 类型：房款盲区/电子钱包盲区/转账疑点/企业疑点
    target_name: str = ""                   # 相关人员/公司名称
    action_text: str = ""                   # 建议文案
    priority: str = "medium"                # 优先级：high/medium/low
    related_amount: float = 0.0             # 涉及金额


@dataclass
class AutoGeneratedActionsModule:
    """自动生成建议模块"""
    actions: List[AutoGeneratedAction] = field(default_factory=list)
    total_count: int = 0
    high_priority_count: int = 0


# ---------- v3.0 新增：供应商碰撞结果 ----------

@dataclass
class SupplierCollisionResult:
    """供应商碰撞结果"""
    supplier_name: str = ""                 # 供应商名称
    in_collision_list: bool = False         # 是否在碰撞目标列表
    has_flow: bool = False                  # 是否有资金往来
    flow_direction: str = ""                # 流向：inflow/outflow/both
    total_inflow: float = 0.0               # 流入金额
    total_outflow: float = 0.0              # 流出金额
    transaction_count: int = 0              # 交易笔数
    first_transaction_date: str = ""        # 首次交易日期
    last_transaction_date: str = ""         # 最后交易日期
    risk_level: str = "high"                # 碰撞目标默认高风险
    transactions: List[Dict] = field(default_factory=list)  # 交易明细


@dataclass
class SupplierCollisionModule:
    """供应商碰撞分析模块"""
    results: List[SupplierCollisionResult] = field(default_factory=list)
    hit_count: int = 0                      # 命中数
    total_collision_targets: int = 0        # 碰撞目标总数
    total_flow_amount: float = 0.0          # 涉及总金额


# ---------- 以下为原有结构 ----------


@dataclass
class InvestigationMeta:
    """初查报告元信息"""
    doc_number: str = ""                    # 文号，如 "国监查 [2026] 第 XXXXXX 号"
    case_background: str = ""               # 案件背景
    data_scope: str = ""                    # 数据范围，如 "2020年1月至2025年9月银行流水数据"
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0.0"
    generator: str = "穿云审计初查报告引擎"


@dataclass
class FamilyMember:
    """家庭成员"""
    name: str = ""
    relation: str = ""                      # 本人/配偶/子女/父/母/其他
    has_data: bool = False                  # 是否有流水数据
    id_number: str = ""                     # 身份证号（可选）


@dataclass
class FamilyAssetsSummary:
    """家庭资产汇总"""
    real_estate_count: int = 0              # 房产套数
    real_estate_value: float = 0.0          # 房产价值（万元）
    vehicle_count: int = 0                  # 车辆数量
    deposits: float = 0.0                   # 存款总额（万元）
    wealth_holdings: float = 0.0            # 理财持仓（万元）
    total_assets: float = 0.0               # 总资产（万元）


@dataclass
class FamilySummary:
    """家庭汇总"""
    total_income: float = 0.0               # 家庭总收入
    total_expense: float = 0.0              # 家庭总支出
    net_income: float = 0.0                 # 家庭净收入（剔除互转）
    net_expense: float = 0.0                # 家庭净支出（剔除互转）
    internal_transfers: float = 0.0         # 家庭成员间互转总额
    assets: FamilyAssetsSummary = field(default_factory=FamilyAssetsSummary)


@dataclass
class InvestigationFamily:
    """初查报告家庭部分"""
    primary_person: str = ""                # 核查对象（户主）
    members: List[FamilyMember] = field(default_factory=list)
    summary: FamilySummary = field(default_factory=FamilySummary)


@dataclass
class BankAccountInfo:
    """银行账户信息"""
    bank_name: str = ""                     # 银行名称
    account_number: str = ""                # 账号（完整）
    account_type: str = ""                  # 账户类别：个人账户/对公账户
    card_type: str = ""                     # 卡类型：借记卡/信用卡/工资卡
    status: str = ""                        # 账户状态：正常/冻结/注销
    balance: float = 0.0                    # 当前余额
    last_transaction_date: str = ""         # 最后交易日期


@dataclass
class YearlySalaryStats:
    """年度工资统计"""
    year: str = ""
    total: float = 0.0
    months: int = 0
    avg_monthly: float = 0.0
    transaction_count: int = 0


@dataclass
class PersonAssets:
    """个人资产板块"""
    # 工资
    salary_total: float = 0.0               # 工资总额
    salary_ratio: float = 0.0               # 工资占收入比例
    yearly_salary: List[YearlySalaryStats] = field(default_factory=list)
    
    # 理财
    wealth_total: float = 0.0               # 理财交易总额
    wealth_holding: float = 0.0             # 估算持仓
    
    # 银行账户
    bank_accounts: List[BankAccountInfo] = field(default_factory=list)
    bank_account_count: int = 0


@dataclass
class IncomeGapAnalysis:
    """收支匹配分析"""
    total_income: float = 0.0
    salary_income: float = 0.0
    ratio: float = 0.0                      # 工资占比
    verdict: str = ""                       # 判定结论


@dataclass
class LargeCashAnalysis:
    """大额现金分析"""
    total_amount: float = 0.0
    deposit_amount: float = 0.0             # 存现总额
    withdraw_amount: float = 0.0            # 取现总额
    count: int = 0
    transactions: List[Dict] = field(default_factory=list)


@dataclass
class LargeTransferAnalysis:
    """大额转账分析"""
    threshold: float = 50000.0              # 阈值（元）
    count: int = 0
    total_amount: float = 0.0
    transactions: List[Dict] = field(default_factory=list)


@dataclass
class CounterpartyFlow:
    """按对手方的资金流向"""
    counterparty: str = ""                  # 对手方名称
    total_amount: float = 0.0               # 总金额
    count: int = 0                          # 交易笔数
    percentage: float = 0.0                 # 占比
    category: str = ""                      # 分类：工资/理财/个人转账/来源不明等


@dataclass
class InflowAnalysis:
    """资金流入分析"""
    total_inflow: float = 0.0               # 总流入（剔除内部互转）
    top_sources: List[CounterpartyFlow] = field(default_factory=list)  # Top来源
    category_summary: Dict[str, float] = field(default_factory=dict)   # 按类别汇总
    unknown_source_amount: float = 0.0      # 来源不明金额
    unknown_source_ratio: float = 0.0       # 来源不明占比
    # 三类收入分类（新增）
    legitimate_income: float = 0.0          # 合法收入金额
    legitimate_ratio: float = 0.0           # 合法收入占比
    suspicious_income: float = 0.0          # 可疑收入金额
    suspicious_ratio: float = 0.0           # 可疑收入占比


@dataclass
class OutflowAnalysis:
    """资金流出分析"""
    total_outflow: float = 0.0              # 总流出（剔除内部互转）
    top_destinations: List[CounterpartyFlow] = field(default_factory=list)  # Top去向
    category_summary: Dict[str, float] = field(default_factory=dict)   # 按类别汇总
    large_single_payments: List[Dict] = field(default_factory=list)    # 大额单笔支出


@dataclass
class ExternalDataPlaceholder:
    """外部数据占位（需外部数据源支持）"""
    available: bool = False                 # 是否有数据
    message: str = "需要外部数据源支持"     # 提示信息
    data: Dict = field(default_factory=dict)  # 实际数据（如有）


@dataclass
class PersonAnalysis:
    """个人分析板块"""
    income_gap: IncomeGapAnalysis = field(default_factory=IncomeGapAnalysis)
    inflow_analysis: InflowAnalysis = field(default_factory=InflowAnalysis)      # 新增：资金流入分析
    outflow_analysis: OutflowAnalysis = field(default_factory=OutflowAnalysis)   # 新增：资金流出分析
    large_cash: LargeCashAnalysis = field(default_factory=LargeCashAnalysis)
    large_transfers: LargeTransferAnalysis = field(default_factory=LargeTransferAnalysis)
    third_party_total: float = 0.0          # 第三方支付总额
    suspicious_count: int = 0               # 可疑交易笔数
    # 外部数据占位
    identity_info: ExternalDataPlaceholder = field(default_factory=lambda: ExternalDataPlaceholder(message="基本身份信息需外部数据源"))
    property_info: ExternalDataPlaceholder = field(default_factory=lambda: ExternalDataPlaceholder(message="房产信息需不动产数据"))
    vehicle_info: ExternalDataPlaceholder = field(default_factory=lambda: ExternalDataPlaceholder(message="车辆信息需外部数据源"))


@dataclass
class MemberDetails:
    """家庭成员详情"""
    name: str = ""
    relation: str = ""                      # 与核查对象关系
    total_income: float = 0.0
    total_expense: float = 0.0
    transaction_count: int = 0
    assets: PersonAssets = field(default_factory=PersonAssets)
    analysis: PersonAnalysis = field(default_factory=PersonAnalysis)


@dataclass
class InvestigationUnitFlows:
    """与调查单位资金往来"""
    has_flows: bool = False
    total_amount: float = 0.0
    percentage: float = 0.0                 # 占公司总流水比例
    transactions: List[Dict] = field(default_factory=list)


@dataclass
class KeyPersonTransfers:
    """与关键人员关联交易"""
    has_transfers: bool = False
    total_amount: float = 0.0
    transfer_count: int = 0
    unique_persons: int = 0
    details: List[Dict] = field(default_factory=list)


@dataclass
class CompanyCashAnalysis:
    """公司现金交易分析"""
    has_cash: bool = False
    total_amount: float = 0.0
    deposit_amount: float = 0.0
    withdraw_amount: float = 0.0
    deposit_count: int = 0
    withdraw_count: int = 0


@dataclass
class CompanyReport:
    """公司报告"""
    company_name: str = ""
    
    # 资金规模
    total_income: float = 0.0
    total_expense: float = 0.0
    transaction_count: int = 0
    account_count: int = 0
    
    # 与调查单位往来
    investigation_unit_flows: InvestigationUnitFlows = field(default_factory=InvestigationUnitFlows)
    
    # 与关键人员关联
    key_person_transfers: KeyPersonTransfers = field(default_factory=KeyPersonTransfers)
    
    # 现金交易
    cash_analysis: CompanyCashAnalysis = field(default_factory=CompanyCashAnalysis)
    
    # 银行账户
    bank_accounts: List[BankAccountInfo] = field(default_factory=list)


@dataclass
class IssueItem:
    """问题条目"""
    person: str = ""                        # 涉及人员/公司
    issue_type: str = ""                    # 问题类型：收支不抵/异常资金往来/资金来源不明
    description: str = ""                   # 问题描述
    severity: str = "medium"                # 严重程度：high/medium/low
    # 审计专业分类（新增）
    verification_status: str = "need_verification"  # confirmed(基本确认)/highly_suspicious(高度可疑)/need_verification(需核实)/normal(正常)
    amount: float = 0.0                     # 涉及金额
    evidence_refs: List[str] = field(default_factory=list)


@dataclass
class InvestigationConclusion:
    """综合研判"""
    summary_text: str = ""                  # 研判意见
    issues: List[IssueItem] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0
    # 按确认程度统计（新增）
    confirmed_count: int = 0                # 基本确认
    highly_suspicious_count: int = 0        # 高度可疑
    need_verification_count: int = 0        # 需核实
    total_amount: float = 0.0               # 问题涉及总金额


@dataclass
class InvestigationReport:
    """
    初查报告完整结构
    
    按照 report_guidelines.md 定义的标准格式
    """
    meta: InvestigationMeta = field(default_factory=InvestigationMeta)
    family: InvestigationFamily = field(default_factory=InvestigationFamily)
    member_details: List[MemberDetails] = field(default_factory=list)
    companies: List[CompanyReport] = field(default_factory=list)
    conclusion: InvestigationConclusion = field(default_factory=InvestigationConclusion)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)
