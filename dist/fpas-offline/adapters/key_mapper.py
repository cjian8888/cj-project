"""Key mapper: snake_case <-> camelCase with explicit KEY_MAPPING.

Maps specific known keys via KEY_MAPPING and recursively traverses nested dicts and lists.

NOTE: Only keys defined in KEY_MAPPING are remapped. Unmapped keys are kept as-is.

Usage example:
    from adapters.key_mapper import to_camel_case, to_snake_case
    data = {'cash_collisions': [{'amount': 1000}], 'direct_transfers': []}
    camel = to_camel_case(data)
    back = to_snake_case(camel)
    assert back == data
"""

from typing import Any, Dict, List

# Complete KEY_MAPPING dictionary
KEY_MAPPING: Dict[str, str] = {
    'cash_collisions': 'cashCollisions',
    'direct_transfers': 'directTransfers',
    'hidden_assets': 'hiddenAssets',
    'fixed_frequency': 'fixedFrequency',
    'cash_timing_patterns': 'cashTimingPatterns',
    'holiday_transactions': 'holidayTransactions',
    'amount_patterns': 'amountPatterns',
    'suspicion_type': 'suspicionType',
    'related_transactions': 'relatedTransactions',
    'risk_level': 'riskLevel',
    'total_income': 'totalIncome',
    'total_expense': 'totalExpense',
    'cash_ratio': 'cashRatio',
    'transaction_count': 'transactionCount',
}

# Build reverse mapping for camelCase -> snake_case
REVERSE_KEY_MAPPING: Dict[str, str] = {v: k for k, v in KEY_MAPPING.items()}


def _transform_with_mapping_key(key: str) -> str:
    """Get the mapped key using KEY_MAPPING, or return the original key if not mapped."""
    return KEY_MAPPING.get(key, key)


def _transform_with_reverse_mapping_key(key: str) -> str:
    """Get the snake_case key using the reverse mapping, or return the original key if not mapped."""
    return REVERSE_KEY_MAPPING.get(key, key)


def to_camel_case(obj: Any) -> Any:
    """Recursively convert all top-level and nested snake_case keys to camelCase.
    
    Uses the KEY_MAPPING dictionary. Values are preserved as-is (unless they are
    nested dict/list, in which case they are transformed recursively).
    
    Also converts numpy/pandas types to native Python types for JSON serialization.
    
    Args:
        obj: Input object (dict, list, or any other type)
        
    Returns:
        Transformed object with camelCase keys and JSON-serializable values
    """
    import numpy as np
    import pandas as pd
    from datetime import datetime
    
    # Handle numpy/pandas types first (before dict/list check)
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return to_camel_case(obj.tolist())
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    # Handle NaN/NaT - use try-except to avoid array ambiguity
    try:
        if pd.isna(obj):
            return None
    except (ValueError, TypeError):
        # pd.isna() raises ValueError for arrays, TypeError for some objects
        pass
    if isinstance(obj, dict):
        new_dict: Dict[str, Any] = {}
        for k, v in obj.items():
            mapped_key = _transform_with_mapping_key(k)
            # Always recurse to handle nested numpy types
            new_dict[mapped_key] = to_camel_case(v)
        return new_dict
    elif isinstance(obj, list):
        return [to_camel_case(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(to_camel_case(item) for item in obj)
    else:
        return obj


def to_snake_case(obj: Any) -> Any:
    """Recursively convert camelCase keys (as defined in KEY_MAPPING) back to snake_case.
    
    Unmapped camelCase keys remain as-is.
    
    Args:
        obj: Input object (dict, list, or any other type)
        
    Returns:
        Transformed object with snake_case keys
    """
    if isinstance(obj, dict):
        new_dict: Dict[str, Any] = {}
        for k, v in obj.items():
            snake_key = _transform_with_reverse_mapping_key(k)
            if isinstance(v, (dict, list)):
                new_dict[snake_key] = to_snake_case(v)
            else:
                new_dict[snake_key] = v
        return new_dict
    elif isinstance(obj, list):
        return [to_snake_case(item) for item in obj]
    else:
        return obj
