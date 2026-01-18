# 穿云审计 (F.P.A.S)

<div align="center">
  
  <h3>资金穿透与关联排查系统</h3>
  <p>Fund Penetration & Association Screening</p>
  
  <p>
    <img src="https://img.shields.io/badge/version-4.4.0-blue" alt="Version" />
    <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/React-19.2-61DAFB?logo=react&logoColor=white" alt="React" />
    <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white" alt="TypeScript" />
    <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/License-MIT-green" alt="License" />
  </p>
  
  <p>专业的金融审计分析平台，帮助审计人员高效完成资金流向分析、可疑交易检测、关联关系排查</p>
  
</div>

---

## 📋 目录

- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [项目结构](#-项目结构)
- [配置说明](#️-配置说明)
- [技术栈](#-技术栈)
- [更新日志](#-更新日志)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

---

## ✨ 功能特性

### 🔍 核心分析能力

| 功能模块 | 描述 |
|---------|------|
| **资金画像分析** | 自动生成实体的资金收支画像 |
| **疑点碰撞检测** | 识别个人与企业间的异常直接转账 |
| **现金碰撞分析** | 检测同一时段的大额现金存取巧合 |
| **资金穿透追踪** | 多层次资金流向追踪与可视化 |
| **关联方分析** | 发现隐藏的关联交易关系 |
| **借贷行为识别** | 识别民间借贷和网贷平台交易 |
| **异常收入检测** | 发现来源不明的大额收入 |
| **ML 风险预测** | 基于机器学习的异常交易预警 |
| **时序分析** | 周期性收入、资金突变、延迟转账检测 |
| **线索聚合** | 以实体为中心的证据包视图 |

### 📊 专业可视化 Dashboard

- **现代化深色主题** - 玻璃态效果、流畅动画
- **实时数据可视化** - Recharts 图表展示资金趋势
- **资金流向图谱** - vis-network 交互式关系图
- **可疑交易高亮** - 风险等级标注与详情查看
- **实时日志推送** - WebSocket 实时显示分析进度
- **响应式设计** - 适配桌面和平板设备

### 📝 审计报告输出

- **Excel 核查底稿** - 完整的分析结果工作表
- **HTML 综合报告** - 详细的文字分析报告  
- **资金流向图** - 交互式资金关系可视化
- **可追溯信息** - 每条异常记录标注对应的 Excel 文件和账户

### 🔒 离线单机运行

本系统**完全支持离线/单机环境运行**，无任何外部网络依赖：
- 所有前端资源本地加载（vis-network 等库已内联）
- 生成的 HTML 报告可离线查看
- 适用于保密环境下的审计工作

---

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- npm 或 pnpm

### 安装步骤

```bash
# 克隆项目
git clone https://github.com/your-org/fpas.git
cd fpas

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd dashboard
npm install
```

### 启动系统

**方式一：使用 Dashboard（推荐）**

```bash
# 终端 1：启动后端 API
python api_server.py

# 终端 2：启动前端
cd dashboard
npm run dev
```

访问 http://localhost:5173 打开 Dashboard。

**方式二：命令行执行**

```bash
python main.py --input ./data --output ./output
```

---

## 📁 项目结构

```
fpas/
├── dashboard/              # React 前端 Dashboard
│   ├── src/
│   │   ├── components/     # UI 组件
│   │   ├── contexts/       # 状态管理
│   │   ├── services/       # API 服务
│   │   └── types/          # TypeScript 类型
│   └── package.json
├── output/                 # 分析输出目录
│   ├── cleaned_data/       # 清洗后的成品数据 (唯一真理源)
│   │   ├── 个人/           # 个人流水 Excel
│   │   └── 公司/           # 公司流水 Excel
│   ├── analysis_cache/     # 分析缓存 (v4.3.0+)
│   └── analysis_results/   # 报告输出
├── api_server.py           # FastAPI 后端服务
├── main.py                 # 命令行入口
├── config.py               # 配置参数
├── data_cleaner.py         # 数据清洗
├── financial_profiler.py   # 资金画像
├── suspicion_detector.py   # 疑点检测
├── fund_penetration.py     # 资金穿透
├── loan_analyzer.py        # 借贷分析
├── income_analyzer.py      # 收入分析
├── time_series_analyzer.py # 时序分析
├── clue_aggregator.py      # 线索聚合
├── report_generator.py     # 报告生成
├── audit_logger.py         # 操作审计日志 (v4.4.0+)
├── holiday_service.py      # 节假日服务 (v4.4.0+)
├── graph_adapter.py        # Neo4j 适配器 (v4.4.0+)
├── name_normalizer.py      # 对手方标准化 (v4.4.0+)
├── CHANGELOG.md            # 变更日志
├── CONTRIBUTING.md         # 贡献指南
└── requirements.txt        # Python 依赖
```

---

## ⚙️ 配置说明

### 核心阈值参数 (`config.py`)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `LARGE_CASH_THRESHOLD` | 50,000 | 大额现金交易阈值 (元) |
| `CASH_TIME_WINDOW_HOURS` | 48 | 现金碰撞时间窗口 (小时) |
| `LOAN_MIN_AMOUNT` | 5,000 | 借贷分析最低金额 (元) |
| `INCOME_HIGH_RISK_MIN` | 50,000 | 高风险收入阈值 (元) |

### 数据流铁律

```
┌──────────────────────────────────────────────────────────────────┐
│  铁律：任何 API 接口都必须基于 cleaned_data 进行读取和计算        │
│  口号：Excel 里有什么，界面就显示什么；Excel 里没有的，绝不许瞎编  │
└──────────────────────────────────────────────────────────────────┘
```

### 环境变量

```env
# .env.development
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

---

## 🔧 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.9+ | 核心分析引擎 |
| Pandas | 2.0+ | 数据处理 |
| FastAPI | 0.100+ | REST API 服务 |
| WebSocket | - | 实时通信 |
| NetworkX | - | 图论分析 |
| Scikit-learn | - | 机器学习 |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19.2 | UI 框架 |
| TypeScript | 5.9 | 类型安全 |
| Vite | 6.3 | 构建工具 |
| TailwindCSS | 4.x | 样式框架 |
| Recharts | - | 数据可视化 |
| vis-network | - | 资金流向图谱（本地内联） |
| Lucide React | - | 图标库 |

---

## 📝 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 获取完整的版本更新历史。

### 最近更新

#### [v4.4.0] - 2026-01-18
- 🔧 **代码质量审计**：执行 P0-P5 六阶段系统性改进
- ✅ P0 止血：恢复流水号去重、图谱累计金额
- ✅ P1 加固：对手方名称标准化、风险权重调整
- ✅ P2 优化：Parquet 存储、缓存哈希校验、规则 YAML 化
- ✅ P3 演进：操作审计日志、节假日服务、Neo4j 适配器
- ✅ P4 报告：家庭闭环识别、从摘要提取对手方
- ✅ P5 追溯：报告追加账户/银行/Excel 文件路径，便于人工复核

#### [v4.3.0] - 2026-01-17
- 🎯 **数据铁律重构**：`/api/results` 接口改为从缓存文件读取
- ✅ 新增分析缓存机制 (`output/analysis_cache/`)
- ✅ 实现 cleaned_data 一致性校验

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献规范。

### 提交规范

```
<type>(<scope>): <subject>

feat: 新功能
fix: 修复 bug
docs: 文档更新
refactor: 代码重构
perf: 性能优化
test: 测试相关
chore: 构建/工具链
```

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

---

<div align="center">
  <p>
    <strong>穿云审计</strong> - 穿透资金迷雾，洞察财务真相
  </p>
  <p>
    <sub>Built with ❤️ for auditors</sub>
  </p>
</div>
