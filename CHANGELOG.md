# 变更日志 (CHANGELOG)

本文件记录资金穿透与关联排查系统的重要版本更新。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

---

## [v4.3.0] - 2026-01-17

### 🎯 数据铁律重构：`/api/results` 接口持久化

解决 `/api/results` 依赖内存变量的问题，实现数据一致性保障。

### 新增功能

#### 分析缓存机制 (`api_server.py`)
- **`_get_cleaned_data_mtime()`**: 获取 `cleaned_data/` 目录最新修改时间
- **`_save_analysis_cache()`**: 分析完成时保存结果到 `output/analysis_cache/`
- **`_load_analysis_cache()`**: 读取缓存并校验与 `cleaned_data` 的一致性

#### 缓存目录结构
```
output/analysis_cache/
├── metadata.json       # 元数据（版本、时间戳）
├── profiles.json       # 资金画像
├── suspicions.json     # 可疑交易
├── derived_data.json   # 借贷/收入分析
└── graph_data.json     # 图谱数据（可选）
```

### 变更

#### `/api/results` 接口重构
- **废弃**直接返回内存变量 `analysis_state.results`
- **改为**从 `analysis_cache/` 目录读取 JSON 文件
- **新增** `source` 字段标识数据来源（`analysis_cache` / `memory`）
- **新增**一致性校验：`cleaned_data` 更新后，旧缓存自动失效

### 修复

- 解决用户修改清洗规则后前端不更新的问题
- 解决服务重启后需重新分析的问题（缓存持久化）

### 铁律修复（数据复用原则）

修复以下模块中现金交易识别重复计算的问题，改为直接读取已标记的 `is_cash` 列：

| 模块 | 修复函数 |
|------|----------|
| `suspicion_detector.py` | `run_all_detections()` - 现金碰撞检测 |
| `risk_scoring.py` | `score_transaction()` - 交易风险评分 |
| `risk_scoring.py` | `score_account()` - 账户风险评分 |
| `financial_profiler.py` | `analyze_fund_flow()` - 资金流向分析 |
| `financial_profiler.py` | `detect_large_cash()` - 大额现金检测 |
| `financial_profiler.py` | `categorize_transactions()` - 交易分类 |

### 项目维护

- 清理中间过程文件（审计报告、截图等）
- 压缩日志文件至最近 100 行

### 架构优化（单一修改点原则）

- 新增 `config.py: COLUMN_MAPPING` - Excel 列名统一映射配置
- 新增 `config.py: COLUMN_ORDER` - Excel 列显示顺序配置
- 新增 `config.py: *_COLUMN_VARIANTS` - 读取兼容性列名变体
- 修改 `data_cleaner.py` - 使用 `config.COLUMN_MAPPING` 替代硬编码
- 修改 `api_server.py` - 使用 `config.*_COLUMN_VARIANTS` 替代硬编码

**效果**：今后修改 Excel 列名只需改 `config.py` 一处，其他模块自动引用。

---

## [v4.2.0] - 2026-01-16

### 🔒 离线环境适配

解决资金流向可视化在单机/离线环境下无法渲染的问题。

### 问题修复

#### `flow_visualizer.py` - 移除外部 CDN 依赖
- **问题**: `templates/flow_visualization.html` 和 fallback HTML 使用外部 CDN (`https://unpkg.com/vis-network`)，导致单机环境下图谱无法渲染
- **修复**: 
  - `_generate_fallback_html` 改为读取本地 `vis-network.min.js` 并内联到 HTML
  - `_generate_html_visualization` 添加 `VIS_JS_CONTENT` 模板变量
- **模板更新**: `templates/flow_visualization.html` CDN 引用替换为 `{{VIS_JS_CONTENT}}`

### 验证结果
- 完整分析流程通过（耗时 47 秒，处理 3.4 万条交易）
- 图谱成功渲染（59 节点，80 条资金流向）
- 无任何外部网络请求

---

## [v4.1.0] - 2026-01-11

### 🎯 Phase 4：解决"线索割裂"和"黑盒评分"痛点

基于 GLM-4.7 的"深度审视报告"建议，完成以下核心改进。

### 新增模块

#### `clue_aggregator.py` - 线索聚合引擎（新建）
- 以"人员/公司"为索引键，聚合所有模块的发现
- 包括：资金闭环、过账通道、高风险交易、团伙、周期性收入、资金突变、延迟转账
- 计算综合风险分（0-100分）
- 生成"证据包"视图报告

### 功能增强

#### `risk_scoring.py` - 风险分归因解释
- 新增 `explain_risk_score()` 函数
- 用自然语言解释为什么一笔交易风险分高
- 示例输出："该笔交易风险分95分，主要因为：金额48万是该账户历史均值的9.6倍；发生在凌晨2:17（深夜交易）"

### 新增报告
- `线索聚合报告.txt` - 证据包视图

---

## [v4.0.0] - 2026-01-11

### 🚀 重大升级：从"数据清洗工具"升级为"智能深度资金侦查平台"

基于 GLM-4.7 模型的专业审计建议，本版本进行了三阶段重大升级。

### 新增模块

#### 1. `fund_penetration.py` v2.0 - 图论深度分析
- **MoneyGraph 类**：有向资金图数据结构
- **多跳路径追踪**：发现 A→B→C→D 的复杂资金链路
- **资金闭环检测**：识别 A→B→C→A 的利益回流结构
- **过账通道识别**：发现流量巨大但余额归零的空壳/马甲账户
- **资金枢纽分析**：识别与多方有往来的关键控制节点
- **性能优化**：添加超时机制和关键节点过滤，避免大图分析卡死

#### 2. `risk_scoring.py` - 统一风险评分引擎（新建）
- 交易级风险评分（金额/对手方/时间/摘要/关联五维度）
- 对手方风险画像
- 账户级风险评估
- 批量评分与自动排序

#### 3. `time_series_analyzer.py` - 时序分析模块（新建）
- **周期性收入检测**：发现"每月5日固定入账5万"的养廉资金模式
- **资金突变检测**：发现突然激增的异常收入（使用滚动 Z-Score）
- **固定延迟转账**：发现"收入后 N 天固定转出"的利益分配协议

### 增强功能

#### `income_analyzer.py`
- 新增 `_calculate_confidence_score()` 可信度评分函数（0-100分）
- 新增交易去重逻辑，避免同一笔交易重复出现在多个报告类别
- 可信度评分显示在报告中，方便审计人员优先排序

#### `config.py`
- 新增 `KNOWN_WEALTH_PRODUCTS` 白名单（53个知名理财产品）
- 减少理财赎回被误标为"来源不明收入"的问题

#### `ml_analyzer.py`
- 已有完善的公共节点排除列表（支付宝、微信等）
- 团伙识别只在核心人员/涉案公司之间构建图

### 性能优化
- 图论分析添加 30 秒超时机制
- 只从核心人员/公司节点开始搜索闭环
- 排除支付宝、微信、银行等公共节点
- 限制最大闭环数量（100个）和路径数量（50条）

### 测试结果
- 执行时间：50.88 秒（全量分析）
- 资金闭环：44 个
- 过账通道：4 个
- 资金突变事件：112 个
- 固定延迟转账：27 个

---

## [v3.2.0] - 2026-01-10

### 功能完善
- 修复理财产品误判问题
- 增加政府机关白名单
- 优化借贷分析排除规则

---

## [v3.0.0] - 2026-01-08

### 核心功能
- 完整的数据清洗与合并流程
- 多源数据碰撞分析
- 借贷行为检测
- 异常收入识别
- 资金流向可视化
- 机器学习风险预测

---

## 贡献者
- 系统开发：Claude/Antigravity
- 审计建议：GLM-4.7

## 许可证
内部使用，仅限纪检监察系统
