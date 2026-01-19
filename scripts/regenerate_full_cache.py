#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新生成完整的分析结果缓存文件
包含所有分析模块的结果
"""

import os
import sys
import json
import gc
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import file_categorizer
import data_cleaner
import flow_visualizer
import financial_profiler
import suspicion_detector
import loan_analyzer
import income_analyzer
import related_party_analyzer
import time_series_analyzer

def get_directory_fingerprint(directory):
    """获取目录指纹"""
    file_count = 0
    total_size = 0
    latest_modified = 0
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith(('.xlsx', '.xls', '.csv')):
                file_count += 1
                filepath = os.path.join(root, f)
                stat = os.stat(filepath)
                total_size += stat.st_size
                latest_modified = max(latest_modified, stat.st_mtime)
    return {
        "exists": True,
        "fileCount": file_count,
        "totalSize": total_size,
        "latestModified": latest_modified
    }

def serialize_profiles(profiles):
    """序列化画像数据"""
    result = {}
    for entity, profile in profiles.items():
        if not profile or profile.get("has_data") == False:
            result[entity] = {
                "entityName": entity,
                "totalIncome": 0.0,
                "totalExpense": 0.0,
                "transactionCount": 0,
            }
            continue
        
        summary = profile.get("summary", {})
        income_structure = profile.get("income_structure", {})
        
        total_income = summary.get("total_income") or income_structure.get("total_income", 0)
        total_expense = summary.get("total_expense") or income_structure.get("total_expense", 0)
        transaction_count = summary.get("transaction_count", 0)
        
        result[entity] = {
            "entityName": entity,
            "totalIncome": float(total_income) if total_income else 0.0,
            "totalExpense": float(total_expense) if total_expense else 0.0,
            "transactionCount": int(transaction_count) if transaction_count else 0,
        }
    return result

def serialize_suspicions(suspicions):
    """序列化疑点数据"""
    result = {
        "directTransfers": [],
        "cashCollisions": [],
        "hiddenAssets": {},
        "fixedFrequency": {},
        "cashTimingPatterns": [],
        "holidayTransactions": {},
        "amountPatterns": {},
    }
    
    # 转换直接转账
    for tx in suspicions.get("direct_transfers", []):
        direction = tx.get("direction", "payment")
        if direction == "payment":
            from_entity = str(tx.get("person", ""))
            to_entity = str(tx.get("company", ""))
        else:
            from_entity = str(tx.get("company", ""))
            to_entity = str(tx.get("person", ""))
        
        result["directTransfers"].append({
            "from": from_entity,
            "to": to_entity,
            "amount": float(tx.get("amount", 0)),
            "date": str(tx.get("date", "")),
            "description": str(tx.get("description", "")),
        })
    
    # 转换现金碰撞
    for collision in suspicions.get("cash_collisions", []):
        result["cashCollisions"].append({
            "person1": str(collision.get("withdrawal_entity", collision.get("person1", ""))),
            "person2": str(collision.get("deposit_entity", collision.get("person2", ""))),
            "time1": str(collision.get("withdrawal_date", collision.get("time1", ""))),
            "time2": str(collision.get("deposit_date", collision.get("time2", ""))),
            "amount1": float(collision.get("withdrawal_amount", collision.get("amount1", 0))),
            "amount2": float(collision.get("deposit_amount", collision.get("amount2", 0))),
        })
    
    return result

def serialize_list_with_dates(data_list):
    """序列化包含日期对象的列表"""
    import pandas as pd
    
    def convert_item(item):
        if isinstance(item, dict):
            return {k: convert_value(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [convert_item(i) for i in item]
        else:
            return convert_value(item)
    
    def convert_value(v):
        if v is None:
            return None
        if isinstance(v, (datetime, pd.Timestamp)):
            return v.strftime('%Y-%m-%d') if pd.notna(v) else None
        if isinstance(v, (int, float)):
            if pd.isna(v):
                return None
            return float(v) if not isinstance(v, bool) else v
        if isinstance(v, dict):
            return {str(k): convert_value(vv) for k, vv in v.items()}
        if isinstance(v, list):
            return [convert_value(item) for item in v]
        return str(v)
    
    return [convert_item(item) for item in data_list]

def serialize_analysis_results(analysis_results):
    """
    序列化分析结果
    
    重要: 前端期望 income.details 和 loan.details 包含所有带 _type 标记的条目
    需要将各子分类合并到 details 数组中
    """
    import pandas as pd
    
    def convert_value(v):
        # 处理 datetime 对象
        if isinstance(v, (datetime, pd.Timestamp)):
            return v.strftime('%Y-%m-%d') if pd.notna(v) else None
        elif isinstance(v, (int, float)):
            if pd.isna(v):
                return None
            return float(v) if not isinstance(v, bool) else v
        elif isinstance(v, dict):
            return {str(k): convert_value(vv) for k, vv in v.items()}
        elif isinstance(v, list):
            return [convert_value(item) for item in v]
        elif v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        else:
            return str(v)
    
    def build_income_details(income_data):
        """将 income 各子分类合并到 details 数组，添加 _type 标记"""
        details = []
        
        # 映射: 后端字段名 -> 前端 _type
        type_mapping = {
            'high_risk': 'high_risk',
            'medium_risk': 'medium_risk',
            'large_single_income': 'large_single',
            'large_individual_income': 'large_individual',
            'unknown_source_income': 'unknown_source',
            'same_source_multi': 'same_source_multi',
            'regular_non_salary': 'regular_non_salary',
            'potential_bribe_installment': 'bribe_installment',
        }
        
        for backend_key, frontend_type in type_mapping.items():
            items = income_data.get(backend_key, [])
            for item in items:
                entry = convert_value(item) if isinstance(item, dict) else item
                if isinstance(entry, dict):
                    entry['_type'] = frontend_type
                    details.append(entry)
        
        return details
    
    def build_loan_details(loan_data):
        """将 loan 各子分类合并到 details 数组，添加 _type 标记"""
        details = []
        
        # 映射: 后端字段名 -> 前端 _type
        type_mapping = {
            'bidirectional_flows': 'bidirectional',
            'online_loan_platforms': 'online_loan',
            'regular_repayments': 'regular_repayment',
            'loan_pairs': 'loan_pair',
            'no_repayment_loans': 'no_repayment',
            'abnormal_interest': 'abnormal_interest',
        }
        
        for backend_key, frontend_type in type_mapping.items():
            items = loan_data.get(backend_key, [])
            for item in items:
                entry = convert_value(item) if isinstance(item, dict) else item
                if isinstance(entry, dict):
                    entry['_type'] = frontend_type
                    details.append(entry)
        
        return details
    
    result = {}
    
    # 处理 income 数据
    income_data = analysis_results.get('income', {})
    result['income'] = {
        'summary': convert_value(income_data.get('summary', {})),
        'details': build_income_details(income_data),
        # 保留原始子分类数据（用于 graphData.report）
        **{k: convert_value(v) for k, v in income_data.items() if k not in ['summary']}
    }
    
    # 处理 loan 数据
    loan_data = analysis_results.get('loan', {})
    result['loan'] = {
        'summary': convert_value(loan_data.get('summary', {})),
        'details': build_loan_details(loan_data),
        # 保留原始子分类数据
        **{k: convert_value(v) for k, v in loan_data.items() if k not in ['summary']}
    }
    
    # 处理其他分析结果
    for key, value in analysis_results.items():
        if key not in ['income', 'loan']:
            result[key] = convert_value(value)
    
    return result

def main():
    print("=" * 60)
    print("开始生成完整分析缓存...")
    print("=" * 60)
    
    # 配置
    data_dir = config.DATA_DIR
    cache_path = "./output/analysis_results_cache.json"
    
    # 1. 扫描文件
    print("\n[1/8] 扫描数据目录...")
    categorized_files = file_categorizer.categorize_files(data_dir)
    persons = list(categorized_files['persons'].keys())
    companies = list(categorized_files['companies'].keys())
    print(f"  - 发现 {len(persons)} 个人员, {len(companies)} 个企业")
    
    # 2. 清洗数据
    print("\n[2/8] 清洗数据...")
    cleaned_data = {}
    
    for i, p in enumerate(persons):
        p_files = categorized_files['persons'].get(p, [])
        if p_files:
            df, _ = data_cleaner.clean_and_merge_files(p_files, p)
            if df is not None and not df.empty:
                cleaned_data[p] = df
        print(f"  - 人员 {i+1}/{len(persons)}: {p}")
    
    for i, c in enumerate(companies):
        c_files = categorized_files['companies'].get(c, [])
        if c_files:
            df, _ = data_cleaner.clean_and_merge_files(c_files, c)
            if df is not None and not df.empty:
                cleaned_data[c] = df
        print(f"  - 企业 {i+1}/{len(companies)}: {c}")
    
    print(f"  - 清洗完成，共 {len(cleaned_data)} 个实体")
    
    all_persons = persons
    all_companies = companies
    
    # 3. 生成资金画像
    print("\n[3/8] 生成资金画像...")
    profiles = {}
    for entity, df in cleaned_data.items():
        try:
            profiles[entity] = financial_profiler.generate_profile_report(df, entity)
            print(f"  - {entity}: 完成")
        except Exception as e:
            print(f"  - {entity}: 失败 ({e})")
    
    # 4. 疑点检测
    print("\n[4/8] 疑点检测...")
    try:
        suspicions = suspicion_detector.run_all_detections(cleaned_data, all_persons, all_companies)
        print(f"  - 直接转账: {len(suspicions.get('direct_transfers', []))} 条")
        print(f"  - 现金碰撞: {len(suspicions.get('cash_collisions', []))} 条")
    except Exception as e:
        print(f"  - 疑点检测失败: {e}")
        suspicions = {"direct_transfers": [], "cash_collisions": []}
    
    # 5. 高级分析模块
    print("\n[5/8] 运行高级分析模块...")
    analysis_results = {}
    
    # 借贷分析
    try:
        print("  - 借贷分析...")
        analysis_results["loan"] = loan_analyzer.analyze_loan_behaviors(cleaned_data, all_persons)
        loan_summary = analysis_results["loan"].get("summary", {})
        print(f"    双向往来: {loan_summary.get('双向往来关系数', 0)}")
        print(f"    网贷平台: {loan_summary.get('网贷平台交易数', 0)}")
    except Exception as e:
        print(f"    失败: {e}")
    
    # 收入分析
    try:
        print("  - 收入分析...")
        analysis_results["income"] = income_analyzer.detect_suspicious_income(cleaned_data, all_persons)
        income_summary = analysis_results["income"].get("summary", {})
        print(f"    规律非工资收入: {income_summary.get('规律性非工资收入', 0)}")
    except Exception as e:
        print(f"    失败: {e}")
    
    # 关联方分析
    try:
        print("  - 关联方分析...")
        analysis_results["relatedParty"] = related_party_analyzer.analyze_related_party_flows(
            cleaned_data, all_persons
        )
    except Exception as e:
        print(f"    失败: {e}")
    
    # 时序分析
    try:
        print("  - 时序分析...")
        analysis_results["timeSeries"] = time_series_analyzer.analyze_time_series(
            cleaned_data, all_persons
        )
    except Exception as e:
        print(f"    失败: {e}")
    
    # 6. 生成图谱数据
    print("\n[6/8] 生成图谱数据...")
    try:
        flow_stats = flow_visualizer._calculate_flow_stats(cleaned_data, persons)
        nodes, edges, edge_stats = flow_visualizer._prepare_graph_data(
            flow_stats, persons, companies
        )
        
        # 采样
        max_nodes, max_edges = 200, 500
        sorted_nodes = sorted(nodes, key=lambda x: x.get('size', 0), reverse=True)
        sampled_nodes = sorted_nodes[:max_nodes]
        sampled_node_ids = {node['id'] for node in sampled_nodes}
        
        sampled_edges = [e for e in edges if e['from'] in sampled_node_ids and e['to'] in sampled_node_ids]
        sampled_edges.sort(key=lambda x: x.get('value', 0), reverse=True)
        sampled_edges = sampled_edges[:max_edges]
        
        loan_results = analysis_results.get("loan", {})
        income_results = analysis_results.get("income", {})
        
        graph_data = {
            "nodes": sampled_nodes,
            "edges": sampled_edges,
            "sampling": {
                "totalNodes": len(nodes),
                "totalEdges": len(edges),
                "sampledNodes": len(sampled_nodes),
                "sampledEdges": len(sampled_edges),
                "message": "为保证流畅度，仅展示核心资金网络"
            },
            "stats": {
                "nodeCount": len(nodes),
                "edgeCount": len(edges),
                "corePersonCount": len(persons),
                "corePersonNames": persons,
                "involvedCompanyCount": len(companies),
                "highRiskCount": len(income_results.get("high_risk", [])),
                "mediumRiskCount": len(income_results.get("medium_risk", [])),
                "loanPairCount": len(loan_results.get("bidirectional_flows", [])),
                "noRepayCount": len(loan_results.get("no_repayment_loans", [])),
                "coreEdgeCount": edge_stats.get("core", 0),
                "companyEdgeCount": edge_stats.get("company", 0),
                "otherEdgeCount": edge_stats.get("other", 0),
            },
            "report": {
                "loan_pairs": serialize_list_with_dates(loan_results.get("bidirectional_flows", [])),
                "no_repayment_loans": serialize_list_with_dates(loan_results.get("no_repayment_loans", [])),
                "high_risk_income": serialize_list_with_dates(income_results.get("high_risk", [])),
                "online_loans": serialize_list_with_dates(loan_results.get("online_loan_platforms", []))
            }
        }
        print(f"  - 节点: {len(sampled_nodes)}, 边: {len(sampled_edges)}")
    except Exception as e:
        print(f"  图谱生成失败: {e}")
        graph_data = None
    
    # 7. 组装完整结果
    print("\n[7/8] 组装缓存数据...")
    fingerprint = get_directory_fingerprint(data_dir)
    
    result = {
        "_meta": {
            "version": "3.0.0",
            "inputDirectory": os.path.normpath(data_dir),
            "outputDirectory": os.path.normpath("./output"),
            "analysisTime": datetime.now().isoformat(),
            "analysisTimestamp": datetime.now().timestamp(),
            "sourceFingerprint": fingerprint
        },
        "persons": all_persons,
        "companies": all_companies,
        "profiles": serialize_profiles(profiles),
        "suspicions": serialize_suspicions(suspicions),
        "analysisResults": serialize_analysis_results(analysis_results),
        "graphData": graph_data
    }
    
    # 8. 保存到文件
    print("\n[8/8] 保存缓存...")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 验证
    with open(cache_path, 'r', encoding='utf-8') as f:
        verify = json.load(f)
    
    print("\n" + "=" * 60)
    print("✓ 缓存生成完成!")
    print("=" * 60)
    print(f"  人员: {len(verify.get('persons', []))}")
    print(f"  企业: {len(verify.get('companies', []))}")
    print(f"  画像: {len(verify.get('profiles', {}))}")
    print(f"  直接转账: {len(verify.get('suspicions', {}).get('directTransfers', []))}")
    print(f"  分析结果: {list(verify.get('analysisResults', {}).keys())}")
    print(f"  图谱节点: {len(verify.get('graphData', {}).get('nodes', []))}")
    
    # 释放内存
    del cleaned_data
    gc.collect()

if __name__ == "__main__":
    main()
