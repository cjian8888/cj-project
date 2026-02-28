"""
公安部出入境记录解析模块

解析 公安部出入境记录（定向查询） 目录下的xlsx文件
提取出入境时间、口岸、目的地等信息

作者: AI Assistant
创建时间: 2026-01-20
Phase: 8.2
"""

import re
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

import utils

logger = utils.setup_logger(__name__)


# 数据源目录名称
IMMIGRATION_DIR_NAME = "公安部出入境记录（定向查询）"


def extract_immigration_data(data_dir: str, person_id: str = None) -> Dict[str, List[Dict]]:
    """
    从公安部出入境记录目录提取所有出入境信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, List[Dict]]: 按身份证号分组的出入境数据
    """
    result = {}
    
    # 查找出入境数据目录
    immigration_dir = _find_immigration_dir(data_dir)
    if not immigration_dir:
        logger.warning(f"未找到公安部出入境记录目录: {IMMIGRATION_DIR_NAME}")
        return result
    
    logger.info(f"开始解析公安部出入境记录: {immigration_dir}")
    
    # 遍历所有xlsx文件
    immigration_path = Path(immigration_dir)
    xlsx_files = [f for f in immigration_path.glob("*.xlsx") if not f.name.startswith("~$")]
    
    for file_path in xlsx_files:
        try:
            # 从文件名提取身份证号
            file_person_id = _extract_id_from_filename(file_path.name)
            file_person_name = _extract_name_from_filename(file_path.name)
            
            # 如果指定了person_id，只处理匹配的文件
            if person_id and file_person_id != person_id:
                continue
            
            # 解析文件
            records = parse_immigration_file(str(file_path))
            
            if file_person_id and records:
                if file_person_id not in result:
                    result[file_person_id] = []
                result[file_person_id].extend(records)
                logger.debug(f"从 {file_path.name} 提取了 {len(records)} 条出入境记录")
                
        except Exception as e:
            logger.error(f"解析出入境文件失败 {file_path}: {e}")
            continue
    
    # 按日期排序
    for pid in result:
        result[pid] = sorted(result[pid], key=lambda x: x.get("date", ""), reverse=True)
    
    logger.info(f"公安部出入境记录解析完成，共 {len(result)} 个主体，{sum(len(v) for v in result.values())} 条记录")
    return result


def parse_immigration_file(file_path: str) -> List[Dict]:
    """解析单个公安部出入境记录xlsx文件"""
    records = []
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # 查找出入境记录sheet
        sheet_name = None
        for name in xls.sheet_names:
            if "出入境" in name:
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
            record = _parse_immigration_row(row, filename)
            if record:
                records.append(record)
        
    except Exception as e:
        logger.error(f"读取出入境文件失败 {file_path}: {e}")
    
    return records


def _parse_immigration_row(row: pd.Series, source_file: str) -> Optional[Dict]:
    """解析单行出入境数据"""
    try:
        record = {
            "name": _safe_str(row.get("姓名", "")),
            "person_type": _safe_str(row.get("人员类别", "")),
            "id_type": _safe_str(row.get("证件类别", "")),
            "id_number": _safe_str(row.get("证件号码") or row.get("身份证号", "")),
            "gender": _safe_str(row.get("性别", "")),
            "nationality": _safe_str(row.get("国籍", "")),
            "visa_type": _safe_str(row.get("签证种类", "")),
            "birth_date": _safe_date(row.get("出生日期")),
            "date": _safe_date(row.get("出入日期")),
            "time": _safe_str(row.get("出入时间", "")),
            "port": _safe_str(row.get("出入口岸", "")),
            "transport_mode": _safe_str(row.get("交通方式", "")),
            "transport_vehicle": _safe_str(row.get("交通工具", "")),
            "visa_number": _safe_str(row.get("签证号码", "")),
            "destination_or_origin": _safe_str(row.get("前往/归来国家", "")),
            "source_file": source_file
        }
        
        # 判断出入境类型
        date_str = str(row.get("出入日期", ""))
        if "入" in date_str or "入境" in str(row.get("人员类别", "")):
            record["direction"] = "入境"
        elif "出" in date_str or "出境" in str(row.get("人员类别", "")):
            record["direction"] = "出境"
        else:
            record["direction"] = "未知"
        
        if record["date"] or record["port"]:
            return record
        return None
        
    except Exception as e:
        logger.debug(f"解析出入境行失败: {e}")
        return None


def _find_immigration_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找公安部出入境记录目录"""
    data_path = Path(data_dir)
    
    for path in data_path.rglob("*"):
        if path.is_dir() and IMMIGRATION_DIR_NAME in path.name:
            return str(path)
    
    return None


def _extract_id_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取身份证号"""
    pattern = r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    match = re.search(pattern, filename)
    if match:
        return match.group().upper()
    return None


def _extract_name_from_filename(filename: str) -> str:
    """从文件名中提取名称"""
    parts = filename.split('_')
    if parts:
        return parts[0]
    return ""


def _safe_str(value) -> str:
    """安全转换为字符串"""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _safe_date(value) -> str:
    """安全转换为日期字符串"""
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()[:10]


# 便捷函数
def get_person_immigration(data_dir: str, person_id: str) -> List[Dict]:
    """获取指定人员的出入境记录"""
    result = extract_immigration_data(data_dir, person_id)
    return result.get(person_id, [])


def get_immigration_timeline(data_dir: str) -> List[Dict]:
    """获取所有人员的出入境时间线（按日期排序）"""
    all_data = extract_immigration_data(data_dir)
    
    timeline = []
    for person_id, records in all_data.items():
        for record in records:
            timeline.append({
                "person_id": person_id,
                "name": record.get("name", ""),
                "date": record.get("date", ""),
                "time": record.get("time", ""),
                "direction": record.get("direction", ""),
                "port": record.get("port", ""),
                "destination_or_origin": record.get("destination_or_origin", "")
            })
    
    return sorted(timeline, key=lambda x: x.get("date", ""), reverse=True)


def get_immigration_summary(data_dir: str) -> Dict:
    """获取出入境数据汇总"""
    all_data = extract_immigration_data(data_dir)
    
    total_entries = 0
    total_exits = 0
    destinations = {}
    
    for person_id, records in all_data.items():
        for record in records:
            if record.get("direction") == "入境":
                total_entries += 1
            elif record.get("direction") == "出境":
                total_exits += 1
            
            dest = record.get("destination_or_origin", "未知")
            if dest:
                destinations[dest] = destinations.get(dest, 0) + 1
    
    return {
        "total_persons": len(all_data),
        "total_records": sum(len(v) for v in all_data.values()),
        "total_entries": total_entries,
        "total_exits": total_exits,
        "destination_distribution": destinations
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    # 测试提取
    all_data = extract_immigration_data(test_dir)
    print(f"\n=== 公安部出入境记录 ({len(all_data)} 个主体) ===")
    
    for person_id, records in all_data.items():
        print(f"\n身份证号: {person_id}")
        for record in records[:3]:  # 只显示前3条
            print(f"  日期: {record.get('date')}")
            print(f"  方向: {record.get('direction')}")
            print(f"  口岸: {record.get('port')}")
            print(f"  目的地: {record.get('destination_or_origin')}")
            print(f"  ---")
    
    # 测试汇总
    summary = get_immigration_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"总人数: {summary['total_persons']}")
    print(f"总记录数: {summary['total_records']}")
    print(f"入境次数: {summary['total_entries']}")
    print(f"出境次数: {summary['total_exits']}")
