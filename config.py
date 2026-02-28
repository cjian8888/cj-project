#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件 - 资金穿透与关联排查系统
定义关键参数、白名单规则和检测阈值

【修复说明】
- 问题1修复：硬编码阈值过多，难以维护
- 解决方案：从 config_loader.py 的 YAML 配置文件读取所有阈值
- 修改日期：2026-01-25
- 问题18修复：配置项缺少类型注解
- 解决方案：为所有配置项添加类型注解，提高代码可读性和IDE支持
- 修改日期：2026-01-25
"""

from typing import List, Dict, Any, Tuple, Optional, Union
import config_loader

# 导入统一路径管理器
from paths import DATA_DIR as _DATA_DIR
from paths import OUTPUT_DIR as _OUTPUT_DIR
from paths import CACHE_PATH as _CACHE_PATH
# ============================================================
# 从YAML配置文件加载阈值（问题1修复）
# ============================================================

# 加载配置
_risk_config: Dict[str, Any] = config_loader.load_risk_thresholds()

# 便捷函数：从配置获取值，带默认值
def _get_config(*keys: str, default: Any = None) -> Any:
    """从配置字典获取嵌套值"""
    value = config_loader.get_config_value(_risk_config, *keys)
    return value if value is not None else default

# ============================================================
# 工资识别配置
# ============================================================

# 强工资关键词（优先级最高）
SALARY_STRONG_KEYWORDS: List[str] = [
    '工资', '代发薪', '代发工资', '薪资', '绩效', '奖金', '代发奖金',
    '补贴', '津贴', '补助', '过节费', '防暑降温', '取暖费',
    '基本工资', '岗位工资', '年终奖', '季度奖', '安家费',
    '劳务', '劳务费', '专家费', '评审费', '讲课费', '稿费'
]

# 普通工资关键词（需结合金额和频率判断）
SALARY_KEYWORDS: List[str] = [
    '代发', '各类代发', '福利', 
    '公积金', '社保', '养老', '失业', '医疗'
]

# 需排除的报销/差旅/退款类关键词（即使来自发薪单位也应排除）
EXCLUDED_REIMBURSEMENT_KEYWORDS: List[str] = [
    '差旅', '出差', '住宿', '交通', '车贴', '垫付', 
    '报销', '退款', '退回'
]

# 已知发薪单位（优先级次高）
# 注意：这里只存放通用的发薪单位特征词
# 具体单位名称请在下方的 USER_DEFINED_SALARY_PAYERS 中配置
# 【重要】不要在此处添加特定案件的具体单位名称
KNOWN_SALARY_PAYERS: List[str] = [
    # 通用人力资源服务关键词
    '人力资源', '劳务派遣', '人才服务', '外服', 'FESCO',
    '劳务外包', '人事代理', '人力外包', '劳务公司', '人才中心',
    # 通用大型企业关键词
    '华为技术', '华为终端', '阿里巴巴', '腾讯', '百度',
    '中国航天', '中国航空', '中国船舶', '中国电子', '中国兵器',
    # 通用事业单位关键词
    '研究院', '研究所', '大学', '学院', '中心',
]

# 用户干预配置区
# 在此处填写已知发薪单位的全称或包含的关键词
# 系统将优先把来自这些单位的收入判定为工资
# 【重要】此列表应在具体案件分析时根据实际情况填写，代码库中保持为空
USER_DEFINED_SALARY_PAYERS: List[str] = [
   # 示例: '某某科技公司', '某某研究所'
   # 运行时请根据实际案件填写
]

# ============================================================
# 政府机关白名单（2026-01-08 新增）
# ============================================================

# 来自这些机构的规律性收入应优先识别为合规收入（工资、补贴等），而非异常
GOVERNMENT_AGENCY_KEYWORDS: List[str] = [
    # 财政局
    '财政局', '财政厅', '财政部',
    # 社保公积金
    '社保', '社会保险', '公积金管理中心', '住房公积金',
    # 人社局
    '人力资源和社会保障局', '人社局', '劳动局', '人事局',
    # 教育系统
    '教育局', '教委', '学校', '中学', '小学', '大学', '学院',
    # 医疗卫生
    '卫生局', '卫健委', '医院',
    # 其他政府机关
    '税务局', '民政局', '科技局', '发改委', '国资委',
    '工商局', '市场监督', '街道办', '居委会', '村委会',
    # 事业单位
    '研究院', '研究所', '中心', '档案馆', '图书馆', '博物馆'
]

# ============================================================
# 理财产品对手方排除列表（2026-01-08 新增）
# ============================================================

# 这些对手方名称表明是理财产品交易，不应被识别为借贷
WEALTH_PRODUCT_COUNTERPARTY_KEYWORDS: List[str] = [
    # 银行理财产品名称特征
    '理财产品', '理财', '增利', '稳健', '周周利', '月月盈',
    '天天利', '日日盈', '活期宝', '定活宝', '智能存',
    # 资产管理
    '资产管理', '资管', '非凡资产', '瑞赢', '睿赢',
    # 基金
    '基金', '基金管理', '货币基金', '债券基金',
    # 银行内部账户
    '代销内部', '理财保证金', '划转账户', '过渡户',
    '存管业务', '清算', '头寸', '备付',
    # 保险理财
    '保险', '年金', '投连', '万能险', '证券', '证劵', '证券公司', '证券股份有限公司'
]

# ============================================================
# 知名理财产品白名单（2026-01-11 新增）
# ============================================================

# 这些产品/账户的收支不应被标记为"来源不明"或"疑似借贷"
KNOWN_WEALTH_PRODUCTS: List[str] = [
    # 交通银行理财
    '交银添利', '交银理财', '蕴通财富', '沃德理财', '惠享存',
    # 工商银行理财
    '工银理财', '灵通快线', '稳得利', '节节高',
    # 建设银行理财
    '建信理财', '乾元', '利得盈',
    # 招商银行理财  
    '招银理财', '日日金', '朝朝宝', '金葵花',
    # 农业银行理财
    '农银理财', '本利丰', '安心得利',
    # 民生银行理财
    '民生天天增利', '翠竹', '非凡资产',
    # 浦发银行理财
    '浦银理财', '汇理财', '天添盈',
    # 中信银行理财
    '中信理财', '薪金煲', '乐赢',
    # 光大银行理财
    '阳光理财', '定存宝', '假日盈',
    # 通用定期存款产品
    '结构性存款', '大额存单', '智能存款', '定活两便',
    '定期一本通', '整存整取', '零存整取', '存本取息',
    # 货币基金
    '余额宝', '零钱通', '理财通', '活期宝', '天天宝', '如意宝',
    '添益宝', '现金宝', '日日聚', '薪金宝',
    # 银证转账
    '银证通', '银证转账', '证券转银行', '银行转证券'
]

# ============================================================
# 人力资源/劳务派遣公司关键词
# ============================================================

HR_COMPANY_KEYWORDS: List[str] = [
    '人才服务', '人力资源', '劳务派遣', '劳务外包', '人力外包',
    '人事代理', '人力服务', '劳务服务', '人事外包', '劳务公司',
    '人才中心', '就业服务', '职业介绍'
]

# ============================================================
# 借贷平台关键词（用于排除）
# ============================================================

LOAN_PLATFORM_KEYWORDS: List[str] = [
    '借', '贷', '信贷', '小额贷款', '消费金融', '金融服务',
    '信托', '白条', '金条', '放心借', '借呗', '花呗',
    '微粒贷', '好期贷', '任性贷', '有钱花', '安逸花',
    '省呗', '还呗', '分期', '现金贷', '网贷',
    '融资租赁', '保理', '典当'
]

# ============================================================
# 第三方支付平台关键词
# ============================================================

THIRD_PARTY_PAYMENT_KEYWORDS: List[str] = [
    '支付宝', '微信', '财付通', '微信支付', '支付宝转账',
    '余额宝', '理财通', 'clouds', 'alipay', 'wechat',
    '京东支付', '云闪付', '银联', '快捷支付'
]

# ============================================================
# 疑似购房关键词
# ============================================================

PROPERTY_KEYWORDS: List[str] = [
    '房款', '购房', '首付', '按揭', '房地产', '置业',
    '商品房', '住房', '楼盘', '售楼', '房产', '契税'
]

# ============================================================
# 疑似购车关键词
# ============================================================

VEHICLE_KEYWORDS: List[str] = [
    '车款', '购车', '4s店', '汽车销售', '汽车', '车辆',
    '奔驰', '宝马', '奥迪', '特斯拉', '保时捷', '路虎'
]

# ============================================================
# 现金交易关键词
# ============================================================

CASH_KEYWORDS: List[str] = [
    '取现', '存现', '现金存入', '现金支取', '支取现金', '存入现金',
    'ATM', '柜台存款', '柜台取款', '柜面取款', '柜面存款', '现钞'
]

# ============================================================
# 理财产品关键词（购买和赎回）
# ============================================================

WEALTH_MANAGEMENT_KEYWORDS: List[str] = [
    # 通用理财
    '理财', '理财产品', '理财购买', '理财赎回', '理财到期',
    '定期存款', '定存', '结构性存款', '大额存单',
    # 【新增】定期存款操作关键词（非常重要）
    '活转定', '定转活', '约定定期', '约定活转', '定期到期',
    '本息转活', '本息转入', '定期开户', '定期续存', '自动转存',
    '通知存款', '智能存', '安心存', '智存通',
    # 【新增】活期宝类产品
    '活期宝', '余额宝', '天天宝', '如意宝', '添益宝', '易贷宝',
    '活期通', '薪金宝', '现金宝', '日日聚',
    # 基金类
    '基金', '货币基金', '债券基金', '股票基金', '混合基金',
    '基金申购', '基金赎回', '基金认购', '基金定投',
    # 银行理财
    '银行理财', '保本理财', '非保本理财', '净值型理财',
    '周周利', '月月盈', '稳健理财', '增值理财', '增利',
    '天天增利', '增信', '睿赢', '瑞赢', '非凡资产',
    # 保险理财
    '分红保险', '万能险', '投连险', '年金险',
    # 贵金属/外汇
    '黄金', '白银', '贵金属', '外汇', '纸黄金',
    # 信托/资管
    '信托', '资管计划', '集合理财', '资产管理',
    # 股票/证券
    '证券', '股票', '银证转账', '银证', '证券转银行', '银行转证券',
    # 【新增】预约/申购
    '预约申购', '预约赎回', '自动申购', '自动赎回',
    # 其他
    '收益', '到期兑付', '结息', '产品赎回', '清算'
]

# 银行内部代码映射（Wave1 识别使用）
# 将纯数字摘要映射为银行内部代码，便于将其分类到 wealth_management
BANK_INTERNAL_CODES: Dict[str, str] = {
    '69': '银行内部转账-大额存单',
    '71': '银行内部转账-结构性存款',
    '72': '银行内部转账-理财产品',
    '81': '银行内部转账-定期到期'
}

# ============================================================
# 理财产品购买关键词（支出方向）
# ============================================================

WEALTH_PURCHASE_KEYWORDS: List[str] = [
    '购买', '申购', '认购', '定投', '转入', '投资',
    '银行转证券', '银证转出', '理财购买', '基金申购'
]

# ============================================================
# 理财产品赎回关键词（收入方向）
# ============================================================

WEALTH_REDEMPTION_KEYWORDS: List[str] = [
    '赎回', '到期', '兑付', '卖出', '转出', '支取',
    '证券转银行', '银证转入', '理财到期', '基金赎回',
    '收益', '分红', '利息'
]

# ============================================================
# 检测阈值参数（从YAML配置读取）
# ============================================================

# 大额现金阈值（元）- 可根据核查对象收入水平调整
LARGE_CASH_THRESHOLD: int = _get_config('large_cash', 'threshold', default=50000)

# 动态阈值配置（根据个人年收入调整大额现金阈值）
DYNAMIC_THRESHOLD_CONFIG: Dict[str, Any] = {
    'enabled': True,
    'income_levels': _get_config('income_classification', 'income_levels', default={
        500000: 100000,
        1000000: 200000,
        5000000: 500000,
    })
}

# 数据质量阈值
MAX_AMOUNT_THRESHOLD: int = _get_config('validation', 'max_single_amount', default=100000000)

# 分级阈值
CASH_THRESHOLDS: Dict[str, int] = _get_config('large_cash', 'levels', default={
    'level_1': 10000,
    'level_2': 50000,
    'level_3': 100000,
    'level_4': 500000,
})

# 现金时空伴随检测参数
CASH_TIME_WINDOW_HOURS: int = _get_config('cash_time_window', 'hours', default=48)
AMOUNT_TOLERANCE_RATIO: float = _get_config('cash_time_window', 'amount_tolerance_ratio', default=0.05)

# 固定频率检测参数
FIXED_FREQUENCY_MIN_OCCURRENCES: int = _get_config('fixed_frequency', 'min_occurrences', default=3)
FIXED_FREQUENCY_DATE_TOLERANCE: int = _get_config('fixed_frequency', 'date_tolerance', default=3)
FIXED_FREQUENCY_AMOUNT_TOLERANCE: float = _get_config('fixed_frequency', 'amount_tolerance', default=0.1)

# ============================================================
# 节假日与特殊时段配置（从YAML配置读取）
# ============================================================

# 中国法定节假日（按年配置，支持多年）
CHINESE_HOLIDAYS: Dict[int, List[Tuple[str, str, str]]] = {
    2024: [
        ('2024-01-01', '2024-01-01', '元旦'),
        ('2024-02-10', '2024-02-17', '春节'),
        ('2024-04-04', '2024-04-06', '清明节'),
        ('2024-05-01', '2024-05-05', '劳动节'),
        ('2024-06-08', '2024-06-10', '端午节'),
        ('2024-09-15', '2024-09-17', '中秋节'),
        ('2024-10-01', '2024-10-07', '国庆节'),
    ],
    2025: [
        ('2025-01-01', '2025-01-01', '元旦'),
        ('2025-01-28', '2025-02-04', '春节'),
        ('2025-04-04', '2025-04-06', '清明节'),
        ('2025-05-01', '2025-05-05', '劳动节'),
        ('2025-05-31', '2025-06-02', '端午节'),
        ('2025-10-01', '2025-10-08', '国庆节+中秋'),
    ],
    2026: [
        ('2026-01-01', '2026-01-03', '元旦'),
        ('2026-02-17', '2026-02-23', '春节'),
        ('2026-04-04', '2026-04-06', '清明节'),
        ('2026-05-01', '2026-05-05', '劳动节'),
        ('2026-06-19', '2026-06-21', '端午节'),
        ('2026-10-01', '2026-10-07', '国庆节'),
        ('2026-10-25', '2026-10-25', '中秋节'),
    ]
}

# 非工作时间定义（用于检测异常转账时间）
NON_WORKING_HOURS_START: int = 20
NON_WORKING_HOURS_END: int = 8

# 周末检测开关
WEEKEND_DETECTION_ENABLED: bool = True

# 第三方中转时间窗口（小时）
THIRD_PARTY_RELAY_HOURS: int = 72

# 金额拆分规避检测配置
SPLIT_AMOUNT_THRESHOLD: int = _get_config('structuring', 'min_large_amount', default=50000)
SPLIT_DETECTION_COUNT: int = _get_config('structuring', 'min_split_count', default=3)
SPLIT_AMOUNT_TOLERANCE: float = _get_config('structuring', 'amount_tolerance', default=0.02)

# 整数金额偏好检测阈值
ROUND_AMOUNT_THRESHOLD: int = _get_config('structuring', 'min_large_amount', default=10000)
ROUND_AMOUNT_MIN_COUNT: int = 5

# 吉利数尾号检测
LUCKY_TAIL_NUMBERS: List[str] = ['88', '66', '88888', '66666', '168', '888', '666']

# 节假日大额交易阈值（元）
HOLIDAY_LARGE_AMOUNT_THRESHOLD: int = _get_config('structuring', 'min_large_amount', default=50000)

# 节假日检测时间窗口（新增）
HOLIDAY_DETECTION_CONFIG: Dict[str, Any] = {
    'days_before': 3,
    'days_after': 2,
    'auto_detect_range': True,
}

# 房产购置匹配参数（新增）
PROPERTY_MATCH_CONFIG: Dict[str, Any] = {
    'time_window_months': _get_config('validation', 'property_match', 'time_window_months', default=12),
    'cumulative_match': _get_config('validation', 'property_match', 'cumulative_match', default=True),
    'cumulative_tolerance': _get_config('validation', 'property_match', 'cumulative_tolerance', default=0.2),
    'single_match_tolerance': _get_config('validation', 'property_match', 'single_match_tolerance', default=0.1),
}

# ============================================================
# 银行字段映射配置(支持真实银行数据)
# ============================================================

# 真实银行流水字段映射
BANK_FIELD_MAPPING: Dict[str, List[str]] = {
    'transaction_time': ['交易时间', '发生时间', '记账时间', '交易日期'],
    'transaction_amount': ['交易金额', '发生额', '金额'],
    'debit_credit_flag': ['借贷标志', '借贷', '收支标志'],
    'balance': ['交易余额', '余额', '账户余额', '当前余额'],
    'counterparty_name': ['交易对方名称', '对方账户名称', '对手方', '交易对方'],
    'counterparty_account': ['交易对方账号', '对方账号', '对方账户'],
    'summary': ['交易摘要', '摘要', '用途', '附言'],
    'cash_flag': ['现金标志', '现金'],
    'account_number': ['本方账号', '账号', '卡号', '本方卡号'],
    'transaction_id': ['交易流水号', '流水号', '交易序号', '业务流水号', '日志号']
}

# ============================================================
# Excel 列名统一映射配置 (铁律)
# ============================================================

# 【单一修改点】今后修改 Excel 列名只需改这一处，其他模块自动引用

# 内部字段名 → Excel 显示名
COLUMN_MAPPING: Dict[str, str] = {
    'date': '交易时间',
    'income': '收入(元)',
    'expense': '支出(元)',
    'balance': '余额(元)',
    'counterparty': '交易对手',
    'description': '交易摘要',
    'category': '交易分类',
    'bank_source': '所属银行',
    '银行来源': '所属银行',  # 兼容原始列名
    'account_number': '本方账号',
    'is_cash': '现金',
    '数据来源': '来源文件',
    'transaction_id': '流水号',
    # Phase 0.1 刑侦级指标字段 (2026-01-18 新增)
    'is_balance_zeroed': '余额清空',
    'transaction_channel': '交易渠道',
    'sensitive_keywords': '敏感词',
}

# Excel 列显示顺序
COLUMN_ORDER: List[str] = [
    'date', 'income', 'expense', 'balance',
    'counterparty', 'description', 'category',
    '银行来源', 'account_number', 'is_cash',
    'is_balance_zeroed', 'transaction_channel', 'sensitive_keywords',  # Phase 0.1 新增
    '数据来源'
]

# 读取 Excel 时的列名变体（用于兼容不同格式）
# 按优先级排序，第一个是标准名称
INCOME_COLUMN_VARIANTS: List[str] = ['收入(元)', 'income', '收入', '贷方金额', '存入金额']
EXPENSE_COLUMN_VARIANTS: List[str] = ['支出(元)', 'expense', '支出', '借方金额', '转出金额']
BALANCE_COLUMN_VARIANTS: List[str] = ['余额(元)', 'balance', '余额', '账户余额', '当前余额']
DATE_COLUMN_VARIANTS: List[str] = ['交易时间', 'date', '交易日期', '发生时间', '记账时间']
COUNTERPARTY_COLUMN_VARIANTS: List[str] = ['交易对手', 'counterparty', '对方名称', '交易对方名称']
DESCRIPTION_COLUMN_VARIANTS: List[str] = ['交易摘要', 'description', '摘要', '用途', '附言']
IS_CASH_COLUMN_VARIANTS: List[str] = ['现金', 'is_cash']
CATEGORY_COLUMN_VARIANTS: List[str] = ['交易分类', 'category']

# ============================================================
# 去重配置
# ============================================================

# 去重时间容差(秒)
DEDUP_TIME_TOLERANCE_SECONDS: int = 1

# 去重关键字段
DEDUP_KEYS: List[str] = ['交易时间', '交易金额', '本方账号', '交易对方账号']

# ============================================================
# 交易分类配置 (自动打标)
# ============================================================

TRANSACTION_CATEGORIES: Dict[str, Dict[str, Any]] = {
    '工资收入': {
        'keywords': ['工资', '代发薪', '奖金', '薪资', '补贴', '绩效', '年终奖', '劳务费', '稿费', 
                     '人才服务', '人力资源', '百旺金赋', '外包', '劳务派遣', '空间电源'], # 扩充发薪单位特征
        'priority': 10
    },
    '现金交易': {
        # 这里的关键词应与 CASH_KEYWORDS 保持逻辑一致或更广
        'keywords': ['ATM', '柜台存款', '柜台取款', '现钞', '取现', '存现', '现金支取', '现金存入'],
        'priority': 20
    },
    '投资理财': {
        'keywords': ['理财', '基金', '证券', '股票', '保险', '分红', '股息', '银证', '信托', '资管', '赎回', '申购'],
        'priority': 30
    },
    '网贷/信贷': {
        'keywords': ['贷款', '放款', '还款', '利息', '滞纳金', '借呗', '花呗', '微粒贷', '白条', '金条', '小贷', '消金', '分期', 
                     '汽车金融', '百信银行', '中银消金'], # 扩充车贷与网贷
        'priority': 40
    },
    '生活消费': {
        'keywords': ['美团', '饿了么', '京东', '淘宝', '天猫', '拼多多', '抖音电商', '超市', '餐饮', '百货', '医院', '药房', '滴滴', '打车', '加油', '水电', '燃气', '话费', '消费', 'POS',
                     '三快', '拉扎斯', '网银在线', '汉海信息', '便利', '服务费'], # 扩充美团饿了么京东主体公司
        'priority': 50
    },
    '转账': {
        'keywords': ['转账', '汇款', '往来', '划转'], # 包含本人互转
        'priority': 60
    },
    '第三方支付': {
        # 兜底的网络支付，如果没命中具体的消费
        'keywords': ['支付宝', '微信', '财付通', '京东支付', '快捷支付', '银联', '扫码'],
        'priority': 70
    },
    '银行费用': {
        'keywords': ['手续费', '年费', '短信费', '工本费'],
        'priority': 80
    }
}

# 疑似购房购车金额阈值（元）
PROPERTY_THRESHOLD: int = _get_config('asset', 'large_amount_threshold', default=100000)
VEHICLE_THRESHOLD: int = _get_config('asset', 'default_vehicle_value', default=50000)

# ============================================================
# Excel字段映射配置
# ============================================================

# 支持的日期字段名（优先级从高到低）
DATE_COLUMNS: List[str] = [
    '交易日期', '日期', '交易时间', '记账日期', '时间',
    'date', 'transaction_date', '发生日期'
]

# 支持的摘要/备注字段名
DESCRIPTION_COLUMNS: List[str] = [
    '摘要', '备注', '交易摘要', '说明', '用途', '附言',
    'description', 'memo', 'remark', '交易说明'
]

# 支持的收入字段名
INCOME_COLUMNS: List[str] = [
    '收入', '收入金额', '贷方', '贷方金额', '转入',
    'income', 'credit', 'deposit', '入账金额'
]

# 支持的支出字段名
EXPENSE_COLUMNS: List[str] = [
    '支出', '支出金额', '借方', '借方金额', '转出',
    'expense', 'debit', 'withdrawal', '支取金额'
]

# 支持的对手方字段名
COUNTERPARTY_COLUMNS: List[str] = [
    '对手方', '交易对象', '对方户名', '对方账号', '收款方',
    '付款方', 'counterparty', 'opponent', '对手名称'
]

# 支持的余额字段名
BALANCE_COLUMNS: List[str] = [
    '余额', '账户余额', '当前余额', 'balance', '结余'
]

# ============================================================
# 文件路径配置
# ============================================================

# 输出目录（使用 paths 模块统一管理）
DATA_DIR: str = str(_DATA_DIR)
OUTPUT_DIR: str = str(_OUTPUT_DIR)
# 输出文件名
OUTPUT_EXCEL_FILE: str = '资金核查底稿.xlsx'
OUTPUT_REPORT_FILE: str = '核查结果分析报告.docx'
OUTPUT_LOG_FILE: str = 'audit_system.log'

# PDF线索文件关键词（用于自动识别）
CLUE_FILE_KEYWORDS: List[str] = ['线索', '举报', '信访', 'clue', 'tip']

# ============================================================
# 日志配置
# ============================================================

LOG_FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL: str = 'INFO'

# 日志轮转配置
LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB - 单个日志文件最大大小
LOG_BACKUP_COUNT: int = 5               # 保留的备份文件数量 (audit_system.log.1 ~ .5)

# ============================================================
# 报告模板配置
# ============================================================

# 公文报告标题
REPORT_TITLE: str = '核查结果分析报告'

# 报告章节
REPORT_SECTIONS: List[str] = [
    '一、基本情况',
    '二、个人资产分析',
    '三、公司资金流向',
    '四、发现的疑点',
    '五、下一步工作建议'
]

# 疑点风险等级
RISK_LEVELS: Dict[str, str] = {
    'high': '高风险',
    'medium': '中风险',
    'low': '低风险',
    'info': '信息提示'
}

# ============================================================
# 数据质量检查
# ============================================================

# 必需字段
REQUIRED_FIELDS: List[str] = ['date', 'description']

# 允许的日期格式
DATE_FORMATS: List[str] = [
    '%Y-%m-%d',
    '%Y/%m/%d',
    '%Y.%m.%d',
    '%Y年%m月%d日',
    '%Y-%m-%d %H:%M:%S',
    '%Y/%m/%d %H:%M:%S',
    '%Y%m%d'
]

# ============================================================
# 中式阈值配置（从YAML配置读取）
# ============================================================

# --- 资产分析阈值 ---
ASSET_LARGE_AMOUNT_THRESHOLD: int = _get_config('asset', 'large_amount_threshold', default=50000)
DEFAULT_VEHICLE_VALUE: int = _get_config('asset', 'default_vehicle_value', default=200000)

# --- 数据验证阈值 ---
VALIDATION_MAX_SINGLE_AMOUNT: int = _get_config('validation', 'max_single_amount', default=100000000)
VALIDATION_PROPERTY_EXPENSE_MIN: int = _get_config('validation', 'property_expense_min', default=10000)

# --- 收入分析阈值 ---
INCOME_MIN_AMOUNT: int = _get_config('income_analysis', 'income_min_amount', default=1000)
INCOME_REGULAR_MIN: int = _get_config('income_analysis', 'regular_non_salary_min', default=3000)
INCOME_MEAN_AMOUNT_MIN: int = _get_config('income_analysis', 'mean_amount_min', default=2000)
INCOME_MEAN_AMOUNT_MAX: int = _get_config('income_analysis', 'mean_amount_max', default=80000)
INCOME_UNKNOWN_SOURCE_MIN: int = _get_config('income_analysis', 'unknown_source_min', default=10000)
INCOME_LARGE_PERSONAL_MIN: int = _get_config('income_analysis', 'large_personal_min', default=20000)
INCOME_HIGH_RISK_MIN: int = _get_config('income_analysis', 'high_risk_min', default=50000)
INCOME_VERY_LARGE_MIN: int = _get_config('income_analysis', 'very_large_min', default=100000)

# --- 可视化显示阈值 ---
DISPLAY_AMOUNT_THRESHOLD: int = _get_config('visualization', 'display_amount_threshold', default=10000)

# --- 借贷分析阈值 ---
LOAN_MIN_AMOUNT: int = _get_config('loan', 'min_match_amount', default=5000)
LOAN_HIGH_RISK_MIN: int = _get_config('loan', 'high_risk_min', default=10000)
LOAN_BIDIRECTIONAL_HIGH_RISK: int = _get_config('loan', 'bidirectional_high_risk', default=50000)
LOAN_INTEREST_FREE_MIN: int = _get_config('loan', 'interest_free_min', default=50000)
LOAN_LARGE_NO_REPAY_MIN: int = _get_config('loan', 'large_no_repay_min', default=100000)
LOAN_TIME_WINDOW_DAYS: int = _get_config('loan', 'time_window_days', default=365)
LOAN_AMOUNT_TOLERANCE: float = _get_config('loan', 'amount_tolerance', default=0.2)
LOAN_PAIR_RATIO_MIN: float = _get_config('loan', 'pair_ratio_min', default=1.0)
LOAN_PAIR_RATIO_MAX: float = _get_config('loan', 'pair_ratio_max', default=1.5)
LOAN_USURY_RATE: float = _get_config('loan', 'usury_rate', default=36.0)
LOAN_HIGH_RATE: float = _get_config('loan', 'high_rate', default=24.0)
LOAN_LOW_RATE: float = _get_config('loan', 'low_rate', default=4.0)

# --- 规律性收入检测参数 ---
REGULAR_INCOME_INTERVAL_MIN: int = _get_config('income_analysis', 'regular_interval_min', default=20)
REGULAR_INCOME_INTERVAL_MAX: int = _get_config('income_analysis', 'regular_interval_max', default=40)
REGULAR_INCOME_CV_THRESHOLD: float = _get_config('income_analysis', 'cv_threshold', default=0.5)
REGULAR_REPAYMENT_CV_THRESHOLD: float = _get_config('income_analysis', 'repayment_cv_threshold', default=0.3)

# --- 理财识别参数 ---
WEALTH_IDENTIFICATION_MIN_AMOUNT: int = _get_config('income_analysis', 'wealth_identification_min_amount', default=100000)
WEALTH_ROUND_AMOUNT_UNIT: int = _get_config('income_analysis', 'wealth_round_amount_unit', default=10000)
WEALTH_PERIODIC_MIN_OCCURRENCES: int = _get_config('income_analysis', 'wealth_periodic_min_occurrences', default=4)
WEALTH_PERIODIC_INTERVAL_TOLERANCE: int = _get_config('income_analysis', 'wealth_periodic_interval_tolerance', default=15)
WEALTH_PERIODIC_MIN_INTERVAL: int = _get_config('income_analysis', 'wealth_periodic_min_interval', default=60)
WEALTH_INCREASING_RATIO: float = _get_config('income_analysis', 'wealth_increasing_ratio', default=0.6)

# --- 疑点检测阈值 ---
SUSPICION_PROPERTY_HIGH_RISK: int = _get_config('suspicion', 'medium_high_amount', default=1000000)
SUSPICION_VEHICLE_HIGH_RISK: int = _get_config('suspicion', 'medium_high_amount', default=500000)
SUSPICION_LUCKY_NUMBER_MIN: int = _get_config('suspicion', 'medium_high_amount', default=1000)

# --- 资金穿透阈值 ---
PENETRATION_MIN_AMOUNT: int = _get_config('fund_penetration', 'min_amount', default=10000)

# --- 报告生成阈值 ---
REPORT_CAR_PAYMENT_MIN: int = _get_config('report', 'car_payment_min', default=10000)
REPORT_HOUSE_PAYMENT_MIN: int = _get_config('report', 'house_payment_min', default=50000)

# Unit Conversion
UNIT_WAN: int = 10000  # 1万

# --- 理财分析阈值 ---
WEALTH_SIGNIFICANT_PROFIT: int = _get_config('income_analysis', 'wealth_significant_profit', default=100000)
WEALTH_SIGNIFICANT_REDEMPTION: int = _get_config('income_analysis', 'wealth_significant_redemption', default=100000)

# --- 分期受贿检测参数 (2026-01-11 新增) ---
BRIBE_INSTALLMENT_MIN_OCCURRENCES: int = _get_config('bribe_installment', 'min_occurrences', default=4)
BRIBE_INSTALLMENT_MIN_AMOUNT: int = _get_config('bribe_installment', 'min_amount', default=10000)
BRIBE_INSTALLMENT_MAX_CV: float = _get_config('bribe_installment', 'max_cv', default=0.5)
BRIBE_INSTALLMENT_MIN_MONTHS: int = _get_config('bribe_installment', 'min_months', default=4)

# --- 工资识别增强参数 (2026-01-11 新增) ---
HIGH_FREQUENCY_SALARY_CAP: int = _get_config('income_analysis', 'high_frequency_salary_cap', default=100000)

# --- 风险评分权重 (2026-01-11 新增) ---
RISK_SCORE_FUND_CYCLE: int = _get_config('risk_score', 'fund_cycle', default=15)
RISK_SCORE_FUND_CYCLE_MAX: int = _get_config('risk_score', 'fund_cycle_max', default=30)
RISK_SCORE_PASS_THROUGH: int = _get_config('risk_score', 'pass_through', default=25)
RISK_SCORE_HUB_NODE: int = _get_config('risk_score', 'hub_node', default=10)
RISK_SCORE_HIGH_RISK_TX: int = _get_config('risk_score', 'high_risk_tx', default=5)
RISK_SCORE_HIGH_RISK_TX_MAX: int = _get_config('risk_score', 'high_risk_tx_max', default=20)
RISK_SCORE_AMOUNT_BONUS_PER_100K: int = _get_config('risk_score', 'amount_bonus_per_100k', default=5)
RISK_SCORE_AMOUNT_BONUS_MAX: int = _get_config('risk_score', 'amount_bonus_max', default=20)
RISK_SCORE_COMMUNITY: int = _get_config('risk_score', 'community', default=10)
RISK_SCORE_COMMUNITY_MAX: int = _get_config('risk_score', 'community_max', default=20)
RISK_SCORE_PERIODIC_INCOME: int = _get_config('risk_score', 'periodic_income', default=5)
RISK_SCORE_PERIODIC_INCOME_MAX: int = _get_config('risk_score', 'periodic_income_max', default=10)
RISK_SCORE_SUDDEN_CHANGE: int = _get_config('risk_score', 'sudden_change', default=3)
RISK_SCORE_SUDDEN_CHANGE_MAX: int = _get_config('risk_score', 'sudden_change_max', default=12)
RISK_SCORE_DELAYED_TRANSFER: int = _get_config('risk_score', 'delayed_transfer', default=10)
RISK_SCORE_DELAYED_TRANSFER_MAX: int = _get_config('risk_score', 'delayed_transfer_max', default=20)
RISK_SCORE_LOAN: int = _get_config('risk_score', 'loan', default=8)
RISK_SCORE_LOAN_MAX: int = _get_config('risk_score', 'loan_max', default=16)

# ============================================================
# 缓存配置 (2026-01-17 新增)
# ============================================================

CACHE_VERSION: str = "3.2.0"  # 升级版本号
CACHE_VERSION_MAJOR: int = 3  # 缓存主版本号（用于兼容性检查）
CACHE_PATH: str = str(_CACHE_PATH)  # 缓存文件路径（使用 paths 模块统一管理）
GRAPH_MAX_NODES: int = _get_config('cache', 'max_nodes', default=100)
GRAPH_MAX_EDGES: int = _get_config('cache', 'max_edges', default=500)

# ============================================================
# 刑侦级指标配置 (Phase 0.1 - 2026-01-18 新增)
# ============================================================

# 敏感词列表 - 交易摘要中包含这些词需要标记
SENSITIVE_KEYWORDS: List[str] = [
    # 借贷类
    '还款', '借款', '借贷', '借条', '欠款',
    # 好处费类
    '回扣', '佣金', '好处费', '感谢费', '辛苦费', '介绍费', '中介费',
    # 咨询服务类（可疑）
    '咨询费', '服务费', '顾问费', '劳务费',
    # 礼金类
    '红包', '礼金', '礼品', '过节费', '慰问',
    # 资金走账类
    '过桥', '走账', '垫资', '周转',
    # 退款类
    '退款', '退回', '返还', '退还'
]

# 交易渠道分类关键词
TRANSACTION_CHANNEL_KEYWORDS: Dict[str, List[str]] = {
    'ATM': ['ATM', '自助', '自动柜员', '自助终端', '自助设备'],
    '柜面': ['柜面', '柜台', '网点', '现钞', '柜员', '临柜'],
    '手机银行': ['手机银行', '掌银', 'APP', '移动银行', '手机支付'],
    '网银': ['网银', '网上银行', 'EBANK', '网上支付', '网银转账'],
    '第三方支付': ['支付宝', '微信', '财付通', '云闪付', '京东支付', '银联在线'],
    'POS消费': ['POS', '刷卡', '消费', '银联', '商户']
}

# 余额归零判断阈值（元）
BALANCE_ZERO_THRESHOLD: float = _get_config('data_quality', 'balance_zero_threshold', default=10.0)

# ============================================================
# 行为特征检测配置 (Phase 0.2 - 2026-01-18 新增)
# ============================================================

# 快进快出检测参数
FAST_IN_OUT_TIME_WINDOW_HOURS: int = _get_config('behavioral', 'fast_in_out_time_window_hours', default=24)
FAST_IN_OUT_MIN_AMOUNT: int = _get_config('behavioral', 'fast_in_out_min_amount', default=10000)
FAST_IN_OUT_AMOUNT_RATIO: float = _get_config('behavioral', 'fast_in_out_amount_ratio', default=0.8)

# 整进散出检测参数
STRUCTURING_MIN_SPLIT_COUNT: int = _get_config('behavioral', 'structuring_min_split_count', default=3)
STRUCTURING_AMOUNT_TOLERANCE: float = _get_config('behavioral', 'structuring_amount_tolerance', default=0.2)
STRUCTURING_TIME_WINDOW_DAYS: int = _get_config('behavioral', 'structuring_time_window_days', default=7)
STRUCTURING_MIN_LARGE_AMOUNT: int = _get_config('behavioral', 'structuring_min_large_amount', default=50000)

# 休眠激活检测参数
DORMANT_MIN_DAYS: int = _get_config('behavioral', 'dormant_min_days', default=180)
DORMANT_ACTIVATION_MIN_AMOUNT: int = _get_config('behavioral', 'dormant_activation_min_amount', default=50000)

# ============================================================
# P1 硬编码阈值迁移 (2026-01-18 新增)
# ============================================================

# 以下阈值从各分析模块中迁移过来，便于统一管理和调整

# --- 借贷分析阈值 (loan_analyzer.py) ---
LOAN_MIN_MATCH_AMOUNT: int = _get_config('loan', 'min_match_amount', default=5000)

# --- 时序分析阈值 (time_series_analyzer.py) ---
TIME_SERIES_HIGH_RISK_AMOUNT: int = _get_config('time_series', 'high_risk_amount', default=50000)
SUDDEN_CHANGE_MIN_AMOUNT: int = _get_config('time_series', 'sudden_change_min_amount', default=100000)

# --- 资金穿透阈值 (fund_penetration.py) ---
FUND_FLOW_MIN_AMOUNT: int = _get_config('fund_penetration', 'min_amount', default=100000)
GRAPH_EDGE_MIN_AMOUNT: int = _get_config('fund_penetration', 'edge_min_amount', default=10000)

# --- 疑点检测阈值 (suspicion_detector.py) ---
SUSPICION_MEDIUM_HIGH_AMOUNT: int = _get_config('suspicion', 'medium_high_amount', default=50000)

# --- 高频收入阈值 (financial_profiler.py) ---
# 注意：HIGH_FREQUENCY_SALARY_CAP 已在前面定义，此处复用

# ============================================================
# 调查单位配置 (Phase 4 - 2026-01-20 新增)
# ============================================================

# 用于识别与调查单位的资金往来
# 【重要】此列表应在具体案件分析时根据实际情况填写
# 【使用说明】:
#   1. 在分析具体案件时,将调查单位的名称或关键词添加到此列表
#   2. 支持部分匹配,例如添加"某某公司"可以匹配"某某公司有限公司"
#   3. 系统会自动识别与这些单位的资金往来,并在报告中单独统计
INVESTIGATION_UNIT_KEYWORDS: List[str] = [
    # 示例: '某某公司', '某某单位', '某某部门'
    # 运行时请根据实际案件填写
]

# ============================================================
# 虚户过滤配置 (Phase 4 - 2026-01-20 新增)
# ============================================================

# 用于过滤非真实银行卡账户
# 这些关键词用于识别理财账户、基金账户等非银行卡账户
# 在Phase 1的账户类型识别中作为补充判断依据
BANK_ACCOUNT_EXCLUDE_KEYWORDS: List[str] = [
    # 理财相关
    '理财', '理财产品', '理财账户', '财富账户', '财富管理',
    # 基金相关
    '基金', '基金账户', '货币基金', '债券基金', '股票基金',
    # 证券相关
    '证券', '证券账户', '股票账户', '资金账户', '保证金账户',
    # 其他虚拟账户
    '保证金', '清算', '过渡户', '内部户', '中间户',
    '代销', '托管', '存管', '备付金'
]

# ============================================================
# 关联交易排查配置 (P1增强 - 2026-01-20 新增)
# ============================================================

# 敏感人员关键词 - 用于识别需要重点关注的交易对手
# 【重要】此列表应在具体案件分析时根据实际情况填写
# 【使用说明】:
#   1. 在分析具体案件时,将需要重点关注的人员姓名添加到此列表
#   2. 系统会自动识别与这些人员的资金往来,并标记为敏感交易
SENSITIVE_PERSON_KEYWORDS: List[str] = [
    # 示例: '张三', '李四', '某某'
    # 运行时请根据实际案件填写
]

# 敏感公司关键词 - 用于识别涉案公司或关联公司
SENSITIVE_COMPANY_KEYWORDS: List[str] = [
    # 示例: '某某公司', '某某企业'
    # 运行时请根据实际案件填写
]

# 关联交易排查阈值
RELATED_PARTY_CONFIG: Dict[str, Any] = {
    # 高频交易阈值（同一对手方）
    'high_frequency_count': 10,
    'high_frequency_period_days': 365,
    
    # 大额交易阈值
    'large_amount_single': 50000,
    'large_amount_total': 200000,
    
    # 异常时段交易
    'off_hours_start': 22,
    'off_hours_end': 6,
    
    # 敏感人员交易自动标记为高风险
    'sensitive_auto_high_risk': True,
}

# ============================================================
# 资金沉淀分析配置 (Phase 0.3 - 2026-01-18 新增)
# ============================================================

FUND_RETENTION_PASS_THRESHOLD: float = _get_config('fund_retention', 'pass_through_threshold', default=0.1)
FUND_RETENTION_LOW_THRESHOLD: float = _get_config('fund_retention', 'low_retention_threshold', default=0.3)
FUND_RETENTION_HIGH_THRESHOLD: float = _get_config('fund_retention', 'high_retention_threshold', default=0.9)

# ============================================================
# 数据质量评分配置 (Phase 0.3 - 2026-01-18 新增)
# ============================================================

DATA_QUALITY_ISSUE_PENALTY: int = _get_config('data_quality', 'issue_penalty', default=20)
DATA_QUALITY_WARNING_PENALTY: int = _get_config('data_quality', 'warning_penalty', default=5)
DATA_QUALITY_HIGH_NULL_PENALTY: int = _get_config('data_quality', 'high_null_penalty', default=10)
DATA_QUALITY_EXCELLENT_SCORE: int = _get_config('data_quality', 'quality_levels', 'excellent', default=90)
DATA_QUALITY_GOOD_SCORE: int = _get_config('data_quality', 'quality_levels', 'good', default=70)
DATA_QUALITY_MEDIUM_SCORE: int = _get_config('data_quality', 'quality_levels', 'medium', default=50)
DATA_QUALITY_POOR_SCORE: int = _get_config('data_quality', 'quality_levels', 'poor', default=0)

# ============================================================
# 报告生成配置 (从YAML读取)
# ============================================================

REPORT_USE_GLOBAL_TIMESTAMP: bool = _get_config('report', 'use_global_timestamp', default=True)
REPORT_TIMESTAMP_FORMAT: str = _get_config('report', 'timestamp_format', default='%Y年%m月%d日 %H:%M:%S')
REPORT_ISO_TIMESTAMP_FORMAT: str = _get_config('report', 'iso_timestamp_format', default='%Y-%m-%dT%H:%M:%S')

# ============================================================
# 性能优化配置 (从YAML读取)
# ============================================================

PERFORMANCE_BATCH_SIZE: int = _get_config('performance', 'batch_size', default=10000)
PERFORMANCE_CHUNK_SIZE: int = _get_config('performance', 'chunk_size', default=10000)
PERFORMANCE_ENABLE_MEMORY_OPTIMIZATION: bool = _get_config('performance', 'enable_memory_optimization', default=True)
PERFORMANCE_ENABLE_BATCH_PROCESSING: bool = _get_config('performance', 'enable_batch_processing', default=True)

# ============================================================
# 理财识别参数 (从YAML读取)
# ============================================================

WEALTH_PERIODIC_MIN_OCCURRENCES: int = _get_config('income_analysis', 'wealth_periodic_min_occurrences', default=4)
WEALTH_PERIODIC_INTERVAL_TOLERANCE: int = _get_config('income_analysis', 'wealth_periodic_interval_tolerance', default=15)
WEALTH_PERIODIC_MIN_INTERVAL: int = _get_config('income_analysis', 'wealth_periodic_min_interval', default=60)
WEALTH_INCREASING_RATIO: float = _get_config('income_analysis', 'wealth_increasing_ratio', default=0.6)

# ============================================================
# 可视化配置 (从YAML读取)
# ============================================================

VISUALIZATION_MAX_NODES: int = _get_config('visualization', 'max_nodes', default=200)
VISUALIZATION_MAX_EDGES: int = _get_config('visualization', 'max_edges', default=500)
VISUALIZATION_DISPLAY_AMOUNT_THRESHOLD: int = _get_config('visualization', 'display_amount_threshold', default=10000)

# ============================================================
# 调查单位配置 (从YAML读取)
# ============================================================

INVESTIGATION_UNIT_KEYWORDS: List[str] = _get_config('investigation_unit', 'keywords', default=[])

# ============================================================
# 敏感人员配置 (从YAML读取)
# ============================================================

SENSITIVE_PERSON_KEYWORDS: List[str] = _get_config('sensitive_person', 'keywords', default=[])

# ============================================================
# 敏感公司配置 (从YAML读取)
# ============================================================

SENSITIVE_COMPANY_KEYWORDS: List[str] = _get_config('sensitive_company', 'keywords', default=[])
