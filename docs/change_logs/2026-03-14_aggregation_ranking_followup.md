# 2026-03-14 聚合排序增强收尾

## 本次目标

把 AML 第一阶段已经产出的 explainability 字段，真正接入线索聚合层、API 输出、聚合报告和前端风险概览消费链路。

## 本次改动

### 1. `clue_aggregator.py`

- `aggregate_penetration_results()`
  - 正式消费 `penetration.fund_cycles` 的 `risk_score / confidence / evidence`
  - 保留 `analysis_metadata.fund_cycles`
  - 兼容旧闭环 list 结构与新 dict 结构
- `aggregate_related_party_results()`
  - 从旧 `direct_transactions` 迁移为优先消费：
    - `direct_flows`
    - `third_party_relays`
    - `fund_loops`
    - `discovered_nodes`
    - `relationship_clusters`
  - `fund_loops` 统一并入 `fund_cycles` 证据桶，避免闭环证据在聚合层丢失
- `calculate_entity_risk_scores()`
  - 保留 `UnifiedRiskModel` 作为基础总分模型
  - 新增聚合排序辅助指标：
    - `risk_confidence`
    - `top_evidence_score`
    - `high_priority_clue_count`
    - `aggregation_explainability`
  - 排序不再只看总分，而是“总分 + 置信度 + 最强证据 + 高优先线索数”
- `to_dict()`
  - 正式输出：
    - `rankedEntities`
    - `summary`
    - `evidencePacks`
    - `analysisMetadata`
  - 同时保留旧 snake_case 字段，避免兼容性回退
- 聚合报告增强
  - 新增展示：
    - 第三方中转链路
    - 外围节点发现
    - 关系簇识别
    - 风险置信度 / 最强证据分 / 高优先线索数

### 2. `api_server.py`

- `serialize_analysis_results()`
  - `aggregation` 分支改为显式调用 `serialize_for_json()`
  - 确保 `ClueAggregator.to_dict()` 真正进入 API 输出链路

### 3. 前端消费

- `dashboard/src/types/index.ts`
  - 扩展 `AggregationResult` / `RankedEntity` 类型，纳入：
    - `riskConfidence`
    - `topEvidenceScore`
    - `highPriorityClueCount`
    - `aggregationExplainability`
- `dashboard/src/components/TabContent.tsx`
  - 风险实体弹窗描述增加：
    - 风险置信度
    - 高优先线索数

## 算法口径变化

### 排序口径

旧口径：

1. `risk_score`

新口径：

1. `risk_score`
2. `risk_confidence`
3. `top_evidence_score`
4. `high_priority_clue_count`
5. `evidence_count`

### Explainability 聚合

- `risk_confidence`
  - 由统一模型置信度和各证据项置信度混合计算
- `top_evidence_score`
  - 当前实体所有带评分线索中的最高值
- `high_priority_clue_count`
  - 当前实体中 `risk_score >= 50` 的线索数
- `aggregation_explainability.top_clues`
  - 输出 Top 3 关键线索摘要，供报告和前端展示

## 本次覆盖的函数树

```text
clue_aggregator.py
├── aggregate_penetration_results
├── aggregate_related_party_results
├── calculate_entity_risk_scores
├── get_ranked_entities
├── get_summary
├── to_dict
├── generate_aggregation_report
├── _write_third_party_relays_section
├── _write_discovered_nodes_section
└── _write_relationship_clusters_section

api_server.py
└── serialize_analysis_results

dashboard/src/components/TabContent.tsx
└── 风险实体明细展示文案增强

dashboard/src/types/index.ts
└── Aggregation 类型扩展
```

## 验证结果

- `pytest -q tests/test_clue_aggregator.py tests/test_api_server_config_flow.py tests/test_specialized_reports.py`
  - `24 passed`
- `cd dashboard && npm run type-check`
  - passed

## 已知未处理项

- 仍有既有 `PydanticDeprecatedSince212` 告警，本次未动
- `UnifiedRiskModel` 本体权重体系尚未改造，本次仅增强其上层聚合排序解释力
