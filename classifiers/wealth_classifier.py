"""Wealth (理财) classifier

Implements a 6-dimension wealth recognition logic:
- Product name matching (using learners results)
- Bank internal code matching
- Product code prefix matching
- Buy-Hold/Buy-Sell pairing
- Counterparty empty + round amount + money flow back
- Wealth keywords matching
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import datetime


@dataclass
class Transaction:
    """Minimal representation of a transaction record used by classifiers."""

    id: str
    product_name: Optional[str] = None
    bank_code: Optional[str] = None
    product_code: Optional[str] = None
    amount: Optional[float] = None
    counterparty: Optional[str] = None
    direction: str = "out"  # 'out' or 'in'
    notes: Optional[str] = None
    date: Optional[str] = None  # ISO-like date, e.g., '2026-02-20'
    buy_id: Optional[str] = None
    sell_id: Optional[str] = None
    is_return_flow: bool = False
    amount_history: Optional[List[float]] = None
    repeat_interval: Optional[str] = None
    from_account_id: Optional[str] = None
    to_account_id: Optional[str] = None
    from_owner_id: Optional[str] = None
    to_owner_id: Optional[str] = None
    is_salary_source: Optional[bool] = None
    # Learner results can influence classification heuristics
    learners_results: Optional[Dict[str, List[str]]] = None


class WealthClassifier:
    """Encapsulates 6-dimension wealth recognition logic."""

    # Knowledge-base based constants
    WEALTH_NAME_TERMS = [
        "理财",
        "财富管理",
        "投资",
        "基金",
        "资产配置",
        "理财产品",
        "理财产品",
        "投資",
    ]
    BANK_WEALTH_CODES = {"WB01", "WB02", "WB03", "WB04"}
    CODE_PREFIXES = ("PF", "WP", "INV", "PRD")
    WEALTH_KEYWORDS = ["定投", "分红", "收益", "收益率"]

    def __init__(
        self,
        threshold: int = 4,
        learners_results: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.threshold = threshold
        self.learners_results = learners_results or {}

    # Internal helpers
    @staticmethod
    def _get_attr(txn: Any, key: str) -> Any:
        if isinstance(txn, dict):
            return txn.get(key)
        return getattr(txn, key, None)

    def _match_product_name(self, txn: Transaction) -> bool:
        name = self._get_attr(txn, "product_name") or ""
        # Prioritize explicit learner results if provided
        if self.learners_results and "wealth" in self.learners_results:
            for v in self.learners_results["wealth"]:
                if v and v in name:
                    return True
        for term in self.WEALTH_NAME_TERMS:
            if term in name:
                return True
        return False

    def _match_bank_code(self, txn: Transaction) -> bool:
        code = self._get_attr(txn, "bank_code")
        return isinstance(code, str) and code in self.BANK_WEALTH_CODES

    def _match_code_prefix(self, txn: Transaction) -> bool:
        code = self._get_attr(txn, "product_code")
        if not isinstance(code, str):
            return False
        return any(code.startswith(p) for p in self.CODE_PREFIXES)

    def _pair_buy_sell(self, txn: Transaction) -> bool:
        return bool(self._get_attr(txn, "buy_id") and self._get_attr(txn, "sell_id"))

    def _empty_counterparty_and_round(self, txn: Transaction) -> bool:
        counterparty = self._get_attr(txn, "counterparty")
        amount = self._get_attr(txn, "amount")
        if counterparty:
            return False
        if amount is not None and isinstance(amount, (int, float)):
            # Check for round amount (multiples of 10000)
            return int(abs(amount)) % 10000 == 0
        return False

    def _keywords_match(self, txn: Transaction) -> bool:
        notes = self._get_attr(txn, "notes") or ""
        if self.learners_results and "wealth" in self.learners_results:
            for v in self.learners_results["wealth"]:
                if v and v in notes:
                    return True
        for kw in self.WEALTH_KEYWORDS:
            if kw in notes:
                return True
        return False

    def classify(self, txn: Transaction) -> Dict[str, Any]:
        """Compute 6 binary signals and aggregate a score.

        Returns a dictionary with a score (0-6) and detailed flags.
        The higher the score, the more likely the transaction is wealth-related.
        """
        flags = {
            "product_name_match": self._match_product_name(txn),
            "bank_code_match": self._match_bank_code(txn),
            "code_prefix_match": self._match_code_prefix(txn),
            "buy_sell_pair": self._pair_buy_sell(txn),
            "empty_counterparty_and_round": self._empty_counterparty_and_round(txn),
            "keywords_match": self._keywords_match(txn),
        }
        score = sum(1 for v in flags.values() if v)
        return {
            "score": score,
            "threshold": self.threshold,
            "flags": flags,
        }

    def is_wealth(self, txn: Transaction) -> bool:
        """Shorthand: True if classify(txn).score >= threshold."""
        return self.classify(txn).get("score", 0) >= self.threshold
