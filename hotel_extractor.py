"""
公安部旅馆住宿解析模块

解析 公安部旅馆住宿（定向查询） 目录下的xlsx文件
提取入住时间、旅馆信息，用于同住分析

作者: AI Assistant
创建时间: 2026-01-20
Phase: 8.3
"""

import re
from typing import List, Dict, Optional
from pathlib import Path
from collections import defaultdict

import pandas as pd

import utils

logger = utils.setup_logger(__name__)


# 数据源目录名称
HOTEL_DIR_NAME = "公安部旅馆住宿（定向查询）"


def extract_hotel_data(data_dir: str, person_id: str = None) -> Dict[str, List[Dict]]:
    """
    从公安部旅馆住宿目录提取所有住宿信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, List[Dict]]: 按身份证号分组的住宿数据
    """
    result = {}
    
    # 查找旅馆住宿数据目录
    hotel_dir = _find_hotel_dir(data_dir)
    if not hotel_dir:
        logger.warning(f"未找到公安部旅馆住宿目录: {HOTEL_DIR_NAME}")
        return result
    
    logger.info(f"开始解析公安部旅馆住宿数据: {hotel_dir}")
    
    # 遍历所有xlsx文件
    hotel_path = Path(hotel_dir)
    xlsx_files = [f for f in hotel_path.glob("*.xlsx") if not f.name.startswith("~$")]
    
    for file_path in xlsx_files:
        try:
            file_person_id = _extract_id_from_filename(file_path.name)
            
            if person_id and file_person_id != person_id:
                continue
            
            records = parse_hotel_file(str(file_path))
            
            if file_person_id and records:
                if file_person_id not in result:
                    result[file_person_id] = []
                result[file_person_id].extend(records)
                logger.debug(f"从 {file_path.name} 提取了 {len(records)} 条住宿记录")
                
        except Exception as e:
            logger.error(f"解析旅馆文件失败 {file_path}: {e}")
            continue
    
    # 按入住时间排序
    for pid in result:
        result[pid] = sorted(result[pid], key=lambda x: x.get("check_in_time", ""), reverse=True)
    
    logger.info(f"公安部旅馆住宿解析完成，共 {len(result)} 个主体，{sum(len(v) for v in result.values())} 条记录")
    return result


def parse_hotel_file(file_path: str) -> List[Dict]:
    """解析单个公安部旅馆住宿xlsx文件"""
    records = []
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        sheet_name = None
        for name in xls.sheet_names:
            if "旅馆" in name or "住宿" in name:
                sheet_name = name
                break
        
        if not sheet_name:
            sheet_name = xls.sheet_names[0] if xls.sheet_names else None
        
        if not sheet_name:
            return records
        
        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        if df.empty:
            return records
        
        for _, row in df.iterrows():
            record = _parse_hotel_row(row, filename)
            if record:
                records.append(record)
        
    except Exception as e:
        logger.error(f"读取旅馆文件失败 {file_path}: {e}")
    
    return records


def _parse_hotel_row(row: pd.Series, source_file: str) -> Optional[Dict]:
    """解析单行住宿数据"""
    try:
        record = {
            "name": _safe_str(row.get("姓名", "")),
            "gender": _safe_str(row.get("性别", "")),
            "ethnicity": _safe_str(row.get("民族", "")),
            "birth_date": _safe_date(row.get("出生日期")),
            "id_type": _safe_str(row.get("证件类型", "")),
            "id_number": _safe_str(row.get("证件号码", "")),
            "hotel_code": _safe_str(row.get("旅店代码", "")),
            "province": _safe_str(row.get("省级名称", "")),
            "room_number": _safe_str(row.get("房间号码", "")),
            "check_in_time": _safe_datetime(row.get("入住时间")),
            "check_out_time": _safe_datetime(row.get("离店时间")),
            "hotel_phone": _safe_str(row.get("旅店联系号码", "")),
            "hotel_name": _safe_str(row.get("旅店名称", "")),
            "hotel_district": _safe_str(row.get("旅店区划", "")),
            "hukou_district": _safe_str(row.get("户籍地区划", "")),
            "hukou_address": _safe_str(row.get("户籍地详情", "")),
            "hotel_address": _safe_str(row.get("旅店地址", "")),
            "source_file": source_file
        }
        
        if record["check_in_time"] or record["hotel_name"]:
            return record
        return None
        
    except Exception as e:
        logger.debug(f"解析住宿行失败: {e}")
        return None


def analyze_cohabitation(data_dir: str) -> Dict:
    """
    分析同住情况
    
    返回同一时间、同一旅店、同一房间的住宿记录
    """
    all_data = extract_hotel_data(data_dir)
    
    # 按 (旅店, 房间, 日期) 分组
    room_guests = defaultdict(list)
    
    for person_id, records in all_data.items():
        for record in records:
            hotel = record.get("hotel_name", "")
            room = record.get("room_number", "")
            check_in = record.get("check_in_time", "")[:10]  # 只取日期部分
            
            if hotel and room and check_in:
                key = (hotel, room, check_in)
                room_guests[key].append({
                    "person_id": person_id,
                    "name": record.get("name", ""),
                    "check_in_time": record.get("check_in_time", ""),
                    "check_out_time": record.get("check_out_time", "")
                })
    
    # 找出有多人同住的记录
    cohabitation = []
    for key, guests in room_guests.items():
        if len(guests) > 1:
            cohabitation.append({
                "hotel": key[0],
                "room": key[1],
                "date": key[2],
                "guests": guests,
                "guest_count": len(guests)
            })
    
    return {
        "total_cohabitation_records": len(cohabitation),
        "cohabitation_details": sorted(cohabitation, key=lambda x: x.get("date", ""), reverse=True)
    }


def _find_hotel_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找公安部旅馆住宿目录"""
    data_path = Path(data_dir)
    
    for path in data_path.rglob("*"):
        if path.is_dir() and HOTEL_DIR_NAME in path.name:
            return str(path)
    
    return None


def _extract_id_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取身份证号"""
    pattern = r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    match = re.search(pattern, filename)
    if match:
        return match.group().upper()
    return None


def _safe_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _safe_date(value) -> str:
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()[:10]


def _safe_datetime(value) -> str:
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value).strip()[:19]


def get_hotel_summary(data_dir: str) -> Dict:
    """获取旅馆住宿数据汇总"""
    all_data = extract_hotel_data(data_dir)
    
    total_records = sum(len(v) for v in all_data.values())
    hotels = {}
    provinces = {}
    
    for person_id, records in all_data.items():
        for record in records:
            hotel = record.get("hotel_name", "未知")
            hotels[hotel] = hotels.get(hotel, 0) + 1
            
            province = record.get("province", "未知")
            provinces[province] = provinces.get(province, 0) + 1
    
    return {
        "total_persons": len(all_data),
        "total_records": total_records,
        "hotel_distribution": hotels,
        "province_distribution": provinces
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    all_data = extract_hotel_data(test_dir)
    print(f"\n=== 公安部旅馆住宿 ({len(all_data)} 个主体) ===")
    
    for person_id, records in all_data.items():
        print(f"\n身份证号: {person_id}")
        for record in records[:3]:
            print(f"  入住时间: {record.get('check_in_time')}")
            print(f"  旅店: {record.get('hotel_name')}")
            print(f"  房间: {record.get('room_number')}")
            print(f"  ---")
    
    # 同住分析
    cohab = analyze_cohabitation(test_dir)
    print(f"\n=== 同住分析 ===")
    print(f"同住记录数: {cohab['total_cohabitation_records']}")
    
    summary = get_hotel_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"总人数: {summary['total_persons']}")
    print(f"总记录数: {summary['total_records']}")
