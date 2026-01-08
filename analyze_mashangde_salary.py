import pandas as pd
import numpy as np
from datetime import datetime

print('=' * 100)
print('马尚德工资性收入详细分析')
print('=' * 100)

# 1. 读取资金核查底稿
df_summary = pd.read_excel('./output/analysis_results/资金核查底稿.xlsx')
row = df_summary[df_summary['对象名称'] == '马尚德'].iloc[0]

print('\n【汇总数据】')
print(f'数据时间范围: {row["数据时间范围"]}')
print(f'交易笔数: {row["交易笔数"]}')
print(f'总收入: {row["总收入(万元)"]:.2f} 万元')
print(f'总支出: {row["总支出(万元)"]:.2f} 万元')
print(f'工资性收入: {row["工资性收入(万元)"]:.2f} 万元  ⚠️')
print(f'工资性收入占比: {row["工资性收入占比"]:.1%}')

# 2. 读取合并流水
df_flow = pd.read_excel('./output/cleaned_data/个人/马尚德_合并流水.xlsx')
df_flow['date'] = pd.to_datetime(df_flow['date'])

# 按年份统计收入
df_flow['year'] = df_flow['date'].dt.year
df_flow['month'] = df_flow['date'].dt.to_period('M')

print('\n【收入记录统计】')
income_records = df_flow[df_flow['income'] > 0].copy()
print(f'收入记录总数: {len(income_records)}')
print(f'总收入金额: {income_records["income"].sum():,.2f} 元 = {income_records["income"].sum()/10000:.2f} 万元')

# 按年份统计收入
print('\n【按年份统计总收入】')
for year in sorted(income_records['year'].unique()):
    if year < 2022 or year > 2025:
        continue
    year_income = income_records[income_records['year'] == year]['income'].sum()
    year_count = len(income_records[income_records['year'] == year])
    print(f'{year}年: {year_income/10000:>8.2f} 万元 ({year_count:>3}笔)')

# 2022-2025年9月的总收入
income_2022_2025sep = income_records[
    (income_records['year'].isin([2022, 2023, 2024])) | 
    ((income_records['year'] == 2025) & (income_records['date'] <= '2025-09-30'))
]['income'].sum()
print(f'\n2022年1月-2025年9月总收入: {income_2022_2025sep/10000:.2f} 万元')

# 3. 分析工资识别逻辑
print('\n' + '=' * 100)
print('【工资识别逻辑分析】')
print('=' * 100)

# 从financial_profiler中读取逻辑
import sys
sys.path.insert(0, '.')
from financial_profiler import calculate_income_structure
from config import SALARY_KEYWORDS, HR_COMPANY_KEYWORDS, LOAN_PLATFORM_KEYWORDS

print(f'\n当前配置:')
print(f'- 工资关键词数量: {len(SALARY_KEYWORDS)}')
print(f'- 人力资源公司关键词数量: {len(HR_COMPANY_KEYWORDS)}')
print(f'- 借贷平台关键词数量: {len(LOAN_PLATFORM_KEYWORDS)}')

# 重新运行工资识别
profile_result = calculate_income_structure(df_flow)

print(f'\n【工资识别结果】')
print(f'工资性收入金额: {profile_result.get("salary_income", 0)/10000:.2f} 万元')
print(f'工资性收入笔数: {profile_result.get("salary_count", 0)}')

# 获取工资明细
salary_details = profile_result.get("salary_details", [])
print(f'\n【工资明细】(共{len(salary_details)}笔)')

if salary_details:
    # 按年份汇总
    salary_df = pd.DataFrame(salary_details)
    salary_df['date'] = pd.to_datetime(salary_df['date'])
    salary_df['year'] = salary_df['date'].dt.year
    
    print('\n按年份统计:')
    for year in sorted(salary_df['year'].unique()):
        if year < 2022 or year > 2025:
            continue
        year_salary = salary_df[salary_df['year'] == year]['amount'].sum()
        year_count = len(salary_df[salary_df['year'] == year])
        print(f'{year}年: {year_salary/10000:>8.2f} 万元 ({year_count:>3}笔)')
    
    # 2022-2025年9月的工资
    salary_2022_2025sep = salary_df[
        (salary_df['year'].isin([2022, 2023, 2024])) | 
        ((salary_df['year'] == 2025) & (salary_df['date'] <= '2025-09-30'))
    ]['amount'].sum()
    print(f'\n2022年1月-2025年9月工资性收入: {salary_2022_2025sep/10000:.2f} 万元')
    
    # 按对手方汇总
    print('\n【按对手方汇总】')
    counterparty_summary = salary_df.groupby('counterparty').agg({
        'amount': ['sum', 'count', 'mean']
    }).reset_index()
    counterparty_summary.columns = ['对手方', '总金额', '笔数', '平均金额']
    counterparty_summary = counterparty_summary.sort_values('总金额', ascending=False)
    
    for _, row in counterparty_summary.iterrows():
        print(f'{row["对手方"]:50s} {row["总金额"]/10000:>8.2f}万 ({int(row["笔数"]):>3}笔, 均{row["平均金额"]:>8.0f}元)')
    
    # 显示前20笔工资明细
    print('\n【工资明细前20笔】')
    print(f'{"日期":<12} {"金额(元)":<12} {"对手方":<50} {"判定依据"}')
    print('-' * 120)
    for detail in salary_details[:20]:
        print(f'{detail["date"]:<12} {detail["amount"]:>10,.0f}  {detail["counterparty"]:<50} {detail["reason"]}')

print('\n' + '=' * 100)
print('【差异分析】')
print('=' * 100)
print(f'用户核实基线数据: 141.8万元 (2022年1月-2025年9月)')
print(f'系统识别结果: {salary_2022_2025sep/10000:.2f}万元 (2022年1月-2025年9月)' if salary_details else '无工资识别结果')
if salary_details:
    diff = 141.8 - salary_2022_2025sep/10000
    print(f'差异: {diff:.2f}万元 ({diff/141.8*100:.1f}%)')
    
    if diff > 0:
        print(f'\n⚠️ 系统少识别了 {diff:.2f}万元 的工资性收入！')
        print('\n可能原因:')
        print('1. 部分工资记录的对手方名称不包含工资关键词')
        print('2. 部分工资记录的摘要不包含工资关键词')
        print('3. 高频稳定收入的判定条件过于严格')
        print('4. 某些正常工资被排除规则误排除')
