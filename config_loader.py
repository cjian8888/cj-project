#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载器 (2026-01-25 修复）
从YAML配置文件加载风险阈值和系统参数

【修复说明】
- 问题2修复：默认配置与config.py硬编码值不一致
- 解决方案：补充完整的默认配置，确保向后兼容性
- 修改日期：2026-01-25
"""

import os
import yaml
import logging
from typing import Dict, Any


# 使用标准库 logging 避免循环导入
def _get_logger():
    """获取 logger（使用标准库避免循环导入）"""
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        # 如果没有处理器，添加一个简单的控制台处理器
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = _get_logger()  # 初始化 logger

# 导入统一路径管理器
from paths import CONFIG_DIR

# 默认配置文件路径（使用 paths 模块统一管理）
DEFAULT_CONFIG_PATH = str(CONFIG_DIR / "risk_thresholds.yaml")


def load_risk_thresholds(config_path: str = None) -> Dict[str, Any]:
    """
    从YAML配置文件加载风险阈值

    Args:
        config_path: 配置文件路径，默认为 config/risk_thresholds.yaml

    Returns:
        配置字典
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    # 检查配置文件是否存在
    if not os.path.exists(config_path):
        _get_logger().warning(f"配置文件不存在: {config_path}，使用默认配置")
        return get_default_config()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        _get_logger().info(f"成功加载配置文件: {config_path}")
        return config
    except Exception as e:
        _get_logger().error(f"加载配置文件失败: {str(e)}，使用默认配置")
        return get_default_config()


def _build_income_classification_config() -> Dict[str, Any]:
    """
    构建收入分类配置。

    包含工资识别、大额现金、分期受贿检测等参数。

    Returns:
        收入分类配置字典
    """
    return {
        "large_cash_threshold": 50000,
        "large_third_party_threshold": 50000,
        "high_frequency_salary_cap": 100000,
        "income_min_amount": 1000,
        "income_max_amount": 5000000,
        "income_high_risk_min": 50000,
        # 收入分析增强参数
        "regular_non_salary_min": 3000,
        "mean_amount_min": 2000,
        "mean_amount_max": 80000,
        "unknown_source_min": 10000,
        "large_personal_min": 20000,
        "high_risk_min": 50000,
        "very_large_min": 100000,
        # 分期受贿检测参数
        "bribe_installment_min_occurrences": 4,
        "bribe_installment_min_amount": 10000,
        "bribe_installment_max_cv": 0.5,
        "bribe_installment_min_months": 4,
        # 理财识别参数
        "wealth_identification_min_amount": 100000,
        "wealth_round_amount_unit": 10000,
        "wealth_periodic_min_occurrences": 4,
        "wealth_periodic_interval_tolerance": 15,
        "wealth_periodic_min_interval": 60,
        "wealth_increasing_ratio": 0.6,
    }


def _build_detection_configs() -> Dict[str, Dict[str, Any]]:
    """
    构建各类检测算法配置。

    包含快进快出、整进散出、休眠激活等检测参数。

    Returns:
        检测配置字典
    """
    return {
        "fast_in_out": {
            "max_time_hours": 24,
            "min_amount": 10000,
            "amount_ratio": 0.8,
            "balance_zero_threshold": 10.0,
            "same_day": True,
        },
        "structuring": {
            "min_large_amount": 50000,
            "min_split_count": 3,
            "time_window_days": 7,
            "amount_tolerance": 0.2,
        },
        "dormant_activation": {"min_days": 180, "activation_min_amount": 50000},
        "fixed_frequency": {
            "min_occurrences": 3,
            "date_tolerance": 3,
            "amount_tolerance": 0.1,
        },
    }


def _build_validation_configs() -> Dict[str, Dict[str, Any]]:
    """
    构建数据验证与质量评估配置。

    Returns:
        验证配置字典
    """
    return {
        "validation": {
            "max_single_amount": 100000000,
            "property_expense_min": 10000,
            "property_match": {
                "time_window_months": 12,
                "cumulative_match": True,
                "cumulative_tolerance": 0.2,
                "single_match_tolerance": 0.1,
            },
        },
        "data_quality": {
            "issue_penalty": 20,
            "warning_penalty": 5,
            "high_null_penalty": 10,
            "quality_levels": {"excellent": 90, "good": 70, "medium": 50, "poor": 0},
            "balance_zero_threshold": 10.0,
            "excellent_score": 90,
            "good_score": 70,
            "medium_score": 50,
            "poor_score": 0,
        },
    }


def _build_cash_and_time_configs() -> Dict[str, Dict[str, Any]]:
    """
    构建现金分析与时间窗口配置。

    Returns:
        现金与时间配置字典
    """
    return {
        "large_cash": {
            "threshold": 50000,
            "levels": {
                "level_1": 10000,
                "level_2": 50000,
                "level_3": 100000,
                "level_4": 500000,
            },
        },
        "cash_time_window": {"hours": 48, "amount_tolerance_ratio": 0.05},
        "fund_retention": {
            "pass_through_threshold": 0.1,
            "low_retention_threshold": 0.3,
            "high_retention_threshold": 0.9,
        },
        "counterparty_frequency": {
            "min_frequency": 5,
            "max_amount": 5000,
            "period_days": 30,
        },
        "time_series": {"high_risk_amount": 50000, "sudden_change_min_amount": 100000},
    }


def _build_loan_and_risk_configs() -> Dict[str, Dict[str, Any]]:
    """
    构建借贷分析与风险评分配置。

    Returns:
        借贷与风险配置字典
    """
    return {
        "loan": {
            "min_match_amount": 5000,
            "time_window_days": 365,
            "amount_tolerance": 0.2,
            "pair_ratio_min": 1.0,
            "pair_ratio_max": 1.5,
            "usury_rate": 36.0,
            "high_rate": 24.0,
            "low_rate": 4.0,
            "bidirectional_high_risk": 50000,
            "interest_free_min": 50000,
            "large_no_repay_min": 100000,
        },
        "risk_score": {
            "fund_cycle": 15,
            "fund_cycle_max": 30,
            "pass_through": 25,
            "hub_node": 10,
            "high_risk_tx": 5,
            "high_risk_tx_max": 20,
            "amount_bonus_per_100k": 5,
            "amount_bonus_max": 20,
            "community": 10,
            "community_max": 20,
            "periodic_income": 5,
            "periodic_income_max": 10,
            "sudden_change": 3,
            "sudden_change_max": 12,
            "delayed_transfer": 10,
            "delayed_transfer_max": 20,
            "loan": 8,
            "loan_max": 16,
        },
        "suspicion": {"medium_high_amount": 50000},
        "behavioral": {
            "fast_in_out_time_window_hours": 24,
            "fast_in_out_same_day": True,
            "fast_in_out_min_amount": 10000,
            "fast_in_out_amount_ratio": 0.8,
            "structuring_min_split_count": 3,
            "structuring_amount_tolerance": 0.2,
            "structuring_time_window_days": 7,
            "structuring_min_large_amount": 50000,
            "dormant_min_days": 180,
            "dormant_activation_min_amount": 50000,
        },
    }


def _build_system_configs() -> Dict[str, Dict[str, Any]]:
    """
    构建系统与性能相关配置。

    Returns:
        系统配置字典
    """
    return {
        "report": {
            "use_global_timestamp": True,
            "timestamp_format": "%Y年%m月%d日 %H:%M:%S",
            "iso_timestamp_format": "%Y-%m-%dT%H:%M:%S",
            "car_payment_min": 10000,
            "house_payment_min": 50000,
        },
        "performance": {
            "batch_size": 10000,
            "chunk_size": 10000,
            "enable_memory_optimization": True,
            "enable_batch_processing": True,
        },
        "cache": {
            "version": "3.2.0",
            "version_major": 3,
            "max_nodes": 200,
            "max_edges": 500,
        },
        "visualization": {
            "max_nodes": 200,
            "max_edges": 500,
            "display_amount_threshold": 10000,
        },
    }


def _build_entity_configs() -> Dict[str, Dict[str, Any]]:
    """
    构建实体相关配置（资产、涉案单位、敏感对象等）。

    Returns:
        实体配置字典
    """
    return {
        "asset": {"large_amount_threshold": 50000, "default_vehicle_value": 200000},
        "fund_penetration": {"min_amount": 100000, "edge_min_amount": 10000},
        "investigation_unit": {
            "keywords": [
                # 示例: '某某公司', '某某单位', '某某部门'
                # 运行时请根据实际案件填写
            ]
        },
        "sensitive_person": {
            "keywords": [
                # 示例: '张三', '李四', '某某'
                # 运行时请根据实际案件填写
            ]
        },
        "sensitive_company": {
            "keywords": [
                # 示例: '某某公司', '某某企业'
                # 运行时请根据实际案件填写
            ]
        },
        "related_party": {
            "high_frequency_count": 10,
            "high_frequency_period_days": 365,
            "large_amount_single": 50000,
            "large_amount_total": 200000,
            "off_hours_start": 22,
            "off_hours_end": 6,
            "sensitive_auto_high_risk": True,
        },
    }


def get_default_config() -> Dict[str, Any]:
    """
    获取默认配置（当配置文件不存在或加载失败时使用）。

    通过组合多个专门的配置构建函数，创建完整的默认配置字典。
    各配置模块分别负责不同功能领域的参数设置。

    Returns:
        默认配置字典（与原config.py硬编码值保持一致）
    """
    config = {}

    # 合并所有配置模块
    config["income_classification"] = _build_income_classification_config()
    config.update(_build_detection_configs())
    config.update(_build_validation_configs())
    config.update(_build_cash_and_time_configs())
    config.update(_build_loan_and_risk_configs())
    config.update(_build_system_configs())
    config.update(_build_entity_configs())

    return config


def get_config_value(config: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    从配置字典中获取嵌套值

    Args:
        config: 配置字典
        *keys: 键路径，如 'income_classification', 'large_cash_threshold'
        default: 默认值

    Returns:
        配置值
    """
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value if value is not None else default


def update_config_value(config: Dict[str, Any], *keys: str, value: Any):
    """
    更新配置字典中的嵌套值

    Args:
        config: 配置字典
        *keys: 键路径
        value: 新值
    """
    if len(keys) == 0:
        return

    # 导航到目标字典
    current = config
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
            current = current[key]
        elif not isinstance(current[key], dict):
            current[key] = {}
            current = current[key]
        else:
            current = current[key]

    # 设置最后一个键的值
    current[keys[-1]] = value


def save_config(config: Dict[str, Any], config_path: str = None):
    """
    保存配置到YAML文件

    Args:
        config: 配置字典
        config_path: 配置文件路径
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        _get_logger().info(f"配置已保存到: {config_path}")
    except Exception as e:
        _get_logger().error(f"保存配置失败: {str(e)}")


# ============================================================
# 便捷函数：直接获取常用配置值
# ============================================================


def get_income_classification_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取收入分类配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("income_classification", {})


def get_fast_in_out_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取快进快出配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("fast_in_out", {})


def get_validation_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取数据验证配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("validation", {})


def get_performance_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取性能优化配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("performance", {})


# ============================================================
# 新增便捷函数：获取其他常用配置
# ============================================================


def get_loan_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取借贷分析配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("loan", {})


def get_time_series_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取时序分析配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("time_series", {})


def get_fund_penetration_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取资金穿透配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("fund_penetration", {})


def get_risk_score_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取风险评分配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("risk_score", {})


def get_behavioral_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取行为特征分析配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("behavioral", {})


def get_visualization_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取可视化配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("visualization", {})


def get_investigation_unit_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取调查单位配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("investigation_unit", {})


def get_sensitive_person_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取敏感人员配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("sensitive_person", {})


def get_sensitive_company_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取敏感公司配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("sensitive_company", {})


def get_related_party_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """获取关联交易排查配置"""
    if config is None:
        config = load_risk_thresholds()
    return config.get("related_party", {})


if __name__ == "__main__":
    # 测试配置加载
    config = load_risk_thresholds()
    print("配置加载成功:")
    print(f"  - 大额现金阈值: {config['large_cash']['threshold']}")
    print(f"  - 快进快出时间窗口: {config['fast_in_out']['max_time_hours']}小时")
    print(
        f"  - 数据质量优秀阈值: {config['data_quality']['quality_levels']['excellent']}分"
    )
