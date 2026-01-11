#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程序 - 资金穿透与关联排查系统(优化版)
完整的端到端执行流程,支持数据清洗和中间数据生成

重构说明 (2026-01-09):
- 将超长main()函数拆分为多个阶段处理函数
- 提高代码可读性和可维护性
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple

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


def phase0_scan_files(data_directory: str) -> Tuple[Dict, List[str], List[str]]:
    """阶段0: 文件扫描与分类"""
    logger.info('【阶段0】文件扫描与分类')
    logger.info('-' * 80)
    
    categorized_files = file_categorizer.categorize_files(data_directory)
    
    persons = list(categorized_files['persons'].keys())
    companies = list(categorized_files['companies'].keys())
    
    if not persons and not companies:
        raise ValueError('未找到任何人员或公司的流水文件')
    
    logger.info(f'✓ 识别核心人员: {len(persons)} 人 - {persons}')
    logger.info(f'✓ 识别涉案公司: {len(companies)} 家 - {companies}')
    logger.info('')
    
    return categorized_files, persons, companies


def phase1_clean_data(categorized_files: Dict, persons: List[str], companies: List[str], 
                       output_dirs: Dict) -> Dict:
    """阶段1: 数据清洗与合并"""
    logger.info('【阶段1】数据清洗与合并 - 强制重新清洗')
    logger.info('-' * 80)
    
    cleaned_data = {}
    
    # 清洗个人数据
    for person_name in persons:
        file_path = os.path.join(output_dirs['cleaned_persons'], f'{person_name}_合并流水.xlsx')
        person_files = categorized_files['persons'].get(person_name, [])
        
        if person_files:
            logger.info(f'清洗个人数据: {person_name}（{len(person_files)}个文件）')
            try:
                df_merged, stats = data_cleaner.clean_and_merge_files(person_files, person_name)
                if not df_merged.empty:
                    data_cleaner.save_formatted_excel(df_merged, file_path)
                    _fill_na_columns(df_merged)
                    cleaned_data[person_name] = df_merged
                    logger.info(f'  {person_name}: {len(df_merged)} 条记录')
            except Exception as e:
                logger.error(f'清洗失败 {person_name}: {e}')
        else:
            logger.warning(f'未找到个人原始文件: {person_name}')

    # 清洗公司数据
    for company_name in companies:
        file_path = os.path.join(output_dirs['cleaned_companies'], f'{company_name}_合并流水.xlsx')
        company_files = categorized_files['companies'].get(company_name, [])
        
        if company_files:
            logger.info(f'清洗公司数据: {company_name}（{len(company_files)}个文件）')
            try:
                df_merged, stats = data_cleaner.clean_and_merge_files(company_files, company_name)
                if not df_merged.empty:
                    data_cleaner.save_formatted_excel(df_merged, file_path)
                    _fill_na_columns(df_merged)
                    cleaned_data[company_name] = df_merged
                    logger.info(f'  {company_name}: {len(df_merged)} 条记录')
            except Exception as e:
                logger.error(f'清洗公司数据失败 {company_name}: {e}')
        else:
            logger.warning(f'未找到公司原始文件: {company_name}')
    
    logger.info(f'已加载 {len(cleaned_data)} 个实体的清洗数据')
    logger.info('')
    
    return cleaned_data


def _fill_na_columns(df):
    """填充DataFrame中的空值"""
    if 'income' in df.columns: df['income'] = df['income'].fillna(0)
    if 'expense' in df.columns: df['expense'] = df['expense'].fillna(0)
    if 'counterparty' in df.columns: df['counterparty'] = df['counterparty'].fillna('').astype(str)
    if 'description' in df.columns: df['description'] = df['description'].fillna('').astype(str)


def phase2_extract_clues(data_directory: str, persons: List[str], companies: List[str]) -> Tuple[List[str], List[str]]:
    """阶段2: 线索提取"""
    logger.info('【阶段2】线索提取')
    logger.info('-' * 80)
    
    clue_persons, clue_companies = data_extractor.extract_all_clues(data_directory)
    
    all_persons = list(set(persons + clue_persons))
    all_companies = list(set(companies + clue_companies))
    
    logger.info(f'✓ 最终核心人员: {len(all_persons)} 人 - {all_persons}')
    logger.info(f'✓ 最终涉案公司: {len(all_companies)} 家 - {all_companies}')
    logger.info('')
    
    return all_persons, all_companies


def phase2_5_family_analysis(all_persons: List[str], data_directory: str) -> Tuple[Dict, Dict]:
    """阶段2.5: 家族关系识别"""
    logger.info('【阶段2.5】家族关系识别')
    logger.info('-' * 80)
    
    family_tree = family_analyzer.build_family_tree(all_persons, data_directory)
    family_summary = family_analyzer.get_family_summary(family_tree)
    
    total_family_members = sum(len(members) for members in family_tree.values())
    logger.info(f'✓ 识别家族成员: {total_family_members} 人')
    logger.info('')
    
    return family_tree, family_summary


def phase3_profile_analysis(cleaned_data: Dict, all_persons: List[str]) -> Dict:
    """阶段3: 资金画像分析（含理财账户深度分析）"""
    logger.info('【阶段3】资金画像分析')
    logger.info('-' * 80)
    
    import account_analyzer
    
    # 尝试导入理财账户分析模块
    try:
        import wealth_account_analyzer
        has_wealth_analyzer = True
    except ImportError:
        has_wealth_analyzer = False
        logger.warning('wealth_account_analyzer模块未找到，跳过理财账户深度分析')
    
    profiles = {}
    wealth_reports = []  # 收集理财账户报告
    
    for entity_name, df in cleaned_data.items():
        profiles[entity_name] = financial_profiler.generate_profile_report(df, entity_name)
        
        if any(p in entity_name for p in all_persons):
            try:
                # 原有账户分析
                account_report = account_analyzer.generate_account_report(df, entity_name)
                profiles[entity_name]['account_analysis_text'] = account_report
                
                # 新增：理财账户深度分析
                if has_wealth_analyzer:
                    wealth_result = wealth_account_analyzer.analyze_wealth_accounts(df, entity_name)
                    profiles[entity_name]['wealth_account_analysis'] = wealth_result['flow_result']
                    profiles[entity_name]['wealth_account_report'] = wealth_result['report']
                    wealth_reports.append((entity_name, wealth_result['report']))
                    
                    # 记录关键统计
                    ws = wealth_result['flow_result']['wealth_summary']
                    logger.info(f'  {entity_name}: 主账户{len(wealth_result["flow_result"]["primary_accounts"])}个, '
                              f'理财账户{ws["account_count"]}个, '
                              f'理财资金流转{ws["total_wealth_in"]/10000:.0f}万')
                
            except Exception as e:
                logger.error(f'账户分析失败 {entity_name}: {e}')
    
    # 保存理财账户分析报告
    if wealth_reports:
        try:
            report_path = os.path.join(config.OUTPUT_DIR, 'analysis_results', '理财账户分析报告.txt')
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('=' * 80 + '\n')
                f.write('银行理财账户深度分析报告\n')
                f.write(f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
                f.write('=' * 80 + '\n')
                for name, report in wealth_reports:
                    f.write(report)
                    f.write('\n\n')
            logger.info(f'✓ 理财账户分析报告已保存: {report_path}')
        except Exception as e:
            logger.error(f'保存理财账户报告失败: {e}')
    
    logger.info(f'✓ 已生成 {len(profiles)} 份资金画像与账户分析')
    logger.info('')
    
    return profiles


def phase4_suspicion_detection(cleaned_data: Dict, all_persons: List[str], all_companies: List[str]) -> Dict:
    """阶段4: 疑点碰撞检测"""
    logger.info('【阶段4】疑点碰撞检测')
    logger.info('-' * 80)
    
    suspicions = suspicion_detector.run_all_detections(
        cleaned_data, all_persons, all_companies
    )
    
    logger.info('')
    return suspicions


def phase5_asset_analysis(data_directory: str, all_persons: List[str], family_tree: Dict) -> Tuple[List, List, Dict]:
    """阶段5: 资产提取与分析"""
    logger.info('【阶段5】资产提取与分析')
    logger.info('-' * 80)
    
    properties = asset_analyzer.extract_properties(data_directory, all_persons)
    vehicles = asset_analyzer.extract_vehicles(data_directory, all_persons)
    family_assets = asset_analyzer.calculate_family_assets(properties, vehicles, family_tree)
    
    logger.info(f'✓ 提取资产: {len(properties)} 套房产, {len(vehicles)} 辆车')
    logger.info('')
    
    return properties, vehicles, family_assets


def phase5_5_validation(cleaned_data: Dict, properties: List, output_dirs: Dict) -> Tuple[Dict, List]:
    """阶段5.5: 数据验证"""
    logger.info('【阶段5.5】数据验证')
    logger.info('-' * 80)
    
    transaction_validations = {}
    for entity, df in cleaned_data.items():
        validation_result = data_validator.validate_transaction_data(df, entity)
        transaction_validations[entity] = validation_result
        logger.info(f'{entity}: {validation_result["status"]}')
    
    property_validations = data_validator.cross_validate_property_transactions(properties, cleaned_data)
    
    validation_report = data_validator.generate_validation_report(
        transaction_validations, property_validations
    )
    
    validation_report_path = os.path.join(output_dirs['analysis_results'], '数据验证报告.txt')
    with open(validation_report_path, 'w', encoding='utf-8') as f:
        f.write(validation_report)
    logger.info(f'✓ 数据验证报告已生成: {validation_report_path}')
    logger.info('')
    
    return transaction_validations, property_validations


def phase5_6_penetration(cleaned_data: Dict, all_persons: List[str], all_companies: List[str], 
                          output_dirs: Dict) -> Dict:
    """阶段5.6: 资金穿透分析"""
    logger.info('【阶段5.6】资金穿透分析')
    logger.info('-' * 80)
    
    personal_data = {name: df for name, df in cleaned_data.items() if name in all_persons}
    company_data = {name: df for name, df in cleaned_data.items() if name in all_companies}
    
    penetration_results = fund_penetration.analyze_fund_penetration(
        personal_data, company_data, all_persons, all_companies
    )
    
    penetration_report_path = fund_penetration.generate_penetration_report(
        penetration_results, output_dirs['analysis_results']
    )
    logger.info(f'✓ 资金穿透报告已生成: {penetration_report_path}')
    logger.info('')
    
    return penetration_results


def phase5_7_related_party(cleaned_data: Dict, all_persons: List[str], output_dirs: Dict) -> Dict:
    """阶段5.7: 关联方资金分析"""
    logger.info('【阶段5.7】关联方资金穿透分析')
    logger.info('-' * 80)
    
    related_party_results = related_party_analyzer.analyze_related_party_flows(
        cleaned_data, all_persons
    )
    
    related_party_report_path = related_party_analyzer.generate_related_party_report(
        related_party_results, output_dirs['analysis_results']
    )
    logger.info(f'✓ 关联方分析报告已生成: {related_party_report_path}')
    logger.info('')
    
    return related_party_results


def phase5_8_correlation(data_directory: str, cleaned_data: Dict, all_persons: List[str], 
                          output_dirs: Dict) -> Dict:
    """阶段5.8: 多源数据碰撞"""
    logger.info('【阶段5.8】多源数据交叉碰撞分析')
    logger.info('-' * 80)
    
    correlation_results = multi_source_correlator.run_all_correlations(
        data_directory, cleaned_data, all_persons
    )
    
    correlation_report_path = multi_source_correlator.generate_correlation_report(
        correlation_results, output_dirs['analysis_results']
    )
    logger.info(f'✓ 多源碰撞报告已生成: {correlation_report_path}')
    logger.info('')
    
    return correlation_results


def phase5_9_loan_analysis(cleaned_data: Dict, all_persons: List[str], output_dirs: Dict) -> Dict:
    """阶段5.9: 借贷行为分析"""
    logger.info('【阶段5.9】借贷行为分析')
    logger.info('-' * 80)
    
    loan_results = loan_analyzer.analyze_loan_behaviors(cleaned_data, all_persons)
    
    loan_report_path = loan_analyzer.generate_loan_report(
        loan_results, output_dirs['analysis_results']
    )
    logger.info(f'✓ 借贷分析报告已生成: {loan_report_path}')
    logger.info('')
    
    return loan_results


def phase5_10_income_analysis(cleaned_data: Dict, all_persons: List[str], output_dirs: Dict) -> Dict:
    """阶段5.10: 异常收入检测"""
    logger.info('【阶段5.10】异常收入来源检测')
    logger.info('-' * 80)
    
    income_results = income_analyzer.detect_suspicious_income(cleaned_data, all_persons)
    
    income_report_path = income_analyzer.generate_suspicious_income_report(
        income_results, output_dirs['analysis_results']
    )
    logger.info(f'✓ 异常收入报告已生成: {income_report_path}')
    logger.info('')
    
    return income_results


def phase5_11_visualization(cleaned_data: Dict, all_persons: List[str], 
                             loan_results: Dict, income_results: Dict, output_dirs: Dict) -> Dict:
    """阶段5.11: 资金流向可视化"""
    logger.info('【阶段5.11】资金流向可视化')
    logger.info('-' * 80)
    
    viz_results = flow_visualizer.generate_flow_visualizations(
        cleaned_data, all_persons, loan_results, income_results, output_dirs['analysis_results']
    )
    
    logger.info(f'✓ Mermaid资金流向图已生成: {viz_results.get("mermaid", "")}')
    logger.info(f'✓ HTML交互式图表已生成: {viz_results.get("html", "")}')
    logger.info('')
    
    return viz_results


def phase5_12_ml_analysis(cleaned_data: Dict, all_persons: List[str], 
                           all_companies: List[str], output_dirs: Dict) -> Dict:
    """阶段5.12: 机器学习风险预测"""
    logger.info('【阶段5.12】机器学习风险预测')
    logger.info('-' * 80)
    
    ml_results = ml_analyzer.run_ml_analysis(cleaned_data, all_persons, all_companies)
    
    ml_report_path = ml_analyzer.generate_ml_report(ml_results, output_dirs['analysis_results'])
    logger.info(f'✓ 机器学习预测报告已生成: {ml_report_path}')
    logger.info('')
    
    return ml_results


def phase5_13_time_series_analysis(cleaned_data: Dict, all_persons: List[str], 
                                    output_dirs: Dict) -> Dict:
    """阶段5.13: 时间序列分析（新增）"""
    logger.info('【阶段5.13】时间序列分析')
    logger.info('-' * 80)
    
    ts_results = time_series_analyzer.analyze_time_series(cleaned_data, all_persons)
    
    ts_report_path = time_series_analyzer.generate_time_series_report(
        ts_results, output_dirs['analysis_results']
    )
    logger.info(f'✓ 时序分析报告已生成: {ts_report_path}')
    logger.info('')
    
    return ts_results


def phase5_14_clue_aggregation(all_persons: List[str], all_companies: List[str],
                                penetration_results: Dict, ml_results: Dict,
                                ts_results: Dict, related_party_results: Dict,
                                loan_results: Dict, output_dirs: Dict):
    """阶段5.14: 线索聚合（新增）"""
    logger.info('【阶段5.14】线索聚合')
    logger.info('-' * 80)
    
    aggregator = clue_aggregator.aggregate_all_results(
        core_persons=all_persons,
        companies=all_companies,
        penetration_results=penetration_results,
        ml_results=ml_results,
        ts_results=ts_results,
        related_party_results=related_party_results,
        loan_results=loan_results
    )
    
    agg_report_path = clue_aggregator.generate_aggregation_report(
        aggregator, output_dirs['analysis_results']
    )
    logger.info(f'✓ 线索聚合报告已生成: {agg_report_path}')
    
    # 输出高风险实体摘要
    ranked = aggregator.get_ranked_entities()
    critical = [e for e in ranked if e['risk_level'] == 'critical']
    high = [e for e in ranked if e['risk_level'] == 'high']
    
    logger.info(f'✓ 极高风险实体: {len(critical)} 个')
    logger.info(f'✓ 高风险实体: {len(high)} 个')
    logger.info('')
    
    return aggregator


def phase6_generate_reports(profiles: Dict, suspicions: Dict, all_persons: List[str], 
                             all_companies: List[str], family_tree: Dict, family_summary: Dict,
                             family_assets: Dict, transaction_validations: Dict,
                             property_validations: List, penetration_results: Dict,
                             cleaned_data: Dict, output_dirs: Dict):
    """阶段6: 生成分析报告"""
    logger.info('【阶段6】生成分析报告')
    logger.info('-' * 80)
    
    # 生成Excel底稿
    excel_path = report_generator.generate_excel_workbook(
        profiles, suspicions,
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
    
    # 生成公文报告
    report_path = report_generator.generate_official_report(
        profiles, suspicions, all_persons, all_companies,
        os.path.join(output_dirs['analysis_results'], 
                    config.OUTPUT_REPORT_FILE.replace('.docx', '.txt')),
        family_summary=family_summary,
        family_assets=family_assets,
        cleaned_data=cleaned_data
    )
    logger.info(f'✓ 公文报告已生成: {report_path}')
    logger.info('')


def print_execution_summary(categorized_files: Dict, cleaned_data: Dict, suspicions: Dict,
                            related_party_results: Dict, correlation_results: Dict,
                            loan_results: Dict, income_results: Dict, ml_results: Dict,
                            all_persons: List[str], all_companies: List[str],
                            output_directory: str, total_time: float):
    """打印执行摘要"""
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
    logger.info(f'  ├─ cleaned_data/个人/ - 合并流水文件')
    logger.info(f'  ├─ cleaned_data/公司/ - 合并流水文件')
    logger.info(f'  ├─ analysis_results/{config.OUTPUT_EXCEL_FILE}')
    logger.info(f'  ├─ analysis_results/核查结果分析报告.txt')
    logger.info(f'  ├─ analysis_results/关联方资金分析报告.txt')
    logger.info(f'  ├─ analysis_results/多源数据碰撞分析报告.txt')
    logger.info(f'  ├─ analysis_results/借贷行为分析报告.txt')
    logger.info(f'  ├─ analysis_results/异常收入来源分析报告.txt')
    logger.info(f'  ├─ analysis_results/机器学习风险预测报告.txt')
    logger.info(f'  ├─ analysis_results/时序分析报告.txt')
    logger.info(f'  ├─ analysis_results/线索聚合报告.txt')
    logger.info(f'  ├─ analysis_results/资金流向图.md')
    logger.info(f'  └─ analysis_results/资金流向可视化.html')
    logger.info('')


def main(data_directory: str = '.', output_directory: str = './output'):
    """
    主执行流程(重构版)
    
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
        
        # 阶段0: 文件扫描
        categorized_files, persons, companies = phase0_scan_files(data_directory)
        
        # 阶段1: 数据清洗
        cleaned_data = phase1_clean_data(categorized_files, persons, companies, output_dirs)
        
        # 阶段2: 线索提取
        all_persons, all_companies = phase2_extract_clues(data_directory, persons, companies)
        
        # 阶段2.5: 家族关系
        family_tree, family_summary = phase2_5_family_analysis(all_persons, data_directory)
        
        # 阶段3: 资金画像
        profiles = phase3_profile_analysis(cleaned_data, all_persons)
        
        # 阶段4: 疑点检测
        suspicions = phase4_suspicion_detection(cleaned_data, all_persons, all_companies)
        
        # 阶段5: 资产分析
        properties, vehicles, family_assets = phase5_asset_analysis(
            data_directory, all_persons, family_tree
        )
        
        # 阶段5.5: 数据验证
        transaction_validations, property_validations = phase5_5_validation(
            cleaned_data, properties, output_dirs
        )
        
        # 阶段5.6: 资金穿透
        penetration_results = phase5_6_penetration(
            cleaned_data, all_persons, all_companies, output_dirs
        )
        
        # 阶段5.7: 关联方分析
        related_party_results = phase5_7_related_party(cleaned_data, all_persons, output_dirs)
        
        # 阶段5.8: 多源碰撞
        correlation_results = phase5_8_correlation(
            data_directory, cleaned_data, all_persons, output_dirs
        )
        
        # 阶段5.9: 借贷分析
        loan_results = phase5_9_loan_analysis(cleaned_data, all_persons, output_dirs)
        
        # 阶段5.10: 异常收入
        income_results = phase5_10_income_analysis(cleaned_data, all_persons, output_dirs)
        
        # 阶段5.11: 可视化
        viz_results = phase5_11_visualization(
            cleaned_data, all_persons, loan_results, income_results, output_dirs
        )
        
        # 阶段5.12: ML分析
        ml_results = phase5_12_ml_analysis(
            cleaned_data, all_persons, all_companies, output_dirs
        )
        
        # 阶段5.13: 时序分析（新增）
        ts_results = phase5_13_time_series_analysis(
            cleaned_data, all_persons, output_dirs
        )
        
        # 阶段5.14: 线索聚合（新增）
        aggregator = phase5_14_clue_aggregation(
            all_persons, all_companies,
            penetration_results, ml_results, ts_results,
            related_party_results, loan_results, output_dirs
        )
        
        # 阶段6: 报告生成
        phase6_generate_reports(
            profiles, suspicions, all_persons, all_companies,
            family_tree, family_summary, family_assets,
            transaction_validations, property_validations,
            penetration_results, cleaned_data, output_dirs
        )
        
        # 执行摘要
        total_time = (datetime.now() - overall_start).total_seconds()
        print_execution_summary(
            categorized_files, cleaned_data, suspicions,
            related_party_results, correlation_results,
            loan_results, income_results, ml_results,
            all_persons, all_companies, output_directory, total_time
        )
        
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
