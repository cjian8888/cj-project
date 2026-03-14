#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF资产信息提取模块 - 资金穿透与关联排查系统
从资产证明PDF中提取结构化信息
"""

import os
import re
import pdfplumber
from typing import Dict, List, Optional
import utils
from utils.safe_types import safe_float as safe_float_util


logger = utils.setup_logger(__name__)


def extract_property_info(pdf_path: str) -> Dict:
    """
    从房产证明PDF提取信息
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        房产信息字典
    """
    logger.info(f'正在提取房产信息: {pdf_path}')
    
    property_info = {
        'file': os.path.basename(pdf_path),
        'address': None,
        'area': None,
        'owner': None,
        'certificate_number': None,
        'acquisition_date': None,
        'raw_text': ''
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ''
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + '\n'
            
            property_info['raw_text'] = full_text
            
            # 提取地址(常见模式)
            address_patterns = [
                r'(?:房屋坐落|坐落|地址|房屋地址)[:：\s]*([\u4e00-\u9fa5\w\s]+)',
                r'([\u4e00-\u9fa5]+[市区县][\u4e00-\u9fa5]+[路街道][\d\w\-#号楼室]+)'
            ]
            for pattern in address_patterns:
                match = re.search(pattern, full_text)
                if match:
                    property_info['address'] = match.group(1).strip()
                    break
            
            # 提取面积
            area_patterns = [
                r'(?:建筑面积|面积|总面积)[:：\s]*([\d.]+)\s*(?:平方米|㎡|m2)',
                r'([\d.]+)\s*(?:平方米|㎡|m2)'
            ]
            for pattern in area_patterns:
                match = re.search(pattern, full_text)
                if match:
                    try:
                        property_info['area'] = float(match.group(1))
                        break
                    except (ValueError, TypeError):
                        pass
            
            # 提取权利人/所有权人
            owner_patterns = [
                r'(?:权利人|所有权人|产权人|业主)[:：\s]*([\u4e00-\u9fa5]{2,4})',
            ]
            for pattern in owner_patterns:
                match = re.search(pattern, full_text)
                if match:
                    property_info['owner'] = match.group(1).strip()
                    break
            
            # 提取证书编号
            cert_patterns = [
                r'(?:证书编号|证号|房产证号)[:：\s]*([\w\-]+)',
                r'([A-Z0-9]{10,})'
            ]
            for pattern in cert_patterns:
                match = re.search(pattern, full_text)
                if match:
                    property_info['certificate_number'] = match.group(1).strip()
                    break
            
            # 提取登记日期
            date_patterns = [
                r'(?:登记日期|发证日期|颁发日期)[:：\s]*(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2}日?)',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, full_text)
                if match:
                    date_str = match.group(1)
                    property_info['acquisition_date'] = utils.parse_date(date_str)
                    break
            
            logger.info(f'房产信息提取完成: 地址={property_info["address"]}, 面积={property_info["area"]}')
            
    except Exception as e:
        logger.error(f'提取房产信息失败: {pdf_path}, 错误: {str(e)}')
    
    return property_info


def extract_vehicle_info(pdf_path: str) -> Dict:
    """
    从车辆证明PDF提取信息
    
    Args:
        pdf_path: PDF文件路径
        
    Returns:
        车辆信息字典
    """
    logger.info(f'正在提取车辆信息: {pdf_path}')
    
    vehicle_info = {
        'file': os.path.basename(pdf_path),
        'brand': None,
        'model': None,
        'license_plate': None,
        'owner': None,
        'registration_date': None,
        'price': None,
        'raw_text': ''
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ''
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + '\n'
            
            vehicle_info['raw_text'] = full_text
            
            # 提取车辆品牌和型号
            luxury_brands = ['奔驰', '宝马', '奥迪', '保时捷', '特斯拉', '路虎', '雷克萨斯']
            for brand in luxury_brands:
                if brand in full_text:
                    vehicle_info['brand'] = brand
                    break
            
            # 提取型号
            model_patterns = [
                r'(?:车辆型号|型号)[:：\s]*([\w\-\s]+)',
            ]
            for pattern in model_patterns:
                match = re.search(pattern, full_text)
                if match:
                    vehicle_info['model'] = match.group(1).strip()
                    break
            
            # 提取车牌号
            plate_patterns = [
                r'([京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5})',
                r'(?:车牌号|号牌号码)[:：\s]*([京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5})'
            ]
            for pattern in plate_patterns:
                match = re.search(pattern, full_text)
                if match:
                    vehicle_info['license_plate'] = match.group(1).strip()
                    break
            
            # 提取所有人
            owner_patterns = [
                r'(?:所有人|车主|所有者)[:：\s]*([\u4e00-\u9fa5]{2,4})',
            ]
            for pattern in owner_patterns:
                match = re.search(pattern, full_text)
                if match:
                    vehicle_info['owner'] = match.group(1).strip()
                    break
            
            # 提取注册日期
            date_patterns = [
                r'(?:注册日期|登记日期|初次登记)[:：\s]*(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2}日?)',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, full_text)
                if match:
                    date_str = match.group(1)
                    vehicle_info['registration_date'] = utils.parse_date(date_str)
                    break
            
            # 提取价格
            price_patterns = [
                r'(?:购置价|价格|车价)[:：\s]*([\d,.]+)\s*(?:元|万元)',
                r'([\d,.]+)\s*万元'
            ]
            for pattern in price_patterns:
                match = re.search(pattern, full_text)
                if match:
                    try:
                        price_str = match.group(1)
                        unit_hint = 10000.0 if '万' in match.group(0) else 1.0
                        vehicle_info['price'] = utils.format_amount(
                            price_str,
                            unit_hint_multiplier=unit_hint,
                        )
                        break
                    except (ValueError, TypeError):
                        pass
            
            logger.info(f'车辆信息提取完成: 品牌={vehicle_info["brand"]}, 车牌={vehicle_info["license_plate"]}')
            
    except Exception as e:
        logger.error(f'提取车辆信息失败: {pdf_path}, 错误: {str(e)}')
    
    return vehicle_info


def extract_assets_from_directory(directory: str) -> Dict[str, List[Dict]]:
    """
    从目录提取所有资产证明信息
    
    Args:
        directory: 目录路径
        
    Returns:
        资产信息字典 {'properties': [], 'vehicles': []}
    """
    logger.info(f'正在扫描资产证明文件: {directory}')
    
    assets = {
        'properties': [],
        'vehicles': []
    }
    
    # 资产文件关键词
    property_keywords = ['房产', '房屋', '不动产', '产权证']
    vehicle_keywords = ['车辆', '行驶证', '机动车', '汽车']
    
    for filename in os.listdir(directory):
        if not filename.endswith('.pdf'):
            continue
        
        file_path = os.path.join(directory, filename)
        
        # 判断文件类型
        is_property = any(kw in filename for kw in property_keywords)
        is_vehicle = any(kw in filename for kw in vehicle_keywords)
        
        if is_property:
            info = extract_property_info(file_path)
            assets['properties'].append(info)
        elif is_vehicle:
            info = extract_vehicle_info(file_path)
            assets['vehicles'].append(info)
    
    logger.info(f'提取完成: {len(assets["properties"])} 个房产, {len(assets["vehicles"])} 辆车辆')
    
    return assets


def cross_validate_with_transactions(assets: Dict, 
                                     hidden_assets: Dict[str, List[Dict]]) -> List[Dict]:
    """
    将资产证明与流水中的隐形资产交叉验证
    
    Args:
        assets: 从PDF提取的资产信息
        hidden_assets: 从流水检测到的隐形资产
        
    Returns:
        交叉验证结果列表
    """
    logger.info('正在进行资产交叉验证...')
    
    validations = []
    
    # 验证房产
    for entity, asset_list in hidden_assets.items():
        for asset in asset_list:
            if asset['type'] != 'property':
                continue
            
            # 查找时间相近的房产证明
            transaction_date = asset['date']
            
            for prop in assets['properties']:
                if not prop['acquisition_date']:
                    continue
                
                # 检查日期是否相近(±1年)
                days_diff = abs((transaction_date - prop['acquisition_date']).days)
                if days_diff <= 365:
                    validation = {
                        'type': 'property',
                        'entity': entity,
                        'transaction_amount': asset['amount'],
                        'transaction_date': transaction_date,
                        'certificate_date': prop['acquisition_date'],
                        'address': prop['address'],
                        'area': prop['area'],
                        'owner': prop['owner'],
                        'match_confidence': 'high' if days_diff <= 90 else 'medium',
                        'asset_record': asset,
                        'certificate_info': prop
                    }
                    validations.append(validation)
    
    # 验证车辆
    for entity, asset_list in hidden_assets.items():
        for asset in asset_list:
            if asset['type'] != 'vehicle':
                continue
            
            transaction_date = asset['date']
            
            for veh in assets['vehicles']:
                if not veh['registration_date']:
                    continue
                
                # 检查日期是否相近(±6个月)
                days_diff = abs((transaction_date - veh['registration_date']).days)
                if days_diff <= 180:
                    validation = {
                        'type': 'vehicle',
                        'entity': entity,
                        'transaction_amount': asset['amount'],
                        'transaction_date': transaction_date,
                        'registration_date': veh['registration_date'],
                        'brand': veh['brand'],
                        'model': veh['model'],
                        'license_plate': veh['license_plate'],
                        'owner': veh['owner'],
                        'match_confidence': 'high' if days_diff <= 30 else 'medium',
                        'asset_record': asset,
                        'certificate_info': veh
                    }
                    validations.append(validation)
    
    logger.info(f'交叉验证完成: {len(validations)} 个匹配项')
    
    return validations


# =============================================================================
# 自然资源部精准查询解析 (Phase 7.4)
# =============================================================================

PRECISE_PROPERTY_DIR_NAME = "自然资源部精准查询（定向查询）"


def extract_precise_property_info(data_dir: str, person_id: str = None) -> Dict[str, List[Dict]]:
    """
    从自然资源部精准查询目录提取不动产信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, List[Dict]]: 按身份证号分组的不动产数据
    """
    import pandas as pd
    from pathlib import Path
    
    result = {}
    
    # 查找目录
    precise_dir = _find_precise_property_dir(data_dir)
    if not precise_dir:
        logger.warning(f"未找到自然资源部精准查询目录: {PRECISE_PROPERTY_DIR_NAME}")
        return result
    
    logger.info(f"开始解析自然资源部精准查询数据: {precise_dir}")
    
    # 遍历所有xlsx文件
    precise_path = Path(precise_dir)
    xlsx_files = [f for f in precise_path.glob("*.xlsx") if not f.name.startswith("~$")]
    
    for file_path in xlsx_files:
        try:
            # 从文件名提取身份证号
            file_person_id = _extract_id_from_filename_precise(file_path.name)
            
            if person_id and file_person_id != person_id:
                continue
            
            # 解析文件
            properties = parse_precise_property_file(str(file_path))
            
            if file_person_id and properties:
                if file_person_id not in result:
                    result[file_person_id] = []
                result[file_person_id].extend(properties)
                
        except Exception as e:
            logger.error(f"解析精准查询文件失败 {file_path}: {e}")
            continue
    
    # 去重
    for pid in result:
        result[pid] = _deduplicate_properties(result[pid])
    
    logger.info(f"自然资源部精准查询解析完成: {len(result)} 个主体")
    return result


def parse_precise_property_file(file_path: str) -> List[Dict]:
    """解析单个精准查询xlsx文件"""
    import pandas as pd
    from pathlib import Path
    
    properties = []
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # 查找sheet
        sheet_name = None
        for name in xls.sheet_names:
            if "精准查询" in name or "自然资源" in name:
                sheet_name = name
                break
        
        if not sheet_name:
            sheet_name = xls.sheet_names[0] if xls.sheet_names else None
        
        if not sheet_name:
            return properties
        
        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        if df.empty:
            return properties
        
        for _, row in df.iterrows():
            prop = _parse_precise_property_row(row, filename)
            if prop and prop.get("location"):
                properties.append(prop)
        
    except Exception as e:
        logger.error(f"读取精准查询文件失败 {file_path}: {e}")
    
    return properties


def _parse_precise_property_row(row, source_file: str) -> Optional[Dict]:
    """解析单行精准查询数据"""
    import pandas as pd
    
    def safe_str(value) -> str:
        if pd.isna(value):
            return ""
        return str(value).strip()
    
    def safe_bool(value) -> bool:
        if pd.isna(value):
            return False
        s = str(value).strip().lower()
        return s in ["是", "yes", "true", "1"]
    
    try:
        prop = {
            # 【修复】支持多种列名格式（全国总库 vs 精准查询）
            "location": safe_str(row.get("房地坐落") or row.get("不动产坐落", "")),
            "area": safe_str(row.get("建筑面积(平方米)") or row.get("不动产面积", "")),
            "usage": safe_str(row.get("规划用途", "")),
            "right_type": safe_str(row.get("权利类型", "")),
            "owner_name": safe_str(row.get("名称") or row.get("权利人名称", "")),
            "owner_id": safe_str(row.get("证件号码") or row.get("权利人证件号码", "")),
            "co_owners": safe_str(row.get("共有人名称") or row.get("共有权人名称", "")),
            "ownership_type": safe_str(row.get("共有情况") or row.get("共用方式", "")),
            "property_number": safe_str(row.get("不动产单元号", "")),
            "certificate_number": safe_str(row.get("不动产权证号", "")),
            "register_date": safe_str(row.get("登记时间", ""))[:10],
            "status": safe_str(row.get("权属状态", "")),
            "is_mortgaged": safe_bool(row.get("是否抵押")),
            "is_sealed": safe_bool(row.get("是否查封")),
            "query_region": safe_str(row.get("查询申请地区", "")),
            "query_unit": safe_str(row.get("查询单位", "")),
            "transaction_price": safe_float_util(row.get("交易金额(万元)", 0)) or 0.0,
            "source_file": source_file
        }
        
        return prop
        
    except Exception as e:
        logger.debug(f"解析精准查询行失败: {e}")
        return None


def _find_precise_property_dir(data_dir: str) -> Optional[str]:
    """查找自然资源部精准查询目录"""
    from pathlib import Path
    data_path = Path(data_dir)
    
    for path in data_path.rglob("*"):
        if path.is_dir() and PRECISE_PROPERTY_DIR_NAME in path.name:
            return str(path)
    
    return None


def _extract_id_from_filename_precise(filename: str) -> Optional[str]:
    """从文件名提取身份证号"""
    pattern = r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    match = re.search(pattern, filename)
    
    if match:
        return match.group().upper()
    
    return None


def _deduplicate_properties(properties: List[Dict]) -> List[Dict]:
    """按不动产单元号去重"""
    seen = set()
    unique = []
    
    for p in properties:
        key = p.get("property_number", "") or p.get("location", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(p)
    
    return unique


def get_person_precise_properties(data_dir: str, person_id: str) -> List[Dict]:
    """获取指定人员的精准查询不动产列表"""
    result = extract_precise_property_info(data_dir, person_id)
    return result.get(person_id, [])


def get_precise_property_summary(data_dir: str) -> Dict:
    """获取精准查询不动产汇总"""
    all_data = extract_precise_property_info(data_dir)
    
    total_persons = len(all_data)
    total_properties = sum(len(v) for v in all_data.values())
    mortgaged_count = sum(1 for props in all_data.values() for p in props if p.get("is_mortgaged"))
    sealed_count = sum(1 for props in all_data.values() for p in props if p.get("is_sealed"))
    
    return {
        "total_persons": total_persons,
        "total_properties": total_properties,
        "mortgaged_count": mortgaged_count,
        "sealed_count": sealed_count
    }
