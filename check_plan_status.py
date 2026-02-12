#!/usr/bin/env python3
"""检查改进计划完成情况"""

plan = {
    'P0 - 立即修复（必须完成）': [
        ('1. 家庭工资收入修正', '✅ 完成', '0万 → 1088.97万'),
        ('2. 家庭真实收支修正', '✅ 完成', '8442万 → 1594万'),
        ('3. 个人真实收支修正', '✅ 完成', '施灵2235万 → 901万'),
        ('4. 真实银行卡筛选', '✅ 完成', '已筛选真实银行卡'),
    ],
    'P1 - 当前版本（部分完成）': [
        ('5. 房产详细展示', '✅ 完成', '4套房产已展示'),
        ('6. 车辆详细展示', '✅ 完成', '2辆车已展示'),
        ('7. 理财持仓展示', '✅ 完成', '已有专门段落'),
        ('8. 家庭资产快照（概况汇总）', '❌ 未完成', '家庭概况缺少资产汇总'),
        ('9. 收入结构分析表', '⚠️ 部分完成', '有表格但其他收入仍需优化'),
        ('10. 支出结构分析', '❌ 未完成', '尚未添加'),
        ('11. 大额资金往来Top 10', '❌ 未完成', '尚未添加'),
        ('12. 关联公司往来统计', '❌ 未完成', '尚未添加'),
    ],
    'P2 - 下个版本（待实施）': [
        ('13. 风险指标预警系统', '⏳ 待实施', ''),
        ('14. 可视化图表', '⏳ 待实施', ''),
    ]
}

print('=== 改进计划完成情况对照表 ===')
print()

for phase, items in plan.items():
    print(f'【{phase}】')
    for item, status, note in items:
        print(f'  {status} {item}')
        if note:
            print(f'      → {note}')
    print()

# 统计
total = sum(len(items) for items in plan.values())
completed = sum(1 for items in plan.values() for _, status, _ in items if '✅' in status)
partial = sum(1 for items in plan.values() for _, status, _ in items if '⚠️' in status)
not_started = sum(1 for items in plan.values() for _, status, _ in items if '❌' in status or '⏳' in status)

print(f'统计: 共{total}项 | 完成{completed}项 | 部分完成{partial}项 | 未开始{not_started}项')
