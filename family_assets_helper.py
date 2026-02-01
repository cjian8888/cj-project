#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
家庭资产构建辅助模块
用于将精准查询数据和车辆数据转换为report_generator所需的family_assets格式

【修复 2026-01-29】
- 添加字段映射功能，将精准查询数据字段映射到report_generator期望的字段
- 支持房产和车辆数据的格式转换
"""

from typing import Dict, List

import utils

logger = utils.setup_logger(__name__)


def build_family_assets_from_data(precise_property_data: Dict, vehicle_data: Dict,
                                   family_tree: Dict, core_persons: List[str]) -> Dict:
    """
    从精准查询数据和车辆数据构建family_assets格式

    Args:
        precise_property_data: 精准查询房产数据 {person_id: [properties]}
        vehicle_data: 车辆数据 {person_id: [vehicles]}
        family_tree: 家族关系图谱
        core_persons: 核心人员列表

    Returns:
        family_assets格式: {核心人员: {家族成员, 房产套数, 房产总价值, 车辆数量, 房产, 车辆}}
    """
    family_assets = {}

    # 为每个核心人员构建资产数据
    for person in core_persons:
        # 获取家族成员列表
        family_members = []
        if person in family_tree:
            for member in family_tree[person]:
                name = member.get('姓名', '')
                if name and name != person:
                    family_members.append(name)

        # 如果没有family_tree数据，或者该人员没有家族成员
        # 至少包含自己（防止空列表）
        if not family_members:
            family_members = [person]

        # 收集房产数据（本人 + 家族成员）并进行字段映射
        all_properties = []

        # 添加本人的房产
        if person in precise_property_data:
            for prop in precise_property_data[person]:
                mapped_prop = _map_property_fields(prop)
                all_properties.append(mapped_prop)

        # 添加家族成员的房产
        for member in family_members:
            if member in precise_property_data and member != person:
                for prop in precise_property_data[member]:
                    mapped_prop = _map_property_fields(prop)
                    all_properties.append(mapped_prop)

        # 收集车辆数据（本人 + 家族成员）并进行字段映射
        all_vehicles = []

        # 添加本人的车辆
        if person in vehicle_data:
            for vehicle in vehicle_data[person]:
                mapped_vehicle = _map_vehicle_fields(vehicle)
                all_vehicles.append(mapped_vehicle)

        # 添加家族成员的车辆
        for member in family_members:
            if member in vehicle_data and member != person:
                for vehicle in vehicle_data[member]:
                    mapped_vehicle = _map_vehicle_fields(vehicle)
                    all_vehicles.append(mapped_vehicle)

        # 计算房产总价值（单位：万元）
        total_property_value = 0
        for prop in all_properties:
            try:
                price_str = prop.get('交易金额', '') or prop.get('不动产价格', '') or prop.get('房产价值', '')
                if price_str:
                    if '万' in str(price_str):
                        price = float(str(price_str).replace('万', '').replace(',', ''))
                    else:
                        price = float(str(price_str).replace(',', '')) / 10000
                    total_property_value += price
            except (ValueError, TypeError):
                pass

        # 转换为report_generator需要的格式
        family_assets[person] = {
            '家族成员': family_members,
            '房产套数': len(all_properties),
            '房产总价值': total_property_value,
            '车辆数量': len(all_vehicles),
            '房产': all_properties,
            '车辆': all_vehicles
        }

        logger.info(f"构建家庭资产数据: {person} - 房产{len(all_properties)}套, 车辆{len(all_vehicles)}辆")

    return family_assets


def build_family_assets_simple(precise_property_data: Dict, vehicle_data: Dict,
                               core_persons: List[str]) -> Dict:
    """
    简化版本：不依赖family_tree，每个核心人员独立构建资产数据

    Args:
        precise_property_data: 精准查询房产数据 {person_id: [properties]}
        vehicle_data: 车辆数据 {person_id: [vehicles]}
        core_persons: 核心人员列表

    Returns:
        family_assets格式: {核心人员: {家族成员, 房产套数, 房产总价值, 车辆数量, 房产, 车辆}}
    """
    family_assets = {}

    # 为每个核心人员构建资产数据
    for person in core_persons:
        # 收集房产数据并进行字段映射
        all_properties = []
        if person in precise_property_data:
            for prop in precise_property_data[person]:
                mapped_prop = _map_property_fields(prop)
                all_properties.append(mapped_prop)

        # 收集车辆数据并进行字段映射
        all_vehicles = []
        if person in vehicle_data:
            for vehicle in vehicle_data[person]:
                mapped_vehicle = _map_vehicle_fields(vehicle)
                all_vehicles.append(mapped_vehicle)

        # 计算房产总价值（单位：万元）
        total_property_value = 0
        for prop in all_properties:
            try:
                price_str = prop.get('交易金额', '') or prop.get('不动产价格', '') or prop.get('房产价值', '')
                if price_str:
                    if '万' in str(price_str):
                        price = float(str(price_str).replace('万', '').replace(',', ''))
                    else:
                        price = float(str(price_str).replace(',', '')) / 10000
                    total_property_value += price
            except (ValueError, TypeError):
                pass

        # 转换为report_generator需要的格式
        family_assets[person] = {
            '家族成员': [person],  # 只有自己
            '房产套数': len(all_properties),
            '房产总价值': total_property_value,
            '车辆数量': len(all_vehicles),
            '房产': all_properties,
            '车辆': all_vehicles
        }

        logger.info(f"构建家庭资产数据(简化版): {person} - 房产{len(all_properties)}套, 车辆{len(all_vehicles)}辆")

    return family_assets


def _map_property_fields(prop: Dict) -> Dict:
    """
    将精准查询数据字段映射到report_generator期望的字段

    输入字段（来自精准查询）:
    - location: 不动产坐落
    - area: 不动产面积
    - usage: 规划用途
    - owner_name: 权利人名称
    - owner_id: 权利人证件号码
    - co_owners: 共有权人名称
    - register_date: 登记时间
    - status: 权属状态
    - certificate_number: 不动产权证号
    - is_mortgaged: 是否抵押
    - is_sealed: 是否查封

    输出字段（report_generator期望）:
    - 房地坐落
    - 建筑面积
    - 规划用途
    - 产权人
    - 身份证号
    - 共有情况
    - 登记时间
    - 权属状态
    - 不动产权证号
    - 是否抵押
    - 是否查封
    - 数据质量
    """
    return {
        '房地坐落': prop.get('location', ''),
        '建筑面积': prop.get('area', 0),
        '规划用途': prop.get('usage', ''),
        '产权人': prop.get('owner_name', ''),
        '身份证号': prop.get('owner_id', ''),
        '共有情况': prop.get('co_owners', ''),
        '登记时间': prop.get('register_date', ''),
        '权属状态': prop.get('status', ''),
        '不动产权证号': prop.get('certificate_number', ''),
        '是否抵押': '是' if prop.get('is_mortgaged', False) else '否',
        '是否查封': '是' if prop.get('is_sealed', False) else '否',
        '数据质量': '正常'
    }


def _map_vehicle_fields(vehicle: Dict) -> Dict:
    """
    将车辆数据字段映射到report_generator期望的字段

    输入字段:
    - 所有人
    - 号牌号码
    - 中文品牌
    - 车身颜色
    - 初次登记日期
    - 机动车状态
    - 是否抵押质押
    - 能源种类
    - 住所地址

    输出字段（report_generator期望，与输入相同）
    """
    return {
        '所有人': vehicle.get('所有人', ''),
        '号牌号码': vehicle.get('号牌号码', ''),
        '中文品牌': vehicle.get('中文品牌', ''),
        '车身颜色': vehicle.get('车身颜色', ''),
        '初次登记日期': vehicle.get('初次登记日期', ''),
        '机动车状态': vehicle.get('机动车状态', ''),
        '是否抵押质押': vehicle.get('是否抵押质押', 0),
        '能源种类': vehicle.get('能源种类', ''),
        '住所地址': vehicle.get('住所地址', '')
    }
