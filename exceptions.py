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


class FilePermissionError(FileProcessingError):
    """文件权限异常"""
    pass


class FileCorruptedError(FileProcessingError):
    """文件损坏异常"""
    pass


# ============== PDF 处理异常 ==============

class PDFProcessingError(FileProcessingError):
    """PDF 处理异常"""
    pass


class PDFParseError(PDFProcessingError):
    """PDF 解析异常"""
    pass


class PDFPasswordError(PDFProcessingError):
    """PDF 密码异常"""
    pass


class PDFImageExtractionError(PDFProcessingError):
    """PDF 图片提取异常"""
    pass


# ============== Excel 处理异常 ==============

class ExcelProcessingError(FileProcessingError):
    """Excel 处理异常"""
    pass


class ExcelParseError(ExcelProcessingError):
    """Excel 解析异常"""
    pass


class ExcelSheetNotFoundError(ExcelProcessingError):
    """Excel 工作表未找到异常"""
    def __init__(self, file_path: str, sheet_name: str, available_sheets: Optional[list] = None):
        self.sheet_name = sheet_name
        self.available_sheets = available_sheets
        message = f"工作表 '{sheet_name}' 不存在"
        if available_sheets:
            message += f"，可用工作表: {available_sheets}"
        super().__init__(file_path, message)


class ExcelEmptyDataError(ExcelProcessingError):
    """Excel 数据为空异常"""
    def __init__(self, file_path: str, sheet_name: Optional[str] = None):
        message = "Excel 数据为空"
        if sheet_name:
            message += f"（工作表: {sheet_name}）"
        super().__init__(file_path, message)


# ============== Word 处理异常 ==============

class WordProcessingError(FileProcessingError):
    """Word 处理异常"""
    pass


class WordGenerationError(WordProcessingError):
    """Word 文档生成异常"""
    pass


class WordTemplateError(WordProcessingError):
    """Word 模板异常"""
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


# ============== 数据库异常 ==============

class DatabaseError(CJProjectError):
    """数据库异常"""
    pass


class DatabaseConnectionError(DatabaseError):
    """数据库连接异常"""
    pass


class DatabaseQueryError(DatabaseError):
    """数据库查询异常"""
    def __init__(self, query: str, message: str):
        self.query = query
        super().__init__(f"查询失败: {message}", {'query': query})


class DatabaseTransactionError(DatabaseError):
    """数据库事务异常"""
    pass


class DatabaseConstraintError(DatabaseError):
    """数据库约束异常"""
    pass


# ============== API 异常 ==============

class APIError(CJProjectError):
    """API 异常"""
    pass


class APIValidationError(APIError):
    """API 验证异常"""
    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.value = value
        details = {'field': field}
        if value is not None:
            details['value'] = value
        super().__init__(f"字段 '{field}' 验证失败: {message}", details)


class APIAuthenticationError(APIError):
    """API 认证异常"""
    pass


class APIRateLimitError(APIError):
    """API 速率限制异常"""
    pass


class WebSocketError(APIError):
    """WebSocket 异常"""
    pass


class WebSocketConnectionError(WebSocketError):
    """WebSocket 连接异常"""
    pass


class WebSocketMessageError(WebSocketError):
    """WebSocket 消息异常"""
    pass


# ============== 银行格式异常 ==============

class BankFormatError(CJProjectError):
    """银行格式异常"""
    pass


class BankFormatDetectionError(BankFormatError):
    """银行格式检测异常"""
    def __init__(self, file_path: str, reason: str):
        super().__init__(f"无法检测银行格式: {reason}", {'file_path': file_path})


class BankColumnMappingError(BankFormatError):
    """银行列映射异常"""
    def __init__(self, bank_name: str, missing_columns: list):
        self.bank_name = bank_name
        self.missing_columns = missing_columns
        super().__init__(f"银行 '{bank_name}' 缺少必需列: {missing_columns}",
                       {'bank_name': bank_name, 'missing_columns': missing_columns})


class BankDateParseError(BankFormatError):
    """银行日期解析异常"""
    def __init__(self, bank_name: str, date_value: str, reason: str):
        self.bank_name = bank_name
        self.date_value = date_value
        super().__init__(f"银行 '{bank_name}' 日期解析失败: {date_value} - {reason}",
                       {'bank_name': bank_name, 'date_value': date_value})


# ============== AML 分析异常 ==============

class AMLAnalysisError(AnalysisError):
    """AML 分析异常"""
    pass


class AMLFileParseError(AMLAnalysisError):
    """AML 文件解析异常"""
    def __init__(self, file_path: str, reason: str):
        super().__init__(f"AML 文件解析失败: {reason}", {'file_path': file_path})


class AMLQuerySummaryError(AMLAnalysisError):
    """AML 查询汇总异常"""
    pass


class AMLPaymentAccountError(AMLAnalysisError):
    """AML 付款账户异常"""
    pass


# ============== 行为画像异常 ==============

class BehavioralProfilingError(AnalysisError):
    """行为画像异常"""
    pass


class ProfileDataError(BehavioralProfilingError):
    """画像数据异常"""
    pass


class NaNValueError(BehavioralProfilingError):
    """NaN 值异常"""
    def __init__(self, entity: str, field: str):
        super().__init__(f"实体 '{entity}' 的字段 '{field}' 包含 NaN 值",
                       {'entity': entity, 'field': field})


class TimeWindowError(BehavioralProfilingError):
    """时间窗口异常"""
    def __init__(self, message: str, start_date: Any = None, end_date: Any = None):
        details = {}
        if start_date is not None:
            details['start_date'] = str(start_date)
        if end_date is not None:
            details['end_date'] = str(end_date)
        super().__init__(message, details)


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


class ConfigFileError(ConfigurationError):
    """配置文件异常"""
    def __init__(self, file_path: str, reason: str):
        super().__init__(f"配置文件 '{file_path}' 错误: {reason}", {'file_path': file_path})


class ConfigValidationError(ConfigurationError):
    """配置验证异常"""
    pass


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
    import os
    
    logger = logging.getLogger(__name__)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CJProjectError:
            raise # 已是项目异常，直接抛出
        except PermissionError as e:
            raise FilePermissionError(str(e), "文件权限不足")
        except FileNotFoundError as e:
            raise FileProcessingError(str(e), "文件不存在")
        except IsADirectoryError as e:
            raise FileProcessingError(str(e), "路径是目录而非文件")
        except pd.errors.EmptyDataError as e:
            raise ExcelEmptyDataError("", "数据为空")
        except pd.errors.ParserError as e:
            raise ExcelParseError("", f"解析失败: {e}")
        except KeyError as e:
            raise ColumnNotFoundError(str(e))
        except ValueError as e:
            raise DataValidationError(f"数据值异常: {e}")
        except TypeError as e:
            raise DataValidationError(f"数据类型异常: {e}")
        except IndexError as e:
            raise DataValidationError(f"索引越界: {e}")
        except AttributeError as e:
            raise DataValidationError(f"属性访问失败: {e}")
        except MemoryError as e:
            raise DataLoadError(f"内存不足: {e}")
        except TimeoutError as e:
            raise AnalysisError(f"操作超时: {e}")
        except ConnectionError as e:
            raise DatabaseConnectionError(f"连接失败: {e}")
        except Exception as e:
            logger.error(f"未预期的异常: {type(e).__name__}: {e}")
            raise CJProjectError(f"未预期的异常: {e}")
    
    return wrapper


def safe_execute(func: Callable, default: Any = None,
                 raise_on_error: bool = False) -> Any:
    """
    安全执行函数，捕获所有异常
    
    Args:
        func: 要执行的函数
        default: 异常时返回的默认值
        raise_on_error: 是否在异常时抛出异常
        
    Returns:
        函数执行结果或默认值
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        return func()
    except CJProjectError as e:
        logger.warning(f"项目异常: {e}")
        if raise_on_error:
            raise
        return default
    except Exception as e:
        logger.error(f"未预期的异常: {type(e).__name__}: {e}")
        if raise_on_error:
            raise
        return default


# 导入pandas用于装饰器中的类型检查
try:
    import pandas as pd
except ImportError:
    pass
