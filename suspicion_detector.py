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

logger = utils.setup_logger(__name__)


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

    # 1. 准备数据：添加辅助列用于交叉连接
    # 使用 .copy() 避免修改原始 DataFrame（关键修复：防止数据污染）
    wd = withdrawals.copy()
    dp = deposits.copy()
    wd["join_key"] = 1
    dp["join_key"] = 1

    # 2. 执行交叉连接 (寻找所有可能的存取现组合)
    # 注意：在极大数据量(>10万条)下，这可能消耗内存。但对于通常的审计数据(几千-几万条)是极快的。
    merged = pd.merge(wd, dp, on="join_key", suffixes=("_wd", "_dp"))

    # 3. 计算时间差和金额差
    # 确保日期列是datetime类型
    merged["time_diff"] = (merged["date_dp"] - merged["date_wd"]).abs()
    # 将时间差转换为小时
    merged["hours_diff"] = merged["time_diff"].dt.total_seconds() / 3600

    merged["amount_wd"] = merged["amount_wd"].fillna(0)
    merged["amount_dp"] = merged["amount_dp"].fillna(0)
    merged["amount_diff_abs"] = (merged["amount_wd"] - merged["amount_dp"]).abs()

    # 计算金额差异比率 (相对于取现金额)
    # 避免除以0
    merged["amount_ratio"] = np.where(
        merged["amount_wd"] > 0, merged["amount_diff_abs"] / merged["amount_wd"], 1.0
    )

    # 4. 应用阈值筛选
    # 时间窗口：配置的小时数
    time_mask = merged["hours_diff"] <= config.CASH_TIME_WINDOW_HOURS

    # 金额容差：配置的比率
    amount_mask = merged["amount_ratio"] <= config.AMOUNT_TOLERANCE_RATIO

    # 5. 筛选符合条件的记录
    valid_collisions = merged[time_mask & amount_mask]

    # 6. 格式化结果 (适配 report_generator.py 字段要求)
    if not valid_collisions.empty:
        for _, row in valid_collisions.iterrows():
            # 简单的风险等级判定
            if row["hours_diff"] < 4 and row["amount_ratio"] < 0.01:
                risk = "high"
            elif row["hours_diff"] < 24:
                risk = "medium"
            else:
                risk = "low"

            collisions.append(
                {
                    "withdrawal_entity": entity_name,  # 取现方
                    "deposit_entity": entity_name,  # 存现方
                    "withdrawal_date": row["date_wd"],
                    "deposit_date": row["date_dp"],
                    "withdrawal_bank": row.get("银行来源_wd", "未知"),
                    "deposit_bank": row.get("银行来源_dp", "未知"),
                    "withdrawal_source": row.get("数据来源_wd", "未知"),
                    "deposit_source": row.get("数据来源_dp", "未知"),
                    "time_diff_hours": round(row["hours_diff"], 2),  # 字段名适配
                    "withdrawal_amount": row["amount_wd"],
                    "deposit_amount": row["amount_dp"],
                    "amount_diff": round(row["amount_diff_abs"], 2),  # 字段名适配
                    "amount_diff_ratio": round(row["amount_ratio"], 2),
                    "risk_level": risk,
                    "risk_reason": f"取现{row['amount_wd']}元与存现{row['amount_dp']}元时间间隔{row['hours_diff']:.1f}小时内，金额接近",
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
    wd_df["date"] = pd.to_datetime(wd_df["date"])
    dp_df["date"] = pd.to_datetime(dp_df["date"])
    wd_df = wd_df.sort_values("date").reset_index(drop=True)
    dp_df = dp_df.sort_values("date").reset_index(drop=True)

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

        # 执行单实体内检测
        collisions = detect_cash_time_collision(withdrawals, deposits, entity_name)

        if collisions:
            logger.info(
                f"    [{entity_name}] 发现 {len(collisions)} 处现金时空伴随(单实体)"
            )
            results["cash_collisions"].extend(collisions)

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

    # 检测核心人员与涉案公司之间的直接资金往来
    for person in all_persons:
        for company in all_companies:
            if person in cleaned_data and company in cleaned_data:
                # 检测：人员 -> 公司 (支出)
                df_person = cleaned_data[person]
                # 列名映射（中文列名兼容）
                counterparty_col = (
                    "交易对手" if "交易对手" in df_person.columns else "counterparty"
                )
                expense_col = (
                    "支出(元)" if "支出(元)" in df_person.columns else "expense"
                )
                income_col = "收入(元)" if "收入(元)" in df_person.columns else "income"
                description_col = (
                    "交易摘要" if "交易摘要" in df_person.columns else "description"
                )
                transfers_out = df_person[
                    df_person[counterparty_col].str.contains(
                        re.escape(company), na=False, regex=True
                    )
                ]
                if not transfers_out.empty:
                    for _, row in transfers_out.iterrows():
                        amount = row.get(expense_col, 0)
                        # 简单的风险定级
                        if amount > config.INCOME_HIGH_RISK_MIN:
                            risk = "high"
                        elif amount > config.SUSPICION_MEDIUM_HIGH_AMOUNT:
                            risk = "medium"
                        else:
                            risk = "low"

                        # 提取上下文信息 (处理 category 类型和 NaN)
                        bank_val = row.get("银行来源", None)
                        source_val = row.get("数据来源", None)
                        bank = (
                            str(bank_val)
                            if bank_val is not None and str(bank_val) != "nan"
                            else ""
                        )
                        source_file = (
                            str(source_val)
                            if source_val is not None and str(source_val) != "nan"
                            else ""
                        )

                        results["direct_transfers"].append(
                            {
                                "person": person,
                                "company": company,
                                "date": row["date"],
                                "amount": amount,
                                "direction": "payment",  # 付款
                                "description": row.get(description_col, ""),
                                "bank": bank,
                                "source_file": source_file,
                                "risk_level": risk,
                                # Phase 0.2: 证据追溯字段
                                "evidence_refs": {
                                    "source_row_index": int(
                                        row.get("source_row_index", row.name)
                                    )
                                    if row.get("source_row_index") is not None
                                    else int(row.name) + 2,
                                    "transaction_id": str(row.get("transaction_id", ""))
                                    if row.get("transaction_id")
                                    else "",
                                    "balance_after": float(row.get("balance", 0))
                                    if row.get("balance")
                                    else 0.0,
                                    "channel": str(row.get("transaction_channel", ""))
                                    if row.get("transaction_channel")
                                    else "",
                                },
                            }
                        )

                # 检测：公司 -> 人员 (收入)
                df_company = cleaned_data[company]
                transfers_in = df_company[
                    df_company[counterparty_col].str.contains(
                        re.escape(person), na=False, regex=True
                    )
                ]
                if not transfers_in.empty:
                    for _, row in transfers_in.iterrows():
                        amount = row.get(income_col, 0)
                        # 简单的风险定级
                        if amount > config.INCOME_HIGH_RISK_MIN:
                            risk = "high"
                        elif amount > config.SUSPICION_MEDIUM_HIGH_AMOUNT:
                            risk = "medium"
                        else:
                            risk = "low"

                        # 提取上下文信息 (处理 category 类型和 NaN)
                        bank_val = row.get("银行来源", None)
                        source_val = row.get("数据来源", None)
                        bank = (
                            str(bank_val)
                            if bank_val is not None and str(bank_val) != "nan"
                            else ""
                        )
                        source_file = (
                            str(source_val)
                            if source_val is not None and str(source_val) != "nan"
                            else ""
                        )

                        results["direct_transfers"].append(
                            {
                                "person": person,
                                "company": company,
                                "date": row["date"],
                                "amount": amount,
                                "direction": "receive",  # 收款
                                "description": row.get(description_col, ""),
                                "bank": bank,
                                "source_file": source_file,
                                "risk_level": risk,
                                # Phase 0.2: 证据追溯字段
                                "evidence_refs": {
                                    "source_row_index": int(
                                        row.get("source_row_index", row.name)
                                    )
                                    if row.get("source_row_index") is not None
                                    else int(row.name) + 2,
                                    "transaction_id": str(row.get("transaction_id", ""))
                                    if row.get("transaction_id")
                                    else "",
                                    "balance_after": float(row.get("balance", 0))
                                    if row.get("balance")
                                    else 0.0,
                                    "channel": str(row.get("transaction_channel", ""))
                                    if row.get("transaction_channel")
                                    else "",
                                },
                            }
                        )

    # ============================
    # 3. 预留检测模块 (待后续实现)
    # ============================
    # 以下检测模块预留接口，待后续完善：
    #   - holiday: 节假日异常交易检测 (参考 holiday_utils.py)
    #   - fixed_frequency: 固定频率异常检测 (参考 config.FIXED_FREQUENCY_* 常量)
    # 实现时可参考 detect_cash_time_collision 和 detect_cross_entity_cash_collision 的模式

    total_found = len(results["cash_collisions"]) + len(results["direct_transfers"])
    logger.info(f"✓ 疑点检测完成，共发现 {total_found} 条有效线索")

    return results
