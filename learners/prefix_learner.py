from __future__ import annotations

"""PrefixLearner: 学习已知与新前缀，基于知识库和数据流提取前缀信息"""
import json
import os
from typing import Dict, Optional, Set

import yaml
import pandas as pd


class PrefixLearner:
    """从数据流中提取代码前缀，并对比已有前缀知识库，记录学习结果"""

    def __init__(self, knowledge_path: str = "knowledge/product_code_prefixes.yaml", output_dir: str = "output/learned") -> None:
        self.knowledge_path = knowledge_path
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.known_prefixes: Set[str] = set()
        self.learned_prefixes: Dict[str, int] = {}
        self._load_known_prefixes()

    def _load_known_prefixes(self) -> None:
        if not os.path.exists(self.knowledge_path):
            self.known_prefixes = set()
            return
        with open(self.knowledge_path, "r", encoding="utf-8") as f:
            data = json.load(f) if os.path.splitext(self.knowledge_path)[1] == ".json" else yaml.safe_load(f)  # type: ignore
        # unify to a set of prefixes
        if isinstance(data, dict):
            # support both {prefix: info} or {prefixes: [..]}
            if "prefixes" in data:
                prefixes = data.get("prefixes") or []
                self.known_prefixes = set(map(str, prefixes))
            else:
                self.known_prefixes = set(map(str, data.keys()))
        elif isinstance(data, list):
            self.known_prefixes = set(map(str, data))
        else:
            self.known_prefixes = set()

    def learn_from_flow(self, df: pd.DataFrame) -> Dict[str, int]:
        if df is None or not isinstance(df, pd.DataFrame):
            raise ValueError("df must be a pandas DataFrame.")
        # determine potential code column
        code_cols = ["代码", "product_code", "代码前缀", "productPrefix", "code"]
        col = next((c for c in code_cols if c in df.columns), None)
        if col is None:
            for c in df.columns:
                if df[c].dtype == object and df[c].str.match(r"^[A-Za-z0-9]+$").any():
                    col = c
                    break
        if col is None:
            raise ValueError("No suitable code column found.")

        learned: Dict[str, int] = {}
        for val in df[col]:
            if pd.isna(val):
                continue
            s = str(val)
            for L in range(3, 6):  # 3-5 chars prefixes
                if len(s) >= L:
                    prefix = s[:L]
                    learned[prefix] = learned.get(prefix, 0) + 1
                    # count only known prefixes for now; unknowns are tallied as is
        self.learned_prefixes = learned
        return learned

    def save_learned_prefixes(self, path: Optional[str] = None) -> str:
        target_path = path or os.path.join(self.output_dir, "product_prefixes.json")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump({"prefixes": self.learned_prefixes}, f, ensure_ascii=False, indent=2)
        return target_path
