# 2026-03-14 AML 消费层增强记录

## 本轮目标

- 在不修改前端输入界面的前提下，把第一阶段已经产出的新结构接到消费层
- 让外围节点、关系簇、强版资金闭环同时出现在：
  - 图谱可视化面板
  - 资金穿透专项报告
- 保持旧字段兼容，不破坏现有接口和报告入口

## 已完成

### 前端类型与状态兜底

- `dashboard/src/types/index.ts`
  - 为 `PenetrationResult` 增加 `fund_cycles`
  - 为 `RelatedPartyResult` 增加：
    - `direct_flows`
    - `third_party_relays`
    - `fund_loops`
    - `discovered_nodes`
    - `relationship_clusters`
  - 新增：
    - `FundCycle`
    - `DiscoveredNode`
    - `RelationshipCluster`

- `dashboard/src/contexts/AppContext.tsx`
  - 默认值与结果合并逻辑已保留上述新增字段
  - 防止后端已返回新结构时被前端默认兜底逻辑吞掉

### 图谱展示增强

- `dashboard/src/components/NetworkGraph.tsx`
  - 图谱左侧新增三块可折叠面板：
    - `资金闭环`
    - `外围节点`
    - `关系簇`
  - `资金闭环`
    - 优先展示 `report.fund_cycles`
    - 展示路径、节点数、风险等级、金额口径
  - `外围节点`
    - 展示节点名称
    - 关联核心对象
    - 关系类型
    - 出现次数
    - 涉及金额/待估状态
    - 风险等级
  - `关系簇`
    - 展示 `cluster_id`
    - 核心成员
    - 外围成员
    - 关系类型
    - 直接/中转/闭环计数
    - 聚合金额/待估状态
    - 风险等级

### 报告增强

- `specialized_reports.py`
  - `资金穿透分析报告` 的算法说明新增：
    - 外围节点扩展
    - 关系簇识别
  - 报告正文新增：
    - `三、外围节点发现`
    - `四、关系簇识别`
  - 新增输出要素：
    - 外围节点名称
    - 关联核心对象
    - 关系类型
    - 出现次数
    - 涉及金额
    - 关系簇成员与计数结构

## 本轮验证

- `pytest -q tests/test_specialized_reports.py`
  - 15 passed
- `pytest -q tests/test_api_server_config_flow.py tests/test_aml_phase1_foundation.py`
  - 13 passed
- `cd dashboard && npm run type-check`
  - passed

## 当前影响判断

- 前端输入：
  - 不变
- 后端接口：
  - 不需要新增输入参数
  - 继续兼容旧字段
- 图谱展示：
  - 新增结果可见性
  - 不影响既有节点/边加载逻辑
- 报告输出：
  - 在原有穿透报告上追加说明段落
  - 不替换旧的闭环与过账通道章节

## 下一步建议

- 若继续推进，应优先进入以下两项之一：
  - 为关系簇和闭环增加统一评分、置信度、截断说明
  - 在图谱中进一步区分“原始排查对象”和“扩展发现节点”的视觉语义
