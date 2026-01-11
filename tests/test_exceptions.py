#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常处理单元测试
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from exceptions import (
    CJProjectError, DataValidationError, ColumnNotFoundError,
    FileProcessingError, AnalysisError, ConfigurationError,
    ProfileGenerationError, ThresholdError, handle_exception
)


class TestCJProjectError:
    """测试基础异常类"""
    
    def test_cj_project_error_basic(self):
        """测试基础异常"""
        error = CJProjectError("测试错误")
        # CJProjectError的__str__返回self.message
        assert "测试错误" in str(error)
        assert error.message == "测试错误"
        assert error.details == {}
    
    def test_cj_project_error_with_details(self):
        """测试带详情的异常"""
        details = {"key": "value"}
        error = CJProjectError("测试错误", details=details)
        assert error.details == details
    
    def test_cj_project_error_str_with_details(self):
        """测试带详情的字符串表示"""
        details = {"key": "value"}
        error = CJProjectError("测试错误", details=details)
        error_str = str(error)
        assert "测试错误" in error_str
        assert "key" in error_str
        assert "value" in error_str


class TestDataValidationError:
    """测试数据验证异常"""
    
    def test_data_validation_error_basic(self):
        """测试基础数据验证异常"""
        error = DataValidationError("数据验证失败")
        assert str(error) == "数据验证失败"
        assert error.entity is None
        assert error.field is None
    
    def test_data_validation_error_with_entity(self):
        """测试带实体的异常"""
        error = DataValidationError("数据验证失败", entity="张伟")
        assert error.entity == "张伟"
    
    def test_data_validation_error_with_field(self):
        """测试带字段的异常"""
        error = DataValidationError("数据验证失败", field="金额")
        assert error.field == "金额"
    
    def test_data_validation_error_with_all_params(self):
        """测试带所有参数的异常"""
        details = {"expected": "number", "actual": "string"}
        error = DataValidationError(
            "数据验证失败",
            entity="张伟",
            field="金额",
            details=details
        )
        assert error.entity == "张伟"
        assert error.field == "金额"
        assert error.details == details


class TestColumnNotFoundError:
    """测试列未找到异常"""
    
    def test_column_not_found_error_basic(self):
        """测试基础列未找到异常"""
        error = ColumnNotFoundError("金额")
        assert "金额" in str(error)
        assert error.column_name == "金额"
    
    def test_column_not_found_error_with_available_columns(self):
        """测试带可用列的异常"""
        available = ["日期", "摘要", "余额"]
        error = ColumnNotFoundError("金额", available_columns=available)
        assert "金额" in str(error)
        assert "日期" in str(error)
        assert "摘要" in str(error)
        assert "余额" in str(error)
        assert error.available_columns == available


class TestFileProcessingError:
    """测试文件处理异常"""
    
    def test_file_processing_error_basic(self):
        """测试基础文件处理异常"""
        error = FileProcessingError("test.xlsx", "文件读取失败")
        assert "test.xlsx" in str(error)
        assert "文件读取失败" in str(error)
        assert error.file_path == "test.xlsx"
    
    def test_file_processing_error_with_details(self):
        """测试带详情的文件处理异常"""
        details = {"line": 10, "error": "invalid format"}
        error = FileProcessingError(
            "test.xlsx",
            "文件读取失败",
            details=details
        )
        assert error.details == details


class TestAnalysisError:
    """测试分析异常"""
    
    def test_analysis_error_basic(self):
        """测试基础分析异常"""
        error = AnalysisError("分析失败")
        assert str(error) == "分析失败"


class TestConfigurationError:
    """测试配置异常"""
    
    def test_configuration_error_basic(self):
        """测试基础配置异常"""
        error = ConfigurationError("配置错误")
        assert str(error) == "配置错误"


class TestProfileGenerationError:
    """测试画像生成异常"""
    
    def test_profile_generation_error_basic(self):
        """测试基础画像生成异常"""
        error = ProfileGenerationError("张伟", "画像生成失败")
        assert "张伟" in str(error)
        assert "画像生成失败" in str(error)
        assert error.entity == "张伟"
    
    def test_profile_generation_error_inheritance(self):
        """测试继承关系"""
        error = ProfileGenerationError("张伟", "画像生成失败")
        assert isinstance(error, AnalysisError)
        assert isinstance(error, CJProjectError)


class TestThresholdError:
    """测试阈值异常"""
    
    def test_threshold_error_basic(self):
        """测试基础阈值异常"""
        error = ThresholdError("大额交易阈值", 100000)
        assert "大额交易阈值" in str(error)
        assert "100000" in str(error)
    
    def test_threshold_error_with_expected_range(self):
        """测试带期望范围的异常"""
        error = ThresholdError(
            "大额交易阈值",
            100000,
            expected_range="10000-50000"
        )
        assert "10000-50000" in str(error)
    
    def test_threshold_error_inheritance(self):
        """测试继承关系"""
        error = ThresholdError("大额交易阈值", 100000)
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, CJProjectError)


class TestHandleException:
    """测试异常处理装饰器"""
    
    def test_handle_exception_with_no_error(self):
        """测试无异常情况"""
        @handle_exception
        def test_func():
            return "success"
        
        result = test_func()
        assert result == "success"
    
    def test_handle_exception_with_cj_project_error(self):
        """测试CJProjectError异常"""
        @handle_exception
        def test_func():
            raise CJProjectError("测试错误")
        
        # 装饰器应该直接抛出CJProjectError
        with pytest.raises(CJProjectError):
            test_func()
    
    def test_handle_exception_with_generic_exception(self):
        """测试通用异常"""
        @handle_exception
        def test_func():
            raise ValueError("通用错误")
        
        # 装饰器应该将ValueError转换为DataValidationError
        with pytest.raises(DataValidationError):
            test_func()
    
    def test_handle_exception_with_return_value(self):
        """测试带返回值的函数"""
        @handle_exception
        def test_func(x, y):
            return x + y
        
        result = test_func(1, 2)
        assert result == 3
    
    def test_handle_exception_with_exception_in_calculation(self):
        """测试计算中的异常"""
        @handle_exception
        def test_func(x, y):
            return x / y
        
        # ZeroDivisionError会被转换为CJProjectError
        with pytest.raises(CJProjectError):
            test_func(1, 0)


class TestExceptionHierarchy:
    """测试异常继承层次"""
    
    def test_all_exceptions_inherit_from_cj_project_error(self):
        """测试所有异常都继承自CJProjectError"""
        exceptions = [
            DataValidationError,
            ColumnNotFoundError,
            FileProcessingError,
            AnalysisError,
            ConfigurationError,
            ProfileGenerationError,
            ThresholdError
        ]
        
        for exc_class in exceptions:
            assert issubclass(exc_class, CJProjectError)
    
    def test_specific_inheritance(self):
        """测试特定继承关系"""
        assert issubclass(ProfileGenerationError, AnalysisError)
        assert issubclass(ThresholdError, ConfigurationError)
        assert issubclass(DataValidationError, CJProjectError)
        assert issubclass(ColumnNotFoundError, DataValidationError)
        assert issubclass(FileProcessingError, CJProjectError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
