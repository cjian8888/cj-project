#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成完整 v4 HTML 报告
"""
import json
import os
import sys
sys.path.insert(0, '.')

def main():
    print("=" * 60)
    print("生成完整 v4 HTML 报告")
    print("=" * 60)
    
    # 1. 加载新缓存并同步到 analysis_cache 目录
    print("\n【步骤1】同步缓存到 analysis_cache 目录...")
    
    cache_path = './output/analysis_results_cache.json'
    cache_dir = './output/analysis_cache'
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    
    # 保存 profiles.json
    with open(os.path.join(cache_dir, 'profiles.json'), 'w', encoding='utf-8') as f:
        json.dump(cache.get('profiles', {}), f, ensure_ascii=False, indent=2)
    print("  ✅ profiles.json 已更新")
    
    # 保存 derived_data.json（包含 analysisResults 和其他数据）
    derived_data = {
        'loan': cache.get('analysisResults', {}).get('loan', {}),
        'income': cache.get('analysisResults', {}).get('income', {}),
        'large_transactions': cache.get('largeTransactions', []),
        'family_summary': cache.get('familySummary', {}),
        'family_relations': cache.get('familySummary', {}).get('family_tree', {}),
        'family_tree': cache.get('familySummary', {}).get('family_tree', {}),
        'income_classifications': cache.get('incomeClassifications', {}),
    }
    with open(os.path.join(cache_dir, 'derived_data.json'), 'w', encoding='utf-8') as f:
        json.dump(derived_data, f, ensure_ascii=False, indent=2)
    print("  ✅ derived_data.json 已更新")
    
    # 保存 metadata.json
    metadata = {
        'version': cache.get('_meta', {}).get('version', '3.0.0'),
        'generatedAt': cache.get('_meta', {}).get('analysisTime', ''),
        'persons': cache.get('persons', []),
        'companies': cache.get('companies', []),
    }
    with open(os.path.join(cache_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print("  ✅ metadata.json 已更新")
    
    # 保存外部数据缓存
    external_keys = [
        ('precisePropertyData', 'property_data.json'),
        ('vehicleData', 'vehicle_data.json'),
        ('wealthProductData', 'wealth_data.json'),
        ('securitiesData', 'securities_data.json'),
    ]
    for key, filename in external_keys:
        data = cache.get(key, {})
        if data:
            with open(os.path.join(cache_dir, filename), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  ✅ {filename} 已保存 ({len(data)} 条)")
    
    # 2. 加载报告构建器并生成 v4 报告
    print("\n【步骤2】生成 v4 HTML 报告...")
    
    from investigation_report_builder import load_investigation_report_builder
    
    builder = load_investigation_report_builder('./output')
    if not builder:
        print("  ❌ 无法加载报告构建器")
        return
    
    print(f"  ✅ 报告构建器加载成功")
    print(f"     Profiles: {len(builder.profiles)} 个")
    print(f"     身份证映射: {len(builder._id_to_name_map)} 条")
    
    # 生成 v4 报告
    try:
        report = builder.build_report_v4()
        print(f"  ✅ v4 报告生成成功")
        
        # 保存 JSON 报告
        json_path = './output/analysis_results/report_v4.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"  ✅ JSON 报告已保存: {json_path}")
        
        # 保存 HTML 报告
        html_path = './output/analysis_results/初查报告_v4.html'
        builder.save_html_report_v3(report, html_path)
        print(f"  ✅ HTML 报告已保存: {html_path}")
        
        # 显示报告摘要
        print("\n【报告摘要】")
        preface = report.get('preface', {})
        print(f"  查询人员: {preface.get('target_persons', [])}") 
        print(f"  查询公司: {preface.get('target_companies', [])}")
        
        judgment = report.get('comprehensive_judgment', {})
        findings = judgment.get('findings', [])
        print(f"  发现问题: {len(findings)} 项")
        
        for f in findings[:3]:
            print(f"    - [{f.get('risk_level', '')}] {f.get('title', '')}")
        
    except Exception as e:
        import traceback
        print(f"  ❌ 报告生成失败: {e}")
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("✅ 完成！")
    print("=" * 60)

if __name__ == '__main__':
    main()
