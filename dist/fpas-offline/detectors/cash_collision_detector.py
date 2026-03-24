"""
现金碰撞检测器 - CashCollisionDetector
检测现金时空伴随模式，包括单实体内和跨实体的现金取存配对。
"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np

from detectors.base_detector import BaseDetector
import utils


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

    @staticmethod
    def _pick_column(
        container: Any, *candidates: str, is_amount_field: bool = False
    ) -> str:
        columns = getattr(container, "columns", None)
        if columns is not None:
            return (
                utils.find_first_matching_column(
                    container,
                    list(candidates),
                    is_amount_field=is_amount_field,
                )
                or ""
            )

        available = getattr(container, "index", [])
        for column in candidates:
            if column in available:
                return column
        return ""

    @staticmethod
    def _safe_text(value: Any) -> str:
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass

        if value is None:
            return ""

        text = str(value).strip()
        return "" if text.lower() in {"nan", "none", "null"} else text

    def _normalize_cash_flag(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        text = self._safe_text(value).lower()
        return text in {"true", "1", "yes", "y", "是"}

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
        # 单实体自循环默认不进入风险主清单，避免“本人取现-本人存现”噪声淹没跨实体风险
        include_single_entity = bool(
            config.get("include_single_entity_collisions", False)
        )

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
            if include_single_entity:
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
            return df[df["is_cash"].apply(self._normalize_cash_flag)].copy()
        elif "现金" in df.columns:
            cash_flag = utils.normalize_text_series(df["现金"]).str.strip()
            return df[cash_flag.isin({"是", "true", "True", "1"})].copy()
        else:
            # 降级：关键词匹配
            def is_cash_by_keyword(row):
                desc_col = self._pick_column(row, "description", "交易摘要")
                desc = self._safe_text(row.get(desc_col, "") if desc_col else "").lower()
                cash_keywords = ["atm", "现金", "取现", "存款", "withdrawal", "deposit"]
                for kw in cash_keywords:
                    if kw in desc:
                        return True
                return False

            return df[df.apply(is_cash_by_keyword, axis=1)].copy()

    def _split_cash_transactions(self, cash_df: pd.DataFrame) -> tuple:
        """将现金交易拆分为取现和存现。"""
        normalized = cash_df.copy()
        income_col = self._pick_column(
            normalized, "income", "收入(元)", is_amount_field=True
        )
        expense_col = self._pick_column(
            normalized, "expense", "支出(元)", is_amount_field=True
        )
        amount_col = self._pick_column(
            normalized, "amount", "交易金额", is_amount_field=True
        )

        if income_col:
            normalized["_cash_income"] = utils.normalize_amount_series(
                normalized[income_col].astype("object"), income_col
            )
        else:
            normalized["_cash_income"] = 0.0

        if expense_col:
            normalized["_cash_expense"] = utils.normalize_amount_series(
                normalized[expense_col].astype("object"), expense_col
            )
        else:
            normalized["_cash_expense"] = 0.0

        if income_col or expense_col:
            withdrawals = normalized[normalized["_cash_expense"] > 0].copy()
            deposits = normalized[normalized["_cash_income"] > 0].copy()
            withdrawals["amount"] = withdrawals["_cash_expense"]
            deposits["amount"] = deposits["_cash_income"]
        elif amount_col:
            normalized["_cash_amount"] = utils.normalize_amount_series(
                normalized[amount_col].astype("object"), amount_col
            )
            withdrawals = normalized[normalized["_cash_amount"] < 0].copy()
            deposits = normalized[normalized["_cash_amount"] > 0].copy()
            withdrawals["amount"] = withdrawals["_cash_amount"].abs()
            deposits["amount"] = deposits["_cash_amount"]
        else:
            return normalized.iloc[0:0].copy(), normalized.iloc[0:0].copy()

        return withdrawals, deposits

    def _extract_records(self, df: pd.DataFrame, entity_name: str) -> List[Dict]:
        """提取记录用于跨实体检测。"""
        records = []
        for _, row in df.iterrows():
            date_col = self._pick_column(row, "date", "交易时间", "交易日期", "日期")
            parsed_date = utils.parse_date(row.get(date_col) if date_col else None)
            if pd.isna(parsed_date):
                continue
            bank_col = self._pick_column(row, "银行来源", "bank", "所属银行")
            source_col = self._pick_column(row, "数据来源", "source_file")
            desc_col = self._pick_column(row, "description", "交易摘要")
            source_row_col = self._pick_column(row, "source_row_index")
            bank_val = row.get(bank_col, "") if bank_col else ""
            source_val = row.get(source_col, "") if source_col else ""
            records.append(
                {
                    "entity": entity_name,
                    "date": parsed_date,
                    "amount": utils.format_amount(row.get("amount", 0)),
                    "bank": self._safe_text(bank_val),
                    "source_file": self._safe_text(source_val),
                    "description": self._safe_text(
                        row.get(desc_col, "") if desc_col else ""
                    ),
                    "source_row_index": row.get(source_row_col, None)
                    if source_row_col
                    else None,
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
        wd["date"] = utils.normalize_datetime_series(wd["date"])
        dp["date"] = utils.normalize_datetime_series(dp["date"])

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

                # 单实体碰撞仅作为线索，不进入高/中风险主清单
                risk = "low"

                collisions.append(
                    {
                        "type": "single_entity",
                        "pattern_category": "self_cycle",
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
                        "risk_reason": (
                            f"[单实体线索] {entity_name}取现{wd_amount}元后"
                            f"{time_diff:.1f}小时存现{dp_amount}元，金额接近；"
                            "默认仅作资金循环线索。"
                        ),
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
