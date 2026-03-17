#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 离线单机包构建入口。"""

from __future__ import annotations

import subprocess
import sys
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DASHBOARD_DIST_DIR = DASHBOARD_DIR / "dist"
SPEC_FILE = PROJECT_ROOT / "fpas_windows.spec"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    """运行命令并在失败时中断。"""
    workdir = cwd or PROJECT_ROOT
    print(f"[build] cwd={workdir} cmd={' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(workdir), check=True)


def _resolve_npm_command() -> list[str]:
    """解析适用于当前平台的 npm 可执行文件。"""
    candidates = ["npm.cmd", "npm"] if sys.platform == "win32" else ["npm"]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]
    raise SystemExit(
        "未检测到 npm，可先确认 Node.js 已安装且 npm 已加入 PATH。"
    )


def ensure_pyinstaller() -> None:
    """确认 PyInstaller 已安装。"""
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "未检测到 PyInstaller，请先执行 "
            f"`{sys.executable} -m pip install -r requirements-windows-build.txt`"
        ) from exc


def ensure_dashboard_build() -> None:
    """构建前端产物，供后端和 PyInstaller 打包使用。"""
    if not (DASHBOARD_DIR / "package.json").exists():
        raise SystemExit("缺少 dashboard/package.json，无法执行前端构建")

    run([*_resolve_npm_command(), "run", "build"], cwd=DASHBOARD_DIR)
    index_file = DASHBOARD_DIST_DIR / "index.html"
    if not index_file.exists():
        raise SystemExit("前端构建未生成 dashboard/dist/index.html")


def build_windows_bundle() -> None:
    """调用 PyInstaller 生成 one-folder 离线包。"""
    if not SPEC_FILE.exists():
        raise SystemExit(f"缺少 PyInstaller spec 文件: {SPEC_FILE}")

    run([sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC_FILE)])


def main() -> None:
    print("== 穿云审计 Windows 离线包构建 ==")
    print(f"项目目录: {PROJECT_ROOT}")
    ensure_pyinstaller()
    ensure_dashboard_build()
    build_windows_bundle()
    print("构建完成，产物目录: dist/fpas-offline")


if __name__ == "__main__":
    main()
