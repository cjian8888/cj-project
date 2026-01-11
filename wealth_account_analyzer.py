#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
理财账户分析模块 - 资金穿透与关联排查系统
专门处理银行理财产品导致的多子账号问题

功能:
1. 自动识别理财子账号（根据各银行账号格式规律）
2. 分析账户间资金流转关系（主账户 <-> 理财子账号）
3. 计算真实理财规模（剔除内部循环）
4. 生成理财结构报告
"""

import pandas as pd
import re
from typing import Dict, List, Tuple
from collections import defaultdict
import utils

logger = utils.setup_logger(__name__)


# ============= 银行账号格式规则 =============
# 基于实际数据分析总结的各银行账号特征

BANK_ACCOUNT_PATTERNS = {
    # 银行名: [(正则模式, 账号类型, 说明), ...]
    '招商银行': [
        (r'^1213\d{11}$', 'wealth', '招行理财子账号(15位)'),
        (r'^1063\d{11}$', 'wealth', '招行理财专户(15位)'),
        (r'^621\d{13,16}$', 'primary', '招行银行卡'),
    ],
    '民生银行': [
        (r'^50\d{18}$', 'wealth', '民生理财账户(20位50开头)'),
        (r'^51\d{18}$', 'wealth', '民生理财账户(20位51开头)'),
        (r'^0202\d{12}$', 'primary', '民生储蓄卡'),
        (r'^6226\d{12}$', 'primary', '民生银行卡'),
    ],
    '浦发银行': [
        (r'^970\d{17}$', 'wealth', '浦发理财账户(20位97开头)'),
        (r'^6217\d{12,15}$', 'primary', '浦发银行卡'),
    ],
    '交通银行': [
        (r'^310\d{18,}$', 'wealth', '交行内部理财户(21位+)'),
        (r'^622[256]\d{12,16}$', 'primary', '交行银行卡'),
    ],
    '工商银行': [
        (r'^100\d{14}$', 'internal', '工行内部账号(17位100开头)'),
        (r'^12[024]\d{14}$', 'internal', '工行内部账号(17位12x开头)'),
        (r'^6222\d{15}$', 'primary', '工行银行卡'),
    ],
    '光大银行': [
        (r'^62266\d{11}$', 'primary', '光大银行卡'),
        (r'^62267\d{11}$', 'primary', '光大电子账户'),
    ],
    '中信银行': [
        (r'^6217\d{12}$', 'primary', '中信银行卡'),
    ],
}

# 通用理财特征正则
WEALTH_DESC_PATTERNS = [
    r'理财', r'基金', r'定期', r'定存', r'大额存单', r'结息', r'利息',
    r'分红', r'赎回', r'申购', r'转存', r'活期宝', r'如意宝',
    r'固收', r'通知存款', r'产品', r'到期', r'续存',
    r'D\d{20,}',  # 理财产品代码如 D310902355643000045996...
    r'F[A-Z]{2}\d{6}',  # 基金代码如 FSG211212A
]

# 纯数字摘要（银行内部代码）
NUMERIC_DESC_PATTERN = re.compile(r'^[\d]{1,4}$')


class WealthAccountAnalyzer:
    """银行理财账户分析器"""
    
    def __init__(self, df: pd.DataFrame, entity_name: str = None):
        """
        初始化分析器
        
        Args:
            df: 包含交易数据的DataFrame
            entity_name: 实体名称（人员）
        """
        self.df = df.copy()
        self.entity_name = entity_name
        
        # 标准化列名
        self._normalize_columns()
        
        # 账号分类结果
        self.accounts_classification = {}
        # 账号统计
        self.account_stats = {}
        # 账号关系图
        self.account_relations = []
        
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
        
        # 确保account_id列存在（即使为空）
        if 'account_id' not in self.df.columns:
            self.df['account_id'] = ''
    
    def classify_accounts(self) -> Dict:
        """
        对所有账号进行分类
        
        Returns:
            {账号: {'type': 类型, 'bank': 银行, 'confidence': 置信度}}
        """
        logger.info('正在分类银行账号...')
        
        accounts = self.df['account_id'].dropna().unique()
        
        for acc in accounts:
            acc_str = str(acc).strip()
            if not acc_str or acc_str.lower() == 'nan':
                continue
            
            # 获取该账号的交易记录
            sub_df = self.df[self.df['account_id'] == acc]
            bank = sub_df['bank'].iloc[0] if 'bank' in sub_df.columns and len(sub_df) > 0 else ''
            
            # 分类
            acc_type, confidence, reason = self._classify_single_account(acc_str, sub_df, bank)
            
            self.accounts_classification[acc_str] = {
                'type': acc_type,
                'bank': bank,
                'confidence': confidence,
                'reason': reason,
                'record_count': len(sub_df),
                'total_in': sub_df['income'].sum(),
                'total_out': sub_df['expense'].sum(),
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
        对单个账号进行分类
        
        Returns:
            (类型, 置信度, 原因)
        """
        # 方法1: 按银行规则匹配
        if bank and bank in BANK_ACCOUNT_PATTERNS:
            for pattern, acc_type, desc in BANK_ACCOUNT_PATTERNS[bank]:
                if re.match(pattern, acc_str):
                    return (acc_type, 0.9, f'格式匹配: {desc}')
        
        # 方法2: 通用格式规则
        digits = len(acc_str)
        
        # 标准银行卡: 16-19位，以62/60开头
        if re.match(r'^(62|60)\d{14,17}$', acc_str):
            return ('primary', 0.8, '标准银行卡格式')
        
        # 超长账号(20位+)通常是理财
        if digits >= 20:
            return ('wealth', 0.7, '超长账号(>=20位)')
        
        # 短账号(<=15位)通常是内部账号
        if digits <= 15 and not re.match(r'^6\d{14}$', acc_str):
            return ('internal', 0.6, '短账号(<=15位)')
        
        # 方法3: 交易特征分析
        all_descs = ' '.join(sub_df['description'].fillna('').astype(str).tolist())
        
        # 检查理财关键词
        for pattern in WEALTH_DESC_PATTERNS:
            if re.search(pattern, all_descs):
                return ('wealth', 0.7, f'含理财关键词: {pattern}')
        
        # 检查纯数字摘要（银行内部代码）
        descs = sub_df['description'].dropna().astype(str).tolist()
        numeric_count = sum(1 for d in descs if NUMERIC_DESC_PATTERN.match(d.strip()))
        if len(descs) > 0 and numeric_count / len(descs) > 0.5:
            return ('wealth', 0.6, '摘要多为数字代码')
        
        # 方法4: 收支平衡特征（自循环账户）
        total_in = sub_df['income'].sum()
        total_out = sub_df['expense'].sum()
        if total_in > 0 and total_out > 0:
            balance_ratio = abs(total_in - total_out) / max(total_in, total_out)
            if balance_ratio < 0.1:  # 收支差异<10%
                return ('internal', 0.5, '收支近乎平衡(自循环)')
        
        return ('unknown', 0.3, '无法确定')
    
    def analyze_fund_flow(self) -> Dict:
        """
        分析主账户与理财子账号之间的资金流转
        
        Returns:
            {
                'primary_accounts': [...],  # 主账户列表
                'wealth_accounts': [...],   # 理财账户列表
                'fund_flows': [...],        # 资金流转记录
                'wealth_summary': {...}     # 理财汇总
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
        
        # 分析资金流动
        fund_flows = []
        
        # 检测主账户到理财账户的转账
        for _, row in self.df.iterrows():
            acc = str(row.get('account_id', ''))
            counterparty = str(row.get('counterparty', ''))
            desc = str(row.get('description', ''))
            
            # 检查是否是账户间划转
            if acc in primary_accounts:
                # 主账户支出 -> 可能是购买理财
                if row['expense'] > 0:
                    # 检查是否流向理财
                    if any(k in desc for k in ['理财', '基金', '定期', '申购', '转存', '购买']):
                        fund_flows.append({
                            'from_account': acc,
                            'to_account': 'wealth_product',
                            'amount': row['expense'],
                            'date': row.get('date'),
                            'type': 'purchase',
                            'description': desc
                        })
            
            elif acc in wealth_accounts:
                # 理财账户收入 -> 可能是赎回
                if row['income'] > 0:
                    fund_flows.append({
                        'from_account': 'wealth_product',
                        'to_account': acc,
                        'amount': row['income'],
                        'date': row.get('date'),
                        'type': 'redemption',
                        'description': desc
                    })
        
        # 计算理财汇总
        wealth_summary = self._calculate_wealth_summary(wealth_accounts)
        
        return {
            'primary_accounts': primary_accounts,
            'wealth_accounts': wealth_accounts,
            'fund_flows': fund_flows,
            'wealth_summary': wealth_summary
        }
    
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
    
    def generate_report(self) -> str:
        """生成理财账户分析报告"""
        
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
        report.append(f"   - 未知类型: {type_counts['unknown']} 个")
        
        # 2. 主力账户明细
        report.append(f"\n二、主力账户明细")
        for acc, info in sorted(self.accounts_classification.items(), 
                               key=lambda x: -x[1]['total_in']):
            if info['type'] == 'primary':
                report.append(f"   📌 {acc}")
                report.append(f"      银行: {info['bank']} | 记录: {info['record_count']}条")
                report.append(f"      流入: {info['total_in']/10000:.1f}万 | 流出: {info['total_out']/10000:.1f}万")
        
        # 3. 理财账户统计
        ws = flow_result['wealth_summary']
        report.append(f"\n三、理财资金流转统计")
        report.append(f"   理财/内部账户共 {ws['account_count']} 个")
        report.append(f"   总流入: {ws['total_wealth_in']/10000:.1f} 万元")
        report.append(f"   总流出: {ws['total_wealth_out']/10000:.1f} 万元")
        report.append(f"   净变化: {ws['net_wealth_change']/10000:.1f} 万元")
        
        report.append(f"\n   按银行分布:")
        for bank, stats in ws['by_bank'].items():
            report.append(f"   - {bank}: {len(stats['accounts'])}个账户, "
                        f"流入{stats['in']/10000:.1f}万, 流出{stats['out']/10000:.1f}万")
        
        # 4. 理财产品操作明细
        report.append(f"\n四、理财账户明细（按资金规模排序）")
        wealth_list = [(acc, info) for acc, info in self.accounts_classification.items()
                      if info['type'] in ('wealth', 'internal')]
        wealth_list.sort(key=lambda x: -x[1]['total_in'])
        
        for acc, info in wealth_list[:15]:  # 显示前15个
            report.append(f"   💰 {acc[:25]:25s}")
            report.append(f"      {info['bank']:10s} | 记录{info['record_count']:4d}条 | "
                        f"流入{info['total_in']/10000:8.1f}万 | 流出{info['total_out']/10000:8.1f}万")
            report.append(f"      识别依据: {info['reason']}")
        
        if len(wealth_list) > 15:
            report.append(f"   ... 还有 {len(wealth_list)-15} 个理财账户")
        
        return '\n'.join(report)


def analyze_wealth_accounts(df: pd.DataFrame, entity_name: str = None) -> Dict:
    """
    便捷函数: 分析个人理财账户结构
    
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
    
    return {
        'classification': classification,
        'flow_result': flow_result,
        'report': report,
        'analyzer': analyzer
    }


if __name__ == '__main__':
    # 测试
    import sys
    
    # 加载测试数据
    df = pd.read_excel('d:/CJ/project/output/cleaned_data/个人/施灵_合并流水.xlsx')
    
    result = analyze_wealth_accounts(df, '施灵')
    print(result['report'])
