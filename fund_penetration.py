#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金穿透分析模块
检测核心人员与涉案公司之间的直接/间接资金往来
"""

import os
import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime

import utils

logger = utils.setup_logger(__name__)


def analyze_fund_penetration(
    personal_data: Dict[str, pd.DataFrame],
    company_data: Dict[str, pd.DataFrame],
    core_persons: List[str],
    companies: List[str]
) -> Dict:
    """
    资金穿透分析：检测核心人员与涉案公司之间的资金往来
    
    Args:
        personal_data: 个人交易数据 {姓名: DataFrame}
        company_data: 公司交易数据 {公司名: DataFrame}
        core_persons: 核心人员列表
        companies: 涉案公司列表
        
    Returns:
        分析结果字典
    """
    logger.info('='*60)
    logger.info('开始资金穿透分析')
    logger.info('='*60)
    
    results = {
        'person_to_company': [],  # 个人→公司
        'company_to_person': [],  # 公司→个人
        'person_to_person': [],   # 核心人员之间
        'company_to_company': [], # 涉案公司之间
        'summary': {}
    }
    
    # 1. 检测个人→公司的资金往来
    logger.info('【阶段1】检测个人→涉案公司的资金往来')
    for person_name, df in personal_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
            
        for company in companies:
            # 模糊匹配公司名（可能简写）
            company_keywords = _extract_company_keywords(company)
            
            for idx, row in df.iterrows():
                counterparty = str(row.get('counterparty', ''))
                if _match_company(counterparty, company_keywords):
                    results['person_to_company'].append({
                        '发起方': person_name,
                        '接收方': company,
                        '交易对方原文': counterparty,
                        '日期': row.get('date'),
                        '收入': row.get('income', 0),
                        '支出': row.get('expense', 0),
                        '摘要': row.get('description', ''),
                        '方向': '个人→公司'
                    })
    
    logger.info(f'  发现 {len(results["person_to_company"])} 笔个人→公司交易')
    
    # 2. 检测公司→个人的资金往来
    logger.info('【阶段2】检测涉案公司→个人的资金往来')
    for company_name, df in company_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
            
        for person in core_persons:
            for idx, row in df.iterrows():
                counterparty = str(row.get('counterparty', ''))
                # 精确匹配人名
                if person in counterparty:
                    results['company_to_person'].append({
                        '发起方': company_name,
                        '接收方': person,
                        '交易对方原文': counterparty,
                        '日期': row.get('date'),
                        '收入': row.get('income', 0),
                        '支出': row.get('expense', 0),
                        '摘要': row.get('description', ''),
                        '方向': '公司→个人'
                    })
    
    logger.info(f'  发现 {len(results["company_to_person"])} 笔公司→个人交易')
    
    # 3. 检测核心人员之间的资金往来
    logger.info('【阶段3】检测核心人员之间的资金往来')
    for person_name, df in personal_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
            
        for other_person in core_persons:
            if other_person == person_name:
                continue
                
            for idx, row in df.iterrows():
                counterparty = str(row.get('counterparty', ''))
                if other_person in counterparty:
                    results['person_to_person'].append({
                        '发起方': person_name,
                        '接收方': other_person,
                        '交易对方原文': counterparty,
                        '日期': row.get('date'),
                        '收入': row.get('income', 0),
                        '支出': row.get('expense', 0),
                        '摘要': row.get('description', ''),
                        '方向': '个人→个人'
                    })
    
    logger.info(f'  发现 {len(results["person_to_person"])} 笔核心人员间交易')
    
    # 4. 检测涉案公司之间的资金往来
    logger.info('【阶段4】检测涉案公司之间的资金往来')
    for company_name, df in company_data.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
            
        for other_company in companies:
            if other_company == company_name:
                continue
                
            other_keywords = _extract_company_keywords(other_company)
            
            for idx, row in df.iterrows():
                counterparty = str(row.get('counterparty', ''))
                if _match_company(counterparty, other_keywords):
                    results['company_to_company'].append({
                        '发起方': company_name,
                        '接收方': other_company,
                        '交易对方原文': counterparty,
                        '日期': row.get('date'),
                        '收入': row.get('income', 0),
                        '支出': row.get('expense', 0),
                        '摘要': row.get('description', ''),
                        '方向': '公司→公司'
                    })
    
    logger.info(f'  发现 {len(results["company_to_company"])} 笔涉案公司间交易')
    
    # 5. 生成汇总统计
    results['summary'] = _generate_summary(results)
    
    logger.info('')
    logger.info('资金穿透分析完成')
    logger.info(f'  个人→公司: {len(results["person_to_company"])} 笔')
    logger.info(f'  公司→个人: {len(results["company_to_person"])} 笔')
    logger.info(f'  个人→个人: {len(results["person_to_person"])} 笔')
    logger.info(f'  公司→公司: {len(results["company_to_company"])} 笔')
    
    return results


def _extract_company_keywords(company_name: str) -> List[str]:
    """提取公司名关键词用于模糊匹配"""
    keywords = [company_name]
    
    # 移除常见后缀
    suffixes = ['有限公司', '股份有限公司', '有限责任公司', '科技', '技术']
    name = company_name
    for suffix in suffixes:
        name = name.replace(suffix, '')
    
    if name and len(name) >= 2:
        keywords.append(name)
    
    # 提取核心词汇
    if '北京' in company_name:
        core = company_name.replace('北京', '').replace('有限公司', '').replace('科技', '')
        if core and len(core) >= 2:
            keywords.append(core)
    if '贵州' in company_name:
        core = company_name.replace('贵州', '').replace('有限公司', '').replace('科技', '')
        if core and len(core) >= 2:
            keywords.append(core)
    
    return list(set(keywords))


def _match_company(counterparty: str, keywords: List[str]) -> bool:
    """检查对手方是否匹配公司关键词"""
    if not counterparty:
        return False
        
    for keyword in keywords:
        if keyword in counterparty:
            return True
    return False


def _generate_summary(results: Dict) -> Dict:
    """生成资金穿透汇总统计"""
    summary = {
        '个人→公司笔数': len(results['person_to_company']),
        '个人→公司总金额': 0,
        '公司→个人笔数': len(results['company_to_person']),
        '公司→个人总金额': 0,
        '核心人员间笔数': len(results['person_to_person']),
        '核心人员间总金额': 0,
        '涉案公司间笔数': len(results['company_to_company']),
        '涉案公司间总金额': 0,
    }
    
    for item in results['person_to_company']:
        summary['个人→公司总金额'] += item['收入'] + item['支出']
    
    for item in results['company_to_person']:
        summary['公司→个人总金额'] += item['收入'] + item['支出']
        
    for item in results['person_to_person']:
        summary['核心人员间总金额'] += item['收入'] + item['支出']
        
    for item in results['company_to_company']:
        summary['涉案公司间总金额'] += item['收入'] + item['支出']
    
    return summary


def generate_penetration_report(results: Dict, output_dir: str) -> str:
    """
    生成资金穿透分析报告
    
    Args:
        results: 分析结果
        output_dir: 输出目录
        
    Returns:
        报告文件路径
    """
    report_path = os.path.join(output_dir, '资金穿透分析报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('资金穿透分析报告\n')
        f.write('='*60 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        
        # 汇总统计
        f.write('一、汇总统计\n')
        f.write('-'*40 + '\n')
        summary = results['summary']
        f.write(f'个人→涉案公司: {summary["个人→公司笔数"]} 笔, 金额 {summary["个人→公司总金额"]/10000:.2f} 万元\n')
        f.write(f'涉案公司→个人: {summary["公司→个人笔数"]} 笔, 金额 {summary["公司→个人总金额"]/10000:.2f} 万元\n')
        f.write(f'核心人员之间: {summary["核心人员间笔数"]} 笔, 金额 {summary["核心人员间总金额"]/10000:.2f} 万元\n')
        f.write(f'涉案公司之间: {summary["涉案公司间笔数"]} 笔, 金额 {summary["涉案公司间总金额"]/10000:.2f} 万元\n\n')
        
        # 详细明细
        if results['person_to_company']:
            f.write('二、个人→涉案公司明细\n')
            f.write('-'*40 + '\n')
            for i, item in enumerate(results['person_to_company'][:20], 1):  # 限制输出
                date_str = item['日期'].strftime('%Y-%m-%d') if hasattr(item['日期'], 'strftime') else str(item['日期'])[:10]
                amount = item['收入'] if item['收入'] > 0 else item['支出']
                direction = '收入' if item['收入'] > 0 else '支出'
                f.write(f'{i}. [{date_str}] {item["发起方"]} → {item["接收方"]}: {utils.format_currency(amount)}({direction}), 摘要:{item["摘要"][:20]}\n')
            if len(results['person_to_company']) > 20:
                f.write(f'... 共 {len(results["person_to_company"])} 笔，仅显示前20笔\n')
            f.write('\n')
        
        if results['company_to_person']:
            f.write('三、涉案公司→个人明细\n')
            f.write('-'*40 + '\n')
            for i, item in enumerate(results['company_to_person'][:20], 1):
                date_str = item['日期'].strftime('%Y-%m-%d') if hasattr(item['日期'], 'strftime') else str(item['日期'])[:10]
                amount = item['收入'] if item['收入'] > 0 else item['支出']
                direction = '收入' if item['收入'] > 0 else '支出'
                f.write(f'{i}. [{date_str}] {item["发起方"]} → {item["接收方"]}: {utils.format_currency(amount)}({direction}), 摘要:{item["摘要"][:20]}\n')
            if len(results['company_to_person']) > 20:
                f.write(f'... 共 {len(results["company_to_person"])} 笔，仅显示前20笔\n')
            f.write('\n')
            
        if results['person_to_person']:
            f.write('四、核心人员之间明细\n')
            f.write('-'*40 + '\n')
            for i, item in enumerate(results['person_to_person'][:20], 1):
                date_str = item['日期'].strftime('%Y-%m-%d') if hasattr(item['日期'], 'strftime') else str(item['日期'])[:10]
                amount = item['收入'] if item['收入'] > 0 else item['支出']
                direction = '收入' if item['收入'] > 0 else '支出'
                f.write(f'{i}. [{date_str}] {item["发起方"]} → {item["接收方"]}: {utils.format_currency(amount)}({direction}), 摘要:{item["摘要"][:20]}\n')
            if len(results['person_to_person']) > 20:
                f.write(f'... 共 {len(results["person_to_person"])} 笔，仅显示前20笔\n')
            f.write('\n')
            
        if results['company_to_company']:
            f.write('五、涉案公司之间明细\n')
            f.write('-'*40 + '\n')
            for i, item in enumerate(results['company_to_company'][:20], 1):
                date_str = item['日期'].strftime('%Y-%m-%d') if hasattr(item['日期'], 'strftime') else str(item['日期'])[:10]
                amount = item['收入'] if item['收入'] > 0 else item['支出']
                direction = '收入' if item['收入'] > 0 else '支出'
                f.write(f'{i}. [{date_str}] {item["发起方"]} → {item["接收方"]}: {utils.format_currency(amount)}({direction}), 摘要:{item["摘要"][:20]}\n')
            if len(results['company_to_company']) > 20:
                f.write(f'... 共 {len(results["company_to_company"])} 笔，仅显示前20笔\n')
    
    logger.info(f'资金穿透报告已生成: {report_path}')
    return report_path
