#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试浏览器拉起功能的脚本"""

import os
import sys
import subprocess
from pathlib import Path


def test_browser_launch():
    """测试浏览器拉起功能"""
    print("=" * 60)
    print("浏览器拉起功能测试")
    print("=" * 60)

    # 检查环境变量
    print("\n1. 检查环境变量:")
    env_vars = [
        "FPAS_ROOT",
        "FPAS_RUN_DIR",
        "FPAS_BROWSER_PID_FILE",
        "FPAS_BROWSER_PROFILE_DIR",
        "FPAS_STOPPING_FLAG",
        "FPAS_DELIVERY_MODE",
        "FPAS_AUTO_OPEN_BROWSER",
        "FPAS_PORT",
        "FPAS_STARTUP_DIAGNOSTICS_ROOT",
        "PYTHONPATH",
    ]

    for var in env_vars:
        value = os.environ.get(var, "<未设置>")
        print(f"  {var}={value}")

    # 检查Python路径
    print("\n2. 检查Python路径:")
    print(f"  sys.executable={sys.executable}")
    print(f"  sys.path={sys.path[:3]}...")  # 只显示前3个

    # 检查launch_browser_helper.py是否存在
    print("\n3. 检查launch_browser_helper.py:")
    helper_path = Path("launch_browser_helper.py")
    if helper_path.exists():
        print(f"  文件存在: {helper_path.absolute()}")
        # 检查文件内容
        content = helper_path.read_text(encoding="utf-8")
        if "_log_debug" in content:
            print("  ✓ 包含调试日志功能")
        if "--no-first-run" in content:
            print("  ✓ 包含Win7兼容性修复")
    else:
        print(f"  ✗ 文件不存在: {helper_path.absolute()}")

    # 检查run目录
    print("\n4. 检查run目录:")
    run_dir = Path("run")
    if run_dir.exists():
        print(f"  目录存在: {run_dir.absolute()}")
        # 列出目录内容
        files = list(run_dir.iterdir())
        if files:
            print(f"  文件: {[f.name for f in files]}")
        else:
            print("  目录为空")
    else:
        print(f"  目录不存在: {run_dir.absolute()}")

    # 检查调试日志
    print("\n5. 检查调试日志:")
    debug_log = Path("run/browser_launch_debug.log")
    if debug_log.exists():
        print(f"  日志文件存在: {debug_log.absolute()}")
        content = debug_log.read_text(encoding="utf-8")
        print(f"  内容:\n{content}")
    else:
        print(f"  日志文件不存在: {debug_log.absolute()}")

    # 检查错误日志
    print("\n6. 检查错误日志:")
    error_log = Path("run/browser_launch_error.log")
    if error_log.exists():
        print(f"  日志文件存在: {error_log.absolute()}")
        content = error_log.read_text(encoding="utf-8")
        print(f"  内容:\n{content}")
    else:
        print(f"  日志文件不存在: {error_log.absolute()}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_browser_launch()
