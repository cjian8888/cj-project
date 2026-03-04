#!/usr/bin/env python3
"""测试 behavioral_profiler 优化后的结果一致性"""

import pandas as pd
import numpy as np
import sys
import time

# 添加项目目录到路径
sys.path.insert(0, "D:\\cj\\project")

from behavioral_profiler import (
    is_financial_product_transaction,
    _filter_financial_transactions_legacy,
    _filter_financial_transactions_vectorized,
    USE_VECTORIZED_FILTER,
)


# 创建测试数据
def create_test_data():
    """创建包含各种场景的测试数据"""
    data = {
        "date": pd.date_range("2024-01-01", periods=1000, freq="H"),
        "counterparty": [
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
            # 随机填充
        ]
        * 50,  # 重复50次
        "description": [
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
            # 随机填充
        ]
        * 60,  # 重复60次
        "income": np.random.randint(1000, 100000, 1000),
        "expense": np.random.randint(1000, 100000, 1000),
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
    if len(result_legacy) == len(result_vectorized):
        print(f"  ✅ 过滤后行数一致: {len(result_legacy)} 行")
    else:
        print(
            f"  ❌ 行数不一致! 旧版:{len(result_legacy)} 向量化:{len(result_vectorized)}"
        )
        return False

    # 检查索引是否一致（数据内容一致）
    legacy_index = set(result_legacy.index)
    vectorized_index = set(result_vectorized.index)

    if legacy_index == vectorized_index:
        print(f"  ✅ 保留的数据行完全一致")
    else:
        diff = legacy_index.symmetric_difference(vectorized_index)
        print(f"  ❌ 数据不一致! 差异行数: {len(diff)}")
        print(f"    仅在旧版中: {len(legacy_index - vectorized_index)}")
        print(f"    仅在向量化版中: {len(vectorized_index - legacy_index)}")
        return False

    # 性能提升
    speedup = time_legacy / time_vectorized if time_vectorized > 0 else float("inf")
    print(f"\n4. 性能提升: {speedup:.1f}x")

    print("\n" + "=" * 60)
    print("所有测试通过! 结果一致性验证成功。")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = test_consistency()
    sys.exit(0 if success else 1)
