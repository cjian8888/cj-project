#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""深度分析各银行理财账号模式"""

import pandas as pd
import re
from collections import defaultdict

# 加载数据
df = pd.read_excel('d:/CJ/project/output/cleaned_data/个人/施灵_合并流水.xlsx')

print("="*80)
print("银行理财账号模式深度分析")
print("="*80)

# 按银行分组分析
banks = df['所属银行'].dropna().unique()

for bank in banks:
    bank_df = df[df['所属银行'] == bank]
    accounts = bank_df['本方账号'].dropna().unique()
    
    print(f"\n{'='*60}")
    print(f"【{bank}】 共 {len(accounts)} 个账号, {len(bank_df)} 条记录")
    print(f"{'='*60}")
    
    # 分析账号格式
    for acc in accounts:
        acc_str = str(acc)
        sub = bank_df[bank_df['本方账号']==acc]
        
        # 收集摘要
        descs = sub['交易摘要'].dropna().unique()[:5]
        
        # 判断账号类型
        acc_type = "未知"
        
        # 位数分析
        digits = len(acc_str)
        
        # 标准银行卡: 16-19位，以62/60开头
        if re.match(r'^(62|60)\d{14,17}$', acc_str):
            acc_type = "🏦 银行卡"
        # 短账号（内部/理财）
        elif digits <= 15:
            acc_type = "📊 内部账号"
        # 超长账号
        elif digits >= 20:
            acc_type = "💰 理财/内部"
        # 50/51开头（民生理财）
        elif re.match(r'^5[01]\d+$', acc_str):
            acc_type = "💰 理财账号"
        else:
            acc_type = "❓ 待识别"
        
        # 交易特征分析
        income_sum = sub['收入(元)'].sum()
        expense_sum = sub['支出(元)'].sum()
        net = income_sum - expense_sum
        
        # 理财特征
        all_descs = ' '.join(sub['交易摘要'].fillna('').astype(str).tolist())
        wealth_kw = ['理财', '基金', '定期', '定存', '结息', '利息', '分红', '赎回', '申购', '转存', '活期宝', '大额存单', '通知存款', '固收', '产品']
        has_wealth = any(k in all_descs for k in wealth_kw)
        
        # 自转特征（对手方包含本人名字）
        counterparties = sub['交易对手'].fillna('').astype(str).tolist()
        has_self = '施灵' in ' '.join(counterparties)
        
        if has_wealth:
            acc_type = "💰 " + acc_type.split()[-1] if "💰" not in acc_type else acc_type
        
        # 简化输出
        if len(sub) >= 10:  # 只显示有一定交易量的
            print(f"\n  {acc_type} {acc_str}")
            print(f"      记录: {len(sub):4d}条 | 收入: {income_sum/10000:8.1f}万 | 支出: {expense_sum/10000:8.1f}万 | 净额: {net/10000:8.1f}万")
            print(f"      摘要样本: {list(descs)[:3]}")
            if has_wealth:
                print(f"      ⚠️ 含理财关键词")
            if has_self:
                print(f"      🔄 含自转交易")


print("\n\n" + "="*80)
print("账号模式总结 - 用于自动识别规则")
print("="*80)

# 收集银行的账号格式特征
bank_patterns = {}
for bank in banks:
    bank_df = df[df['所属银行'] == bank]
    accounts = bank_df['本方账号'].dropna().unique()
    
    patterns = defaultdict(list)
    for acc in accounts:
        acc_str = str(acc)
        # 提取前缀和长度特征
        prefix = acc_str[:2] if len(acc_str) >= 2 else acc_str
        length = len(acc_str)
        key = f"{prefix}..({length}位)"
        patterns[key].append(acc_str)
    
    if patterns:
        bank_patterns[bank] = patterns

for bank, patterns in bank_patterns.items():
    print(f"\n{bank}:")
    for pattern, accs in sorted(patterns.items(), key=lambda x: -len(x[1])):
        sample = accs[0][:20] + "..." if len(accs[0]) > 20 else accs[0]
        print(f"  {pattern:20s} x{len(accs):2d} 例: {sample}")
