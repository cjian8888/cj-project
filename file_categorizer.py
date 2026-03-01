#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件分类器 - 资金穿透与关联排查系统
负责智能识别和分类各类数据文件
"""

import os
import re
from typing import Dict, List
import utils

logger = utils.setup_logger(__name__)

# 预编译的正则表达式模块级常量
ID_CARD_PATTERN = re.compile(r"^\d{15}$|^\d{17}[\dXx]$")
USCC_PATTERN = re.compile(r"^[0-9A-HJ-NP-RTUW-Y]{2}\d{6}[0-9A-HJ-NP-RTUW-Y]{10}$")


def parse_filename_info(filename: str) -> Dict:
    """
    从文件名解析信息

    文件名格式示例:
    - 标准格式: 甲某某_340825200107190410_国监查【2025】第030696号_中国工商银行交易流水.xlsx
    - 标准格式: XX科技有限公司_91520303MAAK4M2U3H_国监查【2025】第030696号_中国银行交易流水.xlsx
    - 简单格式: 流水_测试人员.xlsx
    - 简单格式: 测试人员.xlsx

    Args:
        filename: 文件名

    Returns:
        解析后的信息字典
    """
    info = {
        "filename": filename,
        "entity_name": None,
        "entity_id": None,  # 身份证号或统一社会信用代码
        "entity_type": None,  # 'person' or 'company'
        "data_type": None,  # 'transaction', 'account', 'other'
        "bank_name": None,
        "category": None,  # 数据类别(如"银行业金融机构交易流水")
    }

    # 移除扩展名
    name_without_ext = os.path.splitext(filename)[0]

    # 识别数据类型
    if "交易流水" in filename or "流水" in filename:
        info["data_type"] = "transaction"
    elif "账户信息" in filename or "账户" in filename:
        info["data_type"] = "account"
    elif "理财" in filename:
        info["data_type"] = "financial_product"
    else:
        info["data_type"] = "other"

    # 按下划线分割
    parts = name_without_ext.split("_")

    # 尝试解析标准格式（包含身份证号或统一社会信用代码）
    if len(parts) >= 2:
        # 第一部分可能是"流水"等前缀，也可能是姓名/公司名
        first_part = parts[0]
        second_part = parts[1]

        # 判断第二部分是否是身份证号或统一社会信用代码
        # 使用模块级预编译正则: ID_CARD_PATTERN, USCC_PATTERN

        # 有效的身份证省份代码前两位
        valid_province_codes = [
            "11",
            "12",
            "13",
            "14",
            "15",  # 北京、天津、河北、山西、内蒙古
            "21",
            "22",
            "23",  # 辽宁、吉林、黑龙江
            "31",
            "32",
            "33",
            "35",
            "36",
            "37",  # 上海、江苏、浙江、福建、江西、山东
            "41",
            "42",
            "43",
            "44",
            "45",
            "46",  # 河南、湖北、湖南、广东、广西、海南
            "50",
            "51",
            "52",
            "53",  # 重庆、四川、贵州、云南
            "54",  # 西藏（实际使用54，相当于原34改为54）
            "61",
            "62",
            "63",
            "64",
            "65",  # 陕西、甘肃、青海、宁夏、新疆
            "71",
            "81",
            "82",  # 台湾、香港、澳门
        ]

        # 判断是否是有效身份证号（必须以有效省份代码开头）
        def is_valid_id_card(code):
            if not ID_CARD_PATTERN.match(code):
                return False
            return code[:2] in valid_province_codes

        # 判断是否是有效的统一社会信用代码
        # USCC通常包含字母，且前两位是登记管理部门代码(91/92/93等)
        # 但要排除那些匹配身份证号格式的纯数字情况
        def is_valid_uscc(code):
            if not USCC_PATTERN.match(code):
                return False
            # 如果是纯数字，且前两位是有效省份代码，则认为是身份证号
            if code.isdigit() and code[:2] in valid_province_codes:
                return False
            # 如果前两位是91/92/93等登记管理部门代码，是USCC
            uscc_dept_codes = [
                "11",
                "12",
                "13",
                "91",
                "92",
                "93",
                "A1",
                "N1",
                "N2",
                "N3",
                "Y1",
            ]
            if code[:2] in uscc_dept_codes:
                return True
            # 如果包含字母，也认为是USCC
            if not code.isdigit():
                return True
            return False

        # 先检查身份证号（使用严格的省份代码验证）
        if is_valid_id_card(second_part):
            # 身份证号 - 第一部分是姓名
            info["entity_name"] = first_part
            info["entity_type"] = "person"
            info["entity_id"] = second_part
        elif is_valid_uscc(second_part):
            # 统一社会信用代码 - 第一部分是公司名
            info["entity_name"] = first_part
            info["entity_type"] = "company"
            info["entity_id"] = second_part
        else:
            # 简单格式：流水_姓名 或 流水_公司名
            if first_part in ["流水", "账户", "理财"]:
                # 第二部分是实体名称
                info["entity_name"] = second_part
            else:
                # 第一部分是实体名称
                info["entity_name"] = first_part

            # 通过关键词判断是个人还是公司
            entity_name = info["entity_name"]
            company_keywords = [
                "公司",
                "有限",
                "集团",
                "企业",
                "科技",
                "投资",
                "贸易",
                "实业",
            ]
            if any(kw in entity_name for kw in company_keywords):
                info["entity_type"] = "company"
            else:
                info["entity_type"] = "person"
    elif len(parts) == 1:
        # 单一部分：直接是姓名或公司名
        info["entity_name"] = parts[0]

        # 通过关键词判断是个人还是公司
        company_keywords = [
            "公司",
            "有限",
            "集团",
            "企业",
            "科技",
            "投资",
            "贸易",
            "实业",
        ]
        if any(kw in info["entity_name"] for kw in company_keywords):
            info["entity_type"] = "company"
        else:
            info["entity_type"] = "person"

    # 识别银行
    info["bank_name"] = utils.extract_bank_name(filename)

    return info


def categorize_files(directory: str) -> Dict[str, List[str]]:
    """
    分类目录下的所有文件

    Args:
        directory: 目录路径

    Returns:
        分类后的文件字典
    """
    logger.info(f"开始分类文件: {directory}")

    categorized = {
        "persons": {},  # {person_name: [file_list]}
        "companies": {},  # {company_name: [file_list]}
        "transaction_files": [],  # 所有流水文件
        "account_files": [],  # 所有账户信息文件
        "other_files": [],  # 其他文件
    }

    # 遍历目录
    for root, dirs, files in os.walk(directory):
        # 排除输出目录
        if (
            "output" in root.split(os.sep)
            or "cleaned_data" in root.split(os.sep)
            or "analysis_results" in root.split(os.sep)
        ):
            continue

        for filename in files:
            if not filename.endswith((".xlsx", ".xls")):
                continue

            if filename.startswith("~"):  # 跳过临时文件
                continue

            # 跳过生成的合并文件
            if "合并流水" in filename:
                continue

            filepath = os.path.join(root, filename)

            # 解析文件名
            info = parse_filename_info(filename)

            # 按类型分类
            if info["data_type"] == "transaction":
                categorized["transaction_files"].append(filepath)

                # 按实体分类
                if info["entity_type"] == "person" and info["entity_name"]:
                    if info["entity_name"] not in categorized["persons"]:
                        categorized["persons"][info["entity_name"]] = []
                    categorized["persons"][info["entity_name"]].append(filepath)

                elif info["entity_type"] == "company" and info["entity_name"]:
                    if info["entity_name"] not in categorized["companies"]:
                        categorized["companies"][info["entity_name"]] = []
                    categorized["companies"][info["entity_name"]].append(filepath)

            elif info["data_type"] == "account":
                categorized["account_files"].append(filepath)
            else:
                categorized["other_files"].append(filepath)

    # 统计
    logger.info(f"文件分类完成:")
    logger.info(f"  核心人员: {len(categorized['persons'])} 人")
    for person, files in categorized["persons"].items():
        logger.info(f"    - {person}: {len(files)} 个流水文件")

    logger.info(f"  涉案公司: {len(categorized['companies'])} 家")
    for company, files in categorized["companies"].items():
        logger.info(f"    - {company}: {len(files)} 个流水文件")

    logger.info(f"  流水文件总计: {len(categorized['transaction_files'])}")
    logger.info(f"  账户文件总计: {len(categorized['account_files'])}")
    logger.info(f"  其他文件: {len(categorized['other_files'])}")

    return categorized


def get_entity_files(entity_name: str, all_files: List[str]) -> List[str]:
    """
    获取特定实体的所有文件

    Args:
        entity_name: 实体名称
        all_files: 所有文件列表

    Returns:
        该实体的文件列表
    """
    entity_files = []

    for filepath in all_files:
        filename = os.path.basename(filepath)
        info = parse_filename_info(filename)

        if info["entity_name"] == entity_name:
            entity_files.append(filepath)

    return entity_files
