#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api_server Dashboard 交付态路由测试。"""

import asyncio
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import api_server


def _prepare_dist(tmp_path):
    dist_dir = tmp_path / "dashboard" / "dist"
    assets_dir = dist_dir / "assets"
    assets_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<html><body>offline dashboard</body></html>", encoding="utf-8"
    )
    (assets_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")
    return dist_dir


def test_root_reports_windows_offline_delivery_target():
    response = asyncio.run(api_server.root())

    assert response["dashboardUrl"] == "/dashboard/"
    assert response["deliveryTarget"] == "windows-offline-one-folder"


def test_dashboard_serves_built_index_file(tmp_path, monkeypatch):
    dist_dir = _prepare_dist(tmp_path)
    monkeypatch.setattr(api_server, "_get_dashboard_dist_dir", lambda: dist_dir)

    response = asyncio.run(api_server.serve_dashboard())

    assert response.path.endswith("index.html")


def test_dashboard_deep_route_falls_back_to_index(tmp_path, monkeypatch):
    dist_dir = _prepare_dist(tmp_path)
    monkeypatch.setattr(api_server, "_get_dashboard_dist_dir", lambda: dist_dir)

    response = asyncio.run(api_server.serve_dashboard("report-center"))

    assert response.path.endswith("index.html")


def test_dashboard_serves_existing_asset_file(tmp_path, monkeypatch):
    dist_dir = _prepare_dist(tmp_path)
    monkeypatch.setattr(api_server, "_get_dashboard_dist_dir", lambda: dist_dir)

    response = asyncio.run(api_server.serve_dashboard("assets/app.js"))

    assert response.path.endswith(os.path.join("assets", "app.js"))


def test_dashboard_returns_404_when_build_is_missing(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dashboard" / "dist"
    monkeypatch.setattr(api_server, "_get_dashboard_dist_dir", lambda: dist_dir)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(api_server.serve_dashboard())

    assert exc_info.value.status_code == 404
    assert "npm run build" in str(exc_info.value.detail)
