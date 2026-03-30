# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-30
**Commit:** cb35a16
**Branch:** main
**Mode:** Update (existing conventions preserved)

---

## OVERVIEW

穿云审计 (F.P.A.S) - 资金穿透与关联排查系统。Python 3.8+ FastAPI 后端 + React 19 TypeScript 前端。核心功能: 交易数据清洗、疑点检测、资金画像、借贷分析、关联方穿透、ML风险预测。

**唯一入口**: `api_server.py` (`main.py` 已废弃)

**当前交付主方向**:
- 最终目标是 `Windows 单机离线 one-folder 包` (portable-runtime bundle)
- 开发态仍可使用 `python api_server.py` + `cd dashboard && npm run dev`
- 交付态必须由后端直接承载前端生产构建，访问路径为 `http://127.0.0.1:8000/dashboard/`
- 新增功能时必须默认满足：`无互联网依赖`、`无 Node 开发服务器依赖`、`无硬编码绝对路径`

---

## STRUCTURE

```
project/
├── api_server.py                  # ⭐ 唯一入口 (9211行, 35个API端点)
├── config.py                      # 全局阈值参数
├── config_loader.py               # YAML 配置加载
├── paths.py                       # 统一路径管理 (dev/portable/PyInstaller)
├── data_cleaner.py                # 数据清洗管道 (1910行)
├── financial_profiler.py          # 资金画像 (5835行)
├── suspicion_engine.py            # 疑点检测协调
├── investigation_report_builder.py # 报告构建 (17453行 - 最大文件)
├── report_quality_guard.py        # 报告质量门控
├── *_extractor.py                 # 数据提取器 (16+)
├── *_analyzer.py                  # 数据分析器 (14+)
├── adapters/                      # 数据格式适配器
├── classifiers/                   # 交易分类引擎
├── detectors/                     # 疑点检测器插件 (8个)
├── schemas/                       # Pydantic 数据模型
├── learners/                      # ML 学习模块
├── knowledge/                     # 行业知识库 (YAML)
├── utils/                         # 工具函数
├── report_config/                 # 报告短语模板 + 风险阈值
├── config/                        # 调查配置模板
├── templates/                     # HTML 报告模板 (Jinja2)
├── tests/                         # pytest 测试 (48文件)
├── docs/                          # 文档 + 变更日志
├── dist/fpas-offline/             # Windows 离线交付构建产物
└── dashboard/                     # React 前端 (Vite 7 + React 19)
    ├── src/components/            # UI 组件 (13 TSX)
    ├── src/contexts/AppContext.tsx # 全局状态 (1078行)
    ├── src/services/api.ts        # HTTP/WebSocket (830行)
    ├── src/types/index.ts         # TS 类型 (754行)
    └── dist/                      # 生产构建 (后端承载)
```

---

## WHERE TO LOOK

| 任务 | 位置 | 关键文件 |
|------|------|--------|
| 修改 API 端点 | 根目录 | `api_server.py` (35端点) |
| 修改配置 | 根目录 | `config.py`, `config_loader.py` |
| 路径管理 | 根目录 | `paths.py` |
| 添加检测器 | `detectors/` | 继承 `BaseDetector` |
| 添加分类器 | `classifiers/` | 实现 `classify()` |
| 修改数据模型 | `schemas/` | 继承 `BaseModel` |
| 修改前端组件 | `dashboard/src/components/` | `*.tsx` |
| 工具函数 | `utils/` | `safe_types.py` (详见 [utils/AGENTS.md](utils/AGENTS.md)) |
| 报告模板 | `templates/` | Jinja2 HTML 模板 |
| 报告配置 | `report_config/` | 短语模板, 风险阈值 |
| 调查配置 | `config/` | 模板, 主要目标 |
| 测试 | `tests/` | `test_*.py` (48文件) |
| 知识库 | `knowledge/` | 4个 YAML 文件 |
| 打包脚本 | 根目录 | `build_windows_package.py` |

---

## CODE MAP

| 符号 | 类型 | 位置 | 职责 |
|------|------|------|------|
| `api_server.py` | FastAPI | 根目录 | 唯一入口, 35 API端点, WebSocket, /dashboard/承载 |
| `config.py` | 配置 | 根目录 | 全局阈值 (87+文件导入) |
| `paths.py` | 路径 | 根目录 | APP_ROOT, DATA_DIR, OUTPUT_DIR (3种运行模式) |
| `data_cleaner.py` | 清洗 | 根目录 | 数据清洗管道 |
| `financial_profiler.py` | 分析 | 根目录 | 资金画像生成 |
| `suspicion_engine.py` | 检测 | 根目录 | 疑点检测协调 |
| `clue_aggregator.py` | 聚合 | 根目录 | 线索聚合引擎 |
| `investigation_report_builder.py` | 报告 | 根目录 | report_package + 正式报告构建 |
| `report_quality_guard.py` | 质控 | 根目录 | 报告质量门控 |
| `BaseDetector` | 基类 | `detectors/` | 检测器抽象基类 (8个实现) |
| `CategoryEngine` | 引擎 | `classifiers/` | 分类引擎入口 (优先级: 工资>理财>内部转账) |
| `safe_str/float/int` | 函数 | `utils/safe_types.py` | 类型安全转换 (16+提取器使用) |
| `AppContext` | Context | `dashboard/src/contexts/` | 全局状态管理 |
| `api` | Service | `dashboard/src/services/` | HTTP/WebSocket通信层 |

---

## COMMANDS

```bash
# 启动后端 (唯一入口)
python api_server.py

# 启动前端 (仅开发态)
cd dashboard && npm run dev

# 运行测试
pytest tests/ -v

# 类型检查
cd dashboard && npm run type-check

# 构建前端生产产物（供后端 /dashboard/ 承载）
cd dashboard && npm run build

# Windows 离线打包（应在 Windows 机器上执行）
python build_windows_package.py

# Windows 离线打包预检 (macOS 可执行)
python build_windows_package.py --preflight
```

---

## NOTES

### 数据源铁律
**所有 API 必须从 `output/cleaned_data/` 读取** - 禁止数据造假

### 三层输出
1. `output/cleaned_data/` — 事实层 (交易原始数据)
2. `output/analysis_cache/` — 语义层 (画像、疑点、缓存)
3. `output/analysis_results/` — 交付层 (HTML/TXT/XLSX 报告)

### 批量文件说明
- 根目录 ~97 个 Python 文件 (扁平结构，建议重构)
- `investigation_report_builder.py` 17453 行 (最大文件)
- `api_server.py` 9211 行 (35个API端点)
- GitHub Actions CI: `.github/workflows/release-windows-package.yml`

### 废弃代码
- `main.py` 已废弃，使用 `api_server.py`

### Windows 离线交付约束
- 如果任务涉及运行形态、启动方式、打包、路径处理、依赖引入，必须优先考虑 `Windows 单机离线 one-folder 包`
- 不要再把 `npm run dev` 视为最终交付方案，它只用于开发
- 前端生产构建由后端 `GET /dashboard/` 提供
- 环境变量: `FPAS_BROWSER_EXE`, `FPAS_AUTO_OPEN_BROWSER`, `FPAS_PORT`
- 优先阅读 `WINDOWS_OFFLINE_DELIVERY.md`

### 质量门控链
`report_package.json → report_quality_guard.py → html_report_consistency_audit.py → 前端展示`

---

## CONVENTIONS

### 🔧 工具函数统一规范

**⚠️ 重要**: 所有数据提取器必须使用统一的工具函数模块，**禁止**在各自文件中重复定义！

**模块**: `utils/safe_types.py`

```python
from utils.safe_types import (
    safe_str,           # → Optional[str]
    safe_float,         # → Optional[float]
    safe_int,           # → Optional[int]
    safe_date,          # → Optional[str] (YYYY-MM-DD)
    safe_datetime,      # → Optional[str] (YYYY-MM-DD HH:MM:SS)
    extract_id_from_filename,  # 从文件名提取身份证
    normalize_column_name,     # 标准化列名
)
```

### 路径管理
- **禁止硬编码绝对路径** — 使用 `paths.py` 模块
- 三种运行模式: `dev` / `portable-runtime` / `PyInstaller`

### 类型注解
- 所有 `safe_*` 返回 `Optional[T]`，转换失败返回 `None`
- Pydantic 模型使用 `Field` + `field_validator`

### 测试
- 无 conftest.py，每个测试文件手动 `sys.path.insert`
- 类结构: `class TestClassName:` + `def test_*():`
- 性能测试: `assert elapsed < N` 模式
