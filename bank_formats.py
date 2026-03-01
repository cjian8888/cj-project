#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多数据源配置模块 - 支持不同银行格式的数据导入

【修复说明】
- 问题4修复：日期解析失败时未处理
- 解决方案：添加详细的错误处理和降级逻辑
- 修改日期：2026-01-25
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import re
import utils

logger = utils.setup_logger(__name__)

# ============== 银行格式配置 ==============

BANK_FORMATS = {
    # 工商银行格式
    "ICBC": {
        "name": "中国工商银行",
        "column_mapping": {
            "交易日期": "date",
            "交易时间": "time",
            "收入金额": "income",
            "支出金额": "expense",
            "交易余额": "balance",
            "对方户名": "counterparty",
            "对方账号": "counterparty_account",
            "交易摘要": "description",
            "交易流水号": "transaction_id",
            "本方账号": "account_number",
        },
        "date_format": "%Y-%m-%d",
        "encoding": "utf-8",
        "skip_rows": 0,
        "header_row": 0,
    },
    # 建设银行格式
    "CCB": {
        "name": "中国建设银行",
        "column_mapping": {
            "交易日期": "date",
            "贷方发生额": "income",
            "借方发生额": "expense",
            "余额": "balance",
            "对手账户名称": "counterparty",
            "对手账号": "counterparty_account",
            "交易摘要": "description",
            "流水号": "transaction_id",
            "账号": "account_number",
        },
        "date_format": "%Y%m%d",
        "encoding": "gbk",
        "skip_rows": 1,
        "header_row": 0,
    },
    # 农业银行格式
    "ABC": {
        "name": "中国农业银行",
        "column_mapping": {
            "日期": "date",
            "存入": "income",
            "支取": "expense",
            "余额": "balance",
            "对方户名": "counterparty",
            "备注": "description",
            "账号": "account_number",
        },
        "date_format": "%Y-%m-%d",
        "encoding": "utf-8",
        "skip_rows": 0,
        "header_row": 0,
    },
    # 中国银行格式
    "BOC": {
        "name": "中国银行",
        "column_mapping": {
            "交易日期": "date",
            "贷": "income",
            "借": "expense",
            "账户余额": "balance",
            "收/付方名称": "counterparty",
            "摘要": "description",
            "交易卡号/账号": "account_number",
        },
        "date_format": "%Y/%m/%d",
        "encoding": "utf-8",
        "skip_rows": 0,
        "header_row": 0,
    },
    # 招商银行格式
    "CMB": {
        "name": "招商银行",
        "column_mapping": {
            "交易日": "date",
            "入账金额": "income",
            "支出金额": "expense",
            "账户余额": "balance",
            "交易对方": "counterparty",
            "交易摘要": "description",
            "卡号": "account_number",
        },
        "date_format": "%Y-%m-%d",
        "encoding": "utf-8",
        "skip_rows": 0,
        "header_row": 0,
    },
    # 通用格式（默认）
    "GENERIC": {
        "name": "通用格式",
        "column_mapping": {
            "交易时间": "date",
            "收入(元)": "income",
            "支出(元)": "expense",
            "余额(元)": "balance",
            "交易对手": "counterparty",
            "交易摘要": "description",
            "本方账号": "account_number",
            "所属银行": "bank_name",
        },
        "date_format": None,  # 自动检测
        "encoding": "utf-8",
        "skip_rows": 0,
        "header_row": 0,
    },
}


# ============== 银行格式检测配置 ==============

# 列权重配置（关键列权重更高）
COLUMN_WEIGHTS = {
    "date": 3.0,  # 日期列权重最高
    "income": 2.0,  # 收入列权重高
    "expense": 2.0,  # 支出列权重高
    "balance": 1.5,  # 余额列权重中等
    "counterparty": 1.0,  # 对手方列权重正常
    "description": 0.5,  # 摘要列权重较低
    "account_number": 1.0,  # 账号列权重正常
    "transaction_id": 0.5,  # 流水号列权重较低
    "default": 1.0,  # 默认权重
}


def _normalize_column_name(col_name: str) -> str:
    """
    规范化列名：去除空格、统一小写、去除特殊字符

    Args:
        col_name: 原始列名

    Returns:
        规范化后的列名
    """
    # 去除前后空格
    normalized = str(col_name).strip()
    # 统一转换为小写
    normalized = normalized.lower()
    # 去除括号及其内容（用于处理"收入(元)"这类列名）
    normalized = re.sub(r"[()（）\[\]【】]", "", normalized)
    # 去除下划线和连字符
    normalized = normalized.replace("_", "").replace("-", "")
    return normalized


def _calculate_column_match_score(
    df_column: str, expected_column: str, df: pd.DataFrame = None
) -> Tuple[float, str]:
    """
    计算列名匹配分数

    Args:
        df_column: DataFrame中的列名
        expected_column: 预期的列名
        df: DataFrame（可选，用于数据特征验证）

    Returns:
        (分数, 匹配类型)
    """
    normalized_df_col = _normalize_column_name(df_column)
    normalized_expected = _normalize_column_name(expected_column)

    # 精确匹配（最高分）
    if normalized_df_col == normalized_expected:
        return 1.0, "exact_match"

    # 前缀匹配
    if normalized_df_col.startswith(normalized_expected):
        return 0.8, "prefix_match"

    # 包含匹配
    if normalized_expected in normalized_df_col:
        return 0.6, "contains_match"

    # 相似度匹配（使用简单的编辑距离）
    if len(normalized_df_col) > 0 and len(normalized_expected) > 0:
        # 简单的相似度检查
        if abs(len(normalized_df_col) - len(normalized_expected)) <= 2:
            common_chars = sum(1 for c in normalized_expected if c in normalized_df_col)
            similarity_ratio = common_chars / len(normalized_expected)
            if similarity_ratio >= 0.7:
                return 0.4, "similarity_match"

    return 0.0, "no_match"


def _calculate_bank_format_score(
    df: pd.DataFrame, bank_config: Dict, verbose: bool = True
) -> Tuple[float, Dict]:
    """
    计算银行格式匹配分数

    Args:
        df: DataFrame
        bank_config: 银行配置
        verbose: 是否输出详细日志

    Returns:
        (总分, 详细信息)
    """
    df_columns = df.columns.tolist()
    column_mapping = bank_config["column_mapping"]

    total_score = 0.0
    max_possible_score = 0.0
    matched_columns = {}
    unmatched_columns = []

    for expected_col, std_col in column_mapping.items():
        # 获取该列的权重
        weight = COLUMN_WEIGHTS.get(std_col, COLUMN_WEIGHTS["default"])
        max_possible_score += weight

        # 查找最佳匹配的列
        best_match_score = 0.0
        best_match_col = None
        best_match_type = None

        for df_col in df_columns:
            score, match_type = _calculate_column_match_score(df_col, expected_col, df)
            if score > best_match_score:
                best_match_score = score
                best_match_col = df_col
                best_match_type = match_type

        if best_match_score > 0:
            weighted_score = best_match_score * weight
            total_score += weighted_score
            matched_columns[expected_col] = {
                "matched_to": best_match_col,
                "score": best_match_score,
                "weight": weight,
                "weighted_score": weighted_score,
                "match_type": best_match_type,
            }
        else:
            unmatched_columns.append(expected_col)

    # 计算匹配率
    match_ratio = total_score / max_possible_score if max_possible_score > 0 else 0.0

    details = {
        "total_score": total_score,
        "max_possible_score": max_possible_score,
        "match_ratio": match_ratio,
        "matched_columns": matched_columns,
        "unmatched_columns": unmatched_columns,
        "matched_count": len(matched_columns),
        "total_columns": len(column_mapping),
    }

    return match_ratio, details


def detect_bank_format(df: pd.DataFrame, verbose: bool = True) -> str:
    """
    自动检测银行格式（改进版）

    使用加权匹配机制和多级匹配策略，提高检测准确率

    Args:
        df: 原始数据DataFrame
        verbose: 是否输出详细日志（默认True）

    Returns:
        银行格式代码 (如 'ICBC', 'CCB', 'GENERIC')
    """
    if df is None or df.empty:
        if verbose:
            logger.warning("DataFrame为空，无法检测银行格式")
        return "GENERIC"

    best_match = "GENERIC"
    best_score = 0.0
    best_details = None
    all_scores = []

    # 计算每个银行格式的匹配分数
    for bank_code, config in BANK_FORMATS.items():
        if bank_code == "GENERIC":
            continue

        match_ratio, details = _calculate_bank_format_score(df, config, verbose=False)
        all_scores.append(
            {
                "bank_code": bank_code,
                "bank_name": config["name"],
                "score": match_ratio,
                "details": details,
            }
        )

        if match_ratio > best_score:
            best_score = match_ratio
            best_match = bank_code
            best_details = details

    # 动态阈值：根据最佳匹配的列数调整阈值
    # 列数少的银行格式阈值更低
    if best_details:
        total_columns = best_details["total_columns"]
        # 列数越少，阈值越低
        dynamic_threshold = max(0.3, 0.5 - (10 - total_columns) * 0.05)
    else:
        dynamic_threshold = 0.5

    # 检查是否达到阈值
    if best_score < dynamic_threshold:
        if verbose:
            logger.warning(
                f"银行格式检测分数过低: {best_score:.2f} < 阈值={dynamic_threshold:.2f}, "
                f"使用通用格式"
            )
        best_match = "GENERIC"

    # 输出详细日志
    if verbose:
        logger.info(
            f"银行格式检测结果: {best_match} ({BANK_FORMATS[best_match]['name']})"
        )
        logger.info(f"  匹配分数: {best_score:.2f} (阈值: {dynamic_threshold:.2f})")

        # 按分数排序显示所有候选
        all_scores.sort(key=lambda x: x["score"], reverse=True)
        logger.debug("所有银行格式匹配分数:")
        for i, score_info in enumerate(all_scores[:5]):  # 只显示前5个
            details = score_info["details"]
            logger.debug(
                f"  {i + 1}. {score_info['bank_code']} ({score_info['bank_name']}): "
                f"分数={score_info['score']:.2f}, "
                f"匹配列数={details['matched_count']}/{details['total_columns']}"
            )

        # 显示最佳匹配的详细信息
        if best_details and best_match != "GENERIC":
            logger.debug(f"最佳匹配 {best_match} 的列映射:")
            for expected_col, match_info in best_details["matched_columns"].items():
                logger.debug(
                    f"  {expected_col} -> {match_info['matched_to']} "
                    f"(分数={match_info['score']:.2f}, "
                    f"权重={match_info['weight']:.1f}, "
                    f"类型={match_info['match_type']})"
                )

            if best_details["unmatched_columns"]:
                logger.debug(f"未匹配的列: {best_details['unmatched_columns']}")

    return best_match


def normalize_dataframe(df: pd.DataFrame, bank_format: str = None) -> pd.DataFrame:
    """
    将银行特定格式转换为标准格式

    Args:
        df: 原始数据DataFrame
        bank_format: 银行格式代码，None则自动检测

    Returns:
        标准化后的DataFrame
    """
    if bank_format is None:
        bank_format = detect_bank_format(df)

    config = BANK_FORMATS.get(bank_format, BANK_FORMATS["GENERIC"])

    # 复制数据
    result_df = df.copy()

    # 列名映射
    rename_map = {}
    for orig_col, std_col in config["column_mapping"].items():
        if orig_col in result_df.columns:
            rename_map[orig_col] = std_col

    # 【P1修复】添加列名存在性检查，返回标准列名提示
    if not rename_map:
        standard_columns = list(config.get("column_mapping", {}).values())
        available_columns = list(result_df.columns)
        logger.warning(
            f"银行格式 {bank_format} 无匹配列。"
            f"期望列: {standard_columns}, "
            f"可用列: {available_columns}"
        )
        return df

    try:
        result_df = result_df.rename(columns=rename_map)
    except Exception as e:
        logger.error(f"重命名列失败: {str(e)}，使用原始数据")
        return df

    # 【修复】添加日期格式转换的错误处理
    if "date" in result_df.columns and config["date_format"]:
        # 保存原始日期列用于降级
        original_dates = result_df["date"].copy()
        try:
            result_df["date"] = pd.to_datetime(
                result_df["date"],
                format=config["date_format"],
                errors="coerce",  # 无效日期转为NaT
            )
            # 记录日期解析失败的行数
            date_parse_failures = result_df["date"].isna().sum()
            if date_parse_failures > 0:
                logger.warning(
                    f"日期解析失败 {date_parse_failures} 条，已转为NaT，尝试使用智能日期解析"
                )
                # 尝试智能解析失败的日期
                failed_mask = result_df["date"].isna()
                if failed_mask.any():
                    try:
                        # 对失败的日期使用智能解析
                        parsed_dates = pd.to_datetime(
                            original_dates[failed_mask],
                            errors="coerce",
                            infer_datetime_format=True,
                        )
                        # 将智能解析成功的日期填充回去
                        success_mask = parsed_dates.notna()
                        if success_mask.any():
                            result_df.loc[failed_mask, "date"] = parsed_dates
                            recovered_count = success_mask.sum()
                            logger.info(
                                f"智能日期解析成功恢复 {recovered_count} 条日期"
                            )
                        # 仍未解析成功的，降级到原始格式
                        still_failed = failed_mask & result_df["date"].isna()
                        if still_failed.any():
                            result_df.loc[still_failed, "date"] = original_dates[
                                still_failed
                            ]
                            logger.warning(
                                f"{still_failed.sum()} 条日期无法解析，已保留原始格式"
                            )
                    except Exception as infer_e:
                        logger.error(
                            f"智能日期解析失败: {str(infer_e)}，降级到原始日期格式"
                        )
                        # 完全降级：恢复所有原始日期
                        result_df["date"] = original_dates
        except (ValueError, TypeError) as e:
            logger.error(f"日期格式转换失败: {str(e)}，使用原始日期列")
            # 降级：恢复原始日期列，不转换
            result_df["date"] = original_dates

    # 【修复】添加金额列转换的错误处理
    for col in ["income", "expense", "balance"]:
        if col in result_df.columns:
            try:
                result_df[col] = pd.to_numeric(result_df[col], errors="coerce").fillna(
                    0
                )
                # 记录转换失败的行数
                conversion_failures = result_df[col].isna().sum()
                if conversion_failures > 0:
                    logger.warning(
                        f"{col}列转换失败 {conversion_failures} 条，已填充为0"
                    )
            except Exception as e:
                logger.warning(f"{col}列转换失败: {str(e)}，填充为0")
                result_df[col] = 0.0

    # 移除无效行(没有日期的行)
    try:
        if "date" in result_df.columns:
            result_df = result_df[result_df["date"].notna()]
    except Exception as e:
        logger.warning(f"移除无效行失败: {str(e)}")

    # 按日期排序
    try:
        result_df = result_df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        logger.warning(f"按日期排序失败: {str(e)}")

    return result_df


def get_supported_banks() -> List[Dict]:
    """获取支持的银行列表"""
    return [
        {"code": code, "name": config["name"]} for code, config in BANK_FORMATS.items()
    ]


def add_custom_bank_format(
    code: str,
    name: str,
    column_mapping: Dict[str, str],
    date_format: str = None,
    encoding: str = "utf-8",
):
    """
    添加自定义银行格式

    Args:
        code: 银行代码
        name: 银行名称
        column_mapping: 列名映射
        date_format: 日期格式
        encoding: 文件编码
    """
    BANK_FORMATS[code] = {
        "name": name,
        "column_mapping": column_mapping,
        "date_format": date_format,
        "encoding": encoding,
        "skip_rows": 0,
        "header_row": 0,
    }
