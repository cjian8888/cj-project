# DASHBOARD COMPONENTS

## OVERVIEW
React UI 组件库，13 个 TSX 文件，深色玻璃态主题。

## STRUCTURE
```
dashboard/src/components/
├── Header.tsx              # 顶部导航
├── Sidebar.tsx             # 侧边栏配置面板
├── KPICards.tsx            # KPI 指标卡片
├── TabContent.tsx          # 主内容区 (5856行 - 包含所有标签页)
├── MainContent.tsx         # 主内容布局
├── NetworkGraph.tsx        # vis-network 资金流向图 (3786行)
├── ReportBuilder.tsx       # 报告生成 UI (900行)
├── PrimaryTargetsConfig.tsx # 主要目标归集配置
├── LogConsole.tsx          # 终端风格日志控制台
├── WalletSupplementTab.tsx # 电子钱包补充页
├── ErrorBoundary.tsx       # 错误边界
└── common/                # 通用组件
    ├── EmptyState.tsx      # 空状态显示
    └── Skeleton.tsx        # 加载骨架屏
```

## WHERE TO LOOK

| 组件 | 文件 | 功能 |
|------|------|------|
| 页面布局 | Header.tsx, Sidebar.tsx, MainContent.tsx | 导航、配置面板、内容区 |
| 数据展示 | KPICards.tsx, TabContent.tsx | 指标卡片、明细表格 |
| 可视化 | NetworkGraph.tsx | vis-network 资金流向图 |
| 报告 | ReportBuilder.tsx | HTML/TXT/XLSX 报告生成 |
| 归集配置 | PrimaryTargetsConfig.tsx | 主要目标配置 CRUD |
| 电子钱包 | WalletSupplementTab.tsx | 微信/支付宝/财付通摘要 |
| 状态 | ../contexts/AppContext.tsx (1078行) | 全局状态管理 |
| API | ../services/api.ts (830行) | HTTP/WebSocket 调用 |

## CONVENTIONS

### 组件风格
- TailwindCSS 4.x 类名
- 深色主题: `#030712` 背景, `#3b82f6` 主色, `#06b6d4` 次色
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
- **TabContent.tsx** 最大 (5856行)，包含所有标签页内容，建议按 tab 拆分
- **NetworkGraph.tsx** 次大 (3786行)，vis-network 资金流向可视化
- **ReportBuilder.tsx** (900行)，报告生成和下载
- 前端生产构建由后端 `GET /dashboard/` 提供
