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
    wealth_holding: float = 0.0  # 理财持仓（万元）
    property_count: int = 0  # 房产套数
    property_value: float = 0.0  # 房产价值（万元）
    vehicle_count: int = 0  # 车辆数量
    total_income: float = 0.0  # 总收入
    total_expense: float = 0.0  # 总支出


@dataclass
class PersonalAssetsModule:
    """个人资产模块"""

    data: List[PersonalAssetItem] = field(default_factory=list)
    columns: List[str] = field(
        default_factory=lambda: [
            "户名",
            "存款估算(万)",
            "理财持仓(万)",
            "房产套数",
            "房产价值(万)",
            "车辆数",
            "总收入",
            "总支出",
        ]
    )


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
    reasoning: str = (
        "现金在短时间内从一方取出，另一方存入，且金额相近，可能是现金过账或洗钱行为。"
    )


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
        if hasattr(module, "__dataclass_fields__"):
            self.modules[name] = asdict(module)
        else:
            self.modules[name] = module

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {"metadata": asdict(self.metadata), "modules": self.modules}

    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=indent, default=str
        )


# ============================================================
# 统一报告数据结构（v4.0新增）- txt和HTML共享
# ============================================================


@dataclass
class UnifiedReportData:
    """
    统一报告数据结构（txt和HTML共享）

    修改此数据结构 = 同时影响txt和HTML
    """

    # 1. 元信息
    meta: InvestigationMeta = field(default_factory=InvestigationMeta)

    # 2. 家庭整体分析
    family_overview: FamilyOverviewSection = field(
        default_factory=FamilyOverviewSection
    )
    family_yearly_salary: List[FamilyYearlySalary] = field(default_factory=list)
    family_financial_profile: FamilyFinancialProfile = field(
        default_factory=FamilyFinancialProfile
    )

    # 3. 成员详细分析
    members: List[MemberReport] = field(default_factory=list)

    # 4. 公司报告
    companies: List[CompanyReport] = field(default_factory=list)

    # 5. 可疑交易分析
    suspicious_transactions: SuspicionAnalysis = field(
        default_factory=lambda: SuspicionAnalysis()
    )

    # 6. 综合研判
    conclusion: InvestigationConclusion = field(default_factory=InvestigationConclusion)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "meta": asdict(self.meta),
            "family_overview": asdict(self.family_overview),
            "family_yearly_salary": [asdict(s) for s in self.family_yearly_salary],
            "family_financial_profile": asdict(self.family_financial_profile),
            "members": [
                m.to_dict() if hasattr(m, "to_dict") else m for m in self.members
            ],
            "companies": [
                c.to_dict() if hasattr(c, "to_dict") else c for c in self.companies
            ],
            "suspicious_transactions": asdict(self.suspicious_transactions),
            "conclusion": asdict(self.conclusion),
        }


@dataclass
class MemberReport:
    """
    单个成员的完整报告数据

    包含：基本信息、资产、收支、年度工资、五维度分析、风险等级、专业话术
    """

    name: str
    relation: str  # 本人/配偶/子女等

    # 基础信息
    basic_info: PersonBasicInfo = field(default_factory=lambda: PersonBasicInfo())

    # 资产数据
    assets: MemberAssets = field(default_factory=lambda: MemberAssets())

    # 收支数据
    income_expense: IncomeExpenseData = field(
        default_factory=lambda: IncomeExpenseData()
    )

    # 年度工资
    yearly_salary: YearlySalaryData = field(default_factory=lambda: YearlySalaryData())

    # 五维度分析
    risk_analysis: FiveDimensionAnalysis = field(
        default_factory=lambda: FiveDimensionAnalysis()
    )

    # 风险等级和证据评分
    risk_level: str = "low"  # low/medium/high
    evidence_score: int = 0

    # 专业话术
    professional_narrative: str = ""

    # 高风险预警
    high_risk_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "name": self.name,
            "relation": self.relation,
            "basic_info": asdict(self.basic_info),
            "assets": asdict(self.assets),
            "income_expense": asdict(self.income_expense),
            "yearly_salary": asdict(self.yearly_salary),
            "risk_analysis": asdict(self.risk_analysis),
            "risk_level": self.risk_level,
            "evidence_score": self.evidence_score,
            "professional_narrative": self.professional_narrative,
            "high_risk_warnings": self.high_risk_warnings,
        }


@dataclass
class PersonBasicInfo:
    """人员基本信息"""

    name: str = ""
    gender: str = ""
    birth_date: str = ""
    birth_place: str = ""
    entry_date: str = ""
    employer: str = ""
    current_position: str = ""
    id_number: str = ""
    family_members_desc: str = ""


@dataclass
class MemberAssets:
    """成员资产数据"""

    total_assets: float = 0.0
    bank_balance: float = 0.0
    property_count: int = 0
    property_value: float = 0.0
    vehicle_count: int = 0
    wealth_holdings: float = 0.0


@dataclass
class IncomeExpenseData:
    """收支数据"""

    total_income: float = 0.0
    total_expense: float = 0.0
    net_income: float = 0.0
    transaction_count: int = 0


@dataclass
class YearlySalaryData:
    """年度工资数据"""

    yearly_data: List[Dict] = field(default_factory=list)

    def __post_init__(self):
        """初始化年度数据"""
        if not self.yearly_data:
            self.yearly_data = []


@dataclass
class FiveDimensionAnalysis:
    """五维度分析"""

    income_expense_match: DimensionScore = field(
        default_factory=lambda: DimensionScore()
    )
    lending_behavior: DimensionScore = field(default_factory=lambda: DimensionScore())
    consumption_pattern: DimensionScore = field(
        default_factory=lambda: DimensionScore()
    )
    fund_flow: DimensionScore = field(default_factory=lambda: DimensionScore())
    cash_operation: DimensionScore = field(default_factory=lambda: DimensionScore())
    total_score: int = 0


@dataclass
class DimensionScore:
    """维度评分"""

    score: int = 0
    verdict: str = ""
    details: str = ""


@dataclass
class FamilyFinancialProfile:
    """家庭财务特征分析"""

    total_income: float = 0.0
    total_expense: float = 0.0
    avg_yearly_salary: float = 0.0
    internal_transfers: float = 0.0
    external_income: float = 0.0
    external_expense: float = 0.0
    net_flow: float = 0.0


@dataclass
class SuspicionAnalysis:
    """可疑交易分析"""

    total_suspicions: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0
    details: List[Dict] = field(default_factory=list)


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
    "loan_analysis",
]

AVAILABLE_FORMATS = ["html", "json", "pdf"]


@dataclass
class ReportGenerateRequest:
    """报告生成请求"""

    sections: List[str] = field(
        default_factory=lambda: ["summary", "suspicious_transactions"]
    )
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
        "info": "信息提示",
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

    name: str = ""  # 被核查人姓名
    id_number: str = ""  # 身份证号（完整18位）
    position: str = ""  # 职务（可选）
    employer: str = ""  # 工作单位（可选）
    entry_date: str = ""  # 入职时间（用于时空碰撞）
    promotion_date: str = ""  # 提拔时间（用于时空碰撞）
    verified_monthly_income: float = 0.0  # 已核实月均工资


@dataclass
class CollisionTarget:
    """碰撞目标公司"""

    name: str = ""  # 公司名称
    type: str = ""  # 类型：供应商/承包商/中标代理
    risk_level: str = "medium"  # 风险等级：high/medium/low
    note: str = ""  # 备注


@dataclass
class SensitivePerson:
    """敏感人员"""

    name: str = ""  # 姓名
    relation: str = ""  # 关系：供应商法人/中标代理/其他


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

    asset_type: str = ""  # 房产/车辆
    asset_description: str = ""  # 资产描述
    registration_date: str = ""  # 登记时间
    related_event: str = ""  # 相关事件：入职/提拔
    event_date: str = ""  # 事件时间
    time_gap_months: int = 0  # 时间差（月）
    fund_source_found: bool = False  # 本人流水是否查见支付
    fund_source_amount: float = 0.0  # 查见的支付金额
    risk_level: str = "medium"  # 风险等级
    verdict: str = ""  # 判定文案


@dataclass
class TimelineCollisionModule:
    """时空碰撞分析模块"""

    collisions: List[TimelineCollision] = field(default_factory=list)
    total_count: int = 0
    high_risk_count: int = 0
    reasoning: str = (
        "资产购置时间与入职/提拔时间相近，且本人流水未见支付记录，需重点核实资金来源。"
    )


# ---------- v3.0 新增：模块二 - 负债压力分析 ----------


@dataclass
class DebtStressAnalysis:
    """负债压力分析"""

    total_loan_platforms: int = 0  # 网贷平台数
    loan_platform_names: List[str] = field(default_factory=list)  # 平台名称列表
    total_loan_count: int = 0  # 网贷笔数
    total_loan_amount: float = 0.0  # 网贷总额
    has_multi_head_lending: bool = False  # 是否多头借贷（≥3个平台）
    repayment_pressure: float = 0.0  # 月均还款额
    risk_level: str = "low"  # 低/中/高
    verdict: str = ""  # 判定文案


# ---------- v3.0 新增：模块五 - 自动生成建议 ----------


@dataclass
class AutoGeneratedAction:
    """自动生成的下一步建议"""

    action_type: str = ""  # 类型：房款盲区/电子钱包盲区/转账疑点/企业疑点
    target_name: str = ""  # 相关人员/公司名称
    action_text: str = ""  # 建议文案
    priority: str = "medium"  # 优先级：high/medium/low
    related_amount: float = 0.0  # 涉及金额


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

    supplier_name: str = ""  # 供应商名称
    in_collision_list: bool = False  # 是否在碰撞目标列表
    has_flow: bool = False  # 是否有资金往来
    flow_direction: str = ""  # 流向：inflow/outflow/both
    total_inflow: float = 0.0  # 流入金额
    total_outflow: float = 0.0  # 流出金额
    transaction_count: int = 0  # 交易笔数
    first_transaction_date: str = ""  # 首次交易日期
    last_transaction_date: str = ""  # 最后交易日期
    risk_level: str = "high"  # 碰撞目标默认高风险
    transactions: List[Dict] = field(default_factory=list)  # 交易明细


@dataclass
class SupplierCollisionModule:
    """供应商碰撞分析模块"""

    results: List[SupplierCollisionResult] = field(default_factory=list)
    hit_count: int = 0  # 命中数
    total_collision_targets: int = 0  # 碰撞目标总数
    total_flow_amount: float = 0.0  # 涉及总金额


# ---------- 以下为原有结构 ----------


@dataclass
class InvestigationMeta:
    """初查报告元信息"""

    doc_number: str = ""  # 文号，如 "国监查 [2026] 第 XXXXXX 号"
    case_background: str = ""  # 案件背景
    data_scope: str = ""  # 数据范围，如 "2020年1月至2025年9月银行流水数据"
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "3.0.0"
    generator: str = "穿云审计初查报告引擎"
    core_persons: List[str] = field(default_factory=list)  # 核心人员列表
    companies: List[str] = field(default_factory=list)  # 涉及公司列表
    data_range: Dict[str, str] = field(default_factory=dict)  # 数据时间范围


@dataclass
class FamilyMember:
    """家庭成员"""

    name: str = ""
    relation: str = ""  # 本人/配偶/子女/父/母/其他
    has_data: bool = False  # 是否有流水数据
    id_number: str = ""  # 身份证号（可选）


@dataclass
class FamilyAssetsSummary:
    """家庭资产汇总"""

    real_estate_count: int = 0  # 房产套数
    real_estate_value: float = 0.0  # 房产价值（万元）
    vehicle_count: int = 0  # 车辆数量
    deposits: float = 0.0  # 存款总额（万元）
    wealth_holdings: float = 0.0  # 理财持仓（万元）
    total_assets: float = 0.0  # 总资产（万元）


@dataclass
class FamilySummary:
    """家庭汇总"""

    total_income: float = 0.0  # 家庭总收入
    total_expense: float = 0.0  # 家庭总支出
    net_income: float = 0.0  # 家庭净收入（剔除互转）
    net_expense: float = 0.0  # 家庭净支出（剔除互转）
    internal_transfers: float = 0.0  # 家庭成员间互转总额
    assets: FamilyAssetsSummary = field(default_factory=FamilyAssetsSummary)


@dataclass
class InvestigationFamily:
    """初查报告家庭部分"""

    primary_person: str = ""  # 核查对象（户主）
    members: List[FamilyMember] = field(default_factory=list)
    summary: FamilySummary = field(default_factory=FamilySummary)


# ============================================================
# v3.1 新增：家庭分析层级结构（对齐用户模板）
# ============================================================


@dataclass
class RelationEvidence:
    """关系证据"""

    evidence_type: str = ""  # 证据类型：户籍确认/同一地址/共同房产/资金往来/推测
    source: str = ""  # 来源描述
    confidence: float = 1.0  # 置信度 0-1


@dataclass
class FamilyRosterMember:
    """家庭成员清单条目（含关系证据）"""

    name: str = ""
    relation: str = ""  # 与核查对象的关系
    has_data: bool = False  # 是否有流水数据
    id_number: str = ""  # 身份证号
    relation_evidence: RelationEvidence = field(default_factory=RelationEvidence)


@dataclass
class FamilyRoster:
    """家庭成员清单（对应模板 family_roster）"""

    householder: str = ""  # 户主
    address: str = ""  # 户籍地址
    members: List[FamilyRosterMember] = field(default_factory=list)
    extended_relatives: List[Dict] = field(default_factory=list)  # 旁系亲属（推测）


@dataclass
class IncomeAssetMismatch:
    """收支资产匹配分析"""

    total_family_income: float = 0.0  # 家庭总收入
    total_family_expense: float = 0.0  # 家庭总支出
    total_assets_value: float = 0.0  # 总资产价值
    income_covers_expense: bool = True  # 收入是否覆盖支出
    income_covers_assets: bool = True  # 收入是否覆盖资产
    gap_amount: float = 0.0  # 缺口金额
    analysis_text: str = ""  # 分析说明
    risk_level: str = "low"  # 风险等级


@dataclass
class JointRisks:
    """家庭成员间联合风险"""

    internal_transfer_total: float = 0.0  # 内部互转总额
    transfer_details: List[Dict] = field(default_factory=list)  # 互转明细
    has_anomaly: bool = False  # 是否异常
    anomaly_description: str = ""  # 异常描述
    risk_level: str = "low"  # 风险等级


@dataclass
class FamilyLevelAnalysis:
    """家庭层面分析（对应模板 family_level_analysis）"""

    income_asset_mismatch: IncomeAssetMismatch = field(
        default_factory=IncomeAssetMismatch
    )
    joint_risks: JointRisks = field(default_factory=JointRisks)


@dataclass
class FamilyUnit:
    """
    家庭单元（对应模板 family_unit）

    包含：
    - family_roster: 成员清单
    - members_detailed: 成员详情列表（复用 MemberDetails）
    - family_level_analysis: 家庭层面分析
    """

    unit_label: str = ""  # 单元标签，如 "施灵家庭"
    anchor: str = ""  # 锚点人员
    family_roster: FamilyRoster = field(default_factory=FamilyRoster)
    # members_detailed 引用 MemberDetails 列表（在后面定义）
    family_level_analysis: FamilyLevelAnalysis = field(
        default_factory=FamilyLevelAnalysis
    )


@dataclass
class HouseholdAnalysisSection:
    """
    家庭分析章节（对应模板 household_analysis_section）

    顶层结构，包含所有家庭单元
    """

    family_units: List[FamilyUnit] = field(default_factory=list)
    total_families: int = 0
    total_persons_with_data: int = 0


@dataclass
class BankAccountInfo:
    """银行账户信息"""

    bank_name: str = ""  # 银行名称
    account_number: str = ""  # 账号（完整）
    account_type: str = ""  # 账户类别：个人账户/对公账户
    account_category: str = ""  # 账户分类：个人账户/联名账户/对公账户
    card_type: str = ""  # 卡类型：借记卡/信用卡/工资卡
    is_real_bank_card: bool = True  # 是否真实银行卡
    status: str = ""  # 账户状态：正常/冻结/注销
    balance: float = 0.0  # 当前余额（last_balance）
    balance_is_estimated: bool = False  # 余额是否为估算值
    last_transaction_date: str = ""  # 最后交易日期
    first_transaction_date: str = ""  # 首次交易日期
    transaction_count: int = 0  # 交易笔数
    total_income: float = 0.0  # 该账户总收入
    total_expense: float = 0.0  # 该账户总支出


@dataclass
class YearlySalaryStats:
    """年度工资统计"""

    year: str = ""
    total: float = 0.0
    months: int = 0
    avg_monthly: float = 0.0
    transaction_count: int = 0


@dataclass
class PropertyInfo:
    """房产信息"""

    address: str = ""  # 地址
    area: float = 0.0  # 面积（平方米）
    value: float = 0.0  # 估值（元）
    registration_date: str = ""  # 登记日期
    owner: str = ""  # 产权人
    certificate_number: str = ""  # 证号
    data_source: str = ""  # 数据来源


@dataclass
class VehicleInfo:
    """车辆信息"""

    plate_number: str = ""  # 车牌号
    brand: str = ""  # 品牌型号
    purchase_date: str = ""  # 购置时间
    estimated_value: float = 0.0  # 估价（元）
    owner: str = ""  # 登记人
    data_source: str = ""  # 数据来源


@dataclass
class PersonAssets:
    """个人资产板块"""

    # 工资
    salary_total: float = 0.0  # 工资总额
    salary_ratio: float = 0.0  # 工资占收入比例
    yearly_salary: List[YearlySalaryStats] = field(default_factory=list)

    # 理财
    wealth_total: float = 0.0  # 理财交易总额
    wealth_holding: float = 0.0  # 估算持仓

    # 银行账户
    bank_accounts: List[BankAccountInfo] = field(default_factory=list)
    bank_account_count: int = 0

    # 不动产
    properties: List[PropertyInfo] = field(default_factory=list)

    # 车辆
    vehicles: List[VehicleInfo] = field(default_factory=list)


@dataclass
class IncomeGapAnalysis:
    """收支匹配分析"""

    total_income: float = 0.0
    salary_income: float = 0.0
    ratio: float = 0.0  # 工资占比
    verdict: str = ""  # 判定结论


@dataclass
class LargeCashAnalysis:
    """大额现金分析"""

    total_amount: float = 0.0
    deposit_amount: float = 0.0  # 存现总额
    withdraw_amount: float = 0.0  # 取现总额
    count: int = 0
    transactions: List[Dict] = field(default_factory=list)


@dataclass
class LargeTransferAnalysis:
    """大额转账分析"""

    threshold: float = 50000.0  # 阈值（元）
    count: int = 0
    total_amount: float = 0.0
    transactions: List[Dict] = field(default_factory=list)


@dataclass
class CounterpartyFlow:
    """按对手方的资金流向"""

    counterparty: str = ""  # 对手方名称
    total_amount: float = 0.0  # 总金额
    count: int = 0  # 交易笔数
    percentage: float = 0.0  # 占比
    category: str = ""  # 分类：工资/理财/个人转账/来源不明等


@dataclass
class InflowAnalysis:
    """资金流入分析"""

    total_inflow: float = 0.0  # 总流入（剔除内部互转）
    top_sources: List[CounterpartyFlow] = field(default_factory=list)  # Top来源
    category_summary: Dict[str, float] = field(default_factory=dict)  # 按类别汇总
    unknown_source_amount: float = 0.0  # 来源不明金额
    unknown_source_ratio: float = 0.0  # 来源不明占比
    # 三类收入分类（新增）
    legitimate_income: float = 0.0  # 合法收入金额
    legitimate_ratio: float = 0.0  # 合法收入占比
    suspicious_income: float = 0.0  # 可疑收入金额
    suspicious_ratio: float = 0.0  # 可疑收入占比


@dataclass
class OutflowAnalysis:
    """资金流出分析"""

    total_outflow: float = 0.0  # 总流出（剔除内部互转）
    top_destinations: List[CounterpartyFlow] = field(default_factory=list)  # Top去向
    category_summary: Dict[str, float] = field(default_factory=dict)  # 按类别汇总
    large_single_payments: List[Dict] = field(default_factory=list)  # 大额单笔支出


@dataclass
class ExternalDataPlaceholder:
    """外部数据占位（需外部数据源支持）"""

    available: bool = False  # 是否有数据
    message: str = "需要外部数据源支持"  # 提示信息
    data: Dict = field(default_factory=dict)  # 实际数据（如有）


@dataclass
class RelatedPartyTransactions:
    """关联交易排查"""

    total_count: int = 0  # 总笔数
    total_amount: float = 0.0  # 总金额
    by_company: List[Dict] = field(default_factory=list)  # 按公司分组


# ============================================================
# v3.1 新增：征信预警与行为风险
# ============================================================


@dataclass
class CreditAlertItem:
    """征信预警条目"""

    name: str = ""  # 姓名
    id_number: str = ""  # 身份证号
    alert_type: str = ""  # 预警类型：欠税记录/民事判决/强制执行/行政处罚
    count: int = 0  # 条数
    source: str = ""  # 数据来源


@dataclass
class BehavioralRiskItem:
    """行为风险条目"""

    risk_type: str = ""  # 类型：fast_in_out/split_in_large_out
    risk_level: str = "medium"  # 风险等级
    trigger_date: str = ""  # 触发日期
    amount: float = 0.0  # 涉及金额
    counterparty: str = ""  # 对手方
    description: str = ""  # 描述


@dataclass
class BehavioralRiskSummary:
    """行为风险摘要"""

    fast_in_out_count: int = 0  # 快进快出次数
    structuring_count: int = 0  # 拆分交易次数
    dormant_activation_count: int = 0  # 休眠激活次数
    total_patterns: int = 0  # 模式总数
    high_risk_items: List[BehavioralRiskItem] = field(default_factory=list)


@dataclass
class SuspiciousFlags:
    """可疑标记汇总（对应模板 suspicious_flags）"""

    # 现金风险
    cash_deposit_total: float = 0.0  # 存现总额
    cash_withdraw_total: float = 0.0  # 取现总额
    cash_transactions: List[Dict] = field(default_factory=list)  # 大额现金明细

    # 转账风险
    unknown_source_transfers: List[Dict] = field(default_factory=list)  # 来源不明转账
    suspicious_counterparty_transfers: List[Dict] = field(
        default_factory=list
    )  # 与可疑对手方转账

    # 征信预警（新增）
    credit_alerts: List[CreditAlertItem] = field(default_factory=list)
    credit_alert_summary: str = ""  # 征信预警摘要

    # 行为风险（新增）
    behavioral_risk: BehavioralRiskSummary = field(
        default_factory=BehavioralRiskSummary
    )


@dataclass
class PersonAnalysis:
    """个人分析板块（增强版）"""

    income_gap: IncomeGapAnalysis = field(default_factory=IncomeGapAnalysis)
    inflow_analysis: InflowAnalysis = field(
        default_factory=InflowAnalysis
    )  # 资金流入分析
    outflow_analysis: OutflowAnalysis = field(
        default_factory=OutflowAnalysis
    )  # 资金流出分析
    large_cash: LargeCashAnalysis = field(default_factory=LargeCashAnalysis)
    large_transfers: LargeTransferAnalysis = field(
        default_factory=LargeTransferAnalysis
    )
    related_party_transactions: RelatedPartyTransactions = field(
        default_factory=RelatedPartyTransactions
    )
    third_party_total: float = 0.0  # 第三方支付总额
    suspicious_count: int = 0  # 可疑交易笔数
    # v3.1 新增：可疑标记汇总
    suspicious_flags: SuspiciousFlags = field(default_factory=SuspiciousFlags)
    # 外部数据占位
    identity_info: ExternalDataPlaceholder = field(
        default_factory=lambda: ExternalDataPlaceholder(
            message="基本身份信息需外部数据源"
        )
    )
    property_info: ExternalDataPlaceholder = field(
        default_factory=lambda: ExternalDataPlaceholder(message="房产信息需不动产数据")
    )
    vehicle_info: ExternalDataPlaceholder = field(
        default_factory=lambda: ExternalDataPlaceholder(message="车辆信息需外部数据源")
    )


# ============================================================
# v4.0 新增：报告骨架结构数据类
# ============================================================


@dataclass
class FamilyAssetsOverview:
    """家庭资产总览"""

    property_count: int = 0  # 房产套数
    property_value: float = 0.0  # 房产总价值（万元）
    property_value_wan: float = 0.0  # 房产总价值（万元，格式化）
    bank_balance: float = 0.0  # 银行存款总额（元）
    bank_balance_wan: float = 0.0  # 银行存款总额（万元）
    wealth_holding: float = 0.0  # 理财持仓总额（元）
    wealth_holding_wan: float = 0.0  # 理财持仓总额（万元）
    vehicle_count: int = 0  # 车辆数量
    total_assets: float = 0.0  # 总资产（元）
    total_assets_wan: float = 0.0  # 总资产（万元）
    narrative: str = ""  # 资产描述话术


@dataclass
class FamilyYearlySalary:
    """家庭年度工资汇总"""

    year: str = ""  # 年份
    total: float = 0.0  # 年度工资总额（元）
    total_wan: float = 0.0  # 年度工资总额（万元）
    member_breakdown: Dict[str, float] = field(default_factory=dict)  # 各成员分解


@dataclass
class FamilyOverviewSection:
    """家庭整体分析章节"""

    family_name: str = ""  # 家庭名称，如"施灵家庭"
    anchor: str = ""  # 核查对象
    member_count: int = 0  # 成员数量
    member_relations: List[Dict] = field(default_factory=list)  # 成员关系列表

    # 家庭资产总览
    assets_overview: FamilyAssetsOverview = field(default_factory=FamilyAssetsOverview)

    # 家庭收支汇总
    total_income: float = 0.0  # 总收入（元）
    total_income_wan: float = 0.0  # 总收入（万元）
    total_expense: float = 0.0  # 总支出（元）
    total_expense_wan: float = 0.0  # 总支出（万元）
    total_salary: float = 0.0  # 总工资（元）
    total_salary_wan: float = 0.0  # 总工资（万元）
    avg_yearly_salary: float = 0.0  # 年均工资（元）
    avg_yearly_salary_wan: float = 0.0  # 年均工资（万元）
    salary_ratio: float = 0.0  # 工资占收入比例（%）

    # 家庭年度工资汇总
    yearly_salary_breakdown: List[FamilyYearlySalary] = field(default_factory=list)

    # 综述话术
    narrative: str = ""
    assets_narrative: str = ""
    salary_narrative: str = ""


@dataclass
class DimensionAnalysis:
    """单个维度分析结果"""

    dimension_name: str = ""  # 维度名称
    dimension_icon: str = ""  # 维度图标
    score: int = 0  # 得分
    max_score: int = 0  # 满分
    risk_level: str = "low"  # 风险等级
    findings: List[str] = field(default_factory=list)  # 具体发现
    narrative: str = ""  # 分析描述


@dataclass
class PersonalFinancialProfile:
    """个人资金特征画像"""

    name: str = ""  # 姓名

    # 整体风险评级
    risk_level: str = "low"  # 风险等级: low/medium/high
    risk_score: int = 0  # 风险评分 0-100
    risk_color: str = "green"  # 颜色: green/yellow/red
    risk_label: str = "低风险"  # 风险标签

    # 五维度评分
    income_expense_match: DimensionAnalysis = field(
        default_factory=lambda: DimensionAnalysis(
            dimension_name="收支匹配度", dimension_icon="💳", max_score=25
        )
    )
    lending_behavior: DimensionAnalysis = field(
        default_factory=lambda: DimensionAnalysis(
            dimension_name="借贷行为", dimension_icon="💴", max_score=20
        )
    )
    consumption_pattern: DimensionAnalysis = field(
        default_factory=lambda: DimensionAnalysis(
            dimension_name="消费特征", dimension_icon="🛍", max_score=15
        )
    )
    fund_flow: DimensionAnalysis = field(
        default_factory=lambda: DimensionAnalysis(
            dimension_name="资金流向", dimension_icon="📊", max_score=25
        )
    )
    cash_operation: DimensionAnalysis = field(
        default_factory=lambda: DimensionAnalysis(
            dimension_name="现金操作", dimension_icon="💵", max_score=15
        )
    )

    # 专业审计话术
    professional_narrative: str = ""
    conclusion_narrative: str = ""

    # 高风险预警
    high_risk_alerts: List[str] = field(default_factory=list)
    has_alerts: bool = False


@dataclass
class MemberDetails:
    """家庭成员详情"""

    name: str = ""
    relation: str = ""  # 与核查对象关系
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
    percentage: float = 0.0  # 占公司总流水比例
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
    investigation_unit_flows: InvestigationUnitFlows = field(
        default_factory=InvestigationUnitFlows
    )

    # 与关键人员关联
    key_person_transfers: KeyPersonTransfers = field(default_factory=KeyPersonTransfers)

    # 现金交易
    cash_analysis: CompanyCashAnalysis = field(default_factory=CompanyCashAnalysis)

    # 银行账户
    bank_accounts: List[BankAccountInfo] = field(default_factory=list)


@dataclass
class IssueItem:
    """问题条目（增强版）"""

    person: str = ""  # 涉及人员/公司
    issue_type: str = ""  # 问题类型：收支不抵/异常资金往来/资金来源不明/借贷异常
    description: str = ""  # 问题描述
    severity: str = "medium"  # 严重程度：high/medium/low
    # 审计专业分类
    verification_status: str = (
        "need_verification"  # confirmed/highly_suspicious/need_verification/normal
    )
    amount: float = 0.0  # 涉及金额
    evidence_refs: List[str] = field(default_factory=list)
    # v3.1 新增字段
    counterparty: str = ""  # 对手方
    counterparty_type: str = ""  # 对手方类型：family(家人)/colleague(同事)/managed_entity(管理对象)/supplier(供应商)/unknown(不明)
    transaction_date: str = ""  # 首次/最近交易日期
    direction: str = ""  # 方向：inflow(流入)/outflow(流出)/both(双向)
    transaction_count: int = 0  # 交易笔数
    priority_score: int = 0  # 优先级评分（0-100，用于排序）


@dataclass
class InvestigationConclusion:
    """综合研判"""

    summary_text: str = ""  # 研判意见
    issues: List[IssueItem] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0
    # 按确认程度统计（新增）
    confirmed_count: int = 0  # 基本确认
    highly_suspicious_count: int = 0  # 高度可疑
    need_verification_count: int = 0  # 需核实
    total_amount: float = 0.0  # 问题涉及总金额


@dataclass
class AnalysisUnit:
    """分析单元（循环体）"""

    anchor: str = ""  # 锚点人员
    unit_type: str = "family"  # 单元类型：family/independent
    unit_name: str = ""  # 单元名称
    members: List[str] = field(default_factory=list)  # 成员列表
    aggregated_data: Dict = field(default_factory=dict)  # 聚合数据
    member_details: List[MemberDetails] = field(default_factory=list)  # 成员详情


@dataclass
class InvestigationReport:
    """
    初查报告完整结构（v3.1）

    按照 report_data_contract.md 定义的标准格式
    支持三段式结构：前言 + 分析单元循环体 + 综合研判

    v3.1 新增 household_analysis_section 对齐用户模板
    """

    meta: InvestigationMeta = field(default_factory=InvestigationMeta)
    family: InvestigationFamily = field(
        default_factory=InvestigationFamily
    )  # 保留兼容性
    # v3.1 新增：家庭分析章节（对齐用户模板）
    household_analysis_section: HouseholdAnalysisSection = field(
        default_factory=HouseholdAnalysisSection
    )
    analysis_units: List[AnalysisUnit] = field(default_factory=list)  # 分析单元
    member_details: List[MemberDetails] = field(default_factory=list)  # 保留兼容性
    company_reports: List[CompanyReport] = field(default_factory=list)  # 公司报告
    conclusion: InvestigationConclusion = field(default_factory=InvestigationConclusion)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=indent, default=str
        )
