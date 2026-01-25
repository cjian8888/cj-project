#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 输入验证模块

提供统一的输入验证逻辑，防止：
- 路径遍历攻击
- 无效的输入参数
- 超出范围的数值
- 格式错误的数据
"""

import os
import re
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi import HTTPException


class ValidationError(Exception):
    """验证错误异常"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class PathValidator:
    """路径验证器 - 防止路径遍历攻击"""
    
    # 允许的相对路径模式
    ALLOWED_PATH_PATTERNS = [
        r'^cleaned_data/个人$',
        r'^cleaned_data/公司$',
        r'^analysis_results$',
        r'^logs$',
        r'^cleaned_data$',
        r'^reports$',
    ]
    
    @staticmethod
    def validate_relative_path(relative_path: str, base_dir: str = "./output") -> str:
        """
        验证相对路径，防止路径遍历攻击
        
        Args:
            relative_path: 相对路径
            base_dir: 基础目录
            
        Returns:
            规范化的绝对路径
            
        Raises:
            ValidationError: 路径无效或存在安全风险
        """
        if not relative_path:
            raise ValidationError("路径不能为空", "relativePath")
        
        # 检查路径遍历攻击
        if ".." in relative_path or relative_path.startswith("/"):
            raise ValidationError("路径包含非法字符", "relativePath")
        
        # 检查路径模式
        normalized_path = os.path.normpath(relative_path)
        is_allowed = any(
            re.match(pattern, normalized_path) 
            for pattern in PathValidator.ALLOWED_PATH_PATTERNS
        )
        
        if not is_allowed:
            raise ValidationError(f"路径 '{relative_path}' 不在允许的范围内", "relativePath")
        
        # 构建完整路径
        abs_base = os.path.abspath(base_dir)
        target_path = os.path.abspath(os.path.join(base_dir, relative_path))
        
        # 确保目标路径在基础目录内
        if not target_path.startswith(abs_base):
            raise ValidationError("路径超出允许范围", "relativePath")
        
        return target_path
    
    @staticmethod
    def validate_directory_exists(directory: str, create: bool = False) -> str:
        """
        验证目录是否存在
        
        Args:
            directory: 目录路径
            create: 如果不存在是否创建
            
        Returns:
            规范化的目录路径
            
        Raises:
            ValidationError: 目录无效
        """
        if not directory:
            raise ValidationError("目录路径不能为空", "directory")
        
        # 规范化路径
        normalized = os.path.normpath(directory)
        
        # 检查路径遍历
        if ".." in normalized.split(os.sep):
            raise ValidationError("目录路径包含非法字符", "directory")
        
        # 检查是否存在
        if not os.path.exists(normalized):
            if create:
                try:
                    os.makedirs(normalized, exist_ok=True)
                except OSError as e:
                    raise ValidationError(f"无法创建目录: {e}", "directory")
            else:
                raise ValidationError(f"目录不存在: {directory}", "directory")
        
        # 检查是否为目录
        if not os.path.isdir(normalized):
            raise ValidationError(f"路径不是目录: {directory}", "directory")
        
        # 检查是否可读
        if not os.access(normalized, os.R_OK):
            raise ValidationError(f"目录不可读: {directory}", "directory")
        
        return normalized
    
    @staticmethod
    def validate_writable_directory(directory: str) -> str:
        """
        验证目录是否可写
        
        Args:
            directory: 目录路径
            
        Returns:
            规范化的目录路径
            
        Raises:
            ValidationError: 目录不可写
        """
        normalized = PathValidator.validate_directory_exists(directory, create=True)
        
        if not os.access(normalized, os.W_OK):
            raise ValidationError(f"目录不可写: {directory}", "directory")
        
        return normalized


class NumericValidator:
    """数值验证器"""
    
    @staticmethod
    def validate_positive_int(value: int, field: str = "value", min_val: int = 1, max_val: int = None) -> int:
        """
        验证正整数
        
        Args:
            value: 待验证的值
            field: 字段名
            min_val: 最小值
            max_val: 最大值
            
        Returns:
            验证通过的值
            
        Raises:
            ValidationError: 值无效
        """
        if not isinstance(value, int):
            raise ValidationError(f"{field} 必须是整数", field)
        
        if value < min_val:
            raise ValidationError(f"{field} 不能小于 {min_val}", field)
        
        if max_val is not None and value > max_val:
            raise ValidationError(f"{field} 不能大于 {max_val}", field)
        
        return value
    
    @staticmethod
    def validate_cash_threshold(value: int) -> int:
        """验证现金阈值"""
        return NumericValidator.validate_positive_int(
            value, 
            "cashThreshold", 
            min_val=1000,  # 最小 1000 元
            max_val=100000000  # 最大 1 亿元
        )
    
    @staticmethod
    def validate_time_window(value: int) -> int:
        """验证时间窗口"""
        return NumericValidator.validate_positive_int(
            value,
            "timeWindow",
            min_val=1,  # 最小 1 小时
            max_val=720  # 最大 30 天
        )


class StringValidator:
    """字符串验证器"""
    
    @staticmethod
    def validate_non_empty(value: str, field: str = "value") -> str:
        """验证非空字符串"""
        if not value or not value.strip():
            raise ValidationError(f"{field} 不能为空", field)
        return value.strip()
    
    @staticmethod
    def validate_person_name(value: str) -> str:
        """验证人员名称（中文或英文）"""
        value = StringValidator.validate_non_empty(value, "primary_person")
        
        # 检查长度
        if len(value) > 50:
            raise ValidationError("人员名称过长", "primary_person")
        
        # 检查字符（允许中文、英文、空格、点）
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z\s\.]+$', value):
            raise ValidationError("人员名称包含非法字符", "primary_person")
        
        return value
    
    @staticmethod
    def validate_case_name(value: str) -> str:
        """验证案件名称"""
        value = StringValidator.validate_non_empty(value, "case_name")
        
        if len(value) > 200:
            raise ValidationError("案件名称过长", "case_name")
        
        return value
    
    @staticmethod
    def validate_doc_number(value: str) -> str:
        """验证文号格式"""
        if value:
            value = value.strip()
            # 基本格式检查
            if len(value) > 100:
                raise ValidationError("文号过长", "doc_number")
        return value


class ReportValidator:
    """报告生成验证器"""
    
    ALLOWED_FORMATS = ["html", "json", "v3", "investigation"]
    ALLOWED_SECTIONS = ["summary", "assets", "risks", "official"]
    
    @staticmethod
    def validate_format(format: str) -> str:
        """验证报告格式"""
        if format not in ReportValidator.ALLOWED_FORMATS:
            raise ValidationError(
                f"不支持的格式: {format}，支持的格式: {', '.join(ReportValidator.ALLOWED_FORMATS)}",
                "format"
            )
        return format
    
    @staticmethod
    def validate_sections(sections: List[str]) -> List[str]:
        """验证报告章节"""
        if not sections:
            return ReportValidator.ALLOWED_SECTIONS
        
        invalid_sections = [s for s in sections if s not in ReportValidator.ALLOWED_SECTIONS]
        if invalid_sections:
            raise ValidationError(
                f"无效的章节: {', '.join(invalid_sections)}，支持的章节: {', '.join(ReportValidator.ALLOWED_SECTIONS)}",
                "sections"
            )
        
        return sections


class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_analysis_units(units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证分析单元配置"""
        if not units:
            raise ValidationError("分析单元列表不能为空", "analysis_units")
        
        validated_units = []
        for i, unit in enumerate(units):
            if not isinstance(unit, dict):
                raise ValidationError(f"分析单元 {i} 必须是对象", "analysis_units")
            
            # 验证 anchor
            anchor = unit.get("anchor", "")
            if not anchor:
                raise ValidationError(f"分析单元 {i} 缺少 anchor 字段", "analysis_units")
            
            # 验证 unit_type
            unit_type = unit.get("unit_type", "family")
            if unit_type not in ["family", "independent"]:
                raise ValidationError(
                    f"分析单元 {i} 的 unit_type 必须是 'family' 或 'independent'",
                    "analysis_units"
                )
            
            # 验证 members
            members = unit.get("members", [])
            if not isinstance(members, list):
                raise ValidationError(f"分析单元 {i} 的 members 必须是数组", "analysis_units")
            
            if not members:
                raise ValidationError(f"分析单元 {i} 的 members 不能为空", "analysis_units")
            
            validated_units.append(unit)
        
        return validated_units
    
    @staticmethod
    def validate_include_companies(companies: List[str]) -> List[str]:
        """验证包含的公司列表"""
        if companies is None:
            return []
        
        if not isinstance(companies, list):
            raise ValidationError("include_companies 必须是数组", "include_companies")
        
        # 去重并过滤空值
        validated = [c.strip() for c in companies if c and c.strip()]
        
        return validated


def handle_validation_error(error: ValidationError):
    """
    将验证错误转换为 HTTPException
    
    Args:
        error: 验证错误
        
    Returns:
        HTTPException
    """
    detail = error.message
    if error.field:
        detail = f"{error.field}: {detail}"
    
    return HTTPException(status_code=400, detail=detail)
