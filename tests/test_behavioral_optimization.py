#!/usr/bin/env python3
"""测试 behavioral_profiler 优化后的结果一致性"""

import pandas as pd
import numpy as np
import sys
import time
from pathlib import Path

# 添加项目目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from behavioral_profiler import (
    is_financial_product_transaction,
    _filter_financial_transactions_legacy,
    _filter_financial_transactions_vectorized,
)


ROW_COUNT = 1000
RNG = np.random.default_rng(42)


def _expand_patterns(patterns, total_count):
    repeats = (total_count + len(patterns) - 1) // len(patterns)
    return (patterns * repeats)[:total_count]


# 创建测试数据
def create_test_data():
    """创建包含各种场景的测试数据"""
    counterparty_patterns = [
        # 正常交易
        "张三",
        "李四",
        "王五",
        "工资发放",
        "奖金",
        # 理财相关
        "理财产品",
        "基金申购",
        "证券账户",
        "华泰证券",
        "易方达",
        # 混合场景
        "张三_理财",
        "基金_李四",
        "存管账户",
        # 空值测试
        None,
        np.nan,
        "",
    ]
    description_patterns = [
        # 正常交易
        "转账",
        "消费",
        "还款",
        # 理财相关
        "购买理财",
        "基金赎回",
        "银证转账",
        "结构性存款",
        # 混合场景
        "理财到期",
        "基金分红",
        # 空值测试
        None,
        np.nan,
        "",
    ]
    data = {
        "date": pd.date_range("2024-01-01", periods=ROW_COUNT, freq="h"),
        "counterparty": _expand_patterns(counterparty_patterns, ROW_COUNT),
        "description": _expand_patterns(description_patterns, ROW_COUNT),
        "income": RNG.integers(1000, 100000, ROW_COUNT),
        "expense": RNG.integers(1000, 100000, ROW_COUNT),
    }
    return pd.DataFrame(data)


def test_consistency():
    """测试新旧实现结果一致性"""
    print("=" * 60)
    print("测试 behavioral_profiler 结果一致性")
    print("=" * 60)

    # 创建测试数据
    df = create_test_data()
    print(f"\n测试数据: {len(df)} 行")

    # 测试逐行函数
    print("\n1. 测试 is_financial_product_transaction 函数...")
    test_cases = [
        pd.Series({"counterparty": "理财产品", "description": "测试"}),
        pd.Series({"counterparty": "张三", "description": "基金申购"}),
        pd.Series({"counterparty": "正常交易", "description": "转账"}),
        pd.Series({"counterparty": None, "description": np.nan}),
    ]

    for i, case in enumerate(test_cases):
        result = is_financial_product_transaction(case)
        print(
            f"  用例{i + 1}: {case.get('counterparty', 'None')} -> {'理财' if result else '非理财'}"
        )

    # 测试过滤函数 - 性能对比
    print("\n2. 测试过滤函数性能...")

    # 旧版
    start = time.time()
    result_legacy = _filter_financial_transactions_legacy(df)
    time_legacy = time.time() - start

    # 向量化版
    start = time.time()
    result_vectorized = _filter_financial_transactions_vectorized(df)
    time_vectorized = time.time() - start

    print(
        f"  旧版:      {len(df)}行 -> {len(result_legacy)}行, 耗时 {time_legacy:.3f}秒"
    )
    print(
        f"  向量化版:  {len(df)}行 -> {len(result_vectorized)}行, 耗时 {time_vectorized:.3f}秒"
    )

    # 验证结果一致性
    print("\n3. 验证结果一致性...")

    # 检查行数是否一致
    assert len(result_legacy) == len(result_vectorized), (
        f"过滤后行数不一致: 旧版={len(result_legacy)}, "
        f"向量化={len(result_vectorized)}"
    )
    print(f"  ✅ 过滤后行数一致: {len(result_legacy)} 行")

    # 检查索引是否一致（数据内容一致）
    legacy_index = set(result_legacy.index)
    vectorized_index = set(result_vectorized.index)

    diff = legacy_index.symmetric_difference(vectorized_index)
    assert legacy_index == vectorized_index, (
        f"过滤结果索引不一致: 差异行数={len(diff)}, "
        f"仅旧版={len(legacy_index - vectorized_index)}, "
        f"仅向量化={len(vectorized_index - legacy_index)}"
    )
    print("  ✅ 保留的数据行完全一致")

    # 性能提升
    speedup = time_legacy / time_vectorized if time_vectorized > 0 else float("inf")
    print(f"\n4. 性能提升: {speedup:.1f}x")

    print("\n" + "=" * 60)
    print("所有测试通过! 结果一致性验证成功。")
    print("=" * 60)

if __name__ == "__main__":
    test_consistency()
