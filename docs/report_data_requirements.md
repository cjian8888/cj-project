# 初查报告数据需求清单

> **版本**: 1.0.0  
> **创建时间**: 2026-01-23  
> **基于**: 样本报告完整版 (sample_report_complete.html)

---

## 一、前言章节数据需求

### 1.1 核查依据
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `case_background` | string | 手动录入 | ✅ |
| `legal_basis` | string | 手动录入 | ⚪ |
| `doc_number` | string | 手动录入 | ⚪ |

### 1.2 数据范围
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `data_sources` | string[] | 自动检测 | ✅ |
| `start_date` | date | 自动检测 | ✅ |
| `end_date` | date | 自动检测 | ✅ |

### 1.3 核查对象
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `family.members[].name` | string | profiles.json | ✅ |
| `family.members[].relation` | string | profiles.json | ✅ |
| `family.members[].has_data` | boolean | profiles.json | ✅ |
| `family.members[].id_number` | string | profiles.json | ⚪ |

---

## 二、个人核查章节数据需求

### 2.1 Section I: 身份与履历

#### 基础身份信息
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `name` | string | profiles.json | ✅ |
| `id_number` | string | profiles.json | ⚪ |
| `gender` | string | 从身份证解析 | ⚪ |
| `age` | number | 从身份证解析 | ⚪ |
| `political_status` | string | 手动录入 | ⚪ |
| `family_members` | string | profiles.json | ⚪ |

#### 职务履历
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `career_history[].date` | date | 手动录入 | ⚪ |
| `career_history[].position` | string | 手动录入 | ⚪ |
| `career_history[].note` | string | 手动录入 | ⚪ |
| `current_position` | string | 手动录入 | ⚪ |
| `authority_scope` | string | 手动录入 | ⚪ |

#### 配偶及子女职业
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `spouse_occupation` | string | 手动录入 | ⚪ |
| `children_occupation` | string | 手动录入 | ⚪ |

---

### 2.2 Section II: 资产存量分析

#### 不动产
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `properties[].address` | string | profiles.*.properties | ⚪ |
| `properties[].area` | number | profiles.*.properties | ⚪ |
| `properties[].purchase_date` | date | profiles.*.properties | ⚪ |
| `properties[].purchase_price` | number | profiles.*.properties | ⚪ |
| `properties[].owner` | string | profiles.*.properties | ⚪ |
| `properties[].data_source` | string | profiles.*.properties | ⚪ |

#### 车辆
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `vehicles[].plate_number` | string | profiles.*.vehicles | ⚪ |
| `vehicles[].brand` | string | profiles.*.vehicles | ⚪ |
| `vehicles[].purchase_date` | date | profiles.*.vehicles | ⚪ |
| `vehicles[].estimated_value` | number | profiles.*.vehicles | ⚪ |
| `vehicles[].owner` | string | profiles.*.vehicles | ⚪ |

#### 银行账户
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `bank_accounts[].bank_name` | string | profiles.*.bankAccounts | ✅ |
| `bank_accounts[].account_number` | string | profiles.*.bankAccounts | ✅ |
| `bank_accounts[].account_type` | string | profiles.*.bankAccounts | ✅ |
| `bank_accounts[].last_balance` | number | profiles.*.bankAccounts | ✅ |
| `bank_accounts[].balance_is_estimated` | boolean | profiles.*.bankAccounts | ✅ |
| `bank_accounts[].last_transaction_date` | date | profiles.*.bankAccounts | ✅ |

#### 理财产品
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `wealth_total` | number | profiles.*.wealthTotal | ⚪ |
| `wealth_holding` | number | profiles.*.wealthHolding | ⚪ |

---

### 2.3 Section III: 收入穿透分析

#### 收入总览
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `total_income` | number | profiles.*.totalIncome | ✅ |
| `salary_total` | number | profiles.*.salaryTotal | ✅ |
| `salary_ratio` | number | profiles.*.salaryRatio | ✅ |
| `income_classification.legitimate_income` | number | profiles.*.income_classification | ⚪ |
| `income_classification.unknown_source` | number | profiles.*.income_classification | ⚪ |
| `income_classification.suspicious_income` | number | profiles.*.income_classification | ⚪ |

#### 收入分类占比
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `inflow_analysis.category_summary` | Object | derived_data.income | ⚪ |
| `inflow_analysis.legitimate_ratio` | number | 计算得出 | ⚪ |
| `inflow_analysis.unknown_ratio` | number | 计算得出 | ⚪ |
| `inflow_analysis.suspicious_ratio` | number | 计算得出 | ⚪ |

#### Top 10 转入对手方
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `inflow_analysis.top_sources[].counterparty` | string | derived_data.income | ⚪ |
| `inflow_analysis.top_sources[].total_amount` | number | derived_data.income | ⚪ |
| `inflow_analysis.top_sources[].count` | number | derived_data.income | ⚪ |
| `inflow_analysis.top_sources[].percentage` | number | derived_data.income | ⚪ |
| `inflow_analysis.top_sources[].category` | string | derived_data.income | ⚪ |

---

### 2.4 Section IV: 支出穿透分析

#### 支出总览
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `total_expense` | number | profiles.*.totalExpense | ✅ |
| `outflow_analysis.category_summary` | Object | derived_data | ⚪ |

#### Top 10 转出对手方
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `outflow_analysis.top_destinations[].counterparty` | string | derived_data | ⚪ |
| `outflow_analysis.top_destinations[].total_amount` | number | derived_data | ⚪ |
| `outflow_analysis.top_destinations[].count` | number | derived_data | ⚪ |
| `outflow_analysis.top_destinations[].percentage` | number | derived_data | ⚪ |
| `outflow_analysis.top_destinations[].category` | string | derived_data | ⚪ |

#### 大额单笔支出清单
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `outflow_analysis.large_single_payments[].date` | date | derived_data | ⚪ |
| `outflow_analysis.large_single_payments[].amount` | number | derived_data | ⚪ |
| `outflow_analysis.large_single_payments[].counterparty` | string | derived_data | ⚪ |
| `outflow_analysis.large_single_payments[].description` | string | derived_data | ⚪ |

---

### 2.5 Section V: GAP收支匹配模型

| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `legitimate_income` | number | 计算：salaryTotal + 公积金 | ✅ |
| `total_expense` | number | profiles.*.totalExpense | ✅ |
| `gap` | number | 计算：total_expense - legitimate_income | ✅ |
| `expense_income_ratio` | number | 计算：total_expense / legitimate_income | ✅ |

---

### 2.6 Section VI: 反洗钱特征识别

#### 现金时空碰撞
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `large_cash.transactions[].date` | date | profiles.*.cashTransactions | ⚪ |
| `large_cash.transactions[].amount` | number | profiles.*.cashTransactions | ⚪ |
| `large_cash.transactions[].type` | string | profiles.*.cashTransactions | ⚪ |
| `large_cash.transactions[].description` | string | profiles.*.cashTransactions | ⚪ |

#### 其他反洗钱特征
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `aml_patterns.structured_deposits` | Object[] | suspicions.json | ⚪ |
| `aml_patterns.rapid_turnover` | Object[] | suspicions.json | ⚪ |
| `aml_patterns.fund_cycles` | Object[] | suspicions.fund_cycles | ⚪ |

---

### 2.7 Section VII: 时空碰撞分析

| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `career_history[].date` | date | 手动录入 | ⚪ |
| `properties[].purchase_date` | date | profiles.*.properties | ⚪ |
| `vehicles[].purchase_date` | date | profiles.*.vehicles | ⚪ |
| `large_transfers.transactions[].date` | date | derived_data.large_transactions | ⚪ |

**计算逻辑**：
- 购房时间 vs 入职时间
- 购车时间 vs 提拔时间
- 大额收入时间 vs 重要决策时间

---

### 2.8 Section VIII: 生活轨迹画像

#### 差旅记录
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `travel_records.flights[]` | Object[] | profiles.*.flight_records | ⚪ |
| `travel_records.railways[]` | Object[] | profiles.*.railway_tickets | ⚪ |
| `travel_records.hotels[]` | Object[] | profiles.*.hotel_records | ⚪ |

#### 消费轨迹
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `annual_consumption` | number | 计算：年度消费支出 | ⚪ |
| `monthly_avg_consumption` | number | 计算：annual_consumption / 12 | ⚪ |

---

## 三、公司核查章节数据需求

### 3.1 公司基本信息
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `company_name` | string | profiles.json (公司) | ✅ |
| `unified_social_credit_code` | string | company_info.json | ⚪ |
| `registered_capital` | string | company_info.json | ⚪ |
| `legal_representative` | string | company_info.json | ⚪ |
| `shareholders[]` | string[] | company_info.json | ⚪ |
| `registration_date` | date | company_info.json | ⚪ |
| `business_scope` | string | company_info.json | ⚪ |
| `registered_address` | string | company_info.json | ⚪ |

### 3.2 资金规模分析
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `total_income` | number | profiles.*.totalIncome | ✅ |
| `total_expense` | number | profiles.*.totalExpense | ✅ |
| `transaction_count` | number | profiles.*.transactionCount | ✅ |
| `bank_accounts[].balance` | number | profiles.*.bankAccounts | ⚪ |

### 3.3 与调查单位往来
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `investigation_unit_flows.has_flows` | boolean | derived_data | ✅ |
| `investigation_unit_flows.total_amount` | number | derived_data | ⚪ |
| `investigation_unit_flows.percentage` | number | derived_data | ⚪ |
| `investigation_unit_flows.note` | string | derived_data | ⚪ |

### 3.4 与关键人员资金往来
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `key_person_transactions.total_count` | number | derived_data | ✅ |
| `key_person_transactions.total_amount` | number | derived_data | ✅ |
| `key_person_transactions.persons[].name` | string | derived_data | ✅ |
| `key_person_transactions.persons[].transaction_count` | number | derived_data | ✅ |
| `key_person_transactions.persons[].total_amount` | number | derived_data | ✅ |
| `key_person_transactions.persons[].inflow_to_person` | number | derived_data | ✅ |
| `key_person_transactions.persons[].outflow_from_person` | number | derived_data | ✅ |
| `key_person_transactions.persons[].transactions[]` | Object[] | derived_data | ⚪ |

### 3.5 公转私违规核查
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `public_to_private_transfers[].date` | date | suspicions.direct_transfers | ⚪ |
| `public_to_private_transfers[].amount` | number | suspicions.direct_transfers | ⚪ |
| `public_to_private_transfers[].recipient` | string | suspicions.direct_transfers | ⚪ |
| `public_to_private_transfers[].relationship` | string | suspicions.direct_transfers | ⚪ |
| `public_to_private_transfers[].description` | string | suspicions.direct_transfers | ⚪ |
| `public_to_private_transfers[].risk_level` | string | suspicions.direct_transfers | ⚪ |

### 3.6 现金交易情况
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `cash_transactions.has_cash` | boolean | profiles.*.cashTransactions | ✅ |
| `cash_transactions.total_amount` | number | profiles.*.cashTransactions | ⚪ |
| `cash_transactions.deposit_count` | number | profiles.*.cashTransactions | ⚪ |
| `cash_transactions.deposit_amount` | number | profiles.*.cashTransactions | ⚪ |
| `cash_transactions.withdraw_count` | number | profiles.*.cashTransactions | ⚪ |
| `cash_transactions.withdraw_amount` | number | profiles.*.cashTransactions | ⚪ |

### 3.7 皮包公司判定
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `shell_company_indicators.revenue_vs_tax` | Object | 计算 | ⚪ |
| `shell_company_indicators.employees_vs_revenue` | Object | 计算 | ⚪ |
| `shell_company_indicators.scope_vs_transactions` | Object | 计算 | ⚪ |
| `shell_company_indicators.office_vs_scale` | Object | 手动录入 | ⚪ |

### 3.8 利益输送判定要素
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `bribery_indicators.abnormal_consulting_fees` | boolean | 规则引擎 | ⚪ |
| `bribery_indicators.procurement_kickback` | boolean | 规则引擎 | ⚪ |
| `bribery_indicators.fund_cycling` | boolean | 规则引擎 | ⚪ |
| `bribery_indicators.split_transfers` | boolean | 规则引擎 | ⚪ |

---

## 四、公司间交叉分析数据需求

### 4.1 公司间资金流向矩阵
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `inter_company_flows[].from_company` | string | 计算 | ⚪ |
| `inter_company_flows[].to_company` | string | 计算 | ⚪ |
| `inter_company_flows[].count` | number | 计算 | ⚪ |
| `inter_company_flows[].amount` | number | 计算 | ⚪ |
| `inter_company_flows[].description` | string | 计算 | ⚪ |

### 4.2 资金闭环识别
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `fund_cycles[]` | Object[] | suspicions.fund_cycles | ⚪ |

### 4.3 共同上下游分析
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `common_counterparties[].name` | string | 计算 | ⚪ |
| `common_counterparties[].companies[]` | Object[] | 计算 | ⚪ |

### 4.4 关联交易时间线
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `timeline_events[].date` | date | 多源汇总 | ⚪ |
| `timeline_events[].event` | string | 多源汇总 | ⚪ |
| `timeline_events[].company` | string | 多源汇总 | ⚪ |

---

## 五、综合研判章节数据需求

### 5.1 个人问题汇总
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `issues[].category` | string | 规则引擎 | ✅ |
| `issues[].severity` | string | 规则引擎 | ✅ |
| `issues[].title` | string | 规则引擎 | ✅ |
| `issues[].description` | string | 规则引擎 | ✅ |
| `issues[].evidence_refs[]` | string[] | 规则引擎 | ⚪ |
| `issues[].affected_persons[]` | string[] | 规则引擎 | ⚪ |
| `issues[].affected_companies[]` | string[] | 规则引擎 | ⚪ |
| `issues[].recommendation` | string | 规则引擎 | ⚪ |

### 5.2 公司问题汇总
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `company_issues[].company_name` | string | 规则引擎 | ✅ |
| `company_issues[].main_issue` | string | 规则引擎 | ✅ |
| `company_issues[].risk_level` | string | 规则引擎 | ✅ |

### 5.3 综合研判意见
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `summary_text` | string | 规则引擎生成 | ✅ |
| `risk_level` | string | 规则引擎 | ✅ |
| `risk_score` | number | 规则引擎 | ⚪ |

### 5.4 风险评级
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `risk_assessment.income_matching_score` | number | 计算 | ⚪ |
| `risk_assessment.bribery_risk_score` | number | 计算 | ⚪ |
| `risk_assessment.asset_concealment_score` | number | 计算 | ⚪ |
| `risk_assessment.money_laundering_score` | number | 计算 | ⚪ |
| `risk_assessment.overall_score` | number | 计算 | ✅ |

### 5.5 下一步工作建议
| 字段 | 数据类型 | 来源 | 必填 |
|------|---------|------|------|
| `next_steps[]` | string[] | 规则引擎生成 | ✅ |

---

## 六、数据来源汇总

| 数据源 | 优先级 | 字段数量 | 覆盖章节 |
|--------|--------|---------|---------|
| `profiles.json` | P0 | 50+ | 所有个人章节 |
| `derived_data.json` | P0 | 30+ | 收支分析、大额交易 |
| `suspicions.json` | P0 | 20+ | 反洗钱、疑点检测 |
| `company_info.json` | P1 | 10+ | 公司基本信息 |
| 手动录入 | P0 | 15+ | 身份履历、核查依据 |
| 外部数据源 | P2 | 10+ | 不动产、车辆、差旅 |

---

## 七、计算字段清单

以下字段需要通过计算得出：

| 计算字段 | 计算公式 | 依赖字段 |
|---------|---------|---------|
| `gap` | `total_expense - legitimate_income` | total_expense, legitimate_income |
| `expense_income_ratio` | `total_expense / legitimate_income × 100%` | total_expense, legitimate_income |
| `salary_ratio` | `salary_total / total_income × 100%` | salary_total, total_income |
| `age` | `当前年份 - 出生年份` | id_number |
| `gender` | 从身份证第17位解析 | id_number |
| `monthly_avg_consumption` | `annual_consumption / 12` | annual_consumption |
| `legitimate_ratio` | `legitimate_income / total_income × 100%` | legitimate_income, total_income |
| `unknown_ratio` | `unknown_source / total_income × 100%` | unknown_source, total_income |
| `suspicious_ratio` | `suspicious_income / total_income × 100%` | suspicious_income, total_income |

---

## 八、优先级说明

| 优先级 | 说明 | 影响 |
|--------|------|------|
| P0 | 核心必需字段 | 缺失将导致报告无法生成 |
| P1 | 重要字段 | 缺失将影响报告完整性 |
| P2 | 增强字段 | 缺失不影响基本功能 |

---

## 九、下一步工作

基于此数据需求清单，需要：

1. **更新 report_schema.py**：确保所有字段都在 Schema 中定义
2. **检查缓存完整性**：验证 `analysis_cache` 是否包含所有必需字段
3. **实现计算逻辑**：为所有计算字段编写算法
4. **实现规则引擎**：为综合研判章节编写规则
5. **实现话术库**：为不同风险等级生成专业话术
