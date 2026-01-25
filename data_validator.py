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
    
    # 【增强】检查余额连续性和一致性
    balance_issues = []
    missing_balance_count = 0
    balance_error_count = 0
    
    if 'balance' in df.columns and len(df) > 1:
        df_sorted = df.sort_values('date').reset_index(drop=True)
        
        # 统计缺失余额的交易
        missing_balance_indices = df_sorted[df_sorted['balance'].isna()].index.tolist()
        missing_balance_count = len(missing_balance_indices)
        
        if missing_balance_count > 0:
            missing_ratio = missing_balance_count / len(df_sorted)
            warnings.append(f'有{missing_balance_count}笔交易缺失余额信息({missing_ratio*100:.1f}%)')
        
        # 检查余额连续性（仅对有余额的交易）
        balances = df_sorted['balance'].dropna()
        if len(balances) > 1:
            # 检查是否有突变（单笔变动超过100万但无对应收支）
            balance_diffs = balances.diff().abs()
            large_jumps = balance_diffs[balance_diffs > 1000000]
            if len(large_jumps) > 0:
                warnings.append(f'余额存在{len(large_jumps)}次大幅跳变(>100万)，可能数据不完整')
            
            # 逐笔验证余额一致性
            prev_balance = None
            prev_idx = None
            
            for idx in df_sorted.index:
                row = df_sorted.loc[idx]
                if pd.isna(row['balance']):
                    continue
                
                if prev_balance is not None and prev_idx is not None:
                    # 计算预期余额
                    amount = 0
                    if 'amount' in df.columns:
                        amount = row['amount']
                    elif 'income' in df.columns and 'expense' in df.columns:
                        amount = row.get('income', 0) - row.get('expense', 0)
                    
                    expected_balance = prev_balance + amount
                    
                    # 允许1分钱的误差
                    if abs(row['balance'] - expected_balance) > 0.01:
                        balance_error_count += 1
                        # 只记录前10个错误，避免警告过多
                        if balance_error_count <= 10:
                            balance_issues.append({
                                'index': idx,
                                'date': row['date'],
                                'expected': expected_balance,
                                'actual': row['balance'],
                                'diff': row['balance'] - expected_balance,
                                'amount': amount
                            })
                
                prev_balance = row['balance']
                prev_idx = idx
            
            if balance_error_count > 0:
                total_balance_records = len(balances)
                error_ratio = balance_error_count / total_balance_records if total_balance_records > 0 else 0
                warnings.append(f'发现{balance_error_count}笔余额不一致({error_ratio*100:.1f}%)，可能原因：跨账户转账、理财申赎或数据缺失')
    
    # 【增强】检查收支平衡（考虑余额缺失情况）
    if 'income' in df.columns and 'expense' in df.columns:
        total_income = df['income'].sum()
        total_expense = df['expense'].sum()
        
        if 'balance' in df.columns and len(df) > 0:
            df_sorted = df.sort_values('date')
            balance_series = df_sorted['balance'].dropna()
            
            if not balance_series.empty:
                first_balance = balance_series.iloc[0]
                last_balance = balance_series.iloc[-1]
                expected_change = total_income - total_expense
                actual_change = last_balance - first_balance
                
                # 计算差异比例
                if abs(expected_change) > 1000:  # 只有收支差超过1000元才检查
                    diff = abs(expected_change - actual_change)
                    diff_ratio = diff / abs(expected_change) if expected_change != 0 else 0
                    
                    # 差异超过1万或差异比例超过10%
                    if diff > 10000 or diff_ratio > 0.1:
                        warning_msg = f'收支与余额变动不一致: 收支差{expected_change/10000:.2f}万, 余额变动{actual_change/10000:.2f}万, 差异{diff/10000:.2f}万'
                        
                        # 添加可能原因
                        reasons = []
                        if missing_balance_count > 0:
                            reasons.append(f'{missing_balance_count}笔交易缺失余额')
                        if balance_error_count > 0:
                            reasons.append(f'{balance_error_count}笔余额不一致')
                        
                        if reasons:
                            warning_msg += f' (可能原因: {", ".join(reasons)})'
                        
                        warnings.append(warning_msg)
    
    # 【修复】计算数据质量评分
    logger.info(f'=== 数据质量评分诊断 [{entity_name}] ===')
    logger.info(f'记录数: {len(df)}')
    
    quality_score = 100
    logger.info(f'初始分数: {quality_score}')
    
    # 扣分项1：问题（严重问题）
    issue_deduction = len(issues) * 20
    quality_score -= issue_deduction
    logger.info(f'问题扣分: {len(issues)}个 × 20分 = -{issue_deduction}分')
    for i, issue in enumerate(issues, 1):
        logger.info(f'  问题{i}: {issue}')
    
    # 扣分项2：警告（考虑数据量因素）
    # 计算警告密度，根据数据量调整扣分权重
    if len(df) > 0:
        warning_ratio = len(warnings) / len(df)
        logger.info(f'警告密度: {len(warnings)}个警告 / {len(df)}条记录 = {warning_ratio*100:.2f}%')
        
        # 根据警告密度调整扣分权重
        # 低密度（<1%）：每个警告扣2分
        # 中密度（1-5%）：每个警告扣5分
        # 高密度（>5%）：每个警告扣10分
        if warning_ratio < 0.01:
            warning_penalty = 2
        elif warning_ratio < 0.05:
            warning_penalty = 5
        else:
            warning_penalty = 10
        
        warning_deduction = len(warnings) * warning_penalty
        quality_score -= warning_deduction
        logger.info(f'警告扣分: {len(warnings)}个 × {warning_penalty}分（密度{warning_ratio*100:.2f}%）= -{warning_deduction}分')
    else:
        # 空数据集，每个警告扣5分
        warning_deduction = len(warnings) * 5
        quality_score -= warning_deduction
        logger.info(f'警告扣分: {len(warnings)}个 × 5分（空数据集）= -{warning_deduction}分')
    
    for i, warning in enumerate(warnings, 1):
        logger.info(f'  警告{i}: {warning}')
    
    # 扣分项3：高空值字段（修复重复扣分问题）
    # 只对不在警告中的高空值字段扣分
    null_warnings = [w for w in warnings if '空值比例' in w]
    # 提取警告中已包含的字段名
    warned_fields = set()
    for w in null_warnings:
        # 从警告中提取字段名，格式如："以下字段空值比例超过50%: field1, field2"
        if '以下字段空值比例超过50%:' in w:
            fields_str = w.split('以下字段空值比例超过50%:')[-1].strip()
            warned_fields.update([f.strip() for f in fields_str.split(',')])
    
    # 只对未在警告中扣分的字段进行额外扣分
    extra_null_fields = [f for f in high_null_fields if f not in warned_fields]
    null_field_deduction = len(extra_null_fields) * 10
    quality_score -= null_field_deduction
    logger.info(f'高空值字段额外扣分: {len(extra_null_fields)}个 × 10分 = -{null_field_deduction}分')
    for field in extra_null_fields:
        logger.info(f'  额外扣分字段: {field}')
    
    # 扣分项4：余额一致性问题（新增）
    if balance_error_count > 0:
        balance_deduction = min(balance_error_count * 2, 20)  # 最多扣20分
        quality_score -= balance_deduction
        logger.info(f'余额不一致扣分: {balance_error_count}笔 × 2分（上限20分）= -{balance_deduction}分')
    
    # 扣分项5：余额缺失问题（新增）
    if missing_balance_count > 0:
        missing_ratio = missing_balance_count / len(df) if len(df) > 0 else 0
        if missing_ratio > 0.5:  # 超过50%缺失
            missing_deduction = 15
        elif missing_ratio > 0.2:  # 超过20%缺失
            missing_deduction = 8
        else:
            missing_deduction = 3
        quality_score -= missing_deduction
        logger.info(f'余额缺失扣分: {missing_ratio*100:.1f}%缺失 = -{missing_deduction}分')
    
    quality_score = max(0, min(100, quality_score))
    logger.info(f'最终分数: {quality_score}')
    logger.info(f'=== 评分诊断结束 ===')
    
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
        'null_fields': high_null_fields,
        'quality_score': quality_score,  # 新增
        'data_quality_label': '优' if quality_score >= 90 else '良' if quality_score >= 70 else '中' if quality_score >= 50 else '差'  # 新增
    }


def cross_validate_property_transactions(
    properties: List[Dict],
    transactions_dict: Dict[str, pd.DataFrame]
) -> List[Dict]:
    """
    交叉验证房产购置与银行流水（性能优化版）
    
    支持：
    - 扩大时间窗口（默认12个月）
    - 累计金额匹配（多笔交易合计接近房产金额）
    - 使用日期索引加速查询
    - 向量化操作优化性能
    
    Args:
        properties: 房产列表
        transactions_dict: 银行流水字典 {实体名: DataFrame}
    
    Returns:
        验证结果列表
    """
    import config
    
    logger.info('=' * 60)
    logger.info('开始交叉验证房产购置与银行流水（性能优化版）')
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
    
    # 【性能优化】预处理：为每个 DataFrame 建立日期索引
    indexed_transactions = {}
    for owner, df in transactions_dict.items():
        if df.empty or 'date' not in df.columns:
            indexed_transactions[owner] = None
            continue
        
        try:
            # 复制 DataFrame 避免修改原始数据
            df_copy = df.copy()
            # 转换日期列
            df_copy['date'] = pd.to_datetime(df_copy['date'])
            # 设置日期索引（加速查询）
            df_copy = df_copy.set_index('date').sort_index()
            indexed_transactions[owner] = df_copy
        except Exception as e:
            logger.warning(f'预处理 {owner} 的交易数据失败: {e}')
            indexed_transactions[owner] = None
    
    logger.info(f'预处理完成，已为 {len([v for v in indexed_transactions.values() if v is not None])} 个实体建立日期索引')
    
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
        
        df_indexed = indexed_transactions.get(owner)
        
        if df_indexed is None:
            validation_results.append({
                '产权人': owner,
                '房产地址': address,
                '交易金额': amount,
                '登记时间': register_date,
                '验证状态': '流水数据为空或预处理失败',
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
                
                # 【性能优化】使用日期索引进行快速范围查询
                period_df = df_indexed.loc[start_date:end_date].reset_index()
                
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
                
                # 方法1：单笔匹配（向量化优化）
                tolerance = amount_yuan * single_tolerance
                if 'expense' in period_df.columns:
                    # 【性能优化】使用向量化操作
                    matched_mask = (period_df['expense'] >= amount_yuan - tolerance) & \
                                  (period_df['expense'] <= amount_yuan + tolerance)
                    matched = period_df[matched_mask]
                    
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
                
                # 方法2：累计匹配（多笔交易合计，性能优化）
                if enable_cumulative and amount_yuan > 0 and 'expense' in period_df.columns:
                    # 【性能优化】筛选大额支出（超过1万元）- 使用向量化操作
                    large_expenses_mask = period_df['expense'] >= config.VALIDATION_PROPERTY_EXPENSE_MIN
                    large_expenses = period_df[large_expenses_mask].copy()
                    
                    if not large_expenses.empty:
                        # 【性能优化】使用 cumsum() 计算累计金额，避免循环
                        large_expenses = large_expenses.sort_values('date')
                        large_expenses['cumulative'] = large_expenses['expense'].cumsum()
                        
                        # 【性能优化】检查累计金额是否在容差范围内
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
    property_validations: List[Dict],
    report_timestamp: str = None
) -> str:
    """
    生成数据验证报告
    
    Args:
        transaction_validations: 流水数据验证结果
        property_validations: 房产交易验证结果
        report_timestamp: 报告时间戳（可选，默认使用全局时间戳）
    
    Returns:
        报告文本
    """
    # 使用统一的时间戳
    if report_timestamp is None:
        report_timestamp = utils.get_global_report_timestamp()
    
    report_lines = []
    report_lines.append('数据验证报告')
    report_lines.append('=' * 60)
    report_lines.append(f'生成时间: {report_timestamp}')
    report_lines.append('')
    
    # 流水数据验证
    report_lines.append('一、银行流水数据验证')
    report_lines.append('-' * 60)
    
    for entity, result in transaction_validations.items():
        quality_label = result.get('data_quality_label', '未知')
        quality_score = result.get('quality_score', 0)
        report_lines.append(f'\n【{entity}】 数据质量: {quality_label} ({quality_score}分)')
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
    persons = ['甲某某', '乙某某', '丙某某', '丁某某']
    
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
