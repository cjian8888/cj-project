#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 离线构建入口的关键回归测试。"""

from pathlib import Path
from typing import Optional
from types import SimpleNamespace

import pytest

import build_windows_package


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_resolve_npm_command_prefers_npm_cmd_on_windows(monkeypatch):
    def fake_which(name: str) -> Optional[str]:
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


def test_windows_runtime_resources_collect_delivery_assets():
    datas = build_windows_package.get_pyinstaller_datas(PROJECT_ROOT)
    hiddenimports = build_windows_package.get_pyinstaller_hiddenimports()
    normalized = {(Path(src).name, dest) for src, dest in datas}

    assert ("README.md", ".") in normalized
    assert ("assets", "docs/assets") in normalized
    assert ("utils.py", ".") in normalized
    assert ("dist", "dashboard/dist") in normalized
    assert (
        "vis-network.min.js",
        "dashboard/node_modules/vis-network/standalone/umd",
    ) in normalized
    assert "chinese_calendar" in hiddenimports
    assert "neo4j" in hiddenimports


def test_collect_preflight_issues_is_clean_for_current_repo():
    assert build_windows_package.collect_preflight_issues(PROJECT_ROOT) == []


def test_requirements_windows_build_pin_pyinstaller_for_win7():
    text = (PROJECT_ROOT / "requirements-windows-build.txt").read_text(
        encoding="utf-8"
    )

    assert "pyinstaller==5.13.2" in text
    assert "Windows 8+" in text


def test_ensure_windows_build_environment_rejects_non_windows(monkeypatch):
    monkeypatch.setattr(build_windows_package.sys, "platform", "darwin")

    with pytest.raises(SystemExit) as exc_info:
        build_windows_package.ensure_windows_build_environment()

    assert "--preflight" in str(exc_info.value)


def test_ensure_pyinstaller_rejects_unpinned_version(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(stdout="6.16.0\n", stderr="")

    monkeypatch.setattr(build_windows_package.subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as exc_info:
        build_windows_package.ensure_pyinstaller()

    assert "5.13.2" in str(exc_info.value)


def test_parse_args_supports_skip_dashboard_build():
    args = build_windows_package.parse_args(["--skip-dashboard-build"])

    assert args.skip_dashboard_build is True
    assert args.preflight is False
