# 2026-03-14 AML 第一阶段启动记录

## 本轮目标

- 将 AML 分阶段重构方案固化到仓库
- 启动第一阶段的底层能力改造
- 优先处理严格排序、现金碰撞、固定延迟转账、无还款借贷重复计提问题

## 已完成

### 方案固化

- 新增 `docs/plans/aml_engine_refactor_master_plan.md`
- 新增 `docs/plans/aml_engine_refactor_phase1.md`

### 公共能力

- `utils.py`
  - 新增 `detect_account_identifier_column()`
  - 新增 `build_transaction_order_columns()`
  - 新增 `sort_transactions_strict()`
- `utils/__init__.py`
  - 导出上述公共能力

### 时序模块

- `time_series_analyzer.py`
  - `_normalize_time_series_df()` 改为统一严格排序
  - `detect_periodic_income()` 组内排序改为严格排序
  - `detect_delayed_transfers()` 从全量双循环改为时间窗口搜索 + 最优候选 + 一对一消费
  - 输出兼容别名：
    - `income_counterparty`
    - `expense_counterparty`
    - `count`

### 疑点检测模块

- `suspicion_detector.py`
  - `detect_cash_time_collision()` 从笛卡尔积改为滑动窗口最优匹配
  - `detect_cross_entity_cash_collision()` 接入严格排序

### 借贷模块

- `loan_analyzer.py`
  - `_detect_loan_pairs()` 接入严格排序
  - 新增 `_build_loan_repayment_states()`
  - `_detect_loan_pairs()` 改为基于序列核销输出闭合借贷对，支持分期还款
  - 新增 `_allocate_future_repayments()`
  - `_detect_no_repayment_loans()` 改为基于未来支出核销结果判定，避免同一笔还款重复复用

### 测试

- 新增 `tests/test_aml_phase1_foundation.py`
- 已验证：
  - 严格排序
  - 单实体现金碰撞最优匹配
  - 固定延迟转账乱序输入
  - 无还款借贷不重复复用未来支出
  - 分期还款可形成闭合借贷配对
  - 单一候选整笔还款仍保留原有利率语义

### 闭环与报告口径

- `related_party_analyzer.py`
  - `_detect_fund_loops()` 不再使用弱版 DFS
  - 改为复用 `fund_penetration` 的强版资金图闭环搜索
  - 输出兼容字段：
    - `participants`
    - `nodes`
    - `path`
    - `core_node_count`
    - `external_node_count`
- `specialized_reports.py`
  - 资金闭环报告改为优先 `penetration.fund_cycles`
  - `relatedParty.fund_loops` 仅作为回退

### 关系发现结构化输出

- `related_party_analyzer.py`
  - `analyze_related_party_flows()` 新增结果字段：
    - `discovered_nodes`
    - `relationship_clusters`
  - `_collect_person_flows()` 接入严格排序与日期标准化
  - 新增 `_extract_discovered_nodes()`
  - 新增 `_build_relationship_clusters()`
  - `_generate_summary()` 新增：
    - `外围节点数`
    - `关系簇数`

### 接口出口兼容接入

- `api_server.py`
  - `serialize_analysis_results()`
    - `relatedParty` 新增统一 `details` 聚合输出
    - 分类 `_type` 新增映射：
      - `direct_flows -> direct_flow`
      - `third_party_relays -> third_party_relay`
      - `fund_loops -> fund_loop`
      - `discovered_nodes -> discovered_node`
      - `relationship_clusters -> relationship_cluster`
  - `/api/analysis/graph-data`
    - `stats` 新增：
      - `discoveredNodeCount`
      - `relationshipClusterCount`
    - `report` 新增：
      - `discovered_nodes`
      - `relationship_clusters`
      - `fund_cycles`
    - `fund_cycles` 口径优先级：
      - 优先 `penetration.fund_cycles`
      - 回退 `relatedParty.fund_loops`

## 本轮验证

- `pytest tests/test_aml_phase1_foundation.py -q`
  - 8 passed
- `pytest tests/test_api_server_config_flow.py -q`
  - 5 passed
- `pytest tests/test_api_server_dashboard_delivery.py -q`
  - 5 passed
- `pytest tests/test_utils.py -q`
  - 83 passed
- `pytest tests/test_specialized_reports.py -q`
  - 14 passed
- 关系发现结构化输出端到端验证通过
- `api_server` 出口透传与图谱接口回归验证通过

## 第一阶段当前完成边界

- 已完成：
  - 严格排序公共底座
  - 现金碰撞最优匹配
  - 延迟转账窗口匹配
  - 借贷序列核销与未来支出去重
  - 强版闭环搜索接入 `related_party_analyzer.py`
  - 报告层闭环口径优先级调整
  - `api_server` 对 `discovered_nodes / relationship_clusters / fund_cycles` 的出口透传
- 尚未进入：
  - 前端展示层对外围节点与关系簇的可视化增强
  - 报告正文对关系簇和外围节点来源的系统性展开
  - 闭环/过账/关系发现的统一评分与置信度体系
  - 大样本场景的显式 `truncated / timeout / confidence` 语义

## 进入下一轮前的硬约束

- 前端界面输入不改
- 旧报告字段不能直接删除
- 新增语义优先通过兼容字段或 metadata 输出
