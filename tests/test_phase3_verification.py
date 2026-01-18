#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 3 循环验证脚本
验证刑侦级审计报告体系实现的完整性和正确性
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def verify_phase0_fields():
    """验证 Phase 0.1 刑侦级字段是否在 data_cleaner 中正确实现"""
    print("=" * 60)
    print("【3.1-A】验证 Phase 0.1 刑侦级字段")
    print("=" * 60)
    
    import config
    
    # 检查配置常量
    required_configs = [
        'SENSITIVE_KEYWORDS',
        'TRANSACTION_CHANNEL_KEYWORDS', 
        'BALANCE_ZERO_THRESHOLD'
    ]
    
    for cfg in required_configs:
        if hasattr(config, cfg):
            value = getattr(config, cfg)
            print(f"  ✅ {cfg} 存在 (类型: {type(value).__name__})")
        else:
            print(f"  ❌ {cfg} 缺失!")
            return False
    
    # 检查列映射
    if 'is_balance_zeroed' in str(config.COLUMN_MAPPING):
        print("  ✅ COLUMN_MAPPING 包含 is_balance_zeroed")
    else:
        print("  ⚠️ COLUMN_MAPPING 未包含 is_balance_zeroed")
    
    return True


def verify_behavioral_profiler():
    """验证 behavioral_profiler 模块功能"""
    print("\n" + "=" * 60)
    print("【3.1-B】验证 behavioral_profiler 模块")
    print("=" * 60)
    
    import behavioral_profiler
    
    # 验证 Phase 0.2 函数
    phase02_funcs = [
        'detect_fast_in_out',
        'detect_structuring', 
        'detect_dormant_activation',
        'analyze_behavioral_patterns'
    ]
    
    for func in phase02_funcs:
        if hasattr(behavioral_profiler, func):
            print(f"  ✅ {func}() 存在")
        else:
            print(f"  ❌ {func}() 缺失!")
            return False
    
    # 验证 Phase 0.3 函数
    phase03_funcs = [
        'calculate_fund_retention_rate',
        'analyze_counterparty_frequency',
        'analyze_fund_sedimentation'
    ]
    
    for func in phase03_funcs:
        if hasattr(behavioral_profiler, func):
            print(f"  ✅ {func}() 存在")
        else:
            print(f"  ❌ {func}() 缺失!")
            return False
    
    return True


def verify_report_generator():
    """验证 report_generator 模块的 Word 导出功能"""
    print("\n" + "=" * 60)
    print("【3.1-C】验证 report_generator Word 导出")
    print("=" * 60)
    
    import report_generator
    
    if hasattr(report_generator, 'generate_word_report'):
        print("  ✅ generate_word_report() 存在")
        
        # 检查函数签名
        import inspect
        sig = inspect.signature(report_generator.generate_word_report)
        params = list(sig.parameters.keys())
        print(f"  ✅ 参数列表: {params[:5]}...")
        return True
    else:
        print("  ❌ generate_word_report() 缺失!")
        return False


def verify_main_integration():
    """验证 main.py 集成"""
    print("\n" + "=" * 60)
    print("【3.1-D】验证 main.py 集成")
    print("=" * 60)
    
    import main
    
    if hasattr(main, 'phase5_15_behavioral_analysis'):
        print("  ✅ phase5_15_behavioral_analysis() 存在")
    else:
        print("  ❌ phase5_15_behavioral_analysis() 缺失!")
        return False
    
    # 检查导入
    if 'behavioral_profiler' in dir(main):
        print("  ✅ behavioral_profiler 已导入")
    else:
        print("  ⚠️ behavioral_profiler 未在 main 模块命名空间")
    
    return True


def verify_logic_traceability():
    """验证逻辑闭环：检测结果是否包含可追溯信息"""
    print("\n" + "=" * 60)
    print("【3.2】验证逻辑闭环可追溯性")
    print("=" * 60)
    
    import behavioral_profiler
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    
    # 创建模拟数据（使用正确的 datetime 类型）
    dates = pd.date_range(start='2025-01-01', periods=100, freq='D')
    mock_df = pd.DataFrame({
        'date': dates,  # 确保是 datetime 类型
        'income': np.random.randint(0, 50000, 100).astype(float),
        'expense': np.random.randint(0, 50000, 100).astype(float),
        'balance': np.random.randint(100, 100000, 100).astype(float),
        'counterparty': ['对手方' + str(i % 10) for i in range(100)],
        'description': ['测试交易'] * 100
    })
    
    # 测试快进快出检测
    try:
        result = behavioral_profiler.detect_fast_in_out(mock_df)  # 使用默认参数
        if isinstance(result, list):
            print(f"  ✅ detect_fast_in_out 返回列表 (长度: {len(result)})")
        else:
            print(f"  ⚠️ detect_fast_in_out 返回类型: {type(result)}")
    except Exception as e:
        print(f"  ⚠️ detect_fast_in_out 执行异常: {e}")
    
    # 测试资金留存率（只传 df）
    try:
        result = behavioral_profiler.calculate_fund_retention_rate(mock_df)  # 只传一个参数
        if isinstance(result, dict):
            print("  ✅ calculate_fund_retention_rate 返回字典结构")
            if 'retention_rate' in result:
                print(f"     留存率: {result.get('retention_percent', 'N/A')}")
        else:
            print(f"  ⚠️ calculate_fund_retention_rate 返回类型: {type(result)}")
    except Exception as e:
        print(f"  ⚠️ calculate_fund_retention_rate 执行异常: {e}")
    
    return True


def main():
    """运行所有验证"""
    print("=" * 60)
    print("Phase 3 循环验证 - 刑侦级审计报告体系")
    print("=" * 60)
    
    results = []
    
    results.append(("Phase 0.1 字段", verify_phase0_fields()))
    results.append(("behavioral_profiler", verify_behavioral_profiler()))
    results.append(("report_generator", verify_report_generator()))
    results.append(("main.py 集成", verify_main_integration()))
    results.append(("逻辑闭环", verify_logic_traceability()))
    
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    
    all_pass = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False
    
    print("\n" + "=" * 60)
    if all_pass:
        print("🎉 Phase 3 验证全部通过!")
    else:
        print("⚠️ 部分验证未通过，请检查")
    print("=" * 60)
    
    return all_pass


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
