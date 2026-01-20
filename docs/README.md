# 工作文档总览

> **项目**: 穿云审计系统后端功能补全
> 
> **创建时间**: 2026-01-20
> 
> **目的**: 引导开发者快速了解项目规划和工作流程

---

## 📚 核心文档索引

### 1. 工作计划与进度

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [work_plan_master.md](work_plan_master.md) | **总体工作计划** - 包含8个Phase的详细任务清单 | ⭐⭐⭐ |
| [work_progress.md](work_progress.md) | **工作进度记录** - 实时更新每个Phase的完成状态 | ⭐⭐⭐ |
| [backend_gap_analysis.md](backend_gap_analysis.md) | **后端功能缺口分析** - 详细的待办清单和优先级 | ⭐⭐⭐ |

### 2. 系统设计与规范

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [architecture_overview.md](architecture_overview.md) | **系统架构概览** - 数据流向和模块职责 | ⭐⭐⭐ |
| [data_processing_principle.md](data_processing_principle.md) | **数据处理原则** - 核查底稿机制和数据复用铁律 | ⭐⭐⭐ |
| [report_guidelines.md](report_guidelines.md) | **报告生成准则** - 初查报告的标准框架和分析维度 | ⭐⭐ |

### 3. 数据源与扫描结果

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [data_source_scan.md](data_source_scan.md) | **数据源扫描结果** - 28个数据源的详细清单 | ⭐⭐ |
| [report_overview.md](report_overview.md) | **报告全貌展示** - 可视化展示报告结构 | ⭐ |

### 4. 工作日志

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [worklog_2026-01-20.md](worklog_2026-01-20.md) | **2026-01-20工作日志** - 今日工作内容记录 | ⭐ |

### 5. 交接与启动文档

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [handoff_template.md](handoff_template.md) | **交接文档模板** - 每个Phase完成后使用 | ⭐⭐ |
| [start_phase_1.md](start_phase_1.md) | **Phase 1启动文档** - 新对话窗口启动指令 | ⭐⭐⭐ |

---

## 🚀 快速开始

### 新手入门 (按顺序阅读)

1. **了解项目背景**
   - 阅读 [architecture_overview.md](architecture_overview.md) - 了解系统架构
   - 阅读 [data_processing_principle.md](data_processing_principle.md) - 理解数据处理原则

2. **查看工作计划**
   - 阅读 [work_plan_master.md](work_plan_master.md) - 了解8个Phase的任务
   - 查看 [work_progress.md](work_progress.md) - 了解当前进度

3. **开始工作**
   - 阅读 [start_phase_1.md](start_phase_1.md) - 启动Phase 1工作
   - 参考 [backend_gap_analysis.md](backend_gap_analysis.md) - 查看详细的功能缺口

### 继续工作 (Phase N已完成)

1. **查看上一阶段交接**
   - 阅读 `handoff_phase_N.md` - 了解上一阶段的完成情况

2. **启动下一阶段**
   - 阅读 `start_phase_N+1.md` - 获取下一阶段的启动指令

3. **更新进度**
   - 完成后更新 [work_progress.md](work_progress.md)
   - 创建 `handoff_phase_N+1.md` 和 `start_phase_N+2.md`

---

## 📋 工作流程

### 全局规则

为避免单个对话中引入过多数据导致混乱,采用以下规则:

1. **单阶段单对话**: 每个Phase在独立的对话窗口中完成
2. **完成即交接**: 每个Phase完成后,必须:
   - ✅ 更新 `work_progress.md` 记录完成状态
   - ✅ 创建 `handoff_phase_X.md` 交接文档
   - ✅ 生成下一阶段的启动Prompt文件 `start_phase_Y.md`
3. **新对话启动**: 使用上一阶段生成的启动Prompt开始新对话
4. **验证机制**: 每个阶段开始前,先验证上一阶段的产出

### Phase工作流程

```
┌─────────────────────────────────────────┐
│  1. 阅读 start_phase_X.md               │
│     - 了解任务目标                       │
│     - 查看任务清单                       │
│     - 阅读参考文档                       │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  2. 执行任务                             │
│     - 按照任务清单逐项完成               │
│     - 遵循数据处理原则                   │
│     - 编写代码并测试                     │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  3. 验证结果                             │
│     - 运行验证方法                       │
│     - 检查数据质量                       │
│     - 确保所有验证通过                   │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  4. 创建交接文档                         │
│     - 使用 handoff_template.md 模板     │
│     - 记录完成状态和修改文件             │
│     - 记录验证结果和遗留问题             │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  5. 创建启动文档                         │
│     - 生成 start_phase_Y.md             │
│     - 包含下一阶段的任务目标             │
│     - 包含前置依赖和准备工作             │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  6. 更新进度记录                         │
│     - 更新 work_progress.md             │
│     - 标记当前Phase为已完成              │
│     - 填写完成时间和详细记录             │
└─────────────────────────────────────────┘
```

---

## 🎯 核心原则

### 数据处理原则

详见 [data_processing_principle.md](data_processing_principle.md)

**核心要点**:
1. ✅ `output/cleaned_data/` 是后续分析的唯一数据来源
2. ✅ 所有外部数据源解析后写入**核查底稿Excel**
3. ✅ 核查底稿Excel是人工审阅的主要载体
4. ✅ JSON缓存是程序计算的数据来源
5. ✅ Excel和JSON保持同步

### 对话窗口管理

详见 [work_plan_master.md](work_plan_master.md) 的"全局规则"部分

**核心要点**:
1. 每个Phase在独立对话窗口中完成
2. 完成后创建交接文档和启动文档
3. 新对话使用启动文档开始
4. 避免单个对话引入过多数据

---

## 📊 工作阶段总览

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

**总预计工期**: 约1周 (5-7个工作日)

---

## 🔍 常见问题

### Q1: 从哪里开始?

**A**: 阅读 [start_phase_1.md](start_phase_1.md),在新对话窗口中启动Phase 1工作。

### Q2: 如何理解数据处理原则?

**A**: 阅读 [data_processing_principle.md](data_processing_principle.md),重点理解"核查底稿Excel"的作用和"唯一数据来源"原则。

### Q3: 如何知道当前进度?

**A**: 查看 [work_progress.md](work_progress.md),了解每个Phase的完成状态。

### Q4: 如何交接给下一个对话?

**A**: 使用 [handoff_template.md](handoff_template.md) 创建交接文档,并生成下一阶段的启动文档。

### Q5: 外部数据源如何处理?

**A**: 参考 [data_processing_principle.md](data_processing_principle.md) 的"外部数据源 → 核查底稿Excel"部分,遵循"解析 → 标准化 → 写入Excel → 缓存"的流程。

---

## 📞 需要帮助?

如果遇到问题:

1. **查看相关文档**: 在上面的文档索引中查找相关主题
2. **查看架构文档**: [architecture_overview.md](architecture_overview.md) 了解整体架构
3. **查看数据处理原则**: [data_processing_principle.md](data_processing_principle.md) 了解数据流向
4. **查看功能缺口分析**: [backend_gap_analysis.md](backend_gap_analysis.md) 了解详细任务

---

## 📅 版本记录

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-01-20 | 初始版本,创建文档总览 |

---

**祝工作顺利!** 🎉
