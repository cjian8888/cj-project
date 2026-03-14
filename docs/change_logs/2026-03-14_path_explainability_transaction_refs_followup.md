# 2026-03-14 逐跳原始交易映射 explainability

## 本轮目标

- 把路径 explainability 从“边级金额 / 时间轴”继续推进到“原始流水引用”
- 让审计员能看到路径上的每一跳对应哪些样本交易、来自哪个文件、哪一行

## 本次改动

### 1. `fund_penetration.py`

- 构图边新增保留字段：
  - `supporting_transactions`
  - `transaction_count`
- 闭环 explainability 的 `edge_segments` 新增：
  - `transaction_refs`
  - `transaction_count`

### 2. `related_party_analyzer.py`

- 第三方中转链新增原始溯源字段：
  - `outflow_source_file`
  - `outflow_source_row_index`
  - `inflow_source_file`
  - `inflow_source_row_index`

### 3. `utils/path_explainability.py`

- 中转 `time_axis` 事件已保留：
  - `source_file`
  - `source_row_index`

### 4. `specialized_reports.py`

- `资金穿透分析报告` 新增输出：
  - `原始流水`
  - 闭环每一跳的样本流水引用
  - 中转时间轴事件的样本流水引用

### 5. `dashboard/src/components/NetworkGraph.tsx`

- 闭环卡片新增：
  - 样本原始流水摘要
- 第三方中转卡片新增：
  - 时间轴事件的来源文件与行号

## 涉及函数树

```text
fund_penetration.py
├── MoneyGraph.add_edge
├── _build_cycle_edge_segments
└── build_cycle_record

related_party_analyzer.py
└── _find_relay_chains

utils/path_explainability.py
└── build_relay_path_explainability

specialized_reports.py
└── _generate_penetration_report

dashboard/src/components/NetworkGraph.tsx
└── 闭环/中转原始流水摘要展示
```

## 验证结果

- `python3 -m py_compile utils/path_explainability.py fund_penetration.py related_party_analyzer.py specialized_reports.py api_server.py`
- `pytest -q tests/test_aml_phase1_foundation.py tests/test_specialized_reports.py tests/test_clue_aggregator.py tests/test_api_server_config_flow.py`
  - `37 passed, 2 warnings`
- `pytest -q tests/test_investigation_report_builder_metrics.py tests/test_report_generator.py`
  - `28 passed`
- `cd dashboard && npm run type-check`
  - passed

## 当前影响判断

- 前端输入界面：
  - 不变
- 图谱展示：
  - 可直接看到路径与样本流水之间的映射
- 报告输出：
  - 报告从“结构解释”进一步推进到“样本证据引用”
- 兼容性：
  - 新字段均为增量
  - 旧消费方不会被打坏
