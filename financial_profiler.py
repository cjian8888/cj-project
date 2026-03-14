#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金画像分析模块 - 资金穿透与关联排查系统
生成个人/公司的资金特征画像
"""

import pandas as pd
import re
from collections import Counter
from dateutil.relativedelta import relativedelta
from typing import Any, Dict, List, Optional, Set, Tuple
import config
import utils

# ========== 列名标准化函数（2026-03-01 通用修复） ==========


def _normalize_column_token(column_name: str) -> str:
    if not column_name:
        return ""
    token = str(column_name).strip().lower()
    token = token.replace("（", "(").replace("）", ")")
    token = re.sub(r"\s+", "", token)
    token = re.sub(r"[(){}\[\]【】:_-]", "", token)
    token = token.replace("人民币", "").replace("rmb", "")
    return token


def _strip_amount_unit_tokens(token: str) -> str:
    normalized = token or ""
    for unit_text in ("亿元", "万元", "亿", "万", "元"):
        normalized = normalized.replace(unit_text, "")
    return normalized


def _find_first_matching_column(
    df: pd.DataFrame, candidates: List[str], is_amount_field: bool = False
) -> Optional[str]:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate

    normalized_candidates = []
    for candidate in candidates:
        token = _normalize_column_token(candidate)
        if is_amount_field:
            token = _strip_amount_unit_tokens(token)
        normalized_candidates.append(token)

    for column_name in df.columns:
        column_token = _normalize_column_token(column_name)
        compare_token = (
            _strip_amount_unit_tokens(column_token) if is_amount_field else column_token
        )
        if compare_token in normalized_candidates:
            return column_name
    return None


def _get_amount_unit_hint_multiplier(column_name: str) -> float:
    token = _normalize_column_token(column_name)
    if "亿元" in token or token.endswith("亿"):
        return 100000000.0
    if "万元" in token or token.endswith("万"):
        return 10000.0
    return 1.0


def _safe_amount(value: Any, column_name: str = "") -> float:
    return utils.format_amount(
        value, unit_hint_multiplier=_get_amount_unit_hint_multiplier(column_name)
    )


def _normalize_amount_series(series: pd.Series, column_name: str) -> pd.Series:
    return series.apply(lambda value: _safe_amount(value, column_name))


def _normalize_datetime_series(series: pd.Series) -> pd.Series:
    normalized = series.apply(utils.parse_date)
    return pd.to_datetime(normalized, errors="coerce")


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    标准化DataFrame的列名，支持个人和公司Excel的不同格式
    【2026-03-01 完善版】支持所有常见列名

    Returns:
        标准化后的DataFrame，包含统一的列名
    """
    df = df.copy()

    # 完整的列名映射字典
    column_mappings = {
        # 日期列
        "date": ["date", "日期", "交易日期", "交易时间", "time", "交易日期时间"],
        # 金额列（单列）
        "amount": [
            "amount",
            "金额",
            "金额(元)",
            "金额(万元)",
            "交易金额",
            "交易金额(元)",
            "交易金额(万元)",
            "发生额",
        ],
        # 收入列（分开）
        "income": [
            "收入(元)",
            "收入(万元)",
            "收入金额",
            "收入",
            "贷方金额",
            "贷方",
            "income",
        ],
        # 支出列（分开）
        "expense": [
            "支出(元)",
            "支出(万元)",
            "支出金额",
            "支出",
            "借方金额",
            "借方",
            "expense",
        ],
        # 交易对手
        "counterparty": [
            "counterparty",
            "交易对手",
            "对方户名",
            "对方账号名",
            "收款人",
            "付款人",
        ],
        # 交易摘要
        "description": ["description", "交易摘要", "摘要", "用途", "备注"],
        # 银行
        "bank": ["bank", "所属银行", "银行", "开户行"],
        # 账号
        "account": ["account", "本方账号", "账号", "银行账号"],
        # 余额
        "balance": ["balance", "余额(元)", "余额(万元)", "余额", "账户余额", "交易余额"],
        # 交易分类
        "category": ["category", "交易分类", "分类", "交易类型"],
        # 现金标识
        "cash": ["cash", "现金", "是否现金"],
    }

    matched_columns: Dict[str, str] = {}

    # 应用映射
    for standard_name, possible_names in column_mappings.items():
        if standard_name in df.columns:
            matched_columns[standard_name] = standard_name
            continue
        matched_name = _find_first_matching_column(
            df,
            possible_names,
            is_amount_field=standard_name in {"amount", "income", "expense", "balance"},
        )
        if matched_name:
            matched_columns[standard_name] = matched_name
            df = df.rename(columns={matched_name: standard_name})

    if "date" in df.columns:
        df["date"] = _normalize_datetime_series(df["date"])

    for amount_col in ("amount", "income", "expense", "balance"):
        if amount_col in df.columns:
            source_col = matched_columns.get(amount_col, amount_col)
            df[amount_col] = _normalize_amount_series(df[amount_col], source_col)

    # 如果有income和expense，合并为amount
    if "income" in df.columns and "expense" in df.columns:
        df["amount"] = df["income"].fillna(0.0) - df["expense"].fillna(0.0)

    return df


def safe_get_column(df: pd.DataFrame, column_names: list, default=None):
    """
    安全获取DataFrame的列，支持多种列名

    Args:
        df: DataFrame
        column_names: 可能的列名列表
        default: 默认值（如果列不存在）

    Returns:
        列数据或默认值
    """
    for col in column_names:
        if col in df.columns:
            return df[col]
    return default


logger = utils.setup_logger(__name__)


AMBIGUOUS_SURNAME_MAP = {
    "侯": {"侯", "候"},
    "候": {"侯", "候"},
}


def _normalize_name_token(value: Any) -> str:
    """标准化姓名/对手方文本，用于别名与家庭成员匹配。"""
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-", "--"}:
        return ""
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[（(【\[].*?[】\])）]", "", text)
    return text


def _name_variants(value: Any) -> Set[str]:
    """生成姓名候选集合，兼容账号后缀、括号附注与常见同音姓。"""
    normalized = _normalize_name_token(value)
    if not normalized:
        return set()

    variants = {normalized}
    chinese_parts = re.findall(r"[\u4e00-\u9fa5]{2,8}", normalized)
    variants.update(part for part in chinese_parts if part)

    for part in list(variants):
        if len(part) < 2:
            continue
        surname = part[0]
        if surname in AMBIGUOUS_SURNAME_MAP:
            for alt in AMBIGUOUS_SURNAME_MAP[surname]:
                variants.add(f"{alt}{part[1:]}")

    trimmed = set()
    for part in variants:
        if len(part) > 4:
            trimmed.update(
                token for token in re.findall(r"[\u4e00-\u9fa5]{2,4}", part) if token
            )
        else:
            trimmed.add(part)
    return {item for item in trimmed if item}


def _matches_name(value: Any, person_name: Any) -> bool:
    """判断文本是否可视为同一人。"""
    if not value or not person_name:
        return False
    value_variants = _name_variants(value)
    name_variants = _name_variants(person_name)
    return bool(value_variants and name_variants and value_variants & name_variants)


def _build_name_alias_set(names: List[Any]) -> Set[str]:
    aliases: Set[str] = set()
    for name in names or []:
        aliases.update(_name_variants(name))
    return aliases


def _matches_alias_set(value: Any, aliases: Set[str]) -> bool:
    return bool(aliases and _name_variants(value) & aliases)


def _find_expenses_near_date(
    expense_history: List[Dict], target_date, amount: float, tolerance: float
) -> bool:
    """
    在给定的支出历史中，查找接近目标日期且金额与给定金额在容忍度范围内的记录。
    仅用于窄化匹配范围，返回布尔值指示是否存在符合条件的记录。
    """
    if not expense_history:
        return False
    parsed_target_date = utils.parse_date(target_date)
    if parsed_target_date is None:
        return False
    target_day = parsed_target_date.date()
    tol = abs(amount) * tolerance
    for e in expense_history:
        ex_date = e.get("date")
        ex_amt = _safe_amount(e.get("amount", e.get("金额", 0) or 0), "amount")
        if ex_date is None:
            continue
        # 将日期统一为 datetime.date 或 datetime-like
        ex_dt = utils.parse_date(ex_date)
        if ex_dt is None:
            continue
        ex_day = ex_dt.date()
        if abs(ex_amt - amount) <= tol:
            # 简单时间匹配：与目标日期在 +/- 30 天内
            days_diff = abs((target_day - ex_day).days)
            if days_diff <= 30:
                return True
    return False


def _find_expenses_near_date_from_history(
    expense_history: List[Dict], target_date, amount: float, tolerance: float
) -> bool:
    return _find_expenses_near_date(expense_history, target_date, amount, tolerance)


def match_historical_expense(
    income_record: Dict, expense_history: List[Dict], tolerance: float = 0.05
) -> (bool, int):
    """
    匹配空摘要/空对手方的收入记录在历史支出中是否有近似金额且近似日期的支出。
    返回 (matched: bool, months_ago: int or None)。若未匹配，months_ago 为 None。
    """
    amount = _safe_amount(income_record.get("amount", 0) or 0, "amount")
    date = utils.parse_date(income_record.get("date"))
    if date is None:
        return False, None
    for months_ago in [3, 6, 12, 24, 36, 48]:
        try:
            target_date = date - relativedelta(months=months_ago)
        except Exception:
            continue
        if _find_expenses_near_date(expense_history, target_date, amount, tolerance):
            return True, months_ago
    return False, None


def _calculate_stable_cv(amounts: List[float], remove_outliers: bool = True) -> float:
    """
    计算变异系数CV，可选择剔除异常值

    Args:
        amounts: 金额列表
        remove_outliers: 是否剔除异常值（使用IQR方法）

    Returns:
        变异系数CV
    """
    if len(amounts) == 0:
        return 999

    # 如果需要剔除异常值且数据量足够
    if remove_outliers and len(amounts) > 3:
        # 使用IQR方法识别异常值
        sorted_amounts = sorted(amounts)
        n = len(sorted_amounts)
        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_amounts[q1_idx]
        q3 = sorted_amounts[q3_idx]
        iqr = q3 - q1

        # 定义上下界
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        # 过滤异常值
        filtered_amounts = [x for x in amounts if lower_bound <= x <= upper_bound]

        # 如果剔除后至少还有一半数据，使用过滤后的数据
        if len(filtered_amounts) >= max(3, len(amounts) * 0.5):
            amounts = filtered_amounts
            logger.debug(
                f"剔除异常值: 原{len(amounts)}笔 -> 保留{len(filtered_amounts)}笔"
            )

    # 计算均值和标准差
    mean_amt = sum(amounts) / len(amounts)
    variance = sum((x - mean_amt) ** 2 for x in amounts) / len(amounts)
    std_amt = variance**0.5

    # 计算CV
    cv = std_amt / mean_amt if mean_amt > 0 else 999

    return cv


def _identify_reimbursements(income_df: pd.DataFrame) -> pd.DataFrame:
    """
    识别报销/差旅/退款（负面清单）- 向量化版本

    Args:
        income_df: 收入DataFrame

    Returns:
        标记了is_reimbursement的DataFrame
    """
    immunity_keywords = [
        "安家费",
        "年终奖",
        "绩效",
        "奖金",
        "工资",
        "薪资",
        "劳务",
        "骨干奖",
        "贡献奖",
    ]

    # 排除自转账记录
    mask_self = ~income_df["is_self_transfer"].fillna(False)

    # 向量化匹配：构建正则表达式
    descriptions = income_df["description"].astype(str).fillna("").str.lower()
    # 修复: 先转 str 再 fillna， 避免 Categorical 类型错误

    # 检查排除关键词（报销关键词）
    if config.EXCLUDED_REIMBURSEMENT_KEYWORDS:
        pattern_exclude = "|".join(
            map(re.escape, config.EXCLUDED_REIMBURSEMENT_KEYWORDS)
        )
        mask_exclude = descriptions.str.contains(pattern_exclude, regex=True, na=False)
    else:
        mask_exclude = pd.Series(False, index=income_df.index)

    # 检查豁免关键词（非报销关键词）
    pattern_immunity = "|".join(map(re.escape, immunity_keywords))
    mask_immunity = descriptions.str.contains(pattern_immunity, regex=True, na=False)

    # 最终条件：包含排除关键词且不包含豁免关键词，且不是自转账
    reimbursement_mask = mask_self & mask_exclude & ~mask_immunity

    # 批量赋值
    income_df.loc[reimbursement_mask, "is_reimbursement"] = True

    # 进一步识别“单位报销/业务往来款”，避免被工资或理财赎回误判
    income_df = _identify_business_reimbursement_income(income_df)
    if "is_business_reimbursement" in income_df.columns:
        income_df.loc[
            income_df["is_business_reimbursement"].fillna(False), "is_reimbursement"
        ] = True

    return income_df


def _identify_business_reimbursement_income(df: pd.DataFrame) -> pd.DataFrame:
    """
    识别单位报销/业务往来款（高精度规则）。

    设计目标：
    1. 识别项目交流、差旅、技术沟通、用餐、交通等看起来像单位报销的收入
    2. 避免把这类资金误识别为工资或理财赎回
    3. 输出单独标记，供真实收入剔除和报告分类统计使用
    """
    if df.empty:
        if "is_business_reimbursement" not in df.columns:
            df["is_business_reimbursement"] = False
        if "business_reimbursement_reason" not in df.columns:
            df["business_reimbursement_reason"] = ""
        return df

    work_df = df.copy()
    if "is_business_reimbursement" not in work_df.columns:
        work_df["is_business_reimbursement"] = False
    if "business_reimbursement_reason" not in work_df.columns:
        work_df["business_reimbursement_reason"] = ""

    description = (
        work_df["description"].astype(str).fillna("").str.strip()
        if "description" in work_df.columns
        else pd.Series("", index=work_df.index)
    )
    counterparty = (
        work_df["counterparty"].astype(str).fillna("").str.strip()
        if "counterparty" in work_df.columns
        else pd.Series("", index=work_df.index)
    )
    combined = counterparty + " " + description
    self_mask = (
        ~work_df["is_self_transfer"].fillna(False)
        if "is_self_transfer" in work_df.columns
        else pd.Series(True, index=work_df.index, dtype=bool)
    )

    strong_keywords = [
        "报销",
        "费用报销",
        "差旅报销",
        "报账",
        "垫付款",
        "垫付返还",
        "商务报销",
        "招待费",
        "会务费",
        "餐费",
        "交通费",
        "住宿费",
        "油费",
        "打车费",
    ]
    business_scene_keywords = [
        "项目交流",
        "技术交流",
        "项目开发",
        "项目支持",
        "出差",
        "差旅",
        "住宿",
        "用餐",
        "会议",
        "会务",
        "培训",
        "商务",
        "考察",
        "招待",
        "交通",
        "车费",
        "机票",
        "高铁",
        "滴滴",
        "打车",
        "过路费",
        "停车费",
        "油费",
    ]
    immunity_keywords = [
        "工资",
        "薪资",
        "绩效",
        "奖金",
        "年终奖",
        "补贴",
        "补助",
        "福利",
        "劳务",
        "稿费",
        "讲课费",
        "专家费",
    ]

    wealth_keywords = []
    for attr in [
        "WEALTH_REDEMPTION_KEYWORDS",
        "KNOWN_WEALTH_PRODUCTS",
        "WEALTH_PRODUCT_COUNTERPARTY_KEYWORDS",
    ]:
        wealth_keywords.extend(getattr(config, attr, []) or [])
    salary_keywords = (getattr(config, "SALARY_STRONG_KEYWORDS", []) or []) + (
        getattr(config, "SALARY_KEYWORDS", []) or []
    )

    def _build_pattern(keywords: List[str]) -> str:
        cleaned = [re.escape(str(kw).strip()) for kw in keywords if str(kw).strip()]
        return "|".join(dict.fromkeys(cleaned))

    strong_pattern = _build_pattern(strong_keywords)
    business_scene_pattern = _build_pattern(business_scene_keywords)
    immunity_pattern = _build_pattern(immunity_keywords)
    wealth_pattern = _build_pattern(wealth_keywords)
    salary_pattern = _build_pattern(salary_keywords)

    institution_pattern = (
        r"(?:公司|有限|股份|集团|中心|研究|医院|学校|大学|学院|研究所|研究院|银行|科技|汽车|工业|贸易|服务|委员会|管理局)"
    )

    has_strong_kw = (
        combined.str.contains(strong_pattern, regex=True, na=False)
        if strong_pattern
        else pd.Series(False, index=work_df.index)
    )
    has_business_scene_kw = (
        description.str.contains(business_scene_pattern, regex=True, na=False)
        if business_scene_pattern
        else pd.Series(False, index=work_df.index)
    )
    has_immunity = (
        combined.str.contains(immunity_pattern, regex=True, na=False)
        if immunity_pattern
        else pd.Series(False, index=work_df.index)
    )
    has_wealth_hint = (
        combined.str.contains(wealth_pattern, regex=True, na=False)
        if wealth_pattern
        else pd.Series(False, index=work_df.index)
    )
    has_salary_hint = (
        combined.str.contains(salary_pattern, regex=True, na=False)
        if salary_pattern
        else pd.Series(False, index=work_df.index)
    )
    has_institution = counterparty.str.contains(
        institution_pattern, regex=True, na=False
    )

    strong_reimbursement_mask = self_mask & has_strong_kw & ~has_immunity & ~has_wealth_hint
    business_reimbursement_mask = (
        self_mask
        & has_business_scene_kw
        & has_institution
        & ~has_immunity
        & ~has_wealth_hint
        & ~has_salary_hint
    )

    work_df.loc[strong_reimbursement_mask, "is_business_reimbursement"] = True
    work_df.loc[
        strong_reimbursement_mask, "business_reimbursement_reason"
    ] = "单位报销/费用报销"

    pure_business_mask = business_reimbursement_mask & ~strong_reimbursement_mask
    work_df.loc[pure_business_mask, "is_business_reimbursement"] = True
    work_df.loc[
        pure_business_mask, "business_reimbursement_reason"
    ] = "单位业务往来款(项目/差旅)"

    return work_df


def _check_payday_pattern(dates: List, min_concentration: float = 0.6) -> Tuple[bool, float, Optional[int]]:
    """
    检查发薪日期是否集中在每月固定几天
    
    Args:
        dates: 日期列表 (datetime 对象)
        min_concentration: 集中度阈值 (默认 0.6 表示 60%)
        
    Returns:
        (is_pattern, concentration, dominant_day) 元组
        is_pattern: 是否有规律
        concentration: 集中度 (0-1)
        dominant_day: 主要发薪日 (1-31)
    """
    if not dates or len(dates) < 4:
        return False, 0.0, None
    
    # 提取每个日期的“日”部分
    days = [d.day for d in dates if hasattr(d, 'day')]
    if not days:
        return False, 0.0, None
    
    # 统计发薪日的分布
    from collections import Counter
    day_counts = Counter(days)
    total = len(days)
    
    # 找出最常见的发薪日区间 (允许 +/- 2 天误差)
    # 将日期分为几个区间: 1-5, 6-10, 11-15, 16-20, 21-25, 26-31
    ranges = [
        (1, 5, '月初'),
        (6, 10, '上旬'),
        (11, 15, '中旬'),
        (16, 20, '下旬'),
        (21, 25, '月末'),
        (26, 31, '月底'),
    ]
    
    range_counts = {}
    for start, end, label in ranges:
        count = sum(c for d, c in day_counts.items() if start <= d <= end)
        range_counts[label] = count
    
    if not range_counts:
        return False, 0.0, None
    
    # 找出最多的区间
    dominant_range = max(range_counts, key=range_counts.get)
    dominant_count = range_counts[dominant_range]
    concentration = dominant_count / total
    
    # 找出最常见的单日
    dominant_day = day_counts.most_common(1)[0][0] if day_counts else None
    
    is_pattern = concentration >= min_concentration
    
    return is_pattern, concentration, dominant_day

def _learn_salary_payers(income_df: pd.DataFrame) -> set:
    """
    自动挖掘工资发放单位 - 向量化优化版

    Args:
        income_df: 收入DataFrame

    Returns:
        发薪单位白名单集合
    """
    learned_salary_payers = set(
        config.KNOWN_SALARY_PAYERS + config.USER_DEFINED_SALARY_PAYERS
    )

    if income_df.empty:
        logger.info(f"已识别的发薪/收入来源白名单: {list(learned_salary_payers)}")
        return learned_salary_payers

    # 定义由于理财/投资/基金导致的"假性工资发放者"黑名单关键词
    WEALTH_ENTITY_BLACKLIST = [
        "基金",
        "资产管理",
        "投资",
        "信托",
        "证券",
        "期货",
        "保险",
        "财富",
        "资本",
        "经营部",
        "个体",
        "直销",
        "理财",
        "固收",
        "定活宝",
        "增利",
        "Fund",
        "Asset",
        "Invest",
        "Capital",
        "Wealth",
    ]

    # 【P1-性能5优化】向量化处理：一次性筛选有效对手方
    # 1. 筛选有对手方且长度>=4的记录
    cp_series = income_df["counterparty"].astype(str).fillna("")
    valid_mask = cp_series.str.len() >= 4
    valid_df = income_df[valid_mask].copy()

    if valid_df.empty:
        logger.info(f"已识别的发薪/收入来源白名单: {list(learned_salary_payers)}")
        return learned_salary_payers

    # 2. 向量化识别代发工资内部户
    payroll_mask = cp_series[valid_mask].str.contains("代发工资", na=False)
    payroll_payers = set(valid_df.loc[payroll_mask, "counterparty"].unique())
    learned_salary_payers.update(payroll_payers)

    # 3. 【P1-性能5优化】向量化识别工资关键词
    salary_keywords = config.SALARY_STRONG_KEYWORDS + [
        "年终奖",
        "骨干奖",
        "绩效",
        "薪酬",
        "代发工资",
    ]
    desc_series = valid_df["description"].astype(str).fillna("")

    # 构建正则表达式模式（性能优化：只编译一次）
    salary_pattern = "|".join(map(re.escape, salary_keywords))
    has_salary_keyword = desc_series.str.contains(salary_pattern, regex=True, na=False)

    # 安全检查函数：排除黑名单和银行分行
    def is_valid_payer(cp: str) -> bool:
        """检查是否为有效发薪单位"""
        if utils.contains_keywords(cp, WEALTH_ENTITY_BLACKLIST):
            return False
        if "银行" in cp and "人力" not in cp:
            return False
        return True

    # 获取有工资关键词但不在黑名单中的对手方
    potential_payers = valid_df.loc[has_salary_keyword, "counterparty"].unique()
    valid_payers = {cp for cp in potential_payers if is_valid_payer(str(cp))}
    learned_salary_payers.update(valid_payers)

    logger.info(f"已识别的发薪/收入来源白名单: {list(learned_salary_payers)}")
    return learned_salary_payers


def _identify_salary_by_whitelist(
    income_df: pd.DataFrame, learned_salary_payers: set
) -> pd.DataFrame:
    """
    轮次1: 白名单单位的所有打款（除非明确是退款或理财赎回）
    【性能优化】使用向量化操作替代双重循环，O(n*m) -> O(n)

    Args:
        income_df: 收入DataFrame
        learned_salary_payers: 发薪单位白名单

    Returns:
        标记了is_salary的DataFrame
    """
    if income_df.empty or not learned_salary_payers:
        return income_df

    # 1. 创建跳过掩码（已为工资、本人转账、报销）
    skip_mask = (
        income_df["is_salary"]
        | income_df["is_self_transfer"]
        | income_df["is_reimbursement"]
    )

    # 2. 创建双重保险掩码（排除理财赎回特征）
    desc_series = income_df["description"].astype(str)
    wealth_mask = desc_series.str.contains(
        "赎回|卖出|本金|退保|分红", regex=True, na=False
    )

    # 3. 【向量化】检查对手方是否匹配任何白名单单位
    # 将所有白名单单位组合成正则表达式模式
    payer_pattern = "|".join(re.escape(payer) for payer in learned_salary_payers)
    cp_series = income_df["counterparty"].astype(str)
    whitelist_mask = cp_series.str.contains(payer_pattern, regex=True, na=False)

    # 4. 综合掩码：符合白名单但未被标记且非理财特征的记录
    final_mask = whitelist_mask & ~skip_mask & ~wealth_mask

    # 5. 批量设置工资标记
    # 【P1修复】空group检查优化
    if final_mask.any() and len(income_df) > 0:
        income_df.loc[final_mask, "is_salary"] = True

        # 6. 【向量化】区分奖金类描述
        bonus_mask = desc_series.str.contains("奖|绩效|年薪", regex=True, na=False)
        bonus_final_mask = final_mask & bonus_mask

        # 设置默认原因
        income_df.loc[final_mask, "salary_reason"] = "已知发薪单位"
        # 设置奖金类原因
        if bonus_final_mask.any():
            income_df.loc[bonus_final_mask, "salary_reason"] = (
                "已知单位-" + income_df.loc[bonus_final_mask, "description"]
            )

    return income_df


def _identify_salary_by_keywords(income_df: pd.DataFrame) -> pd.DataFrame:
    """
    轮次2: 强关键词匹配 (需严格区分理财分红和奖金分红) - 向量化优化版

    Args:
        income_df: 收入DataFrame

    Returns:
        标记了is_salary的DataFrame
    """
    WEALTH_ENTITY_BLACKLIST = [
        "基金",
        "资产管理",
        "投资",
        "信托",
        "证券",
        "期货",
        "保险",
        "财富",
        "资本",
        "经营部",
        "个体",
        "直销",
        "理财",
        "Fund",
        "Asset",
        "Invest",
        "Capital",
        "Wealth",
    ]

    if income_df.empty:
        return income_df

    # 【P1-性能6优化】向量化处理：一次性创建掩码
    # 1. 跳过已经标记为工资、本人转账或报销的记录
    skip_mask = (
        income_df["is_salary"]
        | income_df["is_self_transfer"]
        | income_df["is_reimbursement"].fillna(False)
    )

    # 2. 筛选待处理的记录
    candidates_df = income_df[~skip_mask].copy()
    if candidates_df.empty:
        return income_df

    # 3. 向量化检查工资关键词
    desc_series = candidates_df["description"].astype(str).fillna("")
    salary_pattern = "|".join(map(re.escape, config.SALARY_STRONG_KEYWORDS))
    has_salary_keyword = desc_series.str.contains(salary_pattern, regex=True, na=False)

    # 4. 【P1-性能6优化】处理"分红"特殊情况：排除金融机构的分红
    dividend_mask = desc_series.str.contains("分红", na=False)
    cp_series = candidates_df["counterparty"].astype(str).fillna("")

    # 检查对手方是否在黑名单中（向量化方式）
    blacklist_pattern = "|".join(map(re.escape, WEALTH_ENTITY_BLACKLIST))
    is_wealth_entity = cp_series.str.contains(blacklist_pattern, regex=True, na=False)

    # 分红但对手方是金融机构的，不认定为工资
    invalid_dividend_mask = dividend_mask & is_wealth_entity

    # 5. 最终掩码：有工资关键词，且不是无效分红
    final_mask = has_salary_keyword & ~invalid_dividend_mask

    # 6. 批量更新
    valid_indices = candidates_df[final_mask].index
    if len(valid_indices) > 0:
        income_df.loc[valid_indices, "is_salary"] = True
        income_df.loc[valid_indices, "salary_reason"] = "摘要含强工资关键词"

    return income_df


def _identify_salary_by_hr_company(income_df: pd.DataFrame) -> pd.DataFrame:
    """
    轮次3: 人力资源公司识别 - 向量化优化版

    Args:
        income_df: 收入DataFrame

    Returns:
        标记了is_salary的DataFrame
    """
    if income_df.empty or not config.HR_COMPANY_KEYWORDS:
        return income_df

    # 【P1-性能7优化】向量化处理：一次性创建掩码
    # 1. 跳过已经标记为工资、本人转账或报销的记录
    skip_mask = (
        income_df["is_salary"]
        | income_df["is_self_transfer"]
        | income_df["is_reimbursement"].fillna(False)
    )

    # 2. 筛选待处理的记录
    candidates_df = income_df[~skip_mask].copy()
    if candidates_df.empty:
        return income_df

    # 3. 向量化检查人力资源公司关键词
    cp_series = candidates_df["counterparty"].astype(str).fillna("")
    hr_pattern = "|".join(map(re.escape, config.HR_COMPANY_KEYWORDS))
    is_hr_company = cp_series.str.contains(hr_pattern, regex=True, na=False)

    # 4. 检查金额条件
    meets_amount = candidates_df["income"] >= config.INCOME_MIN_AMOUNT

    # 5. 最终掩码：是人力资源公司且金额达标
    final_mask = is_hr_company & meets_amount

    # 6. 批量更新
    valid_indices = candidates_df[final_mask].index
    if len(valid_indices) > 0:
        income_df.loc[valid_indices, "is_salary"] = True
        income_df.loc[valid_indices, "salary_reason"] = "人力资源公司"

    return income_df


def _identify_salary_by_frequency(income_df: pd.DataFrame) -> pd.DataFrame:
    """
    轮次4: 高频稳定收入 (严格排除金融机构)
    【P1-性能6修复】完全向量化实现，替代iterrows循环

    【审计风险警告 - 2026-01-11 增强】
    此轮次可能将"分期受贿"误识别为工资，增加以下防护：
    1. 金额上限：月均收入超过10万需人工复核（不自动标记为工资）
    2. 对手方类型：如果对手方是个人姓名（2-4个汉字），需要额外警告
    3. 政府机关白名单：来自政府机关的规律性收入优先识别为合规

    Args:
        income_df: 收入DataFrame

    Returns:
        标记了is_salary的DataFrame
    """
    if income_df.empty:
        return income_df

    HIGH_FREQUENCY_AMOUNT_CAP = config.HIGH_FREQUENCY_SALARY_CAP
    wealth_keywords = [
        "赎回",
        "到期",
        "本息",
        "转存",
        "理财",
        "结息",
        "收益",
        "分红",
        "活期宝",
        "转活",
        "提现",
        "银证",
    ]
    wealth_pattern = "|".join(wealth_keywords)
    loan_platform_pattern = "|".join(
        config.LOAN_PLATFORM_KEYWORDS + config.THIRD_PARTY_PAYMENT_KEYWORDS
    )
    gov_pattern = "|".join(config.GOVERNMENT_AGENCY_KEYWORDS)

    # 【向量化1】预筛选：未标记为工资且非本人转账的记录
    base_mask = ~(income_df["is_salary"] | income_df.get("is_self_transfer", False))
    process_df = income_df[base_mask].copy()

    if process_df.empty:
        return income_df

    cp_series = process_df["counterparty"].astype(str)

    # 【向量化2】排除非法对手方（空值、nan、数字账户、金融机构）
    invalid_mask = (
        cp_series.isna()
        | (cp_series == "nan")
        | (cp_series == "")
        | cp_series.str.match(r"^\d{10,}$", na=False)
        | cp_series.str.contains(
            f"银行|保险|证券|基金|信托|期货|资产|投资|理财|{loan_platform_pattern}",
            regex=True,
            na=False,
        )
    )

    # 【向量化3】排除个人姓名（非政府机关）
    individual_mask = cp_series.str.match(r"^[\u4e00-\u9fa5]{2,4}$", na=False)
    gov_mask = cp_series.str.contains(gov_pattern, regex=True, na=False)
    invalid_mask |= individual_mask & ~gov_mask

    process_df = process_df[~invalid_mask]

    if process_df.empty:
        return income_df

    # 【向量化4】按对手方分组统计（核心优化：单次groupby完成所有计算）
    group_stats = (
        process_df.groupby("counterparty")
        .agg(
            total_count=("counterparty", "size"),
            valid_count=("is_reimbursement", lambda x: (~x.fillna(False)).sum()),
            months=(
                "date",
                lambda x: x.apply(
                    lambda d: d.strftime("%Y-%m") if pd.notna(d) else None
                ).nunique(),
            ),
            mean_income=("income", "mean"),
            wealth_ratio=(
                "description",
                lambda x: x.astype(str)
                .str.contains(wealth_pattern, regex=True, na=False)
                .mean(),
            ),
        )
        .reset_index()
    )

    # 【向量化5】计算变异系数（CV）
    def calc_cv(group):
        amounts = group["income"].tolist()
        return (
            _calculate_stable_cv(amounts, remove_outliers=True)
            if len(amounts) > 1
            else float("inf")
        )

    cv_series = process_df.groupby("counterparty").apply(calc_cv, include_groups=False)
    group_stats = group_stats.merge(
        cv_series.rename("cv"), left_on="counterparty", right_index=True, how="left"
    )

    # 【向量化6】应用频率稳定性条件筛选有效对手方 - 使用 config 阈值
    valid_mask = (
        (group_stats["valid_count"] >= config.SALARY_FREQUENCY_MIN_COUNT)
        & (group_stats["months"] >= config.SALARY_FREQUENCY_MIN_MONTHS)
        & (group_stats["valid_count"] / group_stats["months"] > config.SALARY_FREQUENCY_MONTH_RATIO)
        & (group_stats["mean_income"] <= HIGH_FREQUENCY_AMOUNT_CAP)
        & (group_stats["mean_income"] >= config.INCOME_MEAN_AMOUNT_MIN)
        & (group_stats["mean_income"] <= config.INCOME_MEAN_AMOUNT_MAX)
        & (group_stats["wealth_ratio"] <= 0.3)
        & (group_stats["cv"] < config.SALARY_CV_THRESHOLD_LOOSE)
    )

    valid_counterparties = group_stats.loc[valid_mask, "counterparty"].tolist()
    months_dict = dict(
        zip(
            group_stats.loc[valid_mask, "counterparty"],
            group_stats.loc[valid_mask, "months"],
        )
    )

    if not valid_counterparties:
        return income_df

    # 【向量化7】标记符合条件的行
    candidate_mask = process_df["counterparty"].isin(valid_counterparties)
    valid_rows = process_df[candidate_mask].copy()
    valid_rows = valid_rows[~valid_rows["is_reimbursement"].fillna(False)]
    valid_rows = valid_rows[
        ~valid_rows["description"]
        .astype(str)
        .str.contains(wealth_pattern, regex=True, na=False)
    ]

    # 批量更新原始DataFrame
    valid_indices = valid_rows.index
    income_df.loc[valid_indices, "is_salary"] = True
    income_df.loc[valid_indices, "salary_reason"] = valid_rows["counterparty"].map(
        lambda cp: f"高频稳定收入(连续{months_dict.get(cp, 0)}月)"
    )

    return income_df


def _calculate_yearly_monthly_stats(df: pd.DataFrame) -> tuple:
    """
    计算年度/月度统计

    Args:
        df: 交易DataFrame

    Returns:
        (yearly_stats, monthly_stats) 元组
    """
    # 检查DataFrame是否为空，避免空DataFrame访问.dt属性时报错
    if not df.empty and pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["year"] = df["date"].dt.year
        yearly_stats = (
            df.groupby("year").agg({"income": "sum", "expense": "sum"}).to_dict("index")
        )
        df["month"] = df["date"].apply(utils.get_month_key)
        monthly_stats = (
            df.groupby("month")
            .agg({"income": "sum", "expense": "sum"})
            .to_dict("index")
        )
    else:
        yearly_stats = {}
        monthly_stats = {}

    return yearly_stats, monthly_stats


def calculate_income_structure(df: pd.DataFrame, entity_name: str = None) -> Dict:
    """
    计算收支结构（增强版工资识别 - 能够自动识别工资发放单位，并严格剔除理财/投资类回款）

    Args:
        df: 交易DataFrame
        entity_name: 核查对象姓名（用于排除同名转账）

    Returns:
        收支结构字典
    """
    logger.info("正在计算收支结构...")

    # 获取日期范围
    # 【容错处理】安全获取日期列
    date_column = safe_get_column(df, ["date", "交易时间", "交易日期", "日期"])
    if date_column is not None:
        start_date, end_date = utils.calculate_date_range(date_column.tolist())
    else:
        logger.warning("未找到日期列，使用默认日期范围")
        start_date, end_date = "2020-01-01", datetime.now().strftime("%Y-%m-%d")

    # 统计总流入和同名转账
    total_inflow = df["income"].sum()
    total_expense = df["expense"].sum()

    # 识别同名转账（本人转入）
    self_transfer_mask = (df["counterparty"] == entity_name) & (df["income"] > 0)
    self_transfer_income = df[self_transfer_mask]["income"].sum()

    # 计算外部净收入（排除本人互转）
    external_income = total_inflow - self_transfer_income

    # 识别工资性收入（增强版）
    salary_income = 0.0
    non_salary_income = 0.0
    salary_details = []  # 工资明细列表

    # 只处理收入记录
    income_df = df[df["income"] > 0].copy()

    if not income_df.empty:
        # 为每笔收入标记是否为工资
        income_df["is_salary"] = False
        income_df["salary_reason"] = ""  # 判定依据
        income_df["is_self_transfer"] = False  # 是否为本人互转
        income_df["is_reimbursement"] = False  # 是否为报销/退款

        if entity_name:
            income_df.loc[
                income_df["counterparty"] == entity_name, "is_self_transfer"
            ] = True

        # 预处理：识别报销/差旅/退款（负面清单）
        income_df = _identify_reimbursements(income_df)

        # 步骤 A: 自动挖掘工资发放单位
        learned_salary_payers = _learn_salary_payers(income_df)

        # 步骤 B: 多轮次识别
        # 轮次1: 白名单单位的所有打款
        income_df = _identify_salary_by_whitelist(income_df, learned_salary_payers)

        # 轮次2: 强关键词匹配
        income_df = _identify_salary_by_keywords(income_df)

        # 轮次3: 人力资源公司
        income_df = _identify_salary_by_hr_company(income_df)

        # 轮次4: 高频稳定收入
        income_df = _identify_salary_by_frequency(income_df)

        # 【P1-性能8优化】统计：使用向量化操作替代iterrows
        # 1. 计算工资性收入（向量化求和）
        salary_mask = income_df["is_salary"]
        salary_income = income_df.loc[salary_mask, "income"].sum()

        # 2. 批量构建工资明细列表（使用to_dict替代iterrows）
        salary_details = (
            income_df[salary_mask][
                ["date", "income", "counterparty", "description", "salary_reason"]
            ]
            .rename(
                columns={
                    "date": "日期",
                    "income": "金额",
                    "counterparty": "对手方",
                    "description": "摘要",
                    "salary_reason": "判定依据",
                }
            )
            .to_dict("records")
        )

        # 3. 计算非工资收入（向量化）
        non_salary_mask = (
            ~salary_mask
            & ~income_df["is_self_transfer"]
            & ~income_df["is_reimbursement"].fillna(False)
        )
        non_salary_income = income_df.loc[non_salary_mask, "income"].sum()

    # 按年度/月度统计
    yearly_stats, monthly_stats = _calculate_yearly_monthly_stats(df)

    result = {
        "date_range": (start_date, end_date),
        "total_inflow": total_inflow,
        "total_income": total_inflow,
        "self_transfer_income": self_transfer_income,
        "external_income": external_income,
        "total_expense": total_expense,
        "net_flow": total_inflow - total_expense,
        "salary_income": salary_income,
        "non_salary_income": non_salary_income,
        "salary_ratio": salary_income / total_inflow if total_inflow > 0 else 0,
        "salary_details": salary_details,
        "yearly_stats": yearly_stats,
        "monthly_stats": monthly_stats,
        "transaction_count": len(df),
    }

    logger.info(
        f"工资性收入: {utils.format_currency(salary_income)}({len(salary_details)}笔)"
    )
    return result


# ========== Phase 1.2: 银行账户提取 (2026-01-21 新增) ==========

# 余额列名变体，支持多种常见格式
BALANCE_COLUMN_VARIANTS = [
    "余额(元)",
    "balance",
    "余额",
    "交易余额",
    "账户余额",
    "当前余额",
    "结余",
]

# 账号列名候选（包含清洗后英文列与原始中文列）
ACCOUNT_COLUMN_CANDIDATES = [
    "account",
    "account_number",
    "account_id",
    "本方账号",
    "账号",
    "卡号",
]

# 银行名称列名候选
BANK_NAME_CANDIDATES = ["银行来源", "bank_source", "所属银行"]


def _detect_account_column(df: pd.DataFrame) -> Optional[str]:
    """
    检测DataFrame中的账号列名。

    按优先级顺序检查常见账号列名，返回第一个匹配的列名。

    Args:
        df: 交易数据DataFrame

    Returns:
        账号列名，如果未找到则返回None
    """
    for col in ACCOUNT_COLUMN_CANDIDATES:
        if col in df.columns:
            return col
    return None


def _detect_balance_column(df: pd.DataFrame) -> Optional[str]:
    """
    检测DataFrame中的余额列名。

    支持多种余额列名格式，包括中文和英文变体。

    Args:
        df: 交易数据DataFrame

    Returns:
        余额列名，如果未找到则返回None
    """
    for col in BALANCE_COLUMN_VARIANTS:
        if col in df.columns:
            logger.info(f"检测到余额列: {col}")
            return col
    logger.info("未检测到余额列，将使用净流入估算余额")
    return None


def _extract_transaction_basic_info(row: pd.Series, entity_name: Optional[str]) -> Dict:
    """
    从单行数据中提取交易基本信息。

    提取银行名称、账户类型、账户类别、是否真实银行卡等字段。
    对于每个字段，按优先级尝试多个可能的列名。

    Args:
        row: 单行交易数据
        entity_name: 实体名称

    Returns:
        包含基本信息的字典
    """
    # 获取银行名称
    bank_name = ""
    for col in BANK_NAME_CANDIDATES:
        if col in row.index and pd.notna(row[col]):
            bank_name = str(row[col])
            break

    # 获取账户类型（默认借记卡）
    account_type = "借记卡"
    if "account_type" in row.index and pd.notna(row["account_type"]):
        account_type = str(row["account_type"])

    # 获取账户类别（默认个人账户）
    account_category = "个人账户"
    if "account_category" in row.index and pd.notna(row["account_category"]):
        account_category = str(row["account_category"])

    # 获取是否为真实银行卡（默认真）
    is_real_bank_card = True
    if "is_real_bank_card" in row.index:
        is_real_bank_card = bool(row["is_real_bank_card"])

    # 获取交易日期和金额
    tx_date = row.get("date")
    income = _safe_amount(row.get("income", 0), "income")
    expense = _safe_amount(row.get("expense", 0), "expense")

    return {
        "bank_name": bank_name,
        "account_type": account_type,
        "account_category": account_category,
        "is_real_bank_card": is_real_bank_card,
        "tx_date": tx_date,
        "income": income,
        "expense": expense,
        "entity_name": entity_name or "",
    }


def _extract_balance_from_row(row: pd.Series, balance_col: Optional[str]) -> float:
    """
    从行数据中提取余额值。

    Args:
        row: 单行交易数据
        balance_col: 余额列名

    Returns:
        余额值，如果无法提取则返回0.0
    """
    if not balance_col:
        return 0.0

    raw_balance = row.get(balance_col)
    return _safe_amount(raw_balance, balance_col or "balance")


def _create_new_account_record(
    account_num: str, info: Dict, balance: float, tx_date
) -> Dict:
    """
    创建新的账户记录。

    Args:
        account_num: 账号
        info: 基本信息字典
        balance: 余额
        tx_date: 交易日期

    Returns:
        新账户记录字典
    """
    return {
        "account_number": account_num,
        "bank_name": info["bank_name"],
        "account_type": info["account_type"],
        "account_category": info["account_category"],
        "is_real_bank_card": info["is_real_bank_card"],
        "first_transaction_date": tx_date,
        "last_transaction_date": tx_date,
        "transaction_count": 1,
        "total_income": info["income"],
        "total_expense": info["expense"],
        "entity_name": info["entity_name"],
        "last_balance": balance,
        "_last_balance_date": tx_date,  # 内部字段，用于比较日期
    }


def _update_existing_account_record(
    account: Dict, info: Dict, balance: float, tx_date, balance_col: Optional[str]
) -> None:
    """
    更新现有账户记录。

    更新日期范围、余额、统计信息。余额更新逻辑：
    - 如果交易日期晚于当前最后交易日期，更新余额
    - 如果交易日期相同，优先取非零余额

    Args:
        account: 现有账户记录
        info: 新交易的基本信息
        balance: 新交易的余额
        tx_date: 新交易日期
        balance_col: 余额列名（用于判断是否有余额数据）
    """
    # 更新最早交易日期
    if tx_date and (
        account["first_transaction_date"] is None
        or tx_date < account["first_transaction_date"]
    ):
        account["first_transaction_date"] = tx_date

    # 更新最后交易日期和余额
    if tx_date and (
        account["last_transaction_date"] is None
        or tx_date > account["last_transaction_date"]
    ):
        account["last_transaction_date"] = tx_date
        # 关键：当遇到更晚的交易时，更新余额为该笔交易的余额
        if balance_col and balance != 0:
            account["last_balance"] = balance
            account["_last_balance_date"] = tx_date
    elif tx_date and tx_date == account["last_transaction_date"]:
        # 同一天的多笔交易，取有值的余额（非零优先）
        if balance_col and balance != 0 and account["last_balance"] == 0:
            account["last_balance"] = balance

    # 累加统计
    account["transaction_count"] += 1
    account["total_income"] += info["income"]
    account["total_expense"] += info["expense"]

    # 更新银行名称（如果之前为空）
    if not account["bank_name"] and info["bank_name"]:
        account["bank_name"] = info["bank_name"]


def _finalize_account_records(
    accounts: Dict[str, Dict], balance_col: Optional[str]
) -> List[Dict]:
    """
    最终处理账户记录列表。

    移除内部字段、标记余额数据状态、按交易笔数排序。

    Args:
        accounts: 账户记录字典
        balance_col: 余额列名

    Returns:
        处理后的账户列表
    """
    account_list = []

    for acc in accounts.values():
        # 移除内部字段
        acc.pop("_last_balance_date", None)

        # 标记余额数据状态
        # 注意：不使用净流入估算余额（净流入≠余额）
        if acc["last_balance"] == 0 and not balance_col:
            acc["has_balance_data"] = False
        else:
            acc["has_balance_data"] = True

        account_list.append(acc)

    # 按交易笔数排序（活跃账户优先）
    account_list.sort(key=lambda x: x["transaction_count"], reverse=True)

    return account_list


def _log_account_extraction_summary(account_list: List[Dict]) -> None:
    """
    记录账户提取完成摘要。

    Args:
        account_list: 账户列表
    """
    real_bank_cards = [a for a in account_list if a["is_real_bank_card"]]
    other_accounts = [a for a in account_list if not a["is_real_bank_card"]]
    total_balance = sum(a["last_balance"] for a in account_list)

    logger.info(
        f"银行账户提取完成: 共{len(account_list)}个账户，"
        f"其中真实银行卡{len(real_bank_cards)}张，其他账户{len(other_accounts)}个，"
        f"总余额{total_balance / 10000:.2f}万元"
    )


def extract_bank_accounts(df: pd.DataFrame, entity_name: str = None) -> List[Dict]:
    """
    从清洗后的流水数据中提取唯一银行账户列表。

    【Phase 1.2 - 2026-01-21】【Phase 1.3 - 2026-01-22 增强余额提取】
    此函数用于从交易记录中提取去重后的银行账户信息，
    支持区分真实银行卡和理财/证券账户。

    【余额提取逻辑】
    使用每个账户最后一笔交易的余额作为账户当前余额。
    支持多种余额列名格式：余额、余额(元)、交易余额、账户余额、当前余额、balance等。

    Args:
        df: 清洗后的交易DataFrame (含 account_number, account_type, is_real_bank_card 列)
        entity_name: 实体名称（可选，用于标注账户归属）

    Returns:
        银行账户列表，每个账户包含：
        - account_number: 账号
        - bank_name: 银行名称
        - account_type: 账户类型 (借记卡/信用卡/理财账户/证券账户)
        - account_category: 账户类别 (个人账户/对公账户)
        - is_real_bank_card: 是否为真实银行卡
        - first_transaction_date: 首次交易日期
        - last_transaction_date: 最后交易日期
        - transaction_count: 交易笔数
        - total_income: 总收入
        - total_expense: 总支出
        - last_balance: 最后一笔交易的余额（账户当前余额）
    """
    logger.info("正在提取银行账户列表...")

    if df.empty:
        logger.warning("输入数据为空，无法提取银行账户")
        return []

    # 检测必要列
    account_col = _detect_account_column(df)
    if not account_col:
        logger.warning("未找到账号列，无法提取银行账户")
        return []

    balance_col = _detect_balance_column(df)

    # 按账号分组统计
    accounts = {}

    for idx, row in df.iterrows():
        account_num = str(row.get(account_col, "")).strip()

        # 跳过空账号
        if not account_num or account_num in ["", "nan", "None"]:
            continue

        # 提取交易信息
        info = _extract_transaction_basic_info(row, entity_name)
        balance = _extract_balance_from_row(row, balance_col)

        # 初始化或更新账户记录
        if account_num not in accounts:
            accounts[account_num] = _create_new_account_record(
                account_num, info, balance, info["tx_date"]
            )
        else:
            _update_existing_account_record(
                accounts[account_num], info, balance, info["tx_date"], balance_col
            )

    # 最终处理
    account_list = _finalize_account_records(accounts, balance_col)
    _log_account_extraction_summary(account_list)

    return account_list


def _extract_salary_details_from_df(
    df: pd.DataFrame, entity_name: Optional[str]
) -> List[Dict]:
    """
    从DataFrame中提取工资明细。

    支持两种模式：
    1. DataFrame已有is_salary标记 - 直接提取
    2. DataFrame无标记 - 调用calculate_income_structure进行识别

    Args:
        df: 交易数据DataFrame
        entity_name: 实体名称（用于工资识别）

    Returns:
        工资明细列表
    """
    # 检查是否已有工资标记，没有则调用工资识别
    if "is_salary" not in df.columns:
        logger.info("数据缺少工资标记，正在进行工资识别...")
        income_structure = calculate_income_structure(df, entity_name)
        return income_structure.get("salary_details", [])

    # 已有工资标记，直接提取
    salary_df = df[df.get("is_salary", False) == True].copy()
    salary_details = []
    for _, row in salary_df.iterrows():
        salary_details.append(
            {
                "日期": row.get("date"),
                "金额": row.get("income", 0),
                "对手方": row.get("counterparty", ""),
                "摘要": row.get("description", ""),
                "判定依据": row.get("salary_reason", "已标记为工资"),
            }
        )
    return salary_details


def _parse_transaction_date(date) -> Tuple[Optional[str], Optional[str]]:
    """
    解析交易日期为年份和月份。

    支持datetime对象和字符串日期格式。

    Args:
        date: 日期对象或字符串

    Returns:
        (年份, 月份)元组，解析失败返回(None, None)
    """
    parsed_date = utils.parse_date(date)
    if parsed_date is None:
        return None, None
    return str(parsed_date.year), f"{parsed_date.month:02d}"


def _aggregate_yearly_salary_stats(
    salary_details: List[Dict],
) -> Tuple[Dict, float, set]:
    """
    按年份和月份聚合工资统计。

    Args:
        salary_details: 工资明细列表

    Returns:
        ( yearly_stats, total_salary, all_months )
        - yearly_stats: 按年分组的统计字典
        - total_salary: 总工资
        - all_months: 所有月份集合（用于计算月均）
    """
    yearly_stats = {}
    total_salary = 0.0
    all_months = set()

    for detail in salary_details:
        date = detail.get("日期")
        amount = _safe_amount(detail.get("金额", 0) or 0, "amount")

        if not date or not amount:
            continue

        year, month = _parse_transaction_date(date)
        if not year or not month:
            continue

        # 记录月份用于计算跨月数
        all_months.add(f"{year}-{month}")

        # 初始化年份统计
        if year not in yearly_stats:
            yearly_stats[year] = {"total": 0.0, "transaction_count": 0, "months": {}}

        # 初始化月份统计
        if month not in yearly_stats[year]["months"]:
            yearly_stats[year]["months"][month] = {"total": 0.0, "count": 0}

        # 累加统计
        yearly_stats[year]["total"] += amount
        yearly_stats[year]["transaction_count"] += 1
        yearly_stats[year]["months"][month]["total"] += amount
        yearly_stats[year]["months"][month]["count"] += 1
        total_salary += amount

    # 计算每年的月均工资
    for year in yearly_stats:
        months_with_salary = len(yearly_stats[year]["months"])
        if months_with_salary > 0:
            yearly_stats[year]["monthly_avg"] = (
                yearly_stats[year]["total"] / months_with_salary
            )
        else:
            yearly_stats[year]["monthly_avg"] = 0.0

    return yearly_stats, total_salary, all_months


def _calculate_salary_summary(
    yearly_stats: Dict, total_salary: float, all_months: set
) -> Dict:
    """
    计算工资汇总统计。

    Args:
        yearly_stats: 按年统计字典
        total_salary: 总工资
        all_months: 所有月份集合

    Returns:
        汇总统计字典
    """
    years_count = len(yearly_stats)
    months_count = len(all_months)

    return {
        "total": total_salary,
        "years_count": years_count,
        "avg_yearly": total_salary / years_count if years_count > 0 else 0.0,
        "avg_monthly": total_salary / months_count if months_count > 0 else 0.0,
    }


def _format_salary_details(salary_details: List[Dict]) -> List[Dict]:
    """
    格式化工资详情列表为标准格式。

    Args:
        salary_details: 原始工资明细列表

    Returns:
        格式化后的详情列表
    """
    formatted = []
    for detail in salary_details:
        formatted.append(
            {
                "date": detail.get("日期"),
                "amount": detail.get("金额", 0),
                "counterparty": detail.get("对手方", ""),
                "description": detail.get("摘要", ""),
                "reason": detail.get("判定依据", ""),
            }
        )
    return formatted


def _create_empty_salary_result() -> Dict:
    """
    创建空的工资统计结果。

    Returns:
        空结果字典
    """
    return {
        "summary": {
            "total": 0,
            "years_count": 0,
            "avg_yearly": 0,
            "avg_monthly": 0,
        },
        "yearly": {},
        "details": [],
    }


def _log_salary_summary(
    total_salary: float, years_count: int, months_count: int, summary: Dict
) -> None:
    """
    记录工资统计完成日志。

    Args:
        total_salary: 总工资
        years_count: 跨越年数
        months_count: 跨越月数
        summary: 汇总统计字典
    """
    logger.info(
        f"年度工资统计完成: 总额{utils.format_currency(total_salary)}, "
        f"跨{years_count}年{months_count}个月, 月均{utils.format_currency(summary['avg_monthly'])}"
    )


def calculate_yearly_salary(df: pd.DataFrame, entity_name: str = None) -> Dict:
    """
    按年分组统计工资收入。

    【Phase 2.1 - 2026-01-21】
    此函数用于生成年度工资统计报表，便于生成审计报告的工资表格。
    依赖 calculate_income_structure 函数的工资识别结果。

    Args:
        df: 包含 is_salary 标记的交易DataFrame，
            或原始交易DataFrame（将自动调用工资识别）
        entity_name: 实体名称（用于工资识别）

    Returns:
        年度工资统计字典:
        {
            "summary": {
                "total": 总工资收入,
                "years_count": 跨越年数,
                "avg_yearly": 年均工资,
                "avg_monthly": 月均工资
            },
            "yearly": {
                "2024": {
                    "total": 年度工资总额,
                    "transaction_count": 工资笔数,
                    "monthly_avg": 月均,
                    "months": {
                        "01": {"total": 金额, "count": 笔数},
                        ...
                    }
                },
                ...
            },
            "details": [
                {
                    "date": 日期,
                    "amount": 金额,
                    "counterparty": 对手方,
                    "description": 摘要,
                    "reason": 判定依据
                },
                ...
            ]
        }
    """
    logger.info("正在计算年度工资统计...")

    if df.empty:
        logger.warning("输入数据为空，无法计算年度工资")
        return _create_empty_salary_result()

    # 提取工资明细
    salary_details = _extract_salary_details_from_df(df, entity_name)

    if not salary_details:
        logger.info("未识别到工资收入")
        return _create_empty_salary_result()

    # 按年聚合统计
    yearly_stats, total_salary, all_months = _aggregate_yearly_salary_stats(
        salary_details
    )

    # 计算汇总统计
    summary = _calculate_salary_summary(yearly_stats, total_salary, all_months)

    # 格式化详情列表
    formatted_details = _format_salary_details(salary_details)

    # 记录结果
    _log_salary_summary(total_salary, len(yearly_stats), len(all_months), summary)

    return {"summary": summary, "yearly": yearly_stats, "details": formatted_details}


def analyze_fund_flow(df: pd.DataFrame) -> Dict:
    """
    分析资金去向

    Args:
        df: 交易DataFrame

    Returns:
        资金去向分析字典，包含：
        - 第三方支付收支 (third_party_income/expense)
        - 现金交易收支 (cash_income/expense) - ATM取现、存现、柜台现金等
    """
    logger.info("正在分析资金去向...")

    # 流向第三方支付平台的金额（支出）
    third_party_expense = 0.0
    third_party_expense_transactions = []

    # 来自第三方支付平台的金额（收入）
    third_party_income = 0.0
    third_party_income_transactions = []

    # 【新增】现金交易统计（ATM取现、存现、柜台现金等物理现金）
    cash_expense = 0.0  # 现金支出（取现）
    cash_expense_transactions = []
    cash_income = 0.0  # 现金收入（存现）
    cash_income_transactions = []

    for _, row in df.iterrows():
        description = str(row.get("description", ""))
        counterparty = str(row.get("counterparty", ""))

        # 检查是否为第三方支付
        is_third_party = utils.contains_keywords(
            description, config.THIRD_PARTY_PAYMENT_KEYWORDS
        ) or utils.contains_keywords(counterparty, config.THIRD_PARTY_PAYMENT_KEYWORDS)

        # 【铁律修复】检查是否为现金交易 - 优先使用已计算的 is_cash 列
        if "is_cash" in row.index and row["is_cash"] == True:
            is_cash = True
        elif "现金" in row.index and row["现金"] == "是":
            is_cash = True
        else:
            # 降级：使用关键词匹配
            is_cash = utils.contains_keywords(
                description, config.CASH_KEYWORDS
            ) or utils.contains_keywords(counterparty, config.CASH_KEYWORDS)

        if is_third_party:
            if row["expense"] > 0:
                third_party_expense += row["expense"]
                third_party_expense_transactions.append(
                    {
                        "日期": row["date"],
                        "金额": row["expense"],
                        "摘要": description,
                        "对手方": counterparty,
                        "类型": "支出",
                        # 【审计溯源】原始文件和行号
                        "source_file": row.get("数据来源", row.get("source_file", "")),
                        "source_row_index": row.get("source_row_index", None),
                    }
                )
            if row["income"] > 0:
                third_party_income += row["income"]
                third_party_income_transactions.append(
                    {
                        "日期": row["date"],
                        "金额": row["income"],
                        "摘要": description,
                        "对手方": counterparty,
                        "类型": "收入",
                        # 【审计溯源】原始文件和行号
                        "source_file": row.get("数据来源", row.get("source_file", "")),
                        "source_row_index": row.get("source_row_index", None),
                    }
                )

        # 【新增】现金交易统计
        if is_cash:
            if row["expense"] > 0:
                cash_expense += row["expense"]
                cash_expense_transactions.append(
                    {
                        "日期": row["date"],
                        "金额": row["expense"],
                        "摘要": description,
                        "对手方": counterparty,
                        "类型": "取现",
                        # 【审计溯源】原始文件和行号
                        "source_file": row.get("数据来源", row.get("source_file", "")),
                        "source_row_index": row.get("source_row_index", None),
                    }
                )
            if row["income"] > 0:
                cash_income += row["income"]
                cash_income_transactions.append(
                    {
                        "日期": row["date"],
                        "金额": row["income"],
                        "摘要": description,
                        "对手方": counterparty,
                        "类型": "存现",
                        # 【审计溯源】原始文件和行号
                        "source_file": row.get("数据来源", row.get("source_file", "")),
                        "source_row_index": row.get("source_row_index", None),
                    }
                )

    # 按对手方统计
    counterparty_stats = {}
    for _, row in df.iterrows():
        if row["counterparty"]:
            counterparty = row["counterparty"]
            if counterparty not in counterparty_stats:
                counterparty_stats[counterparty] = {
                    "income": 0.0,
                    "expense": 0.0,
                    "count": 0,
                }
            counterparty_stats[counterparty]["income"] += row["income"]
            counterparty_stats[counterparty]["expense"] += row["expense"]
            counterparty_stats[counterparty]["count"] += 1

    # 排序找出前10大对手方
    top_counterparties = sorted(
        counterparty_stats.items(),
        key=lambda x: x[1]["expense"] + x[1]["income"],
        reverse=True,
    )[:10]

    result = {
        # 第三方支付支出
        "third_party_amount": third_party_expense,  # 保持兼容
        "third_party_expense": third_party_expense,
        "third_party_expense_count": len(third_party_expense_transactions),
        "third_party_expense_transactions": third_party_expense_transactions,
        # 第三方支付收入
        "third_party_income": third_party_income,
        "third_party_income_count": len(third_party_income_transactions),
        "third_party_income_transactions": third_party_income_transactions,
        # 合并明细（收入+支出）
        "third_party_transactions": third_party_expense_transactions
        + third_party_income_transactions,
        "third_party_count": len(third_party_expense_transactions)
        + len(third_party_income_transactions),
        # 占比
        "third_party_ratio": third_party_expense / df["expense"].sum()
        if df["expense"].sum() > 0
        else 0,
        # 【新增】现金交易（ATM取现、存现、柜台现金等物理现金）
        "cash_expense": cash_expense,  # 现金支出（取现）
        "cash_expense_count": len(cash_expense_transactions),
        "cash_expense_transactions": cash_expense_transactions,
        "cash_income": cash_income,  # 现金收入（存现）
        "cash_income_count": len(cash_income_transactions),
        "cash_income_transactions": cash_income_transactions,
        "cash_total": cash_expense + cash_income,  # 现金交易总额
        "cash_transactions": cash_expense_transactions + cash_income_transactions,
        "cash_count": len(cash_expense_transactions) + len(cash_income_transactions),
        # 对手方统计
        "counterparty_stats": counterparty_stats,
        "top_counterparties": top_counterparties,
    }

    logger.info(
        f"第三方支付: 收入{utils.format_currency(third_party_income)}({len(third_party_income_transactions)}笔), "
        f"支出{utils.format_currency(third_party_expense)}({len(third_party_expense_transactions)}笔)"
    )
    logger.info(
        f"现金交易: 存现{utils.format_currency(cash_income)}({len(cash_income_transactions)}笔), "
        f"取现{utils.format_currency(cash_expense)}({len(cash_expense_transactions)}笔)"
    )

    return result


def analyze_wealth_holdings(purchase_txs, redemption_txs, default_type="理财"):
    """
    通过对账逻辑，估算当前持有的理财产品
    核心思想：
    1. 尝试按产品代码/描述精确匹配
    2. 尝试按金额匹配（金额相同或接近）
    3. 剩余未匹配的购买记录及视为当前持有
    """
    import copy

    unmatched_purchases = copy.deepcopy(purchase_txs)
    # 按金额降序排序，先匹配大额
    unmatched_purchases.sort(key=lambda x: x["金额"], reverse=True)

    # 剩余赎回池
    remaining_redemptions = copy.deepcopy(redemption_txs)
    remaining_redemptions.sort(key=lambda x: x["金额"], reverse=True)

    # 策略1: 尝试匹配相同金额 (Tolerance 1%)
    # 有些理财有收益，赎回金额 = 本金 + 收益，所以赎回金额通常 >= 本金
    # 我们假设赎回金额如果在 [本金, 本金*1.1] 范围内，则可能是对应的

    matched_indices = set()
    used_redemption_indices = set()

    for i, buy in enumerate(unmatched_purchases):
        buy_amt = buy["金额"]
        best_match_idx = -1
        min_diff = float("inf")

        for j, sell in enumerate(remaining_redemptions):
            if j in used_redemption_indices:
                continue

            # 时间必须在购买之后
            if sell["日期"] < buy["日期"]:
                continue

            sell_amt = sell["金额"]

            # 判定条件: 赎回金额 >= 本金 (允许亏损极小情况) 且 <= 本金 * 1.5 (假设50%收益率上限)
            # 或者如果是完全精准匹配通过代码，这里暂未实现代码提取后的匹配，主要靠金额
            if buy_amt * 0.95 <= sell_amt <= buy_amt * 1.5:
                # 优先找最接近的
                diff = abs(sell_amt - buy_amt)
                if diff < min_diff:
                    min_diff = diff
                    best_match_idx = j

        if best_match_idx != -1:
            matched_indices.add(i)
            used_redemption_indices.add(best_match_idx)

    # 计算估算持有
    current_holding = 0.0
    holding_details = []

    for i, buy in enumerate(unmatched_purchases):
        if i not in matched_indices:
            # 只有最近3年内的未赎回才计入，太久远的可能漏掉了赎回记录
            # 不过对于长期投资，保留也无妨。这里为避免误差，可以加一个时间限制，比如5年
            current_holding += buy["金额"]
            holding_details.append(buy)

    return current_holding, holding_details


def _get_my_accounts(df: pd.DataFrame) -> tuple:
    """
    获取该人员名下的所有账号集合（用于识别隐形自我转账）

    Args:
        df: 交易DataFrame

    Returns:
        (my_accounts, acct_info) 元组
    """
    import account_analyzer

    my_accounts = set()
    acct_info = {}
    try:
        acct_info = account_analyzer.classify_accounts(df)
        my_accounts.update(acct_info["physical_cards"])
        my_accounts.update(acct_info["virtual_accounts"])
        my_accounts.update(acct_info["wealth_accounts"])
    except Exception as e:
        logger.warning(f"获取账户列表失败: {e}")

    return my_accounts, acct_info


def _identify_self_transfer(row: pd.Series, entity_name: str, my_accounts: set) -> bool:
    """
    深度识别自我转账 (同名 or 账号在名下列表中)

    Args:
        row: 交易行
        entity_name: 实体名称
        my_accounts: 我的账号集合

    Returns:
        是否为自我转账
    """
    import re

    counterparty = str(row.get("counterparty", "")).strip()
    description = str(row.get("description", ""))
    is_self_transfer = False

    # A. 精确同名匹配（完整姓名）
    if entity_name:
        # 完全匹配
        if counterparty == entity_name:
            is_self_transfer = True
        # 边界匹配：entity_name后面不能跟汉字（避免"施灵"匹配"施灵玲"）
        elif entity_name in counterparty:
            pos = counterparty.find(entity_name)
            end_pos = pos + len(entity_name)
            if end_pos < len(counterparty):
                next_char = counterparty[end_pos]
                if not re.match(r"[\u4e00-\u9fa5]", next_char):
                    is_self_transfer = True
            else:
                is_self_transfer = True

    # B. 账号匹配
    if not is_self_transfer and counterparty in my_accounts:
        is_self_transfer = True

    # C. 模糊特征 "本人", "户主"
    if not is_self_transfer and utils.contains_keywords(
        counterparty + description, ["本人", "户主", "卡卡转账", "自行转账"]
    ):
        is_self_transfer = True

    return is_self_transfer


def _detect_wealth_transaction(row: pd.Series, product_code_pattern) -> tuple:
    """
    深度识别理财/基金 (包含隐蔽赎回)

    Args:
        row: 交易行
        product_code_pattern: 理财产品代码正则模式

    Returns:
        (is_wealth, wealth_type, confidence) 元组
    """
    import re

    description = str(row.get("description", ""))
    counterparty = str(row.get("counterparty", "")).strip()
    income = row.get("income", 0) or 0
    expense = row.get("expense", 0) or 0

    is_wealth = False
    wealth_type = "其他理财"
    confidence = "low"

    # A. 关键词匹配
    if utils.contains_keywords(
        description + counterparty, config.WEALTH_MANAGEMENT_KEYWORDS
    ):
        is_wealth = True
        confidence = "high"

    # B. 隐蔽赎回特征
    if not is_wealth and income > 0:
        if counterparty in ["", "-", "nan", "NaN"]:
            if product_code_pattern.search(description) or utils.contains_keywords(
                description, ["到期", "赎回", "结清", "自动", "归还"]
            ):
                is_wealth = True
                confidence = "medium"
                wealth_type = "定期存款" if "定期" in description else "银行理财"

    # 【2026-03-03 修复】C. 纯数字摘要识别（Wave1 新增）银行内部代码
    # 识别摘要为纯数字且在 BANK_INTERNAL_CODES 中的情况
    # 【重要修复】如果对手方是发薪单位（含"内部户"），则不是理财
    if not is_wealth:
        code_candidate = None
        if description:
            ds = str(description).strip()
            if ds.isdigit():
                code_candidate = ds
        if not code_candidate and counterparty:
            cs = str(counterparty).strip()
            if cs.isdigit():
                code_candidate = cs
        
        if code_candidate and code_candidate in config.BANK_INTERNAL_CODES:
            # 【关键修复】检查对手方是否是发薪单位
            counterparty_str = str(counterparty).strip() if counterparty else ""
            # 发薪单位特征：含"代发"、"工资"、"内部户"等
            salary_indicators = ["代发", "工资", "薪", "内部户", "内部账户"]
            is_salary = any(ind in counterparty_str for ind in salary_indicators)
            
            if is_salary:
                # 是工资收入，不是理财，跳过
                pass
            else:
                is_wealth = True
                wealth_type = config.BANK_INTERNAL_CODES[code_candidate]
                confidence = "high"
    # D. 产品编号格式
    if not is_wealth and description:
        if re.match(r"^\d{6,}", description):
            is_wealth = True
            wealth_type = "银行理财"
            confidence = "high"

    # E. 理财产品代码前缀
    if not is_wealth and description:
        if re.match(r"^(WLYEB)\d+", description, re.IGNORECASE):
            is_wealth = True
            wealth_type = "银行理财"
            confidence = "high"

    # F. 整万金额+无对手方
    if not is_wealth and income > 0:
        if income >= 100000 and income % 10000 == 0:
            if counterparty in ["", "-", "nan", "NaN"] or len(counterparty) < 2:
                is_wealth = True
                wealth_type = "银行理财"
                confidence = "medium"

    # 【2026-02-20 修复】G. 金额含利息尾数模式 - 删除此逻辑
    # 问题：这个逻辑太宽松，把所有金额>=10万且有余数且对手方为空的交易都识别为银行理财
    # 例如：15.49万收入（154900元），154900 % 10000 = 4900 > 0，就被识别为理财
    # 这导致大量正常收入被误识别
    #
    # 修复：完全删除此逻辑，只保留前面更严格的识别条件
    #
    # 【P1修复】添加income类型检查
    # if not is_wealth and isinstance(income, (int, float)) and income >= 100000:
    #     if counterparty in ['', '-', 'nan', 'NaN'] or len(counterparty) < 2:
    #         remainder = income % 10000 if isinstance(income, (int, float)) else 0
    #         if remainder > 0:
    #             is_wealth = True
    #             wealth_type = '银行理财'
    #             confidence = 'medium'

    return is_wealth, wealth_type, confidence


def _refine_wealth_type(description: str, counterparty: str, initial_type: str) -> str:
    """
    细化理财类型

    Args:
        description: 交易摘要
        counterparty: 对手方
        initial_type: 初始类型

    Returns:
        细化后的类型
    """
    if utils.contains_keywords(
        description + counterparty, ["基金", "申购", "赎回", "定投"]
    ):
        return "基金"
    elif utils.contains_keywords(
        description + counterparty, ["定期", "定存", "大额存单", "通知存款"]
    ):
        return "定期存款"
    elif utils.contains_keywords(description + counterparty, ["证券", "银证", "股票"]):
        return "证券"
    elif utils.contains_keywords(
        description + counterparty,
        ["理财", "理财产品", "资管", "资产管理", "结构性存款"],
    ):
        return "银行理财"
    return initial_type


def _calculate_real_wealth_profit(
    wealth_purchase: float, wealth_redemption: float, wealth_income: float
) -> float:
    """
    计算真实理财收益（修正异常高收益）

    Args:
        wealth_purchase: 理财购买金额
        wealth_redemption: 理财赎回金额
        wealth_income: 理财收益金额

    Returns:
        修正后的真实收益
    """
    real_wealth_profit = wealth_redemption + wealth_income - wealth_purchase

    # 逻辑修正：如果算出巨额正收益，可能是数据缺失导致的"无本之利"
    if wealth_purchase > 0:
        yield_rate = real_wealth_profit / wealth_purchase
        if yield_rate > 0.5 and real_wealth_profit > 100000:
            logger.warning(
                f"检测到异常的理财高收益(投入{wealth_purchase}, 产出{wealth_redemption + wealth_income})，可能是理财购买记录(如自我转账)未被识别"
            )
            # 悲观修正：只计算显式的利息/收益作为盈利
            real_wealth_profit = wealth_income
    elif wealth_redemption > 100000:
        # 如果根本没有购买记录，却有大额赎回，说明购买记录完全缺失
        real_wealth_profit = wealth_income

    return real_wealth_profit


def _estimate_current_holdings(
    wealth_purchase_transactions: list,
    wealth_redemption_transactions: list,
    category_stats: dict,
) -> tuple:
    """
    估算当前持有的理财产品

    Args:
        wealth_purchase_transactions: 理财购买交易列表
        wealth_redemption_transactions: 理财赎回交易列表
        category_stats: 分类统计

    Returns:
        (total_estimated_holding, detailed_holdings) 元组
    """
    total_estimated_holding = 0.0
    detailed_holdings = {}

    # 将交易按类型分组
    tx_by_type = {}
    for cat in category_stats.keys():
        tx_by_type[cat] = {"buy": [], "sell": []}

    for t in wealth_purchase_transactions:
        cat = t.get("类型", "其他理财") or "其他理财"
        if cat in tx_by_type:
            tx_by_type[cat]["buy"].append(t)

    for t in wealth_redemption_transactions:
        cat = t.get("类型", "其他理财") or "其他理财"
        if cat in tx_by_type:
            tx_by_type[cat]["sell"].append(t)

    for cat, txs in tx_by_type.items():
        holding, details = analyze_wealth_holdings(txs["buy"], txs["sell"], cat)
        total_estimated_holding += holding
        if holding > 0:
            detailed_holdings[cat] = {"amount": holding, "count": len(details)}

    return total_estimated_holding, detailed_holdings


def _empty_wealth_result() -> Dict:
    """返回空的理财分析结果结构"""
    return {
        "wealth_purchase": 0.0,
        "wealth_purchase_count": 0,
        "wealth_purchase_transactions": [],
        "wealth_redemption": 0.0,
        "wealth_redemption_count": 0,
        "wealth_redemption_transactions": [],
        "business_reimbursement_income": 0.0,
        "business_reimbursement_count": 0,
        "business_reimbursement_transactions": [],
        "wealth_income": 0.0,
        "wealth_income_count": 0,
        "wealth_income_transactions": [],
        "net_wealth_flow": 0.0,
        "real_wealth_profit": 0.0,
        "self_transfer_income": 0.0,
        "self_transfer_expense": 0.0,
        "self_transfer_count": 0,
        "self_transfer_transactions": [],
        "loan_inflow": 0.0,
        "refund_inflow": 0.0,
        "category_stats": {
            "银行理财": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
            "基金": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
            "定期存款": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
            "证券": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
            "其他理财": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
            "疑似理财": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
            "银行内部转账-大额存单": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
            "银行内部转账-结构性存款": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
            "银行内部转账-理财产品": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
            "银行内部转账-定期到期": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        },
        "yearly_stats": {},
        "total_transactions": 0,
        "deposit_purchase": 0.0,
        "deposit_redemption": 0.0,
        "estimated_holding": 0.0,
        "holding_structure": {},
    }


def analyze_wealth_management(df: pd.DataFrame, entity_name: str = None) -> Dict:
    """
    分析理财产品交易（增强版 - 深度清洗空转资金）- 【P1-性能7修复】向量化优化版
    【2026-03-08 增强】集成WealthAccountAnalyzer进行账户分类

    【性能优化】将140+行的iterrows主循环改为向量化操作，关键改进：
    1. 贷款/退款识别：使用布尔掩码+str.contains向量化匹配（原逐行keyword匹配）
    2. 理财检测：对剩余行批量应用_detect_wealth_transaction（减少循环次数）
    3. 分类统计：使用groupby聚合替代手动累加
    4. 年度统计：使用groupby按年聚合替代字典逐行更新
    5. 交易记录构建：使用列表推导式+iterrows（针对过滤后的子集，数据量已大幅减少）

    识别银行卡中的理财产品操作，包括：
    - 银行理财产品购买/赎回
    - 基金申购/赎回
    - 证券转账（银证互转）
    - 定期存款/大额存单
    - 自我转账（账户间划转，含隐形关联账户）
    - 贷款发放/还款（不算作收入/支出）
    - 退款/冲正（不算作收入）

    Args:
        df: 交易DataFrame
        entity_name: 实体名称（用于识别自我转账）

    Returns:
        理财交易分析字典
    """
    logger.info("正在分析理财产品交易（增强版 - 向量化优化）...")
    
    # 【2026-03-08 新增】使用WealthAccountAnalyzer进行账户分类
    try:
        from wealth_account_analyzer import WealthAccountAnalyzer
        df = df.copy()

        # 兼容多种账号列名，避免直接使用 df['account'] 触发 KeyError
        account_col = _detect_account_column(df)
        if "account" not in df.columns and account_col:
            df["account"] = df[account_col]
        if "account_number" not in df.columns and "account" in df.columns:
            df["account_number"] = df["account"]
        if "account_id" not in df.columns and "account" in df.columns:
            df["account_id"] = df["account"]

        analyzer = WealthAccountAnalyzer(df, entity_name)
        account_classification = analyzer.classify_accounts()
        fund_flow_result = analyzer.analyze_fund_flow()
        
        # 统计账号分类结果
        wealth_accounts = [acc for acc, info in account_classification.items() 
                          if info['type'] in ('wealth', 'internal')]
        securities_accounts = [acc for acc, info in account_classification.items() 
                              if info['type'] == 'securities']
        
        logger.info(f'[WealthAccountAnalyzer] {entity_name or "对象"}: '
                   f'{len(wealth_accounts)}个理财账户, {len(securities_accounts)}个证券账户')
        
        # 将分类结果添加到df中
        if "account" in df.columns:
            df["_account_type"] = df["account"].map(
                lambda x: account_classification.get(str(x), {}).get("type", "unknown")
            )
        else:
            df["_account_type"] = "unknown"
    except Exception as e:
        logger.warning(f'[WealthAccountAnalyzer] 账户分类失败: {e}')
        df['_account_type'] = 'unknown'
        wealth_accounts = []
        securities_accounts = []

    if df.empty:
        return _empty_wealth_result()

    # 1. 获取该人员名下的所有账号集合
    my_accounts, acct_info = _get_my_accounts(df)

    # 分类统计模板
    category_stats = {
        "银行理财": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        "基金": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        "定期存款": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        "证券": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        "其他理财": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        "疑似理财": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        "银行内部转账-大额存单": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        "银行内部转账-结构性存款": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        "银行内部转账-理财产品": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
        "银行内部转账-定期到期": {"购入": 0.0, "赎回": 0.0, "笔数": 0},
    }

    import re

    product_code_pattern = re.compile(r"[A-Za-z0-9]{8,}")

    # ========== 【优化1】向量化预处理 ==========
    # 标准化列名和类型，避免在循环中重复转换
    df_work = df.copy()
    df_work["description"] = df_work.get("description", "").astype(str)
    df_work["counterparty"] = df_work.get("counterparty", "").astype(str).str.strip()
    df_work["income"] = pd.to_numeric(df_work.get("income", 0), errors="coerce").fillna(
        0
    )
    df_work["expense"] = pd.to_numeric(
        df_work.get("expense", 0), errors="coerce"
    ).fillna(0)
    df_work["year"] = (
        pd.to_datetime(df_work["date"], errors="coerce").dt.year.fillna(0).astype(int)
    )

    # ========== 【优化2】向量化识别贷款和退款 ==========
    # 使用布尔掩码+正则表达式向量化匹配，替代逐行utils.contains_keywords
    income_mask = df_work["income"] > 0

    # 贷款发放识别（向量化）- 使用str.contains替代逐行匹配
    loan_keywords = ["放款", "贷款发放", "个贷发放"]
    loan_pattern = "|".join(loan_keywords)
    loan_mask = income_mask & df_work["description"].str.contains(
        loan_pattern, na=False, regex=True
    )
    loan_df = df_work[loan_mask].copy()
    # 【P1修复】中英文列名去重，避免重复统计
    if "income" in loan_df.columns and "收入" in loan_df.columns:
        loan_inflow = loan_df["income"].sum()
    else:
        income_col = "income" if "income" in loan_df.columns else "收入"
        loan_inflow = loan_df[income_col].sum() if income_col in loan_df.columns else 0
    loan_transactions = loan_df.to_dict("records")

    # 退款识别（向量化）
    refund_keywords = ["退款", "冲正", "退回", "撤销"]
    refund_pattern = "|".join(refund_keywords)
    refund_mask = income_mask & df_work["description"].str.contains(
        refund_pattern, na=False, regex=True
    )
    refund_df = df_work[refund_mask].copy()
    refund_inflow = refund_df["income"].sum()
    refund_transactions = refund_df.to_dict("records")

    # 排除已识别的贷款和退款，减少后续处理数据量
    processed_mask = loan_mask | refund_mask
    df_remaining = df_work[~processed_mask].copy()

    # ========== 【优化3】批量识别自我转账 ==========
    # 对剩余行批量应用自我转账检测（无法完全向量化，但只处理子集）
    if not df_remaining.empty:
        self_transfer_mask = df_remaining.apply(
            lambda row: _identify_self_transfer(row, entity_name, my_accounts), axis=1
        )
        self_transfer_df = df_remaining[self_transfer_mask].copy()
        df_remaining = df_remaining[~self_transfer_mask].copy()
    else:
        self_transfer_df = df_remaining.iloc[0:0].copy()

    # 向量化统计自我转账
    self_transfer_out_df = self_transfer_df[self_transfer_df["expense"] > 0]
    self_transfer_in_df = self_transfer_df[self_transfer_df["income"] > 0]

    self_transfer_expense = self_transfer_out_df["expense"].sum()
    self_transfer_income = self_transfer_in_df["income"].sum()

    # 使用列表推导式构建自我转账交易记录（比逐行append快）
    self_transfer_transactions = []
    if not self_transfer_out_df.empty:
        self_transfer_transactions.extend(
            [
                {
                    "日期": row["date"],
                    "收入": 0,
                    "支出": row["expense"],
                    "摘要": row["description"],
                    "对手方": row["counterparty"],
                    "备注": "识别为自我转账-转出",
                }
                for _, row in self_transfer_out_df.iterrows()
            ]
        )
    if not self_transfer_in_df.empty:
        self_transfer_transactions.extend(
            [
                {
                    "日期": row["date"],
                    "收入": row["income"],
                    "支出": 0,
                    "摘要": row["description"],
                    "对手方": row["counterparty"],
                    "备注": "识别为自我转账-转入（无对应转出记录）",
                }
                for _, row in self_transfer_in_df.iterrows()
            ]
        )

    # ========== 【优化4】批量识别理财交易 ==========
    # 对剩余行批量应用理财检测（减少循环次数）
    if not df_remaining.empty:
        wealth_info = df_remaining.apply(
            lambda row: _detect_wealth_transaction(row, product_code_pattern),
            axis=1,
            result_type="expand",
        )
        wealth_info.columns = ["is_wealth", "wealth_type", "confidence"]

        # 合并结果
        df_remaining = df_remaining.reset_index(drop=True)
        df_remaining["is_wealth"] = wealth_info["is_wealth"].values
        df_remaining["wealth_type"] = wealth_info["wealth_type"].values
        df_remaining["confidence"] = wealth_info["confidence"].values

        # 账号属性特征（隐形理财户）- 向量化处理
        wealth_accounts = set(acct_info.get("wealth_accounts", []))
        if wealth_accounts:
            account_col = (
                "本方账号" if "本方账号" in df_remaining.columns else "account_number"
            )
            if account_col in df_remaining.columns:
                hidden_wealth_mask = (
                    ~df_remaining["is_wealth"]
                    & (df_remaining["income"] > 0)
                    & df_remaining["counterparty"].isin(["", "-", "nan", "NaN"])
                    & df_remaining[account_col].astype(str).isin(wealth_accounts)
                )
                df_remaining.loc[hidden_wealth_mask, "is_wealth"] = True
                df_remaining.loc[hidden_wealth_mask, "wealth_type"] = "银行理财"
                df_remaining.loc[hidden_wealth_mask, "confidence"] = "high"

        # 筛选理财交易
        df_wealth = df_remaining[df_remaining["is_wealth"]].copy()
    else:
        df_wealth = df_remaining.iloc[0:0].copy()

    # ========== 【优化5】向量化细化类型和分类统计 ==========
    if not df_wealth.empty:
        # 细化类型（仍需要逐行，但数据量已大幅减少）
        df_wealth["wealth_type"] = df_wealth.apply(
            lambda row: _refine_wealth_type(
                row["description"], row["counterparty"], row["wealth_type"]
            ),
            axis=1,
        )

        # 识别收益类型（向量化）
        yield_keywords = ["利息", "结息", "分红", "收益", "红利"]
        yield_pattern = "|".join(yield_keywords)
        df_wealth["is_yield"] = df_wealth["description"].str.contains(
            yield_pattern, na=False, regex=False
        )

        # 分类：购买 vs 赎回/收益
        df_purchase = df_wealth[df_wealth["expense"] > 0].copy()
        df_income = df_wealth[df_wealth["income"] > 0].copy()
        df_yield = df_income[df_income["is_yield"]].copy()
        df_redeem = df_income[~df_income["is_yield"]].copy()

        # 从“理财赎回”中剥离单位报销/业务往来款，避免误计入本金回流
        if not df_redeem.empty:
            df_redeem = _identify_business_reimbursement_income(df_redeem)
            reimbursement_mask = df_redeem["is_business_reimbursement"].fillna(False)
            df_business_reimbursement = df_redeem[reimbursement_mask].copy()
            df_redeem = df_redeem[~reimbursement_mask].copy()
        else:
            df_business_reimbursement = pd.DataFrame()

        # 向量化统计（使用sum聚合）
        wealth_purchase = df_purchase["expense"].sum()
        wealth_redemption = df_redeem["income"].sum()
        wealth_income = df_yield["income"].sum()
        business_reimbursement_income = df_business_reimbursement["income"].sum()

        # 使用列表推导式构建交易记录
        wealth_purchase_transactions = (
            [
                {
                    "日期": row["date"],
                    "金额": row["expense"],
                    "摘要": row["description"],
                    "对手方": row["counterparty"],
                    "类型": row["wealth_type"],
                    "判断依据": f"支出+{row['wealth_type']}",
                }
                for _, row in df_purchase.iterrows()
            ]
            if not df_purchase.empty
            else []
        )

        wealth_income_transactions = (
            [
                {
                    "日期": row["date"],
                    "金额": row["income"],
                    "摘要": row["description"],
                    "对手方": row["counterparty"],
                    "类型": "收益",
                }
                for _, row in df_yield.iterrows()
            ]
            if not df_yield.empty
            else []
        )

        wealth_redemption_transactions = (
            [
                {
                    "日期": row["date"],
                    "金额": row["income"],
                    "摘要": row["description"],
                    "对手方": row["counterparty"],
                    "类型": row["wealth_type"],
                    "判断依据": f"收入+{row['wealth_type']}"
                    if row["confidence"] == "high"
                    else "隐蔽赎回特征",
                }
                for _, row in df_redeem.iterrows()
            ]
            if not df_redeem.empty
            else []
        )

        business_reimbursement_transactions = (
            [
                {
                    "日期": row["date"],
                    "金额": row["income"],
                    "摘要": row["description"],
                    "对手方": row["counterparty"],
                    "类型": "单位报销/业务往来款",
                    "判断依据": row.get(
                        "business_reimbursement_reason", "单位报销/业务往来款"
                    ),
                }
                for _, row in df_business_reimbursement.iterrows()
            ]
            if not df_business_reimbursement.empty
            else []
        )

        # 【优化6】使用groupby按类型聚合统计（替代逐行累加）
        if not df_purchase.empty:
            purchase_stats = df_purchase.groupby("wealth_type").agg(
                {"expense": ["sum", "count"]}
            )
            purchase_stats.columns = ["amount", "count"]
            for wtype, row in purchase_stats.iterrows():
                if wtype in category_stats:
                    category_stats[wtype]["购入"] += row["amount"]
                    category_stats[wtype]["笔数"] += int(row["count"])

        if not df_redeem.empty:
            redeem_stats = df_redeem.groupby("wealth_type").agg(
                {"income": ["sum", "count"]}
            )
            redeem_stats.columns = ["amount", "count"]
            for wtype, row in redeem_stats.iterrows():
                if wtype in category_stats:
                    category_stats[wtype]["赎回"] += row["amount"]
                    category_stats[wtype]["笔数"] += int(row["count"])
    else:
        wealth_purchase = 0.0
        wealth_redemption = 0.0
        wealth_income = 0.0
        business_reimbursement_income = 0.0
        wealth_purchase_transactions = []
        wealth_income_transactions = []
        wealth_redemption_transactions = []
        business_reimbursement_transactions = []

    # ========== 【优化7】年度统计使用groupby聚合 ==========
    yearly_stats = {}

    # 合并所有相关DataFrame进行年度统计
    stats_dfs = [
        (self_transfer_out_df, "expense", "自我转出"),
        (self_transfer_in_df, "income", "自我转入"),
        (df_purchase if not df_wealth.empty else pd.DataFrame(), "expense", "购入"),
        (df_redeem if not df_wealth.empty else pd.DataFrame(), "income", "赎回"),
        (df_yield if not df_wealth.empty else pd.DataFrame(), "income", "收益"),
    ]

    for df_stat, col, stat_name in stats_dfs:
        if not df_stat.empty:
            for year, group in df_stat.groupby("year"):
                if year not in yearly_stats:
                    yearly_stats[year] = {
                        "购入": 0.0,
                        "赎回": 0.0,
                        "收益": 0.0,
                        "自我转入": 0.0,
                        "自我转出": 0.0,
                    }
                yearly_stats[year][stat_name] += group[col].sum()

    # 计算理财净额和真实收益
    net_wealth_flow = wealth_purchase - wealth_redemption
    real_wealth_profit = _calculate_real_wealth_profit(
        wealth_purchase, wealth_redemption, wealth_income
    )

    # 【2026-02-12 修复】单独统计定期存款，用于后续剔除定存到期
    deposit_purchase = category_stats["定期存款"]["购入"]
    deposit_redemption = category_stats["定期存款"]["赎回"]

    result = {
        "wealth_purchase": wealth_purchase,
        "wealth_purchase_count": len(wealth_purchase_transactions),
        "wealth_purchase_transactions": wealth_purchase_transactions,
        "wealth_redemption": wealth_redemption,
        "wealth_redemption_count": len(wealth_redemption_transactions),
        "wealth_redemption_transactions": wealth_redemption_transactions,
        "business_reimbursement_income": business_reimbursement_income,
        "business_reimbursement_count": len(business_reimbursement_transactions),
        "business_reimbursement_transactions": business_reimbursement_transactions,
        "wealth_income": wealth_income,
        "wealth_income_count": len(wealth_income_transactions),
        "wealth_income_transactions": wealth_income_transactions,
        "net_wealth_flow": net_wealth_flow,
        "real_wealth_profit": real_wealth_profit,
        "self_transfer_income": self_transfer_income,
        "self_transfer_expense": self_transfer_expense,
        "self_transfer_count": len(self_transfer_transactions),
        "self_transfer_transactions": self_transfer_transactions,
        "loan_inflow": loan_inflow,
        "loan_transactions": loan_transactions,
        "refund_inflow": refund_inflow,
        "refund_transactions": refund_transactions,
        "category_stats": category_stats,
        "yearly_stats": yearly_stats,
        "total_transactions": len(wealth_purchase_transactions)
        + len(wealth_redemption_transactions)
        + len(wealth_income_transactions),
        # 【新增】定期存款单独统计
        "deposit_purchase": deposit_purchase,
        "deposit_redemption": deposit_redemption,
    }

    if result["total_transactions"] > 0:
        logger.info(
            f"理财产品: 购买{utils.format_currency(wealth_purchase)}, 赎回{utils.format_currency(wealth_redemption)}"
        )
        if business_reimbursement_income > 0:
            logger.info(
                f"单位报销/业务往来款: {utils.format_currency(business_reimbursement_income)}"
            )
        logger.info(
            f"隐性剔除: 自我转账{utils.format_currency(self_transfer_income)}, 贷款{utils.format_currency(loan_inflow)}, 退款{utils.format_currency(refund_inflow)}"
        )

    # 估算当前持有
    total_estimated_holding, detailed_holdings = _estimate_current_holdings(
        wealth_purchase_transactions, wealth_redemption_transactions, category_stats
    )

    result["estimated_holding"] = total_estimated_holding
    result["holding_structure"] = detailed_holdings

    logger.info(
        f"理财深度估算: 累计交易{utils.format_currency(wealth_purchase)}, 估算当前持有{utils.format_currency(total_estimated_holding)}"
    )
    return result


def _calculate_real_income_expense(
    income_structure: Dict,
    wealth_management: Dict,
    fund_flow: Dict,
    df: pd.DataFrame = None,
    family_members: List[str] = None,
    entity_name: str = None
) -> tuple:
    """
    计算真实收入/支出（改进版 - 2026-03-02 增加家庭转账剔除）

    【关键修复】
    1. 定期存款到期是本金返还，不是收入，需要完全剔除
    2. 理财赎回超出购买的部分（历史存量）也应剔除
    3. 这些"其他收入"实际上是早年工资的积蓄回流
    4. 【2026-03-02 新增】家庭成员间转账需要剔除

    核心原则：
    1. 自我转账理论上应该收支平衡（没数据完整时可能有差额）
    2. 理财/定存的本金回流不是收入，只有收益才是收入
    3. 为保守起见，我们剔除所有本金回流，只保留收益
    4. 家庭成员间转账是内部资金流动，不影响家庭总财富

    Args:
        income_structure: 收支结构
        wealth_management: 理财管理分析结果
        fund_flow: 资金流向分析结果
        df: 交易DataFrame（用于计算家庭转账）
        family_members: 家庭成员列表（不包含本人）
        entity_name: 当前实体名称

    Returns:
        (real_income, real_expense, detail_dict) 元组，detail_dict包含剔除详情
    """

    # 【2026-02-20 修复】增加字段容错处理，避免 KeyError
    # 【P1修复】确保所有amount类型正确
    def _safe_num(val):
        return _safe_amount(val, "amount")

    self_in = _safe_num(wealth_management.get("self_transfer_income", 0))
    self_out = _safe_num(wealth_management.get("self_transfer_expense", 0))
    wealth_buy = _safe_num(wealth_management.get("wealth_purchase", 0))
    wealth_redeem = _safe_num(wealth_management.get("wealth_redemption", 0))
    wealth_yield = _safe_num(wealth_management.get("wealth_income", 0))
    business_reimbursement_in = _safe_num(
        wealth_management.get("business_reimbursement_income", 0)
    )
    loan_in = _safe_num(wealth_management.get("loan_inflow", 0))
    refund_in = _safe_num(wealth_management.get("refund_inflow", 0))

    # 【2026-02-12 修复】获取定期存款数据
    deposit_buy = wealth_management.get("deposit_purchase", 0)
    deposit_redeem = wealth_management.get("deposit_redemption", 0)

    # 已识别为本人互转的收支不属于真实收入/真实支出，均应剔除
    self_transfer_income_offset = self_in
    self_transfer_expense_offset = self_out

    # 定期存款单独处理，避免与综合理财本金对冲重复计算
    non_deposit_wealth_buy = max(0.0, wealth_buy - deposit_buy)
    non_deposit_wealth_redeem = max(0.0, wealth_redeem - deposit_redeem)

    # 非定存理财本金对冲：买入和赎回中较小的部分是完整闭环
    wealth_principal_offset = min(non_deposit_wealth_buy, non_deposit_wealth_redeem)

    # 历史存量赎回（仅针对非定存理财）
    wealth_historical_redeem = max(
        0.0, non_deposit_wealth_redeem - non_deposit_wealth_buy
    )

    # 【2026-02-12 关键修复】定期存款到期完全剔除（本金不是收入）

    # 【2026-03-02 新增】计算家庭转账（如果有家庭成员信息）
    family_transfer_in = 0.0  # 家庭成员转入
    family_transfer_out = 0.0  # 转给家庭成员
    family_transfer_in_count = 0
    family_transfer_out_count = 0
    family_member_aliases = _build_name_alias_set(family_members or [])
    
    if df is not None and family_members and len(family_members) > 0 and entity_name:
        try:
            # 获取交易对手列（支持多种列名）
            counterparty_col = None
            for col in ['counterparty', '交易对手', '对手方', '对方户名']:
                if col in df.columns:
                    counterparty_col = col
                    break
            
            if counterparty_col and family_member_aliases:
                family_match_mask = df[counterparty_col].apply(
                    lambda value: _matches_alias_set(value, family_member_aliases)
                )
                # 计算家庭成员转入（收入）
                family_in_mask = family_match_mask & (
                    df["income"] > 0 if "income" in df.columns else False
                )
                if family_in_mask.any():
                    family_transfer_in = df.loc[family_in_mask, "income"].sum()
                    family_transfer_in_count = int(family_in_mask.sum())
                
                # 计算转给家庭成员（支出）
                family_out_mask = family_match_mask & (
                    df["expense"] > 0 if "expense" in df.columns else False
                )
                if family_out_mask.any():
                    family_transfer_out = df.loc[family_out_mask, "expense"].sum()
                    family_transfer_out_count = int(family_out_mask.sum())
                    
                logger.info(f"  - 家庭转入: {family_transfer_in / 10000:.2f}万 (需从收入剔除)")
                logger.info(f"  - 家庭转出: {family_transfer_out / 10000:.2f}万 (需从支出剔除)")
        except Exception as e:
            logger.warning(f"计算家庭转账失败: {e}")
    
    # 定存到期是本金返还，不应算作收入
    deposit_offset = deposit_redeem  # 完全剔除定存到期本金

    # 【2026-02-20 修复】增加 income_structure 字段容错处理
    total_income = income_structure.get("total_income", 0) if income_structure else 0
    total_expense = income_structure.get("total_expense", 0) if income_structure else 0

    # 计算真实收入
    # 【2026-02-23 修复】恢复剔除 wealth_historical_redeem
    # 【2026-03-02 新增】剔除家庭转入
    real_income = (
        total_income
        - self_transfer_income_offset  # 本人互转转入
        - wealth_principal_offset  # 理财本金对冲（当期闭环）
        - wealth_historical_redeem  # 【恢复】理财历史存量赎回
        - deposit_offset  # 定存到期本金
        - business_reimbursement_in  # 单位报销/业务往来款（非个人真实收入）
        - loan_in  # 贷款发放
        - refund_in  # 退款
        - family_transfer_in  # 【新增】家庭成员转入
    )

    # 计算真实支出
    # 支出端也需要相应调整
    # 【2026-03-02 新增】剔除家庭转出
    real_expense = (
        total_expense
        - self_transfer_expense_offset  # 本人互转转出
        - wealth_principal_offset  # 理财购买对冲
        - deposit_buy  # 定存购买（投资支出）
        - family_transfer_out  # 【新增】转给家庭成员
    )

    # 安全检查
    real_income = max(0, real_income)
    real_expense = max(0, real_expense)

    # 构建剔除详情（用于报告展示）
    offset_detail = {
        "self_transfer": self_transfer_income_offset,
        "self_transfer_expense": self_transfer_expense_offset,
        "wealth_principal": wealth_principal_offset,
        "wealth_historical": wealth_historical_redeem,  # 【恢复】
        "deposit_redemption": deposit_offset,
        "business_reimbursement": business_reimbursement_in,
        "loan": loan_in,
        "refund": refund_in,
        "family_transfer_in": family_transfer_in,  # 【2026-03-02 新增】家庭转入
        "family_transfer_out": family_transfer_out,  # 【2026-03-02 新增】家庭转出
        "family_transfer_in_count": family_transfer_in_count,
        "family_transfer_out_count": family_transfer_out_count,
        "total_offset": (
            self_transfer_income_offset
            + wealth_principal_offset
            + wealth_historical_redeem
            + deposit_offset
            + business_reimbursement_in
            + loan_in
            + refund_in
            + family_transfer_in  # 【新增】
        ),
        "offset_meta": {
            "self_transfer": {
                "bucket": "self_transfer",
                "label": "本人账户互转",
                "income_amount": self_transfer_income_offset,
                "expense_amount": self_transfer_expense_offset,
                "confidence": "high",
            },
            "wealth_principal": {
                "bucket": "wealth_principal",
                "label": "理财/定存本金回流",
                "income_amount": wealth_principal_offset + deposit_offset + wealth_historical_redeem,
                "expense_amount": wealth_principal_offset + deposit_buy,
                "confidence": "medium",
            },
            "business_reimbursement": {
                "bucket": "business_reimbursement",
                "label": "单位报销/业务往来款",
                "income_amount": business_reimbursement_in,
                "expense_amount": 0.0,
                "confidence": "high",
            },
            "loan": {
                "bucket": "loan",
                "label": "贷款发放",
                "income_amount": loan_in,
                "expense_amount": 0.0,
                "confidence": "high",
            },
            "refund": {
                "bucket": "refund",
                "label": "退款/冲正",
                "income_amount": refund_in,
                "expense_amount": 0.0,
                "confidence": "high",
            },
            "family_transfer": {
                "bucket": "family_transfer",
                "label": "家庭成员互转",
                "income_amount": family_transfer_in,
                "expense_amount": family_transfer_out,
                "income_count": family_transfer_in_count,
                "expense_count": family_transfer_out_count,
                "confidence": "medium",
                "matching_mode": "alias_match" if family_member_aliases else "disabled",
            },
        },
    }

    # 日志输出
    logger.info(f"【2026-03-02修复】资金对冲详情（含家庭转账剔除）:")
    logger.info(
        f"  - 自我转账转入: {self_transfer_income_offset / 10000:.2f}万, "
        f"转出: {self_transfer_expense_offset / 10000:.2f}万"
    )
    logger.info(f"  - 理财本金: {wealth_principal_offset / 10000:.2f}万")
    logger.info(f"  - 定存到期: {deposit_offset / 10000:.2f}万")
    if business_reimbursement_in > 0:
        logger.info(
            f"  - 单位报销/业务往来款: {business_reimbursement_in / 10000:.2f}万"
        )
    if family_transfer_in > 0 or family_transfer_out > 0:
        logger.info(f"  - 家庭转入: {family_transfer_in / 10000:.2f}万 (已从收入剔除)")
        logger.info(f"  - 家庭转出: {family_transfer_out / 10000:.2f}万 (已从支出剔除)")
    logger.info(
        f"真实收入: {real_income / 10000:.2f}万, 真实支出: {real_expense / 10000:.2f}万"
    )

    return real_income, real_expense, offset_detail


def _attach_salary_reference_to_income_classification(
    income_classification: Dict,
    yearly_salary: Dict = None,
) -> Dict:
    """给收入分类结果补充严格工资口径参考值，避免报告层混用两套工资口径。"""
    if not isinstance(income_classification, dict):
        return income_classification

    salary_summary = yearly_salary.get("summary", {}) if isinstance(yearly_salary, dict) else {}
    try:
        official_salary_total = float(salary_summary.get("total", 0) or 0)
    except (TypeError, ValueError):
        official_salary_total = 0.0

    reason_breakdown = income_classification.get("reason_breakdown", {})
    if not isinstance(reason_breakdown, dict):
        reason_breakdown = {}
    legitimate_map = reason_breakdown.get("legitimate", {})
    if not isinstance(legitimate_map, dict):
        legitimate_map = {}

    salary_like_prefixes = (
        "工资性收入",
        "已知发薪单位",
        "用户定义发薪单位",
        "人力资源公司",
    )
    salary_like_reasons = {}
    salary_like_total = 0.0
    for reason, amount in legitimate_map.items():
        reason_text = str(reason or "").strip()
        if not reason_text:
            continue
        if any(reason_text.startswith(prefix) for prefix in salary_like_prefixes):
            try:
                current_amount = float(amount or 0)
            except (TypeError, ValueError):
                current_amount = 0.0
            salary_like_reasons[reason_text] = current_amount
            salary_like_total += current_amount

    income_classification["salary_reference_income"] = float(official_salary_total)
    income_classification["salary_classified_income"] = float(salary_like_total)
    income_classification["salary_reference_delta"] = float(
        official_salary_total - salary_like_total
    )
    income_classification["salary_reference_basis"] = "yearly_salary_summary_total"
    income_classification["salary_like_reasons"] = salary_like_reasons

    return income_classification


def recalculate_income_metrics(
    df: pd.DataFrame,
    entity_name: str,
    income_structure: Dict,
    wealth_management: Dict,
    fund_flow: Dict,
    yearly_salary: Dict = None,
    family_members: List[str] = None,
) -> Dict:
    """统一重算真实收入/支出与真实收入分类。"""
    real_income, real_expense, offset_detail = _calculate_real_income_expense(
        income_structure,
        wealth_management,
        fund_flow,
        df,
        family_members,
        entity_name,
    )

    income_df = df[df["income"] > 0].copy()
    income_classification = classify_income_sources(
        income_df,
        entity_name=entity_name,
        wealth_result=wealth_management,
        family_members=family_members,
    )
    income_classification = _attach_salary_reference_to_income_classification(
        income_classification,
        yearly_salary,
    )

    # 统一口径：真实收入剔除桶与分类剔除明细保持一致，避免同一笔交易在两条链路中各说各话。
    offset_bucket_map = {
        "self_transfer": "self_transfer",
        "wealth_redemption": ("wealth_principal", "wealth_historical", "deposit_redemption"),
        "business_reimbursement": "business_reimbursement",
        "loan": "loan",
        "refund": "refund",
        "family_transfer": "family_transfer_in",
    }
    excluded_breakdown = income_classification.get("excluded_breakdown", {}) or {}

    for bucket, target_keys in offset_bucket_map.items():
        classified_amount = float(excluded_breakdown.get(bucket, 0) or 0)
        if not classified_amount:
            continue
        if isinstance(target_keys, tuple):
            current_amount = sum(float(offset_detail.get(key, 0) or 0) for key in target_keys)
        else:
            current_amount = float(offset_detail.get(target_keys, 0) or 0)
        if classified_amount <= current_amount:
            continue

        adjustment = classified_amount - current_amount
        real_income = max(0.0, real_income - adjustment)
        if isinstance(target_keys, tuple):
            primary_key = target_keys[0]
            offset_detail[primary_key] = float(offset_detail.get(primary_key, 0) or 0) + adjustment
        else:
            offset_detail[target_keys] = classified_amount
        offset_detail["total_offset"] = float(
            (offset_detail.get("total_offset", 0) or 0) + adjustment
        )
        offset_meta = offset_detail.get("offset_meta", {})
        if bucket in offset_meta:
            offset_meta[bucket]["income_amount"] = classified_amount
            offset_meta[bucket]["aligned_with_classification"] = True
        logger.info(
            "真实收入口径对齐: %s 补充剔除 %s %.2f 元",
            entity_name,
            bucket,
            adjustment,
        )

    return {
        "real_income": real_income,
        "real_expense": real_expense,
        "offset_detail": offset_detail,
        "income_classification": income_classification,
    }


def _build_profile_summary(
    income_structure: Dict,
    fund_flow: Dict,
    wealth_management: Dict,
    large_cash: list,
    real_income: float,
    real_expense: float,
    df: pd.DataFrame,
) -> Dict:
    """
    构建画像摘要

    Args:
        income_structure: 收支结构
        fund_flow: 资金流向分析结果
        wealth_management: 理财管理分析结果
        large_cash: 大额现金记录
        real_income: 真实收入
        real_expense: 真实支出
        df: 交易DataFrame

    Returns:
        画像摘要字典
    """
    return {
        "total_income": income_structure["total_income"],
        "total_expense": income_structure["total_expense"],
        "net_flow": income_structure["net_flow"],
        "real_income": real_income,
        "real_expense": real_expense,
        "salary_ratio": income_structure["salary_income"] / real_income
        if real_income > 0
        else 0,  # 【2026-02-23修复】工资/真实收入
        "third_party_ratio": fund_flow["third_party_ratio"],
        "large_cash_count": len(large_cash),
        "wealth_transactions": wealth_management["total_transactions"],
        "transaction_count": len(df),
        "date_range": income_structure["date_range"],
    }


def generate_profile_report(df: pd.DataFrame, entity_name: str, family_members: list = None) -> Dict:
    """
    生成资金画像报告

    Args:
        df: 交易DataFrame
        entity_name: 实体名称(人员或公司)

    Returns:
        完整的资金画像报告
    """
    logger.info(f"正在为 {entity_name} 生成资金画像...")

    # 【关键修复】列名映射：支持中英文列名
    # data_cleaner输出中文列名，但本模块期望英文列名
    COLUMN_MAPPING = {
        "交易时间": "date",
        "收入(元)": "income",
        "支出(元)": "expense",
        "交易对手": "counterparty",
        "交易摘要": "description",
        "本方账号": "account_number",
        "余额(元)": "balance",
        "所属银行": "bank_source",
        "数据来源": "source_file",
    }

    # 创建DataFrame副本，避免修改原始数据
    df = df.copy()

    # 执行列名映射
    for chinese_col, english_col in COLUMN_MAPPING.items():
        if chinese_col in df.columns and english_col not in df.columns:
            df.rename(columns={chinese_col: english_col}, inplace=True)
            logger.debug(f"列名映射: {chinese_col} -> {english_col}")

    df = standardize_columns(df)

    # 确保关键列存在
    required_cols = ["date", "income", "expense"]
    for col in required_cols:
        if col not in df.columns:
            logger.error(f"缺少关键列: {col}。可用列: {list(df.columns)}")
            return {
                "entity_name": entity_name,
                "has_data": False,
                "error": f"缺少关键列: {col}",
            }

    # 转换日期列
    if "date" in df.columns:
        df["date"] = _normalize_datetime_series(df["date"])
        invalid_dates = int(df["date"].isna().sum())
        if invalid_dates > 0:
            logger.warning(f"发现 {invalid_dates} 条无法解析的日期，已置为 NaT")

    # 转换金额列为数值类型
    for col in ["income", "expense", "amount"]:
        if col in df.columns:
            df[col] = _normalize_amount_series(df[col], col)
    if "balance" in df.columns:
        df["balance"] = _normalize_amount_series(df["balance"], "balance")

    for text_col in ["counterparty", "description"]:
        if text_col in df.columns:
            df[text_col] = df[text_col].fillna("")

    logger.info(f"数据准备完成: {len(df)} 行, 列: {list(df.columns)}")

    if df.empty:
        logger.warning(f"{entity_name} 无交易数据")
        return {"entity_name": entity_name, "has_data": False}

    # 收支结构
    income_structure = calculate_income_structure(df, entity_name=entity_name)

    # 资金去向
    fund_flow = analyze_fund_flow(df)

    # 理财产品分析（传入entity_name以识别自我转账）
    wealth_management = analyze_wealth_management(df, entity_name=entity_name)

    # 大额现金
    large_cash = extract_large_cash(df)

    # 交易分类
    categories = categorize_transactions(df)

    # 【Phase 2 新增】年度工资统计
    yearly_salary = calculate_yearly_salary(df, entity_name=entity_name)

    metrics = recalculate_income_metrics(
        df,
        entity_name,
        income_structure,
        wealth_management,
        fund_flow,
        yearly_salary=yearly_salary,
        family_members=family_members,
    )
    income_classification = metrics["income_classification"]
    real_income = metrics["real_income"]
    real_expense = metrics["real_expense"]
    offset_detail = metrics["offset_detail"]

    # 构建画像摘要
    summary = _build_profile_summary(
        income_structure,
        fund_flow,
        wealth_management,
        large_cash,
        real_income,
        real_expense,
        df,
    )

    # 【2026-02-12新增】将剔除详情加入summary，供报告使用
    summary["offset_detail"] = offset_detail

    # 计算银行账户列表（用于 bank_accounts 字段）
    bank_accounts = []
    try:
        if hasattr(df, "columns") and "所属银行" in df.columns:
            bank_accounts = df["所属银行"].astype(str).dropna().unique().tolist()
        elif hasattr(df, "columns") and "银行" in df.columns:
            bank_accounts = df["银行"].astype(str).dropna().unique().tolist()
    except Exception:
        bank_accounts = []

    profile = {
        "entity_name": entity_name,
        "has_data": True,
        "income_structure": income_structure,
        "fund_flow": fund_flow,
        "wealth_management": wealth_management,
        "large_cash": large_cash,
        "categories": categories,
        "yearly_salary": yearly_salary,  # Phase 2 新增字段
        "income_classification": income_classification,  # Phase 4 新增字段
        "summary": summary,
        "bank_accounts": bank_accounts,
    }

    logger.info(f"{entity_name} 资金画像生成完成")

    # 【内存优化】强制执行垃圾回收
    import gc

    gc.collect()

    return profile


def extract_large_cash(df: pd.DataFrame, threshold: float = None) -> List[Dict]:
    """
    提取大额现金存取记录

    Args:
        df: 交易DataFrame
        threshold: 金额阈值,默认使用配置

    Returns:
        大额现金记录列表
    """
    # 【P1修复】避免修改传入的DataFrame
    df = df.copy()

    if threshold is None:
        threshold = config.LARGE_CASH_THRESHOLD

    logger.info(f"正在筛查大额现金(阈值: {utils.format_currency(threshold)})...")

    large_cash_records = []

    for _, row in df.iterrows():
        # 【铁律修复】检查是否为现金交易 - 优先使用 is_cash 列
        if "is_cash" in row.index and row["is_cash"] == True:
            is_cash = True
        elif "现金" in row.index and row["现金"] == "是":
            is_cash = True
        else:
            is_cash = utils.contains_keywords(row["description"], config.CASH_KEYWORDS)

        if is_cash:
            amount = max(row["income"], row["expense"])
            if amount >= threshold:
                record = row.to_dict()
                record["cash_type"] = "deposit" if row["income"] > 0 else "withdrawal"
                record["amount"] = amount

                # 判断风险等级
                if amount >= config.CASH_THRESHOLDS["level_4"]:
                    record["risk_level"] = "high"
                elif amount >= config.CASH_THRESHOLDS["level_3"]:
                    record["risk_level"] = "medium"
                else:
                    record["risk_level"] = "low"

                large_cash_records.append(record)

    logger.info(f"发现 {len(large_cash_records)} 笔大额现金交易")

    return large_cash_records


def categorize_transactions(df: pd.DataFrame) -> Dict[str, List[Dict]]:
    """
    交易分类

    Args:
        df: 交易DataFrame

    Returns:
        分类后的交易字典
    """
    categories = {
        "salary": [],  # 工资性收入
        "non_salary": [],  # 非工资性收入
        "third_party": [],  # 第三方支付
        "cash": [],  # 现金交易
        "large_amount": [],  # 大额交易
        "property": [],  # 疑似购房
        "vehicle": [],  # 疑似购车
        "other": [],  # 其他
    }

    for _, row in df.iterrows():
        record = row.to_dict()

        # 收入分类
        if row["income"] > 0:
            if utils.contains_keywords(
                row["description"], config.SALARY_STRONG_KEYWORDS
            ):
                categories["salary"].append(record)
            else:
                categories["non_salary"].append(record)

        # 支出分类
        if row["expense"] > 0:
            # 第三方支付
            if utils.contains_keywords(
                row["description"], config.THIRD_PARTY_PAYMENT_KEYWORDS
            ):
                categories["third_party"].append(record)

            # 疑似购房
            if utils.contains_keywords(row["description"], config.PROPERTY_KEYWORDS):
                if row["expense"] >= config.PROPERTY_THRESHOLD:
                    categories["property"].append(record)

            # 疑似购车
            if utils.contains_keywords(row["description"], config.VEHICLE_KEYWORDS):
                if row["expense"] >= config.VEHICLE_THRESHOLD:
                    categories["vehicle"].append(record)

        # 【铁律修复】现金交易 - 优先使用 is_cash 列
        if "is_cash" in row.index and row["is_cash"] == True:
            categories["cash"].append(record)
        elif "现金" in row.index and row["现金"] == "是":
            categories["cash"].append(record)
        elif utils.contains_keywords(row["description"], config.CASH_KEYWORDS):
            categories["cash"].append(record)

        # 大额交易
        amount = max(row["income"], row["expense"])
        if amount >= config.LARGE_CASH_THRESHOLD:
            categories["large_amount"].append(record)

    return categories


# ========== Phase 2: 公司画像构建 (2026-01-20 新增) ==========


def build_company_profile(df: pd.DataFrame, entity_name: str) -> Dict:
    """
    构建公司资金画像

    【Phase 2 - 2026-01-20】
    功能:
    1. 复用现有的画像生成逻辑
    2. 移除不适用于公司的字段(如工资统计)
    3. 添加公司特有的分析维度

    Args:
        df: 交易DataFrame
        entity_name: 公司名称

    Returns:
        公司资金画像字典,包含:
        - entity_type: 'company'
        - 基础画像数据(复用个人画像结构)
        - company_specific: 公司特有分析
    """
    logger.info(f"正在为公司 {entity_name} 生成资金画像...")

    if df.empty:
        logger.warning(f"{entity_name} 无交易数据")
        return {
            "entity_name": entity_name,
            "entity_type": "company",
            "has_data": False,
        }

    # 【关键修复】标准化列名
    try:
        df = standardize_columns(df)
        logger.info(f"✓ 列名标准化完成: {list(df.columns)}")
    except Exception as e:
        logger.warning(f"列名标准化失败: {str(e)}，使用原始列名")

    # 【容错处理】如果还是没有'date'列，尝试其他方式
    if "date" not in df.columns:
        logger.warning("未找到'date'列，尝试其他日期列名")
        for col in ["交易时间", "交易日期", "日期"]:
            if col in df.columns:
                df = df.rename(columns={col: "date"})
                logger.info(f"✓ 使用'{col}'作为日期列")
                break

    # 复用现有的画像生成逻辑
    # 注意: 不传入entity_name参数,因为公司不需要工资识别
    income_structure = calculate_income_structure(df, entity_name=None)
    fund_flow = analyze_fund_flow(df)
    wealth_management = analyze_wealth_management(df, entity_name=None)
    large_cash = extract_large_cash(df)
    categories = categorize_transactions(df)

    # 计算真实收入/支出（【2026-02-12修复】）
    real_income, real_expense, offset_detail = _calculate_real_income_expense(
        income_structure, wealth_management, fund_flow
    )

    # 公司特有分析
    company_specific = _analyze_company_specific(df, entity_name)

    # 构建公司画像摘要(移除工资相关字段)
    summary = {
        "total_income": income_structure["total_income"],
        "total_expense": income_structure["total_expense"],
        "net_flow": income_structure["net_flow"],
        "real_income": real_income,
        "real_expense": real_expense,
        "cash_ratio": (fund_flow["cash_income"] + fund_flow["cash_expense"])
        / (income_structure["total_income"] + income_structure["total_expense"])
        if (income_structure["total_income"] + income_structure["total_expense"]) > 0
        else 0,
        "third_party_ratio": fund_flow["third_party_ratio"],
        "large_cash_count": len(large_cash),
        "wealth_transactions": wealth_management["total_transactions"],
        "transaction_count": len(df),
        "date_range": income_structure["date_range"],
        "offset_detail": offset_detail,  # 【2026-02-12新增】
    }

    profile = {
        "entity_name": entity_name,
        "entity_type": "company",  # 标识为公司实体
        "has_data": True,
        "income_structure": income_structure,
        "fund_flow": fund_flow,
        "wealth_management": wealth_management,
        "large_cash": large_cash,
        "categories": categories,
        "company_specific": company_specific,  # 公司特有分析
        "summary": summary,
        "transactions": df.head(1000).to_dict("records")
        if not df.empty
        else [],  # 【2026-03-01 修复】添加交易明细供报告生成使用
    }

    logger.info(f"{entity_name} 公司画像生成完成")

    # 【内存优化】强制执行垃圾回收
    import gc

    gc.collect()

    return profile


def _analyze_company_specific(df: pd.DataFrame, company_name: str) -> Dict:
    """
    公司特有分析

    Args:
        df: 交易DataFrame
        company_name: 公司名称

    Returns:
        公司特有分析字典,包含:
        - to_individual_transfers: 公转私统计
        - cash_withdrawal_pattern: 现金提取模式
    """
    logger.info(f"正在分析{company_name}的公司特有维度...")

    # 1. 公转私统计(向个人账户的转账)
    to_individual_transfers = _analyze_to_individual_transfers(df)

    # 2. 现金提取模式分析
    cash_withdrawal_pattern = _analyze_cash_withdrawal_pattern(df)

    return {
        "to_individual_transfers": to_individual_transfers,
        "cash_withdrawal_pattern": cash_withdrawal_pattern,
    }


def _analyze_to_individual_transfers(df: pd.DataFrame) -> Dict:
    """
    分析公转私交易(公司向个人账户的转账)

    Args:
        df: 交易DataFrame

    Returns:
        公转私统计字典
    """
    import re

    # 筛选支出交易
    expense_df = df[df["expense"] > 0].copy()

    if expense_df.empty:
        return {"total_amount": 0.0, "count": 0, "recipients": []}

    # 识别个人姓名(2-4个汉字)
    individual_transfers = []
    total_amount = 0.0

    for _, row in expense_df.iterrows():
        counterparty = str(row.get("counterparty", "")).strip()

        # 判断是否为个人姓名
        if re.match(r"^[\u4e00-\u9fa5]{2,4}$", counterparty):
            amount = row.get("expense", 0)
            individual_transfers.append(
                {
                    "recipient": counterparty,
                    "amount": float(amount),
                    "date": row["date"].strftime("%Y-%m-%d")
                    if pd.notna(row["date"])
                    else "未知",
                    "description": str(row.get("description", "")),
                }
            )
            total_amount += amount

    # 按收款人分组统计
    from collections import defaultdict

    recipient_stats = defaultdict(lambda: {"count": 0, "total": 0.0})

    for transfer in individual_transfers:
        recipient = transfer["recipient"]
        recipient_stats[recipient]["count"] += 1
        recipient_stats[recipient]["total"] += transfer["amount"]

    # 转换为列表并排序
    recipients = [
        {"name": name, "count": stats["count"], "total_amount": stats["total"]}
        for name, stats in recipient_stats.items()
    ]
    recipients.sort(key=lambda x: x["total_amount"], reverse=True)

    logger.info(
        f"公转私统计: 共{len(individual_transfers)}笔, 总额{utils.format_currency(total_amount)}"
    )

    return {
        "total_amount": float(total_amount),
        "count": len(individual_transfers),
        "recipients": recipients[:20],  # 只保留前20个收款人
        "details": individual_transfers[:100],  # 只保留前100笔明细
    }


def _analyze_cash_withdrawal_pattern(df: pd.DataFrame) -> Dict:
    """
    分析现金提取模式

    Args:
        df: 交易DataFrame

    Returns:
        现金提取模式字典
    """
    # 筛选现金支出
    cash_expense_df = df[
        (df["expense"] > 0) & (df.get("is_cash", False) == True)
    ].copy()

    if cash_expense_df.empty:
        # 尝试通过关键词识别
        cash_expense_df = df[df["expense"] > 0].copy()
        cash_expense_df = cash_expense_df[
            cash_expense_df["description"].str.contains(
                "现金|取现|提现|支取", case=False, na=False
            )
        ]

    if cash_expense_df.empty:
        return {
            "total_amount": 0.0,
            "count": 0,
            "avg_amount": 0.0,
            "max_amount": 0.0,
            "frequency": "无",
        }

    total_amount = cash_expense_df["expense"].sum()
    count = len(cash_expense_df)
    avg_amount = total_amount / count if count > 0 else 0
    max_amount = cash_expense_df["expense"].max()

    # 判断频率
    if count >= 20:
        frequency = "频繁"
    elif count >= 10:
        frequency = "较多"
    elif count >= 5:
        frequency = "一般"
    else:
        frequency = "较少"

    logger.info(f"现金提取: 共{count}笔, 总额{utils.format_currency(total_amount)}")

    return {
        "total_amount": float(total_amount),
        "count": int(count),
        "avg_amount": float(avg_amount),
        "max_amount": float(max_amount),
        "frequency": frequency,
    }


# ========== Phase 4: 收入来源分类 (2026-01-20 新增) ==========


def _make_income_tx_signature(
    date_value,
    amount_value,
    counterparty_value="",
    description_value="",
):
    """构建收入交易签名，用于跨模块定位同一笔收入。"""
    parsed_date = utils.parse_date(date_value)
    date_str = parsed_date.strftime("%Y-%m-%d") if parsed_date else "未知"
    amount = round(_safe_amount(amount_value, "amount"), 2)

    return (
        date_str,
        amount,
        str(counterparty_value or "").strip(),
        str(description_value or "").strip(),
    )


def _build_income_tx_counter(
    transactions: List[Dict],
    amount_keys: List[str],
    date_keys: List[str] = None,
    counterparty_keys: List[str] = None,
    description_keys: List[str] = None,
) -> Counter:
    """根据交易列表构建签名计数器，避免同日同额交易被误合并。"""
    counter: Counter = Counter()
    if not isinstance(transactions, list):
        return counter

    date_keys = date_keys or ["日期", "date"]
    counterparty_keys = counterparty_keys or ["对手方", "counterparty"]
    description_keys = description_keys or ["摘要", "description"]

    for tx in transactions:
        if not isinstance(tx, dict):
            continue

        amount = None
        for key in amount_keys:
            value = tx.get(key)
            if value not in (None, ""):
                amount = value
                break
        if amount is None:
            continue

        date_value = next((tx.get(key) for key in date_keys if tx.get(key) is not None), None)
        counterparty_value = next(
            (tx.get(key) for key in counterparty_keys if tx.get(key) is not None), ""
        )
        description_value = next(
            (tx.get(key) for key in description_keys if tx.get(key) is not None), ""
        )
        counter[
            _make_income_tx_signature(
                date_value, amount, counterparty_value, description_value
            )
        ] += 1

    return counter


def classify_income_sources(
    income_df: pd.DataFrame,
    entity_name: str = None,
    wealth_result: Dict = None,
    family_members: List[str] = None,
) -> Dict:
    """
    对收入来源进行分类（增强版 - 2026-01-25）【向量化优化】

    【Phase 4 - 2026-01-20】【增强 - 2026-01-25】【向量化优化 - 2026-03-01】
    功能:
    1. 将收入分为三类: 合法收入、不明收入、可疑收入
    2. 计算各类占比
    3. 提供详细的分类依据

    分类标准:
    - **合法收入**: 工资、政府机关转账、社保公积金、理财收益、投资收益等
    - **不明收入**: 个人转账、无法识别来源的收入
    - **可疑收入**: 借贷平台、高频小额、疑似洗钱模式

    【增强内容】
    1. 新增社保/公积金识别
    2. 新增养老金/职业年金识别
    3. 新增投资收益识别（利息、分红、股息）
    4. 新增代发工资识别
    5. 新增退款/冲正识别
    6. 优化理财收益识别

    Args:
        income_df: 收入交易DataFrame (只包含收入记录)
        entity_name: 实体名称
        wealth_result: 理财分析结果(用于去重识别)

    Returns:
        收入来源分类结果字典
    """
    logger.info("正在对收入来源进行分类（增强版 - 向量化优化）...")

    if income_df.empty:
        logger.warning("无收入数据,无法分类")
        return {
            "classification_basis": "real_income_basis",
            "legitimate_income": 0.0,
            "unknown_income": 0.0,
            "suspicious_income": 0.0,
            "business_reimbursement_income": 0.0,
            "excluded_income": 0.0,
            "legitimate_ratio": 0.0,
            "unknown_ratio": 0.0,
            "suspicious_ratio": 0.0,
            "business_reimbursement_ratio": 0.0,
            "excluded_ratio": 0.0,
            "legitimate_details": [],
            "unknown_details": [],
            "suspicious_details": [],
            "business_reimbursement_details": [],
            "excluded_details": [],
            "excluded_breakdown": {},
            "reason_breakdown": {},
            "legitimate_count": 0,
            "unknown_count": 0,
            "suspicious_count": 0,
            "business_reimbursement_count": 0,
            "excluded_count": 0,
        }

    # 向量化:准备数据列
    df = income_df.copy()
    for column in ("description", "counterparty", "category", "account_type", "account_category"):
        if column not in df.columns:
            df[column] = ""
    df["desc_str"] = df["description"].astype(str).fillna("").str.strip()
    df["cp_str"] = df["counterparty"].astype(str).fillna("").str.strip()
    df["category_str"] = df["category"].astype(str).fillna("").str.strip()
    df["account_type_str"] = df["account_type"].astype(str).fillna("").str.strip()
    df["account_category_str"] = df["account_category"].astype(str).fillna("").str.strip()
    df["text_str"] = (
        df["cp_str"]
        + " "
        + df["desc_str"]
        + " "
        + df["category_str"]
        + " "
        + df["account_type_str"]
        + " "
        + df["account_category_str"]
    ).str.strip()
    df["amount"] = df["income"]
    df["date_str"] = df["date"].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "未知"
    )
    empty_markers = {"", "-", "nan", "None", "\\N"}
    df["is_blank_counterparty"] = df["cp_str"].isin(empty_markers)
    df["is_blank_description"] = df["desc_str"].isin(empty_markers)
    df = _identify_business_reimbursement_income(df)
    df["excluded_reason"] = ""
    df["excluded_bucket"] = ""
    df["excluded_confidence"] = ""
    df["tx_signature"] = df.apply(
        lambda row: _make_income_tx_signature(
            row.get("date"),
            row.get("amount"),
            row.get("cp_str"),
            row.get("desc_str"),
        ),
        axis=1,
    )

    def _consume_counter_match(counter: Counter, signature) -> bool:
        if counter[signature] > 0:
            counter[signature] -= 1
            return True
        return False

    # 向量化:时间模式识别(空摘要定期收入)
    time_pattern_mask = _vectorized_time_pattern_detection(df)
    df["is_time_pattern"] = df.index.isin(time_pattern_mask)

    family_member_aliases = _build_name_alias_set(family_members or [])
    entity_aliases = _build_name_alias_set([entity_name] if entity_name else [])
    redemption_counter = _build_income_tx_counter(
        wealth_result.get("wealth_redemption_transactions", []) if wealth_result else [],
        amount_keys=["金额", "收入", "amount"],
    )
    self_transfer_counter = _build_income_tx_counter(
        wealth_result.get("self_transfer_transactions", []) if wealth_result else [],
        amount_keys=["收入", "金额", "amount"],
    )
    reimbursement_counter = _build_income_tx_counter(
        wealth_result.get("business_reimbursement_transactions", []) if wealth_result else [],
        amount_keys=["金额", "收入", "amount"],
    )
    loan_counter = _build_income_tx_counter(
        wealth_result.get("loan_transactions", []) if wealth_result else [],
        amount_keys=["income", "收入", "金额", "amount"],
        date_keys=["date", "日期"],
    )
    refund_counter = _build_income_tx_counter(
        wealth_result.get("refund_transactions", []) if wealth_result else [],
        amount_keys=["income", "收入", "金额", "amount"],
        date_keys=["date", "日期"],
    )

    loan_issue_keywords = ["放款", "贷款发放", "个贷发放"]
    refund_keywords = ["退款", "冲正", "退回", "撤销", "退货退款"]
    wealth_redemption_keywords = [
        "理财赎回",
        "基金赎回",
        "赎回",
        "定期到期",
        "大额存单到期",
        "结构性存款到期",
        "定期存款到期",
    ]
    insurance_keywords = [
        "保险理赔",
        "保险金",
        "赔款",
        "理赔款",
        "退保",
        "退保金",
        "保险返还",
        "返还",
        "分红",
        "保单红利",
        "满期金",
        "生存金",
        "年金给付",
    ]
    insurance_entity_keywords = [
        "财产保险",
        "人寿保险",
        "保险股份",
        "保险有限公司",
        "保险代理",
        "中国人寿",
        "中国平安财产",
        "中国平安人寿",
        "中国人民人寿",
        "中国太平洋财产",
        "中国太平洋人寿",
        "国任财产保险",
        "中宏人寿",
        "泰康人寿",
        "新华保险",
        "阳光保险",
        "携程保险代理",
        "人保财险",
    ]
    wealth_signal_keywords = [
        "理财",
        "添利",
        "恒享",
        "稳享",
        "增强",
        "定开",
        "现金添利",
        "薪金理财",
        "债券",
        "稳添",
        "沃德",
        "证券",
        "基金",
        "托管专户",
        "第三方存管",
        "存管保证金",
        "快赎业务清算款",
        "快赎",
        "结构性存款",
        "大额存单",
        "定期存款",
    ]
    cash_deposit_keywords = [
        "现金",
        "取现",
        "提现",
        "支取",
        "ATM存款",
        "CRS存款",
        "现金尾箱",
        "尾箱帐户",
        "尾箱账户",
        "续存",
        "现存",
        "自助存款",
    ]

    insurance_pattern = "|".join(re.escape(kw) for kw in insurance_keywords)
    insurance_entity_pattern = "|".join(
        re.escape(kw) for kw in insurance_entity_keywords
    )
    wealth_signal_pattern = "|".join(re.escape(kw) for kw in wealth_signal_keywords)
    cash_deposit_pattern = "|".join(re.escape(kw) for kw in cash_deposit_keywords)

    exclusion_conditions = [
        (
            df["tx_signature"].apply(
                lambda sig: _consume_counter_match(self_transfer_counter, sig)
            )
            | (
                df["cp_str"].apply(lambda value: _matches_alias_set(value, entity_aliases))
                & (df["amount"] > 0)
            ),
            "本人账户互转（已剔除）",
            "self_transfer",
            "high",
        ),
        (
            df["tx_signature"].apply(
                lambda sig: _consume_counter_match(redemption_counter, sig)
            ),
            "理财/定存本金回流（已剔除）",
            "wealth_redemption",
            "high" if wealth_result else "medium",
        ),
        (
            df["tx_signature"].apply(
                lambda sig: _consume_counter_match(reimbursement_counter, sig)
            )
            | df["is_business_reimbursement"].fillna(False),
            "单位报销/业务往来款（已剔除）",
            "business_reimbursement",
            "high",
        ),
        (
            df["tx_signature"].apply(lambda sig: _consume_counter_match(loan_counter, sig))
            | df["desc_str"].apply(lambda x: any(kw in x for kw in loan_issue_keywords)),
            "贷款发放（已剔除）",
            "loan",
            "high" if wealth_result else "medium",
        ),
        (
            df["tx_signature"].apply(lambda sig: _consume_counter_match(refund_counter, sig))
            | df["desc_str"].apply(lambda x: any(kw in x for kw in refund_keywords)),
            "退款/冲正（已剔除）",
            "refund",
            "high" if wealth_result else "medium",
        ),
        (
            df["cp_str"].apply(
                lambda value: _matches_alias_set(value, family_member_aliases)
            )
            if family_member_aliases
            else pd.Series(False, index=df.index),
            "家庭成员转入（已剔除）",
            "family_transfer",
            "medium",
        ),
    ]

    df["has_product_code"] = df["desc_str"].str.contains(
        r"(?:^|[^A-Za-z0-9])[A-Z]*\d{8,}[A-Z]*(?:[^A-Za-z0-9]|$)",
        case=False,
        na=False,
        regex=True,
    )
    df["has_wealth_signal"] = df["text_str"].str.contains(
        wealth_signal_pattern, case=False, na=False, regex=True
    )
    df["has_wealth_category"] = df["category_str"].str.contains(
        r"投资理财|证券", case=False, na=False, regex=True
    ) | df["account_type_str"].isin(["理财账户", "证券账户"])
    df["has_insurance_entity"] = df["text_str"].str.contains(
        insurance_entity_pattern, case=False, na=False, regex=True
    )
    df["has_insurance_signal"] = (
        df["text_str"].str.contains(insurance_pattern, case=False, na=False, regex=True)
        | df["has_insurance_entity"]
    )
    df["has_cash_deposit_marker"] = df["text_str"].str.contains(
        cash_deposit_pattern, case=False, na=False, regex=True
    )
    df["has_securities_transfer_kw"] = df["text_str"].str.contains(
        r"证转银|第三方存管保证金转活期|快赎业务清算款|网商基金快赎|银证转账",
        case=False,
        na=False,
        regex=True,
    )
    fallback_wealth_redemption_mask = (
        (
            df["has_securities_transfer_kw"]
            | (
                (df["has_wealth_category"] | df["has_product_code"])
                & df["has_wealth_signal"]
            )
        )
        & ~df["has_insurance_signal"]
        & ~df["desc_str"].str.contains(r"利息|收益|分红|股息|红利", na=False, regex=True)
        & (df["amount"] >= 1000)
    )
    exclusion_conditions.append(
        (
            fallback_wealth_redemption_mask,
            "理财/定存/证券回款待拆分（已剔除）",
            "wealth_redemption",
            "medium",
        )
    )

    exclusion_conditions.append(
        (
            df["desc_str"].apply(
                lambda x: any(kw in x for kw in wealth_redemption_keywords)
            ),
            "理财/定存本金回流（已剔除）",
            "wealth_redemption",
            "medium" if wealth_result is None else "low",
        )
    )

    for mask, reason, bucket, confidence in exclusion_conditions:
        update_mask = mask & (df["excluded_reason"] == "")
        df.loc[update_mask, "excluded_reason"] = reason
        df.loc[update_mask, "excluded_bucket"] = bucket
        df.loc[update_mask, "excluded_confidence"] = confidence

    excluded_df = df[df["excluded_reason"] != ""].copy()
    df = df[df["excluded_reason"] == ""].copy()
    total_income = df["amount"].sum()
    business_reimbursement_df = excluded_df[
        excluded_df["excluded_reason"] == "单位报销/业务往来款（已剔除）"
    ].copy()
    excluded_income = excluded_df["amount"].sum() if not excluded_df.empty else 0.0

    def build_records(sub_df):
        if sub_df.empty:
            return []
        records = sub_df.apply(
            lambda row: {
                "date": row["date_str"],
                "amount": float(row["amount"]),
                "counterparty": row["cp_str"],
                "description": row["desc_str"],
                "reason": row.get("reason", row.get("excluded_reason", "")),
                "rule_bucket": row.get("excluded_bucket")
                or row.get("rule_bucket")
                or row.get("category", ""),
                "confidence": row.get("excluded_confidence")
                or row.get("confidence", ""),
            },
            axis=1,
        ).tolist()
        records.sort(key=lambda x: x["amount"], reverse=True)
        return records[:50]

    business_reimbursement_details = build_records(business_reimbursement_df)
    excluded_details = build_records(
        excluded_df.rename(columns={"excluded_reason": "reason"})
    )

    if df.empty:
        logger.info(
            f"收入分类完成: 合法¥0.00(0.0%), 不明¥0.00(0.0%), 可疑¥0.00(0.0%), "
            f"其中单位报销/业务往来款{utils.format_currency(business_reimbursement_df['amount'].sum() if not business_reimbursement_df.empty else 0)}"
        )
        return {
            "classification_basis": "real_income_basis",
            "legitimate_income": 0.0,
            "unknown_income": 0.0,
            "suspicious_income": 0.0,
            "business_reimbursement_income": float(
                business_reimbursement_df["amount"].sum()
                if not business_reimbursement_df.empty
                else 0.0
            ),
            "excluded_income": float(excluded_income),
            "legitimate_ratio": 0.0,
            "unknown_ratio": 0.0,
            "suspicious_ratio": 0.0,
            "business_reimbursement_ratio": 0.0,
            "excluded_ratio": 1.0 if excluded_income > 0 else 0.0,
            "legitimate_details": [],
            "unknown_details": [],
            "suspicious_details": [],
            "business_reimbursement_details": business_reimbursement_details,
            "excluded_details": excluded_details,
            "excluded_breakdown": {
                key: float(group["amount"].sum())
                for key, group in excluded_df.groupby("excluded_bucket")
                if key
            },
            "reason_breakdown": {},
            "legitimate_count": 0,
            "unknown_count": 0,
            "suspicious_count": 0,
            "business_reimbursement_count": len(business_reimbursement_details),
            "excluded_count": len(excluded_details),
        }

    # 向量化:关键词匹配
    # 合法收入关键词
    salary_keywords = [
        "工资",
        "奖金",
        "绩效",
        "代发",
        "PAY",
        "薪酬",
        "薪资",
        "劳务费",
        "劳务报酬",
        "年薪",
        "骨干奖",
        "奖励",
        "补差",
        "预发",
        "超额经济贡献奖",
        "补充奖励",
        "安全责任令",
    ]
    gov_keywords = [
        "财政局",
        "公积金",
        "社保",
        "房改资金",
        "民政局",
        "人社局",
        "社保局",
        "公积金中心",
        "住房资金",
    ]
    pension_keywords = ["职业年金", "养老金", "退休金", "退休费", "离休费"]
    invest_keywords = [
        "利息",
        "收益",
        "分红",
        "股息",
        "红利",
        "利息收入",
        "存款利息",
    ]
    welfare_keywords = ["补贴", "补助", "抚恤金", "救济金", "低保", "困难补助"]

    # 可疑收入关键词
    loan_keywords = [
        "借呗",
        "微粒贷",
        "京东金条",
        "度小满",
        "360借条",
        "分期乐",
        "捷信",
        "马上金融",
    ]
    third_party_keywords = ["支付宝", "财付通", "微信支付", "微信", "零钱"]

    # 向量化:关键词匹配掩码
    df["has_salary_kw"] = df.apply(
        lambda row: any(
            kw in row["desc_str"] or kw in row["cp_str"] for kw in salary_keywords
        ),
        axis=1,
    )
    df["has_gov_kw"] = df.apply(
        lambda row: any(
            kw in row["desc_str"] or kw in row["cp_str"] for kw in gov_keywords
        ),
        axis=1,
    )
    df["has_pension_kw"] = df["desc_str"].apply(
        lambda x: any(kw in x for kw in pension_keywords)
    )
    df["has_invest_kw"] = df["text_str"].apply(
        lambda x: any(kw in x for kw in invest_keywords)
    )
    df["has_refund_kw"] = df["desc_str"].apply(
        lambda x: any(kw in x for kw in refund_keywords)
    )
    df["has_insurance_kw"] = df["has_insurance_signal"]
    df["has_welfare_kw"] = df["desc_str"].apply(
        lambda x: any(kw in x for kw in welfare_keywords)
    )

    # 机构特征词
    institution_pattern = r"(?:研究所|局|院|中心|部|集团|公司)"
    bank_payroll_pattern = r"(?:代发工资|内部户|代发)"
    df["has_institution"] = df["cp_str"].str.contains(
        institution_pattern, case=False, na=False, regex=True
    )
    df["has_payroll_pattern"] = df["cp_str"].str.contains(
        bank_payroll_pattern, case=False, na=False, regex=True
    )

    # 向量化:合法收入分类
    legitimate_conditions = [
        (df["has_salary_kw"], "工资性收入", "salary", "high"),
        (df["has_pension_kw"], "养老金/职业年金", "pension", "high"),
        (df["has_invest_kw"], "投资收益", "investment_income", "medium"),
        (df["has_insurance_kw"], "保险赔付/返还", "insurance_income", "high"),
        (df["has_welfare_kw"], "福利补贴", "welfare", "medium"),
        (df["has_gov_kw"], "政府机关转账(社保/公积金)", "government_income", "high"),
        (df["is_time_pattern"], "定期收入(时间模式识别)", "time_pattern_income", "medium"),
        (
            (df["has_institution"] | df["has_payroll_pattern"]) & (df["amount"] > 0),
            "工资性收入(机构/代发单位)",
            "salary_institution",
            "high",
        ),
    ]

    # 已知发薪单位(从config)
    if hasattr(config, "KNOWN_SALARY_PAYERS") and config.KNOWN_SALARY_PAYERS:
        df["has_known_payer"] = df.apply(
            lambda row: any(kw in row["cp_str"] for kw in config.KNOWN_SALARY_PAYERS),
            axis=1,
        )
        legitimate_conditions.append(
            (df["has_known_payer"], "已知发薪单位", "known_salary_payer", "high")
        )

    if (
        hasattr(config, "USER_DEFINED_SALARY_PAYERS")
        and config.USER_DEFINED_SALARY_PAYERS
    ):
        df["has_user_payer"] = df.apply(
            lambda row: any(
                kw in row["cp_str"] for kw in config.USER_DEFINED_SALARY_PAYERS
            ),
            axis=1,
        )
        legitimate_conditions.append(
            (df["has_user_payer"], "用户定义发薪单位", "user_salary_payer", "high")
        )

    # 人力资源公司
    if hasattr(config, "HR_COMPANY_KEYWORDS") and config.HR_COMPANY_KEYWORDS:
        df["has_hr"] = df.apply(
            lambda row: any(kw in row["cp_str"] for kw in config.HR_COMPANY_KEYWORDS),
            axis=1,
        )
        legitimate_conditions.append((df["has_hr"], "人力资源公司", "hr_company", "high"))

    # 理财赎回关键词
    if (
        hasattr(config, "WEALTH_REDEMPTION_KEYWORDS")
        and config.WEALTH_REDEMPTION_KEYWORDS
    ):
        df["has_wealth_kw"] = df["text_str"].apply(
            lambda x: any(kw in x for kw in config.WEALTH_REDEMPTION_KEYWORDS)
        )
        legitimate_conditions.append(
            (
                df["has_wealth_kw"] & ~df["desc_str"].str.contains("赎回", na=False),
                "理财收益",
                "wealth_income",
                "medium",
            )
        )

    # 向量化:可疑收入分类
    df["has_loan_kw"] = df.apply(
        lambda row: any(
            kw in row["desc_str"] or kw in row["cp_str"] for kw in loan_keywords
        ),
        axis=1,
    )
    df["has_third_party"] = df["cp_str"].apply(
        lambda x: any(kw in x for kw in third_party_keywords)
    )
    df["has_cash_kw"] = df["has_cash_deposit_marker"]

    # 大额阈值
    high_risk_min = getattr(config, "INCOME_HIGH_RISK_MIN", 50000)
    large_cash_threshold = getattr(config, "LARGE_CASH_THRESHOLD", 50000)

    suspicious_conditions = [
        (df["has_loan_kw"], "借贷平台", "loan_platform", "high"),
        (
            (df["has_third_party"]) & (df["amount"] >= high_risk_min),
            "第三方支付大额转入",
            "third_party_large",
            "high",
        ),
        (
            (df["has_cash_kw"]) & (df["amount"] >= large_cash_threshold),
            "大额现金存入",
            "cash_large",
            "high",
        ),
    ]

    # 向量化:应用分类
    df["category"] = "unknown"  # 默认不明收入
    df["reason"] = "来源不明"
    df["rule_bucket"] = "unknown"
    df["confidence"] = "low"

    # 应用合法收入分类
    for mask, reason, bucket, confidence in legitimate_conditions:
        update_mask = mask & (df["category"] == "unknown")
        df.loc[update_mask, "category"] = "legitimate"
        df.loc[update_mask, "reason"] = reason
        df.loc[update_mask, "rule_bucket"] = bucket
        df.loc[update_mask, "confidence"] = confidence

    # 应用可疑收入分类
    for mask, reason, bucket, confidence in suspicious_conditions:
        update_mask = mask & (df["category"] == "unknown")
        df.loc[update_mask, "category"] = "suspicious"
        df.loc[update_mask, "reason"] = reason
        df.loc[update_mask, "rule_bucket"] = bucket
        df.loc[update_mask, "confidence"] = confidence

    # 第三方支付小额、现金小额分类为不明收入
    third_party_small_mask = (
        (df["has_third_party"])
        & (df["amount"] < high_risk_min)
        & (df["category"] == "unknown")
    )
    df.loc[third_party_small_mask, "reason"] = "第三方支付小额转入"
    df.loc[third_party_small_mask, "rule_bucket"] = "third_party_small"
    df.loc[third_party_small_mask, "confidence"] = "medium"

    cash_small_mask = (
        (df["has_cash_kw"])
        & (df["amount"] < large_cash_threshold)
        & (df["category"] == "unknown")
    )
    df.loc[cash_small_mask, "reason"] = "小额现金存入"
    df.loc[cash_small_mask, "rule_bucket"] = "cash_small"
    df.loc[cash_small_mask, "confidence"] = "medium"

    blank_structured_mask = (
        df["is_blank_counterparty"] & df["is_blank_description"] & (df["category"] == "unknown")
    )
    blank_amount_repeat = (
        df.loc[blank_structured_mask, "amount"].round(2).value_counts().to_dict()
    )
    df["blank_amount_repeat"] = df["amount"].round(2).map(blank_amount_repeat).fillna(0)
    blank_large_mask = blank_structured_mask & (df["amount"] >= 10000)
    df.loc[blank_large_mask, "reason"] = "空白字段大额入账"
    df.loc[blank_large_mask, "rule_bucket"] = "blank_large"
    df.loc[blank_large_mask, "confidence"] = "medium"

    blank_frequent_mask = (
        blank_structured_mask
        & ~blank_large_mask
        & (df["blank_amount_repeat"] >= 3)
    )
    df.loc[blank_frequent_mask, "reason"] = "空白字段高频入账"
    df.loc[blank_frequent_mask, "rule_bucket"] = "blank_frequent"
    df.loc[blank_frequent_mask, "confidence"] = "low"

    # 个人转账识别(2-4个汉字)
    df["is_individual"] = df["cp_str"].str.match(r"^[\u4e00-\u9fa5]{2,4}$", na=False)
    individual_mask = df["is_individual"] & (df["category"] == "unknown")
    df.loc[individual_mask, "reason"] = "个人转账"
    df.loc[individual_mask, "rule_bucket"] = "individual_transfer"
    df.loc[individual_mask, "confidence"] = "medium"

    # 向量化:统计计算
    legitimate_df = df[df["category"] == "legitimate"].copy()
    suspicious_df = df[df["category"] == "suspicious"].copy()
    unknown_df = df[df["category"] == "unknown"].copy()
    legitimate_income = legitimate_df["amount"].sum()
    suspicious_income = suspicious_df["amount"].sum()
    unknown_income = unknown_df["amount"].sum()
    business_reimbursement_income = business_reimbursement_df["amount"].sum()

    legitimate_details = build_records(legitimate_df)
    suspicious_details = build_records(suspicious_df)
    unknown_details = build_records(unknown_df)

    # 计算占比
    legitimate_ratio = legitimate_income / total_income if total_income > 0 else 0
    unknown_ratio = unknown_income / total_income if total_income > 0 else 0
    suspicious_ratio = suspicious_income / total_income if total_income > 0 else 0
    business_reimbursement_ratio = (
        business_reimbursement_income / total_income if total_income > 0 else 0
    )
    excluded_ratio = (
        excluded_income / (total_income + excluded_income)
        if (total_income + excluded_income) > 0
        else 0
    )

    # 按金额降序排序
    legitimate_details.sort(key=lambda x: x["amount"], reverse=True)
    unknown_details.sort(key=lambda x: x["amount"], reverse=True)
    suspicious_details.sort(key=lambda x: x["amount"], reverse=True)
    business_reimbursement_details.sort(key=lambda x: x["amount"], reverse=True)
    excluded_breakdown = {
        key: float(group["amount"].sum())
        for key, group in excluded_df.groupby("excluded_bucket")
        if key
    }
    reason_breakdown = {}
    for category_name, category_df in (
        ("legitimate", legitimate_df),
        ("unknown", unknown_df),
        ("suspicious", suspicious_df),
    ):
        if category_df.empty:
            continue
        reason_breakdown[category_name] = {
            reason: float(group["amount"].sum())
            for reason, group in category_df.groupby("reason")
            if reason
        }

    logger.info(
        f"收入分类完成: 合法{utils.format_currency(legitimate_income)}({legitimate_ratio:.1%}), "
        f"不明{utils.format_currency(unknown_income)}({unknown_ratio:.1%}), "
        f"可疑{utils.format_currency(suspicious_income)}({suspicious_ratio:.1%}), "
        f"其中单位报销/业务往来款{utils.format_currency(business_reimbursement_income)}({business_reimbursement_ratio:.1%}), "
        f"已剔除非真实收入{utils.format_currency(excluded_income)}"
    )

    return {
        "classification_basis": "real_income_basis",
        "legitimate_income": float(legitimate_income),
        "unknown_income": float(unknown_income),
        "suspicious_income": float(suspicious_income),
        "business_reimbursement_income": float(business_reimbursement_income),
        "excluded_income": float(excluded_income),
        "legitimate_ratio": float(legitimate_ratio),
        "unknown_ratio": float(unknown_ratio),
        "suspicious_ratio": float(suspicious_ratio),
        "business_reimbursement_ratio": float(business_reimbursement_ratio),
        "excluded_ratio": float(excluded_ratio),
        "legitimate_count": len(legitimate_details),
        "unknown_count": len(unknown_details),
        "suspicious_count": len(suspicious_details),
        "business_reimbursement_count": len(business_reimbursement_details),
        "excluded_count": len(excluded_details),
        "legitimate_details": legitimate_details[:50],  # 只保留前50笔
        "unknown_details": unknown_details[:50],
        "suspicious_details": suspicious_details[:50],
        "business_reimbursement_details": business_reimbursement_details[:50],
        "excluded_details": excluded_details[:50],
        "excluded_breakdown": excluded_breakdown,
        "reason_breakdown": reason_breakdown,
    }


def _vectorized_time_pattern_detection(df: pd.DataFrame) -> set:
    """
    向量化的时间模式检测(用于识别空摘要的定期收入)
    Args:
        df: DataFrame包含收入数据
    Returns:
        匹配时间模式记录的索引集合
    """
    idxs = set()
    # 摘要为空且收入>0的候选记录
    empty_desc_mask = df["desc_str"].str.strip() == ""
    cand_mask = empty_desc_mask & (df["income"] > 0)
    if not cand_mask.any():
        return idxs
    cand_df = df[cand_mask].copy()
    # 按金额桶分组
    cand_df["amount_bucket"] = (cand_df["income"] // 1000) * 1000
    for bucket, group in cand_df.groupby("amount_bucket"):
        if len(group) < 3:
            continue
        # 按日期排序
        sub = group.sort_values("date")
        idx_list = sub.index.tolist()
        # 计算月份差
        months = (
            sub["date"]
            .apply(lambda x: x.year * 12 + x.month if pd.notna(x) else 0)
            .tolist()
        )
        if len(months) < 3:
            continue
        diffs = [months[i + 1] - months[i] for i in range(len(months) - 1)]
        for i in range(len(diffs) - 1):
            d1 = diffs[i]
            d2 = diffs[i + 1]

            # 检查是否为周期性(2-7月或11-13月)
            def in_cycle(x):
                return x in (2, 3, 4, 5, 6, 7, 11, 12, 13)

            if in_cycle(d1) and in_cycle(d2):
                idxs.update(idx_list[i : i + 3])
    return idxs
