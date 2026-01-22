# 后端功能缺口分析与待办清单

> 基于 `report_guidelines.md` 准则，对比现有后端模块，识别功能性缺失

---

## 〇、原始数据源清单

> 扫描 `data/材料SL/` 目录发现的可用数据源

### 已有解析支持

| 数据源目录 | 解析模块 | 状态 |
|------------|----------|------|
| 银行业金融机构交易流水 | `data_cleaner.py` | ✅ 已处理 |
| 公安部同户人 | `family_analyzer.py` | ✅ 已处理 |
| 公安部户籍人口 | `family_analyzer.py` | ✅ 已处理 |
| 中航信航班同行人信息 | `multi_source_correlator.py` | ✅ 已处理 |
| 铁路总公司同行人信息 | `multi_source_correlator.py` | ✅ 已处理 |
| 自然资源部全国总库（不动产） | `asset_extractor.py` | ✅ 已处理 |

### 📌 缺少解析支持（待开发）

| 数据源目录 | 数据内容 | 报告价值 | 优先级 |
|------------|----------|----------|--------|
| **中国人民银行银行账户** | 完整账户列表+余额+状态 | 🔴 极高 - 银行存款统计 | P0 |
| **中国人民银行反洗钱** | 可疑交易监测结果 | 🔴 极高 - 风险识别 | P0 |
| **市场监管总局企业登记信息** | 公司注册资本、法人、股东 | 🔴 极高 - 公司背景核查 | P0 |
| **征信（定向查询）** | 个人/企业征信报告 | 🔴 极高 - 负债/信用分析 | P0 |
| **公安部机动车** | 车辆登记信息 | 🟠 高 - 资产统计 | P1 |
| **公安部驾驶证** | 驾驶证信息 | 🟢 低 | P3 |
| **银行业金融机构金融理财** | 理财产品详情 | 🟠 高 - 理财统计 | P1 |
| **证券信息** | 证券持仓 | 🟠 高 - 资产统计 | P1 |
| **保险信息** | 保险持有情况 | 🟡 中 - 资产参考 | P2 |
| **理财产品（定向查询）** | 理财产品详情 | 🟠 高 | P1 |
| **公安部出入境记录** | 出入境时间地点 | 🟡 中 - 时间线参考 | P2 |
| **公安部出国（境）证件** | 护照/通行证 | 🟢 低 | P3 |
| **公安部旅馆住宿** | 住宿记录 | 🟡 中 - 同住分析 | P2 |
| **公安部同住址** | 同住址人员 | 🟡 中 - 关系分析 | P2 |
| **公安部同车违章** | 同车违章记录 | 🟡 中 - 关系分析 | P2 |
| **公安部交通违法** | 交通违法记录 | 🟢 低 | P3 |
| **铁路总公司票面信息** | 铁路购票记录 | 🟡 中 - 时间线 | P2 |
| **铁路总公司互联网注册信息** | 12306注册信息 | 🟢 低 | P3 |
| **自然资源部精准查询** | 不动产详细信息 | 🟠 高 - 房产详情 | P1 |
| **银行业金融机构账户信息** | 银行账户详情 | 🔴 极高 | P0 |
| **市场监管总局统一社会信用代码** | 企业信用代码 | 🟠 高 | P1 |

---

## 一、数据清洗层缺失 (`data_cleaner.py`)

### 【需新增】银行账户识别与过滤

| 缺失项 | 说明 | 优先级 |
|--------|------|--------|
| 真实银行卡识别 | 区分借记卡/储蓄卡/工资卡 vs 基金/理财子账号 | P0 |
| 账号类型标记 | 添加 `account_type` 列（借记卡/信用卡/理财账户/证券账户） | P0 |
| 账户类别标记 | 添加 `account_category` 列（个人/对公/联名） | P1 |
| 过滤逻辑 | 剔除非16-19位账号、含"基金/理财/证券"关键词的账号 | P0 |

### 【需增强】交易分类

| 缺失项 | 说明 | 优先级 |
|--------|------|--------|
| 大额消费事件识别 | 识别购车、装修、海外消费等 | P1 |
| 房贷/车贷还款识别 | 定期还贷支出标记 | P1 |

---

## 二、计算模块层缺失

### 【需新增】银行账户统计模块

| 缺失项 | 位置建议 | 说明 | 优先级 |
|--------|----------|------|--------|
| `extract_bank_accounts()` | `financial_profiler.py` | 从流水中提取唯一银行账户列表 | P0 |
| 账户去重 | 同上 | 同一账号只保留一条，合并多银行信息 | P0 |
| 账户状态判断 | 同上 | 根据最后交易时间判断是否正常/停用 | P2 |

### 【需新增】工资年度统计

| 缺失项 | 位置建议 | 说明 | 优先级 |
|--------|----------|------|--------|
| `calculate_yearly_salary()` | `financial_profiler.py` | 按年分组统计工资收入 | P0 |
| 月度工资明细 | 同上 | 便于生成工资表格 | P1 |

### 【需新增】家庭汇总计算

| 缺失项 | 位置建议 | 说明 | 优先级 |
|--------|----------|------|--------|
| `calculate_family_summary()` | `family_finance.py` | 家庭总收入/总支出/总资产 | P0 |
| 家庭成员间转账剔除 | 同上 | 计算净流入时剔除内部互转 | P0 |

### 【需新增】公司报告分析

| 缺失项 | 位置建议 | 说明 | 优先级 |
|--------|----------|------|--------|
| `build_company_profile()` | `financial_profiler.py` | 公司资金画像（进账/支出/现金） | P0 |
| 与调查单位往来统计 | `related_party_analyzer.py` | 需配置"调查单位"关键词 | P1 |
| 公转私统计 | `related_party_analyzer.py` | 统计向个人账户的转账 | P1 |

### 【需增强】大额交易分析

| 缺失项 | 位置 | 说明 | 优先级 |
|--------|------|------|--------|
| 大额交易明细表 | `income_analyzer.py` | 生成可直接用于报告的表格结构 | P0 |
| 阈值配置化 | `config.py` | 大额交易阈值可前端配置 | P2 |

### 【需增强】资金来源分类

| 缺失项 | 位置 | 说明 | 优先级 |
|--------|------|------|--------|
| 收入来源分类 | `financial_profiler.py` | 合法收入/不明收入/可疑收入占比 | P1 |
| 来源标签 | `data_cleaner.py` | 每笔收入标记来源类型 | P1 |

---

## 三、配置层缺失 (`config.py`)

| 缺失项 | 说明 | 优先级 |
|--------|------|--------|
| `INVESTIGATION_UNIT_KEYWORDS` | 调查单位名称关键词列表 | P1 |
| `LARGE_TRANSACTION_THRESHOLD` | 大额交易阈值（当前可能硬编码） | P2 |
| `BANK_ACCOUNT_EXCLUDE_KEYWORDS` | 账户过滤关键词列表 | P0 |

---

## 四、缓存/输出层缺失 (`profiles.json`)

| 缺失字段 | 说明 | 优先级 |
|----------|------|--------|
| `bank_accounts` | 银行账户列表（按准则格式） | P0 |
| `yearly_salary` | 按年统计的工资 | P0 |
| `income_classification` | 收入来源分类占比 | P1 |
| `large_transactions` | 大额交易明细列表 | P0 |

---

## 五、执行优先级与顺序

### Phase 1: 数据清洗补全 (P0)

- [ ] 1.1 增加银行账户识别逻辑 (`data_cleaner.py`)
  - 添加 `account_type` 列
  - 添加过滤非真实银行卡的逻辑
  
- [x] 1.2 增加账户提取函数 (`financial_profiler.py`) ✅
  - 新增 `extract_bank_accounts()` 函数
  - 返回去重后的银行账户列表

### Phase 2: 计算模块补全 (P0)

- [x] 2.1 年度工资统计 (`financial_profiler.py`) ✅
  - 新增 `calculate_yearly_salary()` 函数
  - 更新 `profiles.json` 结构

- [x] 2.2 大额交易明细 (`income_analyzer.py`) ✅
  - 确保输出包含完整表格字段
  - 更新 `derived_data.json` 结构

- [x] 2.3 公司画像构建 ✅ (2026-01-21)
  - 新增 `build_company_profile()` 函数
  - 确保与个人画像格式一致
  - 集成到 `regenerate_cache.py`

### Phase 3: 家庭汇总 (P0)

- [x] 3.1 家庭汇总计算 (`family_finance.py`) ✅
  - 整合 `calculate_family_total_assets()` 到缓存
  - 剔除家庭成员间互转

### Phase 4: 配置与增强 (P1)

- [x] 4.1 配置项补充 (`config.py`) ✅
  - `INVESTIGATION_UNIT_KEYWORDS`
  - `BANK_ACCOUNT_EXCLUDE_KEYWORDS`

- [x] 4.2 收入来源分类 ✅
  - 在 `financial_profiler.py` 中实现 `classify_income_sources()`

- [x] 4.3 与调查单位往来统计 ✅
  - 在 `related_party_analyzer.py` 中实现 `analyze_investigation_unit_flows()`

### Phase 5: 缓存重生成

- [x] 5.1 更新 `regenerate_cache.py` ✅
  - 已集成: bankAccounts, yearlySalary, largeTransactions, familySummary, companySpecific
  - 已集成: incomeClassifications, investigationUnitFlows

- [ ] 5.2 验证缓存完整性

---

## 六、外部数据源解析模块（新增）

> 📌 此部分针对 "材料SL" 目录中的非银行流水数据

### Phase 6: P0 级外部数据解析

- [x] 6.1 人民银行银行账户解析 (`pboc_account_extractor.py`) ✅ (2026-01-21)
  - 解析 `中国人民银行银行账户（定向查询）/*.xlsx`
  - 提取：银行名称、完整卡号、账户类型、账户状态、当前余额
  - 输出到 `profiles.json` → `pbocAccounts`

- [x] 6.2 人民银行反洗钱数据解析 (`aml_analyzer.py`) ✅ (2026-01-21)
  - 解析 `中国人民银行反洗钱（定向查询）/*.xlsx`
  - 提取：可疑交易记录、大额交易报告
  - 输出到 `suspicions.json` → `amlData`

- [x] 6.3 市场监管总局企业登记解析 (`company_info_extractor.py`) ✅ (2026-01-21)
  - 解析 `市场监管总局企业登记信息（定向查询）/*.xlsx`
  - 提取：公司名称、注册资本、法人、股东、经营范围
  - 输出到 `companyRegistry`

- [x] 6.4 征信数据解析 (`credit_report_extractor.py`) ✅ (2026-01-21)
  - 解析 `征信（定向查询）/*.xlsx`
  - 提取：信用评分、负债情况、贷款记录
  - 输出到 `profiles.json` → `creditData`

- [x] 6.5 银行业金融机构账户信息解析 ✅ (2026-01-21)
  - 解析 `银行业金融机构账户信息（定向查询）/*.xlsx`
  - 与 6.1 合并或补充
  - 输出到 `bankAccountInfo`

### Phase 7: P1 级外部数据解析

- [x] 7.1 公安部机动车解析 (`vehicle_extractor.py`) ✅ (2026-01-21)
  - 解析 `公安部机动车（定向查询）/*.xlsx`
  - 提取：车牌号、品牌型号、购买时间、估价
  - 输出到 `vehicleData`

- [x] 7.2 银行理财产品详情解析 (`wealth_product_extractor.py`) ✅ (2026-01-21)
  - 解析 `银行业金融机构金融理财（定向查询）/*.xlsx`
  - 解析 `理财产品（定向查询）/*.xlsx`
  - 提取：产品名称、持有金额、到期日
  - 输出到 `wealthProductData`

- [x] 7.3 证券信息解析 (`securities_extractor.py`) ✅ (2026-01-21)
  - 解析 `证券信息（定向查询）/*.xlsx`
  - 提取：证券公司、持仓股票、市值
  - 输出到 `securitiesData`

- [x] 7.4 自然资源部精准查询解析 (`asset_extractor.py`) ✅ (2026-01-21)
  - 解析 `自然资源部精准查询（定向查询）/*.xlsx`
  - 与现有不动产解析合并
  - 输出到 `precisePropertyData`

- [x] 7.5 统一社会信用代码解析 (`company_info_extractor.py`) ✅ (2026-01-21)
  - 解析 `市场监管总局统一社会信用代码（定向查询）/*.xlsx`
  - 补充公司信息
  - 输出到 `creditCodeData`

### Phase 8: P2 级外部数据解析

- [x] 8.1 保险信息解析 (`insurance_extractor.py`) ✅ (2026-01-21)
  - 解析 `保险信息（定向查询）/*.xlsx`
  - 提取：保险公司、险种、保额
  - 输出到 `insuranceData`

- [x] 8.2 公安部出入境记录解析 (`immigration_extractor.py`) ✅ (2026-01-21)
  - 解析 `公安部出入境记录（定向查询）/*.xlsx`
  - 提取：出入境时间、目的地
  - 输出到 `immigrationData`

- [x] 8.3 公安部旅馆住宿解析 (`hotel_extractor.py`) ✅ (2026-01-21)
  - 解析 `公安部旅馆住宿（定向查询）/*.xlsx`
  - 提取：入住时间、同住人
  - 输出到 `hotelData`

- [x] 8.4 公安部同住址/同车违章解析 (`cohabitation_extractor.py`) ✅ (2026-01-21)
  - 解析相关文件
  - 用于关系图谱补充
  - 输出到 `cohabitationData`

- [x] 8.5 铁路票面信息解析 (`railway_extractor.py`) ✅ (2026-01-21)
  - 解析 `铁路总公司票面信息（定向查询）/*.xlsx`
  - 提取：出行时间线
  - 输出到 `railwayData`

- [x] 8.6 航班进出港信息解析 (`flight_extractor.py`) ✅ (2026-01-21)
  - 解析 `中航信航班进出港信息（定向查询）/*.xlsx`
  - 提取：航班号、起降时间、机场
  - 输出到 `flightData`

### Phase 9: P3 级外部数据解析

- [x] 9.1 公安部驾驶证解析 (`p3_data_extractor.py`) ✅ (2026-01-21)
  - 解析 `公安部驾驶证（定向查询）/*.xlsx`
  - 提取：准驾车型、有效期
  - 输出到 `p3Data.driverLicenses`

- [x] 9.2 公安部交通违法解析 (`p3_data_extractor.py`) ✅ (2026-01-21)
  - 解析 `公安部交通违法（定向查询）/*.xlsx`
  - 提取：违法时间、地点、罚款、扣分
  - 输出到 `p3Data.trafficViolations`

- [x] 9.3 公安部出国（境）证件解析 (`p3_data_extractor.py`) ✅ (2026-01-21)
  - 解析 `公安部出国（境）证件（定向查询）/*.xlsx`
  - 提取：证件类型、号码、有效期
  - 输出到 `p3Data.exitDocuments`

- [x] 9.4 铁路总公司互联网注册信息解析 (`p3_data_extractor.py`) ✅ (2026-01-21)
  - 解析 `铁路总公司互联网注册信息（定向查询）/*.xlsx`
  - 提取：12306用户名、手机号、邮箱
  - 输出到 `p3Data.railwayRegistrations`

---

## 七、验证方法

| 阶段 | 验证方式 |
|------|----------|
| Phase 1 | 运行清洗后检查 `cleaned_data/*.xlsx` 是否有新增列 |
| Phase 2 | 检查 `profiles.json` 是否包含新增字段 |
| Phase 3 | 检查家庭汇总数据正确性 |
| Phase 4 | 配置项可读取、公司报告可生成 |
| Phase 5 | 完整重启后前端可正确显示所有数据 |
| Phase 6 | 检查 `bank_accounts_official`、`aml_alerts`、`company_info.json` 文件 |
| Phase 7 | 检查 `assets.json` 包含车辆、证券 |
| Phase 8 | 检查出入境、保险等补充数据 |

---

## 八、当前状态标记

- ⬜ 未开始
- 🔄 进行中
- ✅ 已完成
- ⏸️ 等待用户确认

---

## 九、工作量估算

| Phase | 内容 | 预计文件数 | 预计工时 |
|-------|------|------------|----------|
| 1-5 | 现有模块增强 | 5-8 | 1-2天 |
| 6 | P0外部数据解析 | 5 新建 | 2-3天 |
| 7 | P1外部数据解析 | 4 新建 | 2天 |
| 8 | P2外部数据解析 | 4 新建 | 1天 |
| **总计** | - | 15-20 | 约1周 |
