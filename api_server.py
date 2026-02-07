#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金穿透审计系统 - FastAPI 后端服务 (重构版)

🔄 数据流向优化:
  原始数据 → 清洗 → 外部数据提取 → 融合画像 → 全面分析 → 疑点检测 → 报告

关键改进:
  1. 外部数据提取前移到画像生成之前
  2. 画像包含完整的资产/出行信息
  3. 疑点检测有完整上下文
  4. 分析模块并行执行
"""

import asyncio
import sys
import warnings
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
import threading
import queue
import pandas as pd
import time

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    BackgroundTasks,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

# 导入核心模块
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

# 导入缓存管理器
from cache_manager import CacheManager
import time_series_analyzer
import clue_aggregator
import behavioral_profiler
import api_validators
import logging_config

# 导入外部数据提取器 (18个)
import pboc_account_extractor
import aml_analyzer
import company_info_extractor
import credit_report_extractor
import bank_account_info_extractor
import vehicle_extractor
import wealth_product_extractor
import securities_extractor
import asset_extractor
import insurance_extractor
import immigration_extractor
import hotel_extractor
import cohabitation_extractor
import railway_extractor
import flight_extractor

# 导入辅助模块
import family_assets_helper
import family_finance

# 导入报告构建器（v3.0 新架构）
from investigation_report_builder import (
    InvestigationReportBuilder,
    load_investigation_report_builder,
)
from report_config.primary_targets_service import PrimaryTargetsService
from specialized_reports import SpecializedReportGenerator

# ==================== Windows asyncio 兼容性修复 ====================
if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncio")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# ====================================================================


# ==================== 全局状态 ====================
class AnalysisState:
    def __init__(self):
        self.status = "idle"
        self.progress = 0
        self.phase = ""
        self.start_time = None
        self.end_time = None
        self.results = None
        self.error = None
        self._lock = threading.Lock()

    def update(self, status=None, progress=None, phase=None, error=None):
        with self._lock:
            if status is not None:
                self.status = status
            if progress is not None:
                self.progress = progress
            if phase is not None:
                self.phase = phase
            if error is not None:
                self.error = error

    def to_dict(self):
        with self._lock:
            return {
                "status": self.status,
                "progress": self.progress,
                "phase": self.phase,
                "startTime": self.start_time.isoformat() if self.start_time else None,
                "endTime": self.end_time.isoformat() if self.end_time else None,
                "error": self.error,
            }


analysis_state = AnalysisState()
_current_config = {}
_ws_connections = set()
_log_queue = queue.Queue()  # 日志队列，用于 WebSocket 广播
_cache_manager: Optional[CacheManager] = None  # 缓存管理器（懒加载）


def _get_current_time_str() -> str:
    """获取当前时间字符串 HH:MM:SS"""
    now = datetime.now()
    return f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}"


def _get_cache_manager() -> CacheManager:
    """获取或创建缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        # 从全局配置获取缓存目录
        cache_dir = _current_config.get("outputDirectory", "output")
        cache_dir = os.path.join(cache_dir, "analysis_cache")
        _cache_manager = CacheManager(cache_dir)
    return _cache_manager


class WebSocketLogHandler(logging.Handler):
    """
    自定义日志处理器，将所有 Python 日志推送到 WebSocket 队列
    这样前端可以看到和终端一样丰富的日志信息
    """

    # 需要过滤的日志源（避免推送过多无用日志）
    EXCLUDED_LOGGERS = {
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "websockets",
        "asyncio",
    }

    def emit(self, record):
        try:
            # 过滤掉 uvicorn 等框架日志
            if record.name in self.EXCLUDED_LOGGERS:
                return

            # 格式化日志消息
            msg = self.format(record)
            # 移除重复的时间戳前缀（如果有）
            if " - " in msg and msg.startswith("20"):
                # 保留模块名和消息部分
                parts = msg.split(" - ", 2)
                if len(parts) >= 3:
                    msg = f"[{parts[1]}] {parts[2]}"
                elif len(parts) >= 2:
                    msg = f"[{parts[0]}] {parts[1]}"

            level = record.levelname
            log_entry = {"time": _get_current_time_str(), "level": level, "msg": msg}
            _log_queue.put({"type": "log", "data": log_entry})
        except Exception:
            pass  # 避免日志处理器本身抛出异常


# 设置 WebSocket 日志处理器
_ws_handler = WebSocketLogHandler()
_ws_handler.setLevel(logging.INFO)
_ws_handler.setFormatter(logging.Formatter("%(name)s - %(message)s"))

# 添加到根日志器，捕获所有模块的日志
logging.getLogger().addHandler(_ws_handler)


def broadcast_log(level: str, msg: str):
    """
    向 WebSocket 客户端广播日志消息

    消息格式: {type: 'log', data: {time, level, msg}}
    """
    log_entry = {"time": _get_current_time_str(), "level": level, "msg": msg}
    _log_queue.put({"type": "log", "data": log_entry})


# ==================== Pydantic 模型 ====================
class AnalysisConfig(BaseModel):
    inputDirectory: str
    outputDirectory: Optional[str] = None
    cashThreshold: Optional[float] = 50000
    modules: Optional[Dict[str, bool]] = None


# ==================== 辅助函数 ====================
def serialize_for_json(obj):
    """
    递归转换 NumPy/Pandas 类型为 JSON 可序列化的 Python 原生类型
    解决 FastAPI 无法序列化 numpy.int32 等类型的问题
    """
    import numpy as np

    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(serialize_for_json(v) for v in obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif pd.isna(obj):
        return None
    else:
        return obj


def create_output_directories(base_dir: str) -> Dict[str, str]:
    """创建输出目录结构"""
    dirs = {
        "output": base_dir,
        "cleaned_persons": os.path.join(base_dir, "cleaned_data", "个人"),
        "cleaned_companies": os.path.join(base_dir, "cleaned_data", "公司"),
        "analysis_cache": os.path.join(base_dir, "analysis_cache"),
        "analysis_results": os.path.join(base_dir, "analysis_results"),
    }
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    return dirs


def serialize_profiles(profiles: Dict) -> Dict:
    """
    序列化画像数据

    将后端嵌套的 snake_case 结构转换为前端期望的扁平化 camelCase 结构。

    后端结构:
        profile.summary.total_income
        profile.summary.total_expense
        profile.fund_flow.cash_total
        ...

    前端期望:
        profile.entityName
        profile.totalIncome
        profile.totalExpense
        profile.cashTotal
        ...
    """
    result = {}
    for name, profile in profiles.items():
        try:
            # 处理不同类型的 profile 对象
            if hasattr(profile, "dict"):
                profile_dict = profile.dict()
            elif isinstance(profile, dict):
                profile_dict = profile
            else:
                profile_dict = dict(profile)

            # 🔧 关键修复: 将嵌套结构映射为前端期望的扁平化结构
            summary = profile_dict.get("summary", {})
            income_structure = profile_dict.get("income_structure", {})
            fund_flow = profile_dict.get("fund_flow", {})
            wealth_mgmt = profile_dict.get("wealth_management", {})
            large_cash = profile_dict.get("large_cash", [])

            # 计算现金交易总额 (取现 + 存现)
            cash_total = fund_flow.get("cash_income", 0) + fund_flow.get(
                "cash_expense", 0
            )

            # 计算第三方支付总额
            third_party_total = fund_flow.get("third_party_income", 0) + fund_flow.get(
                "third_party_expense", 0
            )

            # 构建前端期望的扁平化结构
            frontend_profile = {
                # 基础标识
                "entityName": name,
                # 核心财务指标 (camelCase)
                "totalIncome": summary.get("total_income", 0)
                or income_structure.get("total_income", 0),
                "totalExpense": summary.get("total_expense", 0)
                or income_structure.get("total_expense", 0),
                "transactionCount": summary.get("transaction_count", 0),
                # 审计关键字段
                "cashTotal": cash_total,
                "thirdPartyTotal": third_party_total,
                "wealthTotal": wealth_mgmt.get("total_transactions", 0),
                "maxTransaction": income_structure.get("max_single_transaction", 0),
                "salaryRatio": summary.get("salary_ratio", 0),
            }

            result[name] = frontend_profile

        except Exception as e:
            logger.warning(f"序列化 {name} profile 失败: {e}")
            # 降级处理：返回基础结构
            result[name] = {
                "entityName": name,
                "totalIncome": 0,
                "totalExpense": 0,
                "transactionCount": 0,
                "cashTotal": 0,
                "thirdPartyTotal": 0,
                "wealthTotal": 0,
                "maxTransaction": 0,
                "salaryRatio": 0,
                "_error": str(e),
            }
    return result


def serialize_suspicions(suspicions: Dict) -> Dict:
    """
    序列化疑点数据

    将后端 snake_case 字段名转换为前端期望的 camelCase 字段名。
    包括顶层字段和每条记录内部的字段。
    """

    def convert_cash_collision(record: Dict) -> Dict:
        """转换单条 cash_collision 记录"""
        return {
            # 核心字段映射 (后端 withdrawal_entity -> 前端 person1)
            "person1": record.get("withdrawal_entity", ""),
            "person2": record.get("deposit_entity", ""),
            "time1": _format_date(record.get("withdrawal_date")),
            "time2": _format_date(record.get("deposit_date")),
            "amount1": record.get("withdrawal_amount", 0),
            "amount2": record.get("deposit_amount", 0),
            # 位置信息
            "location1": record.get("withdrawal_bank", ""),
            "location2": record.get("deposit_bank", ""),
            # 扩展字段 (camelCase)
            "timeDiff": record.get("time_diff_hours", 0),
            "riskLevel": record.get("risk_level", "low"),
            "riskReason": record.get("risk_reason", ""),
            "withdrawalBank": record.get("withdrawal_bank", ""),
            "depositBank": record.get("deposit_bank", ""),
            "withdrawalSource": record.get("withdrawal_source", ""),
            "depositSource": record.get("deposit_source", ""),
        }

    def convert_direct_transfer(record: Dict) -> Dict:
        """转换单条 direct_transfer 记录"""
        return {
            # 核心字段映射 (后端 person -> 前端 from)
            "from": record.get("person", ""),
            "to": record.get("company", ""),
            "amount": record.get("amount", 0),
            "date": _format_date(record.get("date")),
            "description": record.get("description", ""),
            # 扩展字段 (camelCase)
            "direction": record.get("direction", ""),
            "bank": record.get("bank", ""),
            "sourceFile": record.get("source_file", ""),
            "riskLevel": record.get("risk_level", "low"),
            "riskReason": record.get("risk_reason", ""),
        }

    def _format_date(date_val) -> str:
        """格式化日期为 ISO 字符串"""
        if date_val is None:
            return ""
        if isinstance(date_val, str):
            return date_val
        if hasattr(date_val, "isoformat"):
            return date_val.isoformat()
        return str(date_val)

    # 顶层字段名映射: snake_case -> camelCase
    field_mapping = {
        "direct_transfers": "directTransfers",
        "cash_collisions": "cashCollisions",
        "hidden_assets": "hiddenAssets",
        "fixed_frequency": "fixedFrequency",
        "cash_timing_patterns": "cashTimingPatterns",
        "holiday_transactions": "holidayTransactions",
        "amount_patterns": "amountPatterns",
        "aml_alerts": "amlAlerts",
        "credit_alerts": "creditAlerts",
        "hidden_assets_with_context": "hiddenAssetsWithContext",
        "timeSeriesAlerts": "timeSeriesAlerts",
    }

    result = {}
    for key, value in suspicions.items():
        new_key = field_mapping.get(key, key)

        # 对特定字段的记录进行内部转换
        if key == "cash_collisions" and isinstance(value, list):
            result[new_key] = [convert_cash_collision(r) for r in value]
        elif key == "direct_transfers" and isinstance(value, list):
            result[new_key] = [convert_direct_transfer(r) for r in value]
        else:
            result[new_key] = value

    return result


def serialize_analysis_results(results: Dict) -> Dict:
    """
    序列化分析结果

    将后端嵌套的 snake_case 结构转换为前端期望的扁平化 camelCase 结构。

    后端结构:
        profile.summary.total_income
        profile.summary.total_expense
        profile.fund_flow.cash_total
        ...

    前端期望:
        profile.entityName
        profile.totalIncome
        profile.totalExpense
        profile.cashTotal
        ...
    """
    serialized = {}

    for key, value in results.items():
        if key == "loan":
            # 合并借贷分析的多个分类数组为 details
            loan_result = value if isinstance(value, dict) else {}
            details = []

            # 映射：后端数组名 -> 前端 _type 标识
            loan_type_mapping = {
                "bidirectional_flows": "bidirectional",
                "regular_repayments": "regular_payment",
                "no_payment_loans": "no_payment",
                "online_loan_platforms": "online_loan",
                "loan_pairs": "loan_pair",
                "abnormal_interest": "abnormal_interest",
            }

            # 映射：后端数组名 -> 前端 _type 标识
            income_type_mapping = {
                "large_single_income": "large_single",
                "large_individual_income": "large_individual",
                "unknown_source_income": "unknown_source",
                "regular_non_salary": "regular_non_salary",
                "same_source_multi": "same_source_multi",
                "potential_bribe_installment": "bribe_installment",
                "high_risk": "high_risk",
                "medium_risk": "medium_risk",
            }

            for array_name, type_name in loan_type_mapping.items():
                for item in loan_result.get(array_name, []):
                    record = item.copy() if isinstance(item, dict) else {}
                    record["_type"] = type_name
                    details.append(record)

            serialized["loan"] = {
                "summary": loan_result.get("summary", {}),
                "details": details,
                # 保留原始分类数组供需要的地方使用
                **{
                    k: v
                    for k, v in loan_result.items()
                    if k not in ["summary", "details"]
                },
            }

        elif key == "income":
            # 合并收入分析的多个分类数组为 details
            income_result = value if isinstance(value, dict) else {}
            details = []

            # 映射：后端数组名 -> 前端 _type 标识
            income_type_mapping = {
                "large_single_income": "large_single",
                "large_individual_income": "large_individual",
                "unknown_source_income": "unknown_source",
                "regular_non_salary": "regular_non_salary",
                "same_source_multi": "same_source_multi",
                "potential_bribe_installment": "bribe_installment",
                "high_risk": "high_risk",
                "medium_risk": "medium_risk",
            }

            for array_name, type_name in income_type_mapping.items():
                for item in income_result.get(array_name, []):
                    record = item.copy() if isinstance(item, dict) else {}
                    record["_type"] = type_name
                    details.append(record)

            serialized["income"] = {
                "summary": income_result.get("summary", {}),
                "details": details,
                # 保留原始分类数组供需要的地方使用
                **{
                    k: v
                    for k, v in income_result.items()
                    if k not in ["summary", "details"]
                },
            }

        elif key == "timeSeries":
            serialized[key] = value
        elif key == "aggregation":
            serialized[key] = value
        elif key == "family_tree":
            serialized["family_tree"] = value
        elif key == "family_units_v2":
            serialized["family_units_v2"] = value
        elif key == "family_units":
            # 【修复】只有当 family_units_v2 不存在时才处理 family_units（向后兼容）
            if "family_units_v2" not in serialized:
                # 兼容两种格式：family_units（字典）和 family_units_v2（列表）
                if isinstance(value, list):
                    serialized["family_units_v2"] = value
                else:
                    # 如果是字典格式，转换为列表格式
                    serialized["family_units_v2"] = (
                        [value] if isinstance(value, dict) else []
                    )
            # 如果 family_units_v2 已经存在，则忽略 family_units
        elif key == "family_relations":
            if isinstance(value, list):
                serialized["family_relations"] = value
            else:
                # 如果是字典格式，转换为列表格式
                serialized["family_relations"] = (
                    [value] if isinstance(value, dict) else []
                )
        elif key == "family_summary":
            serialized["family_summary"] = value
        elif key == "all_family_summaries":
            serialized["all_family_summaries"] = value
        else:
            # 其他字段原样保留
            serialized[key] = value

    return serialized


def _enhance_suspicions_with_analysis(suspicions: Dict, analysis_results: Dict) -> Dict:
    """用分析结果增强疑点数据"""
    enhanced = suspicions.copy()
    if analysis_results.get("timeSeries"):
        enhanced["timeSeriesAlerts"] = analysis_results["timeSeries"].get("alerts", [])
    return enhanced


# ==================== 🔄 重构后的分析流程 ====================


def run_analysis_refactored(analysis_config: AnalysisConfig):
    """
    重构后的分析流程 - 优化数据流向

    新流程:
      Phase 1: 文件扫描
      Phase 2: 数据清洗
      Phase 3: 线索提取
      Phase 4: 外部数据提取 (全部18个提取器) ← 关键改进: 提前执行!
      Phase 5: 融合数据画像 (结合外部数据)
      Phase 6: 全面分析 (所有12个分析器)
      Phase 7: 疑点检测 (有完整上下文)
      Phase 8: 报告生成
    """
    logger = logging.getLogger(__name__)

    analysis_state.start_time = datetime.now()
    analysis_state.update(status="running", progress=0, phase="初始化分析引擎...")

    try:
        data_dir = analysis_config.inputDirectory
        output_dir = analysis_config.outputDirectory or os.path.join(
            os.path.dirname(data_dir), "output"
        )

        # 更新全局配置
        global _current_config
        _current_config["inputDirectory"] = data_dir
        _current_config["outputDirectory"] = output_dir
        config.LARGE_CASH_THRESHOLD = analysis_config.cashThreshold

        # ========================================================================
        # 清除旧缓存（点击"开始分析"时自动清除）
        # ========================================================================
        try:
            cache_dir = os.path.join(output_dir, "analysis_cache")
            results_dir = os.path.join(output_dir, "analysis_results")

            def clear_directory_contents(directory):
                """清除目录内容（保留目录本身）"""
                if os.path.exists(directory):
                    for item in os.listdir(directory):
                        item_path = os.path.join(directory, item)
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            import shutil

                            shutil.rmtree(item_path)

            clear_directory_contents(cache_dir)
            clear_directory_contents(results_dir)

            logger.info(f"  ✓ 已清除旧缓存: {cache_dir}, {results_dir}")
            broadcast_log("INFO", "  ✓ 已清除旧缓存，开始新分析")
        except Exception as e:
            logger.warning(f"  ⚠ 清除缓存失败: {e}，继续分析...")

        # ========================================================================
        # Phase 1: 文件扫描 (5%)
        # ========================================================================
        analysis_state.update(progress=5, phase="扫描数据目录...")
        broadcast_log("INFO", "▶ Phase 1: 扫描数据目录...")
        logger.info(f"扫描数据目录: {data_dir}")

        phase1_start = time.time()

        categorized_files = file_categorizer.categorize_files(data_dir)
        persons = list(categorized_files["persons"].keys())
        companies = list(categorized_files["companies"].keys())

        phase1_duration = (time.time() - phase1_start) * 1000
        logging_config.log_performance(
            logger,
            "Phase 1-扫描文件",
            phase1_duration,
            person_count=len(persons),
            company_count=len(companies),
        )
        logger.info(f"发现 {len(persons)} 个个人, {len(companies)} 个企业")
        broadcast_log(
            "INFO", f"  ✓ 发现 {len(persons)} 个个人, {len(companies)} 个企业"
        )

        # ========================================================================
        # Phase 2: 数据清洗 (15%)
        # ========================================================================
        analysis_state.update(progress=15, phase="数据清洗与标准化...")
        broadcast_log("INFO", "▶ Phase 2: 数据清洗与标准化...")
        logger.info("开始数据清洗...")

        phase2_start = time.time()

        cleaned_data = {}
        output_dirs = create_output_directories(output_dir)

        total_entities = len(persons) + len(companies)
        broadcast_log(
            "INFO",
            f"  ↻ 待处理实体: {total_entities} 个 ({len(persons)} 个人 + {len(companies)} 企业)",
        )

        # 清洗个人数据
        for i, p in enumerate(persons):
            p_files = categorized_files["persons"].get(p, [])
            if p_files:
                df, _ = data_cleaner.clean_and_merge_files(p_files, p)
                if df is not None and not df.empty:
                    cleaned_data[p] = df
                    output_path = os.path.join(
                        output_dirs["cleaned_persons"], f"{p}_合并流水.xlsx"
                    )
                    try:
                        data_cleaner.save_formatted_excel(df, output_path)
                        logger.info(f"已保存清洗数据: {p} -> {output_path}")
                    except Exception as e:
                        logger.warning(f"保存清洗数据失败 {p}: {e}")

            progress = 15 + int(10 * (i + 1) / total_entities)
            analysis_state.update(progress=progress)
            if (i + 1) % 2 == 0 or i == len(persons) - 1:
                broadcast_log("INFO", f"  ↻ 清洗个人数据: {i + 1}/{len(persons)} - {p}")

        # 清洗公司数据
        for i, c in enumerate(companies):
            c_files = categorized_files["companies"].get(c, [])
            if c_files:
                df, _ = data_cleaner.clean_and_merge_files(c_files, c)
                if df is not None and not df.empty:
                    cleaned_data[c] = df
                    output_path = os.path.join(
                        output_dirs["cleaned_companies"], f"{c}_合并流水.xlsx"
                    )
                    try:
                        data_cleaner.save_formatted_excel(df, output_path)
                        logger.info(f"已保存清洗数据: {c} -> {output_path}")
                    except Exception as e:
                        logger.warning(f"保存清洗数据失败 {c}: {e}")

            progress = 15 + int(10 * (len(persons) + i + 1) / total_entities)
            analysis_state.update(progress=progress)

        phase2_duration = (time.time() - phase2_start) * 1000
        logging_config.log_performance(
            logger, "Phase 2-数据清洗", phase2_duration, entity_count=len(cleaned_data)
        )
        logger.info(f"清洗完成，共 {len(cleaned_data)} 个实体数据")
        broadcast_log("INFO", f"  ✓ 数据清洗完成: {len(cleaned_data)} 个实体")

        # ========================================================================
        # Phase 3: 线索提取 (30%)
        # ========================================================================
        analysis_state.update(progress=30, phase="提取关联线索...")
        broadcast_log("INFO", "▶ Phase 3: 提取关联线索...")

        phase3_start = time.time()
        clue_persons, clue_companies = data_extractor.extract_all_clues(data_dir)
        all_persons = list(set(persons + clue_persons))
        all_companies = list(set(companies + clue_companies))

        phase3_duration = (time.time() - phase3_start) * 1000
        logging_config.log_performance(
            logger,
            "Phase 3-线索提取",
            phase3_duration,
            clue_persons=len(clue_persons),
            clue_companies=len(clue_companies),
        )
        broadcast_log(
            "INFO",
            f"  ✓ 线索提取完成: 新增 {len(clue_persons)} 个人 + {len(clue_companies)} 企业",
        )
        broadcast_log(
            "INFO",
            f"  ↻ 待分析实体总数: {len(all_persons)} 个人, {len(all_companies)} 企业",
        )

        # ========================================================================
        # Phase 4: 外部数据提取 (40%) ← 🔄 关键改进: 全部提取器提前执行!
        # ========================================================================
        analysis_state.update(progress=40, phase="提取外部数据源 (P0/P1/P2)...")
        broadcast_log("INFO", "▶ Phase 4: 提取外部数据源 (18个提取器)...")
        logger.info("🔄 [重构] 开始提取全部外部数据源 (18个提取器)...")

        phase4_start = time.time()

        external_data = {
            "p0": {},  # P0: 核心上下文
            "p1": {},  # P1: 资产数据
            "p2": {},  # P2: 行为数据
            "id_to_name_map": {},  # 身份证号到人名的映射
        }

        # ========== P0: 核心上下文 ==========
        logger.info("  [P0] 提取核心上下文数据...")
        broadcast_log("INFO", "  [P0] 提取核心上下文数据...")

        # P0.1: 人民银行银行账户
        try:
            pboc_accounts = pboc_account_extractor.extract_pboc_accounts(data_dir)
            external_data["p0"]["pboc_accounts"] = pboc_accounts
            logger.info(f"    ✓ 人民银行账户: {len(pboc_accounts)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 人民银行账户提取失败: {e}")
            external_data["p0"]["pboc_accounts"] = {}

        # P0.2: 反洗钱数据
        try:
            aml_data = aml_analyzer.extract_aml_data(data_dir)
            aml_alerts = aml_analyzer.get_aml_alerts(data_dir)
            external_data["p0"]["aml_data"] = aml_data
            external_data["p0"]["aml_alerts"] = aml_alerts
            logger.info(
                f"    ✓ 反洗钱数据: {len(aml_data)} 个主体, {len(aml_alerts)} 条预警"
            )
        except Exception as e:
            logger.warning(f"    ✗ 反洗钱数据提取失败: {e}")
            external_data["p0"]["aml_data"] = {}
            external_data["p0"]["aml_alerts"] = []

        # P0.3: 企业登记信息
        try:
            company_info = company_info_extractor.extract_company_info(data_dir)
            external_data["p0"]["company_info"] = company_info
            logger.info(f"    ✓ 企业登记信息: {len(company_info)} 个企业")
        except Exception as e:
            logger.warning(f"    ✗ 企业登记信息提取失败: {e}")
            external_data["p0"]["company_info"] = {}

        # P0.4: 征信数据
        try:
            credit_data = credit_report_extractor.extract_credit_data(data_dir)
            credit_alerts = credit_report_extractor.get_credit_alerts(data_dir)
            external_data["p0"]["credit_data"] = credit_data
            external_data["p0"]["credit_alerts"] = credit_alerts
            logger.info(
                f"    ✓ 征信数据: {len(credit_data)} 个主体, {len(credit_alerts)} 条预警"
            )
        except Exception as e:
            logger.warning(f"    ✗ 征信数据提取失败: {e}")
            external_data["p0"]["credit_data"] = {}
            external_data["p0"]["credit_alerts"] = []

        # P0.5: 银行业金融机构账户信息
        try:
            bank_account_info = bank_account_info_extractor.extract_bank_account_info(
                data_dir
            )
            external_data["p0"]["bank_account_info"] = bank_account_info
            logger.info(f"    ✓ 银行账户信息: {len(bank_account_info)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 银行账户信息提取失败: {e}")
            external_data["p0"]["bank_account_info"] = {}

        # ========== P1: 资产数据 ==========
        logger.info("  [P1] 提取资产数据...")

        # P1.1: 公安部机动车
        try:
            vehicle_data = vehicle_extractor.extract_vehicle_data(data_dir)
            external_data["p1"]["vehicle_data"] = vehicle_data
            logger.info(f"    ✓ 公安部机动车: {len(vehicle_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 公安部机动车提取失败: {e}")
            external_data["p1"]["vehicle_data"] = {}

        # P1.2: 银行理财产品
        try:
            wealth_product_data = wealth_product_extractor.extract_wealth_product_data(
                data_dir
            )
            external_data["p1"]["wealth_product_data"] = wealth_product_data
            logger.info(f"    ✓ 银行理财产品: {len(wealth_product_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 银行理财产品提取失败: {e}")
            external_data["p1"]["wealth_product_data"] = {}

        # P1.3: 证券信息
        try:
            securities_data = securities_extractor.extract_securities_data(data_dir)
            external_data["p1"]["securities_data"] = securities_data
            logger.info(f"    ✓ 证券信息: {len(securities_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 证券信息提取失败: {e}")
            external_data["p1"]["securities_data"] = {}

        # P1.4: 自然资源部精准查询
        try:
            precise_property_data = asset_extractor.extract_precise_property_info(
                data_dir
            )
            external_data["p1"]["precise_property_data"] = precise_property_data
            logger.info(
                f"    ✓ 自然资源部精准查询: {len(precise_property_data)} 个主体"
            )
        except Exception as e:
            logger.warning(f"    ✗ 自然资源部精准查询提取失败: {e}")
            external_data["p1"]["precise_property_data"] = {}

        # ========== P2: 行为数据 ==========
        logger.info("  [P2] 提取行为数据...")

        # P2.1: 保险信息
        try:
            insurance_data = insurance_extractor.extract_insurance_data(data_dir)
            external_data["p2"]["insurance_data"] = insurance_data
            logger.info(f"    ✓ 保险信息: {len(insurance_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 保险信息提取失败: {e}")
            external_data["p2"]["insurance_data"] = {}

        # P2.2: 出入境记录
        try:
            immigration_data = immigration_extractor.extract_immigration_data(data_dir)
            external_data["p2"]["immigration_data"] = immigration_data
            logger.info(f"    ✓ 出入境记录: {len(immigration_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 出入境记录提取失败: {e}")
            external_data["p2"]["immigration_data"] = {}

        # P2.3: 旅馆住宿
        try:
            hotel_data = hotel_extractor.extract_hotel_data(data_dir)
            cohabitation_analysis = hotel_extractor.analyze_cohabitation(data_dir)
            external_data["p2"]["hotel_data"] = hotel_data
            external_data["p2"]["hotel_cohabitation"] = cohabitation_analysis
            logger.info(f"    ✓ 旅馆住宿: {len(hotel_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 旅馆住宿提取失败: {e}")
            external_data["p2"]["hotel_data"] = {}
            external_data["p2"]["hotel_cohabitation"] = {}

        # P2.4: 铁路出行
        try:
            railway_data = railway_extractor.extract_railway_data(data_dir)
            railway_timeline = railway_extractor.build_railway_timeline(data_dir)
            external_data["p2"]["railway_data"] = railway_data
            external_data["p2"]["railway_timeline"] = railway_timeline
            logger.info(f"    ✓ 铁路出行: {len(railway_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 铁路出行提取失败: {e}")
            external_data["p2"]["railway_data"] = {}
            external_data["p2"]["railway_timeline"] = {}

        # P2.5: 航班出行
        try:
            flight_data = flight_extractor.extract_flight_data(data_dir)
            flight_timeline = flight_extractor.build_flight_timeline(data_dir)
            external_data["p2"]["flight_data"] = flight_data
            external_data["p2"]["flight_timeline"] = flight_timeline
            logger.info(f"    ✓ 航班出行: {len(flight_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 航班出行提取失败: {e}")
            external_data["p2"]["flight_data"] = {}
            external_data["p2"]["flight_timeline"] = {}

        phase4_duration = (time.time() - phase4_start) * 1000
        logging_config.log_performance(
            logger, "Phase 4-外部数据提取(全部)", phase4_duration
        )

        logger.info("🔄 [重构] 外部数据提取完成")
        broadcast_log("INFO", f"  ✓ 外部数据提取完成 (P0/P1/P2 共 18 个提取器)")

        # ========================================================================
        # Phase 5: 融合数据画像 (50%) ← 🔄 结合外部数据生成完整画像
        # ========================================================================
        analysis_state.update(progress=50, phase="生成融合数据画像...")
        broadcast_log("INFO", "▶ Phase 5: 生成融合数据画像...")
        logger.info("🔄 [重构] 生成包含外部数据的完整画像...")

        phase5_start = time.time()

        profiles = {}
        id_to_name_map = {}

        # 🔄 构建身份证号到人名的映射（直接扫描数据目录的文件名）
        import glob

        transaction_dir = os.path.join(data_dir, "银行业金融机构交易流水（定向查询）")
        if os.path.exists(transaction_dir):
            pattern = os.path.join(transaction_dir, "*_*_*.xlsx")
            for file_path in glob.glob(pattern):
                # 从文件名提取: 滕雳_310230196811100267_...
                basename = os.path.basename(file_path)
                parts = basename.split("_")
                if len(parts) >= 2:
                    name = parts[0]
                    id_part = parts[1]
                    if len(id_part) == 18 and id_part.isdigit():
                        id_to_name_map[id_part.upper()] = name

        logger.info(f"身份证号映射表构建完成: {len(id_to_name_map)} 个人员")

        for entity, df in cleaned_data.items():
            try:
                # 1. 生成基础画像
                profile = financial_profiler.generate_profile_report(df, entity)

                # 2. 提取银行账户列表
                if entity in all_persons:
                    try:
                        profile["bank_accounts"] = (
                            financial_profiler.extract_bank_accounts(df)
                        )
                    except Exception as e:
                        logger.warning(f"提取 {entity} 银行账户失败: {e}")

                # 4. 🔄 融合外部数据 (P0 - 核心上下文)
                # P0.1: 人民银行账户
                if entity in external_data["p0"].get("pboc_accounts", {}):
                    profile["bank_accounts_official"] = external_data["p0"][
                        "pboc_accounts"
                    ][entity].get("accounts", [])

                # P0.2: 反洗钱预警
                if entity in external_data["p0"].get("aml_data", {}):
                    profile["aml_info"] = external_data["p0"]["aml_data"][entity]

                # P0.3: 企业信息
                if entity in external_data["p0"].get("company_info", {}):
                    profile["company_registration"] = external_data["p0"][
                        "company_info"
                    ][entity]

                # P0.4: 征信信息
                if entity in external_data["p0"].get("credit_data", {}):
                    profile["credit_info"] = external_data["p0"]["credit_data"][entity]

                # P0.5: 银行账户信息补充
                if entity in external_data["p0"].get("bank_account_info", {}):
                    existing = profile.get("bank_accounts_official", [])
                    existing_nums = {a.get("account_number") for a in existing}
                    for acc in external_data["p0"]["bank_account_info"][entity].get(
                        "accounts", []
                    ):
                        if acc.get("account_number") not in existing_nums:
                            existing.append(acc)
                    profile["bank_accounts_official"] = existing

                # 5. 🔄 融合外部数据 (P1 - 资产)
                # P1.1: 车辆 (使用身份证号映射)
                vehicle_data = external_data["p1"].get("vehicle_data", {})
                for person_id, vehicles in vehicle_data.items():
                    person_name = id_to_name_map.get(person_id, person_id)
                    if person_name == entity:
                        profile["vehicles"] = vehicles
                        break

                # P1.2: 理财产品
                if entity in external_data["p1"].get("wealth_product_data", {}):
                    wealth_info = external_data["p1"]["wealth_product_data"][entity]
                    profile["wealth_products"] = wealth_info.get("products", [])
                    profile["wealth_summary"] = wealth_info.get("summary", {})

                # P1.3: 证券
                if entity in external_data["p1"].get("securities_data", {}):
                    profile["securities"] = external_data["p1"]["securities_data"][
                        entity
                    ]

                # P1.4: 房产
                property_data = external_data["p1"].get("precise_property_data", {})
                for person_id, properties in property_data.items():
                    person_name = id_to_name_map.get(person_id, person_id)
                    if person_name == entity:
                        profile["properties_precise"] = properties
                        break

                # 6. 🔄 融合外部数据 (P2 - 行为)
                # P2.1: 保险
                if entity in external_data["p2"].get("insurance_data", {}):
                    profile["insurance"] = external_data["p2"]["insurance_data"][entity]

                # P2.2: 出入境
                if entity in external_data["p2"].get("immigration_data", {}):
                    profile["immigration_records"] = external_data["p2"][
                        "immigration_data"
                    ][entity]

                # P2.3: 住宿
                if entity in external_data["p2"].get("hotel_data", {}):
                    profile["hotel_records"] = external_data["p2"]["hotel_data"][entity]

                # P2.4: 铁路
                if entity in external_data["p2"].get("railway_data", {}):
                    profile["railway_records"] = external_data["p2"]["railway_data"][
                        entity
                    ]

                # P2.5: 航班
                if entity in external_data["p2"].get("flight_data", {}):
                    profile["flight_records"] = external_data["p2"]["flight_data"][
                        entity
                    ]

                profiles[entity] = profile

            except Exception as e:
                logger.warning(f"生成 {entity} 画像失败: {e}")

        phase5_duration = (time.time() - phase5_start) * 1000
        logging_config.log_performance(
            logger, "Phase 5-融合数据画像", phase5_duration, profile_count=len(profiles)
        )
        logger.info(f"🔄 [重构] 融合画像生成完成: {len(profiles)} 个实体")
        broadcast_log("INFO", f"  ✓ 融合画像生成完成: {len(profiles)} 个实体")

        # ========================================================================
        # Phase 6: 全面分析 (70%) ← 🔄 有完整上下文后执行
        # ========================================================================
        analysis_state.update(progress=70, phase="运行全面分析模块...")
        broadcast_log("INFO", "▶ Phase 6: 运行全面分析模块 (12个分析器)...")
        logger.info("🔄 [重构] 运行全面分析 (有完整上下文)...")

        phase6_start = time.time()

        analysis_results = {}

        # 防御性检查：确保有有效的配置
        modules_config = {}
        if (
            analysis_config is not None
            and hasattr(analysis_config, "modules")
            and analysis_config.modules is not None
        ):
            modules_config = analysis_config.modules
        else:
            # 默认所有模块启用
            modules_config = {
                "loanAnalysis": True,
                "incomeAnalysis": True,
                "relatedParty": True,
                "multiSourceCorrelation": True,
                "timeSeriesAnalysis": True,
                "clueAggregation": True,
            }

        # 6.1 借贷分析
        if modules_config.get("loanAnalysis", True):
            try:
                analysis_results["loan"] = loan_analyzer.analyze_loan_behaviors(
                    cleaned_data, all_persons
                )
                logger.info("  ✓ 借贷分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 借贷分析失败: {e}")

        # 6.2 收入分析
        if modules_config.get("incomeAnalysis", True):
            try:
                analysis_results["income"] = income_analyzer.detect_suspicious_income(
                    cleaned_data, all_persons
                )
                analysis_results["large_transactions"] = (
                    income_analyzer.extract_large_transactions(
                        cleaned_data, all_persons
                    )
                )
                logger.info("  ✓ 收入分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 收入分析失败: {e}")

        # 6.3 关联方分析
        if modules_config.get("relatedParty", True):
            try:
                analysis_results["relatedParty"] = (
                    related_party_analyzer.analyze_related_party_flows(
                        cleaned_data, all_persons
                    )
                )

                # 调查单位往来分析
                investigation_unit_flows = {}
                all_entities = all_persons + all_companies
                for entity in all_entities:
                    if entity in cleaned_data:
                        df = cleaned_data[entity]
                        flows = related_party_analyzer.analyze_investigation_unit_flows(
                            df, entity
                        )
                        if flows.get("has_flows", False):
                            investigation_unit_flows[entity] = {
                                "total_amount": flows.get("total_income", 0)
                                + flows.get("total_expense", 0),
                                "total_income": flows.get("total_income", 0),
                                "total_expense": flows.get("total_expense", 0),
                                "net_flow": flows.get("net_flow", 0),
                                "income_count": flows.get("income_count", 0),
                                "expense_count": flows.get("expense_count", 0),
                                "transactions": flows.get("income_details", [])[:20]
                                + flows.get("expense_details", [])[:20],
                                "matched_units": list(flows.get("matched_units", [])),
                            }
                analysis_results["investigation_unit_flows"] = investigation_unit_flows
                logger.info("  ✓ 关联方分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 关联方分析失败: {e}")

        # 6.4 多源数据碰撞
        if modules_config.get("multiSourceCorrelation", True):
            try:
                analysis_results["correlation"] = (
                    multi_source_correlator.run_all_correlations(
                        data_dir, cleaned_data, all_persons
                    )
                )
                logger.info("  ✓ 多源数据碰撞完成")
            except Exception as e:
                logger.warning(f"  ✗ 多源数据碰撞失败: {e}")

        # 6.5 时序分析
        if modules_config.get("timeSeriesAnalysis", True):
            try:
                analysis_results["timeSeries"] = (
                    time_series_analyzer.analyze_time_series(cleaned_data, all_persons)
                )
                logger.info("  ✓ 时序分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 时序分析失败: {e}")

        # 6.6 线索聚合
        if modules_config.get("clueAggregation", True):
            try:
                analysis_results["aggregation"] = clue_aggregator.aggregate_all_results(
                    all_persons,
                    all_companies,
                    penetration_results=None,
                    ml_results=None,
                    ts_results=analysis_results.get("timeSeries"),
                    related_party_results=analysis_results.get("relatedParty"),
                    loan_results=analysis_results.get("loan"),
                )
                logger.info("  ✓ 线索聚合完成")
            except Exception as e:
                logger.warning(f"  ✗ 线索聚合失败: {e}")

        # 6.7 家庭关系分析
        try:
            family_units_list = family_analyzer.build_family_units(
                all_persons, data_dir
            )
            family_tree = family_analyzer.build_family_tree(all_persons, data_dir)
            family_summary = family_analyzer.get_family_summary(family_tree)

            analysis_results["family_tree"] = family_tree
            analysis_results["family_units"] = family_summary
            analysis_results["family_relations"] = family_tree
            analysis_results["family_units_v2"] = family_units_list

            # 计算家庭财务汇总
            all_family_summaries = {}
            for unit in family_units_list:
                householder = unit.get("householder", "")
                members = unit.get("members", [])
                if members:
                    try:
                        unit_summary = family_finance.calculate_family_summary(
                            profiles, members
                        )
                        unit_summary["householder"] = householder
                        unit_summary["extended_relatives"] = unit.get(
                            "extended_relatives", []
                        )
                        all_family_summaries[householder] = unit_summary
                    except Exception as e:
                        logger.warning(f"计算 {householder} 家庭汇总失败: {e}")

            if all_family_summaries:
                first_householder = list(all_family_summaries.keys())[0]
                analysis_results["family_summary"] = all_family_summaries[
                    first_householder
                ]
                analysis_results["all_family_summaries"] = all_family_summaries
                logger.info(f"  ✓ 家庭分析完成: {len(family_units_list)} 个家庭")
            else:
                family_summary_result = family_finance.calculate_family_summary(
                    profiles, all_persons
                )
                analysis_results["family_summary"] = family_summary_result
                logger.info(f"  ✓ 家庭汇总完成(fallback): {len(all_persons)} 人")

        except Exception as e:
            logger.warning(f"  ✗ 家庭分析失败: {e}")
            analysis_results["family_tree"] = {}
            analysis_results["family_units"] = {}
            analysis_results["family_relations"] = {}
            analysis_results["family_summary"] = {}

        # 6.8 行为画像
        try:
            analysis_results["behavioral"] = (
                behavioral_profiler.analyze_behavioral_patterns(
                    cleaned_data, all_persons, external_data
                )
            )
            logger.info("  ✓ 行为画像完成")
        except Exception as e:
            logger.warning(f"  ✗ 行为画像失败: {e}")

        phase6_duration = (time.time() - phase6_start) * 1000
        logging_config.log_performance(
            logger,
            "Phase 6-全面分析",
            phase6_duration,
            module_count=len(analysis_results),
        )
        broadcast_log("INFO", f"  ✓ 全面分析完成: {len(analysis_results)} 个模块")

        # ========================================================================
        # Phase 7: 疑点检测 (85%) ← 🔄 有完整上下文后执行
        # ========================================================================
        analysis_state.update(progress=85, phase="检测可疑交易模式...")
        broadcast_log("INFO", "▶ Phase 7: 检测可疑交易模式...")
        logger.info("🔄 [重构] 执行疑点检测 (有资产上下文)...")

        phase7_start = time.time()

        # 7.1 基础疑点检测
        suspicions = suspicion_detector.run_all_detections(
            cleaned_data, all_persons, all_companies
        )

        # 7.2 🔄 融合外部疑点数据
        # 反洗钱预警
        aml_alerts = external_data["p0"].get("aml_alerts", [])
        if aml_alerts:
            suspicions["aml_alerts"] = aml_alerts

        # 征信预警
        credit_alerts = external_data["p0"].get("credit_alerts", [])
        if credit_alerts:
            suspicions["credit_alerts"] = credit_alerts

        # 7.3 🔄 隐形资产检测 (现在有房产/车辆数据可以对比!)
        try:
            hidden_assets = _detect_hidden_assets_with_context(
                profiles,
                cleaned_data,
                all_persons,
                external_data["p1"]["precise_property_data"],
                external_data["p1"]["vehicle_data"],
            )
            if hidden_assets:
                suspicions["hidden_assets_with_context"] = hidden_assets
                logger.info(f"  ✓ 隐形资产检测: 发现 {len(hidden_assets)} 个可疑点")
        except Exception as e:
            logger.warning(f"  ✗ 隐形资产检测失败: {e}")

        phase7_duration = (time.time() - phase7_start) * 1000
        logging_config.log_performance(
            logger,
            "Phase 7-疑点检测(增强版)",
            phase7_duration,
            suspicion_count=len(suspicions.get("direct_transfers", [])),
        )
        suspicion_total = sum(
            len(v) if isinstance(v, list) else 1 for v in suspicions.values()
        )
        broadcast_log("INFO", f"  ✓ 疑点检测完成: 发现 {suspicion_total} 个可疑点")

        analysis_state.update(progress=95, phase="生成分析报告...")
        broadcast_log("INFO", "▶ Phase 8: 生成分析报告...")

        derived_data = {
            "loan": analysis_results.get("loan", {}),
            "income": analysis_results.get("income", {}),
            "time_series": analysis_results.get("timeSeries", {}),
            "large_transactions": analysis_results.get("large_transactions", []),
            "family_summary": analysis_results.get("family_summary", {}),
            "family_relations": analysis_results.get("family_relations", {}),
        }

        phase8_start = time.time()

        # 8.1 构建家庭资产数据
        try:
            precise_property_data = external_data["p1"].get("precise_property_data", {})
            vehicle_data = external_data["p1"].get("vehicle_data", {})

            if precise_property_data or vehicle_data:
                family_assets = family_assets_helper.build_family_assets_simple(
                    precise_property_data, vehicle_data, all_persons
                )
                logger.info(f"  ✓ 家庭资产数据: {len(family_assets)} 个人员")
            else:
                family_assets = {}
        except Exception as e:
            logger.warning(f"  ✗ 构建family_assets失败: {e}")
            family_assets = {}

        # 8.2 生成完整txt报告（使用investigation_report_builder）
        try:
            builder = load_investigation_report_builder(output_dir)
            if builder:
                txt_report_path = os.path.join(
                    output_dirs["analysis_results"],
                    config.OUTPUT_REPORT_FILE.replace(".docx", ".txt"),
                )
                txt_report_path = builder.generate_complete_txt_report(txt_report_path)
                logger.info(f"  ✓ 完整txt报告已生成: {txt_report_path}")
                broadcast_log("INFO", "  ✓ 完整txt报告生成成功")
            else:
                logger.warning("  ✗ 报告构建器未加载，txt报告生成失败")
        except Exception as e:
            logger.warning(f"  ✗ 完整txt报告生成失败: {e}")
            broadcast_log("WARN", f"  ✗ 完整txt报告生成失败: {str(e)[:50]}")

        # 8.3 生成 Excel 核查底稿
        try:
            excel_path = report_generator.generate_excel_workbook(
                profiles=profiles,
                suspicions=suspicions,
                output_path=os.path.join(
                    output_dirs["analysis_results"], config.OUTPUT_EXCEL_FILE
                ),
                family_assets=family_assets,
                penetration_results=analysis_results.get("penetration", {}),
                loan_results=analysis_results.get("loan", {}),
                income_results=analysis_results.get("income", {}),
                time_series_results=analysis_results.get("time_series", {}),
                derived_data=derived_data if "derived_data" in dir() else {},
            )
            logger.info(f"  ✓ Excel核查底稿已生成: {excel_path}")
            broadcast_log("INFO", "  ✓ Excel核查底稿生成成功")
        except Exception as e:
            logger.warning(f"  ✗ Excel核查底稿生成失败: {e}")
            broadcast_log("WARN", f"  ✗ Excel核查底稿生成失败: {str(e)[:50]}")

        # 8.4 生成专项txt报告
        try:
            logger.info("  8.4 开始生成专项txt报告...")
            builder = load_investigation_report_builder(output_dir)
            if builder:
                specialized_gen = SpecializedReportGenerator(
                    analysis_results=analysis_results,
                    profiles=builder.profiles,
                    suspicions=builder.suspicions,
                    output_dir=output_dirs["analysis_results"],
                )
                specialized_files = specialized_gen.generate_all_reports()
                if specialized_files:
                    logger.info(
                        f"  ✓ 专项txt报告已生成: {len(specialized_files)} 个文件"
                    )
                    for file in specialized_files:
                        logger.info(f"    - {os.path.basename(file)}")
                    broadcast_log(
                        "INFO",
                        f"  ✓ 专项txt报告生成成功 ({len(specialized_files)} 个文件)",
                    )
                else:
                    logger.warning("  ✗ 专项txt报告未生成（可能无数据）")
            else:
                logger.warning("  ✗ 报告构建器未加载，专项txt报告生成失败")
        except Exception as e:
            logger.warning(f"  ✗ 专项txt报告生成失败: {e}")
            broadcast_log("WARN", f"  ✗ 专项txt报告生成失败: {str(e)[:50]}")

        # 8.5 生成报告目录清单（使用investigation_report_builder）
        try:
            builder = load_investigation_report_builder(output_dir)
            if builder:
                index_path = builder.generate_report_index_file(
                    output_dirs["analysis_results"]
                )
                logger.info(f"  ✓ 报告目录清单已生成: {index_path}")
                broadcast_log("INFO", "  ✓ 报告目录清单生成成功")
            else:
                logger.warning("  ✗ 报告构建器未加载，目录清单生成失败")
        except Exception as e:
            logger.warning(f"  ✗ 报告目录清单生成失败: {e}")
            broadcast_log("WARN", f"  ✗ 报告目录清单生成失败: {str(e)[:50]}")

        # 【修复】8.6 保存分析缓存（提前到 HTML 报告生成之前）
        logger.info("保存分析缓存...")
        _save_analysis_cache_refactored(
            analysis_state.results, output_dirs["analysis_cache"]
        )

        # 8.7 生成初查报告v4.html（HTML报告，自动生成）
        try:
            builder = load_investigation_report_builder(output_dir)
            if builder:
                html_report_path = os.path.join(
                    output_dirs["analysis_results"], "初查报告_v4.html"
                )

                # 加载归集配置
                from report_config.primary_targets_service import PrimaryTargetsService

                config_service = PrimaryTargetsService(
                    data_dir="./data", output_dir="./output"
                )
                primary_targets_config, msg, is_new = (
                    config_service.get_or_create_config()
                )

                if primary_targets_config is None:
                    logger.warning(f"  ✗ 归集配置加载失败: {msg}")
                    broadcast_log("WARN", f"  ✗ 归集配置加载失败")
                else:
                    # 使用新版配置接口生成报告
                    report = builder.build_report_with_config(
                        config=primary_targets_config,
                        case_background="",
                        data_scope="",
                    )

                    # 渲染为HTML
                    html_content = _render_report_to_html(report)

                    # 保存HTML文件
                    with open(html_report_path, "w", encoding="utf-8") as f:
                        f.write(html_content)

                    logger.info(f"  ✓ HTML报告已生成: {html_report_path}")
                    broadcast_log("INFO", "  ✓ HTML报告生成成功（初查报告v4.html）")
            else:
                logger.warning("  ✗ 报告构建器未加载，HTML报告生成失败")
        except Exception as e:
            logger.warning(f"  ✗ HTML报告生成失败: {e}")
            broadcast_log("WARN", f"  ✗ HTML报告生成失败: {str(e)[:50]}")

        phase8_duration = (time.time() - phase8_start) * 1000
        logging_config.log_performance(
            logger, "Phase 8-报告生成", phase8_duration, report_count=2
        )

        # ========================================================================
        # 完成
        # ========================================================================
        analysis_state.update(progress=100, phase="分析完成")
        broadcast_log("INFO", "✓ 分析完成")
        analysis_state.end_time = datetime.now()
        analysis_state.status = "completed"

        enhanced_suspicions = _enhance_suspicions_with_analysis(
            suspicions, analysis_results
        )

        # 预计算图谱数据
        logger.info("预计算图谱数据...")
        graph_data_cache = None
        try:
            flow_stats = flow_visualizer._calculate_flow_stats(
                cleaned_data, all_persons
            )
            nodes, edges, edge_stats = flow_visualizer._prepare_graph_data(
                flow_stats, all_persons, all_companies
            )

            max_nodes, max_edges = config.GRAPH_MAX_NODES, config.GRAPH_MAX_EDGES
            sorted_nodes = sorted(nodes, key=lambda x: x.get("size", 0), reverse=True)
            sampled_nodes = sorted_nodes[:max_nodes]
            sampled_node_ids = {node["id"] for node in sampled_nodes}

            sampled_edges = [
                e
                for e in edges
                if e["from"] in sampled_node_ids and e["to"] in sampled_node_ids
            ]
            sampled_edges.sort(key=lambda x: x.get("value", 0), reverse=True)
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
                    "message": "为保证流畅度，仅展示核心资金网络。",
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
                },
            }
            logger.info(
                f"  ✓ 图谱缓存: {len(sampled_nodes)} 节点, {len(sampled_edges)} 边"
            )
        except Exception as e:
            logger.warning(f"  ✗ 图谱缓存失败: {e}")

        # 保存结果
        analysis_state.results = {
            "persons": all_persons,
            "companies": all_companies,
            "profiles": serialize_profiles(profiles),
            "suspicions": serialize_suspicions(enhanced_suspicions),
            "analysisResults": serialize_analysis_results(analysis_results),
            "graphData": graph_data_cache,
            "externalData": external_data,
            "_profiles_raw": profiles,
        }

        # 内存清理
        logger.info("释放临时数据...")
        try:
            del cleaned_data
            del profiles
            del suspicions
            del enhanced_suspicions
            del analysis_results
            import gc

            gc.collect()
            logger.info("  ✓ 内存清理完成")
        except Exception as e:
            logger.warning(f"  ✗ 内存清理警告: {e}")

        duration = (analysis_state.end_time - analysis_state.start_time).total_seconds()
        logger.info(f"✓ 分析完成，耗时 {duration:.2f} 秒")
        logger.info("🔄 [重构] 新数据流向已生效")

        return analysis_state.results

    except Exception as e:
        logger.exception(f"分析失败: {e}")
        analysis_state.update(status="failed", error=str(e))
        raise


def _detect_hidden_assets_with_context(
    profiles, cleaned_data, all_persons, property_data, vehicle_data
):
    """
    🔄 新功能: 基于外部数据检测隐形资产

    对比交易记录中的资产相关支出与官方登记的资产
    """
    hidden_assets = []

    for person in all_persons:
        if person not in profiles:
            continue

        profile = profiles[person]

        # 官方登记的资产
        official_properties = profile.get("properties_precise", [])
        official_vehicles = profile.get("vehicles", [])

        # 检测疑似隐形房产 (交易中有相关支出但无登记)
        try:
            df = cleaned_data.get(person)
            if df is not None:
                # 查找房产相关交易
                property_transactions = df[
                    df["description"].str.contains("房|地产|物业|按揭", na=False)
                    | df["counterparty"].str.contains("房产|置业|开发商", na=False)
                ]

                if len(property_transactions) > 0 and len(official_properties) == 0:
                    hidden_assets.append(
                        {
                            "person": person,
                            "type": "property",
                            "evidence": f"发现 {len(property_transactions)} 条房产相关交易，但无房产登记",
                            "transaction_count": len(property_transactions),
                            "amount": property_transactions["amount"].sum(),
                        }
                    )
        except Exception as e:
            pass

        # 检测疑似隐形车辆
        try:
            df = cleaned_data.get(person)
            if df is not None:
                vehicle_transactions = df[
                    df["description"].str.contains("车|车辆|购车|4S店", na=False)
                    | df["counterparty"].str.contains("车行|汽车", na=False)
                ]

                if len(vehicle_transactions) > 0 and len(official_vehicles) == 0:
                    hidden_assets.append(
                        {
                            "person": person,
                            "type": "vehicle",
                            "evidence": f"发现 {len(vehicle_transactions)} 条车辆相关交易，但无车辆登记",
                            "transaction_count": len(vehicle_transactions),
                            "amount": vehicle_transactions["amount"].sum(),
                        }
                    )
        except Exception as e:
            pass

    return hidden_assets


def _save_analysis_cache_refactored(results, cache_dir):
    """保存分析缓存到文件（使用缓存管理器）"""
    logger = logging.getLogger(__name__)

    try:
        # 使用缓存管理器保存所有缓存
        cache_mgr = CacheManager(cache_dir)
        cache_mgr.save_results(results)
        logger.info(f"✓ 缓存已保存: {cache_dir}")

    except Exception as e:
        logger.error(f"✗ 保存缓存失败: {e}")


# ==================== FastAPI 应用 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger = logging.getLogger(__name__)
    logger.info("🚀 资金穿透审计系统启动 (重构版)")
    yield
    logger.info("🛑 资金穿透审计系统关闭")


app = FastAPI(
    title="资金穿透审计系统 API (重构版)",
    description="数据流向优化: 外部数据提取 → 融合画像 → 全面分析 → 疑点检测",
    version="3.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== API 端点 ====================
@app.get("/")
async def root():
    return {
        "name": "资金穿透审计系统 API (重构版)",
        "version": "3.2.0",
        "status": "running",
        "dataFlow": "external_data_first",
        "refactored": True,
    }


@app.get("/api/status")
async def get_status():
    """获取分析状态"""
    return analysis_state.to_dict()


@app.post("/api/analysis/start")
async def start_analysis(config: AnalysisConfig, background_tasks: BackgroundTasks):
    """启动分析任务"""
    if analysis_state.status == "running":
        raise HTTPException(status_code=400, detail="分析任务正在运行")

    background_tasks.add_task(run_analysis_refactored, config)
    return {"message": "分析任务已启动 (重构版)", "version": "3.2.0"}


@app.get("/api/results")
async def get_results():
    """获取分析结果（优先从内存读取，fallback到缓存文件）"""
    # 如果内存中有结果，直接返回
    if analysis_state.status == "completed" and analysis_state.results:
        results_data = serialize_for_json(analysis_state.results)
        return {"message": "分析结果获取成功", "data": results_data}

    # 内存中没有结果，尝试从缓存文件读取
    cache_dir = os.path.join("output", "analysis_cache")
    try:
        cache_mgr = CacheManager(cache_dir)
        results_data = cache_mgr.load_results()

        if results_data:
            # 将缓存结果加载到内存
            analysis_state.results = results_data
            analysis_state.status = "completed"
            return {
                "message": "分析结果获取成功（来自缓存）",
                "data": serialize_for_json(results_data),
            }
        else:
            raise HTTPException(status_code=400, detail="分析尚未完成且缓存无效")
    except Exception as e:
        logging.getLogger(__name__).error(f"读取缓存失败: {e}")
        raise HTTPException(
            status_code=400, detail=f"分析尚未完成且缓存读取失败: {str(e)}"
        )


@app.get("/api/reports")
async def get_reports():
    """获取报告列表（递归扫描所有子目录）"""
    reports = []
    reports_dir = os.path.join("output", "analysis_results")

    def scan_directory(directory, prefix=""):
        """递归扫描目录"""
        if not os.path.exists(directory):
            return

        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            relative_path = os.path.relpath(item_path, reports_dir)

            if os.path.isfile(item_path):
                if item.endswith((".html", ".docx", ".txt", ".pdf")):
                    stat_info = os.stat(item_path)
                    # 在子目录中的文件，添加子目录前缀
                    display_name = item if prefix == "" else f"{prefix}/{item}"
                    reports.append(
                        {
                            "name": display_name,  # 前端期望 "name"
                            "path": item_path,
                            "size": stat_info.st_size,
                            "modified": datetime.fromtimestamp(
                                stat_info.st_mtime
                            ).isoformat(),  # 前端期望 "modified"
                        }
                    )
            elif os.path.isdir(item_path):
                # 递归扫描子目录
                scan_directory(
                    item_path, prefix=item if prefix == "" else f"{prefix}/{item}"
                )

    scan_directory(reports_dir)

    # 按修改时间排序，最新的在前面
    reports.sort(key=lambda x: x["modified"], reverse=True)

    return {"reports": reports}


@app.get("/api/reports/subjects")
async def get_report_subjects():
    """获取报告生成可选的核查对象列表"""
    # 优先从缓存中获取
    if analysis_state.status == "completed" and analysis_state.results:
        results = analysis_state.results
        persons = results.get("persons", [])
        companies = results.get("companies", [])
        profiles = results.get("profiles", {})

        subjects = []

        # 添加个人
        for person in persons:
            profile = profiles.get(person, {})
            subjects.append(
                {
                    "name": person,
                    "type": "person",
                    "transactionCount": profile.get("transaction_count", 0),
                    "totalIncome": profile.get("total_income", 0),
                    "salaryRatio": profile.get("salary_ratio", 1.0),
                }
            )

        # 添加公司
        for company in companies:
            profile = profiles.get(company, {})
            subjects.append(
                {
                    "name": company,
                    "type": "company",
                    "transactionCount": profile.get("transaction_count", 0),
                    "totalIncome": profile.get("total_income", 0),
                }
            )

        return {"success": True, "subjects": subjects}

    # 尝试从缓存文件中读取
    cache_dir = os.path.join("output", "analysis_cache")
    metadata_path = os.path.join(cache_dir, "metadata.json")
    profiles_path = os.path.join(cache_dir, "profiles.json")

    subjects = []

    if os.path.exists(metadata_path) and os.path.exists(profiles_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            with open(profiles_path, "r", encoding="utf-8") as f:
                profiles = json.load(f)

            persons = metadata.get("persons", [])
            companies = metadata.get("companies", [])

            for person in persons:
                profile = profiles.get(person, {})
                subjects.append(
                    {
                        "name": person,
                        "type": "person",
                        "transactionCount": profile.get("transaction_count", 0),
                        "totalIncome": profile.get("total_income", 0),
                        "salaryRatio": profile.get("salary_ratio", 1.0),
                    }
                )

            for company in companies:
                profile = profiles.get(company, {})
                subjects.append(
                    {
                        "name": company,
                        "type": "company",
                        "transactionCount": profile.get("transaction_count", 0),
                        "totalIncome": profile.get("total_income", 0),
                    }
                )

            return {"success": True, "subjects": subjects}
        except Exception as e:
            logging.getLogger(__name__).warning(f"读取缓存失败: {e}")

    return {"success": True, "subjects": []}


@app.get("/api/cache/info")
async def get_cache_info():
    """获取缓存信息（用于调试和监控）"""
    cache_dir = os.path.join("output", "analysis_cache")
    try:
        cache_mgr = CacheManager(cache_dir)
        cache_info = cache_mgr.get_cache_info()
        return {"success": True, "data": cache_info}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/cache/invalidate")
async def invalidate_cache(cache_name: Optional[str] = None):
    """
    失效指定的缓存文件

    Args:
        cache_name: 缓存名称（如 'profiles'），None 表示失效所有缓存
    """
    cache_dir = os.path.join("output", "analysis_cache")
    try:
        cache_mgr = CacheManager(cache_dir)
        if cache_name:
            cache_mgr.invalidate(cache_name)
            return {"success": True, "message": f"已失效缓存: {cache_name}"}
        else:
            cache_mgr.clear_all()
            return {"success": True, "message": "已清除所有缓存"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 归集配置 API (Primary Targets) ====================


@app.get("/api/primary-targets")
async def get_primary_targets_config():
    """
    获取当前归集配置

    如果配置不存在，自动生成默认配置
    """
    logger = logging.getLogger(__name__)
    logger.info("[归集配置] 获取配置")

    try:
        service = PrimaryTargetsService(data_dir="./data", output_dir="./output")
        config, msg, is_new = service.get_or_create_config()

        if config is None:
            logger.warning(f"[归集配置] 加载失败: {msg}")
            return {"success": False, "error": msg, "config": None}

        logger.info(
            f"[归集配置] 加载成功: {len(config.analysis_units)} 个分析单元, is_new={is_new}"
        )

        return {
            "success": True,
            "config": config.to_dict(),
            "is_new": is_new,
            "message": msg,
        }

    except Exception as e:
        logger.exception(f"[归集配置] 获取失败: {e}")
        return {"success": False, "error": str(e), "config": None}


@app.get("/api/primary-targets/entities")
async def get_primary_targets_entities():
    """
    获取可用的实体列表（人员和公司）

    用于前端归集配置界面显示可选择的对象
    """
    logger = logging.getLogger(__name__)
    logger.info("[归集配置] 获取实体列表")

    try:
        service = PrimaryTargetsService(data_dir="./data", output_dir="./output")
        result = service.get_entities_with_data_status()

        logger.info(
            f"[归集配置] 实体: {len(result.get('persons', []))} 人员, "
            f"{len(result.get('companies', []))} 公司"
        )

        return {
            "success": True,
            "persons": result.get("persons", []),
            "companies": result.get("companies", []),
            "family_summary": result.get("family_summary"),
        }

    except Exception as e:
        logger.exception(f"[归集配置] 获取实体失败: {e}")
        return {"success": False, "error": str(e), "persons": [], "companies": []}


@app.post("/api/primary-targets")
async def save_primary_targets_config(request: Request):
    """
    保存归集配置
    """
    logger = logging.getLogger(__name__)
    logger.info("[归集配置] 保存配置")

    try:
        config_dict = await request.json()

        # 从字典构建配置对象
        from report_config.primary_targets_schema import PrimaryTargetsConfig

        config = PrimaryTargetsConfig.from_dict(config_dict)

        # 保存配置
        service = PrimaryTargetsService(data_dir="./data", output_dir="./output")
        success, msg = service.save_config(config)

        if success:
            logger.info(f"[归集配置] 保存成功: {msg}")
            return {"success": True, "message": msg}
        else:
            logger.warning(f"[归集配置] 保存失败: {msg}")
            return {"success": False, "error": msg}

    except Exception as e:
        logger.exception(f"[归集配置] 保存失败: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/primary-targets/generate-default")
async def generate_default_primary_targets():
    """
    重新生成默认归集配置

    根据 analysis_cache 中的数据生成配置
    """
    logger = logging.getLogger(__name__)
    logger.info("[归集配置] 重新生成默认配置")

    try:
        service = PrimaryTargetsService(data_dir="./data", output_dir="./output")
        config, msg = service.generate_default_config()

        if config is None:
            logger.warning(f"[归集配置] 生成失败: {msg}")
            return {"success": False, "error": msg, "config": None}

        logger.info(f"[归集配置] 生成成功: {len(config.analysis_units)} 个分析单元")

        return {"success": True, "config": config.to_dict(), "message": msg}

    except Exception as e:
        logger.exception(f"[归集配置] 生成失败: {e}")
        return {"success": False, "error": str(e), "config": None}


# ==================== 报告文件访问 API ====================


@app.get("/api/reports")
async def get_report_files():
    """
    获取已生成的报告文件列表（递归扫描所有子目录）

    返回 output/analysis_results 目录下的所有报告文件（包括子目录）
    """
    logger = logging.getLogger(__name__)
    results_dir = os.path.join("output", "analysis_results")

    if not os.path.exists(results_dir):
        return {"success": True, "reports": [], "message": "报告目录不存在"}

    reports = []

    # 定义报告类型映射
    report_types = {
        ".txt": "text",
        ".html": "html",
        ".xlsx": "excel",
        ".md": "markdown",
        ".pdf": "pdf",
    }

    def scan_directory(directory, prefix=""):
        """递归扫描目录"""
        if not os.path.exists(directory):
            return

        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            relative_path = os.path.relpath(item_path, results_dir)

            if os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                if ext in report_types:
                    stat = os.stat(item_path)
                    # 在子目录中的文件，添加子目录前缀
                    display_name = item if prefix == "" else f"{prefix}/{item}"

                    reports.append(
                        {
                            "filename": display_name,
                            "type": report_types[ext],
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(
                                stat.st_mtime
                            ).isoformat(),
                            "path": item_path,
                        }
                    )
            elif os.path.isdir(item_path):
                # 递归扫描子目录
                scan_directory(
                    item_path, prefix=item if prefix == "" else f"{prefix}/{item}"
                )

    try:
        scan_directory(results_dir)

        # 按修改时间排序（最新的在前）
        reports.sort(key=lambda x: x["modified"], reverse=True)

        logger.info(f"[报告列表] 找到 {len(reports)} 个报告文件")
        return {"success": True, "reports": reports}
    except Exception as e:
        logger.exception(f"[报告列表] 获取失败: {e}")
        return {"success": False, "reports": [], "error": str(e)}


@app.get("/api/reports/preview/{filename:path}")
async def preview_report_file(filename: str):
    """
    预览报告文件内容

    Args:
        filename: 报告文件名

    Returns:
        文件内容（txt/html/md）或下载链接（xlsx）
    """
    logger = logging.getLogger(__name__)

    # 安全检查：防止路径遍历攻击
    safe_filename = os.path.basename(filename)
    filepath = os.path.join("output", "analysis_results", safe_filename)

    if not os.path.exists(filepath):
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"文件不存在: {safe_filename}"},
        )

    ext = os.path.splitext(safe_filename)[1].lower()

    try:
        if ext == ".txt" or ext == ".md":
            # 文本文件，直接返回内容
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "success": True,
                "filename": safe_filename,
                "type": "text",
                "content": content,
            }

        elif ext == ".html":
            # HTML 文件，返回完整 HTML
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return Response(content=content, media_type="text/html; charset=utf-8")

        elif ext == ".xlsx":
            # Excel 文件，返回下载链接
            return {
                "success": True,
                "filename": safe_filename,
                "type": "excel",
                "download_url": f"/api/reports/download/{safe_filename}",
                "message": "Excel 文件请使用下载链接",
            }

        else:
            return {"success": False, "error": f"不支持预览的文件类型: {ext}"}

    except Exception as e:
        logger.exception(f"[报告预览] 读取失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"读取文件失败: {str(e)}"},
        )


@app.get("/api/reports/download/{filename:path}")
async def download_report_file(filename: str):
    """
    下载报告文件

    Args:
        filename: 报告文件名
    """
    from fastapi.responses import FileResponse

    # 安全检查
    safe_filename = os.path.basename(filename)
    filepath = os.path.join("output", "analysis_results", safe_filename)

    if not os.path.exists(filepath):
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"文件不存在: {safe_filename}"},
        )

    return FileResponse(
        path=filepath, filename=safe_filename, media_type="application/octet-stream"
    )


# ==================== 报告生成 API (v3.0 新架构) ====================


class InvestigationReportRequest(BaseModel):
    """v3.0 报告生成请求"""

    case_background: Optional[str] = None
    data_scope: Optional[str] = None


@app.post("/api/investigation-report/generate-with-config")
async def generate_investigation_report_with_config(
    request: InvestigationReportRequest = None,
):
    """
    【G-05】按归集配置生成初查报告 (v3.0 新架构)

    根据 primary_targets.json 中的分析单元配置组织报告章节：
    - 核心家庭单元（family）: 聚合成员数据，生成合并章节
    - 独立关联单元（independent）: 每个成员独立成章

    Returns:
        {
            "success": True,
            "report": { InvestigationReport 完整结构 },
            "message": "报告生成成功"
        }
    """
    logger = logging.getLogger(__name__)
    logger.info("[报告生成] 开始按配置生成 v3.0 报告")

    try:
        # 1. 加载归集配置服务
        service = PrimaryTargetsService(data_dir="./data", output_dir="./output")

        # 2. 获取或创建归集配置
        config, msg, is_new = service.get_or_create_config()
        if config is None:
            logger.warning(f"[报告生成] 归集配置加载失败: {msg}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"归集配置加载失败: {msg}"},
            )

        logger.info(
            f"[报告生成] 配置加载成功: {len(config.analysis_units)} 个分析单元, is_new={is_new}"
        )

        # 3. 加载报告构建器
        builder = load_investigation_report_builder("./output")
        if builder is None:
            logger.warning("[报告生成] 缓存数据不存在，请先运行分析")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "分析缓存不存在，请先运行分析"},
            )

        # 【v4.1 新增】设置用户配置到报告构建器
        builder.set_primary_config(config)
        logger.info(
            f"[报告生成] 已设置用户配置: {len(config.analysis_units)} 个分析单元"
        )

        # 【v4.1 新增】根据用户配置重新计算家庭汇总
        logger.info("[报告生成] 检测到用户配置，重新计算家庭汇总...")

        # 4.1. 加载 profiles.json
        cache_dir = os.path.join("./output", "analysis_cache")
        with open(os.path.join(cache_dir, "profiles.json"), "r", encoding="utf-8") as f:
            profiles = json.load(f)

        # 4.2. 重新计算每个家庭的汇总
        from family_finance import calculate_family_summary

        updated_family_summaries = {}
        for unit in config.analysis_units:
            if unit.unit_type == "family":
                householder = unit.anchor
                members = unit.members

                # 重新计算家庭财务汇总
                try:
                    unit_summary = calculate_family_summary(profiles, members)
                    unit_summary["householder"] = householder
                    updated_family_summaries[householder] = unit_summary
                    logger.info(f"[家庭汇总] 已重新计算 {householder} 家庭汇总")
                except Exception as e:
                    logger.warning(f"计算 {householder} 家庭汇总失败: {e}")

        # 4.3. 更新 derived_data.json
        if updated_family_summaries:
            with open(
                os.path.join(cache_dir, "derived_data.json"), "r+", encoding="utf-8"
            ) as f:
                derived_data = json.load(f)

                # 保留原有数据
                derived_data["all_family_summaries"] = updated_family_summaries

                # 更新第一个家庭的summary（用于旧版兼容）
                first_householder = list(updated_family_summaries.keys())[0]
                derived_data["family_summary"] = updated_family_summaries[
                    first_householder
                ]

                f.seek(0)
                f.truncate()  # 截断文件，避免旧数据残留
                json.dump(derived_data, f, ensure_ascii=False, indent=2)

            logger.info(f"[家庭汇总] 已更新: {len(updated_family_summaries)} 个家庭")

        # 【v4.1 修复】重新加载 builder，确保使用更新后的缓存数据
        logger.info("[报告生成] 重新加载 builder（使用更新后的缓存数据）")
        builder = load_investigation_report_builder("./output")

        if builder is None:
            logger.warning("[报告生成] 缓存数据不存在，请先运行分析")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "分析缓存不存在，请先运行分析"},
            )

        builder.set_primary_config(config)
        logger.info(
            f"[报告生成] 已设置用户配置: {len(config.analysis_units)} 个分析单元"
        )

        report = builder.build_report_with_config(
            config=config,
            case_background=case_background or config.case_notes,
            data_scope=data_scope,
        )

        logger.info(f"[报告生成] v3.0 报告生成成功")

        return {
            "success": True,
            "report": report,
            "message": "报告生成成功",
            "config_info": {
                "analysis_units_count": len(config.analysis_units),
                "doc_number": config.doc_number,
                "employer": config.employer,
            },
        }

    except Exception as e:
        logger.exception(f"[报告生成] 生成失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"报告生成失败: {str(e)}"},
        )


@app.post("/api/investigation-report/save-html")
async def save_html_report(request: dict):
    """
    保存HTML报告到输出目录

    前端生成的HTML报告，保存到 output/analysis_results/ 目录
    """
    logger = logging.getLogger(__name__)
    logger.info("[报告保存] 开始保存HTML报告")

    try:
        html_content = request.get("html", "")
        filename = request.get("filename", "初查报告.html")

        if not html_content:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "HTML内容为空"},
            )

        # 保存到输出目录
        reports_dir = os.path.join("output", "analysis_results")
        os.makedirs(reports_dir, exist_ok=True)

        filepath = os.path.join(reports_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"[报告保存] HTML已保存: {filepath}")
        return {"success": True, "path": filepath, "message": "HTML保存成功"}

    except Exception as e:
        logger.exception(f"[报告保存] 保存失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"保存失败: {str(e)}"},
        )


@app.post("/api/investigation-report/regenerate-txt")
async def regenerate_txt_report():
    """
    【v4.1 新增】根据用户配置重新生成txt报告

    1. 加载 PrimaryTargetsConfig（用户配置）
    2. 使用配置中的家庭单元重新生成txt报告
    3. 更新 output/analysis_results/核查结果分析报告.txt

    Returns:
        {"success": True, "message": "txt报告重新生成成功"}
    """
    logger = logging.getLogger(__name__)
    logger.info("[txt报告] 开始根据用户配置重新生成")

    try:
        # 1. 加载归集配置
        service = PrimaryTargetsService(data_dir="./data", output_dir="./output")
        config, msg = service.load_config()

        if config is None:
            logger.warning(f"[txt报告] 配置加载失败: {msg}，生成默认配置")
            config, msg, _ = service.get_or_create_config()

        # 2. 加载报告构建器
        builder = load_investigation_report_builder("./output")
        if builder is None:
            logger.warning("[txt报告] 缓存数据不存在")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "分析缓存不存在，请先运行分析"},
            )

        # 3. 【关键】设置用户配置到报告构建器
        builder.set_primary_config(config)
        logger.info(
            f"[txt报告] 已设置用户配置: {len(config.analysis_units)} 个分析单元"
        )

        # 4. 重新生成txt报告（会使用用户配置的家庭单元）
        output_dirs = create_output_directories("./output")
        txt_report_path = os.path.join(
            output_dirs["analysis_results"], "核查结果分析报告.txt"
        )

        result = builder.generate_complete_txt_report(txt_report_path)

        logger.info(f"[txt报告] 重新生成成功: {txt_report_path}")
        return {
            "success": True,
            "message": "txt报告重新生成成功",
            "path": txt_report_path,
            "config_info": {
                "analysis_units_count": len(config.analysis_units),
                "doc_number": config.doc_number,
                "employer": config.employer,
            },
        }

    except Exception as e:
        logger.exception(f"[txt报告] 重新生成失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"txt报告重新生成失败: {str(e)}"},
        )


class LegacyReportGenerateRequest(BaseModel):
    """传统报告生成请求"""

    sections: List[str] = ["summary", "assets", "risks"]
    format: str = "html"  # html / json
    case_name: str = "初查报告"
    subjects: List[str] = []
    doc_number: Optional[str] = None
    thresholds: Optional[Dict[str, float]] = None
    primary_person: Optional[str] = None
    case_background: Optional[str] = None


@app.post("/api/reports/generate")
async def generate_legacy_report(request: LegacyReportGenerateRequest):
    """
    传统报告生成 API

    支持 html / json 格式输出
    """
    logger = logging.getLogger(__name__)
    logger.info(
        f"[报告生成] 传统报告生成请求: format={request.format}, subjects={request.subjects}"
    )

    try:
        # 1. 加载报告构建器
        builder = load_investigation_report_builder("./output")
        if builder is None:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "分析缓存不存在，请先运行分析"},
            )

        # 2. 确定核查对象
        primary_person = request.primary_person
        if not primary_person and request.subjects:
            primary_person = request.subjects[0]
        if not primary_person:
            # 使用第一个可用的人员
            available_persons = [p for p in builder._core_persons if p]
            if available_persons:
                primary_person = available_persons[0]
            else:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "未找到可用的核查对象"},
                )

        # 3. 生成报告
        report = builder.build_complete_report(
            primary_person=primary_person,
            doc_number=request.doc_number,
            case_background=request.case_background or request.case_name,
            include_companies=request.subjects if request.subjects else None,
        )

        # 4. 根据格式返回
        if request.format == "json":
            return {
                "success": True,
                "format": "json",
                "report": report,
                "message": "报告生成成功",
            }
        else:
            # 生成 HTML 预览
            html_content = _render_report_to_html(report)
            return Response(content=html_content, media_type="text/html; charset=utf-8")

    except Exception as e:
        logger.exception(f"[报告生成] 传统报告生成失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"报告生成失败: {str(e)}"},
        )


def _render_report_to_html(report: Dict) -> str:
    """将报告字典渲染为 HTML"""
    meta = report.get("meta", {})
    family = report.get("family", {})
    member_details = report.get("member_details", [])
    conclusion = report.get("conclusion", {})

    # 格式化金额
    def format_amount(amount):
        if amount is None:
            return "0"
        return f"{amount:,.2f}" if isinstance(amount, (int, float)) else str(amount)

    def format_wan(amount):
        if amount is None:
            return "0.00"
        return (
            f"{amount / 10000:,.2f}"
            if isinstance(amount, (int, float))
            else str(amount)
        )

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>初查报告 - {meta.get("doc_number", "")}</title>
        <style>
            body {{ font-family: "SimSun", "Songti SC", serif; background: #f5f5f5; padding: 20px; margin: 0; }}
            .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ text-align: center; font-size: 24px; margin-bottom: 30px; }}
            h2 {{ font-size: 18px; border-bottom: 2px solid #333; padding-bottom: 5px; margin-top: 30px; }}
            h3 {{ font-size: 16px; margin-top: 20px; }}
            .meta {{ background: #f9f9f9; padding: 15px; margin-bottom: 20px; border-left: 4px solid #0066cc; }}
            .meta p {{ margin: 5px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background: #f0f0f0; font-weight: bold; }}
            .amount {{ text-align: right; font-family: monospace; }}
            .highlight {{ color: #c00; font-weight: bold; }}
            .issue {{ background: #fff0f0; padding: 10px; margin: 10px 0; border-left: 4px solid #c00; }}
            .issue.high {{ border-color: #c00; }}
            .issue.medium {{ border-color: #f90; }}
            .issue.low {{ border-color: #090; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>资金穿透审计初查报告</h1>
             
            <div class="meta">
                <p><strong>文号：</strong>{meta.get("doc_number", "待填写")}</p>
                <p><strong>生成时间：</strong>{meta.get("generated_at", "")}</p>
                <p><strong>数据范围：</strong>{meta.get("data_scope", "待补充")}</p>
                <p><strong>案件背景：</strong>{meta.get("case_background", "")}</p>
            </div>
             
            <h2>一、家庭基本情况</h2>
            <p>核查对象：<strong>{family.get("primary_person", "")}</strong></p>
            <p>家庭成员共 {len(family.get("members", []))} 人</p>
             
            <table>
                <tr><th>姓名</th><th>关系</th><th>有流水数据</th></tr>
    """

    for m in family.get("members", []):
        has_data = "✓" if m.get("has_data") else "✗"
        html += f"<tr><td>{m.get('name', '')}</td><td>{m.get('relation', '')}</td><td>{has_data}</td></tr>"

    # 家庭汇总 - 修复数据单位为万元
    summary = family.get("summary", {})
    html += f"""
            </table>
             
            <h3>家庭财务汇总</h3>
            <table>
                <tr><th>项目</th><th>金额（万元）</th></tr>
                <tr><td>总收入</td><td class="amount">{format_wan(summary.get("total_income", 0))}</td></tr>
                <tr><td>总支出</td><td class="amount">{format_wan(summary.get("total_expense", 0))}</td></tr>
                <tr><td>净收入（剔除互转）</td><td class="amount">{format_wan(summary.get("net_income", 0))}</td></tr>
                <tr><td>家庭内部互转</td><td class="amount">{format_wan(summary.get("internal_transfers", 0))}</td></tr>
            </table>
             
            <h3>家庭年度工资收入（按年统计）</h3>
            <table>
                <tr><th>年份</th><th>家庭总工资(万元)</th></tr>
    """

    # 提取年度工资数据
    family_yearly_salary = {}
    for md in member_details:
        assets = md.get("assets", {})
        yearly_salary_list = assets.get("yearly_salary", [])
        for ys in yearly_salary_list:
            year = ys.get("year", "")
            if year:
                if year not in family_yearly_salary:
                    family_yearly_salary[year] = 0
                family_yearly_salary[year] += ys.get("total", 0)

    # 按年份排序并添加到HTML
    for year in sorted(family_yearly_salary.keys()):
        total_wan = family_yearly_salary[year] / 10000
        html += f"<tr><td>{year}</td><td class='amount'>{total_wan:.2f}</td></tr>"

    html += """
            </table>
            
            <h2>二、成员详细分析</h2>
    """

    for i, md in enumerate(member_details, 1):
        html += f"""
            <h3>{i}. {md.get("name", "")} ({md.get("relation", "")})</h3>
            <table>
                <tr><th>项目</th><th>数值</th></tr>
                <tr><td>总收入</td><td class="amount">{format_wan(md.get("total_income", 0))} 万元</td></tr>
                <tr><td>总支出</td><td class="amount">{format_wan(md.get("total_expense", 0))} 万元</td></tr>
                <tr><td>交易笔数</td><td>{md.get("transaction_count", 0)}</td></tr>
            </table>
        """

        # 资产信息
        assets = md.get("assets", {})
        if assets:
            salary_ratio = assets.get("salary_ratio", 0)
            # 统一处理：salaryRatio 是小数形式（如 0.2396 = 23.96%），需要乘以100
            salary_ratio_percent = salary_ratio * 100
            html += f"""
            <p><strong>资产情况：</strong></p>
            <ul>
                <li>工资总额: {format_wan(assets.get("salary_total", 0))} 万元</li>
                <li>工资占比: {salary_ratio_percent:.1f}%</li>
                <li>银行账户数: {assets.get("bank_account_count", 0)}</li>
                <li>理财持仓: {format_wan(assets.get("wealth_holding", 0))} 万元</li>
            </ul>
            """

    # 综合研判
    html += f"""
            <h2>三、综合研判</h2>
            <p>{conclusion.get("summary_text", "待补充研判意见")}</p>
             
            <h3>发现问题</h3>
    """

    issues = conclusion.get("issues", [])
    if issues:
        for issue in issues:
            severity = issue.get("severity", "medium")
            html += f"""
            <div class="issue {severity}">
                <strong>[{issue.get("issue_type", "")}]</strong> {issue.get("person", "")}：
                {issue.get("description", "")}
            </div>
            """
    else:
        html += "<p>暂无明显问题</p>"

    # 下一步建议
    next_steps = conclusion.get("next_steps", [])
    if next_steps:
        html += "<h3>下一步建议</h3><ul>"
        for step in next_steps:
            html += f"<li>{step}</li>"
        html += "</ul>"

    html += """
        </div>
    </body>
    </html>
    """

    return html


class OpenFolderRequest(BaseModel):
    """打开文件夹请求"""

    relativePath: str


@app.post("/api/open-folder")
async def open_folder(request: OpenFolderRequest):
    """在系统文件管理器中打开指定文件夹"""
    import subprocess
    import platform

    # 构建绝对路径
    folder_path = os.path.abspath(request.relativePath)

    # 检查路径是否存在
    if not os.path.exists(folder_path):
        raise HTTPException(
            status_code=404, detail=f"路径不存在: {request.relativePath}"
        )

    # 如果是文件，获取其父目录
    if os.path.isfile(folder_path):
        folder_path = os.path.dirname(folder_path)

    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["open", folder_path], check=True)
        elif system == "Windows":
            # 使用 os.startfile 打开文件夹，窗口会跳到前台
            os.startfile(folder_path)
        else:  # Linux
            subprocess.run(["xdg-open", folder_path], check=True)

        return {"success": True, "path": folder_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开文件夹失败: {str(e)}")


@app.get("/api/analysis/graph-data")
async def get_graph_data():
    """获取图谱可视化数据"""
    if analysis_state.status != "completed" or not analysis_state.results:
        raise HTTPException(status_code=400, detail="分析尚未完成")

    results = analysis_state.results
    persons = results.get("persons", [])
    companies = results.get("companies", [])

    # 从缓存结果中获取图谱数据
    graph_cache = results.get("graphData", {})
    nodes = graph_cache.get("nodes", [])
    edges = graph_cache.get("edges", [])

    # 构建完整的统计信息（前端 GraphData 接口要求）
    stats = {
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "corePersonCount": len(persons),
        "corePersonNames": persons,
        "involvedCompanyCount": len(companies),
        "highRiskCount": 0,
        "mediumRiskCount": 0,
        "loanPairCount": 0,
        "noRepayCount": 0,
        "coreEdgeCount": 0,
        "companyEdgeCount": 0,
        "otherEdgeCount": len(edges),
    }

    # 构建报告数据结构（前端 GraphData.report 接口要求）
    report = {
        "loan_pairs": [],
        "no_repayment_loans": [],
        "high_risk_income": [],
        "online_loans": [],
    }

    # 构建采样信息
    sampling = {
        "totalNodes": len(nodes),
        "totalEdges": len(edges),
        "sampledNodes": len(nodes),
        "sampledEdges": len(edges),
        "message": "完整数据",
    }

    # 返回前端期望的格式: { message: 'success', data: { nodes, edges, stats, sampling, report } }
    return serialize_for_json(
        {
            "message": "success",
            "data": {
                "nodes": nodes,
                "edges": edges,
                "stats": stats,
                "sampling": sampling,
                "report": report,
            },
        }
    )


@app.get("/api/audit-navigation")
async def get_audit_navigation():
    """获取审计导航结构（包含文件夹路径和报告列表）"""
    if analysis_state.status != "completed" or not analysis_state.results:
        raise HTTPException(status_code=400, detail="分析尚未完成")

    results = analysis_state.results
    persons = results.get("persons", [])
    companies = results.get("companies", [])

    # 定义输出目录路径（相对路径，与 config.py 一致）
    output_dir = "output"
    cleaned_data_person_dir = os.path.join(output_dir, "cleaned_data", "个人")
    cleaned_data_company_dir = os.path.join(output_dir, "cleaned_data", "公司")
    analysis_results_dir = os.path.join(output_dir, "analysis_results")

    # 构建个人清洗数据列表
    person_files = []
    if os.path.exists(cleaned_data_person_dir):
        for filename in os.listdir(cleaned_data_person_dir):
            if filename.endswith(".xlsx"):
                filepath = os.path.join(cleaned_data_person_dir, filename)
                stat_info = os.stat(filepath)
                # 提取人名（假设格式为 "姓名_合并流水.xlsx"）
                name = filename.replace("_合并流水.xlsx", "").replace(".xlsx", "")
                person_files.append(
                    {
                        "name": name,
                        "filename": filename,
                        "size": stat_info.st_size,
                        "sizeFormatted": f"{stat_info.st_size / 1024:.1f}KB"
                        if stat_info.st_size < 1024 * 1024
                        else f"{stat_info.st_size / 1024 / 1024:.1f}MB",
                        "modified": datetime.fromtimestamp(
                            stat_info.st_mtime
                        ).isoformat(),
                    }
                )

    # 构建公司清洗数据列表
    company_files = []
    if os.path.exists(cleaned_data_company_dir):
        for filename in os.listdir(cleaned_data_company_dir):
            if filename.endswith(".xlsx"):
                filepath = os.path.join(cleaned_data_company_dir, filename)
                stat_info = os.stat(filepath)
                name = filename.replace("_合并流水.xlsx", "").replace(".xlsx", "")
                company_files.append(
                    {
                        "name": name,
                        "filename": filename,
                        "size": stat_info.st_size,
                        "sizeFormatted": f"{stat_info.st_size / 1024:.1f}KB"
                        if stat_info.st_size < 1024 * 1024
                        else f"{stat_info.st_size / 1024 / 1024:.1f}MB",
                        "modified": datetime.fromtimestamp(
                            stat_info.st_mtime
                        ).isoformat(),
                    }
                )

    # 构建报告文件列表
    report_files = []
    primary_report_patterns = ["核查底稿", "审计报告", "report"]
    if os.path.exists(analysis_results_dir):
        for filename in os.listdir(analysis_results_dir):
            if filename.endswith((".xlsx", ".html", ".docx", ".txt", ".pdf")):
                filepath = os.path.join(analysis_results_dir, filename)
                stat_info = os.stat(filepath)
                is_primary = any(p in filename.lower() for p in primary_report_patterns)
                report_files.append(
                    {
                        "name": filename,
                        "size": stat_info.st_size,
                        "sizeFormatted": f"{stat_info.st_size / 1024:.1f}KB"
                        if stat_info.st_size < 1024 * 1024
                        else f"{stat_info.st_size / 1024 / 1024:.1f}MB",
                        "modified": datetime.fromtimestamp(
                            stat_info.st_mtime
                        ).isoformat(),
                        "isPrimary": is_primary,
                    }
                )
        # 主要报告排在前面
        report_files.sort(key=lambda x: (not x["isPrimary"], x["name"]))

    return serialize_for_json(
        {
            "persons": person_files
            if person_files
            else [{"name": p, "type": "person"} for p in persons],
            "companies": company_files
            if company_files
            else [{"name": c, "type": "company"} for c in companies],
            "reports": report_files,
            "outputDir": output_dir,
            "paths": {
                "cleanedDataPerson": cleaned_data_person_dir,
                "cleanedDataCompany": cleaned_data_company_dir,
                "analysisResults": analysis_results_dir,
            },
            "totalEntities": len(persons) + len(companies),
        }
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时日志推送

    消息格式 (与前端 WebSocketMessage 接口对齐):
    {
        "type": "status" | "complete" | "log",
        "data": { status, progress, currentPhase, startTime, endTime, error }
    }
    """
    await websocket.accept()
    _ws_connections.add(websocket)
    last_status = None

    try:
        while True:
            # 1. 发送所有待发送的日志消息
            while not _log_queue.empty():
                try:
                    log_message = _log_queue.get_nowait()
                    await websocket.send_json(log_message)
                except queue.Empty:
                    break

            # 2. 发送状态更新
            state_dict = analysis_state.to_dict()

            # 将 phase 映射为 currentPhase 以匹配前端 AnalysisStatus 接口
            message_data = {
                "status": state_dict.get("status"),
                "progress": state_dict.get("progress"),
                "currentPhase": state_dict.get("phase", ""),
                "startTime": state_dict.get("startTime"),
                "endTime": state_dict.get("endTime"),
                "error": state_dict.get("error"),
            }

            # 判断消息类型
            current_status = state_dict.get("status")

            if current_status == "completed":
                # 状态为 completed，总是发送 complete 消息
                # 修复：确保前端总是能收到 complete 消息并自动加载数据
                message = {"type": "complete", "data": message_data}
            else:
                # 发送普通状态更新
                message = {"type": "status", "data": message_data}

            last_status = current_status
            await websocket.send_json(message)
            await asyncio.sleep(0.5)  # 缩短间隔以更快地推送日志
    except WebSocketDisconnect:
        _ws_connections.discard(websocket)


# ==================== 启动服务器 ====================
if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
