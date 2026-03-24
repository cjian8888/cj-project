"""Unified category engine

Orchestrates the three classifiers in a defined priority order and
exposes a single entry point to classify a transaction record.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .wealth_classifier import WealthClassifier
from .salary_classifier import SalaryClassifier
from .self_transfer_classifier import SelfTransferClassifier


class CategoryEngine:
    """Unified entry point for classification with simple priority rules."""

    def __init__(self,
                 wealth_classifier: Optional[WealthClassifier] = None,
                 salary_classifier: Optional[SalaryClassifier] = None,
                 self_transfer_classifier: Optional[SelfTransferClassifier] = None) -> None:
        self.wealth_classifier = wealth_classifier
        self.salary_classifier = salary_classifier
        self.self_transfer_classifier = self_transfer_classifier

    def _to_dict(self, txn: Any) -> Dict[str, Any]:
        if isinstance(txn, dict):
            return txn
        return txn.__dict__ if hasattr(txn, '__dict__') else {}

    def classify(self, txn: Any) -> Dict[str, Any]:
        """Classify a transaction by priority: wealth, salary, then self-transfer."""
        data = self._to_dict(txn)

        # Wealth first
        if self.wealth_classifier is not None:
            try:
                w = self.wealth_classifier.is_wealth(txn if isinstance(txn, object) else data)
                if w:
                    return {'category': 'wealth', 'confidence': 0.8, 'source': 'WealthClassifier'}
            except Exception:
                pass

        # Salary second
        if self.salary_classifier is not None:
            try:
                if self.salary_classifier.is_salary(txn if isinstance(txn, object) else data):
                    return {'category': 'salary', 'confidence': 0.6, 'source': 'SalaryClassifier'}
            except Exception:
                pass

        # Self-transfer third
        if self.self_transfer_classifier is not None:
            try:
                if self.self_transfer_classifier.is_self_transfer(txn if isinstance(txn, object) else data):
                    return {'category': 'self_transfer', 'confidence': 0.7, 'source': 'SelfTransferClassifier'}
            except Exception:
                pass

        return {'category': 'unknown', 'confidence': 0.0, 'source': 'CategoryEngine'}
