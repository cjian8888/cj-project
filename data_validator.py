#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据验证模块
验证银行流水数据完整性，交叉验证资产购置与交易记录
"""

import os
from typing import Dict, List
from datetime import datetime, timedelta
import pandas as pd

import config
import utils

logger = utils.setup_logger(__name__)


def validate_transaction_data(df: pd.DataFrame, entity_name: str) -> Dict:
    """
    验证银行流水数据的完整性和合理性
    
    Args:
        df: 银行流水DataFrame
        entity_name: 实体名称（人员或公司）
    
    Returns:
        验证结果字典
    """
    issues = []
    warnings = []
    
    # 检查必需字段（使用实际字段名）
    required_fields = ['date', 'description']
    for field in required_fields:
        if field not in df.columns:
            issues.append(f'缺少必需字段: {field}')
    
    if issues:
        return {
            'entity': entity_name,
            'status': 'FAILED',
            'issues': issues,
            'warnings': warnings,
            'record_count': len(df)
        }
    
    # 检查日期格式
    try:
        df['date'] = pd.to_datetime(df['date'])
    except Exception as e:
        issues.append(f'日期格式错误: {str(e)}')
    
    # 检查金额合理性
    if 'income' in df.columns:
        max_income = df['income'].max()
        if max_income > config.VALIDATION_MAX_SINGLE_AMOUNT:  # 单笔收入超过阈值
            warnings.append(f'存在异常大额收入: {max_income:.2f}元')
    
    if 'expense' in df.columns:
        max_expense = df['expense'].max()
        if max_expense > config.VALIDATION_MAX_SINGLE_AMOUNT:  # 单笔支出超过阈值
            warnings.append(f'存在异常大额支出: {max_expense:.2f}元')
    
    # 检查数据时间跨度
    date_range = 0
    if not df.empty and 'date' in df.columns:
        date_range = (df['date'].max() - df['date'].min()).days
        if date_range < 30:
            warnings.append(f'数据时间跨度较短: {date_range}天')
    
    # 检查空值比例
    null_ratio = df.isnull().sum() / len(df)
    high_null_fields = null_ratio[null_ratio > 0.5].index.tolist()
    if high_null_fields:
        warnings.append(f'以下字段空值比例超过50%: {", ".join(high_null_fields)}')
    
    status = 'PASSED' if not issues else 'FAILED'
    if warnings and status == 'PASSED':
        status = 'WARNING'
    
    return {
        'entity': entity_name,
        'status': status,
        'issues': issues,
        'warnings': warnings,
        'record_count': len(df),
        'date_range_days': date_range if not df.empty else 0,
        'null_fields': high_null_fields
    }


def cross_validate_property_transactions(
    properties: List[Dict],
    transactions_dict: Dict[str, pd.DataFrame]
) -> List[Dict]:
    """
    交叉验证房产购置与银行流水（优化版）
    
    支持：
    - 扩大时间窗口（默认12个月）
    - 累计金额匹配（多笔交易合计接近房产金额）
    
    Args:
        properties: 房产列表
        transactions_dict: 银行流水字典 {实体名: DataFrame}
    
    Returns:
        验证结果列表
    """
    import config
    
    logger.info('=' * 60)
    logger.info('开始交叉验证房产购置与银行流水')
    logger.info('=' * 60)
    
    # 获取配置
    match_config = getattr(config, 'PROPERTY_MATCH_CONFIG', {
        'time_window_months': 12,
        'cumulative_match': True,
        'cumulative_tolerance': 0.2,
        'single_match_tolerance': 0.1
    })
    
    time_window_days = match_config['time_window_months'] * 30
    single_tolerance = match_config.get('single_match_tolerance', 0.1)
    cumulative_tolerance = match_config.get('cumulative_tolerance', 0.2)
    enable_cumulative = match_config.get('cumulative_match', True)
    
    validation_results = []
    
    for prop in properties:
        owner = prop.get('产权人', '')
        address = prop.get('房地坐落', '')
        amount = prop.get('交易金额', 0)
        register_date = prop.get('登记时间', '')
        
        if owner not in transactions_dict:
            validation_results.append({
                '产权人': owner,
                '房产地址': address,
                '交易金额': amount,
                '登记时间': register_date,
                '验证状态': '未找到流水数据',
                '匹配交易': None
            })
            continue
        
        df = transactions_dict[owner]
        
        if df.empty or 'date' not in df.columns:
            validation_results.append({
                '产权人': owner,
                '房产地址': address,
                '交易金额': amount,
                '登记时间': register_date,
                '验证状态': '流水数据为空',
                '匹配交易': None
            })
            continue
        
        # 尝试匹配大额支出
        try:
            # 转换登记日期
            if register_date:
                register_dt = pd.to_datetime(register_date)
                
                # 扩大时间窗口到配置的月数
                start_date = register_dt - timedelta(days=time_window_days)
                end_date = register_dt + timedelta(days=time_window_days)
                
                df['date'] = pd.to_datetime(df['date'])
                period_df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
                
                if 'expense' not in period_df.columns:
                    validation_results.append({
                        '产权人': owner,
                        '房产地址': address,
                        '交易金额': amount,
                        '登记时间': register_date,
                        '验证状态': '流水无支出字段',
                        '匹配交易': None
                    })
                    continue
                
                amount_yuan = amount * config.UNIT_WAN  # 转换为元
                
                # 方法1：单笔匹配
                tolerance = amount_yuan * single_tolerance
                matched = period_df[
                    (period_df['expense'] >= amount_yuan - tolerance) &
                    (period_df['expense'] <= amount_yuan + tolerance)
                ]
                
                if not matched.empty:
                    match_info = matched.iloc[0]
                    validation_results.append({
                        '产权人': owner,
                        '房产地址': address,
                        '交易金额': amount,
                        '登记时间': register_date,
                        '验证状态': '找到匹配交易（单笔）',
                        '匹配交易': {
                            '日期': match_info['date'],
                            '金额': match_info['expense'],
                            '摘要': match_info.get('description', ''),
                            '对手方': match_info.get('counterparty', '')
                        }
                    })
                    logger.info(f'✓ {owner} 的房产 {address} 找到单笔匹配交易')
                    continue
                
                # 方法2：累计匹配（多笔交易合计）
                if enable_cumulative and amount_yuan > 0:
                    # 筛选大额支出（超过1万元）
                    large_expenses = period_df[period_df['expense'] >= config.VALIDATION_PROPERTY_EXPENSE_MIN].copy()
                    if not large_expenses.empty:
                        large_expenses = large_expenses.sort_values('date')
                        
                        # 计算累计金额
                        cumulative_sum = large_expenses['expense'].sum()
                        cumulative_tolerance_amount = amount_yuan * cumulative_tolerance
                        
                        if abs(cumulative_sum - amount_yuan) <= cumulative_tolerance_amount:
                            validation_results.append({
                                '产权人': owner,
                                '房产地址': address,
                                '交易金额': amount,
                                '登记时间': register_date,
                                '验证状态': '找到匹配交易（累计）',
                                '匹配交易': {
                                    '日期': f"{large_expenses['date'].min()} 至 {large_expenses['date'].max()}",
                                    '金额': cumulative_sum,
                                    '摘要': f'共{len(large_expenses)}笔大额支出累计',
                                    '对手方': ''
                                }
                            })
                            logger.info(f'✓ {owner} 的房产 {address} 找到累计匹配交易')
                            continue
                
                # 未找到匹配
                validation_results.append({
                    '产权人': owner,
                    '房产地址': address,
                    '交易金额': amount,
                    '登记时间': register_date,
                    '验证状态': '未找到匹配交易',
                    '匹配交易': None
                })
                logger.warning(f'✗ {owner} 的房产 {address} 未找到匹配交易')
            else:
                validation_results.append({
                    '产权人': owner,
                    '房产地址': address,
                    '交易金额': amount,
                    '登记时间': register_date,
                    '验证状态': '无登记日期',
                    '匹配交易': None
                })
        except Exception as e:
            logger.warning(f'验证 {owner} 的房产时出错: {str(e)}')
            validation_results.append({
                '产权人': owner,
                '房产地址': address,
                '交易金额': amount,
                '登记时间': register_date,
                '验证状态': f'验证出错: {str(e)}',
                '匹配交易': None
            })
    
    matched_count = sum(1 for r in validation_results if '找到匹配' in r['验证状态'])
    logger.info(f'\n房产交易验证完成: {matched_count}/{len(properties)} 找到匹配')
    
    return validation_results


def generate_validation_report(
    transaction_validations: Dict[str, Dict],
    property_validations: List[Dict]
) -> str:
    """
    生成数据验证报告
    
    Args:
        transaction_validations: 流水数据验证结果
        property_validations: 房产交易验证结果
    
    Returns:
        报告文本
    """
    report_lines = []
    report_lines.append('数据验证报告')
    report_lines.append('=' * 60)
    report_lines.append(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}')
    report_lines.append('')
    
    # 流水数据验证
    report_lines.append('一、银行流水数据验证')
    report_lines.append('-' * 60)
    
    for entity, result in transaction_validations.items():
        report_lines.append(f'\n【{entity}】')
        report_lines.append(f'  状态: {result["status"]}')
        report_lines.append(f'  记录数: {result["record_count"]}')
        report_lines.append(f'  时间跨度: {result.get("date_range_days", 0)}天')
        
        if result['issues']:
            report_lines.append('  问题:')
            for issue in result['issues']:
                report_lines.append(f'    - {issue}')
        
        if result['warnings']:
            report_lines.append('  警告:')
            for warning in result['warnings']:
                report_lines.append(f'    - {warning}')
    
    # 房产交易验证
    report_lines.append('\n\n二、房产交易交叉验证')
    report_lines.append('-' * 60)
    
    matched = [r for r in property_validations if r['验证状态'] == '找到匹配交易']
    unmatched = [r for r in property_validations if r['验证状态'] == '未找到匹配交易']
    other = [r for r in property_validations if r['验证状态'] not in ['找到匹配交易', '未找到匹配交易']]
    
    report_lines.append(f'\n总计: {len(property_validations)} 套房产')
    report_lines.append(f'  - 找到匹配交易: {len(matched)} 套')
    report_lines.append(f'  - 未找到匹配交易: {len(unmatched)} 套')
    report_lines.append(f'  - 其他情况: {len(other)} 套')
    
    if matched:
        report_lines.append('\n(一) 已匹配房产:')
        for r in matched:
            report_lines.append(f'\n  • {r["产权人"]} - {r["房产地址"]}')
            report_lines.append(f'    房产金额: {r["交易金额"]:.2f}万元')
            if r['匹配交易']:
                report_lines.append(f'    匹配交易: {r["匹配交易"]["日期"]} {r["匹配交易"]["金额"]:.2f}元')
                report_lines.append(f'    摘要: {r["匹配交易"]["摘要"]}')
    
    if unmatched:
        report_lines.append('\n(二) 未匹配房产（需人工核查）:')
        for r in unmatched:
            report_lines.append(f'\n  • {r["产权人"]} - {r["房产地址"]}')
            report_lines.append(f'    房产金额: {r["交易金额"]:.2f}万元')
            report_lines.append(f'    登记时间: {r["登记时间"]}')
    
    if other:
        report_lines.append('\n(三) 其他情况:')
        for r in other:
            report_lines.append(f'\n  • {r["产权人"]} - {r["房产地址"]}')
            report_lines.append(f'    状态: {r["验证状态"]}')
    
    report_lines.append('\n\n三、数据质量总结')
    report_lines.append('-' * 60)
    
    passed = sum(1 for r in transaction_validations.values() if r['status'] == 'PASSED')
    warning = sum(1 for r in transaction_validations.values() if r['status'] == 'WARNING')
    failed = sum(1 for r in transaction_validations.values() if r['status'] == 'FAILED')
    
    report_lines.append(f'\n流水数据质量:')
    report_lines.append(f'  - 通过: {passed} 个实体')
    report_lines.append(f'  - 警告: {warning} 个实体')
    report_lines.append(f'  - 失败: {failed} 个实体')
    
    match_rate = len(matched) / len(property_validations) * 100 if property_validations else 0
    report_lines.append(f'\n房产交易匹配率: {match_rate:.1f}%')
    
    report_lines.append('\n' + '=' * 60)
    
    return '\n'.join(report_lines)


if __name__ == '__main__':
    # 测试代码
    import sys
    
    data_dir = sys.argv[1] if len(sys.argv) > 1 else './data'
    
    # 读取清洗后的流水数据
    transactions_dict = {}
    persons = ['朱明', '朱永平', '陈斌', '马尚德']
    
    for person in persons:
        file_path = f'output/cleaned_data/个人/{person}_合并流水.xlsx'
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            transactions_dict[person] = df
    
    # 验证流水数据
    print('=' * 60)
    print('银行流水数据验证')
    print('=' * 60)
    
    transaction_validations = {}
    for entity, df in transactions_dict.items():
        result = validate_transaction_data(df, entity)
        transaction_validations[entity] = result
        print(f'\n{entity}: {result["status"]}')
        if result['issues']:
            print(f'  问题: {result["issues"]}')
        if result['warnings']:
            print(f'  警告: {result["warnings"]}')
    
    # 提取房产并验证
    import asset_analyzer
    properties = asset_analyzer.extract_properties(data_dir, persons)
    
    property_validations = cross_validate_property_transactions(
        properties, transactions_dict
    )
    
    # 生成报告
    report = generate_validation_report(transaction_validations, property_validations)
    print('\n' + report)
