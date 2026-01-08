
import pandas as pd
import config
import utils
import financial_profiler
import account_analyzer

def analyze_gap():
    # Load specific file for Shi Ling
    # Searching for Shi Ling's file in data dir
    import os
    data_dir = r"d:\CJ\project\data"
    
    # Load specific file for Shi Ling from OUTPUT directory (Cleaned)
    import os
    target_file = r"d:\CJ\project\output\cleaned_data\个人\施灵_合并流水.xlsx"
    
    if not os.path.exists(target_file):
        print(f"Cleaned data file not found: {target_file}")
        # Fallback to searching in output folder just in case
        return

    print(f"Loading cleaned file: {target_file}...")
    try:
        df = pd.read_excel(target_file, engine='openpyxl')
    except Exception as e:
        print(f"Error reading {target_file}: {e}")
        return
        
    print(f"Columns found: {df.columns.tolist()}")
    
    # Cleaned data usually has 'date', 'income', 'expense', etc. or Chinese standard names
    # Mapping based on typical cleaner output
    column_mapping = {
        '交易时间': 'date', '交易日期': 'date', '日期': 'date',
        '交易金额': 'amount', '金额': 'amount',
        '交易摘要': 'description', '摘要': 'description',
        '对手方名称': 'counterparty', '对方户名': 'counterparty', '交易对手': 'counterparty', '对手方': 'counterparty',
        '收入': 'income', '支出': 'expense',
        '借方发生额': 'expense', '贷方发生额': 'income',
        '收入(元)': 'income', '支出(元)': 'expense',
        '交易分类': 'category', '来源文件': 'source_file', '余额(元)': 'balance'
    }
    df.rename(columns=column_mapping, inplace=True)
    
    # Clean Data
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    # If income/expense are strings, clean them
    if 'income' in df.columns:
        df['income'] = pd.to_numeric(df['income'], errors='coerce').fillna(0)
    else:
        df['income'] = 0
        
    if 'expense' in df.columns:
        df['expense'] = pd.to_numeric(df['expense'], errors='coerce').fillna(0)
    else:
        df['expense'] = 0
    df['description'] = df['description'].astype(str).fillna('')
    df['counterparty'] = df['counterparty'].astype(str).fillna('')
    df['category'] = df['category'].astype(str).fillna('')
    df['source_file'] = df['source_file'].astype(str).fillna('')
    if '本方账号' in df.columns:
        df['my_account'] = df['本方账号'].astype(str).fillna('')
    else:
        df['my_account'] = ''

    print(f"Total Transactions: {len(df)}")
    print(f"Total Income: {df['income'].sum():,.2f}")
    
    # 1. Identify Wealth Management / Self Accounts (Logic from financial_profiler)
    print("Analyzing Wealth Management & Self Transfers...")
    wealth_res = financial_profiler.analyze_wealth_management(df, "施灵")
    
    # Mark rows based on wealth analysis
    # Since financial_profiler returns a summary/list of dicts, we need to map back to DF indices is hard if we don't have IDs.
    # PRO TIP: The financial_profiler logic iterates rows. We sort of need to re-run that logic on the DF directly to tag rows.
    # To be precise, I will replicate the core tagging logic here or just assume I need to pinpoint the "Other" bucket.
    
    # Let's perform a direct tagging here to be transparent
    df['type'] = 'unknown'
    
    # A. Identify Self Transfers (Strict)
    # Using account_analyzer logic
    my_accounts = set()
    try:
        acct_info = account_analyzer.classify_accounts(df)
        my_accounts.update(acct_info['physical_cards'])
        my_accounts.update(acct_info['virtual_accounts'])
        my_accounts.update(acct_info['wealth_accounts'])
    except:
        pass
        
    for i, row in df.iterrows():
        if row['income'] <= 0: continue
        
        desc = str(row['description'])
        cp = str(row['counterparty'])
        
        # 1. Self Transfer
        if "施灵" in cp or cp in my_accounts or utils.contains_keywords(cp+desc, ['本人', '户主', '卡卡转账', '自行转账']):
            df.at[i, 'type'] = 'self_transfer'
            continue
            
        # 2. Wealth Redemption / Income
        # Keywords from financial_profiler
        is_wealth = False
        if utils.contains_keywords(desc+cp, config.WEALTH_MANAGEMENT_KEYWORDS):
            is_wealth = True
        elif cp in ['', '-', 'nan', 'NaN'] and (utils.contains_keywords(desc, ['到期', '赎回', '结清', '自动', '归还']) or len(desc)>8): # code pattern
            is_wealth = True
            
        if is_wealth:
            # Check yield vs principal
            if utils.contains_keywords(desc, ['利息', '结息', '分红', '收益', '红利']):
                df.at[i, 'type'] = 'wealth_income'
            else:
                df.at[i, 'type'] = 'wealth_redemption'
            continue
            
        # 3. Loans / Refunds
        if utils.contains_keywords(desc, ['放款', '贷款发放', '个贷发放']):
            df.at[i, 'type'] = 'loan_inflow'
            continue
        if utils.contains_keywords(desc, ['退款', '冲正', '退回', '撤销']):
            df.at[i, 'type'] = 'refund_inflow'
            continue
            
    # Now, Salary Logic (The one we just updated)
    # We need to apply the SAME logic for whitelist
    learned_salary_payers = set(config.KNOWN_SALARY_PAYERS + config.USER_DEFINED_SALARY_PAYERS)
    learned_salary_payers.add("上海航天化工应用研究所")
    
    WEALTH_ENTITY_BLACKLIST = [
            '基金', '资产管理', '投资', '信托', '证券', '期货', '保险', 
            '财富', '资本', '经营部', '个体', '直销', '理财', 
            'Fund', 'Asset', 'Invest', 'Capital', 'Wealth'
    ]
    
    # Auto-learn
    for i, row in df.iterrows():
        if row['income'] <= 0: continue
        if df.at[i, 'type'] != 'unknown': continue # Already classified
        
        desc = str(row['description'])
        cp = str(row['counterparty']).strip()
        
        if not cp or len(cp) < 4: continue
        if utils.contains_keywords(cp, WEALTH_ENTITY_BLACKLIST): continue
        if '银行' in cp and not '人力' in cp: continue
        
        if utils.contains_keywords(desc, config.SALARY_STRONG_KEYWORDS + ['年终奖', '骨干奖', '绩效', '薪酬']):
            learned_salary_payers.add(cp)
            
    print(f"Learned Salary Payers: {len(learned_salary_payers)}")
    
    # Tag Salary
    for i, row in df.iterrows():
        if row['income'] <= 0: continue
        if df.at[i, 'type'] != 'unknown': continue
        
        desc = str(row['description'])
        cp = str(row['counterparty'])
        
        is_salary = False
        reason = ""
        
        # 1. Known Payer
        is_known = False
        for p in learned_salary_payers:
            if p in cp: 
                is_known=True
                break
        
        if is_known and not utils.contains_keywords(desc, ['赎回', '卖出', '本金', '退保', '分红']):
             is_salary = True
             reason = "Known Payer"
        
        # 2. Strong Keywords
        elif utils.contains_keywords(desc, config.SALARY_STRONG_KEYWORDS):
             # check blacklist for dividends
             if '分红' in desc and utils.contains_keywords(cp, WEALTH_ENTITY_BLACKLIST):
                 pass
             else:
                 is_salary = True
                 reason = "Strong Keyword"
        
        # 3. HR Company
        elif utils.contains_keywords(cp, config.HR_COMPANY_KEYWORDS) and row['income'] >= 1000:
             is_salary = True
             reason = "HR Company"
             
        if is_salary:
            df.at[i, 'type'] = 'salary'
            
    # Now analyze the GAP
    # Gap = those still 'unknown'
    gap_df = df[(df['income'] > 0) & (df['type'] == 'unknown')].copy()
    
    print("-" * 60)
    print(f"Gap Analysis Results")
    print(f"Total Gap Amount: {gap_df['income'].sum():,.2f}")
    print(f"Gap Transaction Count: {len(gap_df)}")
    print("-" * 60)
    
    # Top Counterparties in Gap
    top_cp = gap_df.groupby('counterparty')['income'].sum().sort_values(ascending=False).head(20)
    print("\nTop Gap Counterparties:")
    print(top_cp)
    
    # Top Specific Transactions
    print("\nTop 10 Largest Gap Transactions:")
    top_trans = gap_df.sort_values('income', ascending=False).head(10)
    for _, row in top_trans.iterrows():
        print(f"Date: {row['date']}, Amount: {row['income']:,.2f}, CP: {row['counterparty']}, Desc: {row['description']}, Cat: {row.get('category','')}, Acct: {row.get('my_account','')}")

    # Keyword Analysis in Gap
    print("\nKeyword Analysis in Descriptions:")
    for kw in ['报销', '差旅', '费', '款', '往来', '借', '还']:
        total = gap_df[gap_df['description'].str.contains(kw, na=False)]['income'].sum()
        if total > 0:
            print(f"Keyword '{kw}': {total:,.2f}")

if __name__ == "__main__":
    analyze_gap()
