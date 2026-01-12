import pandas as pd

df = pd.read_excel('output/cleaned_data/个人/施灵_合并流水.xlsx')
income_col = '收入(元)'
expense_col = '支出(元)'

# 分析'其他'类别中的大额收入
other_df = df[df['交易分类'] == '其他'].copy()
other_income = other_df[other_df[income_col] > 0].copy()
other_income = other_income.sort_values(income_col, ascending=False)

print('===== 其他分类中的大额收入 TOP 15 =====')
for idx, row in other_income.head(15).iterrows():
    desc = str(row.get('交易摘要', ''))[:30]
    counterparty = str(row.get('交易对手', ''))[:30]
    amt = row[income_col]
    print(f'{amt:12,.2f} | {desc} | {counterparty}')

# 统计对手方出现频率和金额
print('\n===== 其他分类大额收入的对手方汇总 TOP 10 =====')
other_income_grouped = other_income.groupby('交易对手').agg({income_col: ['sum', 'count']}).reset_index()
other_income_grouped.columns = ['对手方', '总金额', '笔数']
other_income_grouped = other_income_grouped.sort_values('总金额', ascending=False).head(10)
for _, row in other_income_grouped.iterrows():
    counterparty = str(row['对手方'])[:40]
    print(f'{row["总金额"]/10000:8.2f}万 ({int(row["笔数"]):3d}笔) | {counterparty}')
