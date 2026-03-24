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

from __future__ import annotations

import asyncio
import faulthandler
import sys
import warnings
import os
import json
import http.client
import re
import shutil
import logging
import math
import subprocess
import traceback
import importlib
from html import escape as html_escape
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from functools import lru_cache
import threading
import queue
import pandas as pd
import time
from urllib.parse import quote


_STARTUP_FATAL_LOG_NAME = "startup_fatal.log"
_startup_fault_log_handle = None


def _startup_diagnostics_root() -> Path:
    env_override = os.environ.get("FPAS_STARTUP_DIAGNOSTICS_ROOT", "").strip()
    if env_override:
        return Path(env_override).expanduser().resolve()
    target = getattr(sys, "executable", "") or __file__
    return Path(target).resolve().parent


def _append_startup_diagnostics(message: str) -> None:
    try:
        log_path = _startup_diagnostics_root() / _STARTUP_FATAL_LOG_NAME
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(message)
            if not message.endswith("\n"):
                handle.write("\n")
    except OSError:
        pass


def _install_startup_diagnostics() -> None:
    global _startup_fault_log_handle
    log_path = _startup_diagnostics_root() / _STARTUP_FATAL_LOG_NAME

    try:
        _startup_fault_log_handle = open(log_path, "a", encoding="utf-8")
        _startup_fault_log_handle.write(
            "\n=== startup probe "
            f"{datetime.now().isoformat()} pid={os.getpid()} "
            f"frozen={getattr(sys, 'frozen', False)} "
            f"executable={getattr(sys, 'executable', '')} ===\n"
        )
        _startup_fault_log_handle.flush()
        faulthandler.enable(_startup_fault_log_handle, all_threads=True)
    except OSError:
        _startup_fault_log_handle = None

    def _startup_excepthook(exc_type, exc_value, exc_tb):
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _append_startup_diagnostics(
            "\n=== fatal startup exception "
            f"{datetime.now().isoformat()} ===\n{formatted}\n"
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _startup_excepthook


_install_startup_diagnostics()

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
from paths import APP_ROOT, DASHBOARD_DIST_DIR, DATA_DIR, OUTPUT_DIR
import utils
from utils.aggregation_view import (
    annotate_focus_entities_with_graph,
    build_aggregation_overview,
)
from utils.suspicion_text import (
    build_serialized_direct_transfer_dedupe_key,
    normalize_direct_transfer_description_text,
    score_direct_transfer_record,
)
from utils.safe_types import extract_id_from_filename

# 【修复】Python 3.14 导入路径修复：utils 导入后项目目录可能从 sys.path 消失
project_dir = str(APP_ROOT)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)


@lru_cache(maxsize=1)
def _load_report_generator():
    # Win7 打包态在服务启动阶段导入 openpyxl 容易触发 MemoryError。
    return importlib.import_module("report_generator")


@lru_cache(maxsize=1)
def _load_data_extractor():
    # PDF 线索提取链会加载 pdfplumber/pdfminer，按需导入避免阻塞 Win7 启动。
    return importlib.import_module("data_extractor")


@lru_cache(maxsize=1)
def _load_asset_extractor():
    # 房产提取链同样依赖 pdfplumber，不能放在 Win7 冻结包启动路径上。
    return importlib.import_module("asset_extractor")


@lru_cache(maxsize=1)
def _load_wallet_report_builder():
    # 电子钱包 Excel 产物链路同样依赖 openpyxl，按需加载避免阻塞启动。
    return importlib.import_module("wallet_report_builder")


@lru_cache(maxsize=1)
def _load_investigation_report_builder_module():
    # 完整报告构建器模块体量很大，不应阻塞 Win7 服务冷启动。
    return importlib.import_module("investigation_report_builder")


def InvestigationReportBuilder(*args, **kwargs):
    return _load_investigation_report_builder_module().InvestigationReportBuilder(
        *args, **kwargs
    )


def load_investigation_report_builder(*args, **kwargs):
    return _load_investigation_report_builder_module().load_investigation_report_builder(
        *args, **kwargs
    )


@lru_cache(maxsize=1)
def _load_primary_targets_service_module():
    return importlib.import_module("report_config.primary_targets_service")


def PrimaryTargetsService(*args, **kwargs):
    return _load_primary_targets_service_module().PrimaryTargetsService(*args, **kwargs)


@lru_cache(maxsize=1)
def _load_specialized_reports_module():
    return importlib.import_module("specialized_reports")


def SpecializedReportGenerator(*args, **kwargs):
    return _load_specialized_reports_module().SpecializedReportGenerator(
        *args, **kwargs
    )


@lru_cache(maxsize=1)
def _load_suspicion_engine_module():
    return importlib.import_module("suspicion_engine")


def SuspicionEngine(*args, **kwargs):
    return _load_suspicion_engine_module().SuspicionEngine(*args, **kwargs)


@lru_cache(maxsize=1)
def _load_report_quality_guard_module():
    return importlib.import_module("report_quality_guard")


def _get_report_qa_guard_version() -> str:
    return _load_report_quality_guard_module().REPORT_QA_GUARD_VERSION


@lru_cache(maxsize=1)
def _load_report_text_formatter_module():
    return importlib.import_module("report_text_formatter")


def format_report_qa_check_display(*args, **kwargs):
    return _load_report_text_formatter_module().format_report_qa_check_display(
        *args, **kwargs
    )


class _LazyModuleProxy:
    def __init__(self, module_name: str):
        object.__setattr__(self, "_module_name", module_name)
        object.__setattr__(self, "_module", None)

    def _load(self):
        module = object.__getattribute__(self, "_module")
        if module is None:
            module = importlib.import_module(object.__getattribute__(self, "_module_name"))
            object.__setattr__(self, "_module", module)
        return module

    def __getattr__(self, name):
        return getattr(self._load(), name)

    def __setattr__(self, name, value):
        setattr(self._load(), name, value)

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(dir(self._load())))


def _lazy_module(module_name: str):
    return _LazyModuleProxy(module_name)


def _lazy_constructor(module_name: str, attr_name: str):
    def _factory(*args, **kwargs):
        target = getattr(importlib.import_module(module_name), attr_name)
        return target(*args, **kwargs)

    return _factory


file_categorizer = _lazy_module("file_categorizer")
data_cleaner = _lazy_module("data_cleaner")
financial_profiler = _lazy_module("financial_profiler")
suspicion_detector = _lazy_module("suspicion_detector")
family_analyzer = _lazy_module("family_analyzer")
asset_analyzer = _lazy_module("asset_analyzer")
data_validator = _lazy_module("data_validator")
fund_penetration = _lazy_module("fund_penetration")
related_party_analyzer = _lazy_module("related_party_analyzer")
multi_source_correlator = _lazy_module("multi_source_correlator")
loan_analyzer = _lazy_module("loan_analyzer")
income_analyzer = _lazy_module("income_analyzer")
salary_analyzer = _lazy_module("salary_analyzer")
flow_visualizer = _lazy_module("flow_visualizer")
ml_analyzer = _lazy_module("ml_analyzer")
time_series_analyzer = _lazy_module("time_series_analyzer")
clue_aggregator = _lazy_module("clue_aggregator")
behavioral_profiler = _lazy_module("behavioral_profiler")
api_validators = _lazy_module("api_validators")
logging_config = _lazy_module("logging_config")
pboc_account_extractor = _lazy_module("pboc_account_extractor")
aml_analyzer = _lazy_module("aml_analyzer")
company_info_extractor = _lazy_module("company_info_extractor")
credit_report_extractor = _lazy_module("credit_report_extractor")
bank_account_info_extractor = _lazy_module("bank_account_info_extractor")
tax_info_extractor = _lazy_module("tax_info_extractor")
vehicle_extractor = _lazy_module("vehicle_extractor")
wealth_product_extractor = _lazy_module("wealth_product_extractor")
securities_extractor = _lazy_module("securities_extractor")
insurance_extractor = _lazy_module("insurance_extractor")
immigration_extractor = _lazy_module("immigration_extractor")
hotel_extractor = _lazy_module("hotel_extractor")
cohabitation_extractor = _lazy_module("cohabitation_extractor")
railway_extractor = _lazy_module("railway_extractor")
flight_extractor = _lazy_module("flight_extractor")
wallet_data_extractor = _lazy_module("wallet_data_extractor")
wallet_risk_analyzer = _lazy_module("wallet_risk_analyzer")
family_assets_helper = _lazy_module("family_assets_helper")
family_finance = _lazy_module("family_finance")

RealSalaryIncomeAnalyzer = _lazy_constructor(
    "real_salary_income_analyzer", "RealSalaryIncomeAnalyzer"
)
FinancialProductAnalyzer = _lazy_constructor(
    "professional_finance_analyzer", "FinancialProductAnalyzer"
)
IncomeExpenseMatchAnalyzer = _lazy_constructor(
    "income_expense_match_analyzer", "IncomeExpenseMatchAnalyzer"
)
PersonalFundFeatureAnalyzer = _lazy_constructor(
    "personal_fund_feature_analyzer", "PersonalFundFeatureAnalyzer"
)

# 导入缓存管理器
from cache_manager import CacheManager

# 导入键名映射层
from adapters.key_mapper import to_camel_case

# ==================== Windows asyncio 兼容性修复 ====================
if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncio")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# ====================================================================


# ==================== 全局状态 ====================
# 【P1修复】添加缓存并发锁
_cache_lock = threading.Lock()


class AnalysisState:
    def __init__(self):
        self.status = "idle"
        self.progress = 0
        self.phase = ""
        self.start_time = None
        self.end_time = None
        self.results = None
        self.error = None
        self.stop_requested = False
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
                # 兼容前端字段命名（REST/WS 对齐）
                "currentPhase": self.phase,
                "startTime": self.start_time.isoformat() if self.start_time else None,
                "endTime": self.end_time.isoformat() if self.end_time else None,
                "error": self.error,
                "stopRequested": self.stop_requested,
            }

    def reset(self, phase: str = "等待开始分析"):
        """重置状态（清空内存结果）。"""
        with self._lock:
            self.status = "idle"
            self.progress = 0
            self.phase = phase
            self.start_time = None
            self.end_time = None
            self.results = None
            self.error = None
            self.stop_requested = False

    def request_stop(self):
        with self._lock:
            self.stop_requested = True

    def clear_stop_request(self):
        with self._lock:
            self.stop_requested = False

    def is_stop_requested(self) -> bool:
        with self._lock:
            return self.stop_requested


class AnalysisStoppedError(RuntimeError):
    """用于中断分析流程的显式停止异常。"""


analysis_state = AnalysisState()
_current_config = {}
_ws_connections = set()
_log_queue = queue.Queue()  # 日志队列，用于 WebSocket 广播
_cache_manager: Optional[CacheManager] = None  # 缓存管理器（懒加载）
APP_RELEASE_VERSION = "4.6.0"
_cli_entrypoint_invoked = False
_browser_auto_open_started = False
_browser_auto_open_lock = threading.Lock()


def _slugify_doc_heading(text: str) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", str(text or "").strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "section"


def _resolve_docs_link_target(url: str) -> str:
    target = str(url or "").strip()
    if not target:
        return "#"
    if re.match(r"^(?:https?:|mailto:|#)", target, flags=re.IGNORECASE):
        return target
    normalized = os.path.normpath(target).replace("\\", "/").lstrip("/")
    return f"/docs/file/{quote(normalized)}"


def _render_markdown_inline(text: str) -> str:
    pattern = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))")
    result: List[str] = []
    cursor = 0

    for match in pattern.finditer(text):
        if match.start() > cursor:
            result.append(html_escape(text[cursor : match.start()]))
        token = match.group(0)
        if token.startswith("`") and token.endswith("`"):
            result.append(f"<code>{html_escape(token[1:-1])}</code>")
        elif token.startswith("**") and token.endswith("**"):
            result.append(f"<strong>{html_escape(token[2:-2])}</strong>")
        else:
            link_match = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token)
            if link_match:
                label, url = link_match.groups()
                href = html_escape(_resolve_docs_link_target(url), quote=True)
                safe_label = html_escape(label)
                result.append(
                    f'<a href="{href}" target="_blank" rel="noreferrer">{safe_label}</a>'
                )
            else:
                result.append(html_escape(token))
        cursor = match.end()

    if cursor < len(text):
        result.append(html_escape(text[cursor:]))
    return "".join(result)


def _render_markdown_document(markdown_text: str, page_title: str) -> str:
    toc: List[Dict[str, str]] = []
    body_parts: List[str] = []
    paragraph_lines: List[str] = []
    unordered_items: List[str] = []
    ordered_items: List[str] = []
    quote_lines: List[str] = []
    code_lines: List[str] = []
    code_language = ""
    in_code_block = False

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = " ".join(line.strip() for line in paragraph_lines if line.strip())
        if text:
            body_parts.append(f"<p>{_render_markdown_inline(text)}</p>")
        paragraph_lines.clear()

    def flush_unordered_list() -> None:
        if not unordered_items:
            return
        body_parts.append(
            "<ul>" + "".join(f"<li>{item}</li>" for item in unordered_items) + "</ul>"
        )
        unordered_items.clear()

    def flush_ordered_list() -> None:
        if not ordered_items:
            return
        body_parts.append(
            "<ol>" + "".join(f"<li>{item}</li>" for item in ordered_items) + "</ol>"
        )
        ordered_items.clear()

    def flush_quote() -> None:
        if not quote_lines:
            return
        quote_html = "<br>".join(_render_markdown_inline(line) for line in quote_lines)
        body_parts.append(f"<blockquote>{quote_html}</blockquote>")
        quote_lines.clear()

    def flush_all() -> None:
        flush_paragraph()
        flush_unordered_list()
        flush_ordered_list()
        flush_quote()

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if in_code_block:
            if stripped.startswith("```"):
                safe_code = html_escape("\n".join(code_lines))
                language_attr = (
                    f' data-language="{html_escape(code_language)}"' if code_language else ""
                )
                body_parts.append(
                    f'<pre><code{language_attr}>{safe_code}</code></pre>'
                )
                code_lines.clear()
                code_language = ""
                in_code_block = False
            else:
                code_lines.append(line)
            continue

        if stripped.startswith("```"):
            flush_all()
            in_code_block = True
            code_language = stripped[3:].strip()
            continue

        if not stripped:
            flush_all()
            continue

        if stripped == "---":
            flush_all()
            body_parts.append("<hr>")
            continue

        image_match = re.match(r"^!\[(.*?)\]\((.*?)\)$", stripped)
        if image_match:
            flush_all()
            alt_text, image_url = image_match.groups()
            resolved_src = html_escape(_resolve_docs_link_target(image_url), quote=True)
            safe_alt = html_escape(alt_text or "文档配图")
            caption = f"<figcaption>{safe_alt}</figcaption>" if alt_text else ""
            body_parts.append(
                f'<figure><img src="{resolved_src}" alt="{safe_alt}" loading="lazy" />{caption}</figure>'
            )
            continue

        heading_match = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading_match:
            flush_all()
            level = min(len(heading_match.group(1)), 4)
            heading_text = heading_match.group(2).strip()
            anchor = _slugify_doc_heading(heading_text)
            toc.append(
                {
                    "level": str(level),
                    "text": heading_text,
                    "anchor": anchor,
                }
            )
            body_parts.append(
                f'<h{level} id="{anchor}">{_render_markdown_inline(heading_text)}</h{level}>'
            )
            continue

        unordered_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if unordered_match:
            flush_paragraph()
            flush_ordered_list()
            flush_quote()
            unordered_items.append(_render_markdown_inline(unordered_match.group(1)))
            continue

        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered_match:
            flush_paragraph()
            flush_unordered_list()
            flush_quote()
            ordered_items.append(_render_markdown_inline(ordered_match.group(1)))
            continue

        quote_match = re.match(r"^>\s?(.*)$", stripped)
        if quote_match:
            flush_paragraph()
            flush_unordered_list()
            flush_ordered_list()
            quote_lines.append(quote_match.group(1).strip())
            continue

        paragraph_lines.append(stripped)

    flush_all()

    toc_html = "".join(
        (
            f'<a class="toc-item level-{item["level"]}" href="#{item["anchor"]}">'
            f"{html_escape(item['text'])}</a>"
        )
        for item in toc
        if int(item["level"]) <= 3
    )
    page_title_html = html_escape(page_title)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{page_title_html}</title>
  <style>
    :root {{
      --bg: #07111d;
      --bg-soft: #0b1727;
      --panel: rgba(10, 19, 34, 0.9);
      --panel-strong: rgba(12, 22, 39, 0.96);
      --panel-muted: rgba(9, 17, 30, 0.72);
      --line: rgba(148, 163, 184, 0.16);
      --line-strong: rgba(125, 211, 252, 0.24);
      --text: #e8eef7;
      --text-soft: #dbe7f5;
      --muted: #9db4cb;
      --muted-strong: #bfd2e6;
      --accent: #67d4ff;
      --accent-strong: #22c3ee;
      --accent-soft: rgba(56, 189, 248, 0.12);
      --accent-glow: rgba(34, 195, 238, 0.2);
      --code: #08111d;
      --shadow: 0 26px 72px rgba(2, 6, 23, 0.34);
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "SF Pro Text", "Segoe UI Variable", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei UI", sans-serif;
      background:
        radial-gradient(circle at 12% 0%, rgba(56, 189, 248, 0.16), transparent 28%),
        radial-gradient(circle at 88% 10%, rgba(96, 165, 250, 0.12), transparent 24%),
        linear-gradient(180deg, #08111b 0%, #091420 38%, #0b1420 100%);
      color: var(--text);
      line-height: 1.8;
      font-size: 16.5px;
      letter-spacing: 0.01em;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.025), transparent 20%),
        radial-gradient(circle at bottom left, rgba(34, 195, 238, 0.08), transparent 26%);
      opacity: 0.9;
    }}
    a {{
      color: #8ce0ff;
      text-decoration: none;
      text-underline-offset: 0.18em;
    }}
    a:hover {{
      color: #d7f4ff;
      text-decoration: underline;
    }}
    strong {{
      color: #f8fbff;
      font-weight: 650;
    }}
    p {{
      margin: 1rem 0;
      color: var(--text-soft);
    }}
    code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      background: rgba(7, 15, 26, 0.9);
      border: 1px solid rgba(148, 163, 184, 0.14);
      border-radius: 9px;
      padding: 0.14rem 0.42rem;
      font-size: 0.9em;
      color: #dff4ff;
    }}
    pre {{
      position: relative;
      margin: 1.35rem 0;
      padding: 1.05rem 1.15rem 1.15rem;
      overflow: auto;
      background: var(--code);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.03),
        0 16px 36px rgba(2, 6, 23, 0.2);
    }}
    pre code {{
      background: transparent;
      border: 0;
      padding: 0;
      border-radius: 0;
      display: block;
      color: #dbeafe;
    }}
    pre code[data-language]::before {{
      content: attr(data-language);
      display: block;
      margin-bottom: 0.85rem;
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}
    hr {{
      border: 0;
      height: 1px;
      background: linear-gradient(90deg, transparent, var(--line-strong), transparent);
      margin: 2.4rem 0;
    }}
    blockquote {{
      margin: 1.3rem 0;
      padding: 1rem 1.15rem 1rem 1.35rem;
      border-left: 4px solid var(--accent);
      border: 1px solid var(--line-strong);
      background: linear-gradient(135deg, rgba(34, 195, 238, 0.09), rgba(15, 23, 42, 0.3));
      color: #d9ecfb;
      border-radius: 0 18px 18px 0;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
    }}
    img {{
      display: block;
      width: 100%;
      max-width: 100%;
      border-radius: 18px;
      border: 1px solid var(--line);
      box-shadow: 0 22px 60px rgba(2, 6, 23, 0.42);
    }}
    figure {{
      margin: 1.7rem 0 2.05rem;
      padding: 14px;
      border-radius: 24px;
      border: 1px solid var(--line);
      background: rgba(8, 14, 24, 0.42);
    }}
    figcaption {{
      margin-top: 0.95rem;
      color: var(--muted);
      font-size: 0.92rem;
      text-align: center;
    }}
    ul, ol {{
      padding-left: 1.5rem;
      margin: 1rem 0 1.2rem;
      color: var(--text-soft);
    }}
    li::marker {{
      color: #7dd3fc;
    }}
    li + li {{
      margin-top: 0.55rem;
    }}
    ::selection {{
      background: rgba(34, 195, 238, 0.28);
      color: #f8fbff;
    }}
    ::-webkit-scrollbar {{
      width: 10px;
      height: 10px;
    }}
    ::-webkit-scrollbar-thumb {{
      background: rgba(125, 211, 252, 0.18);
      border-radius: 999px;
    }}
    ::-webkit-scrollbar-track {{
      background: transparent;
    }}
    .page {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 26px 24px 56px;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
      padding: 0 4px;
    }}
    .topbar-brand {{
      display: inline-flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }}
    .topbar-mark {{
      width: 11px;
      height: 11px;
      border-radius: 999px;
      background: radial-gradient(circle at 30% 30%, #d8f6ff, var(--accent-strong));
      box-shadow: 0 0 0 6px rgba(34, 195, 238, 0.08);
      flex-shrink: 0;
    }}
    .topbar-label {{
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
    }}
    .topbar-kicker {{
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }}
    .topbar-title {{
      color: var(--text);
      font-size: 0.96rem;
      font-weight: 700;
      white-space: nowrap;
    }}
    .topbar-route {{
      color: var(--muted);
      font-size: 0.82rem;
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      padding: 34px 36px;
      border-radius: 32px;
      border: 1px solid var(--line);
      background:
        linear-gradient(135deg, rgba(34, 195, 238, 0.18), rgba(17, 24, 39, 0.08) 48%, rgba(56, 189, 248, 0.08)),
        var(--panel);
      box-shadow: var(--shadow);
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      align-items: flex-start;
      margin-bottom: 24px;
    }}
    .hero::before {{
      content: "";
      position: absolute;
      inset: -120px auto auto -80px;
      width: 280px;
      height: 280px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(103, 212, 255, 0.18), transparent 68%);
      pointer-events: none;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: -80px;
      bottom: -110px;
      width: 260px;
      height: 260px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(96, 165, 250, 0.14), transparent 68%);
      pointer-events: none;
    }}
    .hero-copy,
    .hero-actions {{
      position: relative;
      z-index: 1;
    }}
    .hero-eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 0.95rem;
      padding: 0.42rem 0.75rem;
      border-radius: 999px;
      border: 1px solid rgba(125, 211, 252, 0.2);
      background: rgba(6, 13, 23, 0.34);
      color: #d8f5ff;
      font-size: 0.76rem;
      font-weight: 700;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }}
    .hero h1 {{
      margin: 0 0 0.75rem;
      font-size: clamp(2.1rem, 3vw, 3rem);
      line-height: 1.15;
      letter-spacing: -0.02em;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      max-width: 64ch;
      font-size: 1rem;
    }}
    .hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 1.15rem;
    }}
    .meta-chip {{
      display: inline-flex;
      align-items: center;
      padding: 0.44rem 0.72rem;
      border-radius: 999px;
      border: 1px solid rgba(125, 211, 252, 0.16);
      background: rgba(7, 15, 26, 0.3);
      color: var(--muted-strong);
      font-size: 0.86rem;
      font-weight: 600;
    }}
    .hero-actions {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .hero-actions a {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 214px;
      gap: 8px;
      padding: 11px 15px;
      border-radius: 14px;
      font-weight: 600;
      white-space: nowrap;
      transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
    }}
    .hero-actions a:hover {{
      transform: translateY(-1px);
      text-decoration: none;
    }}
    .hero-actions .primary-link {{
      background: linear-gradient(135deg, rgba(34, 195, 238, 0.26), rgba(37, 99, 235, 0.14));
      border: 1px solid rgba(125, 211, 252, 0.28);
      color: #ebfbff;
      box-shadow: 0 16px 30px rgba(14, 165, 233, 0.12);
    }}
    .hero-actions .secondary-link {{
      background: rgba(7, 15, 26, 0.24);
      border: 1px solid rgba(148, 163, 184, 0.16);
      color: var(--muted-strong);
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 300px;
      gap: 24px;
      align-items: start;
    }}
    .content {{
      position: relative;
      overflow: hidden;
      padding: 34px 38px 42px;
      border-radius: 32px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(13, 24, 40, 0.95), rgba(9, 16, 28, 0.93));
      box-shadow: 0 24px 60px rgba(2, 6, 23, 0.28);
    }}
    .content::before {{
      content: "";
      position: absolute;
      inset: 0 0 auto 0;
      height: 120px;
      background: linear-gradient(180deg, rgba(103, 212, 255, 0.06), transparent);
      pointer-events: none;
    }}
    .content > * {{
      position: relative;
    }}
    .content h1:first-child {{
      margin-top: 0;
      padding-bottom: 0.9rem;
      border-bottom: 1px solid var(--line);
    }}
    .content h1 {{
      font-size: 1.9rem;
      letter-spacing: -0.02em;
    }}
    .content h1, .content h2, .content h3, .content h4 {{
      scroll-margin-top: 88px;
      line-height: 1.25;
      color: #f6fbff;
    }}
    .content h2 {{
      position: relative;
      margin-top: 2.85rem;
      margin-bottom: 0.95rem;
      padding: 0 0 0.8rem 1rem;
      border-bottom: 1px solid var(--line);
      font-size: 1.56rem;
      letter-spacing: -0.01em;
    }}
    .content h2::before {{
      content: "";
      position: absolute;
      left: 0;
      top: 0.18rem;
      bottom: 1rem;
      width: 4px;
      border-radius: 999px;
      background: linear-gradient(180deg, var(--accent), rgba(103, 212, 255, 0.08));
    }}
    .content h3 {{
      margin-top: 2rem;
      margin-bottom: 0.55rem;
      font-size: 1.18rem;
      color: #eef7ff;
    }}
    .content h4 {{
      margin-top: 1.5rem;
      margin-bottom: 0.4rem;
      font-size: 1rem;
      color: #dff1ff;
    }}
    .content > p,
    .content > ul,
    .content > ol,
    .content > pre,
    .content > blockquote,
    .content > figure {{
      max-width: 78ch;
    }}
    .content table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1.2rem 0 1.5rem;
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
    }}
    .toc {{
      position: sticky;
      top: 24px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      max-height: calc(100vh - 48px);
      padding: 18px;
      border-radius: 28px;
      border: 1px solid var(--line);
      background: rgba(8, 15, 28, 0.82);
      backdrop-filter: blur(18px);
      box-shadow: 0 18px 46px rgba(2, 6, 23, 0.22);
    }}
    .toc-section {{
      min-height: 0;
      display: flex;
      flex-direction: column;
    }}
    .toc-kicker {{
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      margin-bottom: 0.45rem;
    }}
    .toc h2 {{
      margin: 0 0 0.9rem;
      font-size: 1.08rem;
      color: #f4fbff;
    }}
    .toc-links {{
      overflow: auto;
      padding-right: 4px;
    }}
    .toc-item {{
      display: block;
      padding: 9px 10px;
      border-radius: 12px;
      color: var(--muted);
      font-size: 0.92rem;
      transition: background 160ms ease, color 160ms ease, transform 160ms ease;
    }}
    .toc-item:hover {{
      background: rgba(56, 189, 248, 0.08);
      color: #ecfbff;
      transform: translateX(2px);
      text-decoration: none;
    }}
    .toc-item.level-1 {{
      font-weight: 650;
      color: #dce8f5;
    }}
    .toc-item.level-2 {{
      padding-left: 16px;
    }}
    .toc-item.level-3 {{
      padding-left: 26px;
      font-size: 0.88rem;
    }}
    .toc-empty {{
      display: block;
      color: var(--muted);
      font-size: 0.88rem;
      padding: 0.2rem 0;
    }}
    .toc-meta {{
      display: grid;
      gap: 10px;
      padding-top: 0.95rem;
      border-top: 1px solid var(--line);
    }}
    .toc-meta-row {{
      display: flex;
      flex-direction: column;
      gap: 4px;
      color: var(--muted);
      font-size: 0.84rem;
    }}
    .toc-meta-row strong {{
      color: #ecfbff;
      font-size: 0.95rem;
      font-weight: 650;
    }}
    .toc-meta-row code {{
      width: fit-content;
    }}
    @media (max-width: 980px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .toc {{
        position: static;
        max-height: none;
      }}
      .content {{
        padding: 24px 22px 28px;
      }}
      .hero {{
        flex-direction: column;
        grid-template-columns: 1fr;
        padding: 28px 24px;
      }}
      .hero-actions {{
        width: 100%;
      }}
      .hero-actions a {{
        width: 100%;
      }}
    }}
    @media (max-width: 640px) {{
      body {{
        font-size: 15.5px;
      }}
      .page {{
        padding: 18px 14px 36px;
      }}
      .topbar {{
        align-items: flex-start;
        flex-direction: column;
      }}
      .content h2 {{
        font-size: 1.34rem;
      }}
      .content h1 {{
        font-size: 1.62rem;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="topbar">
      <div class="topbar-brand">
        <span class="topbar-mark"></span>
        <div class="topbar-label">
          <span class="topbar-kicker">Delivery Readme</span>
          <span class="topbar-title">穿云审计交付文档</span>
        </div>
      </div>
      <span class="topbar-route">只读入口：/docs/readme</span>
    </div>
    <section class="hero">
      <div class="hero-copy">
        <span class="hero-eyebrow">交付文档</span>
        <h1>{page_title_html}</h1>
        <p>这份文档是当前交付版本的唯一说明入口。前端只提供只读链接，不复制文案，避免系统行为与说明文档再次漂移。</p>
        <div class="hero-meta">
          <span class="meta-chip">只读文档</span>
          <span class="meta-chip">离线交付</span>
          <span class="meta-chip">当前版本 v{APP_RELEASE_VERSION}</span>
        </div>
      </div>
      <div class="hero-actions">
        <a class="primary-link" href="/dashboard/">打开仪表盘</a>
        <a class="secondary-link" href="/docs/file/README.md" target="_blank" rel="noreferrer">查看原始 Markdown</a>
      </div>
    </section>
    <div class="layout">
      <main class="content">{''.join(body_parts)}</main>
      <aside class="toc">
        <div class="toc-section">
          <span class="toc-kicker">目录导航</span>
          <h2>交付文档</h2>
          <div class="toc-links">
            {toc_html or '<span class="toc-empty">当前文档暂无可索引章节。</span>'}
          </div>
        </div>
        <div class="toc-meta">
          <div class="toc-meta-row">
            <span>当前应用版本</span>
            <strong>v{APP_RELEASE_VERSION}</strong>
          </div>
          <div class="toc-meta-row">
            <span>访问入口</span>
            <code>/dashboard/</code>
          </div>
          <div class="toc-meta-row">
            <span>文档地址</span>
            <code>/docs/readme</code>
          </div>
        </div>
      </aside>
    </div>
  </div>
</body>
</html>"""


def _resolve_docs_file(relative_path: str) -> Optional[Path]:
    normalized = os.path.normpath(str(relative_path or "")).replace("\\", "/").lstrip("/")
    if not normalized:
        return None

    readme_path = (APP_ROOT / "README.md").resolve()
    if normalized == "README.md":
        return readme_path if readme_path.is_file() else None

    candidate = (APP_ROOT / normalized).resolve()
    allowed_roots = [
        (APP_ROOT / "docs" / "assets").resolve(),
    ]
    for root in allowed_roots:
        root_str = str(root)
        candidate_str = str(candidate)
        if candidate.is_file() and (
            candidate == root or candidate_str.startswith(root_str + os.sep)
        ):
            return candidate
    return None
_analysis_log_lock = threading.Lock()
_active_analysis_log_paths: Dict[str, str] = {}
_last_analysis_log_paths: Dict[str, str] = {}
_ANALYSIS_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"\[(?P<level>[A-Z]+)\] "
    r"(?P<message>.*)$"
)


def _get_dashboard_dist_dir() -> Path:
    """返回前端生产构建目录。"""
    return DASHBOARD_DIST_DIR


def _get_server_port() -> int:
    """获取服务监听端口，默认保持 8000。"""
    raw_port = os.environ.get("FPAS_PORT", "8000").strip()
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        logger.warning(f"无效 FPAS_PORT={raw_port!r}，回退到默认端口 8000")
        return 8000

    if 1 <= port <= 65535:
        return port

    logger.warning(f"越界 FPAS_PORT={raw_port!r}，回退到默认端口 8000")
    return 8000


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"0", "false", "no", "off"}:
        return False
    if normalized in {"1", "true", "yes", "on"}:
        return True
    return default


def _should_auto_open_dashboard_browser() -> bool:
    default_enabled = sys.platform == "win32" and _cli_entrypoint_invoked
    return _env_flag("FPAS_AUTO_OPEN_BROWSER", default_enabled)


def _get_dashboard_launch_url() -> str:
    return f"http://127.0.0.1:{_get_server_port()}/dashboard/"


def _wait_for_dashboard_ready(timeout_seconds: float = 15.0) -> bool:
    deadline = time.time() + max(timeout_seconds, 1.0)
    port = _get_server_port()

    while time.time() < deadline:
        connection: Optional[http.client.HTTPConnection] = None
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            connection.request("GET", "/dashboard/")
            response = connection.getresponse()
            response.read(1)
            if response.status == 200:
                return True
        except Exception:
            pass
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
        time.sleep(0.5)

    return False


def _open_url_in_default_browser(url: str) -> None:
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            ["cmd", "/c", "start", "", url],
            creationflags=creationflags,
        )
        return

    import webbrowser

    webbrowser.open(url, new=2)


def _schedule_dashboard_browser_launch() -> None:
    global _browser_auto_open_started

    if not _should_auto_open_dashboard_browser():
        return

    with _browser_auto_open_lock:
        if _browser_auto_open_started:
            return
        _browser_auto_open_started = True

    target_url = _get_dashboard_launch_url()

    def _launch_worker() -> None:
        launch_logger = logging.getLogger("uvicorn.error")
        ready = _wait_for_dashboard_ready()
        if not ready:
            launch_logger.warning(f"自动打开浏览器前未探测到 Dashboard 就绪: {target_url}")
            return

        try:
            launch_logger.info(f"正在自动打开默认浏览器: {target_url}")
            _open_url_in_default_browser(target_url)
            launch_logger.info(f"已自动打开默认浏览器: {target_url}")
        except Exception as exc:
            launch_logger.warning(f"自动打开默认浏览器失败: {exc}")

    threading.Thread(
        target=_launch_worker,
        name="fpas-dashboard-launcher",
        daemon=True,
    ).start()


def _resolve_dashboard_file(requested_path: str = "") -> Optional[Path]:
    """解析 Dashboard 静态文件，未知前端路由回落到 index.html。"""
    dist_dir = _get_dashboard_dist_dir().resolve()
    index_file = dist_dir / "index.html"
    if not index_file.exists():
        return None

    normalized_path = requested_path.replace("\\", "/").lstrip("/")
    if normalized_path in {"", "."}:
        return index_file

    candidate = (dist_dir / normalized_path).resolve()
    try:
        candidate.relative_to(dist_dir)
    except ValueError:
        return None

    if candidate.is_file():
        return candidate

    # SPA 前端路由回落到 index.html；真实静态资源缺失则返回 404。
    if "." not in Path(normalized_path).name:
        return index_file
    return None


def _get_current_time_str() -> str:
    """获取当前时间字符串 HH:MM:SS"""
    now = datetime.now()
    return f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}"


def _get_cache_manager() -> CacheManager:
    """获取或创建缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        # 从全局配置获取缓存目录
        cache_dir = _current_config.get("outputDirectory", str(OUTPUT_DIR))
        cache_dir = os.path.join(cache_dir, "analysis_cache")
        _cache_manager = CacheManager(cache_dir)
    return _cache_manager


def _append_analysis_runtime_log(level: str, msg: str):
    """将前端实时日志流固化到当前分析输出目录。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} [{level}] {msg}\n"
    with _analysis_log_lock:
        paths = [path for path in _active_analysis_log_paths.values() if path]
    for path in paths:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            # 日志固化失败不能打断主流程
            pass


def _start_analysis_runtime_log_capture(output_dir: str, start_time: Optional[datetime] = None) -> Dict[str, str]:
    """为本次分析初始化独立日志文件。"""
    run_time = start_time or datetime.now()
    logs_dir = os.path.join(output_dir, "analysis_logs")
    os.makedirs(logs_dir, exist_ok=True)

    timestamp = run_time.strftime("%Y%m%d_%H%M%S")
    run_log_path = os.path.join(logs_dir, f"analysis_run_{timestamp}.log")
    latest_log_path = os.path.join(logs_dir, "analysis_run_latest.log")

    with _analysis_log_lock:
        _active_analysis_log_paths.clear()
        _active_analysis_log_paths.update(
            {
                "run": run_log_path,
                "latest": latest_log_path,
            }
        )
        _last_analysis_log_paths.clear()
        _last_analysis_log_paths.update(_active_analysis_log_paths)

    for path in [run_log_path, latest_log_path]:
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                f"# 分析运行日志\n"
                f"# 启动时间: {run_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"# 输出目录: {output_dir}\n\n"
            )

    return {
        "runLog": run_log_path,
        "latestLog": latest_log_path,
    }


def _attach_analysis_results_log_mirror(results_dir: str) -> Optional[str]:
    """在 analysis_results 中附加当前运行日志镜像，便于和报告一起查看。"""
    os.makedirs(results_dir, exist_ok=True)
    mirror_path = os.path.join(results_dir, "分析执行日志.txt")

    with _analysis_log_lock:
        run_log_path = _active_analysis_log_paths.get("run")
        _active_analysis_log_paths["resultsMirror"] = mirror_path
        _last_analysis_log_paths["resultsMirror"] = mirror_path

    if run_log_path and os.path.exists(run_log_path):
        shutil.copyfile(run_log_path, mirror_path)
    else:
        with open(mirror_path, "w", encoding="utf-8") as f:
            f.write("# 分析执行日志\n")
    return mirror_path


def _finalize_analysis_runtime_log_capture(status: str):
    """收尾当前分析日志固化状态，避免后续无关日志继续写入。"""
    _append_analysis_runtime_log("INFO", f"日志固化收尾，分析状态: {status}")
    with _analysis_log_lock:
        _last_analysis_log_paths.clear()
        _last_analysis_log_paths.update(_active_analysis_log_paths)
        _active_analysis_log_paths.clear()


def _clear_analysis_log_path_state():
    """清空运行态日志路径，避免目录切换或清缓存后继续读取旧日志。"""
    with _analysis_log_lock:
        _active_analysis_log_paths.clear()
        _last_analysis_log_paths.clear()


def _sync_analysis_log_paths_with_output(
    output_dir: str, runtime_log_paths: Optional[Dict[str, Any]] = None
):
    """让日志历史路径与当前输出目录对齐。"""
    normalized_output_dir = os.path.realpath(os.path.abspath(output_dir))
    candidates: Dict[str, str] = {}

    if isinstance(runtime_log_paths, dict):
        for key, raw_path in runtime_log_paths.items():
            path = str(raw_path or "").strip()
            if not path:
                continue
            resolved = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
            if os.path.exists(resolved) and _is_path_within(normalized_output_dir, resolved):
                candidates[str(key)] = resolved

    results_mirror = os.path.join(normalized_output_dir, "analysis_results", "分析执行日志.txt")
    latest_log = os.path.join(normalized_output_dir, "analysis_logs", "analysis_run_latest.log")
    if os.path.exists(results_mirror):
        candidates["resultsMirror"] = results_mirror
    if os.path.exists(latest_log):
        candidates.setdefault("latest", latest_log)

    with _analysis_log_lock:
        _active_analysis_log_paths.clear()
        _last_analysis_log_paths.clear()
        _last_analysis_log_paths.update(candidates)


def _get_last_analysis_log_paths() -> Dict[str, str]:
    with _analysis_log_lock:
        return dict(_last_analysis_log_paths)


def _normalize_analysis_log_level(level: str) -> str:
    normalized = str(level or "").strip().upper()
    if normalized in {"WARN", "WARNING"}:
        return "WARN"
    if normalized in {"ERROR", "ERR", "FATAL"}:
        return "ERROR"
    return "INFO"


def _resolve_analysis_log_history_path() -> Optional[str]:
    last_paths = _get_last_analysis_log_paths()
    candidates = [
        last_paths.get("resultsMirror"),
        os.path.join(_get_active_results_dir(), "分析执行日志.txt"),
        last_paths.get("latest"),
        os.path.join(_get_active_output_dir(), "analysis_logs", "analysis_run_latest.log"),
        last_paths.get("run"),
    ]

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _load_analysis_log_history(limit: int = 200) -> Dict[str, Any]:
    target_limit = max(1, min(int(limit or 200), 500))
    log_path = _resolve_analysis_log_history_path()
    if not log_path or not os.path.exists(log_path):
        return {
            "logs": [],
            "stats": {"info": 0, "warn": 0, "error": 0},
            "path": "",
            "source": "unavailable",
        }

    parsed_logs: List[Dict[str, str]] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = _ANALYSIS_LOG_LINE_RE.match(line)
            if not match:
                continue
            parsed_logs.append(
                {
                    "time": match.group("timestamp")[11:19],
                    "level": _normalize_analysis_log_level(match.group("level")),
                    "msg": match.group("message").strip(),
                }
            )

    visible_logs = parsed_logs[-target_limit:]
    stats = {"info": 0, "warn": 0, "error": 0}
    for item in visible_logs:
        if item["level"] == "WARN":
            stats["warn"] += 1
        elif item["level"] == "ERROR":
            stats["error"] += 1
        else:
            stats["info"] += 1

    return {
        "logs": visible_logs,
        "stats": stats,
        "path": log_path,
        "source": "analysis_results_mirror"
        if os.path.basename(log_path) == "分析执行日志.txt"
        else "analysis_runtime_log",
    }


def _get_active_output_dir() -> str:
    """获取当前生效的输出目录（优先使用最近一次分析配置）。"""
    configured = _current_config.get("outputDirectory")
    if configured:
        return os.path.abspath(os.path.expanduser(str(configured)))
    return str(OUTPUT_DIR)


def _get_active_input_dir() -> str:
    """获取当前生效的输入目录（优先使用最近一次分析配置）。"""
    configured = _current_config.get("inputDirectory")
    if configured:
        return os.path.abspath(os.path.expanduser(str(configured)))
    return str(DATA_DIR)


def _get_active_cache_dir() -> str:
    return os.path.join(_get_active_output_dir(), "analysis_cache")


def _get_active_results_dir() -> str:
    return os.path.join(_get_active_output_dir(), "analysis_results")


def _refresh_report_index_file(output_dir: str) -> Optional[str]:
    """刷新报告目录清单，允许在缓存缺失时退化为纯目录扫描。"""
    logger = logging.getLogger(__name__)
    reports_dir = os.path.join(output_dir, "analysis_results")

    try:
        builder = load_investigation_report_builder(output_dir)
        if builder is None:
            builder = InvestigationReportBuilder({}, output_dir)
        return builder.generate_report_index_file(reports_dir)
    except Exception as exc:
        logger.warning(f"刷新报告目录清单失败: {exc}")
        return None


def _refresh_report_semantic_artifacts(output_dir: str) -> Optional[Dict[str, str]]:
    """刷新 report_package 与 QA 一致性产物。"""
    logger = logging.getLogger(__name__)
    try:
        builder = load_investigation_report_builder(output_dir)
        if builder is None:
            logger.info("跳过 report_package 刷新: 报告构建器未就绪")
            return None
        return builder.save_report_package_artifacts()
    except Exception as exc:
        logger.warning(f"刷新 report_package 失败: {exc}")
        return None


def _persist_report_semantic_artifacts(
    builder: Optional[InvestigationReportBuilder],
    report: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """在报告预生成链路中落地 report_package 与 QA 产物。"""
    logger = logging.getLogger(__name__)
    if builder is None:
        return None
    try:
        return builder.save_report_package_artifacts(
            report=report,
            formal_report_path=None,
        )
    except Exception as exc:
        logger.warning(f"预生成 report_package 失败: {exc}")
        if output_dir:
            return _refresh_report_semantic_artifacts(output_dir)
        return None


def _is_path_within(base_dir: str, target_path: str) -> bool:
    """判断目标路径是否位于指定目录内（解析符号链接后）。"""
    try:
        base_real = os.path.realpath(base_dir)
        target_real = os.path.realpath(target_path)
        return os.path.commonpath([base_real, target_real]) == base_real
    except ValueError:
        return False


def _get_allowed_open_folder_roots() -> List[str]:
    """限制可通过 open-folder 打开的目录范围。"""
    output_dir = _get_active_output_dir()
    return [
        os.path.join(output_dir, "cleaned_data", "个人"),
        os.path.join(output_dir, "cleaned_data", "公司"),
        os.path.join(output_dir, "analysis_results"),
    ]


def _resolve_open_folder_path(requested_path: str) -> str:
    """校验并返回允许打开的目录路径。"""
    if not requested_path or not str(requested_path).strip():
        raise HTTPException(status_code=400, detail="路径不能为空")

    resolved_path = os.path.realpath(os.path.abspath(os.path.expanduser(str(requested_path).strip())))

    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail=f"路径不存在: {requested_path}")

    if os.path.isfile(resolved_path):
        resolved_path = os.path.dirname(resolved_path)

    allowed_roots = _get_allowed_open_folder_roots()
    if not any(_is_path_within(root, resolved_path) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="仅允许打开输出目录中的审计结果文件夹")

    return resolved_path


def _has_valid_disk_cache(output_dir: Optional[str] = None) -> bool:
    """
    判断磁盘缓存是否完整。
    仅当核心缓存文件齐全时，认为可恢复历史结果。
    """
    base = output_dir or _get_active_output_dir()
    cache_dir = os.path.join(base, "analysis_cache")
    required_files = ("profiles.json", "derived_data.json", "suspicions.json", "metadata.json")
    return all(os.path.exists(os.path.join(cache_dir, name)) for name in required_files)


def _normalize_directory_path(path: Optional[str], fallback: str) -> str:
    """标准化目录路径，空值回退到默认目录。"""
    candidate = str(path).strip() if path is not None else ""
    resolved = candidate or fallback
    return os.path.abspath(os.path.expanduser(resolved))


def _set_active_paths(
    input_dir: Optional[str] = None, output_dir: Optional[str] = None
) -> Dict[str, str]:
    """更新当前活动输入/输出目录，并重置缓存管理器。"""
    global _cache_manager

    if input_dir is not None:
        _current_config["inputDirectory"] = _normalize_directory_path(
            input_dir, str(DATA_DIR)
        )
    if output_dir is not None:
        _current_config["outputDirectory"] = _normalize_directory_path(
            output_dir, str(OUTPUT_DIR)
        )

    _cache_manager = None

    return {
        "inputDirectory": _get_active_input_dir(),
        "outputDirectory": _get_active_output_dir(),
    }


def _sync_analysis_state_with_active_output(force_reload: bool = False) -> bool:
    """
    让内存分析状态与当前活动输出目录对齐。

    force_reload=True 时，即使内存中已有 completed 结果，也优先从当前输出目录缓存重载。
    """
    _ensure_completed_state_consistent()

    if analysis_state.status == "running":
        return False

    target_output_dir = _get_active_output_dir()
    if (
        not force_reload
        and analysis_state.status == "completed"
        and analysis_state.results
    ):
        return True

    if not _has_valid_disk_cache(target_output_dir):
        return False

    try:
        cache_mgr = CacheManager(os.path.join(target_output_dir, "analysis_cache"))
        results_data = cache_mgr.load_results()
    except Exception as exc:
        logging.getLogger(__name__).warning(f"从活动输出目录恢复缓存失败: {exc}")
        return False

    if not results_data:
        _clear_analysis_log_path_state()
        return False

    if isinstance(results_data, dict) and isinstance(results_data.get("suspicions"), dict):
        results_data = dict(results_data)
        results_data["suspicions"] = _normalize_serialized_suspicions_payload(
            results_data["suspicions"]
        )
        _sync_analysis_log_paths_with_output(
            target_output_dir,
            results_data.get("runtimeLogPaths", {}),
        )
    else:
        _sync_analysis_log_paths_with_output(target_output_dir, {})

    analysis_state.results = _normalize_results_contract(results_data)
    if not analysis_state.end_time:
        analysis_state.end_time = datetime.now()
    analysis_state.update(
        status="completed", progress=100, phase="已从缓存恢复", error=None
    )
    return True


def _clear_directory_contents(directory: str):
    """清空目录内容但保留目录本身。"""
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        return

    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as exc:
            logging.getLogger(__name__).warning(f"清理路径失败: {path}, {exc}")


def _ensure_completed_state_consistent():
    """
    保证内存状态与磁盘一致：
    - 若内存显示 completed，但磁盘缓存已被清空，则自动回退为 idle。
    """
    if analysis_state.status != "completed" or not analysis_state.results:
        return

    output_dir = _get_active_output_dir()
    if _has_valid_disk_cache(output_dir):
        return

    logging.getLogger(__name__).warning(
        f"检测到内存结果与磁盘不一致（缓存缺失），重置状态。output={output_dir}"
    )
    analysis_state.reset("缓存已清空，请重新开始分析")


def _get_primary_targets_service() -> PrimaryTargetsService:
    """基于当前活动输入/输出目录构造归集配置服务。"""
    return PrimaryTargetsService(
        data_dir=_get_active_input_dir(),
        output_dir=_get_active_output_dir(),
    )


def _load_saved_primary_targets_config(
    data_dir: str, output_dir: str
) -> Optional[Any]:
    """加载用户已保存的归集配置，仅在显式存在时返回。"""
    try:
        service = PrimaryTargetsService(data_dir=data_dir, output_dir=output_dir)
        config_obj, msg = service.load_config()
        if config_obj and getattr(config_obj, "analysis_units", None):
            return config_obj
        if msg != "配置文件不存在":
            logging.getLogger(__name__).warning(f"加载归集配置失败: {msg}")
    except Exception as exc:
        logging.getLogger(__name__).warning(f"加载归集配置异常: {exc}")
    return None


def _analysis_unit_to_family_unit_dict(
    unit: Any, profiles: Dict[str, Any]
) -> Dict[str, Any]:
    """将用户归集单元转换为分析阶段通用的家庭单元字典。"""
    anchor = str(getattr(unit, "anchor", "") or "").strip()
    members_raw = getattr(unit, "members", []) or []
    members: List[str] = []
    for raw_member in members_raw:
        member_name = str(raw_member or "").strip()
        if member_name and member_name not in members:
            members.append(member_name)

    if anchor and anchor not in members:
        members.insert(0, anchor)
    if not members:
        return {}

    normalized_anchor = anchor if anchor in members else members[0]
    unit_type = str(getattr(unit, "unit_type", "family") or "family").strip() or "family"

    member_details = []
    for detail in getattr(unit, "member_details", []) or []:
        name = str(getattr(detail, "name", "") or "").strip()
        if not name:
            continue
        has_data = getattr(detail, "has_data", None)
        member_details.append(
            {
                "name": name,
                "relation": str(getattr(detail, "relation", "") or "家庭成员").strip()
                or "家庭成员",
                "has_data": bool(name in profiles) if has_data is None else bool(has_data),
                "id_number": str(getattr(detail, "id_number", "") or "").strip(),
            }
        )

    if not member_details:
        for member_name in members:
            member_details.append(
                {
                    "name": member_name,
                    "relation": "本人" if member_name == normalized_anchor else "家庭成员",
                    "has_data": member_name in profiles,
                    "id_number": "",
                }
            )

    return {
        "anchor": normalized_anchor,
        "householder": normalized_anchor,
        "members": members,
        "member_details": member_details,
        "unit_type": unit_type,
        "source": "primary_targets",
    }


def _get_effective_family_units_for_analysis(
    inferred_units: List[Dict[str, Any]],
    data_dir: str,
    output_dir: str,
    profiles: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], Optional[Any]]:
    """
    为分析阶段选择生效的家庭归集单元。

    规则：
    - 若存在用户保存的 primary_targets.json，则以其 analysis_units 为准
    - 否则回退到程序自动推断的 family_units_v2
    """
    config_obj = _load_saved_primary_targets_config(data_dir, output_dir)
    if not config_obj:
        return inferred_units, None

    configured_units = []
    for unit in getattr(config_obj, "analysis_units", []) or []:
        family_unit = _analysis_unit_to_family_unit_dict(unit, profiles)
        if family_unit:
            configured_units.append(family_unit)

    if configured_units:
        return configured_units, config_obj

    return inferred_units, None


def _build_person_to_family_map(
    family_units_list: List[Dict[str, Any]]
) -> Dict[str, List[str]]:
    """根据家庭单元构建人员到其他家庭成员的映射。"""
    person_to_family: Dict[str, List[str]] = {}
    for unit in family_units_list:
        members = unit.get("members", []) or []
        for member in members:
            other_members = [name for name in members if name and name != member]
            if other_members:
                person_to_family[member] = other_members
    return person_to_family


def _refresh_profiles_with_family_units(
    profiles: Dict[str, Any],
    cleaned_data: Dict[str, pd.DataFrame],
    family_units_list: List[Dict[str, Any]],
    income_expense_match_analyzer: IncomeExpenseMatchAnalyzer,
    logger: logging.Logger,
) -> int:
    """按当前生效的家庭归集单元刷新真实收入相关口径。"""
    person_to_family = _build_person_to_family_map(family_units_list)
    updated_count = 0

    for person_name, profile in profiles.items():
        family_members = person_to_family.get(person_name, [])
        df = cleaned_data.get(person_name)
        if df is None or df.empty or not family_members:
            continue

        try:
            _refresh_profile_real_metrics(
                profile,
                df,
                person_name,
                family_members,
                income_expense_match_analyzer,
            )
            updated_count += 1
            logger.info(
                f"  ✓ 更新 {person_name} 真实收入: "
                f"    原始: {profile.get('income_structure', {}).get('total_income', 0)/10000:.2f}万, "
                f"    更新后: {profile.get('summary', {}).get('real_income', 0)/10000:.2f}万 (剔除家庭转账)"
            )
        except Exception as exc:
            logger.warning(f"更新 {person_name} 真实收入失败: {exc}")

    return updated_count


def _build_all_family_summaries(
    profiles: Dict[str, Any],
    family_units_list: List[Dict[str, Any]],
    logger: logging.Logger,
) -> Dict[str, Dict[str, Any]]:
    """基于当前画像状态构建全部家庭财务汇总。"""
    all_family_summaries: Dict[str, Dict[str, Any]] = {}

    for unit in family_units_list:
        householder = unit.get("householder", "") or unit.get("anchor", "")
        members = unit.get("members", [])
        if not members:
            continue
        if not _family_unit_has_profile_members(members, profiles):
            logger.info(f"  · 跳过无画像家庭单元: {householder}")
            continue
        try:
            family_assets = _collect_family_assets_for_summary(members, profiles)
            unit_summary = family_finance.calculate_family_summary(
                profiles,
                members,
                properties=family_assets["properties"],
                vehicles=family_assets["vehicles"],
            )
            unit_summary["householder"] = householder
            unit_summary["extended_relatives"] = unit.get("extended_relatives", [])
            all_family_summaries[householder] = unit_summary
        except Exception as e:
            logger.warning(f"计算 {householder} 家庭汇总失败: {e}")

    return all_family_summaries


def _refresh_profiles_and_build_family_summaries(
    profiles: Dict[str, Any],
    cleaned_data: Dict[str, pd.DataFrame],
    family_units_list: List[Dict[str, Any]],
    income_expense_match_analyzer: IncomeExpenseMatchAnalyzer,
    logger: logging.Logger,
) -> tuple[int, Dict[str, Dict[str, Any]]]:
    """先刷新个人真实收支，再用刷新后的画像重建家庭汇总。"""
    updated_count = 0
    if family_units_list:
        logger.info("  ▶ 根据当前生效归集单元刷新真实收入...")
        updated_count = _refresh_profiles_with_family_units(
            profiles,
            cleaned_data,
            family_units_list,
            income_expense_match_analyzer,
            logger,
        )
        logger.info(f"  ✓ 已根据家庭关系更新 {updated_count} 人的真实收入")

    logger.info("  ▶ 计算家庭财务汇总...")
    all_family_summaries = _build_all_family_summaries(
        profiles,
        family_units_list,
        logger,
    )
    return updated_count, all_family_summaries


def _save_external_report_caches(
    cache_mgr: CacheManager, external_data: Dict[str, Any], logger: logging.Logger
) -> None:
    """为报告生成预先保存外部数据缓存，空结果也要覆盖旧文件。"""
    external_cache_mapping = {
        "precisePropertyData": external_data.get("p1", {}).get("precise_property_data", {}),
        "vehicleData": external_data.get("p1", {}).get("vehicle_data", {}),
        "wealthProductData": external_data.get("p1", {}).get("wealth_product_data", {}),
        "securitiesData": external_data.get("p1", {}).get("securities_data", {}),
        "bankAccountInfo": external_data.get("p0", {}).get("bank_account_info", {}),
        "taxData": external_data.get("p0", {}).get("tax_data", {}),
        "creditData": external_data.get("p0", {}).get("credit_data", {}),
        "amlData": external_data.get("p0", {}).get("aml_data", {}),
        "insuranceData": external_data.get("p2", {}).get("insurance_data", {}),
        "immigrationData": external_data.get("p2", {}).get("immigration_data", {}),
        "hotelData": external_data.get("p2", {}).get("hotel_data", {}),
        "hotelCohabitation": external_data.get("p2", {}).get("hotel_cohabitation", {}),
        "railwayData": external_data.get("p2", {}).get("railway_data", {}),
        "flightData": external_data.get("p2", {}).get("flight_data", {}),
        "coaddressData": external_data.get("p2", {}).get("coaddress_data", {}),
        "coviolationData": external_data.get("p2", {}).get("coviolation_data", {}),
    }

    for key, data in external_cache_mapping.items():
        cache_mgr.save_cache(key, data if data is not None else {})
        logger.info(f"  ✓ 已保存 {key}")


def _raise_if_analysis_stopped(phase: str = "分析已停止"):
    """在分析流程关键节点检查是否收到停止请求。"""
    if analysis_state.is_stop_requested():
        raise AnalysisStoppedError(phase)


def _populate_transport_external_data(
    data_dir: str, phase2_external_data: Dict[str, Any], logger: logging.Logger
) -> None:
    """提取铁路/航班主体数据与时间线，避免单点失败抹掉已提取结果。"""
    try:
        railway_data = railway_extractor.extract_railway_data(data_dir)
        phase2_external_data["railway_data"] = railway_data
        logger.info(f"    ✓ 铁路出行: {len(railway_data)} 个主体")
    except Exception as e:
        logger.warning(f"    ✗ 铁路出行提取失败: {e}")
        phase2_external_data["railway_data"] = {}

    try:
        phase2_external_data["railway_timeline"] = (
            railway_extractor.get_travel_timeline(data_dir)
        )
    except Exception as e:
        logger.warning(f"    ✗ 铁路出行时间线构建失败: {e}")
        phase2_external_data["railway_timeline"] = []

    try:
        flight_data = flight_extractor.extract_flight_data(data_dir)
        phase2_external_data["flight_data"] = flight_data
        logger.info(f"    ✓ 航班出行: {len(flight_data)} 个主体")
    except Exception as e:
        logger.warning(f"    ✗ 航班出行提取失败: {e}")
        phase2_external_data["flight_data"] = {}

    try:
        phase2_external_data["flight_timeline"] = (
            flight_extractor.get_flight_timeline(data_dir)
        )
    except Exception as e:
        logger.warning(f"    ✗ 航班出行时间线构建失败: {e}")
        phase2_external_data["flight_timeline"] = []


def _load_json_dict_or_default(
    filepath: str, logger: logging.Logger, label: str, default: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """读取 JSON 对象，缺失或损坏时回退到默认值。"""
    fallback = dict(default or {})

    if not os.path.exists(filepath):
        logger.warning(f"[{label}] 文件不存在，使用默认空对象: {filepath}")
        return fallback

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        logger.warning(f"[{label}] JSON损坏，使用默认空对象: {filepath}, error={exc}")
        return fallback
    except Exception as exc:
        logger.warning(f"[{label}] 读取失败，使用默认空对象: {filepath}, error={exc}")
        return fallback

    if isinstance(data, dict):
        return data

    logger.warning(f"[{label}] 内容不是对象，使用默认空对象: {filepath}")
    return fallback


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
            _append_analysis_runtime_log(level, msg)
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
    _append_analysis_runtime_log(level, msg)


# ==================== Pydantic 模型 ====================
class AnalysisConfig(BaseModel):
    inputDirectory: str
    outputDirectory: Optional[str] = None
    cashThreshold: Optional[float] = 50000
    timeWindow: Optional[float] = 48
    modules: Optional[Dict[str, bool]] = None


class ActivePathsRequest(BaseModel):
    inputDirectory: Optional[str] = None
    outputDirectory: Optional[str] = None


class DirectorySelectRequest(BaseModel):
    """目录选择请求"""

    type: str  # "input" 或 "output"
    current_path: Optional[str] = None


class DirectorySelectResponse(BaseModel):
    """目录选择响应"""

    success: bool
    path: Optional[str] = None
    error: Optional[str] = None


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
    elif isinstance(obj, (set, frozenset)):
        return [serialize_for_json(v) for v in sorted(obj, key=repr)]
    elif isinstance(obj, tuple):
        return tuple(serialize_for_json(v) for v in obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return [serialize_for_json(v) for v in obj.tolist()]
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif isinstance(obj, date):
        # Handle datetime.date (different from datetime.datetime)
        return obj.isoformat()
    # Handle NaN/NaT - use try-except to avoid array ambiguity
    try:
        if pd.isna(obj):
            return None
    except (ValueError, TypeError):
        # pd.isna() raises ValueError for arrays, TypeError for some objects
        pass

    # Final check: if it's still a numpy type, convert it
    if hasattr(obj, "dtype") and hasattr(obj, "item"):
        # This handles any remaining numpy scalar types
        return obj.item()

    # Handle arbitrary Python objects (like ClueAggregator)
    # Check if it has a to_dict method
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return serialize_for_json(obj.to_dict())

    # Check if it has __dict__ attribute (custom class instance)
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        # Convert to dict, excluding private attributes and methods
        obj_dict = {}
        for key, value in obj.__dict__.items():
            if not key.startswith("_") and not callable(value):
                obj_dict[key] = serialize_for_json(value)
        return obj_dict

    return obj


def _collect_family_assets_for_summary(
    members: List[str], profiles: Dict[str, Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """聚合家庭成员资产，供 family_finance.calculate_family_summary 复用。"""
    properties: List[Dict[str, Any]] = []
    vehicles: List[Dict[str, Any]] = []
    seen_properties = set()
    seen_vehicles = set()

    def _normalize_property_key(prop: Dict[str, Any]) -> str:
        return family_assets_helper.build_property_identity_key(prop)

    def _normalize_vehicle_key(vehicle: Dict[str, Any]) -> str:
        return str(
            vehicle.get("号牌号码")
            or vehicle.get("plate_number")
            or vehicle.get("vehicle_identification_number")
            or vehicle.get("车辆识别代号")
            or vehicle.get("source_file")
            or ""
        ).strip()

    for member in members:
        profile = profiles.get(member, {}) or {}
        property_sources = (profile.get("properties_precise", []) or []) + (
            profile.get("properties", []) or []
        )

        for prop in property_sources:
            normalized = dict(prop)
            normalized.setdefault(
                "价格",
                prop.get("不动产价格")
                or prop.get("estimated_value")
                or prop.get("value")
                or prop.get("transaction_price")
                or 0,
            )
            normalized.setdefault(
                "房地坐落",
                prop.get("location") or prop.get("address") or prop.get("坐落") or "",
            )
            identifier = _normalize_property_key(normalized)
            if identifier and identifier not in seen_properties:
                seen_properties.add(identifier)
                properties.append(normalized)

        for vehicle in profile.get("vehicles", []) or []:
            identifier = _normalize_vehicle_key(vehicle)
            if identifier and identifier not in seen_vehicles:
                seen_vehicles.add(identifier)
                vehicles.append(dict(vehicle))

    return {"properties": properties, "vehicles": vehicles}


def _family_unit_has_profile_members(
    members: List[str], profiles: Dict[str, Dict[str, Any]]
) -> bool:
    """判断家庭单元是否至少包含一个可分析画像成员。"""
    return any(member in profiles for member in members or [])


def create_output_directories(base_dir: str) -> Dict[str, str]:
    """创建输出目录结构"""
    dirs = {
        "output": base_dir,
        "cleaned_persons": os.path.join(base_dir, "cleaned_data", "个人"),
        "cleaned_companies": os.path.join(base_dir, "cleaned_data", "公司"),
        "analysis_cache": os.path.join(base_dir, "analysis_cache"),
        "analysis_results": os.path.join(base_dir, "analysis_results"),
        "analysis_logs": os.path.join(base_dir, "analysis_logs"),
    }
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    return dirs


def _safe_abs_amount(value: Any) -> float:
    """将交易金额安全转换为绝对值浮点数。"""
    if value in (None, ""):
        return 0.0

    if isinstance(value, str):
        value = value.replace(",", "").replace("¥", "").replace("￥", "").strip()
        if not value:
            return 0.0

    try:
        return abs(float(value))
    except (TypeError, ValueError):
        return 0.0


def _calculate_profile_max_transaction(profile_dict: Dict[str, Any]) -> float:
    """
    从现有画像中的交易明细列表提取最大单笔金额。

    仅扫描具备交易特征的明细项，避免把资产余额、汇总统计误判为单笔交易。
    """
    amount_keys = ("金额", "amount", "交易金额", "transaction_amount", "abs_amount")
    fallback_amount_keys = ("income", "expense", "收入", "支出")
    transaction_hint_keys = (
        "日期",
        "date",
        "交易日期",
        "摘要",
        "description",
        "对手方",
        "counterparty",
        "类型",
        "type",
        "transaction_id",
        "source_file",
        "source_row_index",
    )
    max_amount = 0.0

    def walk(node: Any) -> None:
        nonlocal max_amount

        if isinstance(node, dict):
            for value in node.values():
                walk(value)
            return

        if not isinstance(node, list):
            return

        for item in node:
            if isinstance(item, dict):
                if any(key in item for key in transaction_hint_keys):
                    direct_amount = 0.0
                    for key in amount_keys:
                        direct_amount = max(direct_amount, _safe_abs_amount(item.get(key)))

                    if direct_amount > 0:
                        max_amount = max(max_amount, direct_amount)
                    else:
                        for key in fallback_amount_keys:
                            max_amount = max(
                                max_amount, _safe_abs_amount(item.get(key))
                            )

                for value in item.values():
                    walk(value)
            elif isinstance(item, list):
                walk(item)

    walk(profile_dict)
    return max_amount


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
            wealth_total_amount = (
                wealth_mgmt.get("wealth_purchase", 0)
                + wealth_mgmt.get("wealth_redemption", 0)
                + wealth_mgmt.get("wealth_income", 0)
            )
            max_transaction = _calculate_profile_max_transaction(profile_dict)

            # 【2026-02-12 关键改进】保留完整的原始数据，供报告生成使用
            # 问题背景：之前的简化版缺失 yearly_salary 等关键字段，导致报告生成器
            # 必须同时维护 profiles.json 和 profiles_full.json 两个文件，造成混淆
            # 解决方案：简化版保留所有原始数据，只是添加前端需要的扁平化字段

            # 构建前端期望的扁平化结构（同时保留完整原始数据）
            frontend_profile = {
                # 基础标识
                "entityName": name,
                "entity_id": profile_dict.get("entity_id", ""),  # 【修复】添加身份证号
                # 核心财务指标 (camelCase) - 前端展示用
                "totalIncome": summary.get("total_income", 0)
                or income_structure.get("total_income", 0),
                "totalExpense": summary.get("total_expense", 0)
                or income_structure.get("total_expense", 0),
                "realIncome": summary.get("real_income")
                if summary.get("real_income") is not None
                else profile_dict.get("real_income", 0),
                "realExpense": summary.get("real_expense")
                if summary.get("real_expense") is not None
                else profile_dict.get("real_expense", 0),
                "transactionCount": summary.get("transaction_count", 0),
                # 审计关键字段 - 前端展示用
                "cashTotal": cash_total,
                # 将 cash_transactions 提升到顶层字段，以便前端直接访问
                "cashTransactions": fund_flow.get("cash_transactions", []),
                "thirdPartyTotal": third_party_total,
                "wealthTotal": wealth_total_amount,
                "wealthTransactionCount": wealth_mgmt.get("total_transactions", 0),
                "maxTransaction": max_transaction,
                "salaryRatio": summary.get("salary_ratio", 0),
                # 【修复】保留房产/车辆/理财等资产数据，供报告生成使用
                "properties": profile_dict.get("properties", []),
                "properties_precise": profile_dict.get("properties_precise", []),
                "vehicles": profile_dict.get("vehicles", []),
                "wealth_products": profile_dict.get("wealth_products", []),
                "securities": profile_dict.get("securities", []),
                "insurance": profile_dict.get("insurance", []),
                "insurance_summary": profile_dict.get("insurance_summary", {}),
                "bank_accounts_official": profile_dict.get(
                    "bank_accounts_official", []
                ),
                "hotel_records": profile_dict.get("hotel_records", []),
                "railway_records": profile_dict.get("railway_records", {}),
                "flight_records": profile_dict.get("flight_records", {}),
                "coaddress_persons": profile_dict.get("coaddress_persons", []),
                "coviolation_vehicles": profile_dict.get("coviolation_vehicles", []),
                # 【2026-02-12 新增】保留完整的原始嵌套数据，供报告生成使用
                # 这样报告生成器只需要使用 profiles.json，无需再加载 profiles_full.json
                "entity_name": profile_dict.get("entity_name", name),
                "has_data": profile_dict.get("has_data", False),
                "summary": summary,
                "income_structure": income_structure,
                "fund_flow": fund_flow,
                "wealth_management": wealth_mgmt,
                "large_cash": large_cash,
                "categories": profile_dict.get("categories", {}),
                "yearly_salary": profile_dict.get("yearly_salary", {}),
                "income_classification": profile_dict.get("income_classification", {}),
                "bank_accounts": profile_dict.get("bank_accounts", []),
                # 【2026-03-01 修复】添加公司特有分析数据，供报告生成使用
                "company_specific": profile_dict.get("company_specific", {}),
                "transactions": profile_dict.get("transactions", []),
                # 企业登记信息（报告生成使用）
                "registered_companies": profile_dict.get("registered_companies", []),
                "company_registration": profile_dict.get("company_registration", []),
                "tax_records": profile_dict.get("tax_records", []),
                # 增强分析器输出
                "salary_enhanced_analysis": profile_dict.get(
                    "salary_enhanced_analysis", {}
                ),
                "real_salary_analysis": profile_dict.get("real_salary_analysis", {}),
                "finance_risk_analysis": profile_dict.get("finance_risk_analysis", {}),
                "income_expense_match_analysis": profile_dict.get(
                    "income_expense_match_analysis", {}
                ),
                "personal_fund_feature_analysis": profile_dict.get(
                    "personal_fund_feature_analysis", {}
                ),
                "wallet_summary": profile_dict.get("wallet_summary", {}),
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
                "wealthTransactionCount": 0,
                "maxTransaction": 0,
                "salaryRatio": 0,
                "_error": str(e),
            }
    return result


def _safe_profile_amount(value: Any) -> float:
    """安全转换画像金额字段，异常值统一回落为 0。"""
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _build_profile_excluded_breakdown(summary: Dict[str, Any]) -> Dict[str, float]:
    """
    从旧版 summary.offset_detail 反推出前端需要的 excluded_breakdown。

    旧缓存里很多主体只有 offset_detail，没有 excluded_breakdown。
    为了让真实收入剔除明细在前端稳定展示，这里统一补齐兼容结构。
    """
    if not isinstance(summary, dict):
        return {}

    existing = summary.get("excluded_breakdown")
    if isinstance(existing, dict) and existing:
        return existing

    offset_detail = summary.get("offset_detail")
    if not isinstance(offset_detail, dict):
        return {}

    wealth_redemption = (
        _safe_profile_amount(offset_detail.get("wealth_principal"))
        + _safe_profile_amount(offset_detail.get("wealth_historical"))
        + _safe_profile_amount(offset_detail.get("deposit_redemption"))
    )

    derived = {
        "self_transfer": _safe_profile_amount(offset_detail.get("self_transfer")),
        "wealth_redemption": wealth_redemption,
        "bank_product_adjustment": _safe_profile_amount(
            offset_detail.get("bank_product_adjustment")
        ),
        "business_reimbursement": _safe_profile_amount(
            offset_detail.get("business_reimbursement")
        ),
        "family_transfer": _safe_profile_amount(offset_detail.get("family_transfer_in")),
        "refund": _safe_profile_amount(offset_detail.get("refund")),
        "installment_adjustment": _safe_profile_amount(
            offset_detail.get("installment_adjustment")
        ),
        "loan": _safe_profile_amount(offset_detail.get("loan")),
    }

    return {key: value for key, value in derived.items() if value > 0}


def _normalize_profile_contract(profile: Any) -> Any:
    """
    兼容旧版 profiles.json 字段语义。

    重点修复：
    1. wealthTotal 旧值曾保存为“笔数”，新版必须统一为“金额”
    2. wealthTransactionCount 需要从 wealth_management 反补
    3. excluded_breakdown 需要从旧版 offset_detail 推导
    """
    if not isinstance(profile, dict):
        return profile

    normalized = dict(profile)

    wealth_mgmt = normalized.get("wealth_management")
    if isinstance(wealth_mgmt, dict):
        wealth_total_amount = (
            _safe_profile_amount(wealth_mgmt.get("wealth_purchase"))
            + _safe_profile_amount(wealth_mgmt.get("wealth_redemption"))
            + _safe_profile_amount(wealth_mgmt.get("wealth_income"))
        )
        if wealth_total_amount > 0:
            normalized["wealthTotal"] = wealth_total_amount

        wealth_tx_count = wealth_mgmt.get("total_transactions")
        if wealth_tx_count is not None:
            normalized["wealthTransactionCount"] = wealth_tx_count

    summary = normalized.get("summary")
    if isinstance(summary, dict):
        summary_copy = dict(summary)
        derived_breakdown = _build_profile_excluded_breakdown(summary_copy)
        if derived_breakdown:
            summary_copy["excluded_breakdown"] = derived_breakdown
        normalized["summary"] = summary_copy

    return normalized


def _normalize_results_contract(results_data: Any) -> Any:
    """统一修正缓存恢复后的结果契约，避免旧缓存污染当前接口。"""
    if not isinstance(results_data, dict):
        return results_data

    normalized = dict(results_data)
    profiles = normalized.get("profiles")
    if isinstance(profiles, dict):
        normalized["profiles"] = {
            name: _normalize_profile_contract(profile)
            for name, profile in profiles.items()
        }

    return normalized


def _pick_first_existing_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """从候选列中返回第一个存在的列名"""
    return utils.find_first_matching_column(
        df,
        candidates,
        is_amount_field=any(
            keyword in " ".join(candidates)
            for keyword in ["income", "expense", "amount", "收入", "支出", "金额", "余额"]
        ),
    )


def _prepare_person_transactions_for_advanced_analyzers(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    为工资/理财/收支匹配/资金特征分析器准备统一字段。

    输出字段：
    - date
    - income
    - expense
    - direction (income/expense)
    - amount
    - counterparty
    - description
    - account_number
    - account
    - transaction_type
    """
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "income",
                "expense",
                "direction",
                "amount",
                "counterparty",
                "description",
                "account_number",
                "account",
                "transaction_type",
            ]
        )

    tx_df = df.copy()

    date_col = _pick_first_existing_column(
        tx_df, ["date", "交易时间", "交易日期", "日期", "time"]
    )
    income_col = _pick_first_existing_column(
        tx_df, ["income", "收入(元)", "收入(万元)", "收入"]
    )
    expense_col = _pick_first_existing_column(
        tx_df, ["expense", "支出(元)", "支出(万元)", "支出"]
    )
    direction_col = _pick_first_existing_column(tx_df, ["direction", "收支方向"])
    amount_col = _pick_first_existing_column(
        tx_df, ["amount", "交易金额", "交易金额(万元)", "金额", "金额(万元)"]
    )
    counterparty_col = _pick_first_existing_column(tx_df, ["counterparty", "交易对手"])
    description_col = _pick_first_existing_column(tx_df, ["description", "交易摘要", "摘要"])
    account_col = _pick_first_existing_column(tx_df, ["account_number", "本方账号", "账号"])
    category_col = _pick_first_existing_column(
        tx_df, ["transaction_type", "交易分类", "交易类型"]
    )

    normalized = pd.DataFrame(index=tx_df.index)

    if date_col:
        normalized["date"] = utils.normalize_datetime_series(tx_df[date_col])
    else:
        normalized["date"] = pd.NaT

    if income_col:
        normalized["income"] = utils.normalize_amount_series(tx_df[income_col], income_col)
    else:
        normalized["income"] = 0.0

    if expense_col:
        normalized["expense"] = utils.normalize_amount_series(tx_df[expense_col], expense_col)
    else:
        normalized["expense"] = 0.0

    if amount_col:
        normalized["amount"] = utils.normalize_amount_series(tx_df[amount_col], amount_col)
    else:
        normalized["amount"] = normalized["income"].where(
            normalized["income"] > 0, normalized["expense"]
        )

    if direction_col:
        normalized["direction"] = tx_df[direction_col].astype(str).str.lower().replace(
            {"in": "income", "out": "expense", "收入": "income", "支出": "expense"}
        )
    else:
        normalized["direction"] = "other"
        normalized.loc[normalized["income"] > 0, "direction"] = "income"
        normalized.loc[
            (normalized["income"] <= 0) & (normalized["expense"] > 0), "direction"
        ] = "expense"

    def _normalize_text_series(column_name: Optional[str]) -> pd.Series:
        if not column_name:
            return pd.Series("", index=tx_df.index, dtype="string")
        # 清洗后的文本列可能被压缩为 Categorical；先转成 string 再填空值，避免 fillna
        # 在分类类型上写入新类别时报错。
        return tx_df[column_name].astype("string").fillna("")

    normalized["counterparty"] = _normalize_text_series(counterparty_col)
    normalized["description"] = _normalize_text_series(description_col)
    normalized["account_number"] = _normalize_text_series(account_col)
    normalized["account"] = normalized["account_number"]

    category_series = _normalize_text_series(category_col)

    def _map_transaction_type(
        raw_category: str, direction: str, description: str
    ) -> str:
        category_text = str(raw_category or "")
        direction_text = str(direction or "").lower()
        desc_text = str(description or "")

        if "工资" in category_text:
            return "工资"
        if "生活消费" in category_text or category_text == "消费":
            return "消费"
        if "网贷" in category_text or "信贷" in category_text or "贷款" in category_text:
            return "借款" if direction_text == "income" else "还款"
        if "转账" in category_text:
            return "转账" if direction_text == "income" else "转账支出"
        if "现金" in category_text:
            return "存现" if direction_text == "income" else "取现"
        if "投资理财" in category_text or "理财" in desc_text or "基金" in desc_text:
            if direction_text == "income" and any(
                kw in desc_text for kw in ["收益", "分红", "利息"]
            ):
                return "投资收益"
            return "投资理财"

        if direction_text == "income":
            if any(kw in desc_text for kw in ["借款", "贷款"]):
                return "借款"
            return "转账收入"
        if direction_text == "expense":
            if any(kw in desc_text for kw in ["还款", "还贷"]):
                return "还款"
            return "其他支出"
        return "其他"

    normalized["transaction_type"] = [
        _map_transaction_type(cat, d, desc)
        for cat, d, desc in zip(
            category_series, normalized["direction"], normalized["description"]
        )
    ]

    normalized = normalized.dropna(subset=["date"])
    return normalized.reset_index(drop=True)


def _summarize_salary_enhanced_analysis(result: Dict[str, Any]) -> Dict[str, Any]:
    """提取工资增强分析中的可序列化关键结果，避免写入 DataFrame 对象"""
    if not isinstance(result, dict):
        return {}

    summary = {
        "total_income": float(result.get("total_income", 0) or 0),
        "salary_income": float(result.get("salary_income", 0) or 0),
        "wealth_income": float(result.get("wealth_income", 0) or 0),
        "interest_income": float(result.get("interest_income", 0) or 0),
        "other_income": float(result.get("other_income", 0) or 0),
        "salary_ratio": float(result.get("salary_ratio", 0) or 0),
        "salary_stats": result.get("salary_stats", {}) or {},
        "salary_details": result.get("salary_details", [])[:200],
    }
    return serialize_for_json(summary)


def _summarize_personal_fund_feature_analysis(result: Dict[str, Any]) -> Dict[str, Any]:
    """提取个人资金特征分析可序列化摘要，控制缓存体积。"""
    if not isinstance(result, dict):
        return {}

    dimensions = result.get("dimensions", {})
    dimension_summary = {}
    if isinstance(dimensions, dict):
        for dim_name, dim_data in dimensions.items():
            if not isinstance(dim_data, dict):
                continue
            metrics = dim_data.get("metrics", {})
            if not isinstance(metrics, dict):
                metrics = {}
            dimension_summary[dim_name] = {
                "score": float(dim_data.get("score", 0) or 0),
                "description": str(dim_data.get("description", "") or ""),
                "metrics": {
                    "coverage_ratio": float(metrics.get("coverage_ratio", 0) or 0),
                    "gap": float(metrics.get("gap", 0) or 0),
                    "borrow_total": float(metrics.get("borrow_total", 0) or 0),
                    "transfer_total": float(metrics.get("transfer_total", 0) or 0),
                    "cash_total": float(metrics.get("cash_total", 0) or 0),
                },
            }

    summary = {
        "overall_feature": str(result.get("overall_feature", "") or ""),
        "risk_level": str(result.get("risk_level", "") or ""),
        "evidence_score": float(result.get("evidence_score", 0) or 0),
        "audit_description": (
            result.get("audit_description", [])[:5]
            if isinstance(result.get("audit_description", []), list)
            else []
        ),
        "risk_exclusions": (
            result.get("risk_exclusions", [])[:5]
            if isinstance(result.get("risk_exclusions", []), list)
            else []
        ),
        "red_flags": (
            result.get("red_flags", [])[:10]
            if isinstance(result.get("red_flags", []), list)
            else []
        ),
        "dimension_summary": dimension_summary,
    }
    return serialize_for_json(summary)


def _extract_income_yearly_for_finance(
    real_salary_analysis: Dict[str, Any], profile: Dict[str, Any]
) -> Dict[int, float]:
    """
    提取理财分析所需的年度收入口径（万元）。

    优先使用真实工资分析器输出；若缺失则回退到 profile.yearly_salary。
    """
    income_yearly: Dict[int, float] = {}

    if isinstance(real_salary_analysis, dict):
        yearly = real_salary_analysis.get("yearly_salary", {})
        if isinstance(yearly, dict):
            for year, amount in yearly.items():
                try:
                    income_yearly[int(year)] = float(amount or 0)
                except (TypeError, ValueError):
                    continue

    if income_yearly:
        return income_yearly

    yearly_salary = profile.get("yearly_salary", {}) or {}
    yearly_data = yearly_salary.get("yearly", {}) if isinstance(yearly_salary, dict) else {}
    if isinstance(yearly_data, dict):
        for year, year_stats in yearly_data.items():
            if not isinstance(year_stats, dict):
                continue
            try:
                year_total_yuan = float(year_stats.get("total", 0) or 0)
                income_yearly[int(year)] = year_total_yuan / 10000.0
            except (TypeError, ValueError):
                continue

    return income_yearly


def _extract_real_extra_income_types(profile: Dict[str, Any]) -> List[str]:
    """基于真实收入分类提取非工资收入类型。"""
    income_classification = (
        profile.get("income_classification", {})
        if isinstance(profile.get("income_classification", {}), dict)
        else {}
    )
    extra_income_types: List[str] = []

    legitimate_income = float(income_classification.get("legitimate_income", 0) or 0)
    unknown_income = float(income_classification.get("unknown_income", 0) or 0)
    suspicious_income = float(income_classification.get("suspicious_income", 0) or 0)

    if legitimate_income > 0:
        extra_income_types.append("可核实合法收入")
    if unknown_income > 0:
        extra_income_types.append("来源待核实收入")
    if suspicious_income > 0:
        extra_income_types.append("可疑收入")

    return extra_income_types


def _build_income_expense_match_summary(
    analyzer: IncomeExpenseMatchAnalyzer, profile: Dict[str, Any]
) -> Dict[str, Any]:
    """统一以真实收入/真实支出和年度工资口径生成收支匹配分析。"""
    summary_obj = (
        profile.get("summary", {})
        if isinstance(profile.get("summary", {}), dict)
        else {}
    )
    yearly_salary = (
        profile.get("yearly_salary", {})
        if isinstance(profile.get("yearly_salary", {}), dict)
        else {}
    )
    salary_summary = (
        yearly_salary.get("summary", {})
        if isinstance(yearly_salary.get("summary", {}), dict)
        else {}
    )

    real_income_wan = float(summary_obj.get("real_income", 0) or 0) / 10000.0
    real_expense_wan = float(summary_obj.get("real_expense", 0) or 0) / 10000.0
    salary_total_wan = float(salary_summary.get("total", 0) or 0) / 10000.0
    extra_income_wan = max(0.0, real_income_wan - salary_total_wan)
    extra_income_types = _extract_real_extra_income_types(profile)

    return analyzer.analyze(
        real_salary=salary_total_wan,
        effective_expense=real_expense_wan,
        extra_income=extra_income_wan,
        extra_income_types=extra_income_types,
        data_quality_note="",
    )


def _refresh_profile_real_metrics(
    profile: Dict[str, Any],
    df: pd.DataFrame,
    person_name: str,
    family_members: List[str],
    income_expense_match_analyzer: IncomeExpenseMatchAnalyzer,
) -> None:
    """在家庭关系补齐后，统一刷新真实收入相关口径。"""
    metrics = financial_profiler.recalculate_income_metrics(
        df,
        person_name,
        profile.get("income_structure", {}) if isinstance(profile.get("income_structure", {}), dict) else {},
        profile.get("wealth_management", {}) if isinstance(profile.get("wealth_management", {}), dict) else {},
        profile.get("fund_flow", {}) if isinstance(profile.get("fund_flow", {}), dict) else {},
        yearly_salary=(
            profile.get("yearly_salary", {})
            if isinstance(profile.get("yearly_salary", {}), dict)
            else {}
        ),
        family_members=family_members,
    )

    summary = profile.setdefault("summary", {})
    summary["real_income"] = metrics["real_income"]
    summary["real_expense"] = metrics["real_expense"]
    summary["offset_detail"] = metrics["offset_detail"]

    salary_income = 0.0
    income_structure = profile.get("income_structure", {})
    if isinstance(income_structure, dict):
        salary_income = float(income_structure.get("salary_income", 0) or 0)
    summary["salary_ratio"] = (
        salary_income / metrics["real_income"] if metrics["real_income"] > 0 else 0
    )

    profile["real_income"] = metrics["real_income"]
    profile["real_expense"] = metrics["real_expense"]
    profile["income_classification"] = metrics["income_classification"]
    profile["income_expense_match_analysis"] = serialize_for_json(
        _build_income_expense_match_summary(income_expense_match_analyzer, profile)
    )


def _normalize_direct_transfer_description_text(
    raw_description: Any, bank: str = ""
) -> tuple[str, str]:
    return normalize_direct_transfer_description_text(raw_description, bank)


def _normalize_serialized_suspicions_payload(suspicions: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(suspicions, dict):
        return suspicions

    direct_transfers = suspicions.get("directTransfers")
    if not isinstance(direct_transfers, list):
        return suspicions

    normalized_records_by_key: Dict[tuple, Dict[str, Any]] = {}
    ordered_keys: List[tuple] = []
    for record in direct_transfers:
        if not isinstance(record, dict):
            continue

        normalized_record = dict(record)
        normalized_description, raw_description = _normalize_direct_transfer_description_text(
            normalized_record.get("description", ""),
            normalized_record.get("bank", ""),
        )
        normalized_record["description"] = (
            normalized_description or "核心人员与涉案企业直接资金往来"
        )

        if raw_description and raw_description != normalized_description:
            evidence_refs = normalized_record.get("evidenceRefs", {})
            if not isinstance(evidence_refs, dict):
                evidence_refs = {}
            else:
                evidence_refs = dict(evidence_refs)
            evidence_refs.setdefault("rawDescription", raw_description)
            normalized_record["evidenceRefs"] = evidence_refs

        dedupe_key = build_serialized_direct_transfer_dedupe_key(normalized_record)
        existing = normalized_records_by_key.get(dedupe_key)
        if existing is None:
            normalized_records_by_key[dedupe_key] = normalized_record
            ordered_keys.append(dedupe_key)
            continue

        direction = str(normalized_record.get("direction", "") or "")
        person = (
            str(normalized_record.get("to", "") or "")
            if direction == "receive"
            else str(normalized_record.get("from", "") or "")
        )
        company = (
            str(normalized_record.get("from", "") or "")
            if direction == "receive"
            else str(normalized_record.get("to", "") or "")
        )

        if score_direct_transfer_record(
            normalized_record,
            person=person,
            company=company,
        ) > score_direct_transfer_record(
            existing,
            person=person,
            company=company,
        ):
            normalized_records_by_key[dedupe_key] = normalized_record

    normalized_suspicions = dict(suspicions)
    normalized_suspicions["directTransfers"] = [
        normalized_records_by_key[key] for key in ordered_keys
    ]
    return normalized_suspicions


_PERSON_ID_VALUE_PATTERN = re.compile(r"^[1-9]\d{16}[\dXx]$")
_ID_TO_NAME_ID_FIELDS = (
    "entity_id",
    "owner_id",
    "id_number",
    "passenger_id",
    "person_id",
    "subjectId",
    "subject_id",
    "注册身份证号",
)
_ID_TO_NAME_NAME_FIELDS = (
    "entity_name",
    "owner_name",
    "name",
    "passenger_name_cn",
    "subjectName",
    "subject_name",
    "注册姓名",
)
_FILE_ID_COLUMNS = (
    "身份证号",
    "证件号码",
    "自然人证件号码",
    "权利人证件号码",
    "旅客证件号",
    "注册身份证号",
)
_FILE_NAME_COLUMNS = (
    "姓名",
    "自然人姓名",
    "自然人对象名称",
    "权利人名称",
    "机动车所有人",
    "旅客中文姓名",
    "注册姓名",
)


def _normalize_person_id_value(value: Any) -> Optional[str]:
    text = str(value or "").strip().upper()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    if _PERSON_ID_VALUE_PATTERN.fullmatch(text):
        return text
    extracted = extract_id_from_filename(text)
    if extracted and _PERSON_ID_VALUE_PATTERN.fullmatch(extracted):
        return extracted
    return None


def _normalize_person_name_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def _register_id_name_candidate(
    id_to_name_map: Dict[str, str],
    confidence_scores: Dict[str, int],
    person_id: Any,
    person_name: Any,
    confidence: int,
    known_person_names: Optional[set[str]] = None,
) -> None:
    normalized_id = _normalize_person_id_value(person_id)
    normalized_name = _normalize_person_name_value(person_name)
    if not normalized_id or not normalized_name:
        return
    if known_person_names and normalized_name not in known_person_names:
        return

    if confidence >= confidence_scores.get(normalized_id, 0):
        id_to_name_map[normalized_id] = normalized_name
        confidence_scores[normalized_id] = confidence


def _infer_person_name_from_filename(
    file_name: str, known_person_names: Optional[set[str]]
) -> tuple[str, int]:
    stem = Path(file_name).stem
    if known_person_names:
        matched_names = sorted(
            {name for name in known_person_names if name and name in stem},
            key=len,
            reverse=True,
        )
        if len(matched_names) == 1:
            return matched_names[0], 2

    for part in re.split(r"[_\-\s]+", stem):
        candidate = part.strip("()[]【】（）")
        if not candidate or _normalize_person_id_value(candidate):
            continue
        if re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", candidate):
            return candidate, 1

    return "", 0


def _extract_id_name_pairs_from_dataframe(
    df: pd.DataFrame, known_person_names: Optional[set[str]]
) -> List[tuple[str, str]]:
    if df is None or df.empty:
        return []

    id_columns = [column for column in _FILE_ID_COLUMNS if column in df.columns]
    name_columns = [column for column in _FILE_NAME_COLUMNS if column in df.columns]
    if not id_columns or not name_columns:
        return []

    pairs: List[tuple[str, str]] = []
    for _, row in df.head(200).iterrows():
        normalized_id = None
        for id_column in id_columns:
            normalized_id = _normalize_person_id_value(row.get(id_column))
            if normalized_id:
                break
        if not normalized_id:
            continue

        normalized_name = ""
        for name_column in name_columns:
            candidate_name = _normalize_person_name_value(row.get(name_column))
            if not candidate_name:
                continue
            if not known_person_names or candidate_name in known_person_names:
                normalized_name = candidate_name
                break

        if normalized_name:
            pairs.append((normalized_id, normalized_name))

    return pairs


def _read_id_name_pairs_from_file(
    file_path: str, known_person_names: Optional[set[str]]
) -> List[tuple[str, str]]:
    suffix = Path(file_path).suffix.lower()
    pairs: List[tuple[str, str]] = []

    try:
        if suffix == ".csv":
            for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
                try:
                    df = pd.read_csv(file_path, dtype=str, nrows=200, encoding=encoding)
                    return _extract_id_name_pairs_from_dataframe(df, known_person_names)
                except UnicodeDecodeError:
                    continue
            return []

        if suffix in {".xlsx", ".xls"}:
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str, nrows=200)
                pairs.extend(_extract_id_name_pairs_from_dataframe(df, known_person_names))
                if pairs:
                    break
    except Exception as exc:
        logging.getLogger(__name__).debug(f"读取身份证映射候选文件失败: {file_path}, {exc}")

    return pairs


def _collect_id_name_pairs_from_external_data(
    payload: Any, known_person_names: Optional[set[str]]
) -> List[tuple[str, str]]:
    pairs: List[tuple[str, str]] = []

    def _visit(node: Any) -> None:
        if isinstance(node, dict):
            for id_field in _ID_TO_NAME_ID_FIELDS:
                normalized_id = _normalize_person_id_value(node.get(id_field))
                if not normalized_id:
                    continue
                for name_field in _ID_TO_NAME_NAME_FIELDS:
                    normalized_name = _normalize_person_name_value(node.get(name_field))
                    if not normalized_name:
                        continue
                    if known_person_names and normalized_name not in known_person_names:
                        continue
                    pairs.append((normalized_id, normalized_name))
                    break

            for value in node.values():
                _visit(value)
        elif isinstance(node, list):
            for item in node:
                _visit(item)

    _visit(payload)
    return pairs


def _build_id_to_name_map(
    data_dir: str, external_data: Optional[Dict[str, Any]], known_person_names: List[str]
) -> Dict[str, str]:
    id_to_name_map: Dict[str, str] = {}
    confidence_scores: Dict[str, int] = {}
    known_person_name_set = {name for name in known_person_names if name}
    data_root = Path(data_dir)

    if data_root.exists():
        for file_path in sorted(data_root.rglob("*")):
            if (
                not file_path.is_file()
                or file_path.suffix.lower() not in {".xlsx", ".xls", ".csv"}
            ):
                continue

            normalized_id = extract_id_from_filename(file_path.name)
            inferred_name, confidence = _infer_person_name_from_filename(
                file_path.name, known_person_name_set
            )
            if normalized_id and inferred_name:
                _register_id_name_candidate(
                    id_to_name_map,
                    confidence_scores,
                    normalized_id,
                    inferred_name,
                    confidence,
                    known_person_name_set,
                )

            for person_id, person_name in _read_id_name_pairs_from_file(
                str(file_path), known_person_name_set
            ):
                _register_id_name_candidate(
                    id_to_name_map,
                    confidence_scores,
                    person_id,
                    person_name,
                    3,
                    known_person_name_set,
                )

    for person_id, person_name in _collect_id_name_pairs_from_external_data(
        external_data or {}, known_person_name_set
    ):
        _register_id_name_candidate(
            id_to_name_map,
            confidence_scores,
            person_id,
            person_name,
            3,
            known_person_name_set,
        )

    return id_to_name_map


def _group_suspicions_by_entity(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for record in records or []:
        if not isinstance(record, dict):
            continue
        entity_name = str(record.get("entity_name") or record.get("entity") or "").strip()
        if not entity_name:
            entity_name = "未知实体"
        grouped.setdefault(entity_name, []).append(record)
    return grouped


def _merge_plugin_suspicions(
    suspicions: Dict[str, Any], plugin_results: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    merged = dict(suspicions or {})

    if plugin_results.get("direct_transfer"):
        merged["direct_transfers"] = plugin_results["direct_transfer"]
    if plugin_results.get("cash_collision"):
        merged["cash_collisions"] = plugin_results["cash_collision"]
    if plugin_results.get("time_anomaly"):
        merged["timeSeriesAlerts"] = plugin_results["time_anomaly"]
    if plugin_results.get("fixed_frequency"):
        merged["fixed_frequency"] = _group_suspicions_by_entity(
            plugin_results["fixed_frequency"]
        )

    amount_pattern_records: List[Dict[str, Any]] = []
    for detector_name in ("round_amount", "fixed_amount"):
        detector_records = plugin_results.get(detector_name) or []
        if detector_records:
            merged[detector_name] = detector_records
            amount_pattern_records.extend(detector_records)
    if amount_pattern_records:
        merged["amount_patterns"] = _group_suspicions_by_entity(amount_pattern_records)

    for detector_name in ("frequency_anomaly", "suspicious_pattern"):
        detector_records = plugin_results.get(detector_name) or []
        if detector_records:
            merged[detector_name] = detector_records

    return merged


def serialize_suspicions(suspicions: Dict) -> Dict:
    """
    序列化疑点数据

    将后端 snake_case 字段名转换为前端期望的 camelCase 字段名。
    包括顶层字段和每条记录内部的字段。
    """

    def convert_cash_collision(record: Dict) -> Dict:
        """转换单条 cash_collision 记录"""
        evidence_refs = record.get("evidence_refs", {})
        if not isinstance(evidence_refs, dict):
            evidence_refs = {}
        withdrawal_row = record.get("withdrawal_row")
        if withdrawal_row is None:
            withdrawal_row = evidence_refs.get("withdrawal_row")
        deposit_row = record.get("deposit_row")
        if deposit_row is None:
            deposit_row = evidence_refs.get("deposit_row")
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
            "withdrawalRow": withdrawal_row,
            "depositRow": deposit_row,
            "withdrawalTransactionId": record.get("withdrawal_transaction_id", ""),
            "depositTransactionId": record.get("deposit_transaction_id", ""),
            "evidenceRefs": evidence_refs,
            "type": record.get("type", ""),
            "patternCategory": record.get("pattern_category", ""),
        }

    def convert_direct_transfer(record: Dict) -> Dict:
        """转换单条 direct_transfer 记录"""
        evidence_refs = record.get("evidence_refs", {})
        if not isinstance(evidence_refs, dict):
            evidence_refs = {}
        source_row_index = record.get("source_row_index")
        if source_row_index is None:
            source_row_index = evidence_refs.get("source_row_index")
        transaction_id = record.get("transaction_id", "")
        if not transaction_id:
            transaction_id = evidence_refs.get("transaction_id", "")
        direction = record.get("direction", "")
        bank = record.get("bank", "")
        normalized_description, raw_description = _normalize_direct_transfer_description_text(
            record.get("description", ""), bank
        )
        if raw_description and raw_description != normalized_description:
            evidence_refs = dict(evidence_refs)
            evidence_refs.setdefault("rawDescription", raw_description)
        if direction == "receive":
            from_party = record.get("company", "")
            to_party = record.get("person", "")
        else:
            from_party = record.get("person", "")
            to_party = record.get("company", "")
        return {
            # 直接往来日志按真实资金方向展示 from/to
            "from": from_party,
            "to": to_party,
            "amount": record.get("amount", 0),
            "date": _format_date(record.get("date")),
            "description": normalized_description or "核心人员与涉案企业直接资金往来",
            # 扩展字段 (camelCase)
            "direction": direction,
            "bank": bank,
            "sourceFile": record.get("source_file", ""),
            "sourceRowIndex": source_row_index,
            "transactionId": transaction_id,
            "evidenceRefs": evidence_refs,
            "riskLevel": record.get("risk_level", "low"),
            "riskReason": record.get("risk_reason", ""),
        }

    def convert_holiday_transaction(record: Dict) -> Dict:
        """转换单条 holiday_transaction 记录。"""
        evidence_refs = record.get("evidence_refs", {})
        if not isinstance(evidence_refs, dict):
            evidence_refs = {}
        source_row_index = evidence_refs.get("source_row_index")
        transaction_id = evidence_refs.get("transaction_id", "")
        return {
            "date": _format_date(record.get("date")),
            "amount": record.get("amount", 0),
            "description": record.get("description", ""),
            "holidayName": record.get("holiday_name", record.get("holidayName", "")),
            "holidayPeriod": record.get(
                "holiday_period", record.get("holidayPeriod", "")
            ),
            "counterparty": record.get("counterparty", ""),
            "direction": record.get("direction", ""),
            "bank": record.get("bank", ""),
            "sourceFile": record.get("source_file", ""),
            "sourceRowIndex": source_row_index,
            "transactionId": transaction_id,
            "evidenceRefs": evidence_refs,
            "riskLevel": record.get("risk_level", "medium"),
            "riskReason": record.get("risk_reason", ""),
        }

    def convert_wallet_alert(record: Dict) -> Dict:
        """转换单条电子钱包预警记录。"""
        return {
            "person": record.get("person", ""),
            "counterparty": record.get("counterparty", ""),
            "date": _format_date(record.get("date")),
            "amount": record.get("amount", 0),
            "description": record.get("description", ""),
            "riskLevel": record.get("risk_level", "medium"),
            "riskReason": record.get("risk_reason", ""),
            "alertType": record.get("alert_type", ""),
            "riskScore": record.get("risk_score"),
            "confidence": record.get("confidence"),
            "ruleCode": record.get("rule_code", ""),
            "evidenceSummary": record.get("evidence_summary", ""),
        }

    def convert_standard_suspicion(record: Dict) -> Dict:
        """转换标准 Suspicion 模型记录为统一 camelCase 输出。"""
        if not isinstance(record, dict):
            return record

        normalized = dict(record)
        alias_mapping = {
            "suspicionId": ("suspicionId", "suspicion_id"),
            "suspicionType": ("suspicionType", "suspicion_type"),
            "relatedTransactions": ("relatedTransactions", "related_transactions"),
            "detectionDate": ("detectionDate", "detection_date"),
            "entityName": ("entityName", "entity_name"),
        }

        for target_key, aliases in alias_mapping.items():
            found = False
            value = None
            for alias in aliases:
                if alias in normalized:
                    value = normalized.pop(alias)
                    found = True
                    break
            if not found:
                continue
            normalized[target_key] = (
                _format_date(value) if target_key == "detectionDate" else value
            )

        return normalized

    def convert_grouped_standard_suspicions(
        grouped_records: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not isinstance(grouped_records, dict):
            return grouped_records
        return {
            entity_name: [convert_standard_suspicion(record) for record in records]
            for entity_name, records in grouped_records.items()
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
        "round_amount": "roundAmount",
        "fixed_amount": "fixedAmount",
        "frequency_anomaly": "frequencyAnomaly",
        "suspicious_pattern": "suspiciousPattern",
        "aml_alerts": "amlAlerts",
        "credit_alerts": "creditAlerts",
        "hidden_assets_with_context": "hiddenAssetsWithContext",
        "timeSeriesAlerts": "timeSeriesAlerts",
        "wallet_alerts": "walletAlerts",
    }

    result = {}
    for key, value in suspicions.items():
        new_key = field_mapping.get(key, key)

        # 对特定字段的记录进行内部转换
        if key == "cash_collisions" and isinstance(value, list):
            result[new_key] = [convert_cash_collision(r) for r in value]
        elif key == "cash_timing_patterns" and isinstance(value, list):
            result[new_key] = [convert_cash_collision(r) for r in value]
        elif key == "direct_transfers" and isinstance(value, list):
            result[new_key] = [convert_direct_transfer(r) for r in value]
        elif key == "holiday_transactions" and isinstance(value, dict):
            result[new_key] = {
                entity: [convert_holiday_transaction(r) for r in records]
                for entity, records in value.items()
            }
        elif key in (
            "round_amount",
            "fixed_amount",
            "frequency_anomaly",
            "suspicious_pattern",
            "timeSeriesAlerts",
        ) and isinstance(value, list):
            result[new_key] = [convert_standard_suspicion(r) for r in value]
        elif key in ("fixed_frequency", "amount_patterns") and isinstance(value, dict):
            result[new_key] = convert_grouped_standard_suspicions(value)
        elif key == "wallet_alerts" and isinstance(value, list):
            result[new_key] = [convert_wallet_alert(r) for r in value]
        else:
            result[new_key] = value

    return result


def _wallet_graph_node_group(node_name: str, core_persons: List[str], companies: List[str]) -> str:
    """为电子钱包图谱节点选择分组。"""
    if node_name in core_persons:
        return "core"
    if node_name in companies:
        return "involved_company"
    return "wallet_counterparty"


def _create_wallet_graph_additions(
    wallet_data: Dict[str, Any],
    core_persons: List[str],
    companies: List[str],
    existing_node_ids: Optional[set] = None,
    existing_edge_keys: Optional[set] = None,
    max_subjects: int = 12,
    max_counterparties_per_subject: int = 4,
) -> Dict[str, Any]:
    """基于电子钱包补充摘要生成图谱增量节点、边和报告区块。"""
    if not isinstance(wallet_data, dict):
        return {"nodes": [], "edges": [], "report": {"wallet_alerts": [], "wallet_counterparties": []}}

    existing_node_ids = set(existing_node_ids or set())
    existing_edge_keys = set(existing_edge_keys or set())
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    wallet_counterparties: List[Dict[str, Any]] = []

    subjects = wallet_data.get("subjects", []) or []
    def _wallet_subject_total(item: Dict[str, Any]) -> float:
        platforms = item.get("platforms", {}) or {}
        alipay = platforms.get("alipay", {}) or {}
        wechat = platforms.get("wechat", {}) or {}
        return float(alipay.get("incomeTotalYuan", 0) or 0) + float(
            alipay.get("expenseTotalYuan", 0) or 0
        ) + float(wechat.get("incomeTotalYuan", 0) or 0) + float(
            wechat.get("expenseTotalYuan", 0) or 0
        )

    ranked_subjects = sorted(
        [item for item in subjects if isinstance(item, dict) and item.get("matchedToCore")],
        key=lambda item: (-_wallet_subject_total(item), str(item.get("subjectName", ""))),
    )[:max_subjects]

    for subject in ranked_subjects:
        person = str(subject.get("subjectName") or subject.get("subjectId") or "").strip()
        if not person:
            continue
        if person not in existing_node_ids:
            nodes.append(
                {
                    "id": person,
                    "label": person,
                    "group": _wallet_graph_node_group(person, core_persons, companies),
                    "size": 34 if person in core_persons else 18,
                }
            )
            existing_node_ids.add(person)

        platforms = subject.get("platforms", {}) or {}
        counterparty_map: Dict[str, Dict[str, Any]] = {}
        for platform_key, platform_label in (("alipay", "支付宝"), ("wechat", "财付通")):
            platform_summary = platforms.get(platform_key, {}) or {}
            for item in (platform_summary.get("topCounterparties", []) or [])[:max_counterparties_per_subject]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                stat = counterparty_map.setdefault(
                    name,
                    {"platforms": set(), "amount": 0.0, "count": 0},
                )
                stat["platforms"].add(platform_label)
                try:
                    stat["amount"] += float(item.get("totalAmountYuan", 0) or 0)
                except (TypeError, ValueError):
                    pass
                try:
                    stat["count"] += int(item.get("count", 0) or 0)
                except (TypeError, ValueError):
                    pass

        ranked_counterparties = sorted(
            counterparty_map.items(),
            key=lambda kv: (kv[1]["amount"], kv[1]["count"], kv[0]),
            reverse=True,
        )[:max_counterparties_per_subject]

        for counterparty, stat in ranked_counterparties:
            if counterparty not in existing_node_ids:
                nodes.append(
                    {
                        "id": counterparty,
                        "label": counterparty,
                        "group": _wallet_graph_node_group(counterparty, core_persons, companies),
                        "size": 22 if counterparty in companies else 18,
                    }
                )
                existing_node_ids.add(counterparty)

            edge_key = (person, counterparty, "wallet")
            if edge_key in existing_edge_keys:
                continue
            existing_edge_keys.add(edge_key)

            amount_wan = round(stat["amount"] / 10000, 2)
            platforms_text = " / ".join(sorted(stat["platforms"])) or "电子钱包"
            edges.append(
                {
                    "from": person,
                    "to": counterparty,
                    "value": max(amount_wan, 0.2),
                    "type": "wallet",
                    "title": (
                        f"[电子钱包] {person} → {counterparty}\n"
                        f"平台: {platforms_text}\n"
                        f"累计金额: {amount_wan:.2f}万元 ({stat['count']}笔)"
                    ),
                }
            )
            wallet_counterparties.append(
                {
                    "person": person,
                    "counterparty": counterparty,
                    "platforms": sorted(stat["platforms"]),
                    "amount": round(stat["amount"], 2),
                    "count": stat["count"],
                }
            )

    wallet_alerts = []
    for alert in (wallet_data.get("alerts", []) or [])[:30]:
        if not isinstance(alert, dict):
            continue
        wallet_alerts.append(
            {
                "person": alert.get("person", ""),
                "counterparty": alert.get("counterparty", ""),
                "amount": alert.get("amount", 0),
                "date": alert.get("date", ""),
                "description": alert.get("description", ""),
                "risk_level": alert.get("risk_level", "medium"),
                "alert_type": alert.get("alert_type", ""),
                "risk_reason": alert.get("risk_reason", ""),
            }
        )

    wallet_counterparties.sort(
        key=lambda item: (
            -(float(item.get("amount", 0) or 0)),
            -int(item.get("count", 0) or 0),
            str(item.get("counterparty", "")),
        )
    )

    return {
        "nodes": nodes,
        "edges": edges,
        "report": {
            "wallet_alerts": wallet_alerts,
            "wallet_counterparties": wallet_counterparties[:20],
        },
    }


def _augment_graph_cache_with_wallet_data(
    graph_cache: Optional[Dict[str, Any]],
    wallet_data: Dict[str, Any],
    core_persons: List[str],
    companies: List[str],
) -> Dict[str, Any]:
    """把电子钱包补充边增量并入图谱缓存。"""
    def _merge_wallet_report(
        existing_report: Optional[Dict[str, Any]],
        new_report: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        existing = existing_report if isinstance(existing_report, dict) else {}
        current = new_report if isinstance(new_report, dict) else {}

        def _dedupe_records(
            records: List[Dict[str, Any]],
            key_builder,
        ) -> List[Dict[str, Any]]:
            seen = set()
            merged_records: List[Dict[str, Any]] = []
            for item in records:
                if not isinstance(item, dict):
                    continue
                key = key_builder(item)
                if key in seen:
                    continue
                seen.add(key)
                merged_records.append(item)
            return merged_records

        merged_alerts = _dedupe_records(
            list(existing.get("wallet_alerts", []) or [])
            + list(current.get("wallet_alerts", []) or []),
            lambda item: (
                str(item.get("person") or ""),
                str(item.get("counterparty") or ""),
                str(item.get("date") or ""),
                str(item.get("alert_type") or ""),
                str(item.get("description") or ""),
                str(item.get("amount") or ""),
            ),
        )
        merged_counterparties = _dedupe_records(
            list(existing.get("wallet_counterparties", []) or [])
            + list(current.get("wallet_counterparties", []) or []),
            lambda item: (
                str(item.get("person") or ""),
                str(item.get("counterparty") or ""),
                tuple(str(platform) for platform in list(item.get("platforms", []) or [])),
                str(item.get("amount") or ""),
                str(item.get("count") or ""),
            ),
        )
        return {
            "wallet_alerts": merged_alerts[:30],
            "wallet_counterparties": merged_counterparties[:20],
        }

    base = dict(graph_cache or {})
    nodes = list(base.get("nodes", []) or [])
    edges = list(base.get("edges", []) or [])
    existing_node_ids = {
        str(node.get("id"))
        for node in nodes
        if isinstance(node, dict) and node.get("id")
    }
    existing_edge_keys = {
        (
            str(edge.get("from") or edge.get("source") or ""),
            str(edge.get("to") or edge.get("target") or ""),
            str(edge.get("type") or "base"),
        )
        for edge in edges
        if isinstance(edge, dict)
    }

    additions = _create_wallet_graph_additions(
        wallet_data,
        core_persons=core_persons,
        companies=companies,
        existing_node_ids=existing_node_ids,
        existing_edge_keys=existing_edge_keys,
    )

    if additions["nodes"]:
        nodes.extend(additions["nodes"])
    if additions["edges"]:
        edges.extend(additions["edges"])

    base["nodes"] = nodes
    base["edges"] = edges
    wallet_report = _merge_wallet_report(base.get("walletReport", {}), additions.get("report", {}))
    if wallet_report:
        base["walletReport"] = wallet_report
    return base


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
                "regular_repayments": "regular_repayment",
                "no_repayment_loans": "no_repayment",
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
        elif key == "relatedParty":
            related_result = value if isinstance(value, dict) else {}
            details = []

            related_type_mapping = {
                "direct_flows": "direct_flow",
                "third_party_relays": "third_party_relay",
                "fund_loops": "fund_loop",
                "discovered_nodes": "discovered_node",
                "relationship_clusters": "relationship_cluster",
            }

            for array_name, type_name in related_type_mapping.items():
                for item in related_result.get(array_name, []):
                    record = item.copy() if isinstance(item, dict) else {}
                    record["_type"] = type_name
                    details.append(record)

            serialized["relatedParty"] = {
                "summary": related_result.get("summary", {}),
                "details": details,
                **{
                    k: v
                    for k, v in related_result.items()
                    if k not in ["summary", "details"]
                },
            }
        elif key == "aggregation":
            serialized[key] = serialize_for_json(value)
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
    time_series = analysis_results.get("timeSeries")
    if isinstance(time_series, dict) and "alerts" in time_series:
        alerts = time_series.get("alerts")
        if alerts:
            enhanced["timeSeriesAlerts"] = alerts
        elif "timeSeriesAlerts" not in enhanced:
            enhanced["timeSeriesAlerts"] = []
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

    if analysis_state.status != "running":
        analysis_state.clear_stop_request()
    analysis_state.start_time = datetime.now()
    analysis_state.end_time = None
    analysis_state.results = None
    analysis_state.update(
        status="running", progress=0, phase="初始化分析引擎...", error=None
    )
    log_capture_started = False

    try:
        if analysis_state.is_stop_requested():
            raise AnalysisStoppedError("分析启动前已收到停止请求")

        data_dir = analysis_config.inputDirectory
        output_dir = analysis_config.outputDirectory or str(OUTPUT_DIR)

        # 转换为绝对路径
        data_dir = os.path.abspath(os.path.expanduser(data_dir))
        output_dir = os.path.abspath(os.path.expanduser(output_dir))

        # 验证输入目录存在
        if not os.path.exists(data_dir):
            error_msg = f"输入目录不存在: {data_dir}"
            logger.error(error_msg)
            analysis_state.update(status="failed", phase=error_msg)
            return

        if not os.path.isdir(data_dir):
            error_msg = f"输入路径不是目录: {data_dir}"
            logger.error(error_msg)
            analysis_state.update(status="failed", phase=error_msg)
            return

        runtime_log_paths = _start_analysis_runtime_log_capture(
            output_dir,
            analysis_state.start_time,
        )
        log_capture_started = True
        output_dirs = create_output_directories(output_dir)
        logger.info(f"输入目录 (绝对路径): {data_dir}")
        logger.info(f"输出目录 (绝对路径): {output_dir}")

        # 更新全局配置
        global _current_config
        _current_config["inputDirectory"] = data_dir
        _current_config["outputDirectory"] = output_dir
        config.LARGE_CASH_THRESHOLD = analysis_config.cashThreshold
        if analysis_config.timeWindow is not None:
            config.CASH_TIME_WINDOW_HOURS = analysis_config.timeWindow

        saved_primary_config = _load_saved_primary_targets_config(data_dir, output_dir)

        # ========================================================================
        # 清除旧缓存（点击"开始分析"时自动清除）
        # ========================================================================
        try:
            cache_dir = output_dirs["analysis_cache"]
            results_dir = output_dirs["analysis_results"]

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
            _attach_analysis_results_log_mirror(output_dirs["analysis_results"])

            logger.info(f"  ✓ 已清除旧缓存: {cache_dir}, {results_dir}")
            logger.info(
                "分析日志固化已启用: run=%s latest=%s mirror=%s",
                runtime_log_paths.get("runLog", ""),
                runtime_log_paths.get("latestLog", ""),
                _get_last_analysis_log_paths().get("resultsMirror", ""),
            )
            broadcast_log("INFO", "  ✓ 已清除旧缓存，开始新分析")
        except Exception as e:
            logger.warning(f"  ⚠ 清除缓存失败: {e}，继续分析...")

        _raise_if_analysis_stopped("分析已停止")

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
        _raise_if_analysis_stopped("文件扫描后收到停止请求")

        # ========================================================================
        # Phase 2: 数据清洗 (15%)
        # ========================================================================
        analysis_state.update(progress=15, phase="数据清洗与标准化...")
        broadcast_log("INFO", "▶ Phase 2: 数据清洗与标准化...")
        logger.info("开始数据清洗...")

        phase2_start = time.time()

        cleaned_data = {}

        total_entities = len(persons) + len(companies)
        broadcast_log(
            "INFO",
            f"  ↻ 待处理实体: {total_entities} 个 ({len(persons)} 个人 + {len(companies)} 企业)",
        )

        # 清洗个人数据
        for i, p in enumerate(persons):
            _raise_if_analysis_stopped(f"清洗 {p} 时收到停止请求")
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
            _raise_if_analysis_stopped(f"清洗 {c} 时收到停止请求")
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
        _raise_if_analysis_stopped("数据清洗后收到停止请求")

        # ========================================================================
        # Phase 3: 线索提取 (30%)
        # ========================================================================
        analysis_state.update(progress=30, phase="提取关联线索...")
        broadcast_log("INFO", "▶ Phase 3: 提取关联线索...")

        phase3_start = time.time()
        clue_persons, clue_companies = _load_data_extractor().extract_all_clues(data_dir)
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
        _raise_if_analysis_stopped("线索提取后收到停止请求")

        # ========================================================================
        # Phase 4: 外部数据提取 (40%) ← 🔄 关键改进: 全部提取器提前执行!
        # ========================================================================
        analysis_state.update(progress=40, phase="提取外部数据源 (P0/P1/P2)...")
        broadcast_log("INFO", "▶ Phase 4: 提取外部数据源 (18个提取器)...")
        logger.info("🔄 [重构] 开始提取全部外部数据源 (18个提取器)...")

        # 验证数据目录存在
        if not os.path.exists(data_dir):
            logger.error(f"数据目录不存在: {data_dir}")
            raise ValueError(f"数据目录不存在: {data_dir}")

        phase4_start = time.time()

        external_data = {
            "p0": {},  # P0: 核心上下文
            "p1": {},  # P1: 资产数据
            "p2": {},  # P2: 行为数据
            "id_to_name_map": {},  # 身份证号到人名的映射
            "wallet": {},  # 电子钱包补充数据
        }
        wallet_artifact_bundle = wallet_data_extractor.empty_wallet_artifact_bundle()

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

        # P0.6: 国税登记及纳税信息
        try:
            tax_data = tax_info_extractor.extract_tax_data(data_dir)
            external_data["p0"]["tax_data"] = tax_data
            logger.info(f"    ✓ 税务数据: {len(tax_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 税务数据提取失败: {e}")
            external_data["p0"]["tax_data"] = {}

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
            precise_property_data = _load_asset_extractor().extract_precise_property_info(
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

        # P2.3b: 同住址 / 同车违章
        try:
            coaddress_data = cohabitation_extractor.extract_coaddress_data(data_dir)
            coviolation_data = cohabitation_extractor.extract_coviolation_data(data_dir)
            external_data["p2"]["coaddress_data"] = coaddress_data
            external_data["p2"]["coviolation_data"] = coviolation_data
            logger.info(
                f"    ✓ 同住址/同车违章: {len(coaddress_data)} 个同住址主体, {len(coviolation_data)} 个同车主体"
            )
        except Exception as e:
            logger.warning(f"    ✗ 同住址/同车违章提取失败: {e}")
            external_data["p2"]["coaddress_data"] = {}
            external_data["p2"]["coviolation_data"] = {}

        # P2.4/P2.5: 铁路/航班出行
        _populate_transport_external_data(data_dir, external_data["p2"], logger)

        # 电子钱包补充数据（微信 / 支付宝 / 财付通）
        try:
            wallet_artifact_bundle = wallet_data_extractor.extract_wallet_artifact_bundle(
                data_dir,
                known_person_names=all_persons,
            )
            wallet_data = wallet_artifact_bundle.get("walletData", {})
            external_data["wallet"] = wallet_data
            wallet_summary = wallet_data.get("summary", {}) if isinstance(wallet_data, dict) else {}
            logger.info(
                "    ✓ 电子钱包补充数据: %s 个主体, %s 条财付通交易, %s 条支付宝交易",
                wallet_summary.get("subjectCount", 0),
                wallet_summary.get("tenpayTransactionCount", 0),
                wallet_summary.get("alipayTransactionCount", 0),
            )
        except Exception as e:
            logger.warning(f"    ✗ 电子钱包补充数据提取失败: {e}")
            external_data["wallet"] = wallet_data_extractor.empty_wallet_data()
            wallet_artifact_bundle = wallet_data_extractor.empty_wallet_artifact_bundle()

        phase4_duration = (time.time() - phase4_start) * 1000
        logging_config.log_performance(
            logger, "Phase 4-外部数据提取(全部)", phase4_duration
        )

        logger.info("🔄 [重构] 外部数据提取完成")
        broadcast_log("INFO", f"  ✓ 外部数据提取完成 (P0/P1/P2 共 18 个提取器)")
        _raise_if_analysis_stopped("外部数据提取后收到停止请求")

        # ========================================================================
        # Phase 5: 融合数据画像 (50%) ← 🔄 结合外部数据生成完整画像
        # ========================================================================
        analysis_state.update(progress=50, phase="生成融合数据画像...")
        broadcast_log("INFO", "▶ Phase 5: 生成融合数据画像...")
        logger.info("🔄 [重构] 生成包含外部数据的完整画像...")

        phase5_start = time.time()

        profiles = {}
        id_to_name_map = {}
        real_salary_income_analyzer = RealSalaryIncomeAnalyzer()
        income_expense_match_analyzer = IncomeExpenseMatchAnalyzer()
        personal_fund_feature_analyzer = PersonalFundFeatureAnalyzer()
        try:
            finance_product_analyzer = FinancialProductAnalyzer()
        except Exception as e:
            logger.warning(f"理财分析器初始化失败，使用回退阈值: {e}")

            class _FallbackFinanceThresholds:
                risk_score_high = 70

            finance_product_analyzer = FinancialProductAnalyzer(
                thresholds=_FallbackFinanceThresholds()
            )

        # 🔄 构建身份证号到人名的映射（兼容 CSV / 非标准文件名 / 外部数据主体信息）
        id_to_name_map = _build_id_to_name_map(
            data_dir,
            external_data,
            all_persons,
        )

        logger.info(f"身份证号映射表构建完成: {len(id_to_name_map)} 个人员")
        try:
            external_data["wallet"] = wallet_data_extractor.reconcile_wallet_data(
                external_data.get("wallet", {}),
                id_to_name_map=id_to_name_map,
                known_person_names=all_persons,
            )
        except Exception as exc:
            logger.warning(f"电子钱包补充数据主体映射修正失败: {exc}")
            external_data["wallet"] = external_data.get("wallet", {})
        # 企业登记信息按人员聚合（company_info 以 uscc 为 key，需要转换为按姓名索引）
        person_company_map = {}
        company_info_map = external_data["p0"].get("company_info", {})
        if isinstance(company_info_map, dict):
            for company in company_info_map.values():
                if not isinstance(company, dict):
                    continue
                related_to = str(company.get("related_to", "") or "").strip()
                if not related_to:
                    continue
                company_name = company.get("company_name") or company.get("name") or ""
                person_company_map.setdefault(related_to, []).append(
                    {
                        "name": company_name,
                        "company_name": company_name,
                        "uscc": company.get("uscc", ""),
                        "legal_representative": company.get(
                            "legal_representative", ""
                        ),
                        "registration_status": company.get("registration_status", ""),
                        "company_type": company.get("company_type", ""),
                        "industry": company.get("industry", ""),
                        "source_file": company.get("source_file", ""),
                        "related_to": related_to,
                    }
                )

        for entity, df in cleaned_data.items():
            _raise_if_analysis_stopped(f"生成 {entity} 画像时收到停止请求")
            try:
                # 1. 生成基础画像（区分个人和公司）
                if entity in all_companies:
                    # 公司使用专门的公司画像生成函数
                    profile = financial_profiler.build_company_profile(df, entity)
                else:
                    # 个人使用标准画像生成函数
                    profile = financial_profiler.generate_profile_report(df, entity)

                # 【修复】添加 entity_id（身份证号）到 profile
                # 从 id_to_name_map 反向查找
                entity_id = ""
                for id_num, mapped_name in id_to_name_map.items():
                    if mapped_name == entity:
                        entity_id = id_num
                        break
                profile["entity_id"] = entity_id

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
                related_companies = person_company_map.get(entity, [])
                if related_companies:
                    profile["registered_companies"] = related_companies
                    profile["company_registration"] = related_companies
                elif entity in external_data["p0"].get("company_info", {}):
                    profile["company_registration"] = external_data["p0"]["company_info"][
                        entity
                    ]

                # P0.4: 征信信息
                if entity in external_data["p0"].get("credit_data", {}):
                    profile["credit_info"] = external_data["p0"]["credit_data"][entity]

                # P0.5: 银行账户信息补充
                bank_account_info_map = external_data["p0"].get("bank_account_info", {})
                bank_account_subject = None
                if entity_id and entity_id in bank_account_info_map:
                    bank_account_subject = bank_account_info_map.get(entity_id)
                elif entity in bank_account_info_map:
                    bank_account_subject = bank_account_info_map.get(entity)
                if isinstance(bank_account_subject, dict):
                    existing = profile.get("bank_accounts_official", [])
                    existing_nums = {a.get("account_number") for a in existing}
                    for acc in bank_account_subject.get("accounts", []):
                        if acc.get("account_number") not in existing_nums:
                            existing.append(acc)
                    profile["bank_accounts_official"] = existing

                # P0.6: 税务数据补充
                tax_data_map = external_data["p0"].get("tax_data", {})
                tax_subject = None
                if entity_id and entity_id in tax_data_map:
                    tax_subject = tax_data_map.get(entity_id)
                elif entity in tax_data_map:
                    tax_subject = tax_data_map.get(entity)
                if isinstance(tax_subject, dict):
                    existing_tax_records = profile.get("tax_records", []) or []
                    existing_tax_keys = {
                        (
                            str(record.get("period_start") or ""),
                            str(record.get("period_end") or ""),
                            str(record.get("tax_name") or record.get("税种名称") or ""),
                            round(float(record.get("amount", record.get("应纳税额", 0)) or 0), 2),
                            str(record.get("source_file") or ""),
                        )
                        for record in existing_tax_records
                        if isinstance(record, dict)
                    }
                    for record in tax_subject.get("tax_records", []) or []:
                        if not isinstance(record, dict):
                            continue
                        record_key = (
                            str(record.get("period_start") or ""),
                            str(record.get("period_end") or ""),
                            str(record.get("tax_name") or record.get("税种名称") or ""),
                            round(float(record.get("amount", record.get("应纳税额", 0)) or 0), 2),
                            str(record.get("source_file") or ""),
                        )
                        if record_key in existing_tax_keys:
                            continue
                        existing_tax_records.append(record)
                        existing_tax_keys.add(record_key)
                    profile["tax_records"] = existing_tax_records
                    if tax_subject.get("registration") and not profile.get("tax_registration"):
                        profile["tax_registration"] = tax_subject.get("registration", {})
                    if tax_subject.get("employers"):
                        profile["tax_employers"] = tax_subject.get("employers", [])

                # 5. 🔄 融合外部数据 (P1 - 资产)
                # P1.1: 车辆 (使用身份证号映射)
                vehicle_data = external_data["p1"].get("vehicle_data", {})
                for person_id, vehicles in vehicle_data.items():
                    person_name = id_to_name_map.get(person_id, person_id)
                    if person_name == entity:
                        profile["vehicles"] = vehicles
                        break

                # P1.2: 理财产品（使用身份证号映射，与车辆/房产保持一致）
                wealth_data = external_data["p1"].get("wealth_product_data", {})
                for person_id, wealth_info in wealth_data.items():
                    person_name = id_to_name_map.get(person_id, person_id)
                    if person_name == entity:
                        profile["wealth_products"] = wealth_info.get("products", [])
                        profile["wealth_summary"] = wealth_info.get("summary", {})
                        break

                # P1.3: 证券（使用身份证号映射，与车辆/房产保持一致）
                securities_data = external_data["p1"].get("securities_data", {})
                for person_id, securities in securities_data.items():
                    person_name = id_to_name_map.get(person_id, person_id)
                    if person_name == entity:
                        profile["securities"] = securities
                        break
                # P1.4: 房产
                property_data = external_data["p1"].get("precise_property_data", {})
                for person_id, properties in property_data.items():
                    person_name = id_to_name_map.get(person_id, person_id)
                    if person_name == entity:
                        profile["properties_precise"] = properties
                        break

                # 6. 🔄 融合外部数据 (P2 - 行为)
                entity_id = next(
                    (person_id for person_id, person_name in id_to_name_map.items() if person_name == entity),
                    None,
                )
                wallet_subject = None
                wallet_data = external_data.get("wallet", {})
                if isinstance(wallet_data, dict):
                    wallet_subject = (
                        wallet_data.get("subjectsByName", {}).get(entity)
                        or (
                            wallet_data.get("subjectsById", {}).get(entity_id)
                            if entity_id
                            else None
                        )
                    )
                if wallet_subject:
                    profile["wallet_summary"] = wallet_subject

                # P2.1: 保险
                insurance_data = external_data["p2"].get("insurance_data", {})
                if entity_id and entity_id in insurance_data:
                    insurance_info = insurance_data[entity_id]
                    if isinstance(insurance_info, dict):
                        profile["insurance"] = insurance_info.get("policies", [])
                        profile["insurance_summary"] = insurance_info.get("summary", {})
                    else:
                        profile["insurance"] = insurance_info
                elif entity in insurance_data:
                    profile["insurance"] = insurance_data[entity]

                # P2.2: 出入境
                immigration_data = external_data["p2"].get("immigration_data", {})
                if entity_id and entity_id in immigration_data:
                    profile["immigration_records"] = immigration_data[entity_id]
                elif entity in immigration_data:
                    profile["immigration_records"] = immigration_data[entity]

                # P2.3: 住宿
                hotel_data = external_data["p2"].get("hotel_data", {})
                if entity_id and entity_id in hotel_data:
                    profile["hotel_records"] = hotel_data[entity_id]
                elif entity in hotel_data:
                    profile["hotel_records"] = hotel_data[entity]

                # P2.4: 铁路
                railway_data = external_data["p2"].get("railway_data", {})
                if entity_id and entity_id in railway_data:
                    profile["railway_records"] = railway_data[entity_id]
                elif entity in railway_data:
                    profile["railway_records"] = railway_data[entity]

                # P2.5: 航班
                flight_data = external_data["p2"].get("flight_data", {})
                if entity_id and entity_id in flight_data:
                    profile["flight_records"] = flight_data[entity_id]
                elif entity in flight_data:
                    profile["flight_records"] = flight_data[entity]

                # P2.6: 同住址
                coaddress_data = external_data["p2"].get("coaddress_data", {})
                if entity_id and entity_id in coaddress_data:
                    profile["coaddress_persons"] = coaddress_data[entity_id]
                elif entity in coaddress_data:
                    profile["coaddress_persons"] = coaddress_data[entity]

                # P2.7: 同车违章
                coviolation_data = external_data["p2"].get("coviolation_data", {})
                if entity_id and entity_id in coviolation_data:
                    profile["coviolation_vehicles"] = coviolation_data[entity_id]
                elif entity in coviolation_data:
                    profile["coviolation_vehicles"] = coviolation_data[entity]

                # 7. 增强分析器（工资/真实工资/理财）
                if entity in all_persons:
                    analyzer_tx_df = _prepare_person_transactions_for_advanced_analyzers(df)

                    if not analyzer_tx_df.empty:
                        # 7.1 工资结构增强分析
                        try:
                            salary_enhanced = salary_analyzer.analyze_income_structure(
                                analyzer_tx_df, entity
                            )
                            profile["salary_enhanced_analysis"] = (
                                _summarize_salary_enhanced_analysis(salary_enhanced)
                            )
                        except Exception as e:
                            logger.warning(f"{entity} 工资增强分析失败: {e}")

                        # 7.2 真实工资分析
                        try:
                            real_salary_result = real_salary_income_analyzer.analyze(
                                analyzer_tx_df, entity
                            )
                            profile["real_salary_analysis"] = serialize_for_json(
                                real_salary_result
                            )
                        except Exception as e:
                            logger.warning(f"{entity} 真实工资分析失败: {e}")

                        # 7.3 理财风险分析
                        try:
                            income_yearly_for_finance = _extract_income_yearly_for_finance(
                                profile.get("real_salary_analysis", {}), profile
                            )
                            finance_risk_result = finance_product_analyzer.analyze(
                                person_profile=profile,
                                person_transactions=analyzer_tx_df,
                                income_yearly=income_yearly_for_finance,
                                property_data=profile.get("properties_precise", [])
                                or profile.get("properties", []),
                                vehicle_data=profile.get("vehicles", []),
                            )
                            profile["finance_risk_analysis"] = serialize_for_json(
                                finance_risk_result
                            )
                        except Exception as e:
                            logger.warning(f"{entity} 理财风险分析失败: {e}")

                        # 7.4 收支匹配度分析（未接入分析器补齐）
                        try:
                            income_expense_match_result = _build_income_expense_match_summary(
                                income_expense_match_analyzer, profile
                            )
                            profile["income_expense_match_analysis"] = serialize_for_json(
                                income_expense_match_result
                            )
                        except Exception as e:
                            logger.warning(f"{entity} 收支匹配分析失败: {e}")

                        # 7.5 个人资金特征分析（未接入分析器补齐）
                        try:
                            summary_obj = (
                                profile.get("summary", {})
                                if isinstance(profile.get("summary", {}), dict)
                                else {}
                            )
                            total_income_wan = float(
                                summary_obj.get("total_income", 0)
                                or profile.get("totalIncome", 0)
                                or 0
                            ) / 10000.0
                            real_salary_obj = (
                                profile.get("real_salary_analysis", {})
                                if isinstance(profile.get("real_salary_analysis", {}), dict)
                                else {}
                            )
                            salary_enhanced_obj = (
                                profile.get("salary_enhanced_analysis", {})
                                if isinstance(profile.get("salary_enhanced_analysis", {}), dict)
                                else {}
                            )
                            wage_income_wan = float(
                                real_salary_obj.get("total_salary", 0) or 0
                            )
                            if wage_income_wan <= 0:
                                wage_income_wan = float(
                                    salary_enhanced_obj.get("salary_income", 0) or 0
                                ) / 10000.0

                            feature_tx_df = analyzer_tx_df.copy()
                            # 该分析器按“分”处理金额，这里将元口径转换为分。
                            feature_tx_df["amount"] = (
                                utils.normalize_amount_series(
                                    feature_tx_df["amount"], "amount"
                                )
                                .astype(float)
                                * 100.0
                            )

                            personal_feature_result = personal_fund_feature_analyzer.analyze(
                                person_profile={
                                    "name": entity,
                                    "id": entity_id,
                                    "wage_income": wage_income_wan,
                                    "total_income": total_income_wan,
                                },
                                person_transactions=feature_tx_df,
                                family_members=[],
                                suspicions=None,
                                income_expense_match_analysis=profile.get(
                                    "income_expense_match_analysis", {}
                                ),
                            )
                            profile["personal_fund_feature_analysis"] = (
                                _summarize_personal_fund_feature_analysis(
                                    personal_feature_result
                                )
                            )
                        except Exception as e:
                            logger.warning(f"{entity} 个人资金特征分析失败: {e}")

                profiles[entity] = profile

            except Exception as e:
                logger.warning(f"生成 {entity} 画像失败: {e}")

        phase5_duration = (time.time() - phase5_start) * 1000
        logging_config.log_performance(
            logger, "Phase 5-融合数据画像", phase5_duration, profile_count=len(profiles)
        )
        logger.info(f"🔄 [重构] 融合画像生成完成: {len(profiles)} 个实体")
        broadcast_log("INFO", f"  ✓ 融合画像生成完成: {len(profiles)} 个实体")
        _raise_if_analysis_stopped("画像生成后收到停止请求")

        try:
            external_data["wallet"] = wallet_risk_analyzer.enhance_wallet_alerts(
                external_data.get("wallet", {}),
                wallet_artifact_bundle.get("artifacts", {}),
                cleaned_data,
                id_to_name_map=id_to_name_map,
                profiles=profiles,
            )
        except Exception as exc:
            logger.warning(f"电子钱包高级风险增强失败: {exc}")

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
                "fundPenetration": True,
                "mlAnalysis": True,
                "relatedParty": True,
                "multiSourceCorrelation": True,
                "timeSeriesAnalysis": True,
                "clueAggregation": True,
            }
        # 兼容旧配置：缺省时启用关键分析模块
        if not isinstance(modules_config, dict):
            if hasattr(modules_config, "dict"):
                modules_config = modules_config.dict()
            elif hasattr(modules_config, "items"):
                modules_config = dict(modules_config.items())
            else:
                modules_config = {}
        modules_config.setdefault("fundPenetration", True)
        modules_config.setdefault("mlAnalysis", True)

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

        # 6.3 资金穿透分析
        if modules_config.get("fundPenetration", True):
            try:
                personal_transactions = {
                    person: cleaned_data[person]
                    for person in all_persons
                    if person in cleaned_data
                }
                company_transactions = {
                    company: cleaned_data[company]
                    for company in all_companies
                    if company in cleaned_data
                }
                analysis_results["penetration"] = fund_penetration.analyze_fund_penetration(
                    personal_transactions,
                    company_transactions,
                    all_persons,
                    all_companies,
                )
                logger.info("  ✓ 资金穿透分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 资金穿透分析失败: {e}")

        # 6.4 机器学习分析
        if modules_config.get("mlAnalysis", True):
            try:
                analysis_results["ml"] = ml_analyzer.run_ml_analysis(
                    cleaned_data, all_persons, all_companies
                )
                logger.info("  ✓ 机器学习分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 机器学习分析失败: {e}")

        # 6.5 关联方分析
        if modules_config.get("relatedParty", True):
            try:
                analysis_results["relatedParty"] = (
                    related_party_analyzer.analyze_related_party_flows(
                        cleaned_data,
                        all_persons,
                        profiles=profiles,
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

        # 6.6 多源数据碰撞
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

        # 6.7 时序分析
        if modules_config.get("timeSeriesAnalysis", True):
            try:
                logger.info("  ▶ 时序分析开始...")
                analysis_results["timeSeries"] = (
                    time_series_analyzer.analyze_time_series(cleaned_data, all_persons)
                )
                logger.info("  ✓ 时序分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 时序分析失败: {e}")

        # 6.8 线索聚合
        if modules_config.get("clueAggregation", True):
            try:
                logger.info("  ▶ 线索聚合开始...")
                analysis_results["aggregation"] = clue_aggregator.aggregate_all_results(
                    all_persons,
                    all_companies,
                    penetration_results=analysis_results.get("penetration"),
                    ml_results=analysis_results.get("ml"),
                    ts_results=analysis_results.get("timeSeries"),
                    related_party_results=analysis_results.get("relatedParty"),
                    loan_results=analysis_results.get("loan"),
                    wallet_results=external_data.get("wallet"),
                )
                logger.info("  ✓ 线索聚合完成")
            except Exception as e:
                logger.warning(f"  ✗ 线索聚合失败: {e}")

        # 6.7 家庭关系分析
        try:
            # 使用V2版本：传入内存中的external_data进行家庭推断
            logger.info("  ▶ 家庭关系分析开始...")
            inferred_family_units, inference_details = family_analyzer.infer_family_units_v2(
                core_persons=all_persons,
                external_data=external_data,
                profiles=profiles,
                cleaned_data=cleaned_data,
                data_directory=data_dir,
                confidence_threshold=0.6
            )
            logger.info(f"  ✓ 家庭单元推断完成: {len(inferred_family_units)} 个家庭")
            family_tree = family_analyzer.build_family_tree(all_persons, data_dir)
            family_summary = family_analyzer.get_family_summary(family_tree)

            effective_family_units, applied_primary_config = (
                _get_effective_family_units_for_analysis(
                    inferred_family_units, data_dir, output_dir, profiles
                )
            )
            if applied_primary_config:
                logger.info(
                    "  ✓ 已应用用户保存的归集配置参与家庭分析: "
                    f"{len(applied_primary_config.analysis_units)} 个分析单元"
                )
            else:
                logger.info("  ✓ 当前未发现用户保存归集配置，使用自动推断家庭单元")

            analysis_results["family_tree"] = family_tree
            analysis_results["family_units"] = family_summary
            analysis_results["family_relations"] = family_tree
            analysis_results["family_units_v2"] = inferred_family_units

            _, all_family_summaries = _refresh_profiles_and_build_family_summaries(
                profiles,
                cleaned_data,
                effective_family_units,
                income_expense_match_analyzer,
                logger,
            )

            if all_family_summaries:
                first_householder = list(all_family_summaries.keys())[0]
                analysis_results["family_summary"] = all_family_summaries[
                    first_householder
                ]
                analysis_results["all_family_summaries"] = all_family_summaries
                logger.info(f"  ✓ 家庭分析完成: {len(effective_family_units)} 个分析单元")
            else:
                family_assets = _collect_family_assets_for_summary(all_persons, profiles)
                family_summary_result = family_finance.calculate_family_summary(
                    profiles,
                    all_persons,
                    properties=family_assets["properties"],
                    vehicles=family_assets["vehicles"],
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
        _raise_if_analysis_stopped("综合分析后收到停止请求")

        # ========================================================================
        # Phase 7: 疑点检测 (85%) ← 🔄 有完整上下文后执行
        # ========================================================================
        analysis_state.update(progress=85, phase="检测可疑交易模式...")
        broadcast_log("INFO", "▶ Phase 7: 检测可疑交易模式...")
        logger.info("🔄 [重构] 执行疑点检测 (有资产上下文)...")

        phase7_start = time.time()

        # 7.1 基础疑点检测（以稳定版旧检测器为主，插件引擎做增强）
        suspicions = suspicion_detector.run_all_detections(
            cleaned_data, all_persons, all_companies
        )
        try:
            engine = SuspicionEngine()
            detector_input = {
                "cleaned_data": cleaned_data,
                "all_persons": all_persons,
                "all_companies": all_companies,
            }
            detector_config = {
                "cash_time_window_hours": getattr(config, "CASH_TIME_WINDOW_HOURS", 48),
                "amount_tolerance_ratio": getattr(config, "AMOUNT_TOLERANCE_RATIO", 0.05),
                "income_high_risk_min": getattr(config, "INCOME_HIGH_RISK_MIN", 50000),
                "suspicion_medium_high_amount": getattr(
                    config, "SUSPICION_MEDIUM_HIGH_AMOUNT", 20000
                ),
                "off_hours_start": getattr(config, "NON_WORKING_HOURS_START", 20),
                "off_hours_end": getattr(config, "NON_WORKING_HOURS_END", 8),
                "holiday_threshold": getattr(
                    config, "HOLIDAY_LARGE_AMOUNT_THRESHOLD", 50000
                ),
                "weekend_threshold": getattr(
                    config, "HOLIDAY_LARGE_AMOUNT_THRESHOLD", 50000
                ),
                "holiday_detection_config": getattr(
                    config, "HOLIDAY_DETECTION_CONFIG", {}
                ),
                # 默认不把“本人取现-本人存现”当作风险主清单
                "include_single_entity_collisions": False,
                # 节假日由配置统一管理（支持多年）
                "holidays": [
                    holiday
                    for _, holidays in sorted(
                        getattr(config, "CHINESE_HOLIDAYS", {}).items()
                    )
                    for holiday in holidays
                ],
            }
            plugin_results = engine.run_all(detector_input, detector_config)
            suspicions = _merge_plugin_suspicions(suspicions, plugin_results)
        except Exception as e:
            logger.warning(f"SuspicionEngine 增强失败，保留旧检测器结果: {e}")

        # 7.2 🔄 融合外部疑点数据
        # 反洗钱预警
        aml_alerts = external_data["p0"].get("aml_alerts", [])
        if aml_alerts:
            suspicions["aml_alerts"] = aml_alerts

        # 征信预警
        credit_alerts = external_data["p0"].get("credit_alerts", [])
        if credit_alerts:
            suspicions["credit_alerts"] = credit_alerts

        # 电子钱包补充预警
        wallet_alerts = external_data.get("wallet", {}).get("alerts", [])
        if wallet_alerts:
            suspicions["wallet_alerts"] = wallet_alerts

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
        _raise_if_analysis_stopped("疑点检测后收到停止请求")

        derived_data = {
            "penetration": analysis_results.get("penetration", {}),
            "correlation": analysis_results.get("correlation", {}),
            "ml": analysis_results.get("ml", {}),
            "loan": analysis_results.get("loan", {}),
            "income": analysis_results.get("income", {}),
            "time_series": analysis_results.get("timeSeries", {}),
            "timeSeries": analysis_results.get("timeSeries", {}),
            "aggregation": analysis_results.get("aggregation", {}),
            "large_transactions": analysis_results.get("large_transactions", []),
            "family_tree": analysis_results.get("family_tree", {}),
            "family_summary": {
                "family_units": analysis_results.get("family_units_v2", []),
                "family_relations": analysis_results.get("family_relations", {}),
                "all_family_summaries": analysis_results.get("all_family_summaries", {}),
            },
            "family_units_v2": analysis_results.get("family_units_v2", []),
            "all_family_summaries": analysis_results.get("all_family_summaries", {}),
        }

        analysis_state.update(progress=95, phase="生成分析报告...")
        broadcast_log("INFO", "▶ Phase 8: 生成分析报告...")

        phase8_start = time.time()

        # 8.1 预计算图谱数据（提前执行，确保报告生成器可读取 graph_data.json）
        logger.info("预计算图谱数据...")
        graph_data_cache = None
        try:
            flow_stats = flow_visualizer._calculate_flow_stats(cleaned_data, all_persons)
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
            graph_data_cache = _augment_graph_cache_with_wallet_data(
                graph_data_cache,
                external_data.get("wallet", {}),
                core_persons=all_persons,
                companies=all_companies,
            )
            wallet_report = graph_data_cache.get("walletReport", {}) if isinstance(graph_data_cache, dict) else {}
            if isinstance(wallet_report, dict):
                graph_data_cache.setdefault("stats", {})["walletAlertCount"] = len(
                    wallet_report.get("wallet_alerts", []) or []
                )
                graph_data_cache["stats"]["walletCounterpartyCount"] = len(
                    wallet_report.get("wallet_counterparties", []) or []
                )
            logger.info(
                f"  ✓ 图谱缓存: {len(sampled_nodes)} 节点, {len(sampled_edges)} 边"
            )

            # 提前落盘，避免报告生成阶段出现 graph_data.json 不存在
            CacheManager(output_dirs["analysis_cache"]).save_cache(
                "graph_data", graph_data_cache
            )
            logger.info("  ✓ 图谱缓存已提前保存（供报告生成）")
        except Exception as e:
            logger.warning(f"  ✗ 图谱缓存失败: {e}")

        # 8.2 构建家庭资产数据
        try:
            precise_property_data = external_data["p1"].get("precise_property_data", {})
            vehicle_data = external_data["p1"].get("vehicle_data", {})

            if precise_property_data or vehicle_data:
                # 【修复】构建姓名→身份证号映射，用于查询资产数据
                name_to_id_map = {}
                for id_num, name in id_to_name_map.items():
                    name_to_id_map[name] = id_num
                
                # 【修复】将core_persons（姓名）映射到身份证号后查询资产数据
                family_assets = {}
                for person in all_persons:
                    person_id = name_to_id_map.get(person)
                    if person_id:
                        # 用身份证号查询资产数据
                        person_assets = family_assets_helper.build_family_assets_simple(
                            {person_id: precise_property_data.get(person_id, [])},
                            {person_id: vehicle_data.get(person_id, [])},
                            [person_id]
                        )
                        if person_id in person_assets:
                            family_assets[person] = person_assets[person_id]
                    else:
                        # 无身份证号映射，返回空资产
                        family_assets[person] = {
                            "家族成员": [person],
                            "房产套数": 0,
                            "房产总价值": 0.0,
                            "车辆数量": 0,
                            "房产": [],
                            "车辆": [],
                        }
                
                logger.info(f"  ✓ 家庭资产数据: {len(family_assets)} 个人员")
            else:
                family_assets = {}
        except Exception as e:
            logger.warning(f"  ✗ 构建family_assets失败: {e}")
            family_assets = {}

        # 8.2 先增强疑点并固化完整缓存，确保报告生成器读取到完整数据
        enhanced_suspicions = _enhance_suspicions_with_analysis(
            suspicions, analysis_results
        )

        analysis_state.results = {
            "persons": all_persons,
            "companies": all_companies,
            "profiles": serialize_profiles(profiles),
            "suspicions": serialize_suspicions(enhanced_suspicions),
            "analysisResults": serialize_analysis_results(analysis_results),
            "graphData": graph_data_cache,
            "walletData": external_data.get("wallet", {}),
            "externalData": external_data,
            "runtimeLogPaths": _get_last_analysis_log_paths(),
            "_profiles_raw": profiles,
        }

        logger.info("保存分析缓存（供报告生成）...")
        try:
            _save_analysis_cache_refactored(
                analysis_state.results, output_dirs["analysis_cache"], id_to_name_map
            )
            logger.info("  ✓ 分析缓存已保存")
        except Exception as e:
            logger.error(f"  ✗ 保存分析缓存失败: {e}")

        report_builder = load_investigation_report_builder(output_dir)
        if report_builder and saved_primary_config:
            report_builder.set_primary_config(saved_primary_config)

        # 8.3 生成完整txt报告（使用investigation_report_builder）
        try:
            if report_builder:
                txt_report_path = os.path.join(
                    output_dirs["analysis_results"],
                    config.OUTPUT_REPORT_FILE.replace(".docx", ".txt"),
                )
                txt_report_path = report_builder.generate_complete_txt_report(
                    txt_report_path
                )
                logger.info(f"  ✓ 完整txt报告已生成: {txt_report_path}")
                broadcast_log("INFO", "  ✓ 完整txt报告生成成功")
            else:
                logger.warning("  ✗ 报告构建器未加载，txt报告生成失败")
        except Exception as e:
            logger.warning(f"  ✗ 完整txt报告生成失败: {e}")
            broadcast_log("WARN", f"  ✗ 完整txt报告生成失败: {str(e)[:50]}")

        # 8.4 生成 Excel 核查底稿
        try:
            report_package_for_excel = None
            report_package_path = os.path.join(
                output_dirs["analysis_results"], "qa", "report_package.json"
            )
            if os.path.exists(report_package_path):
                try:
                    with open(report_package_path, "r", encoding="utf-8") as handle:
                        report_package_for_excel = json.load(handle)
                except (OSError, ValueError, TypeError) as exc:
                    logger.warning(f"  ✗ 读取 report_package 供 Excel 对齐失败: {exc}")
            excel_path = _load_report_generator().generate_excel_workbook(
                profiles=profiles,
                suspicions=suspicions,
                output_path=os.path.join(
                    output_dirs["analysis_results"], config.OUTPUT_EXCEL_FILE
                ),
                family_tree=analysis_results.get("family_tree", {}),
                family_assets=family_assets,
                penetration_results=analysis_results.get("penetration", {}),
                loan_results=analysis_results.get("loan", {}),
                income_results=analysis_results.get("income", {}),
                time_series_results=analysis_results.get("timeSeries", {}),
                derived_data=derived_data if "derived_data" in dir() else {},
                report_package=report_package_for_excel,
            )
            logger.info(f"  ✓ Excel核查底稿已生成: {excel_path}")
            broadcast_log("INFO", "  ✓ Excel核查底稿生成成功")
        except Exception as e:
            logger.warning(f"  ✗ Excel核查底稿生成失败: {e}")
            broadcast_log("WARN", f"  ✗ Excel核查底稿生成失败: {str(e)[:50]}")

        # 8.5 生成专项txt报告
        try:
            logger.info("  8.5 开始生成电子钱包专项产物...")
            wallet_output_files = _load_wallet_report_builder().generate_wallet_artifacts(
                output_dirs["analysis_results"],
                external_data.get("wallet", {}),
                wallet_artifact_bundle.get("artifacts", {}),
            )
            if wallet_output_files:
                logger.info(
                    "  ✓ 电子钱包专项产物已生成: %s, %s, %s",
                    wallet_output_files.get("txt"),
                    wallet_output_files.get("excel"),
                    wallet_output_files.get("focus_txt"),
                )
                broadcast_log("INFO", "  ✓ 电子钱包专项产物生成成功")
            else:
                logger.info("  - 未检测到可生成的电子钱包专项产物")
        except Exception as e:
            logger.warning(f"  ✗ 电子钱包专项产物生成失败: {e}")
            broadcast_log("WARN", f"  ✗ 电子钱包专项产物生成失败: {str(e)[:50]}")

        # 8.6 生成专项txt报告
        try:
            logger.info("  8.6 开始生成专项txt报告...")
            if report_builder:
                specialized_gen = SpecializedReportGenerator(
                    analysis_results=analysis_results,
                    profiles=report_builder.profiles,
                    suspicions=report_builder.suspicions,
                    output_dir=output_dirs["analysis_results"],
                    input_dir=_get_active_input_dir(),
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

        # 8.6 生成报告目录清单
        try:
            index_path = _refresh_report_index_file(output_dir)
            if index_path:
                logger.info(f"  ✓ 报告目录清单已生成: {index_path}")
                broadcast_log("INFO", "  ✓ 报告目录清单生成成功")
            else:
                logger.warning("  ✗ 报告构建器未加载，目录清单生成失败")
        except Exception as e:
            logger.warning(f"  ✗ 报告目录清单生成失败: {e}")
            broadcast_log("WARN", f"  ✗ 报告目录清单生成失败: {str(e)[:50]}")

        # 完成状态更新（在缓存保存之后）
        analysis_state.update(progress=100, phase="分析完成")
        broadcast_log("INFO", "✓ 分析完成")
        analysis_state.end_time = datetime.now()
        analysis_state.status = "completed"

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
        if log_capture_started:
            _finalize_analysis_runtime_log_capture("completed")

        return analysis_state.results

    except AnalysisStoppedError as e:
        stop_message = str(e) or "分析已停止"
        logger.info(stop_message)
        analysis_state.end_time = datetime.now()
        analysis_state.results = None
        analysis_state.update(
            status="idle",
            progress=0,
            phase="已停止，可重新开始",
            error=None,
        )
        broadcast_log("WARN", f"■ {stop_message}")
        if log_capture_started:
            _finalize_analysis_runtime_log_capture("stopped")
        return None
    except Exception as e:
        logger.exception(f"分析失败: {e}")
        analysis_state.update(status="failed", error=str(e))
        if log_capture_started:
            _finalize_analysis_runtime_log_capture("failed")
        raise
    finally:
        analysis_state.clear_stop_request()


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


def _save_analysis_cache_refactored(results, cache_dir, id_to_name_map=None):
    """保存分析缓存到文件（使用缓存管理器）"""
    logger = logging.getLogger(__name__)

    try:
        # 使用缓存管理器保存所有缓存
        cache_mgr = CacheManager(cache_dir)
        cache_mgr.save_results(results, id_to_name_map)
        logger.info(f"✓ 缓存已保存: {cache_dir}")

    except Exception as e:
        logger.error(f"✗ 保存缓存失败: {e}")

# ==================== FastAPI 应用 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger = logging.getLogger("uvicorn.error")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info("🚀 资金穿透审计系统启动 (重构版)")
    _schedule_dashboard_browser_launch()
    yield
    logger.info("🛑 资金穿透审计系统关闭")


app = FastAPI(
    title="资金穿透审计系统 API (重构版)",
    description="数据流向优化: 外部数据提取 → 融合画像 → 全面分析 → 疑点检测",
    version=APP_RELEASE_VERSION,
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
        "version": APP_RELEASE_VERSION,
        "status": "running",
        "dataFlow": "external_data_first",
        "refactored": True,
        "dashboardUrl": "/dashboard/",
        "readmeUrl": "/docs/readme",
        "deliveryTarget": "windows-offline-one-folder",
    }


@app.get("/dashboard", include_in_schema=False)
@app.get("/dashboard/", include_in_schema=False)
@app.get("/dashboard/{requested_path:path}", include_in_schema=False)
async def serve_dashboard(requested_path: str = ""):
    """提供前端生产构建产物，支持 SPA 路由回落。"""
    asset_path = _resolve_dashboard_file(requested_path)
    if asset_path is None:
        dist_dir = _get_dashboard_dist_dir()
        if not (dist_dir / "index.html").exists():
            raise HTTPException(
                status_code=404,
                detail=(
                    "Dashboard 生产构建不存在，请先在 dashboard 目录执行 npm run build。"
                ),
            )
        raise HTTPException(status_code=404, detail="Dashboard 资源不存在")

    return FileResponse(str(asset_path))


@app.get("/docs/readme", include_in_schema=False)
async def serve_delivery_readme():
    readme_path = (APP_ROOT / "README.md").resolve()
    if not readme_path.exists():
        raise HTTPException(status_code=404, detail="README.md 不存在")

    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"读取 README 失败: {exc}") from exc

    html_content = _render_markdown_document(
        readme_text,
        page_title=f"穿云审计交付文档 v{APP_RELEASE_VERSION}",
    )
    return Response(content=html_content, media_type="text/html; charset=utf-8")


@app.get("/docs/file/{relative_path:path}", include_in_schema=False)
async def serve_delivery_doc_file(relative_path: str):
    resolved = _resolve_docs_file(relative_path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="文档资源不存在")
    return FileResponse(str(resolved))


@app.get("/api/status")
async def get_status():
    """获取分析状态"""
    _sync_analysis_state_with_active_output()
    return analysis_state.to_dict()


@app.get("/api/analysis/log-history")
async def get_analysis_log_history(limit: int = 200):
    """获取最近一次分析的历史日志，供前端恢复日志面板。"""
    _sync_analysis_state_with_active_output()
    return {
        "message": "分析日志获取成功",
        "data": serialize_for_json(_load_analysis_log_history(limit=limit)),
    }


@app.post("/api/active-paths")
async def sync_active_paths(request: ActivePathsRequest):
    """同步前端当前选中的输入/输出目录，并尝试恢复该输出目录缓存。"""
    requested_input = (
        _normalize_directory_path(request.inputDirectory, _get_active_input_dir())
        if request.inputDirectory is not None
        else _get_active_input_dir()
    )
    requested_output = (
        _normalize_directory_path(request.outputDirectory, _get_active_output_dir())
        if request.outputDirectory is not None
        else _get_active_output_dir()
    )

    current_input = _get_active_input_dir()
    current_output = _get_active_output_dir()

    if analysis_state.status == "running" and (
        requested_input != current_input or requested_output != current_output
    ):
        raise HTTPException(status_code=409, detail="分析运行中，暂不支持切换输入/输出目录")

    active_paths = _set_active_paths(
        request.inputDirectory, request.outputDirectory
    )
    os.makedirs(active_paths["outputDirectory"], exist_ok=True)

    output_changed = active_paths["outputDirectory"] != current_output
    cache_restored = _sync_analysis_state_with_active_output(
        force_reload=output_changed
    )

    if output_changed and not cache_restored:
        analysis_state.reset("等待开始分析")
        _clear_analysis_log_path_state()

    return {
        "success": True,
        "data": {
            **active_paths,
            "cacheRestored": cache_restored,
            "status": analysis_state.status,
        },
    }


@app.post("/api/analysis/start")
async def start_analysis(config: AnalysisConfig, background_tasks: BackgroundTasks):
    """启动分析任务"""
    if analysis_state.status == "running":
        raise HTTPException(status_code=400, detail="分析任务正在运行")

    _set_active_paths(config.inputDirectory, config.outputDirectory)
    _clear_analysis_log_path_state()
    analysis_state.clear_stop_request()
    analysis_state.start_time = None
    analysis_state.end_time = None
    analysis_state.results = None
    analysis_state.update(
        status="running",
        progress=0,
        phase="等待任务启动...",
        error=None,
    )
    background_tasks.add_task(run_analysis_refactored, config)
    return {"message": "分析任务已启动 (重构版)", "version": APP_RELEASE_VERSION}


@app.post("/api/analysis/stop")
async def stop_analysis():
    """请求安全停止当前分析任务。"""
    if analysis_state.status != "running":
        return {
            "message": "当前没有运行中的分析任务",
            "status": analysis_state.status,
        }

    analysis_state.request_stop()
    analysis_state.update(phase="正在停止分析...")
    broadcast_log("WARN", "■ 已收到停止请求，正在安全终止当前分析...")
    return {"message": "已发送停止请求", "status": "stopping"}


@app.get("/api/results")
async def get_results():
    """获取分析结果（优先从内存读取，fallback到缓存文件）"""
    from fastapi.responses import Response
    import json

    try:
        _sync_analysis_state_with_active_output()

        # 如果内存中有结果，直接返回
        if analysis_state.status == "completed" and analysis_state.results:
            results_data = serialize_for_json(
                _normalize_results_contract(analysis_state.results)
            )
            results_data = to_camel_case(results_data)
            results_data = serialize_for_json(results_data)
            if isinstance(results_data, dict):
                results_data = dict(results_data)
                if isinstance(results_data.get("suspicions"), dict):
                    results_data["suspicions"] = _normalize_serialized_suspicions_payload(
                        results_data["suspicions"]
                    )
                results_dir = _get_active_results_dir()
                report_package = _load_report_package_for_manifest(results_dir)
                results_data["reportPackage"] = (
                    serialize_for_json(report_package) if report_package else None
                )
            response_body = json.dumps(
                {"message": "分析结果获取成功", "data": results_data},
                ensure_ascii=False,
            )
            return Response(content=response_body, media_type="application/json")

        raise HTTPException(status_code=400, detail="分析尚未完成且缓存无效")
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger(__name__).exception(f"获取结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取结果失败: {str(e)}")


def _build_dashboard_results_payload() -> Dict[str, Any]:
    """为 Dashboard 构造轻量完成态载荷，避免前端恢复时读取超大对象。"""
    _sync_analysis_state_with_active_output()

    if analysis_state.status != "completed" or not analysis_state.results:
        raise HTTPException(status_code=400, detail="分析尚未完成且缓存无效")

    results_data = serialize_for_json(_normalize_results_contract(analysis_state.results))
    results_data = to_camel_case(results_data)
    results_data = serialize_for_json(results_data)

    if not isinstance(results_data, dict):
        raise HTTPException(status_code=500, detail="分析结果格式无效")

    allowed_keys = {
        "persons",
        "companies",
        "profiles",
        "suspicions",
        "analysisResults",
        "walletData",
    }
    compact_payload = {
        key: value for key, value in dict(results_data).items() if key in allowed_keys
    }

    profiles_payload = compact_payload.get("profiles")
    if isinstance(profiles_payload, dict):
        compact_profiles = {}
        keep_keys = {
            "entityName",
            "entityId",
            "totalIncome",
            "totalExpense",
            "realIncome",
            "realExpense",
            "transactionCount",
            "cashTotal",
            "thirdPartyTotal",
            "wealthTotal",
            "wealthTransactionCount",
            "maxTransaction",
            "salaryRatio",
            "hasData",
            "companySpecific",
            "companyRegistration",
            "salaryEnhancedAnalysis",
            "realSalaryAnalysis",
            "financeRiskAnalysis",
            "incomeExpenseMatchAnalysis",
            "personalFundFeatureAnalysis",
        }
        for entity_name, profile_value in profiles_payload.items():
            if not isinstance(profile_value, dict):
                compact_profiles[entity_name] = profile_value
                continue

            cash_transaction_count = 0
            raw_cash_transactions = profile_value.get("cashTransactions")
            if isinstance(raw_cash_transactions, list):
                cash_transaction_count = len(raw_cash_transactions)

            profile_compact = {
                key: value
                for key, value in profile_value.items()
                if key in keep_keys
            }
            profile_compact["cashTransactionCount"] = cash_transaction_count

            compact_profiles[entity_name] = profile_compact

        compact_payload["profiles"] = compact_profiles

    if isinstance(compact_payload.get("suspicions"), dict):
        compact_payload["suspicions"] = _normalize_serialized_suspicions_payload(
            compact_payload["suspicions"]
        )

    results_dir = _get_active_results_dir()
    report_package = _load_report_package_for_manifest(results_dir)
    compact_payload["reportPackage"] = (
        serialize_for_json(report_package) if report_package else None
    )

    return compact_payload


@app.get("/api/results/dashboard")
async def get_dashboard_results():
    """获取 Dashboard 完成态恢复载荷，剔除 Win7 易卡顿的超大字段。"""
    from fastapi.responses import Response
    import json

    try:
        response_body = json.dumps(
            {
                "message": "Dashboard 结果获取成功",
                "data": _build_dashboard_results_payload(),
            },
            ensure_ascii=False,
        )
        return Response(content=response_body, media_type="application/json")
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger(__name__).exception(f"获取 Dashboard 结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取 Dashboard 结果失败: {str(e)}")


@app.get("/api/reports/legacy")
async def get_reports():
    """获取报告列表（递归扫描所有子目录）"""
    logger = logging.getLogger(__name__)
    reports_dir = _get_active_results_dir()
    if not os.path.exists(reports_dir):
        return {"reports": []}

    _refresh_semantic_artifacts_for_runtime_read(reports_dir, logger, "报告列表旧接口")
    legacy_extensions = {".html", ".docx", ".txt", ".pdf"}
    reports = [
        {
            "name": item["name"],
            "path": item["path"],
            "size": item["size"],
            "modified": item["modified"],
        }
        for item in _collect_report_files(reports_dir)
        if str(item.get("extension") or "").lower() in legacy_extensions
    ]
    reports.sort(key=lambda x: x["modified"], reverse=True)
    return {"reports": reports}


@app.get("/api/reports/subjects")
async def get_report_subjects():
    """获取报告生成可选的核查对象列表"""
    _sync_analysis_state_with_active_output()

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
                    "transactionCount": profile.get(
                        "transactionCount", profile.get("transaction_count", 0)
                    ),
                    "totalIncome": profile.get(
                        "totalIncome", profile.get("total_income", 0)
                    ),
                    "salaryRatio": profile.get(
                        "salaryRatio", profile.get("salary_ratio", 1.0)
                    ),
                }
            )

        # 添加公司
        for company in companies:
            profile = profiles.get(company, {})
            subjects.append(
                {
                    "name": company,
                    "type": "company",
                    "transactionCount": profile.get(
                        "transactionCount", profile.get("transaction_count", 0)
                    ),
                    "totalIncome": profile.get(
                        "totalIncome", profile.get("total_income", 0)
                    ),
                }
            )

        return {"success": True, "subjects": subjects}

    # 尝试从缓存文件中读取
    cache_dir = _get_active_cache_dir()
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
                        "transactionCount": profile.get(
                            "transactionCount", profile.get("transaction_count", 0)
                        ),
                        "totalIncome": profile.get(
                            "totalIncome", profile.get("total_income", 0)
                        ),
                        "salaryRatio": profile.get(
                            "salaryRatio", profile.get("salary_ratio", 1.0)
                        ),
                    }
                )

            for company in companies:
                profile = profiles.get(company, {})
                subjects.append(
                    {
                        "name": company,
                        "type": "company",
                        "transactionCount": profile.get(
                            "transactionCount", profile.get("transaction_count", 0)
                        ),
                        "totalIncome": profile.get(
                            "totalIncome", profile.get("total_income", 0)
                        ),
                    }
                )

            return {"success": True, "subjects": subjects}
        except Exception as e:
            logging.getLogger(__name__).warning(f"读取缓存失败: {e}")

    return {"success": True, "subjects": []}


@app.get("/api/cache/info")
async def get_cache_info():
    """获取缓存信息（用于调试和监控）"""
    cache_dir = _get_active_cache_dir()
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
    global _cache_manager
    cache_dir = _get_active_cache_dir()
    try:
        cache_mgr = CacheManager(cache_dir)
        if cache_name:
            cache_mgr.invalidate(cache_name)
            _cache_manager = None
            analysis_state.reset("缓存已失效，请重新开始分析")
            return {"success": True, "message": f"已失效缓存: {cache_name}"}
        else:
            cache_mgr.clear_all()
            _cache_manager = None
            # 缓存失效后同步清空内存态，避免旧结果继续返回
            analysis_state.reset("缓存已失效，请重新开始分析")
            return {"success": True, "message": "已清除所有缓存"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/cache/clear")
async def clear_cache():
    """彻底清空缓存（内存 + 当前输出目录）。"""
    global _cache_manager
    if analysis_state.status == "running":
        return {"success": False, "error": "分析正在运行，无法清空缓存"}

    output_dir = _get_active_output_dir()
    cache_dir = _get_active_cache_dir()
    results_dir = _get_active_results_dir()
    cleaned_data_dir = os.path.join(output_dir, "cleaned_data")
    analysis_logs_dir = os.path.join(output_dir, "analysis_logs")

    try:
        with _cache_lock:
            _clear_directory_contents(cache_dir)
            _clear_directory_contents(results_dir)
            _clear_directory_contents(cleaned_data_dir)
            _clear_directory_contents(analysis_logs_dir)

        _cache_manager = None
        _clear_analysis_log_path_state()
        analysis_state.reset("缓存已清空，等待开始分析")
        return {
            "success": True,
            "message": f"缓存已清空: output={output_dir}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 路径管理 API ====================


@app.get("/api/default-paths")
async def get_default_paths():
    """
    获取默认的 data 和 output 目录的绝对路径

    用于前端初始化时获取默认路径
    """
    try:
        # 使用 paths 模块获取默认路径（绝对路径）
        default_input = str(DATA_DIR)
        default_output = str(OUTPUT_DIR)
        project_root = str(APP_ROOT)

        # 确保目录存在
        os.makedirs(default_input, exist_ok=True)
        os.makedirs(default_output, exist_ok=True)

        return {
            "success": True,
            "data": {
                "inputDirectory": default_input,
                "outputDirectory": default_output,
                "projectRoot": project_root,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/select-directory")
async def select_directory(request: DirectorySelectRequest):
    """
    弹出文件选择对话框，让用户选择目录

    macOS: 使用 AppleScript 弹出访达
    Windows: 使用 tkinter
    """
    import platform
    import subprocess

    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # 使用 AppleScript 弹出访达选择文件夹
            initial_dir = (
                request.current_path
                if request.current_path and os.path.exists(request.current_path)
                else os.path.expanduser("~")
            )

            # AppleScript 代码
            script = f'''
            set chosenFolder to choose folder with prompt "选择{("输入目录 (data)" if request.type == "input" else "输出目录 (output)")}" default location (POSIX file "{initial_dir}")
            return POSIX path of chosenFolder
            '''

            result = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                selected_path = result.stdout.strip()
                if selected_path:
                    return {"success": True, "path": selected_path}
                else:
                    return {"success": False, "error": "用户取消了选择"}
            else:
                error_msg = (
                    result.stderr.strip() if result.stderr else "AppleScript 执行失败"
                )
                return {"success": False, "error": error_msg}

        elif system == "Windows":
            # Windows 使用 tkinter
            import threading
            import queue

            result_queue = queue.Queue()

            def run_dialog():
                try:
                    import tkinter as tk
                    from tkinter import filedialog

                    root = tk.Tk()
                    root.withdraw()
                    root.attributes("-topmost", True)

                    initial_dir = (
                        request.current_path
                        if request.current_path and os.path.exists(request.current_path)
                        else os.getcwd()
                    )

                    selected_path = filedialog.askdirectory(
                        title="选择"
                        + (
                            "输入目录 (data)"
                            if request.type == "input"
                            else "输出目录 (output)"
                        ),
                        initialdir=initial_dir,
                    )

                    root.destroy()

                    if selected_path:
                        result_queue.put({"success": True, "path": selected_path})
                    else:
                        result_queue.put({"success": False, "error": "用户取消了选择"})

                except Exception as e:
                    result_queue.put({"success": False, "error": str(e)})

            dialog_thread = threading.Thread(target=run_dialog)
            dialog_thread.start()
            dialog_thread.join(timeout=60)

            if dialog_thread.is_alive():
                return {"success": False, "error": "文件选择超时"}

            return result_queue.get()
        else:
            return {"success": False, "error": f"不支持的操作系统: {system}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "文件选择超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/primary-targets")
async def get_primary_targets_config():
    """
    获取当前归集配置

    如果配置不存在，自动生成默认配置
    """
    logger = logging.getLogger(__name__)
    logger.info("[归集配置] 获取配置")

    try:
        service = _get_primary_targets_service()
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
        service = _get_primary_targets_service()
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
        service = _get_primary_targets_service()
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
        service = _get_primary_targets_service()
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


_REPORT_FILE_TYPES = {
    ".txt": "text",
    ".html": "html",
    ".htm": "html",
    ".xlsx": "excel",
    ".xls": "excel",
    ".md": "markdown",
    ".pdf": "pdf",
    ".json": "json",
    ".docx": "docx",
}

_REPORT_GROUP_DEFS = [
    {
        "key": "primary_reports",
        "label": "主报告",
        "description": "正式 HTML/TXT/PDF 报告与主入口文件。",
        "order": 10,
    },
    {
        "key": "appendices",
        "label": "附录",
        "description": "专题输出与附录类报告文件。",
        "order": 20,
    },
    {
        "key": "dossiers",
        "label": "对象卷宗",
        "description": "按家庭、个人、公司沉淀的对象级卷宗。",
        "order": 30,
    },
    {
        "key": "qa_artifacts",
        "label": "QA与一致性检查",
        "description": "report_package、QA 检查与一致性产物。",
        "order": 40,
    },
    {
        "key": "workpapers",
        "label": "工作底稿",
        "description": "Excel、底稿与结构化明细文件。",
        "order": 50,
    },
    {
        "key": "technical_files",
        "label": "技术文件",
        "description": "日志、索引、说明等技术性辅助文件。",
        "order": 60,
    },
]

_PRIMARY_REPORT_PRIORITY_HINTS = {
    "初查报告.html": 10,
    "初查报告.htm": 10,
    "初查报告.pdf": 15,
    "核查结果分析报告.txt": 20,
    "核查结果分析报告.pdf": 25,
}

_APPENDIX_SEMANTIC_HINTS = [
    {
        "appendixKey": "appendix_a_assets_income",
        "order": 10,
        "tokens": ["资产全貌分析报告"],
    },
    {
        "appendixKey": "appendix_b_income_loan",
        "order": 20,
        "tokens": ["借贷行为分析报告", "异常收入来源分析报告"],
    },
    {
        "appendixKey": "appendix_c_network_penetration",
        "order": 30,
        "tokens": ["资金穿透分析报告", "疑点检测分析报告"],
    },
    {
        "appendixKey": "appendix_d_timeline_behavior",
        "order": 40,
        "tokens": ["时序分析报告", "行为特征分析报告"],
    },
    {
        "appendixKey": "appendix_e_wallet_supplement",
        "order": 50,
        "tokens": ["电子钱包补充分析报告", "电子钱包重点核查清单"],
    },
]


def _manifest_as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _manifest_as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _manifest_as_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _manifest_unique_texts(values: List[Any]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _manifest_parse_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _get_latest_semantic_source_timestamp(results_dir: str) -> Optional[datetime]:
    latest_timestamp: Optional[datetime] = None
    for root, dirs, files in os.walk(results_dir):
        dirs[:] = [item for item in dirs if item != "qa"]
        for filename in files:
            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, results_dir).replace("\\", "/")
            ext = os.path.splitext(filename)[1].lower()
            if ext not in _REPORT_FILE_TYPES:
                continue
            group_meta = _classify_report_group(relative_path, ext)
            if group_meta.get("key") in {"qa_artifacts", "technical_files"}:
                continue
            try:
                modified_at = datetime.fromtimestamp(os.stat(file_path).st_mtime)
            except OSError:
                continue
            if latest_timestamp is None or modified_at > latest_timestamp:
                latest_timestamp = modified_at
    return latest_timestamp


_REPORT_SEMANTIC_LOGIC_FILES = (
    "investigation_report_builder.py",
    "report_view_builder.py",
    "report_dossier_builder.py",
    "report_issue_engine.py",
    "report_quality_guard.py",
)


def _get_latest_report_logic_timestamp() -> Optional[datetime]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    latest_timestamp: Optional[datetime] = None
    for relative_path in _REPORT_SEMANTIC_LOGIC_FILES:
        file_path = os.path.join(base_dir, relative_path)
        if not os.path.exists(file_path):
            continue
        try:
            modified_at = datetime.fromtimestamp(os.stat(file_path).st_mtime)
        except OSError:
            continue
        if latest_timestamp is None or modified_at > latest_timestamp:
            latest_timestamp = modified_at
    return latest_timestamp


def _report_package_requires_refresh(results_dir: str, payload: Dict[str, Any]) -> bool:
    if not payload:
        return True

    qa_checks = _manifest_as_dict(payload.get("qa_checks"))
    qa_meta = _manifest_as_dict(qa_checks.get("meta"))
    artifact_meta = _manifest_as_dict(payload.get("artifact_meta"))
    stored_guard_version = str(
        qa_meta.get("qa_guard_version") or artifact_meta.get("qa_guard_version") or ""
    ).strip()
    if stored_guard_version != _get_report_qa_guard_version():
        return True

    dossier_explanation_fields = (
        ("person_dossiers", "financial_gap_explanation"),
        ("family_dossiers", "family_financial_explanation"),
        ("company_dossiers", "company_business_explanation"),
    )
    for dossier_key, explanation_key in dossier_explanation_fields:
        dossiers = _manifest_as_list(payload.get(dossier_key))
        if not dossiers:
            continue
        for dossier in dossiers:
            if not isinstance(dossier, dict):
                return True
            if not _manifest_as_dict(dossier.get(explanation_key)):
                return True

    package_generated_at = _manifest_parse_datetime(
        artifact_meta.get("package_generated_at")
    )
    if package_generated_at is None:
        return True

    qa_dir = os.path.join(results_dir, "qa")
    required_paths = [
        os.path.join(qa_dir, "report_package.json"),
        os.path.join(qa_dir, "report_consistency_check.json"),
        os.path.join(qa_dir, "report_consistency_check.txt"),
    ]
    if not all(os.path.exists(path) for path in required_paths):
        return True

    latest_source_timestamp = _get_latest_semantic_source_timestamp(results_dir)
    latest_logic_timestamp = _get_latest_report_logic_timestamp()
    latest_refresh_baseline = latest_source_timestamp
    if latest_logic_timestamp and (
        latest_refresh_baseline is None or latest_logic_timestamp > latest_refresh_baseline
    ):
        latest_refresh_baseline = latest_logic_timestamp

    if latest_refresh_baseline and latest_refresh_baseline > (
        package_generated_at + timedelta(seconds=1)
    ):
        return True

    return False


def _load_report_package_for_manifest(results_dir: str) -> Dict[str, Any]:
    package_path = os.path.join(results_dir, "qa", "report_package.json")
    logger = logging.getLogger(__name__)

    def _read_package() -> Dict[str, Any]:
        if not os.path.exists(package_path):
            return {}
        try:
            with open(package_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            logger.warning("[报告清单] 无法读取 report_package.json: %s", package_path)
            return {}

    payload = _read_package()
    if payload and not _report_package_requires_refresh(results_dir, payload):
        return payload

    if payload:
        logger.info("[报告清单] report_package 版本或时间戳已过期，尝试刷新")

    output_dir = os.path.dirname(os.path.abspath(results_dir))
    semantic_paths = _refresh_report_semantic_artifacts(output_dir)
    if semantic_paths:
        logger.info("[报告清单] report_package 已按当前缓存与QA规则刷新")
    refreshed_payload = _read_package()
    return refreshed_payload or payload


def _build_manifest_main_report_overview(report_package: Dict[str, Any]) -> Dict[str, Any]:
    main_report_view = _manifest_as_dict(report_package.get("main_report_view"))
    if not main_report_view:
        return {}

    issue_count = _manifest_as_int(
        main_report_view.get("issue_count"),
        len(_manifest_as_list(main_report_view.get("issues"))),
    )
    high_risk_issue_count = _manifest_as_int(
        main_report_view.get("high_risk_issue_count")
    )
    top_priority_entities = []
    highlights = []

    for item in _manifest_as_list(main_report_view.get("top_priority_entities"))[:3]:
        if not isinstance(item, dict):
            continue
        entity_name = str(item.get("entity_name") or "").strip()
        if not entity_name:
            continue
        top_priority_entities.append(entity_name)
        highlights.append(
            {
                "title": entity_name,
                "summary": "；".join(
                    _manifest_unique_texts(_manifest_as_list(item.get("top_reasons")))[:2]
                ),
            }
        )

    badges = []
    if issue_count:
        badges.append(f"重点问题 {issue_count} 项")
    if high_risk_issue_count:
        badges.append(f"高风险 {high_risk_issue_count} 项")
    if top_priority_entities:
        badges.append(f"优先对象 {'、'.join(top_priority_entities)}")

    headline = str(main_report_view.get("summary_narrative") or "").strip()
    if not headline and badges:
        headline = "统一语义层已生成主报告结论摘要。"

    return {
        "headline": headline,
        "badges": badges,
        "highlights": highlights,
        "issueCount": issue_count,
        "highRiskIssueCount": high_risk_issue_count,
        "topPriorityEntities": top_priority_entities,
    }


def _build_manifest_appendix_overview(report_package: Dict[str, Any]) -> Dict[str, Any]:
    appendix_views = _manifest_as_dict(report_package.get("appendix_views"))
    appendix_index = _manifest_as_dict(appendix_views.get("appendix_index"))
    appendix_items = []
    appendix_lookup: Dict[str, Dict[str, Any]] = {}

    for item in _manifest_as_list(appendix_index.get("items")):
        if not isinstance(item, dict):
            continue
        appendix_key = str(item.get("appendix_key") or "").strip()
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary_line") or "").strip()
        if not appendix_key or not title:
            continue
        normalized_item = {
            "appendixKey": appendix_key,
            "title": title,
            "summary": summary,
            "itemCount": _manifest_as_int(item.get("item_count")),
        }
        appendix_items.append(normalized_item)
        appendix_lookup[appendix_key] = normalized_item

    if not appendix_items:
        return {}

    total_count = sum(item["itemCount"] for item in appendix_items)
    badges = [f"附录主题 {len(appendix_items)} 组"]
    if total_count:
        badges.append(f"摘要内容 {total_count} 条")

    return {
        "headline": f"统一语义层已归集 {len(appendix_items)} 个正式附录主题。",
        "badges": badges,
        "highlights": [
            {"title": item["title"], "summary": item["summary"]}
            for item in appendix_items[:5]
        ],
        "appendixLookup": appendix_lookup,
        "appendixCount": len(appendix_items),
    }


def _format_manifest_qa_check_highlight(item: Dict[str, Any]) -> Dict[str, str]:
    return format_report_qa_check_display(item)


def _build_manifest_qa_overview(report_package: Dict[str, Any]) -> Dict[str, Any]:
    qa_checks = _manifest_as_dict(report_package.get("qa_checks"))
    summary = _manifest_as_dict(qa_checks.get("summary"))
    checks = _manifest_as_list(qa_checks.get("checks"))
    if not summary and not checks:
        return {}

    fail_count = _manifest_as_int(summary.get("fail"))
    warn_count = _manifest_as_int(summary.get("warn"))
    pass_count = _manifest_as_int(summary.get("pass"))
    total_count = _manifest_as_int(summary.get("total"), len(checks))

    if fail_count:
        headline = f"QA 检查存在 {fail_count} 项阻断问题，当前仍需收口。"
    elif warn_count:
        headline = f"QA 检查存在 {warn_count} 项提示，主链路已可继续推进。"
    elif total_count:
        headline = f"QA 检查 {total_count} 项均已通过。"
    else:
        headline = ""

    highlights = []
    focus_statuses = {"fail", "warn"} if (fail_count or warn_count) else {"pass"}
    for item in checks:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status not in focus_statuses:
            continue
        highlights.append(_format_manifest_qa_check_highlight(item))
        if len(highlights) >= 4:
            break

    badges = []
    if total_count:
        badges.append(f"检查 {total_count} 项")
    if fail_count:
        badges.append(f"阻断 {fail_count} 项")
    if warn_count:
        badges.append(f"提示 {warn_count} 项")
    if pass_count:
        badges.append(f"通过 {pass_count} 项")

    artifact_meta = _manifest_as_dict(report_package.get("artifact_meta"))
    source_report_generated_at = str(
        artifact_meta.get("source_report_generated_at")
        or _manifest_as_dict(report_package.get("meta")).get("generated_at")
        or ""
    ).strip()
    if source_report_generated_at:
        badges.append(
            f"报告批次 {source_report_generated_at[:16].replace('T', ' ')}"
        )

    package_generated_at = _manifest_parse_datetime(
        artifact_meta.get("package_generated_at")
    )
    source_report_generated_ts = _manifest_parse_datetime(source_report_generated_at)
    if (
        package_generated_at
        and source_report_generated_ts
        and package_generated_at > source_report_generated_ts + timedelta(minutes=1)
    ):
        badges.append(f"QA重校 {package_generated_at.strftime('%Y-%m-%d %H:%M')}")

    return {
        "headline": headline,
        "badges": badges,
        "highlights": highlights,
        "failCount": fail_count,
        "warnCount": warn_count,
        "passCount": pass_count,
        "totalCount": total_count,
    }


def _build_manifest_dossier_overview(report_package: Dict[str, Any]) -> Dict[str, Any]:
    family_dossiers = _manifest_as_list(report_package.get("family_dossiers"))
    person_dossiers = _manifest_as_list(report_package.get("person_dossiers"))
    company_dossiers = _manifest_as_list(report_package.get("company_dossiers"))
    if not family_dossiers and not person_dossiers and not company_dossiers:
        return {}

    role_tag_counts: Dict[str, int] = {}
    high_risk_company_count = 0
    for item in company_dossiers:
        if not isinstance(item, dict):
            continue
        risk_overview = _manifest_as_dict(item.get("risk_overview"))
        risk_level = str(risk_overview.get("risk_level") or "").strip().lower()
        if risk_level in {"high", "critical"}:
            high_risk_company_count += 1
        for tag in _manifest_as_list(item.get("role_tags")):
            text = str(tag or "").strip()
            if not text:
                continue
            role_tag_counts[text] = role_tag_counts.get(text, 0) + 1

    ordered_role_tags = sorted(
        role_tag_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )

    badges = []
    if family_dossiers:
        badges.append(f"家庭 {len(family_dossiers)} 份")
    if person_dossiers:
        badges.append(f"个人 {len(person_dossiers)} 份")
    if company_dossiers:
        badges.append(f"公司 {len(company_dossiers)} 份")
    if high_risk_company_count:
        badges.append(f"高风险公司 {high_risk_company_count} 家")

    return {
        "headline": (
            f"卷宗层已覆盖 {len(family_dossiers)} 个家庭、"
            f"{len(person_dossiers)} 名个人、{len(company_dossiers)} 家公司。"
        ),
        "badges": badges,
        "highlights": [
            {"title": tag, "summary": f"涉及 {count} 家公司卷宗"}
            for tag, count in ordered_role_tags[:4]
        ],
        "familyCount": len(family_dossiers),
        "personCount": len(person_dossiers),
        "companyCount": len(company_dossiers),
    }


def _build_manifest_semantic_context(results_dir: str) -> Dict[str, Any]:
    report_package = _load_report_package_for_manifest(results_dir)
    if not report_package:
        return {}

    main_report = _build_manifest_main_report_overview(report_package)
    appendices = _build_manifest_appendix_overview(report_package)
    qa = _build_manifest_qa_overview(report_package)
    dossiers = _build_manifest_dossier_overview(report_package)

    return {
        "available": any([main_report, appendices, qa, dossiers]),
        "mainReport": main_report,
        "appendices": appendices,
        "qa": qa,
        "dossiers": dossiers,
    }


def _infer_appendix_semantic_meta(relative_path: str) -> Dict[str, Any]:
    normalized_path = str(relative_path or "").replace("\\", "/").strip("/")
    for item in _APPENDIX_SEMANTIC_HINTS:
        if any(token in normalized_path for token in item["tokens"]):
            return item
    return {}


def _build_group_semantic_summary(
    group_key: str, semantic_context: Dict[str, Any]
) -> Dict[str, Any]:
    section_map = {
        "primary_reports": "mainReport",
        "appendices": "appendices",
        "dossiers": "dossiers",
        "qa_artifacts": "qa",
    }
    section = _manifest_as_dict(semantic_context.get(section_map.get(group_key, "")))
    if not section:
        return {}
    return {
        "semanticHeadline": str(section.get("headline") or "").strip(),
        "semanticBadges": _manifest_as_list(section.get("badges")),
        "semanticHighlights": _manifest_as_list(section.get("highlights")),
    }


def _build_report_item_semantic_meta(
    report: Dict[str, Any], semantic_context: Dict[str, Any]
) -> Dict[str, Any]:
    filename = str(report.get("name") or "").replace("\\", "/").strip("/")
    basename = os.path.basename(filename)
    group_key = str(report.get("groupKey") or "").strip()

    primary_rank = _PRIMARY_REPORT_PRIORITY_HINTS.get(basename)
    if primary_rank is not None:
        main_report = _manifest_as_dict(semantic_context.get("mainReport"))
        return {
            "semanticTitle": "正式主报告入口",
            "semanticSummary": str(main_report.get("headline") or "").strip(),
            "semanticBadges": _manifest_as_list(main_report.get("badges"))[:3],
            "semanticRank": primary_rank,
        }

    if group_key == "appendices":
        appendix_context = _manifest_as_dict(semantic_context.get("appendices"))
        appendix_lookup = _manifest_as_dict(appendix_context.get("appendixLookup"))
        appendix_meta = _infer_appendix_semantic_meta(filename)
        appendix_key = str(appendix_meta.get("appendixKey") or "").strip()
        appendix_item = _manifest_as_dict(appendix_lookup.get(appendix_key))
        if appendix_key and appendix_item:
            badges = ["正式附录主题"]
            if appendix_item.get("itemCount"):
                badges.append(f"摘要 {appendix_item['itemCount']} 条")
            return {
                "semanticTitle": str(appendix_item.get("title") or "").strip(),
                "semanticSummary": str(appendix_item.get("summary") or "").strip(),
                "semanticBadges": badges,
                "semanticRank": _manifest_as_int(appendix_meta.get("order"), 999),
            }

    if group_key == "qa_artifacts":
        qa = _manifest_as_dict(semantic_context.get("qa"))
        main_report = _manifest_as_dict(semantic_context.get("mainReport"))
        if basename == "report_package.json":
            badges = []
            issue_count = _manifest_as_int(main_report.get("issueCount"))
            if issue_count:
                badges.append(f"问题卡 {issue_count} 项")
            badges.extend(_manifest_as_list(qa.get("badges"))[:2])
            return {
                "semanticTitle": "统一报告语义包",
                "semanticSummary": str(main_report.get("headline") or "").strip(),
                "semanticBadges": _manifest_unique_texts(badges),
                "semanticRank": 10,
            }
        if basename in {"report_consistency_check.txt", "report_consistency_check.json"}:
            return {
                "semanticTitle": "QA 一致性检查",
                "semanticSummary": str(qa.get("headline") or "").strip(),
                "semanticBadges": _manifest_as_list(qa.get("badges"))[:4],
                "semanticRank": 20,
            }

    return {}


def _report_manifest_sort_key(item: Dict[str, Any]) -> Any:
    try:
        modified_ts = datetime.fromisoformat(str(item.get("modified") or "")).timestamp()
    except (TypeError, ValueError):
        modified_ts = 0.0
    return (
        int(item.get("groupOrder", 999) or 999),
        int(item.get("semanticRank", 999) or 999),
        -int(modified_ts),
        str(item.get("name") or ""),
    )


def _get_report_group_meta(group_key: str) -> Dict[str, Any]:
    for item in _REPORT_GROUP_DEFS:
        if item["key"] == group_key:
            return dict(item)
    return {
        "key": group_key,
        "label": group_key,
        "description": "",
        "order": 999,
    }


def _classify_report_group(relative_path: str, ext: str) -> Dict[str, Any]:
    normalized_path = str(relative_path or "").replace("\\", "/").strip("/")
    lower_path = normalized_path.lower()
    filename = os.path.basename(normalized_path)
    lower_name = filename.lower()

    if (
        lower_path.startswith("qa/")
        or lower_name in {
            "report_package.json",
            "report_consistency_check.json",
            "report_consistency_check.txt",
        }
    ):
        return _get_report_group_meta("qa_artifacts")

    if (
        "卷宗" in filename
        or "dossier" in lower_name
        or lower_path.startswith("卷宗/")
        or lower_path.startswith("dossiers/")
    ):
        return _get_report_group_meta("dossiers")

    if (
        lower_path.startswith("专项报告/")
        or "附录" in filename
        or "appendix" in lower_name
        or "电子钱包补充分析报告" in filename
    ):
        return _get_report_group_meta("appendices")

    if (
        ext in {".xlsx", ".xls"}
        or "底稿" in filename
        or "核查清单" in filename
        or "清洗表" in filename
    ):
        return _get_report_group_meta("workpapers")

    if (
        lower_name in {"分析执行日志.txt", "报告目录清单.txt"}
        or ext in {".md"}
        or lower_path.startswith("logs/")
    ):
        return _get_report_group_meta("technical_files")

    return _get_report_group_meta("primary_reports")


def _collect_report_files(results_dir: str) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []

    def scan_directory(directory: str, prefix: str = "") -> None:
        if not os.path.exists(directory):
            return

        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            relative_path = os.path.relpath(item_path, results_dir)

            if os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                if ext not in _REPORT_FILE_TYPES:
                    continue

                stat = os.stat(item_path)
                display_name = item if prefix == "" else f"{prefix}/{item}"
                group_meta = _classify_report_group(display_name, ext)
                reports.append(
                    {
                        "name": display_name,
                        "filename": display_name,
                        "type": _REPORT_FILE_TYPES[ext],
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                        "path": item_path,
                        "extension": ext,
                        "groupKey": group_meta["key"],
                        "groupLabel": group_meta["label"],
                        "groupOrder": group_meta["order"],
                        "isPreviewable": ext in {".txt", ".html", ".htm", ".md", ".json"},
                    }
                )
            elif os.path.isdir(item_path):
                scan_directory(
                    item_path, prefix=item if prefix == "" else f"{prefix}/{item}"
                )

    scan_directory(results_dir)
    reports.sort(key=_report_manifest_sort_key)
    return reports


def _build_report_manifest(results_dir: str) -> Dict[str, Any]:
    semantic_context = _build_manifest_semantic_context(results_dir)
    reports = []
    for item in _collect_report_files(results_dir):
        semantic_meta = _build_report_item_semantic_meta(item, semantic_context)
        reports.append({**item, **semantic_meta})
    reports.sort(key=_report_manifest_sort_key)
    groups: List[Dict[str, Any]] = []

    for group_def in _REPORT_GROUP_DEFS:
        items = [item for item in reports if item.get("groupKey") == group_def["key"]]
        if not items:
            continue
        items.sort(key=_report_manifest_sort_key)
        group_payload = {
            "key": group_def["key"],
            "label": group_def["label"],
            "description": group_def["description"],
            "order": group_def["order"],
            "count": len(items),
            "items": items,
        }
        group_payload.update(_build_group_semantic_summary(group_def["key"], semantic_context))
        groups.append(group_payload)

    return {
        "success": True,
        "reports": reports,
        "groups": groups,
        "semanticOverview": {
            "mainReport": _manifest_as_dict(semantic_context.get("mainReport")),
            "appendices": {
                key: value
                for key, value in _manifest_as_dict(semantic_context.get("appendices")).items()
                if key != "appendixLookup"
            },
            "qa": _manifest_as_dict(semantic_context.get("qa")),
            "dossiers": _manifest_as_dict(semantic_context.get("dossiers")),
        },
        "totals": {
            "reportCount": len(reports),
            "groupCount": len(groups),
        },
    }


def _should_refresh_semantic_artifacts_for_path(relative_path: str) -> bool:
    normalized = str(relative_path or "").replace("\\", "/").strip("/")
    if not normalized:
        return False

    basename = os.path.basename(normalized)
    parent = os.path.dirname(normalized).replace("\\", "/").strip("/")
    if basename not in {
        "report_package.json",
        "report_consistency_check.json",
        "report_consistency_check.txt",
    }:
        return False

    return parent in {"", "qa"}


def _refresh_semantic_artifacts_for_runtime_read(results_dir: str, logger, scene: str) -> None:
    try:
        _load_report_package_for_manifest(results_dir)
    except Exception as exc:
        logger.warning("[%s] 预刷新语义产物失败: %s", scene, exc)


@app.get("/api/reports")
async def get_report_files():
    """
    获取已生成的报告文件列表（递归扫描所有子目录）

    返回 output/analysis_results 目录下的所有报告文件（包括子目录）
    """
    logger = logging.getLogger(__name__)
    results_dir = _get_active_results_dir()

    if not os.path.exists(results_dir):
        return {"success": True, "reports": [], "message": "报告目录不存在"}

    try:
        _refresh_semantic_artifacts_for_runtime_read(results_dir, logger, "报告列表")
        reports = _collect_report_files(results_dir)
        logger.info(f"[报告列表] 找到 {len(reports)} 个报告文件")
        return {"success": True, "reports": reports}
    except Exception as e:
        logger.exception(f"[报告列表] 获取失败: {e}")
        return {"success": False, "reports": [], "error": str(e)}


@app.get("/api/reports/manifest")
async def get_report_manifest():
    """获取报告中心分组清单。"""
    logger = logging.getLogger(__name__)
    results_dir = _get_active_results_dir()

    if not os.path.exists(results_dir):
        return {
            "success": True,
            "reports": [],
            "groups": [],
            "semanticOverview": {},
            "totals": {"reportCount": 0, "groupCount": 0},
            "message": "报告目录不存在",
        }

    try:
        manifest = _build_report_manifest(results_dir)
        logger.info(
            "[报告清单] 分组完成: %s 个文件, %s 个分组",
            manifest["totals"]["reportCount"],
            manifest["totals"]["groupCount"],
        )
        return manifest
    except Exception as e:
        logger.exception(f"[报告清单] 获取失败: {e}")
        return {
            "success": False,
            "reports": [],
            "groups": [],
            "semanticOverview": {},
            "totals": {"reportCount": 0, "groupCount": 0},
            "error": str(e),
        }


@app.api_route("/api/reports/preview/{filename:path}", methods=["GET", "HEAD"])
async def preview_report_file(filename: str, request: Request):
    """
    预览报告文件内容

    Args:
        filename: 报告文件名（支持子目录路径如"专项报告/xxx.txt"）

    Returns:
        文件内容（txt/html/md）或下载链接（xlsx）
    """
    logger = logging.getLogger(__name__)
    logger.info(f"[报告预览] 请求预览: {filename}")

    # 【P1修复】路径遍历安全增强
    # 1. 检查空文件名
    if not filename or not filename.strip():
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "文件名不能为空"},
        )

    # 2. 检查文件名长度
    if len(filename) > 255:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "文件名过长"},
        )

    # 3. 检查非法字符
    invalid_chars = ["<", ">", ":", '"', "|", "?", "*", "\x00"]
    if any(char in filename for char in invalid_chars):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "文件名包含非法字符"},
        )

    # 4. 规范化路径（去除 .. 等）
    normalized_path = os.path.normpath(filename)

    # 5. 检查是否包含路径遍历攻击（规范化后仍包含..）
    if (
        ".." in normalized_path
        or normalized_path.startswith("/")
        or normalized_path.startswith("\\")
    ):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "非法文件路径"},
        )

    # 构建完整路径
    results_dir = _get_active_results_dir()
    base_dir = os.path.abspath(results_dir)
    filepath = os.path.abspath(os.path.join(results_dir, normalized_path))

    # 确保路径在允许的目录内
    if not (filepath == base_dir or filepath.startswith(base_dir + os.sep)):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "非法文件路径"},
        )

    if _should_refresh_semantic_artifacts_for_path(normalized_path):
        _refresh_semantic_artifacts_for_runtime_read(results_dir, logger, "报告预览")

    if not os.path.exists(filepath):
        logger.warning(f"[报告预览] 文件不存在: {filepath}")
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"文件不存在: {filename}"},
        )

    # 获取文件扩展名（用于判断文件类型）
    ext = os.path.splitext(filepath)[1].lower()
    if request.method == "HEAD":
        media_type = "text/html; charset=utf-8" if ext == ".html" else "application/json"
        return Response(status_code=200, media_type=media_type)

    try:
        if ext in {".txt", ".md", ".json"}:
            # 文本文件，直接返回内容
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "success": True,
                "filename": filename,
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
            safe_filename = normalized_path
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
        filename: 报告文件名（支持子目录路径如"专项报告/xxx.txt"）
    """
    from fastapi.responses import FileResponse

    # 安全检查：防止路径遍历攻击
    normalized_path = os.path.normpath(filename)

    # 检查是否包含路径遍历攻击
    if (
        ".." in normalized_path
        or normalized_path.startswith("/")
        or normalized_path.startswith("\\")
    ):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "非法文件路径"},
        )

    # 构建完整路径
    results_dir = _get_active_results_dir()
    base_dir = os.path.abspath(results_dir)
    filepath = os.path.abspath(os.path.join(results_dir, normalized_path))

    # 确保路径在允许的目录内
    if not (filepath == base_dir or filepath.startswith(base_dir + os.sep)):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "非法文件路径"},
        )

    if _should_refresh_semantic_artifacts_for_path(normalized_path):
        _refresh_semantic_artifacts_for_runtime_read(
            results_dir, logging.getLogger(__name__), "报告下载"
        )

    if not os.path.exists(filepath):
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"文件不存在: {filename}"},
        )

    # 下载时使用的文件名（取basename）
    download_name = os.path.basename(filepath)
    return FileResponse(
        path=filepath, filename=download_name, media_type="application/octet-stream"
    )


# ==================== 报告生成 API (v3.0 新架构) ====================


class InvestigationReportRequest(BaseModel):
    """v3.0 报告生成请求"""

    case_background: Optional[str] = None
    data_scope: Optional[str] = None
    # v5.2: 报告生成模块参数（前端可配置）
    doc_number: Optional[str] = None
    selected_subjects: Optional[List[str]] = None
    thresholds: Optional[Dict[str, float]] = None
    sections: Optional[List[str]] = None


def _apply_report_generation_overrides(config_obj, request_obj):
    """
    将前端报告生成参数应用到归集配置。

    支持:
    - doc_number 覆盖
    - selected_subjects 过滤分析单元和公司列表
    """
    if request_obj is None:
        return config_obj

    if getattr(request_obj, "doc_number", None):
        config_obj.doc_number = str(request_obj.doc_number).strip()

    selected_subjects = getattr(request_obj, "selected_subjects", None) or []
    selected = {str(name).strip() for name in selected_subjects if str(name).strip()}
    if not selected:
        return config_obj

    try:
        from report_config.primary_targets_schema import AnalysisUnit, AnalysisUnitMember
    except Exception:
        return config_obj

    filtered_units = []
    for unit in config_obj.analysis_units:
        members = [m for m in unit.members if m in selected]
        if unit.anchor in selected and unit.anchor not in members:
            members.insert(0, unit.anchor)

        if unit.unit_type == "independent":
            if unit.anchor not in selected:
                continue
            members = [unit.anchor]

        if not members:
            continue

        anchor = unit.anchor if unit.anchor in members else members[0]

        filtered_member_details = []
        for md in unit.member_details or []:
            if md.name in members:
                filtered_member_details.append(
                    AnalysisUnitMember(
                        name=md.name,
                        relation=md.relation,
                        has_data=md.has_data,
                        id_number=getattr(md, "id_number", ""),
                    )
                )

        if not filtered_member_details:
            for m in members:
                filtered_member_details.append(
                    AnalysisUnitMember(
                        name=m,
                        relation="本人" if m == anchor else "家庭成员",
                        has_data=True,
                    )
                )

        filtered_units.append(
            AnalysisUnit(
                anchor=anchor,
                members=members,
                unit_type=unit.unit_type,
                member_details=filtered_member_details,
                note=unit.note,
            )
        )

    config_obj.analysis_units = filtered_units
    if config_obj.include_companies:
        config_obj.include_companies = [
            c for c in config_obj.include_companies if c in selected
        ]

    return config_obj


def _apply_runtime_report_options(builder_obj, request_obj) -> None:
    """
    将前端运行时报告参数注入报告构建器（阈值、章节开关）。
    """
    if builder_obj is None:
        return

    thresholds = getattr(request_obj, "thresholds", None) if request_obj else None
    sections = getattr(request_obj, "sections", None) if request_obj else None

    if hasattr(builder_obj, "set_generation_options"):
        builder_obj.set_generation_options(thresholds=thresholds, sections=sections)


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

    # 从请求中提取参数（如果 request 为 None 则使用默认值）
    case_background = request.case_background if request else None
    data_scope = request.data_scope if request else None

    try:
        active_input_dir = _get_active_input_dir()
        active_output_dir = _get_active_output_dir()

        # 1. 加载归集配置服务
        service = PrimaryTargetsService(
            data_dir=active_input_dir, output_dir=active_output_dir
        )

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
        config = _apply_report_generation_overrides(config, request)

        # 3. 加载报告构建器
        builder = load_investigation_report_builder(active_output_dir)
        if builder is None:
            logger.warning("[报告生成] 缓存数据不存在，请先运行分析")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "分析缓存不存在，请先运行分析"},
            )

        # 【v4.1 新增】设置用户配置到报告构建器
        builder.set_primary_config(config)
        _apply_runtime_report_options(builder, request)
        logger.info(
            f"[报告生成] 已设置用户配置: {len(config.analysis_units)} 个分析单元"
        )

        # 【v5.0】使用最新报告生成方法
        report = builder.build_report_v5(
            config=config,
            case_background=case_background or config.case_notes,
            data_scope=data_scope,
        )
        if request and isinstance(report, dict):
            report.setdefault("meta", {})
            report["meta"]["generation_options"] = {
                "selected_subjects": request.selected_subjects or [],
                "thresholds": request.thresholds or {},
                "sections": request.sections or [],
            }

        semantic_paths = _persist_report_semantic_artifacts(
            builder, report=report, output_dir=active_output_dir
        )
        if semantic_paths:
            logger.info(f"[报告生成] report_package 已生成: {semantic_paths}")

        logger.info(f"[报告生成] v5.0 报告生成成功（完整四部分架构）")

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


@app.post("/api/investigation-report/generate-v5")
async def generate_investigation_report_v5(
    request: InvestigationReportRequest = None,
):
    """
    【v5.0】生成最新初查报告（完整四部分架构）

    根据最新报告生成构架准则，生成包含以下四部分的完整报告：
    - PART A: 家庭核查部分（家庭层级）
    - PART B: 个人核查部分（16个板块）
    - PART C: 公司核查部分（5个维度）
    - PART D: 综合研判

    Returns:
        {
            "success": True,
            "report": { InvestigationReport v5.0 完整结构 },
            "message": "v5.0报告生成成功"
        }
    """
    logger = logging.getLogger(__name__)
    logger.info("[报告生成v5] 开始生成v5.0报告（完整四部分架构）")

    # 从请求中提取参数
    case_background = request.case_background if request else None
    data_scope = request.data_scope if request else None

    try:
        active_input_dir = _get_active_input_dir()
        active_output_dir = _get_active_output_dir()

        # 1. 加载归集配置服务
        service = PrimaryTargetsService(
            data_dir=active_input_dir, output_dir=active_output_dir
        )

        # 2. 获取或创建归集配置
        config, msg, is_new = service.get_or_create_config()
        if config is None:
            logger.warning(f"[报告生成v5] 归集配置加载失败: {msg}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"归集配置加载失败: {msg}"},
            )

        logger.info(
            f"[报告生成v5] 配置加载成功: {len(config.analysis_units)} 个分析单元"
        )
        config = _apply_report_generation_overrides(config, request)

        # 3. 加载报告构建器
        builder = load_investigation_report_builder(active_output_dir)
        if builder is None:
            logger.warning("[报告生成v5] 缓存数据不存在，请先运行分析")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "分析缓存不存在，请先运行分析"},
            )

        # 4. 设置用户配置
        builder.set_primary_config(config)
        _apply_runtime_report_options(builder, request)

        # 5. 使用v5.0方法生成报告
        report = builder.build_report_v5(
            config=config,
            case_background=case_background or config.case_notes,
            data_scope=data_scope,
        )
        if request and isinstance(report, dict):
            report.setdefault("meta", {})
            report["meta"]["generation_options"] = {
                "selected_subjects": request.selected_subjects or [],
                "thresholds": request.thresholds or {},
                "sections": request.sections or [],
            }

        semantic_paths = _persist_report_semantic_artifacts(
            builder, report=report, output_dir=active_output_dir
        )
        if semantic_paths:
            logger.info(f"[报告生成v5] report_package 已生成: {semantic_paths}")

        logger.info("[报告生成v5] 调查报告生成成功")

        return {
            "success": True,
            "report": report,
            "message": "调查报告生成成功（完整四部分架构）",
            "version": APP_RELEASE_VERSION,
            "report_schema_version": "5.0.0",
            "config_info": {
                "analysis_units_count": len(config.analysis_units),
                "doc_number": config.doc_number,
                "employer": config.employer,
            },
        }

    except Exception as e:
        logger.exception(f"[报告生成v5] 生成失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"调查报告生成失败: {str(e)}"},
        )


@app.post("/api/investigation-report/generate-html")
async def generate_investigation_report_html(
    request: InvestigationReportRequest = None,
):
    """
    【v5.1 新增】生成HTML格式初查报告（所见即所得）

    严格遵循"所见即所得"原则：
    - 使用与正式报告完全相同的 Jinja2 模板 (templates/report_v3/)
    - 使用与正式报告完全相同的数据生成逻辑 (build_report_v5)
    - 预览中看到的，就是最终下载的正式报告

    Returns:
        {
            "success": True,
            "html": "<html>...</html>",  # 完整HTML报告
            "message": "HTML报告生成成功"
        }
    """
    logger = logging.getLogger(__name__)
    logger.info("[HTML报告生成] 开始生成正式HTML报告（所见即所得）")

    # 从请求中提取参数
    case_background = request.case_background if request else None
    data_scope = request.data_scope if request else None

    try:
        data_dir = _get_active_input_dir()
        output_dir = _get_active_output_dir()

        # 1. 加载归集配置服务
        service = PrimaryTargetsService(data_dir=data_dir, output_dir=output_dir)

        # 2. 获取或创建归集配置
        config, msg, is_new = service.get_or_create_config()
        if config is None:
            logger.warning(f"[HTML报告生成] 归集配置加载失败: {msg}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"归集配置加载失败: {msg}"},
            )

        logger.info(
            f"[HTML报告生成] 配置加载成功: {len(config.analysis_units)} 个分析单元"
        )
        config = _apply_report_generation_overrides(config, request)

        # 3. 加载报告构建器
        builder = load_investigation_report_builder(output_dir)
        if builder is None:
            logger.warning("[HTML报告生成] 缓存数据不存在，请先运行分析")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "分析缓存不存在，请先运行分析"},
            )

        # 4. 设置用户配置
        builder.set_primary_config(config)
        _apply_runtime_report_options(builder, request)

        # 5. 【关键】使用 build_report_v5 生成完整报告数据
        report = builder.build_report_v5(
            config=config,
            case_background=case_background or config.case_notes,
            data_scope=data_scope,
        )
        if request and isinstance(report, dict):
            report.setdefault("meta", {})
            report["meta"]["generation_options"] = {
                "selected_subjects": request.selected_subjects or [],
                "thresholds": request.thresholds or {},
                "sections": request.sections or [],
            }

        semantic_paths = _persist_report_semantic_artifacts(
            builder, report=report, output_dir=output_dir
        )
        if semantic_paths:
            logger.info(f"[HTML报告生成] report_package 已生成: {semantic_paths}")

        logger.info(f"[HTML报告生成] 报告数据生成完成，开始渲染HTML模板")

        # 6. 【关键】使用 Jinja2 模板渲染正式HTML
        html_content = builder.render_html_report_v3(report)

        logger.info(f"[HTML报告生成] HTML渲染完成，长度: {len(html_content)} 字符")

        return {
            "success": True,
            "html": html_content,
            "message": "HTML报告生成成功（所见即所得）",
            "config_info": {
                "analysis_units_count": len(config.analysis_units),
                "doc_number": config.doc_number,
                "selected_subjects_count": len(request.selected_subjects or [])
                if request
                else 0,
            },
        }

    except Exception as e:
        logger.exception(f"[HTML报告生成] 生成失败: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"HTML报告生成失败: {str(e)}"},
        )


@app.post("/api/investigation-report/save-html")
async def save_html_report(request: dict):
    """
    保存HTML报告到输出目录

    【v5.1 修改】前端传来的HTML应该是从 /generate-html 获取的正式报告
    保存到 output/analysis_results/ 目录
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
        reports_dir = _get_active_results_dir()
        os.makedirs(reports_dir, exist_ok=True)

        # 路径安全校验：仅允许保存到 analysis_results 根目录
        if not filename or not str(filename).strip():
            filename = "初查报告.html"
        filename = str(filename).strip()
        if len(filename) > 255:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "文件名过长"},
            )
        invalid_chars = ["<", ">", ":", '"', "|", "?", "*", "\x00"]
        if any(char in filename for char in invalid_chars):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "文件名包含非法字符"},
            )
        normalized_name = os.path.normpath(filename)
        if (
            ".." in normalized_name
            or normalized_name.startswith("/")
            or normalized_name.startswith("\\")
            or "/" in normalized_name
            or "\\" in normalized_name
        ):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "非法文件路径"},
            )
        if not normalized_name.lower().endswith(".html"):
            normalized_name += ".html"

        base_dir = os.path.abspath(reports_dir)
        filepath = os.path.abspath(os.path.join(reports_dir, normalized_name))
        if not filepath.startswith(base_dir + os.sep):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "非法文件路径"},
            )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        semantic_paths = _refresh_report_semantic_artifacts(_get_active_output_dir())
        if semantic_paths:
            logger.info(f"[报告保存] report_package 已刷新: {semantic_paths}")

        index_path = _refresh_report_index_file(_get_active_output_dir())
        if index_path:
            logger.info(f"[报告保存] 报告目录清单已刷新: {index_path}")

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
        active_input_dir = _get_active_input_dir()
        active_output_dir = _get_active_output_dir()

        # 1. 加载归集配置
        service = PrimaryTargetsService(
            data_dir=active_input_dir, output_dir=active_output_dir
        )
        config, msg = service.load_config()

        if config is None:
            logger.warning(f"[txt报告] 配置加载失败: {msg}，生成默认配置")
            config, msg, _ = service.get_or_create_config()

        # 2. 加载报告构建器
        builder = load_investigation_report_builder(active_output_dir)
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
        output_dirs = create_output_directories(active_output_dir)
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


class OpenFolderRequest(BaseModel):
    """打开文件夹请求"""

    relativePath: str


@app.post("/api/open-folder")
async def open_folder(request: OpenFolderRequest):
    """在系统文件管理器中打开指定文件夹"""
    import subprocess
    import platform

    folder_path = _resolve_open_folder_path(request.relativePath)

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
    _sync_analysis_state_with_active_output()
    if analysis_state.status != "completed" or not analysis_state.results:
        raise HTTPException(status_code=400, detail="分析尚未完成")

    results = analysis_state.results
    persons = results.get("persons", [])
    companies = results.get("companies", [])
    wallet_data = results.get("walletData", {})
    analysis_results = results.get("analysisResults", {})
    related_party = analysis_results.get("relatedParty", {}) if isinstance(analysis_results, dict) else {}
    penetration = analysis_results.get("penetration", {}) if isinstance(analysis_results, dict) else {}
    aggregation_overview = build_aggregation_overview(
        analysis_results=analysis_results if isinstance(analysis_results, dict) else {},
        scope_entities=persons + companies,
        limit=8,
    )
    penetration_meta = (
        penetration.get("analysis_metadata", {}) if isinstance(penetration, dict) else {}
    )
    related_party_meta = (
        related_party.get("analysis_metadata", {}) if isinstance(related_party, dict) else {}
    )

    # 从缓存结果中获取图谱数据
    graph_cache = _augment_graph_cache_with_wallet_data(
        results.get("graphData", {}),
        wallet_data,
        core_persons=persons,
        companies=companies,
    )
    nodes = graph_cache.get("nodes", [])
    edges = graph_cache.get("edges", [])
    wallet_report = graph_cache.get("walletReport", {}) if isinstance(graph_cache, dict) else {}
    focus_entities = annotate_focus_entities_with_graph(
        aggregation_overview.get("highlights", []),
        graph_nodes=nodes,
    )
    aggregation_summary = aggregation_overview.get("summary", {})

    # 构建完整的统计信息（前端 GraphData 接口要求）
    stats = {
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "corePersonCount": len(persons),
        "corePersonNames": persons,
        "involvedCompanyCount": len(companies),
        "highRiskCount": int(
            aggregation_summary.get("极高风险实体数", 0)
            + aggregation_summary.get("高风险实体数", 0)
        ),
        "mediumRiskCount": int(aggregation_summary.get("中风险实体数", 0) or 0),
        "loanPairCount": 0,
        "noRepayCount": 0,
        "discoveredNodeCount": len(related_party.get("discovered_nodes", [])),
        "relationshipClusterCount": len(related_party.get("relationship_clusters", [])),
        "walletAlertCount": len(wallet_report.get("wallet_alerts", []) or []) if isinstance(wallet_report, dict) else 0,
        "walletCounterpartyCount": len(wallet_report.get("wallet_counterparties", []) or []) if isinstance(wallet_report, dict) else 0,
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
        "third_party_relays": related_party.get("third_party_relays", []),
        "discovered_nodes": related_party.get("discovered_nodes", []),
        "relationship_clusters": related_party.get("relationship_clusters", []),
        "fund_cycles": penetration.get("fund_cycles") or related_party.get("fund_loops", []),
        "fund_cycle_meta": penetration_meta.get("fund_cycles")
        or related_party_meta.get("fund_loops", {})
        or {},
        "focus_entities": focus_entities,
        "aggregation_summary": aggregation_summary,
        "aggregation_metadata": aggregation_overview.get("analysis_metadata", {}),
        "wallet_alerts": wallet_report.get("wallet_alerts", []) if isinstance(wallet_report, dict) else [],
        "wallet_counterparties": wallet_report.get("wallet_counterparties", []) if isinstance(wallet_report, dict) else [],
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
    _sync_analysis_state_with_active_output()
    if analysis_state.status != "completed" or not analysis_state.results:
        raise HTTPException(status_code=400, detail="分析尚未完成")

    results = analysis_state.results
    persons = results.get("persons", [])
    companies = results.get("companies", [])

    output_dir = _get_active_output_dir()
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
    audit_navigation_extensions = {".xlsx", ".html", ".docx", ".txt", ".pdf"}
    if os.path.exists(analysis_results_dir):
        _refresh_semantic_artifacts_for_runtime_read(
            analysis_results_dir, logging.getLogger(__name__), "审计导航"
        )
        report_files = [
            {
                "name": item["name"],
                "size": item["size"],
                "sizeFormatted": f"{item['size'] / 1024:.1f}KB"
                if item["size"] < 1024 * 1024
                else f"{item['size'] / 1024 / 1024:.1f}MB",
                "modified": item["modified"],
                "isPrimary": str(item.get("groupKey") or "") == "primary_reports",
            }
            for item in _collect_report_files(analysis_results_dir)
            if str(item.get("extension") or "").lower() in audit_navigation_extensions
        ]
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

            if current_status == "completed" and last_status != "completed":
                # 仅在 completed 边沿发送一次 complete，避免前端重复拉取结果
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

    _cli_entrypoint_invoked = True
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    uvicorn.run(app, host="0.0.0.0", port=_get_server_port())
