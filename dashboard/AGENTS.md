# DASHBOARD MODULE

## OVERVIEW
React 前端应用，深色玻璃态主题的审计仪表盘。

## STRUCTURE
```
dashboard/
├── src/
│   ├── components/    # UI 组件
│   ├── contexts/      # 全局状态 (React Context)
│   ├── services/      # API 调用层
│   ├── utils/         # 工具函数
│   └── types/         # TypeScript 类型
├── public/            # 静态资源
└── package.json
```

## WHERE TO LOOK

| 任务 | 位置 |
|------|------|
| 页面组件 | src/components/ |
| API 调用 | src/services/api.ts |
| 全局状态 | src/contexts/ |
| 类型定义 | src/types/ |

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

## COMMANDS

```bash
npm run dev        # 开发服务器 (localhost:5173)
npm run build      # 生产构建
npm run type-check # TypeScript 检查
```

## NOTES
- Vite 7.x 构建
- vis-network 用于资金流向图
- Recharts 用于数据可视化
