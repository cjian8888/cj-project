import pandas as pd

# 读取资金核查底稿
df = pd.read_excel('./output/analysis_results/资金核查底稿.xlsx')

# 查看马尚德的数据
row = df[df['对象名称'] == '马尚德'].iloc[0]
print('=' * 80)
print('马尚德 - 资金核查底稿汇总数据')
print('=' * 80)
for col in df.columns:
    print(f'{col}: {row[col]}')

print('\n' + '=' * 80)
print('工资性收入详细分析')
print('=' * 80)

# 读取马尚德的合并流水
df_flow = pd.read_excel('./output/cleaned_data/个人/马尚德_合并流水.xlsx')
print(f'\n总交易笔数: {len(df_flow)}')
print(f'数据时间范围: {df_flow["交易时间"].min()} 至 {df_flow["交易时间"].max()}')

# 筛选收入记录
income_records = df_flow[df_flow['收入'] > 0].copy()
print(f'\n收入记录总数: {len(income_records)}')
print(f'总收入金额: {income_records["收入"].sum():,.2f} 元 = {income_records["收入"].sum()/10000:.2f} 万元')

# 查看文本报告中的工资识别情况
print('\n' + '=' * 80)
print('从分析报告中提取工资性收入信息')
print('=' * 80)

with open('./output/analysis_results/核查结果分析报告.txt', 'r', encoding='utf-8') as f:
    content = f.read()
    
# 查找马尚德相关内容
lines = content.split('\n')
in_mashangde_section = False
for i, line in enumerate(lines):
    if '马尚德' in line:
        in_mashangde_section = True
        # 打印前后10行
        start = max(0, i - 5)
        end = min(len(lines), i + 30)
        print('\n'.join(lines[start:end]))
        break
