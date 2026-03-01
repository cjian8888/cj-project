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
import re

import utils


def _normalize_property_address(address: str) -> str:
    """
    【新增】标准化房产地址，用于模糊匹配去重

    处理规则：
    1. 去除首尾空格
    2. 统一全角/半角括号
    3. 车位地址：去除末尾的"室"字（车位不应该有"室"）
    4. 统一"地下1层"为"地下一层"
    5. 去除多余空格
    """
    if not address:
        return ""

    normalized = address.strip()

    # 1. 统一全角/半角括号 -> 全角
    normalized = normalized.replace("(", "（").replace(")", "）")

    # 2. 车位特殊处理：如果包含"车位"，去除末尾的"室"
    if "车位" in normalized:
        normalized = re.sub(r"室$", "", normalized)

    # 3. 统一"地下1层"等数字层为中文
    floor_map = {"1": "一", "2": "二", "3": "三", "4": "四", "5": "五"}
    for num, cn in floor_map.items():
        normalized = re.sub(f"地下{num}层", f"地下{cn}层", normalized)
        normalized = re.sub(f"{num}层", f"{cn}层", normalized)

    # 4. 去除多余空格
    normalized = re.sub(r"\s+", "", normalized)

    return normalized


logger = utils.setup_logger(__name__)


def _get_family_members(family_tree: Dict, person: str) -> List[str]:
    """
    从家族关系树中获取指定人员的家族成员列表。

    如果该人员在family_tree中无记录或家族成员为空，
    返回包含该人员自身的单元素列表（防止空列表）。

    Args:
        family_tree: 家族关系图谱
        person: 核心人员名称

    Returns:
        家族成员列表（不包括核心人员自身）
    """
    family_members = []
    if person in family_tree:
        for member in family_tree[person]:
            name = member.get("姓名", "")
            if name and name != person:
                family_members.append(name)

    # 如果没有家族成员，至少包含自己
    if not family_members:
        family_members = [person]

    return family_members


def _extract_property_location(prop: Dict) -> str:
    """
    从房产数据中提取地址信息。

    按优先级尝试多个可能的字段名。

    Args:
        prop: 房产数据字典

    Returns:
        地址字符串，未找到返回空字符串
    """
    return (
        prop.get("房地坐落", "")
        or prop.get("坐落", "")
        or prop.get("location", "")
        or prop.get("address", "")
    )


def _collect_unique_properties(
    precise_property_data: Dict, person: str, family_members: List[str]
) -> List[Dict]:
    """
    收集核心人员及其家族成员的所有房产数据（去重）。

    使用标准化地址进行去重，避免同一房产被重复统计。

    Args:
        precise_property_data: 房产数据字典
        person: 核心人员名称
        family_members: 家族成员列表

    Returns:
        去重后的房产列表
    """
    unique_properties = {}  # 用于去重：标准化地址 -> property

    # 添加本人的房产
    if person in precise_property_data:
        for prop in precise_property_data[person]:
            mapped_prop = _map_property_fields(prop)
            location = _extract_property_location(mapped_prop)
            if location:
                normalized_loc = _normalize_property_address(location)
                if normalized_loc and normalized_loc not in unique_properties:
                    unique_properties[normalized_loc] = mapped_prop

    # 添加家族成员的房产（排除核心人员自身）
    for member in family_members:
        if member in precise_property_data and member != person:
            for prop in precise_property_data[member]:
                mapped_prop = _map_property_fields(prop)
                location = _extract_property_location(mapped_prop)
                if location:
                    normalized_loc = _normalize_property_address(location)
                    if normalized_loc and normalized_loc not in unique_properties:
                        unique_properties[normalized_loc] = mapped_prop

    return list(unique_properties.values())


def _collect_vehicles(
    vehicle_data: Dict, person: str, family_members: List[str]
) -> List[Dict]:
    """
    收集核心人员及其家族成员的所有车辆数据。

    Args:
        vehicle_data: 车辆数据字典
        person: 核心人员名称
        family_members: 家族成员列表

    Returns:
        车辆列表
    """
    all_vehicles = []

    # 添加本人的车辆
    if person in vehicle_data:
        for vehicle in vehicle_data[person]:
            mapped_vehicle = _map_vehicle_fields(vehicle)
            all_vehicles.append(mapped_vehicle)

    # 添加家族成员的车辆（排除核心人员自身）
    for member in family_members:
        if member in vehicle_data and member != person:
            for vehicle in vehicle_data[member]:
                mapped_vehicle = _map_vehicle_fields(vehicle)
                all_vehicles.append(mapped_vehicle)

    return all_vehicles


def _parse_property_price(price_str) -> float:
    """
    解析房产价格字符串为数值（万元）。

    支持两种格式：
    1. 包含"万"字：直接解析数字部分
    2. 不包含"万"字：将金额除以10000转换为万元

    Args:
        price_str: 价格字符串或数值

    Returns:
        价格（万元），解析失败返回0
    """
    if not price_str:
        return 0.0

    try:
        if "万" in str(price_str):
            return float(str(price_str).replace("万", "").replace(",", ""))
        else:
            return float(str(price_str).replace(",", "")) / 10000
    except (ValueError, TypeError):
        return 0.0


def _calculate_total_property_value(properties: List[Dict]) -> float:
    """
    计算房产总价值（单位：万元）。

    Args:
        properties: 房产列表

    Returns:
        总价值（万元）
    """
    total_value = 0.0
    for prop in properties:
        price_str = (
            prop.get("交易金额", "")
            or prop.get("不动产价格", "")
            or prop.get("房产价值", "")
        )
        total_value += _parse_property_price(price_str)

    return total_value


def _create_person_assets(
    family_members: List[str], properties: List[Dict], vehicles: List[Dict]
) -> Dict:
    """
    创建个人资产数据字典。

    Args:
        family_members: 家族成员列表
        properties: 房产列表
        vehicles: 车辆列表

    Returns:
        个人资产字典
    """
    total_value = _calculate_total_property_value(properties)

    return {
        "家族成员": family_members,
        "房产套数": len(properties),
        "房产总价值": total_value,
        "车辆数量": len(vehicles),
        "房产": properties,
        "车辆": vehicles,
    }


def build_family_assets_from_data(
    precise_property_data: Dict,
    vehicle_data: Dict,
    family_tree: Dict,
    core_persons: List[str],
) -> Dict:
    """
    从精准查询数据和车辆数据构建family_assets格式。

    处理流程：
    1. 为每个核心人员获取家族成员
    2. 收集家族成员（含本人）的房产数据并去重
    3. 收集家族成员（含本人）的车辆数据
    4. 计算房产总价值
    5. 组装为report_generator所需的格式

    Args:
        precise_property_data: 精准查询房产数据 {person_id: [properties]}
        vehicle_data: 车辆数据 {person_id: [vehicles]}
        family_tree: 家族关系图谱
        core_persons: 核心人员列表

    Returns:
        family_assets格式: {核心人员: {家族成员, 房产套数, 房产总价值, 车辆数量, 房产, 车辆}}
    """
    family_assets = {}

    for person in core_persons:
        # 获取家族成员
        family_members = _get_family_members(family_tree, person)

        # 收集房产数据（去重）
        all_properties = _collect_unique_properties(
            precise_property_data, person, family_members
        )

        # 收集车辆数据
        all_vehicles = _collect_vehicles(vehicle_data, person, family_members)

        # 创建个人资产数据
        family_assets[person] = _create_person_assets(
            family_members, all_properties, all_vehicles
        )

        logger.info(
            f"构建家庭资产数据: {person} - "
            f"房产{len(all_properties)}套, 车辆{len(all_vehicles)}辆"
        )

    return family_assets


def build_family_assets_simple(
    precise_property_data: Dict, vehicle_data: Dict, core_persons: List[str]
) -> Dict:
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
                price_str = (
                    prop.get("交易金额", "")
                    or prop.get("不动产价格", "")
                    or prop.get("房产价值", "")
                )
                if price_str:
                    if "万" in str(price_str):
                        price = float(str(price_str).replace("万", "").replace(",", ""))
                    else:
                        price = float(str(price_str).replace(",", "")) / 10000
                    total_property_value += price
            except (ValueError, TypeError):
                pass

        # 转换为report_generator需要的格式
        family_assets[person] = {
            "家族成员": [person],  # 只有自己
            "房产套数": len(all_properties),
            "房产总价值": total_property_value,
            "车辆数量": len(all_vehicles),
            "房产": all_properties,
            "车辆": all_vehicles,
        }

        logger.info(
            f"构建家庭资产数据(简化版): {person} - 房产{len(all_properties)}套, 车辆{len(all_vehicles)}辆"
        )

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
        "房地坐落": prop.get("location", ""),
        "建筑面积": prop.get("area", 0),
        "规划用途": prop.get("usage", ""),
        "产权人": prop.get("owner_name", ""),
        "身份证号": prop.get("owner_id", ""),
        "共有情况": prop.get("co_owners", ""),
        "登记时间": prop.get("register_date", ""),
        "权属状态": prop.get("status", ""),
        "不动产权证号": prop.get("certificate_number", ""),
        "是否抵押": "是" if prop.get("is_mortgaged", False) else "否",
        "是否查封": "是" if prop.get("is_sealed", False) else "否",
        "数据质量": "正常",
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
        "所有人": vehicle.get("所有人", ""),
        "号牌号码": vehicle.get("号牌号码", ""),
        "中文品牌": vehicle.get("中文品牌", ""),
        "车身颜色": vehicle.get("车身颜色", ""),
        "初次登记日期": vehicle.get("初次登记日期", ""),
        "机动车状态": vehicle.get("机动车状态", ""),
        "是否抵押质押": vehicle.get("是否抵押质押", 0),
        "能源种类": vehicle.get("能源种类", ""),
        "住所地址": vehicle.get("住所地址", ""),
    }
