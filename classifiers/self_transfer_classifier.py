"""Self-transfer classifier

Identifies transfers that occur between accounts belonging to the same owner.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class TransferTransaction:
    id: str
    from_account_id: Optional[str] = None
    to_account_id: Optional[str] = None
    from_owner_id: Optional[str] = None
    to_owner_id: Optional[str] = None


class SelfTransferClassifier:
    """Simple heuristic to detect self-transfers within the same owner."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _get_attr(txn: Any, key: str) -> Any:
        if isinstance(txn, dict):
            return txn.get(key)
        return getattr(txn, key, None)

    def classify(self, txn: Any) -> Dict[str, Any]:
        from_owner = self._get_attr(txn, 'from_owner_id')
        to_owner = self._get_attr(txn, 'to_owner_id')
        is_self = bool(from_owner) and bool(to_owner) and str(from_owner) == str(to_owner)
        return {
            'is_self_transfer': is_self,
            'details': {
                'from_owner_id': from_owner,
                'to_owner_id': to_owner,
            }
        }

    def is_self_transfer(self, txn: Any) -> bool:
        return self.classify(txn).get('is_self_transfer', False)
