#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节假日服务模块

【模块定位】
提供中国法定节假日查询与节日前后窗口构建服务。
支持多种数据源：
1. chinese-calendar 库（首选，适合离线打包）
2. config.py 中的本地节假日配置
3. holiday_utils.py 中的规则回退

创建日期: 2026-01-18
"""

from datetime import datetime, date, timedelta
from typing import Any, Optional, List, Tuple, Set, Dict

import utils

logger = utils.setup_logger(__name__)

HolidayRange = Tuple[date, date, str]
HolidayWindowInfo = Tuple[str, str]

ENGLISH_HOLIDAY_NAME_MAP = {
    "New Year's Day": "元旦",
    "Spring Festival": "春节",
    "Tomb-sweeping Day": "清明节",
    "Labour Day": "劳动节",
    "Labor Day": "劳动节",
    "Dragon Boat Festival": "端午节",
    "Mid-autumn Festival": "中秋节",
    "National Day": "国庆节",
}


class HolidayService:
    """
    中国法定节假日服务
    
    优先使用 chinese-calendar 库，如未安装则回退到本地配置
    """
    
    def __init__(self):
        self._use_library = False
        self._cached_holidays: Set[date] = set()
        self._cached_workdays: Set[date] = set()  # 调休工作日
        self._cached_holiday_names: Dict[date, str] = {}
        self._year_range_cache: Dict[int, List[HolidayRange]] = {}
        self._fallback_loaded = False
        self._init_service()
    
    def _init_service(self):
        """初始化服务"""
        try:
            import chinese_calendar
            _ = chinese_calendar
            self._use_library = True
            logger.info('节假日服务: 使用 chinese-calendar 库')
        except ImportError:
            logger.warning('chinese-calendar 未安装，使用本地配置。可通过 pip install chinese-calendar 安装')
            self._load_local_config()

    def _load_local_config(self):
        """加载本地配置（从 config.py）"""
        if self._fallback_loaded:
            return

        try:
            import config
            for year, holidays in getattr(config, 'CHINESE_HOLIDAYS', {}).items():
                normalized = self._normalize_holiday_ranges(holidays)
                self._year_range_cache[year] = normalized
                self._cache_holiday_ranges(normalized)
            self._fallback_loaded = True
            logger.info(f'已加载 {len(self._cached_holidays)} 天本地节假日配置')
        except Exception as e:
            logger.error(f'加载本地配置失败: {e}')

    def _normalize_holiday_ranges(
        self, holidays: List[Tuple[str, str, str]]
    ) -> List[HolidayRange]:
        """将字符串形式的节假日区间标准化为 date 元组。"""
        normalized: List[HolidayRange] = []
        for start_str, end_str, name in holidays:
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_str, '%Y-%m-%d').date()
            normalized.append((start, end, name))
        return normalized

    def _cache_holiday_ranges(self, holidays: List[HolidayRange]) -> None:
        """将节假日区间缓存到按日查询结构。"""
        for start, end, name in holidays:
            current = start
            while current <= end:
                self._cached_holidays.add(current)
                self._cached_holiday_names.setdefault(current, name)
                current += timedelta(days=1)

    @staticmethod
    def _resolve_holiday_name(detail: Any) -> str:
        """兼容不同版本 chinese-calendar 的节日详情返回结构。"""
        raw_name = detail
        if isinstance(detail, tuple):
            if len(detail) > 1:
                raw_name = detail[1]
            elif detail:
                raw_name = detail[0]
            else:
                raw_name = None

        if hasattr(raw_name, "chinese"):
            raw_name = getattr(raw_name, "chinese", None)

        if raw_name is None:
            return "节假日"

        normalized = str(raw_name).strip()
        if not normalized:
            return "节假日"

        return ENGLISH_HOLIDAY_NAME_MAP.get(normalized, normalized)

    def _build_ranges_from_library(self, year: int) -> List[HolidayRange]:
        """从 chinese-calendar 动态生成指定年份的节假日区间。"""
        import chinese_calendar

        ranges: List[HolidayRange] = []
        current = date(year, 1, 1)
        year_end = date(year, 12, 31)

        range_start: Optional[date] = None
        range_end: Optional[date] = None
        range_name: Optional[str] = None

        while current <= year_end:
            if chinese_calendar.is_holiday(current):
                detail = chinese_calendar.get_holiday_detail(current)
                name = self._resolve_holiday_name(detail)

                if (
                    range_start is not None
                    and range_end is not None
                    and current == range_end + timedelta(days=1)
                    and name == range_name
                ):
                    range_end = current
                else:
                    if range_start is not None and range_end is not None and range_name:
                        ranges.append((range_start, range_end, range_name))
                    range_start = current
                    range_end = current
                    range_name = name
            else:
                if range_start is not None and range_end is not None and range_name:
                    ranges.append((range_start, range_end, range_name))
                    range_start = None
                    range_end = None
                    range_name = None

                if current.weekday() >= 5 and chinese_calendar.is_workday(current):
                    self._cached_workdays.add(current)

            current += timedelta(days=1)

        if range_start is not None and range_end is not None and range_name:
            ranges.append((range_start, range_end, range_name))

        self._cache_holiday_ranges(ranges)
        return ranges

    def _get_fallback_ranges_for_year(self, year: int) -> List[HolidayRange]:
        """获取本地配置或规则回退生成的节假日区间。"""
        self._load_local_config()

        if year in self._year_range_cache:
            return list(self._year_range_cache[year])

        try:
            from holiday_utils import get_holidays_for_year

            generated = self._normalize_holiday_ranges(get_holidays_for_year(year))
            self._year_range_cache[year] = generated
            self._cache_holiday_ranges(generated)
            logger.info(f'节假日服务: 使用规则回退生成 {year} 年节假日区间')
            return list(generated)
        except Exception as e:
            logger.error(f'生成 {year} 年节假日区间失败: {e}')
            return []

    def get_holiday_ranges_for_year(self, year: int) -> List[HolidayRange]:
        """获取指定年份的节假日区间。"""
        if year in self._year_range_cache:
            return list(self._year_range_cache[year])

        if self._use_library:
            try:
                ranges = self._build_ranges_from_library(year)
                self._year_range_cache[year] = ranges
                return list(ranges)
            except Exception as e:
                logger.warning(f'chinese-calendar 查询 {year} 年节假日失败，回退本地配置: {e}')
                self._use_library = False

        ranges = self._get_fallback_ranges_for_year(year)
        self._year_range_cache[year] = list(ranges)
        return list(ranges)

    def get_holiday_ranges_in_range(
        self,
        start_date: date,
        end_date: date,
    ) -> List[HolidayRange]:
        """获取时间区间内的节假日区间。"""
        if start_date > end_date:
            return []

        matched: List[HolidayRange] = []
        for year in range(start_date.year, end_date.year + 1):
            for holiday_start, holiday_end, name in self.get_holiday_ranges_for_year(year):
                if holiday_end < start_date or holiday_start > end_date:
                    continue
                matched.append(
                    (
                        max(holiday_start, start_date),
                        min(holiday_end, end_date),
                        name,
                    )
                )

        matched.sort(key=lambda item: (item[0], item[1], item[2]))
        return matched

    def build_holiday_window(
        self,
        start_date: date,
        end_date: date,
        days_before: int = 3,
        days_after: int = 2,
    ) -> Dict[date, HolidayWindowInfo]:
        """按数据时间范围构建节前/节中/节后检测窗口。"""
        if start_date > end_date:
            return {}

        window: Dict[date, HolidayWindowInfo] = {}
        query_start = start_date - timedelta(days=max(days_before, 0))
        query_end = end_date + timedelta(days=max(days_after, 0))

        def assign_window(target_date: date, name: str, period: str) -> None:
            if target_date < start_date or target_date > end_date:
                return

            existing = window.get(target_date)
            priority = {'during': 3, 'before': 2, 'after': 2}
            if existing and priority.get(existing[1], 0) >= priority.get(period, 0):
                return
            window[target_date] = (name, period)

        for holiday_start, holiday_end, name in self.get_holiday_ranges_in_range(
            query_start, query_end
        ):
            for offset in range(days_before, 0, -1):
                assign_window(holiday_start - timedelta(days=offset), name, 'before')

            current = holiday_start
            while current <= holiday_end:
                assign_window(current, name, 'during')
                current += timedelta(days=1)

            for offset in range(1, days_after + 1):
                assign_window(holiday_end + timedelta(days=offset), name, 'after')

        return window

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
            except Exception as e:
                logger.warning(f'chinese-calendar 判断节假日失败，回退本地配置: {e}')
                self._use_library = False

        self.get_holiday_ranges_for_year(check_date.year)
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
            except Exception as e:
                logger.warning(f'chinese-calendar 判断工作日失败，回退本地配置: {e}')
                self._use_library = False

        self.get_holiday_ranges_for_year(check_date.year)
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
                    return self._resolve_holiday_name(detail)
            except Exception as e:
                logger.warning(f'chinese-calendar 获取节假日名称失败，回退本地配置: {e}')
                self._use_library = False

        self.get_holiday_ranges_for_year(check_date.year)
        return self._cached_holiday_names.get(check_date)

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
        for holiday_start, holiday_end, name in self.get_holiday_ranges_in_range(
            start_date, end_date
        ):
            current = holiday_start
            while current <= holiday_end:
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
        window = self.build_holiday_window(
            check_date,
            check_date,
            days_before=days_before,
            days_after=days_after,
        )
        if check_date in window:
            name, _ = window[check_date]
            return True, name

        return False, None

    def get_holiday_window_info(
        self,
        check_date: date,
        days_before: int = 3,
        days_after: int = 2,
    ) -> Tuple[bool, Optional[str], str]:
        """获取指定日期是否处于节前/节中/节后窗口。"""
        window = self.build_holiday_window(
            check_date,
            check_date,
            days_before=days_before,
            days_after=days_after,
        )
        info = window.get(check_date)
        if not info:
            return False, None, ''

        name, period = info
        return True, name, period


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


def get_holiday_ranges_in_range(
    start_date: date,
    end_date: date,
) -> List[HolidayRange]:
    """获取时间范围内的节假日区间。"""
    return get_holiday_service().get_holiday_ranges_in_range(start_date, end_date)


def build_holiday_window(
    start_date: date,
    end_date: date,
    days_before: int = 3,
    days_after: int = 2,
) -> Dict[date, HolidayWindowInfo]:
    """构建节前/节中/节后检测窗口。"""
    return get_holiday_service().build_holiday_window(
        start_date,
        end_date,
        days_before=days_before,
        days_after=days_after,
    )
