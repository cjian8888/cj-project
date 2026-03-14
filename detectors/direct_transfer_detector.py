"""
直接转账检测器 - DirectTransferDetector
检测核心人员与涉案公司之间的直接资金往来。
"""

from typing import Dict, List, Any

import utils
from detectors.base_detector import BaseDetector


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

        results = []

        # 检测核心人员与涉案公司之间的直接资金往来
        for person in all_persons:
            for company in all_companies:
                if person not in cleaned_data or company not in cleaned_data:
                    continue

                # 检测：人员 -> 公司 (支出)
                df_person = cleaned_data[person]
                transfers_out = df_person[
                    df_person["counterparty"].astype(str).str.contains(
                        company, na=False, regex=False
                    )
                ]

                for _, row in transfers_out.iterrows():
                    amount = utils.format_amount(row.get("expense", 0))

                    # 风险定级
                    if amount > income_high_risk_min:
                        risk = "high"
                    elif amount > suspicion_medium_high_amount:
                        risk = "medium"
                    else:
                        risk = "low"

                    # 提取上下文信息
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

                    results.append(
                        {
                            "person": person,
                            "company": company,
                            "date": row["date"],
                            "amount": amount,
                            "direction": "payment",
                            "description": row.get("description", ""),
                            "bank": bank,
                            "source_file": source_file,
                            "risk_level": risk,
                            "evidence_refs": {
                                "source_row_index": int(
                                    row.get("source_row_index", row.name)
                                )
                                if row.get("source_row_index") is not None
                                else int(row.name) + 2,
                                "transaction_id": str(row.get("transaction_id", ""))
                                if row.get("transaction_id")
                                else "",
                                "balance_after": utils.format_amount(
                                    row.get("balance", 0)
                                ),
                                "channel": str(row.get("transaction_channel", ""))
                                if row.get("transaction_channel")
                                else "",
                            },
                        }
                    )

                # 检测：公司 -> 人员 (收入)
                df_company = cleaned_data[company]
                transfers_in = df_company[
                    df_company["counterparty"].astype(str).str.contains(
                        person, na=False, regex=False
                    )
                ]

                for _, row in transfers_in.iterrows():
                    amount = utils.format_amount(row.get("income", 0))

                    # 风险定级
                    if amount > income_high_risk_min:
                        risk = "high"
                    elif amount > suspicion_medium_high_amount:
                        risk = "medium"
                    else:
                        risk = "low"

                    # 提取上下文信息
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

                    results.append(
                        {
                            "person": person,
                            "company": company,
                            "date": row["date"],
                            "amount": amount,
                            "direction": "receive",
                            "description": row.get("description", ""),
                            "bank": bank,
                            "source_file": source_file,
                            "risk_level": risk,
                            "evidence_refs": {
                                "source_row_index": int(
                                    row.get("source_row_index", row.name)
                                )
                                if row.get("source_row_index") is not None
                                else int(row.name) + 2,
                                "transaction_id": str(row.get("transaction_id", ""))
                                if row.get("transaction_id")
                                else "",
                                "balance_after": utils.format_amount(
                                    row.get("balance", 0)
                                ),
                                "channel": str(row.get("transaction_channel", ""))
                                if row.get("transaction_channel")
                                else "",
                            },
                        }
                    )

        return results
