# 2026-03-14 路径级 explainability 首轮落地

## 本轮目标

- 把资金闭环、第三方中转、关系簇从“只有 evidence 文本”升级为可复用的结构化路径 explainability
- 让聚合器、专项报告、图谱接口、前端展示消费同一套路径解释字段

## 本次改动

### 1. 新增共享 helper

- 新增：
  - `utils/path_explainability.py`

提供统一结构：

- `build_cycle_path_explainability()`
- `build_relay_path_explainability()`
- `build_cluster_path_explainability()`

统一输出：

- `summary`
- `inspection_points`
- 路径类型 / 节点列表 / 金额口径 / 时差 / 代表性链路等结构化字段

### 2. `fund_penetration.py`

- `build_cycle_record()` 新增：
  - `path_explainability`

### 3. `related_party_analyzer.py`

- `_enrich_relay_record()` 新增：
  - `path_explainability`
- `_build_relationship_clusters()` 新增：
  - `path_explainability`
  - `representative_paths`

### 4. `clue_aggregator.py`

- 资金闭环标准化时会兜底补 `path_explainability`
- 聚合器消费 relay / cluster 时会补 explainability 兜底
- `aggregationExplainability.top_clues` 已保留：
  - `path_explainability`

### 5. `api_server.py`

- `/api/analysis/graph-data` 新增输出：
  - `report.third_party_relays`

### 6. `specialized_reports.py`

- `资金穿透分析报告` 对以下模块优先输出：
  - `路径摘要`
  - `路径解释`
- 已覆盖：
  - 资金闭环
  - 第三方中转
  - 关系簇

### 7. `dashboard/src/components/NetworkGraph.tsx`

- 资金闭环面板优先展示：
  - `path_explainability.summary`
  - `inspection_points`
- 新增 `第三方中转` 面板
- 外围节点 / 关系簇面板也优先消费结构化路径解释

## 涉及函数树

```text
utils/path_explainability.py
├── build_cycle_path_explainability
├── build_relay_path_explainability
└── build_cluster_path_explainability

fund_penetration.py
└── build_cycle_record

related_party_analyzer.py
├── _enrich_relay_record
└── _build_relationship_clusters

clue_aggregator.py
├── _normalize_fund_cycle_record
├── aggregate_related_party_results
└── _build_explainability_metrics

api_server.py
└── get_graph_data

specialized_reports.py
└── _generate_penetration_report

dashboard/src/components/NetworkGraph.tsx
└── 路径 explainability 展示与第三方中转面板
```

## 验证结果

- `python3 -m py_compile fund_penetration.py related_party_analyzer.py clue_aggregator.py specialized_reports.py api_server.py utils/path_explainability.py`
- `pytest -q tests/test_clue_aggregator.py tests/test_specialized_reports.py tests/test_api_server_config_flow.py`
  - `28 passed, 2 warnings`
- `pytest -q tests/test_aml_phase1_foundation.py tests/test_investigation_report_builder_metrics.py`
  - `33 passed`
- `cd dashboard && npm run type-check`
  - passed

## 当前影响判断

- 前端输入界面：
  - 不变
- API 输入参数：
  - 不变
- 图谱展示：
  - 新增第三方中转面板
  - 闭环 / 关系簇 / 外围节点可看到结构化路径解释
- 报告输出：
  - `资金穿透分析报告` 的可解释性明显增强
- 兼容性：
  - 旧 `evidence` 文本保留
  - 新结构为增量字段，不会打坏旧消费方
