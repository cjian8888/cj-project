import json

with open('./output/analysis_results_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

persons = d.get('persons', [])
profiles = d.get('profiles', {})

print("=" * 60)
print("个人报告字段验证")
print("=" * 60)

for name in persons:
    v = profiles.get(name, {})
    if not v:
        continue
    
    print(f"\n【{name}】")
    print(f"  交易笔数: {v.get('transactionCount', 0)}")
    print(f"  总收入: {v.get('totalIncome', 0)/10000:.2f} 万元")
    print(f"  工资总额 (salaryTotal): {v.get('salaryTotal', 'N/A')}")
    print(f"  工资占比 (salaryRatio): {v.get('salaryRatio', 'N/A')}")
    print(f"  现金交易明细 (cashTransactions): {len(v.get('cashTransactions', []))} 条")
    
    txs = v.get('cashTransactions', [])
    if txs:
        print(f"  前2条现金交易:")
        for tx in txs[:2]:
            print(f"    - {tx.get('date', '')} | {tx.get('amount', 0)/10000:.2f}万 | {tx.get('description', '')[:30]}")

print("\n" + "=" * 60)
