#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 离线构建入口的关键回归测试。"""

from pathlib import Path

import build_windows_package


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_resolve_npm_command_prefers_npm_cmd_on_windows(monkeypatch):
    def fake_which(name: str) -> str | None:
        if name == "npm.cmd":
            return r"C:\Program Files\nodejs\npm.cmd"
        if name == "npm":
            return r"C:\Program Files\nodejs\npm"
        return None

    monkeypatch.setattr(build_windows_package.sys, "platform", "win32")
    monkeypatch.setattr(build_windows_package.shutil, "which", fake_which)

    assert build_windows_package._resolve_npm_command() == [
        r"C:\Program Files\nodejs\npm.cmd"
    ]


def test_dashboard_entry_has_no_external_font_preconnects():
    html = (PROJECT_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")

    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html


def test_dashboard_styles_have_no_external_font_imports():
    css = (PROJECT_ROOT / "dashboard" / "src" / "index.css").read_text(
        encoding="utf-8"
    )

    assert "fonts.googleapis.com" not in css


def test_windows_spec_collects_delivery_runtime_resources():
    spec_text = (PROJECT_ROOT / "fpas_windows.spec").read_text(encoding="utf-8")

    assert '"dashboard" / "dist"' in spec_text
    assert "vis-network.min.js" in spec_text
    assert '"utils.py"' in spec_text
    assert '"chinese_calendar"' in spec_text
    assert '"neo4j"' in spec_text
