#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多源数据交叉碰撞分析模块
关联分析出行同行人、同住宿人、快递联系人与银行流水的交集
"""

import os
import glob
import pandas as pd
from datetime import datetime
from typing import Dict, List
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
    flight_pattern = os.path.join(data_directory, '**', '中航信航班同行人信息（定向查询）', '*.xlsx')
    results['flight_companions'] = _read_flight_companions(flight_pattern, core_persons)
    logger.info(f'  读取到航班同行记录 {len(results["flight_companions"])} 条')
    
    # 2. 读取铁路同行人数据
    rail_pattern = os.path.join(data_directory, '**', '铁路总公司同行人信息（定向查询）', '*.xlsx')
    results['rail_companions'] = _read_rail_companions(rail_pattern, core_persons)
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


def _read_flight_companions(flight_pattern: str, core_persons: List[str]) -> List[Dict]:
    """读取航班同行人数据"""
    companions = []
    
    for file in glob.glob(flight_pattern, recursive=True):
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


def _read_rail_companions(rail_pattern: str, core_persons: List[str]) -> List[Dict]:
    """读取铁路同行人数据"""
    companions = []
    
    for file in glob.glob(rail_pattern, recursive=True):
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


def _build_transaction_index(all_transactions: Dict[str, pd.DataFrame], core_persons: List[str]) -> Dict[str, List[tuple]]:
    """
    预构建交易数据索引，按核心人员分组
    返回: {person_name: [(key, df), ...]}
    """
    index = {p: [] for p in core_persons}
    for key, df in all_transactions.items():
        if df.empty or 'counterparty' not in df.columns:
            continue
        for person in core_persons:
            if person in key:
                index[person].append((key, df))
    return index


def _normalize_name(name: str) -> str:
    """规范化姓名：去掉脱敏符号和空格"""
    if not name:
        return ''
    for char in ['*', '＊', '×', '○', '●', '_', '-', ' ']:
        name = name.replace(char, '')
    return name.strip()


def _fuzzy_match(name1: str, name2: str) -> bool:
    """模糊匹配姓名"""
    n1 = _normalize_name(name1)
    n2 = _normalize_name(name2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    if len(n1) >= 2 and len(n2) >= 2:
        if n1 in n2 or n2 in n1:
            return True
    if len(n1) >= 2 and len(n2) >= 2:
        if n1[0] == n2[0] and abs(len(n1) - len(n2)) <= 1:
            return True
    return False


def _correlate_companions_with_funds(
    companions: List[Dict],
    all_transactions: Dict[str, pd.DataFrame],
    core_persons: List[str],
    time_window_days: int = 30
) -> List[Dict]:
    """将同行人与银行流水碰撞（优化版：预构建索引 + 向量化匹配）"""
    if not companions:
        return []
    
    correlations = []
    
    # 预构建交易索引
    tx_index = _build_transaction_index(all_transactions, core_persons)
    
    # 按人员分组同行人记录，减少交易遍历次数
    from collections import defaultdict
    companions_by_person = defaultdict(list)
    for c in companions:
        companions_by_person[c['person']].append(c)
    
    # 预解析旅行日期
    for person, person_companions in companions_by_person.items():
        for c in person_companions:
            travel_date = c.get('travel_date')
            if travel_date is not None:
                try:
                    if hasattr(travel_date, 'date'):
                        c['_travel_dt'] = travel_date
                    else:
                        c['_travel_dt'] = pd.to_datetime(travel_date)
                except:
                    c['_travel_dt'] = None
    
    # 遍历每个人员的交易
    for person, person_companions in companions_by_person.items():
        person_tx_list = tx_index.get(person, [])
        if not person_tx_list:
            continue
        
        # 合并该人员所有账户的交易
        all_dfs = []
        for key, df in person_tx_list:
            df_copy = df[['date', 'counterparty', 'income', 'expense', 'description']].copy()
            df_copy['_account_key'] = key
            all_dfs.append(df_copy)
        
        if not all_dfs:
            continue
        
        merged_df = pd.concat(all_dfs, ignore_index=True)
        
        # 预解析交易日期
        try:
            merged_df['_trans_dt'] = pd.to_datetime(merged_df['date'], errors='coerce')
        except:
            merged_df['_trans_dt'] = None
        
        # 遍历同行人记录
        for c in person_companions:
            travel_dt = c.get('_travel_dt')
            if travel_dt is None:
                continue
            
            companion_name = c['companion_name']
            normalized_companion = _normalize_name(companion_name)
            if not normalized_companion or len(normalized_companion) < 2:
                continue
            
            # 使用向量化字符串匹配
            mask = merged_df['counterparty'].astype(str).str.contains(
                normalized_companion, na=False, regex=False
            )
            matched = merged_df[mask]
            
            # 对匹配结果进行二次模糊匹配验证 + 时间窗口过滤
            for row in matched.itertuples():
                counterparty = str(row.counterparty)
                if not _fuzzy_match(companion_name, counterparty):
                    continue
                
                trans_dt = row._trans_dt
                if pd.isna(trans_dt):
                    continue
                
                days_diff = (trans_dt - travel_dt).days
                
                if abs(days_diff) > time_window_days:
                    continue
                
                timing = '先付款后同行' if days_diff < 0 else ('先同行后收款' if days_diff > 0 else '同日')
                
                correlations.append({
                    'person': person,
                    'companion': companion_name,
                    'travel_date': c.get('travel_date'),
                    'travel_type': c.get('travel_type', ''),
                    'transaction_date': row.date,
                    'days_diff': days_diff,
                    'timing': timing,
                    'amount': max(getattr(row, 'income', 0) or 0, getattr(row, 'expense', 0) or 0),
                    'direction': 'income' if (getattr(row, 'income', 0) or 0) > 0 else 'expense',
                    'description': getattr(row, 'description', ''),
                    'counterparty_raw': counterparty,
                    'risk_level': 'high' if abs(days_diff) <= 7 else 'medium'
                })
    
    return correlations

def _summarize_companions(companions: List[Dict]) -> Dict:
    """汇总同行人信息"""
    summary = defaultdict(lambda: {'count': 0, 'persons': set(), 'dates': []})
    
    def is_valid_name(name: str) -> bool:
        """检查是否为有效的人名"""
        if not name or not name.strip():
            return False
        name = name.strip()
        # 排除纯数字
        if name.isdigit():
            return False
        # 排除太短（单字符）
        if len(name) < 2:
            return False
        # 排除 nan/None 等
        if name.lower() in ('nan', 'none', 'null', '-'):
            return False
        # 排除纯符号
        if all(c in '*_-.' for c in name):
            return False
        return True
    
    for rec in companions:
        name = rec.get('companion_name', '')
        if not is_valid_name(name):
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
    
    hotel_pattern = os.path.join(data_directory, '**', '公安部同住宿（定向查询）', '*.xlsx')
    
    # 读取同住宿数据
    for file in glob.glob(hotel_pattern, recursive=True):
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
    
    # 与银行流水碰撞（优化版：预构建索引 + 向量化匹配）
    if not results['cohabitants']:
        logger.info(f'同住宿分析完成: 发现 0 条资金碰撞')
        return results
    
    # 预构建交易索引
    tx_index = _build_transaction_index(all_transactions, core_persons)
    
    # 按人员分组同住宿记录
    from collections import defaultdict
    cohabitants_by_person = defaultdict(list)
    for rec in results['cohabitants']:
        cohabitants_by_person[rec['person']].append(rec)
    
    # 遍历每个人员
    for person, person_cohabitants in cohabitants_by_person.items():
        person_tx_list = tx_index.get(person, [])
        if not person_tx_list:
            continue
        
        # 合并该人员所有账户的交易
        all_dfs = []
        for key, df in person_tx_list:
            df_copy = df[['date', 'counterparty', 'income', 'expense', 'description']].copy()
            df_copy['_account_key'] = key
            all_dfs.append(df_copy)
        
        if not all_dfs:
            continue
        
        merged_df = pd.concat(all_dfs, ignore_index=True)
        
        # 为每个同住人进行向量化匹配
        for rec in person_cohabitants:
            cohabitant = rec['cohabitant']
            stay_date = rec.get('stay_date')
            
            # 使用向量化字符串匹配
            mask = merged_df['counterparty'].astype(str).str.contains(cohabitant, na=False, regex=False)
            matched = merged_df[mask]
            
            for row in matched.itertuples():
                results['fund_correlations'].append({
                    'person': person,
                    'cohabitant': cohabitant,
                    'stay_date': stay_date,
                    'transaction_date': row.date,
                    'amount': max(getattr(row, 'income', 0) or 0, getattr(row, 'expense', 0) or 0),
                    'direction': 'income' if (getattr(row, 'income', 0) or 0) > 0 else 'expense',
                    'description': getattr(row, 'description', ''),
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
    
    express_pattern = os.path.join(data_directory, '**', '国家邮政局快递信息（定向查询）', '*.xlsx')
    
    # 收集快递联系人
    contact_counter = defaultdict(lambda: {'count': 0, 'persons': set()})
    
    for file in glob.glob(express_pattern, recursive=True):
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
    
    # 与银行流水碰撞（优化版：预构建索引 + 向量化匹配）
    if not contact_counter:
        logger.info(f'快递联系人分析完成: 发现 0 条资金碰撞')
        return results
    
    # 预构建交易索引
    tx_index = _build_transaction_index(all_transactions, core_persons)
    
    # 收集所有联系人姓名
    all_contact_names = list(contact_counter.keys())
    
    # 合并所有核心人员的交易数据
    all_dfs = []
    for person in core_persons:
        person_tx_list = tx_index.get(person, [])
        for key, df in person_tx_list:
            df_copy = df[['date', 'counterparty', 'income', 'expense', 'description']].copy()
            df_copy['_person'] = person
            all_dfs.append(df_copy)
    
    if not all_dfs:
        logger.info(f'快递联系人分析完成: 发现 0 条资金碰撞')
        return results
    
    merged_tx = pd.concat(all_dfs, ignore_index=True)
    
    # 预规范化 counterparty 列，用于模糊匹配
    merged_tx['_normalized_counterparty'] = merged_tx['counterparty'].astype(str).apply(_normalize_name)
    
    # 批量匹配所有联系人
    for contact_name in all_contact_names:
        normalized_contact = _normalize_name(contact_name)
        if not normalized_contact or len(normalized_contact) < 2:
            continue
        
        # 使用规范化后的 counterparty 进行匹配
        mask = merged_tx['_normalized_counterparty'].str.contains(
            normalized_contact, na=False, regex=False
        )
        matched = merged_tx[mask]
        
        # 对匹配结果进行处理（使用模糊匹配二次验证）
        for row in matched.itertuples():
            # 使用模糊匹配验证，避免误匹配
            if not _fuzzy_match(contact_name, str(row.counterparty)):
                continue
            
            results['fund_correlations'].append({
                'person': row._person,
                'contact': contact_name,
                'transaction_date': row.date,
                'amount': max(getattr(row, 'income', 0) or 0, getattr(row, 'expense', 0) or 0),
                'direction': 'income' if (getattr(row, 'income', 0) or 0) > 0 else 'expense',
                'description': getattr(row, 'description', ''),
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
