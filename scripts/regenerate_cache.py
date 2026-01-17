#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新生成分析结果缓存文件（增强版）
包含完整的 loan 和 income 分析结果
"""

import os
import sys
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import file_categorizer
import data_cleaner
import flow_visualizer
import loan_analyzer
import income_analyzer
import gc

def main():
    print("开始重新生成缓存...")
    
    # 配置
    data_dir = config.DATA_DIR
    cache_path = "./output/analysis_results_cache.json"
    
    # 1. 扫描文件
    print("扫描数据目录...")
    categorized_files = file_categorizer.categorize_files(data_dir)
    persons = list(categorized_files['persons'].keys())
    companies = list(categorized_files['companies'].keys())
    print(f"发现 {len(persons)} 个人员, {len(companies)} 个企业")
    
    # 2. 清洗数据
    print("清洗数据...")
    cleaned_data = {}
    
    for p in persons:
        p_files = categorized_files['persons'].get(p, [])
        if p_files:
            df, _ = data_cleaner.clean_and_merge_files(p_files, p)
            if df is not None and not df.empty:
                cleaned_data[p] = df
    
    for c in companies:
        c_files = categorized_files['companies'].get(c, [])
        if c_files:
            df, _ = data_cleaner.clean_and_merge_files(c_files, c)
            if df is not None and not df.empty:
                cleaned_data[c] = df
    
    print(f"清洗完成，共 {len(cleaned_data)} 个实体")
    
    # 3. 生成资金画像（增强版 - 与后端 serialize_profiles 保持一致）
    print("生成资金画像...")
    
    # 现金相关关键词
    CASH_KEYWORDS = ['取现', '存现', '取款', '存款', 'ATM', '现金']
    # 第三方支付关键词
    THIRD_PARTY_KEYWORDS = ['支付宝', '微信', '财付通', '云闪付', '京东支付']
    # 理财关键词
    WEALTH_KEYWORDS = ['理财', '基金', '定存', '存款', '结息', '股票', '债券']
    
    def contains_keywords(text, keywords):
        if not text:
            return False
        text = str(text).upper()
        return any(kw.upper() in text for kw in keywords)
    
    profiles = {}
    for entity, df in cleaned_data.items():
        try:
            # 处理金额字段
            if '金额' in df.columns:
                amounts = df['金额']
            elif 'income' in df.columns and 'expense' in df.columns:
                amounts = df['income'].fillna(0) - df['expense'].fillna(0)
            else:
                amounts = None
            
            income = 0
            expense = 0
            if amounts is not None:
                income = float(amounts[amounts > 0].sum())
                expense = float(abs(amounts[amounts < 0].sum()))
            
            # 计算现金交易总额
            cash_total = 0
            if 'description' in df.columns and amounts is not None:
                cash_mask = df['description'].apply(lambda x: contains_keywords(x, CASH_KEYWORDS))
                if cash_mask.any():
                    cash_amounts = amounts[cash_mask]
                    cash_total = float(cash_amounts[cash_amounts > 0].sum() + abs(cash_amounts[cash_amounts < 0].sum()))
            
            # 计算第三方支付交易总额
            third_party_total = 0
            if 'counterparty' in df.columns and amounts is not None:
                tp_mask = df['counterparty'].apply(lambda x: contains_keywords(x, THIRD_PARTY_KEYWORDS))
                if tp_mask.any():
                    tp_amounts = amounts[tp_mask]
                    third_party_total = float(tp_amounts[tp_amounts > 0].sum() + abs(tp_amounts[tp_amounts < 0].sum()))
            
            # 计算理财交易总额
            wealth_total = 0
            if 'description' in df.columns and amounts is not None:
                wealth_mask = df['description'].apply(lambda x: contains_keywords(x, WEALTH_KEYWORDS))
                if wealth_mask.any():
                    wealth_amounts = amounts[wealth_mask]
                    wealth_total = float(wealth_amounts[wealth_amounts > 0].sum() + abs(wealth_amounts[wealth_amounts < 0].sum()))
            
            # 计算最大单笔交易
            max_transaction = 0
            if amounts is not None and len(amounts) > 0:
                max_transaction = float(amounts.abs().max())
            
            profiles[entity] = {
                "entityName": entity,
                "totalIncome": income,
                "totalExpense": expense,
                "transactionCount": len(df),
                # 新增审计关键字段
                "cashTotal": cash_total,
                "thirdPartyTotal": third_party_total,
                "wealthTotal": wealth_total,
                "maxTransaction": max_transaction,
                "salaryRatio": 0.0,  # 简化版不计算工资占比
            }
        except Exception as e:
            print(f"  生成 {entity} 画像失败: {e}")
    
    # 4. 生成图谱数据
    print("生成图谱数据...")
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
        
        graph_data = {
            "nodes": sampled_nodes,
            "edges": sampled_edges,
            "sampling": {
                "totalNodes": len(nodes),
                "totalEdges": len(edges),
                "sampledNodes": len(sampled_nodes),
                "sampledEdges": len(sampled_edges),
                "message": "为保证流畅度，仅展示核心资金网络，完整数据请查看 Excel 报告。"
            },
            "stats": {
                "nodeCount": len(nodes),
                "edgeCount": len(edges),
                "corePersonCount": len(persons),
                "corePersonNames": persons,
                "involvedCompanyCount": len(companies),
                "highRiskCount": 0,
                "mediumRiskCount": 0,
                "loanPairCount": 0,
                "noRepayCount": 0,
                "coreEdgeCount": edge_stats.get("core", 0),
                "companyEdgeCount": edge_stats.get("company", 0),
                "otherEdgeCount": edge_stats.get("other", 0),
            },
            "report": {
                "loan_pairs": [],
                "no_repayment_loans": [],
                "high_risk_income": [],
                "online_loans": []
            }
        }
        print(f"图谱生成完成: {len(sampled_nodes)} 节点, {len(sampled_edges)} 边")
    except Exception as e:
        print(f"图谱生成失败: {e}")
        graph_data = None
    
    # 5. 运行借贷分析
    print("运行借贷分析...")
    try:
        loan_results = loan_analyzer.analyze_loan_behaviors(cleaned_data, persons)
        print(f"  发现 {loan_results['summary'].get('双向往来关系数', 0)} 个双向往来")
        print(f"  发现 {loan_results['summary'].get('网贷平台交易数', 0)} 个网贷交易")
    except Exception as e:
        print(f"  借贷分析失败: {e}")
        loan_results = {"summary": {}, "bidirectional_flows": [], "online_loan_platforms": []}
    
    # 6. 运行收入分析
    print("运行收入分析...")
    try:
        income_results = income_analyzer.detect_suspicious_income(cleaned_data, persons)
        print(f"  发现 {income_results['summary'].get('规律性非工资收入', 0)} 个规律非工资收入")
    except Exception as e:
        print(f"  收入分析失败: {e}")
        income_results = {"summary": {}, "regular_non_salary": []}
    
    # 7. 序列化分析结果（与 api_server 相同的逻辑）
    def serialize_analysis_results(loan_data, income_data):
        """序列化分析结果为前端期望的格式"""
        result = {
            "loan": {
                "summary": loan_data.get("summary", {}),
                "details": []
            },
            "income": {
                "summary": income_data.get("summary", {}),
                "details": []
            },
            "aggregation": {
                "rankedEntities": [],
                "summary": {"极高风险实体数": 0, "高风险实体数": 0}
            }
        }
        
        # 合并 loan details
        for item in loan_data.get("bidirectional_flows", []):
            result["loan"]["details"].append({**item, "_type": "bidirectional"})
        for item in loan_data.get("online_loan_platforms", []):
            result["loan"]["details"].append({**item, "_type": "online_loan"})
        for item in loan_data.get("regular_repayments", []):
            result["loan"]["details"].append({**item, "_type": "regular_repayment"})
        for item in loan_data.get("loan_pairs", []):
            result["loan"]["details"].append({**item, "_type": "loan_pair"})
        for item in loan_data.get("no_repayment_loans", []):
            result["loan"]["details"].append({**item, "_type": "no_repayment"})
        
        # 合并 income details
        for item in income_data.get("regular_non_salary", []):
            result["income"]["details"].append({**item, "_type": "regular_non_salary"})
        for item in income_data.get("large_individual_income", []):
            result["income"]["details"].append({**item, "_type": "large_individual"})
        for item in income_data.get("unknown_source_income", []):
            result["income"]["details"].append({**item, "_type": "unknown_source"})
        for item in income_data.get("large_single_income", []):
            result["income"]["details"].append({**item, "_type": "large_single"})
        for item in income_data.get("same_source_multi", []):
            result["income"]["details"].append({**item, "_type": "same_source_multi"})
        for item in income_data.get("high_risk", []):
            result["income"]["details"].append({**item, "_type": "high_risk"})
        
        print(f"  序列化: loan.details={len(result['loan']['details'])}, income.details={len(result['income']['details'])}")
        return result
    
    analysis_results = serialize_analysis_results(loan_results, income_results)
    
    # 8. 获取目录指纹
    from datetime import datetime
    file_count = 0
    total_size = 0
    latest_modified = 0
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if f.endswith(('.xlsx', '.xls', '.csv')):
                file_count += 1
                filepath = os.path.join(root, f)
                stat = os.stat(filepath)
                total_size += stat.st_size
                latest_modified = max(latest_modified, stat.st_mtime)
    
    # 9. 组装结果（包含元数据）
    result = {
        "_meta": {
            "version": "3.0.0",
            "inputDirectory": os.path.normpath(data_dir),
            "outputDirectory": os.path.normpath("./output"),
            "analysisTime": datetime.now().isoformat(),
            "analysisTimestamp": datetime.now().timestamp(),
            "sourceFingerprint": {
                "exists": True,
                "fileCount": file_count,
                "totalSize": total_size,
                "latestModified": latest_modified
            }
        },
        "persons": persons,
        "companies": companies,
        "profiles": profiles,
        "suspicions": {
            "directTransfers": [],
            "cashCollisions": []
        },
        "analysisResults": analysis_results,
        "graphData": graph_data
    }
    
    # 10. 保存到文件（使用自定义编码器处理日期）
    import pandas as pd
    
    class CustomJSONEncoder(json.JSONEncoder):
        """自定义 JSON 编码器，处理不可序列化的类型"""
        def default(self, obj):
            if isinstance(obj, (pd.Timestamp, datetime)):
                return obj.isoformat() if hasattr(obj, 'isoformat') else str(obj)
            if hasattr(obj, 'item'):  # numpy types
                return obj.item()
            if isinstance(obj, (set, frozenset)):
                return list(obj)
            return str(obj)
    
    print(f"保存缓存到 {cache_path}...")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
    
    # 验证
    with open(cache_path, 'r', encoding='utf-8') as f:
        verify = json.load(f)
    print(f"✓ 缓存验证成功: {len(verify.get('persons', []))} 人员")
    
    # 释放内存
    del cleaned_data
    gc.collect()
    
    print("✓ 缓存重新生成完成!")

if __name__ == "__main__":
    main()
