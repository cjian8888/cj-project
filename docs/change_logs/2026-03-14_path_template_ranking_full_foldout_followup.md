# 2026-03-14 路径证据模板 / 代表路径排序 / 全量逐笔折叠收口

## 本轮目标

- 完成剩余三项：
  - 路径证据模板全系统统一一层
  - 代表路径排序继续精炼
  - 逐跳原始交易从样本升级为可折叠全量返回

## 本次改动

### 1. `utils/path_explainability.py`

- 新增统一能力：
  - `build_path_evidence_template`
  - `get_or_build_path_evidence_template`
  - `ensure_path_evidence_template`
  - `rank_representative_paths`
- 所有主路径 explainability 均新增：
  - `evidence_template`
- `relationship_cluster` 新增：
  - `representative_path_total`

### 2. `fund_penetration.py`

- 交易引用从“仅保留少量样本”升级为：
  - `transaction_refs_total`
  - `transaction_refs_returned`
  - `transaction_refs_truncated`
  - `transaction_refs_limit`
- 聚合边保留更大规模原始流水引用，支持逐跳折叠展开

### 3. `related_party_analyzer.py`

- 关系簇代表路径已切换到统一排序器
- 代表路径新增：
  - `priority_score`
  - `priority_reason`
  - `evidence_template`

### 4. `clue_aggregator.py`

- 聚合 `top_clues` 已保留：
  - `evidence_template`
- 线索描述优先使用统一路径证据标题

### 5. `specialized_reports.py`

- 路径摘要 / 路径解释 / 代表路径说明开始优先复用统一证据模板
- 关系簇章节新增：
  - `优先级`
  - `证据`

### 6. `dashboard/src/components/NetworkGraph.tsx`

- 前端类型已兼容：
  - `transaction_refs_returned`
  - `priority_score`
  - `priority_reason`
  - `evidence_template`
- 逐跳折叠明细现在显示“当前返回条数 / 实际总数”
- 代表路径面板新增排序依据与证据提示

## 验证结果

- `pytest -q tests/test_aml_phase1_foundation.py tests/test_specialized_reports.py tests/test_clue_aggregator.py tests/test_api_server_config_flow.py tests/test_investigation_report_builder_metrics.py tests/test_report_generator.py`
  - `67 passed, 2 warnings`
- `cd dashboard && npm run type-check`
  - passed

## 当前影响判断

- 前端输入界面：
  - 不变
- 图谱展示：
  - 逐跳原始流水和代表路径排序依据都可直接展示
- 报告输出：
  - 路径证据模板开始统一收敛
- 兼容性：
  - 新字段为增量字段
  - 旧字段未删除
- 阶段建议：
  - 到此应暂停新增功能，进入阶段性系统全量测试
