#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模板引擎模块 - 资金穿透与关联排查系统
提供HTML模板加载和渲染功能

使用方法:
    from template_engine import TemplateEngine
    
    engine = TemplateEngine()
    html = engine.render('html_report.html', {
        'REPORT_TITLE': '核查报告',
        'CONTENT': '<p>报告内容</p>'
    })
"""

import os
import re
from typing import Dict, Any
import utils

logger = utils.setup_logger(__name__)

# 导入统一路径管理器
from paths import TEMPLATES_DIR

# 模板目录路径（使用 paths 模块统一管理）
TEMPLATE_DIR = str(TEMPLATES_DIR)


class TemplateEngine:
    """
    简单的模板引擎
    支持占位符替换: {{PLACEHOLDER}}
    """
    
    def __init__(self, template_dir: str = None):
        """
        初始化模板引擎
        
        Args:
            template_dir: 模板目录路径，默认为项目下的templates目录
        """
        self.template_dir = template_dir or TEMPLATE_DIR
        self._cache = {}  # 模板缓存
        
    def load(self, template_name: str) -> str:
        """
        加载模板文件
        
        Args:
            template_name: 模板文件名（相对于template_dir）
            
        Returns:
            模板内容字符串
        """
        # 检查缓存
        if template_name in self._cache:
            return self._cache[template_name]
        
        template_path = os.path.join(self.template_dir, template_name)
        
        if not os.path.exists(template_path):
            logger.error(f'模板文件不存在: {template_path}')
            raise FileNotFoundError(f'模板文件不存在: {template_path}')
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 缓存模板
        self._cache[template_name] = content
        logger.debug(f'加载模板: {template_name}')
        
        return content
    
    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        渲染模板
        
        Args:
            template_name: 模板文件名
            context: 占位符替换字典，如 {'TITLE': '标题', 'CONTENT': '内容'}
            
        Returns:
            渲染后的HTML字符串
        """
        template = self.load(template_name)
        
        # 替换所有 {{PLACEHOLDER}} 形式的占位符
        for key, value in context.items():
            placeholder = '{{' + key + '}}'
            template = template.replace(placeholder, str(value))
        
        # 检查是否有未替换的占位符
        remaining = re.findall(r'\{\{(\w+)\}\}', template)
        if remaining:
            logger.warning(f'模板中存在未替换的占位符: {remaining}')
        
        return template
    
    def render_string(self, template_content: str, context: Dict[str, Any]) -> str:
        """
        渲染模板字符串（不从文件加载）
        
        Args:
            template_content: 模板内容字符串
            context: 占位符替换字典
            
        Returns:
            渲染后的字符串
        """
        result = template_content
        for key, value in context.items():
            placeholder = '{{' + key + '}}'
            result = result.replace(placeholder, str(value))
        return result
    
    def clear_cache(self):
        """清除模板缓存（用于开发时热更新）"""
        self._cache.clear()
        logger.info('模板缓存已清除')


# 全局单例实例
_engine = None

def get_engine() -> TemplateEngine:
    """获取全局模板引擎实例"""
    global _engine
    if _engine is None:
        _engine = TemplateEngine()
    return _engine


def render_template(template_name: str, context: Dict[str, Any]) -> str:
    """
    便捷函数：渲染模板
    
    Args:
        template_name: 模板文件名
        context: 占位符替换字典
        
    Returns:
        渲染后的HTML字符串
        
    Example:
        html = render_template('html_report.html', {
            'REPORT_TITLE': '核查报告',
            'CONTENT': '<p>内容</p>',
            'GENERATE_TIME': '2026-01-09'
        })
    """
    return get_engine().render(template_name, context)


def load_template(template_name: str) -> str:
    """
    便捷函数：加载模板
    
    Args:
        template_name: 模板文件名
        
    Returns:
        模板内容字符串
    """
    return get_engine().load(template_name)
