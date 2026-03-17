#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utils package - re-exports from utils.py module
"""

# Import all from the parent utils.py module
import sys
import os

# Add parent directory to path temporarily to import utils.py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
added_parent_dir = False
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    added_parent_dir = True

# Import all functions from utils.py (the module, not this package)
try:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "utils_module", os.path.join(parent_dir, "utils.py")
    )
    utils_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utils_module)

    # Re-export all public functions
    setup_logger = utils_module.setup_logger
    parse_date = utils_module.parse_date
    format_amount = utils_module.format_amount
    format_amount_to_wan = utils_module.format_amount_to_wan
    format_currency = utils_module.format_currency
    find_first_matching_column = utils_module.find_first_matching_column
    get_amount_unit_hint_multiplier = utils_module.get_amount_unit_hint_multiplier
    normalize_amount_series = utils_module.normalize_amount_series
    normalize_column_token = utils_module.normalize_column_token
    normalize_datetime_series = utils_module.normalize_datetime_series
    detect_account_identifier_column = utils_module.detect_account_identifier_column
    build_transaction_order_columns = utils_module.build_transaction_order_columns
    sort_transactions_strict = utils_module.sort_transactions_strict
    normalize_name = utils_module.normalize_name
    extract_chinese_name = utils_module.extract_chinese_name
    extract_company_name = utils_module.extract_company_name
    contains_keywords = utils_module.contains_keywords
    clean_text = utils_module.clean_text
    safe_str = utils_module.safe_str
    extract_bank_name = utils_module.extract_bank_name
    is_within_time_window = utils_module.is_within_time_window
    is_amount_similar = utils_module.is_amount_similar
    # 【2026-02-23 修复】添加遗漏的函数
    calculate_date_range = utils_module.calculate_date_range
    format_date_str = utils_module.format_date_str
    get_month_key = utils_module.get_month_key
    normalize_person_name = utils_module.normalize_person_name
    extract_keywords = utils_module.extract_keywords
    get_timestamp = utils_module.get_timestamp
    get_day_of_month = utils_module.get_day_of_month
    number_to_chinese = utils_module.number_to_chinese
    safe_account_display = utils_module.safe_account_display
    # 【2026-02-23 修复】添加遗漏的函数

finally:
    # Restore sys.path
    if added_parent_dir and parent_dir in sys.path:
        sys.path.remove(parent_dir)

# Also export phrase_loader and safe_types from this package
from .phrase_loader import PhraseLoader
from .safe_types import extract_id_from_filename

__all__ = [
    "setup_logger",
    "parse_date",
    "format_amount",
    "format_amount_to_wan",
    "format_currency",
    "find_first_matching_column",
    "get_amount_unit_hint_multiplier",
    "normalize_amount_series",
    "normalize_column_token",
    "normalize_datetime_series",
    "detect_account_identifier_column",
    "build_transaction_order_columns",
    "sort_transactions_strict",
    "normalize_name",
    "extract_chinese_name",
    "extract_company_name",
    "contains_keywords",
    "clean_text",
    "safe_str",
    "extract_bank_name",
    "is_within_time_window",
    "is_amount_similar",
    # 【2026-02-23 修复】添加遗漏的函数
    "calculate_date_range",
    "format_date_str",
    "get_month_key",
    "normalize_person_name",
    "extract_keywords",
    "get_timestamp",
    "get_day_of_month",
    "number_to_chinese",
    "safe_account_display",
    "extract_id_from_filename",
    "PhraseLoader",
]
