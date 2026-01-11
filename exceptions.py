#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义异常类 - 资金穿透与关联排查系统
提供细粒度的异常分类，便于问题定位和处理
"""

from typing import Optional, Dict, Any, Callable


class CJProjectError(Exception):
    """项目基础异常类"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | 详情: {self.details}"
        return self.message


# ============== 数据处理异常 ==============

class DataLoadError(CJProjectError):
    """数据加载异常"""
    pass


class DataCleaningError(CJProjectError):
    """数据清洗异常"""
    pass


class DataValidationError(CJProjectError):
    """数据验证异常"""
    def __init__(self, message: str, entity: Optional[str] = None,
                 field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.entity = entity
        self.field = field
        super().__init__(message, details)


class ColumnNotFoundError(DataValidationError):
    """列名未找到异常"""
    def __init__(self, column_name: str, available_columns: Optional[list] = None):
        self.column_name = column_name
        self.available_columns = available_columns
        message = f"列 '{column_name}' 不存在"
        if available_columns:
            message += f"，可用列: {available_columns[:10]}..."
        super().__init__(message)


class EmptyDataError(DataValidationError):
    """数据为空异常"""
    def __init__(self, entity: str):
        super().__init__(f"实体 '{entity}' 的数据为空", entity=entity)


# ============== 文件处理异常 ==============

class FileProcessingError(CJProjectError):
    """文件处理异常"""
    def __init__(self, file_path: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.file_path = file_path
        full_message = f"处理文件 '{file_path}' 时出错: {message}"
        super().__init__(full_message, details)


class FileFormatError(FileProcessingError):
    """文件格式异常"""
    pass


class FileNotFoundError(FileProcessingError):
    """文件未找到异常"""
    pass


# ============== 业务逻辑异常 ==============

class AnalysisError(CJProjectError):
    """分析逻辑异常"""
    pass


class ProfileGenerationError(AnalysisError):
    """资金画像生成异常"""
    def __init__(self, entity: str, message: str):
        self.entity = entity
        super().__init__(f"生成 '{entity}' 的资金画像失败: {message}")


class SuspicionDetectionError(AnalysisError):
    """疑点检测异常"""
    pass


class ReportGenerationError(AnalysisError):
    """报告生成异常"""
    pass


# ============== 配置异常 ==============

class ConfigurationError(CJProjectError):
    """配置异常"""
    pass


class ThresholdError(ConfigurationError):
    """阈值配置异常"""
    def __init__(self, threshold_name: str, value: Any, expected_range: Optional[str] = None):
        message = f"阈值 '{threshold_name}' 的值 {value} 无效"
        if expected_range:
            message += f"，期望范围: {expected_range}"
        super().__init__(message)


# ============== 辅助函数 ==============

def handle_exception(func: Callable) -> Callable:
    """
    异常处理装饰器，将通用异常转换为项目特定异常
    
    Args:
        func: 被装饰的函数
        
    Returns:
        包装后的函数
    """
    import functools
    import logging
    
    logger = logging.getLogger(__name__)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CJProjectError:
            raise # 已是项目异常，直接抛出
        except FileNotFoundError as e:
            raise FileProcessingError(str(e), "文件不存在")
        except pd.errors.EmptyDataError as e:
            raise DataLoadError(f"数据为空: {e}")
        except KeyError as e:
            raise ColumnNotFoundError(str(e))
        except ValueError as e:
            raise DataValidationError(f"数据值异常: {e}")
        except Exception as e:
            logger.error(f"未预期的异常: {type(e).__name__}: {e}")
            raise CJProjectError(f"未预期的异常: {e}")
    
    return wrapper


# 导入pandas用于装饰器中的类型检查
try:
    import pandas as pd
except ImportError:
    pass
