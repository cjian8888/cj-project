"""
画像数据模型 - Profile Schema
定义资金特征画像的标准数据结构。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, Field, field_validator, ConfigDict


class ProfileMetrics(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        extra='ignore'
    )

    total_income: float = Field(
        default=0.0,
        ge=0,
        lt=1e12,
        description="总收入金额"
    )
    total_expense: float = Field(
        default=0.0,
        ge=0,
        lt=1e12,
        description="总支出金额"
    )
    net_flow: float = Field(
        default=0.0,
        gt=-1e12,
        lt=1e12,
        description="净资金流入 (收入-支出)"
    )
    cash_income: float = Field(
        default=0.0,
        ge=0,
        lt=1e12,
        description="现金收入金额"
    )
    cash_expense: float = Field(
        default=0.0,
        ge=0,
        lt=1e12,
        description="现金支出金额"
    )
    cash_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="现金交易占比"
    )
    transaction_count: int = Field(
        default=0,
        ge=0,
        description="交易笔数"
    )
    unique_counterparties: int = Field(
        default=0,
        ge=0,
        description="对手方数量"
    )
    avg_transaction_amount: float = Field(
        default=0.0,
        ge=0,
        description="平均交易金额"
    )
    max_transaction_amount: float = Field(
        default=0.0,
        ge=0,
        description="最大单笔交易金额"
    )
    period_days: int = Field(
        default=0,
        ge=0,
        description="统计期间天数"
    )


class Profile(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        extra='ignore',
        validate_assignment=True,
        str_strip_whitespace=True
    )

    profile_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="画像唯一标识符"
    )
    entity_type: str = Field(
        ...,
        pattern=r'^(个人|公司)$',
        description="实体类型：个人或公司"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="实体名称"
    )
    metrics: ProfileMetrics = Field(
        default_factory=ProfileMetrics,
        description="核心指标"
    )
    top_income_sources: List[str] = Field(
        default_factory=list,
        max_length=50,
        description="主要收入来源"
    )
    top_expense_targets: List[str] = Field(
        default_factory=list,
        max_length=50,
        description="主要支出去向"
    )
    accounts: List[str] = Field(
        default_factory=list,
        max_length=100,
        description="关联账户列表"
    )
    banks: List[str] = Field(
        default_factory=list,
        max_length=50,
        description="开户银行列表"
    )
    analysis_period_start: Optional[date] = Field(
        None,
        description="分析期间开始日期"
    )
    analysis_period_end: Optional[date] = Field(
        None,
        description="分析期间结束日期"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    risk_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="风险评分 (0-100)"
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=100,
        description="标签列表"
    )
    notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="备注信息"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError('名称不能为空')
        return v

    def get_cash_intensity(self) -> str:
        if self.metrics.cash_ratio > 0.5:
            return "高"
        elif self.metrics.cash_ratio > 0.2:
            return "中"
        return "低"

    def is_high_frequency(self, threshold: int = 100) -> bool:
        return self.metrics.transaction_count > threshold


class ProfileComparison(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        extra='ignore'
    )

    comparison_id: str = Field(..., description="对比ID")
    base_profile: str = Field(..., description="基准画像ID")
    compare_profile: str = Field(..., description="对比画像ID")
    income_diff: float = Field(
        default=0.0,
        description="收入差额"
    )
    expense_diff: float = Field(
        default=0.0,
        description="支出差额"
    )
    common_counterparties: List[str] = Field(
        default_factory=list,
        description="共同对手方"
    )
    similarity_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="相似度评分"
    )
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="生成时间"
    )


class ProfileCollection(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        extra='ignore'
    )

    collection_id: str = Field(..., description="集合ID")
    profiles: List[Profile] = Field(
        default_factory=list,
        max_length=1000,
        description="画像列表"
    )
    summary: Dict[str, float] = Field(
        default_factory=dict,
        description="汇总统计"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )

    def get_total_income(self) -> float:
        return sum(p.metrics.total_income for p in self.profiles)

    def get_total_expense(self) -> float:
        return sum(p.metrics.total_expense for p in self.profiles)

    def get_high_risk_profiles(self, threshold: float = 70.0) -> List[Profile]:
        return [p for p in self.profiles if p.risk_score and p.risk_score >= threshold]
