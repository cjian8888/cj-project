#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数库 - 资金穿透与关联排查系统
提供日期解析、金额处理、文本标准化等通用功能
"""

import re
import logging
from datetime import datetime
import pandas as pd
from typing import Optional, Union, List
import config


def setup_logger(name: str = 'AuditSystem') -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # 避免重复添加handler
    if not logger.handlers:
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 文件处理器
        file_handler = logging.FileHandler(config.OUTPUT_LOG_FILE, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 格式化器
        formatter = logging.Formatter(config.LOG_FORMAT, config.LOG_DATE_FORMAT)
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    
    return logger


def parse_date(date_str: Union[str, datetime]) -> Optional[datetime]:
    """
    智能解析日期字符串
    
    Args:
        date_str: 日期字符串或datetime对象
        
    Returns:
        datetime对象,解析失败返回None
    """
    if isinstance(date_str, datetime):
        return date_str
    
    if not date_str or str(date_str).strip() == '':
        return None
    
    date_str = str(date_str).strip()
    
    # 尝试各种日期格式
    for fmt in config.DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # 尝试pandas的通用解析
    try:
        import pandas as pd
        return pd.to_datetime(date_str)
    except Exception:
        pass
    
    return None


def format_amount(amount: Union[int, float, str]) -> float:
    """
    标准化金额格式
    
    Args:
        amount: 金额（可能包含逗号、货币符号等）
        
    Returns:
        浮点数金额
    """
    if amount is None or amount == '':
        return 0.0
    
    if isinstance(amount, (int, float)):
        return float(amount)
    
    # 移除货币符号、逗号、空格等
    amount_str = str(amount).replace(',', '').replace('¥', '').replace('￥', '')
    amount_str = amount_str.replace('元', '').replace(' ', '').strip()
    
    try:
        return float(amount_str)
    except ValueError:
        return 0.0


def is_amount_similar(amount1: float, amount2: float, tolerance: float = None) -> bool:
    """
    判断两个金额是否相近
    
    Args:
        amount1: 金额1
        amount2: 金额2
        tolerance: 容差比例,默认使用配置中的值
        
    Returns:
        是否相近
    """
    if tolerance is None:
        tolerance = config.AMOUNT_TOLERANCE_RATIO
    
    if amount1 == 0 and amount2 == 0:
        return True
    
    if amount1 == 0 or amount2 == 0:
        return False
    
    diff_ratio = abs(amount1 - amount2) / max(amount1, amount2)
    return diff_ratio <= tolerance


def is_within_time_window(date1: datetime, date2: datetime, hours: int = None) -> bool:
    """
    判断两个日期是否在指定时间窗口内
    
    Args:
        date1: 日期1
        date2: 日期2
        hours: 时间窗口(小时),默认使用配置中的值
        
    Returns:
        是否在时间窗口内
    """
    if hours is None:
        hours = config.CASH_TIME_WINDOW_HOURS
    
    time_diff = abs((date1 - date2).total_seconds() / 3600)
    return time_diff <= hours


def contains_keywords(text: str, keywords: List[str]) -> bool:
    """
    检查文本是否包含任意关键词
    
    Args:
        text: 待检查的文本
        keywords: 关键词列表
        
    Returns:
        是否包含
    """
    if not text:
        return False
    
    text = str(text).lower()
    return any(keyword.lower() in text for keyword in keywords)


def extract_keywords(text: str, keywords: List[str]) -> List[str]:
    """
    提取文本中出现的关键词
    
    Args:
        text: 待检查的文本
        keywords: 关键词列表
        
    Returns:
        匹配到的关键词列表
    """
    if not text:
        return []
    
    text = str(text).lower()
    matched = []
    for keyword in keywords:
        if keyword.lower() in text:
            matched.append(keyword)
    
    return matched


def normalize_name(name: str) -> str:
    """
    标准化人名/公司名
    
    Args:
        name: 原始名称
        
    Returns:
        标准化后的名称
    """
    if not name:
        return ''
    
    # 移除多余空格
    name = re.sub(r'\s+', '', str(name))
    # 移除特殊字符
    name = re.sub(r'[^\w\u4e00-\u9fa5]', '', name)
    
    return name.strip()


def extract_chinese_name(text: str) -> List[str]:
    """
    从文本中提取中文姓名(2-4个汉字)
    
    Args:
        text: 待提取的文本
        
    Returns:
        提取到的姓名列表
    """
    if not text:
        return []
    
    # 匹配2-4个汉字的姓名模式
    pattern = r'[\u4e00-\u9fa5]{2,4}'
    matches = re.findall(pattern, str(text))
    
    # 过滤常见的非姓名词汇（包括银行、征信、法律、金融术语等）
    exclude_words = [
        # 公司相关
        '有限公司', '股份', '集团', '投资', '管理', '科技', '发展', '公司', '银行',
        '中心', '信用卡', '融资', '贷款', '信用', '征信', '股份有限', '有限责任',
        # 金融/业务术语
        '还款', '透支', '逾期', '销户', '审查', '循环', '授信', '利息', '保证',
        '抵押', '担保', '清偿', '结清', '催收', '违约', '预期', '资金', '资产',
        '负债', '余额', '本息', '账户', '账单', '金额', '期限', '日期', '时间',
        '交易', '记录', '报告', '查询', '实名', '认证', '证件', '类型', '状态',
        # 制度/规定相关
        '规定', '说明', '条款', '合同', '协议', '法规', '规则', '制度', '办法',
        '程序', '流程', '步骤', '方式', '方法', '标准', '要求', '条件', '范围',
        # 银行/机构名称片段
        '浦东', '民生', '招商', '建设', '工商', '农业', '交通', '光大', '华夏',
        '广发', '兴业', '平安', '中信', '浦发', '邮政', '储蓄', '信托', '证券',
        # 其他常见非名词
        '信息', '数据', '内容', '材料', '文件', '表格', '系统', '平台', '机构',
        '部门', '单位', '企业', '个人', '用户', '客户', '人员', '成员', '名单',
        '序号', '编号', '号码', '地址', '电话', '邮件', '网址', '备注', '说明书',
    ]
    
    names = []
    for match in matches:
        # 排除包含关键词的匹配项
        if not any(word in match for word in exclude_words):
            # 额外过滤：长度为4的需要更严格（很多术语是4字）
            if len(match) == 4:
                # 4字词需要不包含常见后缀
                four_char_exclude = ['报告', '中心', '银行', '服务', '系统', '分析']
                if any(match.endswith(w) for w in four_char_exclude):
                    continue
            names.append(match)
    
    return list(set(names))  # 去重


def extract_company_name(text: str) -> List[str]:
    """
    从文本中提取公司名称
    
    Args:
        text: 待提取的文本
        
    Returns:
        提取到的公司名称列表
    """
    if not text:
        return []
    
    # 匹配包含公司标识的名称
    company_suffixes = [
        '有限公司', '股份有限公司', '有限责任公司',
        '集团', '企业', '经营部', '商行', '中心',
        '工作室', '合伙企业', '个体户'
    ]
    
    companies = []
    for suffix in company_suffixes:
        # 查找以公司标识结尾的文本
        pattern = f'[\u4e00-\u9fa5()（）\\w]+{suffix}'
        matches = re.findall(pattern, str(text))
        companies.extend(matches)
    
    return list(set(companies))  # 去重


def format_currency(amount: float) -> str:
    """
    格式化金额为货币显示
    
    Args:
        amount: 金额（单位：元）
        
    Returns:
        格式化后的字符串，如：¥367.72万、¥-125.69万、¥6,305.52
    """
    abs_amount = abs(amount)
    sign = '' if amount >= 0 else '-'
    
    if abs_amount >= 100000000:  # 亿
        return f'¥{sign}{abs_amount/100000000:.2f}亿'
    elif abs_amount >= 10000:  # 万
        return f'¥{sign}{abs_amount/10000:.2f}万'
    else:
        return f'¥{sign}{abs_amount:,.2f}'


def calculate_date_range(dates: List[datetime]) -> tuple:
    """
    计算日期范围
    
    Args:
        dates: 日期列表
        
    Returns:
        (最早日期, 最晚日期)
    """
    if not dates:
        return None, None
    
    valid_dates = [d for d in dates if d is not None]
    if not valid_dates:
        return None, None
    
    return min(valid_dates), max(valid_dates)


def get_month_key(date: datetime) -> str:
    """
    获取月份键值(用于分组)
    
    Args:
        date: 日期
        
    Returns:
        格式为'YYYY-MM'的字符串
    """
    if not date or pd.isna(date):
        return ''
    
    return date.strftime('%Y-%m')


def get_day_of_month(date: datetime) -> int:
    """
    获取日期在月份中的天数
    
    Args:
        date: 日期
        
    Returns:
        天数(1-31)
    """
    if not date or pd.isna(date):
        return 0
    
    return date.day


def clean_text(text: str) -> str:
    """
    清理文本(移除特殊字符、多余空格等)
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    if not text:
        return ''
    
    # 移除多余空格和换行
    text = re.sub(r'\s+', ' ', str(text))
    text = text.strip()
    
    return text


def extract_bank_name(filename: str) -> str:
    """
    从文件名中提取银行名称
    
    Args:
        filename: 文件名
        
    Returns:
        银行名称
    """
    # 常见银行名称列表
    banks = [
        '中国工商银行', '工商银行', '工行',
        '中国建设银行', '建设银行', '建行',
        '中国农业银行', '农业银行', '农行',
        '中国银行', '中行',
        '交通银行', '交行',
        '招商银行', '招行',
        '中国邮政储蓄银行', '邮政储蓄银行', '邮储银行', '邮储',
        '上海浦东发展银行', '浦东发展银行', '浦发银行', '浦发',
        '广东发展银行', '广发银行', '广发',
        '中信银行',
        '光大银行',
        '民生银行',
        '兴业银行',
        '平安银行',
        '华夏银行',
        '上海农村商业银行', '农村商业银行', '农商银行'
    ]
    
    filename_lower = filename.lower()
    
    for bank in banks:
        if bank in filename:
            # 标准化银行名称
            if bank in ['工商银行', '工行', '中国工商银行']:
                return '工商银行'
            elif bank in ['建设银行', '建行', '中国建设银行']:
                return '建设银行'
            elif bank in ['农业银行', '农行', '中国农业银行']:
                return '农业银行'
            elif bank in ['中国银行', '中行']:
                return '中国银行'
            elif bank in ['交通银行', '交行']:
                return '交通银行'
            elif bank in ['招商银行', '招行']:
                return '招商银行'
            elif bank in ['邮政储蓄银行', '邮储银行', '邮储', '中国邮政储蓄银行']:
                return '邮储银行'
            elif bank in ['浦东发展银行', '浦发银行', '浦发', '上海浦东发展银行']:
                return '浦发银行'
            elif bank in ['广东发展银行', '广发银行', '广发']:
                return '广发银行'
            else:
                return bank
    
    return '未知银行'


def normalize_person_name(name: str) -> str:
    """
    标准化人名(去除身份证号等)
    
    Args:
        name: 原始名称
        
    Returns:
        标准化后的名称
    """
    if not name:
        return ''
    
    # 移除身份证号(18位或15位数字)
    name = re.sub(r'_\d{15,18}', '', name)
    
    # 移除其他数字和特殊字符
    name = re.sub(r'[_\d]+', '', name)
    
    # 移除空格
    name = name.replace(' ', '')
    
    return name.strip()

def number_to_chinese(n):
    """
    将阿拉伯数字转换为中文数字 (支持1-99)
    """
    if not isinstance(n, int):
        return str(n)
        
    chars = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    
    if 0 < n < 10:
        return chars[n]
    elif 10 <= n < 20:
        return "十" + (chars[n%10] if n%10!=0 else "")
    elif 20 <= n < 100:
        return chars[n//10] + "十" + (chars[n%10] if n%10!=0 else "")
    else:
        return str(n)


def safe_str(value, default: str = "-", max_len: int = None) -> str:
    """
    安全地将任何值转换为字符串，处理 NaN、None 等特殊值
    
    Args:
        value: 任意值
        default: NaN/None/空值时的默认替换文本
        max_len: 可选，最大长度限制
        
    Returns:
        安全的字符串，不会返回 "nan" 或 "None"
    """
    if value is None:
        return default
    
    # 处理 pandas 的 NA/NaN
    if pd.isna(value):
        return default
    
    # 转换为字符串
    s = str(value).strip()
    
    # 检查是否为空或 nan 字符串
    if not s or s.lower() in ('nan', 'none', 'null', ''):
        return default
    
    # 长度限制
    if max_len and len(s) > max_len:
        s = s[:max_len-3] + '...'
    
    return s


def safe_account_display(account: str, mask: bool = False) -> str:
    """
    安全地显示账号，处理 NaN 并可选脱敏
    
    Args:
        account: 账号字符串
        mask: 是否脱敏（只显示后4位）
        
    Returns:
        安全的账号显示字符串
    """
    s = safe_str(account, default="未知账号")
    if s == "未知账号":
        return s
    
    if mask and len(s) > 4:
        return f"****{s[-4:]}"
    
    # 如果账号较长，显示后8位
    if len(s) > 8:
        return s[-8:]
    
    return s
