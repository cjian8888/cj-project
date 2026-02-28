"""
公安部同住址/同车违章解析模块

解析以下目录下的xlsx文件：
- 公安部同住址（定向查询）
- 公安部同车违章（定向查询）

用于关系图谱补充分析

作者: AI Assistant
创建时间: 2026-01-20
Phase: 8.4
"""

import re
from typing import List, Dict, Optional
from pathlib import Path
from collections import defaultdict

import pandas as pd

import utils

logger = utils.setup_logger(__name__)


# 数据源目录名称
COADDRESS_DIR_NAME = "公安部同住址（定向查询）"
COVIOLATION_DIR_NAME = "公安部同车违章（定向查询）"


def extract_coaddress_data(data_dir: str, person_id: str = None) -> Dict[str, List[Dict]]:
    """
    从公安部同住址目录提取所有同住址人员信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, List[Dict]]: 按查询人身份证号分组的同住址人员数据
    """
    result = {}
    
    coaddress_dir = _find_dir(data_dir, COADDRESS_DIR_NAME)
    if not coaddress_dir:
        logger.warning(f"未找到公安部同住址目录: {COADDRESS_DIR_NAME}")
        return result
    
    logger.info(f"开始解析公安部同住址数据: {coaddress_dir}")
    
    coaddress_path = Path(coaddress_dir)
    xlsx_files = [f for f in coaddress_path.glob("*.xlsx") if not f.name.startswith("~$")]
    
    for file_path in xlsx_files:
        try:
            file_person_id = _extract_id_from_filename(file_path.name)
            
            if person_id and file_person_id != person_id:
                continue
            
            records = _parse_coaddress_file(str(file_path))
            
            if file_person_id:
                if file_person_id not in result:
                    result[file_person_id] = []
                result[file_person_id].extend(records)
                logger.debug(f"从 {file_path.name} 提取了 {len(records)} 条同住址记录")
                
        except Exception as e:
            logger.error(f"解析同住址文件失败 {file_path}: {e}")
            continue
    
    logger.info(f"公安部同住址解析完成，共 {len(result)} 个主体")
    return result


def extract_coviolation_data(data_dir: str, person_id: str = None) -> Dict[str, List[Dict]]:
    """
    从公安部同车违章目录提取所有同车违章信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, List[Dict]]: 按查询人身份证号分组的同车违章数据
    """
    result = {}
    
    coviolation_dir = _find_dir(data_dir, COVIOLATION_DIR_NAME)
    if not coviolation_dir:
        logger.warning(f"未找到公安部同车违章目录: {COVIOLATION_DIR_NAME}")
        return result
    
    logger.info(f"开始解析公安部同车违章数据: {coviolation_dir}")
    
    coviolation_path = Path(coviolation_dir)
    xlsx_files = [f for f in coviolation_path.glob("*.xlsx") if not f.name.startswith("~$")]
    
    for file_path in xlsx_files:
        try:
            file_person_id = _extract_id_from_filename(file_path.name)
            
            if person_id and file_person_id != person_id:
                continue
            
            records = _parse_coviolation_file(str(file_path))
            
            if file_person_id:
                if file_person_id not in result:
                    result[file_person_id] = []
                result[file_person_id].extend(records)
                logger.debug(f"从 {file_path.name} 提取了 {len(records)} 条同车违章记录")
                
        except Exception as e:
            logger.error(f"解析同车违章文件失败 {file_path}: {e}")
            continue
    
    logger.info(f"公安部同车违章解析完成，共 {len(result)} 个主体")
    return result


def _parse_coaddress_file(file_path: str) -> List[Dict]:
    """解析同住址xlsx文件"""
    records = []
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        sheet_name = None
        for name in xls.sheet_names:
            if "同住址" in name:
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
            record = {
                "name": _safe_str(row.get("姓名", "")),
                "gender": _safe_str(row.get("性别", "")),
                "birth_date": _safe_date(row.get("出生日期")),
                "id_number": _safe_str(row.get("身份证号", "")),
                "ethnicity": _safe_str(row.get("民族", "")),
                "native_place": _safe_str(row.get("籍贯", "")),
                "hukou_address": _safe_str(row.get("户籍地", "")),
                "former_name": _safe_str(row.get("曾用名", "")),
                "age": _safe_int(row.get("年龄")),
                "height": _safe_str(row.get("身高", "")),
                "occupation": _safe_str(row.get("职业", "")),
                "education": _safe_str(row.get("文化程度", "")),
                "person_status": _safe_str(row.get("人员状态", "")),
                "employer": _safe_str(row.get("从业单位", "")),
                "relation_to_head": _safe_str(row.get("与户主关系", "")),
                "hukou_district": _safe_str(row.get("户籍地区划", "")),
                "military_status": _safe_str(row.get("兵役情况", "")),
                "marital_status": _safe_str(row.get("婚姻状况", "")),
                "death_date": _safe_date(row.get("死亡日期")),
                "source_file": filename
            }
            
            if record["name"] or record["id_number"]:
                records.append(record)
        
    except Exception as e:
        logger.error(f"读取同住址文件失败 {file_path}: {e}")
    
    return records


def _parse_coviolation_file(file_path: str) -> List[Dict]:
    """解析同车违章xlsx文件"""
    records = []
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        sheet_name = None
        for name in xls.sheet_names:
            if "同车违章" in name:
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
            record = {
                "name": _safe_str(row.get("姓名", "")),
                "id_number": _safe_str(row.get("身份证号", "")),
                "plate_number": _safe_str(row.get("车号牌", "")),
                "violation_count": _safe_int(row.get("同次数")),
                "source_file": filename
            }
            
            if record["name"] or record["id_number"]:
                records.append(record)
        
    except Exception as e:
        logger.error(f"读取同车违章文件失败 {file_path}: {e}")
    
    return records


def get_relationship_graph(data_dir: str) -> Dict:
    """
    构建关系图谱数据
    
    基于同住址和同车违章数据，分析人员间的关联关系
    """
    coaddress_data = extract_coaddress_data(data_dir)
    coviolation_data = extract_coviolation_data(data_dir)
    
    # 节点集合
    nodes = {}
    # 边集合
    edges = []
    
    # 处理同住址关系
    for query_person, coaddress_list in coaddress_data.items():
        if query_person not in nodes:
            nodes[query_person] = {"id": query_person, "type": "person", "relations": []}
        
        for person in coaddress_list:
            person_id = person.get("id_number", "")
            if person_id and person_id != query_person:
                if person_id not in nodes:
                    nodes[person_id] = {
                        "id": person_id,
                        "name": person.get("name", ""),
                        "type": "person",
                        "relations": []
                    }
                
                relation = person.get("relation_to_head", "同住址")
                edges.append({
                    "source": query_person,
                    "target": person_id,
                    "relation_type": "同住址",
                    "relation": relation
                })
    
    # 处理同车违章关系
    for query_person, violations in coviolation_data.items():
        if query_person not in nodes:
            nodes[query_person] = {"id": query_person, "type": "person", "relations": []}
        
        for violation in violations:
            person_id = violation.get("id_number", "")
            plate = violation.get("plate_number", "")
            count = violation.get("violation_count", 0)
            
            if person_id and person_id != query_person:
                if person_id not in nodes:
                    nodes[person_id] = {
                        "id": person_id,
                        "name": violation.get("name", ""),
                        "type": "person",
                        "relations": []
                    }
                
                edges.append({
                    "source": query_person,
                    "target": person_id,
                    "relation_type": "同车违章",
                    "plate_number": plate,
                    "violation_count": count
                })
    
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "coaddress_persons": len(coaddress_data),
            "coviolation_persons": len(coviolation_data)
        }
    }


def _find_dir(data_dir: str, dir_name: str) -> Optional[str]:
    """在数据目录中查找指定目录"""
    data_path = Path(data_dir)
    
    for path in data_path.rglob("*"):
        if path.is_dir() and dir_name in path.name:
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


def _safe_int(value) -> int:
    if pd.isna(value):
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _safe_date(value) -> str:
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()[:10]


def get_cohabitation_summary(data_dir: str) -> Dict:
    """获取同住址/同车违章数据汇总"""
    coaddress = extract_coaddress_data(data_dir)
    coviolation = extract_coviolation_data(data_dir)
    
    return {
        "coaddress_persons": len(coaddress),
        "coaddress_records": sum(len(v) for v in coaddress.values()),
        "coviolation_persons": len(coviolation),
        "coviolation_records": sum(len(v) for v in coviolation.values())
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    # 测试同住址
    coaddress = extract_coaddress_data(test_dir)
    print(f"\n=== 公安部同住址 ({len(coaddress)} 个主体) ===")
    for person_id, records in coaddress.items():
        print(f"\n查询人: {person_id}")
        print(f"  同住址人数: {len(records)}")
        for r in records[:3]:
            print(f"    - {r.get('name')} ({r.get('relation_to_head', '未知关系')})")
    
    # 测试同车违章
    coviolation = extract_coviolation_data(test_dir)
    print(f"\n=== 公安部同车违章 ({len(coviolation)} 个主体) ===")
    for person_id, records in coviolation.items():
        print(f"\n查询人: {person_id}")
        for r in records[:3]:
            print(f"  - {r.get('name')}: 车牌 {r.get('plate_number')}, 同次 {r.get('violation_count')}")
    
    # 测试关系图谱
    graph = get_relationship_graph(test_dir)
    print(f"\n=== 关系图谱 ===")
    print(f"节点数: {graph['summary']['total_nodes']}")
    print(f"边数: {graph['summary']['total_edges']}")
    
    summary = get_cohabitation_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"同住址人数: {summary['coaddress_persons']}")
    print(f"同住址记录: {summary['coaddress_records']}")
    print(f"同车违章人数: {summary['coviolation_persons']}")
    print(f"同车违章记录: {summary['coviolation_records']}")
