# 2026-03-14 边级金额与时间轴 explainability 细化

## 本轮目标

- 把路径 explainability 从“摘要级”继续细化到：
  - 闭环每一跳的金额口径
  - 第三方中转的时间轴

## 本次改动

### 1. `utils/path_explainability.py`

- 资金闭环新增：
  - `edge_segments`
  - `bottleneck_edge`
  - `amount_basis_detail`
- 第三方中转新增：
  - `time_axis`
  - `sequence_summary`

### 2. `fund_penetration.py`

- `build_cycle_record()` 已输出闭环边级金额 explainability
- 金额口径说明：
  - 以每一跳累计金额构造 `edge_segments`
  - 以最小边额识别 `bottleneck_edge`
  - 用于解释“为什么闭环金额按这个数算”

### 3. `specialized_reports.py`

- `资金穿透分析报告` 新增输出：
  - `边级金额`
  - `时间轴摘要`
  - `时间轴`

### 4. `dashboard/src/components/NetworkGraph.tsx`

- 资金闭环卡片新增：
  - 每一跳金额拆解
  - 瓶颈边说明
- 第三方中转卡片新增：
  - 时间轴摘要
  - 两步时间轴明细

### 5. `clue_aggregator.py`

- 聚合 explainability 的 `top_clues.path_explainability`
  - 已保留 `time_axis`
  - 便于后续继续在风险实体详情或报告中下钻

## 涉及函数树

```text
utils/path_explainability.py
├── build_cycle_path_explainability
└── build_relay_path_explainability

fund_penetration.py
├── _build_cycle_edge_segments
└── build_cycle_record

specialized_reports.py
└── _generate_penetration_report

dashboard/src/components/NetworkGraph.tsx
└── 闭环/中转 explainability 细节展示

clue_aggregator.py
└── aggregation top_clues explainability 保留时间轴
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
  - 闭环和中转的解释维度明显增强
- 报告输出：
  - 审计员能看到为什么是这个金额口径、两步中转的先后顺序
- 兼容性：
  - 旧字段保留
  - 新字段均为增量结构
