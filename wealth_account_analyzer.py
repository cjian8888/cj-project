#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
理财账户分析模块 - 资金穿透与关联排查系统（增强版）
专门处理银行理财产品导致的多子账号问题

【修复记录 2026-03-08】
1. 修复数据预处理：科学计数法、空值处理
2. 补充银行规则：中国银行、农业银行、建设银行等
3. 增强交易特征：金额特征、时间特征、收支配对
4. 统一与现有代码的一致性
5. 添加与主流程的集成接口

功能:
1. 自动识别理财子账号（根据各银行账号格式规律）
2. 分析账户间资金流转关系（主账户 <-> 理财子账号）
3. 计算真实理财规模（剔除内部循环）
4. 生成理财结构报告
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
import utils

logger = utils.setup_logger(__name__)


# ============= 银行账号格式规则（增强版） =============
# 基于实际数据分析总结的各银行账号特征

BANK_ACCOUNT_PATTERNS = {
    # 银行名: [(正则模式, 账号类型, 说明), ...]
    '招商银行': [
        (r'^1213\d{11}$', 'wealth', '招行理财子账号(15位)'),
        (r'^1063\d{11}$', 'wealth', '招行理财专户(15位)'),
        (r'^621\d{13,16}$', 'primary', '招行银行卡'),
        (r'^6225\d{13,16}$', 'primary', '招行银联卡'),
        (r'^4392\d{10}$', 'primary', '招行借记卡'),
    ],
    '民生银行': [
        (r'^50\d{18}$', 'wealth', '民生理财账户(20位50开头)'),
        (r'^51\d{18}$', 'wealth', '民生理财账户(20位51开头)'),
        (r'^0202\d{12}$', 'primary', '民生储蓄卡'),
        (r'^6226\d{12,16}$', 'primary', '民生银行卡'),
        (r'^4155\d{12}$', 'primary', '民生借记卡'),
    ],
    '浦发银行': [
        (r'^970\d{17}$', 'wealth', '浦发理财账户(20位97开头)'),
        (r'^6217\d{12,15}$', 'primary', '浦发银行卡'),
        (r'^6225\d{13}$', 'primary', '浦发借记卡'),
    ],
    '交通银行': [
        (r'^310\d{18,}$', 'wealth', '交行内部理财户(21位+)'),
        (r'^622[256]\d{12,16}$', 'primary', '交行银行卡'),
        (r'^4581\d{12}$', 'primary', '交行太平洋卡'),
    ],
    '工商银行': [
        (r'^100\d{14}$', 'internal', '工行内部账号(17位100开头)'),
        (r'^12[024]\d{14}$', 'internal', '工行内部账号(17位12x开头)'),
        (r'^6222\d{15}$', 'primary', '工行银行卡'),
        (r'^9558\d{15}$', 'primary', '工行借记卡'),
        (r'^6212\d{14}$', 'primary', '工行牡丹卡'),
    ],
    '光大银行': [
        (r'^62266\d{11}$', 'primary', '光大银行卡'),
        (r'^62267\d{11}$', 'primary', '光大电子账户'),
        (r'^9003\d{14}$', 'primary', '光大借记卡'),
    ],
    '中信银行': [
        (r'^6217\d{12}$', 'primary', '中信银行卡'),
        (r'^6226\d{13}$', 'primary', '中信借记卡'),
    ],
    # 【新增】中国银行
    '中国银行': [
        (r'^4563\d{13}$', 'primary', '中行借记卡'),
        (r'^6227\d{13}$', 'primary', '中行银行卡'),
        (r'^6216\d{13}$', 'primary', '中行长城卡'),
        (r'^6013\d{12}$', 'primary', '中行借记卡'),
        (r'^456351\d{10}$', 'primary', '中行一卡通'),
    ],
    # 【新增】农业银行
    '农业银行': [
        (r'^6228\d{13}$', 'primary', '农行借记卡'),
        (r'^9559\d{16}$', 'primary', '农行卡'),
        (r'^6213\d{13}$', 'primary', '农行金穗卡'),
        (r'^62284\d{13}$', 'primary', '农行银联卡'),
    ],
    # 【新增】建设银行
    '建设银行': [
        (r'^4367\d{13}$', 'primary', '建行龙卡'),
        (r'^6222\d{14}$', 'primary', '建行借记卡'),
        (r'^6217\d{13}$', 'primary', '建行银行卡'),
    ],
    # 【新增】广发银行
    '广发银行': [
        (r'^6225\d{13}$', 'primary', '广发银行卡'),
        (r'^6214\d{13}$', 'primary', '广发借记卡'),
        (r'^4336\d{12}$', 'primary', '广发卡'),
    ],
    # 【新增】平安银行
    '平安银行': [
        (r'^6229\d{13}$', 'primary', '平安银行卡'),
        (r'^6230\d{13}$', 'primary', '平安借记卡'),
        (r'^6029\d{14}$', 'primary', '平安信用卡'),
    ],
    # 【新增】兴业银行
    '兴业银行': [
        (r'^4512\d{13}$', 'primary', '兴业银行卡'),
        (r'^6229\d{13}$', 'primary', '兴业借记卡'),
        (r'^9666\d{14}$', 'primary', '兴业卡'),
    ],
    # 【新增】邮储银行
    '邮储银行': [
        (r'^6210\d{13}$', 'primary', '邮储银行卡'),
        (r'^6221\d{13}$', 'primary', '邮储绿卡'),
    ],
    # 【新增】上海银行
    '上海银行': [
        (r'^6222\d{13}$', 'primary', '上海银行卡'),
        (r'^6217\d{13}$', 'primary', '上海借记卡'),
    ],
    # 【新增】上海农村商业银行
    '上海农村商业银行': [
        (r'^6223\d{13}$', 'primary', '上海农商行卡'),
        (r'^6217\d{13}$', 'primary', '上海农商行借记卡'),
        (r'^7013\d{14,17}$', 'primary', '上海农商行账户'),
    ],
    # 【新增】恒丰银行
    '恒丰银行': [
        (r'^6230\d{13}$', 'primary', '恒丰银行卡'),
        (r'^6228\d{13}$', 'primary', '恒丰借记卡'),
    ],
    # 【新增】华兴银行
    '华兴银行': [
        (r'^6228\d{13}$', 'primary', '华兴银行卡'),
        (r'^6212\d{13}$', 'primary', '华兴借记卡'),
    ],
}

# 通用理财特征正则（增强版）
WEALTH_DESC_PATTERNS = [
    r'理财', r'基金', r'定期', r'定存', r'大额存单', r'结息', r'利息',
    r'分红', r'赎回', r'申购', r'转存', r'活期宝', r'如意宝',
    r'固收', r'通知存款', r'产品', r'到期', r'续存',
    r'黄金份额', r'积存金',  # 【新增】黄金类产品
    r'天天宝', r'朝朝宝', r'添利',  # 【新增】常见货基产品
    r'D\d{20,}',  # 理财产品代码如 D310902355643000045996...
    r'F[A-Z]{2}\d{6}',  # 基金代码如 FSG211212A
    r'X[A-Z]\d{8}',  # 【新增】净值型产品代码
]

# 银证转账关键词（新增）
SECURITIES_KEYWORDS = [
    r'银证转账', r'证转银', r'银转证', r'证券转银行', r'银行转证券',
    r'第三方存管', r'资金清算',
]

# 纯数字摘要（银行内部代码）
NUMERIC_DESC_PATTERN = re.compile(r'^[\d]{1,4}$')


class WealthAccountAnalyzer:
    """银行理财账户分析器（增强版）"""
    
    def __init__(self, df: pd.DataFrame, entity_name: str = None):
        """
        初始化分析器
        
        Args:
            df: 包含交易数据的DataFrame
            entity_name: 实体名称（人员）
        """
        self.df = df.copy()
        self.entity_name = entity_name
        
        # 【修复】标准化列名和数据格式
        self._normalize_columns()
        self._preprocess_data()
        
        # 账号分类结果
        self.accounts_classification = {}
        # 账号统计
        self.account_stats = {}
        # 账号关系图
        self.account_relations = []
        # 【新增】收支配对结果
        self.income_expense_pairs = []
        
    def _normalize_columns(self):
        """标准化列名"""
        column_mapping = {
            '交易摘要': 'description',
            '收入(元)': 'income',
            '支出(元)': 'expense',
            '余额(元)': 'balance',
            '交易对手': 'counterparty',
            '交易时间': 'date',
            '本方账号': 'account_id',
            '所属银行': 'bank',
        }
        for source, target in column_mapping.items():
            if source in self.df.columns and target not in self.df.columns:
                self.df[target] = self.df[source]
        
        # 确保必要列存在
        for col in ['income', 'expense', 'description', 'counterparty']:
            if col not in self.df.columns:
                self.df[col] = 0 if col in ['income', 'expense'] else ''
        
        # 兼容清洗后账号列命名，确保 account_id 可用
        if 'account_id' not in self.df.columns:
            for candidate in ['account', 'account_number', '账号', '卡号']:
                if candidate in self.df.columns:
                    self.df['account_id'] = self.df[candidate]
                    break

        # 兜底：仍不存在时创建空列
        if 'account_id' not in self.df.columns:
            self.df['account_id'] = ''

        # 若 account_id 列存在但为空，尝试用候选列回填
        if self.df['account_id'].astype(str).str.strip().eq('').all():
            for candidate in ['account', 'account_number', '账号', '卡号']:
                if candidate in self.df.columns:
                    self.df['account_id'] = self.df[candidate]
                    break
    
    def _preprocess_data(self):
        """【新增】数据预处理"""
        # 处理账号格式（科学计数法、浮点数）
        if 'account_id' in self.df.columns:
            self.df['account_id'] = self.df['account_id'].apply(
                lambda x: self._normalize_account_id(x)
            )
        
        # 处理日期格式
        if 'date' in self.df.columns:
            self.df['date'] = utils.normalize_datetime_series(self.df['date'])
        
        # 清理空值账号
        self.df = self.df[self.df['account_id'].notna()]
        self.df = self.df[self.df['account_id'] != '']
    
    @staticmethod
    def _normalize_account_id(acc) -> str:
        """【新增】标准化账号格式
        
        处理:
        - 科学计数法 (6.22260011e+18 → 6222600110000000000)
        - 浮点数 (4581240110555894.0 → 4581240110555894)
        - 空值
        """
        if pd.isna(acc):
            return ''
        
        acc_str = str(acc).strip()
        
        # 处理科学计数法
        if 'e' in acc_str.lower():
            try:
                acc_str = str(int(float(acc_str)))
            except:
                return ''
        
        # 处理带.0的浮点数
        if '.' in acc_str:
            try:
                acc_str = str(int(float(acc_str)))
            except:
                pass
        
        # 过滤无效账号
        if acc_str.lower() in ['nan', 'none', '']:
            return ''
        
        return acc_str
    
    def classify_accounts(self) -> Dict:
        """
        对所有账号进行分类（增强版）
        
        Returns:
            {账号: {'type': 类型, 'bank': 银行, 'confidence': 置信度}}
        """
        logger.info('正在分类银行账号...')
        
        accounts = self.df['account_id'].unique()
        
        for acc in accounts:
            if not acc:  # 跳过空值
                continue
            
            # 获取该账号的交易记录
            sub_df = self.df[self.df['account_id'] == acc]
            bank = sub_df['bank'].iloc[0] if 'bank' in sub_df.columns and len(sub_df) > 0 else ''
            bank = str(bank) if pd.notna(bank) else ''
            
            # 分类
            acc_type, confidence, reason = self._classify_single_account(acc, sub_df, bank)
            
            # 【新增】增强分析：交易特征
            transaction_features = self._analyze_transaction_features(sub_df)
            
            self.accounts_classification[acc] = {
                'type': acc_type,
                'bank': bank,
                'confidence': confidence,
                'reason': reason,
                'record_count': len(sub_df),
                'total_in': sub_df['income'].sum(),
                'total_out': sub_df['expense'].sum(),
                'features': transaction_features,  # 【新增】
            }
        
        # 统计
        type_counts = defaultdict(int)
        for acc, info in self.accounts_classification.items():
            type_counts[info['type']] += 1
        
        logger.info(f'账号分类完成: 主账户{type_counts["primary"]}个, '
                   f'理财账户{type_counts["wealth"]}个, '
                   f'内部账户{type_counts["internal"]}个, '
                   f'未知{type_counts["unknown"]}个')
        
        return self.accounts_classification
    
    def _classify_single_account(self, acc_str: str, sub_df: pd.DataFrame, bank: str) -> Tuple[str, float, str]:
        """
        对单个账号进行分类（增强版）
        
        Returns:
            (类型, 置信度, 原因)
        """
        digits = len(acc_str)
        
        # 方法1: 按银行规则匹配（优先级最高）
        if bank and bank in BANK_ACCOUNT_PATTERNS:
            for pattern, acc_type, desc in BANK_ACCOUNT_PATTERNS[bank]:
                if re.match(pattern, acc_str):
                    return (acc_type, 0.9, f'格式匹配: {desc}')
        
        # 方法2: 通用格式规则（保守策略）
        # 标准银行卡: 16-19位，以62/60/40开头
        if re.match(r'^(62|60|40)\d{14,17}$', acc_str):
            return ('primary', 0.7, '标准银行卡格式(16-19位)')
        
        # 【修改】超长账号不一定是理财，可能是企业账户
        # 结合交易特征判断
        if digits >= 20:
            # 检查是否有理财交易特征
            has_wealth_feature = self._has_wealth_transaction_feature(sub_df)
            if has_wealth_feature:
                return ('wealth', 0.6, '超长账号+理财交易特征')
            else:
                return ('unknown', 0.4, '超长账号(需进一步分析)')
        
        # 短账号(<=15位)通常是内部账号
        if digits <= 15 and not re.match(r'^6\d{14}$', acc_str):
            return ('internal', 0.5, '短账号(<=15位)')
        
        # 方法3: 交易特征分析
        all_descs = ' '.join(sub_df['description'].fillna('').astype(str).tolist())
        
        # 检查理财关键词
        for pattern in WEALTH_DESC_PATTERNS:
            if re.search(pattern, all_descs):
                return ('wealth', 0.65, f'含理财关键词: {pattern}')
        
        # 检查银证转账
        for pattern in SECURITIES_KEYWORDS:
            if re.search(pattern, all_descs):
                return ('securities', 0.7, f'银证转账特征: {pattern}')
        
        # 检查纯数字摘要（银行内部代码）
        descs = sub_df['description'].dropna().astype(str).tolist()
        numeric_count = sum(1 for d in descs if NUMERIC_DESC_PATTERN.match(d.strip()))
        if len(descs) > 0 and numeric_count / len(descs) > 0.5:
            return ('wealth', 0.55, '摘要多为数字代码')
        
        # 方法4: 收支平衡特征（自循环账户）
        total_in = sub_df['income'].sum()
        total_out = sub_df['expense'].sum()
        if total_in > 0 and total_out > 0:
            balance_ratio = abs(total_in - total_out) / max(total_in, total_out)
            if balance_ratio < 0.1:  # 收支差异<10%
                return ('internal', 0.5, '收支近乎平衡(自循环)')
        
        return ('unknown', 0.3, '无法确定')
    
    def _has_wealth_transaction_feature(self, sub_df: pd.DataFrame) -> bool:
        """【新增】检查是否有理财交易特征"""
        all_descs = ' '.join(sub_df['description'].fillna('').astype(str).tolist())
        
        for pattern in WEALTH_DESC_PATTERNS:
            if re.search(pattern, all_descs):
                return True
        
        return False
    
    def _analyze_transaction_features(self, sub_df: pd.DataFrame) -> Dict:
        """【新增】分析交易特征
        
        Returns:
            特征字典
        """
        features = {
            'has_round_amount': False,
            'has_interest_tail': False,
            'has_same_day_pair': False,
            'avg_amount': 0,
            'max_amount': 0,
            'large_tx_count': 0,
        }
        
        if sub_df.empty:
            return features
        
        # 金额特征分析
        amounts = []
        for _, row in sub_df.iterrows():
            amount = row.get('income', 0) or row.get('expense', 0)
            if amount and amount > 0:
                amounts.append(utils.format_amount(amount))
        
        if amounts:
            features['avg_amount'] = np.mean(amounts)
            features['max_amount'] = max(amounts)
            features['large_tx_count'] = sum(1 for a in amounts if a >= 100000)
            
            # 检查整万金额
            round_amounts = [a for a in amounts if a >= 10000 and a % 10000 == 0]
            features['has_round_amount'] = len(round_amounts) > 0
            
            # 检查含利息尾数的金额
            interest_tails = [a for a in amounts if a % 1 > 0 or (a % 10000 > 0 and a % 10000 < 1000)]
            features['has_interest_tail'] = len(interest_tails) > 0
        
        # 时间特征分析
        if 'date' in sub_df.columns and not sub_df['date'].isna().all():
            features['has_same_day_pair'] = self._detect_same_day_pairs(sub_df)
        
        return features
    
    def _detect_same_day_pairs(self, sub_df: pd.DataFrame) -> bool:
        """【新增】检测同一天收支配对"""
        try:
            df_day = sub_df.copy()
            df_day['day'] = df_day['date'].dt.date
            df_day['net'] = df_day['income'].fillna(0) - df_day['expense'].fillna(0)
            
            # 按天统计
            daily = df_day.groupby('day').agg({
                'income': 'sum',
                'expense': 'sum',
                'net': 'sum'
            })
            
            # 检查是否有天既有收入又有支出且金额接近
            for _, row in daily.iterrows():
                if row['income'] > 0 and row['expense'] > 0:
                    ratio = abs(row['income'] - row['expense']) / max(row['income'], row['expense'])
                    if ratio < 0.2:  # 差异<20%
                        return True
            
            return False
        except:
            return False
    
    def analyze_fund_flow(self) -> Dict:
        """
        分析主账户与理财子账号之间的资金流转（增强版）
        
        Returns:
            {
                'primary_accounts': [...],  # 主账户列表
                'wealth_accounts': [...],   # 理财账户列表
                'fund_flows': [...],        # 资金流转记录
                'wealth_summary': {...},    # 理财汇总
                'income_expense_pairs': [...],  # 【新增】收支配对
            }
        """
        if not self.accounts_classification:
            self.classify_accounts()
        
        logger.info('正在分析账户间资金流转...')
        
        # 按类型分组账户
        primary_accounts = [a for a, info in self.accounts_classification.items() 
                          if info['type'] == 'primary']
        wealth_accounts = [a for a, info in self.accounts_classification.items() 
                         if info['type'] in ('wealth', 'internal')]
        securities_accounts = [a for a, info in self.accounts_classification.items() 
                             if info['type'] == 'securities']
        
        # 分析资金流动
        fund_flows = []
        
        # 检测主账户到理财账户的转账
        for _, row in self.df.iterrows():
            acc = str(row.get('account_id', ''))
            counterparty = str(row.get('counterparty', ''))
            desc = str(row.get('description', ''))
            income = row.get('income', 0) or 0
            expense = row.get('expense', 0) or 0
            
            if acc in primary_accounts:
                # 主账户支出 -> 可能是购买理财
                if expense > 0:
                    # 检查是否流向理财
                    if any(k in desc for k in ['理财', '基金', '定期', '申购', '转存', '购买', '黄金份额']):
                        fund_flows.append({
                            'from_account': acc,
                            'to_account': 'wealth_product',
                            'amount': expense,
                            'date': row.get('date'),
                            'type': 'purchase',
                            'description': desc,
                            'confidence': 'high' if any(k in desc for k in ['理财', '黄金份额']) else 'medium'
                        })
                
                # 主账户收入 -> 可能是理财赎回
                if income > 0:
                    if any(k in desc for k in ['理财', '基金', '赎回', '到期', '分红', '利息']):
                        fund_flows.append({
                            'from_account': 'wealth_product',
                            'to_account': acc,
                            'amount': income,
                            'date': row.get('date'),
                            'type': 'redemption',
                            'description': desc,
                            'confidence': 'high'
                        })
            
            elif acc in wealth_accounts:
                # 理财账户收入 -> 可能是赎回
                if income > 0:
                    fund_flows.append({
                        'from_account': 'wealth_product',
                        'to_account': acc,
                        'amount': income,
                        'date': row.get('date'),
                        'type': 'redemption',
                        'description': desc,
                        'confidence': 'high'
                    })
                
                # 理财账户支出 -> 可能是购买
                if expense > 0:
                    fund_flows.append({
                        'from_account': acc,
                        'to_account': 'wealth_product',
                        'amount': expense,
                        'date': row.get('date'),
                        'type': 'purchase',
                        'description': desc,
                        'confidence': 'medium'
                    })
            
            elif acc in securities_accounts or any(k in desc for k in SECURITIES_KEYWORDS):
                # 银证转账
                if expense > 0:
                    fund_flows.append({
                        'from_account': acc,
                        'to_account': 'securities_account',
                        'amount': expense,
                        'date': row.get('date'),
                        'type': 'to_securities',
                        'description': desc,
                        'confidence': 'high'
                    })
                if income > 0:
                    fund_flows.append({
                        'from_account': 'securities_account',
                        'to_account': acc,
                        'amount': income,
                        'date': row.get('date'),
                        'type': 'from_securities',
                        'description': desc,
                        'confidence': 'high'
                    })
        
        # 【新增】检测收支配对
        self.income_expense_pairs = self._detect_income_expense_pairs()
        
        # 计算理财汇总
        wealth_summary = self._calculate_wealth_summary(wealth_accounts)
        
        return {
            'primary_accounts': primary_accounts,
            'wealth_accounts': wealth_accounts,
            'securities_accounts': securities_accounts,
            'fund_flows': fund_flows,
            'wealth_summary': wealth_summary,
            'income_expense_pairs': self.income_expense_pairs,  # 【新增】
        }
    
    def _detect_income_expense_pairs(self) -> List[Dict]:
        """【新增】检测收支配对（核心功能）
        
        检测同一天或相邻天的收入+支出配对
        这是识别理财操作的关键特征
        """
        pairs = []
        
        if 'date' not in self.df.columns or self.df['date'].isna().all():
            return pairs
        
        try:
            # 按日期分组
            df_clean = self.df[self.df['date'].notna()].copy()
            df_clean['date_only'] = df_clean['date'].dt.date
            
            # 只考虑大额交易（>=5万）
            df_clean['amount'] = df_clean['income'].fillna(0) + df_clean['expense'].fillna(0)
            df_large = df_clean[df_clean['amount'] >= 50000]
            
            # 按天统计
            daily_groups = df_large.groupby('date_only')
            
            for date, day_df in daily_groups:
                day_income = day_df[day_df['income'] > 0]
                day_expense = day_df[day_df['expense'] > 0]
                
                if len(day_income) > 0 and len(day_expense) > 0:
                    # 检查金额配对
                    for _, inc_row in day_income.iterrows():
                        for _, exp_row in day_expense.iterrows():
                            inc_amt = inc_row['income']
                            exp_amt = exp_row['expense']
                            
                            # 金额差异<20%
                            if inc_amt > 0 and exp_amt > 0:
                                diff_ratio = abs(inc_amt - exp_amt) / max(inc_amt, exp_amt)
                                if diff_ratio < 0.2:
                                    pairs.append({
                                        'date': date,
                                        'income_tx': {
                                            'account': inc_row.get('account_id', ''),
                                            'amount': inc_amt,
                                            'desc': inc_row.get('description', ''),
                                        },
                                        'expense_tx': {
                                            'account': exp_row.get('account_id', ''),
                                            'amount': exp_amt,
                                            'desc': exp_row.get('description', ''),
                                        },
                                        'diff_ratio': diff_ratio,
                                        'type': 'same_day_pair'
                                    })
            
            return pairs
        except Exception as e:
            logger.warning(f'收支配对检测失败: {e}')
            return []
    
    def _calculate_wealth_summary(self, wealth_accounts: List[str]) -> Dict:
        """计算理财汇总统计"""
        total_in = 0.0
        total_out = 0.0
        by_bank = defaultdict(lambda: {'in': 0.0, 'out': 0.0, 'accounts': []})
        
        for acc in wealth_accounts:
            if acc not in self.accounts_classification:
                continue
            info = self.accounts_classification[acc]
            total_in += info['total_in']
            total_out += info['total_out']
            
            bank = info['bank'] or '未知银行'
            by_bank[bank]['in'] += info['total_in']
            by_bank[bank]['out'] += info['total_out']
            by_bank[bank]['accounts'].append(acc)
        
        return {
            'total_wealth_in': total_in,
            'total_wealth_out': total_out,
            'net_wealth_change': total_in - total_out,
            'by_bank': dict(by_bank),
            'account_count': len(wealth_accounts)
        }
    
    def get_transaction_classification(self) -> pd.DataFrame:
        """【新增】为每笔交易打分类标签
        
        Returns:
            添加了'category'列的DataFrame
        """
        if not self.accounts_classification:
            self.classify_accounts()
        
        df_result = self.df.copy()
        df_result['category'] = 'unknown'
        df_result['category_confidence'] = 0.0
        df_result['category_reason'] = ''
        
        for idx, row in df_result.iterrows():
            acc = str(row.get('account_id', ''))
            desc = str(row.get('description', ''))
            income = row.get('income', 0) or 0
            expense = row.get('expense', 0) or 0
            
            if acc in self.accounts_classification:
                acc_type = self.accounts_classification[acc]['type']
                acc_confidence = self.accounts_classification[acc]['confidence']
                
                # 基于账户类型和交易特征分类
                if acc_type == 'wealth':
                    if income > 0:
                        df_result.at[idx, 'category'] = 'wealth_redemption'
                        df_result.at[idx, 'category_confidence'] = acc_confidence
                        df_result.at[idx, 'category_reason'] = '理财账户收入'
                    elif expense > 0:
                        df_result.at[idx, 'category'] = 'wealth_purchase'
                        df_result.at[idx, 'category_confidence'] = acc_confidence
                        df_result.at[idx, 'category_reason'] = '理财账户支出'
                
                elif acc_type == 'securities':
                    if income > 0:
                        df_result.at[idx, 'category'] = 'securities_inflow'
                    elif expense > 0:
                        df_result.at[idx, 'category'] = 'securities_outflow'
                    df_result.at[idx, 'category_confidence'] = acc_confidence
                    df_result.at[idx, 'category_reason'] = '银证转账'
                
                elif acc_type == 'primary':
                    # 主账户需要更详细的判断
                    if any(k in desc for k in ['理财', '黄金份额', '赎回', '到期']):
                        if income > 0:
                            df_result.at[idx, 'category'] = 'wealth_redemption'
                        else:
                            df_result.at[idx, 'category'] = 'wealth_purchase'
                        df_result.at[idx, 'category_confidence'] = 0.85
                        df_result.at[idx, 'category_reason'] = f'关键词匹配: {desc[:20]}'
                    elif any(k in desc for k in SECURITIES_KEYWORDS):
                        if income > 0:
                            df_result.at[idx, 'category'] = 'securities_inflow'
                        else:
                            df_result.at[idx, 'category'] = 'securities_outflow'
                        df_result.at[idx, 'category_confidence'] = 0.9
                        df_result.at[idx, 'category_reason'] = f'银证转账: {desc[:20]}'
        
        return df_result
    
    def generate_report(self) -> str:
        """生成理财账户分析报告（增强版）"""
        if not self.accounts_classification:
            self.classify_accounts()
        
        flow_result = self.analyze_fund_flow()
        
        report = []
        report.append(f"\n{'='*70}")
        report.append(f"【{self.entity_name or '对象'} 银行理财账户深度分析报告】")
        report.append(f"{'='*70}")
        
        # 1. 账户概览
        type_counts = defaultdict(int)
        for acc, info in self.accounts_classification.items():
            type_counts[info['type']] += 1
        
        report.append(f"\n一、账户概览")
        report.append(f"   总账号数: {len(self.accounts_classification)}")
        report.append(f"   - 主力账户: {type_counts['primary']} 个（日常收支用）")
        report.append(f"   - 理财账户: {type_counts['wealth']} 个（理财/基金/定期）")
        report.append(f"   - 内部账户: {type_counts['internal']} 个（银行内部划转）")
        report.append(f"   - 证券账户: {type_counts['securities']} 个（银证转账）")
        report.append(f"   - 未知类型: {type_counts['unknown']} 个")
        
        # 2. 【新增】收支配对检测
        pairs = flow_result.get('income_expense_pairs', [])
        if pairs:
            report.append(f"\n二、收支配对检测（疑似理财操作）")
            report.append(f"   发现 {len(pairs)} 组收支配对")
            for i, pair in enumerate(pairs[:5], 1):
                report.append(f"\n   {i}. 日期: {pair['date']}")
                report.append(f"      收入: {pair['income_tx']['amount']:,.2f} ({pair['income_tx']['desc'][:20]})")
                report.append(f"      支出: {pair['expense_tx']['amount']:,.2f} ({pair['expense_tx']['desc'][:20]})")
                report.append(f"      差异: {pair['diff_ratio']*100:.1f}%")
        
        # 3. 主力账户明细
        report.append(f"\n三、主力账户明细")
        for acc, info in sorted(self.accounts_classification.items(), 
                               key=lambda x: -x[1]['total_in']):
            if info['type'] == 'primary':
                features = info.get('features', {})
                feature_str = ""
                if features.get('has_round_amount'):
                    feature_str += " [整万金额]"
                if features.get('has_same_day_pair'):
                    feature_str += " [收支配对]"
                
                report.append(f"   📌 {acc}")
                report.append(f"      银行: {info['bank']} | 记录: {info['record_count']}条")
                report.append(f"      流入: {info['total_in']/10000:.1f}万 | 流出: {info['total_out']/10000:.1f}万")
                if feature_str:
                    report.append(f"      特征:{feature_str}")
        
        # 4. 理财账户统计
        ws = flow_result['wealth_summary']
        report.append(f"\n四、理财资金流转统计")
        report.append(f"   理财/内部账户共 {ws['account_count']} 个")
        report.append(f"   总流入: {ws['total_wealth_in']/10000:.1f} 万元")
        report.append(f"   总流出: {ws['total_wealth_out']/10000:.1f} 万元")
        report.append(f"   净变化: {ws['net_wealth_change']/10000:.1f} 万元")
        
        report.append(f"\n   按银行分布:")
        for bank, stats in ws['by_bank'].items():
            report.append(f"   - {bank}: {len(stats['accounts'])}个账户, "
                        f"流入{stats['in']/10000:.1f}万, 流出{stats['out']/10000:.1f}万")
        
        # 5. 理财产品操作明细
        report.append(f"\n五、理财账户明细（按资金规模排序）")
        wealth_list = [(acc, info) for acc, info in self.accounts_classification.items()
                      if info['type'] in ('wealth', 'internal')]
        wealth_list.sort(key=lambda x: -x[1]['total_in'])
        
        for acc, info in wealth_list[:15]:
            report.append(f"   💰 {acc[:25]:25s}")
            report.append(f"      {info['bank']:10s} | 记录{info['record_count']:4d}条 | "
                        f"流入{info['total_in']/10000:8.1f}万 | 流出{info['total_out']/10000:8.1f}万")
            report.append(f"      识别依据: {info['reason']}")
        
        if len(wealth_list) > 15:
            report.append(f"   ... 还有 {len(wealth_list)-15} 个理财账户")
        
        return '\n'.join(report)


def analyze_wealth_accounts(df: pd.DataFrame, entity_name: str = None) -> Dict:
    """
    便捷函数: 分析个人理财账户结构（增强版）
    
    Args:
        df: 交易数据DataFrame
        entity_name: 实体名称
        
    Returns:
        分析结果字典
    """
    analyzer = WealthAccountAnalyzer(df, entity_name)
    classification = analyzer.classify_accounts()
    flow_result = analyzer.analyze_fund_flow()
    report = analyzer.generate_report()
    
    # 【新增】返回带分类的交易数据
    classified_df = analyzer.get_transaction_classification()
    
    return {
        'classification': classification,
        'flow_result': flow_result,
        'report': report,
        'analyzer': analyzer,
        'classified_df': classified_df,  # 【新增】
        'income_expense_pairs': flow_result.get('income_expense_pairs', []),  # 【新增】
    }


# 【新增】与主流程集成的接口函数
def integrate_with_income_analyzer(df: pd.DataFrame, entity_name: str = None) -> pd.DataFrame:
    """
    与 income_analyzer.py 集成的接口
    
    在 income_analyzer 的交易分类流程中调用此函数
    为每笔交易添加理财分类标签
    
    Args:
        df: 交易数据DataFrame
        entity_name: 实体名称
        
    Returns:
        添加了'category'列的DataFrame
    """
    try:
        analyzer = WealthAccountAnalyzer(df, entity_name)
        classified_df = analyzer.get_transaction_classification()
        
        logger.info(f'[WealthAccountAnalyzer] {entity_name} 分类完成: '
                   f'{len(classified_df[classified_df["category"] != "unknown"])} 笔交易已识别')
        
        return classified_df
    except Exception as e:
        logger.error(f'[WealthAccountAnalyzer] 分类失败: {e}')
        # 失败时返回原数据
        df['category'] = 'unknown'
        df['category_confidence'] = 0.0
        df['category_reason'] = f'分析失败: {str(e)}'
        return df


if __name__ == '__main__':
    # 测试
    import sys
    import os
    
    # 从命令行参数获取文件路径
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        test_file = os.path.join('output', 'cleaned_data', '个人', '示例_合并流水.xlsx')
    
    # 从文件路径提取人员名称
    filename = os.path.basename(test_file)
    match = re.match(r'(.+?)_合并流水\.xlsx', filename)
    if match:
        person_name = match.group(1)
    else:
        person_name = '测试人员'
    
    if not os.path.exists(test_file):
        print(f"错误: 文件不存在: {test_file}")
        print(f"请提供正确的文件路径，例如:")
        print(f"  python wealth_account_analyzer.py output/cleaned_data/个人/某人_合并流水.xlsx")
        sys.exit(1)
    
    # 加载测试数据
    df = pd.read_excel(test_file)
    
    result = analyze_wealth_accounts(df, person_name)
    print(result['report'])
    
    # 【新增】输出分类统计
    classified_df = result['classified_df']
    print(f"\n\n【交易分类统计】")
    print(classified_df['category'].value_counts())
