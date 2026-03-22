#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国税登记与纳税信息提取模块

解析 `国税（定向查询）` 目录下的 xlsx 文件，提取：
- 登记信息
- 个人工作单位 / 企业登记补充信息
- 纳税记录
"""

from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

import utils
from utils.safe_types import safe_date, safe_float, safe_str


logger = utils.setup_logger(__name__)


TAX_DIR_NAME = "国税（定向查询）"


def _normalize_identifier(value) -> str:
    """规整身份证号 / 统一社会信用代码 / 手机号等标识字段。"""
    text = safe_str(value)
    if not text:
        return ""
    text = text.upper()
    if re.fullmatch(r"\d{17}[\dX]", text):
        return text
    try:
        numeric = float(text)
        if numeric.is_integer():
            return str(int(numeric))
    except (TypeError, ValueError):
        pass
    return text


def _extract_subject_from_filename(filename: str) -> Tuple[str, str]:
    """从文件名提取主体名称和主体证件号。"""
    parts = Path(filename).stem.split("_")
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip().upper()
    return "", ""


def _find_tax_dirs(data_dir: str) -> List[str]:
    data_path = Path(data_dir)
    matched_dirs = sorted(
        {
            str(path)
            for path in data_path.rglob("*")
            if path.is_dir() and TAX_DIR_NAME in path.name
        }
    )
    return matched_dirs


def _dedupe_tax_records(records: List[Dict]) -> List[Dict]:
    seen = set()
    deduped = []
    for record in records:
        key = (
            safe_str(record.get("period_start")),
            safe_str(record.get("period_end")),
            safe_str(record.get("tax_name")),
            safe_str(record.get("item_name")),
            round(float(record.get("amount", 0) or 0), 2),
            safe_str(record.get("source_file")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _dedupe_named_rows(rows: List[Dict]) -> List[Dict]:
    seen = set()
    deduped = []
    for row in rows:
        key = (
            safe_str(row.get("name")),
            safe_str(row.get("role")),
            safe_str(row.get("id_number")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _parse_registration_sheet(
    df: pd.DataFrame, subject_name: str, subject_id: str
) -> Tuple[Dict, List[Dict]]:
    registration = {
        "name": subject_name,
        "subject_id": subject_id,
    }
    related_rows: List[Dict] = []
    if df.empty:
        return registration, related_rows

    columns = list(df.columns)
    first_row = df.iloc[0].to_dict()
    if "机构名称" in columns or "纳税人名称" in columns:
        registration.update(
            {
                "name": safe_str(first_row.get("机构名称"))
                or safe_str(first_row.get("纳税人名称"))
                or subject_name,
                "subject_id": _normalize_identifier(
                    first_row.get("社会信用代码")
                    or first_row.get("机构证件号码")
                    or first_row.get("纳税人识别号")
                    or subject_id
                ),
                "status": safe_str(first_row.get("纳税人状态名称")),
                "registered_at": safe_date(first_row.get("登记日期")),
                "address": safe_str(first_row.get("注册地址"))
                or safe_str(first_row.get("生产经营地址")),
                "legal_representative": safe_str(first_row.get("法定代表人姓名")),
            }
        )
    else:
        registration.update(
            {
                "name": safe_str(first_row.get("姓名")) or subject_name,
                "subject_id": _normalize_identifier(
                    first_row.get("证件号码") or subject_id
                ),
                "taxpayer_id": _normalize_identifier(first_row.get("纳税人识别号")),
                "address": safe_str(first_row.get("居住地址")),
                "phone": _normalize_identifier(first_row.get("电话号码")),
            }
        )

    if len(columns) >= 3:
        first_col, second_col, third_col = columns[:3]
        for idx, row in df.iterrows():
            if idx == 0:
                continue
            seq_text = safe_str(row.get(first_col))
            name_text = safe_str(row.get(second_col))
            role_text = safe_str(row.get(third_col))
            id_text = _normalize_identifier(row.get(columns[3])) if len(columns) >= 4 else ""
            if seq_text in {"", "序号"}:
                continue
            if not name_text or name_text in {"单位名称", "投资方（合伙人）名称"}:
                continue
            related_rows.append(
                {
                    "name": name_text,
                    "role": role_text,
                    "id_number": id_text,
                }
            )

    return registration, _dedupe_named_rows(related_rows)


def _parse_tax_sheet(
    df: pd.DataFrame, subject_name: str, subject_id: str, source_file: str
) -> List[Dict]:
    if df.empty:
        return []

    records = []
    for _, row in df.iterrows():
        tax_name = safe_str(row.get("税种名称")) or safe_str(row.get("征收项目名称"))
        item_name = safe_str(row.get("征收品目名称")) or safe_str(row.get("征收品目"))
        period_start = safe_date(row.get("税款所属期始") or row.get("税款所属期起"))
        period_end = safe_date(row.get("税款所属期止"))
        amount = safe_float(
            row.get("应纳税额")
            or row.get("应补（退）税额")
            or row.get("应补(退)税额")
            or 0
        ) or 0.0

        if not any([tax_name, item_name, period_start, period_end, amount]):
            continue

        records.append(
            {
                "subject_name": safe_str(row.get("纳税人名称")) or subject_name,
                "subject_id": safe_str(row.get("社会信用代码"))
                or safe_str(row.get("纳税人识别号"))
                or subject_id,
                "period_start": period_start,
                "period_end": period_end,
                "tax_name": tax_name,
                "item_name": item_name,
                "amount": amount,
                "tax_basis": safe_float(row.get("计税依据")) or 0.0,
                "tax_rate": safe_float(row.get("税率")) or 0.0,
                "paid_at": safe_date(row.get("入库日期")),
                "source_file": source_file,
            }
        )

    return _dedupe_tax_records(records)


def parse_tax_file(file_path: str) -> Optional[Dict]:
    filename = Path(file_path).name
    subject_name, subject_id = _extract_subject_from_filename(filename)
    if not subject_id:
        return None

    result = {
        "name": subject_name,
        "subject_id": subject_id,
        "registration": {},
        "employers": [],
        "tax_records": [],
    }

    try:
        xls = pd.ExcelFile(file_path)
    except Exception as e:
        logger.error(f"读取税务文件失败 {filename}: {e}")
        return None

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)
        except Exception as e:
            logger.error(f"读取税务sheet失败 {filename}#{sheet_name}: {e}")
            continue

        if "登记信息" in sheet_name:
            registration, related_rows = _parse_registration_sheet(
                df, subject_name, subject_id
            )
            if registration:
                result["registration"] = registration
                result["name"] = registration.get("name") or result["name"]
                result["subject_id"] = registration.get("subject_id") or result["subject_id"]
            result["employers"].extend(related_rows)
        elif "税务缴纳" in sheet_name:
            result["tax_records"].extend(
                _parse_tax_sheet(df, subject_name, subject_id, filename)
            )

    result["employers"] = _dedupe_named_rows(result["employers"])
    result["tax_records"] = _dedupe_tax_records(result["tax_records"])
    return result


def extract_tax_data(data_dir: str, subject_id: str = None) -> Dict[str, Dict]:
    """提取全部税务数据，按主体证件号分组。"""
    tax_dirs = _find_tax_dirs(data_dir)
    if not tax_dirs:
        logger.warning(f"未找到税务目录: {TAX_DIR_NAME}")
        return {}

    results: Dict[str, Dict] = {}
    for tax_dir in tax_dirs:
        tax_path = Path(tax_dir)
        xlsx_files = [f for f in tax_path.glob("*.xlsx") if not f.name.startswith("~$")]
        for xlsx_file in xlsx_files:
            file_subject_name, file_subject_id = _extract_subject_from_filename(xlsx_file.name)
            if subject_id and file_subject_id != subject_id:
                continue

            file_data = parse_tax_file(str(xlsx_file))
            if not file_data:
                continue

            key = file_data.get("subject_id") or file_subject_id
            if not key:
                continue

            if key not in results:
                results[key] = {
                    "name": file_data.get("name") or file_subject_name,
                    "subject_id": key,
                    "registration": file_data.get("registration", {}),
                    "employers": list(file_data.get("employers", [])),
                    "tax_records": list(file_data.get("tax_records", [])),
                }
            else:
                if not results[key].get("registration") and file_data.get("registration"):
                    results[key]["registration"] = file_data.get("registration", {})
                results[key]["employers"].extend(file_data.get("employers", []))
                results[key]["tax_records"].extend(file_data.get("tax_records", []))

    for key, payload in results.items():
        payload["employers"] = _dedupe_named_rows(payload.get("employers", []))
        payload["tax_records"] = _dedupe_tax_records(payload.get("tax_records", []))
        if not payload.get("name"):
            payload["name"] = key

    logger.info(f"税务数据解析完成，共 {len(results)} 个主体")
    return results


if __name__ == "__main__":
    import sys

    test_dir = sys.argv[1] if len(sys.argv) > 1 else "./data"
    tax_data = extract_tax_data(test_dir)
    print(f"税务主体数: {len(tax_data)}")
