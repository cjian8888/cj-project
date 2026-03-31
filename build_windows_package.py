#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 离线单机包构建入口。"""

from __future__ import annotations

import argparse
import html
import importlib.util
import os
import re
import subprocess
import sys
import sysconfig
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DASHBOARD_DIST_DIR = DASHBOARD_DIR / "dist"
SPEC_FILE = PROJECT_ROOT / "fpas_windows.spec"
DIST_DIR = PROJECT_ROOT / "dist" / "fpas-offline"
PORTABLE_RUNTIME_DIR = DIST_DIR / "runtime" / "python"
PORTABLE_SOURCE_DIRS = [
    Path("adapters"),
    Path("classifiers"),
    Path("config"),
    Path("dashboard") / "dist",
    Path("detectors"),
    Path("docs") / "assets",
    Path("knowledge"),
    Path("learners"),
    Path("report_config"),
    Path("schemas"),
    Path("templates"),
    Path("utils"),
]
PORTABLE_ROOT_FILE_PATTERNS = ("*.py", "*.md", "*.txt", "*.json", "*.yaml", "*.yml")
PORTABLE_ROOT_SKIP_NAMES = {"dist", "build", ".git", ".pytest_cache", "dashboard"}
PORTABLE_RUNTIME_TOP_LEVEL_SKIP_NAMES = {
    "Doc",
    "docs",
    "Tools",
    "test",
    "tests",
    "turtledemo",
    "idlelib",
}
VIS_NETWORK_JS = (
    DASHBOARD_DIR
    / "node_modules"
    / "vis-network"
    / "standalone"
    / "umd"
    / "vis-network.min.js"
)
TARGET_WINDOWS_PYTHON = (3, 8)
PINNED_PYINSTALLER_VERSION = "5.13.2"
REQUIRED_RUNTIME_MODULES = ("websockets",)
PORTABLE_BUNDLE_AUDIT_MODULES = (
    "api_server",
    "yaml",
    "pandas",
    "openpyxl",
    "pdfplumber",
    "neo4j",
    "jinja2",
    "pydantic",
    "uvicorn",
    "uvicorn.protocols.websockets.websockets_impl",
)
PORTABLE_BUNDLE_VERSION_PINS: Dict[str, str] = {
    "cryptography": "39.0.2",
}
LAZY_RUNTIME_MODULES = [
    "aml_analyzer",
    "asset_analyzer",
    "asset_extractor",
    "bank_account_info_extractor",
    "behavioral_profiler",
    "clue_aggregator",
    "cohabitation_extractor",
    "company_info_extractor",
    "credit_report_extractor",
    "data_cleaner",
    "data_extractor",
    "data_validator",
    "family_analyzer",
    "family_assets_helper",
    "family_finance",
    "file_categorizer",
    "financial_profiler",
    "flight_extractor",
    "flow_visualizer",
    "fund_penetration",
    "hotel_extractor",
    "immigration_extractor",
    "income_analyzer",
    "income_expense_match_analyzer",
    "investigation_report_builder",
    "loan_analyzer",
    "logging_config",
    "ml_analyzer",
    "multi_source_correlator",
    "pboc_account_extractor",
    "personal_fund_feature_analyzer",
    "professional_finance_analyzer",
    "railway_extractor",
    "real_salary_income_analyzer",
    "related_party_analyzer",
    "report_config.primary_targets_service",
    "report_generator",
    "report_quality_guard",
    "report_text_formatter",
    "salary_analyzer",
    "securities_extractor",
    "specialized_reports",
    "suspicion_detector",
    "suspicion_engine",
    "tax_info_extractor",
    "time_series_analyzer",
    "vehicle_extractor",
    "wallet_data_extractor",
    "wallet_report_builder",
    "wallet_risk_analyzer",
    "wealth_product_extractor",
]
DEFAULT_BUNDLE_MODE = "portable-runtime"
BUNDLE_MODES = ("portable-runtime", "pyinstaller")
WIN7_PREREQUISITE_DIR_NAME = "win7-prerequisites"
WIN7_PREREQUISITE_CANDIDATES = {
    "Windows6.1-KB4490628-x64.msu": [
        PROJECT_ROOT / "win7-patches" / "Windows6.1-KB4490628-x64.msu",
        Path.home() / "Desktop" / "win7-patches" / "Windows6.1-KB4490628-x64.msu",
        Path.home()
        / "OneDrive"
        / "Desktop"
        / "win7-patches"
        / "Windows6.1-KB4490628-x64.msu",
        PROJECT_ROOT
        / ".tmp_win7_bootstrap"
        / "patches-min"
        / "Windows6.1-KB4490628-x64.msu",
        PROJECT_ROOT / ".tmp_ssh_bootstrap" / "serve" / "Windows6.1-KB4490628-x64.msu",
    ],
    "Windows6.1-KB4474419-v3-x64.msu": [
        PROJECT_ROOT / "win7-patches" / "Windows6.1-KB4474419-v3-x64.msu",
        Path.home() / "Desktop" / "win7-patches" / "Windows6.1-KB4474419-v3-x64.msu",
        Path.home()
        / "OneDrive"
        / "Desktop"
        / "win7-patches"
        / "Windows6.1-KB4474419-v3-x64.msu",
        PROJECT_ROOT
        / ".tmp_win7_bootstrap"
        / "patches-min"
        / "Windows6.1-KB4474419-v3-x64.msu",
        PROJECT_ROOT
        / ".tmp_ssh_bootstrap"
        / "serve"
        / "Windows6.1-KB4474419-v3-x64.msu",
    ],
    "Windows6.1-KB2533623-x64.msu": [
        PROJECT_ROOT / "win7-patches" / "Windows6.1-KB2533623-x64.msu",
        Path.home() / "Desktop" / "win7-patches" / "Windows6.1-KB2533623-x64.msu",
        Path.home()
        / "OneDrive"
        / "Desktop"
        / "win7-patches"
        / "Windows6.1-KB2533623-x64.msu",
        PROJECT_ROOT
        / ".tmp_win7_bootstrap"
        / "patches-min"
        / "Windows6.1-KB2533623-x64.msu",
        PROJECT_ROOT
        / ".tmp_win7_bootstrap"
        / "patches"
        / "Windows6.1-KB2533623-x64.msu",
        PROJECT_ROOT / ".tmp_ssh_bootstrap" / "serve" / "Windows6.1-KB2533623-x64.msu",
    ],
    "Windows6.1-KB2999226-x64.msu": [
        PROJECT_ROOT / "win7-patches" / "Windows6.1-KB2999226-x64.msu",
        Path.home() / "Desktop" / "win7-patches" / "Windows6.1-KB2999226-x64.msu",
        Path.home()
        / "OneDrive"
        / "Desktop"
        / "win7-patches"
        / "Windows6.1-KB2999226-x64.msu",
        PROJECT_ROOT
        / ".tmp_win7_bootstrap"
        / "patches-min"
        / "Windows6.1-KB2999226-x64.msu",
        PROJECT_ROOT
        / ".tmp_win7_bootstrap"
        / "patches"
        / "Windows6.1-KB2999226-x64.msu",
        PROJECT_ROOT / ".tmp_ssh_bootstrap" / "serve" / "Windows6.1-KB2999226-x64.msu",
    ],
    "109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe": [
        PROJECT_ROOT
        / "win7-patches"
        / "109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe",
        Path.home()
        / "Desktop"
        / "win7-patches"
        / "109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe",
        Path.home()
        / "OneDrive"
        / "Desktop"
        / "win7-patches"
        / "109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe",
        Path.home() / "Downloads" / "109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe",
    ],
}


def run(cmd: Sequence[str], cwd: Optional[Path] = None) -> None:
    """运行命令并在失败时中断。"""
    workdir = cwd or PROJECT_ROOT
    print(f"[build] cwd={workdir} cmd={' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(workdir), check=True)


def _resolve_npm_command() -> List[str]:
    """解析适用于当前平台的 npm 可执行文件。"""
    candidates = ["npm.cmd", "npm"] if sys.platform == "win32" else ["npm"]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]
    raise SystemExit("未检测到 npm，可先确认 Node.js 已安装且 npm 已加入 PATH。")


def _python_version_text() -> str:
    return ".".join(str(part) for part in sys.version_info[:3])


def get_pyinstaller_datas(project_root: Optional[Path] = None) -> List[Tuple[str, str]]:
    """返回 Windows one-folder 包必须携带的运行时资源。"""
    root = project_root or PROJECT_ROOT
    return [
        (str(root / "README.md"), "."),
        (str(root / "docs" / "assets"), "docs/assets"),
        (str(root / "utils.py"), "."),
        (str(root / "config"), "config"),
        (str(root / "knowledge"), "knowledge"),
        (str(root / "report_config"), "report_config"),
        (str(root / "templates"), "templates"),
        (str(root / "dashboard" / "dist"), "dashboard/dist"),
        (
            str(
                root
                / "dashboard"
                / "node_modules"
                / "vis-network"
                / "standalone"
                / "umd"
                / "vis-network.min.js"
            ),
            "dashboard/node_modules/vis-network/standalone/umd",
        ),
    ]


def get_pyinstaller_hiddenimports() -> List[str]:
    """返回 PyInstaller 需要显式声明的隐藏依赖。"""
    return LAZY_RUNTIME_MODULES + [
        "chinese_calendar",
        "neo4j",
        "websockets",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan.on",
    ]


def get_portable_source_dirs(
    project_root: Optional[Path] = None,
) -> List[Tuple[str, str]]:
    """返回 portable runtime bundle 需要复制的目录映射。"""
    root = project_root or PROJECT_ROOT
    return [
        (str(root / rel_path), rel_path.as_posix()) for rel_path in PORTABLE_SOURCE_DIRS
    ]


def render_portable_start_cmd() -> str:
    """生成 Win7 交付包的显式启动脚本。"""
    lines = [
        "@echo off",
        "setlocal",
        'cd /d "%~dp0"',
        'set "FPAS_ROOT=%~dp0"',
        'if "%FPAS_ROOT:~-1%"=="\\" set "FPAS_ROOT=%FPAS_ROOT:~0,-1%"',
        'set "FPAS_RUN_DIR=%FPAS_ROOT%\\run"',
        'if not exist "%FPAS_RUN_DIR%" mkdir "%FPAS_RUN_DIR%" >nul 2>nul',
        'set "FPAS_SERVER_PID_FILE=%FPAS_RUN_DIR%\\server.pid"',
        'set "FPAS_BROWSER_PID_FILE=%FPAS_RUN_DIR%\\browser.pid"',
        'set "FPAS_BROWSER_PROFILE_DIR=%FPAS_RUN_DIR%\\browser-profile"',
        'set "FPAS_STOPPING_FLAG=%FPAS_RUN_DIR%\\stopping.flag"',
        'del /f /q "%FPAS_SERVER_PID_FILE%" >nul 2>nul',
        'del /f /q "%FPAS_BROWSER_PID_FILE%" >nul 2>nul',
        'del /f /q "%FPAS_STOPPING_FLAG%" >nul 2>nul',
        'set "FPAS_DELIVERY_MODE=1"',
        'if not defined FPAS_AUTO_OPEN_BROWSER set "FPAS_AUTO_OPEN_BROWSER=1"',
        'set "FPAS_PYTHON=%FPAS_ROOT%\\runtime\\python\\python.exe"',
        'if not exist "%FPAS_PYTHON%" (',
        'echo [FPAS] 缺少内置 Python 运行时: "%FPAS_PYTHON%"',
        "pause",
        "exit /b 1",
        ")",
        'set "FPAS_STARTUP_DIAGNOSTICS_ROOT=%FPAS_ROOT%"',
        'set "PYTHONPATH=%FPAS_ROOT%"',
        'set "PATH=%FPAS_ROOT%\\runtime\\python;%FPAS_ROOT%\\runtime\\python\\DLLs;%FPAS_ROOT%\\runtime\\python\\Scripts;%PATH%"',
        # 关键修复：传递所有必要的环境变量给浏览器助手
        'if not defined FPAS_PORT set "FPAS_PORT=8000"',
        'start "" /b cmd /c "set FPAS_ROOT=%FPAS_ROOT% && set FPAS_RUN_DIR=%FPAS_RUN_DIR% && set FPAS_SERVER_PID_FILE=%FPAS_SERVER_PID_FILE% && set FPAS_BROWSER_PID_FILE=%FPAS_BROWSER_PID_FILE% && set FPAS_BROWSER_PROFILE_DIR=%FPAS_BROWSER_PROFILE_DIR% && set FPAS_STOPPING_FLAG=%FPAS_STOPPING_FLAG% && set FPAS_DELIVERY_MODE=%FPAS_DELIVERY_MODE% && set FPAS_AUTO_OPEN_BROWSER=%FPAS_AUTO_OPEN_BROWSER% && set FPAS_PORT=%FPAS_PORT% && set FPAS_STARTUP_DIAGNOSTICS_ROOT=%FPAS_STARTUP_DIAGNOSTICS_ROOT% && set PYTHONPATH=%PYTHONPATH% && set PATH=%PATH% && "%FPAS_PYTHON%" "%FPAS_ROOT%\\launch_browser_helper.py""',
        '"%FPAS_PYTHON%" "%FPAS_ROOT%\\api_server.py"',
        'set "EXIT_CODE=%ERRORLEVEL%"',
        'del /f /q "%FPAS_SERVER_PID_FILE%" >nul 2>nul',
        'del /f /q "%FPAS_BROWSER_PID_FILE%" >nul 2>nul',
        'if exist "%FPAS_STOPPING_FLAG%" (',
        'del /f /q "%FPAS_STOPPING_FLAG%" >nul 2>nul',
        ") else (",
        'if not "%EXIT_CODE%"=="0" (',
        "echo.",
        "echo [FPAS] 服务异常退出，退出码=%EXIT_CODE%",
        "pause",
        ")",
        ")",
        "exit /b %EXIT_CODE%",
    ]
    return "\n".join(lines) + "\n"


def render_portable_start_vbs() -> str:
    """生成静默启动包装器，便于双击时隐藏 cmd 窗口。"""
    lines = [
        'Set shell = CreateObject("WScript.Shell")',
        'Set fso = CreateObject("Scripting.FileSystemObject")',
        "appDir = fso.GetParentFolderName(WScript.ScriptFullName)",
        "shell.CurrentDirectory = appDir",
        'shell.Run Chr(34) & appDir & "\\start_fpas.cmd" & Chr(34), 0, False',
    ]
    return "\n".join(lines) + "\n"


def render_portable_launch_browser_helper_py() -> str:
    """生成受控浏览器启动辅助脚本。"""
    return '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launch a manageable browser instance for the packaged FPAS dashboard."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
CreateJobObjectW = kernel32.CreateJobObjectW
CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
CreateJobObjectW.restype = wintypes.HANDLE
SetInformationJobObject = kernel32.SetInformationJobObject
SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
SetInformationJobObject.restype = wintypes.BOOL
AssignProcessToJobObject = kernel32.AssignProcessToJobObject
AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
AssignProcessToJobObject.restype = wintypes.BOOL
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE
CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


def _normalize_path(value: str) -> str:
    return os.path.normcase(os.path.abspath(value))


def _extract_executable(command: str) -> str | None:
    text = str(command or "").strip()
    if not text:
        return None
    match = re.match(
        r'^\\s*(?:"([^"]+?\\.exe)"|(.+?\\.exe))(?:\\s|$)',
        text,
        re.IGNORECASE,
    )
    if match:
        candidate = (match.group(1) or match.group(2) or "").strip()
        return candidate or None
    return None


def _resolve_default_browser_executable() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except Exception:
        return None

    registry_candidates = []
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice",
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
            if prog_id:
                registry_candidates.extend(
                    [
                        (winreg.HKEY_CLASSES_ROOT, rf"{prog_id}\\shell\\open\\command"),
                        (winreg.HKEY_CURRENT_USER, rf"Software\\Classes\\{prog_id}\\shell\\open\\command"),
                    ]
                )
    except OSError:
        pass

    registry_candidates.extend(
        [
            (winreg.HKEY_CLASSES_ROOT, r"http\\shell\\open\\command"),
            (winreg.HKEY_CLASSES_ROOT, r"https\\shell\\open\\command"),
        ]
    )

    for hive, subkey in registry_candidates:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                command, _ = winreg.QueryValueEx(key, "")  # type: ignore[arg-type]
        except OSError:
            continue
        executable = _extract_executable(command)
        if executable and os.path.exists(executable):
            return executable
    return None


def _known_browser_candidates() -> list[str]:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    return [
        r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        r"C:\\Program Files\\Mozilla Firefox\\firefox.exe",
        r"C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe",
        r"C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
        r"C:\\Program Files (x86)\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
        r"C:\\Program Files\\Chromium\\Application\\chrome.exe",
        r"C:\\Program Files (x86)\\Chromium\\Application\\chrome.exe",
        os.path.join(local_app_data, r"Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(local_app_data, r"Microsoft\\Edge\\Application\\msedge.exe"),
        os.path.join(local_app_data, r"Mozilla Firefox\\firefox.exe"),
        os.path.join(local_app_data, r"BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
        os.path.join(local_app_data, r"Chromium\\Application\\chrome.exe"),
    ]


def _iter_browser_candidates() -> list[str]:
    override = os.environ.get("FPAS_BROWSER_EXE", "").strip()
    default_browser = _resolve_default_browser_executable()
    candidates = [override, default_browser, *_known_browser_candidates()]
    unique_candidates = []
    seen = set()
    for candidate in candidates:
        normalized = _normalize_path(candidate) if candidate else ""
        if not candidate or normalized in seen or not os.path.exists(candidate):
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)
    return unique_candidates


def _is_managed_browser(browser_exe: str) -> bool:
    exe_name = Path(browser_exe).name.lower()
    return "firefox" in exe_name or any(
        token in exe_name for token in ("chrome", "msedge", "chromium", "brave")
    )


def _close_handle(handle: int | None) -> None:
    if handle:
        CloseHandle(handle)


def _create_kill_on_close_job() -> int | None:
    if sys.platform != "win32":
        return None
    job_handle = CreateJobObjectW(None, None)
    if not job_handle:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not SetInformationJobObject(
        job_handle,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        _close_handle(job_handle)
        return None
    return int(job_handle)


def _assign_process_to_job(job_handle: int | None, pid: int) -> bool:
    if not job_handle or pid <= 0:
        return False
    process_handle = OpenProcess(
        PROCESS_SET_QUOTA | PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid,
    )
    if not process_handle:
        return False
    try:
        return bool(AssignProcessToJobObject(job_handle, process_handle))
    finally:
        _close_handle(process_handle)


def _write_managed_browser_pid_file(
    browser_pid_file: Path,
    browser_pid: int,
    browser_exe: str,
    browser_profile_dir: Path,
) -> None:
    browser_pid_file.parent.mkdir(parents=True, exist_ok=True)
    browser_pid_file.write_text(
        f"{os.getpid()}\\n{browser_pid}\\n{_normalize_path(browser_exe)}\\n{_normalize_path(str(browser_profile_dir))}\\nmanaged-job\\n",
        encoding="utf-8",
    )


def _guard_managed_browser(
    process: subprocess.Popen,
    job_handle: int,
    browser_pid_file: Path,
    browser_exe: str,
    browser_profile_dir: Path,
    stopping_flag: Path,
) -> int:
    _write_managed_browser_pid_file(
        browser_pid_file,
        int(process.pid),
        browser_exe,
        browser_profile_dir,
    )
    try:
        while True:
            if process.poll() is not None:
                return int(process.returncode or 0)
            if stopping_flag.exists():
                return 0
            time.sleep(0.5)
    finally:
        try:
            lines = [
                line.strip()
                for line in browser_pid_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except OSError:
            lines = []
        if lines:
            try:
                recorded_guard_pid = int(lines[0])
            except ValueError:
                recorded_guard_pid = 0
            if recorded_guard_pid == os.getpid():
                try:
                    browser_pid_file.unlink()
                except OSError:
                    pass
        _close_handle(job_handle)


def _launch_managed_browser(browser_exe: str, url: str, profile_dir: Path) -> tuple[int | None, subprocess.Popen | None, int | None]:
    if not _is_managed_browser(browser_exe):
        return None, None, None

    exe_name = Path(browser_exe).name.lower()
    args = [browser_exe]

    if "firefox" in exe_name:
        shutil.rmtree(profile_dir, ignore_errors=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        args.extend(["-new-instance", "-profile", str(profile_dir), url])
    else:
        shutil.rmtree(profile_dir, ignore_errors=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        # Win7兼容: 使用 --no-first-run 和 --no-default-browser-check 避免启动问题
        args.extend(
            [
                f"--user-data-dir={profile_dir}",
                "--new-window",
                "--no-first-run",
                "--no-default-browser-check",
                url,
            ]
        )

    try:
        # Win7兼容: 不使用CREATE_NO_WINDOW，让浏览器正常显示
        creationflags = 0
        process = subprocess.Popen(args, creationflags=creationflags)
        job_handle = _create_kill_on_close_job()
        if job_handle and not _assign_process_to_job(job_handle, int(process.pid)):
            _close_handle(job_handle)
            job_handle = None
        return int(process.pid), process, job_handle
    except Exception as e:
        # 记录启动失败
        try:
            root = Path(__file__).resolve().parent
            log_path = root / "run" / "browser_launch_error.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Failed to launch {browser_exe}: {e}\\n")
                f.write(f"  Args: {args}\\n")
        except:
            pass
        return None, None, None


def _open_url_fallback(url: str, browser_exe: str | None = None) -> None:
    """Win7/Win11兼容的回退打开方式"""
    # Win7兼容: 不使用CREATE_NO_WINDOW
    creationflags = 0
    
    if browser_exe and os.path.exists(browser_exe):
        try:
            subprocess.Popen([browser_exe, url], creationflags=creationflags)
            return
        except Exception as e:
            # 记录错误
            try:
                root = Path(__file__).resolve().parent
                log_path = root / "run" / "browser_launch_error.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fallback browser failed: {e}\\n")
            except:
                pass
    
    # 使用系统默认方式打开
    try:
        subprocess.Popen(["cmd", "/c", "start", "", url], creationflags=creationflags)
    except Exception as e:
        try:
            root = Path(__file__).resolve().parent
            log_path = root / "run" / "browser_launch_error.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] System start command failed: {e}\\n")
        except:
            pass


def _log_debug(message: str) -> None:
    """记录调试日志"""
    try:
        root = Path(__file__).resolve().parent
        log_path = root / "run" / "browser_launch_debug.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\\n")
    except:
        pass


def main() -> int:
    root = Path(__file__).resolve().parent
    browser_pid_file = Path(os.environ.get("FPAS_BROWSER_PID_FILE", "") or root / "run" / "browser.pid")
    browser_profile_dir = Path(os.environ.get("FPAS_BROWSER_PROFILE_DIR", "") or root / "run" / "browser-profile")
    stopping_flag = Path(os.environ.get("FPAS_STOPPING_FLAG", "") or root / "run" / "stopping.flag")
    port = str(os.environ.get("FPAS_PORT", "8000") or "8000").strip() or "8000"
    dashboard_url = f"http://127.0.0.1:{port}/dashboard/"
    auto_open_browser = str(os.environ.get("FPAS_AUTO_OPEN_BROWSER", "1") or "1").strip().lower()

    _log_debug(f"Browser helper started")
    _log_debug(f"PORT={port}, AUTO_OPEN={auto_open_browser}")
    _log_debug(f"URL={dashboard_url}")

    if auto_open_browser in {"0", "false", "no", "off"}:
        _log_debug("Auto open disabled, exiting")
        return 0

    # 等待服务器启动
    _log_debug("Waiting for server to start...")
    for i in range(60):
        try:
            import urllib.request

            with urllib.request.urlopen(dashboard_url, timeout=2) as response:
                if response.getcode() == 200:
                    _log_debug(f"Server ready after {i+1} attempts")
                    break
        except Exception as e:
            if i == 0 or i == 30:  # 只在开始和中间记录一次
                _log_debug(f"Server not ready yet (attempt {i+1}): {e}")
            time.sleep(0.5)
    else:
        _log_debug("Server failed to start within timeout")
        return 0

    # 获取浏览器候选列表
    candidates = _iter_browser_candidates()
    _log_debug(f"Found {len(candidates)} browser candidates: {candidates}")

    browser_pid = None
    fallback_browser_exe = None
    for browser_exe in candidates:
        if fallback_browser_exe is None:
            fallback_browser_exe = browser_exe
        _log_debug(f"Trying browser: {browser_exe}")
        try:
            browser_pid, process, job_handle = _launch_managed_browser(
                browser_exe,
                dashboard_url,
                browser_profile_dir,
            )
            _log_debug(f"Launch result: pid={browser_pid}, process={process is not None}, job={job_handle is not None}")
        except Exception as e:
            _log_debug(f"Launch exception: {e}")
            browser_pid = None
            process = None
            job_handle = None
        if browser_pid:
            if process is not None and job_handle is not None:
                _log_debug(f"Using managed browser with job object")
                return _guard_managed_browser(
                    process,
                    job_handle,
                    browser_pid_file,
                    browser_exe,
                    browser_profile_dir,
                    stopping_flag,
                )
            _log_debug(f"Browser launched without job object, writing pid file")
            browser_pid_file.parent.mkdir(parents=True, exist_ok=True)
            browser_pid_file.write_text(
                f"{browser_pid}\\n{_normalize_path(browser_exe)}\\n{_normalize_path(str(browser_profile_dir))}\\n",
                encoding="utf-8",
            )
            return 0

    _log_debug(f"All managed browsers failed, using fallback")
    _open_url_fallback(dashboard_url, fallback_browser_exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def render_portable_stop_cmd() -> str:
    """生成 Win7 交付包的一键停止脚本。"""
    lines = [
        "@echo off",
        "setlocal",
        'cd /d "%~dp0"',
        'set "FPAS_ROOT=%~dp0"',
        'if "%FPAS_ROOT:~-1%"=="\\" set "FPAS_ROOT=%FPAS_ROOT:~0,-1%"',
        'set "FPAS_PYTHON=%FPAS_ROOT%\\runtime\\python\\python.exe"',
        'set "FPAS_STOP_HELPER=%FPAS_ROOT%\\stop_fpas_helper.py"',
        'set "FPAS_RUN_DIR=%FPAS_ROOT%\\run"',
        'if not exist "%FPAS_PYTHON%" (',
        'echo [FPAS] 缺少内置 Python 运行时: "%FPAS_PYTHON%"',
        "pause",
        "exit /b 1",
        ")",
        'if not exist "%FPAS_STOP_HELPER%" (',
        'echo [FPAS] 缺少停止脚本: "%FPAS_STOP_HELPER%"',
        "pause",
        "exit /b 1",
        ")",
        '"%FPAS_PYTHON%" "%FPAS_STOP_HELPER%"',
        'set "EXIT_CODE=%ERRORLEVEL%"',
        'del /f /q "%FPAS_RUN_DIR%\\server.pid" >nul 2>nul',
        'del /f /q "%FPAS_RUN_DIR%\\browser.pid" >nul 2>nul',
        'del /f /q "%FPAS_RUN_DIR%\\stopping.flag" >nul 2>nul',
        'if not "%EXIT_CODE%"=="0" (',
        "echo.",
        "echo [FPAS] 停止脚本执行失败，退出码=%EXIT_CODE%",
        "pause",
        ")",
        "exit /b %EXIT_CODE%",
    ]
    return "\n".join(lines) + "\n"


def render_portable_stop_helper_py() -> str:
    """生成不依赖 PowerShell 的停止辅助脚本。"""
    return '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stop FPAS package processes for the current delivery root."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
CreateToolhelp32Snapshot.restype = wintypes.HANDLE
Process32FirstW = kernel32.Process32FirstW
Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
Process32FirstW.restype = wintypes.BOOL
Process32NextW = kernel32.Process32NextW
Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
Process32NextW.restype = wintypes.BOOL
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE
QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
QueryFullProcessImageNameW.restype = wintypes.BOOL
CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL


def _normalize_path(value: str) -> str:
    return os.path.normcase(os.path.abspath(value))


def _normalize_command_text(value: str) -> str:
    return str(value or "").strip().lower().replace("/", "\\\\")


def _iter_processes():
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        has_entry = Process32FirstW(snapshot, ctypes.byref(entry))
        while has_entry:
            yield {
                "pid": int(entry.th32ProcessID),
                "parent_pid": int(entry.th32ParentProcessID),
                "name": entry.szExeFile,
            }
            has_entry = Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        CloseHandle(snapshot)


def _query_process_image_path(pid: int) -> str | None:
    handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        CloseHandle(handle)


def _kill_pid(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _iter_wmic_process_rows():
    try:
        result = subprocess.run(
            ["wmic", "process", "get", "ProcessId,ExecutablePath,CommandLine", "/format:csv"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []

    output_text = str(result.stdout or "").strip()
    if not output_text:
        return []

    rows = []
    reader = csv.DictReader(io.StringIO(output_text))
    for row in reader:
        if not row:
            continue
        pid_text = str(row.get("ProcessId", "") or "").strip()
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        rows.append(
            {
                "pid": pid,
                "command_line": str(row.get("CommandLine", "") or "").strip(),
                "executable_path": str(row.get("ExecutablePath", "") or "").strip(),
            }
        )
    return rows


def _collect_managed_browser_pids(browser_image_hint: str, browser_profile_hint: str) -> set[int]:
    """收集受控浏览器进程PID，支持多种检测方式"""
    normalized_image_hint = _normalize_path(browser_image_hint) if browser_image_hint else ""
    normalized_profile_hint = _normalize_command_text(browser_profile_hint)
    browser_pids: set[int] = set()

    # 方法1: 使用WMIC查询
    try:
        for row in _iter_wmic_process_rows():
            executable_path = str(row.get("executable_path", "") or "").strip()
            if not executable_path:
                continue
            normalized_executable_path = _normalize_path(executable_path)

            # 检查可执行文件路径匹配
            image_match = False
            if normalized_image_hint:
                image_match = normalized_executable_path == normalized_image_hint
            else:
                # 如果没有指定image_hint，匹配常见浏览器
                exe_lower = normalized_executable_path.lower()
                image_match = any(x in exe_lower for x in ["chrome", "msedge", "firefox", "brave", "chromium"])

            if not image_match:
                continue

            # 检查命令行参数匹配
            command_line = str(row.get("command_line", "") or "")
            normalized_command_line = _normalize_command_text(command_line)
            if normalized_profile_hint and normalized_profile_hint not in normalized_command_line:
                continue

            browser_pids.add(int(row["pid"]))
    except Exception as e:
        print(f"[FPAS] WMIC查询浏览器进程失败: {e}")

    # 方法2: 使用Toolhelp32遍历进程（备用方案）
    if not browser_pids and normalized_image_hint:
        try:
            for proc in _iter_processes():
                pid = proc["pid"]
                image_path = _query_process_image_path(pid)
                if image_path and _normalize_path(image_path) == normalized_image_hint:
                    browser_pids.add(pid)
        except Exception as e:
            print(f"[FPAS] Toolhelp32查询浏览器进程失败: {e}")

    return browser_pids


def _kill_pid_set(pids: set[int], label: str) -> None:
    remaining_pids = {int(pid) for pid in pids if int(pid) > 0}
    if not remaining_pids:
        return

    for attempt in range(10):  # 增加重试次数到10次
        active_pids = []
        for pid in sorted(remaining_pids):
            if _query_process_image_path(pid):
                active_pids.append(pid)
        if not active_pids:
            return
        for pid in active_pids:
            print(f"[FPAS] 正在结束{label} PID={pid} (attempt {attempt + 1})")
            _kill_pid(pid)
            # Win7兼容: 尝试使用taskkill /IM按名称杀进程
            if label == "受控浏览器":
                try:
                    image_path = _query_process_image_path(pid)
                    if image_path:
                        exe_name = Path(image_path).name
                        subprocess.run(
                            ["taskkill", "/IM", exe_name, "/T", "/F"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                except:
                    pass
        time.sleep(1.0 if attempt < 5 else 2.0)  # 前5次等1秒，后5次等2秒
        remaining_pids = set(active_pids)


def _remove_tree_with_retries(path: Path, attempts: int = 10, sleep_s: float = 0.5) -> bool:
    if not path.exists():
        return True
    for _ in range(max(attempts, 1)):
        try:
            shutil.rmtree(path)
            return True
        except OSError:
            time.sleep(sleep_s)
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def main() -> int:
    root = Path(__file__).resolve().parent
    runtime_python = _normalize_path(str(root / "runtime" / "python" / "python.exe"))
    server_pid_file = root / "run" / "server.pid"
    browser_pid_file = root / "run" / "browser.pid"
    browser_profile_dir = root / "run" / "browser-profile"
    stopping_flag = root / "run" / "stopping.flag"
    self_pid = os.getpid()
    processes = list(_iter_processes())
    process_map = {proc["pid"]: proc for proc in processes}
    python_pids: set[int] = set()
    browser_pids: set[int] = set()
    cmd_pids: set[int] = set()

    stopping_flag.parent.mkdir(parents=True, exist_ok=True)
    try:
        stopping_flag.write_text("stopping\\n", encoding="ascii")
    except OSError:
        pass

    for proc in processes:
        pid = proc["pid"]
        if pid == self_pid:
            continue
        image_path = _query_process_image_path(pid)
        if image_path is None:
            continue
        if _normalize_path(image_path) != runtime_python:
            continue
        python_pids.add(pid)
        parent = process_map.get(proc["parent_pid"])
        if parent and str(parent["name"]).lower() == "cmd.exe":
            cmd_pids.add(parent["pid"])

    if server_pid_file.exists():
        try:
            recorded_pid = int(server_pid_file.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            recorded_pid = 0
        if recorded_pid and recorded_pid != self_pid:
            python_pids.add(recorded_pid)

    browser_guard_pid = 0
    browser_pid = 0
    browser_image_hint = ""
    browser_profile_hint = _normalize_path(str(browser_profile_dir))
    if browser_pid_file.exists():
        try:
            browser_lines = [line.strip() for line in browser_pid_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError:
            browser_lines = []
        if len(browser_lines) >= 5 and browser_lines[4] == "managed-job":
            try:
                browser_guard_pid = int(browser_lines[0])
            except ValueError:
                browser_guard_pid = 0
            try:
                browser_pid = int(browser_lines[1])
            except ValueError:
                browser_pid = 0
            if len(browser_lines) > 2:
                browser_image_hint = _normalize_path(browser_lines[2])
            if len(browser_lines) > 3:
                browser_profile_hint = _normalize_path(browser_lines[3])
        elif browser_lines:
            try:
                browser_pid = int(browser_lines[0])
            except ValueError:
                browser_pid = 0
            if len(browser_lines) > 1:
                browser_image_hint = _normalize_path(browser_lines[1])
            if len(browser_lines) > 2:
                browser_profile_hint = _normalize_path(browser_lines[2])
        if browser_guard_pid and browser_guard_pid != self_pid:
            python_pids.add(browser_guard_pid)
        if browser_pid and browser_pid != self_pid:
            current_image_path = _query_process_image_path(browser_pid)
            if current_image_path:
                normalized_image_path = _normalize_path(current_image_path)
                if not browser_image_hint or normalized_image_path == browser_image_hint:
                    browser_pids.add(browser_pid)
            else:
                # Win7兼容: 即使无法查询进程路径，也尝试杀死记录的PID
                print(f"[FPAS] 无法查询浏览器进程 {browser_pid} 的路径，将尝试强制结束")
                browser_pids.add(browser_pid)

    if not python_pids and not browser_pids and not cmd_pids:
        print("[FPAS] 未发现当前交付包的运行中后端进程")
        return 0

    _kill_pid_set(python_pids, "后端进程")
    time.sleep(1.0)
    if browser_image_hint or browser_profile_hint:
        browser_pids.update(_collect_managed_browser_pids(browser_image_hint, browser_profile_hint))
    browser_pids.discard(self_pid)
    _kill_pid_set(browser_pids, "受控浏览器")
    _kill_pid_set(cmd_pids, "关联启动窗口")

    # 最后手段：尝试按名称杀死所有相关浏览器进程
    if browser_image_hint:
        try:
            exe_name = Path(browser_image_hint).name
            print(f"[FPAS] 最后手段：尝试按名称杀死 {exe_name}")
            subprocess.run(
                ["taskkill", "/IM", exe_name, "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception as e:
            print(f"[FPAS] 按名称杀死浏览器进程失败: {e}")

    if server_pid_file.exists():
        try:
            server_pid_file.unlink()
        except OSError:
            pass

    if browser_pid_file.exists():
        try:
            browser_pid_file.unlink()
        except OSError:
            pass

    _remove_tree_with_retries(browser_profile_dir, attempts=12, sleep_s=0.5)
    if stopping_flag.exists():
        try:
            stopping_flag.unlink()
        except OSError:
            pass

    print("[FPAS] 停止脚本执行完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _reset_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copytree(src: Path, dst: Path, ignore=None) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)


def _merge_tree(src: Path, dst: Path, ignore=None) -> None:
    if not src.exists():
        return
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)


def _portable_tree_ignore(_dir_path: str, names: List[str]) -> set[str]:
    return {
        name
        for name in names
        if name == "__pycache__" or name.endswith((".pyc", ".pyo"))
    }


def _render_markdown_inline(text: str) -> str:
    rendered = html.escape(text, quote=False)
    rendered = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2" />', rendered
    )
    rendered = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', rendered)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", rendered)
    return rendered


def render_readme_html(markdown_text: str, title: str = "FPAS README") -> str:
    """将 README Markdown 渲染为可直接浏览器打开的 HTML。"""
    lines = markdown_text.splitlines()
    parts: List[str] = []
    in_code = False
    code_lines: List[str] = []
    in_ul = False
    in_ol = False
    in_blockquote = False
    blockquote_lines: List[str] = []
    paragraph_lines: List[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            merged = " ".join(line.strip() for line in paragraph_lines)
            parts.append(f"<p>{_render_markdown_inline(merged)}</p>")
            paragraph_lines = []

    def flush_ul() -> None:
        nonlocal in_ul
        if in_ul:
            parts.append("</ul>")
            in_ul = False

    def flush_ol() -> None:
        nonlocal in_ol
        if in_ol:
            parts.append("</ol>")
            in_ol = False

    def flush_blockquote() -> None:
        nonlocal in_blockquote, blockquote_lines
        if in_blockquote:
            body = "<br/>".join(
                _render_markdown_inline(line) for line in blockquote_lines
            )
            parts.append(f"<blockquote><p>{body}</p></blockquote>")
            in_blockquote = False
            blockquote_lines = []

    for line in lines:
        if line.startswith("```"):
            flush_paragraph()
            flush_ul()
            flush_ol()
            flush_blockquote()
            if not in_code:
                in_code = True
                code_lines = []
            else:
                code_text = html.escape("\n".join(code_lines))
                parts.append(f"<pre><code>{code_text}</code></pre>")
                in_code = False
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_blockquote()
            flush_ul()
            flush_ol()
            continue

        if stripped == "---":
            flush_paragraph()
            flush_blockquote()
            flush_ul()
            flush_ol()
            parts.append("<hr/>")
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            flush_ul()
            flush_ol()
            in_blockquote = True
            blockquote_lines.append(stripped[1:].strip())
            continue
        flush_blockquote()

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            flush_paragraph()
            flush_ul()
            flush_ol()
            level = len(heading_match.group(1))
            parts.append(
                f"<h{level}>{_render_markdown_inline(heading_match.group(2))}</h{level}>"
            )
            continue

        ul_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if ul_match:
            flush_paragraph()
            flush_ol()
            if not in_ul:
                parts.append("<ul>")
                in_ul = True
            parts.append(f"<li>{_render_markdown_inline(ul_match.group(1))}</li>")
            continue

        ol_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ol_match:
            flush_paragraph()
            flush_ul()
            if not in_ol:
                parts.append("<ol>")
                in_ol = True
            parts.append(f"<li>{_render_markdown_inline(ol_match.group(1))}</li>")
            continue

        flush_ul()
        flush_ol()
        paragraph_lines.append(line)

    flush_paragraph()
    flush_blockquote()
    flush_ul()
    flush_ol()

    body = "".join(parts)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --paper: #fffdf8;
      --text: #1f2328;
      --muted: #5b6169;
      --line: #d8d0c2;
      --accent: #8b2e1e;
      --code-bg: #f1ebde;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top, #f9f4ea 0%, var(--bg) 55%, #e8e0d2 100%);
      color: var(--text);
      font: 16px/1.7 "Segoe UI", "Microsoft YaHei", sans-serif;
    }}
    main {{
      max-width: 980px;
      margin: 32px auto;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 40px 48px;
      box-shadow: 0 18px 50px rgba(70, 50, 20, 0.10);
    }}
    h1,h2,h3,h4,h5,h6 {{ line-height: 1.25; color: #2a2118; margin: 1.6em 0 0.7em; }}
    h1 {{ font-size: 2.2rem; margin-top: 0; border-bottom: 2px solid var(--line); padding-bottom: 0.4em; }}
    h2 {{ font-size: 1.6rem; border-left: 6px solid var(--accent); padding-left: 12px; }}
    h3 {{ font-size: 1.25rem; }}
    p, ul, ol, blockquote, pre {{ margin: 0 0 1em; }}
    ul, ol {{ padding-left: 1.5em; }}
    li {{ margin: 0.25em 0; }}
    blockquote {{
      margin-left: 0;
      padding: 0.9em 1em;
      color: var(--muted);
      background: #f8f3ea;
      border-left: 4px solid #c89b63;
      border-radius: 8px;
    }}
    code {{
      font-family: Consolas, Monaco, monospace;
      background: var(--code-bg);
      padding: 0.15em 0.35em;
      border-radius: 6px;
      font-size: 0.92em;
    }}
    pre {{
      background: #201b18;
      color: #f7f3ec;
      padding: 16px;
      border-radius: 12px;
      overflow: auto;
    }}
    pre code {{ background: transparent; padding: 0; color: inherit; }}
    a {{ color: #0d5c94; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    hr {{ border: 0; border-top: 1px solid var(--line); margin: 1.8em 0; }}
    img {{ max-width: 100%; height: auto; border-radius: 12px; border: 1px solid var(--line); }}
  </style>
</head>
<body>
  <main>{body}</main>
</body>
</html>
"""


def _write_packaged_readme_html(project_root: Path, target_root: Path) -> None:
    source_path = project_root / "README.md"
    html_text = render_readme_html(
        source_path.read_text(encoding="utf-8"), title="FPAS README"
    )
    with open(
        target_root / "README.html", "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(html_text)


def _resolve_first_existing_path(candidates: Sequence[Path]) -> Optional[Path]:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _copy_win7_prerequisites(target_root: Path) -> None:
    target_dir = target_root / WIN7_PREREQUISITE_DIR_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    missing: List[str] = []
    for filename, candidates in WIN7_PREREQUISITE_CANDIDATES.items():
        source = _resolve_first_existing_path(candidates)
        if source is None:
            missing.append(filename)
            continue
        _copy_file(source, target_dir / filename)
    if missing:
        missing_text = ", ".join(missing)
        # CI环境（如GitHub Actions）中跳过Win7补丁，不报错
        if os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"[build] 警告：缺少 Win7 前置安装文件（CI环境跳过）：{missing_text}")
            # 创建一个说明文件
            readme_path = target_dir / "README.txt"
            readme_content = """Win7 Prerequisites
==================

以下文件需要在打包前准备好：

1. Windows6.1-KB4490628-x64.msu  (9.2MB)
2. Windows6.1-KB4474419-v3-x64.msu  (54MB)
3. Windows6.1-KB2533623-x64.msu  (2.3MB)
4. Windows6.1-KB2999226-x64.msu  (1MB)
5. 109.0.5414.120-64Bit-ChromeStandaloneSetup64.exe  (89MB)

在本地Windows机器上打包时，将这些文件放在以下任一位置：
- 项目根目录的 win7-patches/ 文件夹
- 用户桌面的 win7-patches/ 文件夹

总大小约155MB，不适合提交到git仓库。
"""
            readme_path.write_text(readme_content, encoding="utf-8")
        else:
            raise SystemExit(f"缺少 Win7 前置安装文件，无法继续打包：{missing_text}")


def _copy_portable_root_files(project_root: Path, target_root: Path) -> None:
    copied: set[str] = set()
    for pattern in PORTABLE_ROOT_FILE_PATTERNS:
        for src in project_root.glob(pattern):
            if not src.is_file():
                continue
            if src.name.startswith("tmp_"):
                continue
            if src.name in copied:
                continue
            _copy_file(src, target_root / src.name)
            copied.add(src.name)


def _copy_portable_source_tree(project_root: Path, target_root: Path) -> None:
    _copy_portable_root_files(project_root, target_root)
    for src_text, rel_text in get_portable_source_dirs(project_root):
        src = Path(src_text)
        if not src.exists():
            raise SystemExit(f"portable bundle 缺少必备目录: {src}")
        _copytree(src, target_root / rel_text, ignore=_portable_tree_ignore)


def _copy_portable_python_runtime(target_runtime_dir: Path) -> None:
    base_runtime = Path(sys.base_prefix).resolve()
    venv_prefix = Path(sys.prefix).resolve()
    stdlib_dir = Path(sysconfig.get_path("stdlib")).resolve()
    platstdlib_text = sysconfig.get_path("platstdlib") or str(stdlib_dir)
    platstdlib_dir = Path(platstdlib_text).resolve()
    if not base_runtime.exists():
        raise SystemExit(f"找不到当前解释器基座目录: {base_runtime}")

    def _runtime_ignore(dir_path: str, names: List[str]) -> set[str]:
        ignored = {
            name
            for name in names
            if name == "__pycache__" or name.endswith((".pyc", ".pyo"))
        }
        current_dir = Path(dir_path).resolve()
        if current_dir == base_runtime:
            ignored.update(
                name
                for name in names
                if name.casefold()
                in {
                    candidate.casefold()
                    for candidate in PORTABLE_RUNTIME_TOP_LEVEL_SKIP_NAMES
                }
            )
        return ignored

    _copytree(base_runtime, target_runtime_dir, ignore=_runtime_ignore)

    stdlib_targets = []
    for candidate in (stdlib_dir, platstdlib_dir):
        if candidate.exists() and candidate not in stdlib_targets:
            stdlib_targets.append(candidate)

    for stdlib_source in stdlib_targets:
        if stdlib_source.name.lower() == "lib":
            _merge_tree(
                stdlib_source,
                target_runtime_dir / "Lib",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )

    python_zip_name = f"python{sys.version_info[0]}{sys.version_info[1]}.zip"
    zip_candidates = []
    for candidate in (
        Path(sys.executable).resolve().parent / python_zip_name,
        base_runtime / python_zip_name,
        venv_prefix / python_zip_name,
        stdlib_dir.parent / python_zip_name,
        platstdlib_dir.parent / python_zip_name,
    ):
        if candidate.exists() and candidate not in zip_candidates:
            zip_candidates.append(candidate)

    for zip_source in zip_candidates:
        _copy_file(zip_source, target_runtime_dir / zip_source.name)

    if venv_prefix != base_runtime:
        venv_site_packages = venv_prefix / "Lib" / "site-packages"
        if venv_site_packages.exists():
            _merge_tree(
                venv_site_packages,
                target_runtime_dir / "Lib" / "site-packages",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )

    has_stdlib_dir = (target_runtime_dir / "Lib" / "encodings").exists()
    has_stdlib_zip = (target_runtime_dir / python_zip_name).exists()
    if not has_stdlib_dir and not has_stdlib_zip:
        raise SystemExit(
            "portable runtime 缺少标准库启动件，至少需要 Lib/encodings 或 "
            f"{python_zip_name}；请在带完整标准库的 Windows Python 3.8 环境中重新打包。"
        )


def _remove_portable_bundle_caches(target_root: Path) -> None:
    """清理打包过程中的运行时缓存和临时文件。"""
    # 1. 清理 Python 字节码缓存文件
    for suffix in ("*.pyc", "*.pyo"):
        for file_path in list(target_root.rglob(suffix)):
            try:
                file_path.unlink()
            except OSError:
                pass

    # 2. 清理 __pycache__ 目录
    cache_dirs = sorted(
        (path for path in target_root.rglob("__pycache__") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for cache_dir in cache_dirs:
        shutil.rmtree(cache_dir, ignore_errors=True)

    # 3. 清理运行时生成的浏览器配置文件 (重要: 可能占用200MB+)
    browser_profile_dir = target_root / "run" / "browser-profile"
    if browser_profile_dir.exists():
        print(f"[build] 清理浏览器配置文件: {browser_profile_dir}")
        shutil.rmtree(browser_profile_dir, ignore_errors=True)

    # 4. 清理运行时日志文件
    log_files = [
        target_root / "audit_system.log",
        target_root / "startup_fatal.log",
    ]
    run_dir = target_root / "run"
    if run_dir.exists():
        log_files.extend(run_dir.glob("*.log"))
        log_files.extend(run_dir.glob("*.pid"))
        log_files.extend(run_dir.glob("*.flag"))

    for log_file in log_files:
        try:
            if log_file.exists():
                log_file.unlink()
        except OSError:
            pass

    # 5. 清理临时文件
    for suffix in ("*.tmp", ".DS_Store", "Thumbs.db"):
        for file_path in list(target_root.rglob(suffix)):
            try:
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    shutil.rmtree(file_path, ignore_errors=True)
            except OSError:
                pass

    # 6. 清理运行时目录中的其他临时数据
    if run_dir.exists():
        # 保留 run 目录本身，但清理其中的内容（除了 .gitkeep 等标记文件）
        for item in run_dir.iterdir():
            try:
                if item.is_file() and item.name not in (".gitkeep", ".gitignore"):
                    item.unlink()
                elif item.is_dir() and item.name != "browser-profile":
                    # 保留其他子目录（如果有的话）
                    pass
            except OSError:
                pass


def _get_portable_bundle_audit_relpaths() -> List[str]:
    relpaths = [
        Path("runtime") / "python" / "python.exe",
        Path("dashboard") / "dist" / "index.html",
        Path("config") / "risk_thresholds.yaml",
        Path("config") / "report_phrases.yaml",
        Path("report_config") / "rules.yaml",
        Path("templates") / "report_v3" / "base.html",
        Path("knowledge") / "suspicion_rules.yaml",
        Path("start_fpas.cmd"),
        Path("stop_fpas.cmd"),
        Path("launch_browser_helper.py"),
        Path("stop_fpas_helper.py"),
    ]
    # CI环境中跳过Win7补丁文件检查（这些文件太大，不适合提交到git）
    if os.environ.get("CI") != "true" and os.environ.get("GITHUB_ACTIONS") != "true":
        relpaths.extend(
            Path(WIN7_PREREQUISITE_DIR_NAME) / filename
            for filename in sorted(WIN7_PREREQUISITE_CANDIDATES)
        )
    return [path.as_posix() for path in relpaths]


def _get_portable_bundle_audit_modules() -> List[str]:
    ordered_modules = list(REQUIRED_RUNTIME_MODULES) + list(
        PORTABLE_BUNDLE_AUDIT_MODULES
    )
    return list(dict.fromkeys(ordered_modules))


def _render_portable_bundle_audit_script() -> str:
    required_files = _get_portable_bundle_audit_relpaths()
    required_modules = _get_portable_bundle_audit_modules()
    version_pins = dict(PORTABLE_BUNDLE_VERSION_PINS)
    return f"""import importlib
import importlib.metadata
import json
import sys
from pathlib import Path

bundle_root = Path.cwd()
sys.path.insert(0, str(bundle_root))
required_files = {required_files!r}
required_modules = {required_modules!r}
version_pins = {version_pins!r}

missing_files = [rel for rel in required_files if not (bundle_root / Path(rel)).exists()]
import_errors = {{}}
for module_name in required_modules:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        import_errors[module_name] = f"{{type(exc).__name__}}: {{exc}}"

version_errors = {{}}
for dist_name, expected_version in version_pins.items():
    try:
        actual_version = importlib.metadata.version(dist_name)
    except Exception as exc:
        version_errors[dist_name] = f"missing ({{type(exc).__name__}}: {{exc}})"
        continue
    if actual_version != expected_version:
        version_errors[dist_name] = (
            f"expected {{expected_version}}, got {{actual_version}}"
        )

if missing_files or import_errors or version_errors:
    print(
        json.dumps(
            {{
                "missing_files": missing_files,
                "import_errors": import_errors,
                "version_errors": version_errors,
            }},
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(1)

print(json.dumps({{"ok": True, "python": sys.version.split()[0]}}, ensure_ascii=False))
"""


def _audit_portable_runtime_bundle(target_root: Path) -> None:
    runtime_python = target_root / "runtime" / "python" / "python.exe"
    if not runtime_python.exists():
        raise SystemExit(f"portable bundle 缺少内置 Python: {runtime_python}")

    result = subprocess.run(
        [str(runtime_python), "-c", _render_portable_bundle_audit_script()],
        cwd=str(target_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout_text = str(result.stdout or "").strip()
    stderr_text = str(result.stderr or "").strip()
    if result.returncode != 0:
        details = stdout_text or stderr_text or "无额外输出"
        raise SystemExit(f"portable bundle 运行时审计失败:\n{details}")
    if stdout_text:
        print(f"[build] portable bundle audit ok: {stdout_text}")


def _write_portable_launchers(target_root: Path) -> None:
    with open(
        target_root / "start_fpas.cmd", "w", encoding="utf-8", newline="\r\n"
    ) as handle:
        handle.write(render_portable_start_cmd())
    with open(
        target_root / "start_fpas_silent.vbs",
        "w",
        encoding="utf-8",
        newline="\r\n",
    ) as handle:
        handle.write(render_portable_start_vbs())
    with open(
        target_root / "launch_browser_helper.py",
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        handle.write(render_portable_launch_browser_helper_py())
    with open(
        target_root / "stop_fpas.cmd", "w", encoding="utf-8", newline="\r\n"
    ) as handle:
        handle.write(render_portable_stop_cmd())
    with open(
        target_root / "stop_fpas_helper.py",
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        handle.write(render_portable_stop_helper_py())


def build_portable_runtime_bundle() -> None:
    """复制 Python 运行时与源码，生成 Win7 友好的 one-folder 离线包。"""
    _reset_directory(DIST_DIR)
    _copy_portable_source_tree(PROJECT_ROOT, DIST_DIR)
    _copy_portable_python_runtime(PORTABLE_RUNTIME_DIR)
    _write_portable_launchers(DIST_DIR)
    _write_packaged_readme_html(PROJECT_ROOT, DIST_DIR)
    _copy_win7_prerequisites(DIST_DIR)
    _remove_portable_bundle_caches(DIST_DIR)
    _audit_portable_runtime_bundle(DIST_DIR)


def _required_preflight_paths(project_root: Optional[Path] = None) -> List[Path]:
    """返回在任何平台都可做的仓库侧预检路径。"""
    root = project_root or PROJECT_ROOT
    vis_network_js = (
        root
        / "dashboard"
        / "node_modules"
        / "vis-network"
        / "standalone"
        / "umd"
        / "vis-network.min.js"
    )
    return [
        root / "README.md",
        root / "docs" / "assets",
        root / "utils.py",
        root / "config",
        root / "knowledge",
        root / "report_config",
        root / "templates",
        root / "dashboard" / "package.json",
        root / "dashboard" / "index.html",
        root / "dashboard" / "src" / "index.css",
        vis_network_js,
        root / "fpas_windows.spec",
    ]


def collect_preflight_issues(project_root: Optional[Path] = None) -> List[str]:
    """收集当前仓库在 mac/Linux 也能识别的硬性缺口。"""
    missing = []
    for path in _required_preflight_paths(project_root):
        if not path.exists():
            missing.append(str(path))
    return missing


def run_preflight() -> None:
    """执行跨平台预检，确保仓库已具备 Windows 打包前提。"""
    print("== Windows 离线打包预检 ==")
    print(f"项目目录: {PROJECT_ROOT}")
    issues = collect_preflight_issues()
    if issues:
        print("[preflight] 缺少以下必备资源：")
        for item in issues:
            print(f"  - {item}")
        raise SystemExit("预检失败，请先补齐资源后再继续。")

    print("[preflight] 运行时资源检查通过")
    print(
        "[preflight] README、docs/assets、模板、知识库、前端构建源文件和 spec 均已存在"
    )

    if sys.platform != "win32":
        print(
            "[preflight] 当前不是 Windows，现阶段只能做仓库预检和前端生产构建验证，"
            "不能在本机产出最终 Windows one-folder 包。"
        )
    if sys.version_info[:2] != TARGET_WINDOWS_PYTHON:
        print(
            "[preflight] 注意：目标要求 Windows7+，正式构建机应使用 Python "
            f"{TARGET_WINDOWS_PYTHON[0]}.{TARGET_WINDOWS_PYTHON[1]}.x。"
            f"当前解释器是 {_python_version_text()}，仅适合做预检。"
        )


def ensure_windows_build_environment() -> None:
    """限制正式构建只能在 Windows Python 3.8 环境执行。"""
    if sys.platform != "win32":
        raise SystemExit(
            "当前平台不是 Windows。正式 Windows 离线包只能在 Windows 机器上构建；"
            "如需先做仓库检查，请执行 `python build_windows_package.py --preflight`。"
        )
    if sys.version_info[:2] != TARGET_WINDOWS_PYTHON:
        raise SystemExit(
            "目标为 Windows7+ 时，正式构建机必须使用 Python "
            f"{TARGET_WINDOWS_PYTHON[0]}.{TARGET_WINDOWS_PYTHON[1]}.x；"
            f"当前解释器为 {_python_version_text()}。"
        )


def ensure_pyinstaller() -> None:
    """确认 PyInstaller 已安装。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "未检测到 PyInstaller，请先执行 "
            f"`{sys.executable} -m pip install -r requirements-windows-build.txt`"
        ) from exc

    version = (result.stdout or result.stderr or "").strip().splitlines()
    installed_version = version[-1].strip() if version else ""
    if installed_version != PINNED_PYINSTALLER_VERSION:
        raise SystemExit(
            "目标为 Windows7+ 时，PyInstaller 必须固定为 "
            f"{PINNED_PYINSTALLER_VERSION}；当前检测到 {installed_version or '未知版本'}。"
        )


def ensure_required_runtime_modules() -> None:
    """确认 Windows 包关键运行时模块已安装，避免产出功能残缺的 exe。"""
    missing = [
        module
        for module in REQUIRED_RUNTIME_MODULES
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        raise SystemExit(
            "缺少 Windows 离线包关键运行时模块："
            f"{', '.join(missing)}。请先执行 "
            f"`{sys.executable} -m pip install -r requirements.txt -r requirements-windows-build.txt`"
        )


def ensure_dashboard_build() -> None:
    """构建前端产物，供后端和 PyInstaller 打包使用。"""
    if not (DASHBOARD_DIR / "package.json").exists():
        raise SystemExit("缺少 dashboard/package.json，无法执行前端构建")

    run([*_resolve_npm_command(), "run", "build"], cwd=DASHBOARD_DIR)
    ensure_dashboard_dist()


def ensure_dashboard_dist() -> None:
    """确认前端生产产物已经存在。"""
    index_file = DASHBOARD_DIST_DIR / "index.html"
    if not index_file.exists():
        raise SystemExit("前端构建未生成 dashboard/dist/index.html")


def build_windows_bundle() -> None:
    """调用 PyInstaller 生成 one-folder 离线包。"""
    if not SPEC_FILE.exists():
        raise SystemExit(f"缺少 PyInstaller spec 文件: {SPEC_FILE}")

    run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC_FILE)])


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="穿云审计 Windows 单机离线 one-folder 打包工具"
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="只执行仓库与交付前检查，不产出最终 Windows 包",
    )
    parser.add_argument(
        "--skip-dashboard-build",
        action="store_true",
        help="跳过 Windows 本地前端重建，直接复用已有 dashboard/dist",
    )
    parser.add_argument(
        "--bundle-mode",
        choices=BUNDLE_MODES,
        default=DEFAULT_BUNDLE_MODE,
        help="Windows 离线包构建模式：portable-runtime 为 Win7 默认推荐；pyinstaller 仅保留为兼容调试路径",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    run_preflight()
    if args.preflight:
        print("预检完成。")
        return

    ensure_windows_build_environment()
    ensure_required_runtime_modules()
    if args.skip_dashboard_build:
        ensure_dashboard_dist()
        print("[build] 已跳过前端重建，直接复用现有 dashboard/dist")
    else:
        ensure_dashboard_build()
    if args.bundle_mode == "pyinstaller":
        ensure_pyinstaller()
        build_windows_bundle()
        _write_packaged_readme_html(PROJECT_ROOT, DIST_DIR)
        _copy_win7_prerequisites(DIST_DIR)
        print("构建完成，产物目录: dist/fpas-offline (PyInstaller)")
        return

    build_portable_runtime_bundle()
    print("构建完成，产物目录: dist/fpas-offline (portable-runtime)")


if __name__ == "__main__":
    main()
