"""
中航信航班进出港信息解析模块

解析 中航信航班进出港信息（定向查询） 目录下的xlsx文件
提取航班号、起降时间、起降机场等信息

作者: AI Assistant
创建时间: 2026-01-20
Phase: 8.6
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
)

logger = utils.setup_logger(__name__)


# 数据源目录名称
FLIGHT_DIR_NAME = "中航信航班进出港信息（定向查询）"


def extract_flight_data(data_dir: str, person_id: str = None) -> Dict[str, Dict]:
    """
    从中航信航班进出港信息目录提取所有航班信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, Dict]: 按身份证号分组的航班数据
        {
            "身份证号": {
                "completed": [已成行航班列表],
                "cancelled": [未成行航班列表]
            }
        }
    """
    result = {}
    
    flight_dir = _find_flight_dir(data_dir)
    if not flight_dir:
        logger.warning(f"未找到中航信航班进出港信息目录: {FLIGHT_DIR_NAME}")
        return result
    
    logger.info(f"开始解析中航信航班进出港信息: {flight_dir}")
    
    flight_path = Path(flight_dir)
    xlsx_files = [f for f in flight_path.glob("*.xlsx") if not f.name.startswith("~$")]
    
    for file_path in xlsx_files:
        try:
            file_person_id = _extract_id_from_filename(file_path.name)
            
            if person_id and file_person_id != person_id:
                continue
            
            data = parse_flight_file(str(file_path))
            
            if file_person_id:
                if file_person_id not in result:
                    result[file_person_id] = {"completed": [], "cancelled": []}
                result[file_person_id]["completed"].extend(data.get("completed", []))
                result[file_person_id]["cancelled"].extend(data.get("cancelled", []))
                
                total = len(data.get("completed", [])) + len(data.get("cancelled", []))
                logger.debug(f"从 {file_path.name} 提取了 {total} 条航班记录")
                
        except Exception as e:
            logger.error(f"解析航班文件失败 {file_path}: {e}")
            continue
    
    # 按日期排序
    for pid in result:
        result[pid]["completed"] = sorted(
            result[pid]["completed"],
            key=lambda x: x.get("departure_date", ""),
            reverse=True
        )
        result[pid]["cancelled"] = sorted(
            result[pid]["cancelled"],
            key=lambda x: x.get("departure_date", ""),
            reverse=True
        )
    
    logger.info(f"中航信航班进出港信息解析完成，共 {len(result)} 个主体")
    return result


def parse_flight_file(file_path: str) -> Dict:
    """解析单个航班进出港xlsx文件"""
    result = {"completed": [], "cancelled": []}
    filename = Path(file_path).name
    
    try:
        # 尝试使用 openpyxl 引擎，如果失败则尝试 xlrd
        try:
            xls = pd.ExcelFile(file_path, engine='openpyxl')
        except Exception:
            try:
                xls = pd.ExcelFile(file_path, engine='xlrd')
            except Exception:
                xls = pd.ExcelFile(file_path, engine='openpyxl')
        
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            if df.empty:
                continue
            
            is_completed = "已成行" in sheet_name
            
            for _, row in df.iterrows():
                flight = _parse_flight_row(row, filename, is_completed)
                if flight:
                    if is_completed:
                        result["completed"].append(flight)
                    else:
                        result["cancelled"].append(flight)
        
    except Exception as e:
        logger.error(f"读取航班文件失败 {file_path}: {e}")
    
    return result


def _parse_flight_row(row: pd.Series, source_file: str, is_completed: bool) -> Optional[Dict]:
    """解析航班信息行"""
    try:
        flight = {
            "passenger_id": safe_str(row.get("旅客证件号", "")),
            "phone": safe_str(row.get("手机号", "")),
            "airline": safe_str(row.get("航空公司", "")),
            "flight_number": safe_str(row.get("航班号", "")),
            "passenger_name_cn": safe_str(row.get("旅客中文姓名", "")),
            "passenger_name_en": safe_str(row.get("旅客英文名字", "")),
            "departure_date": safe_date(row.get("起飞日期")),
            "departure_time": safe_str(row.get("起飞时间", "")),
            "arrival_date": safe_date(row.get("到达日期")),
            "arrival_time": safe_str(row.get("到达时间", "")),
            "departure_airport_code": safe_str(row.get("起飞机场三字码", "")),
            "arrival_airport_code": safe_str(row.get("到达机场三字码", "")),
            "departure_airport": safe_str(row.get("起飞机场", "")),
            "arrival_airport": safe_str(row.get("到达机场", "")),
            "checkin_date": safe_date(row.get("值机日期")),
            "checkin_time": safe_str(row.get("值机时间", "")),
            "cabin_class": safe_str(row.get("离港舱位", "")),
            "boarding_sequence": safe_str(row.get("登机牌序号", "")),
            "seat_row": safe_str(row.get("座位行号", "")),
            "seat_number": safe_str(row.get("座位号", "")),
            "ticket_number": safe_str(row.get("票号", "")),
            "record_number": safe_str(row.get("记录编号", "")),
            "sales_cabin": safe_str(row.get("销售舱位", "")),
            "ticket_date": safe_date(row.get("出票日期")),
            "ffp_airline": safe_str(row.get("常客卡所属航空公司", "")),
            "ffp_number": safe_str(row.get("常客卡号", "")),
            "baggage_count": safe_int(row.get("行李件数")),
            "baggage_weight": safe_float(row.get("行李重量(kg)")),
            "ticket_price": safe_float(row.get("票面总价")),
            "payment_method": safe_str(row.get("付款方式", "")),
            "currency": safe_str(row.get("票价货币类型", "")),
            "ticket_office": safe_str(row.get("出票处office", "")),
            "ticket_office_phone": safe_str(row.get("出票处电话", "")),
            "ticket_office_address": safe_str(row.get("出票处地址", "")),
            "booking_office": safe_str(row.get("订票处office", "")),
            "booking_office_name": safe_str(row.get("订票处名字", "")),
            "booking_office_phone": safe_str(row.get("订票处电话", "")),
            "booking_office_address": safe_str(row.get("订票处地址", "")),
            "companion_type": safe_str(row.get("同行人类别", "")),
            "related_target": safe_str(row.get("关联目标人", "")),
            "person_type": safe_str(row.get("人员类别", "")),
            "is_completed": is_completed,
            "source_file": source_file
        }
        
        if flight["departure_date"] or flight["flight_number"]:
            return flight
        return None
        
    except Exception as e:
        logger.debug(f"解析航班行失败: {e}")
        return None


def get_flight_timeline(data_dir: str) -> List[Dict]:
    """
    获取所有人员的航班出行时间线（按日期排序）
    """
    all_data = extract_flight_data(data_dir)
    
    timeline = []
    for person_id, data in all_data.items():
        for flight in data.get("completed", []):
            timeline.append({
                "person_id": person_id,
                "name": flight.get("passenger_name_cn", ""),
                "date": flight.get("departure_date", ""),
                "time": flight.get("departure_time", ""),
                "flight": flight.get("flight_number", ""),
                "airline": flight.get("airline", ""),
                "from": flight.get("departure_airport", ""),
                "to": flight.get("arrival_airport", ""),
                "status": "已成行",
                "type": "flight"
            })
        
        for flight in data.get("cancelled", []):
            timeline.append({
                "person_id": person_id,
                "name": flight.get("passenger_name_cn", ""),
                "date": flight.get("departure_date", ""),
                "time": flight.get("departure_time", ""),
                "flight": flight.get("flight_number", ""),
                "airline": flight.get("airline", ""),
                "from": flight.get("departure_airport", ""),
                "to": flight.get("arrival_airport", ""),
                "status": "未成行",
                "type": "flight"
            })
    
    return sorted(timeline, key=lambda x: x.get("date", ""), reverse=True)


def _find_flight_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找中航信航班进出港信息目录"""
    data_path = Path(data_dir)
    
    for path in data_path.rglob("*"):
        if path.is_dir() and FLIGHT_DIR_NAME in path.name:
            return str(path)
    
    return None


def _extract_id_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取身份证号"""
    pattern = r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    match = re.search(pattern, filename)
    if match:
        return match.group().upper()
    return None


def get_flight_summary(data_dir: str) -> Dict:
    """获取航班数据汇总"""
    all_data = extract_flight_data(data_dir)
    
    total_completed = 0
    total_cancelled = 0
    airlines = {}
    airports = {}
    
    for person_id, data in all_data.items():
        completed = data.get("completed", [])
        cancelled = data.get("cancelled", [])
        total_completed += len(completed)
        total_cancelled += len(cancelled)
        
        for flight in completed + cancelled:
            airline = flight.get("airline", "未知")
            airlines[airline] = airlines.get(airline, 0) + 1
            
            dep = flight.get("departure_airport", "未知")
            arr = flight.get("arrival_airport", "未知")
            airports[dep] = airports.get(dep, 0) + 1
            airports[arr] = airports.get(arr, 0) + 1
    
    return {
        "total_persons": len(all_data),
        "total_completed": total_completed,
        "total_cancelled": total_cancelled,
        "airline_distribution": airlines,
        "airport_distribution": airports
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    all_data = extract_flight_data(test_dir)
    print(f"\n=== 中航信航班进出港信息 ({len(all_data)} 个主体) ===")
    
    for person_id, data in all_data.items():
        completed = data.get("completed", [])
        cancelled = data.get("cancelled", [])
        print(f"\n身份证号: {person_id}")
        print(f"  已成行: {len(completed)} 条")
        print(f"  未成行: {len(cancelled)} 条")
        
        for flight in completed[:2]:
            print(f"    {flight.get('departure_date')} {flight.get('flight_number')}")
            print(f"    {flight.get('departure_airport')} → {flight.get('arrival_airport')}")
            print(f"    ---")
    
    # 时间线
    timeline = get_flight_timeline(test_dir)
    print(f"\n=== 航班时间线 ({len(timeline)} 条) ===")
    for t in timeline[:5]:
        status = t.get('status')
        print(f"  [{status}] {t.get('date')} {t.get('flight')}: {t.get('from')} → {t.get('to')}")
    
    summary = get_flight_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"总人数: {summary['total_persons']}")
    print(f"已成行: {summary['total_completed']}")
    print(f"未成行: {summary['total_cancelled']}")
