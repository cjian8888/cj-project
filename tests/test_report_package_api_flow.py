#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""report_package API flow regression tests."""

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import api_server
from report_config.primary_targets_schema import AnalysisUnit, PrimaryTargetsConfig


def _make_workspace_tmp_dir() -> Path:
    root = Path(__file__).resolve().parents[1] / "output" / "tmp_test_report_api_flow"
    root.mkdir(parents=True, exist_ok=True)
    case_dir = root / f"case_{uuid4().hex}"
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_minimal_cache(output_dir: Path) -> None:
    cache_dir = output_dir / "analysis_cache"
    _write_json(
        cache_dir / "profiles.json",
        {
            "张三": {
                "transactionCount": 6,
                "totalIncome": 200000,
                "totalExpense": 150000,
                "summary": {
                    "total_income": 200000,
                    "total_expense": 150000,
                    "real_income": 180000,
                    "real_expense": 120000,
                },
            }
        },
    )
    _write_json(
        cache_dir / "derived_data.json",
        {
            "family_units_v2": [
                {
                    "anchor": "张三",
                    "members": ["张三", "李四"],
                    "member_details": [
                        {"name": "张三", "relation": "本人", "has_data": True},
                        {"name": "李四", "relation": "配偶", "has_data": False},
                    ],
                }
            ],
            "aggregation": {
                "summary": {
                    "极高风险实体数": 0,
                    "高风险实体数": 1,
                    "高优先线索实体数": 1,
                },
                "ranked_entities": [
                    {
                        "name": "张三",
                        "risk_score": 72.0,
                        "risk_confidence": 0.76,
                        "risk_level": "high",
                        "summary": "存在待核查直接往来",
                    }
                ],
            },
        },
    )
    _write_json(
        cache_dir / "suspicions.json",
        {
            "directTransfers": [
                {
                    "from": "张三",
                    "to": "某公司",
                    "amount": 80000,
                    "date": "2026-03-18",
                    "description": "往来款",
                    "riskLevel": "medium",
                    "sourceFile": "张三流水.xlsx",
                    "sourceRowIndex": 6,
                }
            ]
        },
    )
    _write_json(cache_dir / "graph_data.json", {})
    _write_json(
        cache_dir / "metadata.json",
        {
            "version": "2026.03",
            "generatedAt": "2026-03-18T13:00:00",
            "dataFlow": "cache-first",
        },
    )


def test_save_html_report_refreshes_report_package_artifacts():
    output_dir = _make_workspace_tmp_dir()
    previous_config = dict(api_server._current_config)
    try:
        _seed_minimal_cache(output_dir)

        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)

        response = asyncio.run(
            api_server.save_html_report(
                {"html": "<html><body>semantic report</body></html>", "filename": "初查报告"}
            )
        )

        assert response["success"] is True

        report_path = output_dir / "analysis_results" / "初查报告.html"
        report_package_path = output_dir / "analysis_results" / "qa" / "report_package.json"
        consistency_path = (
            output_dir / "analysis_results" / "qa" / "report_consistency_check.json"
        )
        summary_path = (
            output_dir / "analysis_results" / "qa" / "report_consistency_check.txt"
        )

        assert report_path.exists()
        assert report_package_path.exists()
        assert consistency_path.exists()
        assert summary_path.exists()

        report_package = json.loads(report_package_path.read_text(encoding="utf-8"))
        checks = json.loads(consistency_path.read_text(encoding="utf-8"))

        assert report_package["coverage"]["persons_count"] == 1
        assert report_package["priority_board"][0]["entity_name"] == "张三"
        assert report_package["issues"][0]["category"] == "直接往来"
        assert (
            report_package["appendix_views"]["appendix_index"]["items"][2]["title"]
            == "附录C 关系网络与资金穿透"
        )
        assert any(
            item["check_id"] == "html_missing_but_index_points_html"
            and item["status"] == "pass"
            for item in checks["checks"]
        )
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        shutil.rmtree(output_dir, ignore_errors=True)


def test_generate_report_v5_persists_report_package_before_save(monkeypatch):
    output_dir = _make_workspace_tmp_dir()
    previous_config = dict(api_server._current_config)
    try:
        _seed_minimal_cache(output_dir)

        api_server._current_config.clear()
        api_server._current_config["outputDirectory"] = str(output_dir)

        config = PrimaryTargetsConfig(
            analysis_units=[AnalysisUnit(anchor="张三", members=["张三", "李四"])]
        )
        monkeypatch.setattr(
            "report_config.primary_targets_service.PrimaryTargetsService.get_or_create_config",
            lambda self: (config, "ok", False),
        )

        response = asyncio.run(api_server.generate_investigation_report_v5())

        assert response["success"] is True
        assert response["report"]["meta"]["title_subject"] == "张三"
        assert "report_package" in response["report"]

        report_package_path = output_dir / "analysis_results" / "qa" / "report_package.json"
        summary_path = (
            output_dir / "analysis_results" / "qa" / "report_consistency_check.txt"
        )

        assert report_package_path.exists()
        assert summary_path.exists()

        report_package = json.loads(report_package_path.read_text(encoding="utf-8"))
        summary_text = summary_path.read_text(encoding="utf-8")

        assert report_package["coverage"]["persons_count"] == 1
        assert report_package["priority_board"][0]["entity_name"] == "张三"
        assert (
            report_package["appendix_views"]["appendix_e_wallet_supplement"]["title"]
            == "附录E 电子钱包补证"
        )
        assert "REPORT PACKAGE QA SUMMARY" in summary_text
    finally:
        api_server._current_config.clear()
        api_server._current_config.update(previous_config)
        shutil.rmtree(output_dir, ignore_errors=True)
