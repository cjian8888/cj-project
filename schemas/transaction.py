"""
交易数据模型 - Transaction Schema
定义金融交易的标准数据结构，包含完整的验证规则。
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class Transaction(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        extra='ignore',
        validate_assignment=True,
        str_strip_whitespace=True
    )

    tx_date: date = Field(..., description="交易日期 (YYYY-MM-DD格式)")
    amount: float = Field(
        ...,
        gt=-1e12,
        lt=1e12,
        description="交易金额 (正数为收入，负数为支出)"
    )
    tx_type: str = Field(
        ...,
        min_length=1,
        max_length=20,
        pattern=r'^(收入|支出|转账|现金|其他)$',
        description="交易类型：收入、支出、转账、现金、其他"
    )
    counterparty: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="交易对手方名称"
    )
    account: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="交易账户号码"
    )
    bank: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="开户银行名称"
    )
    currency: str = Field(
        default='CNY',
        pattern=r'^[A-Z]{3}$',
        description="货币代码 (ISO 4217标准，如CNY、USD)"
    )
    balance_after: Optional[float] = Field(
        None,
        gt=-1e12,
        lt=1e12,
        description="交易后账户余额"
    )
    reference: Optional[str] = Field(
        None,
        max_length=100,
        description="交易参考号或流水号"
    )
    memo: Optional[str] = Field(
        None,
        max_length=500,
        description="交易备注信息"
    )

    @field_validator('tx_date', mode='before')
    @classmethod
    def parse_date(cls, v):
        from datetime import date as date_cls
        if isinstance(v, date_cls):
            return v
        if isinstance(v, str):
            from datetime import datetime
            formats = ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%Y年%m月%d日']
            for fmt in formats:
                try:
                    return datetime.strptime(v.strip(), fmt).date()
                except ValueError:
                    continue
            raise ValueError(f'无法解析日期格式: {v}')
        raise ValueError(f'日期必须是字符串或date类型，实际类型: {type(v)}')

    @field_validator('amount', mode='before')
    @classmethod
    def parse_amount(cls, v):
        if isinstance(v, str):
            cleaned = v.strip().replace(',', '').replace('¥', '').replace('$', '').replace('￥', '')
            try:
                return float(cleaned)
            except ValueError:
                raise ValueError(f'无法解析金额: {v}')
        return float(v)

    @field_validator('counterparty', 'account', 'bank', 'tx_type')
    @classmethod
    def strip_and_validate(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError('该字段不能为空')
        return v

    def is_income(self) -> bool:
        return self.amount > 0 or self.tx_type == '收入'

    def is_expense(self) -> bool:
        return self.amount < 0 or self.tx_type == '支出'

    def is_cash(self) -> bool:
        return self.tx_type == '现金'


class TransactionBatch(BaseModel):
    model_config = ConfigDict(
        frozen=False,
        extra='ignore'
    )

    transactions: list[Transaction] = Field(
        default_factory=list,
        max_length=100000,
        description="交易记录列表，最多10万条"
    )
    source_file: Optional[str] = Field(
        None,
        max_length=500,
        description="数据来源文件路径"
    )

    @field_validator('transactions')
    @classmethod
    def validate_batch_size(cls, v):
        if len(v) > 100000:
            raise ValueError('单次批次最多支持10万条交易记录')
        return v

    def get_total_amount(self) -> float:
        return sum(t.amount for t in self.transactions)

    def get_income_total(self) -> float:
        return sum(t.amount for t in self.transactions if t.is_income())

    def get_expense_total(self) -> float:
        return sum(abs(t.amount) for t in self.transactions if t.is_expense())
