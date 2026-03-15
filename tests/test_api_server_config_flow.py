#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api_server 归集配置与缓存边界回归测试。"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest
from starlette.requests import Request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import api_server
import clue_aggregator
from api_server import (
    InvestigationReportRequest,
    _apply_report_generation_overrides,
    _get_effective_family_units_for_analysis,
    _populate_transport_external_data,
    _save_external_report_caches,
    get_graph_data,
    serialize_analysis_results,
)
from cache_manager import CacheManager
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
