# 报告体系重构实施清单 v1

> 状态: 草案  
> 日期: 2026-03-18  
> 对应设计: `docs/report_system_rearchitecture_v1.md`

---

## 1. 实施目标

将当前报告链路从：

- `analysis_cache -> investigation_report_builder/specialized_reports -> html/txt/xlsx`

重构为：

- `analysis_cache -> report_package -> 主报告/附录/卷宗/前端报告中心`

并确保：

1. 主报告、HTML、附录、前端使用同一语义层。
2. 风险评价体系同步统一。
3. 公司分析升级为独立对象体系。
4. 技术日志、正式报告、附录、底稿彻底分层。

---

## 2. 总体阶段划分

### Phase 0: 基线与样本固化

目标：

- 固定一套基线案件缓存，用于重构期间回归。
- 对当前输出建立“旧版对照样本”。

建议动作：

- 复制当前 `output/analysis_cache/` 为测试基线样本。
- 固化当前主报告、专项报告、HTML 产物作为对照件。
- 增加“报告一致性基线测试”样本目录。

新增文件建议：

- `tests/fixtures/report_cache_case_2026_03_18/`
- `tests/fixtures/report_outputs_legacy_2026_03_18/`

---

### Phase 1: 构建 report_package 语义层

目标：

- 在不影响现有报告输出的前提下，先把统一语义层做出来。

新增模块：

- `report_fact_normalizer.py`
- `report_issue_engine.py`
- `report_dossier_builder.py`
- `report_quality_guard.py`
- `report_view_builder.py`

#### 1.1 report_fact_normalizer.py

职责：

- 统一读取 `profiles / derived_data / suspicions / walletData / metadata / graph_data`
- 清洗字段命名差异
- 统一实体名、家庭名、公司名映射
- 统一溯源字段

关键输出：

- `normalized_entities`
- `normalized_transactions`
- `normalized_relationships`
- `normalized_wallet_alerts`
- `normalized_external_assets`

#### 1.2 report_issue_engine.py

职责：

- 将模块命中聚合成问题卡
- 合并跨模块证据
- 计算 `severity / confidence / priority`
- 输出 `issues[]`

问题生成子引擎建议：

- `income_issue_rules`
- `loan_issue_rules`
- `penetration_issue_rules`
- `relationship_issue_rules`
- `behavioral_issue_rules`
- `timeline_issue_rules`
- `wallet_issue_rules`
- `company_issue_rules`

#### 1.3 report_dossier_builder.py

职责：

- 构建 `family_dossiers`
- 构建 `person_dossiers`
- 构建 `company_dossiers`

#### 1.4 report_quality_guard.py

职责：

- 主报告前置 QA
- 检查口径冲突、误报、目录一致性、强措辞门控

建议硬检查：

- `no_cycle_but_cycle_community`
- `zero_frequency_but_frequent_wording`
- `html_missing_but_index_points_html`
- `high_risk_without_minimum_evidence`
- `benign_scenario_promoted_to_high_risk`

#### 1.5 report_view_builder.py

职责：

- 汇总 `meta / coverage / priority_board / issues / dossiers / appendices / evidence_index / qa_checks`
- 输出 `report_package`

交付物：

- `output/analysis_results/qa/report_package.json`

---

### Phase 2: 风险评价体系统一

目标：

- 统一个人、家庭、公司的风险表达口径。

涉及文件：

- `unified_risk_model.py`
- `clue_aggregator.py`
- `company_risk_analyzer.py`
- `wallet_risk_analyzer.py`
- 新增 `report_issue_engine.py`

关键动作：

1. 保留现有底层风控结果，但不再让其直接决定正式报告排序。
2. 新增 `severity / confidence / priority` 三层评分。
3. 个人、家庭、公司分别计算内部维度，再统一映射到 `priority_score`。
4. 统一风险等级枚举和阈值。

建议统一枚举：

- `critical`
- `high`
- `medium`
- `low`
- `info`

建议统一状态：

- `lead`
- `suspicious`
- `high_confidence`
- `corroborated`

---

### Phase 3: 公司体系重构

目标：

- 将公司对象从“补充章节”升级为完整卷宗。

涉及文件：

- `company_risk_analyzer.py`
- `investigation_report_builder.py`
- `templates/report_v3/company_section.html`
- 新增 `report_company_role_engine.py` 或并入 `report_dossier_builder.py`

具体动作：

1. 在公司分析中增加“角色标签”计算：
   - 汇集节点
   - 分发节点
   - 通道节点
   - 桥接节点
   - 疑似利益输送节点
2. 将公司问题卡独立生成，不再仅做 narrative。
3. 补充公司与：
   - 核心人员
   - 家庭成员
   - 关联公司
   - 调查单位
   的交叉关系输出。
4. 公司卷宗支持“主要上下游”“关键路径”“关键异常交易”。

新增输出：

- `company_dossiers[]`
- `company_issue_refs`

---

### Phase 4: 主报告与附录重组

目标：

- 重构主报告结构，专项报告转为附录体系。

涉及文件：

- `investigation_report_builder.py`
- `specialized_reports.py`
- `wallet_report_builder.py`
- `templates/report_v3/report.html`
- `templates/report_v3/person_section.html`
- `templates/report_v3/company_section.html`
- `templates/report_v3/conclusion.html`

具体动作：

#### 4.1 主报告

- 主报告只读取 `report_package`
- 只展示：
  - 数据范围
  - 问题总览
  - 优先级排序
  - 家庭/个人/公司重点问题
  - 综合研判
  - 下一步建议

#### 4.2 附录

将旧 7 份专项报告重组为：

- 附录A 资产与收入匹配
- 附录B 异常收入与借贷
- 附录C 关系网络与资金穿透
- 附录D 时序与行为模式
- 附录E 电子钱包补证

#### 4.3 技术文件降级

- `分析执行日志.txt` 从正式目录首页移到 `qa/`
- 新增 `报告目录清单` 分层显示：
  - 正式报告
  - 对象卷宗
  - 附录
  - 工作底稿
  - 技术文件

---

### Phase 5: HTML 重构

目标：

- 让 HTML 真正成为问题驱动的正式报告，而不是旧 TXT 的视觉包装。

涉及文件：

- `templates/report_v3/report.html`
- `templates/report_v3/person_section.html`
- `templates/report_v3/company_section.html`
- 可能新增：
  - `issue_card.html`
  - `priority_board.html`
  - `dossier_navigation.html`
  - `appendix_section.html`

HTML 第一阶段改动：

- 保持 Jinja2 架构不变
- 改为读取 `report_package`
- 首页增加：
  - coverage
  - priority_board
  - top issues

HTML 第二阶段改动：

- 问题卡折叠
- 对象卷宗导航
- 证据抽屉
- 公司专题锚点

---

### Phase 6: 前端适配

目标：

- 先保证可用，再逐步升级为“报告中心”。

涉及文件：

- `dashboard/src/services/api.ts`
- `dashboard/src/components/ReportBuilder.tsx`
- `dashboard/src/components/TabContent.tsx`
- `dashboard/src/components/NetworkGraph.tsx`
- 可能新增：
  - `dashboard/src/components/report/IssueBoard.tsx`
  - `dashboard/src/components/report/EntityDossier.tsx`
  - `dashboard/src/components/report/CompanyDossier.tsx`
  - `dashboard/src/components/report/EvidenceDrawer.tsx`

#### 6.1 第一阶段前端改造

- 报告列表支持新的文件分组
- 主报告/问题清单/附录/卷宗分类展示
- HTML 预览和下载逻辑保持不变

#### 6.2 第二阶段前端改造

- 新增“问题总览”
- 新增“公司专题”
- 图谱与问题卡联动
- 风险页消费统一问题卡，而不是继续散吃 `suspicions / derived_data` 零散结构

---

### Phase 7: QA、回归与迁移

目标：

- 确保新旧切换期间产物可控。

新增测试建议：

- `tests/test_report_fact_normalizer.py`
- `tests/test_report_issue_engine.py`
- `tests/test_report_quality_guard.py`
- `tests/test_report_package_builder.py`
- `tests/test_company_dossier_builder.py`
- `tests/test_html_report_semantic_render.py`

回归重点：

1. 同一案件下主报告、HTML、附录、前端排序一致。
2. 不再出现已知口径冲突。
3. 已知误报样本不再进入主报告高风险问题卡。
4. 公司对象在主报告和公司卷宗中的风险表述一致。

迁移策略：

- 第一阶段保留旧输出并行生成，文件名加 `legacy`
- 第二阶段切换目录默认入口到新体系
- 第三阶段删除旧专项报告直出逻辑

---

## 3. 文件级改造清单

### 新增文件

- `report_fact_normalizer.py`
- `report_issue_engine.py`
- `report_dossier_builder.py`
- `report_quality_guard.py`
- `report_view_builder.py`
- `report_renderer_html.py`
- `report_renderer_txt.py`
- `report_manifest_builder.py`

### 重点修改文件

- `investigation_report_builder.py`
  - 收敛为总编排器
  - 输出主报告 / 问题清单 / 卷宗
- `specialized_reports.py`
  - 改为附录渲染器
- `wallet_report_builder.py`
  - 改为钱包补证附录生成器
- `company_risk_analyzer.py`
  - 补公司角色与公司问题卡支撑
- `unified_risk_model.py`
  - 统一为三层评分体系
- `templates/report_v3/*.html`
  - 切到新语义包
- `dashboard/src/components/ReportBuilder.tsx`
  - 报告生成后展示新入口
- `dashboard/src/components/TabContent.tsx`
  - 报告页和风险页适配新结构

---

## 4. 验收标准

### P0 验收

- 能生成 `report_package.json`
- QA 检查可读
- 不影响现有缓存生成

### P1 验收

- 主报告 HTML/TXT 成功从 `report_package` 渲染
- 旧的 3 个已知问题消失：
  - HTML 不存在却要求优先查看 HTML
  - 未发现闭环却出现闭环团伙
  - 低价值生活消费混入主报告高风险交易

### P2 验收

- 公司卷宗上线
- 统一优先级排序可跨个人/家庭/公司比较
- 前端报告页可识别新产物体系

### P3 验收

- 风险页和图谱页接入问题卡与卷宗联动
- 旧专项报告平铺输出下线

---

## 5. 推荐实施顺序

实际落地建议如下：

1. 先做 `report_package` 与 QA，不动模板。
2. 再切主报告与 HTML。
3. 再切公司卷宗与问题卡。
4. 再切附录重组。
5. 最后切前端报告中心与风险页。

原因：

- 先稳住语义层，后面模板、前端、附录才不会反复返工。
- 公司与风险口径同步做，避免后面再次大改排序逻辑。

---

## 6. 当前建议的第一批落地任务

建议下一轮优先做这 6 个任务：

1. 新增 `report_fact_normalizer.py`
2. 新增 `report_issue_engine.py`
3. 新增 `report_quality_guard.py`
4. 在 `investigation_report_builder.py` 中新增 `build_report_package()`
5. 输出 `output/analysis_results/qa/report_package.json`
6. 新增最小回归测试，验证当前 2026-03-18 样本案件可生成语义包

做到这一步后，再开始改 HTML 和前端，成本最低。

