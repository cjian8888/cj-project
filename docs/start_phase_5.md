# Phase 5 启动 Prompt

## 背景

我正在进行穿云审计系统的后端功能补全工作。

## 已完成阶段

- ✅ Phase 1: 数据清洗补全 (2026-01-20 14:44完成)
  - 新增账户类型识别功能
  - 新增账户提取函数
  
- ✅ Phase 2: 计算模块补全 (2026-01-20 14:55完成)
  - 新增年度工资统计功能
  - 新增大额交易明细提取功能
  - 新增公司画像构建功能

- ✅ Phase 3: 家庭汇总 (2026-01-20 15:10完成)
  - 新增家庭汇总计算功能

- ✅ Phase 4: 配置与增强 (2026-01-20 15:20完成)
  - 新增调查单位关键词配置
  - 新增账户过滤关键词配置
  - 新增收入来源分类功能
  - 新增调查单位往来统计功能

## 当前阶段

**Phase 5: 缓存重生成**

## 任务目标

根据 `work_plan_master.md` 中的定义,Phase 5 的目标是确保所有新增字段写入缓存。

### 任务清单

- [ ] 5.1 更新缓存生成逻辑
  - 确保 Phase 1-4 新增的所有字段写入缓存
  - 验证缓存文件结构
  
- [ ] 5.2 验证缓存完整性
  - 检查所有新增字段
  - 验证数据格式正确
  - 测试前端显示

### 涉及文件

- `main.py` (或缓存生成相关脚本)
- `output/analysis_results_cache.json`

### 新增字段清单

**Phase 1 新增**:
- `bank_accounts` - 银行账户列表
- `account_type` - 账户类型
- `account_category` - 账户类别
- `is_real_bank_card` - 是否真实银行卡

**Phase 2 新增**:
- `yearly_salary` - 年度工资统计

**Phase 3 新增**:
- `family_summary` - 家庭汇总数据

**Phase 4 新增**:
- `income_classification` - 收入来源分类

### 预计工时

0.5天

## 上一阶段交接

请先阅读 `docs/handoff_phase_4.md` 了解上一阶段的完成情况。

**Phase 4 关键成果**:
- 新增 `INVESTIGATION_UNIT_KEYWORDS` 配置项 - 调查单位关键词
- 新增 `BANK_ACCOUNT_EXCLUDE_KEYWORDS` 配置项 - 账户过滤关键词
- 新增 `classify_income_sources()` 函数 - 收入来源分类
- 新增 `analyze_investigation_unit_flows()` 函数 - 调查单位往来统计

**遗留问题**:
- 配置项需要用户填写(将在具体案件分析时填写)
- 实际数据验证需要在Phase 5完成

## 开始工作

请按照 `work_plan_master.md` 中 Phase 5 的任务清单开始工作。

**重点任务**:
1. 检查 `main.py` 中的缓存生成逻辑
2. 确保所有新增字段都被写入缓存
3. 重新生成缓存文件
4. 验证缓存完整性
5. 测试前端显示

完成后,请创建:
- `handoff_phase_5.md` 交接文档
- `start_phase_6.md` 启动文档

并更新 `work_progress.md` 中的进度记录。
