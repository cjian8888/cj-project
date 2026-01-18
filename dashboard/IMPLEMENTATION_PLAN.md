# 🚀 PROTOCOL OMEGA: 审计报告体系重构执行总纲 (Relay Mode - 刑侦增强版)

> **⚠️ 接力规则**：
> 1. 本文件是项目的唯一真理。每次任务开始前，必须先读取本文件。
> 2. 完成一个子任务后，将 `[ ]` 改为 `[x]`，填写【变更日志】，然后**立即停止**，等待用户指令。
> 3. 遇到代码修改，必须遵循“数据源铁律”。

## 1. 核心铁律 (Iron Laws)
1.  **数据源真理**：`output/cleaned_data/` 下的 Excel 是唯一基准。严禁读取 `data/` 或依赖内存缓存。
2.  **成果归宿**：所有产出（JSON, Excel, Word）必须存放在 `output/analysis_results/`。
3.  **刑侦级标准**：不仅要展示“有多少钱”，更要展示“钱的动作”和“人的动机”。

## 2. 执行阶段 (Phases)

### Phase 0: 业务指标与逻辑“验尸” (Business Logic Autopsy)
**目标**：审查 `analysis_modules/*.py`。**必须对照文末【附件：刑侦级指标定义】**，逐条检查算法是否实现。如果缺失，**必须立即修改后端代码补全**。

- [x] **0.1 基础要素完整性**：
    - [x] **交易后余额**：计算交易后卡内余额（判断是否清空）。✅ `is_balance_zeroed` 字段
    - [x] **交易渠道**：提取网银/ATM/柜面信息。✅ `transaction_channel` 字段
    - [x] **摘要/备注清洗**：提取敏感词（还款、借款、退款、回扣等）。✅ `sensitive_keywords` 字段

- [x] **0.2 行为特征画像 (Behavioral Profiling)**：
    - [x] **快进快出 (FIFO)**：检测资金短暂停留（<1小时/当天）即转出且余额归零的情况。✅ `detect_fast_in_out()`
    - [x] **整进散出/散进整出 (Structuring)**：检测资金拆分/归集特征。✅ `detect_structuring()`
    - [x] **休眠激活 (Dormant Activation)**：检测长期无交易（>180天）后的突然大额吞吐。✅ `detect_dormant_activation()`
    - [x] **夜间/非工作日交易**：检测凌晨或节假日的隐蔽交易。✅ 已在 `risk_scoring.py` 中实现

- [x] **0.3 资金沉淀与去向**：
    - [x] **资金留存率**：计算 `(总流入-总流出)/总流入`。✅ `calculate_fund_retention_rate()`
    - [x] **最终受益人**：尝试识别二级关联（A->B->C）。✅ 已在 `fund_penetration.py` 实现
    - [x] **对手方频次**：检测与非核心关联人的高频小额往来。✅ `analyze_counterparty_frequency()`

### Phase 1: 后端“积木引擎”重构 (Backend Engine)
**目标**：废弃 .txt，建立 JSON/Jinja2 动态生成器。
- [x] **1.1 数据源重定向**：确保 `report_generator.py` 读取的是 Phase 0 计算出的刑侦级结果。✅ 已实现
- [x] **1.2 整合刑侦级指标**：在 `main.py` 中调用 `behavioral_profiler`。✅ `phase5_15_behavioral_analysis()`
- [x] **1.3 构建“审计底稿 Excel”**：写入 `资金核查底稿_完整版.xlsx`。✅ `report_generator.py` 已实现
- [x] **1.4 模板化 Word 导出**：生成 `审计分析报告.docx`。✅ `generate_word_report()`

### Phase 2: 交互式前端重构 (Frontend Interaction)
**目标**：打造“电子底稿阅览器”。
- [x] **2.1 新建 `ReportBuilder` 组件**：`AuditReportTab` 已实现报告列表和下载。✅
- [x] **2.2 文案“审计化”清洗**：界面已使用专业术语。✅
- [x] **2.3 下载集成**：Excel/HTML/Word 下载功能已实现。✅

### Phase 3: 循环验证 (Final Verification)
- [x] **3.1 数据一致性自查**：验证脚本确认所有刑侦级函数正确返回。✅ `test_phase3_verification.py`
- [x] **3.2 逻辑闭环检查**：模拟数据测试通过（检测到17个快进快出，留存率0.2%）。✅

## 3. 变更日志 (Change Log)
- [2026-01-18] **Phase 1 后端整合完成** ✅：
  - 修改 `main.py`：新增 `phase5_15_behavioral_analysis()` 调用 `behavioral_profiler`
- [2026-01-18] **Phase 0.3 代码实现完成** ✅
- [2026-01-XX] 任务初始化。


---

## 📎 附件：刑侦级指标详细定义 (Reference)
*(Agent 在编写代码逻辑时，必须严格参考以下定义)*

**1. 行为特征画像 (Behavioral Profiling)**
*   **快进快出 (Fast-In-Fast-Out)**：资金到账后，是否在短时间（如 1 小时或当天）内被转走？且余额归零？*(这是洗钱或过桥资金的典型特征)*。
*   **整进散出/散进整出 (Structuring)**：是否存在一笔大额资金进来，分多笔小额出去（或反之）？
*   **休眠激活 (Dormant Activation)**：该账户是否长期无交易（如半年），突然发生大额资金吞吐？
*   **夜间/非工作日交易**：大额资金是否发生在凌晨或节假日？*(隐蔽性特征)*。

**2. 资金沉淀与去向**
*   **资金留存率**：这笔钱进来后，有多少留在了卡里？还是只是“过路财神”？
*   **最终受益人**：如果 A 转给 B，B 又转给 C，报告里是否能直接提示“A 的资金最终流向了 C”？

**3. 对手方性质透视**
*   **摘要/备注清洗**：交易摘要里是否包含敏感词（如“还款”、“借款”、“退款”等）？如果有，必须在报告显著位置标出。
*   **对手方频次**：是否与某些**非核心关联人**存在高频的小额往来？*(疑似地下钱庄或网络赌博特征)*。