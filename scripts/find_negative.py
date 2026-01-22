#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查找负数余额账户"""

import json

def main():
    with open('./output/analysis_results_cache.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    profiles = data.get('profiles', {})
    
    print('=== 查找负数余额账户 ===\n')
    
    for name, profile in profiles.items():
        for acc in profile.get('bankAccounts', []):
            balance = acc.get('last_balance', 0)
            if balance < 0:
                print(f'【{name}】')
                print(f'  银行: {acc.get("bank_name", "")}')
                print(f'  账号: {acc.get("account_number", "")}')
                print(f'  余额: ¥{balance:,.2f}')
                print(f'  类型: {acc.get("account_type", "")}')
                print(f'  总收入: ¥{acc.get("total_income", 0):,.2f}')
                print(f'  总支出: ¥{acc.get("total_expense", 0):,.2f}')
                print(f'  has_balance_data: {acc.get("has_balance_data", "N/A")}')
                print()

if __name__ == '__main__':
    main()
