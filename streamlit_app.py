#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金穿透与关联排查系统 - Streamlit 交互式界面

功能特性：
- 文件上传与管理
- 模块化分析执行
- 实时结果展示
- 报告下载
"""

import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import json

# 导入系统模块
import config
import utils
import file_categorizer
import data_cleaner
import data_extractor
import financial_profiler
import suspicion_detector
import report_generator
import family_analyzer
import asset_analyzer
import data_validator
import fund_penetration
import related_party_analyzer
import multi_source_correlator
import loan_analyzer
import income_analyzer
import flow_visualizer
import ml_analyzer
import time_series_analyzer
import clue_aggregator

# 配置页面
st.set_page_config(
    page_title="资金穿透与关联排查系统",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化session state
if 'data_directory' not in st.session_state:
    st.session_state.data_directory = None
if 'output_directory' not in st.session_state:
    st.session_state.output_directory = './output_streamlit'
if 'cleaned_data' not in st.session_state:
    st.session_state.cleaned_data = {}
if 'all_persons' not in st.session_state:
    st.session_state.all_persons = []
if 'all_companies' not in st.session_state:
    st.session_state.all_companies = []
if 'profiles' not in st.session_state:
    st.session_state.profiles = {}
if 'suspicions' not in st.session_state:
    st.session_state.suspicions = {}
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}


def create_output_directories(base_dir: str) -> Dict[str, str]:
    """创建输出目录结构"""
    dirs = {
        'base': base_dir,
        'cleaned_data': os.path.join(base_dir, 'cleaned_data'),
        'cleaned_persons': os.path.join(base_dir, 'cleaned_data', '个人'),
        'cleaned_companies': os.path.join(base_dir, 'cleaned_data', '公司'),
        'analysis_results': os.path.join(base_dir, 'analysis_results'),
        'logs': os.path.join(base_dir, 'logs')
    }
    
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    
    return dirs


def scan_files(data_directory: str) -> tuple:
    """文件扫描与分类"""
    with st.spinner('正在扫描文件...'):
        categorized_files = file_categorizer.categorize_files(data_directory)
        persons = list(categorized_files['persons'].keys())
        companies = list(categorized_files['companies'].keys())
        
        return categorized_files, persons, companies


def clean_data(categorized_files: Dict, persons: List[str], companies: List[str], 
               output_dirs: Dict) -> Dict:
    """数据清洗与合并"""
    cleaned_data = {}
    progress_bar = st.progress(0)
    total = len(persons) + len(companies)
    current = 0
    
    # 清洗个人数据
    for person_name in persons:
        file_path = os.path.join(output_dirs['cleaned_persons'], f'{person_name}_合并流水.xlsx')
        person_files = categorized_files['persons'].get(person_name, [])
        
        if person_files:
            try:
                df_merged, stats = data_cleaner.clean_and_merge_files(person_files, person_name)
                if not df_merged.empty:
                    data_cleaner.save_formatted_excel(df_merged, file_path)
                    # 填充空值
                    if 'income' in df_merged.columns: df_merged['income'] = df_merged['income'].fillna(0)
                    if 'expense' in df_merged.columns: df_merged['expense'] = df_merged['expense'].fillna(0)
                    if 'counterparty' in df_merged.columns: df_merged['counterparty'] = df_merged['counterparty'].fillna('').astype(str)
                    if 'description' in df_merged.columns: df_merged['description'] = df_merged['description'].fillna('').astype(str)
                    cleaned_data[person_name] = df_merged
            except Exception as e:
                st.error(f'清洗失败 {person_name}: {e}')
        
        current += 1
        progress_bar.progress(current / total)
    
    # 清洗公司数据
    for company_name in companies:
        file_path = os.path.join(output_dirs['cleaned_companies'], f'{company_name}_合并流水.xlsx')
        company_files = categorized_files['companies'].get(company_name, [])
        
        if company_files:
            try:
                df_merged, stats = data_cleaner.clean_and_merge_files(company_files, company_name)
                if not df_merged.empty:
                    data_cleaner.save_formatted_excel(df_merged, file_path)
                    # 填充空值
                    if 'income' in df_merged.columns: df_merged['income'] = df_merged['income'].fillna(0)
                    if 'expense' in df_merged.columns: df_merged['expense'] = df_merged['expense'].fillna(0)
                    if 'counterparty' in df_merged.columns: df_merged['counterparty'] = df_merged['counterparty'].fillna('').astype(str)
                    if 'description' in df_merged.columns: df_merged['description'] = df_merged['description'].fillna('').astype(str)
                    cleaned_data[company_name] = df_merged
            except Exception as e:
                st.error(f'清洗公司数据失败 {company_name}: {e}')
        
        current += 1
        progress_bar.progress(current / total)
    
    progress_bar.empty()
    return cleaned_data


def extract_clues(data_directory: str, persons: List[str], companies: List[str]) -> tuple:
    """线索提取"""
    clue_persons, clue_companies = data_extractor.extract_all_clues(data_directory)
    all_persons = list(set(persons + clue_persons))
    all_companies = list(set(companies + clue_companies))
    return all_persons, all_companies


def run_profile_analysis(cleaned_data: Dict, all_persons: List[str]) -> Dict:
    """资金画像分析"""
    profiles = {}
    for entity_name, df in cleaned_data.items():
        profiles[entity_name] = financial_profiler.generate_profile_report(df, entity_name)
    return profiles


def run_suspicion_detection(cleaned_data: Dict, all_persons: List[str], 
                            all_companies: List[str]) -> Dict:
    """疑点碰撞检测"""
    return suspicion_detector.run_all_detections(cleaned_data, all_persons, all_companies)


def run_loan_analysis(cleaned_data: Dict, all_persons: List[str]) -> Dict:
    """借贷行为分析"""
    return loan_analyzer.analyze_loan_behaviors(cleaned_data, all_persons)


def run_income_analysis(cleaned_data: Dict, all_persons: List[str]) -> Dict:
    """异常收入检测"""
    return income_analyzer.detect_suspicious_income(cleaned_data, all_persons)


def run_time_series_analysis(cleaned_data: Dict, all_persons: List[str]) -> Dict:
    """时间序列分析"""
    return time_series_analyzer.analyze_time_series(cleaned_data, all_persons)


def run_ml_analysis(cleaned_data: Dict, all_persons: List[str], 
                    all_companies: List[str]) -> Dict:
    """机器学习风险预测"""
    return ml_analyzer.run_ml_analysis(cleaned_data, all_persons, all_companies)


def display_profile_summary(profiles: Dict):
    """显示资金画像摘要"""
    st.subheader("📊 资金画像摘要")
    
    for entity_name, profile in profiles.items():
        with st.expander(f"{entity_name} - 资金画像"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("总收入", f"{profile.get('total_income', 0)/10000:.2f}万")
                st.metric("总支出", f"{profile.get('total_expense', 0)/10000:.2f}万")
            
            with col2:
                st.metric("净收入", f"{profile.get('net_income', 0)/10000:.2f}万")
                st.metric("交易笔数", profile.get('transaction_count', 0))
            
            with col3:
                st.metric("收入来源数", profile.get('income_sources', 0))
                st.metric("支出对象数", profile.get('expense_targets', 0))
            
            # 收入结构
            if 'income_structure' in profile:
                st.write("**收入结构:**")
                income_df = pd.DataFrame(profile['income_structure'])
                st.dataframe(income_df, use_container_width=True)


def display_suspicion_summary(suspicions: Dict):
    """显示疑点摘要"""
    st.subheader("⚠️ 疑点摘要")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("直接资金往来", len(suspicions.get('direct_transfers', [])))
        st.metric("现金时空伴随", len(suspicions.get('cash_collisions', [])))
    
    with col2:
        hidden_count = sum(len(v) for v in suspicions.get('hidden_assets', {}).values())
        st.metric("隐形资产", hidden_count)
        fixed_count = sum(len(v) for v in suspicions.get('fixed_frequency', {}).values())
        st.metric("固定频率异常", fixed_count)
    
    with col3:
        timing_count = len(suspicions.get('cash_timing_patterns', []))
        st.metric("现金时间点配对", timing_count)
        holiday_count = sum(len(v) for v in suspicions.get('holiday_transactions', {}).values())
        st.metric("节假日交易", holiday_count)
    
    # 详细疑点列表
    if suspicions.get('direct_transfers'):
        with st.expander("直接资金往来详情"):
            df = pd.DataFrame(suspicions['direct_transfers'])
            st.dataframe(df, use_container_width=True)


def display_loan_summary(loan_results: Dict):
    """显示借贷分析摘要"""
    st.subheader("💰 借贷行为分析")
    
    summary = loan_results.get('summary', {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("双向往来关系", summary.get('双向往来关系数', 0))
        st.metric("网贷平台交易", summary.get('网贷平台交易数', 0))
    
    with col2:
        st.metric("规律还款模式", summary.get('规律还款模式数', 0))
        st.metric("无还款借贷", summary.get('无还款借贷数', 0))
    
    with col3:
        st.metric("可疑借贷", summary.get('可疑借贷数', 0))
        st.metric("延迟转账", summary.get('延迟转账数', 0))


def display_income_summary(income_results: Dict):
    """显示异常收入摘要"""
    st.subheader("💵 异常收入检测")
    
    summary = income_results.get('summary', {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("规律性非工资", summary.get('规律性非工资收入', 0))
        st.metric("个人大额转入", summary.get('个人大额转入', 0))
    
    with col2:
        st.metric("来源不明收入", summary.get('来源不明收入', 0))
        st.metric("固定金额收入", summary.get('固定金额收入', 0))
    
    with col3:
        st.metric("高风险收入", summary.get('高风险收入', 0))
        st.metric("中风险收入", summary.get('中风险收入', 0))


def display_time_series_summary(ts_results: Dict):
    """显示时序分析摘要"""
    st.subheader("📈 时间序列分析")
    
    summary = ts_results.get('summary', {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("周期性收入模式", summary.get('周期性收入模式', 0))
        st.metric("资金突变事件", summary.get('资金突变事件', 0))
    
    with col2:
        st.metric("固定延迟转账", summary.get('固定延迟转账', 0))
    
    # 周期性收入详情
    if ts_results.get('periodic_income'):
        with st.expander("周期性收入详情（疑似养廉资金）"):
            df = pd.DataFrame(ts_results['periodic_income'])
            st.dataframe(df, use_container_width=True)


def display_ml_summary(ml_results: Dict):
    """显示ML分析摘要"""
    st.subheader("🤖 机器学习风险预测")
    
    summary = ml_results.get('summary', {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("高风险异常", summary.get('anomaly_count', 0))
        st.metric("中风险异常", summary.get('medium_risk_count', 0))
    
    with col2:
        st.metric("低风险异常", summary.get('low_risk_count', 0))
        st.metric("预测准确率", f"{summary.get('accuracy', 0):.2%}")
    
    with col3:
        st.metric("分析实体数", summary.get('entity_count', 0))
        st.metric("交易记录数", summary.get('transaction_count', 0))


def display_transaction_data(cleaned_data: Dict, entity_name: str):
    """显示交易数据"""
    if entity_name in cleaned_data:
        df = cleaned_data[entity_name]
        st.subheader(f"📋 {entity_name} - 交易明细")
        
        # 数据过滤
        col1, col2, col3 = st.columns(3)
        with col1:
            min_date = df['date'].min() if 'date' in df.columns else None
            max_date = df['date'].max() if 'date' in df.columns else None
            if min_date and max_date:
                date_range = st.date_input("日期范围", [min_date, max_date])
        
        with col2:
            min_amount = st.number_input("最小金额", value=0.0)
        
        with col3:
            transaction_type = st.selectbox("交易类型", ["全部", "收入", "支出"])
        
        # 应用过滤
        filtered_df = df.copy()
        if 'date' in df.columns and len(date_range) == 2:
            filtered_df = filtered_df[
                (pd.to_datetime(filtered_df['date']).dt.date >= date_range[0]) &
                (pd.to_datetime(filtered_df['date']).dt.date <= date_range[1])
            ]
        
        if 'income' in df.columns and 'expense' in df.columns:
            if transaction_type == "收入":
                filtered_df = filtered_df[filtered_df['income'] > 0]
            elif transaction_type == "支出":
                filtered_df = filtered_df[filtered_df['expense'] > 0]
        
        if 'income' in df.columns:
            filtered_df = filtered_df[filtered_df['income'] >= min_amount]
        elif 'expense' in df.columns:
            filtered_df = filtered_df[filtered_df['expense'] >= min_amount]
        
        st.dataframe(filtered_df, use_container_width=True, height=400)
        
        # 统计信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("记录数", len(filtered_df))
        with col2:
            if 'income' in filtered_df.columns:
                st.metric("总收入", f"{filtered_df['income'].sum()/10000:.2f}万")
        with col3:
            if 'expense' in filtered_df.columns:
                st.metric("总支出", f"{filtered_df['expense'].sum()/10000:.2f}万")


# ==================== 主界面 ====================

def main():
    st.title("🔍 资金穿透与关联排查系统")
    st.markdown("---")
    
    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 系统设置")
        
        # 数据目录选择
        data_dir = st.text_input("数据目录", value="./data")
        
        # 输出目录选择
        output_dir = st.text_input("输出目录", value="./output")
        
        st.markdown("---")
        
        # 分析模块选择
        st.header("📋 分析模块")
        
        modules = {
            "资金画像分析": "profile",
            "疑点碰撞检测": "suspicion",
            "借贷行为分析": "loan",
            "异常收入检测": "income",
            "时间序列分析": "timeseries",
            "机器学习预测": "ml",
        }
        
        selected_modules = []
        for name, key in modules.items():
            if st.checkbox(name, value=True, key=f"module_{key}"):
                selected_modules.append(key)
        
        st.markdown("---")
        
        # 快速操作
        st.header("🚀 快速操作")
        
        if st.button("📁 扫描文件", key="scan_btn"):
            st.session_state.data_directory = data_dir
            st.session_state.output_directory = output_dir
            
            with st.spinner('正在扫描文件...'):
                categorized_files, persons, companies = scan_files(data_dir)
                st.session_state.categorized_files = categorized_files
                st.session_state.persons = persons
                st.session_state.companies = companies
            
            st.success(f"扫描完成！发现 {len(persons)} 人，{len(companies)} 家公司")
            st.rerun()
        
        if st.button("🧹 清洗数据", key="clean_btn"):
            if 'categorized_files' not in st.session_state:
                st.error("请先扫描文件！")
            else:
                output_dirs = create_output_directories(output_dir)
                
                with st.spinner('正在清洗数据...'):
                    cleaned_data = clean_data(
                        st.session_state.categorized_files,
                        st.session_state.persons,
                        st.session_state.companies,
                        output_dirs
                    )
                    st.session_state.cleaned_data = cleaned_data
                
                st.success(f"清洗完成！处理了 {len(cleaned_data)} 个实体")
                st.rerun()
        
        if st.button("🔍 提取线索", key="extract_btn"):
            if 'cleaned_data' not in st.session_state or not st.session_state.cleaned_data:
                st.error("请先清洗数据！")
            else:
                with st.spinner('正在提取线索...'):
                    all_persons, all_companies = extract_clues(
                        data_dir,
                        st.session_state.persons,
                        st.session_state.companies
                    )
                    st.session_state.all_persons = all_persons
                    st.session_state.all_companies = all_companies
                
                st.success(f"线索提取完成！核心人员 {len(all_persons)} 人，涉案公司 {len(all_companies)} 家")
                st.rerun()
        
        if st.button("▶️ 运行分析", key="run_btn"):
            if 'cleaned_data' not in st.session_state or not st.session_state.cleaned_data:
                st.error("请先清洗数据！")
            elif not st.session_state.all_persons:
                st.error("请先提取线索！")
            else:
                output_dirs = create_output_directories(output_dir)
                
                # 运行选中的分析模块
                if 'profile' in selected_modules:
                    with st.spinner('正在运行资金画像分析...'):
                        profiles = run_profile_analysis(
                            st.session_state.cleaned_data,
                            st.session_state.all_persons
                        )
                        st.session_state.profiles = profiles
                
                if 'suspicion' in selected_modules:
                    with st.spinner('正在运行疑点碰撞检测...'):
                        suspicions = run_suspicion_detection(
                            st.session_state.cleaned_data,
                            st.session_state.all_persons,
                            st.session_state.all_companies
                        )
                        st.session_state.suspicions = suspicions
                
                if 'loan' in selected_modules:
                    with st.spinner('正在运行借贷行为分析...'):
                        loan_results = run_loan_analysis(
                            st.session_state.cleaned_data,
                            st.session_state.all_persons
                        )
                        st.session_state.analysis_results['loan'] = loan_results
                
                if 'income' in selected_modules:
                    with st.spinner('正在运行异常收入检测...'):
                        income_results = run_income_analysis(
                            st.session_state.cleaned_data,
                            st.session_state.all_persons
                        )
                        st.session_state.analysis_results['income'] = income_results
                
                if 'timeseries' in selected_modules:
                    with st.spinner('正在运行时间序列分析...'):
                        ts_results = run_time_series_analysis(
                            st.session_state.cleaned_data,
                            st.session_state.all_persons
                        )
                        st.session_state.analysis_results['timeseries'] = ts_results
                
                if 'ml' in selected_modules:
                    with st.spinner('正在运行机器学习预测...'):
                        ml_results = run_ml_analysis(
                            st.session_state.cleaned_data,
                            st.session_state.all_persons,
                            st.session_state.all_companies
                        )
                        st.session_state.analysis_results['ml'] = ml_results
                
                st.success("分析完成！")
                st.rerun()
    
    # 主内容区
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 概览", "💰 资金画像", "⚠️ 疑点分析", 
        "📈 时序分析", "🤖 ML预测", "📋 交易明细", "📥 报告下载"
    ])
    
    with tab1:
        st.header("📊 系统概览")
        
        # 系统状态
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("核心人员", len(st.session_state.get('all_persons', [])))
        with col2:
            st.metric("涉案公司", len(st.session_state.get('all_companies', [])))
        with col3:
            st.metric("已清洗实体", len(st.session_state.get('cleaned_data', {})))
        with col4:
            st.metric("已运行分析", len(st.session_state.get('analysis_results', {})))
        
        st.markdown("---")
        
        # 快速统计
        if st.session_state.get('profiles'):
            st.subheader("资金统计")
            total_income = sum(p.get('total_income', 0) for p in st.session_state.profiles.values())
            total_expense = sum(p.get('total_expense', 0) for p in st.session_state.profiles.values())
            total_net = sum(p.get('net_income', 0) for p in st.session_state.profiles.values())
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总收入", f"{total_income/10000:.2f}万")
            with col2:
                st.metric("总支出", f"{total_expense/10000:.2f}万")
            with col3:
                st.metric("净收入", f"{total_net/10000:.2f}万")
    
    with tab2:
        if st.session_state.get('profiles'):
            display_profile_summary(st.session_state.profiles)
        else:
            st.info("请先运行资金画像分析")
    
    with tab3:
        if st.session_state.get('suspicions'):
            display_suspicion_summary(st.session_state.suspicions)
            
            if st.session_state.analysis_results.get('loan'):
                st.markdown("---")
                display_loan_summary(st.session_state.analysis_results['loan'])
            
            if st.session_state.analysis_results.get('income'):
                st.markdown("---")
                display_income_summary(st.session_state.analysis_results['income'])
        else:
            st.info("请先运行疑点碰撞检测")
    
    with tab4:
        if st.session_state.analysis_results.get('timeseries'):
            display_time_series_summary(st.session_state.analysis_results['timeseries'])
        else:
            st.info("请先运行时间序列分析")
    
    with tab5:
        if st.session_state.analysis_results.get('ml'):
            display_ml_summary(st.session_state.analysis_results['ml'])
        else:
            st.info("请先运行机器学习预测")
    
    with tab6:
        if st.session_state.get('cleaned_data'):
            entity_name = st.selectbox(
                "选择实体",
                list(st.session_state.cleaned_data.keys())
            )
            display_transaction_data(st.session_state.cleaned_data, entity_name)
        else:
            st.info("请先清洗数据")
    
    with tab7:
        st.header("📥 报告下载")
        
        output_dirs = create_output_directories(st.session_state.get('output_directory', './output_streamlit'))
        
        # 生成报告按钮
        if st.button("📄 生成完整报告"):
            if not st.session_state.get('profiles') or not st.session_state.get('suspicions'):
                st.error("请先运行分析！")
            else:
                with st.spinner('正在生成报告...'):
                    # 生成Excel报告
                    excel_path = report_generator.generate_excel_workbook(
                        st.session_state.profiles,
                        st.session_state.suspicions,
                        os.path.join(output_dirs['analysis_results'], config.OUTPUT_EXCEL_FILE)
                    )
                    
                    st.success(f"报告已生成: {excel_path}")
                    st.rerun()
        
        # 下载链接
        analysis_dir = os.path.join(st.session_state.get('output_directory', './output_streamlit'), 'analysis_results')
        
        if os.path.exists(analysis_dir):
            st.subheader("可下载文件")
            
            files = []
            for root, dirs, filenames in os.walk(analysis_dir):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    relpath = os.path.relpath(filepath, analysis_dir)
                    files.append((relpath, filepath))
            
            if files:
                for relpath, filepath in files:
                    with open(filepath, 'rb') as f:
                        st.download_button(
                            label=f"📥 {relpath}",
                            data=f,
                            file_name=relpath,
                            mime="application/octet-stream"
                        )
            else:
                st.info("暂无可下载文件")


if __name__ == '__main__':
    main()
