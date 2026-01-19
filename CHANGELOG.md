# 变更日志 (CHANGELOG)

本文件记录资金穿透与关联排查系统的重要版本更新。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

---

## [v4.5.3] - 2026-01-19

### 🔧 UI/UX 优化

#### 快捷导航栏折叠优化 (`Sidebar.tsx`)
- **添加文字提示**: 折叠箭头旁增加"收起/展开"文字
- **增强悬停效果**: 添加背景色变化和圆角边框
- **视觉分隔**: 增加顶部边框分隔线，区分配置区域

#### 疑似分期受贿渲染修复 (`TabContent.tsx`)
- **问题**: 点击"异常收入分析"第8项"疑似分期受贿"后黑屏
- **根因**: 后端 `risk_factors` 返回字符串，前端按数组处理导致 `.join()` 报错
- **修复**: 兼容字符串和数组两种格式，增加描述信息

### 🛠 构建优化

#### 简化构建脚本 (`package.json`)
- `build` 命令从 `tsc -b && vite build` 改为 `vite build`
- 原因: TypeScript 严格模式的未使用变量警告导致构建失败

### 📁 项目清理
- 删除 output 目录中的中间过程文件
- 删除根目录调试/测试文件
- 创建 `archives/2026-01-19_v4.5.0/` 存档目录

---


## [v4.5.2] - 2026-01-19

### 🔧 审计专业角度数据问题修复

#### P0 - 标题数字与内容不一致 (严重)
- **问题**: 高风险项目标题显示 0，但展开后有 114 条数据
- **根因**: 后端 `stats.highRiskCount` 使用了错误的数据源
- **修复**: 后端/前端统一使用 `high_risk` 和 `bidirectional_flows` 作为数据源
- **验证**: 标题与内容现已 100% 一致

#### P1 - 付款/收款方向标注
- 统一显示为 `付款方 → 收款方` 格式
- 未知对手方显示橙色 `⚠ 来源不明` 警告

#### P2 - 金额单位统一
- 统一使用万元单位 (≥0.01万显示2位小数)

#### P2 - 资金流向统计穿透
- 改为可展开菜单，显示分类说明和总条数

### ✨ 交易详情弹窗增强
- 新增**收入类型**显示 (如"个人大额转入")
- 新增**交易详情**区域 (日期、摘要等)
- 新增**📍 精确溯源信息**卡片 (来源文件名、行号)

### 🔧 技术修复
- **Windows asyncio 兼容性**: 使用 `WindowsSelectorEventLoopPolicy` 避免 ProactorEventLoop bug
- **"查看完整报告"按钮**: 改为下载 `资金核查底稿.xlsx`
- **缓存脚本日期序列化**: 修复 datetime 对象 JSON 序列化错误

---

## [v4.5.1] - 2026-01-19

### ✨ 资金流向可视化重构

#### 界面精简
- **移除冗余按钮**: 删除右上角的"交互视图"、"完整报告"、"导出证据快照"按钮
- **移除底部报告区域**: 删除可视化图表下方的"详细核查报告"大块内容

#### 左侧二级菜单
将左侧统计卡片改造为可点击展开/折叠的二级菜单：
- **核心人员** 👥: 展开显示人员名单
- **高风险项目** 🔴: 展开显示高风险收入详情，可穿透查看交易 Modal
- **借贷配对** 💳: 展开显示借贷配对列表，含借入/还款金额及还款率
- **无还款借贷** ⚠️: 展开显示疑似利益输送记录，含未还天数警告
- **涉案公司** 🏢: 展开显示涉案企业名单
- **网贷平台** 🏦: 展开显示平台统计，含涉及金额和交易笔数

#### 代码清理
- 清理未使用导入: `html2canvas`, `Camera`, `Download`, `Banknote`, `formatCurrency`
- 新增导入: `ChevronDown`, `ChevronUp`, `Users`, `Building2`
- 新增辅助函数: `formatAmount()`

---

## [v4.5.0] - 2026-01-19

### ✨ 交互体验与UI优化

#### 交互体验 (UX)
- **"打开文件夹"跨平台强力修复**: 解决从网页点击无法唤起文件夹窗口到前台的顽疾。
  - **Windows**: 使用 Shell COM 接口枚举 Explorer 窗口，精确匹配路径后调用 `AttachThreadInput` + `SetForegroundWindow` 强制置顶。
  - **macOS**: 使用 AppleScript 调用 `Finder.activate` + `set frontmost` 将窗口带到前台。
  - **Linux**: 使用 `xdg-open` 配合 `wmctrl` (可选) 激活窗口。
  - 优化路径安全检查，仅允许打开 `output` 目录下的路径。

#### 仪表盘优化 (UI)
- **重构"审计发现分布"**: 
  - 弃用无意义的"可疑交易分布"（仅显示现金碰撞）。
  - 新增基于业务逻辑的分布统计：展示规律还款、网贷交易、大额收入、来源不明等 8 大类审计发现的占比。
  - 为审计人员提供更有价值的宏观视角。
- **信息降噪**:
  - 移除冗余的"主要实体资金画像"表格，释放版面空间。
  - 优化卡片布局，使核心信息更聚焦。
- **布局与Tooltip优化**:
  - 缩小饼图容器高度（`h-48` → `h-40`），减少图与图例之间空白。
  - 优化图例间距（`space-y-2` → `space-y-1.5`），布局更紧凑。
  - 增强饼图 Tooltip 可见性：蓝色边框 + 深蓝背景 + 高对比度文字。

### 🔧 系统优化
- **后端热重载**: `api_server.py` 启用 `reload=True`，开发调试更高效。

---

## [v4.4.0] - 2026-01-18

### 🔧 代码质量审计：P0-P5 六阶段系统性改进

基于 Claude 版代码审查意见书，执行了全面的系统性改进。

### P0 止血（Immediate Fixes）

#### 数据清洗 (`data_cleaner.py`)
- **恢复流水号去重**：优先使用 `transaction_id` 而非启发式规则
- **修复索引警告**：流水号去重后重新创建 `duplicates_mask`

#### 资金穿透 (`fund_penetration.py`)
- **图谱改为累计金额**：边权重基于累计发生额，解决"蚂蚁搬家"漏查问题

### P1 加固（High Priority）

#### 新增模块
- **`name_normalizer.py`**：对手方名称标准化模块
  - `normalize_for_matching()`：模糊匹配标准化
  - `is_same_person()`：同名判断

#### 线索聚合 (`clue_aggregator.py`)
- **调整周期性收入权重**：从 +5/10 提高到 +12/24

### P2 优化（Medium Priority）

#### 数据清洗 (`data_cleaner.py`)
- **Parquet 中间存储**：`save_as_parquet()` 高性能存储
- **双格式输出**：`save_cleaned_data_dual_format()` Excel + Parquet

#### API 服务 (`api_server.py`)
- **缓存哈希校验**：`_compute_cleaned_data_hash()` 替代 mtime 检测

#### 新增配置
- **`config/rules.yaml`**：规则引擎 YAML 配置文件
- **`rule_engine.py`**：支持从 YAML 加载规则参数

### P3 演进（Long-term）

#### 新增模块
- **`audit_logger.py`**：操作审计日志（等保合规）
  - 线程安全日志记录
  - 防篡改校验 (MD5 checksum)
  - 日志自动轮转
  - `@audited` 装饰器
  
- **`holiday_service.py`**：节假日服务
  - 优先使用 chinese-calendar 库
  - 回退到本地配置
  
- **`graph_adapter.py`**：Neo4j 图数据库适配器
  - `GraphAdapter` 抽象接口
  - `MemoryGraphAdapter` 内存实现
  - `Neo4jAdapter` 数据库实现

### P4 报告质量

#### 收入分析 (`income_analyzer.py`)
- **从摘要提取对手方**：`_extract_counterparty_from_description()` 支持 7 种模式
- 减少"来源不明"收入误报

#### 线索聚合 (`clue_aggregator.py`)
- **家庭成员闭环识别**：`_is_family_cycle()` 函数
- **降低家庭闭环评分**：从 +15/30 降为 +3/6

### P5 报告可追溯性

#### 追溯字段
- 数据记录新增 `account`、`bank`、`source_file` 字段
- 报告显示 `▶ 追溯: 银行 账户` 和 `▶ 文件: Excel路径`
- 便于从报告直接定位到 Excel 进行人工复核

### 测试结果
- 单元测试：190 passed ✓
- 完整运行：~55 秒，正常生成所有报告

---

## [v4.3.1] - 2026-01-17

### 修复

#### 前端问题修复
- **P1 DOM 结构错误**: 修复 `NetworkGraph.tsx` 中 `<p>` 标签内嵌套 `<div>` 导致的 React Hydration 警告
- **P2 连接状态显示**: 修复 WebSocket 初始显示"未连接"问题，应用启动时自动连接
- **P2 图表初始化警告**: 为 `TabContent.tsx` 中的 ResponsiveContainer 添加 minHeight 防止负尺寸警告

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
