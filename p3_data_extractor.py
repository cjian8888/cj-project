"""
P3级外部数据解析模块

解析低优先级外部数据源：
- 公安部驾驶证（定向查询）
- 公安部交通违法（定向查询）
- 公安部出国（境）证件（定向查询）
- 铁路总公司互联网注册信息（定向查询）

作者: AI Assistant
创建时间: 2026-01-21
Phase: 9 (P3级)
"""

import re
from typing import Dict, List, Optional
from pathlib import Path

import pandas as pd

import utils
from utils.safe_types import (
    safe_str,
    safe_float,
    safe_int,
    safe_date,
    safe_datetime,
)

logger = utils.setup_logger(__name__)


# ============================================
# 9.1 公安部驾驶证解析
# ============================================

DRIVER_LICENSE_DIR_NAME = "公安部驾驶证（定向查询）"


def extract_driver_license_data(data_dir: str) -> Dict[str, Dict]:
    """
    从驾驶证目录提取所有驾驶证信息
    
    Args:
        data_dir: 数据根目录路径
        
    Returns:
        {身份证号: {驾驶证信息}}
    """
    result = {}
    
    license_dir = _find_data_dir(data_dir, DRIVER_LICENSE_DIR_NAME)
    if not license_dir:
        logger.info(f"未找到驾驶证目录: {DRIVER_LICENSE_DIR_NAME}")
        return result
    
    for file_path in license_dir.glob("*.xlsx"):
        if file_path.name.startswith("~$"):
            continue
        
        try:
            person_id = _extract_id_from_filename(file_path.name)
            data = _parse_driver_license_file(str(file_path))
            if person_id and data:
                result[person_id] = data
                logger.info(f"解析驾驶证信息: {person_id}")
        except Exception as e:
            logger.warning(f"解析驾驶证文件失败 {file_path.name}: {e}")
    
    return result


def _parse_driver_license_file(file_path: str) -> Dict:
    """解析单个驾驶证xlsx文件"""
    try:
        df = pd.read_excel(file_path)
        if df.empty:
            return {}
        
        # 提取驾驶证信息
        info = {
            "source_file": Path(file_path).name,
            "license_number": safe_str(df.iloc[0].get("证号", df.iloc[0].get("档案编号", ""))),
            "license_type": safe_str(df.iloc[0].get("准驾车型", "")),
            "issue_date": safe_date(df.iloc[0].get("初次领证日期", "")),
            "valid_from": safe_date(df.iloc[0].get("有效起始日期", "")),
            "valid_until": safe_date(df.iloc[0].get("有效期止", df.iloc[0].get("有效截止日期", ""))),
            "status": safe_str(df.iloc[0].get("状态", df.iloc[0].get("证件状态", "正常"))),
        }
        
        return info
    except Exception as e:
        logger.warning(f"解析驾驶证文件失败: {e}")
        return {}


# ============================================
# 9.2 公安部交通违法解析
# ============================================

TRAFFIC_VIOLATION_DIR_NAME = "公安部交通违法（定向查询）"


def extract_traffic_violation_data(data_dir: str) -> Dict[str, List[Dict]]:
    """
    从交通违法目录提取所有违法记录
    
    Args:
        data_dir: 数据根目录路径
        
    Returns:
        {身份证号: [违法记录列表]}
    """
    result = {}
    
    violation_dir = _find_data_dir(data_dir, TRAFFIC_VIOLATION_DIR_NAME)
    if not violation_dir:
        logger.info(f"未找到交通违法目录: {TRAFFIC_VIOLATION_DIR_NAME}")
        return result
    
    for file_path in violation_dir.glob("*.xlsx"):
        if file_path.name.startswith("~$"):
            continue
        
        try:
            person_id = _extract_id_from_filename(file_path.name)
            records = _parse_traffic_violation_file(str(file_path))
            if person_id and records:
                result[person_id] = records
                logger.info(f"解析交通违法记录: {person_id} ({len(records)} 条)")
        except Exception as e:
            logger.warning(f"解析交通违法文件失败 {file_path.name}: {e}")
    
    return result


def _parse_traffic_violation_file(file_path: str) -> List[Dict]:
    """解析单个交通违法xlsx文件"""
    try:
        df = pd.read_excel(file_path)
        if df.empty:
            return []
        
        records = []
        for _, row in df.iterrows():
            record = {
                "source_file": Path(file_path).name,
                "violation_date": safe_date(row.get("违法时间", row.get("违法日期", ""))),
                "violation_type": safe_str(row.get("违法行为", row.get("违法类型", ""))),
                "location": safe_str(row.get("违法地点", "")),
                "vehicle_plate": safe_str(row.get("号牌号码", row.get("车牌号", ""))),
                "fine_amount": safe_float(row.get("罚款金额", 0)),
                "points_deducted": safe_int(row.get("记分", row.get("扣分", 0))),
                "status": safe_str(row.get("处理状态", "未处理")),
            }
            records.append(record)
        
        return records
    except Exception as e:
        logger.warning(f"解析交通违法文件失败: {e}")
        return []


# ============================================
# 9.3 公安部出国（境）证件解析
# ============================================

EXIT_DOCUMENT_DIR_NAME = "公安部出国（境）证件（定向查询）"


def extract_exit_document_data(data_dir: str) -> Dict[str, Dict]:
    """
    从出国（境）证件目录提取证件信息
    
    Args:
        data_dir: 数据根目录路径
        
    Returns:
        {身份证号: {证件信息}}
    """
    result = {}
    
    doc_dir = _find_data_dir(data_dir, EXIT_DOCUMENT_DIR_NAME)
    if not doc_dir:
        logger.info(f"未找到出境证件目录: {EXIT_DOCUMENT_DIR_NAME}")
        return result
    
    for file_path in doc_dir.glob("*.xlsx"):
        if file_path.name.startswith("~$"):
            continue
        
        try:
            person_id = _extract_id_from_filename(file_path.name)
            data = _parse_exit_document_file(str(file_path))
            if person_id and data:
                result[person_id] = data
                logger.info(f"解析出境证件信息: {person_id}")
        except Exception as e:
            logger.warning(f"解析出境证件文件失败 {file_path.name}: {e}")
    
    return result


def _parse_exit_document_file(file_path: str) -> Dict:
    """解析单个出境证件xlsx文件"""
    try:
        df = pd.read_excel(file_path)
        if df.empty:
            return {}
        
        # 收集所有证件信息
        documents = []
        for _, row in df.iterrows():
            doc = {
                "doc_type": safe_str(row.get("证件类型", row.get("证照类型", ""))),
                "doc_number": safe_str(row.get("证件号码", row.get("证照号码", ""))),
                "issue_date": safe_date(row.get("签发日期", "")),
                "valid_until": safe_date(row.get("有效期至", row.get("有效截止日期", ""))),
                "issue_authority": safe_str(row.get("签发机关", "")),
                "status": safe_str(row.get("状态", "有效")),
            }
            if doc["doc_number"]:
                documents.append(doc)
        
        return {
            "source_file": Path(file_path).name,
            "documents": documents,
            "count": len(documents)
        }
    except Exception as e:
        logger.warning(f"解析出境证件文件失败: {e}")
        return {}


# ============================================
# 9.4 铁路总公司互联网注册信息解析
# ============================================

RAILWAY_REGISTRATION_DIR_NAME = "铁路总公司互联网注册信息（定向查询）"


def extract_railway_registration_data(data_dir: str) -> Dict[str, Dict]:
    """
    从铁路互联网注册信息目录提取12306注册信息
    
    Args:
        data_dir: 数据根目录路径
        
    Returns:
        {身份证号: {注册信息}}
    """
    result = {}
    
    reg_dir = _find_data_dir(data_dir, RAILWAY_REGISTRATION_DIR_NAME)
    if not reg_dir:
        logger.info(f"未找到铁路注册信息目录: {RAILWAY_REGISTRATION_DIR_NAME}")
        return result
    
    for file_path in reg_dir.glob("*.xlsx"):
        if file_path.name.startswith("~$"):
            continue
        
        try:
            person_id = _extract_id_from_filename(file_path.name)
            data = _parse_railway_registration_file(str(file_path))
            if person_id and data:
                result[person_id] = data
                logger.info(f"解析12306注册信息: {person_id}")
        except Exception as e:
            logger.warning(f"解析铁路注册文件失败 {file_path.name}: {e}")
    
    return result


def _parse_railway_registration_file(file_path: str) -> Dict:
    """解析单个铁路注册信息xlsx文件"""
    try:
        df = pd.read_excel(file_path)
        if df.empty:
            return {}
        
        row = df.iloc[0]
        info = {
            "source_file": Path(file_path).name,
            "username": safe_str(row.get("用户名", "")),
            "phone": safe_str(row.get("手机号码", row.get("联系电话", ""))),
            "email": safe_str(row.get("邮箱", row.get("电子邮箱", ""))),
            "register_date": safe_date(row.get("注册日期", row.get("注册时间", ""))),
            "bindred_cards": safe_str(row.get("绑定银行卡", "")),
            "bindred_id_cards": safe_str(row.get("绑定身份证", "")),
        }
        
        return info
    except Exception as e:
        logger.warning(f"解析铁路注册文件失败: {e}")
        return {}


# ============================================
# 工具函数
# ============================================

def _find_data_dir(data_dir: str, dir_name: str) -> Optional[Path]:
    """在数据目录中查找指定目录"""
    base_path = Path(data_dir)
    
    for path in base_path.rglob(dir_name):
        if path.is_dir():
            return path
    
    return None


def _extract_id_from_filename(filename: str) -> str:
    """从文件名中提取身份证号"""
    match = re.search(r'[0-9]{17}[0-9X]', filename)
    return match.group(0) if match else ""


def extract_all_p3_data(data_dir: str) -> Dict[str, Dict]:
    """
    一次性提取所有P3级外部数据
    
    Returns:
        {
            "driverLicenses": {驾驶证数据},
            "trafficViolations": {交通违法数据},
            "exitDocuments": {出境证件数据},
            "railwayRegistrations": {12306注册信息}
        }
    """
    return {
        "driverLicenses": extract_driver_license_data(data_dir),
        "trafficViolations": extract_traffic_violation_data(data_dir),
        "exitDocuments": extract_exit_document_data(data_dir),
        "railwayRegistrations": extract_railway_registration_data(data_dir)
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    all_data = extract_all_p3_data(test_dir)
    
    print(f"\n=== P3级数据汇总 ===")
    print(f"驾驶证: {len(all_data['driverLicenses'])} 人")
    print(f"交通违法: {len(all_data['trafficViolations'])} 人")
    print(f"出境证件: {len(all_data['exitDocuments'])} 人")
    print(f"12306注册: {len(all_data['railwayRegistrations'])} 人")
