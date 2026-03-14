# 2026-03-14 图谱与右侧详情双向联动

## 本轮目标

- 把图谱与右侧详情从“按钮式定位”升级为“双向联动”
- 图上点击节点/边时，右侧自动展开并高亮最相关路径
- 右侧点击路径时，图谱自动高亮对应节点集合

## 本次改动

### `dashboard/src/components/NetworkGraph.tsx`

- 新增统一联动状态：
  - `activeSelection`
- 新增联动对象抽象：
  - `LinkedSelection`
- 新增核心 helper：
  - `expandSections`
  - `buildLinkedSelections`
  - `getSelectionEdges`
  - `activateSelection`
  - `syncPanelToGraphSelection`
  - `resolveGraphNodeNameById`
- 图谱点击增强：
  - 点击节点时，按节点命中关系自动联动右侧
  - 点击边时，优先按边命中关系自动联动右侧
- 右侧卡片增强：
  - 资金闭环新增“定位路径”
  - 第三方中转新增“定位路径”
  - 关系簇新增“定位关系簇”
  - 关系簇代表路径新增“定位路径”
- 视觉反馈增强：
  - 当前联动对象卡片高亮
  - 顶部标题栏展示“联动路径”
  - 操作提示补充“点击图中节点/边会自动联动到右侧最相关路径”

## 联动范围

```text
图谱 -> 右侧
├── 资金闭环
├── 第三方中转
├── 关系簇
└── 关系簇代表路径

右侧 -> 图谱
├── 资金闭环路径定位
├── 第三方中转路径定位
├── 关系簇整体定位
└── 关系簇代表路径定位
```

## 验证结果

- `cd dashboard && npm run type-check`
  - passed
- `pytest -q tests/test_aml_phase1_foundation.py tests/test_api_server_config_flow.py tests/test_specialized_reports.py`
  - `33 passed, 2 warnings`

## 当前影响判断

- 前端输入界面：
  - 不变
- 图谱展示：
  - 节点/边点击后会自动联动到右侧路径
- 右侧详情：
  - 路径可反向驱动图谱定位
- 兼容性：
  - 纯前端交互增强，不改接口输入，不破坏旧字段
