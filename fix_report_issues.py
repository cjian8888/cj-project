#!/usr/bin/env python3
"""
修复报告中的问题清单数据
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from investigation_report_builder import InvestigationReportBuilder

def fix_report_issues():
    """重新构建报告以修复问题清单"""
    
    cache_dir = os.path.join('output', 'analysis_cache')
    output_dir = os.path.join('output', 'analysis_results')
    
    # 加载缓存
    cache_files = {
        'profiles': 'profiles.json',
        'derived_data': 'derived_data.json',
        'suspicions': 'suspicions.json',
        'graph_data': 'graph_data.json',
        'metadata': 'metadata.json',
    }
    
    analysis_cache = {}
    for key, filename in cache_files.items():
        filepath = os.path.join(cache_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                analysis_cache[key] = json.load(f)
            print(f"✅ 加载: {filename}")
        else:
            print(f"⚠️  缺失: {filename}")
            analysis_cache[key] = {}
    
    # 创建报告构建器
    builder = InvestigationReportBuilder(
        output_dir=output_dir,
        analysis_cache=analysis_cache
    )
    
    # 加载配置
    config_path = os.path.join('config', 'primary_targets.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        builder.load_primary_targets_config(config_data)
        print("✅ 加载配置: config/primary_targets.json")
    
    # 构建报告
    print("\n🔨 构建报告...")
    report = builder.build_report_v5()
    
    print("\n✅ 报告构建完成!")
    
    # 检查问题清单
    issues = report.get('conclusion', {}).get('issues', [])
    print(f"\n问题清单 ({len(issues)}项):")
    for issue in issues[:5]:
        print(f"  - {issue.get('person')}: {issue.get('issue_type')} - {issue.get('description', '')[:50]}...")
    
    return report

if __name__ == '__main__':
    report = fix_report_issues()
    
    # 保存报告
    output_path = os.path.join('output', 'analysis_results', 'report_fixed.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report.to_dict() if hasattr(report, 'to_dict') else report, f, ensure_ascii=False, indent=2)
    print(f"\n💾 报告已保存: {output_path}")
