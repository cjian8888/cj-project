# 2026-03-14 关系簇代表路径与图谱联动

## 本轮目标

- 把关系簇从“统计摘要卡片”升级为“可展开的代表路径视图”
- 让代表路径可以直接联动图谱高亮，便于从簇级风险下钻到具体链路

## 本次改动

### 1. `utils/path_explainability.py`

- 新增 `build_direct_flow_path_explainability`
  - 统一直接往来的结构化解释
  - 输出路径、金额、方向、原始流水引用
- `build_cluster_path_explainability` 新增：
  - `representative_path_count`
  - 更明确的代表路径 inspection point

### 2. `related_party_analyzer.py`

- `_build_relationship_clusters` 的 `representative_paths` 不再只保留：
  - `path_type`
  - `path`
  - `risk_score`
- 现在补充为结构化路径对象：
  - `nodes`
  - `amount`
  - `confidence`
  - `summary`
  - `inspection_points`
  - `path_explainability`

### 3. `specialized_reports.py`

- 关系簇章节新增“代表路径”输出
- 报告可直接看到：
  - 路径类型
  - 代表路径文本
  - 摘要
  - 关键解释点

### 4. `dashboard/src/components/NetworkGraph.tsx`

- 新增图谱聚焦 helper：
  - 支持多节点关系簇高亮
  - 支持单条代表路径节点高亮
- 关系簇卡片新增：
  - `定位关系簇`
  - `代表路径`折叠面板
  - `定位路径`
  - `展开细节`
- 代表路径细节支持：
  - 闭环边级明细与样本流水
  - 中转时间轴明细
  - 直接往来原始流水样本

## 涉及函数树

```text
utils/path_explainability.py
├── build_direct_flow_path_explainability
└── build_cluster_path_explainability

related_party_analyzer.py
└── _build_relationship_clusters
    └── _collect_representative_paths

specialized_reports.py
└── _append_representative_paths

dashboard/src/components/NetworkGraph.tsx
├── getRepresentativePathPayload
├── getRepresentativePathNodes
├── focusGraphNodes
└── 关系簇代表路径渲染与图谱联动
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
  - 关系簇可以从摘要下钻到代表路径，并直接定位到图谱
- 报告输出：
  - 关系簇不再只有统计描述，开始具备链路级解释
- 兼容性：
  - 新字段均为增量字段
  - 旧消费方不受影响
