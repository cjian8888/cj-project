#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金穿透与关联排查系统 - 交互式界面 (Google Opal Design)
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
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== CSS 注入 ====================
def inject_custom_css():
    st.markdown("""
        <style>
        /* 全局深色主题适配 */
        .stApp {
            background-color: #0E1117;
            color: #FAFAFA;
        }
        
        /* 顶栏 Header 样式 */
        header[data-testid="stHeader"] {
            background-color: #003366 !important; /* 深蓝色 */
        }
        
        /* 侧边栏样式微调 */
        section[data-testid="stSidebar"] {
            background-color: #1A1C24;
        }
        
        /* 按钮样式增强 */
        .stButton>button {
            background-color: #4A90E2; 
            color: white; 
            border-radius: 5px;
            font-weight: bold;
            width: 100%;
        }
        .stButton>button:hover {
            background-color: #357ABD;
        }

        /* 底部 Footer 伪装 (Streamlit本身有footer，这里我们可以尝试覆盖底部区域) */
        /* 由于Streamlit结构限制，我们主要通过Main Container底部添加Terminal来实现 */
        
        /* Metric 卡片样式 */
        div[data-testid="stMetricValue"] {
            color: #4A90E2; 
            font-size: 2.5rem !important;
        }
        div[data-testid="stMetricLabel"] {
            color: #A0A0A0;
            font-size: 1rem !important;
        }
        
        /* 日志终端样式 */
        .terminal-container {
            background-color: #000000;
            color: #00FF00;
            font-family: 'Courier New', Courier, monospace;
            padding: 15px;
            border-radius: 5px;
            height: 200px;
            overflow-y: auto;
            border: 1px solid #333;
            margin-top: 20px;
            font-size: 0.85em;
            line-height: 1.4;
            white-space: pre-wrap; /* 保持换行 */
        }
        
        /* 隐藏Streamlit默认Footer */
        footer {visibility: hidden;}
        
        /* Tab 样式优化 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 4px 4px 0px 0px;
            color: #FAFAFA;
            font-size: 16px;
        }
        .stTabs [aria-selected="true"] {
            background-color: transparent;
            border-bottom: 2px solid #4A90E2;
            color: #4A90E2;
        }
        
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
            # 添加时间戳
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            formatted_msg = f"[{timestamp} {record.levelname}] {msg}"
            
            if 'log_buffer' not in st.session_state:
                st.session_state.log_buffer = []
            
            st.session_state.log_buffer.append(formatted_msg)
            
            # 保持缓冲区大小，避免无限增长
            if len(st.session_state.log_buffer) > 100:
                st.session_state.log_buffer.pop(0)
                
        except Exception:
            self.handleError(record)

# 初始化日志系统
if 'logger_initialized' not in st.session_state:
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除现有的处理器（避免重复）
    # root_logger.handlers = [] # 不完全清除，保留控制台输出以便调试
    
    # 添加自定义处理器
    st_handler = StreamlitLogHandler()
    formatter = logging.Formatter('%(message)s')
    st_handler.setFormatter(formatter)
    root_logger.addHandler(st_handler)
    
    st.session_state.logger_initialized = True
    st.session_state.log_buffer = ["系统就绪，等待用户指令..."]

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
        'config_time_window': 48
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

# ==================== 功能函数 ====================

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

def perform_full_analysis():
    """执行全流程分析"""
    logger = logging.getLogger()
    logger.info("开始全流程分析...")
    
    data_dir = st.session_state.data_directory
    output_dir = st.session_state.output_directory
    
    try:
        # 1. 创建目录
        output_dirs = create_output_directories(output_dir)
        logger.info(f"输出目录已创建: {output_dir}")
        
        # 2. 扫描文件
        logger.info("正在扫描文件...")
        categorized_files = file_categorizer.categorize_files(data_dir)
        persons = list(categorized_files['persons'].keys())
        companies = list(categorized_files['companies'].keys())
        st.session_state.persons = persons
        st.session_state.companies = companies
        logger.info(f"扫描完成: 发现 {len(persons)} 位人员, {len(companies)} 家公司")
        
        # 3. 清洗数据
        logger.info("开始清洗数据...")
        cleaned_data = {}
        # 为了演示进度，我们简单模拟，实际逻辑如果太快可能看不到进度条
        # 此处复用原有的清洗逻辑，但简化调用以适配单次执行
        
        # ... (可以使用原由 clean_data 逻辑，这里简化为模拟日志流) ...
        # 调用原始模块的逻辑
        # 这里需要注意：data_cleaner.clean_and_merge_files 是核心
        
        # 个人数据
        for p in persons:
            logger.info(f"处理个人数据: {p}")
            p_files = categorized_files['persons'].get(p, [])
            if p_files:
                df, _ = data_cleaner.clean_and_merge_files(p_files, p)
                if not df.empty:
                    cleaned_data[p] = df
        
        # 公司数据
        for c in companies:
            logger.info(f"处理公司数据: {c}")
            c_files = categorized_files['companies'].get(c, [])
            if c_files:
                df, _ = data_cleaner.clean_and_merge_files(c_files, c)
                if not df.empty:
                    cleaned_data[c] = df
        
        st.session_state.cleaned_data = cleaned_data
        logger.info("数据清洗完成")

        # 4. 提取线索
        logger.info("提取关联线索...")
        clue_persons, clue_companies = data_extractor.extract_all_clues(data_dir)
        all_persons = list(set(persons + clue_persons))
        all_companies = list(set(companies + clue_companies))
        st.session_state.all_persons = all_persons
        st.session_state.all_companies = all_companies
        logger.info(f"线索提取完成: 扩展至 {len(all_persons)} 人, {len(all_companies)} 公司")

        # 5. 执行各项分析
        logger.info(">>> 启动核心分析引擎 <<<")
        
        # 资金画像
        logger.info("正在生成资金画像...")
        profiles = {}
        for entity, df in cleaned_data.items():
            profiles[entity] = financial_profiler.generate_profile_report(df, entity)
        st.session_state.profiles = profiles
        logger.info("资金画像生成完毕")
        
        # 疑点检测
        logger.info("正在进行疑点碰撞检测...")
        # 更新配置
        config.LARGE_CASH_THRESHOLD = st.session_state.config_cash_threshold
        # TIME_WINDOW 更新需要看 config 结构，假设支持动态修改或重新加载
        
        suspicions = suspicion_detector.run_all_detections(cleaned_data, all_persons, all_companies)
        st.session_state.suspicions = suspicions
        logger.info("疑点检测完成")
        
        # 其他分析
        logger.info("运行借贷分析...")
        st.session_state.analysis_results['loan'] = loan_analyzer.analyze_loan_behaviors(cleaned_data, all_persons)
        
        logger.info("运行异常收入检测...")
        st.session_state.analysis_results['income'] = income_analyzer.detect_suspicious_income(cleaned_data, all_persons)
        
        logger.info("运行机器学习风险评估...")
        st.session_state.analysis_results['ml'] = ml_analyzer.run_ml_analysis(cleaned_data, all_persons, all_companies)
        
        logger.info("生成最终报表...")
        report_generator.generate_excel_workbook(
            profiles, suspicions, 
            os.path.join(output_dirs['analysis_results'], config.OUTPUT_EXCEL_FILE)
        )
        
        logger.info("=== 分析流程全部结束 ===")
        st.success("分析完成")
        
    except Exception as e:
        logger.error(f"分析过程中发生错误: {str(e)}")
        st.error(f"发生错误: {e}")

# ==================== 主界面渲染 ====================

def main():
    # ---------- Sidebar (侧边栏) ----------
    with st.sidebar:
        st.title("资金穿透与关联调查系统")
        st.caption("v5.1 专业版")
        st.markdown("---")
        
        st.header("数据录入与配置")
        
        # 文件上传区 (模拟)
        st.subheader("银行流水Excel文件上传")
        uploaded_excel = st.file_uploader("选择文件", type=['xlsx', 'xls'], key="excel_uploader", label_visibility="collapsed")
        if uploaded_excel:
            # 实际场景需保存文件，这里仅做演示
            st.info(f"已选择: {uploaded_excel.name} (演示模式)")
            
        st.subheader("线索文件PDF上传")
        uploaded_pdf = st.file_uploader("选择文件", type=['pdf'], key="pdf_uploader", label_visibility="collapsed")
        
        st.markdown("---")
        
        st.header("参数配置")
        st.session_state.config_cash_threshold = st.number_input(
            "现金阈值 (元)", value=50000, step=10000, help="大额现金交易的判定标准"
        )
        st.session_state.config_time_window = st.number_input(
            "时空窗口 (天)", value=30, step=1, help="判定时空伴随的时间范围"
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 开始分析按钮
        if st.button("🚀 开始分析", use_container_width=True):
            perform_full_analysis()
            
    # ---------- Main Content (主区域) ----------
    
    # 顶部指标卡片
    col1, col2, col3, col4 = st.columns(4)
    
    # 计算指标数据
    total_tx_count = 0
    suspected_amount = 0.0
    entity_count = len(st.session_state.get('all_persons', [])) + len(st.session_state.get('all_companies', []))
    risk_level = "评估中"
    risk_color = "#A0A0A0"
    
    if st.session_state.get('profiles'):
        total_tx_count = sum(p.get('transaction_count', 0) for p in st.session_state.profiles.values())
    
    if st.session_state.get('suspicions'):
        # 简单估算涉嫌金额：sum of abnormal transactions
        # 这里仅作示例，实际应从 suspicions 提取具体金额
        suspected_amount = 1234567.00 # Placeholder for demo unless computed
        # 尝试从疑点中汇总金额
        total_susp_amt = 0
        direct_txs = st.session_state.suspicions.get('direct_transfers', [])
        for tx in direct_txs:
            total_susp_amt += tx.get('amount', 0)
        suspected_amount = total_susp_amt if total_susp_amt > 0 else 0
        
        risk_level = "中高" if suspected_amount > 1000000 else "中低" 
        risk_color = "#FF4B4B" if suspected_amount > 1000000 else "#00FF00"

    with col1:
        st.metric("总交易笔数", f"{total_tx_count:,}", "近30天平均")
    with col2:
        st.metric("涉嫌关联金额", f"¥ {suspected_amount:,.2f}", "已识别高风险交易")
    with col3:
        st.metric("可疑实体数量", f"{entity_count}", "待进一步调查")
    with col4:
        # 自定义 Metric 样式展示风险等级
        st.markdown(f"""
        <div style="font-size: 1rem; color: #A0A0A0;">风险级别分布</div>
        <div style="font-size: 2.5rem; color: {risk_color}; font-weight: bold;">{risk_level}</div>
        <div style="font-size: 0.8rem; color: #A0A0A0;">当前系统评估</div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 导航栏 Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "关键绩效指标", 
        "资金整体画像", 
        "智能可疑调查", 
        "家庭与资产", 
        "审计报告"
    ])
    
    with tab1:
        st.subheader("关键绩效指标")
        # 将原有的概览内容迁移至此或重新设计
        c1, c2 = st.columns(2)
        with c1:
            if 'analysis_results' in st.session_state and 'timeseries' in st.session_state.analysis_results:
                st.info("时序波动趋势 (示例占位)")
                st.line_chart(pd.DataFrame({'amount': [100, 200, 150, 400, 300]}))
            else:
                st.caption("暂无数据，请运行分析")
        with c2:
            st.info("资金流向分布 (示例占位)")
            st.bar_chart(pd.DataFrame({'flow': [50, 20, 30]}, index=['转出', '提现', '消费']))

    with tab2:
        st.subheader("资金整体画像")
        if st.session_state.get('profiles'):
            # 整合原 display_profile_summary
            entities = list(st.session_state.profiles.keys())
            sel_entity = st.selectbox("选择实体查看详情", entities)
            if sel_entity:
                p = st.session_state.profiles[sel_entity]
                c1, c2, c3 = st.columns(3)
                c1.metric("总收入", f"{p.get('total_income', 0)/10000:.2f}万")
                c2.metric("总支出", f"{p.get('total_expense', 0)/10000:.2f}万")
                c3.metric("净流向", f"{p.get('net_income', 0)/10000:.2f}万")
                
                st.dataframe(pd.DataFrame(p.get('income_structure', [])), use_container_width=True)
        else:
            st.caption("暂无画像数据")

    with tab3:
        st.subheader("智能可疑调查")
        if st.session_state.get('suspicions'):
            # 整合原 display_suspicion_summary
            susp = st.session_state.suspicions
            st.error(f"发现 {len(susp.get('direct_transfers', []))} 笔直接资金往来")
            st.warning(f"发现 {len(susp.get('cash_collisions', []))} 次现金时空伴随")
            
            with st.expander("查看详细线索清单", expanded=True):
                st.dataframe(pd.DataFrame(susp.get('direct_transfers', [])), use_container_width=True)
        else:
            st.caption("暂无疑点数据")

    with tab4:
        st.subheader("家庭与资产")
        st.caption("该模块整合家庭关系与资产归集功能")
        # 此处可调用 family_analyzer 和 asset_analyzer 的结果
        if st.session_state.get('analysis_results'):
             st.info("资产分析模块数据准备就绪")
        else:
            st.caption("暂无分析数据")

    with tab5:
        st.subheader("审计报告")
        st.markdown("点击侧边栏分析完成后，可在此处下载最终审计底稿。")
        
        output_dir = st.session_state.output_directory
        report_path = os.path.join(output_dir, 'analysis_results', config.OUTPUT_EXCEL_FILE)
        
        if os.path.exists(report_path):
            with open(report_path, "rb") as f:
                st.download_button(
                    label="📥 下载完整审计底稿 (Excel)",
                    data=f,
                    file_name="资金核查审计底稿.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.button("📥 下载完整审计底稿 (Excel)", disabled=True)

    # ---------- Footer / Log Terminal (底部日志终端) ----------
    st.markdown("---")
    st.subheader("实时日志监控")
    
    # 使用 container 来包裹 terminal，虽然 Streamlit 不能完全固定底部，但我们可以放在页面最后
    log_text = "\n".join(st.session_state.get('log_buffer', []))
    
    # 渲染终端
    st.markdown(f"""
        <div class="terminal-container" id="log-terminal">
            {log_text}
        </div>
        <script>
            var terminal = document.getElementById("log-terminal");
            terminal.scrollTop = terminal.scrollHeight;
        </script>
    """, unsafe_allow_html=True)

if __name__ == '__main__':
    main()
