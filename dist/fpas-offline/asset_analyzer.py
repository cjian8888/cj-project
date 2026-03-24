#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资产分析模块
从自然资源部、公安部机动车等数据源提取房产、车辆信息，计算家族总资产
"""

import os
import glob
from typing import Dict, List
import pandas as pd

import config
import utils

logger = utils.setup_logger(__name__)


def clean_property_amount(amount) -> float:
    """
    清洗房产交易金额（处理异常值）
    
    Args:
        amount: 原始金额（万元）
    
    Returns:
        清洗后的金额（万元）
    """
    if pd.isna(amount):
        return 0.0
    
    try:
        amount_float = utils.format_amount_to_wan(amount, unit_hint_multiplier=10000.0)
        
        # 如果金额超过50000万元（5亿），很可能是单位错误，除以10000
        if amount_float > config.ASSET_LARGE_AMOUNT_THRESHOLD:
            logger.warning(f'检测到异常房产金额 {amount_float}万元，自动修正为 {amount_float/10000:.2f}万元')
            return amount_float / 10000
        
        return amount_float
    except (ValueError, TypeError):
        return 0.0


def extract_properties(data_directory: str, persons: List[str]) -> List[Dict]:
    """
    从"自然资源部全国总库"提取房产信息（带去重）
    
    Args:
        data_directory: 数据目录
        persons: 人员列表
    
    Returns:
        房产列表，每套房产包含：产权人、地址、面积、金额、共有人等
        
    注意：
        1. 同一房产可能因夫妻共有而在不同人名下都有记录，需要去重
        2. 使用(房地坐落, 登记时间, 建筑面积)作为唯一键
        3. 保留第一次出现的产权人，其他人作为共有人
    """
    logger.info('=' * 60)
    logger.info('开始提取房产信息（带去重）')
    logger.info('=' * 60)
    
    all_properties = []
    # 用于去重的字典，key为(房地坐落, 登记时间字符串, 建筑面积)
    property_dedup = {}
    
    for person in persons:
        # 查找房产数据文件
        pattern = os.path.join(
            data_directory,
            '**',
            '自然资源部全国总库（定向查询）',
            f'{person}_*_自然资源部（全国库）.xlsx'
        )
        
        files = glob.glob(pattern, recursive=True)
        
        if not files:
            logger.debug(f'{person} 未找到房产数据')
            continue
        
        for file_path in files:
            try:
                df = pd.read_excel(file_path)
                
                if df.empty:
                    logger.info(f'{person} 房产数据为空')
                    continue
                
                person_count = 0
                dup_count = 0
                
                # 提取房产信息
                for _, row in df.iterrows():
                    # 原始金额
                    raw_amount = row.get('交易金额(万元)', 0)
                    cleaned_amount = clean_property_amount(raw_amount)
                    raw_date = row.get('登记时间', '')
                    
                    # 构建去重键
                    address = str(row.get('房地坐落', '')).strip()
                    area = float(row.get('建筑面积(平方米)', 0))
                    date_key = str(raw_date)[:10] if raw_date else ''  # 只取日期部分
                    
                    dedup_key = (address, date_key, area)
                    
                    # 检查是否已存在
                    if dedup_key in property_dedup:
                        # 已存在，将当前产权人添加为共有人
                        existing_idx = property_dedup[dedup_key]
                        existing_prop = all_properties[existing_idx]
                        
                        # 更新共有人信息
                        existing_co_owners = existing_prop.get('共有人名称', '') or ''
                        if person not in existing_co_owners and person != existing_prop.get('产权人', ''):
                            if existing_co_owners:
                                existing_prop['共有人名称'] = f"{existing_co_owners}, {person}"
                            else:
                                existing_prop['共有人名称'] = person
                            existing_prop['共有情况'] = '共同共有'
                        
                        dup_count += 1
                        continue
                    
                    # 数据质量评估
                    quality_issues = []
                    if pd.isna(raw_amount) or raw_amount == 0:
                        quality_issues.append('金额缺失')
                    elif clean_property_amount(raw_amount) > config.ASSET_LARGE_AMOUNT_THRESHOLD:
                        quality_issues.append('金额异常已修正')
                    
                    # 检查日期异常（1899/1900年是Excel默认值）
                    date_str = str(raw_date)
                    if '1899' in date_str or '1900' in date_str:
                        quality_issues.append('日期异常')
                    
                    quality_status = '正常' if not quality_issues else '; '.join(quality_issues)
                    
                    property_info = {
                        '产权人': person,
                        '姓名': row.get('名称', person),
                        '证件号码': row.get('证件号码', ''),
                        '房地坐落': address,
                        '建筑面积': area,
                        '规划用途': row.get('规划用途', ''),
                        '房屋性质': row.get('房屋性质', ''),
                        '竣工时间': row.get('竣工时间', ''),
                        '不动产权证号': row.get('不动产权证号', ''),
                        '登记时间': row.get('登记时间', ''),
                        '交易金额_原始': raw_amount,
                        '交易金额': cleaned_amount,
                        '共有情况': row.get('共有情况', ''),
                        '共有人名称': row.get('共有人名称', ''),
                        '共有人证件号码': row.get('共有人证件号码', ''),
                        '权属状态': row.get('权属状态', ''),
                        '数据质量': quality_status,
                        '数据来源': '自然资源部全国总库'
                    }
                    
                    # 记录去重索引
                    property_dedup[dedup_key] = len(all_properties)
                    all_properties.append(property_info)
                    person_count += 1
                
                if dup_count > 0:
                    logger.info(f'✓ {person} 提取房产 {person_count} 套（跳过重复 {dup_count} 条）')
                else:
                    logger.info(f'✓ {person} 提取房产 {person_count} 套')
                
            except Exception as e:
                logger.warning(f'读取房产数据失败 {file_path}: {str(e)}')
    
    logger.info(f'\n房产信息提取完成，去重后共 {len(all_properties)} 套')
    
    return all_properties


def extract_vehicles(data_directory: str, persons: List[str]) -> List[Dict]:
    """
    从"公安部机动车"提取车辆信息
    
    Args:
        data_directory: 数据目录
        persons: 人员列表
    
    Returns:
        车辆列表，每辆车包含：所有人、车牌号、品牌、登记日期等
    """
    logger.info('=' * 60)
    logger.info('开始提取车辆信息')
    logger.info('=' * 60)
    
    all_vehicles = []
    
    for person in persons:
        # 查找车辆数据文件（注意文件名模式）
        patterns = [
            os.path.join(data_directory, '**', '公安部机动车（定向查询）', f'{person}_*_公安部机动车信息_1.xlsx'),
            os.path.join(data_directory, '**', '公安部机动车（定向查询）', f'{person}_*_公安部机动车信息_2.xlsx'),
        ]
        
        files = []
        for pattern in patterns:
            files.extend(glob.glob(pattern, recursive=True))
        
        if not files:
            logger.debug(f'{person} 未找到车辆数据')
            continue
        
        for file_path in files:
            try:
                df = pd.read_excel(file_path)
                
                if df.empty:
                    logger.info(f'{person} 车辆数据为空')
                    continue
                
                # 提取车辆信息
                for _, row in df.iterrows():
                    vehicle_info = {
                        '所有人': person,
                        '机动车所有人': row.get('机动车所有人', person),
                        '身份证号': row.get('身份证号', ''),
                        '号牌号码': row.get('号牌号码', ''),
                        '号牌种类': row.get('号牌种类', ''),
                        '中文品牌': row.get('中文品牌', ''),
                        '车身颜色': row.get('车身颜色', ''),
                        '初次登记日期': row.get('初次登记日期', ''),
                        '车辆识别代码': row.get('车辆识别代码', ''),
                        '机动车状态': row.get('机动车状态', ''),
                        '是否抵押质押': row.get('是否抵押/质押', 0),
                        '发动机型号': row.get('机动车发动机型号', ''),
                        '能源种类': row.get('机动车能源种类', ''),
                        '发动机排量': row.get('机动车发动机排量', ''),
                        '核定载客人数': row.get('机动车核定载客人数', ''),
                        '出厂日期': row.get('出厂日期', ''),
                        '住所地址': row.get('住所地址', ''),
                        '数据来源': '公安部机动车'
                    }
                    all_vehicles.append(vehicle_info)
                
                logger.info(f'✓ {person} 提取车辆 {len(df)} 辆')
                
            except Exception as e:
                logger.warning(f'读取车辆数据失败 {file_path}: {str(e)}')
    
    logger.info(f'\n车辆信息提取完成，共 {len(all_vehicles)} 辆')
    
    return all_vehicles


def calculate_family_assets(
    properties: List[Dict],
    vehicles: List[Dict],
    family_tree: Dict[str, List[Dict]]
) -> Dict[str, Dict]:
    """
    计算家族总资产（带全局去重）
    
    Args:
        properties: 房产列表（已去重）
        vehicles: 车辆列表
        family_tree: 家族关系图谱
    
    Returns:
        家族资产汇总，格式：{核心人员: {房产: [], 车辆: [], 总资产: 0}}
        
    注意：
        1. 同一房产只会被分配给一个核心人员（优先分配给产权人本人）
        2. 如果产权人不是核心人员，则分配给第一个包含产权人的核心人员家庭
        3. 避免因核心人员家族成员重叠导致的重复统计
    """
    logger.info('=' * 60)
    logger.info('开始计算家族资产（带去重）')
    logger.info('=' * 60)
    
    family_assets = {}
    
    # 全局跟踪：已分配的房产和车辆（使用房产地址作为key）
    assigned_properties = set()
    assigned_vehicles = set()
    
    # 获取所有核心人员列表
    core_persons = list(family_tree.keys())
    
    # 第一遍：先为每个核心人员建立家族成员列表
    person_to_family = {}
    for person, family_members in family_tree.items():
        family_names = [person]
        for member in family_members:
            name = member.get('姓名', '')
            if name and name != person:
                family_names.append(name)
        person_to_family[person] = family_names
    
    # 第二遍：为每个核心人员分配资产（优先分配给产权人本人）
    for person in core_persons:
        family_names = person_to_family[person]
        
        # 筛选属于该人员本人名下的房产（优先）
        family_properties = []
        for prop in properties:
            owner = prop.get('产权人', '')
            address = prop.get('房地坐落', '')
            
            # 使用地址作为唯一标识
            prop_key = address
            
            # 如果这个房产已经分配给其他人，跳过
            if prop_key in assigned_properties:
                continue
            
            # 优先规则：如果产权人是当前核心人员本人
            if owner == person:
                family_properties.append(prop)
                assigned_properties.add(prop_key)
            # 次优先：如果产权人是当前核心人员的家族成员，且产权人不是其他核心人员
            elif owner in family_names and owner not in core_persons:
                family_properties.append(prop)
                assigned_properties.add(prop_key)
        
        # 筛选属于该人员的车辆
        family_vehicles = []
        for vehicle in vehicles:
            owner = vehicle.get('所有人', '')
            plate = vehicle.get('号牌号码', '')
            
            vehicle_key = plate
            
            if vehicle_key in assigned_vehicles:
                continue
            
            # 同样的优先规则
            if owner == person:
                family_vehicles.append(vehicle)
                assigned_vehicles.add(vehicle_key)
            elif owner in family_names and owner not in core_persons:
                family_vehicles.append(vehicle)
                assigned_vehicles.add(vehicle_key)
        
        # 计算总资产（房产金额）
        total_property_value = sum(prop.get('交易金额', 0) for prop in family_properties)
        
        family_assets[person] = {
            '家族成员': family_names,
            '房产': family_properties,
            '车辆': family_vehicles,
            '房产套数': len(family_properties),
            '车辆数量': len(family_vehicles),
            '房产总价值': total_property_value
        }
        
        logger.info(f'\n【{person}】家族资产:')
        logger.info(f'  成员: {len(family_names)} 人 - {", ".join(family_names)}')
        logger.info(f'  房产: {len(family_properties)} 套，总价值 {total_property_value:.2f} 万元')
        logger.info(f'  车辆: {len(family_vehicles)} 辆')
    
    # 第三遍：处理未分配的共有房产（分配给第一个涉及的核心人员）
    unassigned_count = 0
    for prop in properties:
        address = prop.get('房地坐落', '')
        if address in assigned_properties:
            continue
        
        # 找到第一个涉及此房产的核心人员
        owner = prop.get('产权人', '')
        co_owner = prop.get('共有人名称', '') or ''
        
        for person in core_persons:
            family_names = person_to_family[person]
            if owner in family_names or any(co in family_names for co in co_owner.split(',')):
                family_assets[person]['房产'].append(prop)
                family_assets[person]['房产套数'] += 1
                family_assets[person]['房产总价值'] += prop.get('交易金额', 0)
                assigned_properties.add(address)
                unassigned_count += 1
                break
    
    if unassigned_count > 0:
        logger.info(f'\n额外分配共有房产: {unassigned_count} 套')
    
    logger.info(f'\n家族资产计算完成')
    
    return family_assets


def get_asset_summary(family_assets: Dict[str, Dict]) -> pd.DataFrame:
    """
    生成资产汇总表
    
    Args:
        family_assets: 家族资产数据
    
    Returns:
        资产汇总DataFrame
    """
    summary_data = []
    
    for person, assets in family_assets.items():
        summary_data.append({
            '核心人员': person,
            '家族成员数': len(assets['家族成员']),
            '家族成员': ', '.join(assets['家族成员']),
            '房产套数': assets['房产套数'],
            '房产总价值(万元)': assets['房产总价值'],
            '车辆数量': assets['车辆数量']
        })
    
    return pd.DataFrame(summary_data)


if __name__ == '__main__':
    # 测试代码
    import sys
    import family_analyzer
    
    data_dir = sys.argv[1] if len(sys.argv) > 1 else './data'
    test_persons = ['朱明', '朱永平', '陈斌', '马尚德']
    
    # 先构建家族关系
    family_tree = family_analyzer.build_family_tree(test_persons, data_dir)
    
    # 提取资产
    properties = extract_properties(data_dir, test_persons)
    vehicles = extract_vehicles(data_dir, test_persons)
    
    # 计算家族资产
    family_assets = calculate_family_assets(properties, vehicles, family_tree)
    
    # 生成汇总表
    summary_df = get_asset_summary(family_assets)
    
    print('\n' + '=' * 80)
    print('家族资产汇总表')
    print('=' * 80)
    print(summary_df.to_string(index=False))
    
    # 详细房产信息
    print('\n' + '=' * 80)
    print('房产明细')
    print('=' * 80)
    for person, assets in family_assets.items():
        if assets['房产']:
            print(f'\n【{person}】')
            for prop in assets['房产']:
                print(f"  - {prop['房地坐落']}")
                print(f"    面积: {prop['建筑面积']}㎡, 金额: {prop['交易金额']:.2f}万元")
                if prop['共有人名称']:
                    print(f"    共有人: {prop['共有人名称']}")
