# 2026-03-14 逐跳样本折叠展开 explainability

## 本轮目标

- 把上一轮“样本原始流水引用”继续推进到“样本总数 / 截断状态 / 前端逐跳展开”
- 明确区分“当前展示的是样本”与“底层实际共有多少条支撑流水”，避免审计误判

## 本次改动

### 1. `fund_penetration.py`

- 新增常量：
  - `TRANSACTION_REF_SAMPLE_LIMIT = 5`
- `MoneyGraph` 边样本保留数量从 3 条提升到 5 条
- `_build_cycle_edge_segments` 新增字段：
  - `transaction_refs_total`
  - `transaction_ref_sample_count`
  - `transaction_refs_truncated`
  - `transaction_refs_limit`
- 样本交易按金额优先排序，逐跳展示更稳定

### 2. `utils/path_explainability.py`

- `build_relay_path_explainability` 新增时间轴元数据：
  - `time_axis_total`
  - `time_axis_sample_count`
  - `time_axis_truncated`

### 3. `specialized_reports.py`

- `资金穿透分析报告` 的闭环边级明细新增样本提示：
  - `原始流水样本: 当前展示 X 条，实际共 Y 条`
- 中转时间轴新增样本提示：
  - `时间轴样本: 当前展示 X 步，实际共 Y 步`

### 4. `dashboard/src/components/NetworkGraph.tsx`

- 闭环卡片从“只显示第 1 跳摘要”升级为：
  - 路径级折叠
  - 每一跳独立折叠
  - 每一跳展示原始流水样本、来源文件、行号、摘要
  - 明确提示“当前回传样本数 / 实际总数”
- 第三方中转卡片新增：
  - 时序明细折叠面板
  - 每一步事件展示来源文件与行号

## 涉及函数树

```text
fund_penetration.py
├── _build_supporting_refs
├── _supporting_ref_sort_key
└── _build_cycle_edge_segments

utils/path_explainability.py
└── build_relay_path_explainability

specialized_reports.py
├── _append_cycle_edges
└── _append_time_axis

dashboard/src/components/NetworkGraph.tsx
├── getSegmentTransactionTotal
├── getTimeAxisTotal
└── 闭环 / 中转折叠展开渲染
```

## 验证结果

- `pytest -q tests/test_aml_phase1_foundation.py tests/test_specialized_reports.py tests/test_clue_aggregator.py tests/test_api_server_config_flow.py tests/test_investigation_report_builder_metrics.py tests/test_report_generator.py`
  - `66 passed, 2 warnings`
- `cd dashboard && npm run type-check`
  - passed

## 当前影响判断

- 前端输入界面：
  - 不变
- 图谱展示：
  - 闭环和中转都能展开到“路径 -> 跳 -> 原始流水样本”
- 报告输出：
  - 会明确提示“当前仅展示样本，不代表全量逐笔已全部展开”
- 兼容性：
  - 仍然是增量字段
  - 旧字段和旧入口未删除
