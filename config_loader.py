#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载器 - 从 YAML 文件加载配置

【模块定位】
配置管理模块，用于：
1. 从 YAML 文件加载配置
2. 支持多环境配置（开发、生产）
3. 配置验证和默认值处理
4. 配置热重载支持

【审计价值】
- 配置外部化，便于维护和调整
- 支持不同环境的配置切换
- 提高配置管理的灵活性

【技术实现】
- PyYAML 解析 YAML 文件
- 配置合并和覆盖机制
- 配置验证
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path

import utils

logger = utils.setup_logger(__name__)


class ConfigLoader:
    """
    配置加载器
    
    功能：
    1. 从 YAML 文件加载配置
    2. 支持多环境配置
    3. 配置合并和覆盖
    4. 配置验证
    """
    
    def __init__(self, config_dir: Optional[str] = None, environment: str = 'default'):
        """
        初始化配置加载器
        
        Args:
            config_dir: 配置文件目录，默认为 ./config
            environment: 环境名称（default, development, production）
        """
        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(__file__), 'config')
        
        self.config_dir = config_dir
        self.environment = environment
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        # 加载默认配置
        default_config_path = os.path.join(self.config_dir, 'default.yaml')
        
        if os.path.exists(default_config_path):
            with open(default_config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            logger.info(f'已加载默认配置: {default_config_path}')
        else:
            logger.warning(f'默认配置文件不存在: {default_config_path}')
            self._config = {}
        
        # 加载环境特定配置
        env_config_path = os.path.join(self.config_dir, f'{self.environment}.yaml')
        
        if os.path.exists(env_config_path):
            with open(env_config_path, 'r', encoding='utf-8') as f:
                env_config = yaml.safe_load(f)
            
            # 合并配置（环境配置覆盖默认配置）
            self._config = self._deep_merge(self._config, env_config)
            logger.info(f'已加载环境配置: {env_config_path}')
        
        # 验证配置
        self._validate_config()
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        深度合并两个字典
        
        Args:
            base: 基础字典
            override: 覆盖字典
            
        Returns:
            合并后的字典
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _validate_config(self):
        """验证配置"""
        # 检查必需的配置项
        required_sections = [
            'salary', 'wealth_management', 'loan', 'third_party_payment',
            'asset', 'cash', 'fixed_frequency', 'holiday',
            'bank_field_mapping', 'transaction_categories',
            'excel_fields', 'output', 'logging', 'thresholds'
        ]
        
        for section in required_sections:
            if section not in self._config:
                logger.warning(f'配置缺少必需的节: {section}')
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键（如 'salary.strong_keywords'）
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_list(self, key: str, default: Optional[List] = None) -> List:
        """
        获取列表类型的配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置列表
        """
        value = self.get(key, default)
        
        if value is None:
            return []
        
        if isinstance(value, list):
            return value
        
        return [value]
    
    def get_dict(self, key: str, default: Optional[Dict] = None) -> Dict:
        """
        获取字典类型的配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置字典
        """
        value = self.get(key, default)
        
        if value is None:
            return {}
        
        if isinstance(value, dict):
            return value
        
        return {}
    
    def get_int(self, key: str, default: int = 0) -> int:
        """
        获取整数类型的配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置整数值
        """
        value = self.get(key, default)
        
        if isinstance(value, int):
            return value
        
        if isinstance(value, float):
            return int(value)
        
        if isinstance(value, str) and value.isdigit():
            return int(value)
        
        return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """
        获取浮点数类型的配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置浮点数值
        """
        value = self.get(key, default)
        
        if isinstance(value, float):
            return value
        
        if isinstance(value, int):
            return float(value)
        
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
        
        return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        获取布尔类型的配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置布尔值
        """
        value = self.get(key, default)
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on')
        
        if isinstance(value, (int, float)):
            return bool(value)
        
        return default
    
    def reload(self):
        """重新加载配置"""
        logger.info('重新加载配置...')
        self._load_config()
        logger.info('配置重新加载完成')
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()
    
    def set(self, key: str, value: Any):
        """
        设置配置值（运行时修改）
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        logger.debug(f'设置配置: {key} = {value}')


# 全局配置加载器实例
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(environment: str = 'default') -> ConfigLoader:
    """
    获取全局配置加载器实例
    
    Args:
        environment: 环境名称
        
    Returns:
        配置加载器实例
    """
    global _config_loader
    
    if _config_loader is None:
        _config_loader = ConfigLoader(environment=environment)
    
    return _config_loader


def reload_config():
    """重新加载配置"""
    global _config_loader
    
    if _config_loader is not None:
        _config_loader.reload()


# ==================== 兼容性函数 ====================
# 以下函数用于保持与原有 config.py 的兼容性

def _get_config_value(key: str, default: Any = None) -> Any:
    """获取配置值（兼容性函数）"""
    loader = get_config_loader()
    return loader.get(key, default)


# 工资识别配置
SALARY_STRONG_KEYWORDS = lambda: _get_config_value('salary.strong_keywords', [])
SALARY_KEYWORDS = lambda: _get_config_value('salary.keywords', [])
EXCLUDED_REIMBURSEMENT_KEYWORDS = lambda: _get_config_value('salary.excluded_reimbursement_keywords', [])
KNOWN_SALARY_PAYERS = lambda: _get_config_value('salary.known_payers', [])
USER_DEFINED_SALARY_PAYERS = lambda: _get_config_value('salary.user_defined_payers', [])
HR_COMPANY_KEYWORDS = lambda: _get_config_value('salary.hr_company_keywords', [])

# 政府机关白名单
GOVERNMENT_AGENCY_KEYWORDS = lambda: _get_config_value('government_agency_keywords', [])

# 理财产品配置
WEALTH_PRODUCT_COUNTERPARTY_KEYWORDS = lambda: _get_config_value('wealth_management.counterparty_keywords', [])
KNOWN_WEALTH_PRODUCTS = lambda: _get_config_value('wealth_management.known_products', [])
WEALTH_MANAGEMENT_KEYWORDS = lambda: _get_config_value('wealth_management.keywords', [])
WEALTH_PURCHASE_KEYWORDS = lambda: _get_config_value('wealth_management.purchase_keywords', [])
WEALTH_REDEMPTION_KEYWORDS = lambda: _get_config_value('wealth_management.redemption_keywords', [])

# 借贷平台配置
LOAN_PLATFORM_KEYWORDS = lambda: _get_config_value('loan.platform_keywords', [])

# 第三方支付平台配置
THIRD_PARTY_PAYMENT_KEYWORDS = lambda: _get_config_value('third_party_payment.keywords', [])

# 资产相关配置
PROPERTY_KEYWORDS = lambda: _get_config_value('asset.property_keywords', [])
VEHICLE_KEYWORDS = lambda: _get_config_value('asset.vehicle_keywords', [])
PROPERTY_THRESHOLD = lambda: _get_config_value('asset.thresholds.property', 100000)
VEHICLE_THRESHOLD = lambda: _get_config_value('asset.thresholds.vehicle', 50000)
ASSET_LARGE_AMOUNT_THRESHOLD = lambda: _get_config_value('asset.thresholds.large_amount', 50000)
DEFAULT_VEHICLE_VALUE = lambda: _get_config_value('asset.thresholds.default_vehicle_value', 200000)

# 现金交易配置
CASH_KEYWORDS = lambda: _get_config_value('cash.keywords', [])
LARGE_CASH_THRESHOLD = lambda: _get_config_value('cash.large_threshold', 50000)
CASH_THRESHOLDS = lambda: _get_config_value('cash.thresholds', {})
CASH_TIME_WINDOW_HOURS = lambda: _get_config_value('cash.time_window_hours', 48)
AMOUNT_TOLERANCE_RATIO = lambda: _get_config_value('cash.amount_tolerance_ratio', 0.05)

# 固定频率检测配置
FIXED_FREQUENCY_MIN_OCCURRENCES = lambda: _get_config_value('fixed_frequency.min_occurrences', 3)
FIXED_FREQUENCY_DATE_TOLERANCE = lambda: _get_config_value('fixed_frequency.date_tolerance', 3)
FIXED_FREQUENCY_AMOUNT_TOLERANCE = lambda: _get_config_value('fixed_frequency.amount_tolerance', 0.1)

# 节假日配置
CHINESE_HOLIDAYS = lambda: _get_config_value('holiday.chinese_holidays', {})
NON_WORKING_HOURS_START = lambda: _get_config_value('holiday.non_working_hours.start', 20)
NON_WORKING_HOURS_END = lambda: _get_config_value('holiday.non_working_hours.end', 8)
WEEKEND_DETECTION_ENABLED = lambda: _get_config_value('holiday.weekend_detection_enabled', True)
HOLIDAY_LARGE_AMOUNT_THRESHOLD = lambda: _get_config_value('holiday.large_amount_threshold', 50000)
HOLIDAY_DETECTION_CONFIG = lambda: _get_config_value('holiday.detection_config', {})

# 第三方中转配置
THIRD_PARTY_RELAY_HOURS = lambda: _get_config_value('third_party_relay.time_window_hours', 72)

# 金额拆分规避检测配置
SPLIT_AMOUNT_THRESHOLD = lambda: _get_config_value('split_amount.threshold', 50000)
SPLIT_DETECTION_COUNT = lambda: _get_config_value('split_amount.detection_count', 3)
SPLIT_AMOUNT_TOLERANCE = lambda: _get_config_value('split_amount.tolerance', 0.02)

# 整数金额偏好检测配置
ROUND_AMOUNT_THRESHOLD = lambda: _get_config_value('round_amount.threshold', 10000)
ROUND_AMOUNT_MIN_COUNT = lambda: _get_config_value('round_amount.min_count', 5)
LUCKY_TAIL_NUMBERS = lambda: _get_config_value('lucky_tail_numbers', [])

# 房产购置匹配配置
PROPERTY_MATCH_CONFIG = lambda: _get_config_value('property_match', {})

# 银行字段映射配置
BANK_FIELD_MAPPING = lambda: _get_config_value('bank_field_mapping', {})

# 去重配置
DEDUP_TIME_TOLERANCE_SECONDS = lambda: _get_config_value('dedup.time_tolerance_seconds', 1)
DEDUP_KEYS = lambda: _get_config_value('dedup.keys', [])

# 交易分类配置
TRANSACTION_CATEGORIES = lambda: _get_config_value('transaction_categories', {})

# Excel字段映射配置
DATE_COLUMNS = lambda: _get_config_value('excel_fields.date_columns', [])
DESCRIPTION_COLUMNS = lambda: _get_config_value('excel_fields.description_columns', [])
INCOME_COLUMNS = lambda: _get_config_value('excel_fields.income_columns', [])
EXPENSE_COLUMNS = lambda: _get_config_value('excel_fields.expense_columns', [])
COUNTERPARTY_COLUMNS = lambda: _get_config_value('excel_fields.counterparty_columns', [])
BALANCE_COLUMNS = lambda: _get_config_value('excel_fields.balance_columns', [])

# 文件路径配置
OUTPUT_EXCEL_FILE = lambda: _get_config_value('output.excel_file', '资金核查底稿.xlsx')
OUTPUT_REPORT_FILE = lambda: _get_config_value('output.report_file', '核查结果分析报告.docx')
OUTPUT_LOG_FILE = lambda: _get_config_value('output.log_file', 'audit_system.log')
OUTPUT_DIR = lambda: _get_config_value('output.directory', './output')

# PDF线索文件关键词
CLUE_FILE_KEYWORDS = lambda: _get_config_value('clue_file_keywords', [])

# 日志配置
LOG_FORMAT = lambda: _get_config_value('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOG_DATE_FORMAT = lambda: _get_config_value('logging.date_format', '%Y-%m-%d %H:%M:%S')
LOG_LEVEL = lambda: _get_config_value('logging.level', 'INFO')

# 报告模板配置
REPORT_TITLE = lambda: _get_config_value('report.title', '核查结果分析报告')
REPORT_SECTIONS = lambda: _get_config_value('report.sections', [])
RISK_LEVELS = lambda: _get_config_value('report.risk_levels', {})

# 数据质量检查配置
REQUIRED_FIELDS = lambda: _get_config_value('data_quality.required_fields', [])
DATE_FORMATS = lambda: _get_config_value('data_quality.date_formats', [])
MAX_AMOUNT_THRESHOLD = lambda: _get_config_value('data_quality.max_single_amount', 100000000)

# 集中式阈值配置
VALIDATION_MAX_SINGLE_AMOUNT = lambda: _get_config_value('thresholds.validation.max_single_amount', 10000000)
VALIDATION_PROPERTY_EXPENSE_MIN = lambda: _get_config_value('thresholds.validation.property_expense_min', 10000)
INCOME_MIN_AMOUNT = lambda: _get_config_value('thresholds.income.min_amount', 1000)
INCOME_REGULAR_MIN = lambda: _get_config_value('thresholds.income.regular_min', 3000)
INCOME_MEAN_AMOUNT_MIN = lambda: _get_config_value('thresholds.income.mean_amount_min', 2000)
INCOME_MEAN_AMOUNT_MAX = lambda: _get_config_value('thresholds.income.mean_amount_max', 80000)
INCOME_UNKNOWN_SOURCE_MIN = lambda: _get_config_value('thresholds.income.unknown_source_min', 10000)
INCOME_LARGE_PERSONAL_MIN = lambda: _get_config_value('thresholds.income.large_personal_min', 20000)
INCOME_HIGH_RISK_MIN = lambda: _get_config_value('thresholds.income.high_risk_min', 50000)
INCOME_VERY_LARGE_MIN = lambda: _get_config_value('thresholds.income.very_large_min', 100000)
DISPLAY_AMOUNT_THRESHOLD = lambda: _get_config_value('thresholds.display.amount_threshold', 10000)
LOAN_MIN_AMOUNT = lambda: _get_config_value('thresholds.loan.min_amount', 5000)
LOAN_HIGH_RISK_MIN = lambda: _get_config_value('thresholds.loan.high_risk_min', 10000)
LOAN_BIDIRECTIONAL_HIGH_RISK = lambda: _get_config_value('thresholds.loan.bidirectional_high_risk', 50000)
LOAN_INTEREST_FREE_MIN = lambda: _get_config_value('thresholds.loan.interest_free_min', 50000)
LOAN_LARGE_NO_REPAY_MIN = lambda: _get_config_value('thresholds.loan.large_no_repay_min', 100000)
SUSPICION_PROPERTY_HIGH_RISK = lambda: _get_config_value('thresholds.suspicion.property_high_risk', 1000000)
SUSPICION_VEHICLE_HIGH_RISK = lambda: _get_config_value('thresholds.suspicion.vehicle_high_risk', 500000)
SUSPICION_LUCKY_NUMBER_MIN = lambda: _get_config_value('thresholds.suspicion.lucky_number_min', 1000)
PENETRATION_MIN_AMOUNT = lambda: _get_config_value('thresholds.penetration.min_amount', 10000)
REPORT_CAR_PAYMENT_MIN = lambda: _get_config_value('report.thresholds.car_payment_min', 10000)
REPORT_HOUSE_PAYMENT_MIN = lambda: _get_config_value('report.thresholds.house_payment_min', 50000)
WEALTH_SIGNIFICANT_PROFIT = lambda: _get_config_value('thresholds.wealth.significant_profit', 100000)
WEALTH_SIGNIFICANT_REDEMPTION = lambda: _get_config_value('thresholds.wealth.significant_redemption', 100000)

# 单位转换
UNIT_WAN = 10000

# 动态阈值配置
DYNAMIC_THRESHOLD_CONFIG = lambda: _get_config_value('cash.dynamic_threshold', {})


# ==================== v3.0 主核查配置加载 ====================
# 以下函数用于加载 investigation_config.yaml

import config
from report_schema import (
    InvestigationConfig, PrimarySubjectConfig, 
    CollisionTarget, SensitivePerson
)


def load_investigation_config(config_path: str = None) -> Optional['InvestigationConfig']:
    """
    加载主核查配置
    
    Args:
        config_path: 配置文件路径，默认为 ./config/investigation_config.yaml
        
    Returns:
        InvestigationConfig 对象，如无配置则返回空配置
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'investigation_config.yaml')
    
    # 如果配置文件不存在，返回空配置
    if not os.path.exists(config_path):
        logger.info(f"[配置加载] 配置文件不存在，使用默认空配置: {config_path}")
        return InvestigationConfig()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f) or {}
        
        logger.info(f"[配置加载] 已加载配置文件: {config_path}")
        return _parse_investigation_config(raw_config)
        
    except Exception as e:
        logger.warning(f"[配置加载] 配置文件解析失败: {e}")
        return InvestigationConfig()


def _parse_investigation_config(raw_config: Dict) -> 'InvestigationConfig':
    """解析原始 YAML 配置为 InvestigationConfig 对象"""
    
    # 解析主核查对象
    primary_subject_raw = raw_config.get('primary_subject', {}) or {}
    primary_subject = PrimarySubjectConfig(
        name=primary_subject_raw.get('name', '') or '',
        id_number=primary_subject_raw.get('id_number', '') or '',
        position=primary_subject_raw.get('position', '') or '',
        employer=primary_subject_raw.get('employer', '') or '',
        entry_date=primary_subject_raw.get('entry_date', '') or '',
        promotion_date=primary_subject_raw.get('promotion_date', '') or '',
        verified_monthly_income=primary_subject_raw.get('verified_monthly_income', 0) or 0
    )
    
    # 解析调查单位
    investigation_unit_raw = raw_config.get('investigation_unit', {}) or {}
    investigation_unit_name = investigation_unit_raw.get('name', '') or ''
    investigation_unit_keywords = investigation_unit_raw.get('keywords', []) or []
    
    # 解析白名单
    excluded_companies = raw_config.get('excluded_companies', []) or []
    
    # 解析碰撞目标
    collision_targets_raw = raw_config.get('collision_targets', []) or []
    collision_targets = []
    for target in collision_targets_raw:
        if isinstance(target, dict):
            collision_targets.append(CollisionTarget(
                name=target.get('name', '') or '',
                type=target.get('type', '') or '',
                risk_level=target.get('risk_level', 'medium') or 'medium',
                note=target.get('note', '') or ''
            ))
    
    # 解析敏感人员
    sensitive_persons_raw = raw_config.get('sensitive_persons', []) or []
    sensitive_persons = []
    for person in sensitive_persons_raw:
        if isinstance(person, dict):
            sensitive_persons.append(SensitivePerson(
                name=person.get('name', '') or '',
                relation=person.get('relation', '') or ''
            ))
    
    # 解析数据范围
    data_scope_raw = raw_config.get('data_scope', {}) or {}
    data_scope_auto = data_scope_raw.get('auto_detect', True)
    data_scope_start = data_scope_raw.get('start_date', '') or ''
    data_scope_end = data_scope_raw.get('end_date', '') or ''
    
    # 解析报告元信息
    report_meta_raw = raw_config.get('report_meta', {}) or {}
    doc_number = report_meta_raw.get('doc_number', '') or ''
    case_source = report_meta_raw.get('case_source', '') or ''
    
    return InvestigationConfig(
        primary_subject=primary_subject,
        basic_info_supplement=raw_config.get('basic_info_supplement', []) or [],
        family_members=raw_config.get('family_members', []) or [],
        investigation_unit_name=investigation_unit_name,
        investigation_unit_keywords=investigation_unit_keywords,
        excluded_companies=excluded_companies,
        collision_targets=collision_targets,
        sensitive_persons=sensitive_persons,
        data_scope_auto_detect=data_scope_auto,
        data_scope_start=data_scope_start,
        data_scope_end=data_scope_end,
        doc_number=doc_number,
        case_source=case_source
    )


def apply_investigation_config_to_runtime(investigation_config: 'InvestigationConfig'):
    """
    将配置应用到运行时 config.py
    
    仅覆盖非空配置项，保持默认值不变
    """
    # 应用调查单位关键词
    if investigation_config.investigation_unit_keywords:
        config.INVESTIGATION_UNIT_KEYWORDS = investigation_config.investigation_unit_keywords
        logger.info(f"[配置应用] INVESTIGATION_UNIT_KEYWORDS = {investigation_config.investigation_unit_keywords}")
    
    # 应用白名单
    if investigation_config.excluded_companies:
        if hasattr(config, 'EXCLUDED_COMPANIES'):
            config.EXCLUDED_COMPANIES = investigation_config.excluded_companies
        else:
            setattr(config, 'EXCLUDED_COMPANIES', investigation_config.excluded_companies)
        logger.info(f"[配置应用] EXCLUDED_COMPANIES = {len(investigation_config.excluded_companies)} 项")
    
    # 应用敏感人员
    if investigation_config.sensitive_persons:
        sensitive_names = [p.name for p in investigation_config.sensitive_persons]
        if hasattr(config, 'SENSITIVE_PERSON_KEYWORDS'):
            config.SENSITIVE_PERSON_KEYWORDS = sensitive_names
        else:
            setattr(config, 'SENSITIVE_PERSON_KEYWORDS', sensitive_names)
        logger.info(f"[配置应用] SENSITIVE_PERSON_KEYWORDS = {sensitive_names}")
    
    # 应用碰撞目标公司
    if investigation_config.collision_targets:
        target_names = [t.name for t in investigation_config.collision_targets]
        if hasattr(config, 'COLLISION_TARGET_COMPANIES'):
            config.COLLISION_TARGET_COMPANIES = target_names
        else:
            setattr(config, 'COLLISION_TARGET_COMPANIES', target_names)
        logger.info(f"[配置应用] COLLISION_TARGET_COMPANIES = {target_names}")

