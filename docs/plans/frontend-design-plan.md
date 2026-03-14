# 资金穿透与关联排查系统 - 前端界面设计方案

## 一、项目概述

### 1.1 系统名称
**F.P.A.A.S** - Financial Penetration & Association Audit System
（资金穿透与关联排查系统）

### 1.2 技术栈
- **前端框架**: React 19 + TypeScript
- **样式方案**: Tailwind CSS 4
- **图表库**: Recharts
- **图标库**: Lucide React
- **构建工具**: Vite

### 1.3 设计理念
- **现代化**: 采用深色玻璃拟态（Glassmorphism）设计风格
- **科技感**: 蓝色/青色渐变配色，营造专业金融分析氛围
- **实时性**: 类似 Antigravity 调试界面的实时日志输出
- **专业性**: 清晰的数据展示和可视化图表

---

## 二、界面布局架构

### 2.1 整体布局

```
┌─────────────────────────────────────────────────────────────────┐
│  顶部导航栏 (高度: 60px)                                          │
├──────────┬──────────────────────────────────────────────────────┤
│          │  主内容区域 (可滚动)                                  │
│          │  ┌────────────────────────────────────────────────┐  │
│          │  │  KPI 指标卡片 (4列)                            │  │
│          │  ├────────────────────────────────────────────────┤  │
│          │  │  标签页导航 (Overview / Risk Intel / Graph / Report)│
│          │  ├────────────────────────────────────────────────┤  │
│          │  │  标签页内容区域                                 │  │
│          │  │  - 概览: 资金分布、交易趋势图表                 │  │
│          │  │  - 风险: 疑点活动列表、风险分布图               │  │
│          │  │  - 图谱: 关联关系图                            │  │
│          │  │  - 报告: 导出功能、报告预览                    │  │
│          │  └────────────────────────────────────────────────┘  │
│          ├──────────────────────────────────────────────────────┤
│          │  实时日志控制台 (高度: 280px)                        │
│          │  ┌────────────────────────────────────────────────┐  │
│          │  │  [09:00:01] INFO  System initialized...         │  │
│          │  │  [09:00:02] INFO  Scanning data artifacts...   │  │
│          │  │  [09:00:05] WARN  Latency detected...          │  │
│          │  │  ...                                           │  │
│          │  └────────────────────────────────────────────────┘  │
├──────────┴──────────────────────────────────────────────────────┤
│  左侧侧边栏 (宽度: 280px)                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  LOGO: F.P.A.A.S                                          │  │
│  │  Financial Audit System                                   │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  [🚀 START ENGINE] - 主启动按钮                           │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │  Data Source                                              │  │
│  │  [输入框: ./data] [📂 浏览]                                │  │
│  ├──────────────────────────────────────────────────────────┤
│  │  Output Target                                             │  │
│  │  [输入框: ./output] [💾 浏览]                              │  │
│  ├──────────────────────────────────────────────────────────┤
│  │  Threshold Params                                         │  │
│  │  Cash Threshold (CNY): [50000]                            │  │
│  │  Time Window (Hours): [48]                                │  │
│  ├──────────────────────────────────────────────────────────┤
│  │  Analysis Modules (可勾选)                                 │  │
│  │  ☑ 资金画像分析                                            │  │
│  │  ☑ 疑点碰撞检测                                            │  │
│  │  ☑ 资产提取与分析                                          │  │
│  │  ☑ 数据验证                                                │  │
│  │  ☑ 资金穿透分析                                            │  │
│  │  ☑ 关联方资金分析                                          │  │
│  │  ☑ 多源数据碰撞                                            │  │
│  │  ☑ 借贷行为分析                                            │  │
│  │  ☑ 异常收入检测                                            │  │
│  │  ☑ 资金流向可视化                                          │  │
│  │  ☑ 机器学习风险预测                                        │  │
│  │  ☑ 时间序列分析                                            │  │
│  │  ☑ 线索聚合                                                │  │
│  ├──────────────────────────────────────────────────────────┤
│  │  Navigation                                                │  │
│  │  📊 Overview                                               │  │
│  │  🔍 Investigation                                          │  │
│  │  📁 Data Sources                                           │  │
│  │  📄 Reports                                                │  │
│  │  ⚙️  Settings                                              │  │
│  ├──────────────────────────────────────────────────────────┤
│  │  Last Run: 09:00:00                                        │  │
│  │  v2.4.0-stable                                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 响应式设计
- **桌面端 (≥1280px)**: 完整布局
- **平板端 (768px-1279px)**: 侧边栏可折叠
- **移动端 (<768px)**: 侧边栏抽屉式

---

## 三、左侧侧边栏配置项设计

### 3.1 核心配置项

#### 3.1.1 数据源配置
```typescript
interface DataSourceConfig {
  inputDirectory: string;      // 输入数据目录
  outputDirectory: string;     // 输出目录
}
```

#### 3.1.2 阈值参数
```typescript
interface ThresholdConfig {
  cashThreshold: number;       // 大额现金阈值 (默认: 50000)
  timeWindow: number;          // 时间窗口 (小时, 默认: 48)
}
```

#### 3.1.3 分析模块开关
```typescript
interface AnalysisModules {
  profileAnalysis: boolean;    // 资金画像分析
  suspicionDetection: boolean; // 疑点碰撞检测
  assetAnalysis: boolean;      // 资产提取与分析
  dataValidation: boolean;     // 数据验证
  fundPenetration: boolean;    // 资金穿透分析
  relatedParty: boolean;       // 关联方资金分析
  multiSourceCorrelation: boolean; // 多源数据碰撞
  loanAnalysis: boolean;       // 借贷行为分析
  incomeAnalysis: boolean;     // 异常收入检测
  flowVisualization: boolean;  // 资金流向可视化
  mlAnalysis: boolean;         // 机器学习风险预测
  timeSeriesAnalysis: boolean; // 时间序列分析
  clueAggregation: boolean;    // 线索聚合
}
```

### 3.2 侧边栏组件结构
```
Sidebar
├── LogoSection
├── StartEngineButton
├── DataSourceSection
│   ├── InputDirectoryInput
│   └── OutputDirectoryInput
├── ThresholdSection
│   ├── CashThresholdInput
│   └── TimeWindowInput
├── AnalysisModulesSection
│   └── ModuleToggleList
├── NavigationSection
│   └── NavItem[]
└── FooterSection
```

---

## 四、主内容区域设计

### 4.1 KPI 指标卡片

基于主程序输出，展示以下关键指标：

| 指标名称 | 数据来源 | 图标 | 颜色 |
|---------|---------|------|------|
| Analyzed Entities | persons + companies | Users | 蓝色 |
| Total Transactions | sum(len(df)) | Activity | 青色 |
| High Risk Funds | suspicious amount | ShieldAlert | 红色 |
| System Status | running state | Server | 绿色 |

### 4.2 标签页内容

#### 4.2.1 Overview（概览）
- **左侧**: 资金分布表格
  - 实体名称
  - 收入总额
  - 支出总额
- **右侧**: 交易趋势面积图
  - 时间轴
  - 交易量

#### 4.2.2 Risk Intel（风险情报）
- **筛选器**: Direct Transfers / Round Trip / Cash Anomaly
- **疑点列表**: 表格展示
  - 时间
  - 交易方
  - 金额
  - 风险等级
- **风险分布图**: 柱状图

#### 4.2.3 Graph View（图谱视图）
- 关联关系图（使用 D3.js 或 Cytoscape.js）
- 节点: 人员、公司
- 边: 资金往来
- 颜色编码: 风险等级

#### 4.2.4 Audit Report（审计报告）
- 报告下载按钮
- 报告预览区域
- 报告生成历史

### 4.3 实时日志控制台

#### 4.3.1 日志格式
```
[HH:MM:SS] [LEVEL] Message
```

#### 4.3.2 日志级别颜色
- **INFO**: 蓝色 (#3b82f6)
- **WARN**: 黄色 (#eab308)
- **ERROR**: 红色 (#ef4444)

#### 4.3.3 功能特性
- 自动滚动到底部
- 日志缓冲区限制（200条）
- 可复制日志内容
- 清空日志按钮

---

## 五、配色方案与视觉风格

### 5.1 配色方案（深色玻璃拟态）

```css
/* 主色调 */
--bg-root: #0f172a;              /* slate-950 - 背景深色 */
--bg-sidebar: #020617;           /* slate-950 darker - 侧边栏 */
--bg-card: rgba(15, 23, 42, 0.6); /* 玻璃拟态卡片 */

/* 边框色 */
--border-color: #1e293b;         /* slate-800 */

/* 文字色 */
--text-primary: #f8fafc;         /* slate-50 */
--text-secondary: #94a3b8;       /* slate-400 */

/* 强调色 */
--accent-blue: #3b82f6;          /* blue-500 */
--accent-cyan: #06b6d4;          /* cyan-500 */
--accent-red: #ef4444;           /* red-500 */
--accent-green: #22c55e;         /* green-500 */
--accent-warning: #eab308;       /* yellow-500 */

/* 渐变 */
--gradient-primary: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
--gradient-glow: 0 4px 15px -3px rgba(59, 130, 246, 0.4);
```

### 5.2 字体方案
- **无衬线字体**: Inter (UI 文本)
- **等宽字体**: JetBrains Mono (代码、日志)

### 5.3 视觉特效
- **玻璃拟态**: backdrop-blur-md + 半透明背景
- **发光效果**: box-shadow 渐变光晕
- **渐变按钮**: 蓝色到青色渐变
- **悬停动画**: transform translateY + 阴影增强

---

## 六、组件结构规划

### 6.1 组件树

```
App
├── Sidebar
│   ├── LogoSection
│   ├── StartEngineButton
│   ├── DataSourceSection
│   ├── ThresholdSection
│   ├── AnalysisModulesSection
│   ├── NavigationSection
│   └── FooterSection
├── MainContent
│   ├── Header
│   ├── KPICards
│   │   └── StatsCard[]
│   ├── TabNavigation
│   ├── TabContent
│   │   ├── OverviewTab
│   │   │   ├── FundDistributionTable
│   │   │   └── TransactionTrendChart
│   │   ├── RiskIntelTab
│   │   │   ├── RiskFilter
│   │   │   ├── SuspiciousActivityTable
│   │   │   └── RiskDistributionChart
│   │   ├── GraphViewTab
│   │   │   └── AssociationGraph
│   │   └── AuditReportTab
│   │       ├── ReportDownloadButton
│   │       └── ReportPreview
│   └── LogConsole
│       ├── LogHeader
│       └── LogContent
└── TopBar
```

### 6.2 组件职责

| 组件 | 职责 |
|-----|------|
| App | 根组件，状态管理 |
| Sidebar | 左侧配置面板 |
| MainContent | 主内容区域 |
| KPICards | KPI 指标展示 |
| TabNavigation | 标签页导航 |
| LogConsole | 实时日志控制台 |
| StatsCard | 单个指标卡片 |
| FundDistributionTable | 资金分布表格 |
| TransactionTrendChart | 交易趋势图表 |
| SuspiciousActivityTable | 疑点活动表格 |
| RiskDistributionChart | 风险分布图表 |
| AssociationGraph | 关联关系图 |

---

## 七、数据流与状态管理

### 7.1 状态结构

```typescript
interface AppState {
  // 配置状态
  config: {
    inputDirectory: string;
    outputDirectory: string;
    cashThreshold: number;
    timeWindow: number;
    analysisModules: AnalysisModules;
  };

  // 分析状态
  analysis: {
    isRunning: boolean;
    progress: number;
    currentPhase: string;
    lastRunTime: Date | null;
  };

  // 数据状态
  data: {
    persons: string[];
    companies: string[];
    profiles: Record<string, Profile>;
    suspicions: SuspicionResult;
    analysisResults: AnalysisResults;
  };

  // 日志状态
  logs: LogEntry[];

  // UI 状态
  ui: {
    activeTab: string;
    sidebarCollapsed: boolean;
  };
}
```

### 7.2 数据流

```
用户操作 (侧边栏配置)
    ↓
更新 config 状态
    ↓
点击 "START ENGINE"
    ↓
调用后端 API (Python main.py)
    ↓
接收实时日志流 (WebSocket/SSE)
    ↓
更新 logs 状态
    ↓
更新 analysis 状态 (进度、阶段)
    ↓
分析完成，接收结果数据
    ↓
更新 data 状态
    ↓
触发 UI 重新渲染 (KPI、图表、表格)
```

### 7.3 状态管理方案

使用 React Context + Hooks 进行状态管理：

```typescript
// contexts/AppContext.tsx
const AppContext = createContext<AppState | null>(null);

// hooks/useApp.ts
export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
}
```

---

## 八、与后端 API 交互方案

### 8.1 API 设计

#### 8.1.1 启动分析
```http
POST /api/analysis/start
Content-Type: application/json

{
  "inputDirectory": "./data",
  "outputDirectory": "./output",
  "cashThreshold": 50000,
  "timeWindow": 48,
  "analysisModules": {
    "profileAnalysis": true,
    "suspicionDetection": true,
    ...
  }
}

Response: 202 Accepted
{
  "analysisId": "uuid",
  "status": "started"
}
```

#### 8.1.2 获取分析状态
```http
GET /api/analysis/status/{analysisId}

Response: 200 OK
{
  "status": "running" | "completed" | "failed",
  "progress": 65,
  "currentPhase": "阶段3: 资金画像分析"
}
```

#### 8.1.3 获取分析结果
```http
GET /api/analysis/results/{analysisId}

Response: 200 OK
{
  "persons": ["张三", "李四"],
  "companies": ["公司A", "公司B"],
  "profiles": {...},
  "suspicions": {...},
  "analysisResults": {...}
}
```

#### 8.1.4 实时日志流
```http
GET /api/analysis/logs/{analysisId}
Accept: text/event-stream

Response: Server-Sent Events
data: {"time": "09:00:01", "level": "INFO", "msg": "System initialized..."}
data: {"time": "09:00:02", "level": "INFO", "msg": "Scanning data artifacts..."}
...
```

### 8.2 后端实现方案

#### 方案 A: FastAPI + WebSocket
```python
# backend/main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/analysis/start")
async def start_analysis(config: AnalysisConfig):
    # 启动分析任务
    pass

@app.websocket("/api/analysis/logs/{analysis_id}")
async def log_stream(websocket: WebSocket, analysis_id: str):
    # 实时推送日志
    pass
```

#### 方案 B: Flask + SSE
```python
# backend/app.py
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/api/analysis/start", methods=["POST"])
def start_analysis():
    # 启动分析任务
    pass

@app.route("/api/analysis/logs/<analysis_id>")
def log_stream(analysis_id):
    # SSE 流式响应
    def generate():
        for log in get_logs(analysis_id):
            yield f"data: {json.dumps(log)}\n\n"
    return Response(generate(), mimetype="text/event-stream")
```

### 8.3 推荐方案

**FastAPI + WebSocket**
- 原生支持异步
- WebSocket 双向通信
- 自动生成 API 文档
- 与 Python 主程序集成方便

---

## 九、实施计划

### 阶段 1: 基础架构搭建
- [ ] 配置 Tailwind CSS 主题
- [ ] 创建基础布局组件
- [ ] 实现侧边栏结构
- [ ] 实现主内容区域结构

### 阶段 2: 侧边栏开发
- [ ] 实现数据源配置组件
- [ ] 实现阈值参数组件
- [ ] 实现分析模块开关组件
- [ ] 实现导航菜单组件

### 阶段 3: 主内容区域开发
- [ ] 实现 KPI 指标卡片
- [ ] 实现标签页导航
- [ ] 实现 Overview 标签页
- [ ] 实现 Risk Intel 标签页
- [ ] 实现 Graph View 标签页
- [ ] 实现 Audit Report 标签页

### 阶段 4: 日志控制台开发
- [ ] 实现日志显示组件
- [ ] 实现自动滚动功能
- [ ] 实现日志缓冲区管理
- [ ] 实现日志级别颜色

### 阶段 5: 状态管理
- [ ] 创建 App Context
- [ ] 实现状态管理逻辑
- [ ] 实现配置持久化

### 阶段 6: 后端集成
- [ ] 创建 FastAPI 后端
- [ ] 实现 API 端点
- [ ] 实现 WebSocket 日志流
- [ ] 实现与主程序的集成

### 阶段 7: 测试与优化
- [ ] 功能测试
- [ ] 性能优化
- [ ] 响应式测试
- [ ] 用户体验优化

---

## 十、技术亮点

1. **现代化 UI**: 深色玻璃拟态设计，科技感十足
2. **实时反馈**: 类似 Antigravity 的实时日志输出
3. **模块化**: 清晰的组件结构，易于维护
4. **可配置**: 丰富的配置选项，满足不同分析需求
5. **可视化**: 丰富的图表展示，直观呈现分析结果
6. **响应式**: 支持多种屏幕尺寸

---

## 十一、参考设计

- **配色**: Vercel / Linear 深色主题
- **布局**: Antigravity 调试界面
- **组件**: shadcn/ui + Tailwind CSS
- **图表**: Recharts (React 生态)
- **图标**: Lucide React (现代化图标库)

---

## 十二、后续扩展

1. **用户认证**: 添加登录功能
2. **历史记录**: 保存分析历史
3. **报告模板**: 自定义报告模板
4. **导出功能**: 支持多种格式导出
5. **协作功能**: 多用户协作分析
6. **AI 助手**: 集成 AI 分析建议
