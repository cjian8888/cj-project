#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
节假日工具模块 - 资金穿透与关联排查系统
自动生成指定年份的中国法定节假日日期

功能:
1. 根据数据时间范围自动生成节假日日期
2. 支持阴历节日推算（春节、端午、中秋）
3. 提供节假日窗口检测（节前、节中、节后）
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Set, Tuple
import utils

logger = utils.setup_logger(__name__)


# ============== 阴历节日对照表（2020-2030年） ==============
# 由于阴历计算复杂，这里提供查表法
# 格式: year -> (春节日期, 端午日期, 中秋日期)
LUNAR_HOLIDAYS = {
    2020: ('2020-01-25', '2020-06-25', '2020-10-01'),
    2021: ('2021-02-12', '2021-06-14', '2021-09-21'),
    2022: ('2022-02-01', '2022-06-03', '2022-09-10'),
    2023: ('2023-01-22', '2023-06-22', '2023-09-29'),
    2024: ('2024-02-10', '2024-06-10', '2024-09-17'),
    2025: ('2025-01-29', '2025-05-31', '2025-10-06'),
    2026: ('2026-02-17', '2026-06-19', '2026-10-25'),
    2027: ('2027-02-06', '2027-06-09', '2027-10-15'),
    2028: ('2028-01-26', '2028-05-28', '2028-10-03'),
    2029: ('2029-02-13', '2029-06-16', '2029-09-22'),
    2030: ('2030-02-03', '2030-06-05', '2030-09-12'),
}


def get_holidays_for_year(year: int) -> List[Tuple[str, str, str]]:
    """
    获取指定年份的法定节假日列表
    
    Args:
        year: 年份
        
    Returns:
        [(开始日期, 结束日期, 节日名称), ...]
    """
    holidays = []
    
    # 1. 元旦 (1月1日，放假1-3天)
    holidays.append((f'{year}-01-01', f'{year}-01-01', '元旦'))
    
    # 2. 春节 (阴历正月初一，放假7天)
    if year in LUNAR_HOLIDAYS:
        spring_str = LUNAR_HOLIDAYS[year][0]
        spring = datetime.strptime(spring_str, '%Y-%m-%d')
        # 从除夕开始放假7天
        start = spring - timedelta(days=1)  # 除夕
        end = spring + timedelta(days=6)    # 初六
        holidays.append((start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), '春节'))
    
    # 3. 清明节 (4月4-6日，每年略有变化，取4月4-6日)
    holidays.append((f'{year}-04-04', f'{year}-04-06', '清明节'))
    
    # 4. 劳动节 (5月1日，放假5天)
    holidays.append((f'{year}-05-01', f'{year}-05-05', '劳动节'))
    
    # 5. 端午节 (阴历五月初五，放假3天)
    if year in LUNAR_HOLIDAYS:
        duanwu_str = LUNAR_HOLIDAYS[year][1]
        duanwu = datetime.strptime(duanwu_str, '%Y-%m-%d')
        start = duanwu
        end = duanwu + timedelta(days=2)
        holidays.append((start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), '端午节'))
    
    # 6. 中秋节 (阴历八月十五，放假3天)
    if year in LUNAR_HOLIDAYS:
        zhongqiu_str = LUNAR_HOLIDAYS[year][2]
        zhongqiu = datetime.strptime(zhongqiu_str, '%Y-%m-%d')
        start = zhongqiu
        end = zhongqiu + timedelta(days=2)
        holidays.append((start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), '中秋节'))
    
    # 7. 国庆节 (10月1日，放假7天)
    holidays.append((f'{year}-10-01', f'{year}-10-07', '国庆节'))
    
    return holidays


def get_holidays_for_range(start_date: date, end_date: date) -> Dict[int, List[Tuple[str, str, str]]]:
    """
    根据数据时间范围生成覆盖的所有节假日
    
    Args:
        start_date: 数据开始日期
        end_date: 数据结束日期
        
    Returns:
        {年份: [(开始日期, 结束日期, 节日名称), ...]}
    """
    result = {}
    
    for year in range(start_date.year, end_date.year + 1):
        result[year] = get_holidays_for_year(year)
    
    return result


def build_holiday_window(
    holidays_config: Dict[int, List[Tuple[str, str, str]]],
    days_before: int = 3,
    days_after: int = 2
) -> Tuple[Set[date], Dict[date, Tuple[str, str]]]:
    """
    构建节假日检测窗口（含节前节后）
    
    Args:
        holidays_config: 节假日配置 {年份: [(开始, 结束, 名称)]}
        days_before: 节前天数（送礼高峰）
        days_after: 节后天数（回礼/谢礼）
        
    Returns:
        (holiday_dates_set, holiday_info_dict)
        - holiday_dates_set: 所有需要检测的日期集合
        - holiday_info_dict: {日期: (节日名称, 时段类型)}
          时段类型: 'before'=节前, 'during'=节中, 'after'=节后
    """
    holiday_dates = set()
    holiday_info = {}
    
    for year, holidays in holidays_config.items():
        for start_str, end_str, name in holidays:
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_str, '%Y-%m-%d').date()
            
            # 节前窗口
            for i in range(1, days_before + 1):
                d = start - timedelta(days=i)
                holiday_dates.add(d)
                holiday_info[d] = (name, 'before')
            
            # 节中
            current = start
            while current <= end:
                holiday_dates.add(current)
                holiday_info[current] = (name, 'during')
                current += timedelta(days=1)
            
            # 节后窗口
            for i in range(1, days_after + 1):
                d = end + timedelta(days=i)
                holiday_dates.add(d)
                holiday_info[d] = (name, 'after')
    
    return holiday_dates, holiday_info


def analyze_data_time_range(transactions_data: Dict) -> Tuple[date, date]:
    """
    分析交易数据的时间范围
    
    Args:
        transactions_data: {实体名: DataFrame}
        
    Returns:
        (最早日期, 最晚日期)
    """
    import pandas as pd
    
    all_dates = []
    
    for entity_name, df in transactions_data.items():
        if df.empty:
            continue
        
        # 尝试多种日期列名
        date_cols = ['date', '交易时间', 'transaction_time']
        for col in date_cols:
            if col in df.columns:
                dates = pd.to_datetime(df[col], errors='coerce').dropna()
                if len(dates) > 0:
                    all_dates.extend(dates.dt.date.tolist())
                break
    
    if not all_dates:
        # 默认返回当前年份
        now = datetime.now()
        return date(now.year, 1, 1), date(now.year, 12, 31)
    
    return min(all_dates), max(all_dates)


class HolidayDetector:
    """
    节假日检测器类
    根据数据时间范围自动初始化节假日配置
    """
    
    def __init__(self, start_date: date = None, end_date: date = None, 
                 days_before: int = 3, days_after: int = 2):
        """
        初始化节假日检测器
        
        Args:
            start_date: 数据开始日期（如不指定则使用默认范围）
            end_date: 数据结束日期
            days_before: 节前窗口天数
            days_after: 节后窗口天数
        """
        self.days_before = days_before
        self.days_after = days_after
        
        if start_date and end_date:
            self._init_from_range(start_date, end_date)
        else:
            # 默认使用近3年
            now = datetime.now()
            self._init_from_range(
                date(now.year - 1, 1, 1),
                date(now.year + 1, 12, 31)
            )
    
    def _init_from_range(self, start_date: date, end_date: date):
        """根据时间范围初始化"""
        self.start_date = start_date
        self.end_date = end_date
        
        # 生成节假日配置
        self.holidays_config = get_holidays_for_range(start_date, end_date)
        
        # 构建检测窗口
        self.holiday_dates, self.holiday_info = build_holiday_window(
            self.holidays_config, self.days_before, self.days_after
        )
        
        logger.info(f'节假日检测器初始化: {start_date} ~ {end_date}, '
                   f'覆盖 {len(self.holiday_dates)} 个检测日期')
    
    @classmethod
    def from_transactions(cls, transactions_data: Dict[str, pd.DataFrame], 
                          days_before: int = 3, days_after: int = 2):
        """
        从交易数据自动分析时间范围并初始化
        
        Args:
            transactions_data: 交易数据字典
            days_before: 节前窗口天数
            days_after: 节后窗口天数
        """
        start_date, end_date = analyze_data_time_range(transactions_data)
        return cls(start_date, end_date, days_before, days_after)
    
    def is_holiday_window(self, check_date: date) -> Tuple[bool, str, str]:
        """
        检查日期是否在节假日窗口内
        
        Args:
            check_date: 要检查的日期
            
        Returns:
            (是否在窗口内, 节日名称, 时段类型)
            时段类型: 'before', 'during', 'after', None
        """
        if isinstance(check_date, datetime):
            check_date = check_date.date()
        
        if check_date in self.holiday_dates:
            name, period = self.holiday_info[check_date]
            return True, name, period
        
        return False, '', ''
    
    def get_risk_level(self, check_date: date, amount: float, 
                       threshold: float = 50000) -> str:
        """
        根据日期和金额判断风险等级
        
        Args:
            check_date: 交易日期
            amount: 交易金额
            threshold: 大额阈值
            
        Returns:
            风险等级: 'high', 'medium', 'low'
        """
        is_holiday, name, period = self.is_holiday_window(check_date)
        
        if not is_holiday:
            return 'low'
        
        # 节前送礼风险最高
        if period == 'before' and amount >= threshold:
            return 'high'
        
        # 节中大额也是高风险
        if period == 'during' and amount >= threshold * 2:
            return 'high'
        
        # 节后回礼中等风险
        if period == 'after' and amount >= threshold:
            return 'medium'
        
        # 其他情况
        if amount >= threshold:
            return 'medium'
        
        return 'low'
    
    def get_summary(self) -> Dict:
        """获取节假日覆盖摘要"""
        summary = {
            'date_range': (self.start_date, self.end_date),
            'years_covered': list(self.holidays_config.keys()),
            'total_detection_days': len(self.holiday_dates),
            'window_config': {
                'days_before': self.days_before,
                'days_after': self.days_after
            },
            'holidays_by_year': {}
        }
        
        for year, holidays in self.holidays_config.items():
            summary['holidays_by_year'][year] = [h[2] for h in holidays]
        
        return summary


# 便捷函数
def create_detector_from_data(transactions_data: Dict, 
                               days_before: int = 3, 
                               days_after: int = 2) -> HolidayDetector:
    """
    从交易数据创建节假日检测器（便捷函数）
    
    Args:
        transactions_data: 交易数据字典
        days_before: 节前窗口天数（默认3天）
        days_after: 节后窗口天数（默认2天）
    """
    return HolidayDetector.from_transactions(
        transactions_data, days_before, days_after
    )
