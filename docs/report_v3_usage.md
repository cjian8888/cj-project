# v3.0 三段式报告生成 - 使用指南

## 快速开始

### 1. 准备数据

确保已完成数据分析,生成了以下缓存文件:
```
output/analysis_cache/
├── profiles.json          # 个人/公司画像
├── derived_data.json      # 派生分析数据
├── suspicions.json        # 疑点数据
├── graph_data.json        # 关系图谱
└── metadata.json          # 元数据
```

### 2. 创建归集配置

在 `output/primary_targets.json` 中定义分析单元:

```json
{
  "version": "1.0.0",
  "doc_number": "国监查 [2026] 第 XXXXXX 号",
  "employer": "某单位",
  "analysis_units": [
    {
      "anchor": "张某某",
      "members": ["张某某", "李某某", "张小某"],
      "unit_type": "family",
      "note": "核心家庭单元"
    },
    {
      "anchor": "张大某",
      "members": ["张大某"],
      "unit_type": "independent",
      "note": "独立关联单元"
    }
  ],
  "include_companies": ["XX公司", "YY公司"]
}
```

### 3. 生成报告

#### 方式一: 使用测试脚本

```bash
python3 test_report_v3.py
```

#### 方式二: 编程调用

```python
from investigation_report_builder import load_investigation_report_builder
from report_config.primary_targets_service import PrimaryTargetsService
import json

# 加载报告构建器
builder = load_investigation_report_builder('./output')

# 加载归集配置
service = PrimaryTargetsService('./output')
config, message = service.load_config()

# 生成v3.0报告
report = builder.build_report_v3(
    config=config,
    case_background="依据相关线索反映,现对相关人员进行资金穿透核查。",
    data_scope="银行流水数据"
)

# 保存报告
with open('./output/report_v3.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2, default=str)

print("✅ 报告已生成")
```

## 报告结构说明

### 顶层结构

```json
{
  "meta": {...},                    // 元信息
  "preface": {...},                 // 前言章节
  "analysis_units": [...],          // 分析单元循环体
  "inter_company_analysis": {...},  // 公司间交叉分析
  "conclusion": {...}               // 综合研判
}
```

### 前言章节 (preface)

包含核查依据、数据范围、时间区间和核查对象列表:

```json
{
  "case_background": "依据相关线索反映...",
  "data_scope": {
    "bank_transactions": "2020-01-01 至 2025-09-30",
    "real_estate": "【待调取】自然资源部精准查询",
    "vehicles": "【待调取】公安部机动车查询",
    ...
  },
  "time_range": {
    "start_date": "2020-01-01",
    "end_date": "2025-09-30",
    "months": 68,
    "description": "2020-01-01 至 2025-09-30(共68个月)"
  },
  "subjects": [
    {"name": "张某某", "relation": "本人", "has_data": "是"},
    {"name": "李某某", "relation": "配偶", "has_data": "是"}
  ]
}
```

### 分析单元 (analysis_units)

每个分析单元包含8个Section:

```json
{
  "anchor": "张某某",
  "unit_type": "family",
  "members": ["张某某", "李某某"],
  "sections": {
    "section_1_identity": {
      "basic_info": {...},
      "career_history": [...],
      "family_members": [...]
    },
    "section_2_assets": {
      "real_estate": [...],
      "vehicles": [...],
      "financial_assets": {...},
      "bank_accounts": [...]
    },
    "section_3_income": {
      "total_income": 500000,
      "salary_income": {...},
      "other_income": {...},
      "income_classification": {...}
    },
    "section_4_expense": {
      "total_expense": 450000,
      "expense_categories": {...}
    },
    "section_5_income_gap": {
      "total_income": 500000,
      "total_expense": 450000,
      "salary_income": 300000,
      "gap": 150000,
      "gap_ratio": 50,
      "risk_level": "medium",
      "risk_description": "..."
    },
    "section_6_abnormal_tx": {
      "large_cash": {...},
      "large_transfers": [...]
    },
    "section_7_related_party": {
      "investigation_unit_flows": [...],
      "supplier_transactions": [...]
    },
    "section_8_collision": {
      "asset_purchase_collisions": [...],
      "promotion_collisions": [...]
    }
  }
}
```

### 公司间交叉分析 (inter_company_analysis)

```json
{
  "enabled": true,
  "companies": ["XX公司", "YY公司"],
  "flow_matrix": [
    {
      "from_company": "XX公司",
      "to_company": "YY公司",
      "amount": 0,
      "count": 0,
      "description": "无往来"
    }
  ],
  "fund_cycles": {
    "detected": false,
    "cycles": [],
    "description": "未发现涉案公司间的资金闭环"
  },
  "common_counterparties": [...],
  "timeline_collisions": [...]
}
```

### 综合研判 (conclusion)

```json
{
  "personal_issues": [
    {
      "category": "收支不抵",
      "severity": "high",
      "person": "张某某",
      "description": "总支出是合法收入的4.67倍..."
    }
  ],
  "company_issues": [...],
  "summary_text": "经对相关人员及公司进行资金穿透分析...",
  "risk_assessment": {
    "total_score": 85,
    "risk_level": "high",
    "dimensions": {
      "income_gap": 25.5,
      "benefit_transfer": 25.5,
      "asset_concealment": 17,
      "money_laundering": 17
    }
  },
  "next_steps": {
    "evidence_collection": [...],
    "interviews": [...],
    "field_investigation": [...],
    "expansion": [...]
  }
}
```

## 风险等级说明

### 收支匹配度风险

- **high**: gap_ratio > 300% (支出是合法收入的3倍以上)
- **medium**: gap_ratio > 150% (支出超过合法收入50%以上)
- **low**: gap_ratio <= 150% (收支基本匹配)

### 综合风险评分

- **high**: 总分 >= 80
- **medium**: 总分 >= 50
- **low**: 总分 < 50

评分维度:
- 收支匹配度 (30%)
- 利益输送风险 (30%)
- 资产隐匿风险 (20%)
- 洗钱风险 (20%)

## 常见问题

### Q1: 如何添加新的Section?

在 `investigation_report_builder.py` 中:

1. 添加新的 `_build_person_section_X()` 方法
2. 在 `_build_person_unit_report()` 中调用该方法
3. 更新 `sections` 字典

### Q2: 如何自定义风险判定规则?

修改以下方法:
- `_build_person_section_5_income_gap()` - 收支匹配度判定
- `_calculate_risk_score_v3()` - 综合风险评分
- `_collect_personal_issues_v3()` - 问题识别规则

### Q3: 如何处理缺失的外部数据?

使用占位符标记:
```python
"real_estate": [{"description": "【待调取】不动产登记信息"}]
```

### Q4: 如何优化大数据量性能?

1. 使用生成器处理大额交易列表
2. 限制返回的记录数量 (如 `[:10]`)
3. 添加缓存机制
4. 异步处理耗时操作

## 下一步

- [ ] 实现HTML报告渲染
- [ ] 添加图表生成功能
- [ ] 集成外部数据源
- [ ] 完善关联方分析
- [ ] 实现时空碰撞检测

---

**版本**: v3.0.0  
**更新时间**: 2026-01-23  
**维护者**: 穿云审计系统开发团队
