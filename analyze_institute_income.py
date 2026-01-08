import pandas as pd
import utils
import config

def analyze_institute_income():
    print("Loading data for 施灵...")
    file_path = 'output/cleaned_data/个人/施灵_合并流水.xlsx'
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    # Map columns
    col_map = {
        '交易时间': 'date',
        '收入(元)': 'income',
        '支出(元)': 'expense',
        '交易对手': 'counterparty',
        '交易摘要': 'description'
    }
    df = df.rename(columns=col_map)
    df['date'] = pd.to_datetime(df['date'])
    df['income'] = df['income'].fillna(0)
    
    target_name = "上海航天化工应用研究所"
    
    print(f"Filtering transactions for {target_name}...")
    # Filter for the specific institute
    # Note: Use str.contains in case of slight variations, or exact match if confident.
    # The previous analysis output showed the exact name.
    target_df = df[df['counterparty'] == target_name].copy()
    
    if target_df.empty:
        print(f"No transactions found for {target_name}")
        return

    total_income = target_df['income'].sum()
    count = len(target_df)
    
    print(f"Total Income: {total_income:,.2f}")
    print(f"Transaction Count: {count}")
    
    # Time range
    start_date = target_df['date'].min()
    end_date = target_df['date'].max()
    print(f"Time Range: {start_date} to {end_date}")
    
    # Yearly breakdown
    target_df['year'] = target_df['date'].dt.year
    yearly = target_df.groupby('year')['income'].agg(['sum', 'count', 'mean']).sort_index()
    print("\nYearly Breakdown:")
    print(yearly)
    
    # Description breakdown
    print("\nBreakdown by Description (Top 20):")
    desc_stats = target_df.groupby('description')['income'].agg(['sum', 'count']).sort_values('sum', ascending=False)
    print(desc_stats.head(20))
    
    # Detailed check for large transactions
    print("\nLarge Transactions (>50k):")
    large_tx = target_df[target_df['income'] > 50000].sort_values('income', ascending=False)
    if not large_tx.empty:
        print(large_tx[['date', 'income', 'description']].to_string())
    else:
        print("None")

    # Pattern analysis
    print("\nFrequency Analysis:")
    # Group by year-month to see monthly frequency
    target_df['month'] = target_df['date'].dt.to_period('M')
    monthly_counts = target_df.groupby('month').size()
    print(f"Average transactions per active month: {monthly_counts.mean():.2f}")
    print(f"Max transactions in a single month: {monthly_counts.max()}")
    
    # Check for "Salary" keywords in description
    salary_mask = target_df['description'].astype(str).apply(lambda x: utils.contains_keywords(x, config.SALARY_KEYWORDS))
    salary_total = target_df[salary_mask]['income'].sum()
    print(f"\nExplicitly marked as Salary (by keywords): {salary_total:,.2f}")
    
    # Check for "Bonus" keywords
    bonus_keywords = ['奖金', '绩效', '年终', '分红']
    bonus_mask = target_df['description'].astype(str).apply(lambda x: utils.contains_keywords(x, bonus_keywords))
    bonus_total = target_df[bonus_mask]['income'].sum()
    print(f"Explicitly marked as Bonus (keywords: {bonus_keywords}): {bonus_total:,.2f}")

    # Check for "Reimbursement" keywords
    reim_keywords = ['报销', '差旅', '房补', '车贴']
    reim_mask = target_df['description'].astype(str).apply(lambda x: utils.contains_keywords(x, reim_keywords))
    reim_total = target_df[reim_mask]['income'].sum()
    print(f"Explicitly marked as Reimbursement (keywords: {reim_keywords}): {reim_total:,.2f}")

if __name__ == "__main__":
    analyze_institute_income()
