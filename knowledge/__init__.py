"""行业知识库 - 金融术语、银行产品、代码前缀、检测规则"""
import yaml
import os
from typing import Dict, Any

__all__ = ['load_financial_terms', 'load_bank_products', 'load_product_prefixes', 'load_suspicion_rules']


def _load_yaml(filename: str) -> Dict[str, Any]:
    """加载YAML文件"""
    filepath = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_financial_terms() -> Dict[str, Any]:
    """加载金融术语"""
    return _load_yaml('financial_terms.yaml')


def load_bank_products() -> Dict[str, Any]:
    """加载银行产品线"""
    return _load_yaml('bank_product_lines.yaml')


def load_product_prefixes() -> Dict[str, Any]:
    """加载产品代码前缀"""
    return _load_yaml('product_code_prefixes.yaml')


def load_suspicion_rules() -> Dict[str, Any]:
    """加载疑点检测规则"""
    return _load_yaml('suspicion_rules.yaml')