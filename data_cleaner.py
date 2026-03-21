#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据清洗模块 - 资金穿透与关联排查系统
负责数据去重、验证和标准化
"""

import json
import os
import re
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import config
import utils

logger = utils.setup_logger(__name__)

INVALID_TRANSACTION_STATUS_KEYWORDS = (
    "失败",
    "冲正",
    "冲销",
    "退汇",
    "撤销",
    "撤回",
    "作废",
    "关闭",
    "取消",
    "拒绝",
    "未完成",
    "回退",
)

def _normalize_column_token(column_name: str) -> str:
    """标准化列名文本，便于做模糊匹配。"""
    if not column_name:
        return ""
    token = str(column_name).strip().lower()
    token = token.replace("（", "(").replace("）", ")")
    token = re.sub(r"\s+", "", token)
    token = re.sub(r"[(){}\[\]【】:_-]", "", token)
    token = token.replace("人民币", "").replace("rmb", "")
    return token


def _strip_amount_unit_tokens(token: str) -> str:
    normalized = token or ""
    for unit_text in ("亿元", "万元", "亿", "万", "元"):
        normalized = normalized.replace(unit_text, "")
    return normalized


def _find_first_matching_column(
    df: pd.DataFrame, candidates: List[str], is_amount_field: bool = False
) -> str:
    """在原始列中查找首个匹配列，兼容 `(万元)` 等单位后缀。"""
    if df is None or df.empty and not len(df.columns):
        return None

    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    normalized_candidates = []
    for candidate in candidates:
        token = _normalize_column_token(candidate)
        if is_amount_field:
            token = _strip_amount_unit_tokens(token)
        normalized_candidates.append(token)

    for column_name in df.columns:
        column_token = _normalize_column_token(column_name)
        compare_token = (
            _strip_amount_unit_tokens(column_token) if is_amount_field else column_token
        )
        if compare_token in normalized_candidates:
            return column_name
    return None


def _get_amount_unit_hint_multiplier(column_name: str) -> float:
    token = _normalize_column_token(column_name)
    if "亿元" in token or token.endswith("亿"):
        return 100000000.0
    if "万元" in token or token.endswith("万"):
        return 10000.0
    return 1.0


def _normalize_amount_series(series: pd.Series, column_name: str) -> pd.Series:
    """将原始金额列统一换算到元，并量化到分。"""
    multiplier = _get_amount_unit_hint_multiplier(column_name)
    return series.apply(
        lambda value: utils.format_amount(value, unit_hint_multiplier=multiplier)
    )


def _normalize_optional_text_series(series: pd.Series) -> pd.Series:
    """统一处理可能为 Categorical 的文本列。"""
    return series.astype("string").fillna("").str.strip()


def _clean_optional_text_series(series: pd.Series) -> pd.Series:
    """统一处理可选文本列并复用现有文本清洗逻辑。"""
    return _normalize_optional_text_series(series).apply(utils.clean_text)


def _read_transaction_file(filepath: str) -> pd.DataFrame:
    """安全读取 Excel/CSV，避免因编码差异直接中断整个清洗流程。"""
    extension = os.path.splitext(filepath)[1].lower()
    if extension == ".csv":
        last_error = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            try:
                return pd.read_csv(filepath, encoding=encoding, dtype=str)
            except UnicodeDecodeError as exc:
                last_error = exc
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
    return pd.read_excel(filepath, dtype=str)


def _looks_like_company_entity(entity_name: str) -> bool:
    """根据实体名做轻量公司识别（用于清洗阶段口径修正）。"""
    if not entity_name:
        return False
    name = str(entity_name)
    company_keywords = [
        "公司",
        "有限",
        "集团",
        "企业",
        "科技",
        "投资",
        "贸易",
        "实业",
        "中心",
        "研究所",
    ]
    return any(kw in name for kw in company_keywords)


def _normalize_income_expense_signs(
    income_series: pd.Series, expense_series: pd.Series
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    统一收支符号语义：
    - income >= 0
    - expense >= 0
    负值按方向翻转到对侧字段，避免后续汇总/规则口径混乱。
    """
    income = pd.to_numeric(income_series, errors="coerce").fillna(0.0).round(2)
    expense = pd.to_numeric(expense_series, errors="coerce").fillna(0.0).round(2)

    neg_income = income < 0
    neg_expense = expense < 0

    normalized_income = income.clip(lower=0) + (-expense.where(neg_expense, 0.0))
    normalized_expense = expense.clip(lower=0) + (-income.where(neg_income, 0.0))
    corrected_mask = neg_income | neg_expense

    return normalized_income, normalized_expense, corrected_mask


def _build_dedup_direction_amount_keys(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """
    生成去重分组键：
    - direction_key: I(收入) / E(支出) / M(混合)
    - amount_key: 对应方向金额（混合时为收入+支出的绝对值和）
    """
    income_col = (
        pd.to_numeric(df["income"], errors="coerce")
        if "income" in df.columns
        else pd.Series(0.0, index=df.index)
    ).fillna(0.0)
    expense_col = (
        pd.to_numeric(df["expense"], errors="coerce")
        if "expense" in df.columns
        else pd.Series(0.0, index=df.index)
    ).fillna(0.0)

    income_abs = income_col.abs()
    expense_abs = expense_col.abs()

    is_income = (income_abs > 0) & (expense_abs <= 0)
    is_expense = (expense_abs > 0) & (income_abs <= 0)

    direction_key = pd.Series("M", index=df.index, dtype="object")
    direction_key.loc[is_income] = "I"
    direction_key.loc[is_expense] = "E"

    amount_key = income_abs + expense_abs
    amount_key.loc[is_income] = income_abs.loc[is_income]
    amount_key.loc[is_expense] = expense_abs.loc[is_expense]

    return direction_key, amount_key.round(2)


def _normalize_dedup_text(value: Any) -> str:
    """标准化启发式去重中的文本字段。"""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).replace("nan", "").strip()


def _normalize_dedup_channel(value: Any) -> str:
    channel = _normalize_dedup_text(value)
    return "" if channel in {"其他", "未知"} else channel


def _normalize_dedup_balance(value: Any) -> Optional[float]:
    try:
        balance = utils.format_amount(value)
    except Exception:
        return None
    # `balance` 缺失时通常会被标准化为 0；这里不把 0 当作强特征，避免误删。
    if balance <= 0:
        return None
    return round(balance, 2)


def _normalize_transaction_status_series(series: pd.Series) -> pd.Series:
    return (
        _normalize_optional_text_series(series)
        .str.replace(r"\s+", "", regex=True)
        .str.replace("（", "(")
        .str.replace("）", ")")
        .str.upper()
    )


def _build_invalid_transaction_status_mask(df: pd.DataFrame) -> pd.Series:
    if "transaction_status" not in df.columns:
        return pd.Series(False, index=df.index)

    normalized_status = _normalize_transaction_status_series(df["transaction_status"])
    if normalized_status.empty:
        return pd.Series(False, index=df.index)

    invalid_pattern = "|".join(
        re.escape(keyword.upper()) for keyword in INVALID_TRANSACTION_STATUS_KEYWORDS
    )
    return normalized_status.str.contains(invalid_pattern, na=False, regex=True)


def _collect_dedup_match_signals(
    current_row: pd.Series, next_row: pd.Series
) -> Tuple[bool, int, List[str], int, List[str]]:
    """收集启发式去重的弱/强匹配信号。"""
    weak_matches = 0
    weak_reasons: List[str] = []
    strong_matches = 0
    strong_reasons: List[str] = []

    current_counterparty = _normalize_dedup_text(current_row.get("_counterparty_clean", ""))
    next_counterparty = _normalize_dedup_text(next_row.get("_counterparty_clean", ""))
    if current_counterparty and next_counterparty:
        if current_counterparty != next_counterparty:
            return False, weak_matches, weak_reasons, strong_matches, strong_reasons
        weak_matches += 1
        weak_reasons.append("对手方")

    current_desc = _normalize_dedup_text(current_row.get("_description_clean", ""))
    next_desc = _normalize_dedup_text(next_row.get("_description_clean", ""))
    current_desc_prefix = _normalize_dedup_text(current_row.get("_description_prefix", ""))
    next_desc_prefix = _normalize_dedup_text(next_row.get("_description_prefix", ""))
    if current_desc and next_desc:
        if current_desc == next_desc:
            weak_matches += 1
            weak_reasons.append("摘要")
        elif current_desc_prefix and next_desc_prefix and current_desc_prefix == next_desc_prefix:
            strong_matches += 1
            strong_reasons.append("摘要前缀")
        else:
            return False, weak_matches, weak_reasons, strong_matches, strong_reasons

    text_feature_pairs = [
        ("账号", current_row.get("account_number", ""), next_row.get("account_number", "")),
        (
            "交易渠道",
            _normalize_dedup_channel(current_row.get("transaction_channel", "")),
            _normalize_dedup_channel(next_row.get("transaction_channel", "")),
        ),
    ]
    for feature_name, current_value, next_value in text_feature_pairs:
        normalized_current = _normalize_dedup_text(current_value)
        normalized_next = _normalize_dedup_text(next_value)
        if not normalized_current or not normalized_next:
            continue
        if normalized_current != normalized_next:
            return False, weak_matches, weak_reasons, strong_matches, strong_reasons
        strong_matches += 1
        strong_reasons.append(feature_name)

    current_balance = _normalize_dedup_balance(current_row.get("balance"))
    next_balance = _normalize_dedup_balance(next_row.get("balance"))
    if current_balance is not None and next_balance is not None:
        if current_balance != next_balance:
            return False, weak_matches, weak_reasons, strong_matches, strong_reasons
        strong_matches += 1
        strong_reasons.append("余额")

    return True, weak_matches, weak_reasons, strong_matches, strong_reasons


def deduplicate_transactions(
    df: pd.DataFrame, output_dir: str = None
) -> Tuple[pd.DataFrame, Dict]:
    """
    智能去重交易记录

    Args:
        df: 交易DataFrame

    Returns:
        (去重后的DataFrame, 统计信息字典)
    """
    if df.empty:
        return df, {"original": 0, "duplicates": 0, "final": 0}

    df = df.copy()
    original_count = len(df)
    logger.info(f"开始去重,原始记录数: {original_count}")
    df["_original_order"] = range(original_count)

    # 排序以确保一致性
    df = df.sort_values("date").reset_index(drop=True)

    # 创建去重键 - 【P1修复】确保date列是datetime类型
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["_timestamp"] = df["date"].astype("int64") // 10**9  # 转为秒级时间戳
    df["_direction_key"], df["_amount_rounded"] = _build_dedup_direction_amount_keys(df)

    # DEBUG: 打印前几行数据，检查是否有大量重复值
    if len(df) > 0:
        logger.debug(f"去重前数据采样 (Top 5):")
        for i in range(min(5, len(df))):
            row = df.iloc[i]
            tx_id = row.get("transaction_id", "N/A")
            ts = row.get("_timestamp", "N/A")
            direction = row.get("_direction_key", "N/A")
            amt = row.get("_amount_rounded", "N/A")
            logger.debug(f"  Row {i}: ID={tx_id}, Time={ts}, Dir={direction}, Amt={amt}")

    # 标记潜在重复组
    # 同一账号、相近时间(容差范围内)、相同金额的交易可能是重复
    duplicates_mask = pd.Series(False, index=df.index)
    dedup_details = []  # 记录去重详情
    tx_id_duplicates_removed = 0

    # ====================================================================
    # 【P0 修复 - 2026-01-18】恢复流水号去重
    # 审计原则：交易流水号是银行出具的唯一电子凭证，不同流水号的交易不应被删除
    # ====================================================================

    # 第一步：基于流水号去重（逐行启用，不再要求整表覆盖率超过 50%）
    if "transaction_id" in df.columns:
        # 流水号可用：完全相同的流水号才视为重复
        tx_id_col = _normalize_optional_text_series(df["transaction_id"])
        # 保留原始非空流水号口径；建行等银行会用 "-" 作为占位流水号。
        valid_tx_ids = ~tx_id_col.isin(["", "nan", "None", "N/A"])

        # 对有有效流水号的记录：按来源文件 + 流水号挑选主交易
        if valid_tx_ids.any():
            df_with_tx_id = df[valid_tx_ids].copy()
            df_without_tx_id = df[~valid_tx_ids].copy()
            df_with_tx_id["transaction_id"] = tx_id_col.loc[valid_tx_ids]

            source_col = "数据来源" if "数据来源" in df_with_tx_id.columns else "__txid_source"
            if source_col == "__txid_source":
                df_with_tx_id[source_col] = ""

            original_with_tx_id = len(df_with_tx_id)
            df_with_tx_id = df_with_tx_id.sort_values(
                [source_col, "_original_order"], kind="mergesort"
            )
            df_with_tx_id_dedup = df_with_tx_id.drop_duplicates(
                subset=[source_col, "transaction_id"], keep="first"
            )
            tx_id_dups_removed = original_with_tx_id - len(df_with_tx_id_dedup)
            tx_id_duplicates_removed += tx_id_dups_removed
            if source_col == "__txid_source":
                df_with_tx_id_dedup = df_with_tx_id_dedup.drop(
                    [source_col], axis=1, errors="ignore"
                )

            if tx_id_dups_removed > 0:
                logger.info(f"基于流水号去重: 移除 {tx_id_dups_removed} 条完全重复记录")

            # 合并回来，继续处理无流水号的部分
            concat_frames = []
            if not df_with_tx_id_dedup.empty:
                concat_frames.append(df_with_tx_id_dedup)
            if not df_without_tx_id.empty:
                concat_frames.append(df_without_tx_id)
            df = (
                pd.concat(concat_frames, ignore_index=True)
                if concat_frames
                else df.iloc[0:0].copy()
            )
            # 【P1-异常4修复】添加空DataFrame检查
            if df.empty:
                return df, {"original": 0, "duplicates": 0, "final": 0}
            df = df.sort_values("date").reset_index(drop=True)
            # 重新计算临时列
            df["_timestamp"] = df["date"].astype("int64") // 10**9
            df["_direction_key"], df["_amount_rounded"] = _build_dedup_direction_amount_keys(df)
        else:
            logger.info("流水号字段存在但均无效，将使用启发式去重")
    else:
        logger.info("无可靠流水号字段，将使用启发式去重")

    # 【P1-性能修复-2026-03-01】向量化去重，避免O(n²)双重循环
    duplicates_mask = pd.Series(False, index=df.index)
    dedup_details = []

    # 创建辅助列用于匹配
    df["_counterparty_clean"] = _normalize_optional_text_series(df["counterparty"])
    df["_description_clean"] = _normalize_optional_text_series(df["description"])
    df["_description_prefix"] = df["_description_clean"].str[:10]

    # 无流水号的零金额信息行、模板空白行，只允许按精确自然键去重。
    # 这类记录常见于利息/回执/模板反馈，不能依赖启发式时间容差，否则会在逐户笔数上漂移。
    exact_zero_or_blank_duplicates_removed = 0
    if "transaction_id" in df.columns:
        tx_id_col = _normalize_optional_text_series(df["transaction_id"])
    else:
        tx_id_col = pd.Series("", index=df.index, dtype="string")

    exact_zero_or_blank_mask = tx_id_col.eq("") & (
        df["_amount_rounded"].eq(0)
        | (
            df["_counterparty_clean"].eq("")
            & df["_description_clean"].eq("")
        )
    )
    if exact_zero_or_blank_mask.any():
        exact_subset = ["_timestamp", "_direction_key", "_amount_rounded"]
        source_col = "数据来源" if "数据来源" in df.columns else None
        if source_col:
            exact_subset.insert(0, source_col)
        exact_subset.extend(["_counterparty_clean", "_description_clean"])
        if "account_number" in df.columns:
            exact_subset.append("account_number")

        zero_or_blank_rows = df[exact_zero_or_blank_mask].sort_values(
            "_original_order", kind="mergesort"
        )
        zero_or_blank_rows_dedup = zero_or_blank_rows.drop_duplicates(
            subset=exact_subset, keep="first"
        )
        exact_zero_or_blank_duplicates_removed = (
            len(zero_or_blank_rows) - len(zero_or_blank_rows_dedup)
        )

        if exact_zero_or_blank_duplicates_removed > 0:
            logger.info(
                "基于精确自然键去重: 移除 %s 条无流水号零金额/模板重复记录",
                exact_zero_or_blank_duplicates_removed,
            )
            df = pd.concat(
                [df[~exact_zero_or_blank_mask], zero_or_blank_rows_dedup],
                ignore_index=True,
            ).sort_values("date").reset_index(drop=True)

    duplicates_mask = pd.Series(False, index=df.index)

    # 按金额分组进行向量化去重（金额相同的记录才可能是重复）
    tolerance = config.DEDUP_TIME_TOLERANCE_SECONDS

    for (_, _), group in df.groupby(["_direction_key", "_amount_rounded"], dropna=False):
        if len(group) < 2:
            continue

        # 在相同金额组内，找出时间差在容差范围内的记录对
        group_indices = group.index.tolist()
        timestamps = group["_timestamp"].values

        # 使用向量化操作找出邻近记录
        for i in range(len(group_indices)):
            if duplicates_mask[group_indices[i]]:
                continue

            current_idx = group_indices[i]
            current_ts = timestamps[i]
            current_row = df.loc[current_idx]

            # 检查后续记录的时间差（向量化查找邻近记录）
            j = i + 1
            while j < len(group_indices) and (timestamps[j] - current_ts) <= tolerance:
                next_idx = group_indices[j]

                if not duplicates_mask[next_idx]:
                    next_row = df.loc[next_idx]

                    (
                        candidate_match,
                        weak_matches,
                        weak_reasons,
                        strong_matches,
                        strong_reasons,
                    ) = _collect_dedup_match_signals(current_row, next_row)

                    current_tx_id = _normalize_dedup_text(current_row.get("transaction_id", ""))
                    next_tx_id = _normalize_dedup_text(next_row.get("transaction_id", ""))
                    if current_tx_id and next_tx_id and current_tx_id != next_tx_id:
                        j += 1
                        continue

                    exact_timestamp_match = timestamps[j] == current_ts
                    has_balance_anchor = "余额" in strong_reasons

                    # 兼容旧规则的同时引入强特征兜底：
                    # 1) 对手方+摘要都匹配时，必须完全同一时间戳，避免误删同秒连续转账
                    # 2) 若余额一致，可作为稳定账务锚点，允许一秒内自动去重
                    # 3) 缺少余额锚点时，不再仅靠账号/渠道等弱锚点自动删账
                    should_dedup = candidate_match and (
                        (weak_matches >= 2 and exact_timestamp_match)
                        or (has_balance_anchor and weak_matches >= 1)
                        or (has_balance_anchor and weak_matches == 0 and strong_matches >= 2)
                    )

                    if should_dedup:
                        # 大额交易保护逻辑
                        current_amount = current_row["_amount_rounded"]
                        if current_amount >= config.ASSET_LARGE_AMOUNT_THRESHOLD:
                            has_tx_id = bool(current_tx_id and next_tx_id)
                            if has_tx_id:
                                if (
                                    not current_tx_id
                                    or not next_tx_id
                                    or current_tx_id != next_tx_id
                                ):
                                    j += 1
                                    continue
                            else:
                                logger.warning(
                                    f"发现疑似重复大额交易(¥{current_amount:.2f})，需人工复核，暂不自动去重"
                                )
                                j += 1
                                continue

                        duplicates_mask[next_idx] = True
                        dedup_details.append(
                            {
                                "原始行号": int(next_idx),
                                "日期": next_row.get("date"),
                                "方向": str(next_row.get("_direction_key", "M")),
                                "金额": utils.format_amount(next_row.get("_amount_rounded", 0)),
                                "对手方": str(next_row.get("counterparty", "")),
                                "摘要": str(next_row.get("description", ""))[:30],
                                "与行": int(current_idx),
                                "去重原因": "时间+金额相近，且匹配特征: "
                                + "、".join(weak_reasons + strong_reasons),
                            }
                        )

                j += 1

    # 清理辅助列
    df = df.drop(
        ["_counterparty_clean", "_description_clean", "_description_prefix"],
        axis=1,
        errors="ignore",
    )

    # 移除重复记录
    df_dedup = df[~duplicates_mask].copy()

    # 清理临时列
    df_dedup = df_dedup.drop(
        ["_timestamp", "_direction_key", "_amount_rounded", "_original_order"], axis=1
    )

    duplicate_count = (
        tx_id_duplicates_removed
        + exact_zero_or_blank_duplicates_removed
        + int(duplicates_mask.sum())
    )
    final_count = len(df_dedup)

    stats = {
        "original": original_count,
        "duplicates": duplicate_count,
        "final": final_count,
        "dedup_rate": f"{duplicate_count / original_count * 100:.2f}%"
        if original_count > 0
        else "0%",
        "dedup_details": dedup_details,  # 新增：去重详情
    }

    logger.info(
        f"去重完成: 原始{original_count}条, 去重{duplicate_count}条, "
        f"保留{final_count}条 (去重率: {stats['dedup_rate']})"
    )

    # 【2026-01-27 修复】持久化去重详情到 JSON 文件
    if output_dir and dedup_details:
        try:
            dedup_path = os.path.join(output_dir, "dedup_details.json")
            with open(dedup_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "stats": {
                            "original": original_count,
                            "duplicates": duplicate_count,
                            "final": final_count,
                            "dedup_rate": stats["dedup_rate"],
                        },
                        "details": dedup_details,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f"去重详情已保存: {dedup_path}")
        except Exception as e:
            logger.error(f"保存去重详情失败: {e}")

    return df_dedup, stats


def _build_missing_date_placeholder_mask(
    df: pd.DataFrame,
    income_col: pd.Series,
    expense_col: pd.Series,
) -> pd.Series:
    """识别无日期但应保留的查询反馈/信息型记录。"""
    total_amount = income_col.fillna(0) + expense_col.fillna(0)
    description_series = (
        _normalize_optional_text_series(df["description"])
        if "description" in df.columns
        else pd.Series("", index=df.index, dtype="string")
    )
    counterparty_series = (
        _normalize_optional_text_series(df["counterparty"])
        if "counterparty" in df.columns
        else pd.Series("", index=df.index, dtype="string")
    )
    account_series = (
        _normalize_optional_text_series(df["account_number"])
        if "account_number" in df.columns
        else pd.Series("", index=df.index, dtype="string")
    )
    tx_id_series = (
        _normalize_optional_text_series(df["transaction_id"])
        if "transaction_id" in df.columns
        else pd.Series("", index=df.index, dtype="string")
    )

    return (
        total_amount.eq(0)
        & description_series.eq("")
        & counterparty_series.eq("")
        & account_series.ne("")
        & tx_id_series.eq("")
    )


def validate_data_quality(
    df: pd.DataFrame, output_dir: str = None
) -> Tuple[pd.DataFrame, Dict]:
    """
    验证数据质量

    Args:
        df: 交易DataFrame

    Returns:
        (验证后的DataFrame, 质量报告字典)
    """
    logger.info("开始数据质量验证...")

    quality_report = {
        "total_rows": len(df),
        "invalid_rows": [],
        "warnings": [],
        "audit_alerts": {},
    }

    if df.empty:
        return df, quality_report

    valid_mask = pd.Series(True, index=df.index)
    income_col = (
        pd.to_numeric(df["income"], errors="coerce")
        if "income" in df.columns
        else pd.Series(0.0, index=df.index)
    )
    expense_col = (
        pd.to_numeric(df["expense"], errors="coerce")
        if "expense" in df.columns
        else pd.Series(0.0, index=df.index)
    )
    missing_date_placeholder_mask = _build_missing_date_placeholder_mask(
        df, income_col, expense_col
    )

    # 1. 检查必需字段
    if "date" not in df.columns or df["date"].isna().all():
        logger.error("缺少日期字段")
        quality_report["warnings"].append("缺少日期字段")
        if missing_date_placeholder_mask.any() and missing_date_placeholder_mask.all():
            retained_count = int(missing_date_placeholder_mask.sum())
            quality_report["warnings"].append(
                f"保留{retained_count}条无日期的信息型查询反馈记录，不纳入时序分析"
            )
            quality_report["audit_alerts"]["missing_date_placeholders"] = {
                "count": retained_count,
            }
            quality_report["valid_rows"] = retained_count
            quality_report["removed_rows"] = 0
            return df.copy(), quality_report

        quality_report["invalid_rows"] = df.index.tolist()
        quality_report["valid_rows"] = 0
        quality_report["removed_rows"] = len(df)
        return df.iloc[0:0].copy(), quality_report

    # 标记日期缺失的行
    invalid_date = df["date"].isna()
    if invalid_date.any():
        retained_missing_dates = invalid_date & missing_date_placeholder_mask
        removed_missing_dates = invalid_date & ~missing_date_placeholder_mask
        if removed_missing_dates.any():
            quality_report["invalid_rows"].extend(
                df[removed_missing_dates].index.tolist()
            )
            quality_report["warnings"].append(
                f"发现{int(removed_missing_dates.sum())}条记录日期缺失"
            )
            valid_mask &= ~removed_missing_dates
        if retained_missing_dates.any():
            retained_count = int(retained_missing_dates.sum())
            quality_report["warnings"].append(
                f"保留{retained_count}条无日期的信息型查询反馈记录，不纳入时序分析"
            )
            quality_report["audit_alerts"]["missing_date_placeholders"] = {
                "count": retained_count,
            }

    invalid_status = _build_invalid_transaction_status_mask(df)
    if invalid_status.any():
        invalid_status_count = int(invalid_status.sum())
        quality_report["invalid_rows"].extend(df[invalid_status].index.tolist())
        quality_report["warnings"].append(
            f"发现{invalid_status_count}条无效交易状态记录（失败/冲正/退汇/撤销等），已从主流水剔除"
        )
        quality_report["audit_alerts"]["invalid_transaction_status"] = {
            "count": invalid_status_count,
            "examples": (
                _normalize_transaction_status_series(
                    df.loc[invalid_status, "transaction_status"]
                )
                .drop_duplicates()
                .head(5)
                .tolist()
            ),
        }
        valid_mask &= ~invalid_status

    # 2. 检查金额逻辑
    # 【P1-异常3修复】添加列存在性检查，避免KeyError
    total_amount = income_col.fillna(0) + expense_col.fillna(0)

    # 金额异常检测
    zero_amount = total_amount == 0
    if zero_amount.any():
        quality_report["warnings"].append(f"发现{zero_amount.sum()}条零金额记录")

    # 金额超大检测
    large_amount = total_amount > config.MAX_AMOUNT_THRESHOLD
    if large_amount.any():
        quality_report["warnings"].append(
            f"发现{large_amount.sum()}条超大金额记录(>{utils.format_currency(config.MAX_AMOUNT_THRESHOLD)})"
        )

    # 3. 检查数据完整性
    description_series = (
        _normalize_optional_text_series(df["description"])
        if "description" in df.columns
        else pd.Series("", index=df.index, dtype="string")
    )
    empty_description = description_series == ""
    empty_description_count = int(empty_description.sum())
    if empty_description_count:
        empty_description_ratio = empty_description_count / len(df)
        quality_report["warnings"].append(
            f"{empty_description_count}条记录缺少摘要(占比{empty_description_ratio:.1%})"
        )
        if empty_description_count >= 3 or empty_description_ratio >= 0.2:
            quality_report["warnings"].append(
                f"异常空摘要：发现{empty_description_count}条摘要缺失，建议核查源文件摘要列映射或银行回单完整性"
            )
        quality_report["audit_alerts"]["empty_description"] = {
            "count": empty_description_count,
            "ratio": round(empty_description_ratio, 4),
        }

    # 4. 异常零余额提示（仅在余额列存在时启用，避免把缺字段默认值误报为异常）
    if "balance" in df.columns:
        balance_series = pd.to_numeric(df["balance"], errors="coerce")
        zero_balance = balance_series.fillna(0.0) == 0
        zero_balance_count = int(zero_balance.sum())
        if zero_balance_count:
            zero_balance_ratio = zero_balance_count / len(df)
            if zero_balance_count >= 3 or zero_balance_ratio >= 0.3:
                quality_report["warnings"].append(
                    f"异常零余额：发现{zero_balance_count}条余额为零记录(占比{zero_balance_ratio:.1%})，需核查是否为余额缺失或过桥资金清空"
                )
            quality_report["audit_alerts"]["zero_balance"] = {
                "count": zero_balance_count,
                "ratio": round(zero_balance_ratio, 4),
            }

    # 5. 异常重复日期段提示（同一时间戳重复 >= 3 次）
    repeated_date_counts = df.loc[valid_mask, "date"].value_counts()
    repeated_date_segments = repeated_date_counts[repeated_date_counts >= 3]
    if not repeated_date_segments.empty:
        repeated_segment_count = int(len(repeated_date_segments))
        max_repeat_count = int(repeated_date_segments.max())
        quality_report["warnings"].append(
            f"异常重复日期段：发现{repeated_segment_count}个同一时间戳重复段，最大重复{max_repeat_count}条，需核查批量导入或模板流水"
        )
        quality_report["audit_alerts"]["repeated_date_segments"] = {
            "segments": repeated_segment_count,
            "max_repeat_count": max_repeat_count,
        }

    # 移除无效行
    df_valid = df[valid_mask].copy()

    quality_report["valid_rows"] = len(df_valid)
    quality_report["removed_rows"] = len(df) - len(df_valid)

    logger.info(
        f"数据验证完成: 总计{len(df)}条, 有效{len(df_valid)}条, "
        f"移除{quality_report['removed_rows']}条"
    )

    # 【2026-01-27 修复】持久化质量报告到 JSON 文件
    if output_dir:
        try:
            quality_path = os.path.join(output_dir, "quality_report.json")
            with open(quality_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"timestamp": datetime.now().isoformat(), "report": quality_report},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f"质量报告已保存: {quality_path}")
        except Exception as e:
            logger.error(f"保存质量报告失败: {e}")

    if quality_report["warnings"]:
        for warning in quality_report["warnings"]:
            logger.warning(warning)

    return df_valid, quality_report


def standardize_bank_fields(
    df: pd.DataFrame, bank_name: str = None, entity_name: str = None
) -> pd.DataFrame:
    """
    标准化银行字段(增强版,支持真实银行数据格式)

    Args:
        df: 原始DataFrame
        bank_name: 银行名称(用于特殊处理)

    Returns:
        标准化后的DataFrame
    """
    logger.info(
        f"标准化银行字段,银行: {bank_name or '未知'}, 实体: {entity_name or '未知'}"
    )

    normalized = pd.DataFrame()
    is_company_entity = _looks_like_company_entity(entity_name)

    # 1. 日期字段 - 支持"交易时间"
    date_col = None
    date_col = _find_first_matching_column(
        df, config.BANK_FIELD_MAPPING.get("transaction_time", [])
    )

    if not date_col:
        # 回退到原有逻辑
        date_col = _find_first_matching_column(df, config.DATE_COLUMNS)

    if date_col:
        normalized["date"] = df[date_col].apply(utils.parse_date)
    else:
        logger.warning("未找到日期列")
        normalized["date"] = None

    # 2. 摘要字段 - 支持"交易摘要"
    desc_col = None
    desc_col = _find_first_matching_column(df, config.BANK_FIELD_MAPPING.get("summary", []))

    if desc_col:
        normalized["description"] = _clean_optional_text_series(df[desc_col])
    else:
        normalized["description"] = ""

    # 3. 金额字段 - 重要!需要处理借贷标志
    amount_col = None
    amount_col = _find_first_matching_column(
        df, config.BANK_FIELD_MAPPING.get("transaction_amount", []), is_amount_field=True
    )

    debit_credit_col = None
    debit_credit_col = _find_first_matching_column(
        df, config.BANK_FIELD_MAPPING.get("debit_credit_flag", [])
    )

    if amount_col and debit_credit_col:
        # 根据借贷标志分配收入/支出
        normalized["income"] = 0.0
        normalized["expense"] = 0.0

        # 向量化处理金额和借贷标志
        amounts = _normalize_amount_series(df[amount_col], amount_col)
        flags = _normalize_optional_text_series(df[debit_credit_col]).str.upper()

        # 定义收入/支出标志
        credit_flags = ["贷", "C", "CREDIT", "贷方", "进", "收"]
        debit_flags = ["借", "D", "DEBIT", "借方", "出", "支", "付"]
        income_keywords = ["存入", "转入", "收入", "工资"]

        # 布尔索引：贷方标志
        credit_mask = flags.isin(credit_flags)
        # 布尔索引：借方标志
        debit_mask = flags.isin(debit_flags)
        # 布尔索引：根据摘要推断收入
        desc_lower = (
            _normalize_optional_text_series(df[desc_col]).str.lower()
            if desc_col and desc_col in df.columns
            else pd.Series("", index=df.index, dtype="string")
        )
        inferred_income_mask = (
            ~credit_mask
            & ~debit_mask
            & desc_lower.apply(lambda d: any(kw in d for kw in income_keywords))
        )

        # 向量化赋值
        normalized["income"] = 0.0
        normalized["expense"] = 0.0
        normalized.loc[credit_mask, "income"] = amounts[credit_mask]
        normalized.loc[credit_mask, "expense"] = 0.0
        normalized.loc[debit_mask, "income"] = 0.0
        normalized.loc[debit_mask, "expense"] = amounts[debit_mask]
        normalized.loc[inferred_income_mask, "income"] = amounts[inferred_income_mask]
        normalized.loc[inferred_income_mask, "expense"] = 0.0

        # 无法识别借贷方向的记录保持为 0，避免把空标志/占位值粗暴记成支出。
        remaining_mask = ~credit_mask & ~debit_mask & ~inferred_income_mask
        unclassified_count = int(remaining_mask.sum())
        if unclassified_count > 0:
            logger.info(f"发现 {unclassified_count} 条借贷标志未识别记录，暂不自动计入收支")
    else:
        # 回退到原有逻辑
        logger.warning("未找到借贷标志,使用原有收支字段逻辑")
        income_col = None
        income_col = _find_first_matching_column(
            df, config.INCOME_COLUMNS, is_amount_field=True
        )

        expense_col = None
        expense_col = _find_first_matching_column(
            df, config.EXPENSE_COLUMNS, is_amount_field=True
        )

        if income_col:
            normalized["income"] = _normalize_amount_series(df[income_col], income_col)
        else:
            normalized["income"] = 0.0

        if expense_col:
            normalized["expense"] = _normalize_amount_series(df[expense_col], expense_col)
        else:
            normalized["expense"] = 0.0

    # 3.1 仅在退回到原始收支列时修正符号。
    # 对“金额列 + 借贷标志”场景，原始红字/冲回金额必须原样保留。
    if not (amount_col and debit_credit_col):
        normalized["income"], normalized["expense"], sign_fixed_mask = (
            _normalize_income_expense_signs(normalized["income"], normalized["expense"])
        )
        sign_fixed_count = int(sign_fixed_mask.sum())
        if sign_fixed_count > 0:
            logger.warning(f"检测到并修复 {sign_fixed_count} 条收支符号异常记录")

    # 4. 对手方字段 - 支持"交易对方名称"
    counterparty_col = None
    counterparty_col = _find_first_matching_column(
        df, config.BANK_FIELD_MAPPING.get("counterparty_name", [])
    )

    if counterparty_col:
        normalized["counterparty"] = _clean_optional_text_series(df[counterparty_col])
    else:
        normalized["counterparty"] = ""

    # 5. 余额字段 - 支持"交易余额"
    balance_col = None
    balance_col = _find_first_matching_column(
        df, config.BANK_FIELD_MAPPING.get("balance", []), is_amount_field=True
    )

    if balance_col:
        normalized["balance"] = _normalize_amount_series(df[balance_col], balance_col)
    else:
        normalized["balance"] = 0.0

    status_col = _find_first_matching_column(
        df, config.BANK_FIELD_MAPPING.get("transaction_status", [])
    )
    if status_col:
        normalized["transaction_status"] = _clean_optional_text_series(df[status_col])
    else:
        normalized["transaction_status"] = ""

    # 6. 现金标志
    # 6. 现金标志 (修正：仅识别物理现金)
    # 策略1：优先根据摘要关键词判断（最准确）
    is_cash_by_desc = normalized["description"].apply(
        lambda x: utils.contains_keywords(str(x), config.CASH_KEYWORDS)
    )

    # 策略2：检查银行现金标志列 (已禁用宽泛匹配)
    # 用户反馈：银行的"现金交易"标志包含了转账/POS等非物理现金操作
    # 因此，我们不再信任"现金交易"这个词。除非标志列明确包含"现钞"这种极强指示词。
    is_cash_by_flag = pd.Series(False, index=df.index)
    cash_col = None
    cash_col = _find_first_matching_column(df, config.BANK_FIELD_MAPPING.get("cash_flag", []))

    if cash_col:
        # 只匹配"现钞"、"ATM"。对于"现金"或"现金交易"这种宽泛词予以忽略
        def is_strict_physical_cash(val):
            s = str(val).strip().upper()
            # 排除'现金交易'，因为它通常指即时结算而非物理现金
            if "现金交易" in s:
                return False
            # 只有极强的物理特征才保留
            return "现钞" in s or "ATM" in s

        is_cash_by_flag = df[cash_col].apply(is_strict_physical_cash)

    normalized["is_cash"] = is_cash_by_desc | is_cash_by_flag

    # 7. 账号字段(用于去重)
    account_col = None
    account_col = _find_first_matching_column(
        df, config.BANK_FIELD_MAPPING.get("account_number", [])
    )

    if account_col:
        normalized["account_number"] = _normalize_optional_text_series(df[account_col])
    else:
        normalized["account_number"] = ""

    # ========== Phase 1: 账户类型识别 (2026-01-20 新增) ==========

    # 7.1 账户类型识别 (借记卡/信用卡/理财账户/证券账户)
    def classify_account_type(
        account_num: str, description: str, bank_name: str
    ) -> str:
        """
        识别账户类型

        Args:
            account_num: 账号
            description: 交易摘要
            bank_name: 银行名称

        Returns:
            账户类型: 借记卡/信用卡/理财账户/证券账户
        """
        account_str = str(account_num).strip()
        account_clean = account_str.replace(" ", "").replace("-", "")
        desc_str = str(description).upper()
        bank_str = str(bank_name).upper()

        # 1. 基于账号长度和特征判断
        account_len = len(account_clean)

        # 理财账户/证券账户特征
        if any(kw in desc_str for kw in ["理财", "基金", "证券", "股票", "债券"]):
            if any(kw in bank_str for kw in ["证券", "基金"]):
                return "证券账户"
            return "理财账户"

        # 对公结算账户常见特征（长度通常短于个人银行卡，且为纯数字）
        if account_clean.isdigit() and 9 <= account_len <= 15:
            return "对公结算账户"

        # 基于账号长度判断
        if 16 <= account_len <= 19:
            # 标准银行卡长度
            # 信用卡通常以特定数字开头
            if account_str.startswith(("4", "5", "6")):
                # 进一步通过摘要判断
                if any(
                    kw in desc_str
                    for kw in ["信用卡", "贷记卡", "CREDIT", "透支", "还款"]
                ):
                    return "信用卡"
                return "借记卡"
            return "借记卡"
        elif account_len < 16:
            if any(kw in desc_str for kw in ["证券", "股票"]):
                return "证券账户"
            return "其他"
        else:
            # 超长账号
            return "其他"

    # 7.2 账户类别识别 (个人/对公/联名)
    def classify_account_category(
        account_num: str, account_type: str, description: str
    ) -> str:
        """
        识别账户类别

        Args:
            account_num: 账号
            account_type: 已识别账户类型
            description: 交易摘要

        Returns:
            账户类别: 个人账户/对公账户/联名账户
        """
        desc_str = str(description).upper()
        account_type_str = str(account_type).strip()
        account_str = str(account_num).replace(" ", "").replace("-", "")

        # 联名账户特征
        if any(kw in desc_str for kw in ["联名", "共同", "夫妻"]):
            return "联名账户"

        # 公司实体兜底：公司主体清洗时默认按对公口径
        if is_company_entity:
            return "对公账户"

        # 账户类型已明确识别为对公结算账户，直接按对公口径
        if account_type_str == "对公结算账户":
            return "对公账户"

        # 仅接受能够直接描述“本方账户属性”的显式信号，不能再用对手方名称反推本方账户类别
        explicit_corporate_markers = [
            "对公账户",
            "对公账号",
            "单位结算账户",
            "公司结算账户",
            "单位账户",
        ]
        if any(kw in desc_str for kw in explicit_corporate_markers):
            return "对公账户"

        # 对公账号常见长度（各银行口径不一）
        if account_str.isdigit() and (9 <= len(account_str) <= 15 or len(account_str) > 19):
            return "对公账户"

        # 默认为个人账户
        return "个人账户"

    # 7.3 真实银行卡识别 (过滤基金/理财/证券账户)
    def is_real_bank_card(
        account_num: str,
        account_type: str,
        bank_name: str,
        account_category: str = "个人账户",
    ) -> bool:
        """
        判断是否为真实银行卡

        Args:
            account_num: 账号
            account_type: 账户类型
            bank_name: 银行名称

        Returns:
            是否为真实银行卡
        """
        account_str = str(account_num).strip()
        account_clean = account_str.replace(" ", "").replace("-", "")
        bank_str = str(bank_name).upper()

        # 排除条件1: 账户类型为理财或证券
        if account_type in ["理财账户", "证券账户"]:
            return False

        # 排除条件3: 银行名称包含基金/证券关键词
        if any(kw in bank_str for kw in ["基金", "证券", "资管", "信托"]):
            return False

        # 排除条件4: 账号包含特殊关键词
        if any(kw in account_str.upper() for kw in ["FUND", "SEC", "基金", "理财"]):
            return False

        account_len = len(account_clean)

        # 对公账户按对公结算账号口径识别
        if account_category == "对公账户":
            digit_count = sum(ch.isdigit() for ch in account_clean)
            if digit_count < 6:
                return False
            return 8 <= account_len <= 32

        # 个人银行卡按16-19位识别
        if account_len < 16 or account_len > 19:
            return False

        return True

    # 应用账户类型识别
    normalized["account_type"] = normalized.apply(
        lambda row: classify_account_type(
            row["account_number"],
            row["description"],
            row.get("银行来源", bank_name or ""),
        ),
        axis=1,
    )

    # 应用账户类别识别
    normalized["account_category"] = normalized.apply(
        lambda row: classify_account_category(
            row["account_number"], row["account_type"], row["description"]
        ),
        axis=1,
    )

    # 应用真实银行卡识别
    normalized["is_real_bank_card"] = normalized.apply(
        lambda row: is_real_bank_card(
            row["account_number"],
            row["account_type"],
            row.get("银行来源", bank_name or ""),
            row["account_category"],
        ),
        axis=1,
    )

    logger.info(
        f"账户类型识别完成: {normalized['is_real_bank_card'].sum()}张真实银行卡, "
        f"{(~normalized['is_real_bank_card']).sum()}个非银行卡账户"
    )

    # 8. 交易流水号(用于精确去重)
    tx_id_col = None
    tx_id_col = _find_first_matching_column(
        df, config.BANK_FIELD_MAPPING.get("transaction_id", [])
    )

    if tx_id_col:
        normalized["transaction_id"] = _normalize_optional_text_series(df[tx_id_col])
    else:
        normalized["transaction_id"] = ""

    # ========== 刑侦级指标字段 (Phase 0.1 - 2026-01-18 新增) ==========

    # 9. 余额归零标志 - 判断交易后余额是否清空
    # 余额低于阈值（默认10元）视为"清空"，这是洗钱/过桥资金的典型特征
    normalized["is_balance_zeroed"] = normalized["balance"].apply(
        lambda x: x < config.BALANCE_ZERO_THRESHOLD if pd.notna(x) and x >= 0 else False
    )

    # 10. 交易渠道分类 - 识别网银/ATM/柜面/手机银行等渠道
    def classify_transaction_channel(description: str) -> str:
        """根据交易摘要分类交易渠道"""
        desc = str(description).upper()
        for channel, keywords in config.TRANSACTION_CHANNEL_KEYWORDS.items():
            if any(kw.upper() in desc for kw in keywords):
                return channel
        return "其他"

    normalized["transaction_channel"] = normalized["description"].apply(
        classify_transaction_channel
    )

    # 11. 敏感词提取 - 标记包含敏感词的交易
    def extract_sensitive_keywords(description: str) -> str:
        """从交易摘要中提取敏感词"""
        desc = str(description)
        found = [kw for kw in config.SENSITIVE_KEYWORDS if kw in desc]
        return ",".join(found) if found else ""

    normalized["sensitive_keywords"] = normalized["description"].apply(
        extract_sensitive_keywords
    )

    # 12. 原始行索引 - 保留原始Excel行号用于审计追溯
    # 审计人员可通过此字段快速定位原始凭证
    normalized["source_row_index"] = df.index + 2  # +2 是因为 Excel 从1开始计数且有表头

    # ========== 内存优化 ==========
    # 【内存优化】优化数据类型以节省内存
    # 金额列：保持 float64 确保审计精度
    normalized["income"] = normalized["income"].round(2).astype("float64")
    normalized["expense"] = normalized["expense"].round(2).astype("float64")
    normalized["balance"] = normalized["balance"].round(2).astype("float64")

    # 文本列：转为 category 类型节省内存（这是内存优化的关键）
    for col in [
        "description",
        "counterparty",
        "数据来源",
        "银行来源",
        "account_number",
        "transaction_id",
        "transaction_channel",
        "sensitive_keywords",
        "account_type",
        "account_category",
    ]:  # Phase 1 新增 account_type, account_category
        if col in normalized.columns:
            normalized[col] = normalized[col].astype("category")

    # 布尔列：转为 bool 类型
    for col in [
        "is_cash",
        "is_balance_zeroed",
        "is_real_bank_card",
    ]:  # Phase 1 新增 is_real_bank_card
        if col in normalized.columns:
            normalized[col] = normalized[col].astype("bool")

    logger.info(f"字段标准化完成,有效记录: {len(normalized)}条 (已优化数据类型)")

    return normalized


def generate_cleaning_report(
    entity_name: str, file_stats: List[Dict], final_stats: Dict
) -> pd.DataFrame:
    """
    生成清洗报告

    Args:
        entity_name: 实体名称
        file_stats: 各文件统计列表
        final_stats: 最终统计

    Returns:
        报告DataFrame
    """
    report_data = []

    # 各文件的统计
    for stat in file_stats:
        report_data.append(
            {
                "对象": entity_name,
                "文件名": stat["filename"],
                "银行": stat.get("bank", "未知"),
                "原始行数": stat["original_rows"],
                "有效行数": stat["valid_rows"],
                "去重行数": stat.get("duplicates", 0),
                "处理时间": stat.get("process_time", "-"),
            }
        )

    # 汇总行
    report_data.append(
        {
            "对象": entity_name,
            "文件名": "【汇总】",
            "银行": f"共{len(file_stats)}家银行",
            "原始行数": final_stats["total_original"],
            "有效行数": final_stats["total_valid"],
            "去重行数": final_stats["total_duplicates"],
            "处理时间": final_stats.get("total_time", "-"),
        }
    )

    return pd.DataFrame(report_data)


def clean_and_merge_files(
    file_list: List[str], entity_name: str
) -> Tuple[pd.DataFrame, Dict]:
    """
    清洗并合并多个文件

    Args:
        file_list: 文件路径列表
        entity_name: 实体名称

    Returns:
        (合并后的DataFrame, 统计信息)
    """
    logger.info(f"开始清洗合并 {entity_name} 的数据,共{len(file_list)}个文件")

    all_dfs = []
    file_stats = []

    start_time = datetime.now()

    def _build_final_stats(
        total_valid_rows: int, total_duplicates: int, final_rows: int
    ) -> Dict:
        total_time = (datetime.now() - start_time).total_seconds()
        return {
            "entity": entity_name,
            "file_count": len(file_list),
            "total_original": sum(s["original_rows"] for s in file_stats),
            "total_valid": total_valid_rows,
            "total_duplicates": total_duplicates,
            "final_rows": final_rows,
            "total_time": f"{total_time:.2f}s",
            "file_stats": file_stats,
        }

    for filepath in file_list:
        file_start = datetime.now()
        filename = os.path.basename(
            filepath
        )  # 跨平台：使用os.path.basename替代split('/')

        # 提取银行名称
        bank_name = utils.extract_bank_name(filename)

        logger.info(f"处理文件: {filename}, 银行: {bank_name}")

        try:
            # 读取Excel
            df_raw = _read_transaction_file(filepath)
            original_rows = len(df_raw)

            # 标准化字段
            df_normalized = standardize_bank_fields(
                df_raw, bank_name, entity_name=entity_name
            )

            # 数据验证
            df_valid, quality_report = validate_data_quality(df_normalized)

            # 添加来源信息
            df_valid["数据来源"] = filename
            df_valid["银行来源"] = bank_name

            if not df_valid.empty:
                all_dfs.append(df_valid)

            file_time = (datetime.now() - file_start).total_seconds()

            file_stats.append(
                {
                    "filename": filename,
                    "bank": bank_name,
                    "original_rows": original_rows,
                    "valid_rows": len(df_valid),
                    "duplicates": quality_report.get("removed_rows", 0),
                    "process_time": f"{file_time:.2f}s",
                }
            )

        except Exception as e:
            logger.error(f"处理文件失败: {filename}, 错误: {str(e)}")
            file_stats.append(
                {
                    "filename": filename,
                    "bank": bank_name,
                    "original_rows": 0,
                    "valid_rows": 0,
                    "duplicates": 0,
                    "process_time": "ERROR",
                }
            )

    # 合并所有数据
    if not all_dfs:
        logger.error(f"{entity_name} 没有有效数据")
        final_stats = _build_final_stats(total_valid_rows=0, total_duplicates=0, final_rows=0)
        logger.info(
            f"{entity_name} 清洗合并完成: {len(file_list)}个文件, "
            f"{final_stats['total_original']}行 → {final_stats['final_rows']}行"
        )
        return pd.DataFrame(), final_stats

    df_merged = pd.concat(all_dfs, ignore_index=True)

    # 去重
    df_final, dedup_stats = deduplicate_transactions(df_merged)

    # 按时间排序
    df_final = df_final.sort_values("date").reset_index(drop=True)

    # Phase 0.4: 添加累计统计字段（用于识别分次规避大额的行为）
    # 当日累计：识别当日多笔小额累加超过大额阈值的情况
    # 当月累计：识别月度累计异常
    if "date" in df_final.columns and not df_final.empty:
        try:
            # 创建日期和月份分组键
            df_final["_date_key"] = df_final["date"].dt.date
            df_final["_month_key"] = df_final["date"].dt.to_period("M")

            # 计算当日累计收入/支出
            df_final["daily_cumulative_income"] = df_final.groupby("_date_key")[
                "income"
            ].cumsum()
            df_final["daily_cumulative_expense"] = df_final.groupby("_date_key")[
                "expense"
            ].cumsum()

            # 计算当月累计收入/支出
            df_final["monthly_cumulative_income"] = df_final.groupby("_month_key")[
                "income"
            ].cumsum()
            df_final["monthly_cumulative_expense"] = df_final.groupby("_month_key")[
                "expense"
            ].cumsum()

            # 删除临时分组键
            df_final = df_final.drop(["_date_key", "_month_key"], axis=1)

            logger.info(f"  已添加累计统计字段 (当日/当月累计收支)")
        except Exception as e:
            logger.warning(f"  累计统计字段计算失败: {e}")

    final_stats = _build_final_stats(
        total_valid_rows=len(df_merged),
        total_duplicates=dedup_stats["duplicates"],
        final_rows=len(df_final),
    )

    logger.info(
        f"{entity_name} 清洗合并完成: {len(file_list)}个文件, "
        f"{final_stats['total_original']}行 → {final_stats['final_rows']}行"
    )

    return df_final, final_stats


def _prepare_display_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    准备显示数据（清洗、分类、列名映射）

    Args:
        df: 原始DataFrame

    Returns:
        处理后的显示DataFrame
    """
    df_disp = df.copy()

    # 数据清洗
    if "数据来源" in df_disp.columns:
        df_disp["数据来源"] = df_disp["数据来源"].apply(
            lambda x: str(x).split("/")[-1].split("\\")[-1]
        )
    if "is_cash" in df_disp.columns:
        df_disp["is_cash"] = df_disp["is_cash"].apply(
            lambda x: "是" if x is True else ""
        )

    # 自动化交易分类打标
    def refine_category(row):
        text = str(row.get("description", "")) + " " + str(row.get("counterparty", ""))
        sorted_cats = sorted(
            config.TRANSACTION_CATEGORIES.items(), key=lambda x: x[1]["priority"]
        )
        for cat_name, conf in sorted_cats:
            if utils.contains_keywords(text, conf["keywords"]):
                return cat_name
        return "其他"

    df_disp["category"] = df_disp.apply(refine_category, axis=1)

    # 【铁律】使用统一的列名映射（来自 config.py）
    col_mapping = config.COLUMN_MAPPING

    # 【铁律】使用统一的列顺序（来自 config.py）
    desired_order = config.COLUMN_ORDER

    # 重排与重命名
    existing_cols = [c for c in desired_order if c in df_disp.columns]
    process_cols = set(desired_order)
    other_cols = [c for c in df_disp.columns if c not in process_cols]
    df_disp = df_disp[existing_cols + other_cols]
    df_disp = df_disp.rename(columns=col_mapping)

    return df_disp


def _create_excel_formats(workbook) -> Dict:
    """
    创建Excel格式

    Args:
        workbook: ExcelWriter workbook对象

    Returns:
        格式字典
    """
    # 表头样式：浅灰背景，深色字，加粗，边框
    header_fmt = workbook.add_format(
        {
            "bold": True,
            "valign": "vcenter",
            "align": "center",
            "fg_color": "#EFEFEF",
            "border": 1,
            "font_name": "微软雅黑",
            "font_size": 10,
        }
    )

    # 会计金额格式：千分位，0显示为"-"，对齐
    accounting_fmt = workbook.add_format(
        {
            "num_format": '_ * #,##0.00_ ;_ * -#,##0.00_ ;_ * "-"??_ ;_ @_ ',
            "font_name": "Arial",
            "font_size": 10,
        }
    )

    # 日期格式：yyyy-mm-dd hh:mm:ss
    date_fmt = workbook.add_format(
        {
            "num_format": "yyyy-mm-dd hh:mm:ss",
            "font_name": "Arial",
            "font_size": 10,
            "align": "left",
        }
    )

    # 普通文本：微软雅黑
    text_fmt = workbook.add_format(
        {"font_name": "微软雅黑", "font_size": 10, "valign": "vcenter"}
    )

    return {
        "header": header_fmt,
        "accounting": accounting_fmt,
        "date": date_fmt,
        "text": text_fmt,
    }


def _apply_excel_formatting(worksheet, df_disp: pd.DataFrame, formats: Dict):
    """
    应用Excel格式化

    Args:
        worksheet: Excel工作表对象
        df_disp: 显示DataFrame
        formats: 格式字典
    """
    # 写入表头（覆盖默认格式）
    for col_num, value in enumerate(df_disp.columns.values):
        worksheet.write(0, col_num, value, formats["header"])

    # 遍历每列及数据，计算最佳宽度
    for i, col_name in enumerate(df_disp.columns):
        # 基础列宽：取表头长度
        max_len = len(str(col_name)) * 2

        # 采样前100行数据计算长度
        sample = df_disp[col_name].iloc[:100].astype(str)
        if not sample.empty:
            data_max_len = sample.map(lambda x: len(x.encode("gbk"))).max()
            max_len = max(max_len, data_max_len)

        # 设置宽度限制和特定格式
        col_fmt = formats["text"]
        width = max_len + 2

        if "时间" in col_name:
            width = 23
            col_fmt = formats["date"]
        elif any(c in col_name for c in ["收入", "支出", "余额", "金额"]):
            width = max(width, 15)
            col_fmt = formats["accounting"]
        elif "摘要" in col_name:
            width = min(width, 50)
        elif "账号" in col_name:
            width = max(width, 22)

        # 应用列宽和格式
        worksheet.set_column(i, i, width, col_fmt)

    # 消除绿色小三角 (忽略数字存为文本错误)
    worksheet.ignore_errors({"number_stored_as_text": "A1:XFD1048576"})

    # 冻结首行
    worksheet.freeze_panes(1, 0)

    # 开启筛选
    worksheet.autofilter(0, 0, len(df_disp), len(df_disp.columns) - 1)


# ============================================================
# P2 优化：Parquet 高性能存储
# ============================================================


def save_as_parquet(df: pd.DataFrame, output_path: str) -> bool:
    """
    保存为 Parquet 格式（高性能中间存储）

    【P2 优化 - 2026-01-18】
    Parquet 相比 Excel 的优势：
    - 读取速度快 10-50 倍
    - 文件体积小 50-70%
    - 支持列式存储，按需读取列

    Args:
        df: 要保存的 DataFrame
        output_path: 输出路径（.parquet 后缀）

    Returns:
        是否保存成功
    """
    if df.empty:
        logger.warning(f"空 DataFrame，跳过 Parquet 保存")
        return False

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 保存为 Parquet（使用 pyarrow 引擎）
        df.to_parquet(
            output_path,
            engine="pyarrow",
            compression="snappy",  # 平衡压缩率和速度
            index=False,
        )

        logger.info(f"Parquet 文件已保存: {output_path}")
        return True

    except ImportError:
        logger.warning(
            "pyarrow 未安装，跳过 Parquet 保存。可通过 pip install pyarrow 安装"
        )
        return False
    except Exception as e:
        logger.error(f"Parquet 保存失败: {e}")
        return False


def load_from_parquet_or_excel(parquet_path: str, excel_path: str) -> pd.DataFrame:
    """
    优先从 Parquet 加载，如不存在则从 Excel 加载

    【P2 优化 - 2026-01-18】
    加载顺序：
    1. 优先尝试 Parquet（快）
    2. 回退到 Excel（慢但兼容）

    Args:
        parquet_path: Parquet 文件路径
        excel_path: Excel 文件路径

    Returns:
        加载的 DataFrame
    """
    # 优先尝试 Parquet
    if os.path.exists(parquet_path):
        try:
            df = pd.read_parquet(parquet_path)
            logger.debug(f"从 Parquet 加载: {parquet_path}")
            return df
        except Exception as e:
            logger.warning(f"Parquet 加载失败: {e}，回退到 Excel")

    # 回退到 Excel
    if os.path.exists(excel_path):
        try:
            df = pd.read_excel(excel_path, dtype=str)
            logger.debug(f"从 Excel 加载: {excel_path}")
            return df
        except Exception as e:
            logger.error(f"Excel 加载失败: {e}")
            return pd.DataFrame()

    logger.warning(f"文件不存在: {parquet_path} 或 {excel_path}")
    return pd.DataFrame()


def save_cleaned_data_dual_format(df: pd.DataFrame, base_path: str, entity_name: str):
    """
    同时保存为 Excel 和 Parquet 格式

    Args:
        df: 清洗后的 DataFrame
        base_path: 基础目录路径
        entity_name: 实体名称（用于文件名）
    """
    # Excel 路径（供人阅读）
    excel_path = os.path.join(base_path, f"{entity_name}_cleaned.xlsx")

    # Parquet 路径（供程序快速读取）
    parquet_dir = os.path.join(os.path.dirname(base_path), "parquet")
    parquet_path = os.path.join(parquet_dir, f"{entity_name}.parquet")

    # 保存 Excel
    save_formatted_excel(df, excel_path)

    # 保存 Parquet
    save_as_parquet(df, parquet_path)


def save_formatted_excel(df: pd.DataFrame, output_path: str):
    """
    保存为美观的Excel格式（专家级优化版）：
    1. 智能列宽：根据内容长度自动调整，彻底解决 ######
    2. 视觉降噪：强制移除"数字存为文本"的绿色小三角
    3. 会计格式：0值显示为"-"，金额更易读
    4. 彻底汉化与清洗
    """
    # 1. 准备显示数据
    df_disp = _prepare_display_data(df)

    # 2. 保存并格式化
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
            sheet_name = "交易流水"
            df_disp.to_excel(writer, index=False, sheet_name=sheet_name)

            workbook = writer.book
            worksheet = writer.sheets[sheet_name]

            # 创建格式
            formats = _create_excel_formats(workbook)

            # 应用格式化
            _apply_excel_formatting(worksheet, df_disp, formats)

    except PermissionError:
        logger.warning(
            f"无法保存文件 {output_path}: 文件可能被占用，请关闭Excel后重试。"
        )
    except Exception as e:
        logger.error(f"格式化保存Excel失败: {str(e)}, 回退到普通保存")
        try:
            df_disp.to_excel(output_path, index=False)
        except PermissionError:
            logger.warning(f"无法保存文件 {output_path}: 文件可能被占用。")
