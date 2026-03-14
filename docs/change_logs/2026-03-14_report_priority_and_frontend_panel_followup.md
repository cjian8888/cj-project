# 2026-03-14 正式报告优先级与前端解释面板跟进

## 本次目标

把上一轮已经产出的 `aggregation.evidencePacks` 继续推进到：

- 正式报告结论与文本首页
- 前端风险实体详情弹窗

## 本次改动

### 1. `api_server.py`

- `derived_data` 缓存新增：
  - `aggregation`

这样 `InvestigationReportBuilder` 在离线生成报告时也能直接消费聚合结果，而不是只在运行时内存里可见。

### 2. `investigation_report_builder.py`

新增聚合结果辅助方法：

- `_get_aggregation_data()`
- `_get_aggregation_ranked_entities()`
- `_get_aggregation_evidence_packs()`
- `_get_entity_aggregation_pack()`
- `_build_aggregation_highlights()`

改动点：

- `_extract_high_risk_warnings_unified()`
  - 会把聚合高风险评分、置信度、Top clue 作为预警来源
- `_build_v4_conclusion()`
  - 正式把聚合排序高风险对象并入结论 issues
  - 输出：
    - `aggregation_highlights`
    - `aggregation_summary`
- `_generate_enhanced_summary_text_v4()`
  - 会在综合研判中输出聚合排序重点对象
- `generate_complete_txt_report()`
  - 文本首页新增：
    - `【聚合排序】`
    - `聚合排序识别重点对象`

### 3. 前端 `dashboard/src/components/TabContent.tsx`

风险实体类弹窗从“纯表格”升级为：

- 左侧：实体列表
- 右侧：Explainability 面板

右侧面板内容：

- 风险评分
- 风险置信度
- 最强证据分
- 高优先线索数
- 综合摘要
- Top clues
- 证据分布
- 审计提示

### 4. 前端状态 `dashboard/src/contexts/AppContext.tsx`

保留：

- `aggregation.evidencePacks`
- `aggregation.analysisMetadata`

## 涉及函数树

```text
api_server.py
└── derived_data 构建处新增 aggregation

investigation_report_builder.py
├── _get_aggregation_data
├── _get_aggregation_ranked_entities
├── _get_aggregation_evidence_packs
├── _get_entity_aggregation_pack
├── _build_aggregation_highlights
├── _extract_high_risk_warnings_unified
├── _build_v4_conclusion
├── _generate_enhanced_summary_text_v4
└── generate_complete_txt_report

dashboard/src/contexts/AppContext.tsx
└── aggregation 数据通道补齐

dashboard/src/components/TabContent.tsx
└── 风险实体 Explainability 面板
```

## 验证结果

- `pytest -q tests/test_investigation_report_builder_metrics.py tests/test_api_server_config_flow.py tests/test_clue_aggregator.py tests/test_unified_risk_model.py`
  - `36 passed`
- `pytest -q tests/test_aml_phase1_foundation.py`
  - `9 passed`
- `cd dashboard && npm run type-check`
  - passed

## 当前阶段剩余建议

1. 把 `report_generator.py` 的老式风险摘要也切到聚合 explainability 优先
2. 把图谱重点对象排序与报告重点对象排序统一到同一聚合口径
