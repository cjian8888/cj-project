# 初查报告数据契约 (Data Contract)

> **版本**: 3.0.0
> **创建时间**: 2026-01-23
> **适用范围**: 穿云审计系统初查报告生成

---

## 一、输入数据契约 (Input Contract)

报告生成模块从 `analysis_cache/` 目录读取以下预计算数据。

### 1.1 profiles.json - 个人/公司画像

| 字段路径 | 类型 | 必填 | 说明 |
|----------|------|------|------|
| `profiles` | `Object<string, Profile>` | ✅ | 以实体名称为键的画像字典 |
| `profiles.*.totalIncome` | `number` | ✅ | 总收入（元） |
| `profiles.*.totalExpense` | `number` | ✅ | 总支出（元） |
| `profiles.*.transactionCount` | `number` | ✅ | 交易笔数 |
| `profiles.*.salaryTotal` | `number` | ✅ | 工资总额（元） |
| `profiles.*.salaryRatio` | `number` | ✅ | 工资占比（%） |
| `profiles.*.yearly_salary` | `YearlySalary[]` | ⚪ | 年度工资统计 |
| `profiles.*.bankAccounts` | `BankAccount[]` | ✅ | 银行账户列表 |
| `profiles.*.wealthTotal` | `number` | ⚪ | 理财购买总额 |
| `profiles.*.wealthHolding` | `number` | ⚪ | 理财估计持仓 |
| `profiles.*.cashTransactions` | `CashSummary` | ⚪ | 现金交易统计 |
| `profiles.*.income_classification` | `IncomeClass` | ⚪ | 收入来源分类 |
| `profiles.*.bank_accounts_official` | `BankAccount[]` | ⚪ | 人行官方账户数据 |

#### YearlySalary 结构

```json
{
  "year": "2023",
  "total": 55000.00,
  "months": 12,
  "avg_monthly": 4583.33,
  "transaction_count": 12
}
```

#### BankAccount 结构

```json
{
  "account_number": "6227003012345678901",
  "bank_name": "中国建设银行",
  "account_type": "借记卡",
  "account_category": "个人账户",
  "is_real_bank_card": true,
  "last_balance": 125000.00,
  "balance_is_estimated": false,
  "first_transaction_date": "2020-01-05T10:00:00",
  "last_transaction_date": "2025-09-28T14:30:00",
  "transaction_count": 256,
  "total_income": 500000.00,
  "total_expense": 375000.00
}
```

---

### 1.2 derived_data.json - 派生分析数据

| 字段路径 | 类型 | 必填 | 说明 |
|----------|------|------|------|
| `income` | `IncomeAnalysis` | ⚪ | 收入分析 |
| `large_transactions` | `LargeTransaction[]` | ⚪ | 大额交易明细 |
| `family_summary` | `FamilySummary` | ⚪ | 家庭汇总统计 |
| `loan` | `LoanAnalysis` | ⚪ | 借贷分析 |

#### LargeTransaction 结构

```json
{
  "person": "甲某某",
  "date": "2023-03-15 10:00:00",
  "amount": 200000.00,
  "direction": "income",
  "counterparty": "XX公司",
  "description": "咨询服务费",
  "account_number": "6227****8901",
  "bank_name": "中国建设银行",
  "risk_level": "high"
}
```

---

### 1.3 suspicions.json - 疑点数据

| 字段路径 | 类型 | 必填 | 说明 |
|----------|------|------|------|
| `cash_collisions` | `CashCollision[]` | ⚪ | 现金时空碰撞 |
| `direct_transfers` | `DirectTransfer[]` | ⚪ | 个人↔公司直接转账 |
| `fund_cycles` | `FundCycle[]` | ⚪ | 资金闭环 |
| `aml_alerts` | `AMLAlert[]` | ⚪ | 反洗钱预警 |

---

### 1.4 外部数据（可选）

| 数据源 | 字段位置 | 优先级 | 说明 |
|--------|----------|--------|------|
| 人行征信 | `profiles.*.bank_accounts_official` | P0 | 官方银行账户余额 |
| 人行反洗钱 | `suspicions.aml_alerts` | P0 | 可疑交易报告 |
| 市场监管 | `company_info.json` | P0 | 企业登记信息 |
| 机动车 | `profiles.*.vehicles` | P1 | 车辆信息 |
| 不动产 | `profiles.*.properties` | P1 | 房产信息 |
| 证券 | `profiles.*.securities` | P1 | 证券持仓 |

---

## 二、输出数据契约 (Output Contract)

报告输出为 JSON 格式，结构如下。

### 2.1 顶层结构 (InvestigationReport)

```typescript
interface InvestigationReport {
  meta: ReportMeta;                    // 元信息
  family: InvestigationFamily;         // 家庭概况
  analysis_units: AnalysisUnit[];      // 分析单元（循环体）
  company_reports?: CompanyReport[];   // 公司报告
  conclusion: ReportConclusion;        // 综合研判
}
```

---

### 2.2 ReportMeta - 元信息

| 字段 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `doc_number` | `string` | ⚪ | 文号 | `"国监查 [2026] 第 020734 号"` |
| `case_background` | `string` | ⚪ | 案件背景 | `"依据相关线索..."` |
| `data_scope` | `string` | ⚪ | 数据范围 | `"2020年1月至2025年9月"` |
| `generated_at` | `string` | ✅ | 生成时间 (ISO8601) | `"2026-01-23T18:41:00"` |
| `version` | `string` | ✅ | 报告版本 | `"3.0.0"` |
| `generator` | `string` | ✅ | 生成引擎 | `"穿云审计初查报告引擎"` |
| `core_persons` | `string[]` | ✅ | 核心人员列表 | `["甲某某", "乙某某"]` |
| `companies` | `string[]` | ⚪ | 涉及公司列表 | `["某公司"]` |
| `data_range.start_date` | `string` | ⚪ | 数据起始日期 | `"2020-01-01"` |
| `data_range.end_date` | `string` | ⚪ | 数据结束日期 | `"2025-09-30"` |

---

### 2.3 InvestigationFamily - 家庭概况

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `primary_person` | `string` | ✅ | 核查对象姓名 |
| `members` | `FamilyMember[]` | ✅ | 家庭成员列表 |
| `summary` | `FamilySummary` | ✅ | 家庭汇总统计 |

#### FamilyMember

```json
{
  "name": "甲某某",
  "relation": "本人",
  "has_data": true,
  "id_number": "310230198501010011"
}
```

#### FamilySummary

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_income` | `number` | 家庭总收入 |
| `total_expense` | `number` | 家庭总支出 |
| `internal_transfers` | `number` | 成员间互转金额（已剔除） |
| `assets.real_estate_count` | `number` | 房产套数 |
| `assets.real_estate_value` | `number` | 房产价值 |
| `assets.vehicle_count` | `number` | 车辆数量 |
| `assets.deposits` | `number` | 存款总额 |
| `assets.wealth_holdings` | `number` | 理财持仓 |

---

### 2.4 AnalysisUnit - 分析单元

分析单元是报告的循环体，每个单元代表一个核查对象组。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `anchor` | `string` | ✅ | 锚点人员 |
| `unit_type` | `"family" \| "independent"` | ✅ | 单元类型 |
| `unit_name` | `string` | ⚪ | 单元名称 |
| `members` | `string[]` | ✅ | 成员列表 |
| `aggregated_data` | `AggregatedData` | ✅ | 聚合数据 |
| `member_details` | `MemberDetails[]` | ✅ | 成员详情 |

**单元类型说明**：
- `family`: 核心家庭单元（本人+配偶+子女）
- `independent`: 独立关联单元（父母/兄弟姐妹）

---

### 2.5 MemberDetails - 成员详情

每个成员包含两大板块：资产信息 + 数据分析。

#### 板块一：资产信息 (assets)

| 字段 | 类型 | 说明 |
|------|------|------|
| `salary_total` | `number` | 工资总额 |
| `salary_ratio` | `number` | 工资占比 |
| `yearly_salary` | `YearlySalary[]` | 年度工资统计 |
| `wealth_total` | `number` | 理财购买总额 |
| `wealth_holding` | `number` | 理财估计持仓 |
| `bank_accounts` | `BankAccount[]` | 银行账户列表 |
| `properties` | `Property[]` | 房产信息 |
| `vehicles` | `Vehicle[]` | 车辆信息 |

#### 板块二：数据分析 (analysis)

| 字段 | 类型 | 说明 |
|------|------|------|
| `income_gap` | `IncomeGap` | 收支匹配分析 |
| `inflow_analysis` | `InflowAnalysis` | 资金流入分析 |
| `outflow_analysis` | `OutflowAnalysis` | 资金流出分析 |
| `large_cash` | `LargeCash` | 大额现金分析 |
| `large_transfers` | `LargeTransfers` | 大额转账分析 |
| `related_party_transactions` | `RelatedParty` | 关联交易排查 |

---

### 2.6 CompanyReport - 公司报告

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `company_name` | `string` | ✅ | 公司名称 |
| `total_income` | `number` | ✅ | 累计进账 |
| `total_expense` | `number` | ✅ | 累计支出 |
| `transaction_count` | `number` | ✅ | 交易笔数 |
| `investigation_unit_flows` | `UnitFlows` | ✅ | 与调查单位往来 |
| `key_person_transactions` | `KeyPersonTx` | ✅ | 与关键人员往来 |
| `cash_transactions` | `CashSummary` | ✅ | 现金交易统计 |
| `company_info` | `CompanyInfo` | ⚪ | 企业登记信息 |

---

### 2.7 ReportConclusion - 综合研判

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `issues` | `Issue[]` | ✅ | 发现问题清单 |
| `summary_text` | `string` | ✅ | 研判意见文字 |
| `risk_level` | `"high" \| "medium" \| "low"` | ✅ | 风险等级 |
| `risk_score` | `number` | ⚪ | 风险评分 (0-100) |
| `next_steps` | `string[]` | ✅ | 下一步建议 |

#### Issue 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `category` | `string` | 问题类型：收支不抵/异常往来/来源不明 |
| `severity` | `"high" \| "medium" \| "low"` | 严重程度 |
| `title` | `string` | 问题标题 |
| `description` | `string` | 问题描述 |
| `evidence_refs` | `string[]` | 证据引用 |
| `affected_persons` | `string[]` | 涉及人员 |
| `affected_companies` | `string[]` | 涉及公司 |
| `recommendation` | `string` | 处理建议 |

---

## 三、字段来源映射

| 输出字段 | 输入来源 | 转换逻辑 |
|----------|----------|----------|
| `member.assets.salary_total` | `profiles.*.salaryTotal` | 直接复制 |
| `member.assets.salary_ratio` | `profiles.*.salaryRatio` | 直接复制 |
| `member.assets.bank_accounts` | `profiles.*.bankAccounts` | 过滤 `is_real_bank_card=true` |
| `member.analysis.income_gap` | `profiles.*` | 计算 `salaryTotal/totalIncome` |
| `member.analysis.large_transfers` | `derived_data.large_transactions` | 按 person 过滤 |
| `member.analysis.large_cash` | `profiles.*.cashTransactions` | 直接复制 |
| `family.summary` | `derived_data.family_summary` | 直接复制 |
| `conclusion.issues` | `suspicions.*` | 规则引擎生成 |

---

## 四、验证规则

### 必填字段验证

```python
# 验证报告必填字段
assert report['meta']['generated_at'] is not None
assert report['meta']['version'] is not None
assert report['family']['primary_person'] is not None
assert len(report['family']['members']) > 0
assert len(report['analysis_units']) > 0
assert report['conclusion']['summary_text'] is not None
```

### 数值约束

| 字段 | 约束 |
|------|------|
| `salary_ratio` | `0 <= value <= 100` |
| `risk_score` | `0 <= value <= 100` |
| `amount` 类型字段 | `value >= 0` |
| `count` 类型字段 | `value >= 0` |

---

## 五、版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 3.0.0 | 2026-01-23 | 初始版本，定义完整输入输出契约 |
