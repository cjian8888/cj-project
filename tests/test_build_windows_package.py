#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 离线构建入口的关键回归测试。"""

import shutil
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

    assert cmd_text.splitlines()[0] == "@echo off"
    assert not cmd_text.startswith("\\")
    assert r"%~dp0" in cmd_text
    assert r'FPAS_DELIVERY_MODE=1' in cmd_text
    assert r'if not defined FPAS_AUTO_OPEN_BROWSER set "FPAS_AUTO_OPEN_BROWSER=1"' in cmd_text
    assert r"FPAS_SERVER_PID_FILE=%FPAS_RUN_DIR%\server.pid" in cmd_text
    assert r"FPAS_BROWSER_PID_FILE=%FPAS_RUN_DIR%\browser.pid" in cmd_text
    assert r"FPAS_BROWSER_PROFILE_DIR=%FPAS_RUN_DIR%\browser-profile" in cmd_text
    assert r'FPAS_STOPPING_FLAG=%FPAS_RUN_DIR%\stopping.flag' in cmd_text
    assert r"FPAS_STARTUP_DIAGNOSTICS_ROOT=%FPAS_ROOT%" in cmd_text
    assert r"FPAS_PYTHON=%FPAS_ROOT%\runtime\python\python.exe" in cmd_text
    assert r'start "" /b "%FPAS_PYTHON%" "%FPAS_ROOT%\launch_browser_helper.py"' in cmd_text
    assert r'"%FPAS_PYTHON%" "%FPAS_ROOT%\api_server.py"' in cmd_text
    assert r'if exist "%FPAS_STOPPING_FLAG%" (' in cmd_text
    assert "C:\\" not in cmd_text


def test_portable_start_vbs_launches_cmd_from_same_directory():
    vbs_text = build_windows_package.render_portable_start_vbs()

    assert vbs_text.splitlines()[0] == 'Set shell = CreateObject("WScript.Shell")'
    assert "start_fpas.cmd" in vbs_text
    assert "CurrentDirectory = appDir" in vbs_text
    assert 'shell.Run Chr(34) & appDir & "\\start_fpas.cmd" & Chr(34), 0, False' in vbs_text


def test_portable_launch_browser_helper_handles_default_and_managed_browsers():
    helper_text = build_windows_package.render_portable_launch_browser_helper_py()

    assert r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice" in helper_text
    assert "FPAS_BROWSER_EXE" in helper_text
    assert "FPAS_AUTO_OPEN_BROWSER" in helper_text
    assert r"BraveSoftware\Brave-Browser" in helper_text
    assert r"Chromium\Application\chrome.exe" in helper_text
    assert "_is_managed_browser" in helper_text
    assert '"--user-data-dir={profile_dir}"' in helper_text
    assert '["-new-instance", "-profile", str(profile_dir), url]' in helper_text
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in helper_text
    assert "_guard_managed_browser" in helper_text
    assert 'f"{os.getpid()}\\n{browser_pid}\\n{_normalize_path(browser_exe)}\\n{_normalize_path(str(browser_profile_dir))}\\nmanaged-job\\n"' in helper_text


def test_portable_stop_cmd_uses_pid_file_and_taskkill():
    cmd_text = build_windows_package.render_portable_stop_cmd()

    assert cmd_text.splitlines()[0] == "@echo off"
    assert r"stop_fpas_helper.py" in cmd_text
    assert r"runtime\python\python.exe" in cmd_text
    assert r'FPAS_RUN_DIR=%FPAS_ROOT%\run' in cmd_text
    assert r'del /f /q "%FPAS_RUN_DIR%\browser.pid" >nul 2>nul' in cmd_text
    assert r'del /f /q "%FPAS_RUN_DIR%\stopping.flag" >nul 2>nul' in cmd_text
    assert "powershell" not in cmd_text.lower()
    assert "C:\\" not in cmd_text


def test_render_readme_html_keeps_preview_style_and_basic_markdown():
    html_text = build_windows_package.render_readme_html(
        "# 标题\n\n> 引用\n\n- 项目一\n\n[链接](docs/a.md)\n",
        title="Doc Preview",
    )

    assert "<title>Doc Preview</title>" in html_text
    assert "radial-gradient(circle at top" in html_text
    assert "<h1>标题</h1>" in html_text
    assert "<blockquote><p>引用</p></blockquote>" in html_text
    assert "<li>项目一</li>" in html_text
    assert '<a href="docs/a.md">链接</a>' in html_text


def test_portable_stop_helper_targets_package_python_processes():
    helper_text = build_windows_package.render_portable_stop_helper_py()

    assert "CreateToolhelp32Snapshot" in helper_text
    assert 'runtime" / "python" / "python.exe' in helper_text
    assert 'browser_pid_file = root / "run" / "browser.pid"' in helper_text
    assert 'browser_profile_dir = root / "run" / "browser-profile"' in helper_text
    assert 'stopping_flag = root / "run" / "stopping.flag"' in helper_text
    assert '["taskkill", "/PID", str(pid), "/T", "/F"]' in helper_text
    assert '["wmic", "process", "get", "ProcessId,ExecutablePath,CommandLine", "/format:csv"]' in helper_text
    assert "cmd.exe" in helper_text
    assert 'browser_lines[4] == "managed-job"' in helper_text
    assert '_kill_pid_set(browser_pids, "受控浏览器")' in helper_text
    assert '_kill_pid_set(python_pids, "后端进程")' in helper_text
    assert "_remove_tree_with_retries" in helper_text
    assert "_collect_managed_browser_pids" in helper_text


def test_copy_portable_python_runtime_only_ignores_tools_at_runtime_root(monkeypatch):
    sandbox = PROJECT_ROOT / ".tmp_test_runtime_ignore"
    base_runtime = sandbox / "runtime"
    target_runtime = sandbox / "dist-runtime"
    shutil.rmtree(sandbox, ignore_errors=True)
    (base_runtime / "Lib" / "site-packages" / "pandas" / "core").mkdir(parents=True)
    (target_runtime / "Lib" / "encodings").mkdir(parents=True)

    monkeypatch.setattr(build_windows_package.sys, "base_prefix", str(base_runtime))
    monkeypatch.setattr(build_windows_package.sys, "prefix", str(base_runtime))

    def fake_copytree(src, dst, ignore=None):
        assert src == base_runtime
        assert dst == target_runtime
        assert ignore is not None
        root_ignored = ignore(str(base_runtime), ["Tools", "Lib", "__pycache__", "demo.pyc"])
        nested_ignored = ignore(
            str(base_runtime / "Lib" / "site-packages" / "pandas" / "core"),
            ["tools", "__pycache__", "frame.py"],
        )
        assert "Tools" in root_ignored
        assert "__pycache__" in root_ignored
        assert "demo.pyc" in root_ignored
        assert "tools" not in nested_ignored
        assert "__pycache__" in nested_ignored
        assert "frame.py" not in nested_ignored

    monkeypatch.setattr(build_windows_package, "_copytree", fake_copytree)

    try:
        build_windows_package._copy_portable_python_runtime(target_runtime)
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def test_win7_prerequisite_candidates_include_desktop_win7_patches():
    chrome_candidates = build_windows_package.WIN7_PREREQUISITE_CANDIDATES[
        "109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe"
    ]
    kb_candidates = build_windows_package.WIN7_PREREQUISITE_CANDIDATES[
        "Windows6.1-KB4490628-x64.msu"
    ]

    assert PROJECT_ROOT / "win7-patches" / "109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe" in chrome_candidates
    assert Path.home() / "Desktop" / "win7-patches" / "109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe" in chrome_candidates
    assert Path.home() / "OneDrive" / "Desktop" / "win7-patches" / "109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe" in chrome_candidates
    assert PROJECT_ROOT / "win7-patches" / "Windows6.1-KB4490628-x64.msu" in kb_candidates
    assert Path.home() / "Desktop" / "win7-patches" / "Windows6.1-KB4490628-x64.msu" in kb_candidates
    assert Path.home() / "OneDrive" / "Desktop" / "win7-patches" / "Windows6.1-KB4490628-x64.msu" in kb_candidates


def test_portable_tree_ignore_skips_python_cache_files():
    ignored = build_windows_package._portable_tree_ignore(
        "D:/sandbox/source",
        ["module.py", "__pycache__", "module.pyc", "module.pyo", "subdir"],
    )

    assert "__pycache__" in ignored
    assert "module.pyc" in ignored
    assert "module.pyo" in ignored
    assert "module.py" not in ignored
    assert "subdir" not in ignored


def test_remove_portable_bundle_caches_removes_python_cache_artifacts():
    sandbox = PROJECT_ROOT / ".tmp_test_bundle_cache_cleanup"
    shutil.rmtree(sandbox, ignore_errors=True)
    try:
        (sandbox / "pkg" / "__pycache__").mkdir(parents=True)
        (sandbox / "pkg" / "__pycache__" / "module.cpython-314.pyc").write_bytes(b"pyc")
        (sandbox / "pkg" / "module.pyc").write_bytes(b"pyc")
        (sandbox / "pkg" / "module.pyo").write_bytes(b"pyo")
        (sandbox / "pkg" / "module.py").write_text("print('ok')\n", encoding="utf-8")

        build_windows_package._remove_portable_bundle_caches(sandbox)

        assert not (sandbox / "pkg" / "__pycache__").exists()
        assert not (sandbox / "pkg" / "module.pyc").exists()
        assert not (sandbox / "pkg" / "module.pyo").exists()
        assert (sandbox / "pkg" / "module.py").exists()
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def test_portable_bundle_audit_manifest_covers_win7_runtime_risks():
    relpaths = build_windows_package._get_portable_bundle_audit_relpaths()
    modules = build_windows_package._get_portable_bundle_audit_modules()
    version_pins = build_windows_package.PORTABLE_BUNDLE_VERSION_PINS

    assert "runtime/python/python.exe" in relpaths
    assert "dashboard/dist/index.html" in relpaths
    assert "config/risk_thresholds.yaml" in relpaths
    assert "config/report_phrases.yaml" in relpaths
    assert "report_config/rules.yaml" in relpaths
    assert "templates/report_v3/base.html" in relpaths
    assert "knowledge/suspicion_rules.yaml" in relpaths
    assert "win7-prerequisites/Windows6.1-KB4490628-x64.msu" in relpaths
    assert "win7-prerequisites/109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe" in relpaths
    assert "websockets" in modules
    assert "api_server" in modules
    assert "uvicorn.protocols.websockets.websockets_impl" in modules
    assert version_pins["cryptography"] == "39.0.2"


def test_audit_portable_runtime_bundle_uses_packaged_python(monkeypatch, tmp_path):
    bundle_root = tmp_path / "bundle"
    runtime_python = bundle_root / "runtime" / "python" / "python.exe"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")
    recorded = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, check=None):
        recorded["cmd"] = cmd
        recorded["cwd"] = cwd
        recorded["capture_output"] = capture_output
        recorded["text"] = text
        recorded["check"] = check
        return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(build_windows_package.subprocess, "run", fake_run)

    build_windows_package._audit_portable_runtime_bundle(bundle_root)

    assert recorded["cmd"][0] == str(runtime_python)
    assert recorded["cmd"][1] == "-c"
    assert "cryptography" in recorded["cmd"][2]
    assert recorded["cwd"] == str(bundle_root)
    assert recorded["capture_output"] is True
    assert recorded["text"] is True
    assert recorded["check"] is False


def test_build_portable_runtime_bundle_runs_runtime_audit(monkeypatch):
    calls = []

    monkeypatch.setattr(
        build_windows_package, "_reset_directory", lambda path: calls.append(("reset", path))
    )
    monkeypatch.setattr(
        build_windows_package,
        "_copy_portable_source_tree",
        lambda root, dst: calls.append(("copy_source", root, dst)),
    )
    monkeypatch.setattr(
        build_windows_package,
        "_copy_portable_python_runtime",
        lambda path: calls.append(("copy_runtime", path)),
    )
    monkeypatch.setattr(
        build_windows_package,
        "_write_portable_launchers",
        lambda path: calls.append(("launchers", path)),
    )
    monkeypatch.setattr(
        build_windows_package,
        "_write_packaged_readme_html",
        lambda root, dst: calls.append(("readme", root, dst)),
    )
    monkeypatch.setattr(
        build_windows_package,
        "_copy_win7_prerequisites",
        lambda path: calls.append(("prereq", path)),
    )
    monkeypatch.setattr(
        build_windows_package,
        "_remove_portable_bundle_caches",
        lambda path: calls.append(("cleanup", path)),
    )
    monkeypatch.setattr(
        build_windows_package,
        "_audit_portable_runtime_bundle",
        lambda path: calls.append(("audit", path)),
    )

    build_windows_package.build_portable_runtime_bundle()

    assert calls[-1] == ("audit", build_windows_package.DIST_DIR)
