# 2026-03-14 图谱重点对象排序统一收口

## 本轮目标

- 把图谱侧“重点对象”展示切换到与报告相同的聚合排序口径
- 消除 `api_server.py`、`NetworkGraph.tsx`、`specialized_reports.py` 各自消费不同排序结果的问题

## 本次改动

### 1. 共享排序 helper

- 新增：
  - `utils/aggregation_view.py`

提供统一能力：

- 提取 `aggregation` payload
- 标准化 `rankedEntities`
- 生成聚合摘要 `build_aggregation_overview()`
- 标注对象是否在当前图谱采样中可见

### 2. `api_server.py`

- `/api/analysis/graph-data` 新增输出：
  - `report.focus_entities`
  - `report.aggregation_summary`
  - `report.aggregation_metadata`
- 图谱重点对象列表已按原始排查对象范围统一到聚合排序口径
- `stats.highRiskCount` / `stats.mediumRiskCount` 改为基于聚合摘要统计

### 3. `dashboard/src/components/NetworkGraph.tsx`

- 新增 `重点核查对象` 面板
- 展示：
  - 风险评分
  - 风险等级
  - 风险置信度
  - 高优先线索数
  - 综合摘要
  - Top clue
- 点击重点对象可直接聚焦到当前图谱中的对应节点
- 若对象未进入当前采样图，会明确提示“当前采样图未展示该对象”

### 4. `specialized_reports.py`

- `资金穿透分析报告` 新增：
  - `【重点核查对象排序】`
- 与图谱侧共享同一聚合排序结果，避免专项报告继续沿用散落的旧排序来源

### 5. `report_generator.py`

- 老导出链路改为复用共享 helper
- 避免 `report_generator.py` 和图谱/API 再次出现同一逻辑多份实现

## 涉及函数树

```text
utils/aggregation_view.py
├── extract_aggregation_payload
├── normalize_aggregation_ranked_entities
├── build_aggregation_overview
└── annotate_focus_entities_with_graph

api_server.py
└── get_graph_data

specialized_reports.py
└── _generate_penetration_report

report_generator.py
├── _extract_aggregation_payload
├── _normalize_aggregation_ranked_entities
└── _build_aggregation_overview

dashboard/src/components/NetworkGraph.tsx
└── 重点核查对象面板与图谱聚焦
```

## 验证结果

- `python3 -m py_compile api_server.py report_generator.py specialized_reports.py utils/aggregation_view.py`
- `pytest -q tests/test_api_server_config_flow.py tests/test_specialized_reports.py tests/test_report_generator.py`
  - `26 passed, 2 warnings`
- `pytest -q tests/test_aml_phase1_foundation.py`
  - `9 passed`
- `pytest -q tests/test_investigation_report_builder_metrics.py`
  - `24 passed`
- `cd dashboard && npm run type-check`
  - passed

## 当前影响判断

- 前端输入界面：
  - 不变
- API 输入参数：
  - 不变
- 图谱展示：
  - 新增统一排序的重点对象面板
  - 不破坏原有闭环、外围节点、关系簇面板
- 报告输出：
  - `资金穿透分析报告` 新增统一口径的重点对象摘要
- 兼容性：
  - 旧字段保留
  - 无 `aggregation` 时不会导致接口崩溃
