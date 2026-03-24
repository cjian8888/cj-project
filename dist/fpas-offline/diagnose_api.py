#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断 API 问题"""

import sys
import os

sys.path.insert(0, ".")
# 使用项目根目录（通过paths模块获取）
try:
    from paths import APP_ROOT

    os.chdir(APP_ROOT)
except ImportError:
    # 如果paths模块不可用，使用当前目录
    pass

import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from api_server import (
    analysis_state,
    serialize_for_json,
    to_camel_case,
    _restore_analysis_state_from_cache,
    OUTPUT_DIR,
)
from cache_manager import CacheManager
import json

print("=" * 60)
print("诊断分析状态")
print("=" * 60)

print(f"\n1. 当前 analysis_state.status: {analysis_state.status}")
print(f"2. 当前 analysis_state.results: {analysis_state.results is not None}")

print("\n3. 尝试从缓存恢复...")
_restore_analysis_state_from_cache()

print(f"\n4. 恢复后 analysis_state.status: {analysis_state.status}")
print(f"5. 恢复后 analysis_state.results: {analysis_state.results is not None}")

if analysis_state.results:
    print(f"6. results keys: {list(analysis_state.results.keys())}")

    print("\n7. 测试序列化...")
    try:
        results_data = serialize_for_json(analysis_state.results)
        print(f"   serialize_for_json: OK ({type(results_data)})")

        results_data = to_camel_case(results_data)
        print(f"   to_camel_case: OK ({type(results_data)})")

        json_str = json.dumps(results_data)
        print(f"   json.dumps: OK ({len(json_str)} 字符)")

        print("\n" + "=" * 60)
        print("所有测试通过！序列化正常")
        print("=" * 60)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()
else:
    print("\n6. 尝试直接加载缓存...")
    cache_dir = os.path.join(str(OUTPUT_DIR), "analysis_cache")
    cache_mgr = CacheManager(cache_dir)
    results = cache_mgr.load_results()
    print(f"   缓存加载: {results is not None}")
    if results:
        print(f"   results keys: {list(results.keys())}")
