"""
公安部机动车信息解析模块

解析 公安部机动车（定向查询） 目录下的xlsx文件
提取车辆登记信息、车主信息

作者: AI Assistant
创建时间: 2026-01-20
Phase: 7.1
"""

import re
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

import utils

logger = utils.setup_logger(__name__)


# 数据源目录名称
VEHICLE_DIR_NAME = "公安部机动车（定向查询）"


def extract_vehicle_data(data_dir: str, person_id: str = None) -> Dict[str, List[Dict]]:
    """
    从公安部机动车数据目录提取所有车辆信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号，仅提取该人员的车辆
        
    Returns:
        Dict[str, List[Dict]]: 按身份证号分组的车辆数据
        {
            "310102196504096017": [
                {
                    "plate_number": "沪FNE670",
                    "plate_type": "小型汽车号牌",
                    "brand": "梅赛德斯-奔驰牌",
                    "color": "灰",
                    "register_date": "2022-06-29",
                    "status": "正常",
                    "is_pledged": False,
                    "engine_number": "30356290",
                    "vin": "210596",
                    "displacement": "1991",
                    "source_file": "xxx.xlsx"
                },
                ...
            ]
        }
    """
    result = {}
    
    # 查找车辆数据目录
    vehicle_dir = _find_vehicle_dir(data_dir)
    if not vehicle_dir:
        logger.warning(f"未找到公安部机动车数据目录: {VEHICLE_DIR_NAME}")
        return result
    
    logger.info(f"开始解析公安部机动车数据: {vehicle_dir}")
    
    # 遍历所有xlsx文件
    vehicle_path = Path(vehicle_dir)
    xlsx_files = list(vehicle_path.glob("*.xlsx"))
    
    for file_path in xlsx_files:
        try:
            # 从文件名提取身份证号
            file_person_id = _extract_id_from_filename(file_path.name)
            
            # 如果指定了person_id，只处理匹配的文件
            if person_id and file_person_id != person_id:
                continue
            
            # 解析文件
            vehicles = parse_vehicle_file(str(file_path))
            
            if file_person_id and vehicles:
                if file_person_id not in result:
                    result[file_person_id] = []
                result[file_person_id].extend(vehicles)
                logger.debug(f"从 {file_path.name} 提取了 {len(vehicles)} 条车辆记录")
                
        except Exception as e:
            logger.error(f"解析车辆文件失败 {file_path}: {e}")
            continue
    
    # 去重
    for pid in result:
        result[pid] = _deduplicate_vehicles(result[pid])
    
    logger.info(f"公安部机动车解析完成，共 {len(result)} 个主体，{sum(len(v) for v in result.values())} 条车辆记录")
    return result


def parse_vehicle_file(file_path: str) -> List[Dict]:
    """
    解析单个公安部机动车xlsx文件
    
    Args:
        file_path: xlsx文件路径
        
    Returns:
        List[Dict]: 车辆列表
    """
    vehicles = []
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # 查找机动车信息sheet
        sheet_name = None
        for name in xls.sheet_names:
            if "机动车" in name:
                sheet_name = name
                break
        
        if not sheet_name:
            sheet_name = xls.sheet_names[0] if xls.sheet_names else None
        
        if not sheet_name:
            return vehicles
        
        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        if df.empty:
            return vehicles
        
        # 解析每一行
        for _, row in df.iterrows():
            vehicle = _parse_vehicle_row(row, filename)
            if vehicle and vehicle.get("plate_number"):
                vehicles.append(vehicle)
        
    except Exception as e:
        logger.error(f"读取车辆文件失败 {file_path}: {e}")
    
    return vehicles


def _parse_vehicle_row(row: pd.Series, source_file: str) -> Optional[Dict]:
    """解析单行车辆数据"""
    try:
        # 检查是否为抵押/质押
        is_pledged_val = _safe_str(row.get("是否抵押/质押", ""))
        is_pledged = is_pledged_val in ["1", "是", "有"]
        
        vehicle = {
            "plate_number": _safe_str(row.get("号牌号码", "")),
            "plate_type": _safe_str(row.get("号牌种类", "")),
            "brand": _safe_str(row.get("中文品牌", "")),
            "color": _safe_str(row.get("车身颜色", "")),
            "register_date": _safe_date(row.get("初次登记日期")),
            "status": _safe_str(row.get("机动车状态", "")),
            "is_pledged": is_pledged,
            "engine_number": _safe_str(row.get("机动车发动机号", "")),
            "vin": _safe_str(row.get("车辆识别代码", "")),
            "displacement": _safe_str(row.get("机动车发动机排量", "")),
            "power": _safe_str(row.get("机动车发动机功率", "")),
            "energy_type": _safe_str(row.get("机动车能源种类", "")),
            "manufacture_date": _safe_date(row.get("出厂日期")),
            "owner_name": _safe_str(row.get("机动车所有人", "")),
            "owner_id": _safe_str(row.get("身份证号", "")),
            "contact_phone": _safe_str(row.get("联系电话", "")),
            "address": _safe_str(row.get("住所地址", "")),
            "source_file": source_file
        }
        
        return vehicle
        
    except Exception as e:
        logger.debug(f"解析车辆行失败: {e}")
        return None


def _find_vehicle_dir(data_dir: str) -> Optional[str]:
    """
    在数据目录中查找公安部机动车目录
    
    Args:
        data_dir: 数据根目录
        
    Returns:
        str: 找到的目录路径，未找到返回None
    """
    data_path = Path(data_dir)
    
    # 递归搜索
    for path in data_path.rglob("*"):
        if path.is_dir() and VEHICLE_DIR_NAME in path.name:
            return str(path)
    
    return None


def _extract_id_from_filename(filename: str) -> Optional[str]:
    """
    从文件名中提取身份证号
    
    文件名格式示例: 施灵_310102196504096017_国监查【2024】第020734号_公安部机动车信息_1.xlsx
    
    Args:
        filename: 文件名
        
    Returns:
        str: 身份证号，未找到返回None
    """
    # 匹配18位身份证号
    pattern = r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    match = re.search(pattern, filename)
    
    if match:
        return match.group().upper()
    
    return None


def _deduplicate_vehicles(vehicles: List[Dict]) -> List[Dict]:
    """按车牌号去重"""
    seen = set()
    unique = []
    
    for v in vehicles:
        plate = v.get("plate_number", "")
        if plate and plate not in seen:
            seen.add(plate)
            unique.append(v)
    
    return unique


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
def get_person_vehicles(data_dir: str, person_id: str) -> List[Dict]:
    """
    获取指定人员的车辆列表
    
    Args:
        data_dir: 数据目录
        person_id: 身份证号
        
    Returns:
        List[Dict]: 车辆列表
    """
    result = extract_vehicle_data(data_dir, person_id)
    return result.get(person_id, [])


def get_vehicle_summary(data_dir: str) -> Dict:
    """
    获取车辆数据汇总
    
    Args:
        data_dir: 数据目录
        
    Returns:
        Dict: 汇总信息
    """
    all_data = extract_vehicle_data(data_dir)
    
    total_vehicles = sum(len(v) for v in all_data.values())
    total_persons = len(all_data)
    
    # 统计品牌分布
    brands = {}
    statuses = {}
    pledged_count = 0
    
    for vehicles in all_data.values():
        for v in vehicles:
            brand = v.get("brand", "未知")
            brands[brand] = brands.get(brand, 0) + 1
            
            status = v.get("status", "未知")
            statuses[status] = statuses.get(status, 0) + 1
            
            if v.get("is_pledged"):
                pledged_count += 1
    
    return {
        "total_persons": total_persons,
        "total_vehicles": total_vehicles,
        "pledged_count": pledged_count,
        "brand_distribution": brands,
        "status_distribution": statuses
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    # 测试提取
    all_data = extract_vehicle_data(test_dir)
    print(f"\n=== 公安部机动车数据 ({len(all_data)} 个主体) ===")
    
    for person_id, vehicles in all_data.items():
        print(f"\n身份证号: {person_id}")
        for v in vehicles:
            print(f"  车牌: {v.get('plate_number')}")
            print(f"  品牌: {v.get('brand')}")
            print(f"  状态: {v.get('status')}")
            print(f"  抵押: {'是' if v.get('is_pledged') else '否'}")
            print(f"  ---")
    
    # 测试汇总
    summary = get_vehicle_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"总人数: {summary['total_persons']}")
    print(f"总车辆: {summary['total_vehicles']}")
    print(f"抵押车辆: {summary['pledged_count']}")
