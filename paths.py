#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一路径管理器 - 资金穿透与关联排查系统

解决的问题：
1. 相对路径依赖工作目录，打包后路径错误
2. __file__ 在 PyInstaller 打包后指向临时目录
3. 提供统一的路径获取接口，避免硬编码

使用方法：
    from paths import APP_ROOT, DATA_DIR, OUTPUT_DIR, CONFIG_DIR

注意：
- 所有模块应从此文件导入路径，禁止硬编码路径
- 打包后可写目录位于 exe 同级目录，打包资源目录位于 PyInstaller 资源根
"""

import os
import sys
from pathlib import Path


def get_app_root() -> Path:
    """
    获取应用程序根目录（兼容开发环境和打包环境）

    开发环境：返回项目根目录（paths.py 所在目录）
    打包环境：返回 exe 所在目录

    Returns:
        Path: 应用程序根目录
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后，sys.executable 是 exe 路径
        return Path(sys.executable).parent.resolve()
    else:
        # 开发环境，返回 paths.py 所在目录
        return Path(__file__).parent.resolve()


def get_resource_root() -> Path:
    """
    获取打包资源根目录。

    开发环境：返回项目根目录。
    打包环境：优先返回 PyInstaller 的资源目录（通常为 one-folder 下的 `_internal`）。
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
    return get_app_root()


def get_data_dir() -> Path:
    """
    获取数据目录路径

    Returns:
        Path: data 目录路径
    """
    return get_app_root() / "data"


def get_output_dir() -> Path:
    """
    获取输出目录路径

    Returns:
        Path: output 目录路径
    """
    return get_app_root() / "output"


def get_config_dir() -> Path:
    """
    获取配置目录路径

    Returns:
        Path: config 目录路径
    """
    return get_resource_root() / "config"


def get_cache_path() -> Path:
    """
    获取分析缓存文件路径

    Returns:
        Path: analysis_cache.json 文件路径
    """
    return get_output_dir() / "analysis_cache.json"


def get_templates_dir() -> Path:
    """
    获取模板目录路径

    Returns:
        Path: templates 目录路径
    """
    return get_resource_root() / "templates"


def get_knowledge_dir() -> Path:
    """
    获取知识库目录路径

    Returns:
        Path: knowledge 目录路径
    """
    return get_resource_root() / "knowledge"


def get_dashboard_dist_dir() -> Path:
    """
    获取前端生产构建目录。

    Returns:
        Path: dashboard/dist 目录路径
    """
    return get_resource_root() / "dashboard" / "dist"


def resolve_path(path_str: str, base_dir: Path = None) -> Path:
    """
    将路径字符串解析为绝对路径

    如果是绝对路径，直接返回
    如果是相对路径，相对于 base_dir 解析（默认为 APP_ROOT）

    Args:
        path_str: 路径字符串
        base_dir: 基准目录，默认为 APP_ROOT

    Returns:
        Path: 解析后的绝对路径
    """
    path = Path(path_str)
    if path.is_absolute():
        return path
    else:
        base = base_dir if base_dir else get_app_root()
        return (base / path).resolve()


def ensure_dir(path: Path) -> Path:
    """
    确保目录存在，不存在则创建

    Args:
        path: 目录路径

    Returns:
        Path: 目录路径
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


# 导出常量（方便其他模块导入使用）
APP_ROOT = get_app_root()
RESOURCE_ROOT = get_resource_root()
DATA_DIR = get_data_dir()
OUTPUT_DIR = get_output_dir()
CONFIG_DIR = get_config_dir()
CACHE_PATH = get_cache_path()
TEMPLATES_DIR = get_templates_dir()
KNOWLEDGE_DIR = get_knowledge_dir()
DASHBOARD_DIST_DIR = get_dashboard_dist_dir()


# 调试信息
if __name__ == "__main__":
    print("=" * 60)
    print("路径配置信息")
    print("=" * 60)
    print(f"APP_ROOT:     {APP_ROOT}")
    print(f"RESOURCE_ROOT: {RESOURCE_ROOT}")
    print(f"DATA_DIR:     {DATA_DIR}")
    print(f"OUTPUT_DIR:   {OUTPUT_DIR}")
    print(f"CONFIG_DIR:   {CONFIG_DIR}")
    print(f"CACHE_PATH:   {CACHE_PATH}")
    print(f"TEMPLATES_DIR: {TEMPLATES_DIR}")
    print(f"KNOWLEDGE_DIR: {KNOWLEDGE_DIR}")
    print(f"DASHBOARD_DIST_DIR: {DASHBOARD_DIST_DIR}")
    print("=" * 60)
    print(f"sys.frozen:   {getattr(sys, 'frozen', False)}")
    print(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
    print(f"__file__:     {__file__}")
    print(f"sys.executable: {getattr(sys, 'executable', 'N/A')}")
