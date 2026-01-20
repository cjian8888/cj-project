#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金穿透审计系统 - FastAPI 后端服务

提供 RESTful API 和 WebSocket 实时日志推送，连接 React 前端与 Python 分析引擎

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                        🚨🚨🚨 数据来源铁律 🚨🚨🚨                              ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║                                                                              ║
# ║  输出目录下的 `cleaned_data` 文件夹（及其子目录 `个人` 和 `公司`）中的         ║
# ║  Excel 文件，是本系统【唯一合法】的数据来源。                                 ║
# ║                                                                              ║
# ║  任何 API 接口（无论是概览、列表还是图谱），都必须基于这里面的数据进行         ║
# ║  读取和计算。【严禁】直接读取原始输入目录 (`data/`) 或依赖内存中未落盘的       ║
# ║  临时变量。                                                                  ║
# ║                                                                              ║
# ║  执行口号：Excel 里有什么，界面就显示什么；Excel 里没有的，界面绝不许瞎编。   ║
# ║                                                                              ║
# ║  数据流：                                                                    ║
# ║    main.py (后端) → 读取 data/ → 清洗 → 保存 cleaned_data/*.xlsx            ║
# ║    api_server.py (前端API) → 只读取 cleaned_data/*.xlsx → 返回给界面        ║
# ║                                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ==================== Windows asyncio 兼容性修复 ====================
# 修复 Python 3.11+ 在 Windows 上 ProactorEventLoop 的已知 bug:
# "AssertionError: assert f is self._write_fut" in _loop_writing
# 参考: https://github.com/python/cpython/issues/109538
import asyncio
import sys

if sys.platform == 'win32':
    # 使用更稳定的 SelectorEventLoop 替代问题较多的 ProactorEventLoop
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# ====================================================================

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
import threading
import queue

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
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


# ==================== 自定义 JSON 编码器 ====================

class CustomJSONEncoder(json.JSONEncoder):
    """处理 Pandas Timestamp 和 numpy 类型的 JSON 编码器"""
    def default(self, obj):
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        if hasattr(obj, 'to_pydatetime'):  # Pandas Timestamp
            return obj.to_pydatetime().isoformat()
        if hasattr(obj, 'dtype'):  # numpy types
            if hasattr(obj, 'item'):
                return obj.item()
        if hasattr(obj, 'tolist'):  # numpy array
            return obj.tolist()
        if pd.isna(obj):
            return None
        return super().default(obj)


def _make_json_serializable(obj):
    """
    递归将对象转换为 JSON 可序列化格式
    
    处理 Pandas Timestamp、numpy 数组、NaN 等特殊类型
    在保存缓存前调用此函数预处理数据
    """
    if obj is None:
        return None
    
    # 首先处理复合类型（dict、list、tuple）- 递归处理其内容
    if isinstance(obj, dict):
        return {str(k): _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    
    # 处理 numpy 数组（必须在检查 pd.isna 之前，因为数组会导致 isna 返回数组）
    if hasattr(obj, 'tolist'):  # numpy array
        return obj.tolist()
    
    # 处理日期时间类型
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if hasattr(obj, 'to_pydatetime'):
        return obj.to_pydatetime().isoformat()
    
    # 处理 numpy 标量
    if hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    
    # 安全检查 NaN（使用 try-except 保护）
    try:
        if pd.isna(obj):
            return None
    except (ValueError, TypeError):
        # 如果 isna 无法处理该对象，忽略错误
        pass
    
    # 处理基本类型
    if isinstance(obj, (int, float, str, bool)):
        return obj
    
    return str(obj)

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
        # 【P1修复】遍历连接副本，避免并发修改；发送失败时移除失效连接
        dead_connections = []
        for connection in self.active_connections.copy():
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        
        # 清理失效连接
        for conn in dead_connections:
            self.disconnect(conn)

manager = ConnectionManager()

# 缓存文件路径（使用 config.py 中的配置）
RESULTS_CACHE_PATH = config.CACHE_PATH

# 🆕 分析缓存目录（用于 /api/results 铁律化）
ANALYSIS_CACHE_DIR = os.path.join("./output", "analysis_cache")

# 当前配置的目录（用于缓存验证）
_current_config = {
    "inputDirectory": "./data",
    "outputDirectory": "./output"
}

# ==================== 🆕 分析缓存层（铁律: /api/results 不再依赖内存）====================

def _get_cleaned_data_mtime(output_dir: str = None) -> float:
    """
    获取 cleaned_data 目录下所有 Excel 文件的最新修改时间
    
    用于缓存一致性校验：如果 cleaned_data 有更新，则缓存失效
    
    Returns:
        最新的修改时间戳（float），如果目录不存在返回 0
    """
    if output_dir is None:
        output_dir = _current_config.get("outputDirectory", "./output")
    
    cleaned_data_dir = os.path.join(output_dir, "cleaned_data")
    latest_mtime = 0.0
    
    if not os.path.exists(cleaned_data_dir):
        return 0.0
    
    for subdir in ["个人", "公司"]:
        subdir_path = os.path.join(cleaned_data_dir, subdir)
        if os.path.exists(subdir_path):
            for filename in os.listdir(subdir_path):
                if filename.endswith('.xlsx') and not filename.startswith('~$'):
                    filepath = os.path.join(subdir_path, filename)
                    try:
                        mtime = os.path.getmtime(filepath)
                        latest_mtime = max(latest_mtime, mtime)
                    except OSError:
                        pass
    
    return latest_mtime


def _compute_cleaned_data_hash(output_dir: str = None) -> str:
    """
    计算 cleaned_data 目录的内容哈希（版本标识）
    
    【P2 优化 - 2026-01-18】基于内容哈希替代 mtime
    解决问题：
    - mtime 在分布式系统中不可靠
    - 并发写入时可能读取到不一致的数据
    
    哈希计算基于：
    - 文件列表（排序后）
    - 每个文件的大小
    - 每个文件的 mtime（作为补充）
    
    Returns:
        16 位哈希字符串，如 "a1b2c3d4e5f67890"
    """
    import hashlib
    
    if output_dir is None:
        output_dir = _current_config.get("outputDirectory", "./output")
    
    cleaned_data_dir = os.path.join(output_dir, "cleaned_data")
    
    if not os.path.exists(cleaned_data_dir):
        return "empty"
    
    # 收集所有文件信息
    file_info_list = []
    
    for subdir in ["个人", "公司"]:
        subdir_path = os.path.join(cleaned_data_dir, subdir)
        if os.path.exists(subdir_path):
            for filename in sorted(os.listdir(subdir_path)):
                if filename.endswith('.xlsx') and not filename.startswith('~$'):
                    filepath = os.path.join(subdir_path, filename)
                    try:
                        stat = os.stat(filepath)
                        file_info_list.append(f"{subdir}/{filename}:{stat.st_size}:{int(stat.st_mtime)}")
                    except OSError:
                        pass
    
    if not file_info_list:
        return "empty"
    
    # 计算哈希
    content = "|".join(file_info_list)
    hash_obj = hashlib.md5(content.encode('utf-8'))
    return hash_obj.hexdigest()[:16]


def _save_analysis_cache(results: Dict, output_dir: str = None) -> bool:
    """
    【铁律核心】将分析结果持久化到 analysis_cache 目录
    
    保存的文件：
    - profiles.json: 资金画像
    - suspicions.json: 可疑交易
    - derived_data.json: 借贷分析、收入分析等派生数据
    - metadata.json: 元数据（生成时间、cleaned_data 版本哈希）
    
    Args:
        results: 分析结果字典，需包含 profiles, suspicions, analysisResults 等
        output_dir: 输出目录，默认使用 _current_config["outputDirectory"]
        
    Returns:
        保存是否成功
    """
    if output_dir is None:
        output_dir = _current_config.get("outputDirectory", "./output")
    
    cache_dir = os.path.join(output_dir, "analysis_cache")
    
    try:
        # 创建缓存目录
        os.makedirs(cache_dir, exist_ok=True)
        
        # 获取 cleaned_data 的最新修改时间（用于一致性校验）
        cleaned_data_mtime = _get_cleaned_data_mtime(output_dir)
        
        # 【P2 优化】计算数据哈希（更可靠的版本控制）
        data_hash = _compute_cleaned_data_hash(output_dir)
        
        # 1. 保存 metadata.json
        metadata = {
            "version": "3.1.0",  # 升级版本号
            "generatedAt": datetime.now().isoformat(),
            "generatedTimestamp": datetime.now().timestamp(),
            "cleanedDataMtime": cleaned_data_mtime,
            "cleanedDataMtimeHuman": datetime.fromtimestamp(cleaned_data_mtime).isoformat() if cleaned_data_mtime > 0 else None,
            "dataHash": data_hash,  # 【P2 新增】基于内容的版本标识
            "persons": results.get("persons", []),
            "companies": results.get("companies", []),
        }
        metadata_path = os.path.join(cache_dir, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 2. 保存 profiles.json (预处理数据确保可序列化)
        profiles_path = os.path.join(cache_dir, "profiles.json")
        with open(profiles_path, 'w', encoding='utf-8') as f:
            json.dump(_make_json_serializable(results.get("profiles", {})), f, ensure_ascii=False, indent=2)
        
        # 3. 保存 suspicions.json (预处理数据确保可序列化)
        suspicions_path = os.path.join(cache_dir, "suspicions.json")
        with open(suspicions_path, 'w', encoding='utf-8') as f:
            json.dump(_make_json_serializable(results.get("suspicions", {})), f, ensure_ascii=False, indent=2)
        
        # 4. 保存 derived_data.json（analysisResults，预处理数据确保可序列化）
        derived_path = os.path.join(cache_dir, "derived_data.json")
        with open(derived_path, 'w', encoding='utf-8') as f:
            json.dump(_make_json_serializable(results.get("analysisResults", {})), f, ensure_ascii=False, indent=2)
        
        # 5. 保存 graph_data.json（可选，用于图谱，预处理数据确保可序列化）
        if results.get("graphData"):
            graph_path = os.path.join(cache_dir, "graph_data.json")
            with open(graph_path, 'w', encoding='utf-8') as f:
                json.dump(_make_json_serializable(results.get("graphData")), f, ensure_ascii=False, indent=2)
        
        logger.info(f"📦 分析缓存已保存: {cache_dir}")
        logger.info(f"   - metadata.json: {len(metadata.get('persons', []))} 人员, {len(metadata.get('companies', []))} 企业")
        logger.info(f"   - cleaned_data 版本时间: {metadata.get('cleanedDataMtimeHuman', 'N/A')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 保存分析缓存失败: {e}")
        return False


def _load_analysis_cache(output_dir: str = None) -> tuple[Optional[Dict], str]:
    """
    【铁律核心】从 analysis_cache 目录加载分析结果
    
    一致性校验：比较 metadata.json 中的时间戳与 cleaned_data 目录的修改时间
                如果 cleaned_data 更新了，则视为缓存失效
    
    Args:
        output_dir: 输出目录，默认使用 _current_config["outputDirectory"]
        
    Returns:
        (results, status_message)
        - results: 成功时返回分析结果字典，失败时返回 None
        - status_message: 状态描述（用于前端提示）
    """
    if output_dir is None:
        output_dir = _current_config.get("outputDirectory", "./output")
    
    cache_dir = os.path.join(output_dir, "analysis_cache")
    metadata_path = os.path.join(cache_dir, "metadata.json")
    
    # 检查缓存目录是否存在
    if not os.path.exists(cache_dir) or not os.path.exists(metadata_path):
        return None, "缓存不存在，请先运行分析"
    
    try:
        # 1. 读取 metadata.json
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 2. 一致性校验：【P2 优化】优先使用哈希，回退到 mtime
        cached_hash = metadata.get("dataHash", "")
        current_hash = _compute_cleaned_data_hash(output_dir)
        
        # 哈希校验（3.1.0+ 版本）
        if cached_hash and current_hash != "empty":
            if cached_hash != current_hash:
                logger.warning(f"⚠️ 分析缓存过期: 数据哈希不匹配")
                logger.warning(f"   缓存哈希: {cached_hash}")
                logger.warning(f"   当前哈希: {current_hash}")
                return None, "数据已更新，请重新运行分析"
        else:
            # 回退到 mtime 校验（兼容 3.0.0 版本缓存）
            cached_mtime = metadata.get("cleanedDataMtime", 0)
            current_mtime = _get_cleaned_data_mtime(output_dir)
            
            if current_mtime > cached_mtime:
                logger.warning(f"⚠️ 分析缓存过期: cleaned_data 已更新")
                logger.warning(f"   缓存时间: {metadata.get('cleanedDataMtimeHuman', 'N/A')}")
                logger.warning(f"   当前时间: {datetime.fromtimestamp(current_mtime).isoformat()}")
                return None, "数据已更新，请重新运行分析"
        
        # 3. 读取各个缓存文件
        profiles_path = os.path.join(cache_dir, "profiles.json")
        suspicions_path = os.path.join(cache_dir, "suspicions.json")
        derived_path = os.path.join(cache_dir, "derived_data.json")
        graph_path = os.path.join(cache_dir, "graph_data.json")
        
        profiles = {}
        suspicions = {}
        analysis_results = {}
        graph_data = None
        
        if os.path.exists(profiles_path):
            with open(profiles_path, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
        
        if os.path.exists(suspicions_path):
            with open(suspicions_path, 'r', encoding='utf-8') as f:
                suspicions = json.load(f)
        
        if os.path.exists(derived_path):
            with open(derived_path, 'r', encoding='utf-8') as f:
                analysis_results = json.load(f)
        
        if os.path.exists(graph_path):
            with open(graph_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
        
        # 4. 组装完整结果
        results = {
            "persons": metadata.get("persons", []),
            "companies": metadata.get("companies", []),
            "profiles": profiles,
            "suspicions": suspicions,
            "analysisResults": analysis_results,
            "graphData": graph_data,
            "_meta": {
                "source": "analysis_cache",
                "generatedAt": metadata.get("generatedAt"),
                "cleanedDataMtime": metadata.get("cleanedDataMtimeHuman"),
            }
        }
        
        logger.info(f"📦 加载分析缓存: {cache_dir}")
        logger.info(f"   - {len(results.get('persons', []))} 人员, {len(results.get('companies', []))} 企业")
        logger.info(f"   - 生成时间: {metadata.get('generatedAt', 'N/A')}")
        
        return results, "success"
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ 分析缓存文件损坏 (JSON解析失败): {e}")
        return None, "缓存文件损坏，请重新运行分析"
    except Exception as e:
        logger.error(f"❌ 加载分析缓存失败: {e}")
        return None, f"加载缓存失败: {str(e)}"

def _get_directory_fingerprint(directory: str) -> Dict:
    """获取目录的指纹信息（用于判断数据是否变化）"""
    if not os.path.exists(directory):
        return {"exists": False, "fileCount": 0, "totalSize": 0}
    
    file_count = 0
    total_size = 0
    latest_modified = 0
    
    try:
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith(('.xlsx', '.xls', '.csv')):
                    file_count += 1
                    filepath = os.path.join(root, f)
                    stat = os.stat(filepath)
                    total_size += stat.st_size
                    latest_modified = max(latest_modified, stat.st_mtime)
    except Exception as e:
        logging.warning(f"获取目录指纹失败: {e}")
    
    return {
        "exists": True,
        "fileCount": file_count,
        "totalSize": total_size,
        "latestModified": latest_modified
    }

# ==================== 🚨 成品库读取层 (铁律核心实现) ====================

import pandas as pd
from typing import Tuple

# 【铁律】智能匹配 Excel 列名 - 使用 config.py 中的统一配置
# 今后修改列名只需改 config.py 一处
INCOME_COLUMN_VARIANTS = config.INCOME_COLUMN_VARIANTS
EXPENSE_COLUMN_VARIANTS = config.EXPENSE_COLUMN_VARIANTS

def _find_column(df: pd.DataFrame, variants: list) -> str:
    """
    在DataFrame中查找匹配的列名
    
    Args:
        df: DataFrame
        variants: 候选列名列表，按优先级排序
        
    Returns:
        找到的列名，或 None
    """
    for col in variants:
        if col in df.columns:
            return col
    return None

def _safe_sum_amount(df: pd.DataFrame, col: str) -> float:
    """
    安全地计算金额列的总和，处理类型不一致的情况
    
    Args:
        df: DataFrame
        col: 列名
        
    Returns:
        金额总和（float），如果失败返回 0.0
    """
    if col is None or col not in df.columns:
        return 0.0
    
    try:
        # 先转换为数值类型，无法转换的变为 NaN
        numeric_col = pd.to_numeric(df[col], errors='coerce')
        return numeric_col.fillna(0).abs().sum()
    except Exception as e:
        logging.warning(f"[金额计算] 列 '{col}' 转换失败: {e}")
        return 0.0


def _load_cleaned_data(output_dir: str = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    【铁律核心方法】从 cleaned_data 目录加载已清洗的成品数据
    
    这是本系统唯一合法的数据读取入口！
    严禁使用 file_categorizer.categorize_files() + data_cleaner.clean_and_merge_files() 
    重新读取原始数据。
    
    Args:
        output_dir: 输出目录路径，默认使用 _current_config["outputDirectory"]
        
    Returns:
        (cleaned_data_dict, metadata)
        - cleaned_data_dict: {实体名称: DataFrame} 的字典
        - metadata: 包含统计信息的字典
            - persons: 个人名称列表
            - companies: 公司名称列表
            - person_count: 个人数量
            - company_count: 公司数量
            - total_records: 总记录数
            - total_amount: 资金总规模（收入+支出绝对值）
    """
    if output_dir is None:
        output_dir = _current_config.get("outputDirectory", "./output")
    
    cleaned_data_dir = os.path.join(output_dir, "cleaned_data")
    person_dir = os.path.join(cleaned_data_dir, "个人")
    company_dir = os.path.join(cleaned_data_dir, "公司")
    
    cleaned_data = {}
    persons = []
    companies = []
    total_records = 0
    total_income = 0.0
    total_expense = 0.0
    
    # 读取个人数据
    if os.path.exists(person_dir):
        for filename in os.listdir(person_dir):
            if filename.endswith('.xlsx') and not filename.startswith('~$'):
                # 解析文件名：格式为 "姓名_合并流水.xlsx"
                entity_name = filename.replace('_合并流水.xlsx', '').replace('_合并流水.xls', '')
                filepath = os.path.join(person_dir, filename)
                
                try:
                    df = pd.read_excel(filepath, engine='openpyxl')
                    if not df.empty:
                        cleaned_data[entity_name] = df
                        persons.append(entity_name)
                        total_records += len(df)
                        
                        # 计算资金规模（智能匹配列名，类型安全）
                        income_col = _find_column(df, INCOME_COLUMN_VARIANTS)
                        expense_col = _find_column(df, EXPENSE_COLUMN_VARIANTS)
                        total_income += _safe_sum_amount(df, income_col)
                        total_expense += _safe_sum_amount(df, expense_col)
                            
                        logging.info(f"[CleanedData] 加载个人: {entity_name} ({len(df)} 条)")
                except Exception as e:
                    logging.warning(f"[CleanedData] 读取失败 {filepath}: {e}")
    
    # 读取公司数据
    if os.path.exists(company_dir):
        for filename in os.listdir(company_dir):
            if filename.endswith('.xlsx') and not filename.startswith('~$'):
                entity_name = filename.replace('_合并流水.xlsx', '').replace('_合并流水.xls', '')
                filepath = os.path.join(company_dir, filename)
                
                try:
                    df = pd.read_excel(filepath, engine='openpyxl')
                    if not df.empty:
                        cleaned_data[entity_name] = df
                        companies.append(entity_name)
                        total_records += len(df)
                        
                        # 计算资金规模（智能匹配列名，类型安全）
                        income_col = _find_column(df, INCOME_COLUMN_VARIANTS)
                        expense_col = _find_column(df, EXPENSE_COLUMN_VARIANTS)
                        total_income += _safe_sum_amount(df, income_col)
                        total_expense += _safe_sum_amount(df, expense_col)
                            
                        logging.info(f"[CleanedData] 加载公司: {entity_name} ({len(df)} 条)")
                except Exception as e:
                    logging.warning(f"[CleanedData] 读取失败 {filepath}: {e}")
    
    metadata = {
        "persons": persons,
        "companies": companies,
        "person_count": len(persons),
        "company_count": len(companies),
        "total_records": total_records,
        "total_income": total_income,
        "total_expense": total_expense,
        "total_amount": total_income + total_expense,
        "cleaned_data_dir": cleaned_data_dir,
    }
    
    logging.info(f"[CleanedData] 成品库加载完成: {len(persons)} 人, {len(companies)} 公司, "
                f"共 {total_records} 条记录, 资金规模 {(total_income + total_expense)/10000:.2f} 万元")
    
    return cleaned_data, metadata

def _get_cleaned_data_stats(output_dir: str = None) -> Dict[str, Any]:
    """
    【快速统计接口】获取 cleaned_data 目录的统计摘要（不加载全部数据到内存）
    
    用于 /api/analysis/stats 等接口快速返回概览数据
    """
    if output_dir is None:
        output_dir = _current_config.get("outputDirectory", "./output")
    
    cleaned_data_dir = os.path.join(output_dir, "cleaned_data")
    person_dir = os.path.join(cleaned_data_dir, "个人")
    company_dir = os.path.join(cleaned_data_dir, "公司")
    
    persons = []
    companies = []
    total_records = 0
    total_income = 0.0
    total_expense = 0.0
    
    # 扫描个人目录
    if os.path.exists(person_dir):
        for filename in os.listdir(person_dir):
            if filename.endswith('.xlsx') and not filename.startswith('~$'):
                entity_name = filename.replace('_合并流水.xlsx', '').replace('_合并流水.xls', '')
                persons.append(entity_name)
                
                # 读取 Excel 获取记录数和金额
                filepath = os.path.join(person_dir, filename)
                try:
                    df = pd.read_excel(filepath, engine='openpyxl')
                    total_records += len(df)
                    
                    # 计算资金规模（智能匹配列名，类型安全）
                    income_col = _find_column(df, INCOME_COLUMN_VARIANTS)
                    expense_col = _find_column(df, EXPENSE_COLUMN_VARIANTS)
                    total_income += _safe_sum_amount(df, income_col)
                    total_expense += _safe_sum_amount(df, expense_col)
                except Exception as e:
                    logging.warning(f"[Stats] 读取失败 {filepath}: {e}")
    
    # 扫描公司目录
    if os.path.exists(company_dir):
        for filename in os.listdir(company_dir):
            if filename.endswith('.xlsx') and not filename.startswith('~$'):
                entity_name = filename.replace('_合并流水.xlsx', '').replace('_合并流水.xls', '')
                companies.append(entity_name)
                
                filepath = os.path.join(company_dir, filename)
                try:
                    df = pd.read_excel(filepath, engine='openpyxl')
                    total_records += len(df)
                    
                    # 计算资金规模（智能匹配列名，类型安全）
                    income_col = _find_column(df, INCOME_COLUMN_VARIANTS)
                    expense_col = _find_column(df, EXPENSE_COLUMN_VARIANTS)
                    total_income += _safe_sum_amount(df, income_col)
                    total_expense += _safe_sum_amount(df, expense_col)
                except Exception as e:
                    logging.warning(f"[Stats] 读取失败 {filepath}: {e}")
    
    return {
        "corePersonCount": len(persons),
        "corePersonNames": persons,
        "involvedCompanyCount": len(companies),
        "involvedCompanyNames": companies,
        "totalRecords": total_records,
        "totalIncome": total_income,
        "totalExpense": total_expense,
        "totalAmount": total_income + total_expense,
        "totalAmountDisplay": f"{(total_income + total_expense)/10000:.2f} 万元",
    }


def _validate_cache(cached: Dict) -> tuple[bool, str]:
    """
    验证缓存是否有效
    
    返回: (是否有效, 原因说明)
    """
    meta = cached.get("_meta", {})
    
    if not meta:
        return False, "缓存缺少元数据"
    
    # 【P1修复】使用配置的版本号进行兼容性检查
    cache_version = meta.get("version", "0.0.0")
    try:
        cache_major = int(cache_version.split(".")[0])
        if cache_major != config.CACHE_VERSION_MAJOR:
            return False, f"缓存版本不兼容: {cache_version} (需要 {config.CACHE_VERSION_MAJOR}.x.x)"
    except (ValueError, IndexError):
        return False, f"缓存版本格式错误: {cache_version}"
    
    # 检查输入目录是否匹配
    cached_input_dir = os.path.normpath(meta.get("inputDirectory", ""))
    current_input_dir = os.path.normpath(_current_config["inputDirectory"])
    
    if cached_input_dir != current_input_dir:
        return False, f"输入目录变化: {cached_input_dir} → {current_input_dir}"
    
    # 检查文件是否有变化（可选的更严格检查）
    cached_fingerprint = meta.get("sourceFingerprint", {})
    current_fingerprint = _get_directory_fingerprint(current_input_dir)
    
    if cached_fingerprint.get("fileCount", 0) != current_fingerprint.get("fileCount", 0):
        return False, f"文件数量变化: {cached_fingerprint.get('fileCount')} → {current_fingerprint.get('fileCount')}"
    
    # 检查是否有更新的文件
    if current_fingerprint.get("latestModified", 0) > meta.get("analysisTimestamp", 0):
        return False, "检测到数据目录有更新"
    
    return True, "缓存有效"

def _load_cached_results() -> Optional[Dict]:
    """从磁盘加载缓存的分析结果"""
    if not os.path.exists(RESULTS_CACHE_PATH):
        return None
    
    try:
        with open(RESULTS_CACHE_PATH, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        
        # 验证缓存有效性
        is_valid, reason = _validate_cache(cached)
        
        if is_valid:
            logging.info(f"[Cache] 缓存验证通过: {reason}")
            return cached
        else:
            logging.warning(f"[Cache] 缓存无效: {reason}")
            return None
            
    except json.JSONDecodeError as e:
        logging.error(f"[Cache] 缓存文件损坏 (JSON解析失败): {e}")
        return None
    except Exception as e:
        logging.warning(f"[Cache] 加载缓存失败: {e}")
        return None

def _save_cached_results(results: Dict, input_dir: str, output_dir: str):
    """将分析结果保存到磁盘缓存，包含元数据"""
    try:
        # 构建带元数据的缓存
        fingerprint = _get_directory_fingerprint(input_dir)
        
        cache_with_meta = {
            "_meta": {
                "version": "3.0.0",
                "inputDirectory": os.path.normpath(input_dir),
                "outputDirectory": os.path.normpath(output_dir),
                "analysisTime": datetime.now().isoformat(),
                "analysisTimestamp": datetime.now().timestamp(),
                "sourceFingerprint": fingerprint,
            },
            **results
        }
        
        os.makedirs(os.path.dirname(RESULTS_CACHE_PATH), exist_ok=True)
        with open(RESULTS_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache_with_meta, f, ensure_ascii=False, indent=2)
        
        logging.info(f"[Cache] 分析结果已保存: {fingerprint.get('fileCount')} 个源文件, "
                    f"输入目录: {input_dir}")
    except Exception as e:
        logging.warning(f"[Cache] 保存缓存失败: {e}")

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
    
    # 【优化】启动时尝试从磁盘加载之前的分析结果
    cached_results = _load_cached_results()
    if cached_results:
        analysis_state.results = cached_results
        analysis_state.status = "completed"
        analysis_state.progress = 100
        analysis_state.current_phase = "分析完成（从缓存恢复）"
        
        # 【P0修复】从缓存元数据恢复时间信息
        meta = cached_results.get("_meta", {})
        if meta.get("analysisTime"):
            try:
                analysis_state.end_time = datetime.fromisoformat(meta["analysisTime"])
                # 假设分析耗时约1分钟（用于显示）
                analysis_state.start_time = analysis_state.end_time - timedelta(minutes=1)
            except (ValueError, TypeError):
                pass
        
        logging.info(f"[Cache] 已恢复分析结果: {len(cached_results.get('persons', []))} 人员, "
                    f"{len(cached_results.get('companies', []))} 企业, "
                    f"图谱缓存: {'有' if cached_results.get('graphData') else '无'}")
    
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
        except Exception as e:
            # 【P2修复】记录异常而非静默忽略
            logging.debug(f"日志广播异常: {e}")
            await asyncio.sleep(0.1)

# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="F.P.A.S API",
    description="资金穿透审计系统 API 服务",
    version="4.3.0",
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
    """
    【铁律实现】获取分析结果
    
    数据来源：从 analysis_cache 目录加载持久化的分析结果，而非内存变量
    
    一致性校验：
    - 如果 cleaned_data 目录的修改时间晚于缓存生成时间，缓存视为失效
    - 失效时返回错误提示，引导用户重新运行分析
    
    兼容性：
    - 如果缓存读取失败但内存中有数据，仍尝试返回内存数据（降级策略）
    """
    # 【铁律核心】优先从 analysis_cache 目录读取
    cached_results, status_msg = _load_analysis_cache()
    
    if cached_results is not None:
        logger.info(f"📦 /api/results: 从缓存加载成功")
        return {"message": "success", "source": "analysis_cache", "data": cached_results}
    
    # 缓存失败时的降级策略：尝试使用内存数据
    if analysis_state.results is not None:
        logger.warning(f"⚠️ /api/results: 缓存不可用 ({status_msg})，使用内存数据")
        return {
            "message": "success", 
            "source": "memory", 
            "warning": status_msg,
            "data": analysis_state.results
        }
    
    # 两者都没有
    logger.warning(f"⚠️ /api/results: 无可用数据 - {status_msg}")
    return {
        "message": status_msg, 
        "source": None,
        "data": None,
        "hint": "请点击「开始分析」按钮运行分析任务"
    }

@app.get("/api/analysis/stats")
async def get_analysis_stats():
    """
    【铁律实现】获取分析统计概览
    
    数据来源：直接从 cleaned_data 目录读取，而非内存缓存
    
    返回:
    - corePersonCount: 核心人员数量 = cleaned_data/个人 下的文件数量
    - involvedCompanyCount: 涉案公司数量 = cleaned_data/公司 下的文件数量
    - totalAmount: 资金规模 = 所有 Excel 中金额列的总和
    - totalRecords: 总交易记录数
    """
    try:
        stats = _get_cleaned_data_stats()
        return {
            "message": "success",
            "source": "cleaned_data",
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计数据失败: {str(e)}")


@app.get("/api/cache/info")
async def get_cache_info():
    """获取缓存状态和元数据
    
    返回:
    - hasCachedData: 是否有缓存数据
    - isValid: 缓存是否有效
    - reason: 验证结果说明
    - meta: 缓存元数据（如果存在）
    """
    # 检查内存中是否有数据
    if analysis_state.results is not None:
        meta = analysis_state.results.get("_meta", {})
        return {
            "hasCachedData": True,
            "isValid": True,
            "reason": "内存中有分析结果",
            "source": "memory",
            "meta": meta
        }
    
    # 检查磁盘缓存
    if not os.path.exists(RESULTS_CACHE_PATH):
        return {
            "hasCachedData": False,
            "isValid": False,
            "reason": "无缓存文件",
            "source": None,
            "meta": None
        }
    
    try:
        with open(RESULTS_CACHE_PATH, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        
        is_valid, reason = _validate_cache(cached)
        meta = cached.get("_meta", {})
        
        return {
            "hasCachedData": True,
            "isValid": is_valid,
            "reason": reason,
            "source": "disk",
            "meta": meta
        }
    except Exception as e:
        return {
            "hasCachedData": False,
            "isValid": False,
            "reason": f"读取缓存失败: {str(e)}",
            "source": None,
            "meta": None
        }

@app.post("/api/cache/invalidate")
async def invalidate_cache():
    """手动使缓存失效（用于用户主动选择重新分析）"""
    analysis_state.results = None
    analysis_state.status = "idle"
    analysis_state.progress = 0
    analysis_state.current_phase = ""
    
    # 删除磁盘缓存文件
    if os.path.exists(RESULTS_CACHE_PATH):
        try:
            os.remove(RESULTS_CACHE_PATH)
            logging.info("[Cache] 缓存已手动清除")
        except Exception as e:
            logging.warning(f"[Cache] 删除缓存文件失败: {e}")
    
    return {"message": "缓存已清除", "status": "idle"}

@app.get("/api/audit-navigation")
async def get_audit_navigation():
    """
    【智能审计导航】获取核查资料索引信息
    
    返回清洗数据目录和核查报告的完整文件列表，供前端展示"核查资料索引"
    """
    output_dir = _current_config.get("outputDirectory", "./output")
    cleaned_data_dir = os.path.join(output_dir, "cleaned_data")
    analysis_results_dir = os.path.join(output_dir, "analysis_results")
    
    result = {
        "persons": [],
        "companies": [],
        "reports": [],
        "outputDir": output_dir,  # 返回相对输出目录
        "paths": {
            # 返回相对于输出目录的路径
            "cleanedDataPerson": "cleaned_data/个人",
            "cleanedDataCompany": "cleaned_data/公司",
            "analysisResults": "analysis_results",
        }
    }
    
    # 扫描个人清洗数据
    person_dir = os.path.join(cleaned_data_dir, "个人")
    if os.path.exists(person_dir):
        for filename in sorted(os.listdir(person_dir)):
            if filename.endswith('.xlsx') and not filename.startswith('~$'):
                filepath = os.path.join(person_dir, filename)
                try:
                    stat = os.stat(filepath)
                    entity_name = filename.replace('_合并流水.xlsx', '')
                    result["persons"].append({
                        "name": entity_name,
                        "filename": filename,
                        "size": stat.st_size,
                        "sizeFormatted": f"{stat.st_size / 1024:.1f}KB",
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    })
                except OSError:
                    pass
    
    # 扫描公司清洗数据
    company_dir = os.path.join(cleaned_data_dir, "公司")
    if os.path.exists(company_dir):
        for filename in sorted(os.listdir(company_dir)):
            if filename.endswith('.xlsx') and not filename.startswith('~$'):
                filepath = os.path.join(company_dir, filename)
                try:
                    stat = os.stat(filepath)
                    entity_name = filename.replace('_合并流水.xlsx', '')
                    result["companies"].append({
                        "name": entity_name,
                        "filename": filename,
                        "size": stat.st_size,
                        "sizeFormatted": f"{stat.st_size / 1024:.1f}KB",
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    })
                except OSError:
                    pass
    
    # 扫描核查报告（优先展示核查底稿）
    if os.path.exists(analysis_results_dir):
        priority_files = ['资金核查底稿.xlsx', '资金流向可视化.html']
        other_files = []
        
        for filename in os.listdir(analysis_results_dir):
            filepath = os.path.join(analysis_results_dir, filename)
            if os.path.isfile(filepath):
                try:
                    stat = os.stat(filepath)
                    file_info = {
                        "name": filename,
                        "size": stat.st_size,
                        "sizeFormatted": f"{stat.st_size / 1024:.1f}KB",
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "isPrimary": filename in priority_files
                    }
                    if filename in priority_files:
                        result["reports"].insert(0, file_info)
                    else:
                        other_files.append(file_info)
                except OSError:
                    pass
        
        result["reports"].extend(other_files)
    
    return result


class OpenFolderRequest(BaseModel):
    relativePath: str  # 相对于输出目录的路径，如 "cleaned_data/个人"


@app.post("/api/open-folder")
async def open_folder(request: OpenFolderRequest):
    """
    打开指定文件夹（在文件资源管理器中）
    
    接收相对路径，基于当前配置的输出目录拼接完整路径
    """
    import subprocess
    import platform
    
    output_dir = _current_config.get("outputDirectory", "./output")
    target_path = os.path.abspath(os.path.join(output_dir, request.relativePath))
    
    # 安全检查：确保路径在输出目录内
    abs_output = os.path.abspath(output_dir)
    if not target_path.startswith(abs_output):
        raise HTTPException(status_code=400, detail="非法路径")
    
    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail=f"路径不存在: {request.relativePath}")
    
    try:
        system = platform.system()
        if system == "Windows":
            import ctypes
            import time
            
            # 先打开文件夹
            subprocess.Popen(f'explorer "{target_path}"', shell=True)
            
            # 等待窗口创建（增加等待时间）
            time.sleep(1.0)
            
            # 【改进】使用 Shell COM 接口精确查找并激活窗口
            try:
                import win32com.client
                import pythoncom
                
                # 初始化 COM（在后台线程中需要）
                pythoncom.CoInitialize()
                logger.info(f"🔧 COM 初始化完成")
                
                try:
                    shell = win32com.client.Dispatch("Shell.Application")
                    windows = shell.Windows()
                    
                    logger.info(f"🔍 找到 {windows.Count} 个 Explorer 窗口")
                    
                    target_hwnd = None
                    target_path_normalized = os.path.normpath(target_path).lower()
                    logger.info(f"🎯 目标路径: {target_path_normalized}")
                    
                    # 枚举所有 Explorer 窗口，查找匹配的路径
                    for i, window in enumerate(windows):
                        try:
                            # 获取窗口的当前文件夹路径
                            location_url = window.LocationURL
                            logger.debug(f"窗口 {i}: LocationURL = {location_url}")
                            
                            if location_url:
                                # 转换 file:/// URL 为本地路径
                                from urllib.parse import unquote, urlparse
                                parsed = urlparse(location_url)
                                if parsed.scheme == 'file':
                                    # 处理 file:///C:/path 格式
                                    window_path = unquote(parsed.path)
                                    # 移除开头的 / (Windows 路径)
                                    if window_path.startswith('/') and len(window_path) > 2 and window_path[2] == ':':
                                        window_path = window_path[1:]
                                    window_path_normalized = os.path.normpath(window_path).lower()
                                    
                                    logger.info(f"窗口 {i} 路径: {window_path_normalized}")
                                    
                                    if window_path_normalized == target_path_normalized:
                                        target_hwnd = window.HWND
                                        logger.info(f"✓ 找到匹配窗口: hwnd={target_hwnd}")
                                        break
                        except Exception as e:
                            logger.debug(f"检查窗口 {i} 时出错: {e}")
                            continue
                    
                    if target_hwnd:
                        user32 = ctypes.windll.user32
                        
                        # 获取前台窗口的线程 ID
                        foreground_hwnd = user32.GetForegroundWindow()
                        foreground_thread = user32.GetWindowThreadProcessId(foreground_hwnd, None)
                        
                        # 获取目标窗口的线程 ID
                        target_thread = user32.GetWindowThreadProcessId(target_hwnd, None)
                        
                        logger.info(f"前台线程: {foreground_thread}, 目标线程: {target_thread}")
                        
                        # 附加线程输入队列（绕过 Windows 前台限制的关键）
                        if foreground_thread != target_thread:
                            attach_result = user32.AttachThreadInput(foreground_thread, target_thread, True)
                            logger.info(f"AttachThreadInput: {attach_result}")
                        
                        # 显示并激活窗口
                        user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
                        user32.BringWindowToTop(target_hwnd)
                        fg_result = user32.SetForegroundWindow(target_hwnd)
                        
                        logger.info(f"SetForegroundWindow: {fg_result}")
                        
                        # 分离线程输入队列
                        if foreground_thread != target_thread:
                            user32.AttachThreadInput(foreground_thread, target_thread, False)
                        
                        logger.info(f"✅ 窗口已激活: hwnd={target_hwnd}")
                    else:
                        logger.warning(f"⚠️ 未找到匹配窗口，文件夹可能已在后台打开: {target_path}")
                        
                finally:
                    pythoncom.CoUninitialize()
                    
            except ImportError:
                # 如果没有 pywin32，回退到简单方法
                logger.warning("pywin32 未安装，使用回退方案")
                user32 = ctypes.windll.user32
                folder_name = os.path.basename(target_path)
                hwnd = user32.FindWindowW(None, folder_name)
                if hwnd:
                    user32.ShowWindow(hwnd, 9)
                    user32.SetForegroundWindow(hwnd)
            except Exception as e:
                logger.warning(f"激活窗口时出错（文件夹已打开）: {e}")
                
        elif system == "Darwin":
            # macOS: 使用 AppleScript 打开文件夹并激活 Finder 窗口
            try:
                # 打开文件夹并激活 Finder
                applescript = f'''
                tell application "Finder"
                    activate
                    open POSIX file "{target_path}"
                    -- 将新打开的窗口带到最前
                    set frontmost to true
                end tell
                '''
                subprocess.run(['osascript', '-e', applescript], check=True, capture_output=True)
                logger.info(f"✅ macOS Finder 窗口已激活: {target_path}")
            except subprocess.CalledProcessError as e:
                # 回退到简单的 open 命令
                logger.warning(f"AppleScript 执行失败，回退到 open 命令: {e}")
                subprocess.Popen(['open', target_path])
            except Exception as e:
                logger.warning(f"macOS 打开文件夹出错: {e}")
                subprocess.Popen(['open', target_path])
        else:
            # Linux: 使用 xdg-open，并尝试使用 wmctrl 激活窗口
            subprocess.Popen(['xdg-open', target_path])
            try:
                # 尝试使用 wmctrl 激活文件管理器窗口（如果已安装）
                import shutil
                if shutil.which('wmctrl'):
                    import time
                    time.sleep(0.5)
                    folder_name = os.path.basename(target_path)
                    subprocess.run(['wmctrl', '-a', folder_name], capture_output=True)
            except Exception:
                pass  # wmctrl 不可用时静默失败
        
        logger.info(f"📂 打开文件夹: {target_path}")
        return {"message": "success", "path": target_path}
    except Exception as e:
        logger.error(f"打开文件夹失败: {e}")
        raise HTTPException(status_code=500, detail=f"打开文件夹失败: {str(e)}")


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


@app.get("/api/reports/subjects")
async def get_report_subjects():
    """
    获取可选的嫌疑人列表
    
    【数据复用铁律】从 analysis_cache 中已计算的 profiles 读取，不重新扫描文件
    """
    import report_service
    
    try:
        builder = report_service.load_report_builder(_current_config.get("outputDirectory", "./output"))
        
        if builder is None:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "无可用分析数据，请先运行分析", "subjects": []}
            )
        
        subjects = builder.get_available_subjects()
        
        return {
            "success": True,
            "subjects": subjects,
            "personCount": len([s for s in subjects if s.get("type") == "person"]),
            "companyCount": len([s for s in subjects if s.get("type") == "company"])
        }
    except Exception as e:
        logger.error(f"获取嫌疑人列表失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "subjects": []}
        )


@app.get("/api/reports/available-sections")
async def get_available_sections():
    """获取可用的报告模块列表"""
    return {
        "sections": [
            {"id": "summary", "name": "资金概览", "description": "核心统计指标汇总"},
            {"id": "assets", "name": "个人资产", "description": "各人员资产情况表"},
            {"id": "risks", "name": "可疑交易", "description": "疑点交易、资金闭环、现金伴随"}
        ],
        "formats": ["html", "json"]
    }


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

@app.head("/api/reports/{filename}")
async def check_report_exists(filename: str):
    """检查报告文件是否存在 (HEAD 请求)"""
    filepath = os.path.join("./output/analysis_results", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件不存在")
    return Response(status_code=200)


@app.get("/api/analysis/graph-data")
async def get_graph_data():
    """获取资金流向图谱数据（用于前端 Vis.js 可视化）
    
    【铁律实现】数据来源：
    1. 优先使用分析时预计算的缓存数据 (graphData)
    2. 兜底从 cleaned_data 成品目录读取，严禁读取原始 data/ 目录
    """
    try:
        # 检查是否有分析结果
        if analysis_state.results is None:
            raise HTTPException(status_code=404, detail="暂无分析结果，请先运行分析")
        
        # 【优化】直接返回预计算的图谱缓存数据
        graph_cache = analysis_state.results.get("graphData")
        if graph_cache:
            logger.info(f"[graph-data] 使用缓存数据: {len(graph_cache.get('nodes', []))} 节点")
            return {"message": "success", "data": graph_cache}
        
        # 【铁律修复】兜底：从 cleaned_data 成品目录读取，而非原始目录
        logger.warning("[graph-data] 缓存未命中，从 cleaned_data 成品目录读取...")
        
        # 从成品目录加载数据
        cleaned_data, metadata = _load_cleaned_data()
        all_persons = metadata["persons"]
        all_companies = metadata["companies"]
        
        if not cleaned_data:
            raise HTTPException(status_code=404, detail="cleaned_data 目录为空，请先运行后端分析生成成品数据")
        
        # 计算资金流向统计
        flow_stats = flow_visualizer._calculate_flow_stats(cleaned_data, all_persons)
        nodes, edges, edge_stats = flow_visualizer._prepare_graph_data(
            flow_stats, all_persons, all_companies
        )
        
        # 使用配置的采样限制
        max_nodes, max_edges = config.GRAPH_MAX_NODES, config.GRAPH_MAX_EDGES
        sorted_nodes = sorted(nodes, key=lambda x: x.get('size', 0), reverse=True)
        sampled_nodes = sorted_nodes[:max_nodes]
        sampled_node_ids = {node['id'] for node in sampled_nodes}
        
        sampled_edges = [e for e in edges if e['from'] in sampled_node_ids and e['to'] in sampled_node_ids]
        sampled_edges.sort(key=lambda x: x.get('value', 0), reverse=True)
        sampled_edges = sampled_edges[:max_edges]
        
        # 释放内存
        del cleaned_data, flow_stats
        import gc
        gc.collect()
        
        loan_results = analysis_state.results.get("analysisResults", {}).get("loan", {})
        income_results = analysis_state.results.get("analysisResults", {}).get("income", {})
        
        return {
            "message": "success",
            "source": "cleaned_data",  # 标记数据来源
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
                    "highRiskCount": len(income_results.get("high_risk", [])),
                    "mediumRiskCount": len(income_results.get("medium_risk", [])),
                    "loanPairCount": len(loan_results.get("bidirectional_flows", [])),
                    "noRepayCount": 0,
                    "coreEdgeCount": edge_stats.get("core", 0),
                    "companyEdgeCount": edge_stats.get("company", 0),
                    "otherEdgeCount": edge_stats.get("other", 0),
                },
                "report": {
                    "loan_pairs": loan_results.get("bidirectional_flows", []),
                    "no_repayment_loans": loan_results.get("no_repayment_loans", []),
                    "high_risk_income": income_results.get("high_risk", []),
                    "online_loans": loan_results.get("online_loan_platforms", [])
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
        
        # 更新全局配置（用于缓存验证）
        global _current_config
        _current_config["inputDirectory"] = data_dir
        _current_config["outputDirectory"] = output_dir
        
        # 更新配置
        config.LARGE_CASH_THRESHOLD = analysis_config.cashThreshold
        
        # 阶段 1: 扫描文件
        analysis_state.update(progress=5, phase="扫描数据目录...")
        logger.info(f"扫描数据目录: {data_dir}")
        
        categorized_files = file_categorizer.categorize_files(data_dir)
        persons = list(categorized_files['persons'].keys())
        companies = list(categorized_files['companies'].keys())
        
        logger.info(f"发现 {len(persons)} 个个人, {len(companies)} 个企业")
        
        # 阶段 2: 数据清洗（【铁律】保存到 cleaned_data 目录作为成品数据）
        analysis_state.update(progress=15, phase="数据清洗与标准化...")
        logger.info("开始数据清洗...")
        
        cleaned_data = {}
        output_dirs = create_output_directories(output_dir)
        
        total_entities = len(persons) + len(companies)
        
        # 清洗个人数据并保存到 cleaned_data/个人/
        for i, p in enumerate(persons):
            p_files = categorized_files['persons'].get(p, [])
            if p_files:
                df, _ = data_cleaner.clean_and_merge_files(p_files, p)
                if df is not None and not df.empty:
                    cleaned_data[p] = df
                    # 【铁律】保存清洗结果到成品目录
                    output_path = os.path.join(output_dirs['cleaned_persons'], f'{p}_合并流水.xlsx')
                    try:
                        data_cleaner.save_formatted_excel(df, output_path)
                        logger.info(f"已保存清洗数据: {p} -> {output_path}")
                    except Exception as e:
                        logger.warning(f"保存清洗数据失败 {p}: {e}")
            
            progress = 15 + int(25 * (i + 1) / total_entities)
            analysis_state.update(progress=progress)
        
        # 清洗公司数据并保存到 cleaned_data/公司/
        for i, c in enumerate(companies):
            c_files = categorized_files['companies'].get(c, [])
            if c_files:
                df, _ = data_cleaner.clean_and_merge_files(c_files, c)
                if df is not None and not df.empty:
                    cleaned_data[c] = df
                    # 【铁律】保存清洗结果到成品目录
                    output_path = os.path.join(output_dirs['cleaned_companies'], f'{c}_合并流水.xlsx')
                    try:
                        data_cleaner.save_formatted_excel(df, output_path)
                        logger.info(f"已保存清洗数据: {c} -> {output_path}")
                    except Exception as e:
                        logger.warning(f"保存清洗数据失败 {c}: {e}")
            
            progress = 15 + int(25 * (len(persons) + i + 1) / total_entities)
            analysis_state.update(progress=progress)
        
        logger.info(f"清洗完成，共 {len(cleaned_data)} 个实体数据已保存到 cleaned_data 目录")
        
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
        
        # 【优化】预计算图谱数据并缓存，避免 API 调用时重新读取磁盘
        logger.info("预计算图谱数据缓存...")
        graph_data_cache = None
        try:
            flow_stats = flow_visualizer._calculate_flow_stats(cleaned_data, all_persons)
            nodes, edges, edge_stats = flow_visualizer._prepare_graph_data(
                flow_stats, all_persons, all_companies
            )
            
            # 【P1修复】使用配置的采样限制
            max_nodes, max_edges = config.GRAPH_MAX_NODES, config.GRAPH_MAX_EDGES
            sorted_nodes = sorted(nodes, key=lambda x: x.get('size', 0), reverse=True)
            sampled_nodes = sorted_nodes[:max_nodes]
            sampled_node_ids = {node['id'] for node in sampled_nodes}
            
            sampled_edges = [e for e in edges if e['from'] in sampled_node_ids and e['to'] in sampled_node_ids]
            sampled_edges.sort(key=lambda x: x.get('value', 0), reverse=True)
            sampled_edges = sampled_edges[:max_edges]
            
            loan_results = analysis_results.get("loan", {})
            income_results = analysis_results.get("income", {})
            
            graph_data_cache = {
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
                    "highRiskCount": len(income_results.get("high_risk", [])),
                    "mediumRiskCount": len(income_results.get("medium_risk", [])),
                    "loanPairCount": len(loan_results.get("bidirectional_flows", [])),
                    "noRepayCount": 0,
                    "coreEdgeCount": edge_stats.get("core", 0),
                    "companyEdgeCount": edge_stats.get("company", 0),
                    "otherEdgeCount": edge_stats.get("other", 0),
                },
                "report": {
                    "loan_pairs": loan_results.get("bidirectional_flows", []),
                    "no_repayment_loans": loan_results.get("no_repayment_loans", []),
                    "high_risk_income": income_results.get("high_risk", []),
                    "online_loans": loan_results.get("online_loan_platforms", [])
                }
            }
            logger.info(f"图谱缓存生成完成: {len(sampled_nodes)} 节点, {len(sampled_edges)} 边")
        except Exception as e:
            logger.warning(f"图谱缓存生成失败: {e}，API将使用实时计算")
        
        # 保存结果（包含图谱缓存）
        analysis_state.results = {
            "persons": all_persons,
            "companies": all_companies,
            "profiles": serialize_profiles(profiles),
            "suspicions": serialize_suspicions(enhanced_suspicions),
            "analysisResults": serialize_analysis_results(analysis_results),
            "graphData": graph_data_cache,  # 新增：图谱数据缓存
        }
        
        # 【铁律核心】将分析结果持久化到 analysis_cache 目录
        # 这样 /api/results 可以从文件读取，不依赖内存
        logger.info("📦 正在保存分析缓存到 analysis_cache 目录...")
        _save_analysis_cache(analysis_state.results, output_dir)
        
        # 将结果保存到磁盘缓存（旧版缓存，保持向后兼容）
        _save_cached_results(analysis_state.results, data_dir, output_dir)
        
        # 【P2 内存优化】分析完成后释放大对象，减少内存占用
        logger.info("正在释放分析过程中的临时数据...")
        try:
            # 删除 cleaned_data，这是最大的内存占用者
            del cleaned_data
            # 删除其他不再需要的中间结果
            del profiles
            del suspicions
            del enhanced_suspicions
            del analysis_results
            
            # 【P2修复】使用 Pythonic 的方式删除可能存在的变量
            for var_name in ['flow_stats', 'nodes', 'edges']:
                if var_name in locals():
                    del locals()[var_name]
            
            # 强制垃圾回收
            import gc
            gc.collect()
            logger.info("✓ 内存清理完成")
        except Exception as e:
            logger.warning(f"内存清理时出现警告: {e}")
        
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
    """创建输出目录结构（与 main.py 保持一致）"""
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

def _enhance_suspicions_with_analysis(suspicions: Dict, analysis_results: Dict) -> Dict:
    """
    将分析模块结果整合到 suspicions 中（使前端能显示更多风险数据）
    
    【重要修改】时序分析结果（资金突变、延迟转账、周期收入）属于系统检测的异常，
    不应混入"核心人员往来"（direct_transfers），它们是单个人的资金异常，不是转账记录。
    
    主要整合：
    - timeSeries.sudden_changes -> time_series_alerts（新增）
    - timeSeries.delayed_transfers -> time_series_alerts（新增）
    - timeSeries.periodic_income -> time_series_alerts（新增）
    - relatedParty.direct_flows -> direct_transfers（真正的关联方往来）
    """
    enhanced = suspicions.copy()
    
    # 初始化时序告警列表（新增独立列表，不再混入 direct_transfers）
    if "time_series_alerts" not in enhanced:
        enhanced["time_series_alerts"] = []
    
    # 1. 时序分析结果 -> 独立列表 time_series_alerts（不再混入核心人员往来）
    ts_results = analysis_results.get("timeSeries", {})
    
    # 资金突变（单个人的收入异常，不是转账记录）
    sudden_changes = ts_results.get("sudden_changes", [])
    for change in sudden_changes:
        if isinstance(change, dict):
            enhanced["time_series_alerts"].append({
                "entity": change.get("entity", change.get("person", "")),
                "alert_type": "资金突变",
                "date": change.get("date", change.get("change_date", "")),
                "amount": change.get("amount", change.get("income_change", 0)),
                "description": change.get("description", f"资金突变: {change.get('change_type', '未知')}"),
                "risk_level": change.get("risk_level", "high")
            })
    
    # 延迟转账检测
    delayed_transfers = ts_results.get("delayed_transfers", [])
    for dt in delayed_transfers:
        if isinstance(dt, dict):
            enhanced["time_series_alerts"].append({
                "entity": dt.get("source_person", dt.get("person", "")),
                "counterparty": dt.get("target_person", ""),
                "alert_type": "延迟转账",
                "date": dt.get("source_date", dt.get("date", "")),
                "amount": dt.get("amount", 0),
                "description": dt.get("description", f"延迟{dt.get('delay_days', 0)}天转账"),
                "risk_level": dt.get("risk_level", "medium")
            })
    
    # 周期性收入检测
    periodic_income = ts_results.get("periodic_income", [])
    for pi in periodic_income:
        if isinstance(pi, dict):
            enhanced["time_series_alerts"].append({
                "entity": pi.get("entity", pi.get("person", "")),
                "counterparty": pi.get("counterparty", ""),
                "alert_type": "周期收入",
                "date": pi.get("last_date", pi.get("date", "")),
                "amount": pi.get("avg_amount", pi.get("amount", 0)),
                "description": pi.get("description", f"周期性收入: {pi.get('period_type', '未知')}"),
                "risk_level": pi.get("risk_level", "low")
            })
    
    # 2. 关联方往来 -> 这才是真正的"核心人员往来"
    rp_results = analysis_results.get("relatedParty", {})
    direct_flows = rp_results.get("direct_flows", [])
    for flow in direct_flows:
        if isinstance(flow, dict):
            from_person = flow.get("from_person", flow.get("person", ""))
            to_person = flow.get("to_person", flow.get("counterparty", ""))
            # 只有当 from 和 to 都有明确值时，才是真正的核心人员往来
            if from_person and to_person:
                enhanced["direct_transfers"].append({
                    "person": from_person,
                    "company": to_person,
                    "date": flow.get("date", ""),
                    "amount": flow.get("amount", 0),
                    "direction": "关联往来",
                    "description": flow.get("description", "关联方资金往来"),
                    "risk_level": flow.get("risk_level", "medium")
                })
    
    logger.info(f"风险整合: 核心人员往来{len(enhanced.get('direct_transfers', []))}条, "
               f"时序告警{len(enhanced.get('time_series_alerts', []))}条 "
               f"(突变{len(sudden_changes)}+延迟{len(delayed_transfers)}+周期{len(periodic_income)})")
    
    return enhanced

def serialize_profiles(profiles: Dict) -> Dict:
    """
    序列化画像数据为 JSON 格式（增强版）
    
    新增字段：
    - cashTotal: 现金交易总额（取现+存现）
    - thirdPartyTotal: 第三方支付交易总额
    - wealthTotal: 理财产品交易总额
    - maxTransaction: 最大单笔交易金额
    - salaryRatio: 工资收入占比
    """
    result = {}
    for entity, profile in profiles.items():
        if not profile or profile.get("has_data") == False:
            result[entity] = {
                "entityName": entity,
                "totalIncome": 0.0,
                "totalExpense": 0.0,
                "transactionCount": 0,
                "cashTotal": 0.0,
                "thirdPartyTotal": 0.0,
                "wealthTotal": 0.0,
                "maxTransaction": 0.0,
                "salaryRatio": 0.0,
            }
            continue
        
        # 从 summary 或 income_structure 中获取数据
        summary = profile.get("summary", {})
        income_structure = profile.get("income_structure", {})
        fund_flow = profile.get("fund_flow", {})
        wealth_management = profile.get("wealth_management", {})
        
        # 优先从 summary 获取，如果没有则从 income_structure 获取
        total_income = summary.get("total_income") or income_structure.get("total_income", 0)
        total_expense = summary.get("total_expense") or income_structure.get("total_expense", 0)
        transaction_count = summary.get("transaction_count", 0)
        
        # 现金交易总额（取现+存现）
        cash_income = fund_flow.get("cash_income", 0) or 0
        cash_expense = fund_flow.get("cash_expense", 0) or 0
        cash_total = cash_income + cash_expense
        
        # 第三方支付交易总额（微信/支付宝等）
        third_party_income = fund_flow.get("third_party_income", 0) or 0
        third_party_expense = fund_flow.get("third_party_expense", 0) or 0
        third_party_total = third_party_income + third_party_expense
        
        # 理财产品交易总额
        wealth_purchase = wealth_management.get("wealth_purchase", 0) or 0
        wealth_redemption = wealth_management.get("wealth_redemption", 0) or 0
        wealth_total = wealth_purchase + wealth_redemption
        
        # 最大单笔交易
        max_transaction = summary.get("max_transaction", 0) or summary.get("max_single_transaction", 0) or 0
        
        # 工资收入：优先从 income_structure 获取
        salary_income = income_structure.get("salary_income", 0) or 0
        salary_ratio = income_structure.get("salary_ratio", 0) or summary.get("salary_ratio", 0) or 0
        salary_total = float(salary_income) if salary_income else (float(total_income) * float(salary_ratio) if total_income and salary_ratio else 0)
        
        result[entity] = {
            "entityName": entity,
            "totalIncome": float(total_income) if total_income else 0.0,
            "totalExpense": float(total_expense) if total_expense else 0.0,
            "transactionCount": int(transaction_count) if transaction_count else 0,
            # 新增审计关键字段
            "cashTotal": float(cash_total),
            "cashIncome": float(cash_income),  # 存现
            "cashExpense": float(cash_expense),  # 取现
            "cashIncomeCount": fund_flow.get("cash_income_count", 0) or 0,
            "cashExpenseCount": fund_flow.get("cash_expense_count", 0) or 0,
            "cashTransactions": [
                {
                    "date": str(tx.get("日期", ""))[:19] if tx.get("日期") else "",
                    "amount": float(tx.get("金额", 0)),
                    "description": str(tx.get("摘要", "")),
                    "counterparty": str(tx.get("对手方", "")),
                    "type": str(tx.get("类型", "")),  # 取现 or 存现
                    # 【溯源铁律】原始文件和行号
                    "source_file": str(tx.get("source_file", "")),
                    "source_row_index": tx.get("source_row_index", None)
                }
                for tx in fund_flow.get("cash_transactions", [])
            ],
            "thirdPartyTotal": float(third_party_total),
            "wealthTotal": float(wealth_total),
            "maxTransaction": float(max_transaction),
            "salaryRatio": float(salary_ratio),
            "salaryTotal": float(salary_total),  # 工资收入金额
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
        "timeSeriesAlerts": [],  # 新增：时序分析告警（资金突变、延迟转账等）
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
            # 新增审计关键字段
            "direction": str(direction),
            "bank": str(tx.get("bank", "")),
            "sourceFile": str(tx.get("source_file", "")),
            "sourceRowIndex": tx.get("source_row_index", None),  # 【溯源铁律】添加行号
            "riskLevel": str(tx.get("risk_level", "medium")),
            "riskReason": str(tx.get("risk_reason", "")),
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
            # 新增审计关键字段
            "timeDiff": float(collision.get("time_diff_hours", 0)),
            "amountDiff": float(collision.get("amount_diff", 0)),
            "amountDiffRatio": float(collision.get("amount_diff_ratio", 0)),
            "withdrawalBank": str(collision.get("withdrawal_bank", "")),
            "depositBank": str(collision.get("deposit_bank", "")),
            "riskLevel": str(collision.get("risk_level", "medium")),
            "riskReason": str(collision.get("risk_reason", "")),
            # 【溯源铁律】原始文件和行号
            "withdrawalSourceFile": str(collision.get("withdrawal_source", "")),
            "depositSourceFile": str(collision.get("deposit_source", "")),
            "withdrawalRowIndex": collision.get("withdrawal_row", None),
            "depositRowIndex": collision.get("deposit_row", None),
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
    
    # 转换时序分析告警 (新增)
    for alert in suspicions.get("time_series_alerts", []):
        if isinstance(alert, dict):
            result["timeSeriesAlerts"].append({
                "entity": str(alert.get("entity", "")),
                "counterparty": str(alert.get("counterparty", "")),
                "alertType": str(alert.get("alert_type", "")),
                "date": str(alert.get("date", "")),
                "amount": float(alert.get("amount", 0)),
                "description": str(alert.get("description", "")),
                "riskLevel": str(alert.get("risk_level", "medium")),
                # 【溯源铁律】原始文件和行号
                "sourceFile": str(alert.get("source_file", "")),
                "sourceRowIndex": alert.get("source_row_index", None),
            })
    
    return result

def serialize_analysis_results(analysis_results: Dict) -> Dict:
    """
    序列化分析结果为前端期望的 JSON 格式
    
    关键修复：将后端分析器返回的各个子列表（如 bidirectional_flows, online_loan_platforms）
    合并到 details 数组中，并添加 _type 字段供前端筛选使用。
    """
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
    
    # ========== 特殊处理 loan 模块 ==========
    # 后端 loan_analyzer 返回的是多个子列表，需要合并到 details
    if "loan" in analysis_results and isinstance(analysis_results["loan"], dict):
        loan_data = analysis_results["loan"]
        
        # 复制 summary
        if "summary" in loan_data:
            default["loan"]["summary"] = {**default["loan"]["summary"], **_convert_dict(loan_data["summary"])}
        
        # 合并各类借贷详情到 details，添加 _type 字段
        loan_details = []
        
        # 1. 双向往来 (bidirectional_flows)
        for item in loan_data.get("bidirectional_flows", []):
            loan_details.append({**_convert_value(item), "_type": "bidirectional"})
        
        # 2. 网贷平台交易 (online_loan_platforms)
        for item in loan_data.get("online_loan_platforms", []):
            loan_details.append({**_convert_value(item), "_type": "online_loan"})
        
        # 3. 规律还款 (regular_repayments)
        for item in loan_data.get("regular_repayments", []):
            loan_details.append({**_convert_value(item), "_type": "regular_repayment"})
        
        # 4. 借贷配对 (loan_pairs)
        for item in loan_data.get("loan_pairs", []):
            loan_details.append({**_convert_value(item), "_type": "loan_pair"})
        
        # 5. 无还款借贷 (no_repayment_loans)
        for item in loan_data.get("no_repayment_loans", []):
            loan_details.append({**_convert_value(item), "_type": "no_repayment"})
        
        # 6. 异常利息 (abnormal_interest)
        for item in loan_data.get("abnormal_interest", []):
            loan_details.append({**_convert_value(item), "_type": "abnormal_interest"})
        
        default["loan"]["details"] = loan_details
        logging.info(f"[Serialize] loan.details 已合并 {len(loan_details)} 条记录")
    
    # ========== 特殊处理 income 模块 ==========
    # 后端 income_analyzer 返回的是多个子列表，需要合并到 details
    if "income" in analysis_results and isinstance(analysis_results["income"], dict):
        income_data = analysis_results["income"]
        
        # 复制 summary
        if "summary" in income_data:
            default["income"]["summary"] = {**default["income"]["summary"], **_convert_dict(income_data["summary"])}
        
        # 合并各类收入详情到 details，添加 _type 字段
        income_details = []
        
        # 1. 规律性非工资收入 (regular_non_salary)
        for item in income_data.get("regular_non_salary", []):
            income_details.append({**_convert_value(item), "_type": "regular_non_salary"})
        
        # 2. 个人大额转入 (large_individual_income)
        for item in income_data.get("large_individual_income", []):
            income_details.append({**_convert_value(item), "_type": "large_individual"})
        
        # 3. 来源不明收入 (unknown_source_income)
        for item in income_data.get("unknown_source_income", []):
            income_details.append({**_convert_value(item), "_type": "unknown_source"})
        
        # 4. 大额单笔收入 (large_single_income)
        for item in income_data.get("large_single_income", []):
            income_details.append({**_convert_value(item), "_type": "large_single"})
        
        # 5. 同源多次收入 (same_source_multi)
        for item in income_data.get("same_source_multi", []):
            income_details.append({**_convert_value(item), "_type": "same_source_multi"})
        
        # 6. 疑似分期受贿 (potential_bribe_installment)
        for item in income_data.get("potential_bribe_installment", []):
            income_details.append({**_convert_value(item), "_type": "bribe_installment"})
        
        # 7. 高风险收入 (high_risk)
        for item in income_data.get("high_risk", []):
            income_details.append({**_convert_value(item), "_type": "high_risk"})
        
        # 8. 中风险收入 (medium_risk)
        for item in income_data.get("medium_risk", []):
            income_details.append({**_convert_value(item), "_type": "medium_risk"})
        
        default["income"]["details"] = income_details
        logging.info(f"[Serialize] income.details 已合并 {len(income_details)} 条记录")
    
    # ========== 处理其他模块（使用通用逻辑）==========
    for key, value in analysis_results.items():
        if key in ["loan", "income"]:
            continue  # 已单独处理
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

# ==================== 报告生成 API (Protocol Omega - Phase 1) ====================

from jinja2 import Environment, FileSystemLoader, select_autoescape

# 初始化 Jinja2 环境
_jinja_env = None

def _get_jinja_env():
    """获取 Jinja2 模板环境（延迟初始化）"""
    global _jinja_env
    if _jinja_env is None:
        templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
        _jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
    return _jinja_env


class ReportGenerateRequest(BaseModel):
    """报告生成请求 - Protocol Omega Phase 1"""
    sections: List[str] = ["summary", "suspicious_transactions"]
    format: str = "html"  # html, json
    case_name: str = "初查报告"
    subjects: Optional[List[str]] = None  # 选中的嫌疑人，None 表示全选
    doc_number: Optional[str] = None  # 文号，如 "国监查 [2026] 第 12345 号"
    thresholds: Optional[Dict[str, int]] = None  # 阈值配置，如 {"large_transfer": 50000, "large_cash": 50000}


@app.post("/api/reports/generate")
async def generate_report(request: ReportGenerateRequest):
    """
    动态生成审计报告 (Protocol Omega)
    
    支持按需选择模块，动态拼接 Jinja2 模板生成 HTML 报告。
    
    请求体:
    {
        "sections": ["summary", "risks", "assets"],
        "format": "html",
        "case_name": "案件名称"
    }
    
    可用 sections:
    - summary: 资金概览
    - assets: 个人资产
    - risks: 可疑交易 (包含资金闭环、现金时空伴随)
    """
    try:
        # 1. 加载分析结果
        cached_results, status_msg = _load_analysis_cache()
        
        if cached_results is None:
            # 尝试使用内存数据
            if analysis_state.results is not None:
                cached_results = analysis_state.results
            else:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "无可用分析数据，请先运行分析"}
                )
        
        # 2. 【Protocol Omega】使用 report_service 生成公文格式初查报告
        import report_service
        
        # 如果指定了 subjects，使用新的报告服务生成初查报告
        if request.subjects is not None or "official" in request.sections:
            builder = report_service.ReportDataBuilder(cached_results)
            
            # 确定要分析的嫌疑人
            subjects = request.subjects or cached_results.get("persons", [])
            
            if request.format == "html":
                html_report = builder.generate_html_report(
                    subjects=subjects,
                    case_name=request.case_name,
                    doc_number=request.doc_number,
                    include_assets="assets" in request.sections,
                    include_income="summary" in request.sections,
                    include_loan="risks" in request.sections,
                )
                
                # 对中文文件名进行 RFC 5987 编码
                import urllib.parse
                encoded_filename = urllib.parse.quote(f"{request.case_name}.html")
                
                return Response(
                    content=html_report,
                    media_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"}
                )
            else:
                # JSON 格式：返回每个嫌疑人的分析数据
                subjects_data = [builder.build_person_report(s) for s in subjects]
                return JSONResponse(content={
                    "success": True,
                    "format": "json",
                    "case_name": request.case_name,
                    "subjects": subjects_data
                })
        
        # 3. 旧版报告生成逻辑（兼容）
        from datetime import datetime
        import report_schema
        
        report_data = {
            "metadata": {
                "case_name": request.case_name,
                "generated_at": datetime.now().isoformat(),
                "version": "3.0.0",
                "core_persons": cached_results.get("persons", []),
                "companies": cached_results.get("companies", [])
            },
            "modules": {}
        }
        
        # 3. 按请求的 sections 填充模块数据
        profiles = cached_results.get("profiles", {})
        suspicions = cached_results.get("suspicions", {})
        analysis_results = cached_results.get("analysisResults", {})
        
        # Summary 模块
        if "summary" in request.sections:
            total_income = 0
            total_expense = 0
            transaction_count = 0
            period_start = None
            period_end = None
            
            for entity, profile in profiles.items():
                if profile.get("has_data"):
                    summary = profile.get("summary", {})
                    total_income += summary.get("total_income", 0)
                    total_expense += summary.get("total_expense", 0)
                    transaction_count += summary.get("transaction_count", 0)
                    
                    date_range = summary.get("date_range", [])
                    if date_range and len(date_range) >= 2:
                        if date_range[0]:
                            start = str(date_range[0])[:10]
                            if period_start is None or start < period_start:
                                period_start = start
                        if date_range[1]:
                            end = str(date_range[1])[:10]
                            if period_end is None or end > period_end:
                                period_end = end
            
            report_data["modules"]["summary"] = {
                "total_income": total_income,
                "total_expense": total_expense,
                "net_flow": total_income - total_expense,
                "transaction_count": transaction_count,
                "high_risk_count": len(suspicions.get("direct_transfers", [])),
                "core_person_count": len(cached_results.get("persons", [])),
                "company_count": len(cached_results.get("companies", [])),
                "period_start": period_start or "",
                "period_end": period_end or ""
            }
        
        # Assets 模块
        if "assets" in request.sections:
            assets_data = []
            for entity, profile in profiles.items():
                if profile.get("has_data"):
                    summary = profile.get("summary", {})
                    wealth_mgmt = profile.get("wealth_management", {})
                    
                    assets_data.append({
                        "entity_name": entity,
                        "deposit_estimate": (summary.get("total_income", 0) - summary.get("total_expense", 0)) / 10000,
                        "wealth_holding": wealth_mgmt.get("estimated_holding", 0) / 10000,
                        "property_count": 0,  # 需要从 family_assets 获取
                        "property_value": 0,
                        "vehicle_count": 0,
                        "total_income": summary.get("total_income", 0),
                        "total_expense": summary.get("total_expense", 0)
                    })
            
            report_data["modules"]["personal_assets"] = {
                "data": assets_data,
                "columns": ["户名", "存款估算(万)", "理财持仓(万)", "房产套数", 
                           "房产价值(万)", "车辆数", "总收入", "总支出"]
            }
        
        # Risks 模块 (可疑交易)
        if "risks" in request.sections:
            # 直接转账
            suspicious_txs = []
            for tx in suspicions.get("direct_transfers", []):
                suspicious_txs.append({
                    "date": str(tx.get("date", ""))[:19] if tx.get("date") else "",
                    "entity": tx.get("person", ""),
                    "counterparty": tx.get("company", ""),
                    "amount": tx.get("amount", 0),
                    "direction": tx.get("direction", ""),
                    "description": tx.get("description", ""),
                    "risk_level": tx.get("risk_level", "low"),
                    "risk_reason": tx.get("description", "核心人员与涉案公司直接往来"),
                    "evidence_refs": tx.get("evidence_refs", {})
                })
            
            report_data["modules"]["suspicious_transactions"] = {
                "data": suspicious_txs,
                "reasoning": "系统自动筛查核心人员与涉案公司之间的直接资金往来。",
                "total_count": len(suspicious_txs),
                "high_risk_count": len([t for t in suspicious_txs if t.get("risk_level") == "high"]),
                "medium_risk_count": len([t for t in suspicious_txs if t.get("risk_level") == "medium"])
            }
            
            # 资金闭环
            if analysis_results.get("penetration", {}).get("fund_cycles"):
                cycles = analysis_results["penetration"]["fund_cycles"]
                report_data["modules"]["fund_cycles"] = {
                    "data": [{"cycle": c, "cycle_str": " → ".join(c), "length": len(c)} for c in cycles[:20]],
                    "total_count": len(cycles),
                    "reasoning": "资金闭环表明资金最终回流起点，是典型的洗钱或利益输送结构。"
                }
            
            # 现金时空伴随
            if suspicions.get("cash_collisions"):
                collisions = suspicions["cash_collisions"]
                report_data["modules"]["cash_collisions"] = {
                    "data": [{
                        "withdrawal_entity": c.get("withdrawal_entity", ""),
                        "deposit_entity": c.get("deposit_entity", ""),
                        "withdrawal_date": str(c.get("withdrawal_date", ""))[:19],
                        "deposit_date": str(c.get("deposit_date", ""))[:19],
                        "withdrawal_amount": c.get("withdrawal_amount", 0),
                        "deposit_amount": c.get("deposit_amount", 0),
                        "time_diff_hours": c.get("time_diff_hours", 0),
                        "risk_level": c.get("risk_level", "low"),
                        "risk_reason": c.get("risk_reason", "")
                    } for c in collisions[:20]],
                    "total_count": len(collisions),
                    "reasoning": "现金在短时间内从一方取出另一方存入，金额相近，可能是现金过账或洗钱。"
                }
        
        # 4. 根据格式生成输出
        if request.format == "json":
            return JSONResponse(content={
                "success": True,
                "format": "json",
                "data": report_data
            })
        
        elif request.format == "html":
            # 使用 Jinja2 渲染
            env = _get_jinja_env()
            
            # 动态选择模板
            html_parts = []
            
            # 渲染基础模板头部
            base_template = env.get_template("base_report.html")
            
            # 为每个请求的 section 渲染内容
            section_templates = {
                "summary": "summary.html",
                "assets": "assets.html",
                "risks": "risks.html"
            }
            
            content_html = ""
            for section in request.sections:
                template_name = section_templates.get(section)
                if template_name:
                    try:
                        section_template = env.get_template(template_name)
                        content_html += section_template.render(
                            metadata=report_data["metadata"],
                            modules=report_data["modules"]
                        )
                    except Exception as e:
                        logger.warning(f"模板渲染失败 {template_name}: {e}")
                        content_html += f"<p>模块 {section} 渲染失败: {e}</p>"
            
            # 渲染完整 HTML
            full_html = base_template.render(
                metadata=report_data["metadata"],
                modules=report_data["modules"]
            ).replace("{% block content %}{% endblock %}", content_html)
            
            # 对中文文件名进行 RFC 5987 编码
            import urllib.parse
            encoded_filename = urllib.parse.quote(f"{request.case_name}.html")
            
            return Response(
                content=full_html,
                media_type="text/html; charset=utf-8",
                headers={"Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"}
            )
        
        else:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"不支持的格式: {request.format}"}
            )
    
    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
