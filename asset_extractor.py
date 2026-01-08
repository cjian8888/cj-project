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
                        price_str = match.group(1).replace(',', '')
                        vehicle_info['price'] = float(price_str)
                        if '万元' in match.group(0):
                            vehicle_info['price'] *= 10000
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
