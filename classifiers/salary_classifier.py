"""Salary (工资) classifier

Implements wage recognition without keyword reliance.
- Periodicity detection (monthly payroll window)
- Amount stability check (variation <= 30%)
- Payroll source flag
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import datetime


@dataclass
class SalaryTransaction:
    """Minimal transaction data suitable for salary detection."""
    id: str
    amount: Optional[float] = None
    date: Optional[str] = None  # ISO-formatted date: 'YYYY-MM-DD'
    amount_history: Optional[List[float]] = None
    repeat_interval: Optional[str] = None  # e.g., 'monthly'
    is_salary_source: Optional[bool] = None
    notes: Optional[str] = None


class SalaryClassifier:
    """Determines if a transaction is salary related based on cadence and stability."""

    def __init__(self, expected_payday: int = 25, tolerance_days: int = 2,
                 stability_ratio: float = 0.3) -> None:
        self.expected_payday = int(expected_payday)
        self.tolerance_days = int(tolerance_days)
        self.stability_ratio = float(stability_ratio)

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime.date]:
        if not date_str:
            return None
        try:
            return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            return None

    def _is_payday(self, date_str: Optional[str]) -> bool:
        d = self._parse_date(date_str)
        if not d:
            return False
        return abs(d.day - self.expected_payday) <= self.tolerance_days

    @staticmethod
    def _get_attr(txn: Any, key: str) -> Any:
        if isinstance(txn, dict):
            return txn.get(key)
        return getattr(txn, key, None)

    @staticmethod
    def _mean(nums: List[float]) -> float:
        return sum(nums) / len(nums) if nums else 0.0

    @staticmethod
    def _is_stable(history: List[float], ratio: float) -> bool:
        if not history or len(history) < 3:
            return False
        mean = SalaryClassifier._mean(history)
        if mean == 0:
            return False
        min_v = min(history)
        max_v = max(history)
        return (max_v - min_v) <= (ratio * mean)

    def classify(self, txn: SalaryTransaction) -> Dict[str, Any]:
        """Classify the transaction as salary-related and provide rationale."""
        # Duck-typing access for date/history
        date_str = self._get_attr(txn, 'date') if not isinstance(txn, dict) else txn.get('date')
        history = self._get_attr(txn, 'amount_history') if not isinstance(txn, dict) else txn.get('amount_history', []) or []
        is_payday = self._is_payday(date_str)
        is_stable = self._is_stable(history, self.stability_ratio)
        is_source = bool(self._get_attr(txn, 'is_salary_source') if not isinstance(txn, dict) else txn.get('is_salary_source', False))

        is_salary = any([is_payday, is_stable, is_source])
        details = {
            'is_payday': is_payday,
            'is_stable': is_stable,
            'is_source_flag': is_source,
            'amount_history_length': len(history),
        }
        return {
            'is_salary': is_salary,
            'details': details,
            'thresholds': {
                'payday': self.expected_payday,
                'tolerance_days': self.tolerance_days,
                'stability_ratio': self.stability_ratio,
            },
        }

    def is_salary(self, txn: SalaryTransaction) -> bool:
        return self.classify(txn).get('is_salary', False)
