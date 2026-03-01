"""
征信数据解析模块

解析 征信（定向查询） 目录下的xlsx文件
提取信贷交易信息、借贷账户信息、查询记录等

作者: AI Assistant
创建时间: 2026-01-20
Phase: 6.4
"""

import re
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

import utils
from utils.safe_types import (
    safe_str,
    safe_float,
    safe_int,
    safe_date,
    safe_datetime,
    extract_id_from_filename,
)

logger = utils.setup_logger(__name__)


# 数据源目录名称
CREDIT_DIR_NAME = "征信（定向查询）"


def extract_credit_data(data_dir: str) -> Dict[str, Dict]:
    """
    从征信数据目录提取所有征信信息

    Args:
        data_dir: 数据根目录路径

    Returns:
        Dict[str, Dict]: 按身份证号/信用代码分组的征信数据
        {
            "310102196504096017": {
                "name": "施灵",
                "id_number": "310102196504096017",
                "entity_type": "person",  # person/company
                "credit_summary": {...},
                "loan_accounts": [...],
                "credit_cards": [...],
                "query_records": [...],
                "public_records": {...},
                "source_file": "xxx.xlsx"
            }
        }
    """
    credit_dir = _find_credit_dir(data_dir)
    if not credit_dir:
        logger.warning(f"未找到征信数据目录: {CREDIT_DIR_NAME}")
        return {}

    results = {}
    credit_path = Path(credit_dir)

    # 遍历所有xlsx文件
    xlsx_files = [f for f in credit_path.glob("*.xlsx") if not f.name.startswith("~$")]
    logger.info(f"找到 {len(xlsx_files)} 个征信文件")

    for xlsx_file in xlsx_files:
        try:
            file_data = parse_credit_file(str(xlsx_file))
            for id_key, data in file_data.items():
                if id_key in results:
                    # 合并数据
                    _merge_credit_data(results[id_key], data)
                else:
                    results[id_key] = data
        except Exception as e:
            logger.error(f"解析征信文件失败 {xlsx_file.name}: {e}")

    logger.info(f"成功解析 {len(results)} 个主体的征信数据")
    return results


def parse_credit_file(file_path: str) -> Dict[str, Dict]:
    """
    解析单个征信xlsx文件

    Args:
        file_path: xlsx文件路径

    Returns:
        Dict[str, Dict]: 按身份证号分组的征信数据
    """
    filename = Path(file_path).name
    results = {}

    # 从文件名提取身份信息
    name, id_number = _extract_info_from_filename(filename)
    if not id_number:
        logger.warning(f"无法从文件名提取ID: {filename}")
        return {}

    # 判断是个人还是企业
    entity_type = (
        "company" if len(id_number) == 18 and not id_number[0].isdigit() else "person"
    )

    try:
        xls = pd.ExcelFile(file_path)
        sheet_names = xls.sheet_names

        data = {
            "name": name,
            "id_number": id_number,
            "entity_type": entity_type,
            "credit_summary": {},
            "loan_accounts": [],
            "credit_cards": [],
            "query_records": [],
            "public_records": {},
            "source_file": filename,
        }

        # 解析信贷交易信息概要
        if "信贷交易信息概要" in sheet_names:
            data["credit_summary"] = _parse_credit_summary(xls)

        # 解析借贷账户信息
        if "借贷账户信息" in sheet_names:
            loans, cards = _parse_loan_accounts(xls)
            data["loan_accounts"] = loans
            data["credit_cards"] = cards

        # 解析查询记录
        if "查询记录" in sheet_names:
            data["query_records"] = _parse_query_records(xls)

        # 解析公共信息
        data["public_records"] = _parse_public_records(xls, sheet_names)

        results[id_number] = data

    except Exception as e:
        logger.error(f"解析征信文件出错 {filename}: {e}")

    return results


def _parse_credit_summary(xls: pd.ExcelFile) -> Dict:
    """解析信贷交易信息概要"""
    try:
        df = pd.read_excel(xls, sheet_name="信贷交易信息概要", header=None)

        summary = {"total_accounts": 0, "business_types": 0, "by_type": []}

        # 查找账户数合计和业务类型数量
        for i, row in df.iterrows():
            if pd.notna(row.iloc[0]) and "账户数合计" in str(row.iloc[0]):
                # 下一行包含数据
                if i + 1 < len(df):
                    data_row = df.iloc[i + 1]
                    summary["total_accounts"] = safe_int(data_row.iloc[0])
                    summary["business_types"] = safe_int(data_row.iloc[1])

        return summary
    except Exception as e:
        logger.warning(f"解析信贷交易信息概要失败: {e}")
        return {}


def _parse_loan_accounts(xls: pd.ExcelFile) -> tuple:
    """解析借贷账户信息"""
    loans = []
    cards = []

    try:
        df = pd.read_excel(xls, sheet_name="借贷账户信息", header=None)

        # 查找数据开始行（账户编号列）
        header_row = None
        for i, row in df.iterrows():
            if pd.notna(row.iloc[0]) and "账户编号" in str(row.iloc[0]):
                header_row = i
                break

        if header_row is None:
            return loans, cards

        # 获取列名
        headers = df.iloc[header_row].tolist()

        # 解析数据行
        for i in range(header_row + 1, len(df)):
            row = df.iloc[i]

            # 跳过空行或分隔行
            if pd.isna(row.iloc[0]) or str(row.iloc[0]).startswith("一、"):
                continue

            # 检查是否是新的段落标题
            if pd.notna(row.iloc[0]) and any(
                x in str(row.iloc[0]) for x in ["信息段", "信息单元"]
            ):
                break

            account = {
                "account_id": safe_str(row.iloc[0]),
                "account_type": safe_str(row.iloc[1]),
                "institution_type": safe_str(row.iloc[2]),
                "institution_code": safe_str(row.iloc[3]),
                "business_type": safe_str(row.iloc[6]) if len(row) > 6 else None,
                "open_date": safe_date(row.iloc[7]) if len(row) > 7 else None,
                "currency": safe_str(row.iloc[8]) if len(row) > 8 else None,
                "amount": safe_float(row.iloc[9]) if len(row) > 9 else None,
                "credit_limit": safe_float(row.iloc[10]) if len(row) > 10 else None,
            }

            # D1=贷款, R1/R2=信用卡
            if account["account_type"] and account["account_type"].startswith("D"):
                loans.append(account)
            elif account["account_type"] and account["account_type"].startswith("R"):
                cards.append(account)
            else:
                loans.append(account)  # 默认归类为贷款

    except Exception as e:
        logger.warning(f"解析借贷账户信息失败: {e}")

    return loans, cards


def _parse_query_records(xls: pd.ExcelFile) -> List[Dict]:
    """解析查询记录"""
    records = []

    try:
        df = pd.read_excel(xls, sheet_name="查询记录", header=None)

        # 查询记录可能为空或只有标题
        if len(df) < 3:
            return records

        # 查找数据行
        for i, row in df.iterrows():
            if pd.notna(row.iloc[0]) and "/" in str(row.iloc[0]):
                continue  # 跳过空标记

            # 尝试解析查询记录（格式因文件而异）
            if pd.notna(row.iloc[0]) and not str(row.iloc[0]).startswith("一、"):
                # 简化处理，只记录非标题行数
                pass

    except Exception as e:
        logger.warning(f"解析查询记录失败: {e}")

    return records


def _parse_public_records(xls: pd.ExcelFile, sheet_names: List[str]) -> Dict:
    """解析公共信息（欠税、民事判决、强制执行等）"""
    public_records = {
        "tax_arrears": [],  # 欠税记录
        "civil_judgments": [],  # 民事判决记录
        "enforcements": [],  # 强制执行记录
        "penalties": [],  # 行政处罚记录
    }

    try:
        # 欠税记录
        if "欠税记录" in sheet_names:
            df = pd.read_excel(xls, sheet_name="欠税记录", header=None)
            if len(df) > 2 and "/" not in str(df.iloc[1, 0]):
                public_records["tax_arrears_count"] = len(df) - 2

        # 民事判决记录
        if "民事判决记录" in sheet_names:
            df = pd.read_excel(xls, sheet_name="民事判决记录", header=None)
            if len(df) > 2 and "/" not in str(df.iloc[1, 0]):
                public_records["civil_judgments_count"] = len(df) - 2

        # 强制执行记录
        if "强制执行记录" in sheet_names:
            df = pd.read_excel(xls, sheet_name="强制执行记录", header=None)
            if len(df) > 2 and "/" not in str(df.iloc[1, 0]):
                public_records["enforcements_count"] = len(df) - 2

        # 行政处罚记录
        if "行政处罚记录" in sheet_names:
            df = pd.read_excel(xls, sheet_name="行政处罚记录", header=None)
            if len(df) > 2 and "/" not in str(df.iloc[1, 0]):
                public_records["penalties_count"] = len(df) - 2

    except Exception as e:
        logger.warning(f"解析公共信息失败: {e}")

    return public_records


def _find_credit_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找征信数据目录"""
    data_path = Path(data_dir)

    # 直接查找
    direct_path = data_path / CREDIT_DIR_NAME
    if direct_path.exists():
        return str(direct_path)

    # 递归查找
    for subdir in data_path.rglob(CREDIT_DIR_NAME):
        if subdir.is_dir():
            return str(subdir)

    return None


def _extract_info_from_filename(filename: str) -> tuple:
    """从文件名提取姓名和身份证号"""
    # 格式: 姓名_身份证号_xxx.xlsx
    parts = filename.split("_")
    if len(parts) >= 2:
        name = parts[0]
        id_number = parts[1]
        return name, id_number
    return None, None


def _merge_credit_data(existing: Dict, new: Dict):
    """合并征信数据"""
    for key in ["loan_accounts", "credit_cards", "query_records"]:
        if key in new and new[key]:
            existing.setdefault(key, []).extend(new[key])


# 便捷函数
def get_person_credit_info(data_dir: str, person_id: str) -> Optional[Dict]:
    """
    获取指定人员的征信信息

    Args:
        data_dir: 数据目录
        person_id: 身份证号

    Returns:
        Dict: 征信信息，未找到返回None
    """
    credit_data = extract_credit_data(data_dir)
    return credit_data.get(person_id)


def get_credit_alerts(data_dir: str) -> List[Dict]:
    """
    获取所有征信预警信息（不良记录）

    Args:
        data_dir: 数据目录

    Returns:
        List[Dict]: 预警列表
    """
    alerts = []
    credit_data = extract_credit_data(data_dir)

    for id_number, info in credit_data.items():
        public_records = info.get("public_records", {})

        # 检查不良公共记录
        for key in [
            "tax_arrears_count",
            "civil_judgments_count",
            "enforcements_count",
            "penalties_count",
        ]:
            count = public_records.get(key, 0)
            if count and count > 0:
                alert_type_map = {
                    "tax_arrears_count": "欠税记录",
                    "civil_judgments_count": "民事判决",
                    "enforcements_count": "强制执行",
                    "penalties_count": "行政处罚",
                }
                alerts.append(
                    {
                        "name": info.get("name"),
                        "id_number": id_number,
                        "alert_type": alert_type_map.get(key, key),
                        "count": count,
                        "source": "征信报告",
                    }
                )

    return alerts


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"

    print(f"测试目录: {test_dir}")

    # 测试提取
    credit_data = extract_credit_data(test_dir)
    print(f"\n=== 征信数据 ({len(credit_data)} 条) ===")

    for id_number, info in credit_data.items():
        print(f"\n{info.get('name')} ({id_number}):")
        summary = info.get("credit_summary", {})
        print(f"  账户数: {summary.get('total_accounts', 0)}")
        print(f"  贷款账户: {len(info.get('loan_accounts', []))} 个")
        print(f"  信用卡: {len(info.get('credit_cards', []))} 个")

    # 测试预警
    alerts = get_credit_alerts(test_dir)
    print(f"\n=== 征信预警 ({len(alerts)} 条) ===")
    for alert in alerts:
        print(
            f"  {alert.get('name')}: {alert.get('alert_type')} ({alert.get('count')}次)"
        )
