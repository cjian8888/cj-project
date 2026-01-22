# v3.0 初查报告数据缺失诊断报告

**诊断时间**: 2026-01-22 11:15
**诊断对象**: v3.0 初查报告生成流程

---

## 一、问题现象

用户反馈 v3.0 初查报告中：
1. 银行卡余额全部显示为 ¥0
2. 部分资产数据缺失（房产、车辆数量为 0）
3. 资金规模等汇总数据可能不准确

---

## 二、数据源分析

### 2.1 profiles.json 中 bankAccounts 字段的实际结构

```json
{
  "account_number": "6222620110021733499",
  "bank_name": "交通银行",
  "account_type": "借记卡",
  "account_category": "个人账户",
  "is_real_bank_card": true,
  "first_transaction_date": "2015-08-28T14:07:26",
  "last_transaction_date": "2024-09-06T15:36:20",
  "transaction_count": 1577,
  "total_income": 3777967.77,
  "total_expense": 3735938.22,
  "entity_name": ""
}
```

### 2.2 缺失字段清单

| 字段 | 期望来源 | 实际状态 | 影响 |
|------|----------|----------|------|
| `balance` (余额) | 人行征信报告/PBOC | ❌ 缺失 | 银行卡余额显示为 0 |
| `card_type` (借记卡/信用卡) | 流水或PBOC | ⚠️ 可用 account_type 替代 | 无重大影响 |
| `status` (账户状态) | PBOC | ❌ 缺失 | 默认显示"正常" |
| `available_balance` | PBOC | ❌ 缺失 | 无法判断可用余额 |

### 2.3 profiles.json 中存在但未被充分利用的字段

| 字段 | 内容 | 当前使用状态 |
|------|------|--------------|
| `total_income` | 该账户总收入 | ❌ 未使用（当前取 balance） |
| `total_expense` | 该账户总支出 | ❌ 未使用 |
| `transaction_count` | 该账户交易笔数 | ❌ 未使用 |
| `is_real_bank_card` | 是否真实银行卡 | ✅ 已使用 |

---

## 三、根本原因

### 3.1 缓存生成（regenerate_cache.py）未提取余额

余额数据来源于：
1. **人行征信报告数据**（`pboc_account_extractor.py`）- 可以提取账户余额
2. **原始交易流水中的余额列** - 每笔交易后的余额

当前缓存生成流程没有将这些余额数据写入 `profiles.json`。

### 3.2 investigation_report_builder.py 的数据读取路径

```python
# 第 359-360 行
raw_accounts = profile.get('bankAccounts', []) or profile.get('bank_accounts', []) or []

# 第 362-370 行 - 尝试获取官方账户数据中的余额
official_accounts = profile.get('bank_accounts_official', []) or []
```

问题：`profiles.json` 中既没有 `balance` 字段，也没有 `bank_accounts_official` 数据。

---

## 四、数据完整性评估

### 4.1 可用数据（✅ 正常）

| 数据项 | 数据源 | 状态 |
|--------|--------|------|
| 总收入/总支出 | profiles.json | ✅ 有数据（¥434.31万收入等） |
| 交易笔数 | profiles.json | ✅ 有数据（4226笔） |
| 工资收入 | profiles.json (salaryTotal) | ✅ 有数据（¥104.10万） |
| 工资占比 | profiles.json (salaryRatio) | ✅ 有数据（24.0%） |
| 银行账户列表 | profiles.json (bankAccounts) | ✅ 有数据（银行名、卡号） |
| 大额转账明细 | derived_data.json | ✅ 有数据 |

### 4.2 缺失数据（❌ 需修复）

| 数据项 | 期望来源 | 当前状态 |
|--------|----------|----------|
| 银行卡余额 | PBOC/流水末尾余额 | ❌ 全部为 0 |
| 房产数量/价值 | 外部数据源 | ❌ 全部为 0 |
| 车辆数量 | 外部数据源 | ❌ 全部为 0 |
| 身份信息（职业/单位） | 外部数据源 | ❌ 显示为 "-" |

---

## 五、修复建议

### 方案A：从流水末尾提取最后余额（简单，可行）✅ 已实施

在 `financial_profiler.extract_bank_accounts()` 中，提取每个账户最后一笔交易的余额：

```python
# 【2026-01-22 修复】
# 1. 识别余额列（支持多种格式）
BALANCE_COLUMN_VARIANTS = ['余额(元)', 'balance', '余额', '交易余额', '账户余额', '当前余额', '结余']

# 2. 按账户分组，当遇到更晚的交易时更新余额
if tx_date > accounts[account_num]['last_transaction_date']:
    accounts[account_num]['last_balance'] = balance

# 3. 如果没有余额列，使用净流入估算
if acc['last_balance'] == 0 and not balance_col:
    acc['last_balance'] = acc['total_income'] - acc['total_expense']
    acc['balance_is_estimated'] = True
```

### 方案B：整合 PBOC 数据（完整，需外部数据）

如果有人行征信数据，可以从 `pboc_account_extractor.py` 提取的数据中获取余额。

### 方案C：前端修复显示逻辑（临时方案）

在前端不显示余额为 0 的情况，改为显示 "见流水" 或使用 `total_income - total_expense` 估算净流入。

---

## 六、修复记录

### 2026-01-22 16:20 - P1 修复完成

**修改文件**: `financial_profiler.py` - `extract_bank_accounts()` 函数

**修改内容**:
1. ✅ 新增余额列识别，支持7种列名格式
2. ✅ 在账户初始化时添加 `last_balance` 字段
3. ✅ 按账户分组，取最后一笔交易的余额
4. ✅ 同一天多笔交易时，取非零余额
5. ✅ 无余额列时，使用 `total_income - total_expense` 估算
6. ✅ 添加 `balance_is_estimated` 标记区分真实/估算余额

**验证方式**: 重新生成缓存后，检查 `profiles.json` 中的 `bankAccounts[].last_balance` 字段

---

## 七、结论

v3.0 报告的数据缺失主要是因为 **profiles.json 缓存中没有银行账户余额字段**。这不是代码bug，而是数据源问题：

1. **流水数据** 中有余额列，但没有被提取到缓存 ✅ 已修复
2. **PBOC 征信数据** 如果有，也没有被整合到缓存

**修复优先级及状态**：
1. ✅ P0：使用流水净流入估算账户余额（已实施 - 作为备选方案）
2. ✅ P1：修改 extract_bank_accounts 提取流水末尾余额（已实施 - 主方案）
3. 🟢 P2：整合 PBOC 数据到缓存中（待实施 - 需外部数据）

