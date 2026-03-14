# 2026-03-14 统一评分模型与前端解释展示增强

## 本次目标

在上一轮“聚合排序增强”基础上，继续把 explainability 深入到：

- `UnifiedRiskModel` 本体
- `clue_aggregator.py` 的风险评分入参
- 前端风险实体详情展示

约束保持不变：

- 前端界面输入不改
- 报告与现有 API 出口保持兼容
- 新字段优先作为附加 metadata 输出

## 本次代码改动

### 1. `unified_risk_model.py`

新增直接消费以下证据类型：

- `relay_chains`
- `relationship_clusters`
- `discovered_nodes`
- `direct_relations`
- `transit_channels`

新增评分分量：

- `relay_score`
- `cluster_score`
- `external_node_score`
- `direct_relation_score`

新增细节输出：

- `details.evidence_summary`

置信度增强：

- 不再只看 `total_records`
- 会综合证据项自身的 `confidence`
- 遇到 `truncated` metadata 时降权
- 多类强信号同时出现时提升置信度

### 2. `clue_aggregator.py`

在 `calculate_entity_risk_scores()` 中，传给统一评分模型的证据从旧结构扩展为：

- `money_loops`
- `transit_channel`
- `transit_channels`
- `relay_chains`
- `relationship_clusters`
- `discovered_nodes`
- `direct_relations`
- `related_entities`
- `money_loop_meta`
- `relay_meta`
- `relationship_meta`

这意味着：

- 第三方中转
- 关系簇
- 外围节点
- 直接往来

现在不只是影响排序辅助指标，而是已经进入实体总分模型本身。

### 3. 前端展示

#### `dashboard/src/contexts/AppContext.tsx`

保留并传递：

- `aggregation.evidencePacks`
- `aggregation.analysisMetadata`

#### `dashboard/src/components/TabContent.tsx`

风险实体详情弹窗现在会基于 `evidencePacks` 展示：

- 实体摘要
- 风险置信度
- 高优先线索数
- 最强证据分
- 证据分布
- Top clues

## 这次解决的核心问题

### 旧问题

- 聚合排序已经能看见 relay/cluster/node，但统一评分模型本身还看不见
- 风险实体弹窗只有“分数”，没有“为什么是这个分数”

### 新结果

- 总分模型和排序模型的证据口径更一致
- 前端风险实体明细开始具备“解释性”

## 涉及函数树

```text
unified_risk_model.py
├── calculate_score
├── _score_money_loop
├── _score_transit_channel
├── _score_relay_chains
├── _score_relationship_clusters
├── _score_external_nodes
├── _score_direct_relations
├── _score_multi_entity
└── _calculate_confidence

clue_aggregator.py
└── calculate_entity_risk_scores

dashboard/src/contexts/AppContext.tsx
└── aggregation 数据通道增强

dashboard/src/components/TabContent.tsx
└── 风险实体详情 explainability 展示增强
```

## 验证结果

- `pytest -q tests/test_unified_risk_model.py tests/test_clue_aggregator.py tests/test_api_server_config_flow.py tests/test_specialized_reports.py`
  - `27 passed`
- `pytest -q tests/test_aml_phase1_foundation.py`
  - `9 passed`
- `cd dashboard && npm run type-check`
  - passed

## 未完成项

下一步建议继续做：

1. 风险实体详情从“表格描述”升级为专门的 explainability 面板
2. 正式报告首页和摘要章节直接消费 `aggregation.evidencePacks`
3. 统一 `report_generator.py / investigation_report_builder.py` 的实体排序优先级
