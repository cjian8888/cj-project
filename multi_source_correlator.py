#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源数据交叉碰撞分析模块
关联分析出行同行人、同住宿人、快递联系人与银行流水的交集
"""

import os
import glob
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set
from collections import defaultdict
import utils

logger = utils.setup_logger(__name__)


def correlate_travel_companions(
    data_directory: str,
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """
    出行同行人与资金碰撞分析
    
    读取航班/铁路同行人数据，检查同行前后是否有资金往来
    
    Args:
        data_directory: 数据目录
        all_transactions: 所有银行交易数据
        core_persons: 核心人员列表
        
    Returns:
        碰撞结果
    """
    logger.info('='*60)
    logger.info('开始出行同行人资金碰撞分析')
    logger.info('='*60)
    
    results = {
        'flight_companions': [],     # 航班同行人
        'rail_companions': [],       # 铁路同行人
        'fund_correlations': [],     # 资金碰撞结果
        'companion_summary': {}      # 同行人汇总
    }
    
    # 1. 读取航班同行人数据
    flight_dir = os.path.join(data_directory, '纪检材料（公开）', '中航信航班同行人信息（定向查询）')
    if os.path.exists(flight_dir):
        results['flight_companions'] = _read_flight_companions(flight_dir, core_persons)
        logger.info(f'  读取到航班同行记录 {len(results["flight_companions"])} 条')
    
    # 2. 读取铁路同行人数据
    rail_dir = os.path.join(data_directory, '纪检材料（公开）', '铁路总公司同行人信息（定向查询）')
    if os.path.exists(rail_dir):
        results['rail_companions'] = _read_rail_companions(rail_dir, core_persons)
        logger.info(f'  读取到铁路同行记录 {len(results["rail_companions"])} 条')
    
    # 3. 提取所有同行人名单
    all_companions = set()
    for rec in results['flight_companions'] + results['rail_companions']:
        companion = rec.get('companion_name', '')
        if companion and len(companion) >= 2:
            all_companions.add(companion)
    
    logger.info(f'  总计发现 {len(all_companions)} 个不同同行人')
    
    # 4. 与银行流水碰撞
    results['fund_correlations'] = _correlate_companions_with_funds(
        results['flight_companions'] + results['rail_companions'],
        all_transactions,
        core_persons
    )
    
    # 5. 生成同行人汇总
    results['companion_summary'] = _summarize_companions(
        results['flight_companions'] + results['rail_companions']
    )
    
    logger.info(f'出行同行人分析完成: 发现 {len(results["fund_correlations"])} 条资金碰撞')
    
    return results


def _read_flight_companions(flight_dir: str, core_persons: List[str]) -> List[Dict]:
    """读取航班同行人数据"""
    companions = []
    
    for file in glob.glob(os.path.join(flight_dir, '*.xlsx')):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            
            # 确定核心人员
            filename = os.path.basename(file)
            person = None
            for p in core_persons:
                if p in filename:
                    person = p
                    break
            
            if not person:
                continue
            
            # 查找同行人列
            companion_cols = [c for c in df.columns if '同行' in str(c) or '姓名' in str(c)]
            date_cols = [c for c in df.columns if '日期' in str(c) or '时间' in str(c)]
            flight_cols = [c for c in df.columns if '航班' in str(c) or '班次' in str(c)]
            
            if not companion_cols:
                continue
            
            for _, row in df.iterrows():
                companion_name = str(row.get(companion_cols[0], ''))
                if not companion_name or companion_name == 'nan' or companion_name == person:
                    continue
                
                flight_date = row.get(date_cols[0]) if date_cols else None
                flight_no = row.get(flight_cols[0], '') if flight_cols else ''
                
                companions.append({
                    'person': person,
                    'companion_name': companion_name,
                    'travel_date': flight_date,
                    'travel_type': '航班',
                    'flight_no': flight_no,
                    'source_file': filename
                })
        except Exception as e:
            logger.warning(f'读取航班同行人文件失败: {file}, {e}')
    
    return companions


def _read_rail_companions(rail_dir: str, core_persons: List[str]) -> List[Dict]:
    """读取铁路同行人数据"""
    companions = []
    
    for file in glob.glob(os.path.join(rail_dir, '*.xlsx')):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            
            filename = os.path.basename(file)
            person = None
            for p in core_persons:
                if p in filename:
                    person = p
                    break
            
            if not person:
                continue
            
            # 查找同行人列
            companion_cols = [c for c in df.columns if '同行' in str(c) or '姓名' in str(c)]
            date_cols = [c for c in df.columns if '日期' in str(c) or '时间' in str(c) or '乘车' in str(c)]
            train_cols = [c for c in df.columns if '车次' in str(c) or '列车' in str(c)]
            
            if not companion_cols:
                continue
            
            for _, row in df.iterrows():
                companion_name = str(row.get(companion_cols[0], ''))
                if not companion_name or companion_name == 'nan' or companion_name == person:
                    continue
                
                travel_date = row.get(date_cols[0]) if date_cols else None
                train_no = row.get(train_cols[0], '') if train_cols else ''
                
                companions.append({
                    'person': person,
                    'companion_name': companion_name,
                    'travel_date': travel_date,
                    'travel_type': '火车',
                    'train_no': train_no,
                    'source_file': filename
                })
        except Exception as e:
            logger.warning(f'读取铁路同行人文件失败: {file}, {e}')
    
    return companions


def _correlate_companions_with_funds(
    companions: List[Dict],
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    time_window_days: int = 30
) -> List[Dict]:
    """将同行人与银行流水碰撞（支持模糊匹配）"""
    correlations = []
    
    def normalize_name(name: str) -> str:
        """规范化姓名：去掉脱敏符号和空格"""
        if not name:
            return ''
        # 去掉常见脱敏符号
        for char in ['*', '＊', '×', '○', '●', '_', '-', ' ']:
            name = name.replace(char, '')
        return name.strip()
    
    def fuzzy_match(name1: str, name2: str) -> bool:
        """模糊匹配姓名"""
        n1 = normalize_name(name1)
        n2 = normalize_name(name2)
        if not n1 or not n2:
            return False
        # 完全匹配
        if n1 == n2:
            return True
        # 一个包含另一个（处理脱敏后的部分匹配）
        if len(n1) >= 2 and len(n2) >= 2:
            if n1 in n2 or n2 in n1:
                return True
        # 首字相同 + 长度相近（处理"张三" vs "张*三"）
        if len(n1) >= 2 and len(n2) >= 2:
            if n1[0] == n2[0] and abs(len(n1) - len(n2)) <= 1:
                return True
        return False
    
    for companion_rec in companions:
        person = companion_rec['person']
        companion_name = companion_rec['companion_name']
        travel_date = companion_rec.get('travel_date')
        
        if travel_date is None:
            continue
        
        # 查找该核心人员的交易数据
        for key, df in all_transactions.items():
            if person not in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            # 查找与同行人的资金往来（使用模糊匹配）
            for _, row in df.iterrows():
                counterparty = str(row.get('counterparty', ''))
                
                # 使用模糊匹配
                if not fuzzy_match(companion_name, counterparty):
                    continue
                
                trans_date = row.get('date')
                if trans_date is None:
                    continue
                
                # 检查时间关系
                try:
                    if hasattr(travel_date, 'date'):
                        travel_dt = travel_date
                    else:
                        travel_dt = pd.to_datetime(travel_date)
                    
                    if hasattr(trans_date, 'date'):
                        trans_dt = trans_date
                    else:
                        trans_dt = pd.to_datetime(trans_date)
                    
                    days_diff = (trans_dt - travel_dt).days
                except Exception as e:
                    logger.debug(f'日期解析失败: {e}')
                    continue
                
                if abs(days_diff) > time_window_days:
                    continue
                
                # 判断时序关系
                if days_diff < 0:
                    timing = '先付款后同行'
                elif days_diff > 0:
                    timing = '先同行后收款'
                else:
                    timing = '同日'
                
                correlation = {
                    'person': person,
                    'companion': companion_name,
                    'travel_date': travel_date,
                    'travel_type': companion_rec.get('travel_type', ''),
                    'transaction_date': trans_date,
                    'days_diff': days_diff,
                    'timing': timing,
                    'amount': max(row.get('income', 0), row.get('expense', 0)),
                    'direction': 'income' if row.get('income', 0) > 0 else 'expense',
                    'description': row.get('description', ''),
                    'counterparty_raw': counterparty,
                    'risk_level': 'high' if abs(days_diff) <= 7 else 'medium'
                }
                correlations.append(correlation)
    
    return correlations


def _summarize_companions(companions: List[Dict]) -> Dict:
    """汇总同行人信息"""
    summary = defaultdict(lambda: {'count': 0, 'persons': set(), 'dates': []})
    
    for rec in companions:
        name = rec.get('companion_name', '')
        if not name:
            continue
        
        summary[name]['count'] += 1
        summary[name]['persons'].add(rec.get('person', ''))
        if rec.get('travel_date'):
            summary[name]['dates'].append(rec['travel_date'])
    
    # 转换为普通字典，标记高频同行人
    result = {}
    for name, data in summary.items():
        result[name] = {
            'count': data['count'],
            'persons': list(data['persons']),
            'is_multi_person': len(data['persons']) > 1,  # 与多个核心人员都同行过
            'risk_level': 'high' if len(data['persons']) > 1 or data['count'] >= 3 else 'medium'
        }
    
    return result


def correlate_hotel_cohabitants(
    data_directory: str,
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """
    同住宿人与资金碰撞分析
    
    Args:
        data_directory: 数据目录
        all_transactions: 银行交易数据
        core_persons: 核心人员列表
        
    Returns:
        碰撞结果
    """
    logger.info('开始同住宿人资金碰撞分析')
    
    results = {
        'cohabitants': [],
        'fund_correlations': []
    }
    
    hotel_dir = os.path.join(data_directory, '纪检材料（公开）', '公安部同住宿（定向查询）')
    if not os.path.exists(hotel_dir):
        logger.info('  未找到同住宿数据目录')
        return results
    
    # 读取同住宿数据
    for file in glob.glob(os.path.join(hotel_dir, '*.xlsx')):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            
            filename = os.path.basename(file)
            person = None
            for p in core_persons:
                if p in filename:
                    person = p
                    break
            
            if not person:
                continue
            
            # 查找同住人列
            name_cols = [c for c in df.columns if '姓名' in str(c) or '同住' in str(c)]
            date_cols = [c for c in df.columns if '日期' in str(c) or '入住' in str(c)]
            hotel_cols = [c for c in df.columns if '酒店' in str(c) or '宾馆' in str(c) or '旅馆' in str(c)]
            
            if not name_cols:
                continue
            
            for _, row in df.iterrows():
                cohabitant = str(row.get(name_cols[0], ''))
                if not cohabitant or cohabitant == 'nan' or cohabitant == person:
                    continue
                
                stay_date = row.get(date_cols[0]) if date_cols else None
                hotel_name = row.get(hotel_cols[0], '') if hotel_cols else ''
                
                results['cohabitants'].append({
                    'person': person,
                    'cohabitant': cohabitant,
                    'stay_date': stay_date,
                    'hotel': hotel_name
                })
        except Exception as e:
            logger.warning(f'读取同住宿文件失败: {file}, {e}')
    
    logger.info(f'  读取到同住宿记录 {len(results["cohabitants"])} 条')
    
    # 与银行流水碰撞（复用同行人碰撞逻辑）
    for rec in results['cohabitants']:
        person = rec['person']
        cohabitant = rec['cohabitant']
        stay_date = rec.get('stay_date')
        
        for key, df in all_transactions.items():
            if person not in key:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            for _, row in df.iterrows():
                counterparty = str(row.get('counterparty', ''))
                if cohabitant in counterparty:
                    results['fund_correlations'].append({
                        'person': person,
                        'cohabitant': cohabitant,
                        'stay_date': stay_date,
                        'transaction_date': row.get('date'),
                        'amount': max(row.get('income', 0), row.get('expense', 0)),
                        'direction': 'income' if row.get('income', 0) > 0 else 'expense',
                        'description': row.get('description', ''),
                        'risk_level': 'high'
                    })
    
    logger.info(f'同住宿分析完成: 发现 {len(results["fund_correlations"])} 条资金碰撞')
    
    return results


def correlate_express_contacts(
    data_directory: str,
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """
    快递联系人与资金碰撞分析
    
    Args:
        data_directory: 数据目录
        all_transactions: 银行交易数据
        core_persons: 核心人员列表
        
    Returns:
        碰撞结果
    """
    logger.info('开始快递联系人资金碰撞分析')
    
    results = {
        'express_contacts': [],
        'frequent_addresses': [],
        'fund_correlations': []
    }
    
    express_dir = os.path.join(data_directory, '纪检材料（公开）', '国家邮政局快递信息（定向查询）')
    if not os.path.exists(express_dir):
        logger.info('  未找到快递信息数据目录')
        return results
    
    # 收集快递联系人
    contact_counter = defaultdict(lambda: {'count': 0, 'persons': set()})
    
    for file in glob.glob(os.path.join(express_dir, '*.xlsx')):
        try:
            df = pd.read_excel(file, engine='openpyxl')
            
            filename = os.path.basename(file)
            person = None
            for p in core_persons:
                if p in filename:
                    person = p
                    break
            
            if not person:
                continue
            
            # 查找收件人/寄件人列
            name_cols = [c for c in df.columns if '收件' in str(c) or '寄件' in str(c) or '姓名' in str(c)]
            addr_cols = [c for c in df.columns if '地址' in str(c)]
            
            for _, row in df.iterrows():
                for col in name_cols:
                    contact = str(row.get(col, ''))
                    if contact and contact != 'nan' and contact != person and len(contact) >= 2:
                        # 过滤掉可能是本人的记录
                        if contact not in core_persons:
                            contact_counter[contact]['count'] += 1
                            contact_counter[contact]['persons'].add(person)
                            
                            results['express_contacts'].append({
                                'person': person,
                                'contact': contact,
                                'type': '收件人' if '收件' in col else '寄件人'
                            })
        except Exception as e:
            logger.warning(f'读取快递文件失败: {file}, {e}')
    
    logger.info(f'  读取到快递联系人 {len(contact_counter)} 个')
    
    # 筛选高频联系人
    frequent_contacts = [
        {'name': name, 'count': data['count'], 'persons': list(data['persons'])}
        for name, data in contact_counter.items()
        if data['count'] >= 3 or len(data['persons']) > 1
    ]
    results['frequent_addresses'] = sorted(frequent_contacts, key=lambda x: -x['count'])[:20]
    
    # 与银行流水碰撞
    for contact_name in contact_counter.keys():
        for key, df in all_transactions.items():
            # 检查是否是核心人员的交易数据
            is_core = any(p in key for p in core_persons)
            if not is_core:
                continue
            
            if df.empty or 'counterparty' not in df.columns:
                continue
            
            for _, row in df.iterrows():
                counterparty = str(row.get('counterparty', ''))
                if contact_name in counterparty:
                    person = utils.normalize_person_name(key)
                    results['fund_correlations'].append({
                        'person': person if person else key.split('_')[0],
                        'contact': contact_name,
                        'transaction_date': row.get('date'),
                        'amount': max(row.get('income', 0), row.get('expense', 0)),
                        'direction': 'income' if row.get('income', 0) > 0 else 'expense',
                        'description': row.get('description', ''),
                        'frequency': contact_counter[contact_name]['count'],
                        'risk_level': 'high' if contact_counter[contact_name]['count'] >= 5 else 'medium'
                    })
    
    logger.info(f'快递联系人分析完成: 发现 {len(results["fund_correlations"])} 条资金碰撞')
    
    return results


def run_all_correlations(
    data_directory: str,
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str]
) -> Dict:
    """
    运行所有多源数据交叉碰撞分析
    
    Args:
        data_directory: 数据目录
        all_transactions: 银行交易数据
        core_persons: 核心人员列表
        
    Returns:
        所有碰撞结果汇总
    """
    logger.info('='*60)
    logger.info('开始多源数据交叉碰撞分析')
    logger.info('='*60)
    
    results = {
        'travel_companions': correlate_travel_companions(
            data_directory, all_transactions, core_persons
        ),
        'hotel_cohabitants': correlate_hotel_cohabitants(
            data_directory, all_transactions, core_persons
        ),
        'express_contacts': correlate_express_contacts(
            data_directory, all_transactions, core_persons
        ),
        'summary': {}
    }
    
    # 生成汇总
    total_correlations = (
        len(results['travel_companions'].get('fund_correlations', [])) +
        len(results['hotel_cohabitants'].get('fund_correlations', [])) +
        len(results['express_contacts'].get('fund_correlations', []))
    )
    
    results['summary'] = {
        '航班同行人数': len(results['travel_companions'].get('flight_companions', [])),
        '铁路同行人数': len(results['travel_companions'].get('rail_companions', [])),
        '同住宿人数': len(results['hotel_cohabitants'].get('cohabitants', [])),
        '快递联系人数': len(set(r['contact'] for r in results['express_contacts'].get('express_contacts', []))),
        '资金碰撞总数': total_correlations
    }
    
    logger.info('')
    logger.info('多源数据碰撞分析完成:')
    for k, v in results['summary'].items():
        logger.info(f'  {k}: {v}')
    
    return results


def generate_correlation_report(results: Dict, output_dir: str) -> str:
    """生成多源碰撞分析报告"""
    report_path = os.path.join(output_dir, '多源数据碰撞分析报告.txt')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('多源数据交叉碰撞分析报告\n')
        f.write('='*60 + '\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}\n\n')
        
        # 汇总
        summary = results.get('summary', {})
        f.write('一、汇总统计\n')
        f.write('-'*40 + '\n')
        for k, v in summary.items():
            f.write(f'{k}: {v}\n')
        f.write('\n')
        
        # 出行同行人资金碰撞
        travel = results.get('travel_companions', {})
        correlations = travel.get('fund_correlations', [])
        if correlations:
            f.write('二、出行同行人资金碰撞（重点关注）\n')
            f.write('-'*40 + '\n')
            for i, cor in enumerate(correlations[:20], 1):
                travel_date = cor['travel_date'].strftime('%Y-%m-%d') if hasattr(cor['travel_date'], 'strftime') else str(cor['travel_date'])[:10]
                trans_date = cor['transaction_date'].strftime('%Y-%m-%d') if hasattr(cor['transaction_date'], 'strftime') else str(cor['transaction_date'])[:10]
                f.write(f"{i}. 【{cor['risk_level'].upper()}】{cor['person']} 与 {cor['companion']} ({cor['travel_type']})\n")
                f.write(f"   同行日期: {travel_date} | 交易日期: {trans_date} | {cor['timing']}\n")
                f.write(f"   金额: {utils.format_currency(cor['amount'])} ({cor['direction']})\n")
            f.write('\n')
        
        # 高频同行人
        companion_summary = travel.get('companion_summary', {})
        risky_companions = [
            (name, data) for name, data in companion_summary.items()
            if data.get('risk_level') == 'high'
        ]
        if risky_companions:
            f.write('三、高风险同行人（与多人同行或高频同行）\n')
            f.write('-'*40 + '\n')
            for name, data in risky_companions[:10]:
                f.write(f"  {name}: 同行{data['count']}次, 涉及核心人员: {', '.join(data['persons'])}\n")
            f.write('\n')
        
        # 同住宿资金碰撞
        hotel = results.get('hotel_cohabitants', {})
        hotel_corr = hotel.get('fund_correlations', [])
        if hotel_corr:
            f.write('四、同住宿人资金碰撞\n')
            f.write('-'*40 + '\n')
            for i, cor in enumerate(hotel_corr[:10], 1):
                f.write(f"{i}. {cor['person']} 与 {cor['cohabitant']}: "
                       f"{utils.format_currency(cor['amount'])} ({cor['direction']})\n")
            f.write('\n')
        
        # 快递联系人碰撞
        express = results.get('express_contacts', {})
        express_corr = express.get('fund_correlations', [])
        if express_corr:
            f.write('五、快递联系人资金碰撞\n')
            f.write('-'*40 + '\n')
            for i, cor in enumerate(express_corr[:10], 1):
                f.write(f"{i}. {cor['person']} 与 {cor['contact']}: "
                       f"{utils.format_currency(cor['amount'])} ({cor['direction']}) "
                       f"[快递往来{cor['frequency']}次]\n")
            f.write('\n')
    
    logger.info(f'多源碰撞报告已生成: {report_path}')
    return report_path
