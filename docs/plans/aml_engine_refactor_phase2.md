# AML 分析引擎第二阶段实施与续推方案

## 阶段定位

本文件用于承接原总方案中“关系发现统一”之后的继续落地，避免后续窗口丢失上下文。

当前阶段已经不再只处理“能不能发现关系”，而是进一步处理：

1. 这些关系如何进入统一评分模型
2. 这些关系如何在前端和报告中被解释出来

## 当前已完成

### A. 关系发现统一

已完成内容：

- 强版闭环搜索统一到 `fund_penetration.py`
- `related_party_analyzer.py` 支持：
  - `direct_flows`
  - `third_party_relays`
  - `fund_loops`
  - `discovered_nodes`
  - `relationship_clusters`

### B. 聚合排序 explainability

已完成内容：

- `clue_aggregator.py` 正式消费新结构
- 聚合排序新增：
  - `risk_confidence`
  - `top_evidence_score`
  - `high_priority_clue_count`
  - `aggregation_explainability`

### C. 统一评分模型增强

已完成内容：

- `UnifiedRiskModel` 直接消费：
  - `relay_chains`
  - `relationship_clusters`
  - `discovered_nodes`
  - `direct_relations`
- 置信度计算纳入证据项自身 `confidence`
- `truncated` metadata 会进入置信度降权

### D. 前端风险实体 explainability 初步接线

已完成内容：

- `aggregation.evidencePacks` 已进入前端数据状态
- 风险实体详情弹窗开始展示：
  - 摘要
  - 风险置信度
  - 高优先线索数
  - 最强证据分
  - Top clues

### E. 正式报告与文本首页 explainability 接线

已完成内容：

- `derived_data` 已缓存 `aggregation`
- 正式报告结论会并入聚合高风险对象
- 文本报告首页会输出聚合排序摘要与重点对象
- 风险实体弹窗已升级为“列表 + explainability 面板”

### F. 老导出链路统一到 aggregation explainability

已完成内容：

- `report_generator.py` 已统一消费 `aggregation`
- 已覆盖：
  - TXT 结论页
  - HTML 结论页
  - Excel `聚合风险排序` 工作表
  - Word `generate_word_report()` 结论页
- 旧导出逻辑保留兼容回退：
  - 无 `aggregation` 时仍回退到 `direct_transfers/hidden_assets`

### G. 图谱重点对象排序与报告重点对象排序统一

已完成内容：

- 新增共享 helper：
  - `utils/aggregation_view.py`
- `api_server.py` 的 `/api/analysis/graph-data` 已输出：
  - `report.focus_entities`
  - `report.aggregation_summary`
  - `report.aggregation_metadata`
- `dashboard/src/components/NetworkGraph.tsx`
  - 新增 `重点核查对象` 面板
  - 直接消费统一聚合排序结果
  - 支持点击重点对象后聚焦图谱节点
- `specialized_reports.py`
  - `资金穿透分析报告` 已新增 `【重点核查对象排序】`
  - 与图谱侧共享同一聚合排序口径
- `report_generator.py`
  - 已切换为复用共享 helper，避免消费层排序逻辑再次分叉

### H. 路径级 explainability 首轮统一

已完成内容：

- 新增共享 helper：
  - `utils/path_explainability.py`
- `fund_penetration.py`
  - 资金闭环已输出 `path_explainability`
- `related_party_analyzer.py`
  - 第三方中转已输出 `path_explainability`
  - 关系簇已输出 `path_explainability`
- `clue_aggregator.py`
  - `aggregationExplainability.top_clues` 已保留 `path_explainability`
  - 对旧 relay / cluster 结构增加 explainability 兜底
- `api_server.py`
  - `/api/analysis/graph-data` 已输出 `third_party_relays`
- `dashboard/src/components/NetworkGraph.tsx`
  - 资金闭环 / 第三方中转 / 外围节点 / 关系簇面板优先展示路径摘要与路径解释
- `specialized_reports.py`
  - `资金穿透分析报告` 已优先消费 `path_explainability.summary`
  - 已输出结构化路径解释要点

### I. 边级金额与时间轴 explainability 细化

已完成内容：

- `utils/path_explainability.py`
  - 资金闭环新增：
    - `edge_segments`
    - `bottleneck_edge`
    - `amount_basis_detail`
  - 第三方中转新增：
    - `time_axis`
    - `sequence_summary`
- `fund_penetration.py`
  - 闭环 explainability 已细化到每一跳累计金额
  - 已标注瓶颈边
- `specialized_reports.py`
  - `资金穿透分析报告` 已输出：
    - `边级金额`
    - `时间轴摘要`
    - `时间轴`
- `dashboard/src/components/NetworkGraph.tsx`
  - 资金闭环面板已展示边级金额拆解
  - 第三方中转面板已展示时间轴细节
- `clue_aggregator.py`
  - `top_clues.path_explainability` 已保留时间轴结构

### J. 逐跳原始交易映射 explainability

已完成内容：

- `fund_penetration.py`
  - 构图边已保留样本原始流水引用
  - `edge_segments` 已新增：
    - `transaction_refs`
    - `transaction_count`
- `related_party_analyzer.py`
  - 第三方中转链已保留：
    - `outflow_source_file`
    - `outflow_source_row_index`
    - `inflow_source_file`
    - `inflow_source_row_index`
- `utils/path_explainability.py`
  - `time_axis` 事件已保留原始来源文件与行号
- `specialized_reports.py`
  - `资金穿透分析报告` 已输出：
    - `原始流水`
    - 闭环每一跳对应的样本流水引用
    - 中转时间轴事件对应的样本流水引用
- `dashboard/src/components/NetworkGraph.tsx`
  - 闭环卡片已展示样本原始流水摘要
  - 第三方中转时间轴已展示来源文件与行号

## 本阶段收口状态（2026-03-14 晚）

本阶段原先挂着的 3 个续推项，现已完成：

1. 逐跳原始交易已从“样本摘要”推进到“可折叠全量返回 + 截断提示”
2. 关系簇代表路径已具备统一排序、优先级与可展开链路解释
3. 图谱与右侧详情已实现双向联动

新增收口内容：

- `utils/path_explainability.py`
  - 已形成统一 `evidence_template`
  - 已新增代表路径排序器
- `fund_penetration.py`
  - 闭环边级原始流水已支持更大规模逐笔返回与截断元数据
- `related_party_analyzer.py`
  - 关系簇代表路径已输出：
    - `priority_score`
    - `priority_reason`
    - `evidence_template`
- `clue_aggregator.py`
  - 聚合 `top_clues` 已开始保留统一证据模板
- `specialized_reports.py`
  - 路径解释、代表路径说明已优先复用统一证据模板
- `dashboard/src/components/NetworkGraph.tsx`
  - 已支持路径联动、高亮、逐跳折叠展开

## 下一步建议

当前不再建议继续局部加功能，优先进入：

1. 阶段性系统全量测试
2. 回归核查报告 / 图谱 / 聚合排序 / 老导出链路的一致性
3. 评估第四阶段风险评分增强是否需要继续推进

## 阶段性全量测试建议范围

```text
Stage Checkpoint
├── 资金清洗与金额口径回归
├── 借贷 / 时序 / 疑点检测回归
├── 资金穿透 / 关联方 / 聚合排序回归
├── 专项报告 / 正式报告 / 老导出链路回归
└── 前端图谱 / explainability / 联动交互回归
```
