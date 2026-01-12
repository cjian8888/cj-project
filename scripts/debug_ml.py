
import pandas as pd
import os
import ml_analyzer

# 模拟 main.py 中的数据加载部分，读取一个已经生成的清洗后文件来检查列名
test_file = r"d:\CJ\project\output\cleaned_data\个人\朱永平_合并流水.xlsx"

if os.path.exists(test_file):
    print(f"Found file: {test_file}")
    df = pd.read_excel(test_file)
    print("Columns:", df.columns.tolist())
    
    # 模拟 ml_analyzer 的逻辑
    core_persons = ["朱永平"]
    all_transactions = {"朱永平": df}
    
    print("\n--- Testing _feature_engineering logic ---")
    try:
        features, mapping = ml_analyzer._feature_engineering(all_transactions, core_persons)
        print(f"Features DataFrame shape: {features.shape}")
        if features.empty:
            print("Features are empty. Checking why...")
            if 'counterparty' not in df.columns:
                print("CRITICAL: 'counterparty' column missing!")
            else:
                print("'counterparty' column exists.")
                
            # 手动模拟循环
            for person in core_persons:
                for key, d in all_transactions.items():
                    print(f"Checking key='{key}', person='{person}'")
                    if person not in key:
                        print(f"  Failed: person not in key")
                    if '公司' in key:
                        print(f"  Failed: '公司' in key")
                        
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"File not found: {test_file}")
