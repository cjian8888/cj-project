# 穿云审计系统 - 后端功能补全总体工作计划

> 基于 `backend_gap_analysis.md` 和 `report_guidelines.md`
> 
> **创建时间**: 2026-01-20
> 
> **预计总工期**: 约1周 (5-7个工作日)

---

## 🎯 全局规则

### 对话窗口管理规则

为避免单个对话中引入过多数据导致混乱,采用以下规则:

1. **单阶段单对话**: 每个 Phase 在独立的对话窗口中完成
2. **完成即交接**: 每个 Phase 完成后,必须:
   - ✅ 更新 `work_progress.md` 记录完成状态
   - ✅ 创建 `handoff_phase_X.md` 交接文档
   - ✅ 生成下一阶段的启动 Prompt 文件 `start_phase_Y.md`
3. **新对话启动**: 使用上一阶段生成的启动 Prompt 开始新对话
4. **验证机制**: 每个阶段开始前,先验证上一阶段的产出

---

## 📋 工作阶段总览

| Phase | 名称 | 预计工时 | 优先级 | 状态 |
|-------|------|----------|--------|------|
| Phase 1 | 数据清洗补全 | 0.5天 | P0 | ⬜ 未开始 |
| Phase 2 | 计算模块补全 | 1天 | P0 | ⬜ 未开始 |
| Phase 3 | 家庭汇总 | 0.5天 | P0 | ⬜ 未开始 |
| Phase 4 | 配置与增强 | 0.5天 | P1 | ⬜ 未开始 |
| Phase 5 | 缓存重生成 | 0.5天 | P0 | ⬜ 未开始 |
| Phase 6 | P0外部数据解析 | 2-3天 | P0 | ⬜ 未开始 |
| Phase 7 | P1外部数据解析 | 2天 | P1 | ⬜ 未开始 |
| Phase 8 | P2外部数据解析 | 1天 | P2 | ⬜ 未开始 |

---

## Phase 1: 数据清洗补全 (P0)

**目标**: 增强银行账户识别和过滤能力

**预计工时**: 0.5天

**涉及文件**:
- `data_cleaner.py`
- `financial_profiler.py`

**任务清单**:
- [ ] 1.1 在 `data_cleaner.py` 中增加银行账户识别逻辑
  - 添加 `account_type` 列 (借记卡/信用卡/理财账户/证券账户)
  - 添加 `account_category` 列 (个人/对公/联名)
  - 添加过滤非真实银行卡的逻辑
  
- [ ] 1.2 在 `financial_profiler.py` 中新增账户提取函数
  - 新增 `extract_bank_accounts()` 函数
  - 返回去重后的银行账户列表
  - 账户状态判断(根据最后交易时间)

**验证方法**:
- 运行清洗后检查 `cleaned_data/*.xlsx` 是否有新增列
- 检查 `account_type` 和 `account_category` 列是否正确填充

**交付物**:
- 更新后的 `data_cleaner.py`
- 更新后的 `financial_profiler.py`
- `handoff_phase_1.md` 交接文档
- `start_phase_2.md` 启动文档

---

## Phase 2: 计算模块补全 (P0)

**目标**: 补全核心计算模块

**预计工时**: 1天

**涉及文件**:
- `financial_profiler.py`
- `income_analyzer.py`
- `config.py`

**任务清单**:
- [ ] 2.1 年度工资统计
  - 新增 `calculate_yearly_salary()` 函数
  - 更新 `profiles.json` 结构,添加 `yearly_salary` 字段
  
- [ ] 2.2 大额交易明细
  - 确保输出包含完整表格字段
  - 更新 `derived_data.json` 结构
  
- [ ] 2.3 公司画像构建
  - 新增 `build_company_profile()` 函数
  - 确保与个人画像格式一致

**验证方法**:
- 检查 `profiles.json` 是否包含 `yearly_salary` 字段
- 检查 `derived_data.json` 中大额交易明细是否完整

**交付物**:
- 更新后的 `financial_profiler.py`
- 更新后的 `income_analyzer.py`
- `handoff_phase_2.md` 交接文档
- `start_phase_3.md` 启动文档

---

## Phase 3: 家庭汇总 (P0)

**目标**: 实现家庭级别的资产和收支汇总

**预计工时**: 0.5天

**涉及文件**:
- `family_finance.py`

**任务清单**:
- [ ] 3.1 家庭汇总计算
  - 整合 `calculate_family_total_assets()` 到缓存
  - 剔除家庭成员间互转
  - 计算家庭净流入/净流出

**验证方法**:
- 检查家庭汇总数据正确性
- 验证成员间互转已正确剔除

**交付物**:
- 更新后的 `family_finance.py`
- `handoff_phase_3.md` 交接文档
- `start_phase_4.md` 启动文档

---

## Phase 4: 配置与增强 (P1)

**目标**: 补充配置项和增强功能

**预计工时**: 0.5天

**涉及文件**:
- `config.py`
- `financial_profiler.py`
- `related_party_analyzer.py`

**任务清单**:
- [ ] 4.1 配置项补充
  - 添加 `INVESTIGATION_UNIT_KEYWORDS` (调查单位关键词)
  - 添加 `BANK_ACCOUNT_EXCLUDE_KEYWORDS` (账户过滤关键词)
  
- [ ] 4.2 收入来源分类
  - 在 `financial_profiler.py` 中实现
  - 分类:合法收入/不明收入/可疑收入
  
- [ ] 4.3 与调查单位往来统计
  - 在 `related_party_analyzer.py` 中实现

**验证方法**:
- 配置项可读取
- 收入来源分类正确
- 公司报告可生成

**交付物**:
- 更新后的 `config.py`
- 更新后的 `financial_profiler.py`
- 更新后的 `related_party_analyzer.py`
- `handoff_phase_4.md` 交接文档
- `start_phase_5.md` 启动文档

---

## Phase 5: 缓存重生成 (P0)

**目标**: 确保所有新增字段写入缓存

**预计工时**: 0.5天

**涉及文件**:
- `main.py` 或缓存生成相关脚本

**任务清单**:
- [ ] 5.1 更新缓存生成逻辑
  - 确保新增字段写入缓存
  
- [ ] 5.2 验证缓存完整性
  - 检查所有新增字段
  - 验证数据格式正确

**验证方法**:
- 完整重启后前端可正确显示所有数据
- 缓存文件包含所有新增字段

**交付物**:
- 更新后的缓存生成脚本
- `handoff_phase_5.md` 交接文档
- `start_phase_6.md` 启动文档

---

## Phase 6: P0级外部数据解析 (P0)

**目标**: 解析最高优先级的外部数据源

**预计工时**: 2-3天

**新建文件**:
- `bank_account_extractor.py`
- `aml_analyzer.py`
- `company_info_extractor.py`
- `credit_report_extractor.py`

**任务清单**:
- [ ] 6.1 人民银行银行账户解析
  - 解析 `中国人民银行银行账户（定向查询）/*.xlsx`
  - 提取:银行名称、完整卡号、账户类型、账户状态、当前余额
  - 输出到 `profiles.json` → `bank_accounts_official`
  
- [ ] 6.2 人民银行反洗钱数据解析
  - 解析 `中国人民银行反洗钱（定向查询）/*.xlsx`
  - 提取:可疑交易记录、大额交易报告
  - 输出到 `suspicions.json` → `aml_alerts`
  
- [ ] 6.3 市场监管总局企业登记解析
  - 解析 `市场监管总局企业登记信息（定向查询）/*.xlsx`
  - 提取:公司名称、注册资本、法人、股东、经营范围
  - 输出到新文件 `company_info.json`
  
- [ ] 6.4 征信数据解析
  - 解析 `征信（定向查询）/*.xlsx`
  - 提取:信用评分、负债情况、贷款记录
  - 输出到 `profiles.json` → `credit_info`
  
- [ ] 6.5 银行业金融机构账户信息解析
  - 解析 `银行业金融机构账户信息（定向查询）/*.xlsx`
  - 与 6.1 合并或补充

**验证方法**:
- 检查 `bank_accounts_official`、`aml_alerts`、`company_info.json` 文件
- 验证数据完整性和准确性

**交付物**:
- 新建的解析模块文件
- `handoff_phase_6.md` 交接文档
- `start_phase_7.md` 启动文档

---

## Phase 7: P1级外部数据解析 (P1)

**目标**: 解析高优先级的外部数据源

**预计工时**: 2天

**新建/增强文件**:
- `vehicle_extractor.py`
- `securities_extractor.py`
- 增强 `asset_extractor.py`

**任务清单**:
- [ ] 7.1 公安部机动车解析
  - 解析 `公安部机动车（定向查询）/*.xlsx`
  - 提取:车牌号、品牌型号、购买时间、估价
  - 输出到 `assets.json` → `vehicles`
  
- [ ] 7.2 银行理财产品详情解析
  - 解析 `银行业金融机构金融理财（定向查询）/*.xlsx`
  - 解析 `理财产品（定向查询）/*.xlsx`
  - 提取:产品名称、持有金额、到期日
  - 与 `financial_profiler.py` 的理财分析合并
  
- [ ] 7.3 证券信息解析
  - 解析 `证券信息（定向查询）/*.xlsx`
  - 提取:证券公司、持仓股票、市值
  - 输出到 `assets.json` → `securities`
  
- [ ] 7.4 自然资源部精准查询解析
  - 解析 `自然资源部精准查询（定向查询）/*.xlsx`
  - 与现有不动产解析合并
  
- [ ] 7.5 统一社会信用代码解析
  - 解析 `市场监管总局统一社会信用代码（定向查询）/*.xlsx`
  - 补充公司信息

**验证方法**:
- 检查 `assets.json` 包含车辆、证券
- 验证理财数据与流水分析一致

**交付物**:
- 新建/更新的解析模块文件
- `handoff_phase_7.md` 交接文档
- `start_phase_8.md` 启动文档

---

## Phase 8: P2级外部数据解析 (P2)

**目标**: 解析中优先级的外部数据源

**预计工时**: 1天

**新建文件**:
- `insurance_extractor.py`
- `hotel_analyzer.py`
- `flight_analyzer.py`

**任务清单**:
- [ ] 8.1 保险信息解析
  - 解析 `保险信息（定向查询）/*.xlsx`
  - 提取:保险公司、险种、保额
  
- [ ] 8.2 公安部出入境记录解析
  - 解析 `公安部出入境记录（定向查询）/*.xlsx`
  - 提取:出入境时间、目的地
  - 用于时间线分析
  
- [ ] 8.3 公安部旅馆住宿解析
  - 解析 `公安部旅馆住宿（定向查询）/*.xlsx`
  - 提取:入住时间、同住人
  - 用于同住分析
  
- [ ] 8.4 公安部同住址/同车违章解析
  - 解析相关文件
  - 用于关系图谱补充
  
- [ ] 8.5 铁路票面信息解析
  - 解析 `铁路总公司票面信息（定向查询）/*.xlsx`
  - 提取:出行时间线
  
- [ ] 8.6 中航信航班进出港信息解析 (新增)
  - 解析 `中航信航班进出港信息（定向查询）/*.xlsx`
  - 提取:航班号、起降时间、起降机场
  - 用于时间线分析和出行轨迹
  - 可与航班同行人信息关联分析

**验证方法**:
- 检查出入境、保险等补充数据
- 验证时间线分析功能

**交付物**:
- 新建的解析模块文件
- `handoff_phase_8.md` 交接文档
- 最终总结文档 `final_summary.md`

---

## 📝 交接文档模板

每个 Phase 完成后,创建 `handoff_phase_X.md`,包含:

```markdown
# Phase X 交接文档

## 完成时间
YYYY-MM-DD HH:MM

## 完成状态
- [x] 任务1
- [x] 任务2
- [ ] 遗留问题(如有)

## 修改的文件
- file1.py - 修改说明
- file2.py - 修改说明

## 新增的文件
- new_file.py - 功能说明

## 验证结果
- 验证项1: ✅ 通过
- 验证项2: ✅ 通过

## 遗留问题
- 问题1 (如有)
- 问题2 (如有)

## 下一阶段准备
- 前置条件已满足
- 启动文档: start_phase_Y.md
```

---

## 🚀 启动 Prompt 模板

每个 Phase 完成后,创建 `start_phase_Y.md`,包含:

```markdown
# Phase Y 启动 Prompt

## 背景
我正在进行穿云审计系统的后端功能补全工作。

## 已完成阶段
- ✅ Phase 1: 数据清洗补全
- ✅ Phase 2: 计算模块补全
- ... (列出所有已完成的阶段)

## 当前阶段
Phase Y: [阶段名称]

## 任务目标
[从 work_plan_master.md 复制该阶段的目标和任务清单]

## 上一阶段交接
请先阅读 `handoff_phase_X.md` 了解上一阶段的完成情况。

## 开始工作
请按照 `work_plan_master.md` 中 Phase Y 的任务清单开始工作。
完成后,请创建 `handoff_phase_Y.md` 和 `start_phase_Z.md`。
```

---

## 📊 进度跟踪

进度记录在 `work_progress.md` 中,每个 Phase 完成后更新。

---

## 🔗 相关文档

- `backend_gap_analysis.md` - 详细的功能缺口分析
- `report_guidelines.md` - 报告生成准则
- `architecture_overview.md` - 系统架构概览
- `work_progress.md` - 工作进度记录

---

## 📅 版本记录

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-01-20 | 初始版本,包含全局规则和8个Phase |
| v1.1 | 2026-01-20 | 补充 Phase 8.6 中航信航班进出港信息解析 |
