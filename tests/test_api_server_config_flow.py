#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api_server 归集配置与缓存边界回归测试。"""

import asyncio
import json
import logging
import os
import pathlib
import sys
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest
from starlette.requests import Request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import api_server
import clue_aggregator
from api_server import (
    InvestigationReportRequest,
    _apply_report_generation_overrides,
    _build_all_family_summaries,
    _enhance_suspicions_with_analysis,
    _get_effective_family_units_for_analysis,
    _populate_transport_external_data,
    _refresh_profile_real_metrics,
    _refresh_profiles_and_build_family_summaries,
    _save_external_report_caches,
    get_graph_data,
    serialize_for_json,
    serialize_analysis_results,
)
from cache_manager import CacheManager
from investigation_report_builder import InvestigationReportBuilder
from report_quality_guard import REPORT_QA_GUARD_VERSION
from report_config.primary_targets_schema import (
    AnalysisUnit,
    AnalysisUnitMember,
    PrimaryTargetsConfig,
)
from report_config.primary_targets_service import PrimaryTargetsService
from specialized_reports import SpecializedReportGenerator


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


def test_refresh_profiles_and_build_family_summaries_uses_refreshed_profiles(monkeypatch):
    profiles = {
        "张三": {"summary": {"real_income": 100.0, "real_expense": 40.0}},
        "李四": {"summary": {"real_income": 20.0, "real_expense": 10.0}},
    }
    family_units = [
        {
            "anchor": "张三",
            "householder": "张三",
            "members": ["张三", "李四"],
            "extended_relatives": [],
        }
    ]

    def fake_refresh(_profiles, _cleaned_data, _family_units, _analyzer, _logger):
        _profiles["张三"]["summary"]["real_income"] = 1000.0
        _profiles["李四"]["summary"]["real_income"] = 200.0
        return 2

    monkeypatch.setattr(api_server, "_refresh_profiles_with_family_units", fake_refresh)
    monkeypatch.setattr(
        api_server,
        "_collect_family_assets_for_summary",
        lambda _members, _profiles: {"properties": [], "vehicles": []},
    )
    monkeypatch.setattr(
        api_server.family_finance,
        "calculate_family_summary",
        lambda current_profiles, members, properties=None, vehicles=None: {
            "total_income": sum(
                current_profiles[name]["summary"]["real_income"]
                for name in members
                if name in current_profiles
            ),
            "total_expense": sum(
                current_profiles[name]["summary"]["real_expense"]
                for name in members
                if name in current_profiles
            ),
        },
    )

    updated_count, summaries = _refresh_profiles_and_build_family_summaries(
        profiles=profiles,
        cleaned_data={"张三": pd.DataFrame(), "李四": pd.DataFrame()},
        family_units_list=family_units,
        income_expense_match_analyzer=object(),
        logger=logging.getLogger(__name__),
    )

    assert updated_count == 2
    assert summaries["张三"]["total_income"] == 1200.0
    assert summaries["张三"]["householder"] == "张三"


def test_build_all_family_summaries_uses_current_profile_values(monkeypatch):
    profiles = {
        "张三": {
            "summary": {"real_income": 500.0, "real_expense": 200.0},
            "properties": [],
            "vehicles": [],
        }
    }
    family_units = [{"anchor": "张三", "householder": "张三", "members": ["张三"]}]

    monkeypatch.setattr(
        api_server,
        "_collect_family_assets_for_summary",
        lambda _members, _profiles: {"properties": [], "vehicles": []},
    )
    monkeypatch.setattr(
        api_server.family_finance,
        "calculate_family_summary",
        lambda current_profiles, members, properties=None, vehicles=None: {
            "total_income": current_profiles["张三"]["summary"]["real_income"],
            "total_expense": current_profiles["张三"]["summary"]["real_expense"],
        },
    )

    summaries = _build_all_family_summaries(
        profiles=profiles,
        family_units_list=family_units,
        logger=logging.getLogger(__name__),
    )

    assert summaries["张三"]["total_income"] == 500.0
    assert summaries["张三"]["total_expense"] == 200.0


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


def test_cache_manager_save_and_load_results_preserves_phase2_external_data(tmp_path):
    cache_dir = tmp_path / "analysis_cache"
    cache_mgr = CacheManager(str(cache_dir))

    cache_mgr.save_results(
        {
            "persons": ["张三"],
            "companies": [],
            "profiles": {"张三": {"totalIncome": 1000, "summary": {"total_income": 1000}}},
            "suspicions": {},
            "analysisResults": {},
            "graphData": {},
            "externalData": {
                "p2": {
                    "hotel_data": {
                        "310101199001010011": [{"hotel_name": "某酒店"}]
                    },
                    "flight_data": {
                        "310101199001010011": {
                            "completed": [{"flight_no": "MU5123"}]
                        }
                    },
                    "coaddress_data": {
                        "310101199001010011": [{"name": "李四"}]
                    },
                }
            },
        },
        id_to_name_map={"310101199001010011": "张三"},
    )

    loaded = cache_mgr.load_results()

    assert loaded is not None
    assert loaded["hotelData"]["310101199001010011"][0]["hotel_name"] == "某酒店"
    assert (
        loaded["flightData"]["310101199001010011"]["completed"][0]["flight_no"]
        == "MU5123"
    )
    assert loaded["coaddressData"]["310101199001010011"][0]["name"] == "李四"
    assert loaded["external_p2"]["hotel_data"]["310101199001010011"][0]["hotel_name"] == "某酒店"


def test_cache_manager_load_results_restores_external_data_and_runtime_log_paths(tmp_path):
    cache_dir = tmp_path / "analysis_cache"
    cache_mgr = CacheManager(str(cache_dir))

    cache_mgr.save_results(
        {
            "persons": ["张三"],
            "companies": ["某公司"],
            "profiles": {"张三": {"summary": {"total_income": 1000}}},
            "suspicions": {"directTransfers": []},
            "analysisResults": {"summary": {"ok": True}},
            "graphData": {"nodes": [], "edges": []},
            "walletData": {"subjectsById": {"310101199001010011": {"subjectName": "张三"}}},
            "externalData": {
                "p0": {"credit_data": {"张三": {"alerts": 1}}},
                "p1": {"vehicle_data": {"310101199001010011": [{"plate_number": "沪A12345"}]}},
                "p2": {"hotel_data": {"310101199001010011": [{"hotel_name": "某酒店"}]}},
                "wallet": {"subjectsById": {"310101199001010011": {"subjectName": "张三"}}},
            },
            "runtimeLogPaths": {"analysisLog": "/tmp/analysis.log"},
        },
        id_to_name_map={"310101199001010011": "张三"},
    )

    loaded = cache_mgr.load_results()

    assert loaded is not None
    assert loaded["externalData"]["p0"]["credit_data"]["张三"]["alerts"] == 1
    assert loaded["externalData"]["p1"]["vehicle_data"]["310101199001010011"][0]["plate_number"] == "沪A12345"
    assert loaded["externalData"]["p2"]["hotel_data"]["310101199001010011"][0]["hotel_name"] == "某酒店"
    assert loaded["externalData"]["wallet"]["subjectsById"]["310101199001010011"]["subjectName"] == "张三"
    assert loaded["runtimeLogPaths"]["analysisLog"] == "/tmp/analysis.log"


def test_cache_manager_save_cache_serializes_set_values(tmp_path):
    cache_dir = tmp_path / "analysis_cache"
    cache_mgr = CacheManager(str(cache_dir))

    cache_mgr.save_cache(
        "profiles",
        {"张三": {"aliases": {"A", "B"}, "summary": {"tags": {"高风险", "闭环"}}}},
    )

    with open(cache_dir / "profiles.json", "r", encoding="utf-8") as f:
        saved = json.load(f)

    assert saved["张三"]["aliases"] == ["A", "B"]
    assert saved["张三"]["summary"]["tags"] == ["闭环", "高风险"]


def test_cache_manager_save_cache_keeps_old_file_when_serialization_fails(tmp_path):
    cache_dir = tmp_path / "analysis_cache"
    cache_mgr = CacheManager(str(cache_dir))
    cache_mgr.save_cache("profiles", {"张三": {"totalIncome": 1000}})

    with pytest.raises(TypeError):
        cache_mgr.save_cache("profiles", {"bad": object()})

    with open(cache_dir / "profiles.json", "r", encoding="utf-8") as f:
        saved = json.load(f)

    assert saved == {"张三": {"totalIncome": 1000}}


def test_build_id_to_name_map_supports_csv_and_nonstandard_filename(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    pd.DataFrame(
        [
            {"机动车所有人": "张三", "身份证号": "310101199001010011"},
        ]
    ).to_csv(data_dir / "公安部机动车信息_批次1.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(
        [
            {"姓名": "李四", "证件号码": "310101199001010022"},
        ]
    ).to_excel(data_dir / "住宿明细结果.xlsx", index=False)

    id_to_name_map = api_server._build_id_to_name_map(
        str(data_dir),
        external_data={},
        known_person_names=["张三", "李四"],
    )

    assert id_to_name_map["310101199001010011"] == "张三"
    assert id_to_name_map["310101199001010022"] == "李四"


def test_merge_plugin_suspicions_exposes_transaction_only_detector_outputs():
    merged = api_server._merge_plugin_suspicions(
        {"direct_transfers": [], "fixed_frequency": {}, "amount_patterns": {}},
        {
            "round_amount": [{"entity_name": "张三", "description": "整数金额"}],
            "fixed_amount": [{"entity_name": "张三", "description": "固定金额"}],
            "fixed_frequency": [{"entity_name": "张三", "description": "固定频率"}],
            "frequency_anomaly": [{"entity_name": "张三", "description": "高频异常"}],
            "suspicious_pattern": [{"entity_name": "张三", "description": "可疑模式"}],
        },
    )

    assert len(merged["amount_patterns"]["张三"]) == 2
    assert merged["fixed_frequency"]["张三"][0]["description"] == "固定频率"
    assert merged["frequency_anomaly"][0]["description"] == "高频异常"
    assert merged["suspicious_pattern"][0]["description"] == "可疑模式"


def test_populate_transport_external_data_keeps_base_data_when_timeline_fails(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "railway_extractor",
        SimpleNamespace(
            extract_railway_data=lambda _data_dir: {"pid": {"tickets": [{"id": 1}]}},
            get_travel_timeline=lambda _data_dir: (_ for _ in ()).throw(
                RuntimeError("timeline unavailable")
            ),
        ),
    )
    monkeypatch.setattr(
        api_server,
        "flight_extractor",
        SimpleNamespace(
            extract_flight_data=lambda _data_dir: {
                "pid": {"completed": [{"flight_no": "MU5123"}]}
            },
            get_flight_timeline=lambda _data_dir: [{"type": "flight", "id": 1}],
        ),
    )

    phase2 = {}
    _populate_transport_external_data("dummy-data", phase2, logging.getLogger(__name__))

    assert phase2["railway_data"]["pid"]["tickets"][0]["id"] == 1
    assert phase2["railway_timeline"] == []
    assert phase2["flight_data"]["pid"]["completed"][0]["flight_no"] == "MU5123"
    assert phase2["flight_timeline"][0]["type"] == "flight"


def test_serialize_analysis_results_uses_aggregation_to_dict_output():
    aggregator = clue_aggregator.ClueAggregator(["张三"], [])
    aggregator.evidence_packs["张三"].update(
        {
            "risk_score": 81.0,
            "risk_level": "critical",
            "risk_confidence": 0.87,
            "top_evidence_score": 84.0,
            "high_priority_clue_count": 2,
            "summary": "存在高风险闭环",
            "aggregation_explainability": {
                "top_clues": [{"description": "资金闭环: 张三 → 外围账户B → 张三"}]
            },
        }
    )
    aggregator.evidence_packs["张三"]["evidence"]["fund_cycles"].append(
        {
            "path": "张三 → 外围账户B → 张三",
            "risk_score": 84,
            "confidence": 0.92,
        }
    )

    serialized = serialize_analysis_results({"aggregation": aggregator})

    assert serialized["aggregation"]["rankedEntities"][0]["name"] == "张三"
    assert serialized["aggregation"]["rankedEntities"][0]["riskConfidence"] == 0.87
    assert serialized["aggregation"]["summary"]["极高风险实体数"] == 1


def test_serialize_analysis_results_flattens_related_party_details_with_type_tags():
    serialized = serialize_analysis_results(
        {
            "relatedParty": {
                "summary": {"关系簇数": 1},
                "direct_flows": [{"person": "张三", "counterparty": "李四"}],
                "third_party_relays": [{"person": "张三", "relay": "外围账户B"}],
                "fund_loops": [{"path": "张三 → 外围账户B → 张三"}],
                "discovered_nodes": [{"name": "外围账户B"}],
                "relationship_clusters": [{"cluster_id": "cluster-1"}],
            }
        }
    )

    related_party = serialized["relatedParty"]
    detail_types = [item["_type"] for item in related_party["details"]]

    assert related_party["summary"] == {"关系簇数": 1}
    assert detail_types == [
        "direct_flow",
        "third_party_relay",
        "fund_loop",
        "discovered_node",
        "relationship_cluster",
    ]
    assert related_party["direct_flows"][0]["counterparty"] == "李四"
    assert related_party["discovered_nodes"][0]["name"] == "外围账户B"


def test_enhance_suspicions_keeps_existing_time_series_alerts_when_analysis_alerts_missing():
    suspicions = {"timeSeriesAlerts": [{"id": "plugin-alert"}]}
    analysis_results = {"timeSeries": {"periodic_income": []}}

    enhanced = _enhance_suspicions_with_analysis(suspicions, analysis_results)

    assert enhanced["timeSeriesAlerts"] == [{"id": "plugin-alert"}]


def test_enhance_suspicions_prefers_non_empty_analysis_time_series_alerts():
    suspicions = {"timeSeriesAlerts": [{"id": "plugin-alert"}]}
    analysis_results = {"timeSeries": {"alerts": [{"id": "analysis-alert"}]}}

    enhanced = _enhance_suspicions_with_analysis(suspicions, analysis_results)

    assert enhanced["timeSeriesAlerts"] == [{"id": "analysis-alert"}]


def test_get_graph_data_exposes_phase1_related_party_outputs_and_prefers_penetration_cycles():
    previous_status = api_server.analysis_state.status
    previous_results = api_server.analysis_state.results

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.results = {
        "persons": ["张三", "李四"],
        "companies": [],
        "analysisResults": {
            "aggregation": {
                "summary": {
                    "极高风险实体数": 1,
                    "高风险实体数": 0,
                    "高优先线索实体数": 1,
                },
                "rankedEntities": [
                    {
                        "name": "张三",
                        "riskScore": 88,
                        "riskConfidence": 0.93,
                        "riskLevel": "critical",
                        "highPriorityClueCount": 2,
                        "topEvidenceScore": 86,
                        "summary": "存在高风险资金回流",
                        "aggregationExplainability": {
                            "top_clues": [
                                {"description": "资金闭环: 张三 → 外围账户B → 李四 → 张三"}
                            ]
                        },
                    }
                ],
            },
            "relatedParty": {
                "discovered_nodes": [{"name": "外围账户B"}],
                "third_party_relays": [
                    {
                        "from": "张三",
                        "relay": "外围账户B",
                        "to": "李四",
                        "time_diff_hours": 6.0,
                        "path_explainability": {
                            "summary": "资金在 6.0 小时内经 外围账户B 由 张三 转向 李四",
                            "inspection_points": ["链路路径: 张三 → 外围账户B → 李四"],
                            "sequence_summary": "第1步 张三 向 外围账户B 转出，第2步 外围账户B 向 李四 转入，两步相隔 6.0 小时",
                            "time_axis": [
                                {
                                    "step": 1,
                                    "time": "2024-01-01 10:00:00",
                                    "label": "张三 向 外围账户B 转出",
                                    "amount": 180000,
                                },
                                {
                                    "step": 2,
                                    "time": "2024-01-01 16:00:00",
                                    "label": "外围账户B 向 李四 转入",
                                    "amount": 178000,
                                },
                            ],
                        },
                    }
                ],
                "relationship_clusters": [
                    {
                        "cluster_id": "cluster-1",
                        "core_members": ["张三", "李四"],
                        "external_members": ["外围账户B"],
                        "path_explainability": {
                            "summary": "该关系簇包含核心成员 2 个、外围成员 1 个",
                            "inspection_points": ["成员构成: 核心 张三、李四 / 外围 外围账户B"],
                        },
                    }
                ],
                "fund_loops": [
                    {
                        "path": "张三 → 外围账户B → 张三",
                        "path_explainability": {
                            "summary": "闭环路径包含 2 个节点",
                            "inspection_points": ["回流路径: 张三 → 外围账户B → 张三"],
                            "edge_segments": [
                                {"index": 1, "from": "张三", "to": "外围账户B", "amount": 180000},
                                {"index": 2, "from": "外围账户B", "to": "张三", "amount": 180000},
                            ],
                            "bottleneck_edge": {"from": "张三", "to": "外围账户B", "amount": 180000},
                        },
                    }
                ],
            },
            "penetration": {
                "analysis_metadata": {
                    "fund_cycles": {
                        "truncated": True,
                        "truncated_reasons": ["timeout"],
                        "timeout_seconds": 30,
                    }
                },
                "fund_cycles": [{"path": "张三 → 外围账户B → 李四 → 张三"}]
            },
        },
        "graphData": {
            "nodes": [{"id": "张三"}, {"id": "外围账户B"}],
            "edges": [{"source": "张三", "target": "外围账户B"}],
        },
    }

    try:
        response = asyncio.run(get_graph_data())
    finally:
        api_server.analysis_state.status = previous_status
        api_server.analysis_state.results = previous_results

    assert response["message"] == "success"
    assert response["data"]["stats"]["discoveredNodeCount"] == 1
    assert response["data"]["stats"]["relationshipClusterCount"] == 1
    assert response["data"]["report"]["discovered_nodes"][0]["name"] == "外围账户B"
    assert (
        response["data"]["report"]["relationship_clusters"][0]["cluster_id"]
        == "cluster-1"
    )
    assert response["data"]["report"]["fund_cycles"] == [
        {"path": "张三 → 外围账户B → 李四 → 张三"}
    ]
    assert response["data"]["report"]["fund_cycle_meta"]["truncated"] is True
    assert response["data"]["report"]["fund_cycle_meta"]["truncated_reasons"] == [
        "timeout"
    ]
    assert response["data"]["report"]["focus_entities"][0]["name"] == "张三"
    assert response["data"]["report"]["focus_entities"][0]["in_graph"] is True
    assert response["data"]["report"]["aggregation_summary"]["极高风险实体数"] == 1
    assert response["data"]["report"]["third_party_relays"][0]["relay"] == "外围账户B"
    assert (
        response["data"]["report"]["third_party_relays"][0]["path_explainability"]["summary"]
        == "资金在 6.0 小时内经 外围账户B 由 张三 转向 李四"
    )
    assert len(response["data"]["report"]["third_party_relays"][0]["path_explainability"]["time_axis"]) == 2


def test_get_graph_data_augments_wallet_edges_and_report_sections():
    previous_status = api_server.analysis_state.status
    previous_results = api_server.analysis_state.results

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.results = {
        "persons": ["张三"],
        "companies": [],
        "walletData": {
            "subjects": [
                {
                    "subjectId": "110101199001010011",
                    "subjectName": "张三",
                    "matchedToCore": True,
                    "platforms": {
                        "alipay": {
                            "topCounterparties": [
                                {"name": "李四", "count": 6, "totalAmountYuan": 62000}
                            ]
                        },
                        "wechat": {
                            "topCounterparties": [
                                {"name": "王五", "count": 5, "totalAmountYuan": 58000}
                            ]
                        },
                    },
                }
            ],
            "alerts": [
                {
                    "person": "张三",
                    "counterparty": "李四",
                    "amount": 62000,
                    "risk_level": "medium",
                    "description": "电子钱包往来密集",
                    "alert_type": "wallet_dense_counterparty",
                }
            ],
        },
        "analysisResults": {
            "aggregation": {"summary": {}, "rankedEntities": []},
            "relatedParty": {
                "discovered_nodes": [],
                "third_party_relays": [],
                "relationship_clusters": [],
                "fund_loops": [],
            },
            "penetration": {"summary": {}, "fund_cycles": []},
        },
        "graphData": {
            "nodes": [{"id": "张三", "label": "张三", "group": "core"}],
            "edges": [],
        },
    }

    try:
        response = asyncio.run(get_graph_data())
    finally:
        api_server.analysis_state.status = previous_status
        api_server.analysis_state.results = previous_results

    assert response["message"] == "success"
    assert response["data"]["stats"]["walletAlertCount"] == 1
    assert response["data"]["stats"]["walletCounterpartyCount"] >= 1
    assert response["data"]["report"]["wallet_alerts"][0]["counterparty"] == "李四"
    assert any(edge.get("type") == "wallet" for edge in response["data"]["edges"])


def test_get_graph_data_preserves_snake_case_report_contract():
    previous_status = api_server.analysis_state.status
    previous_results = api_server.analysis_state.results

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.results = {
        "persons": ["张三"],
        "companies": ["测试科技有限公司"],
        "walletData": {},
        "analysisResults": {
            "aggregation": {"summary": {}, "rankedEntities": []},
            "relatedParty": {
                "third_party_relays": [{"from": "张三", "relay": "外围账户B", "to": "李四"}],
                "discovered_nodes": [{"name": "外围账户B"}],
                "relationship_clusters": [{"cluster_id": "cluster-1"}],
                "fund_loops": [],
            },
            "penetration": {
                "analysis_metadata": {"fund_cycles": {"truncated": False}},
                "fund_cycles": [{"path": "张三 → 外围账户B → 李四 → 张三"}],
            },
        },
        "graphData": {
            "nodes": [{"id": "张三", "label": "张三"}],
            "edges": [{"source": "张三", "target": "外围账户B"}],
        },
    }

    try:
        response = asyncio.run(get_graph_data())
    finally:
        api_server.analysis_state.status = previous_status
        api_server.analysis_state.results = previous_results

    report = response["data"]["report"]
    stats = response["data"]["stats"]

    assert "nodeCount" in stats
    assert "node_count" not in stats

    for snake_key in (
        "loan_pairs",
        "no_repayment_loans",
        "high_risk_income",
        "online_loans",
        "third_party_relays",
        "discovered_nodes",
        "relationship_clusters",
        "fund_cycles",
        "fund_cycle_meta",
        "focus_entities",
        "aggregation_summary",
        "aggregation_metadata",
        "wallet_alerts",
        "wallet_counterparties",
    ):
        assert snake_key in report

    for camel_key in (
        "loanPairs",
        "noRepaymentLoans",
        "highRiskIncome",
        "onlineLoans",
        "thirdPartyRelays",
        "discoveredNodes",
        "relationshipClusters",
        "fundCycles",
        "fundCycleMeta",
        "focusEntities",
        "aggregationSummary",
        "aggregationMetadata",
        "walletAlerts",
        "walletCounterparties",
    ):
        assert camel_key not in report

    assert report["relationship_clusters"][0]["cluster_id"] == "cluster-1"
    assert "clusterId" not in report["relationship_clusters"][0]


def test_get_audit_navigation_refreshes_semantic_artifacts_and_includes_recursive_reports(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    analysis_results_dir = output_dir / "analysis_results"
    qa_dir = analysis_results_dir / "qa"
    appendix_dir = analysis_results_dir / "专项报告"
    cleaned_person_dir = output_dir / "cleaned_data" / "个人"
    cleaned_company_dir = output_dir / "cleaned_data" / "公司"

    qa_dir.mkdir(parents=True)
    appendix_dir.mkdir(parents=True)
    cleaned_person_dir.mkdir(parents=True)
    cleaned_company_dir.mkdir(parents=True)

    (analysis_results_dir / "核查结果分析报告.txt").write_text("main", encoding="utf-8")
    (appendix_dir / "资金穿透分析报告.txt").write_text("appendix", encoding="utf-8")
    (cleaned_person_dir / "张三_合并流水.xlsx").write_text("person", encoding="utf-8")
    (cleaned_company_dir / "测试科技有限公司_合并流水.xlsx").write_text(
        "company", encoding="utf-8"
    )
    (qa_dir / "report_package.json").write_text(
        json.dumps(
            {
                "meta": {"generated_at": "2026-03-20T10:00:00"},
                "qa_checks": {
                    "summary": {"pass": 1, "warn": 0, "fail": 0, "total": 1},
                    "checks": [],
                    "meta": {
                        "qa_guard_version": REPORT_QA_GUARD_VERSION,
                        "generated_at": "2026-03-20T10:00:00",
                    },
                },
                "artifact_meta": {
                    "package_generated_at": "2026-03-20T10:00:00",
                    "source_report_generated_at": "2026-03-20T10:00:00",
                    "qa_guard_version": REPORT_QA_GUARD_VERSION,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    refresh_calls = []
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
    }
    previous_config = dict(api_server._current_config)
    previous_sync = api_server._sync_analysis_state_with_active_output

    def fake_refresh(active_output_dir):
        refresh_calls.append(active_output_dir)
        (qa_dir / "report_consistency_check.txt").write_text("fresh qa", encoding="utf-8")
        return {"qa_check_path": str(qa_dir / "report_consistency_check.txt")}

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.progress = 100
    api_server.analysis_state.phase = "已完成"
    api_server.analysis_state.results = {
        "persons": ["张三"],
        "companies": ["测试科技有限公司"],
        "analysisResults": {},
        "graphData": {"nodes": [], "edges": []},
    }

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        monkeypatch.setattr(
            api_server,
            "_refresh_report_semantic_artifacts",
            fake_refresh,
        )
        monkeypatch.setattr(
            api_server,
            "_sync_analysis_state_with_active_output",
            lambda force_reload=False: True,
        )

        payload = asyncio.run(api_server.get_audit_navigation())
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server._sync_analysis_state_with_active_output = previous_sync
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    report_names = {item["name"] for item in payload["reports"]}
    assert refresh_calls == [str(output_dir)]
    assert payload["persons"][0]["filename"] == "张三_合并流水.xlsx"
    assert payload["companies"][0]["filename"] == "测试科技有限公司_合并流水.xlsx"
    assert "核查结果分析报告.txt" in report_names
    assert "专项报告/资金穿透分析报告.txt" in report_names
    assert "qa/report_consistency_check.txt" in report_names
    assert payload["totalEntities"] == 2


def test_sync_active_paths_restores_selected_output_cache_and_graph_data(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    cache_mgr = CacheManager(str(output_dir / "analysis_cache"))
    cache_mgr.save_results(
        {
            "persons": ["张三"],
            "companies": [],
            "profiles": {"张三": {"transactionCount": 1, "totalIncome": 1000}},
            "suspicions": {},
            "analysisResults": {
                "aggregation": {
                    "summary": {"极高风险实体数": 0, "高风险实体数": 0},
                    "rankedEntities": [],
                },
                "relatedParty": {
                    "summary": {"关系簇数": 0},
                    "third_party_relays": [],
                    "discovered_nodes": [],
                    "relationship_clusters": [],
                    "fund_loops": [],
                },
                "penetration": {"summary": {}, "fund_cycles": []},
            },
            "graphData": {"nodes": [{"id": "张三"}], "edges": []},
        }
    )

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_config = dict(api_server._current_config)

    try:
        api_server.analysis_state.reset()
        api_server._current_config.clear()

        response = asyncio.run(
            api_server.sync_active_paths(
                api_server.ActivePathsRequest(
                    inputDirectory=str(input_dir),
                    outputDirectory=str(output_dir),
                )
            )
        )

        assert response["success"] is True
        assert response["data"]["cacheRestored"] is True
        assert response["data"]["status"] == "completed"
        assert api_server.analysis_state.status == "completed"
        assert api_server.analysis_state.results["persons"] == ["张三"]

        graph_response = asyncio.run(api_server.get_graph_data())

        assert graph_response["message"] == "success"
        assert graph_response["data"]["stats"]["nodeCount"] == 1
        assert graph_response["data"]["stats"]["corePersonCount"] == 1
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)


def test_sync_active_paths_resets_stale_completed_state_when_output_has_no_cache(tmp_path):
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_config = dict(api_server._current_config)

    old_output_dir = tmp_path / "old_output"
    new_output_dir = tmp_path / "new_output"
    old_output_dir.mkdir()
    new_output_dir.mkdir()

    try:
        api_server.analysis_state.status = "completed"
        api_server.analysis_state.progress = 100
        api_server.analysis_state.phase = "旧缓存仍在"
        api_server.analysis_state.end_time = datetime.now()
        api_server.analysis_state.results = {
            "persons": ["旧数据"],
            "companies": [],
            "analysisResults": {},
            "graphData": {},
        }
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(old_output_dir)

        response = asyncio.run(
            api_server.sync_active_paths(
                api_server.ActivePathsRequest(outputDirectory=str(new_output_dir))
            )
        )

        assert response["success"] is True
        assert response["data"]["cacheRestored"] is False
        assert response["data"]["status"] == "idle"
        assert api_server.analysis_state.status == "idle"
        assert api_server.analysis_state.results is None
        assert api_server._get_active_output_dir() == str(new_output_dir)
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)


def test_get_report_subjects_preserves_contract_after_cache_restore(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    cache_mgr = CacheManager(str(output_dir / "analysis_cache"))
    cache_mgr.save_results(
        {
            "persons": ["张三"],
            "companies": ["测试科技有限公司"],
            "profiles": {
                "张三": {
                    "transaction_count": 12,
                    "total_income": 88000,
                    "salary_ratio": 0.35,
                },
                "测试科技有限公司": {
                    "transaction_count": 5,
                    "total_income": 280000,
                },
            },
            "suspicions": {},
            "analysisResults": {},
            "graphData": {"nodes": [], "edges": []},
        }
    )

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_config = dict(api_server._current_config)

    try:
        api_server.analysis_state.reset()
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)

        payload = asyncio.run(api_server.get_report_subjects())
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    subject_lookup = {item["name"]: item for item in payload["subjects"]}
    assert payload["success"] is True
    assert subject_lookup["张三"]["type"] == "person"
    assert subject_lookup["张三"]["transactionCount"] == 12
    assert subject_lookup["张三"]["totalIncome"] == 88000
    assert subject_lookup["张三"]["salaryRatio"] == 0.35
    assert subject_lookup["测试科技有限公司"]["type"] == "company"
    assert subject_lookup["测试科技有限公司"]["transactionCount"] == 5
    assert subject_lookup["测试科技有限公司"]["totalIncome"] == 280000
    assert "salaryRatio" not in subject_lookup["测试科技有限公司"]


def test_invalidate_named_cache_resets_memory_state_and_drops_stale_partial_external_data(
    tmp_path,
):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    cache_mgr = CacheManager(str(output_dir / "analysis_cache"))
    cache_mgr.save_results(
        {
            "persons": ["张三"],
            "companies": ["测试科技有限公司"],
            "profiles": {"张三": {"transaction_count": 1, "total_income": 1000}},
            "suspicions": {},
            "analysisResults": {},
            "graphData": {"nodes": [], "edges": []},
            "externalData": {
                "p0": {},
                "p1": {
                    "vehicle_data": {
                        "310101199001010011": [{"plate_number": "沪A12345"}]
                    }
                },
                "p2": {},
                "wallet": {},
            },
        }
    )

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_config = dict(api_server._current_config)
    previous_cache_manager = api_server._cache_manager

    try:
        api_server.analysis_state.status = "completed"
        api_server.analysis_state.progress = 100
        api_server.analysis_state.phase = "已完成"
        api_server.analysis_state.results = {
            "persons": ["张三"],
            "companies": ["测试科技有限公司"],
            "profiles": {"张三": {"transaction_count": 1, "total_income": 1000}},
            "suspicions": {},
            "analysisResults": {},
            "graphData": {"nodes": [], "edges": []},
            "externalData": {
                "p1": {
                    "vehicle_data": {
                        "310101199001010011": [{"plate_number": "沪A12345"}]
                    }
                }
            },
        }
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        api_server._cache_manager = cache_mgr

        response = asyncio.run(api_server.invalidate_cache("external_p1"))

        assert response["success"] is True
        assert api_server.analysis_state.status == "idle"
        assert api_server.analysis_state.results is None
        assert api_server._cache_manager is None
        assert not (output_dir / "analysis_cache" / "external_p1.json").exists()

        restored = api_server._sync_analysis_state_with_active_output(force_reload=True)
        assert restored is True
        assert api_server.analysis_state.status == "completed"
        assert api_server.analysis_state.results["externalData"]["p1"] == {}
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        api_server._cache_manager = previous_cache_manager


def test_get_results_normalizes_cached_direct_transfer_descriptions():
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
    }

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.progress = 100
    api_server.analysis_state.phase = "已从缓存恢复"
    api_server.analysis_state.results = {
        "persons": ["赵峰"],
        "companies": ["贵州锐晶科技有限公司"],
        "suspicions": {
            "directTransfers": [
                {
                    "from": "贵州锐晶科技有限公司",
                    "to": "赵峰",
                    "amount": 7000.0,
                    "date": "2024-05-23T10:04:14",
                    "description": "CPSP051045 US2390 156342405230341291480",
                    "direction": "receive",
                    "bank": "中国银行",
                    "evidenceRefs": {"channel": "其他"},
                }
            ]
        },
        "analysisResults": {},
        "graphData": {"nodes": [], "edges": []},
    }

    try:
        response = asyncio.run(api_server.get_results())
        payload = json.loads(response.body.decode("utf-8"))
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]

    record = payload["data"]["suspicions"]["directTransfers"][0]
    assert record["description"] == "中行系统跨行转账附言（原始流水码已省略）"
    assert record["evidenceRefs"]["rawDescription"].startswith("CPSP051045")


def test_get_results_deduplicates_cached_direct_transfer_mirror_rows():
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
    }

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.progress = 100
    api_server.analysis_state.phase = "已从缓存恢复"
    api_server.analysis_state.results = {
        "persons": ["赵峰"],
        "companies": ["贵州锐晶科技有限公司"],
        "suspicions": {
            "directTransfers": [
                {
                    "from": "贵州锐晶科技有限公司",
                    "to": "赵峰",
                    "amount": 7000.0,
                    "date": "2024-05-23T10:04:14",
                    "description": "CPSP051045 US2390 156342405230341291480",
                    "direction": "receive",
                    "bank": "中国银行",
                    "sourceFile": "赵峰_中国银行交易流水.xlsx",
                    "sourceRowIndex": 11,
                    "transactionId": "P-7000",
                    "evidenceRefs": {"channel": "其他"},
                },
                {
                    "from": "贵州锐晶科技有限公司",
                    "to": "赵峰",
                    "amount": 7000.0,
                    "date": "2024-05-23T10:04:14",
                    "description": "CPSP051045 US2390 156342405230341291480 US",
                    "direction": "receive",
                    "bank": "中国银行",
                    "sourceFile": "贵州锐晶科技有限公司_中国银行交易流水.xlsx",
                    "sourceRowIndex": 91,
                    "transactionId": "C-7000",
                    "evidenceRefs": {"channel": "其他"},
                },
            ]
        },
        "analysisResults": {},
        "graphData": {"nodes": [], "edges": []},
    }

    try:
        response = asyncio.run(api_server.get_results())
        payload = json.loads(response.body.decode("utf-8"))
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]

    records = payload["data"]["suspicions"]["directTransfers"]
    assert len(records) == 1
    assert records[0]["sourceFile"] == "赵峰_中国银行交易流水.xlsx"
    assert records[0]["description"] == "中行系统跨行转账附言（原始流水码已省略）"


def test_serialize_suspicions_normalizes_standard_plugin_suspicion_fields():
    serialized = api_server.serialize_suspicions(
        {
            "timeSeriesAlerts": [
                {
                    "suspicion_id": "TA001",
                    "suspicion_type": "异常时间",
                    "severity": "中",
                    "description": "节假日大额交易",
                    "related_transactions": ["TX_1"],
                    "amount": 120000.0,
                    "detection_date": "2026-03-20",
                    "entity_name": "张三",
                    "confidence": 0.63,
                    "evidence": "节日: 春节, 时段: 节中",
                    "status": "待核实",
                }
            ],
            "round_amount": [
                {
                    "suspicion_id": "RA001",
                    "suspicion_type": "整数金额",
                    "severity": "低",
                    "description": "整数金额偏好",
                    "related_transactions": ["TX_2"],
                    "amount": 50000.0,
                    "detection_date": "2026-03-20",
                    "entity_name": "张三",
                    "confidence": 0.5,
                    "evidence": "整数金额交易",
                    "status": "待核实",
                }
            ],
            "fixed_frequency": {
                "张三": [
                    {
                        "suspicion_id": "FF001",
                        "suspicion_type": "频繁转账",
                        "severity": "中",
                        "description": "固定频率支出",
                        "related_transactions": ["TX_3"],
                        "amount": 150000.0,
                        "detection_date": "2026-03-20",
                        "entity_name": "张三",
                        "confidence": 0.7,
                        "evidence": "周期类型: 每月",
                        "status": "待核实",
                    }
                ]
            },
        }
    )

    time_alert = serialized["timeSeriesAlerts"][0]
    round_amount = serialized["roundAmount"][0]
    fixed_frequency = serialized["fixedFrequency"]["张三"][0]

    for record in (time_alert, round_amount, fixed_frequency):
        assert "suspicionId" in record
        assert "suspicionType" in record
        assert "relatedTransactions" in record
        assert "detectionDate" in record
        assert "entityName" in record
        assert "suspicion_id" not in record
        assert "suspicion_type" not in record
        assert "related_transactions" not in record
        assert "detection_date" not in record
        assert "entity_name" not in record


def test_get_results_keeps_camel_case_for_standard_plugin_suspicions():
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
    }

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.progress = 100
    api_server.analysis_state.phase = "已完成"
    api_server.analysis_state.results = {
        "persons": ["张三"],
        "companies": ["某公司"],
        "suspicions": api_server.serialize_suspicions(
            {
                "timeSeriesAlerts": [
                    {
                        "suspicion_id": "TA001",
                        "suspicion_type": "异常时间",
                        "severity": "中",
                        "description": "节假日大额交易",
                        "related_transactions": ["TX_1"],
                        "amount": 120000.0,
                        "detection_date": "2026-03-20",
                        "entity_name": "张三",
                        "confidence": 0.63,
                        "evidence": "节日: 春节, 时段: 节中",
                        "status": "待核实",
                    }
                ],
                "round_amount": [
                    {
                        "suspicion_id": "RA001",
                        "suspicion_type": "整数金额",
                        "severity": "低",
                        "description": "整数金额偏好",
                        "related_transactions": ["TX_2"],
                        "amount": 50000.0,
                        "detection_date": "2026-03-20",
                        "entity_name": "张三",
                        "confidence": 0.5,
                        "evidence": "整数金额交易",
                        "status": "待核实",
                    }
                ],
                "fixed_frequency": {
                    "张三": [
                        {
                            "suspicion_id": "FF001",
                            "suspicion_type": "频繁转账",
                            "severity": "中",
                            "description": "固定频率支出",
                            "related_transactions": ["TX_3"],
                            "amount": 150000.0,
                            "detection_date": "2026-03-20",
                            "entity_name": "张三",
                            "confidence": 0.7,
                            "evidence": "周期类型: 每月",
                            "status": "待核实",
                        }
                    ]
                },
            }
        ),
        "analysisResults": {},
        "graphData": {"nodes": [], "edges": []},
    }

    try:
        response = asyncio.run(api_server.get_results())
        payload = json.loads(response.body.decode("utf-8"))["data"]["suspicions"]
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]

    time_alert = payload["timeSeriesAlerts"][0]
    round_amount = payload["roundAmount"][0]
    fixed_frequency = payload["fixedFrequency"]["张三"][0]

    for record in (time_alert, round_amount, fixed_frequency):
        assert "suspicionId" in record
        assert "suspicionType" in record
        assert "relatedTransactions" in record
        assert "detectionDate" in record
        assert "entityName" in record
        assert "suspicion_id" not in record
        assert "suspicion_type" not in record
        assert "related_transactions" not in record
        assert "detection_date" not in record
        assert "entity_name" not in record


def test_get_results_includes_report_package_when_semantic_artifact_exists(tmp_path):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results" / "qa"
    results_dir.mkdir(parents=True)
    (results_dir / "report_package.json").write_text(
        json.dumps(
            {
                "main_report_view": {
                    "summary_narrative": "统一语义层共归集2项重点问题。",
                    "issue_count": 2,
                },
                "priority_board": [
                    {
                        "entity_name": "张三",
                        "priority_score": 88.5,
                        "risk_level": "high",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
    }
    previous_config = dict(api_server._current_config)
    previous_sync = api_server._sync_analysis_state_with_active_output

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.progress = 100
    api_server.analysis_state.phase = "已从缓存恢复"
    api_server.analysis_state.results = {
        "persons": ["张三"],
        "companies": [],
        "suspicions": {"directTransfers": []},
        "analysisResults": {},
        "graphData": {"nodes": [], "edges": []},
    }

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        api_server._sync_analysis_state_with_active_output = lambda force_reload=False: True

        response = asyncio.run(api_server.get_results())
        payload = json.loads(response.body.decode("utf-8"))
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server._sync_analysis_state_with_active_output = previous_sync
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    assert payload["data"]["reportPackage"]["main_report_view"]["issue_count"] == 2
    assert payload["data"]["reportPackage"]["priority_board"][0]["entity_name"] == "张三"


def test_get_results_preserves_report_package_snake_case_contract(tmp_path):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results" / "qa"
    results_dir.mkdir(parents=True)
    (results_dir / "report_package.json").write_text(
        json.dumps(
            {
                "main_report_view": {
                    "summary_narrative": "统一语义层共归集3项重点问题。",
                    "issue_count": 3,
                },
                "priority_board": [
                    {
                        "entity_name": "张三",
                        "priority_score": 88.5,
                        "risk_level": "high",
                    }
                ],
                "person_dossiers": [
                    {
                        "entity_name": "张三",
                        "financial_gap_explanation": {
                            "summary": "收支差异已解释。",
                            "income_offset_rows": [],
                            "expense_offset_rows": [],
                        },
                    }
                ],
                "company_dossiers": [
                    {
                        "entity_name": "测试科技有限公司",
                        "company_business_explanation": {
                            "summary": "公司流水存在稳定经营轨迹。",
                            "focus_issue_headlines": ["大额交易核查"],
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
    }
    previous_config = dict(api_server._current_config)
    previous_sync = api_server._sync_analysis_state_with_active_output

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.progress = 100
    api_server.analysis_state.phase = "已从缓存恢复"
    api_server.analysis_state.results = {
        "persons": ["张三"],
        "companies": ["测试科技有限公司"],
        "suspicions": {"directTransfers": []},
        "analysisResults": {},
        "graphData": {"nodes": [], "edges": []},
    }

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        api_server._sync_analysis_state_with_active_output = lambda force_reload=False: True

        response = asyncio.run(api_server.get_results())
        payload = json.loads(response.body.decode("utf-8"))["data"]
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server._sync_analysis_state_with_active_output = previous_sync
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    assert "analysisResults" in payload
    assert "analysis_results" not in payload

    report_package = payload["reportPackage"]
    assert "main_report_view" in report_package
    assert "priority_board" in report_package
    assert "person_dossiers" in report_package
    assert "company_dossiers" in report_package
    assert "mainReportView" not in report_package
    assert "priorityBoard" not in report_package
    assert "personDossiers" not in report_package
    assert "companyDossiers" not in report_package

    priority_item = report_package["priority_board"][0]
    person_dossier = report_package["person_dossiers"][0]
    company_dossier = report_package["company_dossiers"][0]

    assert priority_item["entity_name"] == "张三"
    assert "entityName" not in priority_item
    assert "financial_gap_explanation" in person_dossier
    assert "financialGapExplanation" not in person_dossier
    assert "company_business_explanation" in company_dossier
    assert "companyBusinessExplanation" not in company_dossier
    assert company_dossier["company_business_explanation"]["focus_issue_headlines"] == [
        "大额交易核查"
    ]


def test_get_results_refreshes_report_package_when_semantic_artifact_missing(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    results_dir.mkdir(parents=True)
    refresh_calls = []

    def fake_refresh(active_output_dir):
        refresh_calls.append(active_output_dir)
        qa_dir = output_dir / "analysis_results" / "qa"
        qa_dir.mkdir(parents=True, exist_ok=True)
        (qa_dir / "report_package.json").write_text(
            json.dumps(
                {
                    "main_report_view": {
                        "summary_narrative": "自动补建语义包成功。",
                        "issue_count": 1,
                    },
                    "priority_board": [
                        {
                            "entity_name": "李四",
                            "priority_score": 76.0,
                            "risk_level": "medium",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"report_package_path": str(qa_dir / "report_package.json")}

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
    }
    previous_config = dict(api_server._current_config)

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.progress = 100
    api_server.analysis_state.phase = "已从缓存恢复"
    api_server.analysis_state.results = {
        "persons": ["李四"],
        "companies": [],
        "suspicions": {"directTransfers": []},
        "analysisResults": {},
        "graphData": {"nodes": [], "edges": []},
    }

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        monkeypatch.setattr(
            api_server,
            "_sync_analysis_state_with_active_output",
            lambda force_reload=False: True,
        )
        monkeypatch.setattr(
            api_server,
            "_refresh_report_semantic_artifacts",
            fake_refresh,
        )

        response = asyncio.run(api_server.get_results())
        payload = json.loads(response.body.decode("utf-8"))
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    assert refresh_calls == [str(output_dir)]
    assert payload["data"]["reportPackage"]["main_report_view"]["issue_count"] == 1
    assert payload["data"]["reportPackage"]["priority_board"][0]["entity_name"] == "李四"


def test_get_dashboard_results_omits_heavy_runtime_fields(tmp_path):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results" / "qa"
    results_dir.mkdir(parents=True)
    (results_dir / "report_package.json").write_text(
        json.dumps(
            {
                "main_report_view": {
                    "summary_narrative": "统一语义层共归集1项重点问题。",
                    "issue_count": 1,
                },
                "priority_board": [
                    {
                        "entity_name": "张三",
                        "priority_score": 90.0,
                        "risk_level": "high",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
    }
    previous_config = dict(api_server._current_config)
    previous_sync = api_server._sync_analysis_state_with_active_output

    api_server.analysis_state.status = "completed"
    api_server.analysis_state.progress = 100
    api_server.analysis_state.phase = "已从缓存恢复"
    api_server.analysis_state.results = {
        "persons": ["张三"],
        "companies": ["测试科技有限公司"],
        "profiles": {"张三": {"display_name": "张三", "vehicles": []}},
        "suspicions": {"directTransfers": []},
        "analysisResults": {"aggregation": {"summary": {"高风险实体数": 1}}},
        "graphData": {"nodes": [{"id": "张三"}], "edges": []},
        "walletData": {"alerts": []},
        "externalData": {"p1": {"vehicle_data": {"张三": [{"plate_number": "沪A12345"}]}}},
        "runtimeLogPaths": {"run": str(output_dir / "analysis_logs" / "latest.log")},
        "_profiles_raw": {"张三": {"raw": True}},
    }

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        api_server._sync_analysis_state_with_active_output = lambda force_reload=False: True

        response = asyncio.run(api_server.get_dashboard_results())
        payload = json.loads(response.body.decode("utf-8"))["data"]
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server._sync_analysis_state_with_active_output = previous_sync
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    assert payload["persons"] == ["张三"]
    assert payload["companies"] == ["测试科技有限公司"]
    assert payload["walletData"]["alerts"] == []
    assert payload["analysisResults"]["aggregation"]["summary"]["高风险实体数"] == 1
    assert payload["reportPackage"]["main_report_view"]["issue_count"] == 1
    assert payload["reportPackage"]["priority_board"][0]["entity_name"] == "张三"
    assert "graphData" not in payload
    assert "externalData" not in payload
    assert "runtimeLogPaths" not in payload
    assert "_profiles_raw" not in payload


def test_load_report_package_for_manifest_refreshes_stale_qa_guard_version(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    qa_dir = results_dir / "qa"
    qa_dir.mkdir(parents=True)
    (results_dir / "核查结果分析报告.txt").write_text("main", encoding="utf-8")

    stale_package = {
        "meta": {"generated_at": "2026-03-17T22:52:01"},
        "qa_checks": {
            "summary": {"pass": 1, "warn": 0, "fail": 0, "total": 1},
            "checks": [],
            "meta": {
                "qa_guard_version": "2026-03-17.0",
                "generated_at": "2026-03-17T22:52:01",
            },
        },
        "artifact_meta": {
            "package_generated_at": "2026-03-17T22:52:01",
            "source_report_generated_at": "2026-03-17T22:52:01",
            "qa_guard_version": "2026-03-17.0",
        },
    }
    (qa_dir / "report_package.json").write_text(
        json.dumps(stale_package, ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.json").write_text(
        json.dumps(stale_package["qa_checks"], ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.txt").write_text("stale", encoding="utf-8")

    refresh_calls = []

    def fake_refresh(active_output_dir):
        refresh_calls.append(active_output_dir)
        refreshed_package = {
            "meta": {"generated_at": "2026-03-17T22:52:01"},
            "qa_checks": {
                "summary": {"pass": 2, "warn": 0, "fail": 0, "total": 2},
                "checks": [],
                "meta": {
                    "qa_guard_version": REPORT_QA_GUARD_VERSION,
                    "generated_at": "2026-03-18T22:10:00",
                },
            },
            "artifact_meta": {
                "package_generated_at": "2026-03-18T22:10:00",
                "source_report_generated_at": "2026-03-17T22:52:01",
                "qa_guard_version": REPORT_QA_GUARD_VERSION,
            },
        }
        (qa_dir / "report_package.json").write_text(
            json.dumps(refreshed_package, ensure_ascii=False),
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.json").write_text(
            json.dumps(refreshed_package["qa_checks"], ensure_ascii=False),
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.txt").write_text(
            "fresh",
            encoding="utf-8",
        )
        return {"report_package_path": str(qa_dir / "report_package.json")}

    monkeypatch.setattr(
        api_server,
        "_refresh_report_semantic_artifacts",
        fake_refresh,
    )

    payload = api_server._load_report_package_for_manifest(str(results_dir))

    assert refresh_calls == [str(output_dir)]
    assert payload["qa_checks"]["meta"]["qa_guard_version"] == REPORT_QA_GUARD_VERSION
    assert payload["artifact_meta"]["qa_guard_version"] == REPORT_QA_GUARD_VERSION


def test_load_report_package_for_manifest_refreshes_when_report_logic_is_newer(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    qa_dir = results_dir / "qa"
    qa_dir.mkdir(parents=True)
    (results_dir / "核查结果分析报告.txt").write_text("main", encoding="utf-8")

    package_generated_at = "2026-03-18T10:00:00"
    package = {
        "meta": {"generated_at": package_generated_at},
        "qa_checks": {
            "summary": {"pass": 1, "warn": 0, "fail": 0, "total": 1},
            "checks": [],
            "meta": {
                "qa_guard_version": REPORT_QA_GUARD_VERSION,
                "generated_at": package_generated_at,
            },
        },
        "artifact_meta": {
            "package_generated_at": package_generated_at,
            "source_report_generated_at": package_generated_at,
            "qa_guard_version": REPORT_QA_GUARD_VERSION,
        },
    }
    (qa_dir / "report_package.json").write_text(
        json.dumps(package, ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.json").write_text(
        json.dumps(package["qa_checks"], ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.txt").write_text("fresh", encoding="utf-8")

    refresh_calls = []

    def fake_refresh(active_output_dir):
        refresh_calls.append(active_output_dir)
        refreshed_package = {
            **package,
            "artifact_meta": {
                **package["artifact_meta"],
                "package_generated_at": "2026-03-19T08:40:00",
            },
        }
        (qa_dir / "report_package.json").write_text(
            json.dumps(refreshed_package, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"report_package_path": str(qa_dir / "report_package.json")}

    monkeypatch.setattr(
        api_server,
        "_get_latest_semantic_source_timestamp",
        lambda _results_dir: None,
    )
    monkeypatch.setattr(
        api_server,
        "_get_latest_report_logic_timestamp",
        lambda: datetime.fromisoformat("2026-03-19T08:30:00"),
    )
    monkeypatch.setattr(
        api_server,
        "_refresh_report_semantic_artifacts",
        fake_refresh,
    )

    payload = api_server._load_report_package_for_manifest(str(results_dir))

    assert refresh_calls == [str(output_dir)]
    assert payload["artifact_meta"]["package_generated_at"] == "2026-03-19T08:40:00"


def test_load_report_package_for_manifest_refreshes_when_dossier_explanations_missing(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    qa_dir = results_dir / "qa"
    qa_dir.mkdir(parents=True)
    (results_dir / "核查结果分析报告.txt").write_text("main", encoding="utf-8")

    package_generated_at = "2026-03-19T09:00:00"
    stale_package = {
        "meta": {"generated_at": package_generated_at},
        "person_dossiers": [{"entity_name": "张三", "financial_gap_explanation": None}],
        "family_dossiers": [{"family_name": "张三家庭"}],
        "company_dossiers": [
            {
                "entity_name": "测试科技有限公司",
                "company_business_explanation": None,
            }
        ],
        "qa_checks": {
            "summary": {"pass": 1, "warn": 0, "fail": 0, "total": 1},
            "checks": [],
            "meta": {
                "qa_guard_version": REPORT_QA_GUARD_VERSION,
                "generated_at": package_generated_at,
            },
        },
        "artifact_meta": {
            "package_generated_at": package_generated_at,
            "source_report_generated_at": package_generated_at,
            "qa_guard_version": REPORT_QA_GUARD_VERSION,
        },
    }
    (qa_dir / "report_package.json").write_text(
        json.dumps(stale_package, ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.json").write_text(
        json.dumps(stale_package["qa_checks"], ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.txt").write_text("stale", encoding="utf-8")

    refresh_calls = []

    def fake_refresh(active_output_dir):
        refresh_calls.append(active_output_dir)
        refreshed_package = {
            **stale_package,
            "person_dossiers": [
                {
                    "entity_name": "张三",
                    "financial_gap_explanation": {
                        "summary": "原始口径与真实口径差异已解释。",
                        "income_gap": 0,
                        "expense_gap": 0,
                        "income_offset_rows": [],
                        "expense_offset_rows": [],
                    },
                }
            ],
            "family_dossiers": [
                {
                    "family_name": "张三家庭",
                    "family_financial_explanation": {
                        "summary": "当前已识别成员1名，成员流水覆盖完整。",
                        "member_count": 1,
                        "pending_member_count": 0,
                        "pending_members": [],
                        "focus_clues": [],
                    },
                }
            ],
            "company_dossiers": [
                {
                    "entity_name": "测试科技有限公司",
                    "company_business_explanation": {
                        "summary": "累计流入10.00万、流出8.00万，共2笔交易。",
                        "behavioral_flags": [],
                        "focus_issue_headlines": [],
                    },
                }
            ],
        }
        (qa_dir / "report_package.json").write_text(
            json.dumps(refreshed_package, ensure_ascii=False),
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.json").write_text(
            json.dumps(refreshed_package["qa_checks"], ensure_ascii=False),
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.txt").write_text(
            "fresh",
            encoding="utf-8",
        )
        return {"report_package_path": str(qa_dir / "report_package.json")}

    monkeypatch.setattr(
        api_server,
        "_get_latest_semantic_source_timestamp",
        lambda _results_dir: None,
    )
    monkeypatch.setattr(
        api_server,
        "_get_latest_report_logic_timestamp",
        lambda: None,
    )
    monkeypatch.setattr(
        api_server,
        "_refresh_report_semantic_artifacts",
        fake_refresh,
    )

    payload = api_server._load_report_package_for_manifest(str(results_dir))

    assert refresh_calls == [str(output_dir)]
    assert payload["family_dossiers"][0]["family_financial_explanation"]["member_count"] == 1
    assert (
        payload["company_dossiers"][0]["company_business_explanation"]["summary"]
        == "累计流入10.00万、流出8.00万，共2笔交易。"
    )


def test_preview_report_file_supports_head_requests_for_html(tmp_path):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    results_dir.mkdir(parents=True)
    report_path = results_dir / "初查报告.html"
    report_path.write_text("<html><body>preview</body></html>", encoding="utf-8")

    previous_config = dict(api_server._current_config)
    request = Request(
        {
            "type": "http",
            "method": "HEAD",
            "path": "/api/reports/preview/初查报告.html",
            "headers": [],
        }
    )

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)

        response = asyncio.run(
            api_server.preview_report_file("初查报告.html", request)
        )

        assert response.status_code == 200
        assert response.body == b""
        assert response.headers["content-type"].startswith("text/html")
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)


def test_get_report_manifest_groups_files_by_semantic_category(tmp_path):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    qa_dir = results_dir / "qa"
    appendix_dir = results_dir / "专项报告"
    dossier_dir = results_dir / "对象卷宗"

    qa_dir.mkdir(parents=True)
    appendix_dir.mkdir(parents=True)
    dossier_dir.mkdir(parents=True)

    (results_dir / "核查结果分析报告.txt").write_text("main", encoding="utf-8")
    (results_dir / "初查报告.html").write_text("<html></html>", encoding="utf-8")
    (results_dir / "资金核查底稿.xlsx").write_text("excel", encoding="utf-8")
    (results_dir / "分析执行日志.txt").write_text("log", encoding="utf-8")
    (qa_dir / "report_package.json").write_text('{"ok":true}', encoding="utf-8")
    (qa_dir / "report_consistency_check.txt").write_text("qa", encoding="utf-8")
    (appendix_dir / "资金穿透分析报告.txt").write_text("appendix", encoding="utf-8")
    (dossier_dir / "张三对象卷宗.txt").write_text("dossier", encoding="utf-8")

    previous_config = dict(api_server._current_config)

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)

        payload = asyncio.run(api_server.get_report_manifest())
        groups = {item["key"]: item for item in payload["groups"]}

        assert payload["success"] is True
        assert payload["totals"]["reportCount"] == 8
        assert "primary_reports" in groups
        assert "appendices" in groups
        assert "dossiers" in groups
        assert "qa_artifacts" in groups
        assert "workpapers" in groups
        assert "technical_files" in groups
        assert any(
            item["name"] == "qa/report_package.json"
            for item in groups["qa_artifacts"]["items"]
        )
        assert any(
            item["name"] == "专项报告/资金穿透分析报告.txt"
            for item in groups["appendices"]["items"]
        )
        assert any(
            item["name"] == "对象卷宗/张三对象卷宗.txt"
            for item in groups["dossiers"]["items"]
        )
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)


def test_get_report_manifest_exposes_semantic_navigation_metadata(tmp_path):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    qa_dir = results_dir / "qa"
    appendix_dir = results_dir / "专项报告"
    dossier_dir = results_dir / "对象卷宗"

    qa_dir.mkdir(parents=True)
    appendix_dir.mkdir(parents=True)
    dossier_dir.mkdir(parents=True)

    semantic_package = {
        "main_report_view": {
            "summary_narrative": "统一语义层共归集3项重点问题；其中高风险1项；优先核查对象为张三、测试科技有限公司。",
            "issue_count": 3,
            "high_risk_issue_count": 1,
            "top_priority_entities": [
                {
                    "entity_name": "张三",
                    "top_reasons": ["大额往来异常", "与测试科技有限公司存在直接资金往来"],
                },
                {
                    "entity_name": "测试科技有限公司",
                    "top_reasons": ["公司卷宗已形成", "存在通道节点特征"],
                },
            ],
        },
        "appendix_views": {
            "appendix_index": {
                "items": [
                    {
                        "appendix_key": "appendix_a_assets_income",
                        "title": "附录A 资产与收入匹配",
                        "summary_line": "覆盖2名人员、1个家庭，收支倒挂1人。",
                        "item_count": 3,
                    },
                    {
                        "appendix_key": "appendix_c_network_penetration",
                        "title": "附录C 关系网络与资金穿透",
                        "summary_line": "提炼2个网络重点对象，关联穿透问题4项。",
                        "item_count": 4,
                    },
                    {
                        "appendix_key": "appendix_e_wallet_supplement",
                        "title": "附录E 电子钱包补证",
                        "summary_line": "电子钱包状态已接入，覆盖1个主体，摘要交易15笔。",
                        "item_count": 2,
                    },
                ]
            }
        },
        "family_dossiers": [{"family_name": "张三家庭"}],
        "person_dossiers": [{"entity_name": "张三"}],
        "company_dossiers": [
            {
                "entity_name": "测试科技有限公司",
                "role_tags": ["通道节点", "桥接节点"],
                "risk_overview": {"risk_level": "high"},
            }
        ],
        "qa_checks": {
            "summary": {"pass": 3, "warn": 1, "fail": 1, "total": 5},
            "checks": [
                {
                    "check_id": "high_risk_requires_traceable_evidence_refs",
                    "status": "fail",
                    "message": "High-risk issue is missing traceable evidence refs.",
                },
                {
                    "check_id": "company_dossiers_enriched",
                    "status": "warn",
                    "message": "Some company dossiers were materialized but still lack role/risk enrichment.",
                },
            ],
        },
    }

    (results_dir / "核查结果分析报告.txt").write_text("main", encoding="utf-8")
    (results_dir / "初查报告.html").write_text("<html></html>", encoding="utf-8")
    (results_dir / "电子钱包补充分析报告.txt").write_text("wallet", encoding="utf-8")
    (results_dir / "电子钱包重点核查清单.txt").write_text("wallet list", encoding="utf-8")
    (qa_dir / "report_package.json").write_text(
        json.dumps(semantic_package, ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.txt").write_text("qa", encoding="utf-8")
    (appendix_dir / "资金穿透分析报告.txt").write_text("appendix", encoding="utf-8")
    (dossier_dir / "张三对象卷宗.txt").write_text("dossier", encoding="utf-8")

    previous_config = dict(api_server._current_config)

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)

        payload = asyncio.run(api_server.get_report_manifest())
        groups = {item["key"]: item for item in payload["groups"]}
        report_lookup = {item["name"]: item for item in payload["reports"]}

        assert (
            payload["semanticOverview"]["mainReport"]["issueCount"] == 3
        )
        assert (
            groups["primary_reports"]["semanticHeadline"]
            == "统一语义层共归集3项重点问题；其中高风险1项；优先核查对象为张三、测试科技有限公司。"
        )
        assert "高风险 1 项" in groups["primary_reports"]["semanticBadges"]
        assert (
            groups["appendices"]["semanticHighlights"][0]["title"]
            == "附录A 资产与收入匹配"
        )
        assert (
            groups["qa_artifacts"]["semanticHeadline"]
            == "QA 检查存在 1 项阻断问题，当前仍需收口。"
        )
        assert (
            payload["semanticOverview"]["qa"]["highlights"][0]["title"]
            == "高风险问题证据可追溯"
        )
        assert (
            payload["semanticOverview"]["qa"]["highlights"][0]["summary"]
            == "仍有高风险问题缺少可回溯证据索引，暂不宜直接用于正式定性。"
        )
        assert (
            payload["semanticOverview"]["qa"]["highlights"][1]["title"]
            == "公司卷宗摘要信息完整"
        )
        assert (
            payload["semanticOverview"]["qa"]["highlights"][1]["summary"]
            == "公司卷宗已生成，但仍有摘要或风险概览待补齐。"
        )
        assert (
            groups["dossiers"]["semanticHighlights"][0]["title"] == "桥接节点"
            or groups["dossiers"]["semanticHighlights"][0]["title"] == "通道节点"
        )
        assert report_lookup["初查报告.html"]["semanticTitle"] == "正式主报告入口"
        assert (
            report_lookup["qa/report_package.json"]["semanticTitle"] == "统一报告语义包"
        )
        assert (
            report_lookup["专项报告/资金穿透分析报告.txt"]["semanticTitle"]
            == "附录C 关系网络与资金穿透"
        )
        assert report_lookup["电子钱包补充分析报告.txt"]["groupKey"] == "appendices"
        assert report_lookup["电子钱包重点核查清单.txt"]["groupKey"] == "workpapers"
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)


def test_preview_report_file_supports_json_semantic_artifacts(tmp_path):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results" / "qa"
    results_dir.mkdir(parents=True)
    artifact_path = results_dir / "report_package.json"
    artifact_path.write_text('{"meta":{"case":"测试"}}', encoding="utf-8")

    previous_config = dict(api_server._current_config)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/reports/preview/qa/report_package.json",
            "headers": [],
        }
    )

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)

        response = asyncio.run(
            api_server.preview_report_file("qa/report_package.json", request)
        )

        assert response["success"] is True
        assert response["type"] == "text"
        assert '"case":"测试"' in response["content"]
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)


def test_preview_report_file_refreshes_stale_semantic_package_before_reading(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    qa_dir = results_dir / "qa"
    qa_dir.mkdir(parents=True)
    (results_dir / "核查结果分析报告.txt").write_text("main", encoding="utf-8")

    stale_package = {
        "meta": {"generated_at": "2026-03-18T10:00:00"},
        "qa_checks": {
            "summary": {"pass": 1, "warn": 0, "fail": 0, "total": 1},
            "checks": [],
            "meta": {
                "qa_guard_version": "2026-03-18.0",
                "generated_at": "2026-03-18T10:00:00",
            },
        },
        "artifact_meta": {
            "package_generated_at": "2026-03-18T10:00:00",
            "source_report_generated_at": "2026-03-18T10:00:00",
            "qa_guard_version": "2026-03-18.0",
        },
    }
    (qa_dir / "report_package.json").write_text(
        json.dumps(stale_package, ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.json").write_text(
        json.dumps(stale_package["qa_checks"], ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.txt").write_text("stale", encoding="utf-8")

    refresh_calls = []

    def fake_refresh(active_output_dir):
        refresh_calls.append(active_output_dir)
        refreshed_package = {
            **stale_package,
            "main_report_view": {
                "summary_narrative": "刷新后的正式语义包",
                "issue_count": 2,
            },
            "qa_checks": {
                **stale_package["qa_checks"],
                "meta": {
                    "qa_guard_version": REPORT_QA_GUARD_VERSION,
                    "generated_at": "2026-03-19T09:00:00",
                },
            },
            "artifact_meta": {
                "package_generated_at": "2026-03-19T09:00:00",
                "source_report_generated_at": "2026-03-18T10:00:00",
                "qa_guard_version": REPORT_QA_GUARD_VERSION,
            },
        }
        (qa_dir / "report_package.json").write_text(
            json.dumps(refreshed_package, ensure_ascii=False),
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.json").write_text(
            json.dumps(refreshed_package["qa_checks"], ensure_ascii=False),
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.txt").write_text(
            "fresh",
            encoding="utf-8",
        )
        return {"report_package_path": str(qa_dir / "report_package.json")}

    previous_config = dict(api_server._current_config)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/reports/preview/qa/report_package.json",
            "headers": [],
        }
    )

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        monkeypatch.setattr(
            api_server,
            "_refresh_report_semantic_artifacts",
            fake_refresh,
        )

        response = asyncio.run(
            api_server.preview_report_file("qa/report_package.json", request)
        )
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    assert refresh_calls == [str(output_dir)]
    assert response["success"] is True
    assert "刷新后的正式语义包" in response["content"]
    assert REPORT_QA_GUARD_VERSION in response["content"]


def test_get_report_files_refreshes_semantic_artifacts_before_collecting(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    qa_dir = results_dir / "qa"
    qa_dir.mkdir(parents=True)
    (results_dir / "核查结果分析报告.txt").write_text("main", encoding="utf-8")
    (qa_dir / "report_package.json").write_text(
        json.dumps(
            {
                "meta": {"generated_at": "2026-03-18T10:00:00"},
                "qa_checks": {
                    "summary": {"pass": 1, "warn": 0, "fail": 0, "total": 1},
                    "checks": [],
                    "meta": {
                        "qa_guard_version": REPORT_QA_GUARD_VERSION,
                        "generated_at": "2026-03-18T10:00:00",
                    },
                },
                "artifact_meta": {
                    "package_generated_at": "2026-03-18T10:00:00",
                    "source_report_generated_at": "2026-03-18T10:00:00",
                    "qa_guard_version": REPORT_QA_GUARD_VERSION,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    refresh_calls = []

    def fake_refresh(active_output_dir):
        refresh_calls.append(active_output_dir)
        (qa_dir / "report_consistency_check.json").write_text(
            json.dumps(
                {
                    "summary": {"pass": 2, "warn": 0, "fail": 0, "total": 2},
                    "checks": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.txt").write_text("fresh", encoding="utf-8")
        return {
            "report_package_path": str(qa_dir / "report_package.json"),
            "qa_check_path": str(qa_dir / "report_consistency_check.json"),
        }

    previous_config = dict(api_server._current_config)

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        monkeypatch.setattr(
            api_server,
            "_refresh_report_semantic_artifacts",
            fake_refresh,
        )

        payload = asyncio.run(api_server.get_report_files())
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    report_names = {item["name"] for item in payload["reports"]}
    assert payload["success"] is True
    assert refresh_calls == [str(output_dir)]
    assert "qa/report_package.json" in report_names
    assert "qa/report_consistency_check.json" in report_names
    assert "qa/report_consistency_check.txt" in report_names


def test_download_report_file_refreshes_stale_semantic_package_before_sending(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    qa_dir = results_dir / "qa"
    qa_dir.mkdir(parents=True)
    (results_dir / "核查结果分析报告.txt").write_text("main", encoding="utf-8")

    stale_package = {
        "meta": {"generated_at": "2026-03-18T10:00:00"},
        "qa_checks": {
            "summary": {"pass": 1, "warn": 0, "fail": 0, "total": 1},
            "checks": [],
            "meta": {
                "qa_guard_version": "2026-03-18.0",
                "generated_at": "2026-03-18T10:00:00",
            },
        },
        "artifact_meta": {
            "package_generated_at": "2026-03-18T10:00:00",
            "source_report_generated_at": "2026-03-18T10:00:00",
            "qa_guard_version": "2026-03-18.0",
        },
    }
    artifact_path = qa_dir / "report_package.json"
    artifact_path.write_text(
        json.dumps(stale_package, ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.json").write_text(
        json.dumps(stale_package["qa_checks"], ensure_ascii=False),
        encoding="utf-8",
    )
    (qa_dir / "report_consistency_check.txt").write_text("stale", encoding="utf-8")

    refresh_calls = []

    def fake_refresh(active_output_dir):
        refresh_calls.append(active_output_dir)
        refreshed_package = {
            **stale_package,
            "main_report_view": {
                "summary_narrative": "下载前已刷新",
                "issue_count": 1,
            },
            "qa_checks": {
                **stale_package["qa_checks"],
                "meta": {
                    "qa_guard_version": REPORT_QA_GUARD_VERSION,
                    "generated_at": "2026-03-19T09:30:00",
                },
            },
            "artifact_meta": {
                "package_generated_at": "2026-03-19T09:30:00",
                "source_report_generated_at": "2026-03-18T10:00:00",
                "qa_guard_version": REPORT_QA_GUARD_VERSION,
            },
        }
        artifact_path.write_text(
            json.dumps(refreshed_package, ensure_ascii=False),
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.json").write_text(
            json.dumps(refreshed_package["qa_checks"], ensure_ascii=False),
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.txt").write_text("fresh", encoding="utf-8")
        return {"report_package_path": str(artifact_path)}

    previous_config = dict(api_server._current_config)

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        monkeypatch.setattr(
            api_server,
            "_refresh_report_semantic_artifacts",
            fake_refresh,
        )

        response = asyncio.run(
            api_server.download_report_file("qa/report_package.json")
        )
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    assert refresh_calls == [str(output_dir)]
    assert response.path == str(artifact_path)
    assert response.filename == "report_package.json"
    assert "下载前已刷新" in artifact_path.read_text(encoding="utf-8")
    assert REPORT_QA_GUARD_VERSION in artifact_path.read_text(encoding="utf-8")


def test_get_reports_legacy_refreshes_semantic_artifacts_before_collecting(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    qa_dir = results_dir / "qa"
    qa_dir.mkdir(parents=True)
    (results_dir / "初查报告.html").write_text("<html></html>", encoding="utf-8")
    (qa_dir / "report_package.json").write_text(
        json.dumps(
            {
                "meta": {"generated_at": "2026-03-18T10:00:00"},
                "qa_checks": {
                    "summary": {"pass": 1, "warn": 0, "fail": 0, "total": 1},
                    "checks": [],
                    "meta": {
                        "qa_guard_version": REPORT_QA_GUARD_VERSION,
                        "generated_at": "2026-03-18T10:00:00",
                    },
                },
                "artifact_meta": {
                    "package_generated_at": "2026-03-18T10:00:00",
                    "source_report_generated_at": "2026-03-18T10:00:00",
                    "qa_guard_version": REPORT_QA_GUARD_VERSION,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    refresh_calls = []

    def fake_refresh(active_output_dir):
        refresh_calls.append(active_output_dir)
        (qa_dir / "report_consistency_check.txt").write_text("fresh qa", encoding="utf-8")
        return {"qa_check_path": str(qa_dir / "report_consistency_check.txt")}

    previous_config = dict(api_server._current_config)

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        monkeypatch.setattr(
            api_server,
            "_refresh_report_semantic_artifacts",
            fake_refresh,
        )

        payload = asyncio.run(api_server.get_reports())
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    report_names = {item["name"] for item in payload["reports"]}
    assert refresh_calls == [str(output_dir)]
    assert "初查报告.html" in report_names
    assert "qa/report_consistency_check.txt" in report_names


def test_sync_active_paths_switches_report_center_interfaces_to_new_output_directory(
    tmp_path,
):
    old_output_dir = tmp_path / "old_output"
    new_output_dir = tmp_path / "new_output"
    old_results_dir = old_output_dir / "analysis_results"
    new_results_dir = new_output_dir / "analysis_results"
    old_results_dir.mkdir(parents=True)
    new_results_dir.mkdir(parents=True)

    (old_results_dir / "旧目录报告.txt").write_text("old", encoding="utf-8")
    (new_results_dir / "新目录报告.txt").write_text("new", encoding="utf-8")

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_config = dict(api_server._current_config)

    try:
        api_server.analysis_state.status = "completed"
        api_server.analysis_state.progress = 100
        api_server.analysis_state.phase = "旧目录仍激活"
        api_server.analysis_state.end_time = datetime.now()
        api_server.analysis_state.results = {
            "persons": ["旧数据"],
            "companies": [],
            "analysisResults": {},
            "graphData": {},
        }
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(old_output_dir)

        response = asyncio.run(
            api_server.sync_active_paths(
                api_server.ActivePathsRequest(outputDirectory=str(new_output_dir))
            )
        )
        assert response["success"] is True
        assert response["data"]["status"] == "idle"
        assert api_server._get_active_output_dir() == str(new_output_dir)

        list_payload = asyncio.run(api_server.get_report_files())
        legacy_payload = asyncio.run(api_server.get_reports())
        manifest_payload = asyncio.run(api_server.get_report_manifest())
        with pytest.raises(api_server.HTTPException) as exc_info:
            asyncio.run(api_server.get_audit_navigation())
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    list_names = {item["name"] for item in list_payload["reports"]}
    legacy_names = {item["name"] for item in legacy_payload["reports"]}
    manifest_names = {item["name"] for item in manifest_payload["reports"]}

    assert "新目录报告.txt" in list_names
    assert "旧目录报告.txt" not in list_names
    assert "新目录报告.txt" in legacy_names
    assert "旧目录报告.txt" not in legacy_names
    assert "新目录报告.txt" in manifest_names
    assert "旧目录报告.txt" not in manifest_names
    assert exc_info.value.status_code == 400
    assert all(
        str(new_output_dir / "analysis_results") in item["path"]
        for item in list_payload["reports"]
    )
    assert all(
        str(new_output_dir / "analysis_results") in item["path"]
        for item in legacy_payload["reports"]
    )


def test_analysis_runtime_logs_are_persisted_to_output_and_stop_after_finalize(tmp_path):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    logger = logging.getLogger("analysis_runtime_log_test")
    logger.setLevel(logging.INFO)

    with api_server._analysis_log_lock:
        previous_active = dict(api_server._active_analysis_log_paths)
        previous_last = dict(api_server._last_analysis_log_paths)
        api_server._active_analysis_log_paths.clear()
        api_server._last_analysis_log_paths.clear()

    try:
        runtime_paths = api_server._start_analysis_runtime_log_capture(
            str(output_dir),
            datetime(2026, 3, 14, 12, 0, 0),
        )
        api_server.broadcast_log("INFO", "阶段开始")
        logger.info("内部日志")

        mirror_path = api_server._attach_analysis_results_log_mirror(str(results_dir))
        api_server.broadcast_log("WARN", "阶段结束")
        api_server._finalize_analysis_runtime_log_capture("completed")
        api_server.broadcast_log("INFO", "收尾后无关日志")

        last_paths = api_server._get_last_analysis_log_paths()
        run_log_path = runtime_paths["runLog"]
        latest_log_path = runtime_paths["latestLog"]

        assert mirror_path is not None
        assert os.path.exists(run_log_path)
        assert os.path.exists(latest_log_path)
        assert os.path.exists(mirror_path)
        assert last_paths["run"] == run_log_path
        assert last_paths["latest"] == latest_log_path
        assert last_paths["resultsMirror"] == mirror_path

        with open(run_log_path, "r", encoding="utf-8") as f:
            run_log_content = f.read()
        with open(latest_log_path, "r", encoding="utf-8") as f:
            latest_log_content = f.read()
        with open(mirror_path, "r", encoding="utf-8") as f:
            mirror_content = f.read()

        for content in [run_log_content, latest_log_content, mirror_content]:
            assert "# 分析运行日志" in content
            assert "阶段开始" in content
            assert "analysis_runtime_log_test - 内部日志" in content
            assert "阶段结束" in content
            assert "日志固化收尾，分析状态: completed" in content
            assert "收尾后无关日志" not in content
    finally:
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._active_analysis_log_paths.update(previous_active)
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.update(previous_last)


def test_get_analysis_log_history_restores_visible_logs_and_level_stats(tmp_path):
    output_dir = tmp_path / "output"
    results_dir = output_dir / "analysis_results"
    results_dir.mkdir(parents=True)
    mirror_path = results_dir / "分析执行日志.txt"
    mirror_path.write_text(
        "\n".join(
            [
                "# 分析执行日志",
                "2026-03-17 21:00:48 [INFO] data_cleaner - 开始清洗",
                "2026-03-17 21:00:49 [WARNING] data_cleaner - 发现1条零金额记录",
                "2026-03-17 21:00:50 [ERROR] data_cleaner - 缺少日期字段",
            ]
        ),
        encoding="utf-8",
    )

    previous_config = dict(api_server._current_config)
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    with api_server._analysis_log_lock:
        previous_active = dict(api_server._active_analysis_log_paths)
        previous_last = dict(api_server._last_analysis_log_paths)

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        api_server.analysis_state.reset()

        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths["resultsMirror"] = str(mirror_path)

        response = asyncio.run(api_server.get_analysis_log_history(limit=10))

        assert response["message"] == "分析日志获取成功"
        assert response["data"]["path"] == str(mirror_path)
        assert response["data"]["source"] == "analysis_results_mirror"
        assert response["data"]["stats"] == {"info": 1, "warn": 1, "error": 1}
        assert [item["level"] for item in response["data"]["logs"]] == [
            "INFO",
            "WARN",
            "ERROR",
        ]
        assert response["data"]["logs"][0]["time"] == "21:00:48"
        assert response["data"]["logs"][1]["msg"] == "data_cleaner - 发现1条零金额记录"
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._active_analysis_log_paths.update(previous_active)
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.update(previous_last)


def test_sync_active_paths_rebinds_log_history_to_restored_output_logs(tmp_path):
    input_dir = tmp_path / "input"
    old_output_dir = tmp_path / "old_output"
    new_output_dir = tmp_path / "new_output"
    input_dir.mkdir()
    old_output_dir.mkdir()
    new_output_dir.mkdir()

    cache_mgr = CacheManager(str(new_output_dir / "analysis_cache"))
    cache_mgr.save_results(
        {
            "persons": ["张三"],
            "companies": [],
            "profiles": {"张三": {"transactionCount": 1, "totalIncome": 1000}},
            "suspicions": {},
            "analysisResults": {},
            "graphData": {"nodes": [], "edges": []},
            "runtimeLogPaths": {
                "resultsMirror": str(new_output_dir / "analysis_results" / "分析执行日志.txt")
            },
        }
    )

    new_results_dir = new_output_dir / "analysis_results"
    new_results_dir.mkdir(parents=True, exist_ok=True)
    new_mirror_path = new_results_dir / "分析执行日志.txt"
    new_mirror_path.write_text(
        "\n".join(
            [
                "# 分析执行日志",
                "2026-03-21 10:00:00 [INFO] restored - 新目录日志",
            ]
        ),
        encoding="utf-8",
    )

    old_results_dir = old_output_dir / "analysis_results"
    old_results_dir.mkdir(parents=True, exist_ok=True)
    old_mirror_path = old_results_dir / "分析执行日志.txt"
    old_mirror_path.write_text(
        "\n".join(
            [
                "# 分析执行日志",
                "2026-03-20 09:00:00 [INFO] stale - 旧目录日志",
            ]
        ),
        encoding="utf-8",
    )

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_config = dict(api_server._current_config)
    with api_server._analysis_log_lock:
        previous_active = dict(api_server._active_analysis_log_paths)
        previous_last = dict(api_server._last_analysis_log_paths)

    try:
        api_server.analysis_state.reset()
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(old_output_dir)

        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths["resultsMirror"] = str(old_mirror_path)

        response = asyncio.run(
            api_server.sync_active_paths(
                api_server.ActivePathsRequest(
                    inputDirectory=str(input_dir),
                    outputDirectory=str(new_output_dir),
                )
            )
        )
        log_history = asyncio.run(api_server.get_analysis_log_history(limit=10))
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._active_analysis_log_paths.update(previous_active)
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.update(previous_last)

    assert response["success"] is True
    assert response["data"]["cacheRestored"] is True
    assert log_history["data"]["path"] == str(new_mirror_path)
    assert log_history["data"]["logs"][0]["msg"] == "restored - 新目录日志"


def test_clear_cache_clears_analysis_log_history_for_active_output(tmp_path):
    output_dir = tmp_path / "output"
    analysis_logs_dir = output_dir / "analysis_logs"
    analysis_logs_dir.mkdir(parents=True)
    latest_log_path = analysis_logs_dir / "analysis_run_latest.log"
    latest_log_path.write_text(
        "\n".join(
            [
                "# 分析运行日志",
                "2026-03-21 11:00:00 [INFO] stale - 旧日志",
            ]
        ),
        encoding="utf-8",
    )

    previous_config = dict(api_server._current_config)
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    with api_server._analysis_log_lock:
        previous_active = dict(api_server._active_analysis_log_paths)
        previous_last = dict(api_server._last_analysis_log_paths)

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        api_server.analysis_state.reset()
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths["latest"] = str(latest_log_path)

        response = asyncio.run(api_server.clear_cache())
        log_history = asyncio.run(api_server.get_analysis_log_history(limit=10))
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._active_analysis_log_paths.update(previous_active)
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.update(previous_last)

    assert response["success"] is True
    assert not latest_log_path.exists()
    assert log_history["data"]["path"] == ""
    assert log_history["data"]["logs"] == []
    assert log_history["data"]["source"] == "unavailable"


def test_start_analysis_immediately_switches_active_paths_and_blocks_clear_cache(
    tmp_path,
):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    previous_config = dict(api_server._current_config)
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_cache_manager = api_server._cache_manager
    with api_server._analysis_log_lock:
        previous_active = dict(api_server._active_analysis_log_paths)
        previous_last = dict(api_server._last_analysis_log_paths)

    captured_task = {}

    def fake_add_task(func, *args):
        captured_task["func"] = func
        captured_task["args"] = args

    try:
        api_server.analysis_state.reset()
        api_server._current_config.clear()
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths["latest"] = str(
                tmp_path / "stale.log"
            )

        start_response = asyncio.run(
            api_server.start_analysis(
                api_server.AnalysisConfig(
                    inputDirectory=str(input_dir),
                    outputDirectory=str(output_dir),
                ),
                SimpleNamespace(add_task=fake_add_task),
            )
        )

        assert start_response["message"] == "分析任务已启动 (重构版)"
        assert captured_task["func"] is api_server.run_analysis_refactored
        assert captured_task["args"][0].inputDirectory == str(input_dir)
        assert api_server._get_active_output_dir() == str(output_dir.resolve())
        assert api_server.analysis_state.status == "running"
        assert api_server.analysis_state.phase == "等待任务启动..."
        with api_server._analysis_log_lock:
            assert api_server._last_analysis_log_paths == {}

        clear_response = asyncio.run(api_server.clear_cache())

        assert clear_response == {
            "success": False,
            "error": "分析正在运行，无法清空缓存",
        }
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._cache_manager = previous_cache_manager
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._active_analysis_log_paths.update(previous_active)
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.update(previous_last)


def test_stop_analysis_before_worker_execution_is_honored_by_run_analysis_refactored(
    tmp_path,
):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    previous_config = dict(api_server._current_config)
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_cache_manager = api_server._cache_manager
    with api_server._analysis_log_lock:
        previous_active = dict(api_server._active_analysis_log_paths)
        previous_last = dict(api_server._last_analysis_log_paths)

    captured_task = {}

    def fake_add_task(func, *args):
        captured_task["func"] = func
        captured_task["args"] = args

    try:
        api_server.analysis_state.reset()
        api_server._current_config.clear()
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.clear()

        asyncio.run(
            api_server.start_analysis(
                api_server.AnalysisConfig(
                    inputDirectory=str(input_dir),
                    outputDirectory=str(output_dir),
                ),
                SimpleNamespace(add_task=fake_add_task),
            )
        )

        stop_response = asyncio.run(api_server.stop_analysis())
        result = captured_task["func"](*captured_task["args"])

        assert stop_response == {"message": "已发送停止请求", "status": "stopping"}
        assert result is None
        assert api_server.analysis_state.status == "idle"
        assert api_server.analysis_state.phase == "已停止，可重新开始"
        assert api_server.analysis_state.results is None
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._cache_manager = previous_cache_manager
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._active_analysis_log_paths.update(previous_active)
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.update(previous_last)


def test_analysis_runtime_state_machine_rejects_stale_reads_until_stopped_and_cleared(
    tmp_path,
):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    previous_config = dict(api_server._current_config)
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_cache_manager = api_server._cache_manager
    with api_server._analysis_log_lock:
        previous_active = dict(api_server._active_analysis_log_paths)
        previous_last = dict(api_server._last_analysis_log_paths)

    captured_task = {}

    def fake_add_task(func, *args):
        captured_task["func"] = func
        captured_task["args"] = args

    try:
        api_server.analysis_state.reset()
        api_server._current_config.clear()
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.clear()

        asyncio.run(
            api_server.start_analysis(
                api_server.AnalysisConfig(
                    inputDirectory=str(input_dir),
                    outputDirectory=str(output_dir),
                ),
                SimpleNamespace(add_task=fake_add_task),
            )
        )

        with pytest.raises(api_server.HTTPException) as get_results_exc:
            asyncio.run(api_server.get_results())
        with pytest.raises(api_server.HTTPException) as get_graph_exc:
            asyncio.run(api_server.get_graph_data())

        assert get_results_exc.value.status_code == 400
        assert get_results_exc.value.detail == "分析尚未完成且缓存无效"
        assert get_graph_exc.value.status_code == 400
        assert get_graph_exc.value.detail == "分析尚未完成"

        stop_response = asyncio.run(api_server.stop_analysis())
        worker_result = captured_task["func"](*captured_task["args"])

        assert stop_response == {"message": "已发送停止请求", "status": "stopping"}
        assert worker_result is None
        assert api_server.analysis_state.status == "idle"
        assert api_server.analysis_state.phase == "已停止，可重新开始"
        assert api_server.analysis_state.results is None

        clear_response = asyncio.run(api_server.clear_cache())

        assert clear_response["success"] is True
        assert api_server.analysis_state.status == "idle"
        assert api_server.analysis_state.results is None

        with pytest.raises(api_server.HTTPException) as cleared_results_exc:
            asyncio.run(api_server.get_results())
        with pytest.raises(api_server.HTTPException) as cleared_graph_exc:
            asyncio.run(api_server.get_graph_data())

        assert cleared_results_exc.value.status_code == 400
        assert cleared_results_exc.value.detail == "分析尚未完成且缓存无效"
        assert cleared_graph_exc.value.status_code == 400
        assert cleared_graph_exc.value.detail == "分析尚未完成"
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._cache_manager = previous_cache_manager
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._active_analysis_log_paths.update(previous_active)
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.update(previous_last)


def test_restored_analysis_state_results_keeps_core_schema_and_is_not_mutated_by_interfaces(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    run_log_path = output_dir / "analysis_logs" / "analysis_run_20260321.log"
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    run_log_path.write_text("# 分析执行日志\n", encoding="utf-8")
    expected_report_package = {
        "main_report_view": {
            "summary_narrative": "缓存恢复后的报告语义包。",
            "issue_count": 1,
        },
        "priority_board": [
            {
                "entity_name": "张三",
                "priority_score": 82.5,
                "risk_level": "high",
            }
        ],
    }

    CacheManager(str(output_dir / "analysis_cache")).save_results(
        {
            "persons": ["张三"],
            "companies": ["测试科技有限公司"],
            "profiles": {
                "张三": {
                    "transaction_count": 2,
                    "total_income": 120000.0,
                }
            },
            "suspicions": {"directTransfers": []},
            "analysisResults": {
                "aggregation": {"summary": {"极高风险实体数": 0}, "rankedEntities": []},
                "relatedParty": {
                    "third_party_relays": [],
                    "discovered_nodes": [],
                    "relationship_clusters": [],
                    "fund_loops": [],
                },
                "penetration": {"fund_cycles": [], "analysis_metadata": {}},
            },
            "graphData": {"nodes": [{"id": "张三"}], "edges": []},
            "walletData": {"subjects": [], "alerts": []},
            "externalData": {
                "p0": {"credit_data": {}, "aml_data": {}},
                "p1": {
                    "vehicle_data": {
                        "310101199001010011": [{"plate_number": "沪A12345"}]
                    },
                    "precise_property_data": {},
                },
                "p2": {"insurance_data": {}},
                "wallet": {"subjects": [], "alerts": []},
            },
            "runtimeLogPaths": {"run": str(run_log_path)},
        }
    )

    previous_config = dict(api_server._current_config)
    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_cache_manager = api_server._cache_manager
    with api_server._analysis_log_lock:
        previous_active = dict(api_server._active_analysis_log_paths)
        previous_last = dict(api_server._last_analysis_log_paths)

    try:
        api_server.analysis_state.reset()
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)
        monkeypatch.setattr(
            api_server,
            "_load_report_package_for_manifest",
            lambda _results_dir: expected_report_package,
        )
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.clear()

        restored = api_server._sync_analysis_state_with_active_output(force_reload=True)

        assert restored is True
        assert api_server.analysis_state.status == "completed"
        assert api_server.analysis_state.phase == "已从缓存恢复"
        assert {
            "persons",
            "companies",
            "profiles",
            "suspicions",
            "analysisResults",
            "graphData",
            "walletData",
            "externalData",
            "runtimeLogPaths",
            "_profiles_raw",
        }.issubset(api_server.analysis_state.results.keys())
        assert (
            api_server.analysis_state.results["externalData"]["p1"]["vehicle_data"][
                "310101199001010011"
            ][0]["plate_number"]
            == "沪A12345"
        )
        assert api_server.analysis_state.results["walletData"]["alerts"] == []
        assert api_server.analysis_state.results["runtimeLogPaths"] == {
            "run": str(run_log_path)
        }

        memory_snapshot = json.loads(
            json.dumps(
                serialize_for_json(api_server.analysis_state.results),
                ensure_ascii=False,
            )
        )

        results_response = asyncio.run(api_server.get_results())
        graph_response = asyncio.run(api_server.get_graph_data())

        results_payload = json.loads(results_response.body.decode("utf-8"))["data"]
        assert results_payload["reportPackage"] == expected_report_package
        assert results_payload["graphData"]["nodes"][0]["id"] == "张三"
        assert graph_response["data"]["report"]["fund_cycles"] == []
        assert "fund_cycles" in graph_response["data"]["report"]
        assert "fundCycles" not in graph_response["data"]["report"]

        current_snapshot = json.loads(
            json.dumps(
                serialize_for_json(api_server.analysis_state.results),
                ensure_ascii=False,
            )
        )
        assert current_snapshot == memory_snapshot
        assert "reportPackage" not in api_server.analysis_state.results
        assert "report" not in api_server.analysis_state.results["graphData"]
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._cache_manager = previous_cache_manager
        with api_server._analysis_log_lock:
            api_server._active_analysis_log_paths.clear()
            api_server._active_analysis_log_paths.update(previous_active)
            api_server._last_analysis_log_paths.clear()
            api_server._last_analysis_log_paths.update(previous_last)


def test_run_analysis_refactored_defaults_to_project_output_dir(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    captured = {}

    def fake_start_analysis_runtime_log_capture(output_dir, start_time=None):
        captured["output_dir"] = output_dir
        raise RuntimeError("stop after output-dir capture")

    monkeypatch.setattr(
        api_server,
        "_start_analysis_runtime_log_capture",
        fake_start_analysis_runtime_log_capture,
    )

    with pytest.raises(RuntimeError, match="output-dir capture"):
        api_server.run_analysis_refactored(
            api_server.AnalysisConfig(
                inputDirectory=str(input_dir),
                outputDirectory="",
            )
        )

    assert captured["output_dir"] == str(api_server.OUTPUT_DIR)

    api_server.analysis_state.status = previous_state["status"]
    api_server.analysis_state.progress = previous_state["progress"]
    api_server.analysis_state.phase = previous_state["phase"]
    api_server.analysis_state.start_time = previous_state["start_time"]
    api_server.analysis_state.end_time = previous_state["end_time"]
    api_server.analysis_state.results = previous_state["results"]
    api_server.analysis_state.error = previous_state["error"]
    api_server.analysis_state.stop_requested = previous_state["stop_requested"]


def test_run_analysis_refactored_e2e_preserves_plugin_outputs_and_cache_restore(
    tmp_path, monkeypatch
):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    pd.DataFrame(
        [
            {
                "交易时间": "2024-01-01 09:00:00",
                "交易金额": 60000.0,
                "借贷标志": "贷",
                "交易对手": "来源A",
                "交易摘要": "收入A",
            },
            {
                "交易时间": "2024-01-01 09:10:00",
                "交易金额": 60000.0,
                "借贷标志": "贷",
                "交易对手": "来源B",
                "交易摘要": "收入B",
            },
            {
                "交易时间": "2024-01-01 09:20:00",
                "交易金额": 60000.0,
                "借贷标志": "贷",
                "交易对手": "来源C",
                "交易摘要": "收入C",
            },
            {
                "交易时间": "2024-01-01 09:30:00",
                "交易金额": 60000.0,
                "借贷标志": "贷",
                "交易对手": "来源D",
                "交易摘要": "收入D",
            },
            {
                "交易时间": "2024-01-01 09:40:00",
                "交易金额": 60000.0,
                "借贷标志": "贷",
                "交易对手": "来源E",
                "交易摘要": "收入E",
            },
            {
                "交易时间": "2024-01-02 10:00:00",
                "交易金额": 180000.0,
                "借贷标志": "借",
                "交易对手": "集中去向",
                "交易摘要": "集中转出",
            },
            {
                "交易时间": "2024-01-03 09:00:00",
                "交易金额": 80000.0,
                "借贷标志": "借",
                "交易对手": "某公司",
                "交易摘要": "往来款支付",
            },
            {
                "交易时间": "2024-01-05 11:00:00",
                "交易金额": 50000.0,
                "借贷标志": "借",
                "交易对手": "固定对手方",
                "交易摘要": "固定支出1",
            },
            {
                "交易时间": "2024-02-05 11:00:00",
                "交易金额": 50000.0,
                "借贷标志": "借",
                "交易对手": "固定对手方",
                "交易摘要": "固定支出2",
            },
            {
                "交易时间": "2024-03-05 11:00:00",
                "交易金额": 50000.0,
                "借贷标志": "借",
                "交易对手": "固定对手方",
                "交易摘要": "固定支出3",
            },
            {
                "交易时间": "2024-02-10 23:30:00",
                "交易金额": 120000.0,
                "借贷标志": "贷",
                "交易对手": "夜间来源",
                "交易摘要": "春节夜间交易",
            },
        ]
    ).to_excel(input_dir / "张三_中国银行交易流水.xlsx", index=False)

    pd.DataFrame(
        [
            {
                "交易时间": "2024-01-03 09:00:00",
                "交易金额": 80000.0,
                "借贷标志": "贷",
                "交易对手": "张三",
                "交易摘要": "往来款支付",
            }
        ]
    ).to_excel(input_dir / "某公司_中国银行交易流水.xlsx", index=False)

    pd.DataFrame(
        [{"机动车所有人": "张三", "身份证号": "310101199001010011"}]
    ).to_csv(input_dir / "公安部机动车信息_批次1.csv", index=False, encoding="utf-8-sig")

    previous_state = {
        "status": api_server.analysis_state.status,
        "progress": api_server.analysis_state.progress,
        "phase": api_server.analysis_state.phase,
        "start_time": api_server.analysis_state.start_time,
        "end_time": api_server.analysis_state.end_time,
        "results": api_server.analysis_state.results,
        "error": api_server.analysis_state.error,
        "stop_requested": api_server.analysis_state.stop_requested,
    }
    previous_config = dict(api_server._current_config)
    previous_cache_manager = api_server._cache_manager
    previous_active_log_paths = dict(api_server._active_analysis_log_paths)
    previous_last_log_paths = dict(api_server._last_analysis_log_paths)
    previous_cash_threshold = api_server.config.LARGE_CASH_THRESHOLD
    previous_time_window = api_server.config.CASH_TIME_WINDOW_HOURS

    class _FakeReportBuilder:
        def __init__(self, current_output_dir: str):
            self.output_dir = current_output_dir
            self.profiles = {}
            self.suspicions = {}

        def set_primary_config(self, _config):
            return None

        def generate_complete_txt_report(self, path: str):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("report")
            return path

        def generate_report_index_file(self, reports_dir: str):
            os.makedirs(reports_dir, exist_ok=True)
            path = os.path.join(reports_dir, "报告目录清单.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("index")
            return path

    class _FakeSpecializedReportGenerator:
        def __init__(self, *args, **kwargs):
            pass

        def generate_all_reports(self):
            return []

    class _FakeRealSalaryIncomeAnalyzer:
        def analyze(self, *args, **kwargs):
            return {"total_salary": 0}

    class _FakeIncomeExpenseMatchAnalyzer:
        def analyze(self, **kwargs):
            return {}

    class _FakePersonalFundFeatureAnalyzer:
        def analyze(self, **kwargs):
            return {}

    class _FakeFinancialProductAnalyzer:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, **kwargs):
            return {}

    def _sum_numeric_column(df, column_name):
        if column_name not in df:
            return 0.0
        numeric_series = pd.to_numeric(df[column_name].astype("string"), errors="coerce")
        return float(numeric_series.fillna(0).sum())

    def _fake_profile(df, entity_name):
        total_income = _sum_numeric_column(df, "income")
        total_expense = _sum_numeric_column(df, "expense")
        return {
            "entity_name": entity_name,
            "has_data": True,
            "summary": {
                "total_income": total_income,
                "total_expense": total_expense,
                "transaction_count": len(df),
                "real_income": total_income,
                "real_expense": total_expense,
                "salary_ratio": 0,
            },
            "income_structure": {},
            "fund_flow": {},
            "wealth_management": {},
            "large_cash": [],
            "transactions": [],
        }

    def _fake_generate_excel_workbook(**kwargs):
        output_path = kwargs["output_path"]
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(b"excel")
        return output_path

    try:
        monkeypatch.setattr(api_server, "_load_saved_primary_targets_config", lambda *args, **kwargs: None)
        monkeypatch.setattr(api_server, "load_investigation_report_builder", lambda current_output_dir: _FakeReportBuilder(current_output_dir))
        monkeypatch.setattr(api_server, "SpecializedReportGenerator", _FakeSpecializedReportGenerator)
        monkeypatch.setattr(api_server, "RealSalaryIncomeAnalyzer", _FakeRealSalaryIncomeAnalyzer)
        monkeypatch.setattr(api_server, "IncomeExpenseMatchAnalyzer", _FakeIncomeExpenseMatchAnalyzer)
        monkeypatch.setattr(api_server, "PersonalFundFeatureAnalyzer", _FakePersonalFundFeatureAnalyzer)
        monkeypatch.setattr(api_server, "FinancialProductAnalyzer", _FakeFinancialProductAnalyzer)
        monkeypatch.setattr(api_server.financial_profiler, "generate_profile_report", _fake_profile)
        monkeypatch.setattr(api_server.financial_profiler, "build_company_profile", _fake_profile)
        monkeypatch.setattr(api_server.financial_profiler, "extract_bank_accounts", lambda df: [])
        monkeypatch.setattr(api_server.salary_analyzer, "analyze_income_structure", lambda *args, **kwargs: {})
        monkeypatch.setattr(api_server.pboc_account_extractor, "extract_pboc_accounts", lambda *_: {})
        monkeypatch.setattr(api_server.aml_analyzer, "extract_aml_data", lambda *_: {})
        monkeypatch.setattr(api_server.aml_analyzer, "get_aml_alerts", lambda *_: [])
        monkeypatch.setattr(api_server.company_info_extractor, "extract_company_info", lambda *_: {})
        monkeypatch.setattr(api_server.credit_report_extractor, "extract_credit_data", lambda *_: {})
        monkeypatch.setattr(api_server.credit_report_extractor, "get_credit_alerts", lambda *_: [])
        monkeypatch.setattr(
            api_server.bank_account_info_extractor,
            "extract_bank_account_info",
            lambda *_: {
                "310101199001010011": {
                    "accounts": [
                        {
                            "account_number": "6222000011112222",
                            "bank_name": "工商银行",
                            "balance": 49562.68,
                            "status": "正常",
                        }
                    ]
                }
            },
        )
        monkeypatch.setattr(
            api_server.tax_info_extractor,
            "extract_tax_data",
            lambda *_: {
                "310101199001010011": {
                    "tax_records": [
                        {
                            "period_start": "2024-01-01",
                            "period_end": "2024-12-31",
                            "tax_name": "印花税",
                            "amount": 300.0,
                            "source_file": "test_tax.xlsx",
                        }
                    ]
                }
            },
        )
        monkeypatch.setattr(
            api_server.vehicle_extractor,
            "extract_vehicle_data",
            lambda *_: {
                "310101199001010011": [{"plate_number": "沪A12345", "owner_name": "张三"}]
            },
        )
        monkeypatch.setattr(api_server.wealth_product_extractor, "extract_wealth_product_data", lambda *_: {})
        monkeypatch.setattr(api_server.securities_extractor, "extract_securities_data", lambda *_: {})
        monkeypatch.setattr(api_server.asset_extractor, "extract_precise_property_info", lambda *_: {})
        monkeypatch.setattr(api_server.insurance_extractor, "extract_insurance_data", lambda *_: {})
        monkeypatch.setattr(api_server.immigration_extractor, "extract_immigration_data", lambda *_: {})
        monkeypatch.setattr(api_server.hotel_extractor, "extract_hotel_data", lambda *_: {})
        monkeypatch.setattr(api_server.hotel_extractor, "analyze_cohabitation", lambda *_: {})
        monkeypatch.setattr(api_server.cohabitation_extractor, "extract_coaddress_data", lambda *_: {})
        monkeypatch.setattr(api_server.cohabitation_extractor, "extract_coviolation_data", lambda *_: {})
        monkeypatch.setattr(
            api_server,
            "_populate_transport_external_data",
            lambda _data_dir, p2_data, _logger: p2_data.update(
                {"railway_data": {}, "flight_data": {}}
            ),
        )
        monkeypatch.setattr(
            api_server.wallet_data_extractor,
            "extract_wallet_artifact_bundle",
            lambda *args, **kwargs: api_server.wallet_data_extractor.empty_wallet_artifact_bundle(),
        )
        monkeypatch.setattr(
            api_server.wallet_risk_analyzer,
            "enhance_wallet_alerts",
            lambda wallet_data, *args, **kwargs: wallet_data,
        )
        monkeypatch.setattr(api_server.loan_analyzer, "analyze_loan_behaviors", lambda *args, **kwargs: {})
        monkeypatch.setattr(
            api_server.income_analyzer,
            "detect_suspicious_income",
            lambda *args, **kwargs: {"high_risk": [], "medium_risk": []},
        )
        monkeypatch.setattr(api_server.income_analyzer, "extract_large_transactions", lambda *args, **kwargs: [])
        monkeypatch.setattr(api_server.fund_penetration, "analyze_fund_penetration", lambda *args, **kwargs: {})
        monkeypatch.setattr(api_server.ml_analyzer, "run_ml_analysis", lambda *args, **kwargs: {})
        monkeypatch.setattr(api_server.related_party_analyzer, "analyze_related_party_flows", lambda *args, **kwargs: {})
        monkeypatch.setattr(
            api_server.related_party_analyzer,
            "analyze_investigation_unit_flows",
            lambda *args, **kwargs: {"has_flows": False},
        )
        monkeypatch.setattr(api_server.multi_source_correlator, "run_all_correlations", lambda *args, **kwargs: {})
        monkeypatch.setattr(api_server.time_series_analyzer, "analyze_time_series", lambda *args, **kwargs: {})
        monkeypatch.setattr(api_server.clue_aggregator, "aggregate_all_results", lambda *args, **kwargs: {})
        monkeypatch.setattr(
            api_server.family_analyzer,
            "infer_family_units_v2",
            lambda *args, **kwargs: ([], {}),
        )
        monkeypatch.setattr(api_server.family_analyzer, "build_family_tree", lambda *args, **kwargs: {})
        monkeypatch.setattr(api_server.family_analyzer, "get_family_summary", lambda *args, **kwargs: {})
        monkeypatch.setattr(api_server, "_refresh_profiles_and_build_family_summaries", lambda *args, **kwargs: (0, {}))
        monkeypatch.setattr(
            api_server.behavioral_profiler,
            "analyze_behavioral_patterns",
            lambda *args, **kwargs: {},
        )
        monkeypatch.setattr(
            api_server,
            "_load_report_generator",
            lambda: SimpleNamespace(generate_excel_workbook=_fake_generate_excel_workbook),
        )
        monkeypatch.setattr(
            api_server,
            "_load_wallet_report_builder",
            lambda: SimpleNamespace(generate_wallet_artifacts=lambda *args, **kwargs: {}),
        )
        monkeypatch.setattr(
            api_server.flow_visualizer,
            "_calculate_flow_stats",
            lambda *args, **kwargs: {},
        )
        monkeypatch.setattr(
            api_server.flow_visualizer,
            "_prepare_graph_data",
            lambda _stats, _persons, _companies: (
                [
                    {"id": "张三", "size": 20},
                    {"id": "某公司", "size": 16},
                ],
                [{"from": "张三", "to": "某公司", "value": 8}],
                {},
            ),
        )
        monkeypatch.setattr(
            api_server.family_assets_helper,
            "build_family_assets_simple",
            lambda properties, vehicles, person_ids: {
                person_ids[0]: {
                    "家族成员": person_ids,
                    "房产套数": len(next(iter(properties.values()), [])),
                    "房产总价值": 0.0,
                    "车辆数量": len(next(iter(vehicles.values()), [])),
                    "房产": next(iter(properties.values()), []),
                    "车辆": next(iter(vehicles.values()), []),
                }
            }
            if person_ids
            else {},
        )

        result = api_server.run_analysis_refactored(
            api_server.AnalysisConfig(
                inputDirectory=str(input_dir),
                outputDirectory=str(output_dir),
            )
        )

        assert api_server.analysis_state.status == "completed"
        assert result is api_server.analysis_state.results

        first_results = api_server.analysis_state.results
        assert first_results["profiles"]["张三"]["entity_id"] == "310101199001010011"
        assert first_results["profiles"]["张三"]["bank_accounts_official"][0]["balance"] == 49562.68
        assert first_results["profiles"]["张三"]["tax_records"][0]["tax_name"] == "印花税"
        assert first_results["profiles"]["张三"]["vehicles"][0]["plate_number"] == "沪A12345"
        assert first_results["externalData"]["p1"]["vehicle_data"]["310101199001010011"][0]["plate_number"] == "沪A12345"
        assert first_results["runtimeLogPaths"]["run"].endswith(".log")

        suspicions = first_results["suspicions"]
        assert len(suspicions["directTransfers"]) >= 1
        assert len(suspicions["roundAmount"]) >= 1
        assert len(suspicions["fixedAmount"]) >= 1
        assert len(suspicions["frequencyAnomaly"]) >= 1
        assert len(suspicions["suspiciousPattern"]) >= 1
        assert len(suspicions["timeSeriesAlerts"]) >= 1
        assert "张三" in suspicions["fixedFrequency"]
        assert len(suspicions["fixedFrequency"]["张三"]) >= 1
        assert "张三" in suspicions["amountPatterns"]
        assert len(suspicions["amountPatterns"]["张三"]) >= 1

        first_counts = {
            "directTransfers": len(suspicions["directTransfers"]),
            "roundAmount": len(suspicions["roundAmount"]),
            "fixedAmount": len(suspicions["fixedAmount"]),
            "frequencyAnomaly": len(suspicions["frequencyAnomaly"]),
            "suspiciousPattern": len(suspicions["suspiciousPattern"]),
            "timeSeriesAlerts": len(suspicions["timeSeriesAlerts"]),
            "fixedFrequency": len(suspicions["fixedFrequency"]["张三"]),
        }

        api_server.analysis_state.reset("准备缓存恢复验证")
        restored = api_server._sync_analysis_state_with_active_output(force_reload=True)

        assert restored is True
        assert api_server.analysis_state.status == "completed"
        restored_results = api_server.analysis_state.results
        assert restored_results["externalData"]["p1"]["vehicle_data"]["310101199001010011"][0]["plate_number"] == "沪A12345"
        assert restored_results["runtimeLogPaths"]["run"].endswith(".log")
        assert len(restored_results["suspicions"]["directTransfers"]) == first_counts["directTransfers"]
        assert len(restored_results["suspicions"]["roundAmount"]) == first_counts["roundAmount"]
        assert len(restored_results["suspicions"]["fixedAmount"]) == first_counts["fixedAmount"]
        assert len(restored_results["suspicions"]["frequencyAnomaly"]) == first_counts["frequencyAnomaly"]
        assert len(restored_results["suspicions"]["suspiciousPattern"]) == first_counts["suspiciousPattern"]
        assert len(restored_results["suspicions"]["timeSeriesAlerts"]) == first_counts["timeSeriesAlerts"]
        assert len(restored_results["suspicions"]["fixedFrequency"]["张三"]) == first_counts["fixedFrequency"]

        response = asyncio.run(api_server.get_results())
        payload = json.loads(response.body.decode("utf-8"))["data"]
        vehicle_payload = payload["profiles"]["张三"]["vehicles"][0]
        assert vehicle_payload.get("plateNumber", vehicle_payload.get("plate_number")) == "沪A12345"
        assert len(payload["suspicions"]["roundAmount"]) == first_counts["roundAmount"]
        assert len(payload["suspicions"]["fixedFrequency"]["张三"]) == first_counts["fixedFrequency"]
        assert payload["runtimeLogPaths"]["run"].endswith(".log")
    finally:
        api_server.analysis_state.status = previous_state["status"]
        api_server.analysis_state.progress = previous_state["progress"]
        api_server.analysis_state.phase = previous_state["phase"]
        api_server.analysis_state.start_time = previous_state["start_time"]
        api_server.analysis_state.end_time = previous_state["end_time"]
        api_server.analysis_state.results = previous_state["results"]
        api_server.analysis_state.error = previous_state["error"]
        api_server.analysis_state.stop_requested = previous_state["stop_requested"]
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        api_server._cache_manager = previous_cache_manager
        api_server._active_analysis_log_paths.clear()
        api_server._active_analysis_log_paths.update(previous_active_log_paths)
        api_server._last_analysis_log_paths.clear()
        api_server._last_analysis_log_paths.update(previous_last_log_paths)
        api_server.config.LARGE_CASH_THRESHOLD = previous_cash_threshold
        api_server.config.CASH_TIME_WINDOW_HOURS = previous_time_window


def test_save_html_report_refreshes_report_index(tmp_path):
    output_dir = tmp_path / "output"
    previous_config = dict(api_server._current_config)

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)

        response = asyncio.run(
            api_server.save_html_report(
                {"html": "<html><body>report</body></html>", "filename": "初查报告"}
            )
        )

        assert response["success"] is True

        report_path = output_dir / "analysis_results" / "初查报告.html"
        index_path = output_dir / "analysis_results" / "报告目录清单.txt"

        assert report_path.exists()
        assert index_path.exists()

        index_content = index_path.read_text(encoding="utf-8")
        assert "HTML报告: 1 个" in index_content
        assert "txt报告: 1 个" in index_content
        assert "初查报告.html" in index_content
        assert "报告目录清单.txt" in index_content
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)


def test_report_index_file_includes_recursive_semantic_and_dossier_artifacts(tmp_path):
    output_dir = tmp_path / "output"
    reports_dir = output_dir / "analysis_results"
    qa_dir = reports_dir / "qa"
    appendix_dir = reports_dir / "专项报告"
    dossier_dir = reports_dir / "对象卷宗"

    qa_dir.mkdir(parents=True)
    appendix_dir.mkdir(parents=True)
    dossier_dir.mkdir(parents=True)

    (reports_dir / "初查报告.html").write_text("<html></html>", encoding="utf-8")
    (qa_dir / "report_package.json").write_text('{"ok":true}', encoding="utf-8")
    (qa_dir / "report_consistency_check.txt").write_text("qa", encoding="utf-8")
    (appendix_dir / "资金穿透分析报告.txt").write_text("appendix", encoding="utf-8")
    (dossier_dir / "张三对象卷宗.txt").write_text("dossier", encoding="utf-8")

    builder = InvestigationReportBuilder({}, str(output_dir))
    index_path = builder.generate_report_index_file(str(reports_dir))
    index_content = pathlib.Path(index_path).read_text(encoding="utf-8")

    assert "总计: 6 个文件" in index_content
    assert "JSON/QA产物: 1 个" in index_content
    assert "初查报告.html" in index_content
    assert "qa/report_package.json" in index_content
    assert "qa/report_consistency_check.txt" in index_content
    assert "专项报告/资金穿透分析报告.txt" in index_content
    assert "对象卷宗/张三对象卷宗.txt" in index_content


def test_generate_complete_txt_report_refreshes_index_after_semantic_artifacts(
    tmp_path, monkeypatch
):
    output_dir = tmp_path / "output"
    reports_dir = output_dir / "analysis_results"
    reports_dir.mkdir(parents=True)
    output_path = reports_dir / "核查结果分析报告.txt"

    builder = InvestigationReportBuilder({}, str(output_dir))

    monkeypatch.setattr(
        builder,
        "_ensure_report_package",
        lambda report_data, formal_report_path=None: {},
    )

    def fake_save_report_package_artifacts(report=None, formal_report_path=None):
        qa_dir = reports_dir / "qa"
        qa_dir.mkdir(parents=True, exist_ok=True)
        (qa_dir / "report_package.json").write_text(
            '{"main_report_view":{"summary_narrative":"ok"}}',
            encoding="utf-8",
        )
        (qa_dir / "report_consistency_check.txt").write_text("qa", encoding="utf-8")
        return {
            "report_package_path": str(qa_dir / "report_package.json"),
            "qa_check_path": str(qa_dir / "report_consistency_check.txt"),
        }

    monkeypatch.setattr(
        builder,
        "save_report_package_artifacts",
        fake_save_report_package_artifacts,
    )

    builder.generate_complete_txt_report(
        str(output_path),
        report={
            "family_sections": [],
            "person_sections": [],
            "company_sections": [],
            "conclusion": {},
            "next_steps": [],
        },
    )

    index_content = (reports_dir / "报告目录清单.txt").read_text(encoding="utf-8")
    assert "qa/report_package.json" in index_content
    assert "qa/report_consistency_check.txt" in index_content


def test_resolve_open_folder_path_rejects_old_output_after_sync_switch(tmp_path):
    old_output_dir = tmp_path / "old_output"
    new_output_dir = tmp_path / "new_output"
    old_analysis_results_dir = old_output_dir / "analysis_results"
    new_analysis_results_dir = new_output_dir / "analysis_results"
    old_analysis_results_dir.mkdir(parents=True)
    new_analysis_results_dir.mkdir(parents=True)

    previous_config = dict(api_server._current_config)

    try:
        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(old_output_dir)
        asyncio.run(
            api_server.sync_active_paths(
                api_server.ActivePathsRequest(outputDirectory=str(new_output_dir))
            )
        )

        with pytest.raises(api_server.HTTPException) as exc_info:
            api_server._resolve_open_folder_path(str(old_analysis_results_dir))

        resolved_new = api_server._resolve_open_folder_path(str(new_analysis_results_dir))
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)

    assert exc_info.value.status_code == 403
    assert resolved_new == str(new_analysis_results_dir.resolve())


def test_get_windows_explorer_executable_prefers_absolute_system_path(monkeypatch):
    monkeypatch.setenv("WINDIR", r"D:\Win")
    monkeypatch.setenv("SystemRoot", r"D:\Windows")
    monkeypatch.setattr(
        api_server.os.path,
        "exists",
        lambda path: path == r"D:\Win\explorer.exe",
    )

    explorer_path = api_server._get_windows_explorer_executable()

    assert explorer_path == r"D:\Win\explorer.exe"


def test_open_folder_in_windows_prefers_shell_explore(monkeypatch):
    folder_path = r"C:\cases\analysis_results"
    expected_path = api_server.os.path.realpath(api_server.os.path.abspath(folder_path))
    calls = []

    monkeypatch.setattr(
        api_server,
        "_shell_execute_windows",
        lambda file_path, **kwargs: calls.append((file_path, kwargs)),
    )
    monkeypatch.setattr(
        api_server.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not launch subprocess")),
    )

    api_server._open_folder_in_windows(folder_path)

    assert calls == [
        (
            expected_path,
            {
                "verb": "explore",
                "working_dir": api_server.os.path.dirname(expected_path),
            },
        )
    ]


def test_open_folder_in_windows_falls_back_to_absolute_explorer_after_shell_failure(monkeypatch):
    folder_path = r"C:\cases\analysis_results"
    expected_path = api_server.os.path.realpath(api_server.os.path.abspath(folder_path))
    explorer_path = r"C:\Windows\explorer.exe"
    shell_calls = []

    monkeypatch.setattr(
        api_server,
        "_get_windows_explorer_executable",
        lambda: explorer_path,
    )

    def fake_shell_execute(file_path, **kwargs):
        shell_calls.append((file_path, kwargs))
        if file_path == expected_path:
            raise OSError("shell verb failed")
        return None

    monkeypatch.setattr(api_server, "_shell_execute_windows", fake_shell_execute)
    monkeypatch.setattr(
        api_server.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not launch subprocess")),
    )

    api_server._open_folder_in_windows(folder_path)

    assert shell_calls == [
        (
            expected_path,
            {
                "verb": "explore",
                "working_dir": api_server.os.path.dirname(expected_path),
            },
        ),
        (
            expected_path,
            {
                "verb": "open",
                "working_dir": api_server.os.path.dirname(expected_path),
            },
        ),
        (
            explorer_path,
            {
                "parameters": f'"{expected_path}"',
                "working_dir": api_server.os.path.dirname(explorer_path),
            },
        ),
    ]


def test_open_folder_in_windows_falls_back_to_cmd_start(monkeypatch):
    folder_path = r"C:\cases\analysis_results"
    expected_path = api_server.os.path.realpath(api_server.os.path.abspath(folder_path))
    explorer_path = r"C:\Windows\explorer.exe"
    commands = []

    monkeypatch.setattr(
        api_server,
        "_get_windows_explorer_executable",
        lambda: explorer_path,
    )
    monkeypatch.setattr(
        api_server,
        "_get_windows_cmd_executable",
        lambda: r"C:\Windows\System32\cmd.exe",
    )
    monkeypatch.setattr(
        api_server,
        "_shell_execute_windows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("shell execute failed")),
    )

    def fake_popen(cmd, *args, **kwargs):
        commands.append(cmd)
        if len(commands) == 1:
            raise OSError("explorer failed")
        return SimpleNamespace()

    monkeypatch.setattr(api_server.subprocess, "Popen", fake_popen)

    api_server._open_folder_in_windows(folder_path)

    assert commands == [
        [explorer_path, expected_path],
        [r"C:\Windows\System32\cmd.exe", "/c", "start", "", expected_path],
    ]


def test_collect_family_assets_for_summary_deduplicates_properties_and_vehicles():
    profiles = {
        "张三": {
            "properties_precise": [{"location": "测试路1号101室"}],
            "vehicles": [{"号牌号码": "沪A12345"}],
        },
        "李四": {
            "properties": [{"房地坐落": "测试路1号101室"}],
            "vehicles": [{"号牌号码": "沪A12345"}],
        },
    }

    assets = api_server._collect_family_assets_for_summary(["张三", "李四"], profiles)

    assert len(assets["properties"]) == 1
    assert len(assets["vehicles"]) == 1


def test_collect_family_assets_for_summary_prefers_property_identifier_over_address_variation():
    profiles = {
        "张三": {
            "properties_precise": [
                {
                    "location": "灵石路1123弄23号604",
                    "property_number": "310108013003GB00003F00150028",
                }
            ]
        },
        "李四": {
            "properties": [
                {
                    "房地坐落": "灵石路1123弄23号604室",
                    "property_number": "310108013003GB00003F00150028",
                }
            ]
        },
    }

    assets = api_server._collect_family_assets_for_summary(["张三", "李四"], profiles)

    assert len(assets["properties"]) == 1


def test_family_unit_has_profile_members_only_accepts_units_with_profile_overlap():
    profiles = {"候海焱": {"summary": {}}}

    assert api_server._family_unit_has_profile_members(["候海焱"], profiles) is True
    assert (
        api_server._family_unit_has_profile_members(["侯海焱", "周伟", "周天健"], profiles)
        is False
    )


def test_serialize_profiles_calculates_max_transaction_from_detail_records():
    profiles = {
        "张三": {
            "summary": {
                "total_income": 100000,
                "total_expense": 80000,
                "transaction_count": 3,
            },
            "income_structure": {"total_income": 100000, "total_expense": 80000},
            "fund_flow": {
                "cash_income": 0,
                "cash_expense": 0,
                "third_party_income": 20000,
                "third_party_expense": 30000,
                "third_party_transactions": [
                    {"日期": "2026-01-01", "金额": 12345, "摘要": "转账", "对手方": "李四"}
                ],
            },
            "wealth_management": {
                "wealth_purchase_transactions": [
                    {"日期": "2026-01-02", "金额": 88888, "摘要": "理财申购", "对手方": "某银行"}
                ]
            },
            "categories": {
                "large_amount": [
                    {
                        "date": "2026-01-03",
                        "description": "大额支出",
                        "counterparty": "王五",
                        "amount": -50000,
                    }
                ]
            },
        }
    }

    result = api_server.serialize_profiles(profiles)

    assert result["张三"]["maxTransaction"] == 88888


def test_specialized_suspicion_report_keeps_hits_visible_and_supports_camel_case_fields(
    tmp_path,
):
    generator = SpecializedReportGenerator(
        analysis_results={},
        profiles={},
        suspicions={
            "cashTimingPatterns": [
                {
                    "person1": "张三",
                    "person2": "张三",
                    "time1": "2026-01-01T10:00:00",
                    "time2": "2026-01-01T12:00:00",
                    "amount1": 2000,
                    "amount2": 1980,
                    "timeDiff": 2,
                    "riskLevel": "medium",
                    "withdrawalSource": "张三流水.xlsx",
                    "depositSource": "张三流水.xlsx",
                }
            ],
            "cashCollisions": [
                {
                    "person1": "张三",
                    "person2": "李四",
                    "time1": "2026-01-02T09:00:00",
                    "time2": "2026-01-02T15:00:00",
                    "amount1": 5000,
                    "amount2": 5000,
                    "timeDiff": 6,
                    "riskLevel": "high",
                    "withdrawalSource": "张三流水.xlsx",
                    "depositSource": "李四流水.xlsx",
                }
            ],
            "directTransfers": [
                {
                    "from": "张三",
                    "to": "某公司",
                    "amount": 30000,
                    "date": "2026-01-03",
                    "direction": "out",
                    "description": "往来款",
                    "riskLevel": "high",
                    "sourceFile": "张三流水.xlsx",
                    "sourceRowIndex": 88,
                }
            ],
            "holidayTransactions": {
                "张三": [
                    {
                        "date": "2026-02-10",
                        "amount": 12000,
                        "holidayName": "春节",
                        "holidayPeriod": "during",
                        "direction": "income",
                        "sourceFile": "张三流水.xlsx",
                        "sourceRowIndex": 101,
                        "riskReason": "节假日大额入账",
                    }
                ]
            },
            "amlAlerts": [
                {
                    "name": "张三",
                    "alert_type": "反洗钱查询有结果",
                    "suspicious_transaction_count": 0,
                    "large_transaction_count": 0,
                    "payment_transaction_count": 0,
                    "source": "aml.xlsx",
                }
            ],
            "creditAlerts": [
                {
                    "name": "张三",
                    "alert_type": "欠税记录",
                    "count": 2,
                    "source": "征信报告",
                }
            ],
        },
        output_dir=str(tmp_path / "analysis_results"),
        input_dir=str(tmp_path),
    )

    content = generator._generate_suspicion_report()

    assert "（一）同主体现金时序伴随" in content
    assert "共命中 1 条同主体现金时序伴随" in content
    assert "未发现同主体现金时序伴随" not in content
    assert "（二）跨实体现金碰撞" in content
    assert "共命中 1 条跨实体现金碰撞" in content
    assert "未发现跨实体现金碰撞" not in content
    assert "【直接往来 1】" in content
    assert "交易人: 张三" in content
    assert "对方: 某公司" in content
    assert "📁 溯源: 张三流水.xlsx" in content
    assert "三、节假日敏感交易" in content
    assert "【节假日交易 1】" in content
    assert "AML查询命中 1 人次" in content
    assert "未发现反洗钱预警" not in content
    assert "【预警】张三 - 欠税记录 (2 次)" in content
    assert "未发现征信预警" not in content


def test_refresh_profile_real_metrics_preserves_salary_reference_income():
    class _FakeIncomeExpenseAnalyzer:
        def analyze(self, **kwargs):
            return {"risk_level": "low", "metrics": kwargs}

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-15", "2024-01-31"]),
            "income": [10000.0, 12000.0],
            "expense": [0.0, 0.0],
            "counterparty": ["某医院", "某医院"],
            "description": ["代发工资", "代发奖金"],
        }
    )
    profile = {
        "income_structure": {"salary_income": 22000.0},
        "wealth_management": {},
        "fund_flow": {},
        "yearly_salary": {"summary": {"total": 22000.0}},
        "summary": {},
    }

    _refresh_profile_real_metrics(
        profile,
        df,
        "张三",
        family_members=[],
        income_expense_match_analyzer=_FakeIncomeExpenseAnalyzer(),
    )

    income_classification = profile["income_classification"]
    assert income_classification["salary_reference_income"] == 22000.0
    assert (
        income_classification["salary_reference_basis"]
        == "yearly_salary_summary_total"
    )


def test_serialize_for_json_converts_nested_sets():
    payload = {
        "profiles": {
            "朱明": {
                "wealth_management": {
                    "wealth_accounts": {"A002", "A001"},
                    "tags": frozenset({"x", "y"}),
                }
            }
        }
    }

    result = serialize_for_json(payload)

    assert result["profiles"]["朱明"]["wealth_management"]["wealth_accounts"] == [
        "A001",
        "A002",
    ]
    assert result["profiles"]["朱明"]["wealth_management"]["tags"] == ["x", "y"]


def test_augment_graph_cache_with_wallet_data_preserves_existing_wallet_counterparties():
    graph_cache = {
        "nodes": [
            {"id": "张三", "label": "张三", "group": "core"},
            {"id": "某对手", "label": "某对手", "group": "wallet_counterparty"},
        ],
        "edges": [
            {"from": "张三", "to": "某对手", "type": "wallet", "value": 0.5},
        ],
        "walletReport": {
            "wallet_alerts": [
                {
                    "person": "张三",
                    "counterparty": "某对手",
                    "amount": 100.0,
                    "date": "2026-03-24",
                    "description": "夜间异常收款",
                    "risk_level": "medium",
                    "alert_type": "night_income",
                    "risk_reason": "夜间高频",
                }
            ],
            "wallet_counterparties": [
                {
                    "person": "张三",
                    "counterparty": "某对手",
                    "platforms": ["支付宝"],
                    "amount": 100.0,
                    "count": 2,
                }
            ],
        },
    }
    wallet_data = {
        "subjects": [
            {
                "subjectName": "张三",
                "matchedToCore": True,
                "platforms": {
                    "alipay": {
                        "incomeTotalYuan": 100.0,
                        "expenseTotalYuan": 0.0,
                        "topCounterparties": [
                            {"name": "某对手", "totalAmountYuan": 100.0, "count": 2}
                        ],
                    }
                },
            }
        ],
        "alerts": [
            {
                "person": "张三",
                "counterparty": "某对手",
                "amount": 100.0,
                "date": "2026-03-24",
                "description": "夜间异常收款",
                "risk_level": "medium",
                "alert_type": "night_income",
                "risk_reason": "夜间高频",
            }
        ],
    }

    result = api_server._augment_graph_cache_with_wallet_data(
        graph_cache,
        wallet_data,
        core_persons=["张三"],
        companies=[],
    )

    wallet_report = result["walletReport"]
    assert len(wallet_report["wallet_counterparties"]) == 1
    assert wallet_report["wallet_counterparties"][0]["counterparty"] == "某对手"
    assert len(wallet_report["wallet_alerts"]) == 1
