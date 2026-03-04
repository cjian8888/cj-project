#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数库 - 资金穿透与关联排查系统
提供日期解析、金额处理、文本标准化等通用功能
"""

import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional, Union, List, Tuple, Dict, Any
import pandas as pd
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
    
    # 延迟获取日志级别，避免循环导入
    try:
        log_level = getattr(config, 'LOG_LEVEL', 'INFO')
        logger.setLevel(getattr(logging, log_level))
    except (AttributeError, ImportError):
        # 如果 config 模块尚未加载，使用默认值
        logger.setLevel(logging.INFO)
    
    # 避免重复添加handler
    if not logger.handlers:
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 文件处理器 - 使用轮转机制
        try:
            log_file = getattr(config, 'OUTPUT_LOG_FILE', 'audit_system.log')
            max_bytes = getattr(config, 'LOG_MAX_BYTES', 10 * 1024 * 1024)
            backup_count = getattr(config, 'LOG_BACKUP_COUNT', 5)
        except (AttributeError, ImportError):
            log_file = 'audit_system.log'
            max_bytes = 10 * 1024 * 1024
            backup_count = 5
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # 格式化器
        try:
            log_format = getattr(config, 'LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            date_format = getattr(config, 'LOG_DATE_FORMAT', '%Y-%m-%d %H:%M:%S')
        except (AttributeError, ImportError):
            log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            date_format = '%Y-%m-%d %H:%M:%S'
        
        formatter = logging.Formatter(log_format, date_format)
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
        return pd.to_datetime(date_str)
    except Exception:
        pass
    
    return None


def format_amount(amount: Union[int, float, str, None]) -> float:
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


def is_amount_similar(amount1: float, amount2: float, tolerance: Optional[float] = None) -> bool:
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


def is_within_time_window(date1: datetime, date2: datetime, hours: Optional[int] = None) -> bool:
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


def contains_keywords(text: Optional[str], keywords: List[str]) -> bool:
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


def extract_keywords(text: Optional[str], keywords: List[str]) -> List[str]:
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


def normalize_name(name: Optional[str]) -> str:
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
    name = re.sub(r'[^\w\u4e00-\u9fa5]', '', name)  # 保留中文、字母、数字和下划线
    
    return name.strip()


def extract_chinese_name(text: Optional[str]) -> List[str]:
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


def extract_company_name(text: Optional[str]) -> List[str]:
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
        # 使用非贪婪匹配，避免匹配过长的文本
        pattern = f'[\u4e00-\u9fa5()（）\\w]+?{suffix}'
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


def calculate_date_range(dates: List[datetime]) -> Tuple[Optional[datetime], Optional[datetime]]:
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


def format_date_str(date: Optional[Union[datetime, pd.Timestamp, str]]) -> str:
    """
    【P2新增】统一的日期格式化函数
    
    Args:
        date: 日期对象（datetime、pandas Timestamp 或字符串）
        
    Returns:
        格式为'YYYY-MM-DD'的字符串
    """
    if date is None or pd.isna(date):
        return ''
    
    # 如果是字符串，尝试解析
    if isinstance(date, str):
        parsed = parse_date(date)
        if parsed:
            return parsed.strftime('%Y-%m-%d')
        return date[:10] if len(date) >= 10 else date
    
    # datetime 或 pandas Timestamp
    try:
        return date.strftime('%Y-%m-%d')
    except (AttributeError, ValueError):
        return str(date)[:10]


def get_month_key(date: Optional[datetime]) -> str:
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


def get_day_of_month(date: Optional[datetime]) -> int:
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


def clean_text(text: Optional[str]) -> str:
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


def normalize_person_name(name: Optional[str]) -> str:
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

def number_to_chinese(n: int) -> str:
    """
    将阿拉伯数字转换为中文数字 (支持1-99)
    
    Args:
        n: 阿拉伯数字
        
    Returns:
        中文数字字符串
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


def safe_str(value: Any, default: str = "-", max_len: Optional[int] = None) -> str:
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


# ============================================================
# 报告时间戳管理 (2026-01-25 新增)
# ============================================================

# 全局报告时间戳（用于统一所有报告的时间）
_global_report_timestamp = None


def generate_report_timestamp() -> str:
    """
    生成统一的报告时间戳
    
    Returns:
        格式为'YYYY年MM月DD日 HH:MM:SS'的时间戳字符串
    """
    return datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')


def generate_report_timestamp_iso() -> str:
    """
    生成ISO格式的报告时间戳
    
    Returns:
        格式为'YYYY-MM-DDTHH:MM:SS'的ISO格式时间戳字符串
    """
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def set_global_report_timestamp(timestamp: str = None) -> str:
    """
    设置全局报告时间戳（用于批量生成报告时保持时间一致）
    
    Args:
        timestamp: 可选的时间戳字符串，如果为None则生成新的时间戳
    
    Returns:
        设置的时间戳字符串
    """
    global _global_report_timestamp
    if timestamp is None:
        _global_report_timestamp = generate_report_timestamp()
    else:
        _global_report_timestamp = timestamp
    return _global_report_timestamp


def get_global_report_timestamp() -> str:
    """
    获取全局报告时间戳
    
    Returns:
        全局时间戳字符串，如果未设置则返回当前时间
    """
    global _global_report_timestamp
    if _global_report_timestamp is None:
        _global_report_timestamp = generate_report_timestamp()
    return _global_report_timestamp


def reset_global_report_timestamp():
    """
    重置全局报告时间戳（下次调用时将生成新的时间戳）
    """
    global _global_report_timestamp
    _global_report_timestamp = None


# ============================================================
# 通用时间戳工具 (2026-03-04 新增)
# ============================================================

def get_timestamp() -> str:
    """
    获取当前时间戳（ISO格式，用于计算日志等场景）
    
    Returns:
        格式为'YYYY-MM-DD HH:MM:SS'的时间戳字符串
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# ============================================================
# 报告一致性验证 (2026-01-25 新增)
# ============================================================

def validate_report_consistency(json_data: Dict, html_report_path: str = None) -> List[str]:
    """
    验证JSON数据和HTML报告的一致性
    
    Args:
        json_data: JSON数据字典（派生数据）
        html_report_path: HTML报告文件路径（可选）
    
    Returns:
        一致性问题列表
    """
    issues = []
    
    if not json_data:
        return ['JSON数据为空']
    
    # 1. 检查资产总额一致性
    if 'total_assets' in json_data:
        json_total = json_data['total_assets'].get('total', 0)
        # 如果有HTML报告，可以解析并验证（这里简化处理）
        # 实际使用时需要解析HTML提取数据
        logger.debug(f'JSON资产总额: {json_total}')
    
    # 2. 检查收入分类一致性
    if 'income_classifications' in json_data:
        for person, classification in json_data['income_classifications'].items():
            json_ratio = classification.get('legitimate_ratio', 0)
            json_unknown_ratio = classification.get('unknown_ratio', 0)
            json_suspicious_ratio = classification.get('suspicious_ratio', 0)
            
            # 验证比例总和是否为1
            total_ratio = json_ratio + json_unknown_ratio + json_suspicious_ratio
            if abs(total_ratio - 1.0) > 0.01:  # 允许1%误差
                issues.append(
                    f'{person} 收入分类比例不一致: '
                    f'合法={json_ratio:.2%}, 不明={json_unknown_ratio:.2%}, '
                    f'可疑={json_suspicious_ratio:.2%}, 总和={total_ratio:.2%}'
                )
    
    # 3. 检查风险等级一致性
    if 'risk_assessment' in json_data:
        json_risk = json_data['risk_assessment'].get('overall_risk_level', '')
        logger.debug(f'JSON风险等级: {json_risk}')
    
    # 4. 检查数据完整性
    required_fields = ['income_structure', 'fund_flow', 'wealth_management']
    for field in required_fields:
        if field not in json_data:
            issues.append(f'JSON数据缺少必需字段: {field}')
    
    return issues


# ============================================================
# 大数据量处理优化 (2026-01-25 新增)
# ============================================================

def process_large_dataset_in_batches(
    data: List,
    process_func,
    batch_size: int = 10000,
    **kwargs
) -> List:
    """
    分批处理大数据集
    
    Args:
        data: 待处理的数据列表
        process_func: 处理函数（接受单个批次）
        batch_size: 每批大小
        **kwargs: 传递给处理函数的额外参数
    
    Returns:
        所有批次处理结果的合并列表
    """
    results = []
    
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        batch_result = process_func(batch, **kwargs)
        results.extend(batch_result)
        
        # 释放内存
        del batch
    
    return results


def analyze_transactions_streaming(
    transactions: pd.DataFrame,
    analyze_func,
    **kwargs
):
    """
    流式分析交易数据（生成器模式）
    
    Args:
        transactions: 交易DataFrame
        analyze_func: 分析函数（接受单笔交易）
        **kwargs: 传递给分析函数的额外参数
    
    Yields:
        每笔交易的分析结果
    """
    for idx, row in transactions.iterrows():
        yield analyze_func(row, **kwargs)


def process_large_dataframe_in_chunks(
    df: pd.DataFrame,
    process_func,
    chunk_size: int = 10000,
    **kwargs
) -> pd.DataFrame:
    """
    分块处理大型DataFrame
    
    Args:
        df: 待处理的DataFrame
        process_func: 处理函数（接受单个DataFrame块）
        chunk_size: 每块大小
        **kwargs: 传递给处理函数的额外参数
    
    Returns:
        合并后的DataFrame
    """
    results = []
    
    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i:i + chunk_size].copy()
        chunk_result = process_func(chunk, **kwargs)
        results.append(chunk_result)
        
        # 释放内存
        del chunk
    
    # 合并结果
    if results:
        return pd.concat(results, ignore_index=True)
    else:
        return pd.DataFrame()


def optimize_dataframe_memory(df: pd.DataFrame) -> pd.DataFrame:
    """
    优化DataFrame内存使用
    
    Args:
        df: 待优化的DataFrame
    
    Returns:
        优化后的DataFrame
    """
    # 转换数据类型以减少内存占用
    for col in df.columns:
        if df[col].dtype == 'object':
            # 尝试转换为category类型（适用于低基数字符串）
            unique_count = df[col].nunique()
            if unique_count / len(df) < 0.5:  # 基数小于50%
                df[col] = df[col].astype('category')
        elif df[col].dtype == 'float64':
            # 如果数值范围较小，转换为float32
            if df[col].min() >= -3.4e38 and df[col].max() <= 3.4e38:
                df[col] = df[col].astype('float32')
        elif df[col].dtype == 'int64':
            # 如果数值范围较小，转换为int32
            if df[col].min() >= -2.1e9 and df[col].max() <= 2.1e9:
                df[col] = df[col].astype('int32')
    
    return df


def validate_cross_report_consistency(
    validation_report: Dict,
    behavioral_report: Dict,
    financial_report: Dict
) -> List[str]:
    """
    验证多个报告之间的一致性
    
    Args:
        validation_report: 数据验证报告
        behavioral_report: 行为特征报告
        financial_report: 资金画像报告
    
    Returns:
        一致性问题列表
    """
    issues = []
    
    # 1. 检查实体列表一致性
    entities_in_validation = set(validation_report.keys()) if isinstance(validation_report, dict) else set()
    entities_in_behavioral = set(behavioral_report.get('summary', {}).keys()) if isinstance(behavioral_report, dict) else set()
    entities_in_financial = set(financial_report.keys()) if isinstance(financial_report, dict) else set()
    
    # 检查是否有实体在某些报告中缺失
    all_entities = entities_in_validation | entities_in_behavioral | entities_in_financial
    
    for entity in all_entities:
        missing_reports = []
        if entity not in entities_in_validation:
            missing_reports.append('数据验证')
        if entity not in entities_in_behavioral:
            missing_reports.append('行为特征')
        if entity not in entities_in_financial:
            missing_reports.append('资金画像')
        
        if missing_reports:
            issues.append(f'{entity} 缺少以下报告: {", ".join(missing_reports)}')
    
    # 2. 检查交易记录数一致性
    for entity in all_entities:
        counts = []
        
        if entity in validation_report and isinstance(validation_report[entity], dict):
            count = validation_report[entity].get('record_count', 0)
            counts.append(f'数据验证({count})')
        
        if entity in financial_report and isinstance(financial_report[entity], dict):
            summary = financial_report[entity].get('summary', {})
            count = summary.get('transaction_count', 0)
            counts.append(f'资金画像({count})')
        
        if len(counts) > 1:
            # 检查记录数是否一致（允许10%差异）
            counts_int = [int(re.search(r'\((\d+)\)', c).group(1)) if re.search(r'\((\d+)\)', c) else 0 for c in counts]
            if counts_int:
                max_count = max(counts_int)
                min_count = min(counts_int)
                if max_count > 0 and (max_count - min_count) / max_count > 0.1:
                    issues.append(f'{entity} 交易记录数不一致: {", ".join(counts)}')
    
    return issues
