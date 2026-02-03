#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证银行账户余额提取是否成功 - 修正版"""

import json

def main():
    with open('./output/analysis_results_cache.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    profiles = data.get('profiles', {})
    
    print('=== 银行账户余额验证 (修正版) ===\n')
    
    total_with_balance = 0
    total_without_balance = 0
    
    for name, profile in profiles.items():
        bank_accounts = profile.get('bankAccounts', [])
        if not bank_accounts:
            continue
            
        print(f'【{name}】({len(bank_accounts)}个账户):')
        
        for acc in bank_accounts[:5]:  # 显示前5个
            balance = acc.get('last_balance', 0)
            has_data = acc.get('has_balance_data', 'N/A')
            bank = acc.get('bank_name', '未知银行')
            acct_num = acc.get('account_number', '')
            
            # 只显示后4位
            acct_display = f"*{acct_num[-4:]}" if len(acct_num) >= 4 else acct_num
            
            if has_data:
                status = '✓ 真实余额'
                total_with_balance += 1
            else:
                status = '✗ 无数据'
                total_without_balance += 1
            
            # 检查是否有负数（不应该有了）
            if balance < 0:
                status += ' ⚠️ 异常负值!'
            
            print(f'  {bank} {acct_display}: ¥{balance:,.2f} {status}')
        
        if len(bank_accounts) > 5:
            print(f'  ... 还有 {len(bank_accounts) - 5} 个账户')
        print()
    
    print('=== 汇总统计 ===')
    print(f'有真实余额数据: {total_with_balance}')
    print(f'无余额数据(显示0): {total_without_balance}')
    
    # 检查是否还有负数
    all_balances = []
    for p in profiles.values():
        for acc in p.get('bankAccounts', []):
            all_balances.append(acc.get('last_balance', 0))
    
    negative_count = len([b for b in all_balances if b < 0])
    if negative_count > 0:
        print(f'\n⚠️ 警告: 仍有 {negative_count} 个账户余额为负数!')
    else:
        print(f'\n✓ 所有余额均为非负数')

if __name__ == '__main__':
    main()
