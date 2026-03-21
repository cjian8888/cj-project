"""
SuspicionEngine - 自动注册引擎
实现检测器的自动发现、注册和统一调用。
"""
import importlib
import inspect
import logging
import os
from glob import glob
from pathlib import Path
from typing import Dict, List, Any, Optional, Type

import pandas as pd

from detectors.base_detector import BaseDetector
import utils

# Configure logger
logger = logging.getLogger(__name__)


class SuspicionEngine:
    """疑点检测引擎。
    
    自动扫描detectors/目录，发现并注册所有继承自BaseDetector的检测器类。
    提供统一的接口来运行所有或指定的检测器。
    
    Attributes:
        detectors: 已注册的检测器实例字典，key为检测器name，value为实例
    """
    _TRANSACTION_ONLY_DETECTORS = {
        "round_amount",
        "fixed_amount",
        "fixed_frequency",
        "frequency_anomaly",
        "suspicious_pattern",
    }

    def __init__(self, detectors_dir: Optional[str] = None):
        """初始化引擎并自动注册检测器。"""
        self.detectors: Dict[str, BaseDetector] = {}
        self._detectors_dir = detectors_dir or self._get_default_detectors_dir()
        self._auto_register()
    
    def _get_default_detectors_dir(self) -> str:
        """获取默认的检测器目录路径。"""
        current_file = Path(__file__).resolve()
        return str(current_file.parent / "detectors")
    
    def _auto_register(self) -> None:
        """自动扫描并注册所有检测器。"""
        if not os.path.exists(self._detectors_dir):
            return
        
        pattern = os.path.join(self._detectors_dir, "*.py")
        detector_files = glob(pattern)
        
        for file_path in detector_files:
            file_name = os.path.basename(file_path)
            
            if file_name.startswith("__") or file_name == "base_detector.py":
                continue
            
            module_name = file_name[:-3]
            
            try:
                module_path = f"detectors.{module_name}"
                module = importlib.import_module(module_path)
                
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    
                    is_valid_detector = (
                        inspect.isclass(attr)
                        and issubclass(attr, BaseDetector)
                        and attr is not BaseDetector
                        and not inspect.isabstract(attr)
                    )
                    
                    if is_valid_detector:
                        try:
                            detector_instance = attr()
                            self.detectors[detector_instance.name] = detector_instance
                        except Exception as e:
                            logger.warning(
                                f"注册检测器失败 {module_path}.{attr_name}: {type(e).__name__}: {e}"
                            )
                            
            except ImportError as e:
                logger.warning(f"导入检测器模块失败 {module_name}: {e}")
    
    def list_detectors(self) -> List[Dict[str, Any]]:
        """列出所有已注册的检测器信息。"""
        return [
            {
                "name": detector.name,
                "description": detector.description,
                "risk_level": detector.risk_level,
                "enabled": detector.enabled
            }
            for detector in self.detectors.values()
        ]
    
    def _validate_input(self, data: Any, config: Any) -> tuple[bool, str]:
        """验证输入数据的格式和有效性。

        Returns:
            tuple: (is_valid, error_message)
        """
        if data is None:
            return False, "输入数据为 None"

        if not isinstance(data, dict):
            return False, f"输入数据类型错误: 期望 dict, 实际 {type(data).__name__}"

        if len(data) == 0:
            return False, "输入数据为空字典"

        if config is None:
            return False, "配置参数为 None"

        if not isinstance(config, dict):
            return False, f"配置参数类型错误: 期望 dict, 实际 {type(config).__name__}"

        return True, ""

    @staticmethod
    def _pick_column(frame_or_row: Any, *candidates: str) -> str:
        available = (
            frame_or_row.columns
            if hasattr(frame_or_row, "columns")
            else getattr(frame_or_row, "index", [])
        )
        for column in candidates:
            if column in available:
                return column
        return ""

    @staticmethod
    def _safe_text(value: Any) -> str:
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
        if value is None:
            return ""
        text = str(value).strip()
        return "" if text.lower() in {"nan", "none", "null"} else text

    def _extract_signed_amount_and_type(self, row: Any) -> tuple[float, str]:
        income_col = self._pick_column(row, "income", "收入(元)")
        expense_col = self._pick_column(row, "expense", "支出(元)")
        amount_col = self._pick_column(row, "amount", "交易金额")

        income = utils.format_amount(row.get(income_col, 0)) if income_col else 0.0
        expense = utils.format_amount(row.get(expense_col, 0)) if expense_col else 0.0

        if income > 0 and income >= expense:
            return income, "收入"
        if expense > 0:
            return -expense, "支出"

        amount = utils.format_amount(row.get(amount_col, 0)) if amount_col else 0.0
        if amount > 0:
            return amount, "收入"
        if amount < 0:
            return amount, "支出"
        return 0.0, ""

    def _build_transactions_from_dataframe(self, df: Any) -> List[Dict[str, Any]]:
        if df is None or not hasattr(df, "iterrows") or getattr(df, "empty", True):
            return []

        date_col = self._pick_column(df, "date", "交易时间", "交易日期", "日期")
        if not date_col:
            return []

        counterparty_col = self._pick_column(df, "counterparty", "交易对手", "对手方")
        description_col = self._pick_column(df, "description", "交易摘要", "摘要")
        account_col = self._pick_column(df, "account", "account_number", "本方账号", "账号")
        bank_col = self._pick_column(df, "bank", "银行来源", "所属银行")
        tx_id_col = self._pick_column(df, "transaction_id", "流水号")
        source_col = self._pick_column(df, "source_file", "数据来源")
        channel_col = self._pick_column(df, "transaction_channel", "交易渠道")

        transactions: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            tx_date = row.get(date_col)
            try:
                if pd.isna(tx_date):
                    continue
            except (TypeError, ValueError):
                pass

            amount, tx_type = self._extract_signed_amount_and_type(row)
            if amount == 0 or not tx_type:
                continue

            transactions.append(
                {
                    "tx_date": tx_date,
                    "amount": amount,
                    "tx_type": tx_type,
                    "counterparty": self._safe_text(
                        row.get(counterparty_col, "") if counterparty_col else ""
                    ),
                    "description": self._safe_text(
                        row.get(description_col, "") if description_col else ""
                    ),
                    "account": self._safe_text(
                        row.get(account_col, "") if account_col else ""
                    ),
                    "bank": self._safe_text(row.get(bank_col, "") if bank_col else ""),
                    "transaction_id": self._safe_text(
                        row.get(tx_id_col, "") if tx_id_col else ""
                    ),
                    "transaction_channel": self._safe_text(
                        row.get(channel_col, "") if channel_col else ""
                    ),
                    "source_file": self._safe_text(
                        row.get(source_col, "") if source_col else ""
                    ),
                }
            )

        return transactions

    def _build_detector_inputs(
        self, detector_name: str, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if detector_name not in self._TRANSACTION_ONLY_DETECTORS:
            return [data]

        cleaned_data = data.get("cleaned_data", {})
        if not isinstance(cleaned_data, dict) or not cleaned_data:
            return [data]

        detector_inputs: List[Dict[str, Any]] = []
        for entity_name, df in cleaned_data.items():
            transactions = self._build_transactions_from_dataframe(df)
            if not transactions:
                continue
            detector_inputs.append(
                {
                    "transactions": transactions,
                    "entity_name": entity_name,
                }
            )
        return detector_inputs or [data]

    def run_all(self, data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """运行所有启用的检测器。

        Args:
            data: 输入数据字典
            config: 配置参数字典

        Returns:
            检测结果字典，key为检测器名称，value为疑点列表
        """
        results: Dict[str, List[Dict[str, Any]]] = {}

        is_valid, error_msg = self._validate_input(data, config)
        if not is_valid:
            logger.error(f"SuspicionEngine.run_all 输入验证失败: {error_msg}")
            return results

        enabled_detectors = [(name, detector) for name, detector in self.detectors.items() if detector.enabled]
        if not enabled_detectors:
            logger.warning("没有启用的检测器")
            return results

        logger.info(f"开始运行 {len(enabled_detectors)} 个检测器")
        failed_detectors: List[tuple[str, str]] = []

        for name, detector in enabled_detectors:
            try:
                suspicions: List[Dict[str, Any]] = []
                for detector_input in self._build_detector_inputs(name, data):
                    partial = detector.detect(detector_input, config)
                    if partial:
                        suspicions.extend(partial)
                if suspicions:
                    results[name] = suspicions
                    logger.debug(f"检测器 '{name}' 发现 {len(suspicions)} 个疑点")
                else:
                    logger.debug(f"检测器 '{name}' 未发现疑点")
            except Exception as e:
                error_info = f"{type(e).__name__}: {str(e)}"
                failed_detectors.append((name, error_info))
                logger.error(f"检测器 '{name}' 执行失败: {error_info}")
                results[name] = []

        if failed_detectors:
            logger.warning(f"共有 {len(failed_detectors)} 个检测器执行失败，其他检测器正常运行")

        return results
    
    def run_by_name(self, name: str, data: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """运行指定名称的检测器，不存在时抛出KeyError。"""
        if name not in self.detectors:
            error_msg = f"未找到检测器: {name}"
            logger.error(error_msg)
            raise KeyError(error_msg)

        is_valid, error_msg = self._validate_input(data, config)
        if not is_valid:
            logger.error(f"SuspicionEngine.run_by_name('{name}') 输入验证失败: {error_msg}")
            return []

        detector = self.detectors[name]

        if not detector.enabled:
            logger.warning(f"检测器 '{name}' 未启用")
            return []

        try:
            result: List[Dict[str, Any]] = []
            for detector_input in self._build_detector_inputs(name, data):
                partial = detector.detect(detector_input, config)
                if partial:
                    result.extend(partial)
            logger.debug(f"检测器 '{name}' 执行完成，发现 {len(result) if result else 0} 个疑点")
            return result if result else []
        except Exception as e:
            error_info = f"{type(e).__name__}: {str(e)}"
            logger.error(f"检测器 '{name}' 执行失败: {error_info}")
            return []
    
    def get_detector(self, name: str) -> Optional[BaseDetector]:
        """获取指定名称的检测器实例，不存在返回None。"""
        return self.detectors.get(name)
    
    def is_detector_enabled(self, name: str) -> bool:
        """检查指定检测器是否启用。"""
        detector = self.detectors.get(name)
        return detector.enabled if detector else False
