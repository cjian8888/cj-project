#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
名称标准化工具模块

【模块定位】
提供统一的名称标准化逻辑，用于对手方匹配前的预处理。
解决因空格、括号内容、全角半角差异导致的匹配失败问题。

创建日期: 2026-01-18
"""

import re
from typing import Optional


def normalize_name(name: str) -> str:
    """
    标准化名称（对手方/人员名称）
    
    处理规则：
    1. 去除两端空白
    2. 全角转半角
    3. 去除括号及其内容（如"张三（个人）"→"张三"）
    4. 去除多余空格
    5. 转换为小写字母（针对英文名）
    
    Args:
        name: 原始名称
        
    Returns:
        标准化后的名称
    """
    if not name:
        return ''
    
    result = str(name).strip()
    
    # 全角转半角映射
    FULL_TO_HALF = {
        '　': ' ',  # 全角空格
        '（': '(',
        '）': ')',
        '【': '[',
        '】': ']',
        '，': ',',
        '。': '.',
        '：': ':',
        '；': ';',
    }
    
    for full, half in FULL_TO_HALF.items():
        result = result.replace(full, half)
    
    # 去除括号及其内容
    # 匹配中英文括号：(...)、[...]
    result = re.sub(r'[\(\[].*?[\)\]]', '', result)
    
    # 去除多余空格
    result = re.sub(r'\s+', '', result)
    
    # 去除特殊后缀
    SUFFIXES_TO_REMOVE = ['个人', '对私', '对公', '本人']
    for suffix in SUFFIXES_TO_REMOVE:
        if result.endswith(suffix):
            result = result[:-len(suffix)]
    
    return result.strip()


def normalize_for_matching(name: str) -> str:
    """
    为匹配目的进行名称标准化
    
    比 normalize_name 更激进，适用于判断两个名称是否指向同一实体
    
    Args:
        name: 原始名称
        
    Returns:
        适用于匹配的标准化名称
    """
    result = normalize_name(name)
    
    # 额外处理：转小写（针对英文名）
    result = result.lower()
    
    # 去除所有空格
    result = result.replace(' ', '')
    
    return result


def is_same_person(name1: str, name2: str) -> bool:
    """
    判断两个名称是否指向同一人
    
    Args:
        name1: 第一个名称
        name2: 第二个名称
        
    Returns:
        是否同一人
    """
    if not name1 or not name2:
        return False
    
    norm1 = normalize_for_matching(name1)
    norm2 = normalize_for_matching(name2)
    
    return norm1 == norm2


def find_best_match(target: str, candidates: list) -> Optional[str]:
    """
    从候选列表中找到与目标名称匹配的最佳项
    
    Args:
        target: 目标名称
        candidates: 候选名称列表
        
    Returns:
        匹配到的候选项，如无匹配则返回 None
    """
    if not target or not candidates:
        return None
    
    target_norm = normalize_for_matching(target)
    
    for candidate in candidates:
        if normalize_for_matching(candidate) == target_norm:
            return candidate
    
    return None
