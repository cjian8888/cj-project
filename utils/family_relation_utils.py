#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""家庭关系识别辅助函数。"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

from name_normalizer import normalize_for_matching


_NAME_KEYS = (
    "name",
    "person_name",
    "related_name",
    "owner_name",
    "member_name",
)


def _looks_like_identifier(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if re.fullmatch(r"[0-9A-Za-z_\-@.]+", text):
        return True
    if len(re.findall(r"\d", text)) >= 6:
        return True
    return False


def _iter_name_tokens(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        for token in re.split(r"[，,;；/|、]+", value):
            candidate = token.strip()
            if candidate and not _looks_like_identifier(candidate):
                yield candidate
        return

    if isinstance(value, dict):
        for key in _NAME_KEYS:
            candidate = str(value.get(key, "") or "").strip()
            if candidate and not _looks_like_identifier(candidate):
                yield candidate
        for key in ("co_owner", "co_owners", "members"):
            nested = value.get(key)
            if nested:
                yield from _iter_name_tokens(nested)
        return

    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_name_tokens(item)


def collect_family_names_from_profile(
    profile: Optional[Dict[str, Any]],
    subject_name: str = "",
) -> Set[str]:
    """从画像中提取家庭成员/共同生活人姓名。"""
    if not isinstance(profile, dict):
        return set()

    normalized_subject = normalize_for_matching(subject_name)
    names: Set[str] = set()

    for item in profile.get("coaddress_persons", []) or []:
        for name in _iter_name_tokens(item):
            if normalize_for_matching(name) != normalized_subject:
                names.add(name)

    for key in ("properties_precise", "properties"):
        for item in profile.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            ownership_type = str(item.get("ownership_type", "") or item.get("共有情况", "")).strip()
            if "共同共有" not in ownership_type and not item.get("co_owners"):
                continue
            for name in _iter_name_tokens(item.get("co_owners")):
                if normalize_for_matching(name) != normalized_subject:
                    names.add(name)

    for key in ("family_members", "household_members"):
        for name in _iter_name_tokens(profile.get(key)):
            if normalize_for_matching(name) != normalized_subject:
                names.add(name)

    return names


def build_family_pair_keys(
    core_persons: List[str],
    profiles: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Set[frozenset[str]]:
    """根据画像中的同住址/共同共有等信息构建家庭成员对。"""
    profiles = profiles or {}
    alias_to_person = {
        normalize_for_matching(person): person
        for person in core_persons
        if str(person or "").strip()
    }
    family_pairs: Set[frozenset[str]] = set()

    for person in core_persons:
        profile = profiles.get(person)
        if not isinstance(profile, dict):
            continue
        for family_name in collect_family_names_from_profile(profile, subject_name=person):
            matched = alias_to_person.get(normalize_for_matching(family_name))
            if matched and matched != person:
                family_pairs.add(frozenset((person, matched)))

    return family_pairs


def is_family_pair(
    left: str,
    right: str,
    family_pairs: Optional[Set[frozenset[str]]] = None,
) -> bool:
    if not left or not right or left == right or not family_pairs:
        return False
    return frozenset((left, right)) in family_pairs
