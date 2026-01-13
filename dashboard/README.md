# 穿云审计 Dashboard

<div align="center">
  <img src="../docs/screenshots/dashboard_overview.png" alt="Dashboard Overview" width="700" />
  
  <p>
    <img src="https://img.shields.io/badge/React-19.2.0-61DAFB?logo=react" alt="React" />
    <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript" alt="TypeScript" />
    <img src="https://img.shields.io/badge/Vite-7.2-646CFF?logo=vite" alt="Vite" />
    <img src="https://img.shields.io/badge/TailwindCSS-4.1-06B6D4?logo=tailwindcss" alt="TailwindCSS" />
  </p>
</div>

---

**穿云审计** 的专业级前端 Dashboard，提供现代化的资金审计可视化界面。

## ✨ 功能特性

- 🎨 **现代化 UI 设计** - 深色主题、玻璃态效果、流畅动画
- 📊 **实时数据可视化** - 使用 Recharts 展示资金流动趋势
- 🔍 **风险情报监控** - 可疑交易检测与高亮展示
- 🌐 **关系图谱** - 实体间资金往来可视化
- 📝 **审计报告导出** - 一键下载 Excel/HTML 报告
- 🔄 **实时日志推送** - WebSocket 实时显示分析进度
- 📱 **响应式设计** - 适配桌面和平板设备
- 📂 **原生文件夹选择** - 支持 Mac/Windows/Linux

## 🚀 快速开始

### 前置要求

- Node.js 18+
- npm 或 pnpm

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173 查看 Dashboard。

### 构建生产版本

```bash
npm run build
```

## 🔌 后端 API

Dashboard 需要配合 FastAPI 后端使用以获取真实数据：

```bash
# 在项目根目录启动 API 服务
pip install fastapi uvicorn
python api_server.py
```

API 服务默认运行在 http://localhost:8000。

### 环境变量

在 `.env.development` 或 `.env.production` 中配置：

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

## 📁 项目结构

```
dashboard/
├── src/
│   ├── components/       # UI 组件
│   │   ├── Header.tsx       # 顶部导航栏
│   │   ├── Sidebar.tsx      # 侧边栏配置面板
│   │   ├── KPICards.tsx     # KPI 指标卡片
│   │   ├── TabContent.tsx   # 标签页内容
│   │   ├── LogConsole.tsx   # 终端风格日志控制台
│   │   └── MainContent.tsx  # 主内容区域
│   ├── contexts/         # React Context
│   │   └── AppContext.tsx   # 全局状态管理
│   ├── services/         # API 服务层
│   │   └── api.ts          # HTTP/WebSocket 通信
│   ├── types/            # TypeScript 类型定义
│   │   └── index.ts
│   ├── App.tsx           # 根组件
│   ├── main.tsx          # 入口文件
│   └── index.css         # 全局样式
├── public/               # 静态资源
├── index.html            # HTML 模板
└── package.json
```

## 🎨 设计系统

### 配色方案

| 颜色 | 用途 |
|------|------|
| `#030712` | 主背景色 |
| `#3b82f6` | 主强调色 (蓝) |
| `#06b6d4` | 次强调色 (青) |
| `#ef4444` | 危险/错误 |
| `#10b981` | 成功/安全 |

### 组件类

- `.glass` - 玻璃态背景效果
- `.gradient-border` - 渐变边框
- `.btn-primary` / `.btn-secondary` - 按钮样式
- `.card` - 卡片容器
- `.badge-*` - 标签徽章
- `.terminal` - 终端样式

## 📄 License

MIT License

---

<div align="center">
  <p><strong>穿云审计</strong> - 穿透资金迷雾，洞察财务真相</p>
</div>
