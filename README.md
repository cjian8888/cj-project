# 穿云审计 (F.P.A.S)

> 当前版本：`v4.6.0`
>
> 当前交付形态：`Windows 单机离线 one-folder 包`
>
> 应用内文档入口：启动后访问 `/docs/readme`，或在左下角点击“交付文档”

穿云审计不是一套泛化 BI，也不是一个“导完 Excel 看图表”的轻系统。它的目标是把审计排查里最费人工、最容易口径漂移、最容易被报告打脸的工作链条收口成一条可复核的离线主线：

1. 从原始银行流水和外部协查数据中提取事实。
2. 在 `output/cleaned_data/` 中沉淀可追溯的清洗结果。
3. 在 `output/analysis_cache/` 中沉淀融合画像、分析结果和统一语义层输入。
4. 在 `output/analysis_results/` 中输出正式 HTML/TXT/Excel、专项报告、QA 产物和报告清单。
5. 由 `/dashboard/` 前端直接消费正式语义包、报告清单和 QA 结果，而不是再走一套独立口径。

![当前仪表盘概览（已脱敏，仅保留聚合指标与交付界面）](docs/assets/readme/dashboard-overview-redacted.png)

---

## 这次版本升级解决了什么

`v4.6.0` 对应的不是单点修补，而是一轮交付前收口：

- 银行流水清洗不再粗暴过度去重。
- 无效交易状态会被统一过滤，避免冲正、失败、退汇混入总账。
- 微信手机号归并补上“当前绑定手机号 / 别名 / wxid”链路。
- 正式报告、Excel 底稿、QA 产物和前端报告中心统一围绕 `report_package.json` 工作。
- 报告中心不再只是“文件下载列表”，而是直接展示：
  - 主报告摘要
  - 优先对象排序
  - 问题卡
  - 卷宗覆盖
  - QA 摘要
  - 预览与下载入口
- 交付前新增了金标准、故障注入、异实现复算和总验收套件，不再只靠单一盲盒脚本自证。

---

## 当前系统应该怎么理解

### 一句话架构

`原始数据 -> 清洗成品 -> 分析缓存 -> 统一语义包 -> 正式报告 / QA / 前端报告中心`

### 三层输出契约

- `output/cleaned_data/`
  - 这是全系统的事实成品层。
  - 所有“银行流水到底有多少笔、某人流入流出到底是多少”的人工复核，应优先落在这里。
- `output/analysis_cache/`
  - 这是融合画像与分析中间层。
  - 包含 `profiles.json`、`derived_data.json`、`suspicions.json`、`graph_data.json` 等缓存。
  - 正式报告构建器和前端都从这里读取统一结果，不应再回原始 `data/` 重新拼事实。
- `output/analysis_results/`
  - 这是交付层。
  - 包含正式 HTML/TXT/Excel、专项报告、日志、QA 产物、报告目录清单。

### 报告主链

```text
data/
  -> data_cleaner.py
  -> output/cleaned_data/
  -> financial_profiler.py + analyzer modules
  -> output/analysis_cache/
  -> investigation_report_builder.py
  -> qa/report_package.json
  -> qa/report_consistency_check.{json,txt}
  -> 初查报告.html / 核查结果分析报告.txt / 资金核查底稿.xlsx
  -> /api/reports/manifest
  -> /dashboard/ 审计报告中心
```

---

## 交付标准

### 最终运行形态

- 目标平台：Windows
- 运行方式：单机、离线
- 交付形式：`one-folder`
- 后端入口：`api_server.py`
- 前端入口：由后端直接承载 `dashboard/dist`
- 最终访问地址：`http://localhost:8000/dashboard/`

### 开发态与交付态边界

开发态：

```bash
python api_server.py
cd dashboard
npm run dev
```

交付态 / 打包态：

```bash
cd dashboard
npm run build
cd ..
python api_server.py
```

Windows 打包态：

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-windows-build.txt
cd dashboard
npm install
npm run build
cd ..
python build_windows_package.py
```

### 新功能必须遵守的约束

- 不依赖互联网服务。
- 不依赖 Node 开发服务器作为最终运行方式。
- 不写死 macOS / Windows 绝对路径。
- 新增运行时资源必须能被 PyInstaller 带入离线包。

---

## 报告中心现在怎么工作

前端“审计报告”页面向业务使用者，只展示正式报告终稿，不再暴露内部工程物料。

当前使用方式：

- 只展示供业务阅读的正式报告文件。
- 只保留 `HTML / PDF / TXT` 这类可直接阅读的终稿。
- 前端默认屏蔽 `qa/` 目录产物、`.json` 结构化文件、工作底稿和其他内部技术文件。
- “交付文档”入口打开的是只读使用说明页，不承担研发排障功能。

前端当前能做的事情：

- 预览正式主报告。
- 下载正式主报告和业务附录。
- 浏览正式问题卡、优先对象与卷宗覆盖摘要。
- 在图谱页和报告页统一使用正式报告摘要作为浏览入口。

---

## 数据处理主线

### 1. 银行流水清洗

核心文件：

- `data_cleaner.py`
- `bank_formats.py`
- `data_validator.py`
- `utils/safe_types.py`

当前清洗阶段的重点：

- 统一不同银行的列名、时间、金额、方向、摘要、对手方、账号。
- 保留来源文件与来源行号，确保后续可追溯。
- 优先使用 `transaction_id` 精确去重。
- 拦截失败、冲正、退汇、关闭、撤销等无效交易状态。
- 避免把“同时间同金额的合法连续转账”误删成重复。

### 2. 融合画像与真实收支

核心文件：

- `financial_profiler.py`
- `salary_analyzer.py`
- `income_analyzer.py`
- `loan_analyzer.py`
- `wallet_data_extractor.py`

当前画像层会收口这些口径：

- 总流入 / 总流出
- 真实收入 / 真实支出
- 工资、自转、理财、本金回流、报销退款等剔除项
- 钱包补充层的主体归并、登录轨迹、交易规模和平台交叉信号

### 3. 全面分析与疑点检测

核心文件：

- `fund_penetration.py`
- `related_party_analyzer.py`
- `multi_source_correlator.py`
- `time_series_analyzer.py`
- `suspicion_engine.py`
- `clue_aggregator.py`

输出重点：

- 资金闭环
- 过账通道
- 直接往来
- 多源关系碰撞
- 借贷模式
- 时序异常
- 统一风险线索

### 4. 正式报告输出

核心文件：

- `investigation_report_builder.py`
- `report_view_builder.py`
- `report_dossier_builder.py`
- `report_fact_normalizer.py`
- `report_quality_guard.py`
- `report_generator.py`
- `api_server.py`

当前交付给使用者的正式输出收口到：

- `初查报告.html`
- `核查结果分析报告.txt`
- 业务附录（如存在）

说明：

- `report_package.json`、`report_consistency_check.*` 属于系统内部校验产物。
- 这些内部文件不会在前端业务视图中展示。

---

## 当前推荐的使用方式

### 真实数据全量跑一轮

```bash
python api_server.py
```

然后在前端点击“开始分析”，或通过 API 触发完整分析。

### 看结果时的优先级

1. 先在 `/dashboard/` 查看正式问题、优先对象和卷宗覆盖
2. 再看 `初查报告.html`、`核查结果分析报告.txt` 以及业务附录
3. 如需回溯明细，再看 `output/cleaned_data/`

### 哪些文件是交付基线

- `output/cleaned_data/`
- `output/analysis_results/初查报告.html`
- `output/analysis_results/核查结果分析报告.txt`
- `output/analysis_results/` 下的业务附录终稿（如存在）

---

## 验收与自证

这次交付不再只靠“脚本跑绿了”一句话，而是四层自证：

- 真实数据全量重跑
- 金标准样本校验
- 故障注入验证
- 异实现复算验证

当前仓库内的关键验收脚本：

- `tmp_e2e_blindbox_audit.py`
- `tmp_e2e_boundary_blindbox_audit.py`
- `tmp_e2e_delivery_blindbox_audit.py`
- `tmp_e2e_gold_standard_audit.py`
- `tmp_e2e_fault_injection_validation.py`
- `tmp_e2e_independent_recompute_audit.py`
- `tmp_e2e_final_acceptance_suite.py`

建议的交付前命令：

```bash
python tmp_e2e_final_acceptance_suite.py
```

真实数据下的最终验收结果应落到：

```text
output/analysis_results/qa/e2e_final_acceptance_suite_report.txt
```

---

## 应用内文档策略

这次没有把 README 文案再复制一份塞进前端业务页面，而是采用下面的策略：

- `README.md` 是唯一事实源。
- 前端左下角只提供“交付文档”入口。
- 后端通过 `/docs/readme` 渲染只读文档页。
- 文档内容只面向使用者，不展示内部 QA/JSON 产物与研发排障细节。

这样做的原因很直接：

- 避免 README、前端帮助页、交付说明三份文档继续漂移。
- 让离线包在没有 GitHub、没有编辑器的环境里也能直接查看文档。
- 保持文档更新成本最低，交付时只需要维护一份源文件。

---

## 关键目录与入口文件

后端主入口：

- `api_server.py`

数据清洗：

- `data_cleaner.py`

画像与分析：

- `financial_profiler.py`
- `loan_analyzer.py`
- `income_analyzer.py`
- `fund_penetration.py`
- `related_party_analyzer.py`
- `time_series_analyzer.py`

报告与 QA：

- `investigation_report_builder.py`
- `report_generator.py`
- `report_quality_guard.py`

前端：

- `dashboard/src/components/Sidebar.tsx`
- `dashboard/src/components/TabContent.tsx`
- `dashboard/src/components/NetworkGraph.tsx`
- `dashboard/src/services/api.ts`
- `dashboard/src/constants/appVersion.ts`

打包：

- `build_windows_package.py`
- `build_windows_package.bat`
- `fpas_windows.spec`

---

## 常见问题

### 1. 系统应该以哪里为准？

如果你在核对数字，优先以 `output/cleaned_data/` 为准；如果你在核对正式报告是否一致，优先看 `qa/report_package.json` 与 `qa/report_consistency_check.*`。

### 2. 为什么前端看起来和以前不一样？

因为前端现在已经和正式语义层打通，不再只是展示旧式缓存字段或平铺文件列表。

### 3. 为什么不把 README 整份复制到前端？

复制一份最容易再次漂移。当前策略是前端只提供入口，README 仍是唯一事实源。

### 4. 现在还需要 Vite 开发服务器吗？

开发调试需要；交付运行不需要。最终交付必须由后端直接承载 `dashboard/dist`。

---

## 补充说明

如果你是新接手这个项目的开发者、审计人员或打包人员，先接受以下事实再继续工作：

- `api_server.py` 是唯一后端入口。
- 最终目标是 `Windows 单机离线 one-folder 包`。
- `/dashboard/` 是正式前端入口，不是附属演示页。
- 正式报告、Excel 底稿、QA 和前端报告中心已经进入统一语义层主线。
- 交付前必须跑一轮真实数据和最终验收套件，而不是只看单元测试。

---

## 相关文件

- `CHANGELOG.md`
- `WINDOWS_OFFLINE_DELIVERY.md`
- `output/analysis_results/qa/`
- `tests/fixtures/blindbox_gold_standard.json`
