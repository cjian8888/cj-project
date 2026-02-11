#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行完整分析流程并验证结果"""

import asyncio
import sys
import json
from pathlib import Path

if sys.platform == 'win32':
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from api_server import AnalysisConfig, run_analysis_refactored, serialize_analysis_results

print('=' * 70)
print('完整分析流程测试')
print('=' * 70)
print()

async def main():
    # 清理输出目录
    output_dir = Path('output')
    if output_dir.exists():
        for item in output_dir.iterdir():
            if item.is_file():
                item.unlink()
        print('✓ 已清理输出目录')
    
    # 配置
    config = AnalysisConfig(
        inputDirectory='data',
        outputDirectory='output',
        cashThreshold=50000,
        modules=None
    )
    
    print()
    print('开始分析...')
    print('-' * 70)
    
    # 运行分析
    results = await run_analysis_refactored(config)
    
    print()
    print('-' * 70)
    print('分析完成！')
    print('-' * 70)
    print()
    
    # 验证结果
    print('验证 results 结构...')
    print()
    
    if 'analysisResults' in results:
        ar = results['analysisResults']
        print(f'✓ analysisResults 存在')
        print(f'  键数量: {len(ar)}')
        print(f'  键列表: {list(ar.keys())}')
        print()
        
        # 检查关键键
        print('关键键检查:')
        keys_to_check = ['family_units_v2', 'all_family_summaries', 'family_tree', 'family_summary']
        for key in keys_to_check:
            if key in ar:
                value = ar[key]
                print(f'  ✓ {key}: 存在')
                if isinstance(value, list):
                    print(f'    类型: list, 长度: {len(value)}')
                    if len(value) > 0:
                        print(f'    第一项: {value[0]}')
                elif isinstance(value, dict):
                    print(f'    类型: dict, 子键数量: {len(value)}')
                    if len(value) > 0:
                        first_key = list(value.keys())[0]
                        print(f'    示例: {first_key} = {value[first_key]}')
            else:
                print(f'  ✗ {key}: 不存在')
        print()
        
        # 保存序列化结果用于对比
        serialized = serialize_analysis_results(ar)
        print('serialize_analysis_results 验证:')
        print()
        for key in keys_to_check:
            if key in serialized:
                value = serialized[key]
                if key == 'family_units_v2':
                    # 检查是否为正确的格式
                    if isinstance(value, list) and len(value) > 0:
                        if 'members' in value[0]:
                            print(f'  ✓ {key}: 包含家庭成员数据')
                            print(f'    {value[0]}')
                        else:
                            print(f'  ? {key}: 格式可能不正确')
                            print(f'    {value}')
                    else:
                        print(f'  ? {key}: 空或格式错误')
                else:
                    print(f'  ✓ {key}: 存在')
        
        # 保存完整结果
        output_file = output_dir / 'test_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        print()
        print(f'✓ 完整结果已保存到: {output_file}')
        
        # 保存序列化后的 analysisResults
        serialized_file = output_dir / 'test_serialized.json'
        with open(serialized_file, 'w', encoding='utf-8') as f:
            json.dump(serialized, f, ensure_ascii=False, indent=2, default=str)
        print(f'✓ 序列化结果已保存到: {serialized_file}')
    
    print()
    print('=' * 70)
    print('测试完成！')
    print('=' * 70)

asyncio.run(main())
