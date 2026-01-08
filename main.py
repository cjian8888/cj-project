#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序 - 资金穿透与关联排查系统(优化版)
完整的端到端执行流程,支持数据清洗和中间数据生成
"""

import os
import sys
from datetime import datetime
from typing import Dict, List
import pandas as pd

import config
import utils
import file_categorizer
import data_cleaner
import data_extractor
import financial_profiler
import suspicion_detector
import asset_extractor
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

logger = utils.setup_logger(__name__)


def create_output_directories(base_dir: str) -> Dict[str, str]:
    """
    创建输出目录结构
    
    Returns:
        目录路径字典
    """
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
    
    logger.info(f'输出目录已创建: {base_dir}')
    
    return dirs


def main(data_directory: str = '.', output_directory: str = './output'):
    """
    主执行流程(优化版)
    
    Args:
        data_directory: 数据目录
        output_directory: 输出目录
    """
    overall_start = datetime.now()
    
    logger.info('=' * 80)
    logger.info('资金穿透与关联排查系统(优化版) - 启动')
    logger.info('=' * 80)
    logger.info(f'数据目录: {os.path.abspath(data_directory)}')
    logger.info(f'输出目录: {os.path.abspath(output_directory)}')
    logger.info('')
    
    try:
        # 创建输出目录
        output_dirs = create_output_directories(output_directory)
        
        # ============== 阶段0: 文件扫描与分类 ==============
        logger.info('【阶段0】文件扫描与分类')
        logger.info('-' * 80)
        
        categorized_files = file_categorizer.categorize_files(data_directory)
        
        persons = list(categorized_files['persons'].keys())
        companies = list(categorized_files['companies'].keys())
        
        if not persons and not companies:
            logger.error('未找到任何人员或公司的流水文件')
            return
        
        logger.info(f'✓ 识别核心人员: {len(persons)} 人 - {persons}')
        logger.info(f'✓ 识别涉案公司: {len(companies)} 家 - {companies}')
        logger.info('')
        
        # ============== 阶段1: 数据清洗与合并 ==============
        logger.info('【阶段1】数据清洗与合并')
        logger.info('-' * 80)
        
        # 每次运行都强制重新清洗数据（确保数据准确性）
        logger.info('【阶段1】数据清洗与合并 - 强制重新清洗')
        logger.info('-' * 80)
        
        cleaned_data = {}
        
        # 清洗个人数据（每次都重新清洗）
        for person_name in persons:
            file_path = os.path.join(output_dirs['cleaned_persons'], f'{person_name}_合并流水.xlsx')
            person_files = categorized_files['persons'].get(person_name, [])
            
            if person_files:
                logger.info(f'清洗个人数据: {person_name}（{len(person_files)}个文件）')
                try:
                    df_merged, stats = data_cleaner.clean_and_merge_files(person_files, person_name)
                    if not df_merged.empty:
                        # 保存清洗后的数据
                        data_cleaner.save_formatted_excel(df_merged, file_path)
                        
                        # 填充空值
                        if 'income' in df_merged.columns: df_merged['income'] = df_merged['income'].fillna(0)
                        if 'expense' in df_merged.columns: df_merged['expense'] = df_merged['expense'].fillna(0)
                        if 'counterparty' in df_merged.columns: df_merged['counterparty'] = df_merged['counterparty'].fillna('').astype(str)
                        if 'description' in df_merged.columns: df_merged['description'] = df_merged['description'].fillna('').astype(str)
                        
                        cleaned_data[person_name] = df_merged
                        logger.info(f'  {person_name}: {len(df_merged)} 条记录')
                except Exception as e:
                    logger.error(f'清洗失败 {person_name}: {e}')
            else:
                logger.warning(f'未找到个人原始文件: {person_name}')

        # 清洗公司数据（每次都重新清洗）
        for company_name in companies:
            file_path = os.path.join(output_dirs['cleaned_companies'], f'{company_name}_合并流水.xlsx')
            company_files = categorized_files['companies'].get(company_name, [])
            
            if company_files:
                logger.info(f'清洗公司数据: {company_name}（{len(company_files)}个文件）')
                try:
                    df_merged, stats = data_cleaner.clean_and_merge_files(company_files, company_name)
                    if not df_merged.empty:
                        # 保存清洗后的数据
                        data_cleaner.save_formatted_excel(df_merged, file_path)
                        
                        # 填充空值
                        if 'income' in df_merged.columns: df_merged['income'] = df_merged['income'].fillna(0)
                        if 'expense' in df_merged.columns: df_merged['expense'] = df_merged['expense'].fillna(0)
                        if 'counterparty' in df_merged.columns: df_merged['counterparty'] = df_merged['counterparty'].fillna('').astype(str)
                        if 'description' in df_merged.columns: df_merged['description'] = df_merged['description'].fillna('').astype(str)
                        
                        cleaned_data[company_name] = df_merged
                        logger.info(f'  {company_name}: {len(df_merged)} 条记录')
                except Exception as e:
                    logger.error(f'清洗公司数据失败 {company_name}: {e}')
            else:
                logger.warning(f'未找到公司原始文件: {company_name}')
        
        logger.info(f'已加载 {len(cleaned_data)} 个实体的清洗数据')
        
        logger.info('')
        
        # ============== 阶段2: 线索提取(可选) ==============
        logger.info('【阶段2】线索提取')
        logger.info('-' * 80)
        
        # 由于已经从文件名识别了人员和公司,这里可以跳过
        # 或者仍然尝试从PDF提取作为补充
        core_persons_from_file = persons
        involved_companies_from_file = companies
        
        # 尝试从线索文件提取(如果有)
        clue_persons, clue_companies = data_extractor.extract_all_clues(data_directory)
        
        # 合并
        all_persons = list(set(core_persons_from_file + clue_persons))
        all_companies = list(set(involved_companies_from_file + clue_companies))
        
        logger.info(f'✓ 最终核心人员: {len(all_persons)} 人 - {all_persons}')
        logger.info(f'✓ 最终涉案公司: {len(all_companies)} 家 - {all_companies}')
        logger.info('')
        
        # ============== 阶段2.5: 家族关系识别 ==============
        logger.info('【阶段2.5】家族关系识别')
        logger.info('-' * 80)
        
        family_tree = family_analyzer.build_family_tree(all_persons, data_directory)
        family_summary = family_analyzer.get_family_summary(family_tree)
        
        total_family_members = sum(len(members) for members in family_tree.values())
        logger.info(f'✓ 识别家族成员: {total_family_members} 人')
        logger.info('')
        
        # ============== 阶段3: 资金画像(基于清洗后数据) ==============
        logger.info('【阶段3】资金画像分析')
        logger.info('-' * 80)
        
        profiles = {}
        
        import account_analyzer
        
        for entity_name, df in cleaned_data.items():
            profiles[entity_name] = financial_profiler.generate_profile_report(
                df, entity_name
            )
            
            # 生成账户分析文本报告
            if any(p in entity_name for p in all_persons):
                try:
                    account_report = account_analyzer.generate_account_report(df, entity_name)
                    profiles[entity_name]['account_analysis_text'] = account_report
                except Exception as e:
                    logger.error(f'账户分析失败 {entity_name}: {e}')
        
        logger.info(f'✓ 已生成 {len(profiles)} 份资金画像与账户分析')
        logger.info('')
        
        # ============== 阶段4: 疑点检测 ==============
        logger.info('【阶段4】疑点碰撞检测')
        logger.info('-' * 80)
        
        # 将cleaned_data转换为old format for compatibility
        all_transactions_dict = cleaned_data
        
        suspicions = suspicion_detector.run_all_detections(
            all_transactions_dict,
            all_persons,
            all_companies
        )
        
        logger.info('')
        
        # ============== 阶段5: 资产提取与分析 ==============
        logger.info('【阶段5】资产提取与分析')
        logger.info('-' * 80)
        
        # 提取房产和车辆
        properties = asset_analyzer.extract_properties(data_directory, all_persons)
        vehicles = asset_analyzer.extract_vehicles(data_directory, all_persons)
        
        # 计算家族资产
        family_assets = asset_analyzer.calculate_family_assets(
            properties, vehicles, family_tree
        )
        
        logger.info(f'✓ 提取资产: {len(properties)} 套房产, {len(vehicles)} 辆车')
        logger.info('')
        
        # ============== 阶段5.5: 数据验证 ==============
        logger.info('【阶段5.5】数据验证')
        logger.info('-' * 80)
        
        # 验证流水数据
        transaction_validations = {}
        for entity, df in cleaned_data.items():
            validation_result = data_validator.validate_transaction_data(df, entity)
            transaction_validations[entity] = validation_result
            logger.info(f'{entity}: {validation_result["status"]}')
        
        # 交叉验证房产交易
        property_validations = data_validator.cross_validate_property_transactions(
            properties, cleaned_data
        )
        
        # 生成验证报告
        validation_report = data_validator.generate_validation_report(
            transaction_validations, property_validations
        )
        
        # 保存验证报告
        validation_report_path = os.path.join(
            output_dirs['analysis_results'],
            '数据验证报告.txt'
        )
        with open(validation_report_path, 'w', encoding='utf-8') as f:
            f.write(validation_report)
        logger.info(f'✓ 数据验证报告已生成: {validation_report_path}')
        logger.info('')
        
        # ============== 阶段5.6: 资金穿透分析 ==============
        logger.info('【阶段5.6】资金穿透分析')
        logger.info('-' * 80)
        
        # 分离个人和公司数据
        personal_data = {name: df for name, df in cleaned_data.items() if name in all_persons}
        company_data = {name: df for name, df in cleaned_data.items() if name in all_companies}
        
        # 执行资金穿透分析
        penetration_results = fund_penetration.analyze_fund_penetration(
            personal_data,
            company_data,
            all_persons,
            all_companies
        )
        
        # 生成资金穿透报告
        penetration_report_path = fund_penetration.generate_penetration_report(
            penetration_results,
            output_dirs['analysis_results']
        )
        logger.info(f'✓ 资金穿透报告已生成: {penetration_report_path}')
        logger.info('')
        
        # ============== 阶段5.7: 关联方资金分析 ==============
        logger.info('【阶段5.7】关联方资金穿透分析')
        logger.info('-' * 80)
        
        related_party_results = related_party_analyzer.analyze_related_party_flows(
            cleaned_data,
            all_persons
        )
        
        # 生成关联方分析报告
        related_party_report_path = related_party_analyzer.generate_related_party_report(
            related_party_results,
            output_dirs['analysis_results']
        )
        logger.info(f'✓ 关联方分析报告已生成: {related_party_report_path}')
        logger.info('')
        
        # ============== 阶段5.8: 多源数据碰撞 ==============
        logger.info('【阶段5.8】多源数据交叉碰撞分析')
        logger.info('-' * 80)
        
        correlation_results = multi_source_correlator.run_all_correlations(
            data_directory,
            cleaned_data,
            all_persons
        )
        
        # 生成多源碰撞报告
        correlation_report_path = multi_source_correlator.generate_correlation_report(
            correlation_results,
            output_dirs['analysis_results']
        )
        logger.info(f'✓ 多源碰撞报告已生成: {correlation_report_path}')
        logger.info('')
        
        # ============== 阶段5.9: 借贷行为分析 ==============
        logger.info('【阶段5.9】借贷行为分析')
        logger.info('-' * 80)
        
        loan_results = loan_analyzer.analyze_loan_behaviors(
            cleaned_data,
            all_persons
        )
        
        # 生成借贷分析报告
        loan_report_path = loan_analyzer.generate_loan_report(
            loan_results,
            output_dirs['analysis_results']
        )
        logger.info(f'✓ 借贷分析报告已生成: {loan_report_path}')
        logger.info('')
        
        # ============== 阶段5.10: 异常收入检测 ==============
        logger.info('【阶段5.10】异常收入来源检测')
        logger.info('-' * 80)
        
        income_results = income_analyzer.detect_suspicious_income(
            cleaned_data,
            all_persons
        )
        
        # 生成异常收入报告
        income_report_path = income_analyzer.generate_suspicious_income_report(
            income_results,
            output_dirs['analysis_results']
        )
        logger.info(f'✓ 异常收入报告已生成: {income_report_path}')
        logger.info('')
        
        # ============== 阶段5.11: 资金流向可视化 ==============
        logger.info('【阶段5.11】资金流向可视化')
        logger.info('-' * 80)
        
        viz_results = flow_visualizer.generate_flow_visualizations(
            cleaned_data,
            all_persons,
            loan_results,
            income_results,
            output_dirs['analysis_results']
        )
        
        logger.info(f'✓ Mermaid资金流向图已生成: {viz_results.get("mermaid", "")}')
        logger.info(f'✓ HTML交互式图表已生成: {viz_results.get("html", "")}')
        logger.info('')
        
        # ============== 阶段5.12: 机器学习风险预测 ==============
        logger.info('【阶段5.12】机器学习风险预测')
        logger.info('-' * 80)
        
        ml_results = ml_analyzer.run_ml_analysis(
            cleaned_data,
            all_persons,
            all_companies  # 传入涉案公司列表，用于团伙识别
        )
        
        ml_report_path = ml_analyzer.generate_ml_report(
            ml_results,
            output_dirs['analysis_results']
        )
        logger.info(f'✓ 机器学习预测报告已生成: {ml_report_path}')
        logger.info('')
        
        # ============== 阶段6: 报告生成 ==============
        logger.info('【阶段6】生成分析报告')
        logger.info('-' * 80)
        
        # 生成Excel底稿（包含家族关系和资产信息）
        excel_path = report_generator.generate_excel_workbook(
            profiles,
            suspicions,
            os.path.join(output_dirs['analysis_results'], config.OUTPUT_EXCEL_FILE),
            family_tree=family_tree,
            family_assets=family_assets,
            validation_results={
                'transactions': transaction_validations,
                'properties': property_validations
            },
            penetration_results=penetration_results
        )
        logger.info(f'✓ Excel底稿已生成: {excel_path}')
        
        # 生成公文报告（包含家族关系和资产信息）
        report_path = report_generator.generate_official_report(
            profiles,
            suspicions,
            all_persons,
            all_companies,
            os.path.join(output_dirs['analysis_results'], 
                        config.OUTPUT_REPORT_FILE.replace('.docx', '.txt')),
            family_summary=family_summary,
            family_assets=family_assets,
            cleaned_data=cleaned_data
        )
        logger.info(f'✓ 公文报告已生成: {report_path}')
        
        logger.info('')
        
        # ============== 执行摘要 ==============
        total_time = (datetime.now() - overall_start).total_seconds()
        
        logger.info('=' * 80)
        logger.info('执行摘要')
        logger.info('=' * 80)
        
        total_transactions = sum(len(df) for df in cleaned_data.values())
        
        total_suspicions = (
            len(suspicions['direct_transfers']) +
            len(suspicions['cash_collisions']) +
            sum(len(v) for v in suspicions['hidden_assets'].values()) +
            sum(len(v) for v in suspicions['fixed_frequency'].values()) +
            len(suspicions.get('cash_timing_patterns', [])) +
            sum(len(v) for v in suspicions.get('holiday_transactions', {}).values()) +
            sum(len(v) for v in suspicions.get('amount_patterns', {}).values())
        )
        
        # 关联方分析统计
        related_summary = related_party_results.get('summary', {})
        correlation_summary = correlation_results.get('summary', {})
        loan_summary = loan_results.get('summary', {})
        income_summary = income_results.get('summary', {})
        ml_summary = ml_results.get('summary', {})
        
        logger.info(f'✓ 核查对象: {len(all_persons)} 人, {len(all_companies)} 家公司')
        logger.info(f'✓ 原始文件: {len(categorized_files["transaction_files"])} 个')
        logger.info(f'✓ 清洗后交易: {total_transactions} 笔')
        logger.info(f'✓ 发现疑点: {total_suspicions} 个')
        logger.info(f'  - 直接资金往来: {len(suspicions["direct_transfers"])} 笔')
        logger.info(f'  - 现金时空伴随: {len(suspicions["cash_collisions"])} 对')
        logger.info(f'  - 隐形资产: {sum(len(v) for v in suspicions["hidden_assets"].values())} 笔')
        logger.info(f'  - 固定频率异常: {sum(len(v) for v in suspicions["fixed_frequency"].values())} 个')
        logger.info(f'  - 现金时间点配对: {len(suspicions.get("cash_timing_patterns", []))} 对')
        logger.info(f'  - 节假日/特殊时段: {sum(len(v) for v in suspicions.get("holiday_transactions", {}).values())} 笔')
        logger.info(f'  - 金额模式异常: {sum(len(v) for v in suspicions.get("amount_patterns", {}).values())} 个')
        logger.info(f'✓ 关联方分析:')
        logger.info(f'  - 直接往来: {related_summary.get("直接往来笔数", 0)} 笔')
        logger.info(f'  - 第三方中转: {related_summary.get("第三方中转链数", 0)} 条链路')
        logger.info(f'  - 资金闭环: {related_summary.get("资金闭环数", 0)} 个')
        logger.info(f'✓ 多源碰撞: {correlation_summary.get("资金碰撞总数", 0)} 条')
        logger.info(f'✓ 借贷分析:')
        logger.info(f'  - 双向往来: {loan_summary.get("双向往来关系数", 0)} 个')
        logger.info(f'  - 网贷平台: {loan_summary.get("网贷平台交易数", 0)} 笔')
        logger.info(f'  - 规律还款: {loan_summary.get("规律还款模式数", 0)} 个')
        logger.info(f'✓ 异常收入:')
        logger.info(f'  - 规律非工资: {income_summary.get("规律性非工资收入", 0)} 个')
        logger.info(f'  - 个人大额转入: {income_summary.get("个人大额转入", 0)} 笔')
        logger.info(f'  - 来源不明: {income_summary.get("来源不明收入", 0)} 笔')
        logger.info(f'✓ ML预测: {ml_summary.get("anomaly_count", 0)} 个高风险异常')
        logger.info(f'✓ 执行时间: {total_time:.2f}秒')
        logger.info('')
        logger.info(f'✓ 输出目录: {output_directory}')
        logger.info(f'  ├─ cleaned_data/个人/ - {len(persons)} 个合并流水文件')
        logger.info(f'  ├─ cleaned_data/公司/ - {len(companies)} 个合并流水文件')
        logger.info(f'  ├─ cleaned_data/cleaning_log.xlsx - 清洗日志')
        logger.info(f'  ├─ analysis_results/{config.OUTPUT_EXCEL_FILE}')
        logger.info(f'  ├─ analysis_results/核查结果分析报告.txt')
        logger.info(f'  ├─ analysis_results/关联方资金分析报告.txt')
        logger.info(f'  ├─ analysis_results/多源数据碰撞分析报告.txt')
        logger.info(f'  ├─ analysis_results/借贷行为分析报告.txt')
        logger.info(f'  ├─ analysis_results/异常收入来源分析报告.txt')
        logger.info(f'  ├─ analysis_results/机器学习风险预测报告.txt')
        logger.info(f'  ├─ analysis_results/资金流向图.md')
        logger.info(f'  └─ analysis_results/资金流向可视化.html')
        logger.info('')
        
        logger.info('=' * 80)
        logger.info('系统执行完成!')
        logger.info('=' * 80)
        
    except Exception as e:
        logger.error(f'系统执行失败: {str(e)}', exc_info=True)
        raise


if __name__ == '__main__':
    # 从命令行参数获取目录
    data_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else './output'
    
    main(data_dir, output_dir)
