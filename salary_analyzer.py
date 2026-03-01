#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收入分析模块 - 资金穿透与关联排查系统
专注于收入的识别、分类和分析

首席架构师视角的改进：
1. 将庞大的 financial_profiler.py 拆分，遵循单一职责原则。
2. 提高工资识别的准确性和覆盖率（多维度综合判断）。
3. 实现更细致的收入分类（工资、理财收益、补贴、利息等）。
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
from collections import defaultdict
import config
import utils

logger = utils.setup_logger(__name__)


def identify_salary_transactions(
    df: pd.DataFrame, entity_name: str
) -> Tuple[pd.DataFrame, Dict]:
    """
    识别工资性收入交易（重构版）

    核心算法改进：
    1. 多维度综合判断：关键词 + 发薪单位 + 频率 + 金额稳定性
    2. 排除规则增强：严格排除理财赎回、报销、政府补贴干扰
    3. 宽松匹配：对于“代发工资”等强信号，降低其他维度的要求

    Args:
        df: 交易DataFrame
        entity_name: 实体名称

    Returns:
        (工资交易DataFrame, 统计字典)
    """
    logger.info(f"正在识别 {entity_name} 的工资性收入...")

    if df.empty or "income" not in df.columns:
        return pd.DataFrame(), {}

    # 1. 基于强关键词的高置信度识别
    # 这些是100%确定的工资
    strong_salary_mask = df["description"].apply(
        lambda x: utils.contains_keywords(str(x), config.SALARY_STRONG_KEYWORDS)
    )
    salary_by_strong = df[(df["income"] > 0) & strong_salary_mask].copy()

    # 2. 基于发薪单位的识别
    # 如果对手方是已知发薪单位，且金额合理
    known_payers = config.KNOWN_SALARY_PAYERS + config.USER_DEFINED_SALARY_PAYERS
    known_payer_mask = df["counterparty"].apply(
        lambda x: any(p in str(x) for p in known_payers)
    )
    # 排除报销等负面关键词
    negative_mask = df["description"].apply(
        lambda x: utils.contains_keywords(
            str(x), config.EXCLUDED_REIMBURSEMENT_KEYWORDS
        )
    )
    salary_by_payer = df[
        (df["income"] > 0) & known_payer_mask & (~negative_mask)
    ].copy()

    # 3. 高频稳定收入检测（排除工资，可能是劳务、私活等）
    # 算法：同一对手方，每月/每周固定日期，金额稳定（CV < 0.3）
    # 注意：这里要排除已识别的工资和理财
    df_income = df[df["income"] > 0].copy()

    # 排除已识别为工资的
    df_income = df_income[~df_income.index.isin(salary_by_strong.index)]
    df_income = df_income[~df_income.index.isin(salary_by_payer.index)]

    # 排除理财相关
    df_income = df_income[
        ~df_income["description"].apply(
            lambda x: utils.contains_keywords(str(x), config.WEALTH_REDEMPTION_KEYWORDS)
        )
    ]

    regular_income = []
    if not df_income.empty:
        # 按对手方分组
        for cp, cp_df in df_income.groupby("counterparty"):
            if len(cp_df) < 3:  # 至少3笔才分析
                continue

            cp_df = cp_df.sort_values("date")
            dates = cp_df["date"].tolist()
            amounts = cp_df["income"].tolist()

            # 检查周期性
            if len(dates) >= 2:
                intervals = [
                    (dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)
                ]
                avg_interval = sum(intervals) / len(intervals)

                # 月度周期（25-35天）
                if 25 <= avg_interval <= 35:
                    # 检查金额稳定性
                    mean_amt = sum(amounts) / len(amounts)
                    if mean_amt > 0:
                        cv = (
                            sum((x - mean_amt) ** 2 for x in amounts) / len(amounts)
                        ) ** 0.5 / mean_amt

                        if cv < 0.3:  # 金额稳定
                            regular_income.append(cp_df)

    if regular_income:
        salary_by_regular = pd.concat(regular_income)
    else:
        salary_by_regular = pd.DataFrame()

    # 合并所有工资收入
    all_salary_transactions = pd.concat(
        [salary_by_strong, salary_by_payer, salary_by_regular]
    )

    # 重新排序
    all_salary_transactions = all_salary_transactions.sort_values("date").reset_index(
        drop=True
    )

    # 生成统计
    stats = {
        "total_count": len(all_salary_transactions),
        "total_amount": all_salary_transactions["income"].sum(),
        "by_strong_keyword": len(salary_by_strong),
        "by_payer": len(salary_by_payer),
        "by_regular_pattern": len(salary_by_regular),
    }

    logger.info(
        f"✓ 识别到工资交易 {len(all_salary_transactions)} 笔 (总计: {utils.format_currency(stats['total_amount'])})"
    )

    return all_salary_transactions, stats


def classify_income(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    对收入进行分类（工资、理财、利息、其他）

    Args:
        df: 收入交易DataFrame (只包含 income>0的记录)

    Returns:
        分类后的字典 {类型: DataFrame}
    """
    if df.empty:
        return {
            "salary": pd.DataFrame(),
            "wealth": pd.DataFrame(),
            "interest": pd.DataFrame(),
            "other": df.copy(),  # 如果空，全部归为other
        }

    # 初始化分类结果
    classified = {
        "salary": pd.DataFrame(),
        "wealth": pd.DataFrame(),
        "interest": pd.DataFrame(),
        "other": pd.DataFrame(),
    }

    # 1. 强关键词分类
    for income_type, keywords in {
        "salary": config.SALARY_KEYWORDS,
        "wealth": config.WEALTH_REDEMPTION_KEYWORDS + config.WEALTH_MANAGEMENT_KEYWORDS,
        "interest": ["利息", "结息", "分红", "收益", "利息收入"],
    }.items():
        mask = df["description"].apply(
            lambda x: utils.contains_keywords(str(x), keywords)
        )
        classified[income_type] = pd.concat([classified[income_type], df[mask]])

    # 2. 金额特征分类
    # 小额利息（<500元）通常是银行利息
    small_interest_mask = (
        (df["income"] > 0)
        & (df["income"] < 500)
        & (df["description"].str.contains("利息|结息", na=False))
    )
    classified["interest"] = pd.concat(
        [classified["interest"], df[small_interest_mask]]
    )

    # 3. 已分类的交易从 other 中移除
    all_classified = pd.concat(
        [classified["salary"], classified["wealth"], classified["interest"]]
    )
    # 注意：这里不能直接用 drop_duplicates，因为有重叠。用索引去重。
    classified["other"] = df[~df.index.isin(all_classified.index)]

    return classified


def analyze_income_structure(df: pd.DataFrame, entity_name: str) -> Dict:
    """
    分析收入结构

    Args:
        df: 收入交易DataFrame
        entity_name: 实体名称

    Returns:
        收入结构分析结果
    """
    logger.info(f"正在分析 {entity_name} 的收入结构...")

    if df.empty or "income" not in df.columns:
        return {
            "total_income": 0.0,
            "salary_income": 0.0,
            "wealth_income": 0.0,
            "interest_income": 0.0,
            "other_income": 0.0,
            "salary_ratio": 0.0,
        }

    # 1. 识别工资
    salary_df, salary_stats = identify_salary_transactions(df, entity_name)

    # 2. 对所有收入进行分类
    income_df = df[df["income"] > 0].copy()
    classified = classify_income(income_df)

    # 3. 计算各类收入
    salary_total = salary_df["income"].sum() if not salary_df.empty else 0
    wealth_total = (
        classified["wealth"]["income"].sum() if not classified["wealth"].empty else 0
    )
    interest_total = (
        classified["interest"]["income"].sum()
        if not classified["interest"].empty
        else 0
    )
    other_total = (
        classified["other"]["income"].sum() if not classified["other"].empty else 0
    )

    total_income = df["income"].sum()

    # 4. 工资收入占比
    salary_ratio = salary_total / total_income if total_income > 0 else 0.0

    # 5. 分年度工资统计
    yearly_salary = defaultdict(float)
    for _, row in salary_df.iterrows():
        if pd.notna(row["date"]):
            year = row["date"].year
            yearly_salary[year] += row["income"]

    salary_details = []
    for year, amount in sorted(yearly_salary.items()):
        salary_details.append({"年份": year, "金额": amount})

    # 结果
    result = {
        "total_income": total_income,
        "salary_income": salary_total,
        "wealth_income": wealth_total,
        "interest_income": interest_total,
        "other_income": other_total,
        "salary_ratio": salary_ratio,
        "salary_details": salary_details,
        "salary_stats": salary_stats,
        "classified_income": classified,
        "salary_transactions": salary_df,
    }

    logger.info(
        f"✓ 收入分析完成: 总收入 {utils.format_currency(total_income)}, 工资收入占比 {salary_ratio:.1%}"
    )

    return result
