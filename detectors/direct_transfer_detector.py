"""
直接转账检测器 - DirectTransferDetector
检测核心人员与涉案公司之间的直接资金往来。
"""

from typing import Dict, List, Any, Tuple

import utils
from detectors.base_detector import BaseDetector
from utils.suspicion_text import (
    build_direct_transfer_dedupe_key,
    score_direct_transfer_record,
)


class DirectTransferDetector(BaseDetector):
    """检测核心人员与涉案公司之间的直接资金往来。

    该检测器分析交易数据，识别核心人员向涉案公司转账或
    从涉案公司收款的交易记录，这类直接往来可能表明利益输送。
    """

    @property
    def name(self) -> str:
        return "direct_transfer"

    @property
    def description(self) -> str:
        return "检测核心人员与涉案公司之间的直接资金往来"

    @property
    def risk_level(self) -> str:
        return "高"

    @staticmethod
    def _pick_column(row: Any, *candidates: str) -> str:
        available = row.columns if hasattr(row, "columns") else row.index
        for column in candidates:
            if column in available:
                return column
        return ""

    @staticmethod
    def _safe_text(value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        return "" if text == "nan" else text

    def _extract_amount_and_direction(
        self, row: Any, account_role: str
    ) -> Tuple[float, str]:
        income_col = self._pick_column(row, "income", "收入(元)")
        expense_col = self._pick_column(row, "expense", "支出(元)")
        amount_col = self._pick_column(row, "amount", "交易金额")

        income = utils.format_amount(row.get(income_col, 0)) if income_col else 0.0
        expense = utils.format_amount(row.get(expense_col, 0)) if expense_col else 0.0

        if income > 0 and income >= expense:
            return (
                income,
                "receive" if account_role == "person" else "payment",
            )
        if expense > 0:
            return (
                expense,
                "payment" if account_role == "person" else "receive",
            )

        if amount_col:
            raw_amount = utils.format_amount(row.get(amount_col, 0))
            if raw_amount > 0:
                return (
                    raw_amount,
                    "receive" if account_role == "person" else "payment",
                )
            if raw_amount < 0:
                return (
                    abs(raw_amount),
                    "payment" if account_role == "person" else "receive",
                )

        return 0.0, ""

    @staticmethod
    def _classify_risk(
        amount: float, high_threshold: float, medium_threshold: float
    ) -> str:
        if amount > high_threshold:
            return "high"
        if amount > medium_threshold:
            return "medium"
        return "low"

    def _build_result(
        self,
        person: str,
        company: str,
        row: Any,
        account_role: str,
        high_threshold: float,
        medium_threshold: float,
    ) -> Dict[str, Any]:
        amount, direction = self._extract_amount_and_direction(row, account_role)
        if amount <= 0 or not direction:
            return {}

        bank_col = self._pick_column(row, "银行来源", "bank")
        source_col = self._pick_column(row, "数据来源", "source_file")
        description_col = self._pick_column(row, "description", "交易摘要")
        balance_col = self._pick_column(row, "balance", "余额(元)")
        date_col = self._pick_column(row, "date", "交易时间")
        tx_id_col = self._pick_column(row, "transaction_id", "流水号")
        channel_col = self._pick_column(row, "transaction_channel", "交易渠道")
        source_row_col = self._pick_column(row, "source_row_index")

        source_row_index = row.get(source_row_col) if source_row_col else None
        if source_row_index is None:
            source_row_index = row.name

        return {
            "person": person,
            "company": company,
            "date": row.get(date_col) if date_col else row.get("date"),
            "amount": amount,
            "direction": direction,
            "description": self._safe_text(row.get(description_col, "")),
            "bank": self._safe_text(row.get(bank_col, "")),
            "source_file": self._safe_text(row.get(source_col, "")),
            "risk_level": self._classify_risk(
                amount, high_threshold, medium_threshold
            ),
            "evidence_refs": {
                "source_row_index": int(source_row_index)
                if source_row_index is not None
                else int(row.name) + 2,
                "transaction_id": self._safe_text(row.get(tx_id_col, "")),
                "balance_after": utils.format_amount(row.get(balance_col, 0)),
                "channel": self._safe_text(row.get(channel_col, "")),
            },
        }

    def _iter_matches(self, df: Any, target: str):
        counterparty_col = self._pick_column(df, "counterparty", "交易对手")
        if not counterparty_col:
            return []
        return df[
            df[counterparty_col].astype(str).str.contains(
                target, na=False, regex=False
            )
        ].iterrows()

    def detect(
        self, data: Dict[str, Any], config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行直接资金往来检测。

        Args:
            data: 包含交易数据的字典
                - cleaned_data: 清洗后的交易数据 {entity_name: DataFrame}
                - all_persons: 所有核心人员名单
                - all_companies: 所有涉案公司名单
            config: 检测配置参数
                - income_high_risk_min: 高风险收入阈值（默认50000）
                - suspicion_medium_high_amount: 中高风险金额阈值（默认20000）

        Returns:
            List[Dict]: 检测到的直接资金往来列表
        """
        cleaned_data = data.get("cleaned_data", {})
        all_persons = data.get("all_persons", [])
        all_companies = data.get("all_companies", [])

        income_high_risk_min = config.get("income_high_risk_min", 50000)
        suspicion_medium_high_amount = config.get("suspicion_medium_high_amount", 20000)

        results_by_key: Dict[Tuple[str, str, str, float, str, str], Dict[str, Any]] = {}
        record_roles: Dict[Tuple[str, str, str, float, str, str], str] = {}
        ordered_keys: List[Tuple[str, str, str, float, str, str]] = []

        # 检测核心人员与涉案公司之间的直接资金往来
        for person in all_persons:
            for company in all_companies:
                # 个人账户视角
                if person in cleaned_data:
                    df_person = cleaned_data[person]
                    for _, row in self._iter_matches(df_person, company):
                        record = self._build_result(
                            person,
                            company,
                            row,
                            "person",
                            income_high_risk_min,
                            suspicion_medium_high_amount,
                        )
                        if not record:
                            continue
                        dedupe_key = build_direct_transfer_dedupe_key(
                            person,
                            company,
                            record["direction"],
                            record["amount"],
                            self._safe_text(record.get("date")),
                            record["description"],
                            record.get("bank", ""),
                        )
                        existing = results_by_key.get(dedupe_key)
                        if existing is None:
                            results_by_key[dedupe_key] = record
                            record_roles[dedupe_key] = "person"
                            ordered_keys.append(dedupe_key)
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
                            account_role=record_roles.get(dedupe_key, ""),
                        ):
                            results_by_key[dedupe_key] = record
                            record_roles[dedupe_key] = "person"

                # 公司账户视角
                if company in cleaned_data:
                    df_company = cleaned_data[company]
                    for _, row in self._iter_matches(df_company, person):
                        record = self._build_result(
                            person,
                            company,
                            row,
                            "company",
                            income_high_risk_min,
                            suspicion_medium_high_amount,
                        )
                        if not record:
                            continue
                        dedupe_key = build_direct_transfer_dedupe_key(
                            person,
                            company,
                            record["direction"],
                            record["amount"],
                            self._safe_text(record.get("date")),
                            record["description"],
                            record.get("bank", ""),
                        )
                        existing = results_by_key.get(dedupe_key)
                        if existing is None:
                            results_by_key[dedupe_key] = record
                            record_roles[dedupe_key] = "company"
                            ordered_keys.append(dedupe_key)
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
                            account_role=record_roles.get(dedupe_key, ""),
                        ):
                            results_by_key[dedupe_key] = record
                            record_roles[dedupe_key] = "company"

        return [results_by_key[key] for key in ordered_keys]
