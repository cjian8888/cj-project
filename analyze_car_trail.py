import pandas as pd
import os

def analyze_car_purchase_trail():
    file_path = r'output/cleaned_data/个人/陈斌_合并流水.xlsx'
    if not os.path.exists(file_path):
        print("文件不存在")
        return
        
    df = pd.read_excel(file_path)
    print(f"载入陈斌数据: {len(df)} 条")
    
    # 1. 锁定购车首付/全款
    # 关键词: 汽车, 4S, 绿地金凯
    car_keywords = ['汽车', '4S', '绿地金凯']
    car_purchase = df[
        df['交易对手'].astype(str).apply(lambda x: any(k in x for k in car_keywords)) |
        df['交易摘要'].astype(str).apply(lambda x: any(k in x for k in car_keywords))
    ]
    
    print("\n=== 1. 购车交易 (4S店) ===")
    if not car_purchase.empty:
        for _, row in car_purchase.iterrows():
            amt = row['支出(元)'] if row['支出(元)'] > 0 else -row['收入(元)']
            print(f"日期: {row['交易时间']} | 金额: {amt} | 对手: {row['交易对手']} | 摘要: {row['交易摘要']}")
    else:
        print("未发现直接支付给车企的大额款项。")

    # 2. 锁定车贷还款
    # 关键词: 汽车金融, 车贷, 通用金融
    finance_keywords = ['汽车金融', '车贷', '通用金融', '上汽通用']
    loan_repayments = df[
        df['交易对手'].astype(str).apply(lambda x: any(k in x for k in finance_keywords)) |
        df['交易摘要'].astype(str).apply(lambda x: any(k in x for k in finance_keywords))
    ].sort_values('交易时间')
    
    print("\n=== 2. 车贷还款 (汽车金融公司) ===")
    if not loan_repayments.empty:
        total_repaid = loan_repayments['支出(元)'].sum()
        count = len(loan_repayments)
        first_date = loan_repayments.iloc[0]['交易时间']
        last_date = loan_repayments.iloc[-1]['交易时间']
        
        # 计算月供特征
        amounts = loan_repayments['支出(元)'].value_counts()
        print(f"还款总额: {total_repaid:.2f}")
        print(f"还款次数: {count}")
        print(f"时间跨度: {first_date} 至 {last_date}")
        print("月供金额分布:")
        print(amounts)
        
        print("\n详细还款记录 (前5笔):")
        for _, row in loan_repayments.head(5).iterrows():
            print(f"  {row['交易时间']} | 支: {row['支出(元)']} | 余额: {row['余额(元)']} | 对手: {row['交易对手']}")
    else:
        print("未发现汽车金融公司还款记录。")

if __name__ == '__main__':
    analyze_car_purchase_trail()
