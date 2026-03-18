# 报告体系重构设计文档 v1

> 状态: 草案  
> 日期: 2026-03-18  
> 目标: 在不推翻现有分析缓存体系的前提下，重构主报告、专项附录、HTML 报告和前端报告中心，使其从“算法命中汇总”升级为“审计问题驱动的统一报告体系”。

---

## 1. 背景与问题

当前系统已经具备较强的分析能力，核心事实层主要沉淀在 `output/analysis_cache/`：

- `profiles.json`: 实体画像
- `derived_data.json`: 借贷、收入、穿透、关联方、时序、行为、聚合结果
- `suspicions.json`: 疑点原始命中
- `walletData.json`: 电子钱包补充层
- `graph_data.json`: 图谱视图
- 以及房产、车辆、证券、保险、酒店、铁路、征信、AML 等外部缓存

但当前报告体系存在以下系统性问题：

1. 报告按“算法模块”组织，不按“审计问题”组织。
2. 主报告、专项报告、HTML、前端风险页分别从不同缓存路径拼装数据，导致口径难以完全一致。
3. 误报压降不足，自我转账、理财赎回、工资、社保、网贷放款、生活消费等正常场景反复进入高风险叙事。
4. 正式报告混入 `analysis_cache/derived_data.json -> ...` 这类开发实现细节。
5. 公司分析仍偏“补充章节”思维，未形成独立的公司卷宗与公司问题卡体系。
6. 风险评分过度依赖单一总分，无法同时表达严重度、证据强度和核查优先级。

因此，本次重构不应简单继续修模板，而应引入统一的“报告语义层”。

---

## 2. 核心设计原则

### 2.1 单一事实层

- 报告阶段严禁回读原始 Excel。
- 唯一事实来源仍是 `output/analysis_cache/` 与 `output/cleaned_data/`。
- 所有正式报告、专项附录、HTML、前端报告中心统一从同一中间产物读取。

### 2.2 单一语义层

- 新增 `report_package.json` 作为统一报告语义包。
- `report_package` 不是原始缓存复制，而是“审计可表达事实 + 审计问题 + 证据索引 + 叙事视图”的组合。

### 2.3 主报告只承载结论

- 主报告只放可写入正式研判的内容。
- 详细明细移入附录或对象卷宗。
- 技术日志与 QA 文件单独输出，不进入正式目录首页。

### 2.4 问题驱动而非算法驱动

- 报告按“问题卡”组织，而不是按 `loan / timeSeries / behavioral / penetration` 逐章堆砌。
- 一个问题可由多个分析模块共同支持。

### 2.5 证据与结论分层

- 每条结论必须包含最小证据链。
- 同时明确反证、限制和未决点，避免过度定性。

### 2.6 HTML 继续遵循“所见即所得”

- 前端预览与最终 HTML 报告必须继续使用同一后端模板链路。
- 但 HTML 结构改为读取新的 `report_package`，不再直接消费旧的混合报告结构。

---

## 3. 目标架构

```text
┌─────────────────────────────────────────────────────────┐
│                 分析缓存层 analysis_cache               │
│ profiles / derived_data / suspicions / wallet / graph  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│            报告语义层 report_package builder            │
│ facts → issue engine → dossier builder → QA guard      │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  report_package.json                    │
│ meta / coverage / issues / dossiers / appendices / qa  │
└─────────────────────────────────────────────────────────┘
              │                    │                    │
              ▼                    ▼                    ▼
      主报告渲染器             附录渲染器           前端报告中心
      HTML / TXT               HTML / TXT           统一读取语义包
```

---

## 4. report_package 结构

顶层建议结构：

```json
{
  "meta": {},
  "coverage": {},
  "priority_board": [],
  "issues": [],
  "family_dossiers": [],
  "person_dossiers": [],
  "company_dossiers": [],
  "appendix_views": {},
  "evidence_index": {},
  "qa_checks": {}
}
```

### 4.1 meta

用于描述报告的生成环境和正式口径：

- `generated_at`
- `report_version`
- `cache_version`
- `data_flow`
- `doc_number`
- `case_name`
- `primary_subjects`
- `companies`
- `generator`

### 4.2 coverage

必须在所有正式报告首页显示：

- `data_range.start_date`
- `data_range.end_date`
- `persons_count`
- `companies_count`
- `bank_transaction_count`
- `wallet_subject_count`
- `wallet_transaction_count`
- `property_record_count`
- `vehicle_record_count`
- `available_external_sources`
- `missing_sources`
- `known_limitations`

### 4.3 priority_board

跨个人、家庭、公司统一排序，只回答“先查谁”。

示例字段：

```json
{
  "entity_type": "person",
  "entity_name": "朱明",
  "family_name": "朱明家庭",
  "priority_score": 87.5,
  "risk_level": "high",
  "confidence": 0.81,
  "top_reasons": [
    "疑似过账通道",
    "与高风险关系簇重合",
    "电子钱包与银行主链出现交叉高风险对手"
  ],
  "issue_refs": ["PEN-001", "WAL-003", "REL-004"]
}
```

### 4.4 issues

`issues` 是主报告的核心。

```json
{
  "issue_id": "PEN-001",
  "theme": "资金穿透",
  "category": "过账通道",
  "scope": {
    "family": "朱明家庭",
    "entity": "赵峰",
    "company": "北京鑫兴航科技有限公司"
  },
  "headline": "赵峰存在同日50万元快进快出并指向北京鑫兴航科技有限公司",
  "severity": 82,
  "confidence": 0.78,
  "priority": 88,
  "risk_level": "high",
  "status": "需核查",
  "amount_impact": 500000.0,
  "time_range": {
    "start": "2025-02-09",
    "end": "2025-02-09"
  },
  "why_flagged": [
    "收到50万元后1.4小时转出50万元",
    "上下游主体均为主链对象",
    "相关路径与团伙/关系簇交叉"
  ],
  "counter_indicators": [
    "尚未见合同、借据或业务背景材料",
    "需排除家庭内部代转或正常代付"
  ],
  "narrative": "从审计角度看，该笔交易更符合通道型资金转移特征，建议优先核查业务背景与交易凭证。",
  "evidence_refs": ["EVT-9001", "PATH-102", "CLUS-004"],
  "next_actions": [
    "调取该笔上下游凭证",
    "核查赵峰与北京鑫兴航科技有限公司关系",
    "补查对应时间段聊天、订单或合同"
  ]
}
```

### 4.5 family_dossiers / person_dossiers / company_dossiers

卷宗用于对象级复核，不承担跨对象排序职责。

#### family_dossier

- 家庭成员构成
- 家庭资产总览
- 家庭真实收入/真实支出
- 家庭内部互转
- 家庭层面风险判断
- 家庭主要问题卡引用

#### person_dossier

- 基本信息
- 房产/车辆/理财/账户
- 真实收入结构
- 收支匹配
- 主要流入/流出对手
- 借贷/时序/行为/关系/穿透相关问题
- 电子钱包补证
- 个人下一步核查动作

#### company_dossier

- 公司画像
- 公司角色标签
- 主要上下游
- 与个人/家庭/公司交叉关系
- 行为异常
- 关键问题卡
- 公司补证建议

### 4.6 appendix_views

专项附录不再按旧的 7 份 TXT 平铺，而是重组为 5 个正式附录：

- `appendix_a_assets_income`
- `appendix_b_income_loan`
- `appendix_c_network_penetration`
- `appendix_d_timeline_behavior`
- `appendix_e_wallet_supplement`

### 4.7 evidence_index

所有正式问题卡只引用 `evidence_refs`，真正的明细都在统一证据索引里。

证据最小单元建议包括：

- `type`: `transaction` / `path` / `cluster` / `wallet_alert` / `property` / `account` / `aml` / `external`
- `source_file`
- `source_row_index`
- `source_sheet`
- `timestamp`
- `amount`
- `counterparty`
- `description`
- `raw_ref`
- `normalized_ref`
- `explainability`

### 4.8 qa_checks

报告前置硬检查：

- 口径冲突检查
- 误报过滤检查
- HTML/主报告/附录目录一致性
- 问题卡最小证据门槛检查
- 高风险强措辞门控检查

---

## 5. 风险评价体系

当前系统的问题不是没有分数，而是“一个分数承担了太多含义”。新体系改为三层：

### 5.1 severity

如果问题属实，风险有多严重。

参考因素：

- 涉及金额
- 身份敏感度
- 公司/个人/家庭关系敏感度
- 闭环/过账/利益输送/现金碰撞等问题类型
- 是否影响正式定性或后续调查

### 5.2 confidence

当前证据有多扎实。

参考因素：

- 是否有原始流水和行号
- 是否有跨模块交叉支持
- 是否存在明确反证
- 对手方和交易摘要是否完整
- 是否只有统计信号而无路径证据

### 5.3 priority

当前应不应该优先查。

参考因素：

- `severity`
- `confidence`
- 对象是否属于核心人员/配偶/子女/关联公司
- 相关材料是否可在短期内核查
- 是否涉及正在调查的关键主题

### 5.4 风险状态

除分值外，每个问题还要输出状态：

- `线索级`
- `可疑级`
- `高可信级`
- `已有较强证据级`

### 5.5 统一映射原则

- 个人、家庭、公司可以保留不同的底层维度。
- 但所有对象最终必须统一映射为 `priority_score`，用于同一排序板。

---

## 6. 公司分析体系

公司部分不再只是“个人报告后的补充页”，而是独立的对象体系。

### 6.1 公司角色标签

每家公司先进行网络角色定位：

- 正常经营主体
- 关键资金节点
- 汇集节点
- 分发节点
- 过账通道
- 桥接节点
- 疑似利益输送节点

### 6.2 公司六维分析

公司卷宗固定包含六个维度：

1. 经营合理性
2. 公司对个人输送
3. 公司间异常循环
4. 通道/枢纽/桥接角色
5. 现金与非工作时段异常
6. 与调查单位、核心家庭、关键对象的交叉关系

### 6.3 公司问题卡示例

#### 示例一：公司对个人输送

- 标题: 北京智晟睿科技有限公司连续向王永安转入大额资金
- 证据: 多次公司转个人、周期性、多家公司/多对象交叉
- 风险: 可能为工资、劳务、借款，也可能为利益输送
- 动作: 补合同、岗位、考勤、项目背景

#### 示例二：公司桥接节点

- 标题: 贵州锐晶科技有限公司呈现高连接度与整进散出特征
- 证据: 图谱连接、行为特征、关系网络交叉
- 风险: 可能为关键桥接/分发节点
- 动作: 核查业务链条与真实上下游

### 6.4 公司卷宗结构

```json
{
  "company_name": "贵州锐晶科技有限公司",
  "role_tags": ["关键资金节点", "桥接节点"],
  "summary": {
    "total_income": 0,
    "total_expense": 0,
    "transaction_count": 0,
    "cash_ratio": 0,
    "active_months": 0
  },
  "top_counterparties": {},
  "person_links": [],
  "company_links": [],
  "behavioral_findings": [],
  "issue_refs": [],
  "recommended_actions": []
}
```

---

## 7. 误报压降与措辞门控

### 7.1 优先排除场景

在进入主报告问题卡之前，优先识别并降级或排除：

- 自我转账
- 理财申购/赎回本金
- 退款
- 工资、劳务、社保、公积金
- 网贷放款
- 明显商户消费
- 家庭内部往来
- 已知支付平台过桥

### 7.2 强措辞门控

未经最小证据门槛，不允许在正式报告中直接使用：

- 洗钱
- 受贿
- 利益输送
- 空壳公司
- 资金闭环

替代措辞：

- “存在可疑线索”
- “符合通道型特征”
- “需进一步核查是否”
- “疑似形成异常路径”

---

## 8. HTML 报告设计

HTML 保持“正式报告唯一预览件”的定位，但结构从旧的“按章节顺铺”升级为“问题驱动 + 对象卷宗 + 证据抽屉”。

### 8.1 HTML 第一层：摘要层

- 数据覆盖概览
- 总体风险判断
- Top 问题矩阵
- Top 对象排序
- Top 公司排序
- 下一步工作建议

### 8.2 HTML 第二层：问题层

- 按主题浏览问题卡
- 支持按风险等级、对象类型筛选
- 每张卡展示：
  - 标题
  - 风险等级
  - 置信度
  - 金额影响
  - 关键证据
  - 排除因素
  - 下一步动作

### 8.3 HTML 第三层：卷宗层

- 家庭卷宗
- 个人卷宗
- 公司卷宗

### 8.4 HTML 第四层：证据层

- 代表交易
- 关键路径
- 代表关系簇
- 电子钱包补证
- 源文件和行号

### 8.5 HTML 交互约束

允许：

- 折叠/展开
- 锚点跳转
- 筛选
- 打印
- 导出

禁止：

- 前端独立重算风险
- 前端重新拼接不同口径的统计数字

---

## 9. 前端影响评估

### 9.1 小影响

- 报告列表
- 报告分类
- HTML/TXT/Excel 预览与下载

### 9.2 中影响

- `审计报告` 页从“文件列表”升级为“报告中心”
- 报告首页增加问题总览与对象导航

### 9.3 中到大影响

- `风险情报` 页改为消费统一的问题卡
- `图谱` 页与公司卷宗、路径证据、问题卡建立联动

### 9.4 前端实施建议

前端分两期：

#### 第一期

- 保持现有页面结构
- 先适配新目录与新 HTML
- 增加主报告 / 问题清单 / 附录 / 卷宗分组展示

#### 第二期

- 新增问题总览页
- 新增公司专题页
- 新增证据抽屉
- 将图谱与问题卡联动

---

## 10. 与现有代码的关系

### 10.1 保留

- `analysis_cache` 事实层
- `templates/report_v3/` 作为 HTML 模板入口
- `ReportBuilder` 前端预览模式
- `company_risk_analyzer.py` 的公司维度基础能力

### 10.2 收敛

- `investigation_report_builder.py` 从“大而全拼装器”收敛为总编排器
- `specialized_reports.py` 从“专题独立报告生成器”收敛为附录渲染器
- `wallet_report_builder.py` 从独立报告生成转为电子钱包补证视图提供器

### 10.3 新增

- `report_fact_normalizer.py`
- `report_issue_engine.py`
- `report_dossier_builder.py`
- `report_quality_guard.py`
- `report_view_builder.py`
- `report_renderer_html.py`
- `report_renderer_txt.py`
- `report_manifest_builder.py`

---

## 11. 成功标准

重构完成后，正式报告应满足：

1. 主报告、HTML、附录、前端展示使用同一语义包。
2. 不再出现 “HTML 不存在却要求优先查看 HTML”。
3. 不再出现 “未发现闭环” 与 “闭环团伙” 同时存在。
4. 不再将工资、社保、理财赎回、自我转账、正常消费直接打入主报告高风险叙事。
5. 公司、个人、家庭均能统一进入同一核查优先级排序板。
6. 技术日志与正式报告彻底分层。

---

## 12. 一句话总结

本次重构的本质，不是“再做一版更漂亮的报告模板”，而是把系统从“分析命中输出器”升级为“审计问题编排器”。

