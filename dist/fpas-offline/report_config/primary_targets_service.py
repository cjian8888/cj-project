#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归集配置服务模块

提供归集配置的读取、保存、生成默认配置等服务功能。
作为报告模块和 analysis_cache 之间的桥梁。

【G-02 实现】从 analysis_cache 读取家庭关系
【G-03 实现】保存/加载归集配置 API
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# 确保可以从项目根目录导入
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from report_config.primary_targets_schema import (
    PrimaryTargetsConfig,
    AnalysisUnit,
    AnalysisUnitMember,
    validate_config,
    SCHEMA_VERSION,
)
from name_normalizer import normalize_for_matching

logger = logging.getLogger(__name__)

# 公司名称关键词
COMPANY_KEYWORDS = ["公司", "有限", "集团", "企业", "股份", "合伙", "事务所", "银行"]

# 默认配置文件名
CONFIG_FILENAME = "primary_targets.json"
AUTO_CONFIG_FILENAME = "primary_targets.auto.json"


class PrimaryTargetsService:
    """
    归集配置服务

    负责：
    1. 从 analysis_cache 读取人员列表和家庭关系
    2. 生成默认归集配置
    3. 保存/加载归集配置文件
    """

    def __init__(self, data_dir: str = "./data", output_dir: str = "./output"):
        """
        初始化

        Args:
            data_dir: 原始数据目录（配置文件保存位置）
            output_dir: 输出目录（analysis_cache 位置）
        """
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.cache_dir = os.path.join(output_dir, "analysis_cache")
        self.config_path = os.path.join(data_dir, CONFIG_FILENAME)
        self.auto_config_path = os.path.join(self.cache_dir, AUTO_CONFIG_FILENAME)

    def get_config_path(self) -> str:
        """获取配置文件完整路径"""
        return self.config_path

    def config_exists(self) -> bool:
        """检查配置文件是否存在"""
        return os.path.exists(self.config_path)

    def load_config(self) -> Tuple[Optional[PrimaryTargetsConfig], str]:
        """
        加载归集配置

        Returns:
            (config, message)
            - config: 成功时返回配置对象，失败时返回 None
            - message: 状态消息
        """
        if not self.config_exists():
            return None, "配置文件不存在"

        try:
            config = PrimaryTargetsConfig.load(self.config_path)
            errors = validate_config(config)
            if errors:
                return None, f"配置验证失败: {', '.join(errors)}"
            return config, "success"
        except json.JSONDecodeError as e:
            logger.error(f"配置文件 JSON 解析失败: {e}")
            return None, f"配置文件格式错误: {e}"
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return None, f"加载失败: {e}"

    def save_config(self, config: PrimaryTargetsConfig) -> Tuple[bool, str]:
        """
        保存归集配置

        Args:
            config: 归集配置对象

        Returns:
            (success, message)
        """
        try:
            # 验证配置
            errors = validate_config(config)
            if errors:
                return False, f"配置验证失败: {', '.join(errors)}"

            # 确保目录存在
            os.makedirs(self.data_dir, exist_ok=True)

            # 保存
            config.save(self.config_path)
            logger.info(f"归集配置已保存: {self.config_path}")
            return True, "success"
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False, f"保存失败: {e}"

    def _save_auto_generated_snapshot(self, config: PrimaryTargetsConfig) -> None:
        """保存临时归集配置快照，便于复核复现，不作为正式配置加载。"""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            payload = config.to_dict()
            payload["_meta"] = {
                "source": "auto_generated",
                "generated_at": datetime.now().isoformat(),
                "note": "系统在未发现 primary_targets.json 时自动生成的临时归集配置快照",
            }
            with open(self.auto_config_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info(f"临时归集配置快照已保存: {self.auto_config_path}")
        except Exception as e:
            logger.warning(f"保存临时归集配置快照失败: {e}")

    def load_analysis_cache(self) -> Tuple[Optional[Dict], str]:
        """
        加载 analysis_cache

        Returns:
            (cache, message)
        """
        if not os.path.exists(self.cache_dir):
            return None, "analysis_cache 不存在，请先运行分析"

        try:
            cache = {}

            # 加载 metadata.json
            metadata_path = os.path.join(self.cache_dir, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, "r", encoding="utf-8") as f:
                    cache["metadata"] = json.load(f)

            # 加载 profiles.json
            profiles_path = os.path.join(self.cache_dir, "profiles.json")
            if os.path.exists(profiles_path):
                with open(profiles_path, "r", encoding="utf-8") as f:
                    cache["profiles"] = json.load(f)

            # 加载 derived_data.json (包含 family_summary)
            derived_path = os.path.join(self.cache_dir, "derived_data.json")
            if os.path.exists(derived_path):
                with open(derived_path, "r", encoding="utf-8") as f:
                    cache["derived"] = json.load(f)

            return cache, "success"
        except Exception as e:
            logger.error(f"加载 analysis_cache 失败: {e}")
            return None, f"加载失败: {e}"

    def get_available_entities(self) -> Tuple[List[str], List[str]]:
        """
        从 analysis_cache 获取可用的人员和公司列表

        Returns:
            (persons, companies)
        """
        cache, msg = self.load_analysis_cache()
        if cache is None:
            return [], []

        profiles = cache.get("profiles", {})

        persons = []
        companies = []

        for name in profiles.keys():
            if self._is_company(name):
                companies.append(name)
            else:
                persons.append(name)

        return persons, companies

    def get_family_summary(self) -> Optional[Dict]:
        """
        从 analysis_cache 获取家庭关系摘要

        Returns:
            family_summary 字典，如果不存在返回 None
        """
        cache, msg = self.load_analysis_cache()
        if cache is None:
            return None

        derived = cache.get("derived", {})
        return derived.get("family_summary")

    def generate_default_config(self) -> Tuple[Optional[PrimaryTargetsConfig], str]:
        """
        【G-02 核心实现】从 analysis_cache 生成默认归集配置

        逻辑：
        1. 读取 profiles.json 获取所有实体列表
        2. 读取 derived_data.json 获取 family_summary（包含 family_units）
        3. 区分个人和公司
        4. 优先使用 family_units 创建独立的家庭分析单元
        5. 如果没有 family_units，回退到使用 family_members 创建默认单元
        6. 【关键修复】检查未分配的人员，为每个未分配人员创建独立分析单元

        Returns:
            (config, message)
        """
        cache, msg = self.load_analysis_cache()
        if cache is None:
            return None, msg

        profiles = cache.get("profiles", {})
        derived = cache.get("derived", {})

        # 区分个人和公司
        persons = []
        companies = []

        for name in profiles.keys():
            if self._is_company(name):
                companies.append(name)
            else:
                persons.append(name)
        person_candidates = list(persons)

        # 获取家庭汇总数据
        family_summary = derived.get("family_summary", {})
        family_units_v2 = derived.get(
            "family_units_v2", []
        )  # 修复：直接从 derived 获取 family_units_v2
        family_relations = derived.get("family_relations", {})

        # 创建默认配置
        config = PrimaryTargetsConfig()

        # 用于跟踪已分配的人员
        assigned_persons = set()

        # 【修复】使用 family_units_v2 创建独立的家庭分析单元
        if family_units_v2:
            for unit in family_units_v2:
                anchor = unit.get("anchor", "")
                members = unit.get("members", [])
                address = unit.get("address", "")

                if not members:
                    continue

                resolved_members = []
                # 创建成员详情
                member_details = []
                for name in members:
                    resolved_name = self._resolve_person_name(name, person_candidates)
                    member_name = resolved_name or name
                    if member_name not in resolved_members:
                        resolved_members.append(member_name)
                    has_data = member_name in profiles
                    # 记录已分配的人员（仅限有数据的人员）
                    if has_data:
                        assigned_persons.add(member_name)

                    # 从 unit.member_details 获取关系信息
                    relation = "家庭成员"
                    for md in unit.get("member_details", []):
                        if md.get("name") == name:
                            relation = md.get("relation", "家庭成员")
                            break

                    relation = self._normalize_relation_label(
                        relation, is_anchor=(name == anchor)
                    )

                    member_details.append(
                        AnalysisUnitMember(
                            name=member_name,
                            relation=relation,
                            has_data=has_data,
                        )
                    )

                resolved_anchor = self._resolve_person_name(anchor, resolved_members) or (
                    resolved_members[0] if resolved_members else anchor
                )
                if resolved_anchor and all(
                    detail.name != resolved_anchor for detail in member_details
                ):
                    member_details.insert(
                        0,
                        AnalysisUnitMember(
                            name=resolved_anchor,
                            relation="本人",
                            has_data=resolved_anchor in profiles,
                        ),
                    )

                # 构建单元备注
                note = f"户籍地址: {address}" if address else "系统自动识别的家庭单元"
                self._merge_analysis_unit(
                    config=config,
                    anchor=resolved_anchor,
                    members=resolved_members,
                    member_details=member_details,
                    note=note,
                    unit_type="family",
                )

        # 如果没有 family_units，回退到旧逻辑
        elif persons:
            family_members = family_summary.get("family_members", persons)
            member_details = []
            resolved_members = []
            for i, name in enumerate(family_members):
                member_name = self._resolve_person_name(name, person_candidates) or name
                if member_name not in resolved_members:
                    resolved_members.append(member_name)
                has_data = member_name in profiles
                relation = "本人" if i == 0 else "待确认"
                member_details.append(
                    AnalysisUnitMember(
                        name=member_name,
                        relation=self._normalize_relation_label(
                            relation, is_anchor=(i == 0)
                        ),
                        has_data=has_data,
                    )
                )
                # 记录已分配的人员（仅限有数据的人员）
                if has_data:
                    assigned_persons.add(member_name)

            resolved_anchor = (
                self._resolve_person_name(family_members[0], resolved_members)
                if family_members
                else ""
            )
            self._merge_analysis_unit(
                config=config,
                anchor=resolved_anchor,
                members=resolved_members,
                member_details=member_details,
                note="系统自动生成的默认配置，请根据实际情况调整成员关系和单元划分",
                unit_type="family",
            )

        # 【关键修复】检查未分配的人员，为每个未分配人员创建独立分析单元
        unassigned_persons = [p for p in persons if p not in assigned_persons]
        if unassigned_persons:
            logger.info(
                f"发现 {len(unassigned_persons)} 个未分配的人员: {unassigned_persons}"
            )

            for person_name in unassigned_persons:
                resolved_name = self._resolve_person_name(person_name, person_candidates) or person_name
                has_data = resolved_name in profiles

                # 创建独立人员单元
                self._merge_analysis_unit(
                    config=config,
                    anchor=resolved_name,
                    members=[resolved_name],
                    member_details=[
                        AnalysisUnitMember(
                            name=resolved_name,
                            relation="本人",
                            has_data=has_data,
                        )
                    ],
                    note="系统自动为未分配人员创建的独立单元",
                    unit_type="independent",
                )

            logger.info(f"已为 {len(unassigned_persons)} 个未分配人员创建独立分析单元")

        # 设置待核查公司
        config.include_companies = companies

        errors = validate_config(config)
        if errors:
            logger.warning(f"默认归集配置生成后仍存在问题: {errors}")

        logger.info(
            f"生成默认归集配置: {len(config.analysis_units)} 个分析单元, "
            f"{len(companies)} 个待核查公司"
        )

        return config, "success"

    def get_or_create_config(self) -> Tuple[Optional[PrimaryTargetsConfig], str, bool]:
        """
        获取或创建归集配置

        如果配置文件存在则加载，否则生成默认配置

        Returns:
            (config, message, is_new)
            - is_new: 是否为新生成的配置
        """
        # 先尝试加载现有配置
        if self.config_exists():
            config, msg = self.load_config()
            if config:
                return config, msg, False

        # 生成默认配置
        config, msg = self.generate_default_config()
        if config:
            self._save_auto_generated_snapshot(config)
        return config, msg, True

    def _is_company(self, name: str) -> bool:
        """判断名称是否为公司"""
        return any(kw in name for kw in COMPANY_KEYWORDS)

    def _resolve_person_name(self, raw_name: str, candidate_names: List[str]) -> str:
        """将 family_units 中的姓名归一到画像中的标准姓名。"""
        if not raw_name:
            return ""

        clean_name = str(raw_name).replace("\u200b", "").strip()
        if not clean_name:
            return ""
        if clean_name in candidate_names:
            return clean_name

        target_norm = normalize_for_matching(clean_name)
        norm_hits = [n for n in candidate_names if normalize_for_matching(n) == target_norm]
        if len(norm_hits) == 1:
            return norm_hits[0]

        alias_pairs = {("侯", "候"), ("候", "侯")}
        confusable_hits = []
        for candidate in candidate_names:
            if len(candidate) != len(clean_name):
                continue
            diff = [(a, b) for a, b in zip(clean_name, candidate) if a != b]
            if len(diff) == 1 and diff[0] in alias_pairs:
                confusable_hits.append(candidate)

        if len(confusable_hits) == 1:
            logger.info(f"[默认归集配置][姓名归一] '{clean_name}' -> '{confusable_hits[0]}'")
            return confusable_hits[0]

        return clean_name

    def _normalize_relation_label(self, relation: str, is_anchor: bool = False) -> str:
        """标准化家庭关系标签，供临时归集配置和快照复用。"""
        if is_anchor:
            return "本人"

        rel = str(relation or "").strip()
        relation_map = {
            "户主": "本人",
            "本人": "本人",
            "夫": "配偶",
            "妻": "配偶",
            "配偶": "配偶",
            "子": "儿子",
            "长子": "儿子",
            "次子": "儿子",
            "儿子": "儿子",
            "女": "女儿",
            "长女": "女儿",
            "次女": "女儿",
            "女儿": "女儿",
            "父": "父亲",
            "父亲": "父亲",
            "母": "母亲",
            "母亲": "母亲",
            "兄": "兄长",
            "哥": "兄长",
            "兄长": "兄长",
            "弟": "弟弟",
            "弟弟": "弟弟",
            "姐": "姐姐",
            "姐姐": "姐姐",
            "妹": "妹妹",
            "妹妹": "妹妹",
        }
        return relation_map.get(rel, rel or "家庭成员")

    def _merge_analysis_unit(
        self,
        config: PrimaryTargetsConfig,
        anchor: str,
        members: List[str],
        member_details: List[AnalysisUnitMember],
        note: str,
        unit_type: str,
    ) -> None:
        """按 anchor 合并分析单元，避免临时配置中出现重复锚点。"""
        existing = config.find_unit_by_anchor(anchor)
        if existing:
            merged_members = list(dict.fromkeys(existing.members + members))
            existing.members = merged_members
            existing.unit_type = (
                "family" if len(merged_members) > 1 or unit_type == "family" else unit_type
            )
            if note and note not in existing.note:
                existing.note = f"{existing.note}；{note}".strip("；") if existing.note else note

            detail_map = {detail.name: detail for detail in existing.member_details}
            for detail in member_details:
                if detail.name not in detail_map:
                    detail_map[detail.name] = detail
                else:
                    current = detail_map[detail.name]
                    if not current.relation and detail.relation:
                        current.relation = detail.relation
                    current.has_data = current.has_data or detail.has_data
                    if not current.id_number and detail.id_number:
                        current.id_number = detail.id_number
            existing.member_details = list(detail_map.values())
            return

        config.analysis_units.append(
            AnalysisUnit(
                anchor=anchor,
                members=members,
                unit_type=unit_type,
                member_details=member_details,
                note=note,
            )
        )

    def get_entities_with_data_status(self) -> Dict[str, Any]:
        """
        获取所有实体及其数据状态

        用于前端展示可选择的归集对象

        Returns:
            {
                "persons": [{"name": "xxx", "has_data": true}, ...],
                "companies": [{"name": "xxx", "has_data": true}, ...],
                "family_summary": {...}  # 家庭关系摘要
            }
        """
        cache, msg = self.load_analysis_cache()
        if not cache:
            return {
                "persons": [],
                "companies": [],
                "family_summary": None,
                "error": msg,
            }

        profiles = cache.get("profiles", {})
        derived = cache.get("derived", {})

        persons = []
        companies = []

        for name in profiles.keys():
            entity_info = {
                "name": name,
                "has_data": True,  # profiles 中存在就有数据
            }
            if self._is_company(name):
                companies.append(entity_info)
            else:
                persons.append(entity_info)

        return {
            "persons": persons,
            "companies": companies,
            "family_summary": derived.get("family_summary"),
        }


# ============================================================
# 便捷函数
# ============================================================


def get_service(
    data_dir: str = "./data", output_dir: str = "./output"
) -> PrimaryTargetsService:
    """获取服务实例"""
    return PrimaryTargetsService(data_dir, output_dir)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import sys

    # 设置日志
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # 创建服务
    service = PrimaryTargetsService()

    # 测试加载 analysis_cache
    print("=" * 60)
    print("测试从 analysis_cache 获取实体列表")
    print("=" * 60)

    persons, companies = service.get_available_entities()
    print(f"个人: {persons}")
    print(f"公司: {companies}")

    # 测试获取家庭关系
    print("\n" + "=" * 60)
    print("测试获取家庭关系摘要")
    print("=" * 60)

    family_summary = service.get_family_summary()
    if family_summary:
        print(json.dumps(family_summary, ensure_ascii=False, indent=2))
    else:
        print("未找到家庭关系摘要")

    # 测试生成默认配置
    print("\n" + "=" * 60)
    print("测试生成默认归集配置")
    print("=" * 60)

    config, msg = service.generate_default_config()
    if config:
        print(f"生成成功: {len(config.analysis_units)} 个分析单元")
        print(config.to_json())
    else:
        print(f"生成失败: {msg}")
