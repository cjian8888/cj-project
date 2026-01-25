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
import financial_profiler  # Phase 2.1: 银行账户提取和工资统计
import family_finance      # Phase 3: 家庭汇总计算
import family_analyzer     # Phase 3: 家庭关系分析（真实关系）
import related_party_analyzer  # Phase 5: 调查单位往来统计
# Phase 6: P0 外部数据源解析
import pboc_account_extractor    # 6.1 人民银行银行账户
import aml_analyzer              # 6.2 人民银行反洗钱
import company_info_extractor    # 6.3 市场监管总局企业登记
import credit_report_extractor   # 6.4 征信数据
import bank_account_info_extractor  # 6.5 银行业金融机构账户
# Phase 7: P1 外部数据源解析
import vehicle_extractor            # 7.1 公安部机动车
import wealth_product_extractor     # 7.2 银行理财产品
import securities_extractor         # 7.3 证券信息
import asset_extractor              # 7.4 精准房产查询
# Phase 8: P2 外部数据源解析
import insurance_extractor          # 8.1 保险信息
import immigration_extractor        # 8.2 出入境记录
import hotel_extractor              # 8.3 旅馆住宿
import cohabitation_extractor       # 8.4 同住址/同车违章
import railway_extractor            # 8.5 铁路票面信息
import flight_extractor             # 8.6 航班进出港信息
# Phase 9: P3级外部数据源解析
import p3_data_extractor            # 9.1-9.4 驾驶证/交通违法/出境证件/12306注册
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
        # Phase 2.3: 区分个人和公司实体
        is_company = entity in companies
        
        try:
            if is_company:
                # Phase 2.3: 公司实体使用专用画像生成函数
                print(f"  [公司] 生成 {entity} 画像...")
                try:
                    company_profile = financial_profiler.build_company_profile(df, entity)
                    
                    # 转换为缓存格式（与个人画像保持一致的字段结构）
                    summary = company_profile.get('summary', {})
                    company_specific = company_profile.get('company_specific', {})
                    
                    profiles[entity] = {
                        "entityName": entity,
                        "entityType": "company",  # 标识为公司实体
                        "totalIncome": summary.get('total_income', 0),
                        "totalExpense": summary.get('total_expense', 0),
                        "transactionCount": summary.get('transaction_count', len(df)),
                        # 审计关键字段
                        "cashTotal": (company_profile.get('fund_flow', {}).get('cash_income', 0) + 
                                     company_profile.get('fund_flow', {}).get('cash_expense', 0)),
                        "thirdPartyTotal": (company_profile.get('fund_flow', {}).get('third_party_income', 0) + 
                                           company_profile.get('fund_flow', {}).get('third_party_expense', 0)),
                        "wealthTotal": company_profile.get('wealth_management', {}).get('total_amount', 0),
                        "maxTransaction": 0,  # 公司画像中暂不计算
                        "salaryRatio": 0.0,  # 公司不适用
                        # 公司不需要银行账户和工资统计
                        "bankAccounts": [],
                        "yearlySalary": {},
                        # Phase 2.3: 公司特有分析
                        "companySpecific": company_specific,
                        # Phase 3: 家庭汇总所需字段
                        "has_data": company_profile.get('has_data', True),
                        "summary": summary,
                    }
                    print(f"  [公司] {entity} 画像生成完成")
                except Exception as e:
                    print(f"  [公司] {entity} 画像生成失败: {e}")
                    # 回退到简化逻辑
                    profiles[entity] = {
                        "entityName": entity,
                        "entityType": "company",
                        "totalIncome": 0,
                        "totalExpense": 0,
                        "transactionCount": len(df),
                        "has_data": False,
                        "summary": {},
                    }
                continue
            
            # 个人实体使用现有逻辑
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
            
            # 计算现金交易总额和明细列表
            cash_total = 0
            cash_transactions = []  # 🆕 现金交易明细列表
            if 'description' in df.columns and amounts is not None:
                cash_mask = df['description'].apply(lambda x: contains_keywords(x, CASH_KEYWORDS))
                if cash_mask.any():
                    cash_df = df[cash_mask].copy()
                    cash_amounts = amounts[cash_mask]
                    cash_total = float(cash_amounts[cash_amounts > 0].sum() + abs(cash_amounts[cash_amounts < 0].sum()))
                    
                    # 🆕 构建现金交易明细（取金额最大的前20条）
                    cash_df['_amount'] = cash_amounts.abs()
                    cash_df = cash_df.nlargest(20, '_amount')
                    for _, row in cash_df.iterrows():
                        cash_transactions.append({
                            "date": str(row.get('date', ''))[:10] if row.get('date') else '',
                            "amount": float(row.get('_amount', 0)),
                            "description": str(row.get('description', ''))[:50],
                            "counterparty": str(row.get('counterparty', ''))[:30],
                            "source_file": str(row.get('数据来源', ''))[:30],
                        })
            
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
            
            # Phase 2.1: 提取银行账户信息
            try:
                bank_accounts = financial_profiler.extract_bank_accounts(df, entity)
            except Exception as e:
                print(f"  提取 {entity} 银行账户失败: {e}")
                bank_accounts = []
            
            # Phase 2.1: 计算年度工资统计
            try:
                yearly_salary = financial_profiler.calculate_yearly_salary(df, entity)
            except Exception as e:
                print(f"  计算 {entity} 年度工资失败: {e}")
                yearly_salary = {}
            
            # 🆕 计算工资总额和工资占比
            salary_total = yearly_salary.get('summary', {}).get('total', 0) if yearly_salary else 0
            salary_ratio = salary_total / income if income > 0 else 0.0
            
            profiles[entity] = {
                "entityName": entity,
                "entityType": "person",  # 标识为个人实体
                "totalIncome": income,
                "totalExpense": expense,
                "transactionCount": len(df),
                # 新增审计关键字段
                "cashTotal": cash_total,
                "cashTransactions": cash_transactions,  # 🆕 现金交易明细
                "thirdPartyTotal": third_party_total,
                "wealthTotal": wealth_total,
                "maxTransaction": max_transaction,
                "salaryTotal": salary_total,  # 🆕 工资总额
                "salaryRatio": salary_ratio,  # 🆕 正确计算工资占比
                # Phase 2.1: 银行账户和年度工资
                "bankAccounts": bank_accounts,
                "yearlySalary": yearly_salary,
                # Phase 3: 家庭汇总所需字段
                "has_data": True,
                "summary": {
                    "total_income": income,
                    "total_expense": expense,
                    "net_flow": income - expense,
                },
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
    
    # 6.5 Phase 2.2: 提取大额交易明细
    print("提取大额交易明细...")
    try:
        large_transactions = income_analyzer.extract_large_transactions(cleaned_data, persons)
        print(f"  发现 {len(large_transactions)} 笔大额交易")
    except Exception as e:
        print(f"  大额交易提取失败: {e}")
        large_transactions = []
    
    # 6.6 Phase 3: 家庭汇总计算（使用真实家庭关系）
    print("分析家庭关系...")
    try:
        # 步骤1: 使用 family_analyzer 获取真实的家庭关系
        family_tree = family_analyzer.build_family_tree(persons, data_dir)
        family_relations = family_analyzer.get_family_summary(family_tree)
        
        # 步骤2: 识别独立的家庭单元（基于同户关系）
        family_groups = {}  # person -> group_id
        group_members = {}  # group_id -> {address, members}
        
        next_group_id = 0
        for person, members in family_tree.items():
            # 获取该人员的户籍地
            person_address = None
            for member in members:
                if member.get('姓名') == person:
                    person_address = member.get('户籍地', '')
                    break
            if not person_address and members:
                person_address = members[0].get('户籍地', '')
            
            # 查找是否有已存在的家庭组使用相同地址
            found_group = None
            for gid in group_members.keys():
                gaddr = group_members[gid].get('address', '')
                if gaddr and person_address and gaddr == person_address:
                    found_group = gid
                    break
            
            if found_group is not None:
                family_groups[person] = found_group
                if person not in group_members[found_group]['members']:
                    group_members[found_group]['members'].append(person)
            else:
                family_groups[person] = next_group_id
                group_members[next_group_id] = {'address': person_address, 'members': [person]}
                next_group_id += 1
        
        # 步骤3: 构建家庭单元信息
        family_units = []
        for gid, group_info in group_members.items():
            members_list = group_info['members']
            members_with_data = [m for m in members_list if m in profiles]
            if members_with_data:
                anchor = members_with_data[0]
                for m in members_with_data:
                    if m in family_tree:
                        for mi in family_tree[m]:
                            if mi.get('姓名') == m and mi.get('与户主关系') == '户主':
                                anchor = m
                                break
                family_units.append({
                    'group_id': gid, 'anchor': anchor,
                    'members': members_with_data, 'address': group_info['address'],
                    'relations': {m: family_relations.get(m, {}) for m in members_with_data}
                })
        
        print(f"  发现 {len(family_units)} 个独立家庭单元")
        for unit in family_units:
            print(f"    - 家庭 {unit['group_id']+1}: {unit['anchor']}(户主), 成员: {unit['members']}")
        
        # 步骤4: 构建 family_summary
        all_family_members = []
        for unit in family_units:
            all_family_members.extend(unit['members'])
        all_family_members = list(set(all_family_members))
        
        family_summary = {
            # 保留完整户籍信息（用于报告生成）
            'family_tree': {p: [{
                '姓名': m.get('姓名', ''),
                '与户主关系': m.get('与户主关系', ''),
                '户籍地': m.get('户籍地', ''),
                '性别': m.get('性别', ''),
                '出生日期': m.get('出生日期', ''),
                '身份证号': m.get('身份证号', ''),
                '民族': m.get('民族', ''),
                '籍贯': m.get('籍贯', ''),
                '从业单位': m.get('从业单位', ''),
                '文化程度': m.get('文化程度', ''),
                '婚姻状况': m.get('婚姻状况', ''),
            } for m in mlist] for p, mlist in family_tree.items()},
            'family_relations': family_relations,
            'family_units': family_units,
            'family_members': all_family_members,
            'total_assets': {}, 'total_income_expense': {}, 'member_transfers': {}
        }
        
        finance_summary = family_finance.calculate_family_summary(profiles, all_family_members)
        family_summary['total_assets'] = finance_summary.get('total_assets', {})
        family_summary['total_income_expense'] = finance_summary.get('total_income_expense', {})
        family_summary['member_transfers'] = finance_summary.get('member_transfers', {})
        print(f"  家庭成员总数: {len(all_family_members)} 人")
    except Exception as e:
        import traceback
        print(f"  家庭汇总计算失败: {e}")
        traceback.print_exc()
        family_summary = {}
    
    # 6.7 Phase 5: 收入来源分类
    print("计算收入来源分类...")
    income_classifications = {}
    for entity, df in cleaned_data.items():
        if entity in companies:  # 公司不计算收入分类
            continue
        try:
            classification = financial_profiler.classify_income_sources(df, entity)
            income_classifications[entity] = classification
        except Exception as e:
            print(f"  {entity} 收入分类失败: {e}")
    print(f"  完成 {len(income_classifications)} 个人员的收入分类")
    
    # 6.8 Phase 5: 调查单位往来统计
    print("统计调查单位往来...")
    investigation_unit_flows = {}
    if config.INVESTIGATION_UNIT_KEYWORDS:  # 只有配置了关键词才执行
        for entity, df in cleaned_data.items():
            try:
                flows = related_party_analyzer.analyze_investigation_unit_flows(df, entity)
                if flows and flows.get('total_amount', 0) > 0:
                    investigation_unit_flows[entity] = flows
            except Exception as e:
                print(f"  {entity} 调查单位往来统计失败: {e}")
        print(f"  发现 {len(investigation_unit_flows)} 个实体与调查单位有往来")
    else:
        print("  未配置调查单位关键词，跳过")
    
    # ============================================
    # Phase 6: P0 外部数据源解析
    # ============================================
    
    # 6.1 人民银行银行账户
    print("提取人民银行账户信息 (6.1)...")
    try:
        pboc_accounts = pboc_account_extractor.extract_pboc_accounts(data_dir)
        print(f"  发现 {len(pboc_accounts)} 人的官方账户信息")
    except Exception as e:
        print(f"  人民银行账户提取失败: {e}")
        pboc_accounts = {}
    
    # 6.2 人民银行反洗钱数据
    print("提取反洗钱数据 (6.2)...")
    try:
        aml_data = aml_analyzer.extract_aml_data(data_dir)
        print(f"  发现 {len(aml_data)} 人的反洗钱信息")
    except Exception as e:
        print(f"  反洗钱数据提取失败: {e}")
        aml_data = {}
    
    # 6.3 市场监管总局企业登记
    print("提取企业登记信息 (6.3)...")
    try:
        company_registry = company_info_extractor.extract_company_info(data_dir)
        print(f"  发现 {len(company_registry)} 个企业登记信息")
    except Exception as e:
        print(f"  企业登记信息提取失败: {e}")
        company_registry = {}
    
    # 6.4 征信数据
    print("提取征信数据 (6.4)...")
    try:
        credit_data = credit_report_extractor.extract_credit_data(data_dir)
        print(f"  发现 {len(credit_data)} 人的征信信息")
    except Exception as e:
        print(f"  征信数据提取失败: {e}")
        credit_data = {}
    
    # 6.5 银行业金融机构账户信息
    print("提取银行账户信息 (6.5)...")
    try:
        bank_account_info = bank_account_info_extractor.extract_bank_account_info(data_dir)
        print(f"  发现 {len(bank_account_info)} 人的银行账户信息")
    except Exception as e:
        print(f"  银行账户信息提取失败: {e}")
        bank_account_info = {}
    
    # ============================================
    # Phase 7: P1 外部数据源解析
    # ============================================
    
    # 7.1 公安部机动车
    print("提取机动车信息 (7.1)...")
    try:
        vehicle_data = vehicle_extractor.extract_vehicle_data(data_dir)
        print(f"  发现 {len(vehicle_data)} 人的机动车信息")
    except Exception as e:
        print(f"  机动车信息提取失败: {e}")
        vehicle_data = {}
    
    # 7.2 银行理财产品
    print("提取理财产品信息 (7.2)...")
    try:
        wealth_product_data = wealth_product_extractor.extract_wealth_product_data(data_dir)
        print(f"  发现 {len(wealth_product_data)} 人的理财产品信息")
    except Exception as e:
        print(f"  理财产品信息提取失败: {e}")
        wealth_product_data = {}
    
    # 7.3 证券信息
    print("提取证券信息 (7.3)...")
    try:
        securities_data = securities_extractor.extract_securities_data(data_dir)
        print(f"  发现 {len(securities_data)} 人的证券信息")
    except Exception as e:
        print(f"  证券信息提取失败: {e}")
        securities_data = {}
    
    # 7.4 精准房产查询
    print("提取精准房产查询 (7.4)...")
    try:
        precise_property_data = asset_extractor.extract_precise_property_info(data_dir)
        print(f"  发现 {len(precise_property_data)} 人的精准房产信息")
    except Exception as e:
        print(f"  精准房产查询提取失败: {e}")
        precise_property_data = {}
    
    # 7.5 统一社会信用代码
    print("提取统一社会信用代码 (7.5)...")
    try:
        credit_code_data = company_info_extractor.extract_credit_code_info(data_dir)
        print(f"  发现 {len(credit_code_data)} 个企业信用代码信息")
    except Exception as e:
        print(f"  统一社会信用代码提取失败: {e}")
        credit_code_data = {}
    
    # ============================================
    # Phase 8: P2 外部数据源解析
    # ============================================
    
    # 8.1 保险信息
    print("提取保险信息 (8.1)...")
    try:
        insurance_data = insurance_extractor.extract_insurance_data(data_dir)
        print(f"  发现 {len(insurance_data)} 人/公司的保险信息")
    except Exception as e:
        print(f"  保险信息提取失败: {e}")
        insurance_data = {}
    
    # 8.2 出入境记录
    print("提取出入境记录 (8.2)...")
    try:
        immigration_data = immigration_extractor.extract_immigration_data(data_dir)
        print(f"  发现 {len(immigration_data)} 人的出入境记录")
    except Exception as e:
        print(f"  出入境记录提取失败: {e}")
        immigration_data = {}
    
    # 8.3 旅馆住宿
    print("提取旅馆住宿记录 (8.3)...")
    try:
        hotel_data = hotel_extractor.extract_hotel_data(data_dir)
        print(f"  发现 {len(hotel_data)} 人的旅馆住宿记录")
    except Exception as e:
        print(f"  旅馆住宿记录提取失败: {e}")
        hotel_data = {}
    
    # 8.4 同住址/同车违章
    print("提取同住址/同车违章 (8.4)...")
    try:
        coaddress_data = cohabitation_extractor.extract_coaddress_data(data_dir)
        coviolation_data = cohabitation_extractor.extract_coviolation_data(data_dir)
        cohabitation_data = {
            "coaddress": coaddress_data,
            "coviolation": coviolation_data
        }
        print(f"  发现 {len(coaddress_data)} 人的同住址信息, {len(coviolation_data)} 人的同车违章")
    except Exception as e:
        print(f"  同住址/同车违章提取失败: {e}")
        cohabitation_data = {"coaddress": {}, "coviolation": {}}
    
    # 8.5 铁路票面信息
    print("提取铁路票面信息 (8.5)...")
    try:
        railway_data = railway_extractor.extract_railway_data(data_dir)
        print(f"  发现 {len(railway_data)} 人的铁路出行信息")
    except Exception as e:
        print(f"  铁路票面信息提取失败: {e}")
        railway_data = {}
    
    # 8.6 航班进出港信息
    print("提取航班进出港信息 (8.6)...")
    try:
        flight_data = flight_extractor.extract_flight_data(data_dir)
        print(f"  发现 {len(flight_data)} 人的航班出行信息")
    except Exception as e:
        print(f"  航班进出港信息提取失败: {e}")
        flight_data = {}
    
    # ============================================
    # Phase 9: P3 级外部数据源解析
    # ============================================
    
    print("提取P3级数据 (9.1-9.4)...")
    try:
        p3_data = p3_data_extractor.extract_all_p3_data(data_dir)
        print(f"  驾驶证: {len(p3_data.get('driverLicenses', {}))} 人")
        print(f"  交通违法: {len(p3_data.get('trafficViolations', {}))} 人")
        print(f"  出境证件: {len(p3_data.get('exitDocuments', {}))} 人")
        print(f"  12306注册: {len(p3_data.get('railwayRegistrations', {}))} 人")
    except Exception as e:
        print(f"  P3级数据提取失败: {e}")
        p3_data = {}
    
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
        "graphData": graph_data,
        "largeTransactions": large_transactions,  # Phase 2.2: 大额交易明细
        "familySummary": family_summary,  # Phase 3: 家庭汇总
        "incomeClassifications": income_classifications,  # Phase 5: 收入来源分类
        "investigationUnitFlows": investigation_unit_flows,  # Phase 5: 调查单位往来
        # Phase 6: P0 外部数据源
        "pbocAccounts": pboc_accounts,         # 6.1 人民银行官方账户
        "amlData": aml_data,                   # 6.2 反洗钱数据
        "companyRegistry": company_registry,   # 6.3 企业登记信息
        "creditData": credit_data,             # 6.4 征信数据
        "bankAccountInfo": bank_account_info,  # 6.5 银行账户信息
        # Phase 7: P1 外部数据源
        "vehicleData": vehicle_data,           # 7.1 机动车信息
        "wealthProductData": wealth_product_data,  # 7.2 理财产品
        "securitiesData": securities_data,     # 7.3 证券信息
        "precisePropertyData": precise_property_data,  # 7.4 精准房产查询
        "creditCodeData": credit_code_data,    # 7.5 统一社会信用代码
        # Phase 8: P2 外部数据源
        "insuranceData": insurance_data,       # 8.1 保险信息
        "immigrationData": immigration_data,   # 8.2 出入境记录
        "hotelData": hotel_data,               # 8.3 旅馆住宿
        "cohabitationData": cohabitation_data, # 8.4 同住址/同车违章
        "railwayData": railway_data,           # 8.5 铁路票面信息
        "flightData": flight_data,             # 8.6 航班进出港信息
        # Phase 9: P3 外部数据源
        "p3Data": p3_data,                     # 9.x 驾驶证/交通违法/出境证件/12306
    }
    
    # ============================================
    # Phase 10: 合并外部数据到 profiles
    # ============================================
    print("合并外部数据到画像...")
    
    # 步骤1: 从户籍数据构建身份证号->姓名的映射
    id_to_name_map = {}
    name_to_id_map = {}
    
    # 从 family_relations 直接提取映射 (结构: {person_name: [list of member dicts]})
    for person_name, members in family_relations.items():
        if isinstance(members, list):
            for m in members:
                if isinstance(m, dict):
                    member_name = m.get('姓名', '')
                    id_num = m.get('身份证号')
                    if member_name and id_num:
                        # 处理科学计数法表示的身份证号
                        if isinstance(id_num, float):
                            id_str = str(int(id_num))
                        else:
                            id_str = str(id_num)
                        id_to_name_map[id_str] = member_name
                        name_to_id_map[member_name] = id_str
    
    # 从 family_tree 补充映射
    if family_tree:
        for person_name, members in family_tree.items():
            if isinstance(members, list):
                for m in members:
                    if isinstance(m, dict):
                        member_name = m.get('姓名', '')
                        id_num = m.get('身份证号')
                        if member_name and id_num and member_name not in name_to_id_map:
                            if isinstance(id_num, float):
                                id_str = str(int(id_num))
                            else:
                                id_str = str(id_num)
                            id_to_name_map[id_str] = member_name
                            name_to_id_map[member_name] = id_str

    
    print(f"  构建身份证映射: {len(id_to_name_map)} 个映射")
    
    # 步骤2: 合并房产数据到 profiles
    property_merged = 0
    for person_id, properties in precise_property_data.items():
        person_id_str = str(int(person_id)) if isinstance(person_id, float) else str(person_id)
        person_name = id_to_name_map.get(person_id_str)
        if person_name and person_name in profiles:
            profiles[person_name]['properties'] = properties
            property_merged += 1
    print(f"  合并房产数据: {property_merged} 人")
    
    # 步骤3: 合并车辆数据到 profiles
    vehicle_merged = 0
    for person_id, vehicles in vehicle_data.items():
        person_id_str = str(int(person_id)) if isinstance(person_id, float) else str(person_id)
        person_name = id_to_name_map.get(person_id_str)
        if person_name and person_name in profiles:
            profiles[person_name]['vehicles'] = vehicles
            vehicle_merged += 1
    print(f"  合并车辆数据: {vehicle_merged} 人")
    
    # 步骤4: 合并保险数据到 profiles
    insurance_merged = 0
    for person_id, insurance in insurance_data.items():
        person_id_str = str(int(person_id)) if isinstance(person_id, float) else str(person_id)
        person_name = id_to_name_map.get(person_id_str)
        if person_name and person_name in profiles:
            profiles[person_name]['insurance'] = insurance
            insurance_merged += 1
    print(f"  合并保险数据: {insurance_merged} 人/公司")
    
    # 步骤5: 合并证券数据到 profiles
    securities_merged = 0
    for person_id, securities in securities_data.items():
        person_id_str = str(int(person_id)) if isinstance(person_id, float) else str(person_id)
        person_name = id_to_name_map.get(person_id_str)
        if person_name and person_name in profiles:
            profiles[person_name]['securities'] = securities
            securities_merged += 1
    print(f"  合并证券数据: {securities_merged} 人")
    
    # 步骤6: 合并征信数据到 profiles
    credit_merged = 0
    for person_id, credit in credit_data.items():
        person_id_str = str(int(person_id)) if isinstance(person_id, float) else str(person_id)
        person_name = id_to_name_map.get(person_id_str)
        if person_name and person_name in profiles:
            profiles[person_name]['creditInfo'] = credit
            credit_merged += 1
    print(f"  合并征信数据: {credit_merged} 人")
    
    print(f"  总计合并: 房产{property_merged}+车辆{vehicle_merged}+保险{insurance_merged}+证券{securities_merged}+征信{credit_merged}")
    
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
