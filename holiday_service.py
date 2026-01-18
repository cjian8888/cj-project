#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节假日服务模块

【模块定位】
提供中国法定节假日查询服务，替代 config.py 中的硬编码配置。
支持多种数据源：
1. chinese-calendar 库（首选）
2. 本地缓存文件
3. 硬编码回退

创建日期: 2026-01-18
"""

import os
from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple, Set
from functools import lru_cache

import utils

logger = utils.setup_logger(__name__)


class HolidayService:
    """
    中国法定节假日服务
    
    优先使用 chinese-calendar 库，如未安装则回退到本地配置
    """
    
    def __init__(self):
        self._use_library = False
        self._cached_holidays: Set[date] = set()
        self._cached_workdays: Set[date] = set()  # 调休工作日
        self._init_service()
    
    def _init_service(self):
        """初始化服务"""
        try:
            import chinese_calendar
            self._use_library = True
            logger.info('节假日服务: 使用 chinese-calendar 库')
        except ImportError:
            logger.warning('chinese-calendar 未安装，使用本地配置。可通过 pip install chinese-calendar 安装')
            self._load_local_config()
    
    def _load_local_config(self):
        """加载本地配置（从 config.py）"""
        try:
            import config
            for year, holidays in getattr(config, 'CHINESE_HOLIDAYS', {}).items():
                for start_str, end_str, name in holidays:
                    start = datetime.strptime(start_str, '%Y-%m-%d').date()
                    end = datetime.strptime(end_str, '%Y-%m-%d').date()
                    current = start
                    while current <= end:
                        self._cached_holidays.add(current)
                        current += timedelta(days=1)
            logger.info(f'已加载 {len(self._cached_holidays)} 天本地节假日配置')
        except Exception as e:
            logger.error(f'加载本地配置失败: {e}')
    
    def is_holiday(self, check_date: date) -> bool:
        """
        判断是否为法定节假日
        
        Args:
            check_date: 要检查的日期
            
        Returns:
            是否为节假日
        """
        if self._use_library:
            try:
                import chinese_calendar
                return chinese_calendar.is_holiday(check_date)
            except Exception:
                pass
        
        return check_date in self._cached_holidays
    
    def is_workday(self, check_date: date) -> bool:
        """
        判断是否为工作日（考虑调休）
        
        Args:
            check_date: 要检查的日期
            
        Returns:
            是否为工作日
        """
        if self._use_library:
            try:
                import chinese_calendar
                return chinese_calendar.is_workday(check_date)
            except Exception:
                pass
        
        # 回退逻辑：周一至周五且非节假日
        if check_date.weekday() >= 5:  # 周六日
            return check_date in self._cached_workdays
        return check_date not in self._cached_holidays
    
    def get_holiday_name(self, check_date: date) -> Optional[str]:
        """
        获取节假日名称
        
        Args:
            check_date: 要检查的日期
            
        Returns:
            节假日名称，如不是节假日则返回 None
        """
        if self._use_library:
            try:
                import chinese_calendar
                if chinese_calendar.is_holiday(check_date):
                    detail = chinese_calendar.get_holiday_detail(check_date)
                    if detail[1]:
                        return detail[1].chinese
            except Exception:
                pass
        
        # 回退：从本地配置查找
        try:
            import config
            for year, holidays in getattr(config, 'CHINESE_HOLIDAYS', {}).items():
                for start_str, end_str, name in holidays:
                    start = datetime.strptime(start_str, '%Y-%m-%d').date()
                    end = datetime.strptime(end_str, '%Y-%m-%d').date()
                    if start <= check_date <= end:
                        return name
        except Exception:
            pass
        
        return None
    
    def get_holidays_in_range(
        self, 
        start_date: date, 
        end_date: date
    ) -> List[Tuple[date, str]]:
        """
        获取日期范围内的所有节假日
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            [(日期, 节假日名称), ...] 列表
        """
        holidays = []
        current = start_date
        
        while current <= end_date:
            if self.is_holiday(current):
                name = self.get_holiday_name(current) or "节假日"
                holidays.append((current, name))
            current += timedelta(days=1)
        
        return holidays
    
    def is_weekend(self, check_date: date) -> bool:
        """判断是否为周末"""
        return check_date.weekday() >= 5
    
    def is_near_holiday(
        self, 
        check_date: date, 
        days_before: int = 3, 
        days_after: int = 3
    ) -> Tuple[bool, Optional[str]]:
        """
        判断日期是否临近节假日
        
        用于检测"节前或节后"的异常交易模式
        
        Args:
            check_date: 要检查的日期
            days_before: 节前几天算临近
            days_after: 节后几天算临近
            
        Returns:
            (是否临近, 节假日名称)
        """
        for delta in range(-days_before, days_after + 1):
            target = check_date + timedelta(days=delta)
            name = self.get_holiday_name(target)
            if name:
                return True, name
        
        return False, None


# 全局单例
_holiday_service: Optional[HolidayService] = None


def get_holiday_service() -> HolidayService:
    """获取节假日服务单例"""
    global _holiday_service
    if _holiday_service is None:
        _holiday_service = HolidayService()
    return _holiday_service


# 便捷函数
def is_holiday(check_date: date) -> bool:
    """判断是否为节假日"""
    return get_holiday_service().is_holiday(check_date)


def is_workday(check_date: date) -> bool:
    """判断是否为工作日"""
    return get_holiday_service().is_workday(check_date)


def get_holiday_name(check_date: date) -> Optional[str]:
    """获取节假日名称"""
    return get_holiday_service().get_holiday_name(check_date)


def is_near_holiday(check_date: date) -> Tuple[bool, Optional[str]]:
    """判断是否临近节假日"""
    return get_holiday_service().is_near_holiday(check_date)
