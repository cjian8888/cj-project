#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
疑点检测模块 - 实现版
用于检测资金流向中的异常模式和可疑交易
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Tuple
from itertools import combinations
import config
import utils
from holiday_service import build_holiday_window
from utils.suspicion_text import (
    build_direct_transfer_dedupe_key,
    score_direct_transfer_record,
)

logger = utils.setup_logger(__name__)


def _safe_float(value) -> float:
    """安全转换金额字段。"""
    return utils.format_amount(value)


def _safe_text(value) -> str:
    """安全转换文本字段。"""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    text = str(value)
    return "" if text == "nan" else text


def _extract_tx_amount(row: pd.Series) -> float:
    """统一提取单笔交易金额。"""
    income = _safe_float(row.get("income", row.get("收入(元)", 0)))
    expense = _safe_float(row.get("expense", row.get("支出(元)", 0)))
    if income or expense:
        return max(abs(income), abs(expense))

    return abs(_safe_float(row.get("amount", 0)))


def _extract_tx_direction(row: pd.Series) -> str:
    """提取交易方向。"""
    income = _safe_float(row.get("income", row.get("收入(元)", 0)))
    expense = _safe_float(row.get("expense", row.get("支出(元)", 0)))
    if income > 0 and income >= expense:
        return "income"
    if expense > 0:
        return "expense"

    amount = _safe_float(row.get("amount", 0))
    if amount > 0:
        return "income"
    if amount < 0:
        return "expense"
    return ""


def _extract_direct_transfer_direction(row: pd.Series, account_role: str) -> str:
    """将账户视角方向统一换算为人员视角方向。"""
    tx_direction = _extract_tx_direction(row)
    if tx_direction == "income":
        return "receive" if account_role == "person" else "payment"
    if tx_direction == "expense":
        return "payment" if account_role == "person" else "receive"
    return ""


def _build_direct_transfer_record(
    row: pd.Series,
    person: str,
    company: str,
    account_role: str,
) -> Dict:
    """构造统一的直接往来记录。"""
    amount = _extract_tx_amount(row)
    direction = _extract_direct_transfer_direction(row, account_role)
    if amount <= 0 or not direction:
        return {}

    source_row_index = row.get("source_row_index", row.name)
    if source_row_index is None:
        source_row_index = int(row.name) + 2

    return {
        "person": person,
        "company": company,
        "date": row.get("date", row.get("交易时间")),
        "amount": amount,
        "direction": direction,
        "description": _safe_text(row.get("description", row.get("交易摘要", ""))),
        "bank": _safe_text(row.get("银行来源", row.get("bank", ""))),
        "source_file": _safe_text(row.get("数据来源", row.get("source_file", ""))),
        "risk_level": "high"
        if amount > config.INCOME_HIGH_RISK_MIN
        else "medium"
        if amount > config.SUSPICION_MEDIUM_HIGH_AMOUNT
        else "low",
        "evidence_refs": {
            "source_row_index": int(source_row_index),
            "transaction_id": _safe_text(
                row.get("transaction_id", row.get("流水号", ""))
            ),
            "balance_after": _safe_float(row.get("balance", row.get("余额(元)", 0))),
            "channel": _safe_text(
                row.get("transaction_channel", row.get("交易渠道", ""))
            ),
        },
    }


def detect_holiday_transactions(cleaned_data: Dict[str, pd.DataFrame]) -> Dict[str, List[Dict]]:
    """
    检测节假日及临近窗口（节前/节中/节后）的大额交易。

    使用原始数据可覆盖的最小/最大日期构建完整检测窗口，确保时间跨度内的传统节假日
    都会被纳入审计范围。
    """
    all_dates: List[pd.Timestamp] = []
    for df in cleaned_data.values():
        if df is None or df.empty or "date" not in df.columns:
            continue

        parsed_dates = utils.normalize_datetime_series(df["date"]).dropna()
        if not parsed_dates.empty:
            all_dates.extend(parsed_dates.tolist())

    if not all_dates:
        return {}

    start_date = min(all_dates).date()
    end_date = max(all_dates).date()
    holiday_config = getattr(config, "HOLIDAY_DETECTION_CONFIG", {}) or {}
    days_before = int(holiday_config.get("days_before", 3))
    days_after = int(holiday_config.get("days_after", 2))
    amount_threshold = float(getattr(config, "HOLIDAY_LARGE_AMOUNT_THRESHOLD", 50000))
    holiday_window = build_holiday_window(
        start_date,
        end_date,
        days_before=days_before,
        days_after=days_after,
    )

    if not holiday_window:
        return {}

    results: Dict[str, List[Dict]] = {}

    for entity_name, df in cleaned_data.items():
        if df is None or df.empty or "date" not in df.columns:
            continue

        working_df = df.copy()
        working_df["_parsed_date"] = utils.normalize_datetime_series(working_df["date"])
        working_df = working_df.dropna(subset=["_parsed_date"])
        if working_df.empty:
            continue

        entity_records: List[Dict] = []
        for _, row in working_df.iterrows():
            tx_date = row["_parsed_date"].date()
            holiday_info = holiday_window.get(tx_date)
            if not holiday_info:
                continue

            amount = _extract_tx_amount(row)
            if amount < amount_threshold:
                continue

            holiday_name, holiday_period = holiday_info
            evidence_refs = {
                "source_row_index": int(row.get("source_row_index", row.name))
                if row.get("source_row_index") is not None
                else int(row.name) + 2,
                "transaction_id": _safe_text(row.get("transaction_id", "")),
            }

            entity_records.append(
                {
                    "date": row["_parsed_date"],
                    "amount": amount,
                    "description": _safe_text(
                        row.get("description", row.get("交易摘要", ""))
                    ),
                    "counterparty": _safe_text(
                        row.get("counterparty", row.get("交易对手", ""))
                    ),
                    "holiday_name": holiday_name,
                    "holiday_period": holiday_period,
                    "direction": _extract_tx_direction(row),
                    "bank": _safe_text(row.get("银行来源", row.get("bank", ""))),
                    "source_file": _safe_text(
                        row.get("数据来源", row.get("source_file", ""))
                    ),
                    "risk_level": "high"
                    if holiday_period == "before" or amount >= amount_threshold * 2
                    else "medium",
                    "risk_reason": (
                        f"交易发生在{holiday_name}"
                        f"{'节前' if holiday_period == 'before' else '节中' if holiday_period == 'during' else '节后'}"
                        "敏感窗口，且金额达到大额阈值"
                    ),
                    "evidence_refs": evidence_refs,
                }
            )

        if entity_records:
            entity_records.sort(key=lambda item: (item["date"], -item["amount"]))
            results[entity_name] = entity_records

    return results


def detect_cash_time_collision(
    withdrawals: pd.DataFrame, deposits: pd.DataFrame, entity_name: str
) -> List[Dict]:
    """
    检测现金时空伴随（Pandas 优化版）

    使用 Pandas 合并操作代替嵌套循环，大幅提升大数据量下的性能。
    输出字段已适配 report_generator.py 的需求。

    Args:
        withdrawals: 取现交易 DataFrame (必须包含 date, amount 等列)
        deposits: 存现交易 DataFrame (必须包含 date, amount 等列)
        entity_name: 当前账户持有人名称

    Returns:
        检测到的伴随交易列表
    """
    collisions = []

    if withdrawals.empty or deposits.empty:
        return collisions

    wd = withdrawals.copy()
    dp = deposits.copy()
    if "amount" in wd.columns:
        wd["amount"] = utils.normalize_amount_series(wd["amount"], "amount")
    if "amount" in dp.columns:
        dp["amount"] = utils.normalize_amount_series(dp["amount"], "amount")

    wd = utils.sort_transactions_strict(wd, date_col="date", dropna_date=True)
    dp = utils.sort_transactions_strict(dp, date_col="date", dropna_date=True)
    if wd.empty or dp.empty:
        return collisions

    wd_dates_ns = wd["date"].astype("int64").to_numpy()
    used_withdrawal_indices = set()

    for _, deposit_row in dp.iterrows():
        deposit_date = deposit_row["date"]
        deposit_amount = float(deposit_row.get("amount", 0) or 0)
        if deposit_amount <= 0:
            continue

        min_date = deposit_date - pd.Timedelta(hours=config.CASH_TIME_WINDOW_HOURS)
        left_idx = np.searchsorted(wd_dates_ns, min_date.value, side="left")
        right_idx = np.searchsorted(wd_dates_ns, deposit_date.value, side="right")
        if left_idx >= right_idx:
            continue

        candidates = wd.iloc[left_idx:right_idx].copy()
        if used_withdrawal_indices:
            candidates = candidates[~candidates.index.isin(used_withdrawal_indices)]
        if candidates.empty:
            continue

        candidates["hours_diff"] = (
            (deposit_date - candidates["date"]).dt.total_seconds() / 3600
        )
        candidates["amount_diff_abs"] = (candidates["amount"] - deposit_amount).abs()
        candidates["amount_ratio"] = np.where(
            candidates["amount"] > 0,
            candidates["amount_diff_abs"] / candidates["amount"],
            1.0,
        )
        candidates = candidates[candidates["amount_ratio"] <= config.AMOUNT_TOLERANCE_RATIO]
        if candidates.empty:
            continue

        best_match = candidates.sort_values(
            ["amount_ratio", "hours_diff", "_strict_source_row", "_strict_transaction_id"],
            kind="mergesort",
        ).iloc[0]
        used_withdrawal_indices.add(int(best_match.name))

        withdrawal_amount = float(best_match.get("amount", 0) or 0)
        amount_diff = abs(withdrawal_amount - deposit_amount)
        amount_ratio = amount_diff / withdrawal_amount if withdrawal_amount > 0 else 1.0
        hours_diff = float(best_match["hours_diff"])

        collisions.append(
            {
                "type": "single_entity",
                "pattern_category": "self_cycle",
                "withdrawal_entity": entity_name,
                "deposit_entity": entity_name,
                "withdrawal_date": best_match["date"],
                "deposit_date": deposit_date,
                "withdrawal_bank": best_match.get("银行来源", best_match.get("bank", "未知")),
                "deposit_bank": deposit_row.get("银行来源", deposit_row.get("bank", "未知")),
                "withdrawal_source": best_match.get("数据来源", best_match.get("source_file", "未知")),
                "deposit_source": deposit_row.get("数据来源", deposit_row.get("source_file", "未知")),
                "time_diff_hours": round(hours_diff, 2),
                "withdrawal_amount": withdrawal_amount,
                "deposit_amount": deposit_amount,
                "amount_diff": round(amount_diff, 2),
                "amount_diff_ratio": round(amount_ratio, 2),
                "risk_level": "low",
                "risk_reason": (
                    f"[单实体线索] {entity_name}取现{withdrawal_amount}元后"
                    f"{hours_diff:.1f}小时存现{deposit_amount}元，金额接近；"
                    "默认仅作资金循环线索。"
                ),
            }
        )

    return collisions


def detect_cross_entity_cash_collision(
    all_withdrawals: List[Dict],
    all_deposits: List[Dict],
    time_window_hours: float = config.CASH_TIME_WINDOW_HOURS,
    amount_tolerance: float = config.AMOUNT_TOLERANCE_RATIO,
) -> List[Dict]:
    """
    跨实体现金碰撞检测 - 核心审计功能 - 向量化优化版

    【P1-性能9优化】使用Pandas merge替代O(n*m)双重循环，大幅提升性能

    检测不同人之间的现金取存时空伴随模式，这是识别洗钱、利益输送的关键手段。

    典型场景:
    - Person A 在 ATM 取现 5万
    - Person B 30分钟后在同一/附近 ATM 存入 5万

    Args:
        all_withdrawals: 所有实体的取现记录列表 [{entity, date, amount, bank, ...}, ...]
        all_deposits: 所有实体的存现记录列表 [{entity, date, amount, bank, ...}, ...]
        time_window_hours: 时间窗口（小时）
        amount_tolerance: 金额容差比例

    Returns:
        跨实体现金碰撞列表
    """
    collisions = []

    if not all_withdrawals or not all_deposits:
        return collisions

    # 【P1-性能9优化】使用基于时间窗口的join替代笛卡尔积，避免O(n*m)内存爆炸
    import pandas as pd

    wd_df = pd.DataFrame(all_withdrawals)
    dp_df = pd.DataFrame(all_deposits)

    if wd_df.empty or dp_df.empty:
        return collisions

    # 确保date列是datetime类型并排序（merge_asof要求）
    wd_df = utils.sort_transactions_strict(wd_df, date_col="date", dropna_date=True)
    dp_df = utils.sort_transactions_strict(dp_df, date_col="date", dropna_date=True)

    # 添加时间窗口边界列用于快速筛选
    dp_df["date_min"] = dp_df["date"] - pd.Timedelta(hours=time_window_hours)

    # 【性能优化核心】使用merge_asof + 时间窗口筛选，替代笛卡尔积
    # 1. 对每个存款，找到时间窗口内最近的取现
    # 2. 然后扩展查找所有在时间窗口内的取现记录

    # 方法：按金额分组，减少比较范围（金额相似度预筛选）
    # 创建金额桶用于初步分组
    amount_bucket_size = 5000  # 5万元一个桶
    wd_df["amount_bucket"] = (wd_df["amount"] / amount_bucket_size).astype(int)
    dp_df["amount_bucket"] = (dp_df["amount"] / amount_bucket_size).astype(int)

    # 只比较金额桶相同或相邻的记录
    collision_records = []

    # 获取所有可能的金额桶
    all_buckets = set(wd_df["amount_bucket"].unique()) | set(
        dp_df["amount_bucket"].unique()
    )

    for bucket in all_buckets:
        # 获取当前桶及其相邻桶的数据
        bucket_range = [bucket - 1, bucket, bucket + 1]
        wd_bucket = wd_df[wd_df["amount_bucket"].isin(bucket_range)].copy()
        dp_bucket = dp_df[dp_df["amount_bucket"] == bucket].copy()

        if wd_bucket.empty or dp_bucket.empty:
            continue

        # 使用merge_asof进行基于时间的最近邻匹配（避免了笛卡尔积）
        # 找到每个存款在时间窗口内的潜在匹配
        dp_bucket = dp_bucket.sort_values("date")
        wd_bucket = wd_bucket.sort_values("date")

        # 对每个存款，找到所有在时间窗口内的取现（使用searchsorted）
        # 将datetime64转换为int64用于numpy的二分查找
        wd_dates_ns = wd_bucket["date"].astype(np.int64).values

        for _, dp_row in dp_bucket.iterrows():
            dp_date = dp_row["date"]
            dp_amount = dp_row["amount"]
            dp_entity = dp_row["entity"]

            # 使用二分查找找到时间窗口内的取现记录索引范围
            min_date = dp_date - pd.Timedelta(hours=time_window_hours)

            # 转换为int64进行比较
            dp_date_ns = dp_date.value
            min_date_ns = min_date.value

            # 找到时间范围内的所有取现索引
            left_idx = np.searchsorted(wd_dates_ns, min_date_ns, side="left")
            right_idx = np.searchsorted(wd_dates_ns, dp_date_ns, side="right")

            if left_idx >= right_idx:
                continue

            # 获取候选取现记录
            candidates = wd_bucket.iloc[left_idx:right_idx].copy()

            # 排除同一实体
            candidates = candidates[candidates["entity"] != dp_entity]

            if candidates.empty:
                continue

            # 计算金额匹配度
            candidates["amount_diff_abs"] = (candidates["amount"] - dp_amount).abs()
            candidates["amount_ratio"] = (
                candidates["amount_diff_abs"] / candidates["amount"]
            )

            # 筛选金额匹配的记录
            matches = candidates[candidates["amount_ratio"] <= amount_tolerance]

            for _, wd_row in matches.iterrows():
                time_diff = (dp_date - wd_row["date"]).total_seconds() / 3600

                # 风险等级判断
                if time_diff < 2 and wd_row["amount_ratio"] < 0.01:
                    risk, risk_desc = "high", "极高相关性"
                elif time_diff < 12 and wd_row["amount_ratio"] < 0.05:
                    risk, risk_desc = "high", "高度可疑"
                elif time_diff < 24:
                    risk, risk_desc = "medium", "需进一步核查"
                else:
                    risk, risk_desc = "low", "可能巧合"

                collision_records.append(
                    {
                        "withdrawal_entity": wd_row["entity"],
                        "deposit_entity": dp_entity,
                        "withdrawal_date": wd_row["date"],
                        "deposit_date": dp_date,
                        "withdrawal_amount": wd_row["amount"],
                        "deposit_amount": dp_amount,
                        "withdrawal_bank": wd_row.get("bank", "未知"),
                        "deposit_bank": dp_row.get("bank", "未知"),
                        "withdrawal_source": wd_row.get("source_file", ""),
                        "deposit_source": dp_row.get("source_file", ""),
                        "withdrawal_row": wd_row.get("source_row_index", None),
                        "deposit_row": dp_row.get("source_row_index", None),
                        "time_diff_hours": round(time_diff, 2),
                        "amount_diff": round(wd_row["amount_diff_abs"], 2),
                        "amount_diff_ratio": round(wd_row["amount_ratio"], 4),
                        "risk_level": risk,
                        "risk_reason": f"[跨实体] {wd_row['entity']}取现{wd_row['amount'] / 10000:.2f}万 → "
                        f"{dp_entity}存现{dp_amount / 10000:.2f}万, "
                        f"时差{time_diff:.1f}小时, {risk_desc}",
                    }
                )

    return collision_records


def run_all_detections(
    cleaned_data: Dict, all_persons: List[str], all_companies: List[str]
) -> Dict:
    """
    运行所有疑点检测的主入口

    Args:
        cleaned_data: 清洗后的交易数据 {entity_name: DataFrame}
        all_persons: 所有核心人员名单
        all_companies: 所有涉案公司名单

    Returns:
        包含所有检测结果的字典
    """
    logger.info("开始执行疑点检测...")

    results = {
        "direct_transfers": [],  # 直接资金往来
        "cash_collisions": [],  # 现金时空伴随
        "hidden_assets": {},  # 隐形资产
        "fixed_frequency": {},  # 固定频率异常
        "cash_timing_patterns": [],  # 现金时间点配对
        "holiday_transactions": {},  # 节假日/特殊时段
        "amount_patterns": {},  # 金额模式异常
    }

    # ============================
    # 1. 现金时空伴随检测
    # ============================
    logger.info("  -> 正在检测现金时空伴随...")

    # 【铁律修复】现金交易识别：直接读取 cleaned_data 中已标记的 is_cash / 现金 列
    # 不再重复用关键词匹配，复用 data_cleaner 的计算结果
    def get_cash_transactions(df: pd.DataFrame) -> pd.DataFrame:
        """
        从 DataFrame 中提取现金交易记录

        优先级：
        1. is_cash 列（布尔类型，data_cleaner 内存中的格式）
        2. 现金 列（字符串 '是'，从 Excel 读取时的格式）
        3. 降级：如果都没有，使用关键词匹配（最后手段）
        """
        if "is_cash" in df.columns:
            # 直接使用已计算的布尔列
            return df[df["is_cash"] == True].copy()
        elif "现金" in df.columns:
            # 从 Excel 读取时，现金列是字符串 '是' 或 ''
            return df[df["现金"] == "是"].copy()
        else:
            # 降级：没有现金标记列，使用关键词匹配（兼容旧数据）
            logger.warning("  ⚠️ 未找到现金标记列，降级为关键词匹配")

            def is_cash_by_keyword(row):
                desc = str(row.get("description", "")).lower()
                for kw in config.CASH_KEYWORDS:
                    if kw in desc:
                        return True
                return False

            return df[df.apply(is_cash_by_keyword, axis=1)].copy()

    # 收集所有实体的取现和存现记录（用于跨实体检测）
    all_withdrawals = []
    all_deposits = []

    for entity_name, df in cleaned_data.items():
        if df.empty:
            continue

        # 【铁律】直接读取已标记的现金列
        cash_df = get_cash_transactions(df)
        if cash_df.empty:
            continue

        # 拆分为取现和存现
        # 注意：根据实际列名调整，这里假设 amount 为正数，或者分列 income/expense
        # 如果是单列 amount，正负表示方向；如果是双列，income表示进，expense表示出

        # 列名映射（中文列名兼容）
        # 将收入(元) -> income，支出(元) -> expense，以兼容后续统一处理
        if "收入(元)" in cash_df.columns or "支出(元)" in cash_df.columns:
            cash_df = cash_df.rename(
                columns={
                    "收入(元)": "income",
                    "支出(元)": "expense",
                }
            )

        # 策略：如果有 income/expense 列
        if "income" in cash_df.columns and "expense" in cash_df.columns:
            withdrawals = cash_df[cash_df["expense"].fillna(0) > 0].copy()
            deposits = cash_df[cash_df["income"].fillna(0) > 0].copy()
            # 标准化金额列为 amount
            withdrawals["amount"] = withdrawals["expense"]
            deposits["amount"] = deposits["income"]
        else:
            # 只有单列 amount 的情况（假设负数为支出）
            withdrawals = cash_df[cash_df["amount"] < 0].copy()
            deposits = cash_df[cash_df["amount"] > 0].copy()
            withdrawals["amount"] = withdrawals["amount"].abs()
            deposits["amount"] = deposits["amount"]

        # 执行单实体内检测（线索化，不计入 cash_collisions 风险主清单）
        self_cycles = detect_cash_time_collision(withdrawals, deposits, entity_name)
        if self_cycles:
            logger.info(
                f"    [{entity_name}] 发现 {len(self_cycles)} 处现金循环线索(单实体)"
            )
            results["cash_timing_patterns"].extend(self_cycles)

        # 收集取现和存现记录用于跨实体检测
        for _, row in withdrawals.iterrows():
            bank_val = row.get("银行来源", row.get("bank", ""))
            source_val = row.get("数据来源", row.get("source_file", ""))
            all_withdrawals.append(
                {
                    "entity": entity_name,
                    "date": row["date"],
                    "amount": row["amount"],
                    "bank": str(bank_val)
                    if bank_val and str(bank_val) != "nan"
                    else "",
                    "source_file": str(source_val)
                    if source_val and str(source_val) != "nan"
                    else "",
                    "description": row.get("description", ""),
                    # 【审计溯源】添加原始行号
                    "source_row_index": row.get("source_row_index", None),
                }
            )

        for _, row in deposits.iterrows():
            bank_val = row.get("银行来源", row.get("bank", ""))
            source_val = row.get("数据来源", row.get("source_file", ""))
            all_deposits.append(
                {
                    "entity": entity_name,
                    "date": row["date"],
                    "amount": row["amount"],
                    "bank": str(bank_val)
                    if bank_val and str(bank_val) != "nan"
                    else "",
                    "source_file": str(source_val)
                    if source_val and str(source_val) != "nan"
                    else "",
                    "description": row.get("description", ""),
                    # 【审计溯源】添加原始行号
                    "source_row_index": row.get("source_row_index", None),
                }
            )

    # ============================
    # 1.1 跨实体现金碰撞检测（核心审计功能）
    # ============================
    if all_withdrawals and all_deposits:
        logger.info("  -> 正在检测跨实体现金碰撞（洗钱模式识别）...")
        cross_collisions = detect_cross_entity_cash_collision(
            all_withdrawals, all_deposits
        )

        if cross_collisions:
            logger.info(f"    发现 {len(cross_collisions)} 处跨实体现金碰撞")
            results["cash_collisions"].extend(cross_collisions)

    # ============================
    # 2. 直接资金往来检测 (修复：适配 report_generator 需求)
    # ============================
    logger.info("  -> 正在分析直接资金往来...")
    seen_direct_transfers: Dict[
        Tuple[str, str, str, float, str, str], Dict
    ] = {}
    direct_transfer_roles: Dict[Tuple[str, str, str, float, str, str], str] = {}
    direct_transfer_order: List[Tuple[str, str, str, float, str, str]] = []

    # 检测核心人员与涉案公司之间的直接资金往来
    for person in all_persons:
        for company in all_companies:
            if person in cleaned_data and company in cleaned_data:
                # 个人账户视角
                df_person = cleaned_data[person]
                counterparty_col = (
                    "交易对手" if "交易对手" in df_person.columns else "counterparty"
                )
                transfers_out = df_person[
                    df_person[counterparty_col].astype(str).str.contains(
                        re.escape(company), na=False, regex=True
                    )
                ]
                if not transfers_out.empty:
                    for _, row in transfers_out.iterrows():
                        record = _build_direct_transfer_record(
                            row, person, company, "person"
                        )
                        if not record:
                            continue
                        dedupe_key = build_direct_transfer_dedupe_key(
                            person,
                            company,
                            record["direction"],
                            record["amount"],
                            _safe_text(record.get("date")),
                            record.get("description", ""),
                            record.get("bank", ""),
                        )
                        existing = seen_direct_transfers.get(dedupe_key)
                        if existing is None:
                            seen_direct_transfers[dedupe_key] = record
                            direct_transfer_roles[dedupe_key] = "person"
                            direct_transfer_order.append(dedupe_key)
                            continue

                        if score_direct_transfer_record(
                            record,
                            person=person,
                            company=company,
                            account_role="person",
                        ) > score_direct_transfer_record(
                            existing,
                            person=person,
                            company=company,
                            account_role=direct_transfer_roles.get(dedupe_key, ""),
                        ):
                            seen_direct_transfers[dedupe_key] = record
                            direct_transfer_roles[dedupe_key] = "person"

                # 公司账户视角
                df_company = cleaned_data[company]
                company_counterparty_col = (
                    "交易对手" if "交易对手" in df_company.columns else "counterparty"
                )
                transfers_in = df_company[
                    df_company[company_counterparty_col].astype(str).str.contains(
                        re.escape(person), na=False, regex=True
                    )
                ]
                if not transfers_in.empty:
                    for _, row in transfers_in.iterrows():
                        record = _build_direct_transfer_record(
                            row, person, company, "company"
                        )
                        if not record:
                            continue
                        dedupe_key = build_direct_transfer_dedupe_key(
                            person,
                            company,
                            record["direction"],
                            record["amount"],
                            _safe_text(record.get("date")),
                            record.get("description", ""),
                            record.get("bank", ""),
                        )
                        existing = seen_direct_transfers.get(dedupe_key)
                        if existing is None:
                            seen_direct_transfers[dedupe_key] = record
                            direct_transfer_roles[dedupe_key] = "company"
                            direct_transfer_order.append(dedupe_key)
                            continue

                        if score_direct_transfer_record(
                            record,
                            person=person,
                            company=company,
                            account_role="company",
                        ) > score_direct_transfer_record(
                            existing,
                            person=person,
                            company=company,
                            account_role=direct_transfer_roles.get(dedupe_key, ""),
                        ):
                            seen_direct_transfers[dedupe_key] = record
                            direct_transfer_roles[dedupe_key] = "company"

    results["direct_transfers"] = [
        seen_direct_transfers[key] for key in direct_transfer_order
    ]

    # ============================
    # 3. 节假日/特殊时段大额交易检测
    # ============================
    logger.info("  -> 正在检测节假日/特殊时段大额交易...")
    results["holiday_transactions"] = detect_holiday_transactions(cleaned_data)
    holiday_tx_count = sum(
        len(records) for records in results["holiday_transactions"].values()
    )
    if holiday_tx_count:
        logger.info(f"    发现 {holiday_tx_count} 笔节假日/特殊时段大额交易")

    # ============================
    # 4. 预留检测模块 (待后续实现)
    # ============================
    # fixed_frequency: 固定频率异常检测 (参考 config.FIXED_FREQUENCY_* 常量)

    total_found = (
        len(results["cash_collisions"])
        + len(results["direct_transfers"])
        + holiday_tx_count
    )
    logger.info(f"✓ 疑点检测完成，共发现 {total_found} 条有效线索")

    return results
