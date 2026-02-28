# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-25
**Commit:** af7f7e2
**Branch:** main

## OVERVIEW

穿云审计 (F.P.A.S) - 专业金融审计分析平台，用于资金流向分析、可疑交易检测、关联关系排查。
**Stack:** Python 3.9+ (FastAPI) + React 19.2 (TypeScript/Vite)

## STRUCTURE

```
cj-project/
├── api_server.py           # ⭐ 唯一入口 - FastAPI 服务
├── config.py               # 主配置 (951行，所有阈值/关键词)
├── detectors/              # 8个疑点检测器
├── classifiers/            # 交易分类引擎
├── schemas/                # Pydantic 数据模型
├── knowledge/              # YAML 行业知识库
├── learners/               # ML 学习器
├── dashboard/              # React 前端
├── output/
│   ├── cleaned_data/       # 🔴 成品数据 (唯一真理源)
│   ├── analysis_cache/     # 分析缓存 (JSON)
│   └── analysis_results/   # 报告输出
└── scripts/                # 工具脚本 (43个)
```

## WHERE TO LOOK

| 任务 | 位置 | 说明 |
|------|------|------|
| 添加检测器 | `detectors/` | 继承 `BaseDetector` |
| 修改阈值 | `config.py` + `config/risk_thresholds.yaml` | 双层配置 |
| 添加API | `api_server.py` | 单文件，按功能分section |
| 报告模板 | `templates/report_v3/` | Jinja2 HTML |
| 前端组件 | `dashboard/src/components/` | React + TailwindCSS |

## CONVENTIONS

### Python
- 文件头: `#!/usr/bin/env python3` + `# -*- coding: utf-8 -*-`
- 命名: snake_case (函数/变量), PascalCase (类), UPPER_SNAKE_CASE (常量)
- 类型注解: 必须
- 中文注释/文档: 允许

### 数据流铁律
```
🚨 任何API必须从 cleaned_data 读取，禁止虚构数据
📌 Excel里有什么，界面就显示什么
```

### Git提交
```
<type>: <subject>
feat/fix/docs/refactor/perf
```

## ANTI-PATTERNS (本项目)

- **禁止** `main.py` 作为入口 (已废弃)
- **禁止** 在 config 中硬编码案件特定数据
- **禁止** 空异常处理 `except: pass`
- **禁止** TODO/FIXME 残留在生产代码

## COMMANDS

```bash
# 启动后端
python api_server.py              # http://localhost:8000

# 启动前端
cd dashboard && npm run dev       # http://localhost:5173

# 测试
pytest tests/

# 类型检查 (前端)
cd dashboard && npm run type-check
```

## 启动服务 (AI 助手专用)

```bash
# 后台启动后端 (使用 & 而非 start /B)
python api_server.py &

# 后台启动前端
cd dashboard && npm run dev &
```

⚠️ **重要**: 当前环境是 Git Bash/Unix-like shell，使用 `&` 后台运行。
- **禁止**使用 `start /B` (Windows cmd 命令，不兼容)
- **禁止**阻塞式启动 (会导致超时)

## KEY THRESHOLDS

| 参数 | 值 | 说明 |
|------|-----|------|
| LARGE_CASH_THRESHOLD | 50,000 | 大额现金阈值(元) |
| CASH_TIME_WINDOW_HOURS | 48 | 现金碰撞窗口(小时) |
| LOAN_MIN_AMOUNT | 5,000 | 借贷分析最低金额 |
| INCOME_HIGH_RISK_MIN | 50,000 | 高风险收入阈值 |

## NOTES

- `investigation_report_builder.py` (416KB) 和 `api_server.py` (124KB) 是最大文件，考虑拆分
- 无 CI/CD 配置，手动部署
- 前端深色玻璃态主题，主色 `#3b82f6`

---

## 🔧 路径修复计划 (2026-02-27)

### 问题根源

打包后在其他Windows电脑运行失败，原因：
1. **相对路径依赖工作目录** - `./data`, `./output` 在不同工作目录下指向错误
2. **`__file__` 打包后指向临时目录** - PyInstaller 解压到 `_MEIxxxx` 临时目录
3. **前端硬编码 localhost** - API 地址固定为 `http://localhost:8000`

### 修复方案

#### Phase 1: 创建统一路径管理器 (新建 `paths.py`)

```python
# paths.py
import os
import sys
from pathlib import Path

def get_app_root() -> Path:
    """获取应用程序根目录（兼容开发环境和打包环境）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path(__file__).parent.resolve()

def get_data_dir() -> Path:
    return get_app_root() / 'data'

def get_output_dir() -> Path:
    return get_app_root() / 'output'

def get_config_dir() -> Path:
    return get_app_root() / 'config'

def get_cache_path() -> Path:
    return get_output_dir() / 'analysis_cache.json'

# 导出常量
APP_ROOT = get_app_root()
DATA_DIR = get_data_dir()
OUTPUT_DIR = get_output_dir()
CONFIG_DIR = get_config_dir()
```

#### Phase 2: 修改 config.py

| 行号 | 当前代码 | 修改为 |
|------|---------|--------|
| 558 | `DATA_DIR: str = './data'` | 从 paths 导入 |
| 559 | `OUTPUT_DIR: str = './output'` | 从 paths 导入 |
| 730 | `CACHE_PATH: str = "./output/analysis_cache.json"` | 从 paths 导入 |

#### Phase 3: 修改 config_loader.py

| 行号 | 当前代码 | 修改为 |
|------|---------|--------|
| 35 | `DEFAULT_CONFIG_PATH = 'config/risk_thresholds.yaml'` | 使用 `paths.get_config_dir() / 'risk_thresholds.yaml'` |

#### Phase 4: 修改 api_server.py (30+ 处)

**核心修改**: 所有硬编码路径改为使用 paths 模块

| 行号范围 | 修改内容 |
|---------|---------|
| 165 | 默认值从 `"output"` 改为 `str(paths.OUTPUT_DIR)` |
| 653-654 | 使用 `paths.OUTPUT_DIR` |
| 1774, 1803, 1883, 1932, 1949 | `os.path.join("output", ...)` → `os.path.join(str(paths.OUTPUT_DIR), ...)` |
| 1976, 2010, 2047, 2073, 2329 | `PrimaryTargetsService(data_dir="./data", output_dir="./output")` → 使用 paths |
| 2189-2190, 2269-2270 | `os.path.abspath("output/...")` → 使用 paths |
| 2345, 2457, 2544, 2739 | `load_investigation_report_builder("./output")` → 使用 paths |
| 2614 | 已使用 base_dir，需确保 base_dir 正确 |
| 2696 | `os.path.join("output", ...)` → 使用 paths |
| 2754-2756 | `create_output_directories("./output")` → 使用 paths |
| 2910-2913 | 全部硬编码 → 使用 paths |

#### Phase 5: 修改其他文件

| 文件 | 修改内容 |
|------|---------|
| `wealth_account_analyzer.py:410` | 测试块改为动态路径或删除 |
| `flow_visualizer.py:311-312` | 使用 paths 获取 vis-network 路径 |
| `investigation_report_builder.py:7242` | 使用 paths |
| `template_engine.py:25` | 使用 paths |

#### Phase 6: 前端修改

**保留用户自定义能力**：
- 前端界面保持 `inputDirectory` 和 `outputDirectory` 输入框
- 如果用户不填 → 后端使用默认路径（程序所在目录）
- 如果用户填写 → 后端使用用户指定的路径

**添加目录选择按钮**（后端 API）：
```python
@app.get("/api/select-folder")
async def select_folder():
    """调用系统原生文件夹选择对话框"""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="选择目录")
    root.destroy()
    return {"path": folder}
```

#### Phase 7: 清理已删除文件

以下临时脚本已删除（2026-02-27）：
- `scripts/` 目录 (43个文件) - 全部临时分析脚本
- `archives/` 目录 (3个文件) - 废弃代码
- 根目录临时脚本: `simulate_frontend.py`, `verify_fixes.py`, `generate_html.py` 等11个文件

### 验证清单

- [x] 开发环境运行正常
- [ ] 打包后运行正常
- [ ] 不同工作目录启动正常
- [x] 前端目录选择功能正常
- [x] 配置文件加载正常
- [x] 缓存读写正常

---

## 📋 工作日志 (2026-02-27)

### 完成的任务

#### 1. 路径修复计划实施 ✅

**新建文件：**
- `paths.py` - 统一路径管理器，兼容开发环境和 PyInstaller 打包环境

**修改文件：**
| 文件 | 修改内容 |
|------|---------|
| `config.py` | 导入 paths 模块，DATA_DIR/OUTPUT_DIR/CACHE_PATH 改为动态路径 |
| `config_loader.py` | DEFAULT_CONFIG_PATH 使用 paths.get_config_dir() |
| `api_server.py` | 30+ 处硬编码路径改为使用 paths 模块，调整缓存保存顺序 |
| `flow_visualizer.py` | vis-network 路径使用 APP_ROOT |
| `investigation_report_builder.py` | 模板目录和默认参数使用 paths，修复 salary_by_year 类型错误 |
| `template_engine.py` | TEMPLATE_DIR 使用 paths |
| `financial_profiler.py` | 修复 IndexError (空 group 检查) |

**新增 API：**
- `POST /api/select-folder` - 调用系统目录选择对话框
- `GET /api/default-paths` - 获取默认路径配置

#### 2. 代码清理 ✅

**删除的文件：**
| 目录/文件 | 数量 | 原因 |
|----------|------|------|
| `scripts/` | 43个 | 全部临时分析脚本 |
| `archives/` | 3个 | 废弃代码 |
| 根目录临时脚本 | 11个 | simulate_frontend.py, verify_fixes.py, generate_html.py 等 |

#### 3. Bug 修复 ✅

| 问题 | 原因 | 修复 |
|------|------|------|
| 报告显示 0 名核心人员 | 缓存在报告生成后才保存 | 调整缓存保存顺序，在报告生成前先保存基础缓存 |
| salary_by_year 类型错误 | dict 被当作数字进行除法 | 检查类型并提取 total 字段 |
| 公司 profile 生成失败 | `group.iloc[0]` IndexError | 添加空 group 检查 |
| 图谱缓存失败 | `GRAPH_MAX_NODES` 配置缺失 | 添加到 config.py |
| 目录选择对话框初始目录错误 | 未传入当前目录 | 传入当前配置目录作为 initialDir |
| 输出目录按钮图标是磁盘 | 使用了 HardDrive 图标 | 改为 FolderOpen 图标 |

#### 4. 验证结果 ✅

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 核心人员 | 0 名 | 4 名 |
| 关联公司 | 0 家 | 2 家 |
| 银行流水 | 0 条 | 23459 条 |
| profiles.json | 4 个实体 | 6 个实体（含公司） |
| 图谱缓存 | 失败 | 成功 |
| 报告生成 | 空/报错 | 完整 |

### 待办事项

- [ ] 打包测试：在不同 Windows 电脑上验证路径修复效果
- [ ] 前端 API 地址配置：支持动态配置而非硬编码 localhost
- [ ] 考虑拆分 `investigation_report_builder.py` (416KB) 和 `api_server.py` (124KB)
