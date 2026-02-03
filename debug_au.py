#!/usr/bin/env python3
import json
with open('output/report_v4.json', 'r', encoding='utf-8') as f:
    r = json.load(f)

result = {
    'report_keys': list(r.keys()),
    'analysis_units_count': len(r.get('analysis_units', [])),
    'family_sections_count': len(r.get('family_sections', [])),
}

if r.get('family_sections'):
    fs0 = r['family_sections'][0]
    result['family_sections_0_keys'] = list(fs0.keys())
    if 'family_summary' in fs0:
        result['family_sections_0_summary'] = fs0['family_summary']

with open('debug_report_structure.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print('Done')
