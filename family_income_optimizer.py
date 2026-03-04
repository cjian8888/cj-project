#!/usr/bin/env python3
"""
【2026-03-04 优化】家庭收入计算优化模块
用于替代 api_server.py 中低效的循环计算
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Set
import time


def calculate_family_transfers_vectorized(
    df: pd.DataFrame, family_members: List[str], person_name: str
) -> Tuple[float, float, Dict]:
    """
    【优化版】向量化计算家庭内部转账金额

    原实现: O(N×M) 双重循环遍历所有交易
    优化后: O(N) 单次向量化操作

    Args:
        df: 个人交易DataFrame
        family_members: 家庭成员列表
        person_name: 当前人员名称

    Returns:
        (家庭转入金额, 家庭转出金额, 明细字典)
    """
    if df.empty or not family_members:
        return 0.0, 0.0, {}

    start_time = time.time()

    # 【优化1】将家庭成员列表转换为Set，O(1)查找
    family_set = set(family_members)

    # 【优化2】向量化判断对手方是否为家庭成员
    # 使用isin而不是逐行比较
    counterparty = df["counterparty"].fillna("").astype(str)
    is_family = counterparty.isin(family_set)

    # 【优化3】向量化计算家庭转账金额
    # 收入来自家庭成员 = 家庭转入
    family_income = df.loc[is_family, "income"].fillna(0).sum()

    # 支出给家庭成员 = 家庭转出
    family_expense = df.loc[is_family, "expense"].fillna(0).sum()

    # 【优化4】使用value_counts统计而不是循环
    detail = {}
    if family_income > 0:
        income_from = df[is_family & (df["income"] > 0)]
        detail["income_sources"] = (
            income_from.groupby("counterparty")["income"].sum().to_dict()
        )

    if family_expense > 0:
        expense_to = df[is_family & (df["expense"] > 0)]
        detail["expense_targets"] = (
            expense_to.groupby("counterparty")["expense"].sum().to_dict()
        )

    elapsed = time.time() - start_time

    return family_income, family_expense, detail


def batch_update_family_income(
    profiles: Dict,
    cleaned_data: Dict[str, pd.DataFrame],
    family_units_list: List[Dict],
    logger=None,
) -> Dict:
    """
    【优化版】批量更新所有人员的真实收入

    原实现: 逐个人员循环，每人内再循环DataFrame
    优化后: 批量处理，预计算映射关系

    Args:
        profiles: 人员画像字典
        cleaned_data: 清洗后的交易数据
        family_units_list: 家庭单元列表
        logger: 日志对象

    Returns:
        更新后的profiles
    """
    import time

    start_total = time.time()

    if logger:
        logger.info("  ▶ [优化] 批量更新家庭真实收入...")

    # 【优化1】预构建人员->家庭成员映射
    person_to_family: Dict[str, Set[str]] = {}
    for unit in family_units_list:
        members = unit.get("members", [])
        member_set = set(members)
        for member in members:
            # 该成员的其他家庭成员
            person_to_family[member] = member_set - {member}

    updated_count = 0
    total_family_income = 0.0
    total_family_expense = 0.0

    # 【优化2】批量处理所有人员
    for person_name, profile in profiles.items():
        family_members = person_to_family.get(person_name)
        if not family_members:
            continue

        df = cleaned_data.get(person_name)
        if df is None or df.empty:
            continue

        try:
            # 【优化3】使用向量化函数计算家庭转账
            family_income, family_expense, detail = (
                calculate_family_transfers_vectorized(
                    df, list(family_members), person_name
                )
            )

            if family_income > 0 or family_expense > 0:
                # 获取原始收入
                income_structure = profile.get("income_structure", {})
                original_income = income_structure.get("total_income", 0)
                original_expense = income_structure.get("total_expense", 0)

                # 计算真实收入（剔除家庭内部转账）
                new_real_income = max(0, original_income - family_income)
                new_real_expense = max(0, original_expense - family_expense)

                # 更新profile
                if "summary" not in profile:
                    profile["summary"] = {}
                profile["summary"]["real_income"] = new_real_income
                profile["summary"]["real_expense"] = new_real_expense
                profile["summary"]["family_transfer_in"] = family_income
                profile["summary"]["family_transfer_out"] = family_expense
                profile["summary"]["family_transfer_detail"] = detail

                # 顶层字段兼容
                profile["real_income"] = new_real_income
                profile["real_expense"] = new_real_expense

                updated_count += 1
                total_family_income += family_income
                total_family_expense += family_expense

                if logger and updated_count <= 5:  # 只打印前5个人的日志
                    logger.info(
                        f"  ✓ {person_name}: 原始收支 {original_income / 10000:.1f}万/{original_expense / 10000:.1f}万, "
                        f"剔除家庭转账 {family_income / 10000:.1f}万/{family_expense / 10000:.1f}万"
                    )

        except Exception as e:
            if logger:
                logger.warning(f"  ✗ 更新 {person_name} 真实收入失败: {e}")

    elapsed_total = time.time() - start_total
    if logger:
        logger.info(
            f"  ✓ [优化] 批量更新完成: {updated_count}人, "
            f"总家庭转账 入{total_family_income / 10000:.1f}万/出{total_family_expense / 10000:.1f}万, "
            f"耗时{elapsed_total:.3f}秒"
        )

    return profiles


# ============================================================
# 使用示例（替换api_server.py中的代码）
# ============================================================


def example_usage():
    """
    在 api_server.py 中替换以下代码：

    【原代码】
    for person_name in profiles:
        family_members = person_to_family.get(person_name, [])
        ...
        for idx, row in df.iterrows():  # 慢！
            counterparty = str(row.get('counterparty', ''))
            if counterparty in family_members:
                ...

    【优化后】
    from family_income_optimizer import batch_update_family_income
    profiles = batch_update_family_income(
        profiles, cleaned_data, family_units_list, logger
    )
    """
    pass


if __name__ == "__main__":
    # 测试代码
    print("家庭收入优化模块加载成功")
    print("使用方法：from family_income_optimizer import batch_update_family_income")
