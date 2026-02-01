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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
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

# ==================== Windows asyncio 兼容性修复 ====================
if sys.platform == 'win32':
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
                "error": self.error
            }

analysis_state = AnalysisState()
_current_config = {}
_ws_connections = set()

# ==================== Pydantic 模型 ====================
class AnalysisConfig(BaseModel):
    inputDirectory: str
    outputDirectory: Optional[str] = None
    cashThreshold: Optional[float] = 50000
    modules: Optional[Dict[str, bool]] = None

# ==================== 辅助函数 ====================
def create_output_directories(base_dir: str) -> Dict[str, str]:
    """创建输出目录结构"""
    dirs = {
        'output': base_dir,
        'cleaned_persons': os.path.join(base_dir, 'cleaned_data', '个人'),
        'cleaned_companies': os.path.join(base_dir, 'cleaned_data', '公司'),
        'analysis_cache': os.path.join(base_dir, 'analysis_cache'),
        'analysis_results': os.path.join(base_dir, 'analysis_results'),
    }
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    return dirs

def serialize_profiles(profiles: Dict) -> Dict:
    """序列化画像数据"""
    result = {}
    for name, profile in profiles.items():
        try:
            if hasattr(profile, 'dict'):
                result[name] = profile.dict()
            elif isinstance(profile, dict):
                result[name] = profile
            else:
                result[name] = dict(profile)
        except Exception:
            result[name] = str(profile)
    return result

def serialize_suspicions(suspicions: Dict) -> Dict:
    """序列化疑点数据"""
    return suspicions

def serialize_analysis_results(results: Dict) -> Dict:
    """序列化分析结果"""
    return results

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
        output_dir = analysis_config.outputDirectory or os.path.join(os.path.dirname(data_dir), "output")

        # 更新全局配置
        global _current_config
        _current_config["inputDirectory"] = data_dir
        _current_config["outputDirectory"] = output_dir
        config.LARGE_CASH_THRESHOLD = analysis_config.cashThreshold

        # ========================================================================
        # Phase 1: 文件扫描 (5%)
        # ========================================================================
        analysis_state.update(progress=5, phase="扫描数据目录...")
        logger.info(f"扫描数据目录: {data_dir}")

        phase1_start = time.time()

        categorized_files = file_categorizer.categorize_files(data_dir)
        persons = list(categorized_files['persons'].keys())
        companies = list(categorized_files['companies'].keys())

        phase1_duration = (time.time() - phase1_start) * 1000
        logging_config.log_performance(logger, "Phase 1-扫描文件", phase1_duration,
                                     person_count=len(persons), company_count=len(companies))
        logger.info(f"发现 {len(persons)} 个个人, {len(companies)} 个企业")

        # ========================================================================
        # Phase 2: 数据清洗 (15%)
        # ========================================================================
        analysis_state.update(progress=15, phase="数据清洗与标准化...")
        logger.info("开始数据清洗...")

        phase2_start = time.time()

        cleaned_data = {}
        output_dirs = create_output_directories(output_dir)

        total_entities = len(persons) + len(companies)

        # 清洗个人数据
        for i, p in enumerate(persons):
            p_files = categorized_files['persons'].get(p, [])
            if p_files:
                df, _ = data_cleaner.clean_and_merge_files(p_files, p)
                if df is not None and not df.empty:
                    cleaned_data[p] = df
                    output_path = os.path.join(output_dirs['cleaned_persons'], f'{p}_合并流水.xlsx')
                    try:
                        data_cleaner.save_formatted_excel(df, output_path)
                        logger.info(f"已保存清洗数据: {p} -> {output_path}")
                    except Exception as e:
                        logger.warning(f"保存清洗数据失败 {p}: {e}")

            progress = 15 + int(10 * (i + 1) / total_entities)
            analysis_state.update(progress=progress)

        # 清洗公司数据
        for i, c in enumerate(companies):
            c_files = categorized_files['companies'].get(c, [])
            if c_files:
                df, _ = data_cleaner.clean_and_merge_files(c_files, c)
                if df is not None and not df.empty:
                    cleaned_data[c] = df
                    output_path = os.path.join(output_dirs['cleaned_companies'], f'{c}_合并流水.xlsx')
                    try:
                        data_cleaner.save_formatted_excel(df, output_path)
                        logger.info(f"已保存清洗数据: {c} -> {output_path}")
                    except Exception as e:
                        logger.warning(f"保存清洗数据失败 {c}: {e}")

            progress = 15 + int(10 * (len(persons) + i + 1) / total_entities)
            analysis_state.update(progress=progress)

        phase2_duration = (time.time() - phase2_start) * 1000
        logging_config.log_performance(logger, "Phase 2-数据清洗", phase2_duration,
                                     entity_count=len(cleaned_data))
        logger.info(f"清洗完成，共 {len(cleaned_data)} 个实体数据")

        # ========================================================================
        # Phase 3: 线索提取 (30%)
        # ========================================================================
        analysis_state.update(progress=30, phase="提取关联线索...")

        phase3_start = time.time()
        clue_persons, clue_companies = data_extractor.extract_all_clues(data_dir)
        all_persons = list(set(persons + clue_persons))
        all_companies = list(set(companies + clue_companies))

        phase3_duration = (time.time() - phase3_start) * 1000
        logging_config.log_performance(logger, "Phase 3-线索提取", phase3_duration,
                                     clue_persons=len(clue_persons), clue_companies=len(clue_companies))

        # ========================================================================
        # Phase 4: 外部数据提取 (40%) ← 🔄 关键改进: 全部提取器提前执行!
        # ========================================================================
        analysis_state.update(progress=40, phase="提取外部数据源 (P0/P1/P2)...")
        logger.info("🔄 [重构] 开始提取全部外部数据源 (18个提取器)...")

        phase4_start = time.time()

        external_data = {
            'p0': {},  # P0: 核心上下文
            'p1': {},  # P1: 资产数据
            'p2': {},  # P2: 行为数据
            'id_to_name_map': {}  # 身份证号到人名的映射
        }

        # ========== P0: 核心上下文 ==========
        logger.info("  [P0] 提取核心上下文数据...")

        # P0.1: 人民银行银行账户
        try:
            pboc_accounts = pboc_account_extractor.extract_pboc_accounts(data_dir)
            external_data['p0']['pboc_accounts'] = pboc_accounts
            logger.info(f"    ✓ 人民银行账户: {len(pboc_accounts)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 人民银行账户提取失败: {e}")
            external_data['p0']['pboc_accounts'] = {}

        # P0.2: 反洗钱数据
        try:
            aml_data = aml_analyzer.extract_aml_data(data_dir)
            aml_alerts = aml_analyzer.get_aml_alerts(data_dir)
            external_data['p0']['aml_data'] = aml_data
            external_data['p0']['aml_alerts'] = aml_alerts
            logger.info(f"    ✓ 反洗钱数据: {len(aml_data)} 个主体, {len(aml_alerts)} 条预警")
        except Exception as e:
            logger.warning(f"    ✗ 反洗钱数据提取失败: {e}")
            external_data['p0']['aml_data'] = {}
            external_data['p0']['aml_alerts'] = []

        # P0.3: 企业登记信息
        try:
            company_info = company_info_extractor.extract_company_info(data_dir)
            external_data['p0']['company_info'] = company_info
            logger.info(f"    ✓ 企业登记信息: {len(company_info)} 个企业")
        except Exception as e:
            logger.warning(f"    ✗ 企业登记信息提取失败: {e}")
            external_data['p0']['company_info'] = {}

        # P0.4: 征信数据
        try:
            credit_data = credit_report_extractor.extract_credit_data(data_dir)
            credit_alerts = credit_report_extractor.get_credit_alerts(data_dir)
            external_data['p0']['credit_data'] = credit_data
            external_data['p0']['credit_alerts'] = credit_alerts
            logger.info(f"    ✓ 征信数据: {len(credit_data)} 个主体, {len(credit_alerts)} 条预警")
        except Exception as e:
            logger.warning(f"    ✗ 征信数据提取失败: {e}")
            external_data['p0']['credit_data'] = {}
            external_data['p0']['credit_alerts'] = []

        # P0.5: 银行业金融机构账户信息
        try:
            bank_account_info = bank_account_info_extractor.extract_bank_account_info(data_dir)
            external_data['p0']['bank_account_info'] = bank_account_info
            logger.info(f"    ✓ 银行账户信息: {len(bank_account_info)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 银行账户信息提取失败: {e}")
            external_data['p0']['bank_account_info'] = {}

        # ========== P1: 资产数据 ==========
        logger.info("  [P1] 提取资产数据...")

        # P1.1: 公安部机动车
        try:
            vehicle_data = vehicle_extractor.extract_vehicle_data(data_dir)
            external_data['p1']['vehicle_data'] = vehicle_data
            logger.info(f"    ✓ 公安部机动车: {len(vehicle_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 公安部机动车提取失败: {e}")
            external_data['p1']['vehicle_data'] = {}

        # P1.2: 银行理财产品
        try:
            wealth_product_data = wealth_product_extractor.extract_wealth_product_data(data_dir)
            external_data['p1']['wealth_product_data'] = wealth_product_data
            logger.info(f"    ✓ 银行理财产品: {len(wealth_product_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 银行理财产品提取失败: {e}")
            external_data['p1']['wealth_product_data'] = {}

        # P1.3: 证券信息
        try:
            securities_data = securities_extractor.extract_securities_data(data_dir)
            external_data['p1']['securities_data'] = securities_data
            logger.info(f"    ✓ 证券信息: {len(securities_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 证券信息提取失败: {e}")
            external_data['p1']['securities_data'] = {}

        # P1.4: 自然资源部精准查询
        try:
            precise_property_data = asset_extractor.extract_precise_property_info(data_dir)
            external_data['p1']['precise_property_data'] = precise_property_data
            logger.info(f"    ✓ 自然资源部精准查询: {len(precise_property_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 自然资源部精准查询提取失败: {e}")
            external_data['p1']['precise_property_data'] = {}

        # ========== P2: 行为数据 ==========
        logger.info("  [P2] 提取行为数据...")

        # P2.1: 保险信息
        try:
            insurance_data = insurance_extractor.extract_insurance_data(data_dir)
            external_data['p2']['insurance_data'] = insurance_data
            logger.info(f"    ✓ 保险信息: {len(insurance_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 保险信息提取失败: {e}")
            external_data['p2']['insurance_data'] = {}

        # P2.2: 出入境记录
        try:
            immigration_data = immigration_extractor.extract_immigration_data(data_dir)
            external_data['p2']['immigration_data'] = immigration_data
            logger.info(f"    ✓ 出入境记录: {len(immigration_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 出入境记录提取失败: {e}")
            external_data['p2']['immigration_data'] = {}

        # P2.3: 旅馆住宿
        try:
            hotel_data = hotel_extractor.extract_hotel_data(data_dir)
            cohabitation_analysis = hotel_extractor.analyze_cohabitation(data_dir)
            external_data['p2']['hotel_data'] = hotel_data
            external_data['p2']['hotel_cohabitation'] = cohabitation_analysis
            logger.info(f"    ✓ 旅馆住宿: {len(hotel_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 旅馆住宿提取失败: {e}")
            external_data['p2']['hotel_data'] = {}
            external_data['p2']['hotel_cohabitation'] = {}

        # P2.4: 铁路出行
        try:
            railway_data = railway_extractor.extract_railway_data(data_dir)
            railway_timeline = railway_extractor.build_railway_timeline(data_dir)
            external_data['p2']['railway_data'] = railway_data
            external_data['p2']['railway_timeline'] = railway_timeline
            logger.info(f"    ✓ 铁路出行: {len(railway_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 铁路出行提取失败: {e}")
            external_data['p2']['railway_data'] = {}
            external_data['p2']['railway_timeline'] = {}

        # P2.5: 航班出行
        try:
            flight_data = flight_extractor.extract_flight_data(data_dir)
            flight_timeline = flight_extractor.build_flight_timeline(data_dir)
            external_data['p2']['flight_data'] = flight_data
            external_data['p2']['flight_timeline'] = flight_timeline
            logger.info(f"    ✓ 航班出行: {len(flight_data)} 个主体")
        except Exception as e:
            logger.warning(f"    ✗ 航班出行提取失败: {e}")
            external_data['p2']['flight_data'] = {}
            external_data['p2']['flight_timeline'] = {}

        phase4_duration = (time.time() - phase4_start) * 1000
        logging_config.log_performance(logger, "Phase 4-外部数据提取(全部)", phase4_duration)

        logger.info("🔄 [重构] 外部数据提取完成")

        # ========================================================================
        # Phase 5: 融合数据画像 (50%) ← 🔄 结合外部数据生成完整画像
        # ========================================================================
        analysis_state.update(progress=50, phase="生成融合数据画像...")
        logger.info("🔄 [重构] 生成包含外部数据的完整画像...")

        phase5_start = time.time()

        profiles = {}
        id_to_name_map = {}

        # 🔄 构建身份证号到人名的映射（直接扫描数据目录的文件名）
        import glob
        transaction_dir = os.path.join(data_dir, '银行业金融机构交易流水（定向查询）')
        if os.path.exists(transaction_dir):
            pattern = os.path.join(transaction_dir, '*_*_*.xlsx')
            for file_path in glob.glob(pattern):
                # 从文件名提取: 滕雳_310230196811100267_...
                basename = os.path.basename(file_path)
                parts = basename.split('_')
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
                        profile['bank_accounts'] = financial_profiler.extract_bank_accounts(df)
                    except Exception as e:
                        logger.warning(f"提取 {entity} 银行账户失败: {e}")

                # 4. 🔄 融合外部数据 (P0 - 核心上下文)
                # P0.1: 人民银行账户
                if entity in external_data['p0'].get('pboc_accounts', {}):
                    profile['bank_accounts_official'] = external_data['p0']['pboc_accounts'][entity].get('accounts', [])

                # P0.2: 反洗钱预警
                if entity in external_data['p0'].get('aml_data', {}):
                    profile['aml_info'] = external_data['p0']['aml_data'][entity]

                # P0.3: 企业信息
                if entity in external_data['p0'].get('company_info', {}):
                    profile['company_registration'] = external_data['p0']['company_info'][entity]

                # P0.4: 征信信息
                if entity in external_data['p0'].get('credit_data', {}):
                    profile['credit_info'] = external_data['p0']['credit_data'][entity]

                # P0.5: 银行账户信息补充
                if entity in external_data['p0'].get('bank_account_info', {}):
                    existing = profile.get('bank_accounts_official', [])
                    existing_nums = {a.get('account_number') for a in existing}
                    for acc in external_data['p0']['bank_account_info'][entity].get('accounts', []):
                        if acc.get('account_number') not in existing_nums:
                            existing.append(acc)
                    profile['bank_accounts_official'] = existing

                # 5. 🔄 融合外部数据 (P1 - 资产)
                # P1.1: 车辆 (使用身份证号映射)
                vehicle_data = external_data['p1'].get('vehicle_data', {})
                for person_id, vehicles in vehicle_data.items():
                    person_name = id_to_name_map.get(person_id, person_id)
                    if person_name == entity:
                        profile['vehicles'] = vehicles
                        break

                # P1.2: 理财产品
                if entity in external_data['p1'].get('wealth_product_data', {}):
                    wealth_info = external_data['p1']['wealth_product_data'][entity]
                    profile['wealth_products'] = wealth_info.get('products', [])
                    profile['wealth_summary'] = wealth_info.get('summary', {})

                # P1.3: 证券
                if entity in external_data['p1'].get('securities_data', {}):
                    profile['securities'] = external_data['p1']['securities_data'][entity]

                # P1.4: 房产
                property_data = external_data['p1'].get('precise_property_data', {})
                for person_id, properties in property_data.items():
                    person_name = id_to_name_map.get(person_id, person_id)
                    if person_name == entity:
                        profile['properties_precise'] = properties
                        break

                # 6. 🔄 融合外部数据 (P2 - 行为)
                # P2.1: 保险
                if entity in external_data['p2'].get('insurance_data', {}):
                    profile['insurance'] = external_data['p2']['insurance_data'][entity]

                # P2.2: 出入境
                if entity in external_data['p2'].get('immigration_data', {}):
                    profile['immigration_records'] = external_data['p2']['immigration_data'][entity]

                # P2.3: 住宿
                if entity in external_data['p2'].get('hotel_data', {}):
                    profile['hotel_records'] = external_data['p2']['hotel_data'][entity]

                # P2.4: 铁路
                if entity in external_data['p2'].get('railway_data', {}):
                    profile['railway_records'] = external_data['p2']['railway_data'][entity]

                # P2.5: 航班
                if entity in external_data['p2'].get('flight_data', {}):
                    profile['flight_records'] = external_data['p2']['flight_data'][entity]

                profiles[entity] = profile

            except Exception as e:
                logger.warning(f"生成 {entity} 画像失败: {e}")

        phase5_duration = (time.time() - phase5_start) * 1000
        logging_config.log_performance(logger, "Phase 5-融合数据画像", phase5_duration,
                                     profile_count=len(profiles))
        logger.info(f"🔄 [重构] 融合画像生成完成: {len(profiles)} 个实体")

        # ========================================================================
        # Phase 6: 全面分析 (70%) ← 🔄 有完整上下文后执行
        # ========================================================================
        analysis_state.update(progress=70, phase="运行全面分析模块...")
        logger.info("🔄 [重构] 运行全面分析 (有完整上下文)...")

        phase6_start = time.time()

        analysis_results = {}

        # 防御性检查：确保有有效的配置
        modules_config = {}
        if analysis_config is not None and hasattr(analysis_config, 'modules') and analysis_config.modules is not None:
            modules_config = analysis_config.modules
        else:
            # 默认所有模块启用
            modules_config = {
                "loanAnalysis": True,
                "incomeAnalysis": True,
                "relatedParty": True,
                "multiSourceCorrelation": True,
                "timeSeriesAnalysis": True,
                "clueAggregation": True
            }

        # 6.1 借贷分析
        if modules_config.get("loanAnalysis", True):
            try:
                analysis_results["loan"] = loan_analyzer.analyze_loan_behaviors(cleaned_data, all_persons)
                logger.info("  ✓ 借贷分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 借贷分析失败: {e}")

        # 6.2 收入分析
        if modules_config.get("incomeAnalysis", True):
            try:
                analysis_results["income"] = income_analyzer.detect_suspicious_income(cleaned_data, all_persons)
                analysis_results["large_transactions"] = income_analyzer.extract_large_transactions(cleaned_data, all_persons)
                logger.info("  ✓ 收入分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 收入分析失败: {e}")

        # 6.3 关联方分析
        if modules_config.get("relatedParty", True):
            try:
                analysis_results["relatedParty"] = related_party_analyzer.analyze_related_party_flows(cleaned_data, all_persons)

                # 调查单位往来分析
                investigation_unit_flows = {}
                all_entities = all_persons + all_companies
                for entity in all_entities:
                    if entity in cleaned_data:
                        df = cleaned_data[entity]
                        flows = related_party_analyzer.analyze_investigation_unit_flows(df, entity)
                        if flows.get('has_flows', False):
                            investigation_unit_flows[entity] = {
                                'total_amount': flows.get('total_income', 0) + flows.get('total_expense', 0),
                                'total_income': flows.get('total_income', 0),
                                'total_expense': flows.get('total_expense', 0),
                                'net_flow': flows.get('net_flow', 0),
                                'income_count': flows.get('income_count', 0),
                                'expense_count': flows.get('expense_count', 0),
                                'transactions': flows.get('income_details', [])[:20] + flows.get('expense_details', [])[:20],
                                'matched_units': list(flows.get('matched_units', []))
                            }
                analysis_results["investigation_unit_flows"] = investigation_unit_flows
                logger.info("  ✓ 关联方分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 关联方分析失败: {e}")

        # 6.4 多源数据碰撞
        if modules_config.get("multiSourceCorrelation", True):
            try:
                analysis_results["correlation"] = multi_source_correlator.run_all_correlations(
                    data_dir, cleaned_data, all_persons
                )
                logger.info("  ✓ 多源数据碰撞完成")
            except Exception as e:
                logger.warning(f"  ✗ 多源数据碰撞失败: {e}")

        # 6.5 时序分析
        if modules_config.get("timeSeriesAnalysis", True):
            try:
                analysis_results["timeSeries"] = time_series_analyzer.analyze_time_series(cleaned_data, all_persons)
                logger.info("  ✓ 时序分析完成")
            except Exception as e:
                logger.warning(f"  ✗ 时序分析失败: {e}")

        # 6.6 线索聚合
        if modules_config.get("clueAggregation", True):
            try:
                analysis_results["aggregation"] = clue_aggregator.aggregate_all_results(
                    all_persons, all_companies,
                    penetration_results=None,
                    ml_results=None,
                    ts_results=analysis_results.get("timeSeries"),
                    related_party_results=analysis_results.get("relatedParty"),
                    loan_results=analysis_results.get("loan")
                )
                logger.info("  ✓ 线索聚合完成")
            except Exception as e:
                logger.warning(f"  ✗ 线索聚合失败: {e}")

        # 6.7 家庭关系分析
        try:
            family_units_list = family_analyzer.build_family_units(all_persons, data_dir)
            family_tree = family_analyzer.build_family_tree(all_persons, data_dir)
            family_summary = family_analyzer.get_family_summary(family_tree)

            analysis_results["family_tree"] = family_tree
            analysis_results["family_units"] = family_summary
            analysis_results["family_relations"] = family_tree
            analysis_results["family_units_v2"] = family_units_list

            # 计算家庭财务汇总
            all_family_summaries = {}
            for unit in family_units_list:
                householder = unit.get('householder', '')
                members = unit.get('members', [])
                if members:
                    try:
                        unit_summary = family_finance.calculate_family_summary(profiles, members)
                        unit_summary['householder'] = householder
                        unit_summary['extended_relatives'] = unit.get('extended_relatives', [])
                        all_family_summaries[householder] = unit_summary
                    except Exception as e:
                        logger.warning(f"计算 {householder} 家庭汇总失败: {e}")

            if all_family_summaries:
                first_householder = list(all_family_summaries.keys())[0]
                analysis_results["family_summary"] = all_family_summaries[first_householder]
                analysis_results["all_family_summaries"] = all_family_summaries
                logger.info(f"  ✓ 家庭分析完成: {len(family_units_list)} 个家庭")
            else:
                family_summary_result = family_finance.calculate_family_summary(profiles, all_persons)
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
            analysis_results["behavioral"] = behavioral_profiler.analyze_behavioral_patterns(
                cleaned_data, all_persons, external_data
            )
            logger.info("  ✓ 行为画像完成")
        except Exception as e:
            logger.warning(f"  ✗ 行为画像失败: {e}")

        phase6_duration = (time.time() - phase6_start) * 1000
        logging_config.log_performance(logger, "Phase 6-全面分析", phase6_duration,
                                     module_count=len(analysis_results))

        # ========================================================================
        # Phase 7: 疑点检测 (85%) ← 🔄 有完整上下文后执行
        # ========================================================================
        analysis_state.update(progress=85, phase="检测可疑交易模式...")
        logger.info("🔄 [重构] 执行疑点检测 (有资产上下文)...")

        phase7_start = time.time()

        # 7.1 基础疑点检测
        suspicions = suspicion_detector.run_all_detections(cleaned_data, all_persons, all_companies)

        # 7.2 🔄 融合外部疑点数据
        # 反洗钱预警
        aml_alerts = external_data['p0'].get('aml_alerts', [])
        if aml_alerts:
            suspicions["aml_alerts"] = aml_alerts

        # 征信预警
        credit_alerts = external_data['p0'].get('credit_alerts', [])
        if credit_alerts:
            suspicions["credit_alerts"] = credit_alerts

        # 7.3 🔄 隐形资产检测 (现在有房产/车辆数据可以对比!)
        try:
            hidden_assets = _detect_hidden_assets_with_context(
                profiles, cleaned_data, all_persons,
                external_data['p1']['precise_property_data'],
                external_data['p1']['vehicle_data']
            )
            if hidden_assets:
                suspicions["hidden_assets_with_context"] = hidden_assets
                logger.info(f"  ✓ 隐形资产检测: 发现 {len(hidden_assets)} 个可疑点")
        except Exception as e:
            logger.warning(f"  ✗ 隐形资产检测失败: {e}")

        phase7_duration = (time.time() - phase7_start) * 1000
        logging_config.log_performance(logger, "Phase 7-疑点检测(增强版)", phase7_duration,
                                     suspicion_count=len(suspicions.get("direct_transfers", [])))

        # ========================================================================
        # Phase 8: 报告生成 (100%)
        # ========================================================================
        analysis_state.update(progress=95, phase="生成分析报告...")

        phase8_start = time.time()

        # 8.1 构建家庭资产数据
        try:
            precise_property_data = external_data['p1'].get('precise_property_data', {})
            vehicle_data = external_data['p1'].get('vehicle_data', {})

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

        # 8.2 生成公文报告
        try:
            official_report_path = report_generator.generate_official_report(
                profiles, suspicions, all_persons, all_companies,
                os.path.join(output_dirs['analysis_results'], config.OUTPUT_REPORT_FILE.replace('.docx', '.txt')),
                family_summary=analysis_results.get("family_summary", {}),
                family_assets=family_assets,
                cleaned_data=cleaned_data
            )
            logger.info(f"  ✓ 公文报告已生成: {official_report_path}")
        except Exception as e:
            logger.warning(f"  ✗ 公文报告生成失败: {e}")

        phase8_duration = (time.time() - phase8_start) * 1000
        logging_config.log_performance(logger, "Phase 8-报告生成", phase8_duration, report_count=1)

        # ========================================================================
        # 完成
        # ========================================================================
        analysis_state.update(progress=100, phase="分析完成")
        analysis_state.end_time = datetime.now()
        analysis_state.status = "completed"

        enhanced_suspicions = _enhance_suspicions_with_analysis(suspicions, analysis_results)

        # 预计算图谱数据
        logger.info("预计算图谱数据...")
        graph_data_cache = None
        try:
            flow_stats = flow_visualizer._calculate_flow_stats(cleaned_data, all_persons)
            nodes, edges, edge_stats = flow_visualizer._prepare_graph_data(flow_stats, all_persons, all_companies)

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
                    "message": "为保证流畅度，仅展示核心资金网络。"
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
                }
            }
            logger.info(f"  ✓ 图谱缓存: {len(sampled_nodes)} 节点, {len(sampled_edges)} 边")
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
            "externalData": external_data,  # 🔄 新增: 外部数据也在结果中
        }

        # 保存到文件
        logger.info("保存分析缓存...")
        _save_analysis_cache_refactored(analysis_state.results, output_dirs['analysis_cache'])

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


def _detect_hidden_assets_with_context(profiles, cleaned_data, all_persons, property_data, vehicle_data):
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
        official_properties = profile.get('properties_precise', [])
        official_vehicles = profile.get('vehicles', [])

        # 检测疑似隐形房产 (交易中有相关支出但无登记)
        try:
            df = cleaned_data.get(person)
            if df is not None:
                # 查找房产相关交易
                property_transactions = df[
                    df['description'].str.contains('房|地产|物业|按揭', na=False) |
                    df['counterparty'].str.contains('房产|置业|开发商', na=False)
                ]

                if len(property_transactions) > 0 and len(official_properties) == 0:
                    hidden_assets.append({
                        'person': person,
                        'type': 'property',
                        'evidence': f'发现 {len(property_transactions)} 条房产相关交易，但无房产登记',
                        'transaction_count': len(property_transactions),
                        'amount': property_transactions['amount'].sum()
                    })
        except Exception as e:
            pass

        # 检测疑似隐形车辆
        try:
            df = cleaned_data.get(person)
            if df is not None:
                vehicle_transactions = df[
                    df['description'].str.contains('车|车辆|购车|4S店', na=False) |
                    df['counterparty'].str.contains('车行|汽车', na=False)
                ]

                if len(vehicle_transactions) > 0 and len(official_vehicles) == 0:
                    hidden_assets.append({
                        'person': person,
                        'type': 'vehicle',
                        'evidence': f'发现 {len(vehicle_transactions)} 条车辆相关交易，但无车辆登记',
                        'transaction_count': len(vehicle_transactions),
                        'amount': vehicle_transactions['amount'].sum()
                    })
        except Exception as e:
            pass

    return hidden_assets


def _save_analysis_cache_refactored(results, cache_dir):
    """保存分析缓存到文件"""
    logger = logging.getLogger(__name__)

    # 自定义JSON编码器处理pandas Timestamp, numpy等类型
    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            # 处理时间戳
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            # 处理numpy整数
            if hasattr(obj, 'dtype'):
                import numpy as np
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
            # 处理pandas Series
            if hasattr(obj, 'tolist'):
                return obj.tolist()
            # 处理字典和对象
            if hasattr(obj, '__dict__'):
                return obj.__dict__
            return super().default(obj)

    try:
        os.makedirs(cache_dir, exist_ok=True)

        # 保存 profiles.json
        with open(os.path.join(cache_dir, 'profiles.json'), 'w', encoding='utf-8') as f:
            json.dump(results['profiles'], f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)

        # 保存 suspicions.json
        with open(os.path.join(cache_dir, 'suspicions.json'), 'w', encoding='utf-8') as f:
            json.dump(results['suspicions'], f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)

        # 保存 derived_data.json
        with open(os.path.join(cache_dir, 'derived_data.json'), 'w', encoding='utf-8') as f:
            json.dump(results['analysisResults'], f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)

        # 保存 graph_data.json
        if results.get('graphData'):
            with open(os.path.join(cache_dir, 'graph_data.json'), 'w', encoding='utf-8') as f:
                json.dump(results['graphData'], f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)

        # 保存 metadata.json
        metadata = {
            "version": "3.2.0",  # 重构版本
            "generatedAt": datetime.now().isoformat(),
            "persons": results.get('persons', []),
            "companies": results.get('companies', []),
            "refactored": True,
            "dataFlow": "external_data_first"
        }
        with open(os.path.join(cache_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

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
    lifespan=lifespan
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
        "refactored": True
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
    """获取分析结果"""
    if analysis_state.status != "completed":
        raise HTTPException(status_code=400, detail="分析尚未完成")

    return analysis_state.results

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时日志推送"""
    await websocket.accept()
    _ws_connections.add(websocket)
    try:
        while True:
            await websocket.send_json(analysis_state.to_dict())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        _ws_connections.discard(websocket)

# ==================== 启动服务器 ====================
if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
