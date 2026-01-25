# 初查报告生成系统交接文档

> 日期: 2026-01-20
> 状态: ✅ 已完成

---

## 一、工作概述

本阶段完成了初查报告生成系统的核心实现，包括：

1. **数据结构定义** - 在 `report_schema.py` 中定义了完整的初查报告 JSON Schema
2. **报告构建器** - 创建 `investigation_report_builder.py` 核心模块
3. **API 集成** - 在 `api_server.py` 新增 3 个 API 端点

---

## 二、新增/修改文件

### 2.1 [NEW] investigation_report_builder.py

**核心构建器模块**，包含：

| 类/函数 | 功能 |
|---------|------|
| `InvestigationReportBuilder` | 初查报告构建器主类 |
| `build_complete_report()` | 生成完整报告 |
| `_build_family_section()` | 构建家庭部分 |
| `_build_member_details()` | 构建成员详情 |
| `_build_company_report()` | 构建公司报告（新增） |
| `_build_conclusion()` | 生成综合研判 |
| `load_investigation_report_builder()` | 加载器函数 |

**数据复用铁律**：100% 复用 `analysis_cache` 数据，禁止读取原始 Excel。

### 2.2 [MODIFY] report_schema.py

新增初查报告数据结构定义：

| 数据类 | 用途 |
|--------|------|
| `InvestigationMeta` | 报告元信息（文号、背景、范围） |
| `InvestigationFamily` | 家庭部分（成员、汇总） |
| `MemberDetails` | 成员详情（资产、分析） |
| `CompanyReport` | 公司报告（5个维度分析） |
| `InvestigationConclusion` | 综合研判（问题清单、建议） |
| `InvestigationReport` | 完整报告结构 |

### 2.3 [MODIFY] api_server.py

新增 3 个 API 端点：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/investigation-report/subjects` | GET | 获取可选核查对象和公司列表 |
| `/api/investigation-report/generate` | POST | 生成初查报告 |
| `/api/investigation-report/{filename}` | GET | 下载报告文件 |

---

## 三、报告结构示例

```json
{
  "meta": {
    "doc_number": "国监查 [2026] 第 000001 号",
    "case_background": "案件背景...",
    "data_scope": "2020-01-01 至 2025-09-30 银行流水数据",
    "generated_at": "2026-01-20T20:21:20",
    "generator": "穿云审计初查报告引擎"
  },
  "family": {
    "primary_person": "甲某某",
    "members": [
      {"name": "甲某某", "relation": "本人", "has_data": true},
      {"name": "乙某某", "relation": "配偶", "has_data": true}
    ],
    "summary": {
      "total_income": 11012646.95,
      "total_expense": 11078802.84,
      "assets": { "wealth_holdings": 963.19 }
    }
  },
  "member_details": [
    {
      "name": "甲某某",
      "relation": "本人",
      "assets": {
        "salary_total": 3459922.74,
        "salary_ratio": 0.31,
        "yearly_salary": [...]
      },
      "analysis": {
        "income_gap": {"ratio": 31.4, "verdict": "工资占比过低..."},
        "large_cash": {"total_amount": 599874.96},
        "large_transfers": {"count": 15}
      }
    }
  ],
  "companies": [
    {
      "company_name": "XX公司",
      "total_income": 5000000,
      "total_expense": 4500000,
      "key_person_transfers": {"has_transfers": true, "total_amount": 100000}
    }
  ],
  "conclusion": {
    "summary_text": "经对相关人员资金流水进行穿透分析，共发现5项问题...",
    "issues": [...],
    "next_steps": ["调取相关银行凭证原件进行核对", ...]
  }
}
```

---

## 四、使用方法

### 4.1 命令行测试

```bash
cd /Users/chenjian/Desktop/Code/cj-project
python3 investigation_report_builder.py ./output
```

### 4.2 API 调用

```bash
# 获取可选对象
curl http://localhost:8000/api/investigation-report/subjects

# 生成报告
curl -X POST http://localhost:8000/api/investigation-report/generate \
  -H "Content-Type: application/json" \
  -d '{"primary_person": "甲某某", "doc_number": "国监查 [2026] 第 XXXXXX 号"}'
```

---

## 五、数据来源映射

| 报告字段 | 缓存来源 |
|----------|----------|
| 个人收支 | `profiles.json` → `totalIncome`, `totalExpense` |
| 工资统计 | `profiles.json` → `salaryTotal`, `salaryRatio`, `yearlySalary` |
| 理财持仓 | `profiles.json` → `wealthTotal` |
| 现金交易 | `profiles.json` → `cashTransactions` |
| 银行账户 | `profiles.json` → `bankAccounts` |
| 大额交易 | `derived_data.json` → `large_transactions` |
| 借贷分析 | `derived_data.json` → `loan.details` |
| 可疑交易 | `suspicions.json` → `direct_transfers` |

---

## 六、验证结果

| 项目 | 状态 |
|------|------|
| `report_schema.py` 语法检查 | ✅ 通过 |
| `investigation_report_builder.py` 语法检查 | ✅ 通过 |
| `api_server.py` 语法检查 | ✅ 通过 |
| 命令行报告生成测试 | ✅ 通过 |

---

## 七、后续工作建议

1. **家庭成员识别增强** - 当前使用简化版关系推断，可整合 `family_analyzer.py` 完整结果
2. **房产/车辆数据** - 需要外部数据源支持
3. **HTML 报告模板** - 可基于 JSON 数据生成公文格式 HTML
4. **前端集成** - Dashboard 添加报告生成界面

---

## 八、版本记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-01-20 | 初始版本，完成核心功能 |
