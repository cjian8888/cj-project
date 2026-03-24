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
    portable_dirs = build_windows_package.get_portable_source_dirs(PROJECT_ROOT)
    normalized = {(Path(src).name, dest) for src, dest in datas}
    portable_normalized = {
        (Path(src).name, dest.replace("\\", "/")) for src, dest in portable_dirs
    }

    assert ("README.md", ".") in normalized
    assert ("assets", "docs/assets") in normalized
    assert ("utils.py", ".") in normalized
    assert ("dist", "dashboard/dist") in normalized
    assert (
        "vis-network.min.js",
        "dashboard/node_modules/vis-network/standalone/umd",
    ) in normalized
    assert "asset_extractor" in hiddenimports
    assert "chinese_calendar" in hiddenimports
    assert "data_extractor" in hiddenimports
    assert "investigation_report_builder" in hiddenimports
    assert "neo4j" in hiddenimports
    assert "report_config.primary_targets_service" in hiddenimports
    assert "report_quality_guard" in hiddenimports
    assert "report_generator" in hiddenimports
    assert "report_text_formatter" in hiddenimports
    assert "specialized_reports" in hiddenimports
    assert "suspicion_engine" in hiddenimports
    assert "websockets" in hiddenimports
    assert "wallet_report_builder" in hiddenimports
    assert "uvicorn.protocols.websockets.websockets_impl" in hiddenimports
    assert ("config", "config") in portable_normalized
    assert ("dist", "dashboard/dist") in portable_normalized
    assert ("knowledge", "knowledge") in portable_normalized
    assert ("report_config", "report_config") in portable_normalized
    assert ("templates", "templates") in portable_normalized
    assert ("utils", "utils") in portable_normalized


def test_collect_preflight_issues_is_clean_for_current_repo():
    assert build_windows_package.collect_preflight_issues(PROJECT_ROOT) == []


def test_requirements_windows_build_pin_pyinstaller_for_win7():
    text = (PROJECT_ROOT / "requirements-windows-build.txt").read_text(
        encoding="utf-8"
    )

    assert "pyinstaller==5.13.2" in text
    assert "Windows 8+" in text
    assert "cryptography==39.0.2" in text


def test_windows_spec_disables_pyz_archive_for_win7_runtime():
    text = (PROJECT_ROOT / "fpas_windows.spec").read_text(encoding="utf-8")

    assert "noarchive=True" in text


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


def test_ensure_required_runtime_modules_rejects_missing_websockets(monkeypatch):
    monkeypatch.setattr(
        build_windows_package.importlib.util,
        "find_spec",
        lambda name: None if name == "websockets" else object(),
    )

    with pytest.raises(SystemExit) as exc_info:
        build_windows_package.ensure_required_runtime_modules()

    assert "websockets" in str(exc_info.value)


def test_parse_args_supports_skip_dashboard_build():
    args = build_windows_package.parse_args(["--skip-dashboard-build"])

    assert args.skip_dashboard_build is True
    assert args.preflight is False
    assert args.bundle_mode == "portable-runtime"


def test_parse_args_supports_explicit_pyinstaller_mode():
    args = build_windows_package.parse_args(["--bundle-mode", "pyinstaller"])

    assert args.bundle_mode == "pyinstaller"


def test_portable_start_cmd_uses_relative_runtime_launcher():
    cmd_text = build_windows_package.render_portable_start_cmd()

    assert r"%~dp0" in cmd_text
    assert r"FPAS_STARTUP_DIAGNOSTICS_ROOT=%FPAS_ROOT%" in cmd_text
    assert r"runtime\python\python.exe" in cmd_text
    assert r'"%FPAS_PYTHON%" "%FPAS_ROOT%api_server.py"' in cmd_text
    assert "C:\\" not in cmd_text


def test_portable_start_vbs_launches_cmd_from_same_directory():
    vbs_text = build_windows_package.render_portable_start_vbs()

    assert "start_fpas.cmd" in vbs_text
    assert "CurrentDirectory = appDir" in vbs_text
