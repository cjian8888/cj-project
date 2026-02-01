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

logger = logging.getLogger(__name__)

# 公司名称关键词
COMPANY_KEYWORDS = ['公司', '有限', '集团', '企业', '股份', '合伙', '事务所', '银行']

# 默认配置文件名
CONFIG_FILENAME = "primary_targets.json"


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
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    cache['metadata'] = json.load(f)
            
            # 加载 profiles.json
            profiles_path = os.path.join(self.cache_dir, "profiles.json")
            if os.path.exists(profiles_path):
                with open(profiles_path, 'r', encoding='utf-8') as f:
                    cache['profiles'] = json.load(f)
            
            # 加载 derived_data.json (包含 family_summary)
            derived_path = os.path.join(self.cache_dir, "derived_data.json")
            if os.path.exists(derived_path):
                with open(derived_path, 'r', encoding='utf-8') as f:
                    cache['derived'] = json.load(f)
            
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
        if not cache:
            return [], []
        
        profiles = cache.get('profiles', {})
        
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
        if not cache:
            return None
        
        derived = cache.get('derived', {})
        return derived.get('family_summary')
    
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
        if not cache:
            return None, msg

        profiles = cache.get('profiles', {})
        derived = cache.get('derived', {})

        # 区分个人和公司
        persons = []
        companies = []

        for name in profiles.keys():
            if self._is_company(name):
                companies.append(name)
            else:
                persons.append(name)

        # 获取家庭汇总数据
        family_summary = derived.get('family_summary', {})
        family_units = family_summary.get('family_units', [])
        family_relations = family_summary.get('family_relations', {})

        # 创建默认配置
        config = PrimaryTargetsConfig()

        # 用于跟踪已分配的人员
        assigned_persons = set()

        # 【修复】使用 family_units 创建独立的家庭分析单元
        if family_units:
            for unit in family_units:
                anchor = unit.get('anchor', '')
                members = unit.get('members', [])
                unit_relations = unit.get('relations', {})
                address = unit.get('address', '')

                if not members:
                    continue

                # 创建成员详情
                member_details = []
                for name in members:
                    has_data = name in profiles
                    # 记录已分配的人员（仅限有数据的人员）
                    if has_data:
                        assigned_persons.add(name)

                    # 从 family_relations 获取关系信息
                    person_rels = unit_relations.get(name, {})
                    if name == anchor:
                        relation = "本人"
                    elif person_rels.get('配偶'):
                        relation = "配偶"
                    elif any(anchor in person_rels.get(rel, []) for rel in ['父母']):
                        relation = "父母"
                    elif any(anchor in person_rels.get(rel, []) for rel in ['子女']):
                        relation = "子女"
                    else:
                        # 反向查找关系
                        anchor_rels = unit_relations.get(anchor, {})
                        if name in anchor_rels.get('配偶', []):
                            relation = "配偶"
                        elif name in anchor_rels.get('子女', []):
                            relation = "子女"
                        elif name in anchor_rels.get('父母', []):
                            relation = "父母"
                        else:
                            relation = "家庭成员"

                    member_details.append(AnalysisUnitMember(
                        name=name,
                        relation=relation,
                        has_data=has_data,
                    ))

                # 构建单元备注
                note = f"户籍地址: {address}" if address else "系统自动识别的家庭单元"

                family_unit = AnalysisUnit(
                    anchor=anchor,
                    members=members,
                    unit_type="family",
                    member_details=member_details,
                    note=note
                )
                config.analysis_units.append(family_unit)

        # 如果没有 family_units，回退到旧逻辑
        elif persons:
            family_members = family_summary.get('family_members', persons)
            member_details = []
            for i, name in enumerate(family_members):
                has_data = name in profiles
                relation = "本人" if i == 0 else "待确认"
                member_details.append(AnalysisUnitMember(
                    name=name,
                    relation=relation,
                    has_data=has_data,
                ))
                # 记录已分配的人员（仅限有数据的人员）
                if has_data:
                    assigned_persons.add(name)

            default_unit = AnalysisUnit(
                anchor=family_members[0],
                members=family_members,
                unit_type="family",
                member_details=member_details,
                note="系统自动生成的默认配置，请根据实际情况调整成员关系和单元划分"
            )
            config.analysis_units.append(default_unit)

        # 【关键修复】检查未分配的人员，为每个未分配人员创建独立分析单元
        unassigned_persons = [p for p in persons if p not in assigned_persons]
        if unassigned_persons:
            logger.info(f"发现 {len(unassigned_persons)} 个未分配的人员: {unassigned_persons}")

            for person_name in unassigned_persons:
                has_data = person_name in profiles

                # 创建独立人员单元
                independent_unit = AnalysisUnit(
                    anchor=person_name,
                    members=[person_name],
                    unit_type="independent",
                    member_details=[
                        AnalysisUnitMember(
                            name=person_name,
                            relation="本人",
                            has_data=has_data,
                        )
                    ],
                    note=f"系统自动为未分配人员创建的独立单元"
                )
                config.analysis_units.append(independent_unit)

            logger.info(f"已为 {len(unassigned_persons)} 个未分配人员创建独立分析单元")

        # 设置待核查公司
        config.include_companies = companies

        logger.info(f"生成默认归集配置: {len(config.analysis_units)} 个分析单元, "
                   f"{len(companies)} 个待核查公司")

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
        return config, msg, True
    
    def _is_company(self, name: str) -> bool:
        """判断名称是否为公司"""
        return any(kw in name for kw in COMPANY_KEYWORDS)
    
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
            return {"persons": [], "companies": [], "family_summary": None, "error": msg}
        
        profiles = cache.get('profiles', {})
        derived = cache.get('derived', {})
        
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
            "family_summary": derived.get('family_summary'),
        }


# ============================================================
# 便捷函数
# ============================================================

def get_service(data_dir: str = "./data", output_dir: str = "./output") -> PrimaryTargetsService:
    """获取服务实例"""
    return PrimaryTargetsService(data_dir, output_dir)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import sys
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
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
