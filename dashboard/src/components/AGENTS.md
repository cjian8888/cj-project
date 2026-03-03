# DASHBOARD COMPONENTS

## OVERVIEW

React UI 组件库，11 个 TSX 文件，深色玻璃态主题。

## STRUCTURE

```
dashboard/src/components/
├── Header.tsx              # 顶部导航
├── Sidebar.tsx             # 侧边栏配置
├── KPICards.tsx            # KPI 指标卡片
├── TabContent.tsx          # 主内容区 (2165行)
├── NetworkGraph.tsx        # 资金流向图
├── ReportBuilder.tsx       # 报告生成器
├── PrimaryTargetsConfig.tsx # 主要目标配置
├── LogConsole.tsx          # 日志控制台
└── common/                # 通用组件
    ├── LoadingSpinner.tsx
    └── ErrorMessage.tsx
```

## WHERE TO LOOK

| 组件 | 文件 | 功能 |
|------|------|------|
| 页面布局 | Header.tsx, Sidebar.tsx | 导航和配置面板 |
| 数据展示 | KPICards.tsx, TabContent.tsx | 指标和明细 |
| 可视化 | NetworkGraph.tsx | vis-network 资金流向 |
| 报告 | ReportBuilder.tsx | Excel/HTML 报告生成 |
| 状态 | ../contexts/AppContext.tsx | 全局状态管理 |
| API | ../services/api.ts | HTTP/WebSocket 调用 |

## CONVENTIONS

### 组件风格
- TailwindCSS 4.x 类名
- 深色主题: `#030712` 背景, `#3b82f6` 主色
- 玻璃态效果: `.glass` 类
- 渐变边框: `.gradient-border` 类

### 状态管理
```typescript
import { useApp } from '@/contexts/AppContext';

const { state, dispatch } = useApp();
```

### API 调用
```typescript
import { api } from '@/services/api';
const data = await api.getAnalysisResults();
```

## NOTES

- **TabContent.tsx** 最大 (2165行)，包含所有标签页内容
- **vis-network** 用于资金流向可视化
- **Recharts** 用于数据图表
- **WebSocket** 实时日志推送
- 响应式设计，适配桌面和平板
