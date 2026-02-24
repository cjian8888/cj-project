from __future__ import annotations

from typing import List, Optional, Set, get_origin, get_args

from pydantic import BaseModel, Field, conlist
from pydantic import model_validator


def _infer_depth(tp, seen: Optional[Set[type]] = None, level: int = 1) -> int:
    origin = get_origin(tp)
    try:
        if isinstance(tp, type) and issubclass(tp, BaseModel):
            if seen is None:
                seen = set()
            if tp in seen:
                return level
            seen.add(tp)
            max_child = level
            for ann in getattr(tp, '__annotations__', {}).values():
                d = _infer_depth(ann, seen, level + 1)
                if d > max_child:
                    max_child = d
            return max_child
        
        if origin in (list, List):
            args = get_args(tp)
            if args:
                return _infer_depth(args[0], seen, level)
            return level
        if origin is Optional:
            args = [a for a in get_args(tp) if a is not type(None)]
            if args:
                return _infer_depth(args[0], seen, level)
            return level
    except Exception:
        pass
    return level


def _is_depth_within_limit():
    max_depth = 0
    for ann in UserConfig.__annotations__.values():  # type: ignore[attr-defined]
        d = _infer_depth(ann, set(), 1)
        if d > max_depth:
            max_depth = d
    return max_depth


class AnalysisUnit(BaseModel):
    unit_id: str = Field(..., description="唯一的分析单元标识")
    name: Optional[str] = Field(None, description="单元名称")
    topics: List[str] = Field(default_factory=list, description="分析主题列表")


class FamilyRelation(BaseModel):
    relation_type: str = Field(..., description="关系类型，例如 parent, sibling, spouse")
    relative_name: str = Field(..., description="相关人员姓名")
    notes: Optional[str] = Field(None, description="备注信息", max_length=256)


class UserConfig(BaseModel):
    primary_target: str = Field(
        ..., min_length=1, max_length=100, description="主要调查目标姓名"
    )
    analysis_units: List[AnalysisUnit] = Field(..., description="分析单元列表")
    family_relations: Optional[List[FamilyRelation]] = Field(None, description="家庭关系")

    @model_validator(mode="after")
    def check_units(cls, values):
        units = values.get("analysis_units")
        if not isinstance(units, list) or len(units) < 1:
            raise ValueError("analysis_units must contain at least 1 item")
        return values

    @model_validator(mode="after")
    def check_nested_depth(cls, values):
        max_depth = _is_depth_within_limit()
        if max_depth > 5:
            raise ValueError(f"Nested depth {max_depth} exceeds maximum of 5 layers")
        return values
