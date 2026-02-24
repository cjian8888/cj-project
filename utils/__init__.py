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
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import all functions from utils.py (the module, not this package)
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("utils_module", os.path.join(parent_dir, "utils.py"))
    utils_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utils_module)
    
    # Re-export all public functions
    setup_logger = utils_module.setup_logger
    parse_date = utils_module.parse_date
    format_amount = utils_module.format_amount
    format_currency = utils_module.format_currency
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
    
finally:
    # Restore sys.path
    if parent_dir in sys.path:
        sys.path.remove(parent_dir)

# Also export phrase_loader from this package
from .phrase_loader import PhraseLoader

__all__ = [
    'setup_logger',
    'parse_date', 
    'format_amount',
    'format_currency',
    'normalize_name',
    'extract_chinese_name',
    'extract_company_name',
    'contains_keywords',
    'clean_text',
    'safe_str',
    'extract_bank_name',
    'is_within_time_window',
    'is_amount_similar',
    # 【2026-02-23 修复】添加遗漏的函数
    'calculate_date_range',
    'format_date_str',
    'get_month_key',
    'normalize_person_name',
    'extract_keywords',
    'PhraseLoader',
]
