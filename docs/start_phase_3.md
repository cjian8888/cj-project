# Phase 3 启动 Prompt

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

## 当前阶段

**Phase 3: 家庭汇总**

## 任务目标

根据 `work_plan_master.md` 中的定义,Phase 3 的目标是实现家庭级别的资产和收支汇总。

### 任务清单

- [ ] 3.1 家庭汇总计算
  - 整合 `calculate_family_total_assets()` 到缓存
  - 剔除家庭成员间互转
  - 计算家庭净流入/净流出

### 涉及文件

- `family_finance.py`

### 预计工时

0.5天

## 上一阶段交接

请先阅读 `docs/handoff_phase_2.md` 了解上一阶段的完成情况。

**Phase 2 关键成果**:
- 新增 `calculate_yearly_salary()` 函数 - 年度工资统计
- 新增 `extract_large_transactions()` 函数 - 大额交易明细
- 新增 `build_company_profile()` 函数 - 公司画像构建

**遗留问题**:
- 大额交易提取需要在main.py中集成(将在Phase 5完成)
- 所有新功能需要在Phase 5重新生成缓存后才会生效

## 开始工作

请按照 `work_plan_master.md` 中 Phase 3 的任务清单开始工作。

完成后,请创建:
- `handoff_phase_3.md` 交接文档
- `start_phase_4.md` 启动文档

并更新 `work_progress.md` 中的进度记录。
