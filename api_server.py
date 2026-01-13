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
        
        # 保存结果
        analysis_state.results = {
            "persons": all_persons,
            "companies": all_companies,
            "profiles": serialize_profiles(profiles),
            "suspicions": serialize_suspicions(suspicions),
            "analysisResults": analysis_results,
        }
        
        duration = (analysis_state.end_time - analysis_state.start_time).total_seconds()
        logger.info(f"✓ 分析完成，耗时 {duration:.2f} 秒")
        
        # 广播完成状态
        asyncio.run(manager.broadcast({
            "type": "complete",
            "data": analysis_state.to_dict()
        }))
        
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

def serialize_profiles(profiles: Dict) -> Dict:
    """序列化画像数据为 JSON 格式"""
    result = {}
    for entity, profile in profiles.items():
        result[entity] = {
            "entityName": entity,
            "totalIncome": profile.get("total_income", 0),
            "totalExpense": profile.get("total_expense", 0),
            "transactionCount": profile.get("transaction_count", 0),
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
    
    # 转换直接转账
    for tx in suspicions.get("direct_transfers", []):
        result["directTransfers"].append({
            "from": str(tx.get("from", "")),
            "to": str(tx.get("to", "")),
            "amount": float(tx.get("amount", 0)),
            "date": str(tx.get("date", "")),
        })
    
    # 转换现金碰撞
    for collision in suspicions.get("cash_collisions", []):
        result["cashCollisions"].append({
            "person1": str(collision.get("person1", "")),
            "person2": str(collision.get("person2", "")),
            "time1": str(collision.get("time1", "")),
            "time2": str(collision.get("time2", "")),
            "amount1": float(collision.get("amount1", 0)),
            "amount2": float(collision.get("amount2", 0)),
        })
    
    return result

# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
