# Codex Handoff - 2026-03-18

状态: 当日阶段性交接  
主线: `report_package` 语义层重构  
仓库: `D:\CJ\project`  
分支: `main`

## 1. 本次交接目的

本文件用于在异地机器重新拉取仓库后，让新的 Codex 会话无需依赖今天的聊天上下文，也能继续沿着当前主线推进，不偏离阶段目标。

当前要求不是前端大改，也不是另起炉灶重写报告系统，而是继续沿着已经确认的重构路径推进：

1. 先稳住统一语义层。
2. 再扩正式报告与附录消费。
3. 公司体系和风险评价口径已经纳入这条主线，但本阶段仍以语义层和报告层重构为先。

## 2. 今日已完成内容

### 2.1 语义层骨架已落地

已新增并接入以下模块：

- `report_fact_normalizer.py`
- `report_issue_engine.py`
- `report_dossier_builder.py`
- `report_quality_guard.py`
- `report_view_builder.py`

当前 `investigation_report_builder.py` 已通过 `build_report_package()` 生成统一语义包，并将其落地到：

- `output/analysis_results/qa/report_package.json`
- `output/analysis_results/qa/report_consistency_check.json`
- `output/analysis_results/qa/report_consistency_check.txt`

### 2.2 风险与对象卷宗已接入报告主链路

统一语义包当前已包含：

- `meta`
- `coverage`
- `risk_schema`
- `priority_board`
- `issues`
- `family_dossiers`
- `person_dossiers`
- `company_dossiers`
- `appendix_views`
- `evidence_index`
- `qa_checks`

公司卷宗已具备以下语义增强：

- `role_tags`
- `risk_overview`
- `related_persons`
- `related_companies`
- `key_issue_cards`
- `summary`

HTML/TXT 在公司章节已优先消费 semantic dossier，旧结构仅作为回退。

### 2.3 附录 A-E 语义视图已补齐

`report_view_builder.py` 当前已生成以下附录语义视图：

- `appendix_a_assets_income`
- `appendix_b_income_loan`
- `appendix_c_network_penetration`
- `appendix_d_timeline_behavior`
- `appendix_e_wallet_supplement`

并额外生成：

- `company_issue_overview`
- `suspicion_summary`
- `aggregation_summary`
- `appendix_index`

这意味着“附录体系”现在已经有统一的语义入口，但还没有扩展成完整的正式附录章节正文。

### 2.4 TXT / HTML 已加入附录摘要入口

当前主报告已新增轻量附录摘要入口：

- TXT 中新增 `【统一语义层附录摘要】`
- HTML 首页新增“统一语义层附录摘要”卡片

注意：这一步是“主报告轻量挂接附录入口”，不是全面重做前端或 HTML 导航系统。

## 3. 今日已记录的审计式复核材料

今天已经形成并纳入仓库的报告复核记录：

- `docs/report_txt_audit_review_2026-03-18.md`

该文档记录了对现有 TXT 报告的逐份审计式拷问，明确指出了：

- 口径冲突
- 误报压降不足
- 技术实现细节泄露
- 主报告 / 专项报告 / 技术日志分层混乱
- 公司分析体系弱、附录结构散

这份复核记录是本轮重构方向的重要依据，不应被忽略。

## 4. 今日验证证据

本次交接前，已实际执行并通过以下验证：

```powershell
python -m py_compile report_view_builder.py report_quality_guard.py investigation_report_builder.py tests\test_report_package_builder.py tests\test_report_package_api_flow.py
pytest -q tests\test_report_package_builder.py tests\test_report_package_api_flow.py
pytest -q tests\test_investigation_report_builder_metrics.py -k "render_html_report_v3_formats_dates_and_property_area_cleanly"
```

结果：

- `tests\test_report_package_builder.py tests\test_report_package_api_flow.py` 共 `10 passed`
- `tests\test_investigation_report_builder_metrics.py -k "render_html_report_v3_formats_dates_and_property_area_cleanly"` 为 `1 passed`

已确认：

- `report_package` 可成功生成
- `appendix_views` 已包含附录 A-E 及 `appendix_index`
- TXT 含 `【统一语义层附录摘要】`
- HTML 含“统一语义层附录摘要”
- 现有公司语义渲染未回退损坏

## 5. 当前阶段边界

当前阶段明确只做到这里：

1. 搭好统一语义层。
2. 让主报告 TXT / HTML 能读取语义层。
3. 让公司体系和附录摘要进入主报告。

当前阶段明确还没有做的事情：

1. 没有把附录 A-E 扩成完整正式附录章节正文。
2. 没有做大规模前端重构。
3. 没有把风险情报页、图谱页、报告中心全部切到新语义包。
4. 没有做公司专题页重构。

如果新的 Codex 会话直接跳去做前端大改，属于偏离主线。

## 6. 下一阶段推荐动作

下一阶段应继续沿主线推进，优先做下面几项：

### P1. 将附录 A-E 从“摘要视图”扩展为“正式附录章节”

建议顺序：

1. 优先扩 `附录C 关系网络与资金穿透`
2. 再扩 `附录A 资产与收入匹配`
3. 再扩 `附录B 异常收入与借贷`
4. 最后补 `附录D` 和 `附录E`

要求：

- 继续 semantic-first
- 不从原始 Excel 重算
- 不把内部缓存路径直接暴露给正式报告正文

### P2. 将附录渲染与主报告消费进一步解耦

建议新增：

- 更正式的 appendix renderer 或在现有 builder 中继续扩章节生成逻辑

但注意：

- 不要推翻现有 `templates/report_v3/`
- 不要在这一阶段就把所有模板拆散重写

### P3. 继续收紧 QA 门控

建议继续补 QA 检查项，例如：

- 附录标题与目录一致性
- 附录摘要与正文统计口径一致性
- 高风险问题卡最小证据门槛
- 强措辞门控

## 7. 在家里重新开始的最稳方式

### 7.1 拉代码

如果家里机器没有仓库：

```powershell
git clone https://github.com/cjian8888/cj-project.git
cd cj-project
git checkout main
```

如果家里机器已经有仓库：

```powershell
cd 你的仓库目录
git checkout main
git pull origin main
```

### 7.2 先读这些文件

新的 Codex 会话第一轮应先读：

1. `AGENTS.md`
2. `docs/report_system_rearchitecture_v1.md`
3. `docs/report_system_rearchitecture_implementation_plan_v1.md`
4. `docs/report_txt_audit_review_2026-03-18.md`
5. `docs/codex_handoff_2026-03-18.md`
6. `tests/test_report_package_builder.py`

### 7.3 先跑这组定向验证

```powershell
pytest -q tests\test_report_package_builder.py tests\test_report_package_api_flow.py
pytest -q tests\test_investigation_report_builder_metrics.py -k "render_html_report_v3_formats_dates_and_property_area_cleanly"
```

### 7.4 新 Codex 会话起手提示词

建议直接使用下面这段作为第一条消息：

```text
先读 AGENTS.md、docs/report_system_rearchitecture_v1.md、docs/report_system_rearchitecture_implementation_plan_v1.md、docs/report_txt_audit_review_2026-03-18.md、docs/codex_handoff_2026-03-18.md，再看 tests/test_report_package_builder.py 和最近一次提交。

当前主线是 report_package 语义层重构。已完成：
1. fact normalizer / issue engine / dossier builder / quality guard / view builder
2. company dossier 语义优先渲染
3. Appendix A-E semantic summary views
4. TXT/HTML 已接 appendix summary
5. 定向测试通过

不要跳去做前端大改。下一步是在当前主线上，把附录 A-E 从摘要视图扩成正式附录章节，并继续保持 semantic-first。
先检查 git status 和定向测试结果，再继续。
```

## 8. 关键约束，后续不要忘

- 唯一入口仍是 `api_server.py`
- 报告阶段禁止回读原始 Excel 重算
- 正式口径以 `output/analysis_cache/` 与 `output/cleaned_data/` 为准
- 交付目标仍是 `Windows 单机离线 one-folder 包`
- 当前阶段不以 `npm run dev` 作为交付方案
- 新能力默认应兼容后端承载前端生产构建

## 9. 一句话总结

今天已经把“报告语义层 + 公司卷宗接入 + 附录 A-E 摘要入口”这条主线打通。下一位 Codex 不需要重复做 Phase 1 基建，直接在这条线上继续扩正式附录即可。
