from __future__ import annotations

"""ProductNameLearner: 提取从理财数据中的产品名称关键词"""
import os
import json
import re
from typing import List, Set, Optional

import pandas as pd
import pandas.core.frame  # for type hints compatibility


class ProductNameLearner:
    """学习器从理财数据中提取可复用的产品名称关键词"""

    def __init__(self, output_dir: str = "output/learned") -> None:
        self.output_dir: str = output_dir
        self.keywords: Set[str] = set()
        os.makedirs(self.output_dir, exist_ok=True)

    def _extract_keywords(self, text_values: List[str]) -> Set[str]:
        keywords: Set[str] = set()
        for text in text_values:
            if not isinstance(text, str):
                text = str(text)
            # Simple tokenization: split by non-alphanumeric characters and Chinese characters
            for token in re.split(r"[^A-Za-z0-9\u4e00-\u9fff]+", text):
                if not token:
                    continue
                t = token.strip().lower()
                # keep reasonably long tokens as keywords
                if 2 <= len(t) <= 50:
                    keywords.add(t)
        return keywords

    def learn_from_wealth_excel(self, excel_path: str) -> Set[str]:
        """从理财Excel提取名为 '产品名称' 的列中的关键词"""
        if not os.path.isfile(excel_path):
            raise FileNotFoundError(f"Excel not found: {excel_path}")
        df = pd.read_excel(excel_path)
        col: Optional[str] = None
        if "产品名称" in df.columns:
            col = "产品名称"
        elif "Product Name" in df.columns:
            col = "Product Name"
        else:
            # 尝试选择首个文本列作为兜底
            text_cols = [c for c in df.columns if df[c].dtype == object]
            col = text_cols[0] if text_cols else None
        if col is None:
            raise ValueError("No suitable product name column found in Excel.")
        values = df[col].astype(str).dropna().tolist()
        self.keywords = self._extract_keywords(values)
        return self.keywords

    def save_learned_keywords(self, path: Optional[str] = None) -> str:
        """将学习到的关键词保存为 JSON 文件"""
        target_path = path or os.path.join(self.output_dir, "product_keywords.json")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        data = sorted(list(self.keywords))
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump({"keywords": data}, f, ensure_ascii=False, indent=2)
        return target_path
