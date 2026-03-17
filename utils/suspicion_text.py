#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接转账疑点的文本归一化与去重辅助函数。"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple


def safe_suspicion_text(value: Any) -> str:
    """将疑点文本统一转换为可比较字符串。"""
    if value is None:
        return ""

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    return text


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_mirror_suffix(text: str) -> str:
    compact = _normalize_whitespace(text)
    return re.sub(r"\s+US$", "", compact, flags=re.IGNORECASE).strip()


def normalize_direct_transfer_description_text(
    raw_description: Any, bank: str = ""
) -> Tuple[str, str]:
    """统一直接转账摘要的展示文案，并保留原始附言。"""
    raw_text = safe_suspicion_text(raw_description)
    if not raw_text:
        return "", ""

    compact = _normalize_whitespace(raw_text)
    bank_text = safe_suspicion_text(bank)

    if re.fullmatch(r"网银跨行汇款(?:\s*/\s*/CHN|CHN)", compact, re.IGNORECASE):
        return "网银跨行汇款", raw_text

    if re.match(r"^冲正\d+/\s*(?:CPSP|IBPS|BEPS)\d+\b", compact, re.IGNORECASE):
        normalized = (
            "中行系统跨行转账冲正附言（原始流水码已省略）"
            if "中国银行" in bank_text or "中行" in bank_text
            else "银行系统跨行转账冲正附言（原始流水码已省略）"
        )
        return normalized, raw_text

    if re.match(r"^(?:CPSP|IBPS|BEPS)\d+\b", compact, re.IGNORECASE):
        normalized = (
            "中行系统跨行转账附言（原始流水码已省略）"
            if "中国银行" in bank_text or "中行" in bank_text
            else "银行系统跨行转账附言（原始流水码已省略）"
        )
        return normalized, raw_text

    return compact, raw_text


def canonicalize_direct_transfer_description(
    raw_description: Any, bank: str = ""
) -> str:
    """为镜像流水去重生成稳定摘要 key。"""
    normalized, raw_text = normalize_direct_transfer_description_text(
        raw_description, bank
    )
    if normalized and normalized != safe_suspicion_text(raw_text):
        return normalized

    return _strip_mirror_suffix(raw_text or normalized)


def _coerce_amount(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_direct_transfer_dedupe_key(
    person: Any,
    company: Any,
    direction: Any,
    amount: Any,
    date_value: Any,
    description: Any,
    bank: str = "",
) -> Tuple[str, str, str, float, str, str]:
    """构造原始检测记录的去重键。"""
    return (
        safe_suspicion_text(person),
        safe_suspicion_text(company),
        safe_suspicion_text(direction),
        round(_coerce_amount(amount), 2),
        safe_suspicion_text(date_value),
        canonicalize_direct_transfer_description(description, bank),
    )


def build_serialized_direct_transfer_dedupe_key(
    record: Dict[str, Any]
) -> Tuple[str, str, str, float, str, str]:
    """构造前端序列化记录的去重键。"""
    return (
        safe_suspicion_text(record.get("from")),
        safe_suspicion_text(record.get("to")),
        safe_suspicion_text(record.get("direction")),
        round(_coerce_amount(record.get("amount")), 2),
        safe_suspicion_text(record.get("date")),
        canonicalize_direct_transfer_description(
            record.get("description"), safe_suspicion_text(record.get("bank"))
        ),
    )


def score_direct_transfer_record(
    record: Dict[str, Any],
    *,
    person: str = "",
    company: str = "",
    account_role: str = "",
) -> Tuple[int, int, int]:
    """为重复记录选择更适合作为展示来源的一条。"""
    role_rank = 0
    if account_role == "person":
        role_rank = 2
    elif account_role == "company":
        role_rank = 1
    else:
        source_file = safe_suspicion_text(record.get("sourceFile", record.get("source_file")))
        if person and person in source_file:
            role_rank = 2
        elif company and company in source_file:
            role_rank = 1

    evidence_refs = record.get("evidenceRefs", record.get("evidence_refs", {}))
    if not isinstance(evidence_refs, dict):
        evidence_refs = {}

    transaction_id = safe_suspicion_text(
        record.get("transactionId")
        or record.get("transaction_id")
        or evidence_refs.get("transaction_id")
        or evidence_refs.get("transactionId")
    )
    source_row_index = record.get("sourceRowIndex")
    if source_row_index is None:
        source_row_index = record.get("source_row_index")
    if source_row_index is None:
        source_row_index = evidence_refs.get("source_row_index")
    if source_row_index is None:
        source_row_index = evidence_refs.get("sourceRowIndex")

    try:
        row_score = -int(source_row_index)
    except (TypeError, ValueError):
        row_score = 0

    return (role_rank, 1 if transaction_id else 0, row_score)
