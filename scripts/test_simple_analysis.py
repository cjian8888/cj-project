#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的分析测试脚本 - 用于定位问题
"""

import sys
import logging
import json
from datetime import datetime
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 导入分析模块
try:
    import config
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
    import pboc_account_extractor
    import aml_analyzer
    import company_info_extractor
    import credit_report_extractor
    import bank_account_info_extractor
    import vehicle_extractor
    import wealth_product_extractor
    import securities_extractor
    import insurance_extractor
    import immigration_extractor
    import hotel_extractor
    import cohabitation_extractor
    import railway_extractor
    import flight_extractor
    import asset_extractor
except ImportError as e:
    logger.error(f"导入模块失败: {e}")
    sys.exit(1)

# 读取配置
data_dir = "./data"
output_dir = "./output"

logger.info("=" * 60)
logger.info("开始简化分析测试")
logger.info("=" * 60)

try:
    # 阶段 1: 扫描文件
    logger.info("[1/10] 扫描数据目录...")
    categorized_files = file_categorizer.categorize_files(data_dir)
    persons = list(categorized_files['persons'].keys())
    companies = list(categorized_files['companies'].keys())
    logger.info(f"发现 {len(persons)} 个个人, {len(companies)} 个企业")
    logger.info("✓ 阶段 1 完成")

    # 阶段 2: 数据清洗
    logger.info("[2/10] 数据清洗与标准化...")
    cleaned_data = {}
    
    # 创建输出目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(f"{output_dir}/cleaned_data/个人").mkdir(parents=True, exist_ok=True)
    Path(f"{output_dir}/cleaned_data/公司").mkdir(parents=True, exist_ok=True)
    Path(f"{output_dir}/analysis_results").mkdir(parents=True, exist_ok=True)
    
    # 只清洗第一个人员的数据作为测试
    if persons:
        p = persons[0]
        p_files = categorized_files['persons'].get(p, [])
        if p_files:
            logger.info(f"开始清洗 {p} 的数据,共{len(p_files)}个文件")
            try:
                df, _ = data_cleaner.clean_and_merge_files(p_files, p)
                if df is not None and not df.empty:
                    cleaned_data[p] = df
                    output_path = f"{output_dir}/cleaned_data/个人/{p}_合并流水.xlsx"
                    data_cleaner.save_formatted_excel(df, output_path)
                    logger.info(f"✓ 已保存清洗数据: {p}")
                else:
                    logger.warning(f"✗ 清洗数据为空: {p}")
            except Exception as e:
                logger.error(f"✗ 清洗 {p} 失败: {e}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
    
    logger.info(f"清洗完成，共 {len(cleaned_data)} 个实体数据")
    logger.info("✓ 阶段 2 完成")

    # 阶段 3: 线索提取
    logger.info("[3/10] 提取关联线索...")
    try:
        clue_persons, clue_companies = data_extractor.extract_all_clues(data_dir)
        all_persons = list(set(persons + clue_persons))
        all_companies = list(set(companies + clue_companies))
        logger.info(f"✓ 阶段 3 完成: 线索人员 {len(clue_persons)} 人, 线索公司 {len(clue_companies)} 家")
    except Exception as e:
        logger.error(f"✗ 阶段 3 失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        sys.exit(1)

    # 阶段 4: 资金画像
    logger.info("[4/10] 执行资金画像分析...")
    profiles = {}
    try:
        for entity, df in cleaned_data.items():
            try:
                profiles[entity] = financial_profiler.generate_profile_report(df, entity)
                logger.info(f"✓ 生成 {entity} 画像成功")
            except Exception as e:
                logger.warning(f"✗ 生成 {entity} 画像失败: {e}")
        logger.info(f"✓ 阶段 4 完成: 生成 {len(profiles)} 个画像")
    except Exception as e:
        logger.error(f"✗ 阶段 4 失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        sys.exit(1)

    # 阶段 5: 疑点检测
    logger.info("[5/10] 检测可疑交易模式...")
    try:
        suspicions = suspicion_detector.run_all_detections(cleaned_data, all_persons, all_companies)
        logger.info(f"✓ 阶段 5 完成: 发现 {len(suspicions.get('direct_transfers', []))} 条直接往来")
    except Exception as e:
        logger.error(f"✗ 阶段 5 失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("简化分析测试完成")
    logger.info("=" * 60)
    logger.info(f"处理人员: {len(all_persons)}")
    logger.info(f"处理公司: {len(all_companies)}")
    logger.info(f"生成画像: {len(profiles)}")
    logger.info(f"疑点检测: {len(suspicions.get('direct_transfers', []))} 条直接往来")

except Exception as e:
    logger.error(f"分析过程中发生错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
