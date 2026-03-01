"""
铁路票面信息解析模块

解析 铁路总公司票面信息（定向查询） 目录下的xlsx文件
提取车次、发站、到站、时间等出行信息

作者: AI Assistant
创建时间: 2026-01-20
Phase: 8.5
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
RAILWAY_DIR_NAME = "铁路总公司票面信息（定向查询）"


def extract_railway_data(data_dir: str, person_id: str = None) -> Dict[str, Dict]:
    """
    从铁路票面信息目录提取所有铁路出行信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, Dict]: 按身份证号分组的铁路数据
        {
            "身份证号": {
                "tickets": [票面信息列表],
                "transactions": [交易信息列表]
            }
        }
    """
    result = {}
    
    railway_dir = _find_railway_dir(data_dir)
    if not railway_dir:
        logger.warning(f"未找到铁路票面信息目录: {RAILWAY_DIR_NAME}")
        return result
    
    logger.info(f"开始解析铁路票面信息: {railway_dir}")
    
    railway_path = Path(railway_dir)
    xlsx_files = [f for f in railway_path.glob("*.xlsx") if not f.name.startswith("~$")]
    
    for file_path in xlsx_files:
        try:
            file_person_id = _extract_id_from_filename(file_path.name)
            
            if person_id and file_person_id != person_id:
                continue
            
            data = parse_railway_file(str(file_path))
            
            if file_person_id:
                if file_person_id not in result:
                    result[file_person_id] = {"tickets": [], "transactions": []}
                result[file_person_id]["tickets"].extend(data.get("tickets", []))
                result[file_person_id]["transactions"].extend(data.get("transactions", []))
                logger.debug(f"从 {file_path.name} 提取了 {len(data.get('tickets', []))} 条票面记录")
                
        except Exception as e:
            logger.error(f"解析铁路文件失败 {file_path}: {e}")
            continue
    
    # 按日期排序
    for pid in result:
        result[pid]["tickets"] = sorted(
            result[pid]["tickets"], 
            key=lambda x: x.get("departure_date", ""), 
            reverse=True
        )
    
    logger.info(f"铁路票面信息解析完成，共 {len(result)} 个主体")
    return result


def parse_railway_file(file_path: str) -> Dict:
    """解析单个铁路票面信息xlsx文件"""
    result = {"tickets": [], "transactions": []}
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        for sheet_name in xls.sheet_names:
            if "票面" in sheet_name:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if not df.empty:
                    for _, row in df.iterrows():
                        ticket = _parse_ticket_row(row, filename)
                        if ticket:
                            result["tickets"].append(ticket)
            
            elif "交易" in sheet_name:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if not df.empty:
                    for _, row in df.iterrows():
                        trans = _parse_transaction_row(row, filename)
                        if trans:
                            result["transactions"].append(trans)
        
    except Exception as e:
        logger.error(f"读取铁路文件失败 {file_path}: {e}")
    
    return result


def _parse_ticket_row(row: pd.Series, source_file: str) -> Optional[Dict]:
    """解析票面信息行"""
    try:
        ticket = {
            "ticket_seq": safe_str(row.get("车票序号", "")),
            "departure_date": safe_date(row.get("发车日期")),
            "departure_time": safe_str(row.get("发车时间", "")),
            "passenger_name": safe_str(row.get("乘车人姓名", "")),
            "id_type": safe_str(row.get("证件类型", "")),
            "id_number": safe_str(row.get("证件号码", "")),
            "ticket_number": safe_str(row.get("票号", "")),
            "train_number": safe_str(row.get("列车车次", "")),
            "departure_station": safe_str(row.get("发站", "")),
            "arrival_station": safe_str(row.get("到站", "")),
            "carriage_number": safe_str(row.get("车厢号", "")),
            "seat_type": safe_str(row.get("席别", "")),
            "seat_number": safe_str(row.get("席位号", "")),
            "ticket_station": safe_str(row.get("售票车站", "")),
            "ticket_time": safe_datetime(row.get("售票时间")),
            "buyer_name": safe_str(row.get("购票人", "")),
            "buyer_id": safe_str(row.get("购票人证件号码", "")),
            "buyer_contact": safe_str(row.get("购票人联系方式", "")),
            "refund_station": safe_str(row.get("退票车站", "")),
            "refund_date": safe_date(row.get("退票日期")),
            "refund_time": safe_str(row.get("退票时间", "")),
            "change_station": safe_str(row.get("改签车站", "")),
            "change_time": safe_datetime(row.get("改签时间")),
            "new_ticket_number": safe_str(row.get("改签新票票号", "")),
            "source_file": source_file
        }
        
        if ticket["departure_date"] or ticket["train_number"]:
            return ticket
        return None
        
    except Exception as e:
        logger.debug(f"解析票面行失败: {e}")
        return None


def _parse_transaction_row(row: pd.Series, source_file: str) -> Optional[Dict]:
    """解析交易信息行"""
    try:
        trans = {
            "ticket_seq": safe_str(row.get("车票序号", "")),
            "train_number": safe_str(row.get("列车车次", "")),
            "departure_date": safe_date(row.get("发车日期")),
            "order_number": safe_str(row.get("交易订单号", "")),
            "transaction_time": safe_datetime(row.get("交易时间")),
            "acquiring_bank": safe_str(row.get("收单行", "")),
            "source_file": source_file
        }
        
        if trans["order_number"] or trans["transaction_time"]:
            return trans
        return None
        
    except Exception as e:
        logger.debug(f"解析交易行失败: {e}")
        return None


def get_travel_timeline(data_dir: str) -> List[Dict]:
    """
    获取所有人员的铁路出行时间线（按日期排序）
    """
    all_data = extract_railway_data(data_dir)
    
    timeline = []
    for person_id, data in all_data.items():
        for ticket in data.get("tickets", []):
            timeline.append({
                "person_id": person_id,
                "name": ticket.get("passenger_name", ""),
                "date": ticket.get("departure_date", ""),
                "time": ticket.get("departure_time", ""),
                "train": ticket.get("train_number", ""),
                "from": ticket.get("departure_station", ""),
                "to": ticket.get("arrival_station", ""),
                "type": "railway"
            })
    
    return sorted(timeline, key=lambda x: x.get("date", ""), reverse=True)


def _find_railway_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找铁路票面信息目录"""
    data_path = Path(data_dir)
    
    for path in data_path.rglob("*"):
        if path.is_dir() and RAILWAY_DIR_NAME in path.name:
            return str(path)
    
    return None


def _extract_id_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取身份证号"""
    pattern = r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    match = re.search(pattern, filename)
    if match:
        return match.group().upper()
    return None


def get_railway_summary(data_dir: str) -> Dict:
    """获取铁路票面数据汇总"""
    all_data = extract_railway_data(data_dir)
    
    total_tickets = 0
    stations = {}
    trains = {}
    
    for person_id, data in all_data.items():
        tickets = data.get("tickets", [])
        total_tickets += len(tickets)
        
        for ticket in tickets:
            dep = ticket.get("departure_station", "未知")
            arr = ticket.get("arrival_station", "未知")
            train = ticket.get("train_number", "未知")
            
            stations[dep] = stations.get(dep, 0) + 1
            stations[arr] = stations.get(arr, 0) + 1
            trains[train] = trains.get(train, 0) + 1
    
    return {
        "total_persons": len(all_data),
        "total_tickets": total_tickets,
        "station_distribution": stations,
        "train_distribution": trains
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    all_data = extract_railway_data(test_dir)
    print(f"\n=== 铁路票面信息 ({len(all_data)} 个主体) ===")
    
    for person_id, data in all_data.items():
        tickets = data.get("tickets", [])
        print(f"\n身份证号: {person_id}")
        print(f"  票数: {len(tickets)}")
        for ticket in tickets[:3]:
            print(f"    {ticket.get('departure_date')} {ticket.get('train_number')}")
            print(f"    {ticket.get('departure_station')} → {ticket.get('arrival_station')}")
            print(f"    ---")
    
    # 时间线
    timeline = get_travel_timeline(test_dir)
    print(f"\n=== 出行时间线 ({len(timeline)} 条) ===")
    for t in timeline[:5]:
        print(f"  {t.get('date')} {t.get('train')}: {t.get('from')} → {t.get('to')}")
    
    summary = get_railway_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"总人数: {summary['total_persons']}")
    print(f"总票数: {summary['total_tickets']}")
