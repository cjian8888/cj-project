import pandas as pd
import re

def analyze_account_types(file_path):
    print(f"Analyzing: {file_path}")
    df = pd.read_excel(file_path)
    
    # 映射列名
    col_map = {
        '交易时间': 'date',
        '收入(元)': 'income',
        '支出(元)': 'expense',
        '交易对手': 'counterparty',
        '交易摘要': 'description',
        '本方账号': 'account_id',
        '余额(元)': 'balance'
    }
    df = df.rename(columns=col_map)
    
    accounts = df['account_id'].dropna().unique()
    print(f"Total Unique Accounts: {len(accounts)}")
    
    account_stats = []
    
    for acct in accounts:
        # 获取该账号的交易
        sub_df = df[df['account_id'] == acct]
        
        # 统计特征
        tx_count = len(sub_df)
        income_sum = sub_df['income'].sum()
        expense_sum = sub_df['expense'].sum()
        
        # 关键词特征
        desc_text = ' '.join(sub_df['description'].fillna('').astype(str).tolist())
        cp_text = ' '.join(sub_df['counterparty'].fillna('').astype(str).tolist())
        full_text = desc_text + ' ' + cp_text
        
        is_wealth = any(k in full_text for k in ['理财', '基金', '赎回', '红利', '结息', '证券', '银证'])
        is_daily = any(k in full_text for k in ['消费', 'POS', 'ATM', '取款', '工资', '转账'])
        
        # 账号长度特征
        acct_str = str(acct)
        acct_len = len(acct_str)
        is_card_format = re.match(r'^62\d{14,17}$', acct_str) is not None
        
        account_stats.append({
            'account': acct,
            'len': acct_len,
            'count': tx_count,
            'is_card_format': is_card_format,
            'is_wealth_related': is_wealth,
            'is_daily_related': is_daily,
            'sample_desc': sub_df['description'].iloc[0] if not sub_df.empty else ''
        })
        
    # 转换为DataFrame打印
    stats_df = pd.DataFrame(account_stats)
    print("\nPotential Physical Cards (Standard Format + Daily Activity):")
    cards = stats_df[stats_df['is_card_format']]
    print(cards[['account', 'count', 'is_wealth_related', 'is_daily_related']])
    
    print("\nPotential Internal/Wealth Accounts (Non-Standard or Pure Wealth):")
    others = stats_df[~stats_df['is_card_format']]
    print(others[['account', 'len', 'count', 'is_wealth_related', 'is_daily_related', 'sample_desc']].head(20))

if __name__ == "__main__":
    analyze_account_types('output/cleaned_data/个人/施灵_合并流水.xlsx')
