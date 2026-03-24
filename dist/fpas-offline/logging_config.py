#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志配置模块 - 资金穿透与关联排查系统

【修复说明】
- 问题21修复：缺少统一的日志标准
- 解决方案：创建统一的日志配置模块，定义日志级别使用指南和结构化日志格式
- 修改日期：2026-01-25
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any
from datetime import datetime
import json
import os

# ============================================================
# 日志级别使用指南
# ============================================================

"""
日志级别使用指南：

DEBUG (10):
  - 用途：详细的调试信息，仅在开发时使用
  - 示例：logger.debug(f'列名匹配候选: {candidates}')
  - 场景：算法中间结果、变量值、循环迭代等

INFO (20):
  - 用途：一般信息，记录正常的操作流程
  - 示例：logger.info(f'正在读取Excel文件: {file_path}')
  - 场景：开始/结束操作、处理进度、关键节点等

WARNING (30):
  - 用途：警告信息，不影响程序运行但需要注意
  - 示例：logger.warning(f'日期解析失败 {count} 条，已转为NaT')
  - 场景：数据质量问题、降级处理、非预期但可恢复的情况

ERROR (40):
  - 用途：错误信息，影响部分功能但程序继续运行
  - 示例：logger.error(f'读取Excel失败: {file_path}, 错误: {str(e)}')
  - 场景：文件处理失败、数据库操作失败、API调用失败等

CRITICAL (50):
  - 用途：严重错误，程序无法继续运行
  - 示例：logger.critical(f'数据库连接失败，程序退出')
  - 场景：配置错误、资源不可用、致命错误等
"""

# ============================================================
# 日志分类
# ============================================================

class LogCategory:
    """日志分类枚举"""
    APPLICATION = 'application'  # 应用日志：正常业务流程
    AUDIT = 'audit'            # 审计日志：重要操作记录
    PERFORMANCE = 'performance'  # 性能日志：性能监控
    ERROR = 'error'            # 错误日志：错误和异常
    SECURITY = 'security'       # 安全日志：安全相关事件

# ============================================================
# 日志格式配置
# ============================================================

# 标准日志格式
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(category)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 结构化日志格式（JSON）
STRUCTURED_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# 日志文件路径
LOG_DIR = './logs'
APPLICATION_LOG_FILE = os.path.join(LOG_DIR, 'application.log')
AUDIT_LOG_FILE = os.path.join(LOG_DIR, 'audit.log')
PERFORMANCE_LOG_FILE = os.path.join(LOG_DIR, 'performance.log')
ERROR_LOG_FILE = os.path.join(LOG_DIR, 'error.log')

# 日志轮转配置
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# ============================================================
# 全局日志配置
# ============================================================

# 已配置的日志记录器（记录最后一次配置，便于同名 logger 在配置变更时重建）
_configured_loggers: Dict[str, Dict[str, Any]] = {}

# 上下文信息（用于结构化日志）
_log_context: Dict[str, Any] = {}


def set_log_context(**kwargs):
    """
    设置日志上下文信息
    
    Args:
        **kwargs: 上下文键值对（如 request_id, user_id, task_id 等）
    """
    global _log_context
    _log_context.update(kwargs)


def get_log_context() -> Dict[str, Any]:
    """
    获取当前日志上下文信息
    
    Returns:
        上下文字典
    """
    return _log_context.copy()


def clear_log_context():
    """清除日志上下文信息"""
    global _log_context
    _log_context.clear()


class CategoryFilter(logging.Filter):
    """日志分类过滤器"""
    
    def __init__(self, category: str):
        super().__init__()
        self.category = category
    
    def filter(self, record):
        record.category = getattr(record, 'category', LogCategory.APPLICATION)
        return record.category == self.category


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器（JSON格式）"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'logger': record.name,
            'level': record.levelname,
            'category': getattr(record, 'category', LogCategory.APPLICATION),
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # 添加上下文信息
        if _log_context:
            log_data['context'] = _log_context.copy()
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logger(
    name: str,
    level: str = 'INFO',
    log_file: Optional[str] = None,
    category: str = LogCategory.APPLICATION,
    structured: bool = False,
    console_output: bool = True
) -> logging.Logger:
    """
    设置统一的日志记录器
    
    Args:
        name: 日志记录器名称（通常使用 __name__）
        level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_file: 日志文件路径（可选）
        category: 日志分类（LogCategory枚举）
        structured: 是否使用结构化日志（JSON格式）
        console_output: 是否输出到控制台
        
    Returns:
        配置好的日志记录器
    """
    logger_key = f"{name}_{category}"
    logger = logging.getLogger(name)
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    desired_config = {
        'level': resolved_level,
        'log_file': os.path.abspath(log_file) if log_file else None,
        'structured': structured,
        'console_output': console_output,
    }

    # 相同配置直接复用，避免重复添加处理器。
    if _configured_loggers.get(logger_key) == desired_config:
        return logger

    logger.setLevel(resolved_level)
    
    # 配置变更时先移除旧处理器，避免复用到过时的输出目标。
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    
    # 创建格式化器
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
    
    # 控制台处理器
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        # 确保日志目录存在（处理空目录路径的情况）
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # 添加分类过滤器
        category_filter = CategoryFilter(category)
        file_handler.addFilter(category_filter)
        
        logger.addHandler(file_handler)
    
    # 标记为已配置
    _configured_loggers[logger_key] = desired_config
    
    return logger


def get_logger(name: str, category: str = LogCategory.APPLICATION) -> logging.Logger:
    """
    获取日志记录器（便捷函数）
    
    Args:
        name: 日志记录器名称（通常使用 __name__）
        category: 日志分类（LogCategory枚举）
        
    Returns:
        日志记录器
    """
    # 根据分类选择日志文件
    log_file_map = {
        LogCategory.APPLICATION: APPLICATION_LOG_FILE,
        LogCategory.AUDIT: AUDIT_LOG_FILE,
        LogCategory.PERFORMANCE: PERFORMANCE_LOG_FILE,
        LogCategory.ERROR: ERROR_LOG_FILE,
        LogCategory.SECURITY: ERROR_LOG_FILE  # 安全日志也写入错误日志文件
    }
    
    log_file = log_file_map.get(category)
    
    return setup_logger(
        name=name,
        level='INFO',
        log_file=log_file,
        category=category,
        structured=False,
        console_output=True
    )


def log_performance(logger: logging.Logger, operation: str, duration_ms: float, **kwargs):
    """
    记录性能日志
    
    Args:
        logger: 日志记录器
        operation: 操作名称
        duration_ms: 执行时间（毫秒）
        **kwargs: 额外的性能指标
    """
    metrics = ', '.join([f'{k}={v}' for k, v in kwargs.items()])
    message = f'性能: {operation}, 耗时={duration_ms:.2f}ms, {metrics}'
    logger.info(message, extra={'category': LogCategory.PERFORMANCE})


def log_audit(logger: logging.Logger, action: str, target: str, result: str, **kwargs):
    """
    记录审计日志
    
    Args:
        logger: 日志记录器
        action: 操作动作
        target: 操作目标
        result: 操作结果
        **kwargs: 额外的审计信息
    """
    details = ', '.join([f'{k}={v}' for k, v in kwargs.items()])
    message = f'审计: 动作={action}, 目标={target}, 结果={result}, {details}'
    logger.info(message, extra={'category': LogCategory.AUDIT})


# ============================================================
# 初始化日志目录
# ============================================================

def _init_log_directories():
    """初始化日志目录"""
    for log_file in [APPLICATION_LOG_FILE, AUDIT_LOG_FILE, 
                    PERFORMANCE_LOG_FILE, ERROR_LOG_FILE]:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)


# 模块加载时初始化日志目录
_init_log_directories()
