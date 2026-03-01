"""
现金碰撞检测器 - CashCollisionDetector
检测现金时空伴随模式，包括单实体内和跨实体的现金取存配对。
"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np

from detectors.base_detector import BaseDetector


class CashCollisionDetector(BaseDetector):
    """检测现金时空伴随模式。

    该检测器分析现金交易记录，识别短时间内发生的取现和存现配对，
    包括单实体内的现金碰撞和跨实体的现金碰撞模式。
    """

    @property
    def name(self) -> str:
        return "cash_collision"

    @property
    def description(self) -> str:
        return "检测现金时空伴随模式，识别取现和存现的时间金额配对"

    @property
    def risk_level(self) -> str:
        return "高"

    def detect(
        self, data: Dict[str, Any], config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行现金碰撞检测。

        Args:
            data: 包含交易数据的字典
                - cleaned_data: 清洗后的交易数据 {entity_name: DataFrame}
                - all_persons: 所有核心人员名单
                - all_companies: 所有涉案公司名单
            config: 检测配置参数
                - cash_time_window_hours: 现金碰撞时间窗口（小时，默认48）
                - amount_tolerance_ratio: 金额容差比例（默认0.05）

        Returns:
            List[Dict]: 检测到的现金碰撞列表
        """
        cleaned_data = data.get("cleaned_data", {})

        cash_time_window_hours = config.get("cash_time_window_hours", 48)
        amount_tolerance_ratio = config.get("amount_tolerance_ratio", 0.05)

        results = []

        # 收集所有实体的取现和存现记录
        all_withdrawals = []
        all_deposits = []

        for entity_name, df in cleaned_data.items():
            if df.empty:
                continue

            # 提取现金交易
            cash_df = self._get_cash_transactions(df)
            if cash_df.empty:
                continue

            # 拆分为取现和存现
            withdrawals, deposits = self._split_cash_transactions(cash_df)

            # 单实体内检测
            single_collisions = self._detect_single_entity_collision(
                withdrawals,
                deposits,
                entity_name,
                cash_time_window_hours,
                amount_tolerance_ratio,
            )
            results.extend(single_collisions)

            # 收集用于跨实体检测
            all_withdrawals.extend(self._extract_records(withdrawals, entity_name))
            all_deposits.extend(self._extract_records(deposits, entity_name))

        # 跨实体检测
        if all_withdrawals and all_deposits:
            cross_collisions = self._detect_cross_entity_collision(
                all_withdrawals,
                all_deposits,
                cash_time_window_hours,
                amount_tolerance_ratio,
            )
            results.extend(cross_collisions)

        return results

    def _get_cash_transactions(self, df: pd.DataFrame) -> pd.DataFrame:
        """从DataFrame中提取现金交易记录。

        优先级：
        1. is_cash列（布尔类型）
        2. 现金列（字符串'是'）
        3. 降级：关键词匹配
        """
        if "is_cash" in df.columns:
            return df[df["is_cash"] == True].copy()
        elif "现金" in df.columns:
            return df[df["现金"] == "是"].copy()
        else:
            # 降级：关键词匹配
            def is_cash_by_keyword(row):
                desc = str(row.get("description", "")).lower()
                cash_keywords = ["atm", "现金", "取现", "存款", "withdrawal", "deposit"]
                for kw in cash_keywords:
                    if kw in desc:
                        return True
                return False

            return df[df.apply(is_cash_by_keyword, axis=1)].copy()

    def _split_cash_transactions(self, cash_df: pd.DataFrame) -> tuple:
        """将现金交易拆分为取现和存现。"""
        # 如果有income/expense列
        if "income" in cash_df.columns and "expense" in cash_df.columns:
            withdrawals = cash_df[cash_df["expense"] > 0].copy()
            deposits = cash_df[cash_df["income"] > 0].copy()
            withdrawals["amount"] = withdrawals["expense"]
            deposits["amount"] = deposits["income"]
        else:
            # 只有单列amount的情况（负数为支出）
            withdrawals = cash_df[cash_df["amount"] < 0].copy()
            deposits = cash_df[cash_df["amount"] > 0].copy()
            withdrawals["amount"] = withdrawals["amount"].abs()

        return withdrawals, deposits

    def _extract_records(self, df: pd.DataFrame, entity_name: str) -> List[Dict]:
        """提取记录用于跨实体检测。"""
        records = []
        for _, row in df.iterrows():
            bank_val = row.get("银行来源", row.get("bank", ""))
            source_val = row.get("数据来源", row.get("source_file", ""))
            records.append(
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
                    "source_row_index": row.get("source_row_index", None),
                }
            )
        return records

    def _detect_single_entity_collision(
        self,
        withdrawals: pd.DataFrame,
        deposits: pd.DataFrame,
        entity_name: str,
        time_window_hours: float,
        amount_tolerance: float,
    ) -> List[Dict]:
        """检测单实体内的现金碰撞（索引join优化版，避免笛卡尔积）。"""
        collisions = []

        if withdrawals.empty or deposits.empty:
            return collisions

        # 准备数据
        wd = withdrawals.copy()
        dp = deposits.copy()

        # 确保日期列为datetime类型
        wd["date"] = pd.to_datetime(wd["date"])
        dp["date"] = pd.to_datetime(dp["date"])

        # 填充金额NaN
        wd["amount"] = wd["amount"].fillna(0)
        dp["amount"] = dp["amount"].fillna(0)

        # 按时间排序以优化搜索
        wd = wd.sort_values("date").reset_index(drop=True)
        dp = dp.sort_values("date").reset_index(drop=True)

        # 使用双指针算法，避免笛卡尔积
        # 对于每个取款，只查找时间窗口内的存款
        time_window_td = pd.Timedelta(hours=time_window_hours)

        wd_records = wd.to_dict("records")
        dp_records = dp.to_dict("records")

        for wd_record in wd_records:
            wd_date = wd_record["date"]
            wd_amount = wd_record["amount"]

            if wd_amount <= 0:
                continue

            for dp_record in dp_records:
                dp_date = dp_record["date"]
                dp_amount = dp_record["amount"]

                if dp_amount <= 0:
                    continue

                # 计算时间差
                time_diff = abs((dp_date - wd_date).total_seconds() / 3600)

                # 如果时间差超过窗口，跳过（由于已排序，可以提前终止）
                if dp_date > wd_date + time_window_td:
                    break
                if time_diff > time_window_hours:
                    continue

                # 计算金额差异
                amount_diff_abs = abs(wd_amount - dp_amount)
                amount_ratio = amount_diff_abs / wd_amount if wd_amount > 0 else 1.0

                # 应用阈值筛选
                if amount_ratio > amount_tolerance:
                    continue

                # 确定风险等级
                if time_diff < 4 and amount_ratio < 0.01:
                    risk = "high"
                elif time_diff < 24:
                    risk = "medium"
                else:
                    risk = "low"

                collisions.append(
                    {
                        "type": "single_entity",
                        "withdrawal_entity": entity_name,
                        "deposit_entity": entity_name,
                        "withdrawal_date": wd_date,
                        "deposit_date": dp_date,
                        "withdrawal_bank": wd_record.get("银行来源", "未知"),
                        "deposit_bank": dp_record.get("银行来源", "未知"),
                        "withdrawal_source": wd_record.get("数据来源", "未知"),
                        "deposit_source": dp_record.get("数据来源", "未知"),
                        "time_diff_hours": round(time_diff, 2),
                        "withdrawal_amount": wd_amount,
                        "deposit_amount": dp_amount,
                        "amount_diff": round(amount_diff_abs, 2),
                        "amount_diff_ratio": round(amount_ratio, 2),
                        "risk_level": risk,
                        "risk_reason": f"取现{wd_amount}元与存现{dp_amount}元时间间隔{time_diff:.1f}小时内，金额接近",
                    }
                )

        return collisions

    def _detect_cross_entity_collision(
        self,
        all_withdrawals: List[Dict],
        all_deposits: List[Dict],
        time_window_hours: float,
        amount_tolerance: float,
    ) -> List[Dict]:
        """检测跨实体的现金碰撞。"""
        collisions = []

        if not all_withdrawals or not all_deposits:
            return collisions

        # 按时间排序以优化搜索
        sorted_withdrawals = sorted(all_withdrawals, key=lambda x: x["date"])
        sorted_deposits = sorted(all_deposits, key=lambda x: x["date"])

        for wd in sorted_withdrawals:
            wd_entity = wd["entity"]
            wd_date = wd["date"]
            wd_amount = wd["amount"]

            for dp in sorted_deposits:
                dp_entity = dp["entity"]
                dp_date = dp["date"]
                dp_amount = dp["amount"]

                # 跳过同一实体
                if wd_entity == dp_entity:
                    continue

                # 存现应在取现之后
                if dp_date < wd_date:
                    continue

                # 计算时间差
                time_diff = (dp_date - wd_date).total_seconds() / 3600

                if time_diff > time_window_hours:
                    continue

                # 检查金额匹配
                amount_diff = abs(wd_amount - dp_amount)
                amount_ratio = amount_diff / wd_amount if wd_amount > 0 else 1.0

                if amount_ratio <= amount_tolerance:
                    # 判断风险等级
                    if time_diff < 2 and amount_ratio < 0.01:
                        risk = "high"
                        risk_desc = "极高相关性"
                    elif time_diff < 12 and amount_ratio < 0.05:
                        risk = "high"
                        risk_desc = "高度可疑"
                    elif time_diff < 24:
                        risk = "medium"
                        risk_desc = "需进一步核查"
                    else:
                        risk = "low"
                        risk_desc = "可能巧合"

                    collisions.append(
                        {
                            "type": "cross_entity",
                            "withdrawal_entity": wd_entity,
                            "deposit_entity": dp_entity,
                            "withdrawal_date": wd_date,
                            "deposit_date": dp_date,
                            "withdrawal_amount": wd_amount,
                            "deposit_amount": dp_amount,
                            "withdrawal_bank": wd.get("bank", "未知"),
                            "deposit_bank": dp.get("bank", "未知"),
                            "withdrawal_source": wd.get("source_file", ""),
                            "deposit_source": dp.get("source_file", ""),
                            "withdrawal_row": wd.get("source_row_index", None),
                            "deposit_row": dp.get("source_row_index", None),
                            "time_diff_hours": round(time_diff, 2),
                            "amount_diff": round(amount_diff, 2),
                            "amount_diff_ratio": round(amount_ratio, 4),
                            "risk_level": risk,
                            "risk_reason": f"[跨实体] {wd_entity}取现{wd_amount / 10000:.2f}万 → {dp_entity}存现{dp_amount / 10000:.2f}万, 时差{time_diff:.1f}小时, {risk_desc}",
                        }
                    )

        return collisions
