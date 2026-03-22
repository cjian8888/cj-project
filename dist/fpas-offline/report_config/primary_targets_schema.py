#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归集配置 JSON Schema 定义

【设计目的】
在报告生成阶段，用户选择归集对象，系统按归集对象组织报告章节。
归集配置在报告模块实现，不中断全局分析流程。

【核心概念】
1. 分析单元（Analysis Unit）：报告中一个独立的分析章节
   - 核心家庭单元：本人 + 配偶 + 子女（资产聚合、收支合并）
   - 独立关联单元：父母/兄弟姐妹（各自独立分析）

2. 归集对象（Anchor）：每个分析单元的核心人物
   - 核心家庭单元的归集对象通常是被核查人本人
   - 独立单元的归集对象是该独立个体

【文件位置】
配置文件保存到原始数据目录下：{data_dir}/primary_targets.json

【版本说明】
- v1.0.0: 初始版本，支持基础归集配置
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import os

# ============================================================
# 版本常量
# ============================================================
SCHEMA_VERSION = "1.0.0"


# ============================================================
# 数据类定义
# ============================================================

@dataclass
class AnalysisUnitMember:
    """分析单元成员"""
    name: str                           # 成员姓名
    relation: str = ""                  # 与归集对象的关系: 本人/配偶/子女/父/母/兄弟/姐妹/其他
    has_data: bool = False              # 是否有流水数据
    id_number: str = ""                 # 身份证号（可选）


@dataclass
class AnalysisUnit:
    """
    分析单元
    
    每个分析单元在报告中生成一个完整的分析章节。
    
    类型说明：
    - family: 核心家庭单元（本人+配偶+子女），资产聚合分析
    - independent: 独立关联单元（父母/兄弟姐妹），独立分析
    """
    anchor: str                         # 归集对象（单元核心人物）
    members: List[str] = field(default_factory=list)  # 成员名单
    unit_type: str = "family"           # 单元类型: family / independent
    
    # 成员详情（可选，用于UI展示）
    member_details: List[AnalysisUnitMember] = field(default_factory=list)
    
    # 单元级别备注
    note: str = ""
    
    def __post_init__(self):
        """确保成员列表至少包含归集对象"""
        if self.anchor and self.anchor not in self.members:
            self.members.insert(0, self.anchor)
    
    def to_dict(self) -> Dict:
        """转换为字典（排除空值）"""
        result = {
            "anchor": self.anchor,
            "members": self.members,
            "unit_type": self.unit_type,
        }
        if self.member_details:
            result["member_details"] = [asdict(m) for m in self.member_details]
        if self.note:
            result["note"] = self.note
        return result


@dataclass
class PrimaryTargetsConfig:
    """
    归集配置（完整结构）
    
    【使用流程】
    1. 全局分析运行完成，生成 analysis_cache
    2. 用户进入报告Tab，系统从 analysis_cache 读取人员列表和家庭关系
    3. 用户选择归集对象，配置分析单元
    4. 配置保存到 primary_targets.json
    5. 报告生成时，按归集配置组织章节结构
    """
    
    # 元信息
    version: str = SCHEMA_VERSION       # Schema 版本
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 核心配置
    employer: str = ""                  # 核查对象所在单位（用于报告表头）
    employer_keywords: List[str] = field(default_factory=list)  # 单位关键词（用于流水匹配）
    
    # 分析单元列表
    analysis_units: List[AnalysisUnit] = field(default_factory=list)
    
    # 公司核查（可选）
    include_companies: List[str] = field(default_factory=list)  # 需要深度核查的公司
    
    # 报告元信息（可选）
    doc_number: str = ""                # 文号
    case_source: str = ""               # 线索来源
    case_notes: str = ""                # 案件备注
    
    def get_all_persons(self) -> List[str]:
        """获取所有分析单元中的人员（去重）"""
        persons = set()
        for unit in self.analysis_units:
            persons.update(unit.members)
        return list(persons)
    
    def get_family_units(self) -> List[AnalysisUnit]:
        """获取所有核心家庭单元"""
        return [u for u in self.analysis_units if u.unit_type == "family"]
    
    def get_independent_units(self) -> List[AnalysisUnit]:
        """获取所有独立关联单元"""
        return [u for u in self.analysis_units if u.unit_type == "independent"]
    
    def find_unit_by_anchor(self, anchor: str) -> Optional[AnalysisUnit]:
        """根据归集对象查找分析单元"""
        for unit in self.analysis_units:
            if unit.anchor == anchor:
                return unit
        return None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": datetime.now().isoformat(),
            "employer": self.employer,
            "employer_keywords": self.employer_keywords,
            "analysis_units": [u.to_dict() for u in self.analysis_units],
            "include_companies": self.include_companies,
            "doc_number": self.doc_number,
            "case_source": self.case_source,
            "case_notes": self.case_notes,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    
    def save(self, filepath: str) -> None:
        """保存到文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def load(cls, filepath: str) -> 'PrimaryTargetsConfig':
        """从文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PrimaryTargetsConfig':
        """从字典创建"""
        # 解析分析单元
        analysis_units = []
        for unit_data in data.get('analysis_units', []):
            # 解析成员详情
            member_details = []
            for md in unit_data.get('member_details', []):
                member_details.append(AnalysisUnitMember(
                    name=md.get('name', ''),
                    relation=md.get('relation', ''),
                    has_data=md.get('has_data', False),
                    id_number=md.get('id_number', ''),
                ))
            
            analysis_units.append(AnalysisUnit(
                anchor=unit_data.get('anchor', ''),
                members=unit_data.get('members', []),
                unit_type=unit_data.get('unit_type', 'family'),
                member_details=member_details,
                note=unit_data.get('note', ''),
            ))
        
        return cls(
            version=data.get('version', SCHEMA_VERSION),
            created_at=data.get('created_at', datetime.now().isoformat()),
            updated_at=data.get('updated_at', datetime.now().isoformat()),
            employer=data.get('employer', ''),
            employer_keywords=data.get('employer_keywords', []),
            analysis_units=analysis_units,
            include_companies=data.get('include_companies', []),
            doc_number=data.get('doc_number', ''),
            case_source=data.get('case_source', ''),
            case_notes=data.get('case_notes', ''),
        )


# ============================================================
# JSON Schema 定义（用于验证）
# ============================================================

PRIMARY_TARGETS_JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PrimaryTargetsConfig",
    "description": "归集配置 - 定义报告的分析单元结构",
    "type": "object",
    "required": ["version", "analysis_units"],
    "properties": {
        "version": {
            "type": "string",
            "description": "Schema 版本号",
            "pattern": r"^\d+\.\d+\.\d+$"
        },
        "created_at": {
            "type": "string",
            "format": "date-time",
            "description": "创建时间"
        },
        "updated_at": {
            "type": "string",
            "format": "date-time",
            "description": "更新时间"
        },
        "employer": {
            "type": "string",
            "description": "核查对象所在单位"
        },
        "employer_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "单位关键词列表"
        },
        "analysis_units": {
            "type": "array",
            "description": "分析单元列表",
            "items": {
                "type": "object",
                "required": ["anchor", "members", "unit_type"],
                "properties": {
                    "anchor": {
                        "type": "string",
                        "description": "归集对象（单元核心人物）"
                    },
                    "members": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "成员名单",
                        "minItems": 1
                    },
                    "unit_type": {
                        "type": "string",
                        "enum": ["family", "independent"],
                        "description": "单元类型"
                    },
                    "member_details": {
                        "type": "array",
                        "description": "成员详情",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "relation": {"type": "string"},
                                "has_data": {"type": "boolean"},
                                "id_number": {"type": "string"}
                            }
                        }
                    },
                    "note": {
                        "type": "string",
                        "description": "单元备注"
                    }
                }
            }
        },
        "include_companies": {
            "type": "array",
            "items": {"type": "string"},
            "description": "需要深度核查的公司列表"
        },
        "doc_number": {
            "type": "string",
            "description": "文号"
        },
        "case_source": {
            "type": "string",
            "description": "线索来源"
        },
        "case_notes": {
            "type": "string",
            "description": "案件备注"
        }
    }
}


# ============================================================
# 辅助函数
# ============================================================

def create_default_config_from_cache(analysis_cache: Dict) -> PrimaryTargetsConfig:
    """
    从 analysis_cache 创建默认归集配置
    
    【逻辑说明】
    1. 从 profiles.json 读取所有实体
    2. 从 derived_data.json 读取 family_summary
    3. 区分个人和公司
    4. 默认将所有个人放入一个核心家庭单元（用户可手动调整）
    
    Args:
        analysis_cache: 由 api_server.py 的 _load_analysis_cache() 加载的完整结果
    
    Returns:
        PrimaryTargetsConfig: 默认归集配置
    """
    config = PrimaryTargetsConfig()
    
    # 提取人员和公司
    profiles = analysis_cache.get('profiles', {})
    derived = analysis_cache.get('derived', {})
    
    # 判断实体类型
    company_keywords = ['公司', '有限', '集团', '企业', '股份', '合伙']
    persons = []
    companies = []
    
    for name in profiles.keys():
        if any(kw in name for kw in company_keywords):
            companies.append(name)
        else:
            persons.append(name)
    
    # 从 family_summary 获取家庭成员信息
    family_summary = derived.get('family_summary', {})
    family_members = family_summary.get('family_members', persons)
    
    # 创建默认核心家庭单元（用户需手动调整）
    if family_members:
        # 默认第一个人作为归集对象
        default_unit = AnalysisUnit(
            anchor=family_members[0] if family_members else "",
            members=family_members,
            unit_type="family",
            note="默认配置，请根据实际情况调整"
        )
        config.analysis_units.append(default_unit)
    
    # 设置待核查公司
    config.include_companies = companies
    
    return config


def validate_config(config: PrimaryTargetsConfig) -> List[str]:
    """
    验证归集配置
    
    Returns:
        List[str]: 错误信息列表，空列表表示验证通过
    """
    errors = []
    
    # 检查版本
    if not config.version:
        errors.append("缺少版本号")
    
    # 检查分析单元
    if not config.analysis_units:
        errors.append("至少需要一个分析单元")
    
    # 检查每个分析单元
    seen_anchors = set()
    for i, unit in enumerate(config.analysis_units):
        prefix = f"分析单元[{i}]"
        
        if not unit.anchor:
            errors.append(f"{prefix}: 缺少归集对象")
        elif unit.anchor in seen_anchors:
            errors.append(f"{prefix}: 归集对象 '{unit.anchor}' 重复")
        else:
            seen_anchors.add(unit.anchor)
        
        if not unit.members:
            errors.append(f"{prefix}: 成员列表为空")
        elif unit.anchor and unit.anchor not in unit.members:
            errors.append(f"{prefix}: 归集对象 '{unit.anchor}' 不在成员列表中")
        
        if unit.unit_type not in ['family', 'independent']:
            errors.append(f"{prefix}: 无效的单元类型 '{unit.unit_type}'")
    
    return errors


# ============================================================
# 示例
# ============================================================

def get_example_config() -> PrimaryTargetsConfig:
    """
    获取示例配置
    
    用于文档和测试
    """
    return PrimaryTargetsConfig(
        employer="XX单位",
        employer_keywords=["XX单位", "XX局"],
        analysis_units=[
            AnalysisUnit(
                anchor="甲某某",
                members=["甲某某", "乙某某", "甲小某"],
                unit_type="family",
                member_details=[
                    AnalysisUnitMember(name="甲某某", relation="本人", has_data=True),
                    AnalysisUnitMember(name="乙某某", relation="配偶", has_data=True),
                    AnalysisUnitMember(name="甲小某", relation="子女", has_data=True),
                ],
                note="核心家庭单元"
            ),
            AnalysisUnit(
                anchor="甲大某",
                members=["甲大某"],
                unit_type="independent",
                member_details=[
                    AnalysisUnitMember(name="甲大某", relation="父亲", has_data=True),
                ],
                note="独立关联单元"
            ),
        ],
        include_companies=[
            "XX科技有限公司",
            "YY科技有限公司",
        ],
        doc_number="国监查 [2026] 第 XXXXXX 号",
        case_source="群众举报",
    )


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    # 创建示例配置
    example = get_example_config()
    
    # 验证
    errors = validate_config(example)
    if errors:
        print("验证失败:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("验证通过")
    
    # 输出 JSON
    print("\n示例 JSON:")
    print(example.to_json())
    
    # 测试序列化/反序列化
    json_str = example.to_json()
    loaded = PrimaryTargetsConfig.from_dict(json.loads(json_str))
    print(f"\n反序列化验证: {len(loaded.analysis_units)} 个分析单元")
