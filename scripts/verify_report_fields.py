import json

with open('./output/analysis_results_cache.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

profiles = data.get('profiles', {})
persons = data.get('persons', [])

print("=" * 50)
print("报告字段验证")
print("=" * 50)

for person in persons[:4]:  # 前4个人
    p = profiles.get(person, {})
    if not p:
        continue
    
    print(f"\n【{person}】")
    print(f"  交易笔数: {p.get('transactionCount', 0)}")
    print(f"  总收入: {p.get('totalIncome', 0)/10000:.2f} 万元")
    print(f"  工资总额: {p.get('salaryTotal', 0)/10000:.2f} 万元")
    print(f"  工资占比: {p.get('salaryRatio', 0)*100:.1f}%")
    print(f"  现金总额: {p.get('cashTotal', 0)/10000:.2f} 万元")
    print(f"  现金交易明细: {len(p.get('cashTransactions', []))} 条")
    
    # 显示前2条现金交易
    txs = p.get('cashTransactions', [])
    for i, tx in enumerate(txs[:2]):
        print(f"    - {tx.get('date')} | {tx.get('amount')/10000:.2f}万 | {tx.get('description')[:20]}")

print("\n" + "=" * 50)
print("✅ 报告字段验证完成")
