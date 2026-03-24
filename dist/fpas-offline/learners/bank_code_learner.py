from __future__ import annotations

"""BankCodeLearner: 提取银行交易中的数字摘要编码行为特征"""
import json
import os
from typing import Dict, Optional

import pandas as pd


class BankCodeLearner:
    """学习器从交易数据中提取纯数字摘要的模式和行为特征"""

    def __init__(self, output_dir: str = "output/learned") -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.codes: Dict[str, int] = {}

    def learn_from_transactions(self, df: pd.DataFrame) -> Dict[str, int]:
        """从 DataFrame 的交易数据中筛选摘要为纯数字的记录并聚合编码"""
        if df is None or not isinstance(df, pd.DataFrame):
            raise ValueError("df must be a pandas DataFrame.")
        if "摘要" not in df.columns:
            raise KeyError("DataFrame must contain '摘要' column.")

        mask = df["摘要"].astype(str).str.fullmatch(r"\d+")
        numeric_rows = df[mask]
        codes = numeric_rows["摘要"].astype(str).tolist()
        # 统计简单的出现次数，作为学习结果
        for code in codes:
            self.codes[code] = self.codes.get(code, 0) + 1
        return self.codes

    def save_learned_codes(self, path: Optional[str] = None) -> str:
        target_path = path or os.path.join(self.output_dir, "bank_codes.json")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump({"codes": self.codes}, f, ensure_ascii=False, indent=2)
        return target_path
