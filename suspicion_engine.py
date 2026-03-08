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

from detectors.base_detector import BaseDetector

# Configure logger
logger = logging.getLogger(__name__)


class SuspicionEngine:
    """疑点检测引擎。
    
    自动扫描detectors/目录，发现并注册所有继承自BaseDetector的检测器类。
    提供统一的接口来运行所有或指定的检测器。
    
    Attributes:
        detectors: 已注册的检测器实例字典，key为检测器name，value为实例
    """
    
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
                suspicions = detector.detect(data, config)
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
            result = detector.detect(data, config)
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
