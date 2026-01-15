#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金穿透审计系统 - FastAPI 后端服务

提供 RESTful API 和 WebSocket 实时日志推送，连接 React 前端与 Python 分析引擎
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
import threading
import queue

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# 导入分析模块
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

# ==================== 日志配置 ====================

# 初始化模块级日志记录器
logger = utils.setup_logger(__name__)

class WebSocketLogHandler(logging.Handler):
    """WebSocket 日志处理器，将日志推送到所有连接的客户端"""
    
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        try:
            log_entry = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": record.levelname,
                "msg": self.format(record)
            }
            self.log_queue.put(log_entry)
        except Exception:
            pass

# 全局日志队列
log_queue: queue.Queue = queue.Queue()

# ==================== 数据模型 ====================

class AnalysisConfig(BaseModel):
    inputDirectory: str = "./data"
    outputDirectory: str = "./output"
    cashThreshold: int = 50000
    timeWindow: int = 48
    modules: Dict[str, bool] = {
        "profileAnalysis": True,
        "suspicionDetection": True,
        "assetAnalysis": True,
        "dataValidation": True,
        "fundPenetration": True,
        "relatedParty": True,
        "multiSourceCorrelation": True,
        "loanAnalysis": True,
        "incomeAnalysis": True,
        "flowVisualization": True,
        "mlAnalysis": True,
        "timeSeriesAnalysis": True,
        "clueAggregation": True,
    }

class AnalysisStatus(BaseModel):
    status: str  # idle, running, completed, failed
    progress: int
    currentPhase: str
    startTime: Optional[str] = None
    endTime: Optional[str] = None

class AnalysisResult(BaseModel):
    persons: List[str]
    companies: List[str]
    profiles: Dict[str, Any]
    suspicions: Dict[str, Any]
    analysisResults: Dict[str, Any]

# ==================== 全局状态 ====================

class AnalysisState:
    def __init__(self):
        self.status = "idle"
        self.progress = 0
        self.current_phase = ""
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.results: Optional[Dict] = None
        self.lock = threading.Lock()
    
    def update(self, status: str = None, progress: int = None, phase: str = None):
        with self.lock:
            if status:
                self.status = status
            if progress is not None:
                self.progress = progress
            if phase:
                self.current_phase = phase
        
        # 在更新后广播状态到前端
        self._broadcast_status()
    
    def _broadcast_status(self):
        """在独立线程中广播状态更新"""
        import threading
        import asyncio
        
        def broadcast():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(manager.broadcast({
                    "type": "status",
                    "data": self.to_dict()
                }))
            finally:
                loop.close()
        
        # 启动广播线程
        broadcast_thread = threading.Thread(target=broadcast, daemon=True)
        broadcast_thread.start()
    
    def to_dict(self) -> Dict:
        with self.lock:
            return {
                "status": self.status,
                "progress": self.progress,
                "currentPhase": self.current_phase,
                "startTime": self.start_time.isoformat() if self.start_time else None,
                "endTime": self.end_time.isoformat() if self.end_time else None,
            }

analysis_state = AnalysisState()

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：配置日志
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 添加 WebSocket 日志处理器
    ws_handler = WebSocketLogHandler(log_queue)
    ws_handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(ws_handler)
    
    # 启动日志广播任务
    log_task = asyncio.create_task(broadcast_logs())
    
    logging.info("API 服务已启动")
    
    yield
    
    # 关闭时
    log_task.cancel()
    logging.info("API 服务已关闭")

async def broadcast_logs():
    """异步广播日志到所有 WebSocket 客户端"""
    while True:
        try:
            while not log_queue.empty():
                log_entry = log_queue.get_nowait()
                await manager.broadcast({"type": "log", "data": log_entry})
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            break
        except:
            await asyncio.sleep(0.1)

# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="F.P.A.S API",
    description="资金穿透审计系统 API 服务",
    version="3.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== API 路由 ====================

@app.get("/")
async def root():
    return {"message": "F.P.A.S API v3.0.0", "status": "online"}

@app.get("/api/status")
async def get_status():
    """获取分析状态"""
    return analysis_state.to_dict()

@app.post("/api/analysis/start")
async def start_analysis(config: AnalysisConfig, background_tasks: BackgroundTasks):
    """启动分析任务"""
    if analysis_state.status == "running":
        raise HTTPException(status_code=400, detail="分析已在运行中")
    
    # 在后台任务中运行分析
    background_tasks.add_task(run_analysis, config)
    
    return {"message": "分析已启动", "status": "running"}

@app.post("/api/analysis/stop")
async def stop_analysis():
    """停止分析任务"""
    if analysis_state.status != "running":
        raise HTTPException(status_code=400, detail="没有正在运行的分析任务")
    
    analysis_state.update(status="failed", phase="分析已被用户终止")
    logging.warning("分析已被用户终止")
    
    return {"message": "分析已停止", "status": "stopped"}

@app.get("/api/results")
async def get_results():
    """获取分析结果"""
    if analysis_state.results is None:
        return {"message": "暂无分析结果", "data": None}
    
    return {"message": "success", "data": analysis_state.results}

@app.get("/api/reports")
async def list_reports():
    """列出可用的报告文件"""
    output_dir = "./output/analysis_results"
    if not os.path.exists(output_dir):
        return {"reports": []}
    
    reports = []
    for filename in os.listdir(output_dir):
        filepath = os.path.join(output_dir, filename)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            reports.append({
                "name": filename,
                "path": filepath,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    return {"reports": reports}

@app.get("/api/reports/{filename}")
async def download_report(filename: str):
    """下载报告文件"""
    filepath = os.path.join("./output/analysis_results", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(
        filepath, 
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/api/analysis/graph-data")
async def get_graph_data():
    """获取资金流向图谱数据（用于前端 Vis.js 可视化）"""
    try:
        # 检查是否有分析结果
        if analysis_state.results is None:
            raise HTTPException(status_code=404, detail="暂无分析结果，请先运行分析")
        
        # 从结果中获取核心人员和公司列表
        all_persons = analysis_state.results.get("persons", [])
        all_companies = analysis_state.results.get("companies", [])
        
        # 准备交易数据（从磁盘读取或使用缓存）
        data_dir = config.DATA_DIR
        categorized_files = file_categorizer.categorize_files(data_dir)
        
        # 清洗数据
        cleaned_data = {}
        for person in all_persons:
            p_files = categorized_files['persons'].get(person, [])
            if p_files:
                df, _ = data_cleaner.clean_and_merge_files(p_files, person)
                if df is not None and not df.empty:
                    cleaned_data[person] = df
        
        for company in all_companies:
            c_files = categorized_files['companies'].get(company, [])
            if c_files:
                df, _ = data_cleaner.clean_and_merge_files(c_files, company)
                if df is not None and not df.empty:
                    cleaned_data[company] = df
        
        # 计算资金流向统计
        flow_stats = flow_visualizer._calculate_flow_stats(cleaned_data, all_persons)
        
        # 准备图谱数据
        nodes, edges, edge_stats = flow_visualizer._prepare_graph_data(
            flow_stats, all_persons, all_companies
        )
        
        # 【前端优化】Top N 采样逻辑
        # 按交易金额排序，只返回前 200 个节点和 500 条连线
        max_nodes = 200
        max_edges = 500
        
        # 按节点的大小（重要程度）排序
        sorted_nodes = sorted(nodes, key=lambda x: x.get('size', 0), reverse=True)
        sampled_nodes = sorted_nodes[:max_nodes]
        sampled_node_ids = {node['id'] for node in sampled_nodes}
        
        # 只保留采样节点之间的边
        sampled_edges = []
        for edge in edges:
            if edge['from'] in sampled_node_ids and edge['to'] in sampled_node_ids:
                sampled_edges.append(edge)
                if len(sampled_edges) >= max_edges:
                    break
        
        # 按边的金额排序，保留最重要的边
        sampled_edges.sort(key=lambda x: x.get('value', 0), reverse=True)
        sampled_edges = sampled_edges[:max_edges]
        
        # 【内存优化】清理临时变量
        del cleaned_data, flow_stats
        import gc
        gc.collect()
        
        # 准备统计数据
        loan_results = analysis_state.results.get("analysisResults", {}).get("loan", {})
        income_results = analysis_state.results.get("analysisResults", {}).get("income", {})
        
        return {
            "message": "success",
            "data": {
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
                    "corePersonCount": len(all_persons),
                    "corePersonNames": all_persons,
                    "involvedCompanyCount": len(all_companies),
                    "highRiskCount": len(income_results.get("details", [])),
                    "mediumRiskCount": 0,  # 暂无中风险数据
                    "loanPairCount": loan_results.get("summary", {}).get("双向往来关系数", 0),
                    "noRepayCount": 0,  # 暂无无还款数据
                    "coreEdgeCount": edge_stats.get("core", 0),
                    "companyEdgeCount": edge_stats.get("company", 0),
                    "otherEdgeCount": edge_stats.get("other", 0),
                },
                "report": {
                    "loan_pairs": loan_results.get("loan_pairs", []),
                    "no_repayment_loans": loan_results.get("no_repayment_loans", []),
                    "high_risk_income": income_results.get("high_risk", []),
                    "online_loans": loan_results.get("online_loans", [])
                }
            }
        }
    except Exception as e:
        logger.error(f"获取图谱数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取图谱数据失败: {str(e)}")

# ==================== WebSocket 路由 ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点，用于实时日志推送"""
    await manager.connect(websocket)
    try:
        # 发送当前状态
        await websocket.send_json({
            "type": "status",
            "data": analysis_state.to_dict()
        })
        
        while True:
            # 保持连接活跃
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ==================== 分析任务 ====================

def run_analysis(analysis_config: AnalysisConfig):
    """执行完整分析流程"""
    logger = logging.getLogger(__name__)
    
    analysis_state.start_time = datetime.now()
    analysis_state.update(status="running", progress=0, phase="初始化分析引擎...")
    
    try:
        data_dir = analysis_config.inputDirectory
        output_dir = analysis_config.outputDirectory
        
        # 更新配置
        config.LARGE_CASH_THRESHOLD = analysis_config.cashThreshold
        
        # 阶段 1: 扫描文件
        analysis_state.update(progress=5, phase="扫描数据目录...")
        logger.info(f"扫描数据目录: {data_dir}")
        
        categorized_files = file_categorizer.categorize_files(data_dir)
        persons = list(categorized_files['persons'].keys())
        companies = list(categorized_files['companies'].keys())
        
        logger.info(f"发现 {len(persons)} 个个人, {len(companies)} 个企业")
        
        # 阶段 2: 数据清洗
        analysis_state.update(progress=15, phase="数据清洗与标准化...")
        logger.info("开始数据清洗...")
        
        cleaned_data = {}
        output_dirs = create_output_directories(output_dir)
        
        total_entities = len(persons) + len(companies)
        for i, p in enumerate(persons):
            p_files = categorized_files['persons'].get(p, [])
            if p_files:
                df, _ = data_cleaner.clean_and_merge_files(p_files, p)
                if df is not None and not df.empty:
                    cleaned_data[p] = df
            
            progress = 15 + int(25 * (i + 1) / total_entities)
            analysis_state.update(progress=progress)
        
        for i, c in enumerate(companies):
            c_files = categorized_files['companies'].get(c, [])
            if c_files:
                df, _ = data_cleaner.clean_and_merge_files(c_files, c)
                if df is not None and not df.empty:
                    cleaned_data[c] = df
            
            progress = 15 + int(25 * (len(persons) + i + 1) / total_entities)
            analysis_state.update(progress=progress)
        
        logger.info(f"清洗完成，共 {len(cleaned_data)} 个实体数据")
        
        # 阶段 3: 线索提取
        analysis_state.update(progress=45, phase="提取关联线索...")
        clue_persons, clue_companies = data_extractor.extract_all_clues(data_dir)
        all_persons = list(set(persons + clue_persons))
        all_companies = list(set(companies + clue_companies))
        
        # 阶段 4: 资金画像
        analysis_state.update(progress=55, phase="执行资金画像分析...")
        logger.info("生成资金画像...")
        
        profiles = {}
        for entity, df in cleaned_data.items():
            try:
                profiles[entity] = financial_profiler.generate_profile_report(df, entity)
            except Exception as e:
                logger.warning(f"生成 {entity} 画像失败: {e}")
        
        # 阶段 5: 疑点检测
        analysis_state.update(progress=70, phase="检测可疑交易模式...")
        logger.info("执行疑点碰撞检测...")
        
        suspicions = suspicion_detector.run_all_detections(cleaned_data, all_persons, all_companies)
        
        # 阶段 6: 高级分析
        analysis_state.update(progress=80, phase="运行高级分析模块...")
        
        analysis_results = {}
        
        if analysis_config.modules.get("loanAnalysis", True):
            try:
                analysis_results["loan"] = loan_analyzer.analyze_loan_behaviors(cleaned_data, all_persons)
            except Exception as e:
                logger.warning(f"借贷分析失败: {e}")
        
        if analysis_config.modules.get("incomeAnalysis", True):
            try:
                analysis_results["income"] = income_analyzer.detect_suspicious_income(cleaned_data, all_persons)
            except Exception as e:
                logger.warning(f"收入分析失败: {e}")
        
        if analysis_config.modules.get("relatedParty", True):
            try:
                analysis_results["relatedParty"] = related_party_analyzer.analyze_related_party_flows(
                    cleaned_data, all_persons
                )
            except Exception as e:
                logger.warning(f"关联方分析失败: {e}")
        
        if analysis_config.modules.get("multiSourceCorrelation", True):
            try:
                analysis_results["correlation"] = multi_source_correlator.run_all_correlations(
                    data_dir, cleaned_data, all_persons
                )
            except Exception as e:
                logger.warning(f"多源数据碰撞分析失败: {e}")
        
        if analysis_config.modules.get("timeSeriesAnalysis", True):
            try:
                analysis_results["timeSeries"] = time_series_analyzer.analyze_time_series(
                    cleaned_data, all_persons
                )
            except Exception as e:
                logger.warning(f"时序分析失败: {e}")
        
        if analysis_config.modules.get("clueAggregation", True):
            try:
                analysis_results["aggregation"] = clue_aggregator.aggregate_all_results(
                    all_persons, all_companies,
                    penetration_results=None,
                    ml_results=None,
                    ts_results=analysis_results.get("timeSeries"),
                    related_party_results=analysis_results.get("relatedParty"),
                    loan_results=analysis_results.get("loan")
                )
            except Exception as e:
                logger.warning(f"线索汇总失败: {e}")
        
        # 阶段 7: 生成报告
        analysis_state.update(progress=90, phase="生成审计报告...")
        logger.info("生成分析报告...")
        
        try:
            report_generator.generate_excel_workbook(
                profiles, 
                suspicions, 
                os.path.join(output_dirs['analysis_results'], config.OUTPUT_EXCEL_FILE)
            )
        except Exception as e:
            logger.warning(f"生成报告失败: {e}")
        
        # 完成
        analysis_state.update(progress=100, phase="分析完成")
        analysis_state.end_time = datetime.now()
        analysis_state.status = "completed"
        
        # 将时序分析结果整合到 suspicions（使前端能显示）
        enhanced_suspicions = _enhance_suspicions_with_analysis(suspicions, analysis_results)
        
        # 保存结果
        analysis_state.results = {
            "persons": all_persons,
            "companies": all_companies,
            "profiles": serialize_profiles(profiles),
            "suspicions": serialize_suspicions(enhanced_suspicions),
            "analysisResults": serialize_analysis_results(analysis_results),
        }
        
        duration = (analysis_state.end_time - analysis_state.start_time).total_seconds()
        logger.info(f"✓ 分析完成，耗时 {duration:.2f} 秒")
        
        # 广播完成状态 - 使用线程安全的方式
        import threading
        def broadcast_complete():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(manager.broadcast({
                    "type": "complete",
                    "data": analysis_state.to_dict()
                }))
            finally:
                loop.close()
        
        broadcast_thread = threading.Thread(target=broadcast_complete)
        broadcast_thread.start()
        
    except Exception as e:
        logger.error(f"分析失败: {str(e)}")
        analysis_state.update(status="failed", phase=f"错误: {str(e)}")
        analysis_state.end_time = datetime.now()

def create_output_directories(base_dir: str) -> Dict[str, str]:
    """创建输出目录结构"""
    dirs = {
        'base': base_dir,
        'cleaned_data': os.path.join(base_dir, 'cleaned_data'),
        'analysis_results': os.path.join(base_dir, 'analysis_results'),
        'logs': os.path.join(base_dir, 'logs')
    }
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    return dirs

def _enhance_suspicions_with_analysis(suspicions: Dict, analysis_results: Dict) -> Dict:
    """
    将分析模块结果整合到 suspicions 中（使前端能显示更多风险数据）
    
    主要整合：
    - timeSeries.sudden_changes -> direct_transfers (资金突变)
    - timeSeries.delayed_transfers -> direct_transfers (延迟转账)
    - relatedParty.direct_flows -> direct_transfers (关联方资金往来)
    """
    enhanced = suspicions.copy()
    
    # 1. 整合时序分析结果
    ts_results = analysis_results.get("timeSeries", {})
    
    # 资金突变转为风险记录
    sudden_changes = ts_results.get("sudden_changes", [])
    for change in sudden_changes:
        if isinstance(change, dict):
            enhanced["direct_transfers"].append({
                "person": change.get("entity", change.get("person", "")),
                "company": "系统检测",
                "date": change.get("date", change.get("change_date", "")),
                "amount": change.get("amount", change.get("income_change", 0)),
                "direction": "突变",
                "description": change.get("description", f"资金突变: {change.get('change_type', '未知')}"),
                "risk_level": change.get("risk_level", "medium")
            })
    
    # 延迟转账转为风险记录
    delayed_transfers = ts_results.get("delayed_transfers", [])
    for dt in delayed_transfers:
        if isinstance(dt, dict):
            enhanced["direct_transfers"].append({
                "person": dt.get("source_person", dt.get("person", "")),
                "company": dt.get("target_person", "系统检测"),
                "date": dt.get("source_date", dt.get("date", "")),
                "amount": dt.get("amount", 0),
                "direction": "延迟转账",
                "description": dt.get("description", f"延迟{dt.get('delay_days', 0)}天转账"),
                "risk_level": dt.get("risk_level", "medium")
            })
    
    # 周期性收入转为风险记录
    periodic_income = ts_results.get("periodic_income", [])
    for pi in periodic_income:
        if isinstance(pi, dict):
            enhanced["direct_transfers"].append({
                "person": pi.get("entity", pi.get("person", "")),
                "company": pi.get("counterparty", "系统检测"),
                "date": pi.get("last_date", pi.get("date", "")),
                "amount": pi.get("avg_amount", pi.get("amount", 0)),
                "direction": "周期收入",
                "description": pi.get("description", f"周期性收入: {pi.get('period_type', '未知')}"),
                "risk_level": pi.get("risk_level", "low")
            })
    
    # 2. 整合关联方分析结果
    rp_results = analysis_results.get("relatedParty", {})
    direct_flows = rp_results.get("direct_flows", [])
    for flow in direct_flows:
        if isinstance(flow, dict):
            enhanced["direct_transfers"].append({
                "person": flow.get("from_person", flow.get("person", "")),
                "company": flow.get("to_person", flow.get("counterparty", "")),
                "date": flow.get("date", ""),
                "amount": flow.get("amount", 0),
                "direction": "关联往来",
                "description": flow.get("description", "关联方资金往来"),
                "risk_level": flow.get("risk_level", "medium")
            })
    
    logger.info(f"风险整合: 原始{len(suspicions.get('direct_transfers', []))}条 + "
               f"时序分析{len(sudden_changes)+len(delayed_transfers)+len(periodic_income)}条 + "
               f"关联方{len(direct_flows)}条 = {len(enhanced.get('direct_transfers', []))}条")
    
    return enhanced

def serialize_profiles(profiles: Dict) -> Dict:
    """序列化画像数据为 JSON 格式"""
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
        
        # 从 summary 或 income_structure 中获取数据
        summary = profile.get("summary", {})
        income_structure = profile.get("income_structure", {})
        
        # 优先从 summary 获取，如果没有则从 income_structure 获取
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

def serialize_suspicions(suspicions: Dict) -> Dict:
    """序列化疑点数据为 JSON 格式"""
    result = {
        "directTransfers": [],
        "cashCollisions": [],
        "hiddenAssets": {},
        "fixedFrequency": {},
        "cashTimingPatterns": [],
        "holidayTransactions": {},
        "amountPatterns": {},
    }
    
    # 转换直接转账 (后端字段: person, company, date, amount, direction)
    for tx in suspicions.get("direct_transfers", []):
        # 根据direction决定from/to
        direction = tx.get("direction", "payment")
        if direction == "payment":
            # 人员付款给公司
            from_entity = str(tx.get("person", ""))
            to_entity = str(tx.get("company", ""))
        else:
            # 人员从公司收款
            from_entity = str(tx.get("company", ""))
            to_entity = str(tx.get("person", ""))
        
        result["directTransfers"].append({
            "from": from_entity,
            "to": to_entity,
            "amount": float(tx.get("amount", 0)),
            "date": str(tx.get("date", "")),
            "description": str(tx.get("description", "")),
        })
    
    # 转换现金碰撞 (后端字段: withdrawal_entity, deposit_entity, withdrawal_date, etc.)
    for collision in suspicions.get("cash_collisions", []):
        result["cashCollisions"].append({
            "person1": str(collision.get("withdrawal_entity", collision.get("person1", ""))),
            "person2": str(collision.get("deposit_entity", collision.get("person2", ""))),
            "time1": str(collision.get("withdrawal_date", collision.get("time1", ""))),
            "time2": str(collision.get("deposit_date", collision.get("time2", ""))),
            "amount1": float(collision.get("withdrawal_amount", collision.get("amount1", 0))),
            "amount2": float(collision.get("deposit_amount", collision.get("amount2", 0))),
        })
    
    # 转换现金时间点配对 (保持原有逻辑但更健壮)
    for pattern in suspicions.get("cash_timing_patterns", []):
        if isinstance(pattern, dict):
            result["cashTimingPatterns"].append({
                "person1": str(pattern.get("person1", pattern.get("withdrawal_entity", ""))),
                "person2": str(pattern.get("person2", pattern.get("deposit_entity", ""))),
                "time1": str(pattern.get("time1", pattern.get("withdrawal_date", ""))),
                "time2": str(pattern.get("time2", pattern.get("deposit_date", ""))),
                "amount1": float(pattern.get("amount1", pattern.get("withdrawal_amount", 0))),
                "amount2": float(pattern.get("amount2", pattern.get("deposit_amount", 0))),
                "timeDiff": float(pattern.get("timeDiff", pattern.get("time_diff_hours", 0))),
            })
        else:
            result["cashTimingPatterns"].append({"raw": str(pattern)})
    
    # 转换其他字典类型字段
    for snake_key, camel_key in [
        ("hidden_assets", "hiddenAssets"),
        ("fixed_frequency", "fixedFrequency"), 
        ("holiday_transactions", "holidayTransactions"),
        ("amount_patterns", "amountPatterns")
    ]:
        if snake_key in suspicions and isinstance(suspicions[snake_key], dict):
            for k, v in suspicions[snake_key].items():
                if isinstance(v, (int, float)):
                    result[camel_key][str(k)] = float(v)
                elif isinstance(v, list):
                    result[camel_key][str(k)] = [
                        float(x) if isinstance(x, (int, float)) else str(x) for x in v
                    ]
                elif isinstance(v, dict):
                    result[camel_key][str(k)] = {
                        str(kk): float(vv) if isinstance(vv, (int, float)) else str(vv)
                        for kk, vv in v.items()
                    }
                else:
                    result[camel_key][str(k)] = str(v)
    
    return result

def serialize_analysis_results(analysis_results: Dict) -> Dict:
    """序列化分析结果为前端期望的 JSON 格式"""
    # 定义前端期望的默认结构
    default = {
        "loan": {
            "summary": {"双向往来关系数": 0, "网贷平台交易数": 0, "规律还款模式数": 0},
            "details": []
        },
        "income": {
            "summary": {"规律性非工资收入": 0, "个人大额转入": 0, "来源不明收入": 0},
            "details": []
        },
        "ml": {
            "summary": {"anomalyCount": 0, "highRiskCount": 0},
            "predictions": []
        },
        "penetration": {
            "summary": {"资金穿透链数": 0, "中间节点数": 0},
            "chains": []
        },
        "relatedParty": {
            "summary": {"直接往来笔数": 0, "第三方中转链数": 0, "资金闭环数": 0},
            "details": []
        },
        "correlation": {
            "summary": {"资金碰撞总数": 0},
            "correlations": []
        },
        "timeSeries": {
            "summary": {"异常时间点数": 0},
            "anomalies": []
        },
        "aggregation": {
            "rankedEntities": [],
            "summary": {"极高风险实体数": 0, "高风险实体数": 0}
        },
    }
    
    # 合并实际的分析结果
    for key, value in analysis_results.items():
        if key in default:
            default[key] = _convert_result_to_serializable(value, default[key])
        else:
            default[key] = _convert_value(value)
    
    return default

def _convert_result_to_serializable(value: Any, default_struct: Dict) -> Dict:
    """将分析结果转换为可序列化格式，保持默认结构"""
    if not isinstance(value, dict):
        return default_struct
    
    result = default_struct.copy()
    
    # 处理 summary 字段
    if "summary" in value and isinstance(value["summary"], dict):
        if "summary" in result:
            result["summary"] = {**result["summary"], **_convert_dict(value["summary"])}
        else:
            result["summary"] = _convert_dict(value["summary"])
    
    # 处理列表类型的字段 (details, predictions, chains, correlations, anomalies, rankedEntities)
    for list_key in ["details", "predictions", "chains", "correlations", "anomalies", "rankedEntities"]:
        if list_key in value and isinstance(value[list_key], list):
            result[list_key] = [_convert_value(item) for item in value[list_key]]
    
    return result

def _convert_dict(d: Dict) -> Dict:
    """转换字典中的值为可序列化格式"""
    return {str(k): _convert_value(v) for k, v in d.items()}

def _convert_value(v: Any) -> Any:
    """转换单个值为可序列化格式"""
    if isinstance(v, (int, float)):
        return float(v) if not isinstance(v, bool) else v
    elif isinstance(v, dict):
        return _convert_dict(v)
    elif isinstance(v, list):
        return [_convert_value(item) for item in v]
    elif v is None:
        return None
    else:
        return str(v)

# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
