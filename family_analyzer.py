#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
家族关系分析模块
从同户人、户籍人口等数据源提取家族成员信息，构建家族关系图谱
"""

import os
import glob
from typing import Dict, List
import pandas as pd

import utils

logger = utils.setup_logger(__name__)


def extract_family_from_household(data_directory: str, person_name: str, person_id: str = None) -> List[Dict]:
    """
    从"同户人"数据提取家族成员
    
    Args:
        data_directory: 数据目录
        person_name: 核心人员姓名
        person_id: 身份证号（可选，用于精确匹配）
    
    Returns:
        家族成员列表，每个成员包含：姓名、身份证号、与户主关系、性别、出生日期等
    """
    family_members = []
    
    # 查找同户人数据文件 (有两种可能的命名: __1.xlsx 或 __2.xlsx)
    for suffix in ['__1.xlsx', '__2.xlsx']:
        pattern = os.path.join(
            data_directory,
            '**',
            '公安部同户人（定向查询）',
            f'{person_name}_*{suffix}'
        )
        
        files = glob.glob(pattern, recursive=True)
        if files:
            break
    
    if not files:
        logger.debug(f'{person_name} 未找到同户人数据')
        return family_members
    
    for file_path in files:
        try:
            df = pd.read_excel(file_path)
            
            if df.empty:
                continue
            
            # 提取家族成员信息
            for _, row in df.iterrows():
                member = {
                    '姓名': row.get('姓名', ''),
                    '身份证号': row.get('身份证号', ''),
                    '与户主关系': row.get('与户主关系', ''),
                    '性别': row.get('性别', ''),
                    '出生日期': row.get('出生日期', ''),
                    '民族': row.get('民族', ''),
                    '户籍地': row.get('户籍地', ''),
                    '数据来源': '同户人',
                    '核心人员': person_name
                }
                family_members.append(member)
            
            logger.info(f'{person_name} 从同户人数据提取 {len(df)} 名家族成员')
            
        except Exception as e:
            logger.warning(f'读取同户人数据失败 {file_path}: {str(e)}')
    
    return family_members


def extract_family_from_census(data_directory: str, person_name: str) -> List[Dict]:
    """
    从"户籍人口"数据提取家族成员（补充信息）
    
    Args:
        data_directory: 数据目录
        person_name: 核心人员姓名
    
    Returns:
        家族成员列表
    """
    family_members = []
    
    # 查找户籍人口数据文件
    pattern = os.path.join(
        data_directory,
        '**',
        '公安部户籍人口（定向查询）',
        f'{person_name}_*_公安部人口和户籍信息_1.xlsx'
    )
    
    files = glob.glob(pattern, recursive=True)
    
    if not files:
        logger.debug(f'{person_name} 未找到户籍人口数据')
        return family_members
    
    for file_path in files:
        try:
            df = pd.read_excel(file_path)
            
            if df.empty:
                continue
            
            # 提取家族成员信息
            for _, row in df.iterrows():
                member = {
                    '姓名': row.get('姓名', ''),
                    '身份证号': row.get('身份证号', ''),
                    '与户主关系': row.get('与户主关系', ''),
                    '性别': row.get('性别', ''),
                    '出生日期': row.get('出生日期', ''),
                    '民族': row.get('民族', ''),
                    '户籍地': row.get('户籍地', ''),
                    '婚姻状况': row.get('婚姻状况', ''),
                    '文化程度': row.get('文化程度', ''),
                    '数据来源': '户籍人口',
                    '核心人员': person_name
                }
                family_members.append(member)
            
            logger.info(f'{person_name} 从户籍人口数据提取 {len(df)} 名家族成员')
            
        except Exception as e:
            logger.warning(f'读取户籍人口数据失败 {file_path}: {str(e)}')
    
    return family_members


def merge_family_members(household_members: List[Dict], census_members: List[Dict]) -> List[Dict]:
    """
    合并同户人和户籍人口数据，去重并补充信息
    
    Args:
        household_members: 同户人数据
        census_members: 户籍人口数据
    
    Returns:
        合并后的家族成员列表
    """
    # 使用身份证号作为唯一标识
    members_dict = {}
    
    # 优先使用同户人数据（更可靠）
    for member in household_members:
        id_num = member.get('身份证号', '')
        if id_num:
            members_dict[id_num] = member
    
    # 补充户籍人口数据
    for member in census_members:
        id_num = member.get('身份证号', '')
        if id_num:
            if id_num not in members_dict:
                members_dict[id_num] = member
            else:
                # 补充缺失字段
                for key, value in member.items():
                    if key not in members_dict[id_num] or not members_dict[id_num][key]:
                        members_dict[id_num][key] = value
    
    return list(members_dict.values())


def build_family_tree(core_persons: List[str], data_directory: str) -> Dict[str, List[Dict]]:
    """
    构建家族关系图谱
    
    Args:
        core_persons: 核心人员列表
        data_directory: 数据目录
    
    Returns:
        家族关系图谱，格式：{核心人员: [家族成员列表]}
    """
    logger.info('=' * 60)
    logger.info('开始构建家族关系图谱')
    logger.info('=' * 60)
    
    family_tree = {}
    
    for person in core_persons:
        logger.info(f'\n正在分析 {person} 的家族关系...')
        
        # 从同户人数据提取
        household_members = extract_family_from_household(data_directory, person)
        
        # 从户籍人口数据提取
        census_members = extract_family_from_census(data_directory, person)
        
        # 合并数据
        all_members = merge_family_members(household_members, census_members)
        
        family_tree[person] = all_members
        
        if all_members:
            logger.info(f'✓ {person} 的家族成员: {len(all_members)} 人')
            for member in all_members:
                relation = member.get('与户主关系', '未知')
                name = member.get('姓名', '未知')
                logger.info(f'  - {name} ({relation})')
        else:
            logger.info(f'✓ {person} 未找到家族成员数据')
    
    total_members = sum(len(members) for members in family_tree.values())
    logger.info(f'\n家族关系图谱构建完成，共识别 {total_members} 名家族成员')
    
    return family_tree


def get_family_summary(family_tree: Dict[str, List[Dict]]) -> Dict[str, Dict]:
    """
    生成家族关系摘要统计
    
    注意：同户人数据中的"与户主关系"是相对于户主的关系，
    如果核心人员不是户主，需要进行关系推导。
    
    Args:
        family_tree: 家族关系图谱
    
    Returns:
        家族摘要，格式：{核心人员: {配偶: [], 子女: [], 父母: [], 其他: []}}
    """
    summary = {}
    
    for person, members in family_tree.items():
        person_summary = {
            '配偶': [],
            '子女': [],
            '父母': [],
            '兄弟姐妹': [],
            '其他': []
        }
        
        # 首先找出户主是谁，以及核心人员与户主的关系
        householder = None
        person_relation_to_householder = None
        
        for member in members:
            name = member.get('姓名', '')
            relation = member.get('与户主关系', '')
            
            if relation == '户主':
                householder = name
            if name == person:
                person_relation_to_householder = relation
        
        # 如果核心人员就是户主，直接使用原有关系
        is_householder = (householder == person) or (person_relation_to_householder == '户主')
        
        for member in members:
            name = member.get('姓名', '')
            relation_to_householder = member.get('与户主关系', '')
            
            # 跳过空姓名
            if not name or not name.strip():
                continue
            
            # 排除本人
            if name.strip() == person.strip():
                continue
            
            # 确定该成员与核心人员的关系
            if is_householder:
                # 核心人员是户主，直接使用"与户主关系"
                actual_relation = relation_to_householder
            else:
                # 核心人员不是户主，需要推导关系
                actual_relation = _infer_relation_to_person(
                    person_relation_to_householder, 
                    relation_to_householder,
                    name,
                    householder
                )
            
            # 根据实际关系分类
            if actual_relation in ['妻', '夫', '配偶']:
                person_summary['配偶'].append(name)
            elif actual_relation in ['女', '子', '儿子', '女儿', '子女']:
                person_summary['子女'].append(name)
            elif actual_relation in ['父', '母', '父亲', '母亲']:
                person_summary['父母'].append(name)
            elif actual_relation in ['兄', '弟', '姐', '妹', '兄弟', '姐妹']:
                person_summary['兄弟姐妹'].append(name)
            elif actual_relation in ['户主', '本人', '本户']:
                # 跳过户主/本人
                continue
            elif actual_relation:
                person_summary['其他'].append(f'{name}({actual_relation})')
        
        # 去重
        for key in person_summary:
            person_summary[key] = list(set(person_summary[key]))
        
        summary[person] = person_summary
    
    return summary


def _infer_relation_to_person(person_to_householder: str, member_to_householder: str, 
                               member_name: str, householder_name: str) -> str:
    """
    根据核心人员与户主关系、成员与户主关系，推导成员与核心人员的关系
    
    例如：
    - 如果核心人员是户主的"子"，成员是户主的"妻"，则成员是核心人员的"母"
    - 如果核心人员是户主的"子"，成员也是户主的"子"，则成员是核心人员的"兄弟姐妹"
    
    Args:
        person_to_householder: 核心人员与户主的关系
        member_to_householder: 成员与户主的关系
        member_name: 成员姓名
        householder_name: 户主姓名
        
    Returns:
        成员与核心人员的推导关系
    """
    # 如果成员就是户主
    if member_to_householder == '户主' or member_name == householder_name:
        # 核心人员是户主的子女 -> 成员(户主)是核心人员的父母
        if person_to_householder in ['子', '女', '儿子', '女儿']:
            return '父'  # 户主是父亲（默认）
        # 核心人员是户主的妻/夫 -> 成员(户主)是核心人员的配偶
        if person_to_householder in ['妻', '夫', '配偶']:
            return '配偶'
        return person_to_householder  # 其他情况返回原关系
    
    # 核心人员是户主的子女
    if person_to_householder in ['子', '女', '儿子', '女儿']:
        # 成员是户主的妻 -> 成员是核心人员的母亲
        if member_to_householder in ['妻']:
            return '母'
        # 成员是户主的夫 -> 成员是核心人员的父亲
        if member_to_householder in ['夫']:
            return '父'
        # 成员也是户主的子女 -> 成员是核心人员的兄弟姐妹
        if member_to_householder in ['子', '女', '儿子', '女儿']:
            return '兄弟姐妹'
        # 成员是户主的父母 -> 成员是核心人员的祖父母
        if member_to_householder in ['父', '母', '父亲', '母亲']:
            return f'祖{member_to_householder}'
    
    # 核心人员是户主的配偶
    if person_to_householder in ['妻', '夫', '配偶']:
        # 成员是户主的子女 -> 成员是核心人员的子女
        if member_to_householder in ['子', '女', '儿子', '女儿']:
            return '子女'
        # 成员是户主的父母 -> 成员是核心人员的公婆/岳父母
        if member_to_householder in ['父', '母', '父亲', '母亲']:
            return member_to_householder  # 简化处理
    
    # 其他情况返回原关系
    return member_to_householder


if __name__ == '__main__':
    # 测试代码
    import sys
    
    data_dir = sys.argv[1] if len(sys.argv) > 1 else './data'
    test_persons = ['朱明', '朱永平', '陈斌', '马尚德']
    
    family_tree = build_family_tree(test_persons, data_dir)
    summary = get_family_summary(family_tree)
    
    print('\n' + '=' * 60)
    print('家族关系摘要')
    print('=' * 60)
    for person, relations in summary.items():
        print(f'\n【{person}】')
        for relation_type, names in relations.items():
            if names:
                print(f'  {relation_type}: {", ".join(names)}')
