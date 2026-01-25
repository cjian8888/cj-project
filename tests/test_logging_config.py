#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志配置模块单元测试

【修复说明】
- 问题21修复：缺少统一的日志标准
- 测试内容：测试统一日志配置模块
- 修改日期：2026-01-25
"""

import pytest
import logging
import sys
import os
import json
import tempfile
import shutil

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logging_config import (
    LogCategory,
    CategoryFilter,
    StructuredFormatter,
    setup_logger,
    get_logger,
    set_log_context,
    get_log_context,
    clear_log_context,
    log_performance,
    log_audit,
    _configured_loggers
)


class TestLogCategory:
    """测试日志分类枚举"""
    
    def test_application_category(self):
        """测试应用日志分类"""
        assert LogCategory.APPLICATION == 'application'
    
    def test_audit_category(self):
        """测试审计日志分类"""
        assert LogCategory.AUDIT == 'audit'
    
    def test_performance_category(self):
        """测试性能日志分类"""
        assert LogCategory.PERFORMANCE == 'performance'
    
    def test_error_category(self):
        """测试错误日志分类"""
        assert LogCategory.ERROR == 'error'
    
    def test_security_category(self):
        """测试安全日志分类"""
        assert LogCategory.SECURITY == 'security'


class TestCategoryFilter:
    """测试日志分类过滤器"""
    
    def test_filter_with_matching_category(self):
        """测试匹配分类的日志"""
        filter_obj = CategoryFilter(LogCategory.APPLICATION)
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='test message',
            args=(),
            exc_info=None
        )
        record.category = LogCategory.APPLICATION
        
        result = filter_obj.filter(record)
        assert result is True
    
    def test_filter_with_non_matching_category(self):
        """测试不匹配分类的日志"""
        filter_obj = CategoryFilter(LogCategory.APPLICATION)
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='test message',
            args=(),
            exc_info=None
        )
        record.category = LogCategory.AUDIT
        
        result = filter_obj.filter(record)
        assert result is False


class TestStructuredFormatter:
    """测试结构化日志格式化器"""
    
    def test_format_basic_log(self):
        """测试基本日志格式化"""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name='test.module',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='test message',
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['logger'] == 'test.module'
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'test message'
        assert log_data['category'] == 'application'
        assert 'timestamp' in log_data
    
    def test_format_with_context(self):
        """测试带上下文的日志格式化"""
        set_log_context(request_id='12345', user_id='user001')
        
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name='test.module',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='test message',
            args=(),
            exc_info=None
        )
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert 'context' in log_data
        assert log_data['context']['request_id'] == '12345'
        assert log_data['context']['user_id'] == 'user001'
        
        # 清理上下文
        clear_log_context()
    
    def test_format_with_exception(self):
        """测试带异常的日志格式化"""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("test error")
        except Exception as e:
            record = logging.LogRecord(
                name='test.module',
                level=logging.ERROR,
                pathname='test.py',
                lineno=10,
                msg='error message',
                args=(),
                exc_info=True
            )
            record.exc_info = (type(e), e, e.__traceback__)
            
            result = formatter.format(record)
            log_data = json.loads(result)
            
            assert 'exception' in log_data
            assert 'ValueError' in log_data['exception']


class TestLogContext:
    """测试日志上下文管理"""
    
    def test_set_and_get_context(self):
        """测试设置和获取上下文"""
        set_log_context(request_id='12345', user_id='user001')
        
        context = get_log_context()
        
        assert context['request_id'] == '12345'
        assert context['user_id'] == 'user001'
        
        # 清理
        clear_log_context()
    
    def test_update_context(self):
        """测试更新上下文"""
        set_log_context(request_id='12345')
        set_log_context(user_id='user001')
        
        context = get_log_context()
        
        assert context['request_id'] == '12345'
        assert context['user_id'] == 'user001'
        
        # 清理
        clear_log_context()
    
    def test_clear_context(self):
        """测试清理上下文"""
        set_log_context(request_id='12345', user_id='user001')
        clear_log_context()
        
        context = get_log_context()
        
        assert len(context) == 0


class TestSetupLogger:
    """测试日志记录器设置"""
    
    def test_setup_logger_with_console_output(self):
        """测试带控制台输出的日志记录器"""
        logger = setup_logger('test_logger', console_output=True)
        
        assert logger.name == 'test_logger'
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0
    
    def test_setup_logger_without_console_output(self):
        """测试不带控制台输出的日志记录器"""
        logger = setup_logger('test_logger', console_output=False)
        
        assert logger.name == 'test_logger'
        # 应该没有控制台处理器
        console_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(console_handlers) == 0
    
    def test_setup_logger_with_file_output(self, tmpdir):
        """测试带文件输出的日志记录器"""
        log_file = os.path.join(tmpdir, 'test.log')
        logger = setup_logger('test_logger', log_file=log_file)
        
        # 写入日志
        logger.info('test message')
        
        # 检查文件是否创建
        assert os.path.exists(log_file)
    
    def test_setup_logger_avoids_duplicate_configuration(self):
        """测试避免重复配置"""
        logger1 = setup_logger('test_duplicate')
        logger2 = setup_logger('test_duplicate')
        
        # 应该返回同一个logger
        assert logger1.name == logger2.name


class TestGetLogger:
    """测试获取日志记录器便捷函数"""
    
    def test_get_application_logger(self):
        """测试获取应用日志记录器"""
        logger = get_logger('test.app', LogCategory.APPLICATION)
        
        assert logger.name == 'test.app'
        assert logger.level == logging.INFO
    
    def test_get_audit_logger(self):
        """测试获取审计日志记录器"""
        logger = get_logger('test.audit', LogCategory.AUDIT)
        
        assert logger.name == 'test.audit'
        assert logger.level == logging.INFO
    
    def test_get_performance_logger(self):
        """测试获取性能日志记录器"""
        logger = get_logger('test.perf', LogCategory.PERFORMANCE)
        
        assert logger.name == 'test.perf'
        assert logger.level == logging.INFO


class TestLogPerformance:
    """测试性能日志记录"""
    
    def test_log_performance_basic(self, caplog):
        """测试基本性能日志"""
        logger = get_logger('test.perf', LogCategory.PERFORMANCE)
        
        with caplog.at_level(logging.INFO):
            log_performance(logger, 'test_operation', 123.45)
        
        # 检查日志是否包含性能信息
        assert any('性能: test_operation' in record.message for record in caplog.records)
        assert any('耗时=123.45ms' in record.message for record in caplog.records)
    
    def test_log_performance_with_metrics(self, caplog):
        """测试带指标的性能日志"""
        logger = get_logger('test.perf', LogCategory.PERFORMANCE)
        
        with caplog.at_level(logging.INFO):
            log_performance(logger, 'test_operation', 123.45, records=100, bytes=1024)
        
        # 检查日志是否包含指标
        assert any('性能: test_operation' in record.message for record in caplog.records)
        assert any('records=100' in record.message for record in caplog.records)
        assert any('bytes=1024' in record.message for record in caplog.records)


class TestLogAudit:
    """测试审计日志记录"""
    
    def test_log_audit_basic(self, caplog):
        """测试基本审计日志"""
        logger = get_logger('test.audit', LogCategory.AUDIT)
        
        with caplog.at_level(logging.INFO):
            log_audit(logger, 'login', 'user001', 'success')
        
        # 检查日志是否包含审计信息
        assert any('审计: 动作=login' in record.message for record in caplog.records)
        assert any('目标=user001' in record.message for record in caplog.records)
        assert any('结果=success' in record.message for record in caplog.records)
    
    def test_log_audit_with_details(self, caplog):
        """测试带详情的审计日志"""
        logger = get_logger('test.audit', LogCategory.AUDIT)
        
        with caplog.at_level(logging.INFO):
            log_audit(logger, 'data_export', 'report001', 'success', 
                     record_count=1000, file_size='10MB')
        
        # 检查日志是否包含详情
        assert any('审计: 动作=data_export' in record.message for record in caplog.records)
        assert any('record_count=1000' in record.message for record in caplog.records)
        assert any('file_size=10MB' in record.message for record in caplog.records)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
