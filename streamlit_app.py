#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金穿透与关联排查系统 - 交互式界面 (Futuristic Professional Theme)
"""

import os
import sys
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import json
import logging
import io
import time
import tkinter as tk
from tkinter import filedialog

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
    page_icon="�️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CSS 注入 (Futuristic Professional Theme) ====================
def inject_custom_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            /* Futuristic Palette - Slate/Midnight Blue */
            --bg-root: #0f172a;        /* bg-slate-950 */
            --bg-sidebar: #020617;     /* bg-slate-950 darker variant */
            --bg-card: rgba(15, 23, 42, 0.6); /* Glassmorphism base */
            --border-color: #1e293b;   /* border-slate-800 */
            
            --text-primary: #f8fafc;   /* text-slate-50 */
            --text-secondary: #94a3b8; /* text-slate-400 */
            
            --accent-blue: #3b82f6;    /* blue-500 */
            --accent-cyan: #06b6d4;    /* cyan-500 */
            --accent-red: #ef4444;     /* red-500 */
            --accent-green: #22c55e;   /* green-500 */
            --accent-warning: #eab308; /* yellow-500 */
            
            --font-sans: 'Inter', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }

        /* 1. Global Reset & Background */
        .stApp {
            background-color: var(--bg-root);
            font-family: var(--font-sans);
            color: var(--text-primary);
        }
        
        header, footer, #MainMenu { visibility: hidden; }

        /* 2. Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: var(--bg-sidebar);
            border-right: 1px solid var(--border-color);
        }
        
        .sidebar-header {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-secondary);
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
            padding-left: 0.5rem;
            border-left: 2px solid var(--accent-blue);
        }

        /* 3. Gradient Glow Button (Start Engine) */
        .stButton button[kind="primary"] {
            background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-cyan) 100%);
            border: none;
            color: white;
            font-weight: 600;
            padding: 0.6rem 1.2rem;
            border-radius: 6px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px -3px rgba(59, 130, 246, 0.4); /* Blue glow */
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .stButton button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px -3px rgba(6, 182, 212, 0.5); /* Cyan glow intensified */
        }
        
        .stButton button[kind="secondary"] {
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
        }
        .stButton button[kind="secondary"]:hover {
            border-color: var(--text-primary);
            color: var(--text-primary);
        }

        /* 4. Glassmorphism Cards & Metrics */
        div[data-testid="stMetric"], .stCard, div[data-testid="stExpander"] {
            background-color: var(--bg-card);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
        }
        
        /* Metric Typography */
        div[data-testid="stMetric"] label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 500;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--text-primary);
            font-family: var(--font-sans); /* Instructions said sans for value? Or keeping sleek */
        }
        
        /* 5. Inputs & Forms */
        .stTextInput input, .stNumberInput input {
            background-color: rgba(30, 41, 59, 0.5); /* slate-800/50 */
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            border-radius: 6px;
        }
        .stTextInput input:focus, .stNumberInput input:focus {
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 1px var(--accent-blue);
        }

        /* 6. Terminal / Real-time Logs */
        .log-container {
            background-color: #0d1117; /* Darker than root specifically for terminal */
            border: 1px solid var(--border-color);
            border-radius: 8px;
            font-family: var(--font-mono);
            font-size: 0.8rem;
            padding: 1rem;
            height: 250px;
            overflow-y: auto;
            box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.3);
        }
        .log-entry {
            display: flex;
            gap: 12px;
            margin-bottom: 6px;
            border-bottom: 1px dashed rgba(51, 65, 85, 0.3);
            padding-bottom: 4px;
        }
        .log-time { color: #64748b; min-width: 70px; } /* slate-500 */
        .log-level-info { color: #3b82f6; font-weight: bold; width: 45px; }
        .log-level-warn { color: #eab308; font-weight: bold; width: 45px; }
        .log-level-error { color: #ef4444; font-weight: bold; width: 45px; }
        .log-msg { color: #e2e8f0; } /* slate-200 */

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            background-color: transparent;
            border-bottom: 1px solid var(--border-color);
            gap: 2rem;
        }
        .stTabs [data-baseweb="tab"] {
            color: var(--text-secondary);
            font-weight: 500;
            padding: 1rem 0;
        }
        .stTabs [aria-selected="true"] {
            color: var(--accent-blue) !important;
            border-bottom: 2px solid var(--accent-blue);
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-root); }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }

        </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==================== LogStream 日志处理 ====================

class StreamlitLogHandler(logging.Handler):
    """自定义日志处理器，将日志输出到 Session State"""
    def __init__(self):
        super().__init__()
        
    def emit(self, record):
        try:
            msg = self.format(record)
            timestamp = datetime.now().strftime("%H:%M:%S")
            level_cls = "log-level-info"
            if record.levelno >= logging.ERROR:
                level_cls = "log-level-error"
            elif record.levelno >= logging.WARNING:
                level_cls = "log-level-warn"
            
            # HTML Structure mimicking terminal
            formatted_msg = f"""
                <div class="log-entry">
                    <span class="log-time">{timestamp}</span>
                    <span class="{level_cls}">{record.levelname}</span>
                    <span class="log-msg">{msg}</span>
                </div>
            """
            
            if 'log_buffer' not in st.session_state:
                st.session_state.log_buffer = []
            
            st.session_state.log_buffer.append(formatted_msg)
            
            # 保持缓冲区
            if len(st.session_state.log_buffer) > 200:
                st.session_state.log_buffer.pop(0)
                
        except Exception:
            self.handleError(record)

# 初始化日志系统
if 'logger_initialized' not in st.session_state:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 移除可能存在的旧 handler 避免重复
    for h in root_logger.handlers[:]:
        if isinstance(h, StreamlitLogHandler):
            root_logger.removeHandler(h)
    
    st_handler = StreamlitLogHandler()
    formatter = logging.Formatter('%(message)s')
    st_handler.setFormatter(formatter)
    root_logger.addHandler(st_handler)
    
    st.session_state.logger_initialized = True
    if 'log_buffer' not in st.session_state:
        st.session_state.log_buffer = []
        logging.info("System Initialized. Status: Ready.")

# ==================== Session State 初始化 ====================
def init_session_state():
    defaults = {
        'data_directory': './data',
        'output_directory': './output',
        'cleaned_data': {},
        'all_persons': [],
        'all_companies': [],
        'profiles': {},
        'suspicions': {},
        'analysis_results': {},
        'is_analyzing': False,
        'config_cash_threshold': 50000,
        'config_time_window': 48,
        'run_timestamp': None
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

# ==================== 功能函数 ====================

def select_directory_native(initial_dir: str) -> Optional[str]:
    """系统原生文件夹选择"""
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        directory = filedialog.askdirectory(initialdir=initial_dir)
        root.destroy()
        return directory if directory else None
    except Exception as e:
        logging.error(f"选择目录失败: {e}")
        return None

def create_output_directories(base_dir: str) -> Dict[str, str]:
    dirs = {
        'base': base_dir,
        'cleaned_data': os.path.join(base_dir, 'cleaned_data'),
        'analysis_results': os.path.join(base_dir, 'analysis_results'),
        'logs': os.path.join(base_dir, 'logs')
    }
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    return dirs

def perform_full_analysis():
    """执行全流程分析"""
    logger = logging.getLogger()
    st.session_state.log_buffer = [] # 清空日志
    logger.info(">>> ENGINE STARTED: Full Analysis Sequence Initiated <<<")
    
    start_time = time.time()
    data_dir = st.session_state.data_directory
    output_dir = st.session_state.output_directory
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # 1. 初始化
        status_text.text("System Initialization...")
        output_dirs = create_output_directories(output_dir)
        progress_bar.progress(10)
        
        # 2. 扫描
        status_text.text("Scanning data artifacts...")
        categorized_files = file_categorizer.categorize_files(data_dir)
        persons = list(categorized_files['persons'].keys())
        companies = list(categorized_files['companies'].keys())
        st.session_state.persons = persons
        st.session_state.companies = companies
        logger.info(f"Scan Complete: {len(persons)} Persons, {len(companies)} Companies detected.")
        progress_bar.progress(30)
        
        # 3. 清洗
        status_text.text("Sanitizing and standardizing records...")
        cleaned_data = {}
        
        count = 0
        total_entities = len(persons) + len(companies)
        
        for p in persons:
            p_files = categorized_files['persons'].get(p, [])
            if p_files:
                df, _ = data_cleaner.clean_and_merge_files(p_files, p)
                if not df.empty:
                    cleaned_data[p] = df
            count += 1
            if total_entities > 0:
                progress_bar.progress(30 + int(30 * count / total_entities))
                
        for c in companies:
            c_files = categorized_files['companies'].get(c, [])
            if c_files:
                df, _ = data_cleaner.clean_and_merge_files(c_files, c)
                if not df.empty:
                    cleaned_data[c] = df
            count += 1
            if total_entities > 0:
                progress_bar.progress(30 + int(30 * count / total_entities))

        st.session_state.cleaned_data = cleaned_data
        logger.info("Data Sanitization Module: SUCCESS")
        
        # 4. 线索提取
        status_text.text("Mining association clues...")
        clue_persons, clue_companies = data_extractor.extract_all_clues(data_dir)
        all_persons = list(set(persons + clue_persons))
        all_companies = list(set(companies + clue_companies))
        st.session_state.all_persons = all_persons
        st.session_state.all_companies = all_companies
        progress_bar.progress(70)

        # 5. 核心分析
        status_text.text("Running Multi-vector Analysis Engine...")
        
        # 更新配置参数
        config.LARGE_CASH_THRESHOLD = st.session_state.config_cash_threshold
        
        # 资金画像
        profiles = {}
        for entity, df in cleaned_data.items():
            profiles[entity] = financial_profiler.generate_profile_report(df, entity)
        st.session_state.profiles = profiles
        
        # 疑点检测
        suspicions = suspicion_detector.run_all_detections(cleaned_data, all_persons, all_companies)
        st.session_state.suspicions = suspicions
        
        # 其他高级分析
        st.session_state.analysis_results['loan'] = loan_analyzer.analyze_loan_behaviors(cleaned_data, all_persons)
        st.session_state.analysis_results['income'] = income_analyzer.detect_suspicious_income(cleaned_data, all_persons)
        st.session_state.analysis_results['ml'] = ml_analyzer.run_ml_analysis(cleaned_data, all_persons, all_companies)
        
        progress_bar.progress(90)
        
        # 6. 生成报告
        status_text.text("Generating Audit Manifest...")
        report_generator.generate_excel_workbook(
            profiles, suspicions, 
            os.path.join(output_dirs['analysis_results'], config.OUTPUT_EXCEL_FILE)
        )
        
        progress_bar.progress(100)
        duration = time.time() - start_time
        st.session_state.run_timestamp = datetime.now()
        
        logger.info(f"Analysis Protocol Complete. Duration: {duration:.2f}s")
        st.success("✅ Analysis Protocol Complete")
        time.sleep(1)
        status_text.empty()
        
    except Exception as e:
        logger.error(f"FATAL ERROR: {str(e)}")
        st.error(f"Protocol Warning: {e}")
        progress_bar.empty()

# ==================== 主界面渲染 ====================

def main():
    # ---------- Sidebar (Configuration) ----------
    with st.sidebar:
        st.markdown('<h1 style="color:var(--text-primary); font-size:1.5rem; border:none; margin-bottom:0;">F.P.A.A.S</h1>', unsafe_allow_html=True)
        st.caption("Financial Penetration & Association Audit System")
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 1. Start Engine Button (Prominent Gradient)
        if st.button("🚀 START ENGINE", key="run_analysis", type="primary", use_container_width=True):
            perform_full_analysis()
            
        st.markdown("<br>", unsafe_allow_html=True)

        # 2. Workspace Config
        st.markdown('<div class="sidebar-header">Data Source</div>', unsafe_allow_html=True)
        c1, c2 = st.columns([0.8, 0.2])
        with c1:
            st.session_state.data_directory = st.text_input("Source", value=st.session_state.data_directory, label_visibility="collapsed")
        with c2:
            if st.button("📂", help="Browse"):
                path = select_directory_native(st.session_state.data_directory)
                if path: st.session_state.data_directory = path; st.rerun()
        
        st.markdown('<div class="sidebar-header">Output Target</div>', unsafe_allow_html=True)
        c3, c4 = st.columns([0.8, 0.2])
        with c3:
            st.session_state.output_directory = st.text_input("Target", value=st.session_state.output_directory, label_visibility="collapsed")
        with c4:
            if st.button("💾", help="Browse"):
                path = select_directory_native(st.session_state.output_directory)
                if path: st.session_state.output_directory = path; st.rerun()

        # 3. Parameters
        st.markdown('<div class="sidebar-header">Threshold Params</div>', unsafe_allow_html=True)
        st.session_state.config_cash_threshold = st.number_input(
            "Cash Threshold (CNY)", 
            value=st.session_state.config_cash_threshold, step=10000
        )
        st.session_state.config_time_window = st.number_input(
            "Time Window (Hours)", 
            value=st.session_state.config_time_window, step=1
        )
            
        st.markdown("<div style='margin-top:auto;'></div>", unsafe_allow_html=True)
        if st.session_state.run_timestamp:
            st.caption(f"Last Run: {st.session_state.run_timestamp.strftime('%H:%M:%S')}")

    # ---------- Main Dashboard Area ----------
    
    # 4. KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    total_tx_count = sum(p.get('transaction_count', 0) for p in st.session_state.profiles.values()) if st.session_state.profiles else 0
    suspected_amount = 0
    if st.session_state.suspicions:
        suspected_amount = sum(tx.get('amount', 0) for tx in st.session_state.suspicions.get('direct_transfers', []))
    
    entity_count = len(st.session_state.get('all_persons', [])) + len(st.session_state.get('all_companies', []))
    
    with col1:
        st.metric("Analyzed Entities", f"{entity_count}", delta=None)
    with col2:
        st.metric("Total Transactions", f"{total_tx_count:,}", delta=None)
    with col3:
        # Custom coloring for High Risk Funds handled via CSS on delta or value, but st.metric is limited.
        # We rely on the global CSS styling for stCard/stMetric to make this pop.
        st.metric("High Risk Funds", f"¥ {suspected_amount:,.0f}", delta="Risk Detected!", delta_color="inverse")
    with col4:
        # System Status Indicator
        status_html = f"""
            <div style="display:flex; align-items:center; gap:8px;">
                <div style="width:8px; height:8px; background-color:#22c55e; border-radius:50%; box-shadow:0 0 8px #22c55e;"></div>
                <span style="font-weight:600; color:#22c55e;">READY</span>
            </div>
        """
        if st.session_state.is_analyzing:
            status_html = f"""
                <div style="display:flex; align-items:center; gap:8px;">
                    <div style="width:8px; height:8px; background-color:#eab308; border-radius:50%; box-shadow:0 0 8px #eab308;"></div>
                    <span style="font-weight:600; color:#eab308;">ANALYZING...</span>
                </div>
            """
        
        st.markdown(f"""
            <div class="stCard" style="height:104px; display:flex; flex-direction:column; justify-content:center;">
                <label style="font-size:0.85rem; color:var(--text-secondary);">System Status</label>
                <div style="margin-top:4px;">{status_html}</div>
            </div>
        """, unsafe_allow_html=True)

    st.write("") # Spacer

    # 5. Main Content Tabs
    main_tabs = st.tabs(["Overview", "Risk Intel", "Graph View", "Audit Report"])

    with main_tabs[0]:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("Fund Distribution")
            if st.session_state.profiles:
                profile_df = pd.DataFrame([
                    {'Entity': k, 'In': v['total_income'], 'Out': v['total_expense']} 
                    for k, v in st.session_state.profiles.items()
                ])
                st.dataframe(profile_df, use_container_width=True, height=350)
            else:
                st.info("Awaiting Analysis Data...")
        with c2:
            st.subheader("Transaction Volume Trend")
            chart_data = pd.DataFrame({
                'Date': pd.date_range(start='2024-01-01', periods=15),
                'Volume': [x * 1200 + 5000 for x in range(15)]
            })
            st.area_chart(chart_data.set_index('Date'), color="#3b82f6")

    with main_tabs[1]:
        st.subheader("Suspicious Activity Log")
        if st.session_state.suspicions:
            susp_type = st.radio("Filter Type", ["Direct Transfers", "Round Trip", "Cash Anomaly"], horizontal=True)
            if susp_type == "Direct Transfers":
                data = st.session_state.suspicions.get('direct_transfers', [])
                if data:
                    st.dataframe(pd.DataFrame(data), use_container_width=True)
                else:
                    st.success("No direct transfer anomalies detected.")
        else:
            st.info("No active threats detected. Please run the analysis engine.")

    with main_tabs[2]:
        st.subheader("Association Graph")
        st.markdown("""
            <div style="background:rgba(15, 23, 42, 0.4); border:1px dashed #334155; border-radius:8px; height:400px; display:flex; align-items:center; justify-content:center;">
                <span style="color:#64748b;">Interactive Graph Visualization Module (Placeholder)</span>
            </div>
        """, unsafe_allow_html=True)

    with main_tabs[3]:
        st.subheader("Export Audit Artifacts")
        output_dir = st.session_state.output_directory
        report_path = os.path.join(output_dir, 'analysis_results', config.OUTPUT_EXCEL_FILE)
        
        if os.path.exists(report_path):
            with open(report_path, "rb") as f:
                st.download_button(
                    label="📥 Download Master Audit Excel",
                    data=f,
                    file_name="Audit_Manifest.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
        else:
            st.warning("Audit manifest not yet generated.")

    # 6. Real-time Log Console (Bottom)
    st.markdown("---")
    st.markdown('<h3 style="font-size:1rem; margin-bottom:0.5rem;">Real-time Analysis Logic</h3>', unsafe_allow_html=True)
    log_html = "".join(st.session_state.get('log_buffer', []))
    st.markdown(f'<div class="log-container">{log_html}</div>', unsafe_allow_html=True)

if __name__ == '__main__':
    main()
