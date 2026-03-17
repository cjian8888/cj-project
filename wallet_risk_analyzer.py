#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电子钱包风险增强分析器

在主体摘要型预警之外，补充：
1. 钱包-银行主链联动规则
2. 钱包交易级行为规则
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set

import pandas as pd

import financial_profiler
import utils
import wallet_data_extractor
from name_normalizer import normalize_for_matching
from utils.safe_types import safe_float, safe_int, safe_str

logger = utils.setup_logger(__name__)


def enhance_wallet_alerts(
    wallet_data: Dict[str, Any],
    artifact_details: Dict[str, List[Dict[str, Any]]],
    cleaned_data: Dict[str, pd.DataFrame],
    id_to_name_map: Optional[Dict[str, str]] = None,
    profiles: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """基于规范化明细和银行主链数据补充钱包高级预警。"""
    if not isinstance(wallet_data, dict) or not wallet_data.get("available"):
        return wallet_data or wallet_data_extractor.empty_wallet_data()

    artifact_details = artifact_details or {}
    cleaned_data = cleaned_data or {}
    id_to_name_map = id_to_name_map or {}
    profiles = profiles or {}

    subjects = wallet_data.get("subjects", []) or []
    if not subjects:
        return wallet_data

    unified_wallet_rows = _build_unified_wallet_transactions(wallet_data, artifact_details)
    bank_rows_by_subject = _build_bank_rows_by_subject(subjects, cleaned_data, id_to_name_map)
    subject_contexts = _build_subject_contexts(subjects, profiles, id_to_name_map)

    existing_alerts = list(wallet_data.get("alerts", []) or [])
    seen_keys = {
        (
            safe_str(item.get("alert_type")) or "",
            safe_str(item.get("person")) or "",
            safe_str(item.get("counterparty")) or "",
            safe_str(item.get("date")) or "",
        )
        for item in existing_alerts
        if isinstance(item, dict)
    }

    additional_alerts: List[Dict[str, Any]] = []
    for subject in subjects:
        if not isinstance(subject, dict):
            continue

        subject_id = safe_str(subject.get("subjectId")) or ""
        subject_name = safe_str(subject.get("subjectName")) or subject_id
        matched_to_core = bool(subject.get("matchedToCore"))
        subject_context = (
            subject_contexts.get(subject_id)
            or subject_contexts.get(subject_name)
            or {}
        )
        subject_rows = [
            row for row in unified_wallet_rows
            if row.get("subjectId") == subject_id
            or (
                not row.get("subjectId")
                and subject_name
                and normalize_for_matching(safe_str(row.get("subjectName")) or "") == normalize_for_matching(subject_name)
            )
        ]
        if not subject_rows:
            continue

        additional_alerts.extend(
            _detect_transaction_level_alerts(
                subject=subject,
                transaction_rows=subject_rows,
                subject_context=subject_context,
            )
        )

        if matched_to_core:
            bank_rows = bank_rows_by_subject.get(subject_id)
            if bank_rows is None:
                bank_rows = bank_rows_by_subject.get(subject_name)
            if bank_rows is not None and not bank_rows.empty:
                additional_alerts.extend(
                    _detect_bank_linkage_alerts(
                        subject=subject,
                        transaction_rows=subject_rows,
                        bank_rows=bank_rows,
                        subject_context=subject_context,
                    )
                )

    merged_alerts = existing_alerts[:]
    for alert in additional_alerts:
        key = (
            safe_str(alert.get("alert_type")) or "",
            safe_str(alert.get("person")) or "",
            safe_str(alert.get("counterparty")) or "",
            safe_str(alert.get("date")) or "",
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged_alerts.append(alert)

    wallet_data["alerts"] = _sort_wallet_alerts(merged_alerts)
    return wallet_data


def _build_unified_wallet_transactions(
    wallet_data: Dict[str, Any],
    artifact_details: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    subjects_by_id = wallet_data.get("subjectsById", {}) or {}
    subjects_by_name = wallet_data.get("subjectsByName", {}) or {}
    rows: List[Dict[str, Any]] = []

    for row in artifact_details.get("alipayTransactionRows", []) or []:
        if not isinstance(row, dict) or not row.get("isEffective"):
            continue
        subject = _resolve_wallet_subject(row, subjects_by_id, subjects_by_name)
        direction = safe_str(row.get("direction")) or ""
        if direction not in {"收入", "支出"}:
            continue
        tx_time = pd.to_datetime(row.get("createdAt") or row.get("paidAt") or row.get("modifiedAt"), errors="coerce")
        if pd.isna(tx_time):
            continue
        rows.append(
            {
                "subjectId": safe_str(subject.get("subjectId")) if isinstance(subject, dict) else safe_str(row.get("subjectId")),
                "subjectName": safe_str(subject.get("subjectName")) if isinstance(subject, dict) else safe_str(row.get("subjectName")),
                "matchedToCore": bool(subject.get("matchedToCore")) if isinstance(subject, dict) else False,
                "platform": "alipay",
                "direction": "income" if direction == "收入" else "expense",
                "amountYuan": safe_float(row.get("amountYuan")) or 0.0,
                "counterparty": safe_str(row.get("counterpartyName")) or "",
                "description": safe_str(row.get("itemName")) or "",
                "occurredAt": tx_time,
            }
        )

    for row in artifact_details.get("tenpayTransactionRows", []) or []:
        if not isinstance(row, dict):
            continue
        direction = safe_str(row.get("direction")) or ""
        if direction not in {"入", "出"}:
            continue
        subject = _resolve_wallet_subject(row, subjects_by_id, subjects_by_name)
        tx_time = pd.to_datetime(row.get("transactionTime"), errors="coerce")
        if pd.isna(tx_time):
            continue
        rows.append(
            {
                "subjectId": safe_str(subject.get("subjectId")) if isinstance(subject, dict) else safe_str(row.get("subjectId")),
                "subjectName": safe_str(subject.get("subjectName")) if isinstance(subject, dict) else safe_str(row.get("subjectName")),
                "matchedToCore": bool(subject.get("matchedToCore")) if isinstance(subject, dict) else False,
                "platform": "tenpay",
                "direction": "income" if direction == "入" else "expense",
                "amountYuan": safe_float(row.get("amountYuan")) or 0.0,
                "counterparty": safe_str(row.get("counterpartyName")) or "",
                "description": safe_str(row.get("remark1")) or safe_str(row.get("purposeType")) or "",
                "occurredAt": tx_time,
            }
        )

    rows.sort(key=lambda item: item["occurredAt"])
    return rows


def _resolve_wallet_subject(
    row: Dict[str, Any],
    subjects_by_id: Dict[str, Dict[str, Any]],
    subjects_by_name: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    subject_id = safe_str(row.get("subjectId")) or ""
    if subject_id and subject_id in subjects_by_id:
        return subjects_by_id[subject_id]

    subject_name = safe_str(row.get("subjectName")) or ""
    if subject_name and subject_name in subjects_by_name:
        return subjects_by_name[subject_name]
    return None


def _build_bank_rows_by_subject(
    subjects: Iterable[Dict[str, Any]],
    cleaned_data: Dict[str, pd.DataFrame],
    id_to_name_map: Dict[str, str],
) -> Dict[str, pd.DataFrame]:
    result: Dict[str, pd.DataFrame] = {}
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        subject_id = safe_str(subject.get("subjectId")) or ""
        subject_name = safe_str(subject.get("subjectName")) or ""
        candidate_names = [subject_name]
        mapped_name = id_to_name_map.get(subject_id)
        if mapped_name and mapped_name not in candidate_names:
            candidate_names.append(mapped_name)

        bank_df = None
        for candidate in candidate_names:
            if candidate and candidate in cleaned_data:
                bank_df = cleaned_data[candidate]
                break
        if bank_df is None or not isinstance(bank_df, pd.DataFrame) or bank_df.empty:
            continue

        normalized = financial_profiler.standardize_columns(bank_df)
        working = pd.DataFrame(index=normalized.index)
        working["date"] = pd.to_datetime(_frame_series(normalized, "date", pd.NaT), errors="coerce")
        working["income"] = pd.to_numeric(_frame_series(normalized, "income", 0.0), errors="coerce").fillna(0.0)
        working["expense"] = pd.to_numeric(_frame_series(normalized, "expense", 0.0), errors="coerce").fillna(0.0)
        working["amount"] = pd.to_numeric(_frame_series(normalized, "amount", 0.0), errors="coerce").fillna(0.0)
        working["counterparty"] = _frame_series(normalized, "counterparty", "").fillna("").astype(str)
        working["description"] = _frame_series(normalized, "description", "").fillna("").astype(str)
        working = working.dropna(subset=["date"]).reset_index(drop=True)
        if working.empty:
            continue

        if subject_id:
            result[subject_id] = working
        if subject_name:
            result[subject_name] = working
    return result


def _build_subject_contexts(
    subjects: Iterable[Dict[str, Any]],
    profiles: Dict[str, Dict[str, Any]],
    id_to_name_map: Dict[str, str],
) -> Dict[str, Dict[str, Any]]:
    contexts: Dict[str, Dict[str, Any]] = {}
    if not profiles:
        return contexts

    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        subject_id = safe_str(subject.get("subjectId")) or ""
        subject_name = safe_str(subject.get("subjectName")) or subject_id
        profile = _resolve_profile_for_subject(subject_name, subject_id, profiles, id_to_name_map)
        if not isinstance(profile, dict):
            continue

        context = {
            "self_aliases": financial_profiler._build_name_alias_set([subject_name]),
            "family_aliases": _collect_family_aliases(profile, subject_name),
            "salary_payer_aliases": _collect_salary_payer_aliases(profile),
        }
        if subject_id:
            contexts[subject_id] = context
        if subject_name:
            contexts[subject_name] = context
    return contexts


def _resolve_profile_for_subject(
    subject_name: str,
    subject_id: str,
    profiles: Dict[str, Dict[str, Any]],
    id_to_name_map: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    candidate_names = [subject_name]
    mapped_name = id_to_name_map.get(subject_id)
    if mapped_name and mapped_name not in candidate_names:
        candidate_names.append(mapped_name)

    for candidate in candidate_names:
        if candidate and candidate in profiles and isinstance(profiles[candidate], dict):
            return profiles[candidate]
    return None


def _collect_family_aliases(profile: Dict[str, Any], subject_name: str) -> Set[str]:
    family_aliases: Set[str] = set()
    for name in _extract_person_names(profile.get("coaddress_persons", [])):
        if name and not financial_profiler._matches_name(name, subject_name):
            family_aliases.update(financial_profiler._build_name_alias_set([name]))
    return family_aliases


def _collect_salary_payer_aliases(profile: Dict[str, Any]) -> Set[str]:
    aliases: Set[str] = set()

    legitimate_details = profile.get("income_classification", {}).get("legitimate_details", [])
    for row in legitimate_details if isinstance(legitimate_details, list) else []:
        if not isinstance(row, dict):
            continue
        reason = safe_str(row.get("reason")) or ""
        counterparty = safe_str(row.get("counterparty")) or ""
        if counterparty and "工资性收入" in reason:
            aliases.update(financial_profiler._build_name_alias_set([counterparty]))

    yearly_details = profile.get("yearly_salary", {}).get("details", [])
    for row in yearly_details if isinstance(yearly_details, list) else []:
        if not isinstance(row, dict):
            continue
        counterparty = safe_str(row.get("counterparty")) or ""
        if counterparty:
            aliases.update(financial_profiler._build_name_alias_set([counterparty]))

    return aliases


def _extract_person_names(items: Any) -> List[str]:
    names: List[str] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, str):
                value = safe_str(item) or ""
            elif isinstance(item, dict):
                value = (
                    safe_str(item.get("name"))
                    or safe_str(item.get("person_name"))
                    or safe_str(item.get("related_name"))
                    or ""
                )
            else:
                value = ""
            if value:
                names.append(value)
    return names


def _detect_transaction_level_alerts(
    *,
    subject: Dict[str, Any],
    transaction_rows: List[Dict[str, Any]],
    subject_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    subject_id = safe_str(subject.get("subjectId")) or ""
    subject_name = safe_str(subject.get("subjectName")) or subject_id
    matched_to_core = bool(subject.get("matchedToCore"))
    tx_df = pd.DataFrame(transaction_rows)
    if tx_df.empty:
        return alerts

    tx_df["date_only"] = tx_df["occurredAt"].dt.strftime("%Y-%m-%d")
    tx_df["hour"] = tx_df["occurredAt"].dt.hour
    tx_df["counterparty_role"] = tx_df["counterparty"].map(
        lambda value: _classify_counterparty_role(safe_str(value) or "", subject_context or {})
    )

    income_df = tx_df[tx_df["direction"] == "income"].copy()
    if not income_df.empty:
        income_df["is_small_income"] = income_df["amountYuan"].between(500, 10000, inclusive="both")
        split_candidates = (
            income_df[income_df["is_small_income"]]
            .groupby("date_only")
            .agg(transaction_count=("amountYuan", "count"), total_amount=("amountYuan", "sum"))
            .reset_index()
        )
        for _, row in split_candidates.iterrows():
            transaction_count = int(row["transaction_count"])
            total_amount = float(row["total_amount"])
            if transaction_count >= 8 and total_amount >= 30000:
                alerts.append(
                    wallet_data_extractor._build_wallet_alert_record(
                        alert_type="wallet_split_collection",
                        person=subject_name,
                        counterparty="电子钱包收入聚集",
                        date=safe_str(row["date_only"]) or "",
                        amount=round(total_amount, 2),
                        description=f"{subject_name}在{row['date_only']}出现{transaction_count}笔小额收入，累计{total_amount / 10000:.1f}万元。",
                        risk_level="high" if (transaction_count >= 20 or total_amount >= 100000) else "medium",
                        risk_reason="短时间内连续出现多笔小额收入，存在拆分收款或集中归集的可能。",
                        subject_id=subject_id,
                        matched_to_core=matched_to_core,
                        transaction_count=transaction_count,
                        evidence_summary=f"{row['date_only']} 小额收入 {transaction_count} 笔，累计 {total_amount / 10000:.1f} 万元。",
                    )
                )

    daily_summary = (
        tx_df.groupby(["date_only", "direction"])["amountYuan"]
        .sum()
        .unstack(fill_value=0.0)
        .reset_index()
        .sort_values("date_only")
    )
    if not daily_summary.empty:
        daily_summary["date_dt"] = pd.to_datetime(daily_summary["date_only"], errors="coerce")
        for index, row in daily_summary.iterrows():
            income_total = float(row.get("income", 0.0) or 0.0)
            if income_total < 100000:
                continue
            base_date = row["date_dt"]
            next_window = daily_summary[
                (daily_summary["date_dt"] >= base_date)
                & (daily_summary["date_dt"] <= base_date + pd.Timedelta(days=1))
            ]
            expense_total = float(next_window.get("expense", pd.Series(dtype=float)).sum())
            if expense_total >= 80000 and expense_total >= income_total * 0.7:
                window_rows = tx_df[
                    (tx_df["occurredAt"] >= base_date)
                    & (tx_df["occurredAt"] < base_date + pd.Timedelta(days=2))
                ]
                income_rows = window_rows[window_rows["direction"] == "income"]
                expense_rows = window_rows[window_rows["direction"] == "expense"]
                if _should_suppress_flow_alert(income_rows, "amountYuan") or _should_suppress_flow_alert(
                    expense_rows, "amountYuan"
                ):
                    continue
                transaction_count = int(
                    len(window_rows)
                )
                alerts.append(
                    wallet_data_extractor._build_wallet_alert_record(
                        alert_type="wallet_quick_pass_through",
                        person=subject_name,
                        counterparty="电子钱包快速转手",
                        date=safe_str(row["date_only"]) or "",
                        amount=round(expense_total, 2),
                        description=f"{subject_name}在{row['date_only']}及次日电子钱包收入{income_total / 10000:.1f}万元，随后支出{expense_total / 10000:.1f}万元。",
                        risk_level="high" if expense_total >= 300000 else "medium",
                        risk_reason="收入后短时间内快速转出，存在资金过手或通道化使用的可能。",
                        subject_id=subject_id,
                        matched_to_core=matched_to_core,
                        transaction_count=transaction_count,
                        evidence_summary=f"{row['date_only']} 至次日收入 {income_total / 10000:.1f} 万元，支出 {expense_total / 10000:.1f} 万元。",
                    )
                )
                break

    night_df = tx_df[(tx_df["hour"] >= 22) | (tx_df["hour"] < 6)].copy()
    if not night_df.empty:
        night_count = int(len(night_df))
        night_amount = float(night_df["amountYuan"].sum())
        if night_count >= 8 and night_amount >= 50000:
            latest_date = safe_str(night_df["date_only"].max()) or ""
            alerts.append(
                wallet_data_extractor._build_wallet_alert_record(
                    alert_type="wallet_night_activity",
                    person=subject_name,
                    counterparty="夜间活跃交易",
                    date=latest_date,
                    amount=round(night_amount, 2),
                    description=f"{subject_name}夜间时段发生{night_count}笔电子钱包交易，累计{night_amount / 10000:.1f}万元。",
                    risk_level="high" if night_amount >= 100000 else "medium",
                    risk_reason="夜间高频或大额电子钱包交易异常度较高，建议结合交易用途核查。",
                    subject_id=subject_id,
                    matched_to_core=matched_to_core,
                    transaction_count=night_count,
                    evidence_summary=f"夜间交易 {night_count} 笔，累计 {night_amount / 10000:.1f} 万元。",
                )
            )

    return alerts


def _detect_bank_linkage_alerts(
    *,
    subject: Dict[str, Any],
    transaction_rows: List[Dict[str, Any]],
    bank_rows: pd.DataFrame,
    subject_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    subject_id = safe_str(subject.get("subjectId")) or ""
    subject_name = safe_str(subject.get("subjectName")) or subject_id

    tx_df = pd.DataFrame(transaction_rows)
    wallet_counterparty_stats = _wallet_counterparty_stats(transaction_rows, subject)
    bank_counterparty_stats = _bank_counterparty_stats(bank_rows)
    overlaps = []
    for normalized_name, wallet_stat in wallet_counterparty_stats.items():
        bank_stat = bank_counterparty_stats.get(normalized_name)
        if not bank_stat:
            continue
        combined_amount = float(wallet_stat["amount"]) + float(bank_stat["amount"])
        if int(wallet_stat["count"]) >= 3 and int(bank_stat["count"]) >= 3 and combined_amount >= 100000:
            overlaps.append(
                {
                    "counterparty": wallet_stat["display_name"] or bank_stat["display_name"],
                    "wallet_count": int(wallet_stat["count"]),
                    "wallet_amount": float(wallet_stat["amount"]),
                    "bank_count": int(bank_stat["count"]),
                    "bank_amount": float(bank_stat["amount"]),
                    "combined_amount": combined_amount,
                }
            )
    overlaps.sort(key=lambda item: (item["combined_amount"], item["wallet_count"] + item["bank_count"]), reverse=True)
    contextualized_overlaps = []
    for overlap in overlaps:
        risk_level, risk_reason, counterparty_role = _evaluate_overlap_risk(
            overlap,
            subject_context or {},
        )
        overlap["risk_level"] = risk_level
        overlap["risk_reason"] = risk_reason
        overlap["counterparty_role"] = counterparty_role
        contextualized_overlaps.append(overlap)

    contextualized_overlaps.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(item.get("risk_level", "medium"), 3),
            -float(item.get("combined_amount", 0.0) or 0.0),
            -(int(item.get("wallet_count", 0)) + int(item.get("bank_count", 0))),
        )
    )
    prioritized = [item for item in contextualized_overlaps if item.get("risk_level") != "low"]
    deferred = [item for item in contextualized_overlaps if item.get("risk_level") == "low"]
    selected_overlaps = (prioritized + deferred)[:3]

    for overlap in selected_overlaps:
        role_hint = overlap.get("counterparty_role")
        if _exclude_overlap_from_alerts(role_hint):
            continue
        role_note = f"角色判定: {role_hint}。" if role_hint and role_hint != "external" else ""
        alerts.append(
            wallet_data_extractor._build_wallet_alert_record(
                alert_type="wallet_bank_counterparty_overlap",
                person=subject_name,
                counterparty=overlap["counterparty"],
                date="",
                amount=round(overlap["combined_amount"], 2),
                description=(
                    f"{subject_name}的电子钱包与银行流水均与{overlap['counterparty']}存在集中往来，"
                    f"钱包{overlap['wallet_count']}笔、银行{overlap['bank_count']}笔。"
                ),
                risk_level=overlap["risk_level"],
                risk_reason=overlap["risk_reason"],
                subject_id=subject_id,
                matched_to_core=True,
                transaction_count=overlap["wallet_count"] + overlap["bank_count"],
                overlap_count=1,
                evidence_summary=(
                    f"钱包 {overlap['wallet_count']} 笔/{overlap['wallet_amount'] / 10000:.1f} 万元，"
                    f"银行 {overlap['bank_count']} 笔/{overlap['bank_amount'] / 10000:.1f} 万元。"
                    f"{(' ' + role_note) if role_note else ''}"
                ),
            )
        )

    if not tx_df.empty:
        tx_df["date_only"] = tx_df["occurredAt"].dt.normalize()
        wallet_income = (
            tx_df[tx_df["direction"] == "income"]
            .groupby("date_only")["amountYuan"]
            .sum()
            .reset_index(name="wallet_income")
            .sort_values("date_only")
        )
        bank_working = bank_rows.copy()
        bank_working["date_only"] = bank_working["date"].dt.normalize()
        bank_working["counterparty_role"] = bank_working["counterparty"].map(
            lambda value: _classify_counterparty_role(safe_str(value) or "", subject_context or {})
        )
        bank_expense = (
            bank_working.groupby("date_only")["expense"]
            .sum()
            .reset_index(name="bank_expense")
            .sort_values("date_only")
        )
        for _, row in wallet_income.iterrows():
            income_total = float(row["wallet_income"])
            if income_total < 100000:
                continue
            base_date = row["date_only"]
            bank_window = bank_expense[
                (bank_expense["date_only"] >= base_date)
                & (bank_expense["date_only"] <= base_date + pd.Timedelta(days=2))
            ]
            bank_outflow = float(bank_window["bank_expense"].sum())
            if bank_outflow >= 80000 and bank_outflow >= income_total * 0.7:
                wallet_income_rows = tx_df[
                    (tx_df["occurredAt"] >= base_date)
                    & (tx_df["occurredAt"] < base_date + pd.Timedelta(days=1))
                    & (tx_df["direction"] == "income")
                ]
                bank_expense_rows = bank_working[
                    (bank_working["date"] >= base_date)
                    & (bank_working["date"] < base_date + pd.Timedelta(days=3))
                    & (bank_working["expense"] > 0)
                ]
                if _should_suppress_flow_alert(wallet_income_rows, "amountYuan") or _should_suppress_flow_alert(
                    bank_expense_rows, "expense"
                ):
                    continue
                wallet_tx_count = int(
                    len(
                        tx_df[
                            (tx_df["occurredAt"] >= base_date)
                            & (tx_df["occurredAt"] < base_date + pd.Timedelta(days=3))
                            & (tx_df["direction"] == "income")
                        ]
                    )
                )
                bank_tx_count = int(len(bank_expense_rows))
                alerts.append(
                    wallet_data_extractor._build_wallet_alert_record(
                        alert_type="wallet_bank_quick_outflow",
                        person=subject_name,
                        counterparty="银行账户支出",
                        date=base_date.strftime("%Y-%m-%d"),
                        amount=round(bank_outflow, 2),
                        description=(
                            f"{subject_name}电子钱包在{base_date.strftime('%Y-%m-%d')}流入{income_total / 10000:.1f}万元，"
                            f"银行账户在两日内支出{bank_outflow / 10000:.1f}万元。"
                        ),
                        risk_level="high" if bank_outflow >= 300000 else "medium",
                        risk_reason="电子钱包收入后短时间内银行账户快速支出，存在跨通道过手或转移迹象。",
                        subject_id=subject_id,
                        matched_to_core=True,
                        transaction_count=wallet_tx_count + bank_tx_count,
                        evidence_summary=(
                            f"{base_date.strftime('%Y-%m-%d')} 钱包流入 {income_total / 10000:.1f} 万元，"
                            f"两日内银行支出 {bank_outflow / 10000:.1f} 万元，"
                            f"对应钱包入账 {wallet_tx_count} 笔、银行支出 {bank_tx_count} 笔。"
                        ),
                    )
                )
                break

    return alerts


def _exclude_overlap_from_alerts(counterparty_role: Any) -> bool:
    normalized_role = safe_str(counterparty_role) or ""
    return normalized_role in {"self", "salary_payer"}


def _should_suppress_flow_alert(rows: pd.DataFrame, amount_column: str) -> bool:
    excluded_roles = {"self", "family", "salary_payer"}
    return _role_amount_share(rows, amount_column, excluded_roles) >= 0.7


def _role_amount_share(rows: pd.DataFrame, amount_column: str, roles: Set[str]) -> float:
    if (
        rows is None
        or rows.empty
        or amount_column not in rows.columns
        or "counterparty_role" not in rows.columns
        or not roles
    ):
        return 0.0

    amounts = pd.to_numeric(rows[amount_column], errors="coerce").fillna(0.0).clip(lower=0.0)
    total_amount = float(amounts.sum())
    if total_amount <= 0:
        return 0.0

    role_mask = rows["counterparty_role"].isin(roles)
    role_amount = float(amounts[role_mask].sum())
    return role_amount / total_amount


def _evaluate_overlap_risk(
    overlap: Dict[str, Any],
    subject_context: Dict[str, Any],
) -> tuple[str, str, str]:
    counterparty = safe_str(overlap.get("counterparty")) or ""
    counterparty_role = _classify_counterparty_role(counterparty, subject_context)
    combined_amount = float(overlap.get("combined_amount") or 0.0)
    wallet_amount = float(overlap.get("wallet_amount") or 0.0)
    bank_amount = float(overlap.get("bank_amount") or 0.0)
    wallet_share = wallet_amount / combined_amount if combined_amount > 0 else 0.0

    if counterparty_role == "self":
        return (
            "low",
            "对手方已识别为本人/同名账户，当前重叠更接近跨通道自有资金往来，不宜按外部高风险往来直接上提。",
            counterparty_role,
        )
    if counterparty_role == "family":
        return (
            "low",
            "对手方已识别为家庭成员/同住址成员，当前重叠应按家庭资金往来单独看待，不宜按外部高风险往来直接上提。",
            counterparty_role,
        )
    if counterparty_role == "salary_payer":
        risk_level = "low" if wallet_share <= 0.2 or bank_amount >= wallet_amount else "medium"
        return (
            risk_level,
            "对手方已在工资识别中命中发薪单位，当前跨通道重叠更可能体现为工资、奖金或福利留痕，应先按工资语义核验后再决定是否上提风险。",
            counterparty_role,
        )
    if counterparty_role in {"financial_platform", "public_institution"}:
        return (
            "low",
            "对手方属于金融平台/公共机构语义，当前重叠更适合作为资金路径提示，不宜直接按高风险往来处理。",
            counterparty_role,
        )

    return (
        "high" if combined_amount >= 300000 else "medium",
        "同一对手方同时出现在电子钱包和银行主链中，值得优先核查其真实关系与资金用途。",
        counterparty_role,
    )


def _classify_counterparty_role(counterparty: str, subject_context: Dict[str, Any]) -> str:
    self_aliases = subject_context.get("self_aliases") or set()
    if financial_profiler._matches_alias_set(counterparty, self_aliases):
        return "self"

    family_aliases = subject_context.get("family_aliases") or set()
    if financial_profiler._matches_alias_set(counterparty, family_aliases):
        return "family"

    salary_payer_aliases = subject_context.get("salary_payer_aliases") or set()
    if financial_profiler._matches_alias_set(counterparty, salary_payer_aliases):
        return "salary_payer"

    lower_name = counterparty.lower()
    financial_keywords = [
        "支付宝",
        "财付通",
        "微信支付",
        "银联",
        "网联",
        "基金",
        "证券",
        "保险",
        "理财",
        "花呗",
        "信用购",
        "支付",
    ]
    if any(keyword.lower() in lower_name for keyword in financial_keywords):
        return "financial_platform"

    public_keywords = ["财政局", "公积金", "社保", "医保", "税务", "人力资源和社会保障", "住房公积金"]
    if any(keyword in counterparty for keyword in public_keywords):
        return "public_institution"

    return "external"


def _frame_series(df: pd.DataFrame, column_name: str, default: Any) -> pd.Series:
    if column_name in df.columns:
        return df[column_name]
    return pd.Series([default] * len(df), index=df.index)


def _wallet_counterparty_stats(
    transaction_rows: List[Dict[str, Any]],
    subject: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    for row in transaction_rows:
        if not isinstance(row, dict):
            continue
        name = safe_str(row.get("counterparty")) or ""
        normalized = normalize_for_matching(name)
        if not normalized:
            continue
        stats.setdefault(
            normalized,
            {"display_name": name, "count": 0, "amount": 0.0},
        )
        stats[normalized]["count"] += 1
        stats[normalized]["amount"] += abs(safe_float(row.get("amountYuan")) or 0.0)

    if stats or not isinstance(subject, dict):
        return stats

    platforms = subject.get("platforms", {}) or {}
    for platform_key in ("alipay", "wechat"):
        platform = platforms.get(platform_key, {}) or {}
        for item in platform.get("topCounterparties", []) or []:
            if not isinstance(item, dict):
                continue
            name = safe_str(item.get("name")) or ""
            normalized = normalize_for_matching(name)
            if not normalized:
                continue
            stats.setdefault(
                normalized,
                {"display_name": name, "count": 0, "amount": 0.0},
            )
            stats[normalized]["count"] += safe_int(item.get("count")) or 0
            stats[normalized]["amount"] += safe_float(item.get("totalAmountYuan")) or 0.0
    return stats


def _bank_counterparty_stats(bank_rows: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    if bank_rows is None or bank_rows.empty:
        return stats

    for _, row in bank_rows.iterrows():
        name = safe_str(row.get("counterparty")) or ""
        normalized = normalize_for_matching(name)
        if not normalized:
            continue
        amount = abs(safe_float(row.get("amount")) or 0.0)
        if amount <= 0:
            amount = max(safe_float(row.get("income")) or 0.0, safe_float(row.get("expense")) or 0.0)
        stats.setdefault(
            normalized,
            {"display_name": name, "count": 0, "amount": 0.0},
        )
        stats[normalized]["count"] += 1
        stats[normalized]["amount"] += float(amount or 0.0)
    return stats


def _sort_wallet_alerts(alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        alerts,
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(str(item.get("risk_level", "medium")), 3),
            -(float(item.get("risk_score", 0) or 0)),
            -(float(item.get("amount", 0) or 0)),
            safe_str(item.get("person")) or "",
        ),
    )
