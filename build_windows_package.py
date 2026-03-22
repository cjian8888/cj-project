#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 离线单机包构建入口。"""

from __future__ import annotations

import argparse
import subprocess
import sys
import shutil
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DASHBOARD_DIST_DIR = DASHBOARD_DIR / "dist"
SPEC_FILE = PROJECT_ROOT / "fpas_windows.spec"
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
    return [
        "chinese_calendar",
        "neo4j",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
    ]


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
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    run_preflight()
    if args.preflight:
        print("预检完成。")
        return

    ensure_windows_build_environment()
    ensure_pyinstaller()
    if args.skip_dashboard_build:
        ensure_dashboard_dist()
        print("[build] 已跳过前端重建，直接复用现有 dashboard/dist")
    else:
        ensure_dashboard_build()
    build_windows_bundle()
    print("构建完成，产物目录: dist/fpas-offline")


if __name__ == "__main__":
    main()
