#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查报告构建器的 derived_data 结构
"""
import json
import sys
sys.path.insert(0, '.')

from investigation_report_builder import load_investigation_report_builder

builder = load_investigation_report_builder('./output')
if not builder:
    print('Failed to load builder')
    exit(1)

result = {
    'derived_data_keys': list(builder.derived_data.keys()),
    'family_summary_exists': 'family_summary' in builder.derived_data,
    'familySummary_exists': 'familySummary' in builder.derived_data,
}

fs = builder.derived_data.get('family_summary') or builder.derived_data.get('familySummary') or {}
result['family_summary_keys'] = list(fs.keys()) if fs else []
result['family_members'] = fs.get('family_members', [])
result['total_income'] = fs.get('total_income_expense', {}).get('total_income', 0)

with open('debug_derived_data.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(json.dumps(result, ensure_ascii=False, indent=2))
