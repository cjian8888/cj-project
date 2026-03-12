#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""归集配置服务回归测试。"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from report_config.primary_targets_service import PrimaryTargetsService
from report_config.primary_targets_schema import validate_config


def test_generate_default_config_deduplicates_confusable_anchor_names(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    cache_dir = output_dir / "analysis_cache"
    data_dir.mkdir()
    cache_dir.mkdir(parents=True)

    profiles = {
        "候海焱": {"summary": {"total_income": 10000}},
    }
    derived = {
        "family_units_v2": [
            {
                "anchor": "侯海焱",
                "members": ["周天健", "侯海焱", "周伟"],
                "member_details": [
                    {"name": "周天健", "relation": "配偶"},
                    {"name": "侯海焱", "relation": "本人"},
                    {"name": "周伟", "relation": "子女"},
                ],
            },
            {
                "anchor": "候海焱",
                "members": ["候海焱"],
                "member_details": [
                    {"name": "候海焱", "relation": "本人"},
                ],
            },
        ]
    }

    (cache_dir / "profiles.json").write_text(
        json.dumps(profiles, ensure_ascii=False), encoding="utf-8"
    )
    (cache_dir / "derived_data.json").write_text(
        json.dumps(derived, ensure_ascii=False), encoding="utf-8"
    )
    (cache_dir / "metadata.json").write_text("{}", encoding="utf-8")

    service = PrimaryTargetsService(data_dir=str(data_dir), output_dir=str(output_dir))
    config, msg = service.generate_default_config()

    assert msg == "success"
    assert config is not None
    assert len(config.analysis_units) == 1
    unit = config.analysis_units[0]
    assert unit.anchor == "候海焱"
    assert unit.members == ["周天健", "候海焱", "周伟"]
    assert validate_config(config) == []


def test_get_or_create_config_writes_auto_snapshot(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    cache_dir = output_dir / "analysis_cache"
    data_dir.mkdir()
    cache_dir.mkdir(parents=True)

    (cache_dir / "profiles.json").write_text(
        json.dumps({"张三": {"summary": {"total_income": 10000}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (cache_dir / "derived_data.json").write_text("{}", encoding="utf-8")
    (cache_dir / "metadata.json").write_text("{}", encoding="utf-8")

    service = PrimaryTargetsService(data_dir=str(data_dir), output_dir=str(output_dir))
    config, msg, is_new = service.get_or_create_config()

    assert msg == "success"
    assert is_new is True
    assert config is not None
    assert Path(service.auto_config_path).exists()


def test_generate_default_config_normalizes_relation_labels(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    cache_dir = output_dir / "analysis_cache"
    data_dir.mkdir()
    cache_dir.mkdir(parents=True)

    profiles = {
        "候海焱": {"summary": {"total_income": 10000}},
    }
    derived = {
        "family_units_v2": [
            {
                "anchor": "侯海焱",
                "members": ["周天健", "侯海焱", "周伟"],
                "member_details": [
                    {"name": "周天健", "relation": "女"},
                    {"name": "侯海焱", "relation": "户主"},
                    {"name": "周伟", "relation": "夫"},
                ],
            }
        ]
    }

    (cache_dir / "profiles.json").write_text(
        json.dumps(profiles, ensure_ascii=False), encoding="utf-8"
    )
    (cache_dir / "derived_data.json").write_text(
        json.dumps(derived, ensure_ascii=False), encoding="utf-8"
    )
    (cache_dir / "metadata.json").write_text("{}", encoding="utf-8")

    service = PrimaryTargetsService(data_dir=str(data_dir), output_dir=str(output_dir))
    config, msg = service.generate_default_config()

    assert msg == "success"
    details = {d.name: d.relation for d in config.analysis_units[0].member_details}
    assert details["候海焱"] == "本人"
    assert details["周伟"] == "配偶"
    assert details["周天健"] == "女儿"
