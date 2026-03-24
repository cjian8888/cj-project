#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 离线单机包构建入口。"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import shutil
import textwrap
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


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
PORTABLE_RUNTIME_IGNORE = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "Doc",
    "docs",
    "Tools",
    "test",
    "tests",
    "turtledemo",
    "idlelib",
)
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
    raise SystemExit(
        "未检测到 npm，可先确认 Node.js 已安装且 npm 已加入 PATH。"
    )


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


def get_portable_source_dirs(project_root: Optional[Path] = None) -> List[Tuple[str, str]]:
    """返回 portable runtime bundle 需要复制的目录映射。"""
    root = project_root or PROJECT_ROOT
    return [(str(root / rel_path), rel_path.as_posix()) for rel_path in PORTABLE_SOURCE_DIRS]


def render_portable_start_cmd() -> str:
    """生成 Win7 交付包的显式启动脚本。"""
    return textwrap.dedent(
        r"""\
        @echo off
        setlocal
        cd /d "%~dp0"
        set "FPAS_ROOT=%~dp0"
        set "FPAS_PYTHON=%FPAS_ROOT%runtime\python\python.exe"
        if not exist "%FPAS_PYTHON%" (
            echo [FPAS] 缺少内置 Python 运行时: "%FPAS_PYTHON%"
            pause
            exit /b 1
        )
        set "FPAS_STARTUP_DIAGNOSTICS_ROOT=%FPAS_ROOT%"
        set "PYTHONPATH=%FPAS_ROOT%"
        set "PATH=%FPAS_ROOT%runtime\python;%FPAS_ROOT%runtime\python\DLLs;%FPAS_ROOT%runtime\python\Scripts;%PATH%"
        "%FPAS_PYTHON%" "%FPAS_ROOT%api_server.py"
        set "EXIT_CODE=%ERRORLEVEL%"
        if not "%EXIT_CODE%"=="0" (
            echo.
            echo [FPAS] 服务异常退出，退出码=%EXIT_CODE%
            pause
        )
        exit /b %EXIT_CODE%
        """
    )


def render_portable_start_vbs() -> str:
    """生成静默启动包装器，便于双击时隐藏 cmd 窗口。"""
    return textwrap.dedent(
        """\
        Set shell = CreateObject("WScript.Shell")
        Set fso = CreateObject("Scripting.FileSystemObject")
        appDir = fso.GetParentFolderName(WScript.ScriptFullName)
        shell.CurrentDirectory = appDir
        shell.Run Chr(34) & appDir & "\\start_fpas.cmd" & Chr(34), 0, False
        """
    )


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
        _copytree(src, target_root / rel_text)


def _copy_portable_python_runtime(target_runtime_dir: Path) -> None:
    base_runtime = Path(sys.base_prefix).resolve()
    venv_prefix = Path(sys.prefix).resolve()
    if not base_runtime.exists():
        raise SystemExit(f"找不到当前解释器基座目录: {base_runtime}")

    _copytree(base_runtime, target_runtime_dir, ignore=PORTABLE_RUNTIME_IGNORE)

    if venv_prefix != base_runtime:
        venv_site_packages = venv_prefix / "Lib" / "site-packages"
        if venv_site_packages.exists():
            shutil.copytree(
                venv_site_packages,
                target_runtime_dir / "Lib" / "site-packages",
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )


def _write_portable_launchers(target_root: Path) -> None:
    with open(target_root / "start_fpas.cmd", "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(render_portable_start_cmd())
    with open(
        target_root / "start_fpas_silent.vbs",
        "w",
        encoding="utf-8",
        newline="\r\n",
    ) as handle:
        handle.write(render_portable_start_vbs())


def build_portable_runtime_bundle() -> None:
    """复制 Python 运行时与源码，生成 Win7 友好的 one-folder 离线包。"""
    _reset_directory(DIST_DIR)
    _copy_portable_source_tree(PROJECT_ROOT, DIST_DIR)
    _copy_portable_python_runtime(PORTABLE_RUNTIME_DIR)
    _write_portable_launchers(DIST_DIR)


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
    print("[preflight] README、docs/assets、模板、知识库、前端构建源文件和 spec 均已存在")

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
        module for module in REQUIRED_RUNTIME_MODULES if importlib.util.find_spec(module) is None
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
        print("构建完成，产物目录: dist/fpas-offline (PyInstaller)")
        return

    build_portable_runtime_bundle()
    print("构建完成，产物目录: dist/fpas-offline (portable-runtime)")


if __name__ == "__main__":
    main()
