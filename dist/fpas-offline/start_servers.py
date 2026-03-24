#!/usr/bin/env python3
"""启动前后端服务 - 使用独立窗口"""

import subprocess
import sys
import os

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    print("启动穿云审计系统...")

    # 启动后端 (新窗口)
    print("[1/2] 启动后端 API 服务...")
    backend = subprocess.Popen(
        [sys.executable, "api_server.py"],
        cwd=PROJECT_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    print(f"    后端 PID: {backend.pid}")

    # 启动前端 (新窗口)
    print("[2/2] 启动前端 Dashboard...")
    frontend = subprocess.Popen(
        "npm run dev",
        cwd=os.path.join(PROJECT_DIR, "dashboard"),
        shell=True,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    print(f"    前端 PID: {frontend.pid}")

    print("\n✅ 服务已启动:")
    print("   后端: http://localhost:8000")
    print("   前端: http://localhost:5173")
    print("\n按任意键退出此窗口 (服务将继续在后台运行)...")
    input()


if __name__ == "__main__":
    main()
