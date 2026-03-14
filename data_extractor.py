#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据提取模块 - 资金穿透与关联排查系统
负责从PDF和Excel文件中提取结构化数据

【修复说明】
- 问题3修复：PDF提取缺少错误处理
- 解决方案：添加详细的错误处理、文件验证和错误恢复机制
- 修改日期：2026-01-25
"""

import os
import pandas as pd
import pdfplumber
from typing import Dict, List, Tuple
from datetime import datetime
import config
import utils

logger = utils.setup_logger(__name__)


def extract_clues_from_pdf(pdf_path: str) -> Tuple[List[str], List[str]]:
    """
    从PDF线索文件中提取核心人员名单和涉案公司名单

    Args:
        pdf_path: PDF文件路径

    Returns:
        (核心人员列表, 涉案公司列表)
    """
    logger.info(f"正在提取PDF线索: {pdf_path}")

    # 【修复】添加文件存在性检查
    if not os.path.exists(pdf_path):
        logger.error(f"PDF文件不存在: {pdf_path}")
        return [], []

    # 【修复】添加文件大小检查（避免处理过大的文件）
    file_size = os.path.getsize(pdf_path)
    if file_size > 50 * 1024 * 1024:  # 50MB
        logger.warning(
            f"PDF文件过大({file_size / 1024 / 1024:.1f}MB)，跳过处理: {pdf_path}"
        )
        return [], []

    persons = set()
    companies = set()

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            page_count = 0

            # 【修复】添加页面数量限制，防止内存溢出
            for i, page in enumerate(pdf.pages):
                if i >= 100:  # 最多处理100页
                    logger.warning(f"PDF页数过多(>100页)，仅处理前100页: {pdf_path}")
                    break

                try:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
                    page_count += 1
                except Exception as page_error:
                    logger.warning(f"提取第{i + 1}页文本失败: {str(page_error)}")
                    continue

            # 提取人名
            try:
                names = utils.extract_chinese_name(full_text)
                persons.update(names)
            except Exception as name_error:
                logger.warning(f"提取人名失败: {str(name_error)}")

            # 提取公司名
            try:
                company_names = utils.extract_company_name(full_text)
                companies.update(company_names)
            except Exception as company_error:
                logger.warning(f"提取公司名失败: {str(company_error)}")

            logger.info(f"提取到 {len(persons)} 个人名, {len(companies)} 个公司名")

    except pdfplumber.PDFSyntaxError as e:
        logger.error(f"PDF文件格式错误: {pdf_path}, 错误: {str(e)}")
        return [], []
    except Exception as e:
        logger.error(f"提取PDF失败: {pdf_path}, 错误: {str(e)}")
        return [], []

    return list(persons), list(companies)


def _normalize_column_name(col_name: str) -> str:
    """
    规范化列名：去除空格、统一小写、去除特殊字符

    Args:
        col_name: 原始列名

    Returns:
        规范化后的列名
    """
    import re

    # 去除前后空格
    normalized = str(col_name).strip()
    # 统一转换为小写
    normalized = normalized.lower()
    # 去除括号及其内容（用于处理"收入(元)"这类列名）
    normalized = re.sub(r"[()（）\[\]【】]", "", normalized)
    # 去除下划线和连字符
    normalized = normalized.replace("_", "").replace("-", "")
    return normalized


def _calculate_match_score(normalized_col: str, keyword: str) -> Tuple[int, str]:
    """
    计算列名与关键词的匹配分数

    Args:
        normalized_col: 规范化后的列名
        keyword: 关键词（已小写）

    Returns:
        (分数, 匹配类型)
    """
    # 精确匹配（最高分）
    if normalized_col == keyword:
        return 100, "exact_match"

    # 前缀匹配：允许常见单位后缀，避免将“交易日”这类截断关键词误判为高分匹配。
    suffix = normalized_col[len(keyword):] if normalized_col.startswith(keyword) else ""
    if suffix and (len(suffix) >= 2 or suffix in {"元"}):
        return 80, "prefix_match"

    # 包含匹配（关键词在列名中，但不是前缀）
    if keyword in normalized_col and not normalized_col.startswith(keyword):
        return 60, "contains_match"

    # 相似度匹配（使用简单的编辑距离）
    # 如果编辑距离小于等于1，给予中等分数
    if len(normalized_col) > 0 and len(keyword) > 0:
        # 简单的相似度检查：如果关键词长度接近列名长度，且包含大部分字符
        if abs(len(normalized_col) - len(keyword)) <= 2:
            common_chars = sum(1 for c in keyword if c in normalized_col)
            similarity_ratio = common_chars / len(keyword)
            if similarity_ratio >= 0.7:
                return 40, "similarity_match"

    return 0, "no_match"


def find_column_by_keywords(
    df: pd.DataFrame, keywords: List[str], min_score: int = 60, verbose: bool = True
) -> str:
    """
    根据关键词列表查找DataFrame中的列名（改进版）

    使用多级匹配策略和评分机制，返回最佳匹配的列名

    Args:
        df: DataFrame
        keywords: 关键词列表（按优先级排序）
        min_score: 最低匹配分数阈值（默认60，即至少包含匹配）
        verbose: 是否输出详细日志（默认True）

    Returns:
        匹配到的列名，未找到返回None
    """
    if df is None or df.empty:
        if verbose:
            logger.warning("DataFrame为空，无法查找列名")
        return None

    columns = df.columns.tolist()
    if not columns:
        if verbose:
            logger.warning("DataFrame没有列")
        return None

    # 规范化所有列名
    normalized_columns = {col: _normalize_column_name(col) for col in columns}

    best_match = None
    best_score = 0
    best_match_type = None
    all_candidates = []

    # 遍历所有关键词和列名，计算匹配分数
    for keyword in keywords:
        normalized_keyword = keyword.lower().strip()

        for col in columns:
            normalized_col = normalized_columns[col]
            score, match_type = _calculate_match_score(
                normalized_col, normalized_keyword
            )

            if score > 0:
                all_candidates.append(
                    {
                        "column": col,
                        "keyword": keyword,
                        "score": score,
                        "match_type": match_type,
                    }
                )

                # 更新最佳匹配
                if score > best_score:
                    best_match = col
                    best_score = score
                    best_match_type = match_type

    # 输出详细日志
    if verbose and all_candidates:
        # 按分数排序
        all_candidates.sort(key=lambda x: x["score"], reverse=True)

        logger.debug(f"列名匹配候选（关键词: {keywords}）:")
        for i, candidate in enumerate(all_candidates[:5]):  # 只显示前5个
            logger.debug(
                f"  {i + 1}. 列名='{candidate['column']}', "
                f"关键词='{candidate['keyword']}', "
                f"分数={candidate['score']}, "
                f"类型={candidate['match_type']}"
            )

    # 检查最佳匹配是否达到阈值
    if best_score >= min_score:
        if verbose:
            logger.info(
                f"列名匹配成功: '{best_match}' (分数={best_score}, "
                f"类型={best_match_type}, 关键词='{keywords}')"
            )
        return best_match
    else:
        if verbose:
            if best_match:
                logger.warning(
                    f"列名匹配分数过低: '{best_match}' (分数={best_score} < 阈值={min_score}), "
                    f"关键词='{keywords}', 可用列: {columns}"
                )
            else:
                logger.warning(
                    f"未找到匹配的列名，关键词='{keywords}', 可用列: {columns}"
                )
        return None


def normalize_transactions(
    df: pd.DataFrame, source_file: str = None, extract_timestamp: str = None
) -> pd.DataFrame:
    """
    标准化交易数据

    【2026-01-27 修复】添加数据溯源信息（文件名、行号、提取时间）

    Args:
        df: 原始交易DataFrame
        source_file: 源文件名（用于溯源）
        extract_timestamp: 提取时间戳（用于溯源）

    Returns:
        标准化后的DataFrame（包含溯源信息）
    """
    logger.info("正在标准化交易数据...")

    # 【修复】添加空DataFrame检查
    if df is None or df.empty:
        logger.warning("交易数据为空，跳过标准化")
        return pd.DataFrame()

    normalized = pd.DataFrame()

    # 【修复】添加溯源信息
    normalized["_source_file"] = source_file if source_file else "unknown"
    normalized["_source_row"] = df.index
    normalized["_extract_timestamp"] = (
        extract_timestamp if extract_timestamp else datetime.now().isoformat()
    )

    # 查找并映射字段
    date_col = find_column_by_keywords(df, config.DATE_COLUMNS)
    desc_col = find_column_by_keywords(df, config.DESCRIPTION_COLUMNS)
    income_col = find_column_by_keywords(df, config.INCOME_COLUMNS)
    expense_col = find_column_by_keywords(df, config.EXPENSE_COLUMNS)
    counterparty_col = find_column_by_keywords(df, config.COUNTERPARTY_COLUMNS)
    balance_col = find_column_by_keywords(df, config.BALANCE_COLUMNS)

    # 必需字段检查
    if not date_col:
        logger.warning("未找到日期列,尝试使用第一列")
        date_col = df.columns[0]

    if not desc_col:
        logger.warning("未找到摘要列")

    # 标准化日期
    try:
        normalized["date"] = df[date_col].apply(utils.parse_date)
    except Exception as e:
        logger.error(f"日期标准化失败: {str(e)}，使用原始值")
        normalized["date"] = df[date_col]

    # 标准化摘要
    if desc_col:
        try:
            normalized["description"] = df[desc_col].apply(utils.clean_text)
        except Exception as e:
            logger.warning(f"摘要标准化失败: {str(e)}，使用空字符串")
            normalized["description"] = ""
    else:
        normalized["description"] = ""

    # 标准化金额
    if income_col:
        try:
            normalized["income"] = df[income_col].apply(utils.format_amount)
        except Exception as e:
            logger.warning(f"收入金额标准化失败: {str(e)}，使用0")
            normalized["income"] = 0.0
    else:
        normalized["income"] = 0.0

    if expense_col:
        try:
            normalized["expense"] = df[expense_col].apply(utils.format_amount)
        except Exception as e:
            logger.warning(f"支出金额标准化失败: {str(e)}，使用0")
            normalized["expense"] = 0.0
    else:
        normalized["expense"] = 0.0

    # 标准化对手方
    if counterparty_col:
        try:
            normalized["counterparty"] = df[counterparty_col].apply(utils.clean_text)
        except Exception as e:
            logger.warning(f"对手方标准化失败: {str(e)}，使用空字符串")
            normalized["counterparty"] = ""
    else:
        normalized["counterparty"] = ""

    # 标准化余额
    if balance_col:
        try:
            normalized["balance"] = df[balance_col].apply(utils.format_amount)
        except Exception as e:
            logger.warning(f"余额标准化失败: {str(e)}，使用0")
            normalized["balance"] = 0.0
    else:
        normalized["balance"] = 0.0

    # 移除无效行(没有日期的行)
    try:
        normalized = normalized[normalized["date"].notna()]
    except Exception as e:
        logger.warning(f"移除无效行失败: {str(e)}")
        normalized = normalized

    # 按日期排序
    try:
        normalized = normalized.sort_values("date").reset_index(drop=True)
    except Exception as e:
        logger.warning(f"按日期排序失败: {str(e)}")

    logger.info(f"标准化完成,有效交易记录: {len(normalized)} 条")

    return normalized


def read_excel_transactions(excel_path: str) -> pd.DataFrame:
    """
    读取Excel流水文件

    Args:
        excel_path: Excel文件路径

    Returns:
        标准化后的交易DataFrame
    """
    logger.info(f"正在读取Excel流水: {excel_path}")

    # 【修复】添加文件存在性检查
    if not os.path.exists(excel_path):
        logger.error(f"Excel文件不存在: {excel_path}")
        return pd.DataFrame()

    # 【修复】添加文件大小检查
    file_size = os.path.getsize(excel_path)
    if file_size > 100 * 1024 * 1024:  # 100MB
        logger.warning(
            f"Excel文件过大({file_size / 1024 / 1024:.1f}MB)，跳过处理: {excel_path}"
        )
        return pd.DataFrame()

    try:
        # 尝试读取Excel
        df = pd.read_excel(excel_path, encoding="utf-8")  # type: ignore

        # 【修复】添加空DataFrame检查
        if df is None or df.empty:
            logger.warning(f"Excel文件为空: {excel_path}")
            return pd.DataFrame()

        # 跳过可能的标题行(查找包含"日期"或"交易"的行作为表头)
        header_row = 0
        for i in range(min(10, len(df))):
            try:
                row_text = " ".join([str(x) for x in df.iloc[i].values])
                if (
                    "日期" in row_text
                    or "交易" in row_text
                    or "date" in row_text.lower()
                ):
                    header_row = i
                    break
            except Exception as e:
                logger.warning(f"检查表头行{i}失败: {str(e)}")
                continue

        if header_row > 0:
            try:
                df = pd.read_excel(excel_path, header=header_row)
            except Exception as e:
                logger.warning(
                    f"使用表头行{header_row}读取失败: {str(e)}，使用默认表头"
                )

        logger.info(f"读取到 {len(df)} 行原始数据")

        # 标准化数据（添加溯源信息）
        file_basename = os.path.basename(excel_path)
        extract_timestamp = datetime.now().isoformat()
        normalized_df = normalize_transactions(df, file_basename, extract_timestamp)

        logger.info(
            f"数据溯源信息已添加: 文件={file_basename}, 时间={extract_timestamp}"
        )

        return normalized_df

    except Exception as e:
        logger.error(f"读取Excel失败: {excel_path}, 错误: {str(e)}")
        return pd.DataFrame()


def load_all_transactions(
    directory: str, target_names: List[str] = None
) -> Dict[str, pd.DataFrame]:
    """
    加载目录下所有Excel流水文件(支持递归扫描)

    Args:
        directory: 目录路径
        target_names: 目标人员/公司名单，用于文件名匹配(可选)

    Returns:
        字典: {文件名: 交易DataFrame}
    """
    logger.info(f"正在扫描目录(递归): {directory}")

    # 【修复】添加目录存在性检查
    if not os.path.exists(directory):
        logger.error(f"目录不存在: {directory}")
        return {}

    all_transactions = {}
    processed_files = 0
    failed_files = 0

    try:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                # 【修复】添加文件名验证
                if not filename.endswith((".xlsx", ".xls")):
                    continue
                if filename.startswith("~"):
                    continue

                file_path = os.path.join(root, filename)

                # 【修复】添加文件大小检查
                file_size = os.path.getsize(file_path)
                if file_size > 100 * 1024 * 1024:  # 100MB
                    logger.warning(
                        f"文件过大({file_size / 1024 / 1024:.1f}MB)，跳过: {filename}"
                    )
                    continue

                # 检查是否为线索文件或输出文件
                try:
                    if any(
                        keyword in filename for keyword in config.CLUE_FILE_KEYWORDS
                    ):
                        continue
                    if filename == config.OUTPUT_EXCEL_FILE:
                        continue
                except Exception as e:
                    logger.warning(f"检查文件名失败: {filename}, 错误: {str(e)}")

                # 提取文件名作为标识(去除扩展名)
                try:
                    file_key = os.path.splitext(filename)[0]
                    # 如果有重复文件名，添加前缀区分
                    if file_key in all_transactions:
                        parent_dir = os.path.basename(root)
                        file_key = f"{parent_dir}_{file_key}"
                except Exception as e:
                    logger.warning(f"生成文件标识失败: {filename}, 错误: {str(e)}")
                    file_key = filename

                # 【修复】添加错误处理，单个文件失败不影响整体
                try:
                    df = read_excel_transactions(file_path)

                    if not df.empty:
                        all_transactions[file_key] = df
                        logger.info(f"已加载: {file_path}, 记录数: {len(df)}")
                        processed_files += 1
                    else:
                        logger.warning(f"文件为空: {file_path}")
                        failed_files += 1
                except Exception as e:
                    logger.error(f"处理文件失败: {file_path}, 错误: {str(e)}")
                    failed_files += 1

        logger.info(
            f"共加载 {len(all_transactions)} 个流水文件 (成功: {processed_files}, 失败: {failed_files})"
        )

    except Exception as e:
        logger.error(f"扫描目录失败: {directory}, 错误: {str(e)}")

    return all_transactions


def find_clue_files(directory: str) -> List[str]:
    """
    递归查找目录下的线索PDF文件

    Args:
        directory: 目录路径

    Returns:
        PDF文件路径列表
    """
    logger.info(f"正在递归查找线索文件: {directory}")

    # 【修复】添加目录存在性检查
    if not os.path.exists(directory):
        logger.error(f"目录不存在: {directory}")
        return []

    clue_files = []
    processed_files = 0
    failed_files = 0

    try:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                # 【修复】添加文件名验证
                if not filename.endswith(".pdf"):
                    continue

                file_path = os.path.join(root, filename)

                # 【修复】添加文件大小检查
                file_size = os.path.getsize(file_path)
                if file_size > 50 * 1024 * 1024:  # 50MB
                    logger.warning(
                        f"PDF文件过大({file_size / 1024 / 1024:.1f}MB)，跳过: {filename}"
                    )
                    continue

                # 【修复】添加文件可读性检查
                if not os.access(file_path, os.R_OK):
                    logger.warning(f"PDF文件不可读: {filename}")
                    continue

                # 检查是否包含线索关键词
                try:
                    if any(
                        keyword in filename for keyword in config.CLUE_FILE_KEYWORDS
                    ):
                        clue_files.append(file_path)
                        logger.info(f"找到线索文件: {file_path}")
                        processed_files += 1
                except Exception as e:
                    logger.warning(f"检查文件名失败: {filename}, 错误: {str(e)}")
                    failed_files += 1

        logger.info(
            f"共找到 {len(clue_files)} 个线索文件 (成功: {processed_files}, 失败: {failed_files})"
        )

    except Exception as e:
        logger.error(f"查找线索文件失败: {directory}, 错误: {str(e)}")

    return clue_files


def extract_all_clues(directory: str) -> Tuple[List[str], List[str]]:
    """
    提取目录下所有线索文件中的人员和公司名单

    Args:
        directory: 目录路径

    Returns:
        (核心人员列表, 涉案公司列表)
    """
    logger.info(f"正在提取所有线索: {directory}")

    # 【修复】添加目录存在性检查
    if not os.path.exists(directory):
        logger.error(f"目录不存在: {directory}")
        return [], []

    clue_files = find_clue_files(directory)

    # 【修复】添加错误恢复机制，即使部分PDF失败也不影响整体
    all_persons = set()
    all_companies = set()
    processed_files = 0
    failed_files = 0

    for clue_file in clue_files:
        try:
            persons, companies = extract_clues_from_pdf(clue_file)
            all_persons.update(persons)
            all_companies.update(companies)
            processed_files += 1
        except Exception as e:
            logger.error(f"提取线索文件失败: {clue_file}, 错误: {str(e)}")
            failed_files += 1

    logger.info(
        f"汇总提取: {len(all_persons)} 个人名, {len(all_companies)} 个公司名 (成功: {processed_files}, 失败: {failed_files})"
    )

    return list(all_persons), list(all_companies)


def get_transactions_by_entity(
    all_transactions: Dict[str, pd.DataFrame], entity_name: str
) -> pd.DataFrame:
    """
    获取特定人员或公司的所有交易记录

    Args:
        all_transactions: 所有交易数据字典
        entity_name: 人员或公司名称

    Returns:
        该实体的交易DataFrame
    """
    # 【修复】添加参数验证
    if not all_transactions:
        logger.warning("交易数据为空")
        return pd.DataFrame()

    if not entity_name:
        logger.warning("实体名称为空")
        return pd.DataFrame()

    # 查找文件名包含该实体名称的流水
    matching_dfs = []

    for file_key, df in all_transactions.items():
        try:
            if entity_name in file_key:
                matching_dfs.append(df)
        except Exception as e:
            logger.warning(f"匹配实体{entity_name}失败: {file_key}, 错误: {str(e)}")

    if matching_dfs:
        try:
            combined = pd.concat(matching_dfs, ignore_index=True)
            combined = combined.sort_values("date").reset_index(drop=True)
            return combined
        except Exception as e:
            logger.error(f"合并交易数据失败: {entity_name}, 错误: {str(e)}")
            return pd.DataFrame()

    return pd.DataFrame()
