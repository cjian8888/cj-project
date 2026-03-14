# AML 分析引擎重构总方案

## 目标

本方案用于固化资金穿透与 AML 分析引擎的长期重构路线，避免阶段性对话上下文丢失。

重构必须同时满足以下约束：

- 前端界面输入不改
- 原始数据中的个人与公司统一作为排查对象
- 不预设排查对象之间已存在关系
- 允许从排查对象扩展到外围节点
- 报告与前端展示优先保持兼容
- 任何阶段都不能退化金额单位与时间排序正确性

## 统一概念

- `investigation_scope`
  - 本次核查的原始对象集合
  - 来自导入的个人流水与公司流水主体
- `focus_entities`
  - 报告重点展示对象
  - 只影响排序与展示，不影响图搜索剪枝
- `discovered_nodes`
  - 从交易数据中新发现的外围自然人、公司、账户、中间节点
- `relations`
  - 系统从交易中识别出的直接往来、多跳链路、闭环、借贷、现金碰撞、延迟转移等模式

## 分阶段路线

### 第一阶段：分析底座与高风险算法止血

目标：

- 建立统一严格排序能力
- 消除现金碰撞与延迟转账的明显性能崩点
- 为借贷核销重构提供公共能力
- 保持报告字段兼容

重点文件：

- `utils.py`
- `utils/__init__.py`
- `suspicion_detector.py`
- `time_series_analyzer.py`
- `loan_analyzer.py`

### 第二阶段：资金闭环与关系发现统一

目标：

- 统一强版闭环搜索
- 去掉“只有核心人员才继续深搜”的错误剪枝
- 支持排查对象之间及经外围节点形成的多跳关系发现

重点文件：

- `related_party_analyzer.py`
- `fund_penetration.py`
- `api_server.py`
- `specialized_reports.py`

### 第三阶段：报告与展示增强

目标：

- 报告层切换到统一结果优先级
- 新增 `insufficient_data`、`truncated`、`confidence` 等解释信息
- 前端展示增强外围节点来源与关系类型

重点文件：

- `specialized_reports.py`
- `report_generator.py`
- `flow_visualizer.py`
- `dashboard/src/components/NetworkGraph.tsx`

### 第四阶段：关系发现与风险评分增强

目标：

- 形成针对群体筛查场景的关系簇输出
- 增加闭环风险评分、过账通道评分、关系置信度
- 逐步增强图谱和报告可解释性

重点文件：

- `fund_penetration.py`
- `related_party_analyzer.py`
- `risk_scoring.py`
- `clue_aggregator.py`

## 每阶段必须遵守的兼容约束

### 报告兼容

- 第一阶段不能直接移除 `loan_pairs`
- 第一阶段不能直接移除 `no_repayment_loans`
- 第一阶段不能直接移除 `regular_repayments`
- 第一阶段不能直接改前端已有下载入口与报告入口

### 前端兼容

- 不新增用户输入项
- 不改变上传文件要求
- 不改变分析触发流程
- 新字段优先作为可忽略 metadata 提供

### 审计可解释性

- 新算法必须能给出路径、金额、时差、分配过程
- 不引入不可解释的黑箱主流程
- 大样本降级必须显式返回 `timeout/truncated`

## 当前执行顺序

1. 保持第一阶段金额/时序/借贷底座稳定
2. 持续推进第二阶段关系发现统一后的消费层收敛
3. 统一图谱、专项报告、正式报告的重点对象排序口径
4. 为闭环/中转/关系簇补齐路径级 explainability
5. 再进入更细颗粒度的关系评分增强

## 阶段交付物

每个阶段结束后必须同步更新：

- `docs/plans/aml_engine_refactor_master_plan.md`
- 对应阶段实施文档
- `docs/change_logs/`
- 至少一组覆盖关键算法边界的测试

## 进度快照（2026-03-14）

已完成：

- 第一阶段底座、现金碰撞、延迟转账、借贷序列止血
- 关系发现统一后的强版闭环、中转、外围节点、关系簇输出
- 聚合排序 explainability 接线
- 统一评分模型开始直接消费 relay / cluster / discovered_node
- 前端风险实体详情开始消费 `aggregation.evidencePacks`
- 正式报告结论与文本首页开始优先引用聚合排序重点对象
- `report_generator.py` 的 TXT / HTML / Excel / Word 老导出链路已统一到 `aggregation` 优先
- 图谱重点对象排序与报告重点对象排序已统一到共享 `aggregation` helper
- 闭环 / 中转 / 关系簇的首轮 `path_explainability` 已打通到聚合器、专项报告、图谱接口和前端展示
- 闭环边级金额口径与中转时间轴 explainability 已打通到专项报告和图谱展示
- 闭环逐跳样本流水引用与中转事件原始溯源已打通到专项报告和图谱展示

下一步重点：

- 继续细化关系簇、闭环、多跳中转的全量逐跳交易折叠 explainability
- 继续收敛专项报告与图谱对聚合结果的消费口径
- 逐步统一图谱重点节点高亮与路径证据模板
