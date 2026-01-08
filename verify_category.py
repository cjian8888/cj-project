import pandas as pd
import os

def verify_categorization_logic():
    file_path = r'output/cleaned_data/个人/陈斌_合并流水.xlsx'
    if not os.path.exists(file_path):
        print("文件不存在")
        return
        
    df = pd.read_excel(file_path)
    
    print(f"总记录数: {len(df)}")
    
    # 筛选出摘要信息量极低（如'正常'、空、'消费'）的记录
    # 且 分类不是'其他' 的记录 (说明分类逻辑起作用了)
    # 或者是'其他'但对手方有信息的 (说明分类逻辑漏了)
    
    useless_desc = ['正常', '消费', 'nan', '', '1', '提现', '转账']
    
    # Check 1: 摘要没用，但分类成功了 (证明用到了对手方)
    success_cases = df[
        df['交易摘要'].astype(str).isin(useless_desc) & 
        (df['交易分类'] != '其他') &
        (df['交易分类'] != '第三方支付') # 排除简单的支付宝兜底
    ]
    
    print(f"\n[验证1] 摘要无用但通过对手方分类成功的记录: {len(success_cases)} 条")
    if not success_cases.empty:
        print("示例 (摘要 | 对手方 -> 分类):")
        for _, row in success_cases.head(5).iterrows():
            print(f"  {row['交易摘要']} | {row['交易对手']} -> {row['交易分类']}")
            
    # Check 2: 摘要没用，对手方有用，但分类失败 (漏网之鱼)
    failed_cases = df[
        df['交易摘要'].astype(str).isin(useless_desc) & 
        (df['交易分类'] == '其他') &
        (df['交易对手'].notna()) & 
        (df['交易对手'].astype(str) != 'nan')
    ]
    
    print(f"\n[验证2] 摘要无用且分类失败(是'其他')，需检查对手方是否包含未覆盖关键词: {len(failed_cases)} 条")
    if not failed_cases.empty:
        # 统计对手方高频词
        from collections import Counter
        opponents = failed_cases['交易对手'].astype(str).tolist()
        print("高频未识别对手方:")
        for word, count in Counter(opponents).most_common(10):
            print(f"  {word}: {count}")

if __name__ == '__main__':
    verify_categorization_logic()
