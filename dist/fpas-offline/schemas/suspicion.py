"""
疑点数据模型 - Suspicion Schema
定义可疑交易检测的标准数据结构。
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, ConfigDict


class SuspicionSeverity(str, Enum):
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


class SuspicionType(str, Enum):
    CASH_COLLISION = "现金碰撞"
    DIRECT_TRANSFER = "直接转账"
    LARGE_CASH = "大额现金"
    FREQUENT_TRANSFER = "频繁转账"
    SUSPICIOUS_COUNTERPARTY = "可疑对手方"
    ROUND_AMOUNT = "整数金额"
    UNUSUAL_TIME = "异常时间"
    OTHER = "其他"


class Suspicion(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        extra='ignore',
        validate_assignment=True,
        str_strip_whitespace=True
    )

    suspicion_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="疑点唯一标识符"
    )
    suspicion_type: SuspicionType = Field(
        ...,
        description="疑点类型"
    )
    severity: SuspicionSeverity = Field(
        ...,
        description="严重程度：高、中、低"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="疑点详细描述"
    )
    related_transactions: List[str] = Field(
        default_factory=list,
        max_length=1000,
        description="关联交易ID列表"
    )
    amount: float = Field(
        ...,
        ge=0,
        lt=1e12,
        description="涉及金额"
    )
    detection_date: date = Field(
        default_factory=date.today,
        description="检测日期"
    )
    entity_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="涉及实体名称"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="置信度 (0-1)"
    )
    evidence: Optional[str] = Field(
        None,
        max_length=2000,
        description="证据说明"
    )
    status: str = Field(
        default="待核实",
        pattern=r'^(待核实|已核实|已排除|存疑)$',
        description="核实状态"
    )

    @field_validator('related_transactions')
    @classmethod
    def validate_transaction_ids(cls, v):
        if len(v) > 1000:
            raise ValueError('关联交易ID数量不能超过1000个')
        return v

    @field_validator('description', 'entity_name')
    @classmethod
    def strip_and_validate(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError('该字段不能为空')
        return v


class SuspicionReport(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        extra='ignore'
    )

    report_id: str = Field(..., description="报告ID")
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="生成时间"
    )
    entity_name: str = Field(..., description="目标实体名称")
    suspicions: List[Suspicion] = Field(
        default_factory=list,
        max_length=10000,
        description="疑点列表"
    )
    total_amount: float = Field(
        default=0.0,
        ge=0,
        description="疑点涉及总金额"
    )

    @field_validator('suspicions')
    @classmethod
    def validate_suspicion_count(cls, v):
        if len(v) > 10000:
            raise ValueError('疑点数量不能超过10000个')
        return v

    def get_high_risk_count(self) -> int:
        return sum(1 for s in self.suspicions if s.severity == SuspicionSeverity.HIGH)

    def get_medium_risk_count(self) -> int:
        return sum(1 for s in self.suspicions if s.severity == SuspicionSeverity.MEDIUM)

    def get_low_risk_count(self) -> int:
        return sum(1 for s in self.suspicions if s.severity == SuspicionSeverity.LOW)
