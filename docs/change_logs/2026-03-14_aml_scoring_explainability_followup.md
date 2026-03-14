# 2026-03-14 AML 统一评分与可解释性增强记录

## 本轮目标

- 为闭环、中转、外围节点、关系簇补充统一解释字段
- 统一输出：
  - `risk_score`
  - `confidence`
  - `evidence`
  - `truncated`
- 保持前端输入不变，只增强后端输出、图谱展示和报告解释

## 已完成

### 统一评分底座

- `risk_scoring.py`
  - 新增 `normalize_risk_score()`
  - 新增 `score_to_risk_level()`
  - 新增 `normalize_confidence()`
  - 作为图分析结果的统一评分阈值映射

### 资金闭环与过账通道

- `fund_penetration.py`
  - `MoneyGraph.find_cycles()`
    - 新增闭环搜索元数据：
      - `timed_out`
      - `search_node_truncated`
      - `cycle_limit_hit`
      - `truncated`
      - `truncated_reasons`
  - 新增 `_estimate_cycle_amount()`
    - 按闭环最小边额估算可回流金额
  - 新增 `build_cycle_record()`
    - 为闭环输出：
      - `path`
      - `total_amount`
      - `risk_score`
      - `risk_level`
      - `confidence`
      - `evidence`
  - 新增 `_enrich_pass_through_channel()`
    - 为过账通道输出统一评分与证据
  - `_analyze_graph_deep_analysis()`
    - `fund_cycles` 从原始节点列表升级为结构化对象
    - 新增 `analysis_metadata.fund_cycles`
    - 新增 `analysis_metadata.pass_through_channels`

### 关联方分析

- `related_party_analyzer.py`
  - `analyze_related_party_flows()`
    - 新增 `analysis_metadata`
  - `_detect_third_party_relay()`
    - 中转链新增：
      - `risk_score`
      - `confidence`
      - `evidence`
  - `_detect_fund_loops()`
    - 复用 `fund_penetration.build_cycle_record()`
    - 支持返回闭环搜索 metadata
  - `_extract_discovered_nodes()`
    - 外围节点新增：
      - `risk_score`
      - `confidence`
      - `evidence`
  - `_build_relationship_clusters()`
    - 关系簇新增：
      - `risk_score`
      - `confidence`
      - `evidence`

### 消费层接入

- `api_server.py`
  - `/api/analysis/graph-data`
    - `report` 新增 `fund_cycle_meta`
- `specialized_reports.py`
  - 资金穿透报告新增显示：
    - 风险评分
    - 置信度
    - 证据摘要
    - 闭环搜索截断提示
- `report_generator.py`
  - Excel 工作表 `穿透-资金闭环` 兼容结构化闭环输出
  - 新增 `风险评分` / `置信度` 列
- `dashboard/src/components/NetworkGraph.tsx`
  - 闭环/外围节点/关系簇面板新增：
    - 评分
    - 置信度
    - 证据摘要
    - 闭环截断提示
- `dashboard/src/types/index.ts`
  - 扩展前端类型声明，纳入 explainability 字段
- `dashboard/src/contexts/AppContext.tsx`
  - 默认值与合并逻辑保留 explainability 字段

## 本轮验证

- `pytest -q tests/test_aml_phase1_foundation.py`
  - 9 passed
- `pytest -q tests/test_specialized_reports.py tests/test_api_server_config_flow.py`
  - 20 passed
- `cd dashboard && npm run type-check`
  - passed

## 当前影响判断

- 前端输入：
  - 不变
- 后端分析结果：
  - 从“只有风险等级”升级为“分数 + 置信度 + 证据 + 截断语义”
- 图谱展示：
  - 可区分“高风险但低置信度”和“高风险且高置信度”
- 报告输出：
  - 解释性增强
  - 不删除旧章节

## 下一步建议

- 若继续推进，建议优先做：
  - 将 `risk_score / confidence` 纳入总线索聚合与排序
  - 为大样本路径搜索统一输出 `timeout / truncated / sampled` 的更细粒度语义
