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


def extract_family_from_household(
    data_directory: str, person_name: str, person_id: str = None
) -> List[Dict]:
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
    for suffix in ["__1.xlsx", "__2.xlsx"]:
        pattern = os.path.join(
            data_directory, "**", "公安部同户人（定向查询）", f"{person_name}_*{suffix}"
        )

        files = glob.glob(pattern, recursive=True)
        if files:
            break

    if not files:
        logger.debug(f"{person_name} 未找到同户人数据")
        return family_members

    for file_path in files:
        try:
            df = pd.read_excel(file_path)

            if df.empty:
                continue

            # 提取家族成员信息
            for _, row in df.iterrows():
                member = {
                    "姓名": row.get("姓名", ""),
                    "身份证号": row.get("身份证号", ""),
                    "与户主关系": row.get("与户主关系", ""),
                    "性别": row.get("性别", ""),
                    "出生日期": row.get("出生日期", ""),
                    "民族": row.get("民族", ""),
                    "户籍地": row.get("户籍地", ""),
                    "数据来源": "同户人",
                    "核心人员": person_name,
                }
                family_members.append(member)

            logger.info(f"{person_name} 从同户人数据提取 {len(df)} 名家族成员")

        except Exception as e:
            logger.warning(f"读取同户人数据失败 {file_path}: {str(e)}")

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
        "**",
        "公安部户籍人口（定向查询）",
        f"{person_name}_*_公安部人口和户籍信息_1.xlsx",
    )

    files = glob.glob(pattern, recursive=True)

    if not files:
        logger.debug(f"{person_name} 未找到户籍人口数据")
        return family_members

    for file_path in files:
        try:
            df = pd.read_excel(file_path)

            if df.empty:
                continue

            # 提取家族成员信息
            for _, row in df.iterrows():
                member = {
                    "姓名": row.get("姓名", ""),
                    "身份证号": row.get("身份证号", ""),
                    "与户主关系": row.get("与户主关系", ""),
                    "性别": row.get("性别", ""),
                    "出生日期": row.get("出生日期", ""),
                    "民族": row.get("民族", ""),
                    "户籍地": row.get("户籍地", ""),
                    "婚姻状况": row.get("婚姻状况", ""),
                    "文化程度": row.get("文化程度", ""),
                    "数据来源": "户籍人口",
                    "核心人员": person_name,
                }
                family_members.append(member)

            logger.info(f"{person_name} 从户籍人口数据提取 {len(df)} 名家族成员")

        except Exception as e:
            logger.warning(f"读取户籍人口数据失败 {file_path}: {str(e)}")

    return family_members


def merge_family_members(
    household_members: List[Dict], census_members: List[Dict]
) -> List[Dict]:
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
        id_num = member.get("身份证号", "")
        if id_num:
            members_dict[id_num] = member

    # 补充户籍人口数据
    for member in census_members:
        id_num = member.get("身份证号", "")
        if id_num:
            if id_num not in members_dict:
                members_dict[id_num] = member
            else:
                # 补充缺失字段
                for key, value in member.items():
                    if key not in members_dict[id_num] or not members_dict[id_num][key]:
                        members_dict[id_num][key] = value

    return list(members_dict.values())


def build_family_tree(
    core_persons: List[str], data_directory: str
) -> Dict[str, List[Dict]]:
    """
    构建家族关系图谱

    Args:
        core_persons: 核心人员列表
        data_directory: 数据目录

    Returns:
        家族关系图谱，格式：{核心人员: [家族成员列表]}
    """
    logger.info("=" * 60)
    logger.info("开始构建家族关系图谱")
    logger.info("=" * 60)

    family_tree = {}

    for person in core_persons:
        logger.info(f"\n正在分析 {person} 的家族关系...")

        # 从同户人数据提取
        household_members = extract_family_from_household(data_directory, person)

        # 从户籍人口数据提取
        census_members = extract_family_from_census(data_directory, person)

        # 合并数据
        all_members = merge_family_members(household_members, census_members)

        family_tree[person] = all_members

        if all_members:
            logger.info(f"✓ {person} 的家族成员: {len(all_members)} 人")
            for member in all_members:
                relation = member.get("与户主关系", "未知")
                name = member.get("姓名", "未知")
                logger.info(f"  - {name} ({relation})")
        else:
            logger.info(f"✓ {person} 未找到家族成员数据")

    total_members = sum(len(members) for members in family_tree.values())
    logger.info(f"\n家族关系图谱构建完成，共识别 {total_members} 名家族成员")

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
            "配偶": [],
            "子女": [],
            "父母": [],
            "兄弟姐妹": [],
            "其他": [],
        }

        # 首先找出户主是谁，以及核心人员与户主的关系
        householder = None
        person_relation_to_householder = None

        for member in members:
            name = member.get("姓名", "")
            relation = member.get("与户主关系", "")

            if relation == "户主":
                householder = name
            if name == person:
                person_relation_to_householder = relation

        # 如果核心人员就是户主，直接使用原有关系
        is_householder = (householder == person) or (
            person_relation_to_householder == "户主"
        )

        for member in members:
            name = member.get("姓名", "")
            relation_to_householder = member.get("与户主关系", "")

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
                    householder,
                )

            # 根据实际关系分类
            if actual_relation in ["妻", "夫", "配偶"]:
                person_summary["配偶"].append(name)
            elif actual_relation in ["女", "子", "儿子", "女儿", "子女"]:
                person_summary["子女"].append(name)
            elif actual_relation in ["父", "母", "父亲", "母亲"]:
                person_summary["父母"].append(name)
            elif actual_relation in ["兄", "弟", "姐", "妹", "兄弟", "姐妹"]:
                person_summary["兄弟姐妹"].append(name)
            elif actual_relation in ["户主", "本人", "本户"]:
                # 跳过户主/本人
                continue
            elif actual_relation:
                person_summary["其他"].append(f"{name}({actual_relation})")

        # 去重
        for key in person_summary:
            person_summary[key] = list(set(person_summary[key]))

        summary[person] = person_summary

    return summary


def _infer_relation_to_person(
    person_to_householder: str,
    member_to_householder: str,
    member_name: str,
    householder_name: str,
) -> str:
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
    if member_to_householder == "户主" or member_name == householder_name:
        # 核心人员是户主的子女 -> 成员(户主)是核心人员的父母
        if person_to_householder in ["子", "女", "儿子", "女儿"]:
            return "父"  # 户主是父亲（默认）
        # 核心人员是户主的妻/夫 -> 成员(户主)是核心人员的配偶
        if person_to_householder in ["妻", "夫", "配偶"]:
            return "配偶"
        return person_to_householder  # 其他情况返回原关系

    # 核心人员是户主的子女
    if person_to_householder in ["子", "女", "儿子", "女儿"]:
        # 成员是户主的妻 -> 成员是核心人员的母亲
        if member_to_householder in ["妻"]:
            return "母"
        # 成员是户主的夫 -> 成员是核心人员的父亲
        if member_to_householder in ["夫"]:
            return "父"
        # 成员也是户主的子女 -> 成员是核心人员的兄弟姐妹
        if member_to_householder in ["子", "女", "儿子", "女儿"]:
            return "兄弟姐妹"
        # 成员是户主的父母 -> 成员是核心人员的祖父母
        if member_to_householder in ["父", "母", "父亲", "母亲"]:
            return f"祖{member_to_householder}"

    # 核心人员是户主的配偶
    if person_to_householder in ["妻", "夫", "配偶"]:
        # 成员是户主的子女 -> 成员是核心人员的子女
        if member_to_householder in ["子", "女", "儿子", "女儿"]:
            return "子女"
        # 成员是户主的父母 -> 成员是核心人员的公婆/岳父母
        if member_to_householder in ["父", "母", "父亲", "母亲"]:
            return member_to_householder  # 简化处理

    # 其他情况返回原关系
    return member_to_householder


def identify_householder(members: List[Dict]) -> str:
    """
    从家庭成员中识别户主

    Args:
        members: 家族成员列表

    Returns:
        户主姓名,如未找到返回第一个成员
    """
    for member in members:
        relation = member.get("与户主关系", "")
        if relation == "户主":
            return member.get("姓名", "")

    # 未找到户主,返回第一个成员
    if members:
        return members[0].get("姓名", "")
    return ""


def extract_person_info(data_directory: str, person_name: str) -> Dict:
    """
    提取单个人员的详细信息(用于跨户籍关系推断)

    Args:
        data_directory: 数据目录
        person_name: 人员姓名

    Returns:
        人员信息字典
    """
    info = {
        "姓名": person_name,
        "身份证号": "",
        "出生日期": "",
        "籍贯": "",
        "户籍地": "",  # 用于识别是否同一家庭
        "性别": "",
        "住址": "",  # 别名，方便理解
    }

    # 从户籍人口数据提取
    pattern = os.path.join(
        data_directory,
        "**",
        "公安部户籍人口（定向查询）",
        f"{person_name}_*_公安部人口和户籍信息_1.xlsx",
    )

    files = glob.glob(pattern, recursive=True)
    if files:
        try:
            df = pd.read_excel(files[0])
            if not df.empty:
                row = df.iloc[0]
                info["身份证号"] = str(row.get("身份证号", ""))
                info["出生日期"] = str(row.get("出生日期", ""))
                info["籍贯"] = str(row.get("籍贯", ""))
                address = str(row.get("户籍地", ""))
                info["户籍地"] = address
                info["住址"] = address  # 户籍地即为住址
                info["性别"] = str(row.get("性别", ""))
        except Exception as e:
            logger.warning(f"读取 {person_name} 户籍数据失败: {e}")

    return info


def get_surname(name: str) -> str:
    """提取姓氏(取第一个字)"""
    return name[0] if name else ""


def get_birth_year(id_or_birth: str) -> int:
    """从身份证号或出生日期提取出生年份"""
    s = str(id_or_birth)
    try:
        if len(s) >= 18:  # 身份证号
            return int(s[6:10])
        elif len(s) >= 8:  # 出生日期 YYYYMMDD
            return int(s[:4])
        elif len(s) >= 4:
            return int(s[:4])
    except:
        pass
    return 0


def infer_extended_relatives(
    persons_info: List[Dict], family_tree: Dict[str, List[Dict]] = None
) -> List[Dict]:
    """
    推断跨户籍的扩展亲属关系

    推断逻辑:
    1. 相同姓氏 + 相同籍贯 + 年龄差<5岁 → 可能兄弟姐妹 (置信度: 0.7)
    2. 相同姓氏 + 相同籍贯 + 年龄差20-40岁 → 可能父子/父女 (置信度: 0.6)
       【改进】如果已有明确的父母关系，则不再推断为父母，而是推断为叔侄/姑侄
    3. 身份证前6位相同 → 相同户籍地,增加置信度 +0.1

    Args:
        persons_info: 人员信息列表 [{姓名, 身份证号, 籍贯, 出生日期, ...}]
        family_tree: 已知的家族关系图谱 (用于排除重复推断)

    Returns:
        推断的亲属关系列表: [{person_a, person_b, relation, confidence, reason}]
    """
    relations = []

    # 预处理：构建每个人已知的父母集合
    known_parents = {}
    if family_tree:
        for householder, members in family_tree.items():
            # 找到户主
            real_householder = householder
            for m in members:
                if m.get("与户主关系") == "户主":
                    real_householder = m.get("姓名")
                    break

            for m in members:
                name = m.get("姓名")
                relation = m.get("与户主关系", "")
                if not name:
                    continue

                # 如果成员是户主的子女，则户主是成员的父/母
                if relation in ["子", "女", "儿子", "女儿"]:
                    if name not in known_parents:
                        known_parents[name] = set()
                    known_parents[name].add(real_householder)

                # 如果成员是户主的配偶，则户主的父母是成员的公婆（非直系父母，暂不处理）
                # 如果成员是户主的孙子女，则户主的子女是成员的父母（需递归，暂简化）

    n = len(persons_info)
    for i in range(n):
        for j in range(i + 1, n):
            p1 = persons_info[i]
            p2 = persons_info[j]

            name1 = p1.get("姓名", "")
            name2 = p2.get("姓名", "")

            if not name1 or not name2:
                continue

            # 提取特征
            surname1 = get_surname(name1)
            surname2 = get_surname(name2)

            jiguan1 = p1.get("籍贯", "")
            jiguan2 = p2.get("籍贯", "")

            id1 = p1.get("身份证号", "")
            id2 = p2.get("身份证号", "")

            birth1 = p1.get("出生日期", "") or id1
            birth2 = p2.get("出生日期", "") or id2

            year1 = get_birth_year(birth1)
            year2 = get_birth_year(birth2)

            # 条件判断
            same_surname = surname1 == surname2 and surname1
            same_jiguan = jiguan1 == jiguan2 and jiguan1 and jiguan1 != "nan"
            same_id_prefix = (
                id1[:6] == id2[:6] if len(id1) >= 6 and len(id2) >= 6 else False
            )

            age_diff = abs(year1 - year2) if year1 and year2 else 999

            # 推断关系
            confidence = 0.0
            relation = ""
            reasons = []

            if same_surname and same_jiguan:
                reasons.append(f'同姓"{surname1}"')
                reasons.append(f'同籍贯"{jiguan1}"')

                if age_diff <= 5:
                    relation = "可能兄弟姐妹"
                    confidence = 0.7
                    reasons.append(f"年龄差{age_diff}岁")
                elif 20 <= age_diff <= 40:
                    # 检查是否已存在父母关系
                    # 假设 relation 是 "name1 是 name2 的父/母" (name1 > name2)
                    # 或者 "name2 是 name1 的父/母" (name2 > name1)

                    is_parent_relation = False
                    parent_name, child_name = (
                        (name1, name2) if year1 < year2 else (name2, name1)
                    )

                    # 检查 child 是否已有已知父母
                    has_known_parent = False
                    if child_name in known_parents and known_parents[child_name]:
                        has_known_parent = True
                        # 检查 parent_name 是否就是已知父母之一
                        if parent_name in known_parents[child_name]:
                            # 已经是已知父母，无需再次推断
                            continue

                    if has_known_parent:
                        # 孩子已有已知父母，且当前推断对象不是已知父母
                        # 推断对象可能是 叔叔/伯伯/姑姑/舅舅/姨 (父母的兄弟姐妹)
                        relation = (
                            f"{parent_name}可能是{child_name}的长辈(叔/伯/姑/舅/姨)"
                        )
                        confidence = 0.5
                        reasons.append(f"年龄差{age_diff}岁")
                        reasons.append(f"{child_name}已有已知父母(户籍),推断为旁系长辈")
                    else:
                        # 孩子没有已知父母，推断为父母
                        relation = f"{parent_name}可能是{child_name}的父/母"
                        confidence = 0.6
                        reasons.append(f"年龄差{age_diff}岁")

                elif 5 < age_diff < 20:
                    relation = "可能旁系亲属"
                    confidence = 0.4
                    reasons.append(f"年龄差{age_diff}岁")

            if same_id_prefix and confidence > 0:
                confidence = min(confidence + 0.1, 1.0)
                reasons.append("身份证前6位相同")

            if relation and confidence >= 0.4:
                relations.append(
                    {
                        "person_a": name1,
                        "person_b": name2,
                        "relation": relation,
                        "confidence": confidence,
                        "reason": ", ".join(reasons),
                    }
                )
                logger.info(
                    f"[扩展亲属推断] {name1} ↔ {name2}: {relation} (置信度:{confidence:.1f})"
                )

    return relations


def build_family_units(core_persons: List[str], data_directory: str) -> List[Dict]:
    """
    构建家庭分析单元(应用户主原则)

    户主原则:
    1. 每个家庭以户主为anchor
    2. 如果核查对象不是户主,则家庭anchor调整为户主
    3. 自动识别跨户籍的扩展亲属关系

    Args:
        core_persons: 核心人员列表
        data_directory: 数据目录

    Returns:
        家庭单元列表,格式兼容PrimaryTargetsConfig.analysis_units
    """
    logger.info("=" * 60)
    logger.info("开始构建家庭分析单元(应用户主原则)")
    logger.info("=" * 60)

    # 1. 构建家族树
    family_tree = build_family_tree(core_persons, data_directory)

    # 2. 提取所有人员信息(用于跨户籍推断)
    all_persons_info = []
    for person in core_persons:
        info = extract_person_info(data_directory, person)
        all_persons_info.append(info)

    # 3. 推断跨户籍关系
    extended_relations = infer_extended_relatives(all_persons_info, family_tree)

    # 4. 按户籍分组,识别独立家庭（不同户籍地=不同家庭）
    families = {}  # key: 户主, value: {members, householder, ...}
    person_to_family = {}  # 记录每个人属于哪个家庭
    person_to_address = {}  # 记录每个人的地址

    # 先收集所有人的地址信息
    for info in all_persons_info:
        name = info.get("姓名", "")
        address = info.get("户籍地", "") or info.get("住址", "")
        if name and address:
            person_to_address[name] = address

    for person, members in family_tree.items():
        householder = identify_householder(members)

        if householder and householder not in families:
            # 新家庭
            member_names = [m.get("姓名", "") for m in members if m.get("姓名")]
            # 获取该家庭的地址（户主的地址）
            family_address = person_to_address.get(householder, "")

            families[householder] = {
                "anchor": householder,  # 主归集人，默认为户主，用户可调整
                "householder": householder,
                "members": list(set(member_names)),
                "address": family_address,  # 家庭地址
                "member_details": [],
            }

            # 记录成员归属
            for name in member_names:
                person_to_family[name] = householder

    # 5. 构建成员详情（包含地址信息）
    for householder, family in families.items():
        member_details = []
        for name in family["members"]:
            # 获取关系
            relation = "本人" if name == householder else ""

            # 获取该成员的地址
            member_address = person_to_address.get(name, family.get("address", ""))

            # 从原始数据获取关系
            if name in family_tree:
                for m in family_tree.get(name, []):
                    if m.get("姓名") == name:
                        rel = m.get("与户主关系", "")
                        if rel == "户主":
                            relation = "本人"
                        else:
                            relation = rel
                        break
            else:
                # 从户主的成员中查找
                for p, members in family_tree.items():
                    for m in members:
                        if m.get("姓名") == name:
                            relation = m.get("与户主关系", "")
                            break

            member_details.append(
                {
                    "name": name,
                    "relation": relation or "家庭成员",
                    "address": member_address,
                    "has_data": name in core_persons,
                    "id_number": "",
                }
            )

        family["member_details"] = member_details

    # 6. 检查未分配的核心人员，为每个未分配人员创建独立单元
    assigned_persons = set()
    for unit in families.values():
        assigned_persons.update(unit.get("members", []))

    unassigned_persons = [p for p in core_persons if p not in assigned_persons]
    if unassigned_persons:
        logger.info(
            f"发现 {len(unassigned_persons)} 个未分配的核心人员: {unassigned_persons}"
        )
        for person_name in unassigned_persons:
            independent_unit = {
                "anchor": person_name,
                "householder": person_name,
                "members": [person_name],
                "address": person_to_address.get(person_name, ""),
                "member_details": [
                    {
                        "name": person_name,
                        "relation": "本人",
                        "address": person_to_address.get(person_name, ""),
                        "has_data": True,
                        "id_number": "",
                    }
                ],
                "extended_relatives": [],
            }
            families[person_name] = independent_unit

    # 7. 转换为列表
    units = list(families.values())

    # 8. 添加扩展亲属信息
    for unit in units:
        unit["extended_relatives"] = [
            r
            for r in extended_relations
            if r["person_a"] in unit["members"] or r["person_b"] in unit["members"]
        ]

    logger.info(f"\n家庭分析单元构建完成,共 {len(units)} 个家庭")
    for unit in units:
        address = unit.get("address", "")
        address_str = f" (住址: {address})" if address else ""
        logger.info(
            f"  - {unit['householder']} 家庭{address_str}, 成员: {unit['members']}"
        )
        if unit.get("extended_relatives"):
            for rel in unit["extended_relatives"]:
                logger.info(
                    f"    扩展: {rel['person_a']} ↔ {rel['person_b']} ({rel['relation']})"
                )

    return units


if __name__ == "__main__":
    # 测试代码
    import sys

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "./data"
    test_persons = ["滕雳", "施灵", "施育", "施承天"]

    print("=" * 60)
    print("测试: build_family_units() - 户主原则")
    print("=" * 60)

    units = build_family_units(test_persons, data_dir)

    print("\n结果:")
    for unit in units:
        address = unit.get("address", "")
        address_str = f" (住址: {address})" if address else ""
        print(f"\n家庭: {unit['householder']}{address_str}")
        print(f"  主归集人: {unit['anchor']}")
        print(f"  成员: {unit['members']}")
        if unit.get("extended_relatives"):
            print("  扩展亲属:")
            for rel in unit["extended_relatives"]:
                print(
                    f"    {rel['person_a']} ↔ {rel['person_b']}: {rel['relation']} (置信度:{rel['confidence']:.1f})"
                )
