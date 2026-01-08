import pandas as pd
import glob
import os
import re
from collections import Counter

def analyze_chen_bin_descriptions():
    # 路径指向已生成的清洗后数据（更标准）
    file_path = r'output/cleaned_data/个人/陈斌_合并流水.xlsx'
    
    if not os.path.exists(file_path):
        print(f"找不到文件: {file_path}，尝试读取原始数据...")
        return
        
    print(f"正在深度分析陈斌的交易摘要: {file_path}")
    df = pd.read_excel(file_path)
    
    # 提取摘要列
    desc_col = '交易摘要'
    if desc_col not in df.columns:
        print("未找到'交易摘要'列")
        return
        
    # 去除空值和无关字符
    descriptions = df[desc_col].fillna('').astype(str).tolist()
    cleaned_descs = [re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', d) for d in descriptions if d and d != 'nan']
    
    # 1. 词频统计（全量）
    counter = Counter(cleaned_descs)
    print("\n【Top 20 高频摘要】")
    for word, count in counter.most_common(20):
        print(f"  {word}: {count} 次")
        
    # 2. 敏感/特殊行为检测
    patterns = {
        '游戏/娱乐': ['游戏', '充值', '皮肤', '腾讯', '网易', 'Steam', '抖音', '直播', '打赏'],
        '借贷/还款': ['借款', '贷款', '还款', '分期', '利息', '白条', '花呗', '微粒贷', '小额'],
        '生活消费': ['美团', '饿了么', '京东', '淘宝', '拼多多', '超市', '餐饮'],
        '投资理财': ['理财', '基金', '证券', '股票', '保险'],
        '大额转账': ['转账', '汇款']  # 往往配合金额分析，这里先看摘要
    }
    
    print("\n【分类行为扫描】")
    for category, keywords in patterns.items():
        found = []
        for d in descriptions:
            if any(k in str(d) for k in keywords):
                found.append(d)
        
        if found:
            print(f"\n[{category}] 相关记录 {len(found)} 条:")
            # 打印去重后的前10个示例
            print(f"  示例: {list(set(found))[:10]}")
        else:
            print(f"\n[{category}] 未发现相关记录。")

    # 3. 看看“对手方”配合摘要的情况
    print("\n【大额交易摘要透视 (交易额 > 50000)】")
    large_tx = df[df['收入(元)'] + df['支出(元)'] > 50000]
    if not large_tx.empty:
        for _, row in large_tx.head(10).iterrows():
            amt = row['收入(元)'] if row['收入(元)'] > 0 else -row['支出(元)']
            print(f"  {row['交易时间']} | {amt:>10} | {row['交易对手']} | {row['交易摘要']}")
    else:
        print("  无大额交易。")

if __name__ == '__main__':
    analyze_chen_bin_descriptions()
