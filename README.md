# 穿云审计 (F.P.A.S)

<div align="center">
  
  <h3>🔍 资金穿透与关联排查系统</h3>
  <p>Fund Penetration & Association Screening</p>
  
  <p>
    <img src="https://img.shields.io/badge/version-4.5.0-blue" alt="Version" />
    <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/React-19.2-61DAFB?logo=react&logoColor=white" alt="React" />
    <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white" alt="TypeScript" />
    <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/Vite-7.x-646CFF?logo=vite&logoColor=white" alt="Vite" />
    <img src="https://img.shields.io/badge/License-MIT-green" alt="License" />
  </p>
  
  <p><strong>专业的金融审计分析平台</strong>，帮助审计人员高效完成资金流向分析、可疑交易检测、关联关系排查</p>
  
</div>

---

## ✨ 功能特性

### 🎯 核心分析能力

| 模块 | 功能描述 |
|------|---------|
| **资金画像** | 自动生成实体的收支画像、现金占比、交易频次等关键指标 |
| **借贷分析** | 识别规律性还款、无还款借贷、网贷平台交易、双向往来关系 |
| **收入检测** | 发现大额单笔收入、来源不明收入、规律非工资收入、疑似分期受贿 |
| **疑点碰撞** | 检测核心人员与涉案公司的直接往来 |
| **现金碰撞** | 识别同一时段的大额ATM取存配对 |
| **资金穿透** | 多层次资金流向追踪与可视化 |
| **关联方分析** | 发现隐藏的关联交易关系 |
| **ML风险预测** | 基于机器学习的异常交易预警 |
| **时序分析** | 周期性收入、资金突变、延迟转账检测 |
| **线索聚合** | 以实体为中心的风险评分与证据包视图 |

### 📊 专业可视化 Dashboard

- **深色玻璃态主题** - 流畅动画、现代化 UI 设计
- **审计核心指标** - 点击卡片即可钻取查看详细记录
- **两级数据钻取** - 分类汇总 → 明细记录
- **资金流向图谱** - vis-network 交互式关系可视化
- **实时日志推送** - WebSocket 实时显示分析进度
- **数据溯源** - 每条记录标注来源文件和行号

### 📝 审计报告输出

- **Excel 核查底稿** (`资金核查底稿.xlsx`) - 完整的多工作表分析报告
- **HTML 综合报告** - 详细的文字分析报告
- **资金流向图** (`资金流向可视化.html`) - 交互式关系图，可离线查看

### 🔒 离线单机运行

本系统**完全支持离线/单机环境运行**：
- 所有前端资源本地打包（无 CDN 依赖）
- 生成的 HTML 报告可离线查看
- 适用于保密环境下的审计工作

---

## 🚀 快速开始

### 环境要求

- **Python** 3.9+
- **Node.js** 18+
- **npm** 9+

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/cjian8888/cj-project.git
cd cj-project

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装前端依赖
cd dashboard
npm install
cd ..
```

### 启动系统

**推荐方式：Dashboard 可视化界面**

```bash
# 终端 1：启动后端 API 服务
python api_server.py

# 终端 2：启动前端开发服务器
cd dashboard
npm run dev
```

访问 **http://localhost:5173** 打开 Dashboard。

**命令行方式**

```bash
python main.py --input ./data --output ./output
```

---

## 📁 项目结构

```
cj-project/
├── dashboard/              # React 前端 Dashboard
│   ├── src/
│   │   ├── components/     # UI 组件
│   │   ├── contexts/       # 全局状态管理
│   │   ├── services/       # API 服务层
│   │   ├── utils/          # 工具函数
│   │   └── types/          # TypeScript 类型定义
│   └── package.json
├── output/                 # 分析输出目录
│   ├── cleaned_data/       # 🔴 成品数据 (唯一真理源)
│   │   ├── 个人/           # 个人合并流水 Excel
│   │   └── 公司/           # 公司合并流水 Excel
│   ├── analysis_cache/     # 分析缓存 (加速加载)
│   └── analysis_results/   # 报告输出
├── api_server.py           # FastAPI 后端服务
├── main.py                 # 命令行入口
├── config.py               # 配置参数
├── data_cleaner.py         # 数据清洗
├── financial_profiler.py   # 资金画像
├── suspicion_detector.py   # 疑点检测
├── loan_analyzer.py        # 借贷分析
├── income_analyzer.py      # 收入分析
├── time_series_analyzer.py # 时序分析
├── clue_aggregator.py      # 线索聚合
├── report_generator.py     # 报告生成
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
| `INCOME_REGULAR_MIN` | 10,000 | 规律性收入最低金额 (元) |

### 数据流铁律

```
┌──────────────────────────────────────────────────────────────────┐
│  🚨 铁律：任何 API 接口都必须基于 cleaned_data 进行读取和计算     │
│  📌 口号：Excel 里有什么，界面就显示什么；Excel 里没有的，绝不许瞎编  │
└──────────────────────────────────────────────────────────────────┘
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
| Vite | 7.x | 构建工具 |
| TailwindCSS | 4.x | 样式框架 |
| Recharts | 3.x | 数据可视化 |
| vis-network | 10.x | 资金流向图谱 |
| Lucide React | - | 图标库 |

---

## 📝 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 获取完整版本历史。

### 最近版本

#### [v4.5.0] - 2026-01-19
- 🔧 **快捷导航优化**：折叠按钮添加文字提示，增强视觉反馈
- 🐛 **修复黑屏问题**：解决"疑似分期受贿"子菜单点击后渲染错误
- ⚡ **构建优化**：简化构建流程，提升开发效率

#### [v4.4.0] - 2026-01-18
- 🔧 **代码质量审计**：执行 P0-P5 六阶段系统性改进
- ✅ 操作审计日志、节假日服务、Neo4j 适配器
- ✅ 报告追加账户/银行/Excel 文件路径，便于人工复核

#### [v4.3.0] - 2026-01-17
- 🎯 **数据铁律重构**：`/api/results` 接口改为从缓存文件读取
- ✅ 新增分析缓存机制 (`output/analysis_cache/`)

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献规范。

### 提交规范

```
<type>(<scope>): <subject>

feat: 新功能
fix: 修复 bug
docs: 文档更新
refactor: 代码重构
perf: 性能优化
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
