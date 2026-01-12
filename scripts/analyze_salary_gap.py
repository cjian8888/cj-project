#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
马尚德工资性收入差异分析
对比系统识别结果与用户核实的基线数据
"""

import pandas as pd
import sys
sys.path.insert(0, '.')
from financial_profiler import calculate_income_structure

print('=' * 120)
print('马尚德工资性收入差异分析报告')
print('=' * 120)

# 用户核实的基线数据
baseline_data = {
    'total': 141.8,  # 万元
    '2022': 31.98,
    '2023': 34.4,
    '2024': 62.5,  # 含补贴27.72万元
    '2025': 12.92,
    'note': '2022年1月至2025年9月，均为单位发放'
}

print('\n【用户核实的基线数据】')
print(f'2022年: {baseline_data["2022"]:.2f} 万元')
print(f'2023年: {baseline_data["2023"]:.2f} 万元')
print(f'2024年: {baseline_data["2024"]:.2f} 万元 (含补贴27.72万元)')
print(f'2025年: {baseline_data["2025"]:.2f} 万元')
print(f'合计(2022年1月-2025年9月): {baseline_data["total"]:.2f} 万元')
print(f'备注: {baseline_data["note"]}')

# 读取马尚德的合并流水
df = pd.read_excel('./output/cleaned_data/个人/马尚德_合并流水.xlsx')
df['date'] = pd.to_datetime(df['date'])
df['year'] = df['date'].dt.year
df['month'] = df['date'].dt.month

# 筛选2022-2025年9月的数据
df_target_period = df[
    (df['year'].isin([2022, 2023, 2024])) | 
    ((df['year'] == 2025) & (df['month'] <= 9))
].copy()

print('\n' + '=' * 120)
print('【流水数据基本统计】')
print('=' * 120)
print(f'数据时间范围: {df["date"].min()} 至 {df["date"].max()}')
print(f'总交易笔数: {len(df)}')
print(f'目标期间(2022年1月-2025年9月)交易笔数: {len(df_target_period)}')

# 收入记录统计
income_all = df[df['income'] > 0]
income_target = df_target_period[df_target_period['income'] > 0]

print(f'\n全部收入记录: {len(income_all)}笔, 合计{income_all["income"].sum()/10000:.2f}万元')
print(f'目标期间收入记录: {len(income_target)}笔, 合计{income_target["income"].sum()/10000:.2f}万元')

# 按年份统计收入
print('\n【按年份统计收入】')
for year in [2022, 2023, 2024, 2025]:
    year_income = df[(df['year'] == year) & (df['income'] > 0)]['income'].sum()
    year_count = len(df[(df['year'] == year) & (df['income'] > 0)])
    print(f'{year}年: {year_income/10000:>8.2f} 万元 ({year_count:>3}笔)')

# 2025年1-9月的收入
income_2025_sep = df[(df['year'] == 2025) & (df['month'] <= 9) & (df['income'] > 0)]['income'].sum()
count_2025_sep = len(df[(df['year'] == 2025) & (df['month'] <= 9) & (df['income'] > 0)])
print(f'2025年1-9月: {income_2025_sep/10000:>8.2f} 万元 ({count_2025_sep:>3}笔)')

# 运行工资识别
print('\n' + '=' * 120)
print('【系统工资识别结果】')
print('=' * 120)

profile = calculate_income_structure(df_target_period, entity_name='马尚德')

salary_amount = profile.get('salary_income', 0)
salary_details = profile.get('salary_details', [])

print(f'\n工资性收入总额: {salary_amount/10000:.2f} 万元')
print(f'工资记录笔数: {len(salary_details)}')

if salary_details:
    # 转换为DataFrame便于分析
    salary_df = pd.DataFrame(salary_details)
    salary_df['日期'] = pd.to_datetime(salary_df['日期'])
    salary_df['year'] = salary_df['日期'].dt.year
    
    # 按年份统计工资
    print('\n【按年份统计识别的工资】')
    for year in [2022, 2023, 2024, 2025]:
        year_salary = salary_df[salary_df['year'] == year]['金额'].sum()
        year_count = len(salary_df[salary_df['year'] == year])
        print(f'{year}年: {year_salary/10000:>8.2f} 万元 ({year_count:>3}笔)')
    
    # 按对手方统计
    print('\n【按对手方统计识别的工资】')
    counterparty_summary = salary_df.groupby('对手方').agg({
        '金额': ['sum', 'count', 'mean']
    }).reset_index()
    counterparty_summary.columns = ['对手方', '总金额', '笔数', '平均金额']
    counterparty_summary = counterparty_summary.sort_values('总金额', ascending=False)
    
    print(f'{"对手方":<60} {"总金额(万元)":>12} {"笔数":>6} {"平均(元)":>12}')
    print('-' * 120)
    for _, row in counterparty_summary.iterrows():
        print(f'{row["对手方"]:<60} {row["总金额"]/10000:>12.2f} {int(row["笔数"]):>6} {row["平均金额"]:>12,.0f}')
    
    # 显示工资明细(前30笔)
    print('\n【工资明细(前30笔)】')
    print(f'{"日期":<12} {"金额(元)":>12} {"对手方":<50} {"判定依据":<30}')
    print('-' * 120)
    for _, row in salary_df.head(30).iterrows():
        print(f'{row["日期"].strftime("%Y-%m-%d"):<12} {row["金额"]:>12,.0f} {str(row["对手方"])[:50]:<50} {str(row["判定依据"])[:30]:<30}')

# 差异分析
print('\n' + '=' * 120)
print('【差异分析】')
print('=' * 120)

system_total = salary_amount / 10000
baseline_total = baseline_data['total']
gap = baseline_total - system_total

print(f'\n用户核实基线: {baseline_total:.2f} 万元')
print(f'系统识别结果: {system_total:.2f} 万元')
print(f'差额: {gap:.2f} 万元 (系统{"少识别" if gap > 0 else "多识别"}了 {abs(gap/baseline_total*100):.1f}%)')

# 按年份对比
print('\n【按年份对比】')
print(f'{"年份":<10} {"基线数据(万元)":>15} {"系统识别(万元)":>15} {"差额(万元)":>15} {"差额比例":>15}')
print('-' * 120)

for year in [2022, 2023, 2024, 2025]:
    baseline = baseline_data.get(str(year), 0)
    if salary_details:
        system = salary_df[salary_df['year'] == year]['金额'].sum() / 10000
    else:
        system = 0
    diff = baseline - system
    ratio = (diff / baseline * 100) if baseline > 0 else 0
    print(f'{year:<10} {baseline:>15.2f} {system:>15.2f} {diff:>15.2f} {ratio:>14.1f}%')

# 分析未识别的收入
print('\n' + '=' * 120)
print('【未识别为工资的收入分析】')
print('=' * 120)

if salary_details:
    # 获取已识别为工资的记录的索引
    income_records = df_target_period[df_target_period['income'] > 0].copy()
    income_records['is_salary'] = False
    
    # 重新标记工资
    for _, salary_row in salary_df.iterrows():
        date = salary_row['日期']
        amount = salary_row['金额']
        # 找到匹配的记录
        mask = (income_records['date'] == date) & (income_records['income'] == amount)
        income_records.loc[mask, 'is_salary'] = True
    
    # 未识别的收入
    non_salary = income_records[~income_records['is_salary']].copy()
    
    print(f'\n未识别为工资的收入记录: {len(non_salary)}笔, 合计{non_salary["income"].sum()/10000:.2f}万元')
    
    # 按对手方分组分析
    if len(non_salary) > 0:
        counterparty_analysis = non_salary.groupby('counterparty').agg({
            'income': ['sum', 'count', 'mean']
        }).reset_index()
        counterparty_analysis.columns = ['对手方', '总金额', '笔数', '平均金额']
        counterparty_analysis = counterparty_analysis.sort_values('总金额', ascending=False)
        
        print('\n【未识别收入按对手方分组(前20个)】')
        print(f'{"对手方":<60} {"总金额(万元)":>12} {"笔数":>6} {"平均(元)":>12}')
        print('-' * 120)
        for _, row in counterparty_analysis.head(20).iterrows():
            print(f'{str(row["对手方"])[:60]:<60} {row["总金额"]/10000:>12.2f} {int(row["笔数"]):>6} {row["平均金额"]:>12,.0f}')
        
        # 显示未识别收入的详细记录(按金额从大到小排序,取前30笔)
        print('\n【未识别收入详细记录(前30笔,按金额降序)】')
        print(f'{"日期":<12} {"金额(元)":>12} {"对手方":<50} {"摘要":<40}')
        print('-' * 120)
        for _, row in non_salary.nlargest(30, 'income').iterrows():
            print(f'{row["date"].strftime("%Y-%m-%d"):<12} {row["income"]:>12,.0f} {str(row.get("counterparty", ""))[:50]:<50} {str(row.get("description", ""))[:40]:<40}')

print('\n' + '=' * 120)
print('【问题诊断与建议】')
print('=' * 120)

if gap > 0:
    print(f'\n⚠️ 系统少识别了 {gap:.2f}万元 的工资性收入！')
    print('\n可能原因:')
    print('1. 部分工资记录的摘要不包含工资关键词')
    print('2. 部分工资记录的对手方名称不符合人力资源公司特征')
    print('3. 高频稳定收入的判定条件过于严格(需要6次以上、6个月以上、CV<0.8等)')
    print('4. 某些正常工资被排除规则误排除')
    print('\n建议措施:')
    print('1. 检查上述"未识别收入详细记录",找出哪些应该是工资但未被识别')
    print('2. 补充工资关键词或对手方关键词')
    print('3. 调整高频稳定收入的判定参数')
    print('4. 检查排除规则是否过于严格')
else:
    print('\n✅ 系统识别结果符合预期')

print('\n' + '=' * 120)
print('分析完成')
print('=' * 120)
