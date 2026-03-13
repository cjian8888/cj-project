#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api_server 归集配置与缓存边界回归测试。"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_server import (
    InvestigationReportRequest,
    _apply_report_generation_overrides,
    _get_effective_family_units_for_analysis,
    _save_external_report_caches,
)
from cache_manager import CacheManager
from report_config.primary_targets_schema import (
    AnalysisUnit,
    AnalysisUnitMember,
    PrimaryTargetsConfig,
)
from report_config.primary_targets_service import PrimaryTargetsService


def test_apply_report_generation_overrides_can_filter_to_company_only():
    config = PrimaryTargetsConfig(
        analysis_units=[
            AnalysisUnit(
                anchor="张三",
                members=["张三"],
                unit_type="independent",
                member_details=[
                    AnalysisUnitMember(name="张三", relation="本人", has_data=True)
                ],
            )
        ],
        include_companies=["某公司"],
    )
    request = InvestigationReportRequest(selected_subjects=["某公司"])

    result = _apply_report_generation_overrides(config, request)

    assert result.analysis_units == []
    assert result.include_companies == ["某公司"]


def test_get_effective_family_units_for_analysis_prefers_saved_primary_config(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    service = PrimaryTargetsService(data_dir=str(data_dir), output_dir=str(output_dir))
    config = PrimaryTargetsConfig(
        analysis_units=[
            AnalysisUnit(
                anchor="张三",
                members=["张三", "李四"],
                unit_type="family",
                member_details=[
                    AnalysisUnitMember(name="张三", relation="本人", has_data=True),
                    AnalysisUnitMember(name="李四", relation="配偶", has_data=True),
                ],
            )
        ]
    )
    ok, msg = service.save_config(config)
    assert ok, msg

    inferred_units = [
        {
            "anchor": "自动户主",
            "householder": "自动户主",
            "members": ["自动户主", "家属"],
            "member_details": [],
        }
    ]
    effective_units, applied_config = _get_effective_family_units_for_analysis(
        inferred_units=inferred_units,
        data_dir=str(data_dir),
        output_dir=str(output_dir),
        profiles={"张三": {}, "李四": {}},
    )

    assert applied_config is not None
    assert effective_units[0]["anchor"] == "张三"
    assert effective_units[0]["householder"] == "张三"
    assert effective_units[0]["members"] == ["张三", "李四"]
    assert effective_units[0]["member_details"][1]["relation"] == "配偶"


def test_save_external_report_caches_overwrites_stale_empty_data(tmp_path):
    cache_dir = tmp_path / "analysis_cache"
    cache_dir.mkdir()
    cache_mgr = CacheManager(str(cache_dir))
    cache_mgr.save_cache("vehicleData", {"old": ["stale"]})

    _save_external_report_caches(
        cache_mgr,
        {
            "p0": {"credit_data": {}, "aml_data": {}},
            "p1": {
                "vehicle_data": {},
                "precise_property_data": {},
                "wealth_product_data": {},
                "securities_data": {},
            },
        },
        logging.getLogger(__name__),
    )

    with open(cache_dir / "vehicleData.json", "r", encoding="utf-8") as f:
        vehicle_data = json.load(f)

    assert vehicle_data == {}
