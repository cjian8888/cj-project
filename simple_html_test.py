#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单HTML测试"""

import asyncio
if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from api_server import serialize_analysis_results, _render_report_to_html

print('='*80)
print('HTML渲染测试')
print('='*80)
print()

# 创建模拟报告数据
report = {
    'caseInfo': {
        'caseNumber': '测试案件',
        'caseTitle': '测试标题',
        'investigator': '测试人员'
    },
    'familyUnits': [
        {
            'group_id': 0,
            'anchor': '张三',
            'members': ['张三', '李四'],
            'address': '上海市浦东新区'
        }
    ],
    'allFamilySummaries': {
        '家庭1': {
            'total_assets': 5000000,
            'total_income': 200000
        }
    },
    'familyTree': {
        '张三': [{'姓名': '张三', '与户主关系': '户主'}],
        '李四': [{'姓名': '李四', '与户主关系': '配偶'}]
    }
}

print('模拟报告数据创建完成')
print()

# 渲染HTML
print('渲染HTML...')
html_content = _render_report_to_html(report)

print(f'HTML长度: {len(html_content)} 字符')
print()

# 保存HTML
html_path = 'output/test_simple_report.html'
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f'✓ HTML已保存: {html_path}')
print()

# 展示HTML内容
print('='*80)
print('HTML内容预览 (前300行)')
print('='*80)
print()

lines = html_content.split('\n')
for i, line in enumerate(lines[:300], 1):
    print(f'{i:4d}: {line}')

print()
print('='*80)
print(f'HTML总行数: {len(lines)}')
print('='*80)
