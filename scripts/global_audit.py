"""
全局审计：检查所有需要 details 数组的分析模块
"""
import json

with open('output/analysis_results_cache.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

lines = []
lines.append("=" * 70)
lines.append("全局数据结构审计报告")
lines.append("=" * 70)

# ========== 1. Income 模块 ==========
lines.append("\n## 1. 异常收入分析 (income)")
income = d.get('analysisResults', {}).get('income', {})
income_details = income.get('details', [])
lines.append(f"   details 长度: {len(income_details)}")

# 检查 _type 分布
income_types = {}
for item in income_details:
    t = item.get('_type', 'unknown')
    income_types[t] = income_types.get(t, 0) + 1
for t, count in sorted(income_types.items(), key=lambda x: -x[1]):
    lines.append(f"     {t}: {count} 条")

# 溯源检查
if income_details:
    sample = income_details[0]
    has_file = 'source_file' in sample
    has_row = 'source_row' in sample or 'source_row_index' in sample
    lines.append(f"   溯源: source_file={'OK' if has_file else 'MISSING'}, source_row={'OK' if has_row else 'MISSING'}")

# ========== 2. Loan 模块 ==========
lines.append("\n## 2. 借贷风险分析 (loan)")
loan = d.get('analysisResults', {}).get('loan', {})
loan_details = loan.get('details', [])
lines.append(f"   details 长度: {len(loan_details)}")

# 检查 _type 分布
loan_types = {}
for item in loan_details:
    t = item.get('_type', 'unknown')
    loan_types[t] = loan_types.get(t, 0) + 1
for t, count in sorted(loan_types.items(), key=lambda x: -x[1]):
    lines.append(f"     {t}: {count} 条")

# 溯源检查
if loan_details:
    sample = loan_details[0]
    has_file = 'source_file' in sample or 'loan_source_file' in sample
    has_row = 'source_row' in sample or 'source_row_index' in sample or 'loan_source_row' in sample
    lines.append(f"   溯源: source_file={'OK' if has_file else 'MISSING'}, source_row={'OK' if has_row else 'MISSING'}")

# ========== 3. graphData.report 检查 ==========
lines.append("\n## 3. 图谱报告数据 (graphData.report)")
report = d.get('graphData', {}).get('report', {})
for key, items in report.items():
    if isinstance(items, list):
        count = len(items)
        if items:
            sample = items[0]
            has_file = 'source_file' in sample
            has_row = 'source_row' in sample or 'source_row_index' in sample
            trace = f"file={'OK' if has_file else 'MISS'}, row={'OK' if has_row else 'MISS'}"
        else:
            trace = "空"
        lines.append(f"   {key}: {count} 条 ({trace})")

# ========== 4. suspicions 检查 ==========
lines.append("\n## 4. 疑点检测数据 (suspicions)")
suspicions = d.get('suspicions', {})
for key, items in suspicions.items():
    if isinstance(items, list):
        count = len(items)
        if items:
            sample = items[0]
            has_file = 'source_file' in sample or 'sourceFile' in sample
            has_row = 'source_row_index' in sample or 'evidence_refs' in sample
            trace = f"溯源={'OK' if has_file or has_row else 'MISS'}"
        else:
            trace = "空"
        lines.append(f"   {key}: {count} 条 ({trace})")

lines.append("\n" + "=" * 70)

# 输出到控制台和文件
report_content = "\n".join(lines)
print(report_content)

with open('output/global_audit_report.txt', 'w', encoding='utf-8') as f:
    f.write(report_content)
print("\n报告已保存到 output/global_audit_report.txt")
