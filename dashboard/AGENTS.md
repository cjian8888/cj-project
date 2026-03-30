# DASHBOARD MODULE

## OVERVIEW
React 前端应用，深色玻璃态主题的审计仪表盘。Vite 7 + React 19 + TypeScript 5.9 + TailwindCSS 4.1。

## STRUCTURE
```
dashboard/
├── src/
│   ├── components/    # UI 组件 (13 TSX)
│   │   ├── TabContent.tsx       # 主内容区 (5856行 - 最大)
│   │   ├── NetworkGraph.tsx     # 资金流向图 (3786行)
│   │   ├── ReportBuilder.tsx    # 报告生成器 (900行)
│   │   └── common/             # 通用组件
│   ├── contexts/
│   │   └── AppContext.tsx       # 全局状态 (1078行)
│   ├── services/
│   │   └── api.ts               # HTTP/WebSocket (830行)
│   ├── types/
│   │   └── index.ts             # TypeScript 类型 (754行)
│   ├── utils/                   # 工具函数
│   ├── constants/               # 常量 (appVersion.ts)
│   ├── App.tsx                  # 根组件
│   ├── main.tsx                 # 入口
│   └── index.css                # 全局样式
├── public/                      # 静态资源
├── dist/                        # 生产构建 (后端承载)
├── vite.config.ts               # Vite 配置
├── tsconfig.json                # TypeScript 配置
└── package.json                 # React 19.2, Vite 7.2, TailwindCSS 4.1
```

## WHERE TO LOOK

| 任务 | 位置 |
|------|------|
| 页面组件 | src/components/ |
| API 调用 | src/services/api.ts |
| 全局状态 | src/contexts/AppContext.tsx |
| 类型定义 | src/types/index.ts |
| 工具函数 | src/utils/ (formatters, suspicionUtils, auditTerms) |

## CONVENTIONS

### 组件风格
- TailwindCSS 4.x 类名
- 深色主题: bg `#030712`, 主色 `#3b82f6`
- 玻璃态效果: `.glass` 类

### API 调用
```typescript
import { api } from '@/services/api';
const data = await api.getAnalysisResults();
```

### 状态管理
```typescript
import { useApp } from '@/contexts/AppContext';
const { state, dispatch } = useApp();
```

### Vite 配置
- Base path: `/dashboard/` (build), `/` (dev)
- Proxy: `/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000`
- 开发态: `0.0.0.0:5173`

## COMMANDS

```bash
npm run dev        # 开发服务器 (0.0.0.0:5173)
npm run build      # 生产构建 (base: /dashboard/)
npm run type-check # TypeScript 检查
npm run lint       # ESLint 检查
```

## NOTES
- 生产构建由后端 `GET /dashboard/` 承载，开发代理 `/api` 和 `/ws`
- vis-network 用于资金流向图
- Recharts 用于数据可视化
- html2canvas 用于报告截图
- 交付态不需要 Node 开发服务器
